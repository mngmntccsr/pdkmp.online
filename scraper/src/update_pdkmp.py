"""Entry point per l'integrazione con PaddockMap (pdkmp.online).

Aggiorna events.json (nella root del repo del sito) con gli eventi trovati
sugli autodromi configurati, e registra le variazioni in CHANGELOG.md.

L'email via SMTP è FACOLTATIVA (disattivata di default): si attiva solo
impostando la variabile d'ambiente SEND_EMAIL=true insieme ai secrets SMTP.
Se non la configuri, non serve nessuna password/app-password: lo script
scrive semplicemente CHANGELOG.md nel repo, che puoi controllare quando
vuoi.

Uso:
    python -m src.update_pdkmp
    python -m src.update_pdkmp --dry-run
    python -m src.update_pdkmp --dry-run --track imola
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from src.changelog import append_changelog_entry, build_entry
from src.config import ROOT_DIR, load_keywords, load_tracks
from src.events_json_merge import load_events_json, merge_auto_events, save_events_json
from src.filters import filter_events
from src.pdkmp_schema import event_to_pdkmp_dict
from src.scrapers.imola import ImolaScraper
from src.scrapers.misano import MisanoScraper
from src.scrapers.monza import MonzaScraper
from src.scrapers.vallelunga import VallelungaScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("update_pdkmp")

SCRAPER_REGISTRY = {
    "imola": ImolaScraper,
    "monza": MonzaScraper,
    "misano": MisanoScraper,
    "vallelunga": VallelungaScraper,
}

# events.json vive nella ROOT del repo del sito (accanto a index.html).
# Questa cartella (con src/, config/, ecc.) va messa in una SOTTOCARTELLA
# del repo del sito chiamata "scraper/" (vedi README-INTEGRAZIONE.md):
# in quel caso events.json si trova un livello sopra ROOT_DIR.
# Se invece preferisci un'altra disposizione, imposta la variabile
# d'ambiente EVENTS_JSON_PATH con il percorso assoluto/relativo corretto.
_env_override = os.environ.get("EVENTS_JSON_PATH")
EVENTS_JSON_PATH = Path(_env_override) if _env_override else (ROOT_DIR.parent / "events.json")

CHANGELOG_PATH = ROOT_DIR / "CHANGELOG.md"

SEND_EMAIL = os.environ.get("SEND_EMAIL", "false").strip().lower() == "true"


def run(dry_run: bool = False, only_track: str | None = None) -> int:
    tracks = load_tracks()
    keywords = load_keywords()

    if only_track:
        tracks = [t for t in tracks if t.slug == only_track]
        if not tracks:
            logger.error("Pista sconosciuta: %s", only_track)
            return 1

    all_pdkmp_events: list[dict] = []
    unparsed: list[tuple] = []
    had_errors = False

    for track in tracks:
        scraper_cls = SCRAPER_REGISTRY.get(track.slug)
        if not scraper_cls:
            logger.warning("Nessuno scraper registrato per '%s'", track.slug)
            continue

        logger.info("Scraping %s (%s)...", track.name, track.url)
        try:
            raw_events = scraper_cls(track).scrape()
        except Exception:
            logger.exception("Errore durante lo scraping di %s", track.name)
            had_errors = True
            continue

        current = filter_events(raw_events, keywords)
        logger.info(
            "%s: %d eventi grezzi, %d dopo il filtro motorsport",
            track.name, len(raw_events), len(current),
        )

        for ev in current:
            pdkmp_dict = event_to_pdkmp_dict(ev, track)
            if pdkmp_dict is None:
                unparsed.append((track.name, ev))
            else:
                all_pdkmp_events.append(pdkmp_dict)

    existing = load_events_json(EVENTS_JSON_PATH)
    merged, added, removed = merge_auto_events(existing, all_pdkmp_events)

    logger.info(
        "events.json: %d eventi totali (%d manuali + %d auto), %d aggiunti, %d rimossi, %d scartati (data illeggibile)",
        len(merged), len(merged) - len(all_pdkmp_events), len(all_pdkmp_events),
        len(added), len(removed), len(unparsed),
    )

    if dry_run:
        print(build_entry(added, removed, unparsed))
        logger.info("[DRY RUN] events.json e CHANGELOG.md NON modificati.")
        return 1 if had_errors else 0

    save_events_json(EVENTS_JSON_PATH, merged)
    logger.info("events.json aggiornato in %s", EVENTS_JSON_PATH)

    append_changelog_entry(CHANGELOG_PATH, added, removed, unparsed)
    logger.info("CHANGELOG.md aggiornato in %s", CHANGELOG_PATH)

    if SEND_EMAIL:
        # Email facoltativa: import locale così, se non la usi, non serve
        # nemmeno che python-dotenv/smtplib siano configurati correttamente.
        from src.config import load_email_config
        from src.notifier import send_email

        html_body = "<pre>" + build_entry(added, removed, unparsed) + "</pre>"
        try:
            email_config = load_email_config()
            subject = f"🏁 PaddockMap: {len(added)} aggiunti, {len(removed)} rimossi"
            send_email(email_config, subject, html_body)
            logger.info("Email inviata (SEND_EMAIL=true).")
        except Exception:
            # Un problema con l'email non deve mai far fallire l'intero
            # workflow: events.json e CHANGELOG.md sono già stati salvati.
            logger.exception("Invio email fallito (events.json/CHANGELOG.md sono comunque aggiornati)")

    return 1 if had_errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggiorna events.json di PaddockMap")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--track", help="Esegue solo una pista (slug)")
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run, only_track=args.track))


if __name__ == "__main__":
    main()
