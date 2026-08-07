"""Test di base per la classificazione motorsport/non-motorsport.

Esegui con:  pytest
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_keywords
from src.filters import is_motorsport_event

KEYWORDS = load_keywords()


def test_race_events_are_kept():
    assert is_motorsport_event("Gran Premio di San Marino MotoGP", KEYWORDS)
    assert is_motorsport_event("ACI Racing Weekend", KEYWORDS)
    assert is_motorsport_event("CIV Campionato Italiano Velocità Moto", KEYWORDS)
    assert is_motorsport_event("GT World Challenge Powered by AWS", KEYWORDS)


def test_trackdays_are_kept():
    assert is_motorsport_event("Track Day Pirelli", KEYWORDS)
    assert is_motorsport_event("Pista Aperta - Prova Libera", KEYWORDS)


def test_non_motorsport_events_are_excluded():
    assert not is_motorsport_event("Monsterland Halloween Festival", KEYWORDS)
    assert not is_motorsport_event("Imola Comics & Games", KEYWORDS)
    assert not is_motorsport_event("Duathlon Sprint", KEYWORDS)
    assert not is_motorsport_event("Monza Bike Day", KEYWORDS)
    assert not is_motorsport_event("Run For Life", KEYWORDS)
    assert not is_motorsport_event("Cremonini LIVE26", KEYWORDS)


def test_motorcycle_club_rally_is_excluded_but_moto_racing_is_kept():
    assert not is_motorsport_event("Raduno Moto Harley Davidson Chapter", KEYWORDS)
    assert is_motorsport_event("MotoGP Gran Premio di San Marino", KEYWORDS)
