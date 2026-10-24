"""Formats audit records into Telegram messages."""

from app.core.gemini_audit import AuditResult


def format_internal_card(lead: dict, audit: AuditResult) -> str:
    """The card YOU see in Telegram — includes diagnosis + both angles."""
    brand = lead.get("brand") or lead.get("domain") or "Unknown brand"
    days = lead.get("days_active") or "?"
    return (
        f"🏪 <b>{brand}</b> — {lead.get('domain', '')}\n"
        f"📅 Stale ad: running {days} days\n\n"
        f"🎯 <b>Diagnosis</b>\n{audit.diagnosis}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>Angle 1: {audit.hook1.angle_name}</b>\n"
        f"<i>Targets: {audit.hook1.target}</i>\n"
        f"• Headline: {audit.hook1.headline}\n"
        f"• Text: {audit.hook1.text}\n"
        f"• Visual: {audit.hook1.image}\n\n"
        f"<b>Angle 2: {audit.hook2.angle_name}</b>\n"
        f"<i>Targets: {audit.hook2.target}</i>\n"
        f"• Headline: {audit.hook2.headline}\n"
        f"• Text: {audit.hook2.text}\n"
        f"• Visual: {audit.hook2.image}\n"
    )


def format_email_block(audit: AuditResult) -> str:
    """The copyable email — sent as a separate message when you tap Copy."""
    return (
        f"<b>SUBJECT:</b> {audit.email_subject}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{audit.email_body}"
    )
