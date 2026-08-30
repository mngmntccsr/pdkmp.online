"""Modelli dati condivisi dal progetto."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from typing import Optional


def _normalize_for_id(text: str) -> str:
    """Normalizza un testo prima di usarlo nell'hash dell'ID, così piccole
    differenze di formattazione (spazi doppi, tipo di trattino usato dal
    sito) non generano due ID diversi per lo stesso evento reale.
    """
    text = text.strip().lower()
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s+", " ", text)
    return text


def _make_event_id(track_slug: str, title: str, date_text: str, url: str) -> str:
    """ID stabile e deterministico per un evento.

    Usato per capire se un evento è "lo stesso" tra due scraping successivi,
    anche se il sito cambia leggermente l'ordine o alcuni dettagli grafici.
    """
    raw = (
        f"{track_slug}|{_normalize_for_id(title)}|"
        f"{_normalize_for_id(date_text)}|{url.strip()}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class Event:
    track_slug: str
    track_name: str
    title: str
    date_text: str            # testo grezzo della data così come appare sul sito
    url: str = ""
    date_start: Optional[str] = None   # ISO date se siamo riusciti a parsarla
    date_end: Optional[str] = None
    # Per sorgenti che aggregano PIÙ circuiti in un'unica pagina (es.
    # WeCanRace, che elenca date su decine di autodromi diversi): se
    # valorizzati, sovrascrivono track_name/citta della configurazione
    # statica della pista per QUESTO singolo evento.
    circuito_override: Optional[str] = None
    citta_override: Optional[str] = None
    disciplina_override: Optional[list[str]] = None
    event_id: str = field(default="")

    def __post_init__(self):
        if not self.event_id:
            self.event_id = _make_event_id(
                self.track_slug, self.title, self.date_text, self.url
            )

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Event":
        return Event(**d)
