"""Supabase client (service role — bypasses RLS, single-user Phase 1)."""

from supabase import create_client, Client
from app.config import settings

_client: Client | None = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _client
