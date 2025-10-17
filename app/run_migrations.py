import glob
import os
import sqlite3
import sys

if __package__:
    from .db_utils import ensure_db_path
else:
    sys.path.insert(0, os.path.dirname(__file__))
    from db_utils import ensure_db_path

con = sqlite3.connect(str(ensure_db_path(os.getenv("PLA_DB"))))
for p in sorted(glob.glob("migrations/*.sql")):
    with open(p,"r",encoding="utf-8") as f: con.executescript(f.read())
con.commit(); con.close()
print("Migrations applied.")



