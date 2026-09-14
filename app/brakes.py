"""The brakes. Every agent action passes through here before it takes effect.

Everyone builds the agent. Almost nobody builds the brakes, and the brakes are
the reason you can leave the thing switched on.

Four independent limits, in the order they are checked:

  1. The kill switch. One setting, stops everything, visible on every page.
  2. The autonomy dial. Per agent. "ask" holds the output for a human,
     "auto" lets it act and report afterwards.
  3. The no-go list. Topics Kelly will not touch at any autonomy level.
  4. The rate limit. A cap on how often Kelly can speak, so a bad loop
     cannot spray the company name across a platform.

Plus one rule that outranks the dial entirely: anything marked confidential
needs a human yes regardless of autonomy.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config, db


@dataclass
class Verdict:
    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed


ALLOW = Verdict(True)


def kill_switch(on: bool, *, actor: str, surface: str) -> None:
    db.set_setting("kill_switch", "on" if on else "off",
                   actor=actor, surface=surface)


def set_autonomy(agent: str, level: str, *, actor: str, surface: str) -> None:
    if agent not in config.AGENTS:
        raise ValueError(f"unknown agent {agent!r}")
    if level not in ("ask", "auto"):
        raise ValueError("autonomy is either ask or auto")
    db.set_setting(f"autonomy.{agent}", level, actor=actor, surface=surface)


def check_topic(text: str) -> Verdict:
    """The no-go list. Applies at every autonomy level, including auto."""
    lowered = text.lower()
    for topic in config.NO_GO_TOPICS:
        for needle in _needles(topic):
            if needle in lowered:
                return Verdict(False, f"no-go topic: {topic}")
    return ALLOW


def _needles(topic: str) -> list[str]:
    """Words that actually appear in a comment, derived from a policy phrase."""
    base = topic.replace("anything about an individual's employment", "fired")
    base = base.replace("competitors by name", "competitor")
    base = base.replace("pricing disputes", "overcharge")
    words = [w for w in base.split() if len(w) > 3]
    return [w.rstrip("s") for w in words] or [base]


def check_rate(agent: str = "kelly") -> Verdict:
    from .agents import kelly
    if kelly.rate_limited():
        return Verdict(False, f"rate limit: {config.KELLY_MAX_REPLIES_PER_HOUR} "
                              f"replies already sent this hour")
    return ALLOW


def can_act(agent: str, *, text: str = "", confidential: bool = False) -> Verdict:
    """The one call every agent makes before doing anything outward facing."""
    if db.killed():
        return Verdict(False, "kill switch is on")

    if confidential:
        return Verdict(False, "confidential source, needs a human yes")

    if text:
        topic = check_topic(text)
        if not topic:
            return topic

    if agent == "kelly":
        rate = check_rate()
        if not rate:
            return rate

    return ALLOW


def acts_alone(agent: str) -> bool:
    """True when this agent may act without waiting for a human."""
    return db.autonomy(agent) == "auto"


def state() -> dict:
    """What the cockpit shows, and what the kill switch banner reads from."""
    return {
        "kill_switch": "on" if db.killed() else "off",
        "autonomy": {a: db.autonomy(a) for a in config.AGENTS},
        "no_go_topics": config.NO_GO_TOPICS,
        "kelly_rate_limit_per_hour": config.KELLY_MAX_REPLIES_PER_HOUR,
    }
