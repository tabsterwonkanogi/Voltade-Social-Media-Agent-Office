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
    return _req("/users/me/accounts").get("items", []) or []


def accounts_by_platform() -> dict[str, str]:
    return {a["platform"]: a["id"] for a in accounts()}


def pages(account_id: str) -> list[dict]:
    try:
        return _req(f"/users/me/accounts/{account_id}/subaccounts").get("items", []) or []
    except Exception:
        return []


class WouldPostToPersonalProfile(RuntimeError):
    """Refusing to publish because no company page was resolved.

    On LinkedIn and Facebook a target without a pageId posts to the personal
    profile of whoever connected the account. That is not a small mistake, so
    it is an exception rather than a warning.
    """


_PAGE_ENV = {"linkedin": "LINKEDIN_PAGE_ID", "facebook": "FACEBOOK_PAGE_ID"}


def _page_id(account_id: str, platform: str) -> str | None:
    pinned = (os.environ.get(_PAGE_ENV.get(platform, ""), "") or "").strip()
    if pinned:
        return pinned
    found = pages(account_id)
    for page in found:
        if "voltade" in (page.get("name") or "").lower():
            return page.get("id")
    # One page and nothing else it could be is safe on Facebook, where a
    # personal timeline never appears in this list. Never on LinkedIn, where
    # the single entry can be the personal profile.
    if platform == "facebook" and len(found) == 1:
        return found[0].get("id")
    return None


def _target(platform: str, account_id: str) -> dict:
    t = {"targetType": platform}
    if platform == "tiktok":
        t.update({"privacyLevel": "PUBLIC_TO_EVERYONE",
                  "disabledComments": False, "disabledDuet": False,
                  "disabledStitch": False, "isBrandedContent": False,
                  "isYourBrand": True, "isAiGenerated": True})
    elif platform in ("linkedin", "facebook"):
        pid = _page_id(account_id, platform)
        if pid:
            t["pageId"] = pid
        else:
            names = ", ".join((p.get("name") or p.get("id", "?"))
                              for p in pages(account_id)) or "none"
            raise WouldPostToPersonalProfile(
                f"no Voltade page resolved on {platform}, refusing to post to "
                f"the personal profile. Pages found: {names}. "
                f"Pin one with {_PAGE_ENV[platform]}=<page id> in .env")
    return t


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
            "target": _target(platform, account_id),
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
