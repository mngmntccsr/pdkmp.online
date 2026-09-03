"""Scraper per autoraduni.it (homepage).

Sito WordPress statico, niente JavaScript necessario. Ogni evento è un
<div class="listing-item-container" data-listing-type="event"> con TUTTI i
campi utili già negli attributi HTML (niente parsing testuale fragile):

  data-title           = titolo evento
  data-friendly-address = città (senza provincia)
  data-event-date       = "DD/MM/YYYY - DD/MM/YYYY" oppure, per eventi di
                           un solo giorno, "DD/MM/YYYY - " (nota il
                           trattino finale seguito da stringa vuota)

più, dentro al container:
  <span class="tag">Categoria</span>   categoria: Autoraduni / Fiere /
                                        Mostra / Rievocazione / Corse
  <a class="listing-item" href="...">  link alla pagina di dettaglio

Non essendoci un "circuito" fisico per raduni/fiere/mostre (si svolgono
in piazze, parchi, location varie), usiamo la CITTÀ anche come circuito,
per coerenza con la stessa scelta fatta per i rally (vedi rallylink.py).

Le categorie Autoraduni/Fiere/Mostra/Rievocazione vengono mappate alla
disciplina "Raduno" (categoria dedicata sul sito). La categoria "Corse"
(gare vere e proprie ospitate su questo aggregatore) viene invece lasciata
alla normale inferenza automatica della disciplina da titolo.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from src.models import Event
from src.scrapers.base import BaseTrackScraper, download_event_image, fetch_html_static

RADUNO_CATEGORIES = {"autoraduni", "fiere", "mostra", "rievocazione"}


def _parse_date_range(raw: str) -> tuple[str, str] | None:
    """'30/08/2026 - 06/09/2026' oppure '30/08/2026 - ' (un solo giorno)."""
    if not raw:
        return None
    parts = [p.strip() for p in raw.split("-")]
    start_raw = parts[0]
    end_raw = parts[1] if len(parts) > 1 and parts[1] else start_raw

    def to_iso(d: str) -> str | None:
        bits = d.split("/")
        if len(bits) != 3:
            return None
        day, month, year = bits
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    start_iso = to_iso(start_raw)
    end_iso = to_iso(end_raw)
    if not start_iso:
        return None
    return start_iso, end_iso or start_iso


class AutoraduniScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_static(self.config.url)
        soup = BeautifulSoup(html, "lxml")

        events: dict[str, Event] = {}

        for container in soup.find_all("div", attrs={"data-listing-type": "event"}):
            title = container.get("data-title", "").strip()
            citta = container.get("data-friendly-address", "").strip()
            date_raw = container.get("data-event-date", "").strip()
            if not title or not citta or not date_raw:
                continue

            parsed_dates = _parse_date_range(date_raw)
            if not parsed_dates:
                continue
            start_iso, end_iso = parsed_dates

            tag_el = container.find("span", class_="tag")
            category = tag_el.get_text(strip=True).lower() if tag_el else ""

            link_el = container.find("a", class_="listing-item")
            href = link_el.get("href", self.config.url) if link_el else self.config.url
            disciplina_override = ["Raduno"] if category in RADUNO_CATEGORIES else None
            img_tag = container.find("img")
            immagine_url = ""
            if img_tag:
                src = img_tag.get("data-src") or img_tag.get("src", "")
                if src and not src.startswith("http"):
                    src = f"https://www.autoraduni.it{src}"
                if src:
                    immagine_url = download_event_image(src, "autoraduni") or ""
          
            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=title,
                date_text=f"{start_iso} - {end_iso}",   # solo riferimento/debug
                url=href,
                date_start=start_iso,
                date_end=end_iso,
                circuito_override=citta,   # niente circuito fisico: usiamo la città
                citta_override=citta,
                disciplina_override=disciplina_override,
                immagine_override=immagine_url,
            )
            events[ev.event_id] = ev

        return list(events.values())
