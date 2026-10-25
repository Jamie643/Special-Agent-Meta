"""Fetches stale ads from the Meta Ad Library via Apify."""

import logging
from apify_client import ApifyClient
from app.config import settings

log = logging.getLogger(__name__)

# The Apify actor we are using
ACTOR_ID = "brilliant_gum/facebook-ads-library-scraper"

def fetch_stale_ads(limit: int = 10) -> list[dict]:
    """Fetches active ads that have been running for 60+ days.
    
    Returns a list of dicts ready for the database.
    """
    if not hasattr(settings, "APIFY_API_TOKEN"):
        log.error("APIFY_API_TOKEN is missing from settings!")
        return []

    client = ApifyClient(settings.APIFY_API_TOKEN)
    
    # We search for e-commerce style ads that have been running a long time
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
        # Run the actor and wait for it to finish (max 120 seconds)
        run = client.actor(ACTOR_ID).call(run_input=run_input, timeout_secs=120)
        if not run:
            log.error("Apify actor failed to return a run object.")
            return []

        # Fetch the results from the dataset
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        log.info("Apify returned %d ads.", len(dataset_items))
        
        leads = []
        for item in dataset_items:
            # Extract the domain from the ad's landing page URL
            url = item.get("snapshot", {}).get("linkUrl", "")
            domain = url.split("//")[-1].split("/")[0] if url else "unknown.com"
            
            # Sometimes the brand name isn't perfect, fallback to domain
            brand = item.get("pageName") or domain.split(".")[0].title()
            
            leads.append({
                "domain": domain,
                "brand": brand,
                "ad_archive_id": str(item.get("adArchiveID", "")),
                "days_active": item.get("daysActive", 60),
                "ad_headline": item.get("snapshot", {}).get("title", ""),
                "ad_primary": item.get("snapshot", {}).get("body", {}).get("text", ""),
                "ad_image_url": item.get("snapshot", {}).get("images", [{}])[0].get("originalImageUrl", ""),
                "ad_snapshot": item
            })
            
        return leads
    except Exception as e:
        log.error("Apify error: %s", e)
        return []
