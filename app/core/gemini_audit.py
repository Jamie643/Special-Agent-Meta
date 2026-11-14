"""Gemini audit generator — Phase 1 locked prompt (pro revision)."""

from __future__ import annotations

import json
import logging
import time

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings

log = logging.getLogger(__name__)


# ---------- I/O models ----------

class AdInput(BaseModel):
    domain: str
    brand: str | None = None
    sender: str = "the team"
    headline: str | None = None
    primary_text: str | None = None
    image_url: str | None = None
    days_active: int | None = None


class AuditResult(BaseModel):
    diagnosis: str
    hook1_angle_name: str
    hook1_target: str
    hook1_headline: str
    hook1_text: str
    hook1_image: str
    hook2_angle_name: str
    hook2_target: str
    hook2_headline: str
    hook2_text: str
    hook2_image: str
    email_subject: str
    email_body: str


# ---------- LOCKED prompt (pro revision) ----------

SYSTEM = """You are a senior direct-response copywriter writing a cold email to a busy e-commerce founder about their fatiguing Meta ad.

ABSOLUTE RULES:
- The email MUST be under 150 words total (excluding the subject line).
- Use short paragraphs. No walls of text.
- The email MUST end with a low-friction question. No "would you be open to a call" — ask something small and replyable.
- The subject line MUST be curiosity-driven and specific to the brand. Never generic.
- NEVER diagnose their internal metrics as failing ("your CAC is up", "you're burning spend"). Frame everything as an OPPORTUNITY to protect margins or refresh creative. You don't have their dashboard.

EMAIL STRUCTURE (follow exactly):
1. One sentence: name the specific ad + how many days it has been running.
2. One sentence: frame the opportunity (e.g. "cold traffic starts tuning out catalog titles around week four — that's usually where CPMs creep up").
3. "I wrote two direct-response angles based on your customers' real pain points:"
4. Angle 1: bullet of angle name, headline, and one-sentence visual.
5. Angle 2: bullet of angle name, headline, and one-sentence visual.
6. One line of credibility.
7. One low-friction question (e.g. "Want me to send the full copy and mockups for these two?").
8. Sign off with the sender name.

DIAGNOSIS (internal, not for the email):
- 1-2 sentences explaining what is wrong with the ad in plain, observable terms. No metric assumptions.

HOOKS:
- Each hook has a psychological name, a target buyer, a headline (<= 45 chars), one-to-two sentences of body copy, and a specific visual direction.
- Every hook must address a consumer pain point, not a product feature.
- Visuals must be concrete enough that a designer could shoot them (e.g. "split-screen macro of punctured cone vs. flush-mounted mesh").

Never invent specific claims, prices, discount codes, or stats about the brand.
"""

WORKED_EXAMPLE = """
--- WORKED EXAMPLE (match this format) ---
Input: AliExpress, 51 days, speaker grille ad.

Subject: Your speaker grille ads (51 days running)

Hi AliExpress Growth Team,

I noticed your speaker grille ad has been running for 51 days straight using raw catalog text. Usually cold traffic starts tuning out catalog titles around week four — that's where CPMs typically creep up.

To refresh the campaign, I wrote two direct-response angles focused on real car-audio pain points instead of generic discounts:

1. The "Blown Cone" Preventer
• Headline: One Stray Foot Can Destroy A Premium Speaker
• Visual: Split-screen showing a punctured, exposed cone vs. your flush-mounted metal mesh grille in a finished door panel.

2. The "Clean Factory Finish" Upgrade
• Headline: Stop Leaving Your Audio Installs Looking Half-Finished
• Visual: Close-up garage shot of a 4-inch speaker box showing how the guard hides raw mounting screws for an OEM look.

We build direct-response creatives like this daily to help e-commerce brands beat ad fatigue.

Want me to send the full copy and mockups for these two?

Best,
James Liberty
--- END WORKED EXAMPLE ---
"""


def _build_user_prompt(ad: AdInput) -> str:
    return f"""{WORKED_EXAMPLE}

Now produce the same for this input. Sender name for the signoff: {ad.sender}.

Brand domain: {ad.domain}
Brand name:   {ad.brand or "(unknown)"}
Days this ad has been live: {ad.days_active or "(unknown)"}
Current headline: {ad.headline or "(none)"}
Current primary text: {ad.primary_text or "(none)"}
Image reference: {ad.image_url or "(none)"}
"""


# ---------- Client ----------

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def generate_audit(ad: AdInput) -> AuditResult:
    client = _get_client()
    prompt = _build_user_prompt(ad)
    last_err: Exception | None = None

    for model_name in settings.GEMINI_MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM,
                        response_mime_type="application/json",
                        response_schema=AuditResult,
                        temperature=0.9,
                    ),
                )
                return AuditResult.model_validate(json.loads(resp.text))
            except Exception as e:
                err_str = str(e)
                log.warning(
                    "model %s attempt %d failed: %s",
                    model_name, attempt + 1, err_str[:120],
                )
                last_err = e
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    time.sleep(5)
                    continue
                break

    raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")
