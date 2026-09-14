# The job descriptions

One file per agent. This is where you scope what each one does, in plain
English. No code, no escaping, no redeploy needed locally: the files are read
fresh on every run.

The tokens below get filled in from `app/config.py` before the agent sees the
text, so brand facts live in one place and never drift between six prompts.

| Token | What it becomes |
|---|---|
| `{{brand}}` | Voltade |
| `{{product}}` | Volty |
| `{{audience}}` | who we are writing for |
| `{{voice}}` | the house voice rules |
| `{{pillars}}` | the content pillars, one per line |
| `{{no_go}}` | the topics Kelly will not touch |
| `{{posts_per_day}}` | the daily ceiling |
| `{{review_minutes}}` | the human review budget |
| `{{rate_limit}}` | Kelly's replies per hour |

## How to scope an agent well

Three things that have already gone wrong here, worth knowing before you edit:

**Say what not to do, not just what to do.** Pam invented a customer anecdote
on her first run, because nothing told her not to. The rule that fixed it is
specific: do not claim a conversation happened unless the brief says it did.

**Give one agent one job.** Michael decides how much gets made and never
writes copy. Pam writes copy and never decides how much. That split is why the
volume stays at three a day instead of drifting up, because the agent who
enjoys writing is not the one holding the budget.

**Let saying nothing be a valid answer.** Jim is told that finding nothing is
better than padding. Michael is told a thin day beats a full one. Without that,
an agent will always produce, because producing looks like working.

## What is not in these files

Guardrails are not here, deliberately. The kill switch, the autonomy dial, the
no-go list and the rate limit live in `app/brakes.py` and are enforced in code
around the agent, not asked for in the prompt. A rule an agent could talk
itself out of is not a rule.
