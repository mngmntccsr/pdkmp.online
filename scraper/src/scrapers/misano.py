"""Scraper per il Misano World Circuit "Marco Simoncelli".
 
Il sito misanocircuit.com/events è una single-page application React: gli
eventi non sono link <a href> ma "card" cliccabili (div con navigazione
gestita via JavaScript, senza href statico), quindi serve Playwright per
il rendering E un parsing testuale dedicato — i selettori CSS generici non
funzionano perché le classi sono tutte utility Tailwind non semantiche
(niente "event-card" o simili).
 
Ogni card contiene, in quest'ordine:
  - un'immagine con alt="Titolo evento"
  - un'icona calendario seguita dal testo data, es. "10-13 set 2026" o,
    per eventi a cavallo di due mesi, "30 apr - 3 mag 2026"
  - un <h2> con il titolo (ripetuto)
 
Non essendoci un URL diretto per singolo evento estraibile dall'HTML
statico, linkInfo punta alla pagina generale del calendario.
"""
from __future__ import annotations
 
import re
 
from bs4 import BeautifulSoup
 
from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_dynamic
 
IT_MONTH_ABBR = {
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
    "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12,
}
_MONTHS_PATTERN = "|".join(IT_MONTH_ABBR)
 
# "10-13 set 2026"  |  "30 apr - 3 mag 2026" (mese diverso per ciascun giorno)
DATE_RE = re.compile(
    rf"(\d{{1,2}})(?:\s+({_MONTHS_PATTERN}))?\s*[-–]\s*(\d{{1,2}})\s+({_MONTHS_PATTERN})\s+(\d{{4}})",
    re.IGNORECASE,
)
 
 
class MisanoScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_dynamic(self.config.url, wait_selector=self.config.wait_selector)
        soup = BeautifulSoup(html, "lxml")
 
        events: dict[str, Event] = {}
 
        for h2 in soup.find_all("h2"):
            title = h2.get_text(" ", strip=True)
            if not title:
                continue
 
            # risale ai genitori finché non trova il testo della data più
            # vicino: si ferma al primo trovato, per non rischiare di
            # agganciare la data di una card diversa
            container = h2
            date_match = None
            for _ in range(6):
                if container.parent is None:
                    break
                container = container.parent
                found = DATE_RE.search(container.get_text(" ", strip=True))
                if found:
                    date_match = found
                    break
 
            if not date_match:
                continue
 
            day1, month1_abbr, day2, month2_abbr, year = date_match.groups()
            month2 = IT_MONTH_ABBR[month2_abbr.lower()]
            month1 = IT_MONTH_ABBR[month1_abbr.lower()] if month1_abbr else month2
 
            start_iso = f"{year}-{month1:02d}-{int(day1):02d}"
            end_iso = f"{year}-{month2:02d}-{int(day2):02d}"
 
            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=title,
                date_text=date_match.group(0),   # solo riferimento/debug
                url=self.config.url,             # niente URL per singolo evento nell'HTML statico
                date_start=start_iso,
                date_end=end_iso,
            )
            events[ev.event_id] = ev
 
        return list(events.values())
 
