"""Angela. Reads the numbers and says what to do differently.

Also blocked. Metrics need platform access that Blotato does not provide.

She returns "not connected" rather than an estimate, a sample, or a plausible
looking chart. One invented number and nothing on the dashboard can be
trusted again, which is a worse outcome than an empty page.
"""

from __future__ import annotations

from .. import config, db


def connected_platforms() -> list[str]:
    return [p for p in config.PLATFORMS
            if db.get_setting(f"metrics_access.{p}", "off") == "on"]


def status() -> dict:
    connected = connected_platforms()
    return {
        "agent": "angela",
        "ready": bool(connected),
        "connected": connected,
        "blocked_by": None if connected else
        "no platform grants metrics access yet",
    }


def numbers() -> dict:
    """What the dashboard shows. Never a placeholder."""
    s = status()
    if not s["ready"]:
        return {"available": False, "reason": s["blocked_by"], "metrics": {}}
    raise NotImplementedError("wire real metrics when access lands")


def house_numbers() -> dict:
    """What we can count without any platform: our own activity.

    This is honest to show today because it comes from our own store.
    """
    published = db.list_posts(status="published", limit=500)
    pending = db.list_posts(status="pending", limit=500)
    rejected = db.list_posts(status="rejected", limit=500)
    expired = db.list_posts(status="expired", limit=500)
    return {
        "published": len(published),
        "awaiting_review": len(pending),
        "rejected": len(rejected),
        "expired_unreviewed": len(expired),
    }


def check() -> dict:
    s = status()
    if not s["ready"]:
        db.audit("agent.blocked", actor="angela", surface="system",
                 detail=s["blocked_by"])
    return s
