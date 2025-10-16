import os, sqlite3

db = os.getenv('PLA_DB', 'pla.db')
print("DB:", os.path.abspath(db))
con = sqlite3.connect(db)

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
