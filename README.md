# Voltade agent office

Six agents that research, plan, write, post, reply and report, with a human in
the loop by default. Built 14 September 2026.

This is its own thing. It does not import from the existing bot and does not
share a database with it. The only thing in common is the Blotato account,
which is a service subscription, not code.

## The six

| Agent | Job | State |
|---|---|---|
| Michael | decides what gets made, enforces the daily ceiling | running |
| Jim | reads what is actually happening, saves sourced findings | running |
| Pam | writes the post in the house voice | running |
| Dwight | publishes approved posts through Blotato | running |
| Kelly | replies to comments | waiting on platform review |
| Angela | reads the numbers, writes the weekly strategy note | waiting on platform review |

Kelly and Angela report "not connected" rather than inventing data. Nothing in
this system shows a placeholder number.

## The shape

Agents never talk to surfaces. Surfaces never talk to agents. Both only touch
the store. That is why approving is a function in `db`, not logic in a route,
and why adding Telegram approvals later is a couple of hours rather than a
rewrite.

Each agent's job description is a plain English file in `prompts/`, read fresh
on every run. Scoping an agent means editing markdown, not code.

```
prompts/        one job description per agent, in English
app/
  config.py     the whole brand in one file
  db.py         the store: posts, comments, runs, settings, audit, notes, users
  brakes.py     kill switch, autonomy dial, no-go list, rate limit
  scheduler.py  the clock, restart safe
  web.py        the cockpit
  blotato.py    publishing
  notify.py     push, notify only
  agents/       one file each
```

## Running it locally

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m scripts.create_user beatrice owner
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8011
```

Then http://127.0.0.1:8011

## Proving each piece

```bash
python -m scripts.smoke         # the store, and the audit trail
python -m scripts.run_chain     # all six agents, in order
python -m scripts.test_clock    # a job fires with nobody asking
python -m scripts.test_brakes   # the dial, the kill switch, the no-go list
python -m scripts.check_pages   # every cockpit page renders
```

## Environment

```
ANTHROPIC_API_KEY     required
BLOTATO_API_KEY       required to publish
PUBLISHING            set to "on" to allow posting. Production only.
                      Never set this in a local .env: a dev server with a
                      live scheduler will publish approved rows for real.
TELEGRAM_BOT_TOKEN    notifications
TELEGRAM_CHAT_ID      notifications
SESSION_SECRET        required, cookie signing
ADMIN_NAME            first run only, creates the owner account
ADMIN_PASSWORD        first run only, creates the owner account
TZ                    Asia/Singapore
DB_PATH               /data/app.db on Railway
LINKEDIN_PAGE_ID      optional, pins the company page
FACEBOOK_PAGE_ID      optional, pins the company page
```

## Deploying

Three things that will bite if missed:

1. **Attach a volume mounted at `/data`** and set `DB_PATH=/data/app.db`.
   Without it every deploy wipes the database.
2. **One replica.** Two replicas means two schedulers and every post goes out
   twice.
3. **Set `TZ=Asia/Singapore`,** or the 07:00 and 18:00 jobs run on UTC.

Health check is `/health`. It returns 503 if the clock has not ticked in 30
minutes, so a dead scheduler inside a live process restarts itself instead of
sitting there looking healthy.
