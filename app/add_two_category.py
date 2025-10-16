import os, sqlite3
p = os.getenv('PLA_DB', 'pla.db')
con = sqlite3.connect(p)
con.execute("ALTER TABLE quiz ADD COLUMN two_category TEXT")
con.commit(); con.close()
print("two_category added")
