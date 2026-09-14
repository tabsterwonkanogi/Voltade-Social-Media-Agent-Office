"""Record a walkthrough of the cockpit on an emulated iPhone.

    python -m scripts.record_demo [base_url]

Drives the real app with real data. Nothing is faked and nothing is staged:
every screen is the running application responding to actual taps.

Deliberately never touches the kill switch.

Output: recordings/demo.webm, then convert with ffmpeg.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"
USER = "beatrice"
PASSWORD = "voltademarketing123"
OUT = Path(__file__).resolve().parents[1] / "recordings"

# An iPhone 15 viewport. Scale factor 3 so the capture is crisp enough to
# survive a social crop.
VIEWPORT = {"width": 393, "height": 852}
SCALE = 3


def beat(seconds: float = 1.4) -> None:
    """A pause long enough to read. Machines move faster than viewers do."""
    time.sleep(seconds)


def glide(page, distance: int, steps: int = 14) -> None:
    """Scroll the way a thumb does, rather than jumping."""
    for _ in range(steps):
        page.mouse.wheel(0, distance / steps)
        time.sleep(0.05)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=SCALE,
            is_mobile=True,
            has_touch=True,
            user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "Version/17.0 Mobile/15E148 Safari/604.1"),
            record_video_dir=str(OUT),
            record_video_size={"width": VIEWPORT["width"] * SCALE,
                               "height": VIEWPORT["height"] * SCALE},
            color_scheme="dark",
        )
        page = context.new_page()

        # --- signing in -------------------------------------------------
        page.goto(f"{BASE}/login", wait_until="networkidle")
        beat(1.6)
        page.click("#name")
        page.type("#name", USER, delay=110)
        beat(0.4)
        page.click("#password")
        page.type("#password", PASSWORD, delay=70)
        beat(0.7)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        beat(2.0)

        # --- the queue --------------------------------------------------
        glide(page, 420)
        beat(1.2)

        more = page.query_selector("details.more summary")
        if more:
            more.click()          # read the rest of the first draft
            beat(2.6)
            glide(page, 700)
            beat(1.6)
            page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            beat(1.2)

        # --- approving one ----------------------------------------------
        approve = page.query_selector("form[action$='/approve'] button")
        if approve:
            approve.scroll_into_view_if_needed()
            beat(0.8)
            approve.click()
            page.wait_for_load_state("networkidle")
            beat(2.4)          # the flash message and the count dropping

        # --- the six agents ----------------------------------------------
        page.click("a[href='/agents']")
        page.wait_for_load_state("networkidle")
        beat(2.2)
        glide(page, 500)
        beat(2.0)
        glide(page, 500)
        beat(1.8)

        # --- what people said, and what Kelly refused ---------------------
        page.click("a[href='/comments']")
        page.wait_for_load_state("networkidle")
        beat(2.6)
        glide(page, 450)
        beat(2.2)

        # --- the numbers we will not invent -------------------------------
        page.click("a[href='/numbers']")
        page.wait_for_load_state("networkidle")
        beat(2.6)
        glide(page, 350)
        beat(1.6)

        # --- what goes out ------------------------------------------------
        page.click("a[href='/calendar']")
        page.wait_for_load_state("networkidle")
        beat(2.2)

        # --- the brakes, without touching them ----------------------------
        page.goto(f"{BASE}/settings", wait_until="networkidle")
        beat(2.4)
        glide(page, 420)       # kill switch on screen, never pressed
        beat(2.2)
        glide(page, 500)
        beat(1.8)
        glide(page, 500)       # the audit trail
        beat(2.6)

        context.close()
        browser.close()

    video = sorted(OUT.glob("*.webm"), key=lambda f: f.stat().st_mtime)[-1]
    final = OUT / "demo.webm"
    if video != final:
        final.unlink(missing_ok=True)
        video.rename(final)
    print(f"recorded {final}")
    print(f"{final.stat().st_size / 1_000_000:.1f} MB")


if __name__ == "__main__":
    main()
