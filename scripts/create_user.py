"""Make an account.  python -m scripts.create_user <name> <role> [password]"""
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
    name, role = sys.argv[1], sys.argv[2]
    password = sys.argv[3] if len(sys.argv) > 3 else None
    db.init_db()
    uid, pw = auth.create_user(name, role, password)
    print(f"created {name} as {role}")
    print(f"  id       {uid}")
    print(f"  password {pw}")

if __name__ == "__main__":
    main()
