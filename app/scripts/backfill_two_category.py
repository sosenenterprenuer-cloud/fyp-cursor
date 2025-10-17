import os
import sqlite3
import sys

if __package__:
    from ..db_utils import ensure_db_path
else:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from db_utils import ensure_db_path

db_path = str(ensure_db_path(os.getenv('PLA_DB')))
print("DB:", os.path.abspath(db_path))
con = sqlite3.connect(db_path)

# 1) Add column if missing
cols = [r[1] for r in con.execute("PRAGMA table_info(quiz)")]
if "two_category" not in cols:
    con.execute("ALTER TABLE quiz ADD COLUMN two_category TEXT")
    print("Added column: two_category")
else:
    print("Column already exists: two_category")

# 2) Backfill values (no CSV needed)
#   - Put obvious normalization items into 'Normalization & Dependencies'
#   - Everything else defaults to 'Data Modeling & DBMS Fundamentals'
con.execute("""
UPDATE quiz
SET two_category = 'Normalization & Dependencies'
WHERE (two_category IS NULL OR TRIM(two_category) = '')
  AND (
    question LIKE '%functional dependenc%' OR
    question LIKE '%1NF%' OR
    question LIKE '%2NF%' OR
    question LIKE '%3NF%' OR
    question LIKE '%partial dependenc%' OR
    question LIKE '%transitive dependenc%' OR
    question LIKE '%atomic%'
  )
""")
con.execute("""
UPDATE quiz
SET two_category = 'Data Modeling & DBMS Fundamentals'
WHERE (two_category IS NULL OR TRIM(two_category) = '')
""")

con.commit()

filled = con.execute("SELECT COUNT(*) FROM quiz WHERE two_category IS NOT NULL AND TRIM(two_category)<>''").fetchone()[0]
total  = con.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
print(f"Backfill done. Filled: {filled} / Total: {total}")

con.close()
