"""Fetches small-business Meta ads using structural filters (follower counts)."""

import logging
import random
from apify_client import ApifyClient
from app.config import settings

log = logging.getLogger(__name__)

ACTOR_ID = "brilliant_gum/facebook-ads-library-scraper"

# Search terms that surface small sellers, not corporate giants
SMALL_BIZ_TERMS = [
    "handmade", "boutique", "smallbusiness", "etsy",
    "artisan", "vintage", "custom", "handcrafted",
]

def fetch_stale_ads(country: str = "US", limit: int = 10) -> list[dict]:
    """Fetches active Meta ads, then filters to small advertisers."""
    if not hasattr(settings, "APIFY_API_TOKEN"):
        log.error("APIFY_API_TOKEN is missing from settings!")
        return []

    client = ApifyClient(settings.APIFY_API_TOKEN)
    search_term = random.choice(SMALL_BIZ_TERMS)

    run_input = {
        "searchTerms": [search_term],
        "country": country,
        "activeStatus": "active",
        "minDaysRunning": 60,
        "maxAdsPerSearch": limit * 3,   # fetch extra, filter down later
        "scrapeAdDetails": True,
    }

    log.info("Starting Apify actor (term=%s, country=%s)...", search_term, country)
    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input, timeout_secs=180)
        if not run:
            return []

        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        log.info("Apify returned %d raw ads.", len(dataset_items))

        leads = []
        for item in dataset_items:
            if len(leads) >= limit:
                break

            # --- STRUCTURAL FILTER: follower count ---
            # brilliant_gum returns these as pageLikeCount / igFollowers
            page_likes = item.get("pageLikeCount") or item.get("pageLikes") or 0
            ig_followers = item.get("igFollowers") or item.get("instagramFollowers") or 0

            # Small business threshold: under 50K on both platforms
            if page_likes > 50_000 or ig_followers > 50_000:
                log.debug(
                    "Skipping %s (too big: FB=%s, IG=%s)",
                    item.get("pageName"), page_likes, ig_followers,
                )
                continue

            # --- Extract domain ---
            domain = "unknown.com"
            creatives = item.get("creatives", [])
            if creatives:
                dest_url = creatives[0].get("destinationUrl", "")
                if dest_url and "facebook.com" not in dest_url and "instagram.com" not in dest_url:
                    domain = dest_url.split("//")[-1].split("/")[0]

            brand = item.get("pageName") or "Unknown Brand"
            primary_text = creatives[0].get("body", "") if creatives else ""
            headline = creatives[0].get("title", "") if creatives else ""

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

        log.info("Filtered to %d small-business leads.", len(leads))
        return leads

    except Exception as e:
        log.error("Apify error: %s", e)
        return []
