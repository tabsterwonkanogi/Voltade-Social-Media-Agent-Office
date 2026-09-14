"""Step 07 proof: Pam writes a real post and it lands in the store.

    python -m scripts.run_pam "a brief"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app import db  # noqa: E402
from app.agents import pam  # noqa: E402

DEFAULT_BRIEF = (
    "The owner of a 12 person renovation firm is losing quotes because "
    "enquiries come in on WhatsApp at night and nobody answers until morning. "
    "Write the post for LinkedIn and Instagram."
)


def main() -> None:
    db.init_db()
    brief = " ".join(sys.argv[1:]) or DEFAULT_BRIEF
    print(f"brief: {brief}\n")

    result = pam.write(brief)
    print(f"pam finished. {result.input_tokens} in / {result.output_tokens} out\n")

    drafts = db.list_posts(status="pending", limit=1)
    if not drafts:
        print("no draft saved. pam's last words:\n")
        print(result.text)
        return

    d = drafts[0]
    print(f"{d['id']}  pillar={d['pillar']}  platforms={d['platforms']}")
    print("-" * 60)
    print(d["body"])
    print("-" * 60)
    print(f"expires {db.local(d['expires_at']):%a %d %b %H:%M}")


if __name__ == "__main__":
    main()
