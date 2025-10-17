"""Database stabilizer to keep the quiz application safe across migrations."""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


class StabilizationError(RuntimeError):
    """Raised when the stabilizer encounters an unrecoverable issue."""


def _load_app_module():
    app_path = Path(__file__).resolve().parents[1] / "app" / "app.py"
    spec = importlib.util.spec_from_file_location("pla_app", app_path)
    if spec is None or spec.loader is None:
        raise StabilizationError("Unable to load Flask application module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def _ensure_column(conn, table: str, column: str, ddl: str) -> None:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        conn.execute(ddl)


def _ensure_bad_response_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bad_response (
            response_id INTEGER PRIMARY KEY,
            attempt_id INTEGER,
            student_id INTEGER,
            quiz_id INTEGER,
            answer TEXT,
            score INTEGER,
            response_time_s REAL,
            noted_reason TEXT,
            moved_at TEXT DEFAULT (datetime('now'))
        )
        """
    )


def _backfill_attempt_source(conn) -> None:
    conn.execute(
        "UPDATE attempt SET source='live' WHERE source IS NULL OR TRIM(source)=''"
    )


def _default_category(question: str, concept_tag: str) -> str:
    blob = f"{question} {concept_tag}".lower()
    keywords = ["fd", "functional", "1nf", "2nf", "3nf", "boyce", "dependency", "normalize", "normalisation", "bcnf", "4nf"]
    if any(key in blob for key in keywords):
        return "Normalization & Dependencies"
    return "Data Modeling & DBMS Fundamentals"


def _backfill_quiz_category(conn) -> None:
    rows = conn.execute(
        """
        SELECT quiz_id, question, concept_tag, two_category
        FROM quiz
        WHERE two_category IS NULL OR TRIM(two_category)=''
        """
    ).fetchall()
    for row in rows:
        category = _default_category(row["question"], row["concept_tag"])
        conn.execute(
            "UPDATE quiz SET two_category=? WHERE quiz_id=?",
            (category, row["quiz_id"]),
        )


def _sanitize_options_text(conn) -> None:
    rows = conn.execute("SELECT quiz_id, options_text FROM quiz").fetchall()
    for row in rows:
        raw = row["options_text"] or "[]"
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise TypeError
        except Exception:
            conn.execute(
                "UPDATE quiz SET options_text='[]' WHERE quiz_id=?",
                (row["quiz_id"],),
            )


def _move_orphan_responses(conn) -> None:
    _ensure_bad_response_table(conn)
    orphan_rows = conn.execute(
        """
        SELECT r.*,
               (SELECT 1 FROM attempt a WHERE a.attempt_id = r.attempt_id) AS has_attempt,
               (SELECT 1 FROM quiz q WHERE q.quiz_id = r.quiz_id)     AS has_quiz,
               (SELECT 1 FROM student s WHERE s.student_id = r.student_id) AS has_student
        FROM response r
        WHERE (SELECT 1 FROM attempt a WHERE a.attempt_id = r.attempt_id) IS NULL
           OR (SELECT 1 FROM quiz q WHERE q.quiz_id = r.quiz_id) IS NULL
           OR (SELECT 1 FROM student s WHERE s.student_id = r.student_id) IS NULL
        """
    ).fetchall()

    for row in orphan_rows:
        reasons = []
        if row["has_attempt"] is None:
            reasons.append("missing attempt")
        if row["has_quiz"] is None:
            reasons.append("missing quiz")
        if row["has_student"] is None:
            reasons.append("missing student")
        noted = ", ".join(reasons) if reasons else "unknown"
        conn.execute(
            """
            INSERT OR REPLACE INTO bad_response
                (response_id, attempt_id, student_id, quiz_id, answer, score, response_time_s, noted_reason)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                row["response_id"],
                row["attempt_id"],
                row["student_id"],
                row["quiz_id"],
                row["answer"],
                row["score"],
                row["response_time_s"],
                noted,
            ),
        )
        conn.execute("DELETE FROM response WHERE response_id=?", (row["response_id"],))


def _purge_legacy_modules(conn) -> None:
    conn.execute(
        "UPDATE recommendation SET module_id=NULL WHERE module_id IS NOT NULL"
    )
    conn.execute("DELETE FROM module WHERE LOWER(title) IN ('1nf','2nf','3nf','functional dependency','functional dependencies')")
    conn.execute("DELETE FROM module WHERE LOWER(nf_level) IN ('1nf','2nf','3nf','fd')")
    rows = conn.execute("SELECT COUNT(*) FROM module").fetchone()[0]
    if rows < 2:
        conn.execute("DELETE FROM module")
        conn.executemany(
            """
            INSERT INTO module (title, description, nf_level, concept_tag, resource_url)
            VALUES (?,?,?,?,?)
            """,
            [
                (
                    "Data Modeling & DBMS Fundamentals",
                    "Understand core modeling concepts and DBMS components.",
                    "Concept",
                    "Fundamentals",
                    "/module/fundamentals",
                ),
                (
                    "Normalization & Dependencies",
                    "Practice normalization steps and dependency analysis.",
                    "Concept",
                    "Normalization",
                    "/module/norm",
                ),
            ],
        )


def _reload_quiz_if_needed(conn) -> None:
    csv_path = Path(__file__).resolve().parents[1] / "data" / "quiz_30.csv"
    try:
        current = conn.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
    except Exception:
        return
    if current == 30:
        return
    if not csv_path.exists():
        return

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_HEADERS:
            return
        rows = []
        for raw in reader:
            question = (raw.get("question") or "").strip()
            if not question:
                continue
            try:
                options = json.loads(raw.get("options_text", ""))
            except Exception:
                continue
            if not isinstance(options, list) or len(options) != 4:
                continue
            options = [str(opt) for opt in options]
            correct = str(raw.get("correct_answer", ""))
            if correct not in options:
                continue
            category = (raw.get("two_category") or "").strip()
            if category not in ALLOWED_CATEGORIES:
                continue
            rows.append(
                (
                    question,
                    json.dumps(options, ensure_ascii=False),
                    correct,
                    raw.get("nf_level", ""),
                    raw.get("concept_tag", ""),
                    raw.get("explanation", ""),
                    category,
                )
            )

    if rows:
        conn.execute("DELETE FROM quiz")
        conn.executemany(
            """
            INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category)
            VALUES (?,?,?,?,?,?,?)
            """,
            rows,
        )


def stabilize_connection(conn) -> None:
    """Run all stabilization routines against the provided connection."""
    _ensure_column(conn, "quiz", "two_category", "ALTER TABLE quiz ADD COLUMN two_category TEXT")
    _ensure_column(conn, "attempt", "source", "ALTER TABLE attempt ADD COLUMN source TEXT")

    _reload_quiz_if_needed(conn)
    _backfill_attempt_source(conn)
    _backfill_quiz_category(conn)
    _sanitize_options_text(conn)
    _move_orphan_responses(conn)
    _purge_legacy_modules(conn)
    conn.commit()


def run() -> None:
    module = _load_app_module()
    flask_app = module.app
    with flask_app.app_context():
        conn = module.get_db()
        try:
            stabilize_connection(conn)
        finally:
            module.close_db(None)


if __name__ == "__main__":
    run()
EXPECTED_HEADERS = [
    "q_no",
    "question",
    "options_text",
    "correct_answer",
    "nf_level",
    "concept_tag",
    "explanation",
    "two_category",
]
ALLOWED_CATEGORIES = {
    "Data Modeling & DBMS Fundamentals",
    "Normalization & Dependencies",
}

