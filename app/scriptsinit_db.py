import os, sqlite3, io

db_path = os.getenv('PLA_DB', 'pla.db')
print(f"Initializing DB at: {os.path.abspath(db_path)}")

with sqlite3.connect(db_path) as conn:
    # Read SQL files with UTF-8 (Windows safe)
    with io.open('schema.sql', 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    with io.open('seed.sql', 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()

print("Database initialized successfully")
