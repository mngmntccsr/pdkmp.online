"""Scraper per il Misano World Circuit "Marco Simoncelli".

Il sito misanocircuit.com carica il calendario eventi via JavaScript (il
fetch statico della pagina restituisce HTML sostanzialmente vuoto), quindi
usiamo Playwright come per Monza.

IMPORTANTE: i selettori in config/tracks.yaml per "misano" sono un punto di
partenza generico (cercano elementi con classi contenenti "event"/"card").
Verificali/correggili con `python tools/inspect_page.py misano` prima del
primo utilizzo in produzione: è molto probabile che vadano affinati sulla
struttura reale del sito.
"""
from __future__ import annotations

from src.models import Event
from src.scrapers.base import BaseTrackScraper, extract_events_via_selectors, fetch_html_dynamic


class MisanoScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_dynamic(self.config.url, wait_selector=self.config.wait_selector)
        return extract_events_via_selectors(html, self.config)
