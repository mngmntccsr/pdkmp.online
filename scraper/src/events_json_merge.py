"""Fusione degli eventi scrapati dentro il file events.json del sito PaddockMap.

Regola fondamentale: gli eventi inseriti A MANO da te in events.json (quelli
senza il campo "fonteAuto": true) non vengono MAI toccati da questo script,
né modificati né rimossi. Lo script gestisce solo gli eventi che porta
"fonteAuto": true, cioè quelli aggiunti automaticamente in un run
precedente:
  - se un evento nuovo viene trovato -> viene aggiunto
  - se un evento già presente (stesso idAuto) resta invariato -> non fa nulla
  - se un evento non viene più trovato sul sito dell'autodromo, ci sono
    DUE possibilità distinte:
      a) l'evento era ancora FUTURO -> è stato genuinamente cancellato dal
         sito -> viene rimosso da events.json e segnalato come "❌ Rimosso"
      b) l'evento si è semplicemente CONCLUSO (la maggior parte dei siti
         toglie un evento dal calendario appena finisce, è normale) ->
         NON viene trattato come una rimozione: resta in events.json così
         che sia lo step di archiviazione (con la sua finestra di 7 giorni,
         vedi events_archive.py) a spostarlo con calma in
         events-archive.json, invece di sparire subito senza lasciare
         traccia
"""
from __future__ import annotations

import json
from datetime import date
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
    - auto trovati nel nuovo scraping: aggiornati/aggiunti
    - auto NON più trovati: rimossi SOLO se erano ancora futuri (vera
      cancellazione); se erano già conclusi, restano per l'archiviazione
    """
    today_iso = date.today().isoformat()

    manual_events = [e for e in existing if not e.get("fonteAuto")]
    old_auto_by_id = {e.get("idAuto"): e for e in existing if e.get("fonteAuto")}
    new_auto_by_id = {e.get("idAuto"): e for e in new_auto_events}

    added = [e for eid, e in new_auto_by_id.items() if eid not in old_auto_by_id]

    removed: list[dict] = []
    concluded_not_found: dict[str, dict] = {}   # concluso e non ritrovato -> resta per l'archiviazione

    for eid, e in old_auto_by_id.items():
        if eid in new_auto_by_id:
            continue   # ancora presente, gestito da new_auto_by_id
        data_fine = e.get("dataFine", "")
        if data_fine and data_fine < today_iso:
            concluded_not_found[eid] = e
        else:
            removed.append(e)

    final_auto = {**concluded_not_found, **new_auto_by_id}
    merged = manual_events + list(final_auto.values())
    return merged, added, removed
