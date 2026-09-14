"""Michael. Decides what gets made.

He reads Jim's findings and the state of the queue, then writes briefs for Pam.
He never writes copy himself. That separation is what keeps the volume honest:
the agent deciding how much to make is not the agent that enjoys making it.
"""

from __future__ import annotations

from anthropic import beta_tool

from .. import config, db
from . import prompts, runner




@beta_tool
def check_queue() -> str:
    """How much is already waiting for review, and what was made recently."""
    pending = db.list_posts(status="pending", limit=50)
    findings = db.unused_notes("finding", limit=5)
    lines = [f"pending drafts awaiting review: {len(pending)}"]
    for p in pending[:5]:
        lines.append(f"  {p['pillar']}: {p['body'].splitlines()[0][:70]}")
    lines.append(f"unused findings from Jim: {len(findings)}")
    for f in findings:
        lines.append(f"  [{f['id']}] {f['title']}")
        lines.append(f"      {f['body'][:160]}")
    return "\n".join(lines)


@beta_tool
def save_brief(angle: str, pillar: str, platforms: list[str],
               based_on: str = "") -> str:
    """Commission one post from Pam.

    Args:
        angle: The situation and the angle, in plain words. No copy.
        pillar: Which pillar, one of the keys above.
        platforms: Which platforms this suits.
        based_on: Optional finding id this builds on.
    """
    known = {k for k, _ in config.PILLARS}
    if pillar not in known:
        return f"Rejected: pillar must be one of {sorted(known)}."
    body = f"{angle}\n\nPlatforms: {', '.join(platforms)}"
    note_id = db.add_note("brief", angle[:120], body, agent="michael",
                          source=based_on or None)
    if based_on:
        db.mark_used(based_on)
    return f"Saved {note_id}."


def plan() -> runner.Result:
    return runner.run(
        "michael",
        "Plan today's posts. Check the queue first, then commission what is "
        "actually needed and no more.",
        tools=[check_queue, save_brief],
        system=prompts.load("michael"),
    )
