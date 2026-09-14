"""The shared agent runtime.

Every agent goes through run(). That means every agent, without exception:
  - is stopped by the kill switch
  - writes a runs row at start and end, so a 3am failure is explainable
  - has its tokens counted against the daily ceiling

No agent talks to Telegram or to the website. They only touch the store.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Sequence

import anthropic

from .. import config, db

log = logging.getLogger("agents")

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class Halted(Exception):
    """The kill switch is on, or the day's token ceiling is spent."""


@dataclass
class Result:
    agent: str
    run_id: str
    text: str
    input_tokens: int
    output_tokens: int


def tokens_used_today() -> int:
    today = date.today().isoformat()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) AS t "
            "FROM runs WHERE started_at >= ?", (today,)).fetchone()
    return row["t"]


def run(agent: str, task: str, *, tools: Sequence[Callable[..., Any]] = (),
        system: str = "", effort: str = "high",
        max_tokens: int = 16000) -> Result:
    """One agent, one job, looping until it is done."""
    if agent not in config.AGENTS:
        raise ValueError(f"unknown agent {agent!r}")

    if db.killed():
        db.audit("agent.halted", actor=agent, surface="system",
                 detail="kill switch on")
        raise Halted("kill switch is on")

    spent = tokens_used_today()
    if spent >= config.DAILY_TOKEN_CEILING:
        db.audit("agent.halted", actor=agent, surface="system",
                 detail=f"daily token ceiling reached ({spent})")
        raise Halted(f"daily token ceiling reached ({spent})")

    run_id = db.start_run(agent)
    log.info("%s started (%s)", agent, run_id)

    try:
        runner = client().beta.messages.tool_runner(
            model=config.MODEL,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            system=system,
            tools=list(tools),
            messages=[{"role": "user", "content": task}],
        )
        final = runner.until_done()
    except Exception as exc:
        db.end_run(run_id, status="error", error=f"{type(exc).__name__}: {exc}")
        log.exception("%s failed", agent)
        raise

    text = "\n".join(b.text for b in final.content if b.type == "text").strip()
    usage = final.usage
    db.end_run(
        run_id,
        status="ok",
        summary=text[:400],
        input_tokens=usage.input_tokens or 0,
        output_tokens=usage.output_tokens or 0,
    )
    log.info("%s done (%s in / %s out)", agent,
             usage.input_tokens, usage.output_tokens)

    return Result(agent, run_id, text,
                  usage.input_tokens or 0, usage.output_tokens or 0)
