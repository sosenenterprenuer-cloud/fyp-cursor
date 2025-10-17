import io
import os
import sqlite3
import sys

if __package__:
    from .db_utils import ensure_db_path
else:
    sys.path.insert(0, os.path.dirname(__file__))
    from db_utils import ensure_db_path

db_path = str(ensure_db_path(os.getenv('PLA_DB')))
print(f"Initializing DB at: {os.path.abspath(db_path)}")

with sqlite3.connect(db_path) as conn:
    # Read SQL files with UTF-8 (Windows safe)
    with io.open('schema.sql', 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    with io.open('seed.sql', 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()

print("Database initialized successfully")
