"""Seed demo student and lecturer accounts for quick testing."""

import os
import sqlite3

from werkzeug.security import generate_password_hash


def main() -> None:
    db_path = os.getenv("PLA_DB", "pla.db").strip().strip('"').strip("'")
    db_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON")

    con.execute(
        """
        INSERT OR IGNORE INTO student (name, email, program, password_hash)
        VALUES (?,?,?,?)
        """,
        (
            "Demo Student",
            "demo@student.edu",
            "Information Technology",
            generate_password_hash("demo123"),
        ),
    )

    con.execute(
        """
        INSERT OR IGNORE INTO lecturer (name, email, password_hash)
        VALUES (?,?,?)
        """,
        (
            "Admin Lecturer",
            "admin@lct.edu",
            generate_password_hash("Admin123!"),
        ),
    )

    con.commit()
    con.close()
    print("Seeded demo student and lecturer accounts.")


if __name__ == "__main__":
    main()
