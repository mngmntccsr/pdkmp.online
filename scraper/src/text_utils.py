"""Utility di testo condivise tra scraper.

normalize_title_case: converte un titolo TUTTO MAIUSCOLO in "sentence case"
(solo la prima lettera dell'intero titolo maiuscola, come si scrive
correttamente in italiano — a differenza dell'inglese non si capitalizza
ogni parola), poi ricapitalizza i nomi propri noti (città, ecc.) da una
lista mantenibile in config/tracks.yaml.

Si attiva SOLO se il titolo è effettivamente tutto maiuscolo: se contiene
già lettere minuscole, si assume che la fonte l'abbia già scritto
correttamente e lo lascia invariato. Questo la rende sicura da applicare
sempre, anche su fonti che già formattano bene i titoli.
"""
from __future__ import annotations

import re


def normalize_title_case(raw_title: str, proper_nouns: list[str] | None = None) -> str:
    if not raw_title:
        return raw_title
    if raw_title != raw_title.upper():
        return raw_title   # non è tutto maiuscolo, lo lasciamo come sta

    text = raw_title.lower()

    # capitalizza la PRIMA LETTERA VERA (non il primo carattere assoluto:
    # molti titoli iniziano con un numero ordinale, es. "3° Festa del Riso",
    # e "3"[0].upper() non farebbe nulla di utile)
    match = re.search(r"[a-zà-ÿ]", text)
    if match:
        idx = match.start()
        text = text[:idx] + text[idx].upper() + text[idx + 1:]

    for noun in proper_nouns or []:
        text = re.sub(rf"\b{re.escape(noun.lower())}\b", noun, text, flags=re.IGNORECASE)

    return text
