"""Fetches stale ads from the Meta Ad Library via Apify."""

import logging
from apify_client import ApifyClient
from app.config import settings

log = logging.getLogger(__name__)

# The Apify actor we are using
ACTOR_ID = "brilliant_gum/facebook-ads-library-scraper"

def fetch_stale_ads(country: str, limit: int = 10) -> list[dict]:
    """Fetches active ads running 60+ days in a specific country."""
    if not hasattr(settings, "APIFY_API_TOKEN"):
        log.error("APIFY_API_TOKEN is missing from settings!")
        return []

    client = ApifyClient(settings.APIFY_API_TOKEN)
    
    # Optimized input to save quota and get exactly what we need
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
            snapshot = item.get("snapshot", {})
            
            # Get the domain
            domain = "unknown.com"
            link_url = snapshot.get("linkUrl")
            if not link_url:
                cards = snapshot.get("cards", [])
                if cards:
                    link_url = cards[0].get("linkUrl")
            if link_url:
                domain = link_url.split("//")[-1].split("/")[0]
            
            brand = item.get("pageName") or domain.split(".")[0].title()
            
            # Get the text
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
                "page_profile_uri": snapshot.get("page_profile_uri", ""),
            })
            
        return leads
    except Exception as e:
        log.error("Apify error: %s", e)
        return []
