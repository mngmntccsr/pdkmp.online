"""Invio dell'email settimanale di riepilogo via SMTP."""
from __future__ import annotations

import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import EmailConfig
from src.models import Event


def _event_line(e: Event) -> str:
    parts = [f"<b>{e.title}</b>"]
    if e.date_text:
        parts.append(f"— {e.date_text}")
    line = " ".join(parts)
    if e.url:
        line = f'<a href="{e.url}">{line}</a>'
    return f"<li>{line} <span style='color:#888'>[{e.track_name}]</span></li>"


def build_html_body(results: dict[str, dict[str, list[Event]]]) -> str:
    """results: { track_slug: {"added": [...], "removed": [...], "current": [...]} }"""
    today = date.today().strftime("%d/%m/%Y")

    all_added = [e for r in results.values() for e in r["added"]]
    all_removed = [e for r in results.values() for e in r["removed"]]

    html = [f"<h2>Aggiornamento eventi motorsport — {today}</h2>"]

    if not all_added and not all_removed:
        html.append("<p>Nessuna variazione questa settimana rispetto allo scraping precedente.</p>")
    else:
        if all_added:
            html.append(f"<h3 style='color:#0a7d2c'>✅ Eventi aggiunti ({len(all_added)})</h3>")
            html.append("<ul>" + "".join(_event_line(e) for e in all_added) + "</ul>")
        if all_removed:
            html.append(f"<h3 style='color:#b00020'>❌ Eventi rimossi ({len(all_removed)})</h3>")
            html.append("<ul>" + "".join(_event_line(e) for e in all_removed) + "</ul>")

    html.append("<hr><h3>Situazione attuale per autodromo</h3>")
    for slug, r in results.items():
        current = sorted(r["current"], key=lambda e: e.date_text)
        html.append(f"<h4>{r['track_name']} ({len(current)} eventi)</h4>")
        if current:
            html.append("<ul>" + "".join(_event_line(e) for e in current) + "</ul>")
        else:
            html.append("<p><i>Nessun evento trovato (verifica i selettori di scraping).</i></p>")

    html.append(
        "<hr><p style='color:#888;font-size:12px'>"
        "Email generata automaticamente dallo scraper eventi motorsport. "
        "Filtro applicato: solo gare/trackday, esclusi eventi non motoristici."
        "</p>"
    )
    return "\n".join(html)


def send_email(email_config: EmailConfig, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_config.email_from
    msg["To"] = email_config.email_to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(email_config.smtp_host, email_config.smtp_port) as server:
        server.starttls()
        server.login(email_config.smtp_user, email_config.smtp_pass)
        server.sendmail(email_config.email_from, [email_config.email_to], msg.as_string())
