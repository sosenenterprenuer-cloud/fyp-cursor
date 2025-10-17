 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/scripts/cleanup_legacy_10q.py b/scripts/cleanup_legacy_10q.py
new file mode 100644
index 0000000000000000000000000000000000000000..0d6590cdf453f9b3e3541da93bd484c9ac643655
--- /dev/null
+++ b/scripts/cleanup_legacy_10q.py
@@ -0,0 +1,166 @@
+import csv
+import json
+import os
+import sqlite3
+from pathlib import Path
+
+ALLOWED = {
+    "Data Modeling & DBMS Fundamentals",
+    "Normalization & Dependencies",
+}
+CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "quiz_30.csv"
+
+
+def _load_canonical_rows():
+    if not CSV_PATH.exists():
+        print(f"[WARN] {CSV_PATH} missing; cannot align to canonical 30-question bank.")
+        return {}
+
+    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
+        reader = csv.DictReader(handle)
+        rows = {}
+        for idx, row in enumerate(reader, start=2):
+            category = (row.get("two_category", "") or "").strip()
+            if category not in ALLOWED:
+                print(f"[SKIP] Row {idx}: unsupported category '{category}'.")
+                continue
+            try:
+                options = json.loads(row.get("options_text", "[]"))
+                if not isinstance(options, list):
+                    raise ValueError("options_text is not a list")
+            except Exception as exc:
+                print(f"[SKIP] Row {idx}: invalid options_text ({exc!r}).")
+                continue
+            correct = (row.get("correct_answer", "") or "").strip()
+            if correct not in {str(opt) for opt in options}:
+                print(f"[SKIP] Row {idx}: correct answer not found in options.")
+                continue
+            question = (row.get("question", "") or "").strip()
+            if not question:
+                print(f"[SKIP] Row {idx}: missing question text.")
+                continue
+            rows[question] = {
+                "question": question,
+                "options_text": row.get("options_text", "[]"),
+                "correct_answer": correct,
+                "nf_level": row.get("nf_level", ""),
+                "concept_tag": row.get("concept_tag", ""),
+                "explanation": row.get("explanation", ""),
+                "two_category": category,
+            }
+    return rows
+
+
+def main() -> None:
+    db_path = os.getenv("PLA_DB", "pla.db")
+    conn = sqlite3.connect(db_path)
+    conn.row_factory = sqlite3.Row
+    cur = conn.cursor()
+    cur.execute("PRAGMA foreign_keys=ON")
+
+    exists = cur.execute(
+        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='quiz'",
+    ).fetchone()
+    if not exists:
+        print("[SKIP] quiz table not found. Nothing to clean.")
+        conn.close()
+        return
+
+    cols = [row[1] for row in cur.execute("PRAGMA table_info(quiz)")]
+    if "two_category" not in cols:
+        cur.execute("ALTER TABLE quiz ADD COLUMN two_category TEXT")
+
+    canonical = _load_canonical_rows()
+
+    # Remove categories outside the allowed set
+    legacy_rows = cur.execute(
+        """
+        SELECT quiz_id FROM quiz
+        WHERE COALESCE(two_category, '') NOT IN (?, ?)
+        """,
+        tuple(ALLOWED),
+    ).fetchall()
+    legacy_ids = [row["quiz_id"] for row in legacy_rows]
+
+    if legacy_ids:
+        placeholders = ",".join("?" for _ in legacy_ids)
+        cur.execute(f"DELETE FROM response WHERE quiz_id IN ({placeholders})", legacy_ids)
+        cur.execute(f"DELETE FROM quiz WHERE quiz_id IN ({placeholders})", legacy_ids)
+        print(f"[CLEAN] Removed legacy questions: {len(legacy_ids)}")
+    else:
+        print("[CLEAN] No legacy questions to remove.")
+
+    # Remove duplicate question texts, keeping the lowest quiz_id
+    duplicates = []
+    existing_map = {}
+    for row in cur.execute("SELECT quiz_id, question FROM quiz").fetchall():
+        question = row["question"]
+        qid = row["quiz_id"]
+        if question in existing_map:
+            duplicates.append(qid)
+        else:
+            existing_map[question] = qid
+
+    if duplicates:
+        placeholders = ",".join("?" for _ in duplicates)
+        cur.execute(f"DELETE FROM response WHERE quiz_id IN ({placeholders})", duplicates)
+        cur.execute(f"DELETE FROM quiz WHERE quiz_id IN ({placeholders})", duplicates)
+        print(f"[CLEAN] Removed duplicate questions: {len(duplicates)}")
+
+    # Align with canonical CSV if available
+    if canonical:
+        # Remove any question not present in the canonical list
+        extras = []
+        current = cur.execute("SELECT quiz_id, question FROM quiz").fetchall()
+        for row in current:
+            if row["question"] not in canonical:
+                extras.append(row["quiz_id"])
+        if extras:
+            placeholders = ",".join("?" for _ in extras)
+            cur.execute(f"DELETE FROM response WHERE quiz_id IN ({placeholders})", extras)
+            cur.execute(f"DELETE FROM quiz WHERE quiz_id IN ({placeholders})", extras)
+            print(f"[CLEAN] Removed non-canonical questions: {len(extras)}")
+
+        # Insert missing canonical questions
+        existing_questions = {
+            row["question"]
+            for row in cur.execute("SELECT question FROM quiz").fetchall()
+        }
+        insert_sql = (
+            """
+            INSERT INTO quiz
+                (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category)
+            VALUES (?,?,?,?,?,?,?)
+            """
+        )
+        inserted = 0
+        for question, data in canonical.items():
+            if question in existing_questions:
+                continue
+            cur.execute(
+                insert_sql,
+                (
+                    data["question"],
+                    data["options_text"],
+                    data["correct_answer"],
+                    data["nf_level"],
+                    data["concept_tag"],
+                    data["explanation"],
+                    data["two_category"],
+                ),
+            )
+            existing_questions.add(question)
+            inserted += 1
+        if inserted:
+            print(f"[SEED] Inserted canonical questions: {inserted}")
+
+    remaining = cur.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
+    print("[CHECK] quiz rows now:", remaining)
+
+    conn.commit()
+    conn.close()
+    print("[OK] Cleanup complete.")
+
+
+if __name__ == "__main__":
+    main()
 
EOF
)