"""Jim. Goes and reads what is actually happening.

He writes findings into the store and never writes a draft. Keeping research
and copy in separate agents is what stops a post being built around a fact
nobody checked.
"""

from __future__ import annotations

from anthropic import beta_tool

from .. import config, db
from . import prompts, runner



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
        system=prompts.load("jim"),
    )
