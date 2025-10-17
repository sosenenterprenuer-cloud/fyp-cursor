"""Seed demo data from the exported MS Forms CSV file."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import csv
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from werkzeug.security import generate_password_hash

from app.app import app, get_db, get_database_path

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "msforms_30q_17students.csv"
POINTS_PREFIX = "Points - "
TIME_PREFIX = "Time - "
DEFAULT_PASSWORD = "Student123!"


def normalize(text: str) -> str:
    return " ".join(re.sub(r"\s+", " ", text.strip().lower()).split())


def derive_email(first: str, last: str, existing: set[str]) -> str:
    base = ".".join(
        filter(None, [re.sub(r"[^a-z0-9]", "", first.lower()), re.sub(r"[^a-z0-9]", "", last.lower())])
    ) or "student"
    candidate = f"{base}@lct.edu"
    counter = 1
    while candidate in existing:
        candidate = f"{base}.{counter}@lct.edu"
        counter += 1
    existing.add(candidate)
    return candidate


def read_csv() -> Tuple[List[Dict[str, str]], List[str], Dict[str, str], Dict[str, str]]:
    if not CSV_PATH.exists():
        raise SystemExit(f"CSV file not found at {CSV_PATH}")

    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit("CSV file has no header row.")
        points_columns = [name for name in reader.fieldnames if name.startswith(POINTS_PREFIX)]
        if len(points_columns) != 30:
            raise SystemExit(f"Expected 30 point columns; found {len(points_columns)}.")
        time_columns = {name[len(TIME_PREFIX):]: name for name in reader.fieldnames if name.startswith(TIME_PREFIX)}
        rows = list(reader)
    question_map = {col[len(POINTS_PREFIX):]: col for col in points_columns}
    return rows, points_columns, question_map, time_columns


def main() -> None:
    rows, points_columns, question_map, time_columns = read_csv()

    with app.app_context():
        conn = get_db()
        quiz_rows = conn.execute("SELECT quiz_id, question, correct_answer FROM quiz").fetchall()
        if len(quiz_rows) != 30:
            raise SystemExit("Quiz table must contain exactly 30 questions before import.")
        quiz_lookup = {normalize(row["question"]): row for row in quiz_rows}

        mapping: Dict[str, Dict[str, object]] = {}
        for full_question, column in question_map.items():
            norm = normalize(full_question)
            if norm not in quiz_lookup:
                raise SystemExit(f"Quiz text not found for column '{full_question}'.")
            mapping[column] = quiz_lookup[norm]

        existing_emails = {row[0] for row in conn.execute("SELECT email FROM student").fetchall()}

        created_accounts: List[Tuple[str, str]] = []

        for entry in rows:
            first = entry.get("First Name") or entry.get("First name") or entry.get("First") or ""
            last = entry.get("Last Name") or entry.get("Last name") or entry.get("Surname") or entry.get("Last") or ""
            full_name = entry.get("Name") or entry.get("Full Name") or entry.get("Full name") or ""
            if not first and not last and full_name:
                parts = full_name.split()
                if parts:
                    first = parts[0]
                    last = parts[-1] if len(parts) > 1 else ""
            if not first:
                first = "Student"
            if not last:
                last = "Learner"
            name = f"{first.strip()} {last.strip()}".strip()
            email = derive_email(first, last, existing_emails)

            student = conn.execute("SELECT student_id FROM student WHERE email = ?", (email,)).fetchone()
            if not student:
                conn.execute(
                    "INSERT INTO student (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(DEFAULT_PASSWORD)),
                )
                conn.commit()
                student = conn.execute("SELECT student_id FROM student WHERE email = ?", (email,)).fetchone()
                created_accounts.append((name, email))

            student_id = student["student_id"]
            existing_attempt = conn.execute(
                "SELECT attempt_id FROM attempt WHERE student_id = ? AND source = ?",
                (student_id, "import"),
            ).fetchone()
            if existing_attempt:
                continue

            started = entry.get("Timestamp") or entry.get("Start time") or entry.get("Submitted")
            timestamp = started or datetime.utcnow().isoformat(timespec="seconds")

            attempt_cursor = conn.execute(
                """
                INSERT INTO attempt (student_id, nf_scope, started_at, finished_at, items_total, items_correct, score_pct, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (student_id, None, timestamp, timestamp, 0, 0, 0.0, "import"),
            )
            attempt_id = attempt_cursor.lastrowid

            items_correct = 0
            responses_to_insert: List[Tuple[object, ...]] = []

            for column in points_columns:
                quiz = mapping[column]
                quiz_id = quiz["quiz_id"]
                correct_answer = quiz["correct_answer"]
                raw_points = entry.get(column)
                try:
                    score = int(float(raw_points)) if raw_points not in (None, "") else 0
                except ValueError:
                    score = 0
                score = 1 if score > 0 else 0
                if score:
                    items_correct += 1
                time_key = time_columns.get(column[len(POINTS_PREFIX):])
                raw_time = entry.get(time_key) if time_key else None
                try:
                    response_time = float(raw_time) if raw_time not in (None, "") else random.uniform(8, 20)
                except ValueError:
                    response_time = random.uniform(8, 20)
                answer_text = correct_answer if score else None
                responses_to_insert.append(
                    (student_id, attempt_id, quiz_id, answer_text, score, response_time)
                )

            conn.executemany(
                """
                INSERT INTO response (student_id, attempt_id, quiz_id, answer, score, response_time_s)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                responses_to_insert,
            )
            score_pct = round((items_correct / 30) * 100, 2)
            conn.execute(
                """
                UPDATE attempt
                SET items_total = ?, items_correct = ?, score_pct = ?, finished_at = ?
                WHERE attempt_id = ?
                """,
                (30, items_correct, score_pct, timestamp, attempt_id),
            )
            conn.commit()

        if created_accounts:
            print("Created student accounts:")
            for name, email in created_accounts:
                print(f" - {name}: {email} / {DEFAULT_PASSWORD}")
        else:
            print("No new accounts created.")


if __name__ == "__main__":
    from datetime import datetime

    main()
