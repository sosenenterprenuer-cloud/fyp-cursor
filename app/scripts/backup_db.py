import os
import shutil
import time

DB = os.getenv("PLA_DB", os.path.join(os.path.dirname(__file__), "..", "pla.db"))
DB = os.path.abspath(DB)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKUP_DIR = os.path.join(ROOT, "backups")


def main() -> None:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M")
    target = os.path.join(BACKUP_DIR, f"pla_{timestamp}.db")
    if os.path.exists(DB):
        shutil.copy2(DB, target)
        print("Backup ->", target)
    else:
        print("No DB file found at", DB, "(nothing to back up)")


if __name__ == "__main__":
    main()
