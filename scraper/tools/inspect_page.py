"""Tool di debug: salva l'HTML (renderizzato via Playwright se necessario)
di una pista in debug_html/<slug>.html, così puoi aprirlo nel browser o in
un editor e capire quali selettori CSS usare in config/tracks.yaml.

Uso:
    python tools/inspect_page.py monza
    python tools/inspect_page.py misano
    python tools/inspect_page.py imola

Modalità ad-hoc (per esplorare un sito NON ancora in tracks.yaml, es.
prima di aggiungere un nuovo autodromo/fonte):
    python tools/inspect_page.py https://esempio.it/calendario/
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_tracks
from src.scrapers.base import fetch_html_dynamic, fetch_html_static

OUT_DIR = Path(__file__).resolve().parent.parent / "debug_html"


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: python tools/inspect_page.py <slug_pista>")
        print("     python tools/inspect_page.py <url completo>   (modalità ad-hoc)")
        sys.exit(1)

    arg = sys.argv[1]

    if arg.startswith("http://") or arg.startswith("https://"):
        # modalità ad-hoc: nessuna pista configurata, si presume dinamico
        # (Playwright) perché è la scelta più sicura per siti sconosciuti
        print(f"Scarico {arg} (modalità ad-hoc, rendering dinamico via Playwright)...")
        html = fetch_html_dynamic(arg, timeout_ms=30000)
        slug = re.sub(r"[^a-z0-9]+", "-", arg.lower()).strip("-")[:60]
    else:
        slug = arg
        tracks = {t.slug: t for t in load_tracks()}
        if slug not in tracks:
            print(f"Pista sconosciuta '{slug}'. Disponibili: {', '.join(tracks)}")
            print("(oppure passa un URL completo per la modalità ad-hoc)")
            sys.exit(1)

        track = tracks[slug]
        print(f"Scarico {track.url} (parser={track.parser})...")

        if track.parser == "dynamic":
            html = fetch_html_dynamic(track.url, wait_selector=track.wait_selector, timeout_ms=30000)
        else:
            html = fetch_html_static(track.url)

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Salvato in {out_path} ({len(html)} caratteri). Aprilo nel browser per ispezionare la struttura.")


if __name__ == "__main__":
    main()
