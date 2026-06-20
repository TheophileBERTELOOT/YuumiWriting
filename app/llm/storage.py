from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class LLMAnalysisStorage:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.cache_dir = self.project_root / "AnalysesLLM"

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _source_key(self, source_path: Path) -> str:
        resolved = source_path.resolve()
        try:
            identity = resolved.relative_to(self.project_root).as_posix()
        except ValueError:
            identity = str(resolved)
        digest = hashlib.sha256(identity.casefold().encode("utf-8")).hexdigest()[:16]
        readable = source_path.stem[:45] or "document"
        return f"{readable}_{digest}.json"

    def cache_path(self, source_path: Path) -> Path:
        return self.cache_dir / self._source_key(source_path)

    def load(self, source_path: Path) -> dict | None:
        path = self.cache_path(source_path)
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("analyses"), dict):
            raise ValueError(f"Cache LLM invalide : {path.name}")
        return value

    def is_current(
        self,
        source_path: Path,
        text: str,
        expected_keys: set[str],
        prompt_version: int,
    ) -> bool:
        cached = self.load(source_path)
        return bool(
            cached
            and cached.get("source_sha256") == self.content_hash(text)
            and cached.get("prompt_version") == prompt_version
            and expected_keys.issubset(cached["analyses"])
        )

    def save(
        self,
        source_path: Path,
        text: str,
        model: str,
        analyses: dict[str, dict],
        prompt_version: int,
    ) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_path(source_path)
        payload = {
            "version": 1,
            "source_path": str(source_path.resolve()),
            "source_sha256": self.content_hash(text),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "prompt_version": prompt_version,
            "analyses": analyses,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path
