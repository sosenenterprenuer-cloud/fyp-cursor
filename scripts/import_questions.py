import csv, json, os, sqlite3, sys
REQ = ["q_no","question","options_text","correct_answer","nf_level","concept_tag","explanation","two_category"]
DB = os.getenv("PLA_DB","pla.db")
def fail(m): print("[ERROR]", m); sys.exit(1)

if len(sys.argv)!=2: fail("Usage: python scripts/import_questions.py quiz.csv")
path=sys.argv[1]
if not os.path.exists(path): fail(f"Missing {path}")

with open(path, newline="", encoding="utf-8-sig") as f:
    rdr=csv.DictReader(f)
    if rdr.fieldnames!=REQ: fail(f"Headers must be {REQ}. Got {rdr.fieldnames}")
    rows=list(rdr)

# Validate: correct_answer ∈ options_text
for i,r in enumerate(rows, start=2):
    try: opts = json.loads(r["options_text"])
    except Exception: fail(f"Row {i}: options_text invalid JSON")
    ca = (r["correct_answer"] or "").strip()
    if ca and ca not in [str(x) for x in opts]:
        fail(f"Row {i}: correct_answer not in options_text")

con=sqlite3.connect(DB); con.execute("PRAGMA foreign_keys=ON")
ins="""INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category)
       VALUES (?,?,?,?,?,?,?)"""
for r in rows:
    con.execute(ins, (r["question"], r["options_text"], r["correct_answer"],
                      r["nf_level"], r["concept_tag"], r["explanation"], r["two_category"]))
con.commit(); con.close()
print(f"[OK] Imported {len(rows)} questions.")



