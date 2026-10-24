"""Telegram bot handlers — Phase 1 single-user."""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.config import settings
from app.core.gemini_audit import AdInput, AuditResult, generate_audit
from app.bot.cards import format_internal_card, format_email_block
from app.db.client import get_db

log = logging.getLogger(__name__)
router = Router()


def _is_authorized(user_id: int) -> bool:
    return user_id == settings.TELEGRAM_USER_ID


def audit_keyboard(lead_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Copy Email Audit", callback_data=f"copy:{lead_id}"),
                InlineKeyboardButton(text="🔄 Regenerate", callback_data=f"regen:{lead_id}"),
            ],
            [
                InlineKeyboardButton(text="✅ Mark Sent", callback_data=f"sent:{lead_id}"),
                InlineKeyboardButton(text="❌ Skip Lead", callback_data=f"skip:{lead_id}"),
            ],
        ]
    )


# ---------- Commands ----------

@router.message(Command("start"))
async def cmd_start(message: Message):
    if not _is_authorized(message.from_user.id):
        await message.answer("Not authorized.")
        return
    await message.answer(
        "✅ Special Agent Meta online.\n\n"
        "You'll receive audit cards here when the daily job runs.\n\n"
        "Commands:\n"
        "/status — today's counts\n"
        "/whoami — show your user ID"
    )


@router.message(Command("whoami"))
async def cmd_whoami(message: Message):
    await message.answer(f"Your Telegram user ID is: {message.from_user.id}")


@router.message(Command("status"))
async def cmd_status(message: Message):
    if not _is_authorized(message.from_user.id):
        await message.answer("Not authorized.")
        return
    db = get_db()
    try:
        leads = db.table("leads").select("status").execute().data or []
        sends = db.table("sends").select("id").execute().data or []
        audits = db.table("audits").select("id").execute().data or []
        by_status: dict[str, int] = {}
        for row in leads:
            s = row.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
        lines = [f"📊 <b>Status</b>", f"Leads by status: {by_status}",
                 f"Audits generated: {len(audits)}",
                 f"Sends logged: {len(sends)}"]
        await message.answer("\n".join(lines))
    except Exception as e:
        log.exception("status failed")
        await message.answer(f"Status error: {e}")


# ---------- Callback buttons ----------

@router.callback_query(F.data.startswith("copy:"))
async def cb_copy(cb: CallbackQuery):
    if not _is_authorized(cb.from_user.id):
        await cb.answer("Not authorized.")
        return
    lead_id = cb.data.split(":", 1)[1]
    db = get_db()
    row = db.table("audits").select("*").eq("lead_id", lead_id).single().execute().data
    if not row:
        await cb.answer("Audit not found.")
        return
    audit = AuditResult(
        diagnosis=row["diagnosis"],
        hook1=dict(angle_name="Angle 1", target="", headline=row["hook1_headline"], text=row["hook1_text"], image=row["hook1_image"]),
        hook2=dict(angle_name="Angle 2", target="", headline=row["hook2_headline"], text=row["hook2_text"], image=row["hook2_image"]),
        email_subject=row["email_subject"],
        email_body=row["email_body"],
    )
    await cb.message.answer(format_email_block(audit))
    await cb.answer("Email block sent below ↑")


@router.callback_query(F.data.startswith("sent:"))
async def cb_sent(cb: CallbackQuery):
    if not _is_authorized(cb.from_user.id):
        await cb.answer("Not authorized.")
        return
    lead_id = cb.data.split(":", 1)[1]
    db = get_db()
    db.table("sends").insert({"lead_id": lead_id}).execute()
    db.table("leads").update({"status": "sent"}).eq("id", lead_id).execute()
    await cb.answer("Marked as sent ✅")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("skip:"))
async def cb_skip(cb: CallbackQuery):
    if not _is_authorized(cb.from_user.id):
        await cb.answer("Not authorized.")
        return
    lead_id = cb.data.split(":", 1)[1]
    db = get_db()
    db.table("leads").update({"status": "skipped"}).eq("id", lead_id).execute()
    await cb.answer("Skipped")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("regen:"))
async def cb_regen(cb: CallbackQuery):
    if not _is_authorized(cb.from_user.id):
        await cb.answer("Not authorized.")
        return
    lead_id = cb.data.split(":", 1)[1]
    db = get_db()
    lead = db.table("leads").select("*").eq("id", lead_id).single().execute().data
    if not lead:
        await cb.answer("Lead not found.")
        return
    await cb.answer("Regenerating…")
    try:
        ad = AdInput(
            domain=lead.get("domain") or "",
            brand=lead.get("brand"),
            headline=lead.get("ad_headline"),
            primary_text=lead.get("ad_primary"),
            image_url=lead.get("ad_image_url"),
            days_active=lead.get("days_active"),
        )
        audit = generate_audit(ad)
        db.table("audits").update({
            "diagnosis": audit.diagnosis,
            "hook1_headline": audit.hook1.headline, "hook1_text": audit.hook1.text, "hook1_image": audit.hook1.image,
            "hook2_headline": audit.hook2.headline, "hook2_text": audit.hook2.text, "hook2_image": audit.hook2.image,
            "email_subject": audit.email_subject, "email_body": audit.email_body,
        }).eq("lead_id", lead_id).execute()
        await cb.message.answer(format_internal_card(lead, audit), reply_markup=audit_keyboard(lead_id))
    except Exception as e:
        log.exception("regen failed")
        await cb.message.answer(f"Regenerate failed: {e}")
