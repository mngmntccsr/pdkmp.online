"""Classe base per gli scraper e utility di fetch delle pagine.

Ogni autodromo ha un suo scraper dedicato (src/scrapers/<slug>.py) perché,
in pratica, ogni sito organizza gli eventi in modo leggermente diverso.
Questo file fornisce solo l'infrastruttura comune:
  - fetch_html_static: scarica l'HTML "grezzo" via requests (siti server-rendered)
  - fetch_html_dynamic: apre la pagina con un browser headless (Playwright) e
    restituisce l'HTML dopo che il JavaScript ha popolato il calendario
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import requests

from src.config import TrackConfig
from src.models import Event

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
    "MotorsportEventsScraper/1.0 (+https://github.com/)"
)


def fetch_html_static(url: str, timeout: int = 20) -> str:
    """Scarica l'HTML di una pagina server-rendered."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_html_dynamic(url: str, wait_selector: str | None = None, timeout_ms: int = 20000) -> str:
    """Apre la pagina con Playwright (Chromium headless) e restituisce l'HTML
    dopo il rendering JavaScript. Necessario per calendari costruiti con
    plugin/framework client-side (es. EventON su WordPress, app React/Vue).
    """
    from playwright.sync_api import sync_playwright  # import locale: costoso, solo se serve

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        try:
            page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception:
                    # Non blocchiamo lo scraping se il selettore non compare:
                    # verrà semplicemente restituita la pagina così com'è,
                    # e a valle probabilmente 0 eventi -> utile per debug.
                    logger.warning(
                        "Selettore d'attesa '%s' non trovato su %s entro %sms",
                        wait_selector, url, timeout_ms,
                    )
            html = page.content()
        finally:
            browser.close()
    return html


def extract_events_via_selectors(html: str, config: TrackConfig) -> list[Event]:
    """Estrazione generica basata sui selettori CSS definiti in tracks.yaml.

    Usata dagli scraper "dynamic" (Monza, Misano) i cui siti non hanno una
    struttura semplice come Imola. Se in futuro il sito cambia grafica,
    modifica solo i selettori in config/tracks.yaml: non serve toccare
    questo codice.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    sel = config.selectors

    containers = soup.select(sel.get("event_container", "")) if sel.get("event_container") else []

    events: dict[str, Event] = {}

    for container in containers:
        # --- titolo ---
        title = ""
        title_sel = sel.get("title")
        if title_sel and title_sel != "self":
            node = container.select_one(title_sel)
            if node:
                title = node.get_text(" ", strip=True)
        if not title:
            title = container.get_text(" ", strip=True)[:200]
        if not title:
            continue

        # --- data (facoltativa) ---
        date_text = ""
        date_sel = sel.get("date")
        if date_sel:
            node = container.select_one(date_sel)
            if node:
                date_text = node.get_text(" ", strip=True)

        # --- link (facoltativo) ---
        url = ""
        link_sel = sel.get("link", "a")
        if link_sel == "self" and container.name == "a":
            url = container.get("href", "")
        else:
            node = container.select_one(link_sel) if link_sel else None
            if node and node.get("href"):
                url = node["href"]
            elif container.name == "a":
                url = container.get("href", "")

        ev = Event(
            track_slug=config.slug,
            track_name=config.name,
            title=title,
            date_text=date_text,
            url=url,
        )
        events[ev.event_id] = ev

    return list(events.values())


class BaseTrackScraper(ABC):
    """Interfaccia comune a tutti gli scraper di autodromo."""

    def __init__(self, config: TrackConfig):
        self.config = config

    @abstractmethod
    def scrape(self) -> list[Event]:
        """Restituisce la lista GREZZA di eventi trovati sul sito
        (il filtro motorsport/non-motorsport viene applicato dopo, in main.py).
        """
        raise NotImplementedError
