"""Scraper per raduni-auto.it — Raduni, fiere e regolarità in tutta Italia.

Sito statico (server-rendered), niente JavaScript necessario per il primo
batch di risultati. Ogni evento ha un'immagine con un attributo "alt"
MOLTO ricco, che contiene già tutto ciò che ci serve in un'unica stringa:

    "{TITOLO} - {CATEGORIA} a {CITTÀ} ({PROV}) il {giorno settimana} {DD} {mese} {YYYY}"

Per isolare TITOLO da CATEGORIA (entrambi possono contenere trattini)
sfruttiamo il fatto che la categoria è sempre l'ultimo segmento prima di
" a {città}": prendiamo quindi tutto il prefisso prima di " a ", poi lo
tagliamo sull'ULTIMO " - " per separare titolo e categoria.

IMPORTANTE: non assumiamo che <img> sia annidata dentro <a href="/raduno/">
— nel vero HTML sono elementi adiacenti separati. Cerchiamo quindi le
immagini con alt "ricco" direttamente, poi risaliamo al link /raduno/ più
vicino nel documento.

Il sito pagina i risultati (?vista=griglia&page=N): continuiamo a
richiedere pagine finché ne troviamo di nuove, con un tetto di sicurezza.

PREZZO: cerchiamo la parola "Gratuito" nel testo tra un'immagine evento e
la successiva, per non "rubare" il prezzo di una card vicina.

IMMAGINE: usiamo direttamente il src dell'immagine come locandina
dell'evento sulla scheda del sito.
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

_DISCIPLINE_MAP = {
    "regolarità": "Rally",
}

MAX_PAGES = 15


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


class RaduniAutoScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        keywords = load_keywords()
        proper_nouns = keywords.get("rally_proper_nouns", [])

        events: dict[str, Event] = {}
        base_url = self.config.url.rstrip("/")

        for page in range(1, MAX_PAGES + 1):
            page_url = f"{base_url}?vista=griglia&page={page}"
            html = fetch_html_static(page_url)
            soup = BeautifulSoup(html, "lxml")

            imgs = soup.find_all("img", alt=lambda a: a and " il " in a)
            if not imgs:
                break

            found_on_this_page = 0

            for img in imgs:
                parsed = _parse_alt(img["alt"])
                if not parsed:
                    continue
                titolo_raw, categoria, citta, prov, start_iso = parsed

                card_link = img.find_previous("a", href=lambda h: h and "/raduno/" in h)
                href = card_link["href"] if card_link else base_url
                if not href.startswith("http"):
                    href = f"https://raduni-auto.it{href}"

                titolo = normalize_title_case(titolo_raw, proper_nouns)
                disciplina = [_DISCIPLINE_MAP.get(categoria.lower(), "Raduno")]

                next_img = img.find_next("img", alt=lambda a: a and " il " in a)
                collected_text = []
                for node in img.find_all_next(string=True, limit=80):
                    if next_img is not None and node.find_previous("img", alt=lambda a: a and " il " in a) is next_img:
                        break
                    collected_text.append(str(node))
                gratuito = bool(re.search(r"\bgratuito\b", " ".join(collected_text), re.IGNORECASE))

                immagine_url = (
                    img.get("data-src")
                    or img.get("data-lazy-src")
                    or img.get("src", "")
                )
                if immagine_url and not immagine_url.startswith("http"):
                    immagine_url = f"https://raduni-auto.it{immagine_url}"

                ev = Event(
                    track_slug=self.config.slug,
                    track_name=self.config.name,
                    title=titolo,
                    date_text=start_iso,
                    url=href,
                    date_start=start_iso,
                    date_end=start_iso,
                    circuito_override=citta,
                    citta_override=citta,
                    disciplina_override=disciplina,
                    evento_gratuito_override=gratuito,
                    immagine_override=immagine_url,
                )

                if ev.event_id not in events:
                    found_on_this_page += 1
                events[ev.event_id] = ev

            if found_on_this_page == 0:
                break

        return list(events.values())
