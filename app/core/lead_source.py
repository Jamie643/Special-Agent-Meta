"""Fetches stale ads from Facebook & Instagram using meta-ads-collector."""

import logging
from meta_ads_collector import MetaAdsCollector, FilterConfig

log = logging.getLogger(__name__)

def fetch_stale_ads(limit: int = 10) -> list[dict]:
    """Fetches active ads running 60+ days on Facebook AND Instagram."""
    
    filters = FilterConfig(
        publisher_platforms=["facebook", "instagram"],
    )

    leads = []
    try:
        with MetaAdsCollector() as collector:
            for ad in collector.search(
                query="shop", 
                country="US",
                max_results=limit,
                filter_config=filters
            ):
                # Extract the Facebook Page Link (for finding their IG)
                page_link = ""
                if ad.page and hasattr(ad.page, 'page_url'):
                    page_link = ad.page.page_url
                
                # Get the domain from the CTA link if available
                domain = "unknown.com"
                if ad.snapshot and hasattr(ad.snapshot, 'link_url') and ad.snapshot.link_url:
                    domain = ad.snapshot.link_url.split("//")[-1].split("/")[0]
                
                leads.append({
                    "domain": domain,
                    "brand": ad.page.name if ad.page else "Unknown Brand",
                    "ad_archive_id": str(ad.id),
                    "days_active": getattr(ad, 'days_active', 60),
                    "ad_headline": getattr(ad.snapshot, 'title', "") if ad.snapshot else "",
                    "ad_primary": getattr(ad.snapshot, 'body', {}).get('text', "") if ad.snapshot and isinstance(ad.snapshot.body, dict) else "",
                    "ad_image_url": "",
                    "page_profile_uri": page_link,  # For finding their IG
                })
        
        log.info("Fetched %d ads from FB+IG.", len(leads))
        return leads
        
    except Exception as e:
        log.error("MetaAdsCollector error: %s", e)
        return []
