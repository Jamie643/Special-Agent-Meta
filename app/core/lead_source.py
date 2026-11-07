"""Fetches stale ads from the Meta Ad Library via Apify."""

import logging
from apify_client import ApifyClient
from app.config import settings

log = logging.getLogger(__name__)

ACTOR_ID = "brilliant_gum/facebook-ads-library-scraper"

def fetch_stale_ads(country: str, limit: int = 15) -> list[dict]:
    """Fetches active ads that have been running for 60+ days."""
    if not hasattr(settings, "APIFY_API_TOKEN"):
        log.error("APIFY_API_TOKEN is missing from settings!")
        return []

    client = ApifyClient(settings.APIFY_API_TOKEN)
    
    run_input = {
        "searchTerms": ["shop", "buy", "collection"],
        "country": country,
        "activeStatus": "active",
        "minDaysRunning": 60,
        "maxResults": limit,
        "scrapeAdDetails": True
    }

    log.info("Starting Apify actor for country: %s...", country)
    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input, timeout_secs=120)
        if not run:
            return []

        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        log.info("Apify returned %d ads.", len(dataset_items))
        
        leads = []
        for item in dataset_items:
            # 1. Get the real domain from the creative's destinationUrl
            domain = "unknown.com"
            creatives = item.get("creatives", [])
            if creatives:
                dest_url = creatives[0].get("destinationUrl", "")
                if dest_url and "facebook.com" not in dest_url and "instagram.com" not in dest_url:
                    domain = dest_url.split("//")[-1].split("/")[0]

            # 2. Get the brand name
            brand = item.get("pageName") or "Unknown Brand"
            
            # 3. Get the ad text and headline
            primary_text = creatives[0].get("body", "") if creatives else ""
            headline = creatives[0].get("title", "") if creatives else ""
            
            # 4. Get the Facebook Page URI (build it from pageId)
            page_id = item.get("pageId", "")
            page_uri = f"https://www.facebook.com/{page_id}" if page_id else ""
            
            leads.append({
                "domain": domain,
                "brand": brand,
                "ad_archive_id": str(item.get("adArchiveId", "")),
                "days_active": item.get("daysRunning", 60),
                "ad_headline": headline,
                "ad_primary": primary_text,
                "ad_image_url": creatives[0].get("imageUrls", [""])[0] if creatives and creatives[0].get("imageUrls") else "",
                "page_profile_uri": page_uri,
            })
            
        return leads
    except Exception as e:
        log.error("Apify error: %s", e)
        return []
