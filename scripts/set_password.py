"""Change an account password.  python -m scripts.set_password <name> <password>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
from app import auth, db

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    db.init_db()
    name, password = sys.argv[1], sys.argv[2]
    if auth.set_password(name, password):
        print(f"password changed for {name}")
        print("verified:", auth.authenticate(name, password) is not None)
    else:
        print(f"no account called {name}")

if __name__ == "__main__":
    main()
