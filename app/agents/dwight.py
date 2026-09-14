"""Dwight. Posts things.

Deliberately the dumbest agent on the team. He has no judgement and no model
call: he takes what was approved and sends it. Anything that needs a decision
happened before it reached him.

A poster that can think is a poster that can be talked into posting something.
"""

from __future__ import annotations

import logging

from .. import blotato, db

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

    if dry_run or not blotato.configured():
        reason = "dry run" if dry_run else "BLOTATO_API_KEY not set"
        db.end_run(run_id, status="skipped", summary=reason)
        log.info("skipped %s (%s)", post["id"], reason)
        return {"post_id": post["id"], "skipped": reason}

    try:
        accounts = {a.get("platform"): a.get("id") for a in blotato.accounts()}
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
        res = blotato.publish(account_id, platform, post["body"],
                              post["media_paths"])
        outcome[platform] = {"ok": res["ok"], "error": res["error"],
                             "url": res["post_url"]}
        if res["blotato_id"]:
            ids[platform] = res["blotato_id"]

    db.record_publish(post["id"], blotato_ids=ids, result=outcome)
    db.end_run(run_id, status="ok",
               summary=", ".join(f"{k}:{'ok' if v['ok'] else 'failed'}"
                                 for k, v in outcome.items()))
    return {"post_id": post["id"], "result": outcome}
