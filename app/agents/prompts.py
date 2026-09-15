"""Load an agent's job description from prompts/.

Read fresh every run, so editing a job description takes effect on the next
run without a restart. That matters because scoping an agent is an iterative
thing: you read what it produced, change one line, run it again.

Brand facts are substituted in rather than repeated, so there is exactly one
place that knows what the voice rules are.
"""

from __future__ import annotations

from pathlib import Path

from .. import config

PROMPTS = config.ROOT / "prompts"


def persona() -> str:
    """Michael's voice, switchable from Settings without editing a prompt.

    A costume that can only be taken off by editing a file is not a switch,
    and she asked to be able to turn it off immediately.
    """
    from .. import db
    if db.get_setting("persona.michael", "on") != "on":
        return ""
    return config.MICHAEL_PERSONA.strip()


def context() -> dict[str, str]:
    return {
        "brand": config.BRAND,
        "product": config.PRODUCT,
        "audience": config.AUDIENCE,
        "voice": config.VOICE.strip(),
        "pillars": "\n".join(f"- {k}: {v}" for k, v in config.PILLARS),
        "no_go": "\n".join(f"- {t}" for t in config.NO_GO_TOPICS),
        "posts_per_day": str(config.POSTS_PER_DAY),
        "posts_min": str(config.POSTS_PER_DAY_MIN),
        "posts_max": str(config.POSTS_PER_DAY_MAX),
        "opinions": "\n".join("- " + o for o in config.OPINIONS),
        "people": ", ".join(f"{n} ({r})" for n, r in config.PEOPLE.items()),
        "podcast": config.PODCAST,
        "persona": persona(),
        "review_minutes": str(config.REVIEW_BUDGET_MINUTES),
        "rate_limit": str(config.KELLY_MAX_REPLIES_PER_HOUR),
    }


def load(agent: str) -> str:
    path = PROMPTS / f"{agent}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"no job description for {agent}. Expected {path}")
    text = path.read_text(encoding="utf-8")
    for key, value in context().items():
        text = text.replace("{{" + key + "}}", value)
    left = [line for line in text.splitlines() if "{{" in line]
    if left:
        raise ValueError(
            f"{path.name} uses tokens nothing fills: {left[0].strip()!r}. "
            f"Known tokens: {sorted(context())}")
    return text
