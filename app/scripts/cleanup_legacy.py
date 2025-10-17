"""Remove quiz content outside the two supported topics and report the remaining count."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import sqlite3

from app.app import TOPICS, get_database_path


def main() -> None:
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT quiz_id, two_category FROM quiz").fetchall()
        legacy = [row["quiz_id"] for row in rows if row["two_category"] not in TOPICS]
        if legacy:
            conn.executemany("DELETE FROM response WHERE quiz_id = ?", [(qid,) for qid in legacy])
            conn.executemany("DELETE FROM quiz WHERE quiz_id = ?", [(qid,) for qid in legacy])
            conn.commit()
        remaining = conn.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
        print(f"Remaining quiz items: {remaining}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
