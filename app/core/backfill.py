"""Processes leads already in the database that don't have an audit yet."""

import logging
from aiogram import Bot
from app.config import settings
from app.core.gemini_audit import AdInput, generate_audit
from app.bot.cards import format_internal_card
from app.bot.handlers import audit_keyboard
from app.db.client import get_db

log = logging.getLogger(__name__)

async def run_backfill(bot: Bot) -> dict:
    """Finds pending leads, generates audits, and sends to Telegram."""
    db = get_db()
    stats = {"audits_made": 0, "error": None}
    
    try:
        # Find up to 10 leads that haven't been audited yet
        leads = db.table("leads").select("*").eq("status", "new").limit(10).execute().data
        
        if not leads:
            log.info("No pending leads found.")
            return stats

        for lead in leads:
            # We need the domain and brand from the stores table
            store = db.table("stores").select("*").eq("id", lead["store_id"]).single().execute().data
            domain = store.get("domain", "unknown.com")
            brand = store.get("name", "Unknown Brand")
            
            ad_input = AdInput(
                domain=domain,
                brand=brand,
                headline=lead.get("ad_headline", ""),
                primary_text=lead.get("ad_primary", ""),
                image_url=lead.get("ad_image_url", ""),
                days_active=lead.get("days_active", 60),
                sender="James Liberty" 
            )
            
            try:
                audit = generate_audit(ad_input)
            except Exception as e:
                log.error("Gemini failed for %s: %s", domain, e)
                db.table("leads").update({"status": "skipped"}).eq("id", lead["id"]).execute()
                continue
                
            # Save audit
            db.table("audits").insert({
                "lead_id": lead["id"],
                "diagnosis": audit.diagnosis,
                "hook1_headline": audit.hook1_headline,
                "hook1_text": audit.hook1_text,
                "hook1_image": audit.hook1_image,
                "hook2_headline": audit.hook2_headline,
                "hook2_text": audit.hook2_text,
                "hook2_image": audit.hook2_image,
                "email_subject": audit.email_subject,
                "email_body": audit.email_body,
            }).execute()
            
            db.table("leads").update({"status": "audited"}).eq("id", lead["id"]).execute()
            stats["audits_made"] += 1
            
            # Create a fake object so the formatter works
            class SimpleHook:
                def __init__(self, angle, target, headline, text, image):
                    self.angle_name = angle
                    self.target = target
                    self.headline = headline
                    self.text = text
                    self.image = image

            class SimpleAudit:
                def __init__(self, a):
                    self.diagnosis = a.diagnosis
                    self.hook1 = SimpleHook(a.hook1_angle_name, a.hook1_target, a.hook1_headline, a.hook1_text, a.hook1_image)
                    self.hook2 = SimpleHook(a.hook2_angle_name, a.hook2_target, a.hook2_headline, a.hook2_text, a.hook2_image)
                    self.email_subject = a.email_subject
                    self.email_body = a.email_body

            card_text = format_internal_card({"brand": brand, "domain": domain, "days_active": lead.get("days_active")}, SimpleAudit(audit))
            
            try:
                await bot.send_message(
                    chat_id=settings.TELEGRAM_USER_ID,
                    text=card_text,
                    reply_markup=audit_keyboard(lead["id"])
                )
            except Exception as e:
                log.error("Failed to send Telegram message: %s", e)

        return stats
        
    except Exception as e:
        log.exception("Backfill failed")
        stats["error"] = str(e)
        return stats
