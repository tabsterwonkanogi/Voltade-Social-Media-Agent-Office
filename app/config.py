"""Everything about Voltade lives here.

One file, deliberately. A future pivot to another brand edits this file and
nothing else. No brand fact, voice rule or volume number belongs anywhere else
in the codebase.
"""

from __future__ import annotations

import os
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------- environment

TZ = ZoneInfo(os.environ.get("TZ", "Asia/Singapore"))
DB_PATH = os.environ.get("DB_PATH", "data/app.db")

# ---------------------------------------------------------------- the brand

BRAND = "Voltade"
PRODUCT = "Volty"

# Spelling is not negotiable. Transcription and generation both mangle these,
# so anything that produces text or on-screen copy checks against this table.
NAME_FIXES = {
    "voltaid": BRAND, "voltade.": BRAND, "volt aid": BRAND, "boltade": BRAND,
    "volty tan": "Volty", "boaty": PRODUCT, "volti": PRODUCT, "bolty": PRODUCT,
}

AUDIENCE = (
    "Owners of small and medium businesses in Singapore. They are not in the AI "
    "industry and do not care about AI discourse. They care about their own "
    "situation: staff time, missed messages, work that does not get done."
)

VOICE = """
Write like a person who runs a business, not like a brand account.

Rules that are not style preferences, they are hard requirements:
- Never use an em dash. Use a comma, a colon, or a full stop.
- Open on the reader's situation, never on the state of AI.
- One idea per line, blank line between ideas. Never a wall of text.
- No hype, no money claims, no "game changer", no emoji as bullets.
- Say the specific thing. "Answers WhatsApp at 11pm" beats "improves efficiency".
- Three to six hashtags, all relevant, at the end.
"""

# Every row of an on-screen header must be a whole sentence, never a mid
# sentence wrap, and a leading word must never be left dangling at the end of
# a line. Renderers import these.
ORPHAN_WORDS = {"a", "an", "the", "to", "of", "in", "on", "for", "and", "or", "is", "AI"}

# ---------------------------------------------------------------- what we post

PILLARS = [
    ("build_in_public", "What we are building this week and what broke."),
    ("customer_problem", "A real problem an SME owner has, named plainly."),
    ("how_it_works", "One concrete mechanism explained without jargon."),
    ("proof", "Something that actually happened, with a number or a screenshot."),
    ("point_of_view", "A position on how small businesses should adopt AI."),
]

PLATFORMS = ["linkedin", "instagram", "tiktok", "facebook", "x", "youtube"]

POSTS_PER_DAY = 3
REVIEW_BUDGET_MINUTES = 20
DRAFT_EXPIRY_HOURS = 72

# ---------------------------------------------------------------- the brakes

# Kelly will not touch these, ever, regardless of her autonomy setting.
NO_GO_TOPICS = [
    "politics", "elections", "religion", "race",
    "competitors by name", "pricing disputes",
    "customer complaints", "refunds", "legal threats",
    "layoffs", "anything about an individual's employment",
]

KELLY_MAX_REPLIES_PER_HOUR = 6
KELLY_MAX_REPLIES_PER_THREAD = 1

AGENTS = ["michael", "jim", "pam", "dwight", "kelly", "angela"]

AGENT_ROLES = {
    "michael": "coordinator",
    "jim": "research",
    "pam": "design and copy",
    "dwight": "posting",
    "kelly": "engagement",
    "angela": "strategy and analytics",
}

# "ask" means the output waits for a human. "auto" means it acts and reports.
DEFAULT_AUTONOMY = {name: "ask" for name in AGENTS}

# Anything sourced from internal notes or the Volty codebase is confidential by
# default and cannot publish on an autonomy dial alone.
CONFIDENTIAL_SOURCES = ["meeting notes", "volty codebase", "internal"]

# ---------------------------------------------------------------- the look

PALETTE = {
    "ink": "#2a0030",
    "brand": "#5a005f",
    "accent": "#ff6a33",
    "cream": "#fbfde6",
    "mauve": "#6d4a72",
}

FONTS = {
    "display": "Instrument Serif",
    "heading": "League Spartan",
    "mono": "JetBrains Mono",
}

# ---------------------------------------------------------------- model

MODEL = "claude-opus-5"
DAILY_TOKEN_CEILING = 4_000_000
