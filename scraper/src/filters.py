"""Fusione degli eventi scrapati dentro il file events.json del sito PaddockMap.

Regola fondamentale: gli eventi inseriti A MANO da te in events.json (quelli
senza il campo "fonteAuto": true) non vengono MAI toccati da questo script,
né modificati né rimossi. Lo script gestisce solo gli eventi che porta
"fonteAuto": true, cioè quelli aggiunti automaticamente da lui in un run
precedente:
  - se uno di questi eventi non viene più trovato sul sito dell'autodromo
    (es. evento cancellato) -> viene rimosso da events.json
  - se un evento nuovo viene trovato -> viene aggiunto
  - se un evento già presente (stesso idAuto) resta invariato -> non fa nulla
"""
from __future__ import annotations

import json
from pathlib import Path


def load_events_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_events_json(path: Path, events: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
        f.write("\n")


def merge_auto_events(existing: list[dict], new_auto_events: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Restituisce (merged, added, removed).

    - manual: eventi senza "fonteAuto" -> sempre mantenuti così come sono
    - auto esistenti: sostituiti dal nuovo set new_auto_events
    """
    manual_events = [e for e in existing if not e.get("fonteAuto")]
    old_auto_by_id = {e.get("idAuto"): e for e in existing if e.get("fonteAuto")}
    new_auto_by_id = {e.get("idAuto"): e for e in new_auto_events}

    added = [e for eid, e in new_auto_by_id.items() if eid not in old_auto_by_id]
    removed = [e for eid, e in old_auto_by_id.items() if eid not in new_auto_by_id]

    merged = manual_events + list(new_auto_by_id.values())
    return merged, added, removed
