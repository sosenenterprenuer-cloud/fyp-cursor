"""Utility to import quiz questions from a CSV file.

This script validates the CSV structure and then tops up the quiz
bank to 30 questions using the shared ``get_db`` helper.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from typing import Iterable, List, Mapping

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
MAX_QUESTIONS = 30


class CsvImportError(RuntimeError):
    """Raised when the CSV input fails validation."""


def _load_app_module():
    """Dynamically load the Flask app module without requiring a package."""
    app_path = Path(__file__).resolve().parents[1] / "app" / "app.py"
    spec = importlib.util.spec_from_file_location("pla_app", app_path)
    if spec is None or spec.loader is None:
        raise CsvImportError("Unable to load Flask application module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def _validate_rows(rows: Iterable[Mapping[str, str]]) -> List[Mapping[str, str]]:
    validated: List[Mapping[str, str]] = []
    for idx, row in enumerate(rows, start=2):  # header is row 1
        opts_raw = row.get("options_text", "")
        try:
            opts = json.loads(opts_raw)
        except Exception as exc:  # pragma: no cover - defensive logging only
            raise CsvImportError(f"Row {idx}: options_text is not valid JSON ({exc!r}).")
        if not isinstance(opts, list):
            raise CsvImportError(f"Row {idx}: options_text must be a JSON array of strings.")
        if len(opts) != 4:
            raise CsvImportError(f"Row {idx}: options_text must contain exactly 4 options.")
        opts = [str(x) for x in opts]

        correct = str(row.get("correct_answer", ""))
        if correct not in opts:
            raise CsvImportError(f"Row {idx}: correct_answer must match one of the options.")

        category = row.get("two_category", "").strip()
        if category not in ALLOWED_CATEGORIES:
            raise CsvImportError(
                f"Row {idx}: two_category must be one of {sorted(ALLOWED_CATEGORIES)}."
            )

        validated.append(row)
    return validated


def _read_csv(csv_path: Path) -> List[Mapping[str, str]]:
    if not csv_path.exists():
        raise CsvImportError(f"Missing CSV file: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_HEADERS:
            raise CsvImportError(
                f"CSV headers must be exactly {EXPECTED_HEADERS}. Got {reader.fieldnames}"
            )
        rows = list(reader)
    return _validate_rows(rows)


def _top_up_questions(conn, rows: List[Mapping[str, str]]) -> int:
    current = conn.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
    if current >= MAX_QUESTIONS:
        return 0

    # Avoid inserting duplicates by question text.
    existing = {
        r["question"]
        for r in conn.execute("SELECT question FROM quiz")
    }

    slots = MAX_QUESTIONS - current
    inserted = 0
    insert_sql = (
        """
        INSERT INTO quiz
            (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category)
        VALUES (?,?,?,?,?,?,?)
        """
    )

    for row in rows:
        question = row.get("question", "").strip()
        if not question or question in existing:
            continue
        conn.execute(
            insert_sql,
            (
                question,
                row.get("options_text", "[]"),
                row.get("correct_answer", ""),
                row.get("nf_level", ""),
                row.get("concept_tag", ""),
                row.get("explanation", ""),
                row.get("two_category", ""),
            ),
        )
        existing.add(question)
        inserted += 1
        if inserted >= slots:
            break

    return inserted


def import_questions(csv_path: Path) -> int:
    """Import questions from the provided CSV file."""
    rows = _read_csv(csv_path)
    module = _load_app_module()
    flask_app = module.app
    inserted = 0
    with flask_app.app_context():
        conn = module.get_db()
        try:
            inserted = _top_up_questions(conn, rows)
            conn.commit()
        finally:  # ensure the connection is released from ``g``
            module.close_db(None)
    return inserted


def main(argv: List[str]) -> None:
    if len(argv) not in {1, 2}:
        raise SystemExit("Usage: python scripts/import_questions.py [quiz.csv]")
    csv_path = Path(argv[1]) if len(argv) == 2 else Path("data/quiz_30.csv")
    try:
        inserted = import_questions(csv_path)
    except CsvImportError as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
    print(f"[OK] Inserted {inserted} new question(s).")


if __name__ == "__main__":
    main(sys.argv)
