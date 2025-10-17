 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/scripts/clear_quiz_submissions.py b/scripts/clear_quiz_submissions.py
new file mode 100644
index 0000000000000000000000000000000000000000..03a52c76ca9ca5970f493872e4199fdce2a4a17d
--- /dev/null
+++ b/scripts/clear_quiz_submissions.py
@@ -0,0 +1,52 @@
+"""Utility to purge quiz submission data for a clean slate."""
+from __future__ import annotations
+
+import os
+import sqlite3
+
+
+TARGET_TABLES = [
+    "response",
+    "attempt",
+    "bad_response",
+    "feedback",
+]
+
+
+def table_exists(cur: sqlite3.Cursor, table: str) -> bool:
+    row = cur.execute(
+        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
+    ).fetchone()
+    return row is not None
+
+
+def clear_table(cur: sqlite3.Cursor, table: str) -> int:
+    if not table_exists(cur, table):
+        print(f"[SKIP] Table '{table}' does not exist.")
+        return 0
+    deleted = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
+    cur.execute(f"DELETE FROM {table}")
+    print(f"[CLEAR] {table}: removed {deleted} row(s).")
+    return deleted
+
+
+def main() -> None:
+    db_path = os.getenv("PLA_DB", "pla.db")
+    conn = sqlite3.connect(db_path)
+    try:
+        conn.row_factory = sqlite3.Row
+        cur = conn.cursor()
+        cur.execute("PRAGMA foreign_keys=ON")
+
+        total_removed = 0
+        for table in TARGET_TABLES:
+            total_removed += clear_table(cur, table)
+
+        conn.commit()
+        print(f"[DONE] Total rows removed: {total_removed}.")
+    finally:
+        conn.close()
+
+
+if __name__ == "__main__":
+    main()
 
EOF
)