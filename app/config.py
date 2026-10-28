"""Reads all secrets from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SUPABASE_URL: str = os.environ["SUPABASE_URL"]
    SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]
    GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]
    TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
    TELEGRAM_USER_ID: int = int(os.environ["TELEGRAM_USER_ID"])
    GEMINI_MODELS: list[str] = ["gemini-3.8-flash", "gemini-2.5-flash"]

settings = Settings()
