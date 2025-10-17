"""Ensure demo lecturer and student accounts are available."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from werkzeug.security import generate_password_hash

from app.app import app, get_db, seed_default_lecturer


def ensure_student() -> None:
    conn = get_db()
    student = conn.execute("SELECT student_id FROM student WHERE email = ?", ("demo@student.edu",)).fetchone()
    if student:
        return
    conn.execute(
        "INSERT INTO student (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo Student", "demo@student.edu", generate_password_hash("demo123")),
    )
    conn.commit()


def main() -> None:
    with app.app_context():
        conn = get_db()
        seed_default_lecturer(conn)
        ensure_student()
        print("Lecturer: admin@lct.edu / Admin123!")
        print("Student: demo@student.edu / demo123")


if __name__ == "__main__":
    main()
