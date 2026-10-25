"""The daily pipeline: Fetch -> Audit -> Save -> Push to Telegram."""

import logging
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
        raw_leads = fetch_stale_ads(limit=25) # Fetch more than 10 to allow for deduplication
        stats["leads_found"] = len(raw_leads)
        
        if not raw_leads:
            log.info("No leads found today.")
            db.table("jobs").update({"finished_at": datetime.now().isoformat(), **stats}).eq("id", job_id).execute()
            return stats

        audits_pushed = 0
        
        # 2. Loop through leads
        for raw in raw_leads:
            if audits_pushed >= 10:
                break # We only want 10 per day
                
            # Check if we've seen this domain before
            existing_store = db.table("stores").select("id").eq("domain", raw["domain"]).execute().data
            if existing_store:
                continue # Skip, we already audited this store
                
            # Insert new store
            store_res = db.table("stores").insert({"domain": raw["domain"], "name": raw["brand"]}).execute().data[0]
            store_id = store_res["id"]
            
            # Insert lead
            raw["store_id"] = store_id
            lead_res = db.table("leads").insert(raw).execute().data[0]
            lead_id = lead_res["id"]
            
            # Generate audit with Gemini
            ad_input = AdInput(
                domain=raw["domain"],
                brand=raw["brand"],
                headline=raw["ad_headline"],
                primary_text=raw["ad_primary"],
                image_url=raw["ad_image_url"],
                days_active=raw["days_active"],
                sender="James Liberty" 
            )
            
            try:
                audit = generate_audit(ad_input)
            except Exception as e:
                log.error("Gemini failed for %s: %s", raw["domain"], e)
                db.table("leads").update({"status": "skipped"}).eq("id", lead_id).execute()
                continue
                
            # Save audit
            db.table("audits").insert({
                "lead_id": lead_id,
                "diagnosis": audit.diagnosis,
                "hook1_headline": audit.hook1.headline,
                "hook1_text": audit.hook1.text,
                "hook1_image": audit.hook1.image,
                "hook2_headline": audit.hook2.headline,
                "hook2_text": audit.hook2.text,
                "hook2_image": audit.hook2.image,
                "email_subject": audit.email_subject,
                "email_body": audit.email_body,
            }).execute()
            
            db.table("leads").update({"status": "audited"}).eq("id", lead_id).execute()
            stats["audits_made"] += 1
            
            # Push to Telegram
            card_text = format_internal_card(raw, audit)
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
