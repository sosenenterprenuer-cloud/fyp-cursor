 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/scripts/import_questions.py b/scripts/import_questions.py
index 1b69a17b89de87c4c1f80b12f6c64b0b14b48a04..025083386c4c01adb937d2ef3891b877e1d6e430 100644
--- a/scripts/import_questions.py
+++ b/scripts/import_questions.py
@@ -1,33 +1,198 @@
-import csv, json, os, sqlite3, sys
-REQ = ["q_no","question","options_text","correct_answer","nf_level","concept_tag","explanation","two_category"]
-DB = os.getenv("PLA_DB","pla.db")
-def fail(m): print("[ERROR]", m); sys.exit(1)
-
-if len(sys.argv)!=2: fail("Usage: python scripts/import_questions.py quiz.csv")
-path=sys.argv[1]
-if not os.path.exists(path): fail(f"Missing {path}")
-
-with open(path, newline="", encoding="utf-8-sig") as f:
-    rdr=csv.DictReader(f)
-    if rdr.fieldnames!=REQ: fail(f"Headers must be {REQ}. Got {rdr.fieldnames}")
-    rows=list(rdr)
-
-# Validate: correct_answer ∈ options_text
-for i,r in enumerate(rows, start=2):
-    try: opts = json.loads(r["options_text"])
-    except Exception: fail(f"Row {i}: options_text invalid JSON")
-    ca = (r["correct_answer"] or "").strip()
-    if ca and ca not in [str(x) for x in opts]:
-        fail(f"Row {i}: correct_answer not in options_text")
-
-con=sqlite3.connect(DB); con.execute("PRAGMA foreign_keys=ON")
-ins="""INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category)
-       VALUES (?,?,?,?,?,?,?)"""
-for r in rows:
-    con.execute(ins, (r["question"], r["options_text"], r["correct_answer"],
-                      r["nf_level"], r["concept_tag"], r["explanation"], r["two_category"]))
-con.commit(); con.close()
-print(f"[OK] Imported {len(rows)} questions.")
-
-
-
+"""Utility to import quiz questions from a CSV file.
+
+This script validates the CSV structure and then tops up the quiz
+bank to 30 questions using the shared ``get_db`` helper.
+"""
+from __future__ import annotations
+
+import csv
+import importlib.util
+import json
+import sys
+from pathlib import Path
+from typing import Iterable, List, Mapping
+
+REPO_ROOT = Path(__file__).resolve().parents[1]
+DEFAULT_CSV = REPO_ROOT / "data" / "quiz_30.csv"
+
+
+EXPECTED_HEADERS = [
+    "q_no",
+    "question",
+    "options_text",
+    "correct_answer",
+    "nf_level",
+    "concept_tag",
+    "explanation",
+    "two_category",
+]
+ALLOWED_CATEGORIES = {
+    "Data Modeling & DBMS Fundamentals",
+    "Normalization & Dependencies",
+}
+MAX_QUESTIONS = 30
+
+
+class CsvImportError(RuntimeError):
+    """Raised when the CSV input fails validation."""
+
+
+def _load_app_module():
+    """Dynamically load the Flask app module without requiring a package."""
+    app_path = Path(__file__).resolve().parents[1] / "app" / "app.py"
+    spec = importlib.util.spec_from_file_location("pla_app", app_path)
+    if spec is None or spec.loader is None:
+        raise CsvImportError("Unable to load Flask application module.")
+    module = importlib.util.module_from_spec(spec)
+    spec.loader.exec_module(module)  # type: ignore[arg-type]
+    return module
+
+
+def _validate_rows(rows: Iterable[Mapping[str, str]]) -> List[Mapping[str, str]]:
+    validated: List[Mapping[str, str]] = []
+    for idx, row in enumerate(rows, start=2):  # header is row 1
+        opts_raw = row.get("options_text", "")
+        try:
+            opts = json.loads(opts_raw)
+        except Exception as exc:  # pragma: no cover - defensive logging only
+            raise CsvImportError(f"Row {idx}: options_text is not valid JSON ({exc!r}).")
+        if not isinstance(opts, list):
+            raise CsvImportError(f"Row {idx}: options_text must be a JSON array of strings.")
+        if len(opts) != 4:
+            raise CsvImportError(f"Row {idx}: options_text must contain exactly 4 options.")
+        opts = [str(x) for x in opts]
+
+        correct = str(row.get("correct_answer", ""))
+        if correct not in opts:
+            raise CsvImportError(f"Row {idx}: correct_answer must match one of the options.")
+
+        category = row.get("two_category", "").strip()
+        if category not in ALLOWED_CATEGORIES:
+            raise CsvImportError(
+                f"Row {idx}: two_category must be one of {sorted(ALLOWED_CATEGORIES)}."
+            )
+
+        validated.append(row)
+    return validated
+
+
+def _resolve_csv_path(raw_path: Path | str) -> Path:
+    """Resolve a CSV path in a Windows-friendly manner."""
+
+    candidate = Path(raw_path)
+    # Direct hit first (absolute or relative to CWD)
+    if candidate.exists():
+        return candidate
+
+    if not candidate.is_absolute():
+        guesses = [
+            Path.cwd() / candidate,
+            REPO_ROOT / candidate,
+        ]
+
+        if candidate.name:
+            guesses.append(REPO_ROOT / "data" / candidate.name)
+
+        for guess in guesses:
+            if guess.exists():
+                return guess
+
+    raise CsvImportError(
+        f"Missing CSV file: {candidate if candidate.is_absolute() else candidate.as_posix()}"
+    )
+
+
+def _read_csv(csv_path: Path) -> List[Mapping[str, str]]:
+    csv_path = _resolve_csv_path(csv_path)
+    if not csv_path.exists():
+        raise CsvImportError(f"Missing CSV file: {csv_path}")
+    print(f"[INFO] Using quiz CSV: {csv_path}")
+
+    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
+        reader = csv.DictReader(handle)
+        if reader.fieldnames != EXPECTED_HEADERS:
+            raise CsvImportError(
+                f"CSV headers must be exactly {EXPECTED_HEADERS}. Got {reader.fieldnames}"
+            )
+        rows = list(reader)
+    return _validate_rows(rows)
+
+
+def _top_up_questions(conn, rows: List[Mapping[str, str]]) -> int:
+    current = conn.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
+    if current >= MAX_QUESTIONS:
+        return 0
+
+    # Avoid inserting duplicates by question text.
+    existing = {
+        r["question"]
+        for r in conn.execute("SELECT question FROM quiz")
+    }
+
+    slots = MAX_QUESTIONS - current
+    inserted = 0
+    insert_sql = (
+        """
+        INSERT INTO quiz
+            (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category)
+        VALUES (?,?,?,?,?,?,?)
+        """
+    )
+
+    for row in rows:
+        category = (row.get("two_category", "") or "").strip()
+        if category not in ALLOWED_CATEGORIES:
+            continue
+        question = row.get("question", "").strip()
+        if not question or question in existing:
+            continue
+        conn.execute(
+            insert_sql,
+            (
+                question,
+                row.get("options_text", "[]"),
+                row.get("correct_answer", ""),
+                row.get("nf_level", ""),
+                row.get("concept_tag", ""),
+                row.get("explanation", ""),
+                category,
+            ),
+        )
+        existing.add(question)
+        inserted += 1
+        if inserted >= slots:
+            break
+
+    return inserted
+
+
+def import_questions(csv_path: Path) -> int:
+    """Import questions from the provided CSV file."""
+    rows = _read_csv(csv_path)
+    module = _load_app_module()
+    flask_app = module.app
+    inserted = 0
+    with flask_app.app_context():
+        conn = module.get_db()
+        try:
+            inserted = _top_up_questions(conn, rows)
+            conn.commit()
+        finally:  # ensure the connection is released from ``g``
+            module.close_db(None)
+    return inserted
+
+
+def main(argv: List[str]) -> None:
+    if len(argv) not in {1, 2}:
+        raise SystemExit("Usage: python scripts/import_questions.py [quiz.csv]")
+    csv_path = Path(argv[1]) if len(argv) == 2 else DEFAULT_CSV
+    try:
+        inserted = import_questions(csv_path)
+    except CsvImportError as exc:
+        print(f"[ERROR] {exc}")
+        raise SystemExit(1)
+    print(f"[OK] Inserted {inserted} new question(s).")
+
+
+if __name__ == "__main__":
+    main(sys.argv)
 
EOF
)