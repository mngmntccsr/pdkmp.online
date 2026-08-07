"""Scraper per l'Autodromo Enzo e Dino Ferrari di Imola.

La pagina https://www.autodromoimola.it/en/events/ è server-rendered (niente
JavaScript necessario): ogni evento compare come un link tipo

    <a href=".../en/events/aci-racing-weekend/">ACI Racing Weekend 4 - 6 September 2026</a>

cioè titolo e data sono uniti nello stesso testo. Questo scraper individua
questi link (richiedendo la presenza di un anno a 4 cifre nel testo, che è
ciò che distingue un vero "evento con data" da un link di navigazione) e
separa titolo/data con un'espressione regolare sui nomi dei mesi.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_static

MONTHS = (
    r"(?:Gen(?:naio)?|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|"
    r"Settembre|Semptember|Ottobre|Novembre|Dicembre|"
    r"January|February|March|April|May|June|July|August|September|October|"
    r"November|December)"
)

DATE_RE = re.compile(
    rf"(\d{{1,2}}\s*°?\s*(?:[-–]\s*\d{{1,2}}\s*°?\s*)?{MONTHS}\s*\d{{4}})",
    re.IGNORECASE,
)

YEAR_RE = re.compile(r"\b(20\d{2})\b")


class ImolaScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_static(self.config.url)
        soup = BeautifulSoup(html, "lxml")

        events: dict[str, Event] = {}

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/events/" not in href:
                continue
            text = a.get_text(" ", strip=True)
            if not text or text.lower() in {"discover now", "events"}:
                continue
            if not YEAR_RE.search(text):
                # niente anno nel testo del link -> quasi certamente non è
                # una entry "titolo + data" ma un link di navigazione/duplicato
                continue

            match = DATE_RE.search(text)
            if match:
                date_text = match.group(1).strip()
                title = text[: match.start()].strip(" -–|")
            else:
                date_text = ""
                title = text

            if not title:
                continue

            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=title,
                date_text=date_text,
                url=href,
            )
            events[ev.event_id] = ev

        return list(events.values())
