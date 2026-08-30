"""Conversione degli Event scrapati nello schema usato da events.json
del sito PaddockMap (pdkmp.online).

Schema atteso da index.html (vedi repo pdkmp.online):
{
  "titolo": str,
  "dataInizio": "YYYY-MM-DD",
  "dataFine": "YYYY-MM-DD",
  "disciplina": [str, ...],   # valori ammessi: Gt, Formula, Misto, Storico,
                               # Rally, Le Mans Prototype, Cronoscalata
  "circuito": str,
  "citta": str,
  "linkBiglietti": str,
  "linkInfo": str,
  "organizzatore": str,
  "immagine": str,
  "eventoGratuito": bool
}

Aggiungiamo due campi EXTRA (ignorati dal sito, che legge solo le chiavi
sopra) usati solo dal nostro script per riconoscere quali eventi sono stati
inseriti automaticamente da questo scraper, senza toccare quelli inseriti
a mano da te:
  "fonteAuto": true
  "idAuto": "<event_id>"
"""
from __future__ import annotations

import re
from datetime import date

from dateutil import parser as dateparser

from src.config import TrackConfig
from src.models import Event

# --- normalizzazione mesi italiani (+ una svista comune vista sul sito di Imola) ---
IT_MONTHS = {
    "gennaio": "january", "gen": "jan",
    "febbraio": "february", "feb": "feb",
    "marzo": "march", "mar": "mar",
    "aprile": "april", "apr": "apr",
    "maggio": "may", "mag": "may",
    "giugno": "june", "giu": "jun",
    "luglio": "july", "lug": "jul",
    "agosto": "august", "ago": "aug",
    "settembre": "september", "set": "sep",
    "semptember": "september",   # refuso presente sul sito autodromoimola.it
    "ottobre": "october", "ott": "oct",
    "novembre": "november", "nov": "nov",
    "dicembre": "december", "dic": "dec",
}

_DATE_CORE_RE = re.compile(
    r"(\d{1,2})\s*(?:[-–]\s*(\d{1,2}))?\s*([a-z]+)\s*(\d{4})"
)

# Un anno risultante fuori da questo intervallo (rispetto all'anno corrente)
# viene considerato sospetto e l'evento viene scartato per revisione manuale,
# invece di rischiare di pubblicare silenziosamente una data sbagliata
# (es. un bug di parsing che mette l'anno corrente su un evento che in
# realtà è dell'anno prossimo).
_YEAR_TOLERANCE_PAST = 0
_YEAR_TOLERANCE_FUTURE = 3


def parse_date_range(date_text: str) -> tuple[str | None, str | None]:
    """Converte un testo tipo '4 - 6 September 2026' o '1° Maggio 2026'
    in una coppia di date ISO (dataInizio, dataFine).
    Restituisce (None, None) se non riesce a interpretare il formato, o se
    l'anno risulta implausibile (vedi _YEAR_TOLERANCE_*): in quel caso
    l'evento va rivisto a mano (viene comunque segnalato nel changelog).
    """
    if not date_text:
        return None, None

    text = date_text.lower().replace("°", "").strip()
    for it, en in IT_MONTHS.items():
        text = re.sub(rf"\b{it}\b", en, text)

    m = _DATE_CORE_RE.search(text)
    if not m:
        return None, None

    day1, day2, month, year = m.groups()
    day2 = day2 or day1

    current_year = date.today().year
    if not (current_year - _YEAR_TOLERANCE_PAST <= int(year) <= current_year + _YEAR_TOLERANCE_FUTURE):
        return None, None

    try:
        start = dateparser.parse(f"{day1} {month} {year}", dayfirst=True).date().isoformat()
        end = dateparser.parse(f"{day2} {month} {year}", dayfirst=True).date().isoformat()
    except (ValueError, OverflowError):
        return None, None

    return start, end


# --- inferenza disciplina dal titolo (best-effort, verifica sempre a mano) ---
DISCIPLINE_RULES: list[tuple[str, str]] = [
    (r"\brally\b", "Rally"),
    (r"\b(formula|f1|f2|f3|f4|eurocup)\b", "Formula"),
    (r"\b(gt\d?|gt open|gt world|carrera cup|tcr)\b", "Gt"),
    (r"\b(wec|elms|le mans|endurance|prototype|hypercar|lmp)\b", "Le Mans Prototype"),
    (r"\b(storico|historic|classic|revival|vintage|d'epoca)\b", "Storico"),
    (r"\b(cronoscalata|salita|hillclimb)\b", "Cronoscalata"),
]


def infer_disciplines(title: str) -> list[str]:
    t = title.lower()
    found = {tag for pattern, tag in DISCIPLINE_RULES if re.search(pattern, t)}
    return sorted(found) if found else ["Misto"]


def infer_free_entry(title: str, free_entry_keywords: list[str]) -> bool:
    """Deduce se l'ingresso spettatori è gratuito, in base a parole chiave
    nel titolo (es. "racing weekend", "trackday" sono tipicamente eventi
    amatoriali a ingresso libero, mentre campionati ufficiali come CIV/GT/WEC
    di solito richiedono un biglietto).

    È una stima best-effort basata sulle keyword in config/tracks.yaml
    (sezione "free_entry"): verifica sempre a mano, soprattutto per eventi
    che non conosci bene.
    """
    t = title.lower()
    return any(kw.lower() in t for kw in free_entry_keywords)


def infer_organizer(title: str, organizer_rules: list[dict]) -> str:
    """Deduce l'organizzatore dal titolo, in base alle regole in
    config/tracks.yaml (sezione "organizer_rules").

    Questo campo NON serve solo per mostrarlo sul sito: index.html usa già
    "organizzatore" per assegnare automaticamente un'immagine fissa agli
    eventi ricorrenti (vedi "organizerImages" in index.html). Popolandolo
    correttamente, un evento come "ACI Racing Weekend" mantiene la stessa
    immagine ovunque si svolga, senza doverla reimpostare ogni volta.
    """
    t = title.lower()
    for rule in organizer_rules:
        if rule.get("match", "").lower() in t:
            return rule.get("organizzatore", "")
    return ""


def _year_is_plausible(iso_date: str) -> bool:
    try:
        year = int(iso_date[:4])
    except (ValueError, TypeError):
        return False
    current_year = date.today().year
    return current_year - _YEAR_TOLERANCE_PAST <= year <= current_year + _YEAR_TOLERANCE_FUTURE


def event_to_pdkmp_dict(
    event: Event,
    track: TrackConfig,
    free_entry_keywords: list[str] | None = None,
    organizer_rules: list[dict] | None = None,
) -> dict | None:
    """Converte un Event nello schema PaddockMap.
    Restituisce None se la data non è interpretabile o implausibile
    (evento scartato, ma segnalato via changelog per revisione manuale).

    Se lo scraper ha già calcolato date ISO affidabili (event.date_start /
    event.date_end — es. Mugello, che le ricava direttamente dall'URL della
    pagina evento), le usa direttamente invece di re-interpretare
    event.date_text con l'espressione regolare sui nomi dei mesi.
    """
    if event.date_start:
        start = event.date_start
        end = event.date_end or event.date_start
        if not _year_is_plausible(start):
            return None
    else:
        start, end = parse_date_range(event.date_text)
        if not start:
            return None

    return {
        "titolo": event.title,
        "dataInizio": start,
        "dataFine": end or start,
        "disciplina": event.disciplina_override or infer_disciplines(event.title),
        "circuito": event.circuito_override or track.name,
        "citta": event.citta_override or track.citta,
        "linkBiglietti": "",
        "linkInfo": event.url,
        "organizzatore": infer_organizer(event.title, organizer_rules or []),
        "immagine": "",
        "eventoGratuito": infer_free_entry(event.title, free_entry_keywords or []),
        # campi extra, ignorati dal sito, usati solo dallo script di merge:
        "fonteAuto": True,
        "idAuto": event.event_id,
    }
