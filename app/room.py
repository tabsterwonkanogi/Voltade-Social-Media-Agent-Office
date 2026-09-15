"""The team chat: six bots in one Telegram group.

A bot has exactly one identity, so six agents need six bots. Each one posts as
itself, which is the whole point: Pam's draft arrives from Pam.

Telegram never delivers one bot's message to another bot, so the agents cannot
learn what happened by listening to the group. They read the `room` table
instead. We sent all of it, so we already know what was said, and the
transcript is ours rather than Telegram's.

Replying is how you talk to one of them. Telegram delivers a reply to a bot's
own message even with privacy mode on, so nothing has to be switched off and
no mentions are needed: reply to Pam and Pam hears you.
"""

from __future__ import annotations

import logging
import os

import httpx

from . import config, db

log = logging.getLogger("room")

API = "https://api.telegram.org/bot{token}/{method}"


def token(agent: str) -> str:
    return (os.environ.get("TELEGRAM_BOT_TOKEN_" + agent.upper()) or "").strip()


def group_id() -> str:
    return (os.environ.get("TELEGRAM_GROUP_ID") or "").strip()


def topic(agent: str) -> str:
    """Optional per-agent thread, when the group has Topics turned on."""
    return (os.environ.get("TELEGRAM_TOPIC_" + agent.upper()) or "").strip()


def staffed() -> list[str]:
    return [a for a in config.AGENTS if token(a)]


def ready() -> bool:
    return bool(group_id()) and bool(staffed())


def _call(agent: str, method: str, payload: dict) -> dict | None:
    tok = token(agent)
    if not tok:
        log.warning("%s has no bot token, message dropped", agent)
        return None
    try:
        r = httpx.post(API.format(token=tok, method=method), json=payload,
                       timeout=25)
        j = r.json()
        if not j.get("ok"):
            log.error("%s %s failed: %s", agent, method,
                      str(j.get("description"))[:160])
            return None
        return j.get("result")
    except Exception:
        log.exception("%s %s crashed", agent, method)
        return None


def say(agent: str, text: str, *, reply_to: str | None = None) -> str | None:
    """Post to the group as that agent, and keep a copy in the room.

    Best effort on the Telegram side: a failed send must never break the job
    that was reporting. The transcript is written either way, so an agent
    reading the room later sees what was meant to be said.
    """
    chat = group_id()
    payload = {"chat_id": chat, "text": text,
               "disable_web_page_preview": True}
    thread = topic(agent)
    if thread:
        payload["message_thread_id"] = int(thread)
    if reply_to:
        payload["reply_to_message_id"] = int(reply_to)

    sent = _call(agent, "sendMessage", payload) if chat else None
    db.room_add("agent", text, agent=agent, tg_chat_id=chat or None,
                tg_msg_id=str(sent["message_id"]) if sent else None,
                topic_id=thread or None, reply_to=reply_to)
    return str(sent["message_id"]) if sent else None


def broadcast(text: str, *, agent: str = "michael") -> str | None:
    """Something the office says rather than a person. Michael's voice."""
    return say(agent, text)


# ---------------------------------------------------------------- inbound

def handle_update(agent: str, update: dict) -> None:
    """One Telegram update for one agent's bot.

    With privacy mode on we only ever see: messages replying to this bot,
    messages mentioning it, commands, and membership changes. That is exactly
    the surface we want, so privacy mode stays on.
    """
    member = update.get("my_chat_member")
    if member:
        chat = member.get("chat") or {}
        log.info("%s membership changed in chat %s (%s)",
                 agent, chat.get("id"), chat.get("title"))
        db.audit("telegram.membership", actor=agent, surface="telegram",
                 target=str(chat.get("id")), detail=str(chat.get("title")))
        return

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    text = (msg.get("text") or msg.get("caption") or "").strip()
    if not text:
        return

    chat_id = str((msg.get("chat") or {}).get("id"))
    who = msg.get("from") or {}
    name = who.get("username") or who.get("first_name") or "someone"
    replied = msg.get("reply_to_message") or {}

    db.room_add("human", text, actor=name, tg_chat_id=chat_id,
                tg_msg_id=str(msg.get("message_id")),
                topic_id=str(msg.get("message_thread_id") or "") or None,
                reply_to=str(replied.get("message_id") or "") or None)

    # Which agent is this for? The one whose message she replied to, falling
    # back to the bot that received it.
    target = agent
    if replied:
        origin = db.room_by_message(chat_id, str(replied.get("message_id")))
        if origin and origin.get("agent"):
            target = origin["agent"]

    db.say(target, "user", text, actor=name)
    db.audit("agent.instructed", actor=name, surface="telegram",
             target=target, detail=text[:300])
    log.info("instruction for %s from %s: %s", target, name, text[:80])


def register_webhooks(base_url: str, secret: str) -> dict[str, bool]:
    """Point every staffed bot at this service. Idempotent."""
    out = {}
    for agent in staffed():
        url = f"{base_url.rstrip('/')}/telegram/{agent}/{secret}"
        res = _call(agent, "setWebhook", {
            "url": url,
            "allowed_updates": ["message", "edited_message", "my_chat_member"],
            "drop_pending_updates": True,
        })
        out[agent] = bool(res)
    return out


def whois() -> list[dict]:
    """Who is actually staffed, for the cockpit to show honestly."""
    rows = []
    for a in config.AGENTS:
        if not token(a):
            rows.append({"agent": a, "staffed": False, "username": None})
            continue
        me = _call(a, "getMe", {}) or {}
        rows.append({"agent": a, "staffed": True,
                     "username": me.get("username"),
                     "display": me.get("first_name")})
    return rows
