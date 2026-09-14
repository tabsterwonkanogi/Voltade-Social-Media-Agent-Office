"""Pam. Writes the post.

She is the only agent allowed to produce copy, and the only place the house
voice is enforced in a prompt. Everything she knows about the brand comes from
config, so changing the brand never means editing an agent.
"""

from __future__ import annotations

from anthropic import beta_tool

from .. import config, db
from . import prompts, runner




@beta_tool
def save_draft(body: str, pillar: str, platforms: list[str]) -> str:
    """Save the finished post as a draft for human review.

    Args:
        body: The full post copy, including hashtags. No em dashes.
        pillar: Which content pillar this is, one of the keys given to you.
        platforms: Which platforms this suits, from linkedin, instagram,
            tiktok, facebook, x, youtube.
    """
    if "—" in body or "– " in body:
        return ("Rejected: that contains a dash character that is banned. "
                "Rewrite the sentence with a comma, colon or full stop, "
                "then call save_draft again.")

    known = {k for k, _ in config.PILLARS}
    if pillar not in known:
        return f"Rejected: pillar must be one of {sorted(known)}."

    bad = [p for p in platforms if p not in config.PLATFORMS]
    if bad:
        return f"Rejected: unknown platforms {bad}."

    post_id = db.create_draft(body, agent="pam", pillar=pillar,
                              platforms=platforms)
    return f"Saved as {post_id}. Stop now."


def write(brief: str) -> runner.Result:
    return runner.run("pam", brief, tools=[save_draft], system=prompts.load("pam"))
