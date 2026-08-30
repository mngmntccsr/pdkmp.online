"""Scraper per We Can Race (wecanrace.it/calendario/).

Non è il calendario di UN autodromo, ma di UN'AZIENDA che vende esperienze
di guida in supercar a noleggio (Ferrari, Lamborghini) su decine di
autodromi italiani diversi. Ogni "evento" è quindi lo stesso prodotto
commerciale, ripetuto su tante combinazioni data+circuito.

Il sito è una app React (serve Playwright) organizzata così:
  <h3>Febbraio 2026</h3>                      <- intestazione mese, testo pieno
  <div class="grid ...">
    <div class="group relative text-left">     <- una "card" per ogni SINGOLO GIORNO
      <div>21</div>                             giorno (SENZA anno/mese: vanno
      <div>Sabato</div>                         dedotti dall'ultima <h3> vista)
      <div>Autodromo Enzo e Dino Ferrari</div>   nome circuito (CAMBIA per evento!)
      <div>Imola (BO)</div>                      città (provincia)
      <div>19º evento su questo circuito</div>
    </div>
    ...
  </div>

IMPORTANTE: alcune card (tipicamente quelle più lontane nel tempo, es. per
il 2027) hanno un elemento di testo IN PIÙ rispetto alle altre (es. un
badge non sempre presente). Un parsing "posizionale" (campo N-esimo = X)
si rompe in quei casi, spostando tutti i campi di una posizione e facendo
finire — ad esempio — il giorno della settimana al posto del circuito.
Per questo motivo identifichiamo ogni campo dal SUO CONTENUTO (giorno del
mese, nome di un giorno della settimana, "Città (XX)", testo del
contatore) invece che dalla sua posizione nell'elenco: è molto più
robusto a variazioni della struttura.

Il sito mostra un giorno per card anche quando in realtà si tratta di UN
unico evento su più giorni (tipicamente sabato+domenica): dopo aver letto
tutte le card, raggruppiamo quindi i giorni CONSECUTIVI dello STESSO
circuito in un unico Event con date_start/date_end che coprono l'intero
intervallo, così sul sito compare una sola card invece di una per giorno.

Le date già passate hanno la classe CSS "line-through" (barrate a schermo):
le scartiamo subito, non solo più avanti col filtro generale sulle date.

Non essendoci un link diretto per ogni singola data, linkInfo punta alla
pagina generale del calendario.
"""
from __future__ import annotations

import re
from datetime import date as date_cls, timedelta

from bs4 import BeautifulSoup

from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_dynamic

IT_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
WEEKDAYS_IT = {
    "lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica",
}

MONTH_YEAR_RE = re.compile(r"^([a-zàèéìòù]+)\s+(\d{4})$", re.IGNORECASE)
CITY_PROVINCE_RE = re.compile(r"^(.+?)\s*\(([A-Za-z]{2})\)$")
COUNTER_RE = re.compile(r"evento\s+su\s+questo\s+circuito", re.IGNORECASE)


def _parse_card_fields(parts: list[str]) -> tuple[str, str] | None:
    """Identifica giorno del mese e "città (provincia)" dal contenuto dei
    campi della card (non dalla posizione), poi assume che il CIRCUITO sia
    il primo campo restante non riconosciuto come nessuno degli altri.
    Restituisce (day_str, circuito, citta) oppure None se non interpretabile.
    """
    day_idx = weekday_idx = citta_idx = counter_idx = None
    citta_prov = None

    for idx, p in enumerate(parts):
        if day_idx is None and p.isdigit() and 1 <= int(p) <= 31:
            day_idx = idx
        elif weekday_idx is None and p.strip().lower() in WEEKDAYS_IT:
            weekday_idx = idx
        elif citta_idx is None and CITY_PROVINCE_RE.match(p):
            citta_idx = idx
            citta_prov = p
        elif counter_idx is None and COUNTER_RE.search(p):
            counter_idx = idx

    if day_idx is None or citta_idx is None:
        return None   # card non interpretabile, meglio saltarla che sbagliare

    known = {day_idx, weekday_idx, citta_idx, counter_idx} - {None}
    # scarta simboli isolati (es. un asterisco di nota/disclaimer che alcune
    # card hanno in più): un vero nome di circuito contiene sempre almeno
    # un paio di lettere consecutive
    remaining = [
        p for i, p in enumerate(parts)
        if i not in known and re.search(r"[A-Za-zÀ-ÿ]{2,}", p)
    ]
    if not remaining:
        return None
    circuito = remaining[0]

    city_match = CITY_PROVINCE_RE.match(citta_prov)
    citta = city_match.group(1).strip() if city_match else citta_prov

    return parts[day_idx], circuito, citta


class WeCanRaceScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        html = fetch_html_dynamic(self.config.url, wait_selector=self.config.wait_selector)
        soup = BeautifulSoup(html, "lxml")

        # --- passata 1: raccoglie ogni singolo giorno-card ---
        raw_days: list[dict] = []
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
            parsed = _parse_card_fields(parts)
            if parsed is None:
                continue
            day_str, circuito, citta = parsed

            try:
                day = date_cls(current_year, current_month, int(day_str))
            except ValueError:
                continue

            raw_days.append({"circuito": circuito, "citta": citta, "day": day})

        # --- passata 2: raggruppa i giorni consecutivi dello stesso circuito ---
        raw_days.sort(key=lambda d: (d["circuito"], d["day"]))

        events: dict[str, Event] = {}
        i = 0
        while i < len(raw_days):
            group = [raw_days[i]]
            j = i + 1
            while (
                j < len(raw_days)
                and raw_days[j]["circuito"] == group[-1]["circuito"]
                and raw_days[j]["day"] == group[-1]["day"] + timedelta(days=1)
            ):
                group.append(raw_days[j])
                j += 1

            circuito = group[0]["circuito"]
            citta = group[0]["citta"]
            start_iso = group[0]["day"].isoformat()
            end_iso = group[-1]["day"].isoformat()

            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=f"We Can Race - Guida in pista a {circuito}",
                date_text=f"{start_iso} - {end_iso}",   # solo riferimento/debug
                url=self.config.url,
                date_start=start_iso,
                date_end=end_iso,
                circuito_override=circuito,
                citta_override=citta,
                disciplina_override=["Trackday"],
            )
            events[ev.event_id] = ev
            i = j

        return list(events.values())

        # --- passata 2: raggruppa i giorni consecutivi dello stesso circuito ---
        raw_days.sort(key=lambda d: (d["circuito"], d["day"]))

        events: dict[str, Event] = {}
        i = 0
        while i < len(raw_days):
            group = [raw_days[i]]
            j = i + 1
            while (
                j < len(raw_days)
                and raw_days[j]["circuito"] == group[-1]["circuito"]
                and raw_days[j]["day"] == group[-1]["day"] + timedelta(days=1)
            ):
                group.append(raw_days[j])
                j += 1

            circuito = group[0]["circuito"]
            citta = group[0]["citta"]
            start_iso = group[0]["day"].isoformat()
            end_iso = group[-1]["day"].isoformat()

            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=f"We Can Race - Guida in pista a {circuito}",
                date_text=f"{start_iso} - {end_iso}",   # solo riferimento/debug
                url=self.config.url,
                date_start=start_iso,
                date_end=end_iso,
                circuito_override=circuito,
                citta_override=citta,
            )
            events[ev.event_id] = ev
            i = j

        return list(events.values())
