"""Scraper per l'Autodromo Enzo e Dino Ferrari di Imola.

La pagina https://www.autodromoimola.it/en/events/ è server-rendered (niente
JavaScript necessario), ma pubblica gli eventi in DUE strutture diverse:

1) Elenco piatto ("All events" / "Past events"): titolo e data uniti nello
   stesso link:

       <a href=".../en/events/aci-racing-weekend/">ACI Racing Weekend 4 - 6 September 2026</a>

2) Blocchi "in evidenza" con countdown (usati per gli eventi di punta, es.
   il WEC): titolo e data sono in elementi SEPARATI dentro uno stesso
   contenitore, con un link "Discover now"/"Biglietti" che di per sé non
   contiene la data:

       <h6>FIA WEC - 6 Hours of Imola</h6>
       ... "09 - 11 Aprile 2027" ...
       <a href=".../en/wec/">Biglietti</a>

Per questo lo scraper fa DUE passate:
  - _extract_flat_links: individua i link "titolo + data uniti" (richiede un
    anno a 4 cifre nel testo del link stesso, per escludere link di
    navigazione)
  - _extract_featured_cards: per ogni link verso /events/ o simili, risale
    ai contenitori genitori finché non trova un titolo (h1-h6) e cerca la
    data nel testo dell'intero contenitore

I risultati vengono uniti (deduplicati per titolo+data+url): se lo stesso
evento compare in entrambe le strutture, resta una sola voce.
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

# Il sito usa link interni sia sotto /en/events/... sia sotto altri percorsi
# dedicati per i grandi eventi (es. /en/wec/, /wec-6h-of-imola/): includiamo
# entrambi i pattern per la ricerca "in evidenza".
FEATURED_LINK_HINT_RE = re.compile(r"/(events|wec)", re.IGNORECASE)

# Testi di link generici da ignorare come CTA (non sono mai il titolo evento)
_GENERIC_LINK_TEXTS = {"discover now", "events", "biglietti", "tickets", "info evento", "scopri di più"}


def _extract_flat_links(soup: BeautifulSoup, config) -> dict[str, Event]:
    events: dict[str, Event] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/events/" not in href:
            continue
        text = a.get_text(" ", strip=True)
        if not text or text.lower() in _GENERIC_LINK_TEXTS:
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
            track_slug=config.slug, track_name=config.name,
            title=title, date_text=date_text, url=href,
        )
        events[ev.event_id] = ev
    return events


def _extract_featured_cards(soup: BeautifulSoup, config) -> dict[str, Event]:
    events: dict[str, Event] = {}
    for a in soup.find_all("a", href=True):
        if not FEATURED_LINK_HINT_RE.search(a["href"]):
            continue

        # risale ai genitori finché non trova un contenitore con un titolo,
        # fermandosi al PRIMO trovato: risalire oltre peggiorerebbe solo le
        # cose (contenitori più ampi = più a rischio di prendere il titolo
        # di una sezione non correlata della pagina)
        container = a
        heading = None
        for _ in range(6):
            if container.parent is None:
                break
            container = container.parent
            found = container.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if found:
                # accetta solo se il contenitore è "compatto" (pochi link):
                # un contenitore con tanti link è quasi certamente una
                # sezione ampia della pagina, non una singola card evento
                if len(container.find_all("a", href=True)) <= 3:
                    heading = found
                break
        if not heading:
            continue

        title = heading.get_text(" ", strip=True)
        if not title:
            continue

        card_text = container.get_text(" ", strip=True)
        match = DATE_RE.search(card_text)
        if not match:
            continue
        date_text = match.group(1).strip()

        ev = Event(
            track_slug=config.slug, track_name=config.name,
            title=title, date_text=date_text, url=a["href"],
        )
        events[ev.event_id] = ev
    return events


class ImolaScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_static(self.config.url)
        soup = BeautifulSoup(html, "lxml")

        events = _extract_flat_links(soup, self.config)
        for eid, ev in _extract_featured_cards(soup, self.config).items():
            events.setdefault(eid, ev)

        return list(events.values())
