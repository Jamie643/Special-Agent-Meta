"""The daily pipeline: Fetch -> Audit -> Save -> Push to Telegram."""

import logging
import random
from datetime import datetime
from aiogram import Bot
from app.config import settings
from app.core.lead_source import fetch_stale_ads
from app.core.gemini_audit import AdInput, generate_audit
from app.bot.cards import format_internal_card
from app.bot.handlers import audit_keyboard
from app.db.client import get_db

log = logging.getLogger(__name__)

async def run_daily_pipeline(bot: Bot) -> dict:
    """Runs the full daily job. Returns a summary dict."""
    db = get_db()
    job_record = db.table("jobs").insert({"kind": "daily"}).execute().data[0]
    job_id = job_record["id"]
    
    stats = {"leads_found": 0, "audits_made": 0, "error": None}
    
    try:
        # 1. Fetch from Apify
        raw_leads = fetch_stale_ads(limit=25) 
        stats["leads_found"] = len(raw_leads)
        
        if not raw_leads:
            log.info("No leads found today.")
            db.table("jobs").update({"finished_at": datetime.now().isoformat(), **stats}).eq("id", job_id).execute()
            return stats

        audits_pushed = 0
        
        # 2. Loop through leads
        for raw in raw_leads:
            if audits_pushed >= 10:
                break 
            
            # Extract info and clean the dictionary for the database
            raw_brand = raw.pop("brand", "Unknown Brand")
            domain = raw.pop("domain", "unknown.com")
            
            # Ensure every missing domain gets a UNIQUE name so they aren't skipped
            if not domain or domain == "unknown.com" or domain == "unknown-.com":
                domain = f"unknown-{random.randint(1000, 9999)}-{raw.get('ad_archive_id', 'brand')}.com"
                
            # Check if we've seen this domain before
            existing_store = db.table("stores").select("id").eq("domain", domain).execute().data
            if existing_store:
                continue
                
            # Insert new store
            store_res = db.table("stores").insert({"domain": domain, "name": raw_brand}).execute().data[0]
            store_id = store_res["id"]
            
            # Insert lead
            raw["store_id"] = store_id
            lead_res = db.table("leads").insert(raw).execute().data[0]
            lead_id = lead_res["id"]
            
            # Generate audit with Gemini
            ad_input = AdInput(
                domain=domain,
                brand=raw_brand,
                headline=raw.get("ad_headline", ""),
                primary_text=raw.get("ad_primary", ""),
                image_url=raw.get("ad_image_url", ""),
                days_active=raw.get("days_active", 60),
                sender="James Liberty" 
            )
            
            try:
                audit = generate_audit(ad_input)
            except Exception as e:
                log.error("Gemini failed for %s: %s", domain, e)
                db.table("leads").update({"status": "skipped"}).eq("id", lead_id).execute()
                continue
                
            # Save audit (Updated to use flat fields)
            db.table("audits").insert({
                "lead_id": lead_id,
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
            
            db.table("leads").update({"status": "audited"}).eq("id", lead_id).execute()
            stats["audits_made"] += 1
            
            # Push to Telegram (Updated to use flat fields)
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

            card_text = format_internal_card({"brand": raw_brand, "domain": domain, "days_active": raw.get("days_active")}, SimpleAudit(audit))
            
            try:
                await bot.send_message(
                    chat_id=settings.TELEGRAM_USER_ID,
                    text=card_text,
                    reply_markup=audit_keyboard(lead_id)
                )
                audits_pushed += 1
            except Exception as e:
                log.error("Failed to send Telegram message: %s", e)

        # Mark job as finished
        db.table("jobs").update({"finished_at": datetime.now().isoformat(), **stats}).eq("id", job_id).execute()
        return stats
        
    except Exception as e:
        log.exception("Daily pipeline failed")
        stats["error"] = str(e)
        db.table("jobs").update({"finished_at": datetime.now().isoformat(), **stats}).eq("id", job_id).execute()
        return stats
