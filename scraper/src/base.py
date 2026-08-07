"""Scraper per l'Autodromo Nazionale di Monza.

Il calendario su monzanet.it/gare-eventi/ è generato lato client dal plugin
WordPress "EventON": l'HTML statico contiene solo lo shortcode non ancora
renderizzato, quindi serve un browser headless (Playwright) per ottenere gli
eventi effettivi.

IMPORTANTE: i selettori CSS usati per individuare gli eventi sono in
config/tracks.yaml (chiave "monza" -> "selectors") e sono una stima basata
sulle classi tipiche del plugin EventON. Se lo scraper trova 0 eventi,
esegui `python tools/inspect_page.py monza` per salvare l'HTML renderizzato
e correggere i selettori.
"""
from __future__ import annotations

from src.models import Event
from src.scrapers.base import BaseTrackScraper, extract_events_via_selectors, fetch_html_dynamic


class MonzaScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_dynamic(self.config.url, wait_selector=self.config.wait_selector)
        return extract_events_via_selectors(html, self.config)
