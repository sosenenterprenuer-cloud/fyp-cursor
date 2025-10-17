"""Minimal self-test harness to verify database and review view."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import os
import uuid

from werkzeug.security import generate_password_hash

from app.app import app, get_db


def ensure_tables(conn) -> None:
    required = {"student", "lecturer", "quiz", "attempt", "response", "feedback"}
    existing = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = required - existing
    if missing:
        raise SystemExit(f"Missing tables: {', '.join(sorted(missing))}")


def create_temp_records(conn):
    suffix = uuid.uuid4().hex[:6]
    email = f"selftest.{suffix}@example.edu"
    conn.execute(
        "INSERT INTO student (name, email, password_hash) VALUES (?, ?, ?)",
        ("Self Test", email, generate_password_hash("temp")),
    )
    student_id = conn.execute("SELECT student_id FROM student WHERE email = ?", (email,)).fetchone()[0]
    attempt = conn.execute(
        """
        INSERT INTO attempt (student_id, nf_scope, started_at, finished_at, items_total, items_correct, score_pct, source)
        VALUES (?, ?, datetime('now'), datetime('now'), 1, 1, 100, 'selftest')
        """,
        (student_id, None),
    )
    attempt_id = attempt.lastrowid
    quiz_row = conn.execute("SELECT quiz_id, correct_answer FROM quiz LIMIT 1").fetchone()
    conn.execute(
        """
        INSERT INTO response (student_id, attempt_id, quiz_id, answer, score, response_time_s)
        VALUES (?, ?, ?, ?, 1, 5.0)
        """,
        (student_id, attempt_id, quiz_row["quiz_id"], quiz_row["correct_answer"]),
    )
    conn.commit()
    return student_id, attempt_id

def pause_reset():
    original = os.environ.get('PLA_RESET')
    os.environ['PLA_RESET'] = '0'
    return original


def restore_reset(value):
    if value is None:
        os.environ.pop('PLA_RESET', None)
    else:
        os.environ['PLA_RESET'] = value


def main() -> None:
    with app.app_context():
        conn = get_db()
        ensure_tables(conn)
        count = conn.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
        if count != 30:
            raise SystemExit(f"Quiz table expected 30 items, found {count}.")
        student_id, attempt_id = create_temp_records(conn)

    original_reset = pause_reset()
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = student_id
                sess['role'] = 'student'
            response = client.get(f"/review/{attempt_id}")
            if response.status_code != 200:
                raise SystemExit(f"Review page returned status {response.status_code}")
    finally:
        restore_reset(original_reset)

    print("SELFTEST OK")


if __name__ == "__main__":
    main()
