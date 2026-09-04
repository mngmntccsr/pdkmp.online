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

IT_MONTHS = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
    "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12}
_DATE_RE = re.compile(
    r"\b(?:lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)\s+(\d{1,2})\s+([a-zàèéìòù]+)\s+(\d{4})\b",
    re.IGNORECASE)
_H3_RE = re.compile(r"^(.+?)\s*\(([A-Za-z]{2})\)")


# Nomi reali dei circuiti (l'h3 del sito usa solo il nome della località).
# Aggiungi qui altri nomi man mano che li scopri.
CIRCUIT_TRACK_NAMES = {
    "Ortona": "Circuito Internazionale d'Abruzzo",
    "Adria": "Adria International Raceway",
    "Arese": "Autodromo di Arese", 
    "Bar": "Autodromo del Levante",
    "Burino": "Cerrina Race Track",
    "Castelletto di Branduzzo": "Castelletto Circuit",
    "Franciacorta": "Franciacorta Karting Circuit",
    "Imola": "Autodromo Nazionale Enzo e Dino Ferrari",
    "Magione": "Autodromo Nazionale dell'Umbria",
    "Misano": "Misano World Circuit",
    "Mugello": "Mugello Circuit",
    "Pergusa": "Autodromo di Pergusa",
    "Pomposa": "Circuito di Pomposa",
    "Sele": "Circuito del Sele",
    "Siena": "Circuito di Siena",
    "Tazio Nuvolari": "Circuito Tazio Nuvolari",
    "Tazio Nuvolari 5260": "Circuito Tazio Nuvolari",
    "Vallelunga": "Autodromo di Vallelunga Piero Taruffi", 
    "Varano De' Melegari": "Autodromo Riccardo Paletti",
    "Viterbo": "Circuito Internazionale di Viterbo"
}


class RseItaliaScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        from datetime import date as date_cls, timedelta

        html = fetch_html_static(self.config.url)
        soup = BeautifulSoup(html, "lxml")
        raw_days = []   # (localita, giorno)

        for h3 in soup.find_all("h3"):
            m = _H3_RE.match(h3.get_text(strip=True))
            if not m:
                continue
            localita = m.group(1).strip()

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
                raw_days.append((localita, date_cls(int(year), month_num, int(day))))

        raw_days = sorted(set(raw_days))
        events: dict[str, Event] = {}
        i = 0
        while i < len(raw_days):
            localita, start = raw_days[i]
            end = start
            j = i + 1
            while j < len(raw_days) and raw_days[j][0] == localita and raw_days[j][1] == end + timedelta(days=1):
                end = raw_days[j][1]
                j += 1

            circuito = CIRCUIT_TRACK_NAMES.get(localita, localita)
            ev = Event(
                track_slug=self.config.slug, track_name=self.config.name,
                title=f"RSE Italia - Guida in pista a {circuito}",
                date_text=f"{start.isoformat()} - {end.isoformat()}",
                url=self.config.url,
                date_start=start.isoformat(), date_end=end.isoformat(),
                circuito_override=circuito, citta_override=localita,
                disciplina_override=["Trackday"],
            )
            events[ev.event_id] = ev
            i = j
        return list(events.values())
