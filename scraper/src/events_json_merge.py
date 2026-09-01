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


def _date_ranges_overlap(start1: str, end1: str, start2: str, end2: str) -> bool:
    """True se i due intervalli di date [start1,end1] e [start2,end2] si
    sovrappongono anche solo parzialmente (confronto tra stringhe ISO
    'YYYY-MM-DD', valido perché ordinabili lessicograficamente come date).
    """
    if not start1 or not start2:
        return False
    end1 = end1 or start1
    end2 = end2 or start2
    return not (end1 < start2 or end2 < start1)


def dedupe_events(events: list[dict]) -> tuple[list[dict], list[dict]]:
    """Rimuove i doppioni tra eventi AUTOMATICI (non tocca mai gli eventi
    manuali, che restano tutti). Un evento automatico è considerato un
    doppione se, sullo STESSO circuito, il suo intervallo [dataInizio,
    dataFine] si SOVRAPPONE (anche solo parzialmente) con quello di:
      - un evento manuale già esistente (es. "10mo Minardi Day" inserito a
        mano vs "Historic Minardi Day" trovato dallo scraper, stesso
        circuito, stesse date)
      - un altro evento automatico già tenuto in questa stessa passata

    Il confronto per SOVRAPPOSIZIONE (invece che uguaglianza esatta delle
    date) serve perché a volte due fonti diverse per lo stesso evento reale
    riportano un giorno di inizio leggermente diverso (es. "Formula X 5-8
    settembre" vs "FX Racing Weekend 6-8 settembre" allo stesso circuito:
    sono lo stesso evento, ma con date di inizio non identiche).

    Restituisce (eventi_puliti, doppioni_rimossi). Si applica ad OGNI run,
    quindi ripulisce anche doppioni già presenti in events.json da run
    precedenti a questa correzione.
    """
    manual = [e for e in events if not e.get("fonteAuto")]
    cleaned = list(manual)
    duplicates_removed: list[dict] = []

    # ordina per idAuto per un risultato deterministico (stesso risultato
    # ad ogni run, a parità di dati in ingresso)
        auto_events = sorted(
        (e for e in events if e.get("fonteAuto")),
        key=lambda e: (-len(e.get("titolo", "")), e.get("idAuto", "")),
    )
    for e in auto_events:
        circuito = e.get("circuito")
        start = e.get("dataInizio", "")
        end = e.get("dataFine", start)

        is_duplicate = any(
            kept.get("circuito") == circuito
            and _date_ranges_overlap(start, end, kept.get("dataInizio", ""), kept.get("dataFine", ""))
            for kept in cleaned
        )

        if is_duplicate:
            duplicates_removed.append(e)
            continue
        cleaned.append(e)

    return cleaned, duplicates_removed
