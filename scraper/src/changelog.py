"""Log settimanale delle variazioni, scritto in CHANGELOG.md invece che
inviato via email (niente più SMTP/App Password da configurare).

Ogni run aggiunge un blocco in cima al file, così la storia degli
aggiornamenti resta consultabile nel tempo direttamente su GitHub.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

HEADER = "# 📋 Log aggiornamenti eventi — PaddockMap\n\nQuesto file viene aggiornato automaticamente ogni settimana dallo scraper.\n"


def _fmt_event(e: dict) -> str:
    date_range = f"{e.get('dataInizio', '?')} → {e.get('dataFine', '?')}"
    link = e.get("linkInfo", "")
    title = e.get("titolo", "?")
    line = f"- **{title}** — {date_range} _[{e.get('circuito', '?')}]_"
    if link:
        line += f" — {link}"
    return line


def build_entry(added: list[dict], removed: list[dict], unparsed: list[tuple], archived: list[dict] | None = None, duplicates: list[dict] | None = None) -> str:
    archived = archived or []
    duplicates = duplicates or []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"## {ts}", ""]

    if not added and not removed and not unparsed and not archived and not duplicates:
        lines.append("Nessuna variazione questa settimana.")
    else:
        if added:
            lines.append(f"✅ **Aggiunti ({len(added)})**")
            lines.extend(_fmt_event(e) for e in added)
            lines.append("")
        if removed:
            lines.append(f"❌ **Rimossi ({len(removed)})**")
            lines.extend(_fmt_event(e) for e in removed)
            lines.append("")
        if duplicates:
            lines.append(f"🔁 **Duplicati rimossi ({len(duplicates)})** — stesso circuito+data di un evento già presente")
            lines.extend(_fmt_event(e) for e in duplicates)
            lines.append("")
        if archived:
            lines.append(f"📦 **Archiviati ({len(archived)})** — conclusi da oltre una settimana, spostati in events-archive.json")
            lines.extend(_fmt_event(e) for e in archived)
            lines.append("")
        if unparsed:
            lines.append(f"⚠️ **Da rivedere a mano ({len(unparsed)})** — data non interpretabile automaticamente")
            for track_name, ev in unparsed:
                lines.append(f'- {ev.title} _[{track_name}]_ — data grezza: "{ev.date_text}"')
            lines.append("")

    return "\n".join(lines)


def append_changelog_entry(path: Path, added: list[dict], removed: list[dict], unparsed: list[tuple], archived: list[dict] | None = None, duplicates: list[dict] | None = None) -> None:
    entry = build_entry(added, removed, unparsed, archived, duplicates)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        # rimuove l'header per poterlo rimettere in cima, poi lo riaggiunge
        body = existing[len(HEADER):] if existing.startswith(HEADER) else existing
    else:
        body = ""

    new_content = f"{HEADER}\n{entry}\n\n---\n\n{body.strip()}\n" if body.strip() else f"{HEADER}\n{entry}\n"
    path.write_text(new_content, encoding="utf-8")
