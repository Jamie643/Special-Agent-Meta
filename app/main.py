"""FastAPI entrypoint. Mounts the Telegram webhook and the internal job endpoint."""

import logging

from fastapi import FastAPI

from app.config import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Special Agent Meta")


@app.get("/")
def root():
    return {"status": "ok", "service": "special-agent-meta"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/whoami")
def whoami():
    """Sanity check — confirms env vars are loaded without exposing secrets."""
    return {
        "telegram_user_id": settings.TELEGRAM_USER_ID,
        "gemini_models": settings.GEMINI_MODELS,
        "has_supabase_url": bool(settings.SUPABASE_URL),
        "has_supabase_key": bool(settings.SUPABASE_SERVICE_KEY),
        "has_gemini_key": bool(settings.GEMINI_API_KEY),
        "has_telegram_token": bool(settings.TELEGRAM_BOT_TOKEN),
    }
