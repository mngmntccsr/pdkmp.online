"""Script UNA TANTUM: rimuove da events.json tutte le voci automatiche
("fonteAuto": true) di una specifica pista, per ripulire duplicati/date
sbagliate lasciati da versioni precedenti dello scraper.

Gli eventi SENZA "fonteAuto" (quelli che hai inserito a mano) non vengono
MAI toccati.

Dopo averlo lanciato, il prossimo run del workflow settimanale ricostruisce
da zero gli eventi di quella pista con la versione corretta dello scraper.

Uso:
    python tools/purge_track_auto_events.py misano
    python tools/purge_track_auto_events.py misano --dry-run   # mostra solo cosa verrebbe rimosso
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ROOT_DIR
from src.events_json_merge import load_events_json, save_events_json

EVENTS_JSON_PATH = ROOT_DIR.parent / "events.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("circuito_contains", help="Sottostringa del campo 'circuito' da ripulire, es: Misano")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    events = load_events_json(EVENTS_JSON_PATH)
    print(f"Eventi totali in events.json: {len(events)}")

    to_remove = [
        e for e in events
        if e.get("fonteAuto") and args.circuito_contains.lower() in e.get("circuito", "").lower()
    ]
    kept = [e for e in events if e not in to_remove]

    print(f"\nVoci automatiche da rimuovere ({len(to_remove)}):")
    for e in to_remove:
        print(f"  - {e.get('titolo')} | {e.get('dataInizio')} -> {e.get('dataFine')}")

    if args.dry_run:
        print("\n[DRY RUN] Nessuna modifica scritta su disco.")
        return

    if not to_remove:
        print("\nNulla da rimuovere.")
        return

    save_events_json(EVENTS_JSON_PATH, kept)
    print(f"\nFatto. events.json ora ha {len(kept)} eventi (rimossi {len(to_remove)}).")
    print("Al prossimo run del workflow, questa pista verrà ricostruita da zero con lo scraper corretto.")


if __name__ == "__main__":
    main()
