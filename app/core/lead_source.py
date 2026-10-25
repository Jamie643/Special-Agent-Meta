"""Fetches stale ads from the Meta Ad Library via Apify."""

import logging
from apify_client import ApifyClient
from app.config import settings

log = logging.getLogger(__name__)

ACTOR_ID = "brilliant_gum/facebook-ads-library-scraper"

def fetch_stale_ads(limit: int = 10) -> list[dict]:
    """Fetches active ads that have been running for 60+ days."""
    if not hasattr(settings, "APIFY_API_TOKEN"):
        return []

    client = ApifyClient(settings.APIFY_API_TOKEN)
    
    run_input = {
        "searchTerms": ["shop", "buy", "collection"],
        "country": "US",
        "activeStatus": "active",
        "minDaysRunning": 60,
        "maxResults": limit,
        "scrapeAdDetails": True
    }

    log.info("Starting Apify actor %s...", ACTOR_ID)
    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input, timeout_secs=120)
        if not run:
            return []

        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        log.info("Apify returned %d ads.", len(dataset_items))
        
        leads = []
        for item in dataset_items:
            snapshot = item.get("snapshot", {})
            
            # Dig for the real URL (Meta Ad Library stores it in a few places)
            domain = ""
            link_url = snapshot.get("linkUrl")
            if not link_url:
                cards = snapshot.get("cards", [])
                if cards:
                    link_url = cards[0].get("linkUrl")
            if not link_url:
                body = snapshot.get("body", {})
                link_url = body.get("linkUrl")
                
            if link_url:
                domain = link_url.split("//")[-1].split("/")[0]
            
            # If we STILL can't find a domain, fallback to unknown
            if not domain:
                domain = "unknown.com"
            
            brand = item.get("pageName") or domain.split(".")[0].title()
            
            # Grab the primary text (it's sometimes a string, sometimes a dict)
            primary_text = ""
            body = snapshot.get("body", {})
            if isinstance(body, str):
                primary_text = body
            elif isinstance(body, dict):
                primary_text = body.get("text", "")
            
            leads.append({
                "domain": domain,
                "brand": brand,
                "ad_archive_id": str(item.get("adArchiveID", "")),
                "days_active": item.get("daysActive", 60),
                "ad_headline": snapshot.get("title", ""),
                "ad_primary": primary_text,
                "ad_image_url": snapshot.get("images", [{}])[0].get("originalImageUrl", "") if snapshot.get("images") else "",
                "ad_snapshot": item
            })
            
        return leads
    except Exception as e:
        log.error("Apify error: %s", e)
        return []
