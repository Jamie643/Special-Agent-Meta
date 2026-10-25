"""Formats audit records into Telegram messages."""

import html

def format_internal_card(lead: dict, audit: dict) -> str:
    """The card YOU see in Telegram — shows the diagnosis and the full email."""
    brand = lead.get("brand") or lead.get("domain") or "Unknown brand"
    domain = lead.get("domain", "")
    days = lead.get("days_active") or "?"
    
    card = (
        f"🏪 <b>{html.escape(brand)}</b> — {html.escape(domain)}\n"
        f"📅 Stale ad: running {days} days\n\n"
        f"🎯 <b>Diagnosis</b>\n{html.escape(audit['diagnosis'])}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📧 <b>THE EMAIL</b>\n\n"
        f"<b>Subject:</b> {html.escape(audit['email_subject'])}\n\n"
        f"<pre>{html.escape(audit['email_body'])}</pre>\n\n"
        f"🔍 <a href='https://hunter.io/search/{html.escape(domain)}'>Find Contact Email</a>"
    )
    return card


def format_email_block(audit: dict) -> str:
    """The copyable email — sent as raw text so it never breaks."""
    return f"SUBJECT: {audit['email_subject']}\n\n{audit['email_body']}"
