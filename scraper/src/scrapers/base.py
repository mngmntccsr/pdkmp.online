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

# IMPORTANTE: uno User-Agent con un suffisso "da bot" (es. nome dello
# scraper + link) è un segnale che molti sistemi anti-bot riconoscono e
# bloccano subito. Usiamo uno user agent identico a un vero browser Chrome
# aggiornato, senza alcuna firma che ci identifichi come script.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

EXTRA_HTTP_HEADERS = {
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# Testi tipici dei bottoni "accetta i cookie" nei banner italiani/inglesi:
# se compaiono li clicchiamo, così eventuali script bloccati dal banner
# possono partire normalmente.
_COOKIE_BUTTON_TEXTS = [
    "Accetta tutti", "Accetta", "Accept all", "Accept All", "Accept",
    "Consenti tutti", "Consenti", "OK", "Ho capito",
]


def fetch_html_static(url: str, timeout: int = 20) -> str:
    """Scarica l'HTML di una pagina server-rendered."""
    headers = {"User-Agent": USER_AGENT, **EXTRA_HTTP_HEADERS}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text

def fetch_csv_static(url: str, timeout: int = 20) -> str:
    """Come fetch_html_static, ma forza la decodifica UTF-8: i file CSV
    (es. l'export di Google Sheets) spesso non dichiarano l'encoding
    nell'header Content-Type, e la libreria requests di default decodifica
    come Latin-1 in quel caso, corrompendo le lettere accentate (es. "à"
    diventa "Ã "). Forzare esplicitamente UTF-8 risolve il problema.
    """
    headers = {"User-Agent": USER_AGENT, **EXTRA_HTTP_HEADERS}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text

def fetch_html_dynamic(
    url: str, wait_selector: str | None = None, timeout_ms: int = 30000,
    extra_wait_ms: int = 4000,
) -> str:
    """Apre la pagina con Playwright (Chromium headless) e restituisce l'HTML
    dopo il rendering JavaScript. Necessario per calendari costruiti con
    plugin/framework client-side (es. EventON su WordPress, app React/Vue).

    Include alcuni accorgimenti per siti con protezioni anti-bot o
    caricamento asincrono lento:
      - user agent "pulito" (vedi USER_AGENT sopra)
      - navigator.webdriver mascherato (molte protezioni lo controllano)
      - tentativo automatico di chiudere banner cookie che potrebbero
        bloccare script/richieste successive
      - una pausa extra dopo il "networkidle" per i siti che caricano i
        dati con una chiamata asincrona tardiva
      - uno scroll fino in fondo alla pagina, per attivare eventuale
        contenuto caricato "on scroll" (lazy loading)
    """
    from playwright.sync_api import sync_playwright  # import locale: costoso, solo se serve

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="it-IT",
            extra_http_headers=EXTRA_HTTP_HEADERS,
        )
        # maschera il segnale più comune usato per rilevare i browser
        # automatizzati (navigator.webdriver === true di default con Playwright)
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        try:
            page.goto(url, timeout=timeout_ms, wait_until="networkidle")

            # prova a chiudere un eventuale banner cookie
            for text in _COOKIE_BUTTON_TEXTS:
                try:
                    btn = page.get_by_text(text, exact=False).first
                    if btn.is_visible(timeout=1000):
                        btn.click(timeout=1000)
                        page.wait_for_timeout(500)
                        break
                except Exception:
                    continue

            # scroll fino in fondo, nel caso il contenuto sia caricato "on scroll"
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)
            except Exception:
                pass

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception:
                    logger.warning(
                        "Selettore d'attesa '%s' non trovato su %s entro %sms",
                        wait_selector, url, timeout_ms,
                    )

            # pausa extra per chiamate asincrone lente/tardive
            page.wait_for_timeout(extra_wait_ms)

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
