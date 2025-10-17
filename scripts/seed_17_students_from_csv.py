 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/scripts/seed_17_students_from_csv.py b/scripts/seed_17_students_from_csv.py
new file mode 100644
index 0000000000000000000000000000000000000000..dbc9da9110476fcd89b8711ca78a5afa305f720b
--- /dev/null
+++ b/scripts/seed_17_students_from_csv.py
@@ -0,0 +1,120 @@
+import os
+import csv
+import sqlite3
+import re
+from werkzeug.security import generate_password_hash
+
+DB = os.getenv("PLA_DB", "pla.db")
+IN = os.getenv("SEED_CSV", "data/historical_submissions_varied.csv")
+DEFAULT_PW = os.getenv("SEED_PW", "Student123!")
+
+
+def name_from_email(email: str) -> str:
+    username = email.split("@")[0]
+    username = re.sub(r"[^a-z0-9.]+", "", username.lower())
+    parts = [part for part in username.split(".") if part]
+    return " ".join(part.capitalize() for part in parts) or "Student"
+
+
+def ensure_cols(con: sqlite3.Connection) -> None:
+    cols_attempt = [c[1] for c in con.execute("PRAGMA table_info(attempt)")]
+    if "source" not in cols_attempt:
+        con.execute("ALTER TABLE attempt ADD COLUMN source TEXT")
+    cols_quiz = [c[1] for c in con.execute("PRAGMA table_info(quiz)")]
+    if "two_category" not in cols_quiz:
+        con.execute("ALTER TABLE quiz ADD COLUMN two_category TEXT")
+
+
+def upsert_student(con: sqlite3.Connection, email: str) -> int:
+    row = con.execute(
+        "SELECT student_id FROM student WHERE lower(email)=lower(?)", (email,)
+    ).fetchone()
+    if row:
+        return int(row[0])
+    name = name_from_email(email)
+    password_hash = generate_password_hash(DEFAULT_PW)
+    con.execute(
+        "INSERT INTO student(name, email, password_hash) VALUES (?,?,?)",
+        (name, email, password_hash),
+    )
+    return int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
+
+
+def main() -> None:
+    if not os.path.exists(IN):
+        print("CSV not found:", IN)
+        return
+
+    con = sqlite3.connect(DB)
+    con.row_factory = sqlite3.Row
+    con.execute("PRAGMA foreign_keys=ON")
+    ensure_cols(con)
+
+    grouped = {}
+    with open(IN, newline="", encoding="utf-8") as handle:
+        reader = csv.DictReader(handle)
+        for row in reader:
+            email = (row.get("student_email", "") or "").strip().lower()
+            started = (row.get("started_at", "") or "").strip()
+            if not email or not started:
+                continue
+            grouped.setdefault((email, started), []).append(row)
+
+    created = 0
+    for (email, started_at), rows in grouped.items():
+        student_id = upsert_student(con, email)
+        con.execute(
+            "INSERT INTO attempt (student_id, nf_scope, started_at, source) VALUES (?,?,?,?)",
+            (student_id, "seed:first_attempt", started_at, "live"),
+        )
+        attempt_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
+
+        correct = 0
+        total = 0
+        for row in rows:
+            try:
+                quiz_id = int(row.get("quiz_id", 0))
+            except (TypeError, ValueError):
+                continue
+            answer = row.get("answer", "") or ""
+            try:
+                score = int(row.get("correct", "0"))
+            except (TypeError, ValueError):
+                score = 0
+            try:
+                response_time = float(row.get("response_time_s", "0") or 0.0)
+            except (TypeError, ValueError):
+                response_time = 0.0
+
+            con.execute(
+                """
+                INSERT INTO response
+                    (student_id, attempt_id, quiz_id, answer, score, response_time_s)
+                VALUES (?,?,?,?,?,?)
+                """,
+                (student_id, attempt_id, quiz_id, answer, score, response_time),
+            )
+            total += 1
+            correct += score
+
+        score_pct = round(100 * correct / total, 1) if total else 0.0
+        con.execute(
+            """
+            UPDATE attempt
+               SET finished_at=datetime('now'),
+                   items_total=?,
+                   items_correct=?,
+                   score_pct=?
+             WHERE attempt_id=?
+            """,
+            (total, correct, score_pct, attempt_id),
+        )
+        created += 1
+
+    con.commit()
+    con.close()
+    print(f"[OK] Seeded {created} first attempts. Default student password = {DEFAULT_PW}")
+
+
+if __name__ == "__main__":
+    main()
 
EOF
)