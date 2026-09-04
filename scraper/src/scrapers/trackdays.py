"""Scraper per Track-Days.it (https://track-days.it/calendario/).

Il calendario di Track-Days.it espone una riga per ogni giorno, ma lo stesso
evento può occupare più giorni e condividere lo stesso link. Per PaddokMap
queste righe devono diventare UN SOLO evento.

Regola principale:
    stesso URL della pagina prodotto + stesso mese/anno
    -> un unico Event con date_start/date_end.

Esempio:
    sabato 19 -> /negozio/.../track-day-racalmuto/
    domenica 20 -> /negozio/.../track-day-racalmuto/
    => 2026-09-19 / 2026-09-20

Il sito è server-rendered: usiamo requests + BeautifulSoup, senza Playwright.
La struttura viene cercata per contenuto, non per classi CSS fragili.
"""

from __future__ import annotations

import re
from datetime import date as date_cls

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_static

IT_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

WEEKDAYS_IT = {
    "lunedì",
    "martedì",
    "mercoledì",
    "giovedì",
    "venerdì",
    "sabato",
    "domenica",
}

MONTH_YEAR_RE = re.compile(
    r"^([a-zàèéìòù]+)\s+(\d{4})$",
    re.IGNORECASE,
)

DAY_RE = re.compile(r"^(?:[a-zàèéìòù]+)\s+(\d{1,2})$", re.IGNORECASE)


def _parse_day(text: str) -> int | None:
    """Estrae il numero giorno da 'sabato 19'."""
    m = DAY_RE.match(" ".join(text.split()))
    if not m:
        return None
    day = int(m.group(1))
    return day if 1 <= day <= 31 else None


def _find_month_year(soup: BeautifulSoup) -> tuple[int, int] | None:
    """Trova il mese/anno del calendario.

    Il calendario attuale contiene un solo mese/anno visibile per blocco.
    Se in futuro verranno mostrati più mesi contemporaneamente, lo scraper
    usa _iter_month_sections() qui sotto.
    """
    for heading in soup.find_all(["h2", "h3", "h4"]):
        text = heading.get_text(" ", strip=True)
        m = MONTH_YEAR_RE.match(text)
        if m:
            month = IT_MONTHS.get(m.group(1).lower())
            if month:
                return month, int(m.group(2))
    return None


def _iter_month_sections(soup: BeautifulSoup):
    """Yield (month, year, elements) per ogni intestazione mese trovata."""
    headings = []
    for heading in soup.find_all(["h2", "h3", "h4"]):
        text = heading.get_text(" ", strip=True)
        m = MONTH_YEAR_RE.match(text)
        if not m:
            continue
        month = IT_MONTHS.get(m.group(1).lower())
        if month:
            headings.append((heading, month, int(m.group(2))))

    if not headings:
        yield None, None, soup.find_all(True)
        return

    for idx, (heading, month, year) in enumerate(headings):
        elements = []
        for sibling in heading.next_elements:
            if sibling is headings[idx + 1][0] if idx + 1 < len(headings) else False:
                break
            if getattr(sibling, "name", None):
                elements.append(sibling)
        yield month, year, elements


def _is_past_or_invalid(d: date_cls) -> bool:
    return d < date_cls.today()


def _extract_day_link_rows(soup: BeautifulSoup) -> list[dict]:
    """Estrae le coppie giorno/link dalla pagina calendario.

    Strategia robusta:
    - cerca link che puntano a /negozio/ (le pagine prodotto degli eventi);
    - risale al contenitore vicino del link;
    - cerca nel contenitore un testo 'sabato 19', 'domenica 20', ecc.;
    - associa il mese/anno tramite l'heading più vicino.
    """
    rows: list[dict] = []

    # Per il layout attuale il mese è un heading prima delle relative righe.
    current_month: int | None = None
    current_year: int | None = None

    for element in soup.find_all(["h2", "h3", "h4", "a"]):
        if element.name in {"h2", "h3", "h4"}:
            m = MONTH_YEAR_RE.match(element.get_text(" ", strip=True))
            if m:
                current_month = IT_MONTHS.get(m.group(1).lower())
                current_year = int(m.group(2)) if current_month else None
            continue

        href = element.get("href", "")
        if "/negozio/" not in href:
            continue

        title = element.get_text(" ", strip=True)
        if not title:
            continue

        # Risali solo pochi livelli: vogliamo il blocco del singolo giorno,
        # non l'intero mese.
        container = element
        day = None
        for _ in range(6):
            parent = getattr(container, "parent", None)
            if parent is None:
                break
            container = parent

            # Cerca prima testi esatti tipo "sabato 19".
            for txt in container.stripped_strings:
                candidate = _parse_day(txt)
                if candidate is not None:
                    day = candidate
                    break
            if day is not None:
                break

        if day is None or current_month is None or current_year is None:
            continue

        try:
            event_date = date_cls(current_year, current_month, day)
        except ValueError:
            continue

        rows.append(
            {
                "date": event_date,
                "title": title,
                "url": urljoin("https://track-days.it/", href),
            }
        )

    return rows


def _group_rows(rows: list[dict]) -> list[Event]:
    """Raggruppa le giornate che appartengono alla stessa pagina evento.

    L'URL è la chiave primaria perché Track-Days.it riusa lo stesso prodotto
    per tutte le date disponibili. Se per lo stesso URL esistono più blocchi
    separati (es. 19-20 settembre e 19-20 dicembre), il mese/anno fa da
    separatore.
    """
    groups: dict[tuple[str, int, int], list[dict]] = {}

    for row in rows:
        key = (row["url"], row["date"].year, row["date"].month)
        groups.setdefault(key, []).append(row)

    events: list[Event] = []

    for (url, _year, _month), group in groups.items():
        group.sort(key=lambda x: x["date"])

        # Le date non devono necessariamente essere consecutive: il sito
        # potrebbe mostrare più date dello stesso prodotto nello stesso mese.
        # In quel caso manteniamo comunque un solo evento perché la pagina
        # prodotto rappresenta lo stesso evento/prodotto Track-Day.
        start = group[0]["date"]
        end = group[-1]["date"]

        title = group[0]["title"]
        # Se i titoli differiscono leggermente, preferiamo il più lungo:
        # normalmente contiene il nome completo del circuito.
        for row in group[1:]:
            if len(row["title"]) > len(title):
                title = row["title"]

        ev = Event(
            track_slug="trackdays",
            track_name="Track-Days.it",
            title=title,
            date_text=f"{start.isoformat()} - {end.isoformat()}",
            url=url,
            date_start=start.isoformat(),
            date_end=end.isoformat(),
            disciplina_override=["Trackday"],
            evento_gratuito_override=True,
        )
        events.append(ev)

    return events


class TrackDaysScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_static(self.config.url)
        soup = BeautifulSoup(html, "lxml")

        rows = _extract_day_link_rows(soup)

        # Elimina date già concluse. Il filtro generale del progetto lo fa
        # comunque più avanti, ma qui evitiamo di creare eventi inutili.
        rows = [r for r in rows if not _is_past_or_invalid(r["date"])]

        events = _group_rows(rows)

        # Dedup finale per sicurezza.
        unique: dict[str, Event] = {}
        for event in events:
            unique[event.event_id] = event

        return list(unique.values())
