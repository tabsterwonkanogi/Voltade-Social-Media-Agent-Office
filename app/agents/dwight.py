"""Dwight. Posts things.

Deliberately the dumbest agent on the team. He has no judgement and no model
call: he takes what was approved and sends it. Anything that needs a decision
happened before it reached him.

A poster that can think is a poster that can be talked into posting something.
"""

from __future__ import annotations

import logging

from .. import blotato, db, notify

log = logging.getLogger("agents.dwight")


def due() -> list[dict]:
    """Approved posts whose time has come, or which had no time set."""
    now = db.now()
    return [p for p in db.list_posts(status="approved", limit=50)
            if not p["scheduled_for"] or p["scheduled_for"] <= now]


def post_all(dry_run: bool = False) -> list[dict]:
    if db.killed():
        db.audit("agent.halted", actor="dwight", surface="system",
                 detail="kill switch on")
        return []

    results = []
    for post in due():
        results.append(post_one(post, dry_run=dry_run))
    return results


def post_one(post: dict, dry_run: bool = False) -> dict:
    run_id = db.start_run("dwight")

    if dry_run or not blotato.configured() or not blotato.publishing_enabled():
        reason = ("dry run" if dry_run
                  else "BLOTATO_API_KEY not set" if not blotato.configured()
                  else "publishing is off in this environment, PUBLISHING is not on")
        db.end_run(run_id, status="skipped", summary=reason)
        log.info("skipped %s (%s)", post["id"], reason)
        return {"post_id": post["id"], "skipped": reason}

    try:
        accounts = blotato.accounts_by_platform()
    except Exception as exc:
        db.end_run(run_id, status="error", error=str(exc))
        raise

    outcome, ids = {}, {}
    for platform in post["platforms"]:
        account_id = accounts.get(platform)
        if not account_id:
            outcome[platform] = {"ok": False,
                                 "error": f"no {platform} account connected"}
            continue
        try:
            res = blotato.publish(account_id, platform, post["body"],
                                  post["media_paths"])
        except blotato.WouldPostToPersonalProfile as exc:
            outcome[platform] = {"ok": False, "error": str(exc)}
            continue
        outcome[platform] = {"ok": res["ok"], "error": res["error"],
                             "url": res["post_url"]}
        if res["blotato_id"]:
            ids[platform] = res["blotato_id"]

    db.record_publish(post["id"], blotato_ids=ids, result=outcome)
    _tell_her(post, outcome)
    db.end_run(run_id, status="ok",
               summary=", ".join(f"{k}:{'ok' if v['ok'] else 'failed'}"
                                 for k, v in outcome.items()))
    return {"post_id": post["id"], "result": outcome}


def _tell_her(post: dict, outcome: dict) -> None:
    """Say so, every single time something reaches a real account.

    Publishing used to be silent: the only message this system sent was the
    6pm digest, and that reports counts. On 14 September four posts reached
    the company LinkedIn page and the first anyone knew of it was scrolling
    the feed. Anything that speaks in public announces itself.
    """
    first = post["body"].splitlines()[0][:70]
    lines = [f"Posted: {first}", ""]
    for platform, res in outcome.items():
        if res.get("ok"):
            lines.append(f"  {platform}: live  {res.get('url') or ''}".rstrip())
        else:
            lines.append(f"  {platform}: FAILED  {(res.get('error') or '')[:90]}")
    lines += ["", f"Approved by whoever approved {post['id']}. "
                  f"If this is a surprise, the kill switch is in Settings."]
    notify.send("\n".join(lines))
