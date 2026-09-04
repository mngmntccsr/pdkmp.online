"""Scraper per RSE Italia (rseitalia.it/calendario/) — noleggio supercar
in pista su decine di circuiti italiani. Sito statico, una sola pagina.

Per ogni circuito: <h3>Nome (PROV) ... – Km X</h3> seguito da un elenco
"Date disponibili" con date scritte per esteso, es. "domenica 11 Ottobre 2026"
(già con l'anno, nessuna ambiguità). La pagina ripete ogni blocco due volte
(versione mobile/desktop): non serve gestirlo, l'hash dell'evento dedupe
automaticamente.
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_static
from src.scrapers.rallylink import PROVINCE_NAMES

IT_MONTHS = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
    "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12}
_DATE_RE = re.compile(
    r"\b(?:lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\s+(\d{1,2})\s+([a-zàèéìòù]+)\s+(\d{4})\b",
    re.IGNORECASE)
_H3_RE = re.compile(r"^(.+?)\s*\(([A-Za-z]{2})\)")


class RseItaliaScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_static(self.config.url)
        soup = BeautifulSoup(html, "lxml")
        events: dict[str, Event] = {}

        for h3 in soup.find_all("h3"):
            m = _H3_RE.match(h3.get_text(strip=True))
            if not m:
                continue
            circuito, prov = m.group(1).strip(), m.group(2).upper()
            citta = PROVINCE_NAMES.get(prov, prov)

            # cerca le date fino al prossimo h3
            text_block = []
            for sib in h3.find_all_next():
                if sib.name == "h3":
                    break
                text_block.append(sib.get_text(" ", strip=True))
            block_text = " ".join(text_block)

            for dm in _DATE_RE.finditer(block_text):
                day, month_it, year = dm.group(1), dm.group(2).lower(), dm.group(3)
                month_num = IT_MONTHS.get(month_it)
                if not month_num:
                    continue
                iso = f"{year}-{month_num:02d}-{int(day):02d}"
                ev = Event(
                    track_slug=self.config.slug, track_name=self.config.name,
                    title=f"RSE Italia - Guida in pista a {circuito}",
                    date_text=iso, url=self.config.url,
                    date_start=iso, date_end=iso,
                    circuito_override=circuito, citta_override=citta,
                    disciplina_override=["Trackday"],
                )
                events[ev.event_id] = ev
        return list(events.values())
