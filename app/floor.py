"""The office floor: what each agent is doing, as data.

The rule this file exists to enforce: the office is a view of the database,
never an animation loop. A figure moves because an audit row says something
happened. When the kill switch is on, nobody moves, because nobody is working.
An office that looks busy while the system is halted would be the same lie as
an invented number on the analytics page.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from . import auth, config, db
from .agents import angela, jim, kelly, michael, pam, prompts, runner

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "app" / "templates"))

# Who hands work to whom. A walk happens when one of these actually occurs.
HANDOFFS = {
    "note.finding": ("jim", "michael", "a finding"),
    "note.brief": ("michael", "pam", "a brief"),
    "post.created": ("pam", "queue", "a draft"),
    "post.published": ("dwight", "out", "a post"),
    "post.failed": ("dwight", "out", "a failure"),
    "comment.drafted": ("kelly", "queue", "a reply"),
    "comment.blocked": ("kelly", "bin", "a refusal"),
    "note.strategy": ("angela", "michael", "the weekly note"),
}

# What an agent is holding while it works, so the figure carries something.
CARRIES = {
    "jim": "notes", "michael": "clipboard", "pam": "pages",
    "dwight": "box", "kelly": "headset", "angela": "chart",
}


def _state(name: str, killed: bool) -> dict:
    """One agent, right now. Every field traceable to a row."""
    blocked = {"kelly": kelly.status, "angela": angela.status}
    status = blocked[name]() if name in blocked else {"ready": True,
                                                      "blocked_by": None}
    run = db.open_run(name)
    today = db.runs_today(name)

    if not status["ready"]:
        state = "blocked"
    elif killed:
        state = "stopped"
    elif run:
        state = "working"
    else:
        state = "idle"

    working_on = None
    if run:
        started = datetime.fromisoformat(run["started_at"])
        seconds = int((datetime.now(timezone.utc) - started).total_seconds())
        working_on = {"since": run["started_at"], "seconds": seconds}

    ok = [r for r in today if r["status"] == "ok"]
    errors = [r for r in today if r["status"] == "error"]

    return {
        "name": name,
        "role": config.AGENT_ROLES[name],
        "state": state,
        "autonomy": db.autonomy(name),
        "blocked_by": status["blocked_by"],
        "carries": CARRIES[name],
        "working_on": working_on,
        "today": {
            "runs": len(today),
            "ok": len(ok),
            "errors": len(errors),
            "last": (ok[0]["summary"] or "")[:180] if ok else None,
            "tokens": sum(r["input_tokens"] + r["output_tokens"] for r in today),
        },
    }


def _walks(killed: bool) -> list[dict]:
    """Handoffs in the last half hour. Nothing invented, nothing smoothed."""
    if killed:
        return []
    out = []
    for row in db.audit_since(30, 60):
        if row["action"] not in HANDOFFS:
            continue
        src, dst, what = HANDOFFS[row["action"]]
        out.append({"id": row["id"], "at": row["at"], "from": src,
                    "to": dst, "what": what, "detail": row["detail"]})
    return list(reversed(out))


@router.get("/api/floor")
def floor_state(request: Request):
    auth.require(request)
    killed = db.killed()
    return JSONResponse({
        "now": db.now(),
        "killed": killed,
        "agents": [_state(a, killed) for a in config.AGENTS],
        "walks": _walks(killed),
        "queue": len(db.list_posts(status="pending", limit=200)),
        "approved": len(db.list_posts(status="approved", limit=200)),
    })


@router.get("/floor", response_class=HTMLResponse)
def floor_page(request: Request):
    user = auth.current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "floor.html", {
        "user": user,
        "tab": "floor",
        "killed": db.killed(),
        "pending_count": len(db.list_posts(status="pending", limit=200)),
        "flash": request.session.pop("flash", None),
        "agents": config.AGENTS,
        "roles": config.AGENT_ROLES,
    })


# ---------------------------------------------------------------- talking

TOOLS = {
    "jim": lambda: [jim.save_finding,
                    {"type": "web_search_20260209", "name": "web_search",
                     "max_uses": 6}],
    "michael": lambda: [michael.check_queue, michael.save_brief],
    "pam": lambda: [pam.save_draft],
    "kelly": lambda: [kelly.save_reply],
    "dwight": lambda: [],
    "angela": lambda: [],
}


@router.get("/api/agent/{name}/chat")
def read_chat(request: Request, name: str):
    auth.require(request)
    if name not in config.AGENTS:
        return JSONResponse({"error": "no such agent"}, status_code=404)
    return JSONResponse({
        "agent": name,
        "messages": db.conversation(name, 40),
        "busy": db.open_run(name) is not None,
        "killed": db.killed(),
    })


@router.post("/api/agent/{name}/chat")
def send_chat(request: Request, name: str, tasks: BackgroundTasks,
              message: str = Form(...)):
    """Give one agent a direct instruction.

    This runs the agent for real, with its own tools, so it can act. It
    therefore goes through the same runner as a scheduled job and is stopped
    by the same kill switch. A back door that ignored the brakes would not be
    a chat, it would be a hole.
    """
    user = auth.require(request, auth.CAN_APPROVE)
    if name not in config.AGENTS:
        return JSONResponse({"error": "no such agent"}, status_code=404)

    if db.killed():
        return JSONResponse(
            {"error": "Everyone is stopped. Release the kill switch in "
                      "Settings before giving orders."}, status_code=409)
    if db.open_run(name):
        return JSONResponse(
            {"error": f"{name.capitalize()} is in the middle of something. "
                      f"Wait for that to finish."}, status_code=409)

    db.say(name, "user", message.strip(), actor=user["name"])
    db.audit("agent.instructed", actor=user["name"], surface="web",
             target=name, detail=message.strip()[:300])
    tasks.add_task(_talk, name, message.strip())
    return JSONResponse({"ok": True})


def _talk(name: str, message: str) -> None:
    if name in ("dwight", "angela"):
        db.say(name, "agent",
               "I have no judgement to apply. Dwight only sends what was "
               "approved; Angela has no numbers yet."
               if name == "dwight" else
               "I am not connected to any platform metrics yet, so I have "
               "nothing to read. Ask me again when review lands.")
        return
    try:
        result = runner.run(name, message, tools=TOOLS[name](),
                            system=prompts.load(name))
        db.say(name, "agent", result.text or "Done.", run_id=result.run_id)
    except runner.Halted as exc:
        db.say(name, "agent", f"Stopped: {exc}")
    except Exception as exc:
        db.say(name, "agent", f"That went wrong: {type(exc).__name__}: {exc}")
