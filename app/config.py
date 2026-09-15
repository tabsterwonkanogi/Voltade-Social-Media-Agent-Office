"""Everything about Voltade lives here.

One file, deliberately. A future pivot to another brand edits this file and
nothing else. No brand fact, voice rule or volume number belongs anywhere else
in the codebase.
"""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------- environment

ROOT = Path(__file__).resolve().parent.parent

TZ = ZoneInfo(os.environ.get("TZ", "Asia/Singapore"))

# Relative paths resolve against the project, never the working directory.
# Railway runs from elsewhere and the launcher runs from the parent folder.
_db = os.environ.get("DB_PATH", "data/app.db")
DB_PATH = _db if os.path.isabs(_db) else str(ROOT / _db)

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
    "A top of funnel account. SME owners, second generation founders, and "
    "people who could become Voltade customers. The aim is reach, views, "
    "followers and growth, so the content does not have to be only about our "
    "exact buyer. They are not in the AI industry and do not care about AI "
    "discourse. They care about their own situation: staff time, missed "
    "messages, work that does not get done."
)

# Where the CEO says what he thinks, if an agent needs the source.
PODCAST = "https://www.youtube.com/@TheLeonardandVoltyShow"

# People an agent may write for, and what they are.
PEOPLE = {
    "Leonard": "CEO",
    "Yash": "Product Manager",
    "Beatrice": "Marketing Intern",
}

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
    ("education",
     "AI tips, jargon, news and tools. Position Voltade as the people you "
     "think of first when you want AI agents or custom AI for an SME. The "
     "tone is that you should know this by now: AI keeps developing and "
     "keeping up matters."),
    ("opinions",
     "Contrarian takes that cut through the AI noise, always about AI for "
     "businesses rather than AI in general."),
    ("normalisation",
     "For the middle aged and older, and for anyone who thinks they have no "
     "use case. Drowns out the accounts saying AI is only harmful. Used "
     "properly it is genuinely useful to a business, especially in CRM."),
]

# What Voltade actually believes. An opinion post argues one of these.
OPINIONS = [
    "AI is just a tool. The human is what makes it work well.",
    "AI is useful for non-tech companies and non-tech people too.",
    "AI should be integrated into every company.",
    "Companies that do not use AI in their workflows will fall behind.",
    "AI cannot replace human roles, but it is reframing how the work is done.",
    "AI agents are the new employees, and they are partners, not replacements.",
]

PLATFORMS = ["linkedin", "instagram", "tiktok", "facebook", "x", "youtube"]

POSTS_PER_DAY_MIN = 3
POSTS_PER_DAY_MAX = 5
POSTS_PER_DAY = POSTS_PER_DAY_MAX      # the ceiling every check uses
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


# ---------------------------------------------------------------- persona

# Michael talks like Michael Scott. It is a costume, not a licence: it never
# changes what he decides, only how he says it, and it comes off instantly
# from Settings without touching a prompt file.
MICHAEL_PERSONA = """
Talk like Michael Scott from The Office. Witty, a little goofy, fond of a
declaration. Study how he actually speaks: he over-commits to a bit, he
explains the joke, he means well.

Hard limit: never let it interfere with the work. The brief itself stays
precise and the volume rules still bind. If a choice is between being funny
and being clear, be clear.
"""
