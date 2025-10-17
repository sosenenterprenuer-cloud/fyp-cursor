import os; print("PLA_DB =", os.getenv("PLA_DB", "pla.db"))
print("CWD    =", os.getcwd())


import os, sqlite3
from werkzeug.security import generate_password_hash

DB = os.getenv("PLA_DB", "pla.db")
email = "admin@lct.edu"
name = "Admin Lecturer"
# Change if you want; this is the initial lecturer password:
plain = "Admin123!"
pw = generate_password_hash(plain)

con = sqlite3.connect(DB)
con.execute("PRAGMA foreign_keys=ON")

# Create table if missing
con.execute("""
CREATE TABLE IF NOT EXISTS lecturer (
  lecturer_id   INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL
)
""")

# Seed account if missing
row = con.execute("SELECT lecturer_id FROM lecturer WHERE lower(email)=lower(?)", (email,)).fetchone()
if not row:
    con.execute("INSERT INTO lecturer (name,email,password_hash) VALUES (?,?,?)",
                (name, email, pw))
    print(f"[SEED] Lecturer created: {email} / {plain}")
else:
    print("[SEED] Lecturer already exists:", email)

con.commit(); con.close()
print("[OK] lecturer table present.")


