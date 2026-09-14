"""Step 09 proof: set a job seconds away, walk off, and it fires by itself.

    python -m scripts.test_clock

Runs the digest on a 20 second timer instead of at 18:00, so you can watch the
thing happen without waiting for the evening. Everything else is the real
scheduler: same guard, same kill switch check, same restart protection.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402
from apscheduler.triggers.date import DateTrigger  # noqa: E402

from app import config, db, scheduler  # noqa: E402


async def main() -> None:
    db.init_db()
    db.set_setting("lastrun.digest", "", actor="system", surface="system")

    fire_at = datetime.now(config.TZ) + timedelta(seconds=20)
    print(f"now      {datetime.now(config.TZ):%H:%M:%S}")
    print(f"digest   {fire_at:%H:%M:%S}   (nobody is going to ask it to)\n")

    sched = AsyncIOScheduler(timezone=config.TZ)
    sched.add_job(scheduler.guarded("digest", scheduler.digest,
                                    once_per=scheduler.today_stamp),
                  DateTrigger(run_date=fire_at), id="digest")
    sched.start()

    for _ in range(30):
        await asyncio.sleep(1)
        if not sched.get_jobs():
            break
        print(f"  {datetime.now(config.TZ):%H:%M:%S} waiting", end="\r")

    print(f"\n\nit fired at {datetime.now(config.TZ):%H:%M:%S}. "
          f"check your phone.\n")

    note = db.unused_notes("strategy", limit=1)
    if note:
        print("-" * 58)
        print(note[0]["body"])
        print("-" * 58)

    print(f"\nheartbeat age: {scheduler.heartbeat_age_seconds():.0f}s")
    sched.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
