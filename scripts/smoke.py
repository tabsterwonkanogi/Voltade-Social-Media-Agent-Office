"""Step 05 proof: a draft goes in, comes back out, and the audit trail is there.

    python -m scripts.smoke
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app import db  # noqa: E402


def main() -> None:
    db.init_db()
    print("schema ready\n")

    post_id = db.create_draft(
        "Most owners do not need an AI strategy.\n\n"
        "They need the WhatsApp answered at 11pm.",
        agent="pam",
        pillar="customer_problem",
        platforms=["linkedin", "instagram"],
    )
    print(f"created  {post_id}")

    post = db.get_post(post_id)
    print(f"status   {post['status']}")
    print(f"pillar   {post['pillar']}")
    print(f"expires  {db.local(post['expires_at']):%a %d %b, %H:%M} Singapore")
    print(f"body     {post['body'].splitlines()[0]}")

    db.approve(post_id, actor="beatrice", surface="web")
    print(f"\napproved -> {db.get_post(post_id)['status']}")

    print("\naudit trail")
    for row in reversed(db.recent_audit(10)):
        when = f"{db.local(row['at']):%H:%M:%S}"
        print(f"  {when}  {row['actor']:<9} {row['action']:<22} "
              f"{row['surface']:<7} {row['target'] or ''}")

    print(f"\nexpired this run: {db.expire_stale()}")


if __name__ == "__main__":
    main()
