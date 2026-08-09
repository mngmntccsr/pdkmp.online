"""Scraper per l'Autodromo Piero Taruffi di Vallelunga.

La pagina https://motorsport.vallelunga.it/gare/ è server-rendered (niente
JavaScript necessario). Il sito pubblica un elenco compatto
"CALENDARIO GARE <anno>" con righe nel formato:

    18 – 19 Aprile FX Racing Weekend
    03-04 Ottobre TIME ATTACK

cioè DATA seguita dal titolo (ordine opposto rispetto a Imola, dove il
titolo viene prima), SENZA anno esplicito su ogni riga: l'anno si deduce
dal titolo della sezione ("CALENDARIO GARE 2026").

Per essere robusti anche nel caso l'elenco attraversi un cambio d'anno
(es. pubblicato a dicembre con voci che arrivano fino a gennaio
dell'anno successivo), teniamo traccia dell'ordine dei mesi incontrati:
se un mese "torna indietro" rispetto al precedente (es. da Dicembre si
passa a Gennaio), consideriamo che l'anno sia scattato in avanti di uno
per quella voce e per tutte le successive.

Non essendoci un link diretto per ogni singolo evento nell'elenco
compatto, linkInfo punterà alla pagina generale del calendario.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_static

IT_MONTHS_LIST = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]
MONTH_INDEX = {name: i + 1 for i, name in enumerate(IT_MONTHS_LIST)}
IT_MONTHS_PATTERN = "|".join(IT_MONTHS_LIST)

YEAR_HEADING_RE = re.compile(r"CALENDARIO\s+GARE\s+(\d{4})", re.IGNORECASE)

# "18 – 19 Aprile FX Racing Weekend"  |  "03-04 Ottobre TIME ATTACK"
# |  "04 Luglio Titolo" (giorno singolo, senza intervallo)
LIST_ITEM_RE = re.compile(
    rf"^\s*(\d{{1,2}})\s*(?:[-–]\s*(\d{{1,2}})\s*)?({IT_MONTHS_PATTERN})\s+(.+?)\s*$",
    re.IGNORECASE,
)


class VallelungaScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_static(self.config.url)
        soup = BeautifulSoup(html, "lxml")
        full_text = soup.get_text("\n")

        year_match = YEAR_HEADING_RE.search(full_text)
        start_year = int(year_match.group(1)) if year_match else date.today().year

        # Raccoglie le righe candidate mantenendo l'ordine di apparizione
        # nella pagina (necessario per rilevare il cambio d'anno).
        raw_matches = [
            m for m in (
                LIST_ITEM_RE.match(tag.get_text(" ", strip=True).strip())
                for tag in soup.find_all(["li", "p"])
            )
            if m
        ]
        if not raw_matches:
            # fallback: il sito potrebbe non usare <li>/<p> per questo elenco
            raw_matches = [
                m for m in (LIST_ITEM_RE.match(line.strip()) for line in full_text.splitlines())
                if m
            ]

        events: dict[str, Event] = {}
        year = start_year
        last_month_idx = 0

        for m in raw_matches:
            day1, day2, month_it, title = m.groups()
            title = title.strip(" -–")
            if not title or len(title) > 100:
                # riga troppo lunga = probabilmente non è una entry del
                # calendario ma un paragrafo di testo che inizia per caso
                # con un numero
                continue

            month_idx = MONTH_INDEX.get(month_it.lower(), 0)
            if month_idx and month_idx < last_month_idx:
                year += 1   # il mese "torna indietro" -> è scattato l'anno nuovo
            if month_idx:
                last_month_idx = month_idx

            day2 = day2 or day1
            date_text = f"{day1} - {day2} {month_it} {year}"

            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=title,
                date_text=date_text,
                url=self.config.url,
            )
            events[ev.event_id] = ev

        return list(events.values())
