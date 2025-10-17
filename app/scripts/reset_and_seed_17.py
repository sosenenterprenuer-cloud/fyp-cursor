import json
import os
import random
import re
import sqlite3
from datetime import datetime

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("Asia/Kuala_Lumpur")

    def now_str() -> str:
        return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
except Exception:  # pragma: no cover - fallback
    def now_str() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

DB = os.getenv("PLA_DB", os.path.join(os.path.dirname(__file__), "..", "pla.db"))
DB = os.path.abspath(DB)

NAMES = [
    "MOHAMED AIMAN",
    "MUHAMMAD FARHAN ADDREEN BIN SARRAFIAN",
    "NG EN JI",
    "MUHAMMAD MUZAMMIL BIN SALIM",
    "NATALIE CHANG PUI SHAN",
    "LAVANESS A/L SRITHAR",
    "NUR LIYANA BINTI RAMLI",
    "TEE KA HONG",
    "MUHAMMAD AFIQ SHADIQI BIN ZAWAWI",
    "SUKANTHAN A/L SURESH",
    "SRITHARAN A/L RAGU",
    "NUR BATRISYIA BINTI ZOOL HILMI",
    "ANIS AKMA SOFEA BINTI AZMAN",
    "JEMMY O'VEINNEDDICT BULOT",
    "AMANDA FLORA JENOS",
    "SITI FARAH ERLIYANA BINTI MOHD HAIRUL NIZAM",
    "SHARON YEO",
]


def slug_email(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9\s]", " ", name)
    parts = [p for p in base.lower().split() if p]
    if not parts:
        parts = ["student"]
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else "lct"
    return f"{first}.{last}@lct.edu"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS student (
            student_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS lecturer (
            lecturer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quiz (
            quiz_id INTEGER PRIMARY KEY,
            question TEXT NOT NULL,
            options_text TEXT,
            correct_answer TEXT NOT NULL,
            two_category TEXT,
            explanation TEXT
        );

        CREATE TABLE IF NOT EXISTS attempt (
            attempt_id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            nf_scope TEXT,
            started_at TEXT,
            finished_at TEXT,
            items_total INTEGER DEFAULT 0,
            items_correct INTEGER DEFAULT 0,
            score_pct REAL DEFAULT 0,
            source TEXT DEFAULT 'live',
            FOREIGN KEY(student_id) REFERENCES student(student_id)
        );

        CREATE TABLE IF NOT EXISTS response (
            response_id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            attempt_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            answer TEXT,
            score INTEGER DEFAULT 0,
            response_time_s REAL DEFAULT 0,
            FOREIGN KEY(student_id) REFERENCES student(student_id),
            FOREIGN KEY(attempt_id) REFERENCES attempt(attempt_id),
            FOREIGN KEY(quiz_id) REFERENCES quiz(quiz_id)
        );

        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT,
            FOREIGN KEY(student_id) REFERENCES student(student_id)
        );
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(quiz)")}
    if "two_category" not in cols:
        cur.execute("ALTER TABLE quiz ADD COLUMN two_category TEXT")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(attempt)")}
    if "source" not in cols:
        cur.execute("ALTER TABLE attempt ADD COLUMN source TEXT DEFAULT 'live'")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(response)")}
    if "response_time_s" not in cols:
        cur.execute("ALTER TABLE response ADD COLUMN response_time_s REAL DEFAULT 0")
    conn.commit()


def wipe_student_data(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("DELETE FROM response")
    cur.execute("DELETE FROM attempt")
    cur.execute("DELETE FROM feedback")
    cur.execute("DELETE FROM student")
    conn.commit()


def upsert_lecturer(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT lecturer_id FROM lecturer WHERE email=?",
        ("admin@lct.edu",),
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO lecturer(name, email, password_hash) VALUES (?,?,?)",
            ("Admin Lecturer", "admin@lct.edu", ""),
        )
        conn.commit()


def get_quiz_bank(conn: sqlite3.Connection) -> dict[int, str] | None:
    total = conn.execute("SELECT COUNT(*) AS n FROM quiz").fetchone()["n"]
    if total != 30:
        print(
            "[WARN] quiz bank count is",
            total,
            "(expected 30). Aborting seed to avoid inconsistent state.",
        )
        return None
    rows = conn.execute(
        "SELECT quiz_id, correct_answer FROM quiz ORDER BY quiz_id"
    ).fetchall()
    return {row["quiz_id"]: row["correct_answer"] for row in rows}


def make_password_hash(password: str) -> str:
    return password


def seed_students_and_attempts(conn: sqlite3.Connection) -> bool:
    quiz_map = get_quiz_bank(conn)
    if not quiz_map:
        return False
    rng = random.Random(1073)
    emails: set[str] = set()
    for idx, name in enumerate(NAMES, start=1):
        email = slug_email(name)
        if email in emails:
            base, domain = email.split("@", 1)
            suffix = 2
            while f"{base}{suffix}@{domain}" in emails:
                suffix += 1
            email = f"{base}{suffix}@{domain}"
        emails.add(email)
        password = "Student123!"
        conn.execute(
            "INSERT INTO student(name, email, password_hash) VALUES (?,?,?)",
            (name, email, make_password_hash(password)),
        )
        student_id = conn.execute(
            "SELECT student_id FROM student WHERE email=?",
            (email,),
        ).fetchone()["student_id"]
        started = now_str()
        cur = conn.execute(
            "INSERT INTO attempt(student_id, nf_scope, started_at, source) VALUES (?,?,?,?)",
            (student_id, "30Q mixed", started, "live"),
        )
        attempt_id = cur.lastrowid
        items_total = 0
        items_correct = 0
        for quiz_id, correct in quiz_map.items():
            items_total += 1
            prob = 0.60 + (0.35 * ((idx % 7) / 6.0))
            is_correct = 1 if rng.random() < prob else 0
            if is_correct:
                answer = correct
            else:
                answer = rng.choice([opt for opt in ["A", "B", "C", "D"] if opt != correct])
            response_time = round(rng.uniform(8, 22), 1)
            conn.execute(
                """
                INSERT INTO response(student_id, attempt_id, quiz_id, answer, score, response_time_s)
                VALUES (?,?,?,?,?,?)
                """,
                (student_id, attempt_id, quiz_id, answer, is_correct, response_time),
            )
            items_correct += is_correct
        score_pct = round(100.0 * items_correct / max(items_total, 1), 1)
        conn.execute(
            """
            UPDATE attempt
               SET finished_at=?, items_total=?, items_correct=?, score_pct=?
             WHERE attempt_id=?
            """,
            (now_str(), items_total, items_correct, score_pct, attempt_id),
        )
        print(
            f"[SEEDED] {name} <{email}> :: attempt {attempt_id} :: {items_correct}/{items_total} = {score_pct}%"
        )
    conn.commit()
    print("\nLogin for all students: password = Student123!")
    return True


def main() -> None:
    print("[DB]", DB)
    conn = connect()
    ensure_tables(conn)
    upsert_lecturer(conn)
    wipe_student_data(conn)
    ok = seed_students_and_attempts(conn)
    if ok:
        print("\nDONE. 17 students seeded with one attempt each.")
    else:
        print("\nABORT. Fix quiz bank to have exactly 30 questions, then rerun.")
    conn.close()


if __name__ == "__main__":
    main()
