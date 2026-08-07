"""Filtro degli eventi: tiene solo gare motoristiche / trackday.

Regola di classificazione (semplice e volutamente trasparente, così è facile
correggerla): un evento viene TENUTO se il suo titolo contiene almeno una
keyword della lista "include" e NESSUNA keyword della lista "exclude".
L'exclude ha sempre precedenza sull'include.

Le keyword si modificano in config/tracks.yaml, sezione "keywords".
"""
from __future__ import annotations

from src.models import Event


def _normalize(text: str) -> str:
    return f" {text.strip().lower()} "


def is_motorsport_event(title: str, keywords: dict[str, list[str]]) -> bool:
    text = _normalize(title)

    for kw in keywords.get("exclude", []):
        if kw.lower() in text:
            return False

    for kw in keywords.get("include", []):
        if kw.lower() in text:
            return True

    return False


def filter_events(events: list[Event], keywords: dict[str, list[str]]) -> list[Event]:
    return [e for e in events if is_motorsport_event(e.title, keywords)]
