"""The store.

Every draft, decision, comment and scheduled post lives here. Agents write here.
Surfaces write here. Neither ever calls the other.

Two rules enforced in this file rather than left to callers:
  1. Every change to a post or a comment also writes an audit row.
  2. Every draft gets an expiry 72 hours out, so the queue cannot spiral.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from . import config

# ---------------------------------------------------------------- primitives


def now() -> str:
    """UTC, ISO 8601, seconds precision. Stored this way everywhere."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def local(ts: str) -> datetime:
    """An ISO timestamp from the store, in Singapore time, for display."""
    return datetime.fromisoformat(ts).astimezone(config.TZ)


@contextmanager
def connect():
    path = Path(config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------- schema

POST_STATUSES = (
    "draft", "pending", "approved", "rejected",
    "scheduled", "published", "failed", "expired",
)

COMMENT_STATUSES = ("new", "drafted", "replied", "skipped", "blocked")

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id               TEXT PRIMARY KEY,
    created_at       TEXT NOT NULL,
    created_by_agent TEXT,
    pillar           TEXT,
    body             TEXT NOT NULL,
    media_paths      TEXT NOT NULL DEFAULT '[]',
    platforms        TEXT NOT NULL DEFAULT '[]',
    status           TEXT NOT NULL,
    scheduled_for    TEXT,
    published_at     TEXT,
    blotato_ids      TEXT NOT NULL DEFAULT '{}',
    result           TEXT NOT NULL DEFAULT '{}',
    expires_at       TEXT,
    confidential     INTEGER NOT NULL DEFAULT 0,
    notes            TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_sched  ON posts(scheduled_for);

CREATE TABLE IF NOT EXISTS comments (
    id             TEXT PRIMARY KEY,
    platform       TEXT NOT NULL,
    post_ref       TEXT,
    external_id    TEXT,
    author         TEXT,
    text           TEXT NOT NULL,
    received_at    TEXT NOT NULL,
    status         TEXT NOT NULL,
    reply_text     TEXT,
    replied_at     TEXT,
    blocked_reason TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_comments_ext
    ON comments(platform, external_id) WHERE external_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    agent         TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    status        TEXT NOT NULL,
    summary       TEXT,
    error         TEXT,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_runs_agent ON runs(agent, started_at);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at      TEXT NOT NULL,
    actor   TEXT NOT NULL,
    action  TEXT NOT NULL,
    target  TEXT,
    detail  TEXT,
    surface TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit(at);

CREATE TABLE IF NOT EXISTS notes (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    agent      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    source     TEXT,
    used       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notes_kind ON notes(kind, used, created_at);

CREATE TABLE IF NOT EXISTS chats (
    id      TEXT PRIMARY KEY,
    agent   TEXT NOT NULL,
    role    TEXT NOT NULL,
    text    TEXT NOT NULL,
    at      TEXT NOT NULL,
    run_id  TEXT,
    actor   TEXT
);
CREATE INDEX IF NOT EXISTS idx_chats_agent ON chats(agent, at);

CREATE TABLE IF NOT EXISTS room (
    id          TEXT PRIMARY KEY,
    at          TEXT NOT NULL,
    agent       TEXT,
    role        TEXT NOT NULL,
    text        TEXT NOT NULL,
    actor       TEXT,
    tg_chat_id  TEXT,
    tg_msg_id   TEXT,
    topic_id    TEXT,
    reply_to    TEXT
);
CREATE INDEX IF NOT EXISTS idx_room_at ON room(at);
CREATE INDEX IF NOT EXISTS idx_room_msg ON room(tg_chat_id, tg_msg_id);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL,
    telegram_id   TEXT,
    password_hash TEXT,
    created_at    TEXT NOT NULL
);
"""


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
    seed_settings()


# ---------------------------------------------------------------- audit

def audit(action: str, *, actor: str, surface: str,
          target: str | None = None, detail: Any = None,
          conn: sqlite3.Connection | None = None) -> None:
    """Record who did what, where from. Never called optionally."""
    row = (now(), actor, action, target,
           detail if isinstance(detail, str) or detail is None else json.dumps(detail),
           surface)
    sql = ("INSERT INTO audit (at, actor, action, target, detail, surface) "
           "VALUES (?,?,?,?,?,?)")
    if conn is not None:
        conn.execute(sql, row)
    else:
        with connect() as c:
            c.execute(sql, row)


def recent_audit(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- settings

def seed_settings() -> None:
    defaults = {
        "kill_switch": "off",
        "persona.michael": "on",
        "posts_per_day": str(config.POSTS_PER_DAY),
        **{f"autonomy.{a}": v for a, v in config.DEFAULT_AUTONOMY.items()},
    }
    with connect() as conn:
        for key, value in defaults.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?,?) "
                "ON CONFLICT(key) DO NOTHING", (key, value))


def get_setting(key: str, default: str | None = None) -> str | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str, *, actor: str, surface: str,
                record: bool = True) -> None:
    """Change a setting, and by default record who changed it.

    Pass record=False for machine bookkeeping the clock writes on every tick,
    a heartbeat or a last-run marker. Those are not decisions, and auditing
    them buries the decisions: within a day the trail was a hundred percent
    heartbeat and you could no longer see who stopped the system.
    """
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
        if record:
            audit("setting.changed", actor=actor, surface=surface,
                  target=key, detail=value, conn=conn)


def killed() -> bool:
    return get_setting("kill_switch", "off") == "on"


def autonomy(agent: str) -> str:
    return get_setting(f"autonomy.{agent}", "ask") or "ask"


# ---------------------------------------------------------------- posts

def create_draft(body: str, *, agent: str, pillar: str | None = None,
                 platforms: Iterable[str] | None = None,
                 media_paths: Iterable[str] | None = None,
                 confidential: bool = False,
                 scheduled_for: str | None = None) -> str:
    """A new draft. Always expires, always audited.

    Lands as 'pending' when the agent is on ask, 'approved' when it is on auto.
    """
    post_id = new_id("post")
    created = now()
    expires = (datetime.fromisoformat(created)
               + timedelta(hours=config.DRAFT_EXPIRY_HOURS)).isoformat()

    status = "pending"
    if autonomy(agent) == "auto" and not confidential:
        status = "approved"

    with connect() as conn:
        conn.execute(
            "INSERT INTO posts (id, created_at, created_by_agent, pillar, body, "
            "media_paths, platforms, status, scheduled_for, expires_at, confidential) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (post_id, created, agent, pillar, body,
             json.dumps(list(media_paths or [])),
             json.dumps(list(platforms or [])),
             status, scheduled_for, expires, int(confidential)))
        audit("post.created", actor=agent, surface="agent", target=post_id,
              detail={"pillar": pillar, "status": status,
                      "confidential": confidential}, conn=conn)
    return post_id


def get_post(post_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return _hydrate(row) if row else None


def list_posts(status: str | None = None, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM posts"
    args: tuple = ()
    if status:
        sql += " WHERE status = ?"
        args = (status,)
    sql += " ORDER BY created_at DESC LIMIT ?"
    with connect() as conn:
        rows = conn.execute(sql, (*args, limit)).fetchall()
    return [_hydrate(r) for r in rows]


def _hydrate(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("media_paths", "platforms", "blotato_ids", "result"):
        d[key] = json.loads(d[key] or ("[]" if key.endswith("s") and key != "blotato_ids" else "{}"))
    d["confidential"] = bool(d["confidential"])
    return d


def set_status(post_id: str, status: str, *, actor: str, surface: str,
               detail: Any = None) -> None:
    """The single way a post changes state.

    Both the website and, later, Telegram call this. Nothing calls UPDATE on
    posts.status directly, which is what keeps the two surfaces honest.
    """
    if status not in POST_STATUSES:
        raise ValueError(f"unknown status {status!r}")
    with connect() as conn:
        cur = conn.execute(
            "UPDATE posts SET status = ? WHERE id = ?", (status, post_id))
        if cur.rowcount == 0:
            raise KeyError(post_id)
        audit(f"post.{status}", actor=actor, surface=surface,
              target=post_id, detail=detail, conn=conn)


def approve(post_id: str, *, actor: str, surface: str) -> None:
    """Called by the web cockpit today, by the Telegram handler later.

    Keeping this here rather than in a route is the reason adding Telegram is
    a small job instead of a rewrite.
    """
    post = get_post(post_id)
    if post is None:
        raise KeyError(post_id)
    if post["confidential"]:
        audit("post.confidential_release", actor=actor, surface=surface,
              target=post_id, detail="approved despite confidential flag")
    set_status(post_id, "approved", actor=actor, surface=surface)


def reject(post_id: str, *, actor: str, surface: str, reason: str = "") -> None:
    set_status(post_id, "rejected", actor=actor, surface=surface, detail=reason)


def edit_body(post_id: str, body: str, *, actor: str, surface: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE posts SET body = ? WHERE id = ?", (body, post_id))
        audit("post.edited", actor=actor, surface=surface, target=post_id, conn=conn)


def reschedule(post_id: str, when: str, *, actor: str, surface: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE posts SET scheduled_for = ? WHERE id = ?",
                     (when, post_id))
        audit("post.rescheduled", actor=actor, surface=surface,
              target=post_id, detail=when, conn=conn)


def record_publish(post_id: str, *, blotato_ids: dict, result: dict) -> None:
    """What the platforms actually did, not what Blotato accepted."""
    ok = any(v.get("ok") for v in result.values()) if result else False
    with connect() as conn:
        conn.execute(
            "UPDATE posts SET status = ?, published_at = ?, blotato_ids = ?, "
            "result = ? WHERE id = ?",
            ("published" if ok else "failed", now(),
             json.dumps(blotato_ids), json.dumps(result), post_id))
        audit("post.published" if ok else "post.failed", actor="dwight",
              surface="agent", target=post_id, detail=result, conn=conn)


def expire_stale() -> int:
    """Unreviewed drafts roll over, then die. Run hourly."""
    cutoff = now()
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM posts WHERE status = 'pending' AND expires_at < ?",
            (cutoff,)).fetchall()
        for row in rows:
            conn.execute("UPDATE posts SET status = 'expired' WHERE id = ?",
                         (row["id"],))
            audit("post.expired", actor="system", surface="system",
                  target=row["id"], detail="unreviewed for 72 hours", conn=conn)
    return len(rows)


# ---------------------------------------------------------------- runs

def start_run(agent: str) -> str:
    run_id = new_id("run")
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs (id, agent, started_at, status) VALUES (?,?,?,?)",
            (run_id, agent, now(), "running"))
    return run_id


def end_run(run_id: str, *, status: str, summary: str = "",
            error: str = "", input_tokens: int = 0,
            output_tokens: int = 0) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET ended_at = ?, status = ?, summary = ?, error = ?, "
            "input_tokens = ?, output_tokens = ? WHERE id = ?",
            (now(), status, summary, error, input_tokens, output_tokens, run_id))


def recent_runs(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
            (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- notes
# Research findings, briefs and strategy notes. Agents hand work to each other
# through this table, never by calling one another.

NOTE_KINDS = ("finding", "brief", "strategy")


def add_note(kind: str, title: str, body: str, *, agent: str,
             source: str | None = None) -> str:
    if kind not in NOTE_KINDS:
        raise ValueError(f"unknown note kind {kind!r}")
    note_id = new_id(kind[:4])
    with connect() as conn:
        conn.execute(
            "INSERT INTO notes (id, kind, agent, created_at, title, body, source) "
            "VALUES (?,?,?,?,?,?,?)",
            (note_id, kind, agent, now(), title, body, source))
        audit(f"note.{kind}", actor=agent, surface="agent",
              target=note_id, detail=title, conn=conn)
    return note_id


def unused_notes(kind: str, limit: int = 10) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM notes WHERE kind = ? AND used = 0 "
            "ORDER BY created_at DESC LIMIT ?", (kind, limit)).fetchall()
    return [dict(r) for r in rows]


def mark_used(note_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE notes SET used = 1 WHERE id = ?", (note_id,))


# ---------------------------------------------------------------- comments

def add_comment(platform: str, text: str, *, author: str = "",
                post_ref: str | None = None,
                external_id: str | None = None) -> str:
    comment_id = new_id("cmt")
    with connect() as conn:
        conn.execute(
            "INSERT INTO comments (id, platform, post_ref, external_id, author, "
            "text, received_at, status) VALUES (?,?,?,?,?,?,?,'new')",
            (comment_id, platform, post_ref, external_id, author, text, now()))
        audit("comment.received", actor="system", surface="agent",
              target=comment_id, detail=f"{platform} from {author}", conn=conn)
    return comment_id


def list_comments(status: str | None = None, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM comments"
    args: tuple = ()
    if status:
        sql += " WHERE status = ?"
        args = (status,)
    sql += " ORDER BY received_at DESC LIMIT ?"
    with connect() as conn:
        rows = conn.execute(sql, (*args, limit)).fetchall()
    return [dict(r) for r in rows]


def block_comment(comment_id: str, reason: str) -> None:
    """A refused comment is kept with its reason, never silently dropped.

    You have to be able to show the block, not just assert that one happened.
    """
    with connect() as conn:
        conn.execute(
            "UPDATE comments SET status = 'blocked', blocked_reason = ? "
            "WHERE id = ?", (reason, comment_id))
        audit("comment.blocked", actor="kelly", surface="agent",
              target=comment_id, detail=reason, conn=conn)


def draft_reply(comment_id: str, reply: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE comments SET status = 'drafted', reply_text = ? WHERE id = ?",
            (reply, comment_id))
        audit("comment.drafted", actor="kelly", surface="agent",
              target=comment_id, conn=conn)


def mark_replied(comment_id: str, *, actor: str, surface: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE comments SET status = 'replied', replied_at = ? WHERE id = ?",
            (now(), comment_id))
        audit("comment.replied", actor=actor, surface=surface,
              target=comment_id, conn=conn)


# ---------------------------------------------------------------- chat

def say(agent: str, role: str, text: str, *, actor: str | None = None,
        run_id: str | None = None) -> str:
    """One line of conversation with an agent. role is 'user' or 'agent'."""
    msg_id = new_id("msg")
    with connect() as conn:
        conn.execute(
            "INSERT INTO chats (id, agent, role, text, at, run_id, actor) "
            "VALUES (?,?,?,?,?,?,?)",
            (msg_id, agent, role, text, now(), run_id, actor))
    return msg_id


def conversation(agent: str, limit: int = 40) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM chats WHERE agent = ? ORDER BY at DESC, rowid DESC "
            "LIMIT ?", (agent, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def audit_since(minutes: int = 30, limit: int = 60) -> list[dict]:
    """Recent decisions and handoffs, for the floor to animate."""
    cutoff = (datetime.now(timezone.utc)
              - timedelta(minutes=minutes)).replace(microsecond=0).isoformat()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit WHERE at >= ? ORDER BY id DESC LIMIT ?",
            (cutoff, limit)).fetchall()
    return [dict(r) for r in rows]


def day_start() -> str:
    """Midnight in Singapore, expressed in UTC, as stored timestamps are.

    Comparing a UTC timestamp against a local date string looks fine all
    afternoon and breaks every night: between midnight and 8am, everything
    that happened today carries yesterday's UTC date, so every counter reads
    zero while the agents are visibly working.
    """
    here = datetime.now(config.TZ).replace(hour=0, minute=0, second=0,
                                           microsecond=0)
    return here.astimezone(timezone.utc).isoformat()


def runs_today(agent: str) -> list[dict]:
    today = day_start()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE agent = ? AND started_at >= ? "
            "ORDER BY started_at DESC", (agent, today)).fetchall()
    return [dict(r) for r in rows]


def open_run(agent: str) -> dict | None:
    """A run that started and has not ended. This is 'working right now'."""
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE agent = ? AND ended_at IS NULL "
            "ORDER BY started_at DESC LIMIT 1", (agent,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------- the room
# One shared transcript of the team chat. Telegram never delivers one bot's
# message to another bot, so agents cannot learn what happened by listening.
# They read it here instead: we sent all of it, so we already know.

def room_add(role: str, text: str, *, agent: str | None = None,
             actor: str | None = None, tg_chat_id: str | None = None,
             tg_msg_id: str | None = None, topic_id: str | None = None,
             reply_to: str | None = None) -> str:
    msg_id = new_id("room")
    with connect() as conn:
        conn.execute(
            "INSERT INTO room (id, at, agent, role, text, actor, tg_chat_id, "
            "tg_msg_id, topic_id, reply_to) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (msg_id, now(), agent, role, text, actor,
             tg_chat_id, tg_msg_id, topic_id, reply_to))
    return msg_id


def room_recent(limit: int = 30) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM room ORDER BY at DESC, rowid DESC LIMIT ?",
            (limit,)).fetchall()
    return [dict(r) for r in reversed(rows)]


def room_by_message(chat_id: str, msg_id: str) -> dict | None:
    """Which agent said the thing she just replied to."""
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM room WHERE tg_chat_id = ? AND tg_msg_id = ?",
            (str(chat_id), str(msg_id))).fetchone()
    return dict(row) if row else None
