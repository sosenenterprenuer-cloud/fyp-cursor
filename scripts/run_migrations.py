import sqlite3, os, glob
con = sqlite3.connect(os.getenv("PLA_DB","pla.db"))
for p in sorted(glob.glob("migrations/*.sql")):
    with open(p,"r",encoding="utf-8") as f: con.executescript(f.read())
con.commit(); con.close()
print("Migrations applied.")



