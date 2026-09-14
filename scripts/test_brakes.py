"""Step 10 proof, and the three takes for video 5.

    python -m scripts.test_brakes

Take 1  the autonomy dial: ask holds the work, auto lets it go
Take 2  the kill switch: everything stops, and says so
Take 3  the no-go list: a reply refused, with the reason kept on the record

The comments used here are injected locally and labelled as test comments.
Nothing is read from a platform, because no platform has granted that yet,
and nothing is sent anywhere.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app import brakes, config, db  # noqa: E402
from app.agents import kelly  # noqa: E402

R = "\033[91m"
G = "\033[92m"
Y = "\033[93m"
B = "\033[1m"
X = "\033[0m"


def rule(title: str) -> None:
    print(f"\n{B}{title}{X}\n{'-' * 58}")


def main() -> None:
    db.init_db()
    brakes.kill_switch(False, actor="beatrice", surface="web")
    brakes.set_autonomy("pam", "ask", actor="beatrice", surface="web")

    # ---------------------------------------------------- take 1
    rule("TAKE 1   the autonomy dial")

    print(f"pam is on {B}ask{X}")
    pid = db.create_draft("Test draft while Pam is on ask.", agent="pam",
                          pillar="build_in_public", platforms=["linkedin"])
    print(f"   her work lands as {Y}{db.get_post(pid)['status']}{X}, "
          f"waiting for you\n")

    brakes.set_autonomy("pam", "auto", actor="beatrice", surface="web")
    print(f"you flip her to {B}auto{X} from the cockpit")
    pid = db.create_draft("Test draft while Pam is on auto.", agent="pam",
                          pillar="build_in_public", platforms=["linkedin"])
    print(f"   the same work now lands as {G}{db.get_post(pid)['status']}{X}, "
          f"straight into the queue to go out")

    brakes.set_autonomy("pam", "ask", actor="beatrice", surface="web")

    # ---------------------------------------------------- take 2
    rule("TAKE 2   the kill switch")

    print(f"{G}off{X}   ", brakes.can_act("pam").reason or "everything runs")
    brakes.kill_switch(True, actor="beatrice", surface="web")
    print(f"{R}ON{X}    {R}{brakes.can_act('pam').reason}{X}")
    for agent in config.AGENTS:
        v = brakes.can_act(agent)
        print(f"      {agent:<9} {R}stopped{X}: {v.reason}")
    brakes.kill_switch(False, actor="beatrice", surface="web")
    print(f"{G}off{X}    released")

    # ---------------------------------------------------- take 3
    rule("TAKE 3   the no-go list")

    tests = [
        ("safe", "Does this work for a company with 8 staff?"),
        ("politics", "What do you think about the election result?"),
        ("complaint", "Terrible service, I want a refund."),
    ]
    for label, text in tests:
        cid = db.add_comment("instagram", text, author=f"test_{label}")
        result = kelly.handle(db.list_comments(status="new", limit=1)[0]) \
            if False else None
        verdict = brakes.can_act("kelly", text=text)
        if verdict:
            print(f"{G}allowed{X}  {text}")
        else:
            db.block_comment(cid, verdict.reason)
            print(f"{R}blocked{X}  {text}")
            print(f"         reason kept on the record: {verdict.reason}")

    rule("what the cockpit shows")
    s = brakes.state()
    print(f"kill switch        {s['kill_switch']}")
    print(f"autonomy           {s['autonomy']}")
    print(f"kelly rate limit   {s['kelly_rate_limit_per_hour']} replies/hour")
    print(f"blocked comments   {len(db.list_comments(status='blocked'))} "
          f"on file, each with its reason\n")


if __name__ == "__main__":
    main()
