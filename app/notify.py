"""Push, so something reaches her without her going to look.

Notify only. No buttons, no approval logic. Every message carries a link into
the cockpit, and the cockpit is where decisions are made. When full Telegram
approvals arrive they call db.approve like the web does, and this file does
not change.
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("notify")


def configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN")
                and os.environ.get("TELEGRAM_CHAT_ID"))


def send(text: str, *, agent: str = "michael") -> bool:
    """Say it in the team group when there is one, else fall back to the DM.

    The group is the product. The direct message stays wired as a backstop so
    a removed bot or a deleted group does not silently take the 6pm rundown
    and the dead man's switch with it.
    """
    try:
        from . import room
        if room.ready():
            return room.say(agent, text) is not None
    except Exception:
        log.exception("group send failed, falling back to the direct message")
    return _send_dm(text)


def _send_dm(text: str) -> bool:
    """Best effort. A failed notification must never break a scheduled job."""
    if not configured():
        log.warning("telegram not configured, message dropped")
        return False
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    try:
        with httpx.Client(timeout=20) as c:
            r = c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": os.environ["TELEGRAM_CHAT_ID"],
                      "text": text,
                      "disable_web_page_preview": "true"},
            )
        if r.status_code != 200:
            log.error("telegram %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception:
        log.exception("telegram send failed")
        return False
