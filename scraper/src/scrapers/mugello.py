"""Scraper per il Mugello Circuit.

La pagina https://mugellocircuit.com/it/gare/from/<inizio>/to/<fine> è
server-rendered (Joomla, niente JavaScript necessario). Ogni evento è una
card con:
  - un link verso .../gare/details/YYYY-MM-DD/<id>-<slug>/ — la data di
    INIZIO è quindi già codificata nell'URL stesso: fonte affidabile al
    100%, non serve indovinarla dal testo
  - un'intestazione vicina con l'intervallo in formato "DD.MM.YYYY -
    DD.MM.YYYY" (o solo "DD.MM.YYYY" per eventi di un giorno), usata SOLO
    per ricavare la data di fine (utile per eventi a cavallo di due mesi,
    es. "30.10.2026 - 01.11.2026")

A differenza degli altri autodromi, qui calcoliamo le date ISO
direttamente (niente regex sui nomi dei mesi) e le passiamo tramite
Event.date_start/date_end: pdkmp_schema.py le userà così come sono.

L'URL "from/to" viene costruita dinamicamente ad ogni esecuzione, da oggi
fino a ~18 mesi nel futuro, così troviamo sempre gli eventi in programma
senza dover gestire la paginazione del sito.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_static

DETAILS_HREF_RE = re.compile(r"/gare/details/(\d{4}-\d{2}-\d{2})/")
DATE_RANGE_RE = re.compile(
    r"(\d{2})\.(\d{2})\.(\d{4})(?:\s*-\s*(\d{2})\.(\d{2})\.(\d{4}))?"
)

_GENERIC_LINK_TEXTS = {"gare", "dettagli", "scopri di più", "info", "biglietti"}


class MugelloScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        today = date.today()
        end = today + timedelta(days=548)  # ~18 mesi in avanti
        url = f"{self.config.url}/from/{today.isoformat()}/to/{end.isoformat()}"

        html = fetch_html_static(url)
        soup = BeautifulSoup(html, "lxml")

        events: dict[str, Event] = {}

        for a in soup.find_all("a", href=True):
            m = DETAILS_HREF_RE.search(a["href"])
            if not m:
                continue
            title = a.get_text(" ", strip=True)
            if not title or title.lower() in _GENERIC_LINK_TEXTS:
                continue

            start_iso = m.group(1)   # YYYY-MM-DD già affidabile, viene dall'URL

            # risale ai genitori per trovare l'intervallo di date testuale
            # (serve solo per la data di FINE); si ferma al primo
            # contenitore compatto (pochi link) che lo contiene, per non
            # rischiare di agganciare un intervallo non correlato
            container = a
            date_match = None
            for _ in range(6):
                if container.parent is None:
                    break
                container = container.parent
                found = DATE_RANGE_RE.search(container.get_text(" ", strip=True))
                if found:
                    if len(container.find_all("a", href=True)) <= 4:
                        date_match = found
                    break

            if date_match and date_match.group(4):
                end_iso = f"{date_match.group(6)}-{date_match.group(5)}-{date_match.group(4)}"
            else:
                end_iso = start_iso

            href = a["href"]
            if not href.startswith("http"):
                href = f"https://mugellocircuit.com{href}"

            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=title,
                date_text=f"{start_iso} - {end_iso}",   # solo riferimento/debug
                url=href,
                date_start=start_iso,
                date_end=end_iso,
            )
            events[ev.event_id] = ev

        return list(events.values())
