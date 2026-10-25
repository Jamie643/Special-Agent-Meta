"""FastAPI entrypoint. Mounts the Telegram webhook and the internal job endpoint."""

import logging
from fastapi import FastAPI, Request, BackgroundTasks
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.bot.handlers import router as bot_router
from app.core.daily_job import run_daily_pipeline

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Special Agent Meta")

bot = Bot(
    token=settings.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
dp.include_router(bot_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "special-agent-meta"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/whoami")
def whoami():
    return {
        "telegram_user_id": settings.TELEGRAM_USER_ID,
        "gemini_models": settings.GEMINI_MODELS,
        "has_supabase_url": bool(settings.SUPABASE_URL),
        "has_supabase_key": bool(settings.SUPABASE_SERVICE_KEY),
        "has_gemini_key": bool(settings.GEMINI_API_KEY),
        "has_telegram_token": bool(settings.TELEGRAM_BOT_TOKEN),
        "has_apify_token": bool(getattr(settings, "APIFY_API_TOKEN", None)),
    }


@app.post(f"/webhook/{settings.TELEGRAM_BOT_TOKEN}")
async def telegram_webhook(request: Request):
    update = await request.json()
    from aiogram.types import Update
    await dp.feed_update(bot, Update.model_validate(update))
    return {"ok": True}


@app.post("/internal/run-daily")
async def trigger_daily_job(background_tasks: BackgroundTasks):
    """Triggered by Supabase pg_cron every morning."""
    log.info("Received trigger for daily job.")
    background_tasks.add_task(run_daily_pipeline, bot)
    return {"ok": True, "message": "Daily job started in background"}
