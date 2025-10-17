 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/scripts/backup_db.py b/scripts/backup_db.py
new file mode 100644
index 0000000000000000000000000000000000000000..1d798e4d7367515034076952a88e4b0542a79039
--- /dev/null
+++ b/scripts/backup_db.py
@@ -0,0 +1,22 @@
+"""Create a timestamped backup of the PLA database."""
+
+import datetime as dt
+import os
+import shutil
+
+
+def main() -> None:
+    db_path = os.getenv("PLA_DB", "pla.db").strip().strip('"').strip("'")
+    db_path = os.path.abspath(db_path)
+    if not os.path.exists(db_path):
+        raise SystemExit(f"Database not found at {db_path}")
+
+    os.makedirs("backups", exist_ok=True)
+    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
+    target = os.path.join("backups", f"pla_{stamp}.db")
+    shutil.copy2(db_path, target)
+    print(f"Backup created: {target}")
+
+
+if __name__ == "__main__":
+    main()
 
EOF
)