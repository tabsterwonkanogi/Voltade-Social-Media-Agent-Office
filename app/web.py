"""The cockpit.

Routes are thin on purpose. Every route resolves who is asking, calls a
function in the store layer, and redraws. None of them contain the logic for
what approving means, which is why bolting Telegram on later is a couple of
hours rather than a rewrite.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import auth, brakes, config, db
from .agents import angela, kelly

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def render(request: Request, page: str, tab: str, **ctx) -> HTMLResponse:
    user = auth.current_user(request)
    return templates.TemplateResponse(request, page, {
        "user": user,
        "tab": tab,
        "killed": db.killed(),
        "pending_count": len(db.list_posts(status="pending", limit=200)),
        "flash": request.session.pop("flash", None),
        **ctx,
    })


def when(ts: str | None, fmt: str = "%a %d %b %H:%M") -> str:
    return db.local(ts).strftime(fmt) if ts else ""


PREVIEW_PARAS = 3


def _split(body: str) -> dict:
    """Show the opening, hide the rest behind a tap.

    A four hundred word draft pushes Approve off the bottom of a phone, and a
    review budget of fifteen minutes a day does not survive that much
    scrolling. The hook is what you judge anyway.
    """
    gap = "\n\n"
    paras = [p for p in body.split(gap) if p.strip()]
    if len(paras) <= PREVIEW_PARAS:
        return {"preview": body, "rest": "", "words": len(body.split())}
    return {
        "preview": gap.join(paras[:PREVIEW_PARAS]),
        "rest": gap.join(paras[PREVIEW_PARAS:]),
        "words": len(body.split()),
    }


# ---------------------------------------------------------------- sign in

@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return render(request, "login.html", "login", error=None)


@router.post("/login")
def login(request: Request, name: str = Form(...), password: str = Form(...)):
    user = auth.authenticate(name.strip(), password)
    if not user:
        db.audit("login.failed", actor=name.strip(), surface="web")
        return render(request, "login.html", "login",
                      error="That name and password do not match.")
    request.session["user_id"] = user["id"]
    db.audit("login", actor=user["name"], surface="web")
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---------------------------------------------------------------- queue

@router.get("/", response_class=HTMLResponse)
def queue(request: Request):
    if not auth.current_user(request):
        return RedirectResponse("/login", status_code=303)
    drafts = db.list_posts(status="pending", limit=50)
    for d in drafts:
        d["expires_local"] = when(d["expires_at"], "%a %H:%M")
        d.update(_split(d["body"]))
    return render(request, "queue.html", "queue", drafts=drafts)


@router.post("/post/{post_id}/approve")
def approve(request: Request, post_id: str):
    user = auth.require(request, auth.CAN_APPROVE)
    db.approve(post_id, actor=user["name"], surface="web")
    request.session["flash"] = "Approved. Dwight takes it from here."
    return RedirectResponse("/", status_code=303)


@router.post("/post/{post_id}/reject")
def reject(request: Request, post_id: str):
    user = auth.require(request, auth.CAN_APPROVE)
    db.reject(post_id, actor=user["name"], surface="web")
    request.session["flash"] = "Rejected."
    return RedirectResponse("/", status_code=303)


@router.get("/post/{post_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, post_id: str):
    auth.require(request, auth.CAN_APPROVE)
    d = db.get_post(post_id)
    if d is None:
        return RedirectResponse("/", status_code=303)
    d["sched_input"] = (db.local(d["scheduled_for"]).strftime("%Y-%m-%dT%H:%M")
                        if d["scheduled_for"] else "")
    return render(request, "edit.html", "queue", d=d)


@router.post("/post/{post_id}/edit")
def edit(request: Request, post_id: str, body: str = Form(...),
         action: str = Form("save"), scheduled_for: str = Form("")):
    user = auth.require(request, auth.CAN_APPROVE)
    db.edit_body(post_id, body.strip(), actor=user["name"], surface="web")
    if scheduled_for:
        iso = datetime.fromisoformat(scheduled_for).replace(
            tzinfo=config.TZ).astimezone().isoformat()
        db.reschedule(post_id, iso, actor=user["name"], surface="web")
    if action == "save_approve":
        db.approve(post_id, actor=user["name"], surface="web")
        request.session["flash"] = "Edited and approved."
    else:
        request.session["flash"] = "Saved."
    return RedirectResponse("/", status_code=303)


# ---------------------------------------------------------------- calendar

@router.get("/calendar", response_class=HTMLResponse)
def calendar(request: Request):
    auth.require(request)
    posts = db.list_posts(status="approved", limit=50) + \
        db.list_posts(status="scheduled", limit=50)
    rows = []
    for p in posts:
        rows.append({
            "first_line": p["body"].splitlines()[0][:60],
            "platforms": p["platforms"],
            "when": when(p["scheduled_for"]) or "next slot",
        })
    return render(request, "calendar.html", "calendar", posts=rows)


# ---------------------------------------------------------------- agents

@router.get("/agents", response_class=HTMLResponse)
def agents(request: Request):
    user = auth.require(request)
    blocked = {"kelly": kelly.status(), "angela": angela.status()}
    last = {}
    for r in db.recent_runs(200):
        last.setdefault(r["agent"], r)

    rows = []
    for name in config.AGENTS:
        state = blocked.get(name, {"ready": True, "blocked_by": None})
        r = last.get(name)
        rows.append({
            "name": name,
            "role": config.AGENT_ROLES[name],
            "autonomy": db.autonomy(name),
            "ready": state["ready"],
            "blocked_by": state["blocked_by"],
            "last_run": (f"last ran {when(r['started_at'])}, {r['status']}"
                         if r else "has not run yet"),
        })

    runs = [{"when": when(r["started_at"], "%d %b %H:%M"), "agent": r["agent"],
             "status": r["status"], "error": r["error"] or ""}
            for r in db.recent_runs(25)]

    return render(request, "agents.html", "agents", agents=rows, runs=runs,
                  can_configure=user["role"] in auth.CAN_CONFIGURE)


@router.post("/agents/{name}/autonomy")
def set_autonomy(request: Request, name: str, level: str = Form(...)):
    user = auth.require(request, auth.CAN_CONFIGURE)
    brakes.set_autonomy(name, level, actor=user["name"], surface="web")
    request.session["flash"] = (
        f"{name.capitalize()} now acts on her own." if level == "auto"
        else f"{name.capitalize()} will ask you first.")
    return RedirectResponse("/agents", status_code=303)


@router.post("/agents/run")
def run_now(request: Request, tasks: BackgroundTasks):
    """Kick the whole chain by hand, without waiting for the clock.

    Runs in the background because the chain takes minutes and a browser will
    not wait. The kill switch still applies, because every agent goes through
    the runner and the runner checks it.
    """
    user = auth.require(request, auth.CAN_CONFIGURE)
    db.audit("chain.run_requested", actor=user["name"], surface="web")
    tasks.add_task(_run_chain)
    request.session["flash"] = ("The team is working. Refresh in a few "
                                "minutes and the queue will have something.")
    return RedirectResponse("/agents", status_code=303)


def _run_chain() -> None:
    from .agents import jim, michael, pam
    from .scheduler import produce_one
    try:
        jim.research()
        michael.plan()
        for _ in range(config.POSTS_PER_DAY):
            if not db.unused_notes("brief", limit=1):
                break
            produce_one()
    except Exception as exc:
        db.audit("chain.failed", actor="system", surface="system",
                 detail=f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------- comments

@router.get("/comments", response_class=HTMLResponse)
def comments(request: Request):
    auth.require(request)
    return render(request, "comments.html", "comments",
                  ready=kelly.status()["ready"],
                  drafted=db.list_comments(status="drafted", limit=30),
                  blocked=db.list_comments(status="blocked", limit=30))


@router.post("/comment/{comment_id}/send")
def send_comment(request: Request, comment_id: str):
    user = auth.require(request, auth.CAN_APPROVE)
    db.mark_replied(comment_id, actor=user["name"], surface="web")
    request.session["flash"] = "Reply approved."
    return RedirectResponse("/comments", status_code=303)


@router.post("/comment/{comment_id}/skip")
def skip_comment(request: Request, comment_id: str):
    user = auth.require(request, auth.CAN_APPROVE)
    db.block_comment(comment_id, f"skipped by {user['name']}")
    return RedirectResponse("/comments", status_code=303)


# ---------------------------------------------------------------- numbers

@router.get("/numbers", response_class=HTMLResponse)
def numbers(request: Request):
    auth.require(request)
    return render(request, "numbers.html", "numbers",
                  ready=angela.status()["ready"],
                  house=angela.house_numbers())


# ---------------------------------------------------------------- settings

@router.get("/settings", response_class=HTMLResponse)
def settings(request: Request):
    auth.require(request, auth.CAN_CONFIGURE)
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    users = [{"name": u["name"], "role": u["role"],
              "since": when(u["created_at"], "%d %b")} for u in rows]
    audit = [{"when": when(a["at"], "%d %b %H:%M"), "actor": a["actor"],
              "action": a["action"], "surface": a["surface"]}
             for a in db.recent_audit(40)]
    return render(request, "settings.html", "settings", users=users,
                  audit=audit, rate=config.KELLY_MAX_REPLIES_PER_HOUR,
                  no_go=config.NO_GO_TOPICS,
                  persona=db.get_setting("persona.michael", "on") == "on",
                  volume=(config.POSTS_PER_DAY_MIN, config.POSTS_PER_DAY_MAX))


@router.post("/settings/persona")
def persona(request: Request, on: str = Form(...)):
    user = auth.require(request, auth.CAN_CONFIGURE)
    db.set_setting("persona.michael", "on" if on == "1" else "off",
                   actor=user["name"], surface="web")
    request.session["flash"] = ("Michael is doing the bit again."
                                if on == "1" else
                                "Michael will just tell you what happened.")
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/kill")
def kill(request: Request, on: str = Form(...)):
    user = auth.require(request, auth.CAN_CONFIGURE)
    brakes.kill_switch(on == "1", actor=user["name"], surface="web")
    request.session["flash"] = ("Everything is stopped." if on == "1"
                                else "Released. The agents can act again.")
    return RedirectResponse("/settings", status_code=303)
