"""Kelly. Answers the comments.

She cannot run yet. Reading comments needs platform access that Blotato does
not provide, and those applications are in review. Rather than fake it, she
reports honestly that she has no ears.

The guardrails below are written now, before she can act, on purpose. An
engagement agent that talks to strangers under the company name is the one
piece of this system that can do real damage, and the brakes should exist
before the engine does.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from anthropic import beta_tool

from .. import brakes, config, db
from . import runner


def connected_platforms() -> list[str]:
    """Platforms we can actually read comments from. Empty until review lands."""
    return [p for p in config.PLATFORMS
            if db.get_setting(f"comments_access.{p}", "off") == "on"]


def status() -> dict:
    connected = connected_platforms()
    return {
        "agent": "kelly",
        "ready": bool(connected),
        "connected": connected,
        "blocked_by": None if connected else
        "no platform grants comment read access yet",
    }


def rate_limited() -> bool:
    """No more than the configured replies per hour, ever."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM comments "
            "WHERE status = 'replied' AND replied_at >= ?", (cutoff,)).fetchone()
    return row["n"] >= config.KELLY_MAX_REPLIES_PER_HOUR


def screen(text: str) -> str | None:
    """Return a reason to refuse, or None if it is safe to draft a reply.

    A refused comment is stored with its reason rather than dropped, so a
    blocked reply can be shown rather than just asserted.
    """
    lowered = text.lower()
    for topic in config.NO_GO_TOPICS:
        needle = topic.split(" by ")[0].rstrip("s")
        if needle in lowered:
            return f"no-go topic: {topic}"
    if rate_limited():
        return (f"rate limit: already replied "
                f"{config.KELLY_MAX_REPLIES_PER_HOUR} times this hour")
    return None


def check() -> dict:
    s = status()
    if not s["ready"]:
        db.audit("agent.blocked", actor="kelly", surface="system",
                 detail=s["blocked_by"])
    return s


SYSTEM = f"""You are Kelly. You answer comments on {config.BRAND}'s posts,
in public, using the company's name. Write as a person at the company.

How to write:
{config.VOICE}

Rules for replies specifically:
- Short. One or two sentences. This is a comment, not a post.
- Answer what was actually asked. Do not pivot to a pitch.
- If someone asks something you do not know, say you will find out. Never
  invent a price, a timeline, a feature or a customer.
- Never argue. If a comment is critical and fair, acknowledge it.
- No hashtags in replies.
- Never use an em dash.

Call save_reply once with your reply, then stop.
"""


@beta_tool
def save_reply(comment_id: str, reply: str) -> str:
    """Save a reply for review.

    Args:
        comment_id: The comment being answered.
        reply: One or two sentences.
    """
    if "—" in reply:
        return "Rejected: contains an em dash. Rewrite and call again."
    db.draft_reply(comment_id, reply)
    return f"Saved reply to {comment_id}. Stop now."


def handle(comment: dict) -> dict:
    """Screen first, then draft. A refused comment is stored with its reason.

    Nothing here sends anything. A drafted reply waits for a human unless
    Kelly's dial is on auto, and even then the brakes above still apply.
    """
    verdict = brakes.can_act("kelly", text=comment["text"])
    if not verdict:
        db.block_comment(comment["id"], verdict.reason)
        return {"comment_id": comment["id"], "blocked": verdict.reason}

    task = (f"Comment id {comment['id']} on {comment['platform']} "
            f"from {comment['author'] or 'someone'}:\n\n{comment['text']}")
    runner.run("kelly", task, tools=[save_reply], system=SYSTEM,
               effort="medium")

    if brakes.acts_alone("kelly"):
        db.mark_replied(comment["id"], actor="kelly", surface="agent")
        return {"comment_id": comment["id"], "sent": True}

    return {"comment_id": comment["id"], "awaiting_review": True}


def sweep() -> list[dict]:
    """Every new comment, screened and drafted. Called by the clock."""
    return [handle(c) for c in db.list_comments(status="new", limit=20)]
