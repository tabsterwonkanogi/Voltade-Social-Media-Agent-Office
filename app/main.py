"""One process: the clock and, from step 12, the cockpit.

One process and one replica, deliberately. Two replicas means two schedulers
and every post goes out twice.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from . import auth, config, db, scheduler, web  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-12s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("app")

sched = None


def bootstrap_owner() -> None:
    """First run on a fresh volume has no accounts, so nobody can sign in.

    Creates the owner from ADMIN_NAME and ADMIN_PASSWORD once, and only when
    the users table is empty. Never overwrites an existing account, so leaving
    the variables set is harmless.
    """
    if auth.any_users():
        return
    name = os.environ.get("ADMIN_NAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not name or not password:
        log.warning("no accounts and no ADMIN_NAME/ADMIN_PASSWORD set, "
                    "nobody can sign in")
        return
    auth.create_user(name, "owner", password)
    log.info("created the first owner account: %s", name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sched
    db.init_db()
    bootstrap_owner()
    sched = scheduler.build()
    sched.start()
    log.info("clock started, %s jobs", len(sched.get_jobs()))
    for job in sorted(sched.get_jobs(), key=lambda j: j.id):
        log.info("  %-9s next %s", job.id,
                 job.next_run_time.strftime("%a %d %b %H:%M"))
    yield
    sched.shutdown(wait=False)


app = FastAPI(title="Voltade agent office", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-only-change-me"),
    same_site="lax",
    max_age=60 * 60 * 24 * 30,
)
app.mount("/static", StaticFiles(
    directory=str(Path(__file__).parent / "static")), name="static")


@app.get("/health")
def health():
    """Railway pings this. Unhealthy if the clock has stopped ticking.

    A dead scheduler in a live process is the failure that looks like success,
    so this is the one endpoint that must not be generous.
    """
    age = scheduler.heartbeat_age_seconds()
    stalled = age is not None and age > 1800
    body = {
        "ok": not stalled,
        "heartbeat_age_seconds": None if age is None else round(age),
        "kill_switch": "on" if db.killed() else "off",
        "jobs": len(sched.get_jobs()) if sched else 0,
        "pending_drafts": len(db.list_posts(status="pending", limit=200)),
    }
    return JSONResponse(body, status_code=503 if stalled else 200)


app.include_router(web.router)
