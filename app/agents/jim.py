"""Jim. Goes and reads what is actually happening.

He writes findings into the store and never writes a draft. Keeping research
and copy in separate agents is what stops a post being built around a fact
nobody checked.
"""

from __future__ import annotations

from anthropic import beta_tool

from .. import config, db
from . import runner

SYSTEM = f"""You are Jim. You do research for {config.BRAND}, a Singapore
company selling AI to small and medium businesses.

Who we are writing for:
{config.AUDIENCE}

Your job is to find things that are true and specific this week, and that an
SME owner would care about. Not AI industry news. Not funding rounds. Not
model releases, unless a model release changes what a small business can
actually afford or do.

Good findings look like: a policy or grant change in Singapore, a platform
changing something that affects small businesses, a concrete statistic about
SME operations, a shift in what customers expect.

Bad findings look like: "AI is transforming business", anything with no date,
anything you cannot point to a source for.

Search, then call save_finding once per genuinely useful thing, at most three.
Every finding needs a source URL. If you cannot find three worth having, save
fewer. Saving nothing is a valid outcome and better than padding.
Then stop.
"""


@beta_tool
def save_finding(title: str, body: str, source: str) -> str:
    """Save one research finding for the coordinator to use.

    Args:
        title: One line, specific. Not a topic, a finding.
        body: Two to four sentences. What it is and why an SME owner cares.
        source: The URL you got this from. Required.
    """
    if not source.startswith("http"):
        return "Rejected: source must be a URL you actually found this at."
    note_id = db.add_note("finding", title, body, agent="jim", source=source)
    return f"Saved {note_id}."


def research(topic: str = "") -> runner.Result:
    task = topic or (
        "Find what happened in the last seven days that matters to a small or "
        "medium business owner in Singapore thinking about AI or automation."
    )
    return runner.run(
        "jim", task,
        tools=[save_finding,
               {"type": "web_search_20260209", "name": "web_search",
                "max_uses": 8}],
        system=SYSTEM,
    )
