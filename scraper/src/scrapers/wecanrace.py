"""Scraper per We Can Race (wecanrace.it/calendario/).

Non è il calendario di UN autodromo, ma di UN'AZIENDA che vende esperienze
di guida in supercar a noleggio (Ferrari, Lamborghini) su decine di
autodromi italiani diversi. Ogni "evento" è quindi lo stesso prodotto
commerciale, ripetuto su tante combinazioni data+circuito.

Il sito è una app React (serve Playwright) organizzata così:
  <h3>Febbraio 2026</h3>                      <- intestazione mese, testo pieno
  <div class="grid ...">
    <div class="group relative text-left">     <- una "card" per ogni data
      <div>21</div>                             giorno (SENZA anno/mese: vanno
      <div>Sabato</div>                         dedotti dall'ultima <h3> vista)
      <div>Autodromo Enzo e Dino Ferrari</div>   nome circuito (CAMBIA per evento!)
      <div>Imola (BO)</div>                      città (provincia)
      <div>19º evento su questo circuito</div>
    </div>
    ...
  </div>

Le date già passate hanno la classe CSS "line-through" (barrate a schermo):
le scartiamo subito, non solo più avanti col filtro generale sulle date.

Non essendoci un link diretto per ogni singola data, linkInfo punta alla
pagina generale del calendario.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_dynamic

IT_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}

MONTH_YEAR_RE = re.compile(r"^([a-zàèéìòù]+)\s+(\d{4})$", re.IGNORECASE)
CITY_PROVINCE_RE = re.compile(r"^(.+?)\s*\(([A-Za-z]{2})\)$")


class WeCanRaceScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_dynamic(self.config.url, wait_selector=self.config.wait_selector)
        soup = BeautifulSoup(html, "lxml")

        events: dict[str, Event] = {}
        current_month: int | None = None
        current_year: int | None = None

        for el in soup.find_all(["h3", "div"]):
            if el.name == "h3":
                m = MONTH_YEAR_RE.match(el.get_text(strip=True))
                if m:
                    month_num = IT_MONTHS.get(m.group(1).lower())
                    if month_num:
                        current_month = month_num
                        current_year = int(m.group(2))
                continue

            classes = el.get("class") or []
            if not ("group" in classes and "relative" in classes and "text-left" in classes):
                continue
            if current_month is None:
                continue   # non abbiamo ancora incontrato nessuna intestazione mese

            # salta le date già passate (barrate sul sito)
            if el.find(class_=lambda c: c and "line-through" in c):
                continue

            parts = [p for p in el.get_text("|", strip=True).split("|") if p.strip()]
            if len(parts) < 4:
                continue
            day_str, _weekday, circuito, citta_prov = parts[0], parts[1], parts[2], parts[3]
            if not day_str.isdigit():
                continue

            start_iso = f"{current_year}-{current_month:02d}-{int(day_str):02d}"

            city_match = CITY_PROVINCE_RE.match(citta_prov)
            citta = city_match.group(1).strip() if city_match else citta_prov

            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=f"We Can Race - Guida in pista a {circuito}",
                date_text=start_iso,   # solo riferimento/debug
                url=self.config.url,
                date_start=start_iso,
                date_end=start_iso,    # eventi di un solo giorno
                circuito_override=circuito,
                citta_override=citta,
            )
            events[ev.event_id] = ev

        return list(events.values())
