"""The clock. This is what makes it an agent team rather than a tool you open.

Two things this file exists to survive:

  Restarts. Railway redeploys and occasionally restarts on its own. Every
  once-a-day job records that it ran, keyed by the local date, so a restart at
  17:59 neither fires the 18:00 digest twice nor skips it.

  Itself. A job that throws must not take the scheduler down with it, so every
  job is wrapped. A dead scheduler that looks alive is the worst failure mode
  in the system, which is why /health checks the heartbeat.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from . import config, db, notify
from .agents import angela, dwight, jim, kelly, michael, pam

log = logging.getLogger("clock")

HEARTBEAT = "clock.heartbeat"
NL = chr(10)


# ---------------------------------------------------------------- guards

def already_ran(job: str, stamp: str) -> bool:
    """True if this job already ran for this slot. Survives restarts."""
    key = f"lastrun.{job}"
    if db.get_setting(key) == stamp:
        return True
    db.set_setting(key, stamp, actor="system", surface="system", record=False)
    return False


def today_stamp() -> str:
    return f"{db.local(db.now()):%Y-%m-%d}"


def slot_stamp() -> str:
    return f"{db.local(db.now()):%Y-%m-%d %H}"


def guarded(name: str, fn, *, once_per=None):
    """Wrap a job so it cannot kill the scheduler and cannot double fire."""
    def job():
        db.set_setting(HEARTBEAT, db.now(), actor="system", surface="system",
                       record=False)
        if db.killed():
            # Logged, not audited. While the switch is on every job halts
            # every few minutes, and a row each time would bury the one row
            # that matters: who turned it on.
            log.info("%s skipped, kill switch on", name)
            return
        if once_per is not None and already_ran(name, once_per()):
            log.info("%s already ran for this slot", name)
            return
        try:
            fn()
        except Exception:
            log.error("%s failed\n%s", name, traceback.format_exc())
            db.audit("job.failed", actor="system", surface="system",
                     target=name, detail=traceback.format_exc()[-800:])
    return job


# ---------------------------------------------------------------- the jobs

def plan_the_day() -> None:
    jim.research()
    michael.plan()


def produce_one() -> None:
    """One post per slot, never a batch. Three slots a day is the ceiling."""
    pending = db.list_posts(status="pending", limit=100)
    if len(pending) >= config.POSTS_PER_DAY * 2:
        log.info("queue already holds %s, skipping production", len(pending))
        db.audit("job.skipped", actor="michael", surface="system",
                 target="produce", detail=f"{len(pending)} already pending")
        return
    briefs = db.unused_notes("brief", limit=1)
    if not briefs:
        log.info("no briefs waiting")
        return
    brief = briefs[0]
    pam.write(brief["body"])
    db.mark_used(brief["id"])


def publish_due() -> None:
    dwight.post_all()


def check_comments() -> None:
    kelly.check()


def weekly_strategy() -> None:
    angela.check()


def sweep_expired() -> None:
    n = db.expire_stale()
    if n:
        log.info("expired %s unreviewed drafts", n)


def digest() -> None:
    """One message a day. What was made, what is waiting, what goes out."""
    pending = db.list_posts(status="pending", limit=100)
    approved = db.list_posts(status="approved", limit=100)
    since = db.day_start()
    published = [p for p in db.list_posts(status="published", limit=100)
                 if p["published_at"] and p["published_at"] >= since]

    lines = [f"Voltade agent office, {db.local(db.now()):%a %d %b}", ""]
    lines.append(f"published today: {len(published)}")
    lines.append(f"waiting for you: {len(pending)}")
    lines.append(f"approved, going out: {len(approved)}")

    if pending:
        lines += ["", "waiting:"]
        for p in pending[:5]:
            first = p["body"].splitlines()[0][:60]
            expires = db.local(p["expires_at"])
            lines.append(f"  {first}  (expires {expires:%a %H:%M})")
        if len(pending) > 5:
            lines.append(f"  and {len(pending) - 5} more")

    lines += ["", "the team today:"]
    lines += agent_lines()

    text = "\n".join(lines)
    db.add_note("strategy", f"digest {today_stamp()}", text, agent="michael")
    notify.send(text)


def agent_lines() -> list[str]:
    """One line per agent, from runs, not from an opinion about them."""
    out = []
    for name in config.AGENTS:
        runs = db.runs_today(name)
        ok = [r for r in runs if r["status"] == "ok"]
        bad = [r for r in runs if r["status"] == "error"]
        if name == "kelly" and not kelly.status()["ready"]:
            out.append(f"  {name}: blocked, {kelly.status()['blocked_by']}")
        elif name == "angela" and not angela.status()["ready"]:
            out.append(f"  {name}: blocked, {angela.status()['blocked_by']}")
        elif db.open_run(name):
            out.append(f"  {name}: working right now")
        elif bad:
            out.append(f"  {name}: {len(bad)} failed today, last: "
                       f"{(bad[0]['error'] or '')[:60]}")
        elif ok:
            out.append(f"  {name}: {len(ok)} done today")
        else:
            out.append(f"  {name}: nothing yet today")
    return out


def roundup() -> None:
    """09:00. What the team is going to do today, before it does it."""
    plan_the_day()
    briefs = db.unused_notes("brief", limit=10)
    lines = [f"Morning. {db.local(db.now()):%a %d %b}, here is the plan.", ""]
    lines += agent_lines()
    if briefs:
        lines += ["", "commissioned today:"]
        lines += [f"  {b['title'][:70]}" for b in briefs]
    else:
        lines += ["", "nothing commissioned. The queue already holds enough."]
    lines += ["", "Reply here if you want something changed before they start."]
    notify.send(NL.join(lines))


def hourly() -> None:
    """10:00 to 18:00. Silent when nothing changed.

    She asked for hourly updates. Nine identical messages a day would train
    her to ignore all of them, so this speaks when something actually moved
    and says nothing when it did not. The 18:00 rundown always goes.
    """
    fingerprint = "|".join(agent_lines()) + f"|{len(db.list_posts(status='pending', limit=200))}"
    if db.get_setting("lasthourly.fingerprint") == fingerprint:
        log.info("hourly: nothing changed, staying quiet")
        return
    db.set_setting("lasthourly.fingerprint", fingerprint,
                   actor="system", surface="system", record=False)
    pending = db.list_posts(status="pending", limit=200)
    lines = [f"{db.local(db.now()):%H:%M} update", ""]
    lines += agent_lines()
    lines += ["", f"waiting for you: {len(pending)}"]
    notify.send(NL.join(lines))


def week_plan() -> None:
    """Monday. What the week looks like."""
    plan_the_day()
    lines = [f"Monday. Plan for the week of {db.local(db.now()):%d %b}.", ""]
    lines += agent_lines()
    notify.send(NL.join(lines))


def week_review() -> None:
    """Friday. What actually happened, and what needs work."""
    published = [p for p in db.list_posts(status="published", limit=200)]
    rejected = db.list_posts(status="rejected", limit=200)
    expired = db.list_posts(status="expired", limit=200)
    lines = [f"Friday. How the week went.", ""]
    lines += agent_lines()
    lines += ["",
              f"published: {len(published)}",
              f"rejected by you: {len(rejected)}",
              f"expired unreviewed: {len(expired)}"]
    if expired:
        lines.append("  expiring drafts means the queue is outrunning review.")
    notify.send(NL.join(lines))


def alert_if_silent() -> None:
    """Dead man's switch. A silent system looks exactly like a working one."""
    last = db.get_setting(f"lastrun.digest")
    if not last:
        return
    try:
        when = datetime.fromisoformat(last + "T00:00:00+08:00")
    except ValueError:
        return
    if datetime.now(timezone.utc) - when > timedelta(hours=26):
        notify.send("No digest has gone out in over 26 hours. "
                    "Something is wrong with the agent office.")


# ---------------------------------------------------------------- wiring

JOBS = [
    ("roundup",  CronTrigger(hour=9, minute=0, timezone=config.TZ),
     roundup, today_stamp),
    ("produce",  CronTrigger(hour="10,13,16", minute=0, timezone=config.TZ),
     produce_one, slot_stamp),
    ("hourly",   CronTrigger(hour="10-17", minute=0, timezone=config.TZ),
     hourly, slot_stamp),
    ("publish",  IntervalTrigger(minutes=15), publish_due, None),
    ("comments", IntervalTrigger(minutes=10), check_comments, None),
    ("digest",   CronTrigger(hour=18, minute=0, timezone=config.TZ),
     digest, today_stamp),
    ("weekplan", CronTrigger(day_of_week="mon", hour=9, minute=30,
                             timezone=config.TZ), week_plan, today_stamp),
    ("weekreview", CronTrigger(day_of_week="fri", hour=17, minute=30,
                               timezone=config.TZ), week_review, today_stamp),
    ("strategy", CronTrigger(day_of_week="sun", hour=18, minute=30,
                             timezone=config.TZ), weekly_strategy, today_stamp),
    ("sweep",    IntervalTrigger(hours=1), sweep_expired, None),
    ("silence",  IntervalTrigger(hours=2), alert_if_silent, None),
]


def build() -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=config.TZ)
    for name, trigger, fn, stamp in JOBS:
        sched.add_job(guarded(name, fn, once_per=stamp), trigger,
                      id=name, replace_existing=True,
                      misfire_grace_time=600, coalesce=True)
    return sched


def heartbeat_age_seconds() -> float | None:
    last = db.get_setting(HEARTBEAT)
    if not last:
        return None
    return (datetime.now(timezone.utc)
            - datetime.fromisoformat(last)).total_seconds()
