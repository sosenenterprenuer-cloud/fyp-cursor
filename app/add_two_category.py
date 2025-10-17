import os
import sqlite3
import sys

if __package__:
    from .db_utils import ensure_db_path
else:
    sys.path.insert(0, os.path.dirname(__file__))
    from db_utils import ensure_db_path

con = sqlite3.connect(str(ensure_db_path(os.getenv('PLA_DB'))))
con.execute("ALTER TABLE quiz ADD COLUMN two_category TEXT")
con.commit(); con.close()
print("two_category added")
