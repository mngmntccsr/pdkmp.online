"""Archiviazione automatica degli eventi conclusi da oltre una settimana.

Ogni evento (SIA manuale che automatico) la cui data di fine è più vecchia
di ARCHIVE_AFTER_DAYS giorni rispetto a oggi viene spostato da events.json
a events-archive.json: un archivio storico che si accumula nel tempo (non
viene mai sovrascritto, solo esteso), utile per SEO/consultazione storica
senza appesantire il file "eventi correnti" che il sito mostra.

Si applica a TUTTI gli eventi (non solo quelli con "fonteAuto": true):
un evento passato da una settimana va archiviato indipendentemente da come
è stato inserito.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

ARCHIVE_AFTER_DAYS = 7


def _archive_key(event: dict) -> str:
    """Chiave di identità per evitare doppioni nell'archivio nel tempo.
    Basata su titolo+dataInizio+circuito (non su idAuto, che esiste solo
    per gli eventi automatici): funziona sia per eventi manuali che auto.
    """
    raw = f"{event.get('titolo', '')}|{event.get('dataInizio', '')}|{event.get('circuito', '')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_archive(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def split_and_archive(events: list[dict], archive_path: Path) -> tuple[list[dict], list[dict]]:
    """Restituisce (eventi_da_tenere_in_events_json, eventi_appena_archiviati)
    e aggiorna anche events-archive.json su disco (append, mai sovrascritto).
    """
    cutoff = (date.today() - timedelta(days=ARCHIVE_AFTER_DAYS)).isoformat()

    keep: list[dict] = []
    to_archive: list[dict] = []
    for e in events:
        data_fine = e.get("dataFine", "")
        if data_fine and data_fine < cutoff:
            to_archive.append(e)
        else:
            keep.append(e)

    newly_archived: list[dict] = []
    if to_archive:
        existing_archive = load_archive(archive_path)
        existing_keys = {_archive_key(e) for e in existing_archive}
        newly_archived = [e for e in to_archive if _archive_key(e) not in existing_keys]

        if newly_archived:
            merged_archive = existing_archive + newly_archived
            with open(archive_path, "w", encoding="utf-8") as f:
                json.dump(merged_archive, f, ensure_ascii=False, indent=2)
                f.write("\n")

    return keep, newly_archived
