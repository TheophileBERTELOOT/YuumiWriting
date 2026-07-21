from __future__ import annotations

import re
import unicodedata
import html
import json
import ssl
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi


_COMMON_SYNONYMS: dict[str, tuple[str, ...]] = {
    "beau": ("bel", "belle", "joli", "magnifique", "splendide", "superbe"),
    "belle": ("beau", "jolie", "magnifique", "splendide", "superbe"),
    "grand": ("vaste", "immense", "énorme", "majeur", "considérable"),
    "petit": ("minuscule", "court", "modeste", "faible"),
    "haut": ("élevé", "grand", "sublime"),
    "bas": ("faible", "réduit", "modeste"),
    "vite": ("rapidement", "déjà", "promptement", "sans délai"),
    "rapide": ("prompt", "léger", "efficace", "saccadé"),
    "lent": ("ralenti", "paisible", "très lent"),
    "doux": ("tendre", "calme", "douillet"),
    "fort": ("puissant", "robuste", "solide", "marqué"),
    "faible": ("fragile", "modeste", "léger", "doux"),
    "bon": ("excellent", "superbe", "précieux", "agréable"),
    "mauvais": ("nul", "défavorable", "médiocre", "mauvais"),
    "clair": ("transparent", "net", "limpide", "simple"),
    "sombre": ("obscur", "triste", "noir", "ténébreux"),
    "joyeux": ("heureux", "content", "radieux", "gai"),
    "triste": ("malheureux", "sombre", "désolé", "mélancolique"),
    "simple": ("facile", "naturel", "direct", "sans artifice"),
    "complexe": ("compliqué", "difficile", "labyrinthique", "sophistiqué"),
    "important": ("majeur", "considérable", "significatif", "notable"),
    "peur": ("crainte", "angoisse", "frayeur", "terreur"),
    "aimer": ("adorer", "apprécier", "chérir", "priser"),
    "dire": ("annoncer", "affirmer", "mentionner", "rapporter"),
    "voir": ("apercevoir", "découvrir", "constater", "observer"),
}


def _normalize_word(word: str) -> str:
    cleaned = re.sub(r"[^\w]+", "", word.lower())
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    return cleaned


def find_synonyms(word: str) -> list[str]:
    if not word:
        return []

    normalized = _normalize_word(word)
    if not normalized:
        return []

    direct_matches = _COMMON_SYNONYMS.get(normalized)
    if direct_matches:
        return list(direct_matches)

    for key, synonyms in _COMMON_SYNONYMS.items():
        if normalized in key:
            return list(synonyms)

    return []


@lru_cache(maxsize=256)
def find_api_synonyms(word: str, limit: int = 50) -> tuple[list[str], str]:
    """Lit les sections « Synonymes » françaises via l'API du Wiktionnaire."""
    normalized = _normalize_word(word)
    if not normalized:
        return [], "Mot invalide."

    try:
        sections_payload = _wiktionary_request(
            {"action": "parse", "page": word, "prop": "sections"}
        )
        sections = sections_payload.get("parse", {}).get("sections", [])
        in_french = False
        synonym_indexes: list[str] = []
        for section in sections:
            level = str(section.get("level", ""))
            title = html.unescape(re.sub(r"<[^>]+>", "", str(section.get("line", ""))))
            if level == "2":
                in_french = title.casefold() == "français"
            elif in_french and title.casefold() in {"synonymes", "quasi-synonymes"}:
                synonym_indexes.append(str(section.get("index", "")))

        results: list[str] = []
        seen = {normalized}
        for section_index in synonym_indexes:
            payload = _wiktionary_request(
                {
                    "action": "parse",
                    "page": word,
                    "prop": "text",
                    "section": section_index,
                }
            )
            raw_text = payload.get("parse", {}).get("text", "")
            section_html = str(
                raw_text.get("*", "") if isinstance(raw_text, dict) else raw_text
            )
            for item_html in re.findall(r"<li[^>]*>(.*?)</li>", section_html, re.DOTALL):
                match = re.search(r'<a[^>]+href="/wiki/[^\"]+"[^>]*>(.*?)</a>', item_html, re.DOTALL)
                if not match:
                    continue
                candidate = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
                candidate_normalized = _normalize_word(candidate)
                if not candidate_normalized or candidate_normalized in seen:
                    continue
                seen.add(candidate_normalized)
                results.append(candidate)
                if len(results) >= limit:
                    return results, ""
        return results, "" if results else "Aucun synonyme français répertorié."
    except HTTPError as exc:
        if exc.code == 404:
            return [], "Mot absent du Wiktionnaire."
        return [], f"Wiktionnaire indisponible (HTTP {exc.code})."
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        return [], "Connexion au Wiktionnaire impossible."


def _wiktionary_request(parameters: dict[str, str]) -> dict:
    query = urlencode({**parameters, "format": "json", "formatversion": "2"})
    request = Request(
        f"https://fr.wiktionary.org/w/api.php?{query}",
        headers={"User-Agent": "YuumiWriting/1.0 (synonymes)"},
    )
    tls_context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(request, timeout=8, context=tls_context) as response:
        return json.loads(response.read().decode("utf-8"))
