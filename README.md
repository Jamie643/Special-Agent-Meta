# Special Agent Meta

Telegram-driven audit machine for e-commerce brands with fatiguing Meta ads.

## Phase 1 (current)
- Scans Meta Ad Library for stores with ads running 60+ days
- Generates a fatigue diagnosis + 2 fresh ad angles via Gemini
- Pushes 10 audit cards/day to Telegram for manual Gmail outreach

## Stack
- FastAPI + aiogram (Telegram bot + webhook)
- Supabase (Postgres + pg_cron)
- Google Gemini (audit generation)
- Apify (Meta Ad Library scraper)
- Render (free web service host)

## Status
Phase 1 — in build.
