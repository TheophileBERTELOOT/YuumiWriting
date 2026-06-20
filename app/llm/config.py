from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


CONFIG_FILENAME = "openai_config.json"


@dataclass(frozen=True, slots=True)
class OpenAIConfig:
    api_key: str
    project: str
    model: str
    path: Path

    @classmethod
    def load(cls, project_root: Path) -> "OpenAIConfig":
        """Charge la configuration partagée depuis le parent du roman."""
        path = project_root.resolve().parent / CONFIG_FILENAME
        if not path.exists():
            raise FileNotFoundError(
                f"Configuration OpenAI absente : {path}."
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Configuration OpenAI invalide : {path}.") from exc
        if not isinstance(payload, dict):
            raise ValueError("La configuration OpenAI doit être un objet JSON.")

        api_key = str(payload.get("api_key", "")).strip()
        project = str(payload.get("project", "")).strip()
        model = str(payload.get("model", "")).strip()
        if not api_key or api_key == "COLLEZ_VOTRE_CLE_ICI":
            raise ValueError(f"Renseignez `api_key` dans {path}.")
        if not project or project == "COLLEZ_VOTRE_PROJECT_ID_ICI":
            raise ValueError(f"Renseignez `project` dans {path}.")
        if not model:
            raise ValueError(f"Renseignez `model` dans {path}.")
        return cls(api_key, project, model, path)
