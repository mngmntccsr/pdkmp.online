"""Modelli dati condivisi dal progetto."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional


def _make_event_id(track_slug: str, title: str, date_text: str, url: str) -> str:
    """ID stabile e deterministico per un evento.

    Usato per capire se un evento è "lo stesso" tra due scraping successivi,
    anche se il sito cambia leggermente l'ordine o alcuni dettagli grafici.
    """
    raw = f"{track_slug}|{title.strip().lower()}|{date_text.strip().lower()}|{url.strip()}"
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
