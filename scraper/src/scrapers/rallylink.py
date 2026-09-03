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

Il foglio dà solo la PROVINCIA (es. "PV"), non la città esatta. Quando il
titolo segue il pattern inequivocabile "Rally di X" o "Rally Città di X",
estraiamo X e lo usiamo al posto della provincia (più preciso). Per tutti
gli altri casi (titoli che citano regioni, monti, nomi generici — es.
"Rally del Friuli Venezia Giulia", "Paganella Rally" — dove tentare
un'estrazione sarebbe un azzardo) usiamo la provincia come fallback.

Se lo stesso rally compare più volte nel foglio (una riga per ogni
campionato per cui conta, es. WRC + un campionato minore in contemporanea),
la deduplica generale del progetto (dedupe_events) si occupa di tenere
solo una voce, preferendo il titolo più lungo/descrittivo — non serve
gestirlo qui.

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
from src.scrapers.base import BaseTrackScraper, fetch_csv_static
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

TITLE_LOCATION_OVERRIDES = {
    "special rally circuit": ("Autodromo Nazionale Monza", "Monza"),
}

_CROSS_MONTH_RE = re.compile(r"^(\d{1,2})/(\d{1,2})-(\d{1,2})/(\d{1,2})$")
_SAME_MONTH_RE = re.compile(r"^(\d{1,2})(?:-(\d{1,2}))?/(\d{1,2})$")

# Pattern SICURI per estrarre una città dal titolo: solo quando il titolo
# dice esplicitamente "Rally di X" o "Rally Città di X" (gestisce anche
# spazi doppi). Per qualsiasi altro caso (regioni, monti, nomi generici)
# NON tentiamo l'estrazione: meglio la provincia che una città sbagliata.
_CITY_FROM_TITLE_RE = re.compile(r"^Rally\s+(?:Citt[àa]\s+di|di)\s+(.+)$", re.IGNORECASE)
_SMALL_WORDS = {"di", "d'", "del", "della", "delle", "dei", "degli"}


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


def _extract_city_from_title(raw_title: str) -> str | None:
    m = _CITY_FROM_TITLE_RE.match(raw_title.strip())
    if not m:
        return None
    place = re.sub(r"\s+", " ", m.group(1)).strip()
    if not place:
        return None
    return " ".join(w if w.lower() in _SMALL_WORDS else w.capitalize() for w in place.split())


class RallylinkScraper(BaseTrackScraper):
    def scrape(self) -> list[Event]:
        csv_text = fetch_csv_static(self.config.url)
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

            titolo_raw = titolo_raw.strip()
            if not titolo_raw:
                continue

            # estrae la città PRIMA di normalizzare il case del titolo,
            # così il nome del posto mantiene la sua capitalizzazione
            # indipendentemente da come viene poi scritto il titolo
            citta_da_titolo = _extract_city_from_title(titolo_raw)

            titolo = normalize_title_case(titolo_raw, proper_nouns)
            titolo = re.sub(r"\s+", " ", titolo).strip()

            provincia_nome = PROVINCE_NAMES.get(prov.strip().upper(), prov.strip())
            override = next((v for k, v in TITLE_LOCATION_OVERRIDES.items() if k in titolo.lower()), None)
            circuito_final, citta_final = override if override else (citta_da_titolo or provincia_nome, citta_da_titolo or provincia_nome)

            ev = Event(
                track_slug=self.config.slug,
                track_name=self.config.name,
                title=titolo,
                date_text=f"{start_iso} - {end_iso}",   # solo riferimento/debug
                url=self.config.url,
                date_start=start_iso,
                date_end=end_iso,
                circuito_override=circuito_final,
                citta_override=citta_final,
                disciplina_override=["Rally"],
            )
            events[ev.event_id] = ev

        return list(events.values())
