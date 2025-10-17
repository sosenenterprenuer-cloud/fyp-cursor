"""
Safe database migrations for the PLA app.
Adds missing columns and indexes without breaking existing data.
"""

import os
import sqlite3
import sys
from typing import Any

if __package__:
    from .db_utils import ensure_db_path
else:
    sys.path.insert(0, os.path.dirname(__file__))
    from db_utils import ensure_db_path


def run_migrations(db_path: str = None) -> None:
    """Run all pending migrations on the database."""
    if db_path is None:
        db_path = str(ensure_db_path(os.environ.get("PLA_DB")))

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    
    try:
        # Check if recommendation.status column exists
        cur = conn.execute("PRAGMA table_info(recommendation)")
        columns = [row[1] for row in cur.fetchall()]
        
        if 'status' not in columns:
            print("Adding status column to recommendation table...")
            conn.execute("ALTER TABLE recommendation ADD COLUMN status TEXT DEFAULT 'Pending'")
            conn.commit()
            print("Migration completed: Added recommendation.status column")
        else:
            print("Migration skipped: recommendation.status already exists")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()
