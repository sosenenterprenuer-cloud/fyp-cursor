import glob
import os
import sqlite3

from app.db_utils import ensure_db_path

con = sqlite3.connect(str(ensure_db_path(os.getenv("PLA_DB"))))
for p in sorted(glob.glob("migrations/*.sql")):
    with open(p,"r",encoding="utf-8") as f: con.executescript(f.read())
con.commit(); con.close()
print("Migrations applied.")



