"""Entry point per l'integrazione con PaddockMap (pdkmp.online).

Aggiorna events.json (nella root del repo del sito) con gli eventi trovati
sugli autodromi configurati, poi invia l'email settimanale di riepilogo.

Uso:
    python -m src.update_pdkmp
    python -m src.update_pdkmp --dry-run
    python -m src.update_pdkmp --dry-run --track imola
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.config import ROOT_DIR, load_email_config, load_keywords, load_tracks
from src.events_json_merge import load_events_json, merge_auto_events, save_events_json
from src.filters import filter_events
from src.notifier import send_email
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
import os

_env_override = os.environ.get("EVENTS_JSON_PATH")
EVENTS_JSON_PATH = Path(_env_override) if _env_override else (ROOT_DIR.parent / "events.json")


def _build_email_body(added: list[dict], removed: list[dict], unparsed: list[tuple]) -> str:
    from datetime import date
    today = date.today().strftime("%d/%m/%Y")

    def _li(e: dict) -> str:
        link = e.get("linkInfo", "")
        title = e.get("titolo", "")
        date_range = f"{e.get('dataInizio','')} → {e.get('dataFine','')}"
        inner = f"<b>{title}</b> — {date_range} <span style='color:#888'>[{e.get('circuito','')}]</span>"
        if link:
            inner = f'<a href="{link}">{inner}</a>'
        return f"<li>{inner}</li>"

    html = [f"<h2>Aggiornamento events.json — PaddockMap — {today}</h2>"]

    if not added and not removed:
        html.append("<p>Nessuna variazione questa settimana.</p>")
    else:
        if added:
            html.append(f"<h3 style='color:#0a7d2c'>✅ Eventi aggiunti a events.json ({len(added)})</h3>")
            html.append("<ul>" + "".join(_li(e) for e in added) + "</ul>")
        if removed:
            html.append(f"<h3 style='color:#b00020'>❌ Eventi rimossi da events.json ({len(removed)})</h3>")
            html.append("<ul>" + "".join(_li(e) for e in removed) + "</ul>")

    if unparsed:
        html.append(
            f"<h3 style='color:#b06d00'>⚠️ {len(unparsed)} eventi trovati ma NON aggiunti "
            "(data non interpretabile, controlla a mano)</h3><ul>"
        )
        for track_name, ev in unparsed:
            link = f' — <a href="{ev.url}">link</a>' if ev.url else ""
            html.append(f"<li><b>{ev.title}</b> [{track_name}] data grezza: “{ev.date_text}”{link}</li>")
        html.append("</ul>")

    html.append(
        "<hr><p style='color:#888;font-size:12px'>"
        "Email generata automaticamente dallo scraper eventi PaddockMap. "
        "Gli eventi inseriti a mano da te in events.json non vengono mai toccati."
        "</p>"
    )
    return "\n".join(html)


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

    html_body = _build_email_body(added, removed, unparsed)

    if dry_run:
        print(html_body)
        logger.info("[DRY RUN] events.json NON modificato, email NON inviata.")
        return 1 if had_errors else 0

    save_events_json(EVENTS_JSON_PATH, merged)
    logger.info("events.json aggiornato in %s", EVENTS_JSON_PATH)

    if added or removed or unparsed:
        email_config = load_email_config()
        subject = f"🏁 PaddockMap: {len(added)} aggiunti, {len(removed)} rimossi"
        if unparsed:
            subject += f", {len(unparsed)} da rivedere"
        send_email(email_config, subject, html_body)
        logger.info("Email inviata.")
    else:
        email_config = load_email_config()
        if email_config.always_send:
            send_email(email_config, "🏁 PaddockMap: nessuna variazione questa settimana", html_body)
            logger.info("Email inviata (nessuna variazione).")
        else:
            logger.info("Nessuna variazione: email non inviata (ALWAYS_SEND=false).")

    return 1 if had_errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggiorna events.json di PaddockMap")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--track", help="Esegue solo una pista (slug)")
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run, only_track=args.track))


if __name__ == "__main__":
    main()
