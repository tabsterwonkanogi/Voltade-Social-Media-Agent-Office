"""Publishing rail.

Written for this project. Nothing is imported from voltadevideobot; the only
thing shared is the Blotato account itself.

The one thing this file exists to get right: Blotato accepting a post is not
the same as a platform publishing it. POST /v2/posts returns immediately. Only
GET /v2/posts says what each platform actually did, so publish() submits and
then confirms, and an unconfirmed post is never reported as published.
"""

from __future__ import annotations

import os
import time

import httpx

BASE = "https://backend.blotato.com/v2"


class NotConfigured(RuntimeError):
    pass


def key() -> str:
    k = (os.environ.get("BLOTATO_API_KEY") or "").strip()
    if not k:
        raise NotConfigured(
            "BLOTATO_API_KEY is not set. Copy it from the Railway variables "
            "on the existing bot service into agent-team/.env")
    return k


def configured() -> bool:
    return bool((os.environ.get("BLOTATO_API_KEY") or "").strip())


def _req(path: str, body: dict | None = None, method: str = "GET") -> dict:
    with httpx.Client(timeout=60) as c:
        r = c.request(method, f"{BASE}{path}",
                      headers={"blotato-api-key": key(),
                               "content-type": "application/json"},
                      json=body)
        r.raise_for_status()
        return r.json()


def accounts() -> list[dict]:
    return _req("/accounts").get("items", []) or []


def recent_posts() -> list[dict]:
    """The only endpoint that reports what each platform actually did."""
    return _req("/posts").get("items", []) or []


def publish(account_id: str, platform: str, text: str,
            media_urls: list[str] | None = None,
            confirm_timeout: int = 120) -> dict:
    """Submit, then wait for the platform's real answer.

    Returns {ok, post_url, error, blotato_id}. ok is only true once the
    platform has confirmed, never on submission alone.
    """
    before = {p.get("id") for p in recent_posts()}

    submitted = _req("/posts", {
        "post": {
            "accountId": account_id,
            "target": {"targetType": platform},
            "content": {"text": text, "platform": platform,
                        "mediaUrls": media_urls or []},
        }
    }, method="POST")

    blotato_id = submitted.get("id") or (submitted.get("post") or {}).get("id")

    deadline = time.time() + confirm_timeout
    while time.time() < deadline:
        for p in recent_posts():
            if p.get("id") in before:
                continue
            if blotato_id and p.get("id") != blotato_id:
                continue
            state = p.get("state") or {}
            kind = state.get("type")
            if kind in ("published", "success"):
                return {"ok": True, "post_url": state.get("postUrl"),
                        "error": None, "blotato_id": p.get("id")}
            if kind in ("failed", "error"):
                return {"ok": False, "post_url": None,
                        "error": state.get("errorMessage") or "failed",
                        "blotato_id": p.get("id")}
        time.sleep(5)

    return {"ok": False, "post_url": None,
            "error": "no outcome from the platform within the timeout",
            "blotato_id": blotato_id}
