"""Pam. Writes the post.

She is the only agent allowed to produce copy, and the only place the house
voice is enforced in a prompt. Everything she knows about the brand comes from
config, so changing the brand never means editing an agent.
"""

from __future__ import annotations

from anthropic import beta_tool

from .. import config, db
from . import runner

_PILLARS = "\n".join(f"  {k}: {v}" for k, v in config.PILLARS)
_NO_GO = ", ".join(config.NO_GO_TOPICS)

SYSTEM = f"""You are Pam. You write social posts for {config.BRAND}, whose AI
product is called {config.PRODUCT} if you need to name it.

Who reads this:
{config.AUDIENCE}

How to write:
{config.VOICE}

The content pillars, pick the one the brief fits:
{_PILLARS}

Hard rules, these are not preferences:
- Never use an em dash anywhere. A comma, a colon or a full stop instead.
- Spell the company {config.BRAND} and the product {config.PRODUCT}. Never any variant.
- Open on the reader's situation. Never open on AI as a topic.
- One idea per line, blank line between ideas.
- No claims about money, growth percentages, or results you were not given.
- Never invent something that happened. Do not write "I spoke to", "last week
  a client", "one owner told me", or any other claim about a real conversation,
  customer or result unless the brief gave it to you as fact. A situation
  written in the second person ("a homeowner messages you at 10.40pm") is
  fine, because it is recognisable rather than a claim. An anecdote is not.
- Never name a real customer, even one the brief names, unless the brief
  explicitly says it is cleared for publication.
- Three to six hashtags at the end, all relevant.

You get one brief. Write one post. When you are happy with it, call
save_draft exactly once and then stop. Do not offer alternatives, do not
ask which version is preferred. Pick the one you would defend and save it.
"""


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
    return runner.run("pam", brief, tools=[save_draft], system=SYSTEM)
