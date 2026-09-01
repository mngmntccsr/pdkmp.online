"""Scraper per raduni-auto.it — Raduni, fiere e regolarità in tutta Italia.

Sito statico (server-rendered), niente JavaScript necessario per il primo
batch di risultati. Ogni card evento è un link a /raduno/<slug> che
racchiude un'immagine con un attributo "alt" MOLTO ricco, che contiene già
tutto ciò che ci serve in un'unica stringa:

    "{TITOLO} - {CATEGORIA} a {CITTÀ} ({PROV}) il {giorno settimana} {DD} {mese} {YYYY}"

Esempio reale:
    "5° Raduno Auto Moto d'Epoca e Sportive - Los Angeles Motor Day -
     Auto d'Epoca a Sant'Angelo di Piove di Sacco (PD) il venerdì 4
     settembre 2026"

Per isolare TITOLO da CATEGORIA (entrambi possono contenere trattini)
sfruttiamo il fatto che la categoria è sempre l'ultimo segmento prima di
" a {città}": prendiamo quindi tutto il prefisso prima di " a ", poi lo
tagliamo sull'ULTIMO " - " per separare titolo e categoria.

Il sito pagina i risultati (?vista=griglia&page=N): continuiamo a
richiedere pagine finché ne troviamo di nuove, con un tetto di sicurezza.

PREZZO: nella card compare "Gratuito" oppure "da € X,XX". Cerchiamo questo
testo nel contenitore più piccolo che racchiude l'immagine E un solo link
"/organizzatore/" (per non "rubare" il prezzo di una card vicina).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.config import load_keywords
from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_static
from src.text_utils import normalize_title_case

IT_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}

_ALT_RE = re.compile(
    r"^(?P<prefix>.+?)\s+a\s+(?P<citta>.+?)\s*\(([A-Za-z]{2})\)\s+il\s+\w+\s+(\d{1,2})\s+([a-zàèéìòù]+)\s+(\d{4})$",
    re.IGNORECASE,
)

# Le categorie diverse da "Regolarità" (una gara di regolarità cronometrata,
# più vicina al motorsport) finiscono tutte sotto "Raduno".
_DISCIPLINE_MAP = {
    "regolarità": "Rally",
}

MAX_PAGES = 15   # tetto di sicurezza sulla paginazione


def _parse_alt(alt_text: str) -> tuple[str, str, str, str, str] | None:
    m = _ALT_RE.match(alt_text.strip())
    if not m:
        return None

    prefix = m.group("prefix")
    citta = m.group("citta").strip()
    prov = m.group(3)
    day, month_it, year = m.group(4), m.group(5).lower(), m.group(6)

    month_num = IT_MONTHS.get(month_it)
    if not month_num:
        return None
    iso = f"{year}-{month_num:02d}-{int(day):02d}"

    if " - " in prefix:
        titolo, categoria = prefix.rsplit(" - ", 1)
    else:
        titolo, categoria = prefix, ""

    return titolo.strip(), categoria.strip(), citta, prov, iso


def _detect_free(container) -> bool:
    text = container.get_text(" ", strip=True)
    if re.search(r"\bgratuito\b", text, re.IGNORECASE):
        return True
    return False   # include il caso "da € X,XX" e il caso non determinato


class RaduniAutoScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        keywords = load_keywords()
        proper_nouns = keywords.get("rally_proper_nouns", [])   # lista condivisa tra fonti

        events: dict[str, Event] = {}
        base_url = self.config.url.rstrip("/")

        for page in range(1, MAX_PAGES + 1):
            page_url = f"{base_url}?vista=griglia&page={page}"
            html = fetch_html_static(page_url)
            soup = BeautifulSoup(html, "lxml")

            cards = soup.find_all("a", href=lambda h: h and "/raduno/" in h)
            if not cards:
                break   # pagina vuota, ci fermiamo

            found_on_this_page = 0

            for card_link in cards:
                img = card_link.find("img")
                if not img or not img.get("alt"):
                    continue

                parsed = _parse_alt(img["alt"])
                if not parsed:
                    continue
                titolo_raw, categoria, citta, prov, start_iso = parsed

                titolo = normalize_title_case(titolo_raw, proper_nouns)
                disciplina = [_DISCIPLINE_MAP.get(categoria.lower(), "Raduno")]

                # risale per trovare un contenitore "compatto" (una sola
                # card) da cui leggere il prezzo, senza rischiare di
                # prendere quello di una card vicina
                container = card_link
                gratuito = False
                for _ in range(6):
                    if container.parent is None:
                        break
                    container = container.parent
                    org_links = container.find_all("a", href=lambda h: h and "/organizzatore/" in h)
                    if len(org_links) == 1:
                        gratuito = _detect_free(container)
                        break
                    if len(org_links) > 1:
                        break   # contenitore troppo ampio, non tentiamo

                href = card_link["href"]
                if not href.startswith("http"):
                    href = f"https://raduni-auto.it{href}"

                ev = Event(
                    track_slug=self.config.slug,
                    track_name=self.config.name,
                    title=titolo,
                    date_text=start_iso,   # solo riferimento/debug
                    url=href,
                    date_start=start_iso,
                    date_end=start_iso,   # il sito mostra solo una data per evento
                    circuito_override=citta,
                    citta_override=citta,
                    disciplina_override=disciplina,
                    evento_gratuito_override=gratuito,
                )

                if ev.event_id not in events:
                    found_on_this_page += 1
                events[ev.event_id] = ev

            if found_on_this_page == 0:
                break   # tutti gli eventi di questa pagina erano già noti, fine

        return list(events.values())
