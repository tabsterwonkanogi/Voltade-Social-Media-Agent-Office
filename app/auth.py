"""Accounts and roles, so someone else can cover approvals when she is away.

Three roles:
    owner   change settings, flip the kill switch, manage people
    editor  approve, reject, edit, reschedule
    viewer  look only

Every action a person takes writes an audit row naming them and the surface
they used. That is the whole point of having accounts rather than one shared
password.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request

from . import db


def hash_password(password: str) -> str:
    """scrypt from the standard library.

    passlib plus current bcrypt raises on its own probe string, and a login
    that breaks on a dependency bump is not worth the dependency.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                                n=2**14, r=8, p=1)
    except Exception:
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)

ROLES = ("owner", "editor", "viewer")
CAN_APPROVE = ("owner", "editor")
CAN_CONFIGURE = ("owner",)


def create_user(name: str, role: str, password: str | None = None,
                telegram_id: str | None = None) -> tuple[str, str]:
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    password = password or secrets.token_urlsafe(12)
    user_id = db.new_id("usr")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO users (id, name, role, telegram_id, password_hash, "
            "created_at) VALUES (?,?,?,?,?,?)",
            (user_id, name, role, telegram_id, hash_password(password), db.now()))
        db.audit("user.created", actor="system", surface="system",
                 target=user_id, detail=f"{name} as {role}", conn=conn)
    return user_id, password


def set_password(name: str, password: str) -> bool:
    with db.connect() as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ? WHERE name = ?",
            (hash_password(password), name))
        if cur.rowcount:
            db.audit("user.password_changed", actor=name, surface="system",
                     target=name, conn=conn)
        return bool(cur.rowcount)


def authenticate(name: str, password: str) -> dict | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE name = ?", (name,)).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return dict(row)
    return None


def get_user(user_id: str) -> dict | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def current_user(request: Request) -> dict | None:
    user_id = request.session.get("user_id")
    return get_user(user_id) if user_id else None


def require(request: Request, roles: tuple[str, ...] = ROLES) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="sign in first")
    if user["role"] not in roles:
        raise HTTPException(
            status_code=403,
            detail=f"your account is {user['role']} and cannot do that")
    return user


def any_users() -> bool:
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] > 0
