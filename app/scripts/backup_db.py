"""Create a timestamped copy of the database in the backups directory."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import shutil
from datetime import datetime
from pathlib import Path

from app.app import get_database_path


def main() -> None:
    db_path = Path(get_database_path())
    if not db_path.exists():
        raise SystemExit(f"Database not found at {db_path}")
    backups_dir = Path.cwd() / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    target = backups_dir / f"pla_{timestamp}.db"
    shutil.copy2(db_path, target)
    print(f"Backup created at {target}")


if __name__ == "__main__":
    main()
