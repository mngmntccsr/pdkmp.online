"""Tool di debug: salva l'HTML (renderizzato via Playwright se necessario)
di una pista in debug_html/<slug>.html, così puoi aprirlo nel browser o in
un editor e capire quali selettori CSS usare in config/tracks.yaml.

Uso:
    python tools/inspect_page.py monza
    python tools/inspect_page.py misano
    python tools/inspect_page.py imola
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_tracks
from src.scrapers.base import fetch_html_dynamic, fetch_html_static

OUT_DIR = Path(__file__).resolve().parent.parent / "debug_html"


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: python tools/inspect_page.py <slug_pista>")
        sys.exit(1)

    slug = sys.argv[1]
    tracks = {t.slug: t for t in load_tracks()}
    if slug not in tracks:
        print(f"Pista sconosciuta '{slug}'. Disponibili: {', '.join(tracks)}")
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
