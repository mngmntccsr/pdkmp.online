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


def parse_date_range(date_text: str) -> tuple[str | None, str | None]:
    """Converte un testo tipo '4 - 6 September 2026' o '1° Maggio 2026'
    in una coppia di date ISO (dataInizio, dataFine).
    Restituisce (None, None) se non riesce a interpretare il formato:
    in quel caso l'evento va rivisto a mano (viene comunque segnalato
    nel log e nell'email).
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


def event_to_pdkmp_dict(event: Event, track: TrackConfig) -> dict | None:
    """Converte un Event nello schema PaddockMap.
    Restituisce None se la data non è interpretabile (evento scartato,
    ma segnalato via log/email per revisione manuale).
    """
    start, end = parse_date_range(event.date_text)
    if not start:
        return None

    return {
        "titolo": event.title,
        "dataInizio": start,
        "dataFine": end or start,
        "disciplina": infer_disciplines(event.title),
        "circuito": track.name,
        "citta": track.citta,
        "linkBiglietti": "",
        "linkInfo": event.url,
        "organizzatore": "",
        "immagine": "",
        "eventoGratuito": False,
        # campi extra, ignorati dal sito, usati solo dallo script di merge:
        "fonteAuto": True,
        "idAuto": event.event_id,
    }
