"""Every cockpit page, signed in, as a smoke test.

    python -m scripts.check_pages <password>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PAGES = ["/", "/calendar", "/agents", "/comments", "/numbers", "/settings",
         "/health"]


def main() -> None:
    password = sys.argv[1] if len(sys.argv) > 1 else ""
    with TestClient(app) as c:
        r = c.post("/login", data={"name": "beatrice", "password": password},
                   follow_redirects=True)
        print(f"login        {r.status_code}")
        for path in PAGES:
            r = c.get(path)
            flag = "ok " if r.status_code < 400 else "ERR"
            print(f"{path:<12} {flag} {r.status_code}  {len(r.text):>6} bytes")
            if r.status_code >= 400:
                print(r.text[:500])


if __name__ == "__main__":
    main()
