"""Scraper per l'Autodromo Piero Taruffi di Vallelunga.

La pagina https://motorsport.vallelunga.it/gare/ è server-rendered (niente
JavaScript necessario). A differenza di Imola, qui il sito pubblica un
elenco compatto "CALENDARIO GARE <anno>" con righe nel formato:

    18 – 19 Aprile FX Racing Weekend 
    03-04 Ottobre TIME ATTACK

cioè DATA seguita dal titolo (ordine opposto rispetto a Imola, dove il
titolo viene prima). Usiamo questo elenco compatto invece delle schede
descrittive lunghe più sotto nella pagina ("EVENTI <anno>"), perché è più
pulito e meno soggetto a falsi positivi/negativi.

Non essendoci un link diretto per ogni singolo evento nell'elenco
compatto, linkInfo punterà alla pagina generale del calendario.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_static

IT_MONTHS = (
    "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
    "settembre|ottobre|novembre|dicembre"
)

YEAR_HEADING_RE = re.compile(r"CALENDARIO\s+GARE\s+(\d{4})", re.IGNORECASE)

# "18 – 19 Aprile FX Racing Weekend"  |  "03-04 Ottobre TIME ATTACK"
# |  "04 Luglio Titolo" (giorno singolo, senza intervallo)
LIST_ITEM_RE = re.compile(
    rf"^\s*(\d{{1,2}})\s*(?:[-–]\s*(\d{{1,2}})\s*)?({IT_MONTHS})\s+(.+?)\s*$",
    re.IGNORECASE,
)


class VallelungaScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_static(self.config.url)
        soup = BeautifulSoup(html, "lxml")
        full_text = soup.get_text("\n")

        year_match = YEAR_HEADING_RE.search(full_text)
        year = year_match.group(1) if year_match else str(date.today().year)

        events: dict[str, Event] = {}

        def try_add(line: str) -> None:
            m = LIST_ITEM_RE.match(line.strip())
            if not m:
                return
            day1, day2, month_it, title = m.groups()
            day2 = day2 or day1
            title = title.strip(" -–")
            if not title or len(title) > 100:
                # riga troppo lunga = probabilmente non è una entry del
                # calendario ma un paragrafo di testo che inizia per caso
                # con un numero
                return

            date_text = f"{day1} - {day2} {month_it} {year}"
            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=title,
                date_text=date_text,
                url=self.config.url,
            )
            events[ev.event_id] = ev

        # 1) prova sugli elementi di lista/paragrafo (caso più pulito)
        for tag in soup.find_all(["li", "p"]):
            try_add(tag.get_text(" ", strip=True))

        # 2) fallback: scansiona anche il testo grezzo riga per riga, nel
        #    caso il sito non usi <li>/<p> per questo elenco
        for line in full_text.splitlines():
            try_add(line)

        return list(events.values())
