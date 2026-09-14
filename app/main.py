"""One process: the clock and, from step 12, the cockpit.

One process and one replica, deliberately. Two replicas means two schedulers
and every post goes out twice.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

load_dotenv()

from . import config, db, scheduler  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-12s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("app")

sched = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sched
    db.init_db()
    sched = scheduler.build()
    sched.start()
    log.info("clock started, %s jobs", len(sched.get_jobs()))
    for job in sorted(sched.get_jobs(), key=lambda j: j.id):
        log.info("  %-9s next %s", job.id,
                 job.next_run_time.strftime("%a %d %b %H:%M"))
    yield
    sched.shutdown(wait=False)


app = FastAPI(title="Voltade agent office", lifespan=lifespan)


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


@app.get("/")
def root():
    return {"service": "Voltade agent office",
            "agents": config.AGENTS,
            "cockpit": "step 12"}
