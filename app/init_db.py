import os
import sqlite3
from pathlib import Path


def initialize_database(db_path: str) -> None:
    base_dir = Path(__file__).resolve().parent
    schema_sql = (base_dir / "schema.sql").read_text(encoding="utf-8")
    seed_sql = (base_dir / "seed.sql").read_text(encoding="utf-8")

    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(schema_sql)
        con.executescript(seed_sql)
        con.commit()
    finally:
        con.close()


if __name__ == "__main__":
    db = os.environ.get("PLA_DB", "pla.db")
    initialize_database(db)
    print(f"Database initialized at: {db}")
