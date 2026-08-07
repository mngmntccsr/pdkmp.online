import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.events_json_merge import merge_auto_events
from src.pdkmp_schema import infer_disciplines, parse_date_range


def test_parse_date_range_common_formats():
    assert parse_date_range("4 - 6 Semptember 2026") == ("2026-09-04", "2026-09-06")
    assert parse_date_range("19-20 September 2026") == ("2026-09-19", "2026-09-20")
    assert parse_date_range("1° Maggio 2026") == ("2026-05-01", "2026-05-01")
    assert parse_date_range("8 March 2026") == ("2026-03-08", "2026-03-08")
    assert parse_date_range("6-7 Dicembre 2025") == ("2025-12-06", "2025-12-07")


def test_parse_date_range_unparseable_returns_none():
    assert parse_date_range("2026 June 13") == (None, None)
    assert parse_date_range("") == (None, None)


def test_infer_disciplines():
    assert infer_disciplines("ACI Racing Weekend GT4") == ["Gt"]
    assert infer_disciplines("Rally Due Valli") == ["Rally"]
    assert infer_disciplines("Historic Minardi Day") == ["Storico"]
    assert infer_disciplines("Evento senza categorie chiare") == ["Misto"]


def test_merge_never_touches_manual_events():
    existing = [
        {"titolo": "Evento manuale", "circuito": "Mugello"},  # nessun fonteAuto -> manuale
        {"titolo": "Vecchio evento auto", "fonteAuto": True, "idAuto": "old1"},
    ]
    new_auto = [
        {"titolo": "Nuovo evento auto", "fonteAuto": True, "idAuto": "new1"},
    ]

    merged, added, removed = merge_auto_events(existing, new_auto)

    titles = {e["titolo"] for e in merged}
    assert "Evento manuale" in titles
    assert "Nuovo evento auto" in titles
    assert "Vecchio evento auto" not in titles  # rimosso perché non più trovato
    assert len(added) == 1 and added[0]["titolo"] == "Nuovo evento auto"
    assert len(removed) == 1 and removed[0]["titolo"] == "Vecchio evento auto"
