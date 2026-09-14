"""The whole team, once, in order. This is the recording.

    python -m scripts.run_chain
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app import config, db  # noqa: E402
from app.agents import angela, dwight, jim, kelly, michael, pam  # noqa: E402

W = 9


def banner(name: str) -> None:
    role = config.AGENT_ROLES[name]
    print(f"\n\033[95m{name.upper():<{W}}\033[0m {role}")


def line(msg: str, ok: bool = True) -> None:
    mark = "\033[92m ok \033[0m" if ok else "\033[93m -- \033[0m"
    print(f"{'':<{W}}{mark} {msg}")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    db.init_db()

    print(f"\n\033[1mVoltade agent office\033[0m   "
          f"{db.local(db.now()):%a %d %b %Y, %H:%M} Singapore")
    print(f"{'':<{W}}kill switch: {'ON' if db.killed() else 'off'}   "
          f"model: {config.MODEL}")

    start = time.time()

    banner("jim")
    r = jim.research()
    findings = db.unused_notes("finding", limit=10)
    line(f"{len(findings)} findings saved")
    for f in findings:
        line(f"  {f['title'][:70]}")

    banner("michael")
    r = michael.plan()
    briefs = db.unused_notes("brief", limit=10)
    line(f"{len(briefs)} briefs commissioned")
    for b in briefs:
        line(f"  {b['title'][:70]}")

    banner("pam")
    if not briefs:
        line("nothing commissioned, nothing written", ok=False)
    for b in briefs:
        pam.write(b["body"])
        db.mark_used(b["id"])
        line(f"wrote for: {b['title'][:60]}")

    banner("dwight")
    results = dwight.post_all()
    if not results:
        line("nothing approved is due", ok=False)
    for res in results:
        if "skipped" in res:
            line(f"{res['post_id']} held back: {res['skipped']}", ok=False)
        else:
            line(f"{res['post_id']} {res['result']}")

    banner("kelly")
    s = kelly.check()
    line(s["blocked_by"] or f"watching {s['connected']}", ok=s["ready"])

    banner("angela")
    s = angela.check()
    line(s["blocked_by"] or f"reading {s['connected']}", ok=s["ready"])
    line(f"our own numbers: {angela.house_numbers()}")

    pending = db.list_posts(status="pending", limit=100)
    print(f"\n\033[1m{len(pending)} drafts waiting for you.\033[0m  "
          f"chain took {time.time() - start:.0f}s")
    print(f"{'':<{W}}review at the cockpit, or approve from Telegram\n")


if __name__ == "__main__":
    main()
