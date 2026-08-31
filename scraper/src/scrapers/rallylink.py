"""Scraper per rallylink.it — Calendario Rally Italiani.

I dati veri non sono nell'HTML della pagina rallylink.it, ma in un Google
Sheet pubblicato e incorporato via iframe. Leggiamo direttamente l'export
CSV del foglio (dati puliti colonna-per-colonna, senza l'ambiguità del
testo "appiattito" che si otterrebbe leggendo l'HTML della pagina).

Colonne del foglio: Data | Validità | Rally | Prov. | Altro | Altro | Altro
Usiamo solo le prime 4; le colonne "Altro" contengono note secondarie
(es. categoria "CRZ 6" ripetuta) che non ci servono.

Formati data osservati (senza anno, va preso da season_year in config):
  "14-15/2"     giorno-giorno/mese (stesso mese)
  "12/4"        giorno singolo
  "28/2-1/3"    giorno/mese-giorno/mese (a cavallo di due mesi)
  "4-6/06"      come il primo, con mese a due cifre
  "ANNULLATO"   evento cancellato, nessuna data -> lo scartiamo

Il foglio dà solo la PROVINCIA (es. "PV"), non la città esatta: la
traduciamo nel nome della provincia e la usiamo sia come "circuito" che
come "città" (i rally non hanno un circuito fisso, si svolgono su strada
— stessa convenzione already decisa per questa disciplina).

⚠️ MANUTENZIONE ANNUALE: l'URL del foglio (con l'ID lunghissimo) e il
"gid" sono SPECIFICI per la stagione 2026. Quando rallylink.it pubblica
il calendario dell'anno successivo, andranno aggiornati sia l'URL che
"season_year" in config/tracks.yaml — non c'è modo di renderlo automatico,
il sito non ha un URL stabile che valga per tutti gli anni.
"""
from __future__ import annotations

import csv
import io
import re

from src.config import load_keywords
from src.models import Event
from src.scrapers.base import BaseTrackScraper, fetch_html_static
from src.text_utils import normalize_title_case

# Sigle provinciali italiane (+ San Marino, che compare nel calendario
# pur non essendo una provincia italiana) -> nome esteso.
PROVINCE_NAMES = {
    "AG": "Agrigento", "AL": "Alessandria", "AN": "Ancona", "AO": "Aosta",
    "AR": "Arezzo", "AP": "Ascoli Piceno", "AT": "Asti", "AV": "Avellino",
    "BA": "Bari", "BT": "Barletta-Andria-Trani", "BL": "Belluno",
    "BN": "Benevento", "BG": "Bergamo", "BI": "Biella", "BO": "Bologna",
    "BZ": "Bolzano", "BS": "Brescia", "BR": "Brindisi", "CA": "Cagliari",
    "CL": "Caltanissetta", "CB": "Campobasso", "CI": "Carbonia-Iglesias",
    "CE": "Caserta", "CT": "Catania", "CZ": "Catanzaro", "CH": "Chieti",
    "CO": "Como", "CS": "Cosenza", "CR": "Cremona", "KR": "Crotone",
    "CN": "Cuneo", "EN": "Enna", "FM": "Fermo", "FE": "Ferrara",
    "FI": "Firenze", "FG": "Foggia", "FC": "Forlì-Cesena", "FR": "Frosinone",
    "GE": "Genova", "GO": "Gorizia", "GR": "Grosseto", "IM": "Imperia",
    "IS": "Isernia", "SP": "La Spezia", "AQ": "L'Aquila", "LT": "Latina",
    "LE": "Lecce", "LC": "Lecco", "LI": "Livorno", "LO": "Lodi",
    "LU": "Lucca", "MC": "Macerata", "MN": "Mantova", "MS": "Massa-Carrara",
    "MT": "Matera", "ME": "Messina", "MI": "Milano", "MO": "Modena",
    "MB": "Monza e della Brianza", "NA": "Napoli", "NO": "Novara",
    "NU": "Nuoro", "OR": "Oristano", "PD": "Padova", "PA": "Palermo",
    "PR": "Parma", "PV": "Pavia", "PG": "Perugia", "PU": "Pesaro e Urbino",
    "PE": "Pescara", "PC": "Piacenza", "PI": "Pisa", "PT": "Pistoia",
    "PN": "Pordenone", "PZ": "Potenza", "PO": "Prato", "RG": "Ragusa",
    "RA": "Ravenna", "RC": "Reggio Calabria", "RE": "Reggio Emilia",
    "RI": "Rieti", "RN": "Rimini", "RM": "Roma", "RO": "Rovigo",
    "SA": "Salerno", "SS": "Sassari", "SV": "Savona", "SI": "Siena",
    "SR": "Siracusa", "SO": "Sondrio", "SU": "Sud Sardegna", "TA": "Taranto",
    "TE": "Teramo", "TR": "Terni", "TO": "Torino", "TP": "Trapani",
    "TN": "Trento", "TV": "Treviso", "TS": "Trieste", "UD": "Udine",
    "VA": "Varese", "VE": "Venezia", "VB": "Verbano-Cusio-Ossola",
    "VC": "Vercelli", "VR": "Verona", "VV": "Vibo Valentia", "VI": "Vicenza",
    "VT": "Viterbo", "OT": "Olbia-Tempio",
    "RSM": "San Marino",   # non una provincia italiana, ma compare nel calendario
}

_CROSS_MONTH_RE = re.compile(r"^(\d{1,2})/(\d{1,2})-(\d{1,2})/(\d{1,2})$")
_SAME_MONTH_RE = re.compile(r"^(\d{1,2})(?:-(\d{1,2}))?/(\d{1,2})$")


def _parse_date(raw: str, year: int) -> tuple[str, str] | None:
    raw = raw.strip()
    if not raw or raw.upper() == "ANNULLATO":
        return None

    m = _CROSS_MONTH_RE.match(raw)
    if m:
        d1, m1, d2, m2 = (int(x) for x in m.groups())
        return f"{year}-{m1:02d}-{d1:02d}", f"{year}-{m2:02d}-{d2:02d}"

    m = _SAME_MONTH_RE.match(raw)
    if m:
        d1, d2, mo = m.groups()
        d2 = d2 or d1
        mo = int(mo)
        return f"{year}-{mo:02d}-{int(d1):02d}", f"{year}-{mo:02d}-{int(d2):02d}"

    return None


class RallylinkScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        csv_text = fetch_html_static(self.config.url)   # funziona anche per testo CSV, non solo HTML
        keywords = load_keywords()
        proper_nouns = keywords.get("rally_proper_nouns", [])
        season_year = getattr(self.config, "season_year", None)

        events: dict[str, Event] = {}

        reader = csv.reader(io.StringIO(csv_text))
        for row in reader:
            if len(row) < 4:
                continue
            data_raw, _validita, titolo_raw, prov = row[0], row[1], row[2], row[3]

            if data_raw.strip().lower() == "data":
                continue   # riga di intestazione

            parsed = _parse_date(data_raw, season_year)
            if not parsed:
                continue   # data non interpretabile o evento annullato
            start_iso, end_iso = parsed

            titolo = normalize_title_case(titolo_raw.strip(), proper_nouns)
            if not titolo:
                continue

            provincia_nome = PROVINCE_NAMES.get(prov.strip().upper(), prov.strip())

            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=titolo,
                date_text=f"{start_iso} - {end_iso}",   # solo riferimento/debug
                url=self.config.url,
                date_start=start_iso,
                date_end=end_iso,
                circuito_override=provincia_nome,   # niente circuito fisso: usiamo la provincia
                citta_override=provincia_nome,
                disciplina_override=["Rally"],
            )
            events[ev.event_id] = ev

        return list(events.values())
