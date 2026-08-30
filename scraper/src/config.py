"""Caricamento della configurazione da config/tracks.yaml e variabili d'ambiente."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "tracks.yaml"
STATE_DIR = ROOT_DIR / "data" / "state"

load_dotenv(ROOT_DIR / ".env")


@dataclass
class TrackConfig:
    slug: str
    name: str
    url: str
    parser: str            # "static" o "dynamic"
    selectors: dict
    citta: str = ""
    wait_selector: str | None = None
    date_hint_language: str = "it"
    skip_motorsport_filter: bool = False


@dataclass
class EmailConfig:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    email_from: str
    email_to: str
    always_send: bool


def load_tracks() -> list[TrackConfig]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    tracks = []
    for t in raw["tracks"]:
        tracks.append(
            TrackConfig(
                slug=t["slug"],
                name=t["name"],
                url=t["url"],
                parser=t["parser"],
                selectors=t.get("selectors", {}),
                citta=t.get("citta", ""),
                wait_selector=t.get("wait_selector"),
                date_hint_language=t.get("date_hint_language", "it"),
                skip_motorsport_filter=t.get("skip_motorsport_filter", False),
            )
        )
    return tracks


def load_keywords() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw.get("keywords", {"include": [], "exclude": [], "free_entry": [], "organizer_rules": []})

def load_circuit_aliases() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw.get("circuit_aliases", {})

def load_email_config() -> EmailConfig:
    def _req(name: str) -> str:
        val = os.environ.get(name)
        if not val:
            raise RuntimeError(
                f"Variabile d'ambiente mancante: {name}. "
                f"Controlla il tuo file .env o i Secrets di GitHub Actions."
            )
        return val

    return EmailConfig(
        smtp_host=_req("SMTP_HOST"),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_user=_req("SMTP_USER"),
        smtp_pass=_req("SMTP_PASS"),
        email_from=os.environ.get("EMAIL_FROM", os.environ.get("SMTP_USER", "")),
        email_to=_req("EMAIL_TO"),
        always_send=os.environ.get("ALWAYS_SEND", "true").strip().lower() == "true",
    )
