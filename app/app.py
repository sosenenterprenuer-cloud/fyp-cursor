import json
import os
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("Asia/Kuala_Lumpur")

    def now_str() -> str:
        return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
except Exception:  # pragma: no cover - fallback for platforms without zoneinfo
    def now_str() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

TOPIC_FUNDAMENTALS = "Data Modeling & DBMS Fundamentals"
TOPIC_NORMALIZATION = "Normalization & Dependencies"
TOPICS = {TOPIC_FUNDAMENTALS, TOPIC_NORMALIZATION}

PLA_DB = os.environ.get("PLA_DB", "pla.db")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")
app.config["JSON_SORT_KEYS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_database_path() -> str:
    if os.path.isabs(PLA_DB):
        return PLA_DB
    return str(Path(__file__).resolve().parent / PLA_DB)


def get_db() -> sqlite3.Connection:
    if "db" in g:
        return g.db

    needs_reset = os.environ.get("PLA_RESET") == "1"
    db_path = get_database_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    if needs_reset and Path(db_path).exists():
        Path(db_path).unlink()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    ensure_schema(conn)
    ensure_columns(conn)
    seed_default_lecturer(conn)
    ensure_default_quiz(conn)
    purge_legacy_quiz(conn)
    auto_tag_quiz(conn)

    g.db = conn
    return conn


@app.teardown_appcontext
def close_db(_: Any) -> None:
    conn: Optional[sqlite3.Connection] = g.pop("db", None)
    if conn is not None:
        conn.close()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS student (
            student_id    INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS lecturer (
            lecturer_id   INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quiz (
            quiz_id        INTEGER PRIMARY KEY,
            question       TEXT NOT NULL,
            options_text   TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            two_category   TEXT,
            explanation    TEXT
        );

        CREATE TABLE IF NOT EXISTS attempt (
            attempt_id    INTEGER PRIMARY KEY,
            student_id    INTEGER NOT NULL,
            nf_scope      TEXT,
            started_at    TEXT NOT NULL,
            finished_at   TEXT,
            items_total   INTEGER DEFAULT 0,
            items_correct INTEGER DEFAULT 0,
            score_pct     REAL DEFAULT 0.0,
            source        TEXT DEFAULT 'live',
            FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS response (
            response_id     INTEGER PRIMARY KEY,
            student_id      INTEGER NOT NULL,
            attempt_id      INTEGER NOT NULL,
            quiz_id         INTEGER NOT NULL,
            answer          TEXT,
            score           INTEGER DEFAULT 0,
            response_time_s REAL,
            FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE,
            FOREIGN KEY (attempt_id) REFERENCES attempt(attempt_id) ON DELETE CASCADE,
            FOREIGN KEY (quiz_id) REFERENCES quiz(quiz_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id INTEGER PRIMARY KEY,
            student_id  INTEGER NOT NULL,
            rating      INTEGER NOT NULL,
            comment     TEXT,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()


def ensure_columns(conn: sqlite3.Connection) -> None:
    def ensure(table: str, column: str, ddl: str) -> None:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(ddl)
            conn.commit()

    ensure("quiz", "two_category", "ALTER TABLE quiz ADD COLUMN two_category TEXT")
    ensure("attempt", "source", "ALTER TABLE attempt ADD COLUMN source TEXT DEFAULT 'live'")
    ensure("response", "response_time_s", "ALTER TABLE response ADD COLUMN response_time_s REAL")


DEFAULT_QUESTIONS: List[Dict[str, Any]] = [
    {
        "question": "Which attribute uniquely identifies each record in an entity?",
        "options": [
            "Foreign key",
            "Composite attribute",
            "Primary key",
            "Candidate key that is optional",
        ],
        "answer": "Primary key",
        "explanation": "A primary key uniquely identifies each record and cannot be null.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "What does an Entity-Relationship diagram primarily describe?",
        "options": [
            "Procedural logic",
            "User interface layouts",
            "Data entities and their relationships",
            "Physical storage blocks",
        ],
        "answer": "Data entities and their relationships",
        "explanation": "ER diagrams capture how entities relate in a conceptual data model.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "Which relationship type allows multiple instances on both sides?",
        "options": [
            "One-to-one",
            "Many-to-many",
            "Self-referencing",
            "Unary",
        ],
        "answer": "Many-to-many",
        "explanation": "Many-to-many means many rows in one entity relate to many rows in another.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "In a logical data model, what does cardinality express?",
        "options": [
            "Optionality of attributes",
            "Storage requirements",
            "Number of entity instances in a relationship",
            "Security privileges",
        ],
        "answer": "Number of entity instances in a relationship",
        "explanation": "Cardinality conveys how many instances of one entity relate to another.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "Which key enforces referential integrity between related tables?",
        "options": [
            "Surrogate key",
            "Foreign key",
            "Composite primary key",
            "Alternate key",
        ],
        "answer": "Foreign key",
        "explanation": "Foreign keys reference a primary key in another table to enforce relationships.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "What is the main deliverable of conceptual data modeling?",
        "options": [
            "Normalized table structures",
            "ETL pipeline diagrams",
            "Business process maps",
            "High-level entity definitions",
        ],
        "answer": "High-level entity definitions",
        "explanation": "Conceptual modeling focuses on describing entities and relationships at a high level.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "Which type of attribute can be broken down into smaller attributes?",
        "options": [
            "Derived attribute",
            "Simple attribute",
            "Composite attribute",
            "Identifier attribute",
        ],
        "answer": "Composite attribute",
        "explanation": "Composite attributes consist of subcomponents like First Name and Last Name.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "When translating an ER diagram to tables, what becomes a foreign key?",
        "options": [
            "Each weak entity",
            "Each relationship identifier",
            "Each referencing entity's identifier",
            "Each attribute",
        ],
        "answer": "Each referencing entity's identifier",
        "explanation": "Foreign keys originate from the identifying relationship between entities.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "Which constraint ensures that no duplicate rows exist for a key?",
        "options": [
            "Check constraint",
            "Unique constraint",
            "Default constraint",
            "Cascade constraint",
        ],
        "answer": "Unique constraint",
        "explanation": "Unique constraints enforce uniqueness for a column or set of columns.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "What is the purpose of a surrogate key?",
        "options": [
            "Replace a missing business key",
            "Encrypt sensitive data",
            "Store audit information",
            "Track concurrency",
        ],
        "answer": "Replace a missing business key",
        "explanation": "Surrogate keys provide a synthetic identifier when a natural key is not suitable.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "Which phase of database design maps entities to specific columns and data types?",
        "options": [
            "Conceptual modeling",
            "Physical design",
            "Logical modeling",
            "Requirements gathering",
        ],
        "answer": "Physical design",
        "explanation": "Physical design decides data types, indexes, and storage after logical modeling.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "What does the term 'schema' refer to in a database context?",
        "options": [
            "Execution plan",
            "Overall structure of tables and relationships",
            "Runtime configuration",
            "Single table row",
        ],
        "answer": "Overall structure of tables and relationships",
        "explanation": "A schema describes how data is organized within the database.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "Which component of a relational table defines the type of data stored?",
        "options": [
            "Row",
            "Constraint",
            "Column",
            "Trigger",
        ],
        "answer": "Column",
        "explanation": "Columns define data attributes and their domains in a table.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "Which modeling technique is most associated with relational databases?",
        "options": [
            "Document modeling",
            "Graph modeling",
            "Entity-relationship modeling",
            "Key-value modeling",
        ],
        "answer": "Entity-relationship modeling",
        "explanation": "ER modeling is the foundation for relational schema design.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "Which term describes rules about how data can be inserted or updated?",
        "options": [
            "Data governance",
            "Integrity constraints",
            "Caching strategy",
            "Transaction isolation",
        ],
        "answer": "Integrity constraints",
        "explanation": "Integrity constraints prevent invalid data from being stored.",
        "topic": TOPIC_FUNDAMENTALS,
    },
    {
        "question": "What is the primary goal of normalization?",
        "options": [
            "Increase redundancy",
            "Reduce update anomalies",
            "Encrypt data",
            "Create backups",
        ],
        "answer": "Reduce update anomalies",
        "explanation": "Normalization organizes data to avoid anomalies caused by redundancy.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "Which normal form removes repeating groups?",
        "options": [
            "First normal form",
            "Second normal form",
            "Third normal form",
            "Boyce-Codd normal form",
        ],
        "answer": "First normal form",
        "explanation": "1NF requires atomic values, eliminating repeating groups and arrays.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "A partial dependency violates which normal form?",
        "options": [
            "1NF",
            "2NF",
            "3NF",
            "BCNF",
        ],
        "answer": "2NF",
        "explanation": "2NF removes partial dependencies on a composite primary key.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "What is a transitive dependency?",
        "options": [
            "Dependency on part of a key",
            "Dependency between non-key attributes",
            "Dependency on foreign keys",
            "Dependency on surrogate keys",
        ],
        "answer": "Dependency between non-key attributes",
        "explanation": "Transitive dependencies occur when non-key attributes depend on other non-key attributes.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "Which normal form eliminates transitive dependencies?",
        "options": [
            "1NF",
            "2NF",
            "3NF",
            "5NF",
        ],
        "answer": "3NF",
        "explanation": "Third normal form eliminates transitive dependencies to ensure non-key attributes depend only on keys.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "Boyce-Codd normal form is stricter than which normal form?",
        "options": [
            "1NF",
            "2NF",
            "3NF",
            "4NF",
        ],
        "answer": "3NF",
        "explanation": "BCNF strengthens 3NF by requiring every determinant to be a candidate key.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "Which anomaly is prevented by normalization?",
        "options": [
            "Network latency",
            "Update anomaly",
            "Power failure",
            "Deadlock",
        ],
        "answer": "Update anomaly",
        "explanation": "Update anomalies arise from redundant data and are mitigated by normalization.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "What does 4NF specifically address?",
        "options": [
            "Partial dependencies",
            "Transitive dependencies",
            "Multivalued dependencies",
            "Join dependencies",
        ],
        "answer": "Multivalued dependencies",
        "explanation": "Fourth normal form removes unwanted multivalued dependencies.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "Which dependency requires decomposition for BCNF compliance?",
        "options": [
            "Determinant is a candidate key",
            "Determinant is not a candidate key",
            "Determinant includes a foreign key",
            "Determinant is a surrogate key",
        ],
        "answer": "Determinant is not a candidate key",
        "explanation": "BCNF insists that every determinant be a candidate key, otherwise decompose.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "What is the result of over-normalization?",
        "options": [
            "Eliminated joins",
            "Improved caching",
            "Excessive table joins",
            "Increased anomalies",
        ],
        "answer": "Excessive table joins",
        "explanation": "Too much normalization can lead to many joins, impacting performance.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "Which functional dependency notation is correct?",
        "options": [
            "A ->> B",
            "A -> B",
            "A => B",
            "A <> B",
        ],
        "answer": "A -> B",
        "explanation": "Functional dependencies are written as determinants leading to dependents (A -> B).",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "Which normal form requires every non-trivial functional dependency to have a superkey determinant?",
        "options": [
            "2NF",
            "3NF",
            "BCNF",
            "1NF",
        ],
        "answer": "BCNF",
        "explanation": "BCNF demands each determinant be a superkey, strengthening 3NF.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "What does lossless decomposition ensure?",
        "options": [
            "No null values appear",
            "Decomposed tables can be joined without losing data",
            "Each table has the same number of rows",
            "Indexes are preserved",
        ],
        "answer": "Decomposed tables can be joined without losing data",
        "explanation": "Lossless decomposition guarantees the original relation is recoverable by join.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "Which test determines if a decomposition is dependency preserving?",
        "options": [
            "Armstrong's axioms",
            "Closure of functional dependencies",
            "Candidate key analysis",
            "BCNF test",
        ],
        "answer": "Closure of functional dependencies",
        "explanation": "Checking dependency preservation relies on computing closures of FDs in decomposed schemas.",
        "topic": TOPIC_NORMALIZATION,
    },
    {
        "question": "In normalization, what is the attribute set on the left of an FD called?",
        "options": [
            "Dependent",
            "Key",
            "Determinant",
            "Projection",
        ],
        "answer": "Determinant",
        "explanation": "The determinant functionally determines attributes on the right side of the dependency.",
        "topic": TOPIC_NORMALIZATION,
    },
]

def ensure_default_quiz(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
    if existing >= 30:
        return

    conn.execute("DELETE FROM quiz")
    for item in DEFAULT_QUESTIONS:
        conn.execute(
            """
            INSERT INTO quiz (question, options_text, correct_answer, two_category, explanation)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                item["question"],
                json.dumps(item["options"]),
                item["answer"],
                item["topic"],
                item["explanation"],
            ),
        )
    conn.commit()


def seed_default_lecturer(conn: sqlite3.Connection) -> None:
    lecturer = conn.execute("SELECT lecturer_id FROM lecturer LIMIT 1").fetchone()
    if lecturer:
        return
    password_hash = generate_password_hash("Admin123!")
    conn.execute(
        "INSERT INTO lecturer (name, email, password_hash) VALUES (?, ?, ?)",
        ("Lead Lecturer", "admin@lct.edu", password_hash),
    )
    conn.commit()


def purge_legacy_quiz(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT quiz_id, two_category FROM quiz").fetchall()
    legacy_ids = [row[0] for row in rows if row[1] and row[1] not in TOPICS]
    if legacy_ids:
        conn.executemany("DELETE FROM response WHERE quiz_id = ?", [(qid,) for qid in legacy_ids])
        conn.executemany("DELETE FROM quiz WHERE quiz_id = ?", [(qid,) for qid in legacy_ids])
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
    if total != 30:
        print(f"[WARN] Expected 30 quiz items after cleanup, found {total}.")


def auto_tag_quiz(conn: sqlite3.Connection) -> None:
    normalization_words = [
        "normal",
        "normalization",
        "dependency",
        "functional",
        "boyce",
        "bc nf",
        "bc_nf",
        "bcnf",
        "multivalued",
        "anomaly",
    ]
    fundamentals_words = [
        "entity",
        "relationship",
        "schema",
        "model",
        "primary key",
        "foreign key",
        "cardinality",
        "attribute",
        "table",
        "constraint",
    ]

    rows = conn.execute("SELECT quiz_id, question, explanation, two_category FROM quiz").fetchall()
    for row in rows:
        if row[3] in TOPICS:
            continue
        text = " ".join(filter(None, [row[1], row[2]])).lower()
        hits_normal = any(word in text for word in normalization_words)
        hits_fund = any(word in text for word in fundamentals_words)
        category: Optional[str] = None
        if hits_normal:
            category = TOPIC_NORMALIZATION
        elif hits_fund:
            category = TOPIC_FUNDAMENTALS
        if category:
            conn.execute("UPDATE quiz SET two_category = ? WHERE quiz_id = ?", (category, row[0]))
        else:
            print(f"[INFO] Unable to auto-tag quiz {row[0]}: {row[1][:40]}...")
    conn.commit()


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------

def login_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session or "role" not in session:
            flash("Please log in to continue.", "warn")
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper


def lecturer_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("role") != "lecturer":
            flash("Lecturer access required.", "warn")
            return redirect(url_for("dashboard"))
        return func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def create_attempt(student_id: int) -> int:
    conn = get_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    cursor = conn.execute(
        """
        INSERT INTO attempt (student_id, nf_scope, started_at, items_total, items_correct, score_pct, source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (student_id, None, now, 0, 0, 0.0, "live"),
    )
    conn.commit()
    return int(cursor.lastrowid)


def fetch_quiz_order() -> Tuple[List[int], Dict[str, List[Dict[str, str]]]]:
    conn = get_db()
    rows = conn.execute(
        "SELECT quiz_id, options_text FROM quiz ORDER BY quiz_id"
    ).fetchall()
    quiz_ids = [row[0] for row in rows]
    if len(quiz_ids) != 30:
        raise RuntimeError("Quiz bank must contain exactly 30 questions.")
    random.shuffle(quiz_ids)

    option_map: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        options = json.loads(row["options_text"])
        shuffled = options[:]
        random.shuffle(shuffled)
        mapped: List[Dict[str, str]] = []
        for idx, text in enumerate(shuffled):
            mapped.append({"key": chr(ord("A") + idx), "text": text})
        option_map[str(row["quiz_id"])] = mapped
    return quiz_ids, option_map


def current_student_id() -> Optional[int]:
    if session.get("role") == "student":
        return session.get("user_id")
    return None


def load_attempt_state(student_id: int) -> Dict[str, Any]:
    state = session.get("quiz_state")
    if not state or state.get("student_id") != student_id:
        attempt_id = create_attempt(student_id)
        order, options = fetch_quiz_order()
        state = {
            "student_id": student_id,
            "attempt_id": attempt_id,
            "order": order,
            "options": options,
            "started": datetime.utcnow().isoformat(),
        }
        session["quiz_state"] = state
    else:
        attempt = get_db().execute(
            "SELECT finished_at FROM attempt WHERE attempt_id = ?",
            (state["attempt_id"],),
        ).fetchone()
        if attempt and attempt["finished_at"]:
            attempt_id = create_attempt(student_id)
            order, options = fetch_quiz_order()
            state = {
                "student_id": student_id,
                "attempt_id": attempt_id,
                "order": order,
                "options": options,
                "started": datetime.utcnow().isoformat(),
            }
            session["quiz_state"] = state
    session.modified = True
    return state

# ---------------------------------------------------------------------------
# Routes - authentication
# ---------------------------------------------------------------------------


@app.route("/")
def index() -> Any:
    role = session.get("role")
    if role == "student":
        return redirect(url_for("dashboard"))
    if role == "lecturer":
        return redirect(url_for("admin_home"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login() -> Any:
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()

        student = conn.execute("SELECT * FROM student WHERE lower(email) = ?", (email,)).fetchone()
        if student and check_password_hash(student["password_hash"], password):
            session.clear()
            session["user_id"] = student["student_id"]
            session["role"] = "student"
            session["user_name"] = student["name"]
            latest = conn.execute(
                """
                SELECT attempt_id FROM attempt
                WHERE student_id = ? AND finished_at IS NOT NULL
                ORDER BY datetime(finished_at) DESC
                LIMIT 1
                """,
                (student["student_id"],),
            ).fetchone()
            if latest:
                return redirect(url_for("review", attempt_id=latest["attempt_id"]))
            return redirect(url_for("quiz"))

        lecturer = conn.execute("SELECT * FROM lecturer WHERE lower(email) = ?", (email,)).fetchone()
        if lecturer and check_password_hash(lecturer["password_hash"], password):
            session.clear()
            session["user_id"] = lecturer["lecturer_id"]
            session["role"] = "lecturer"
            session["user_name"] = lecturer["name"]
            return redirect(url_for("admin_home"))

        flash("Invalid credentials. Please try again.", "warn")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register() -> Any:
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not name or not email or not password:
            flash("All fields are required.", "warn")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "warn")
            return render_template("register.html")

        conn = get_db()
        existing = conn.execute("SELECT 1 FROM student WHERE lower(email) = ?", (email,)).fetchone()
        if existing:
            flash("Email already registered.", "warn")
            return render_template("register.html")

        conn.execute(
            "INSERT INTO student (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout() -> Any:
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Student experience
# ---------------------------------------------------------------------------


@app.route("/quiz")
@login_required
def quiz() -> Any:
    if session.get("role") != "student":
        return redirect(url_for("admin_home"))
    student_id = session["user_id"]
    load_attempt_state(student_id)
    return render_template("quiz.html")


@app.route("/api/quiz_progressive")
@login_required
def api_quiz_progressive() -> Any:
    student_id = current_student_id()
    if not student_id:
        return jsonify({"error": "Student session required."}), 400

    state = load_attempt_state(student_id)
    conn = get_db()
    placeholders = ",".join("?" for _ in state["order"])
    rows = conn.execute(
        f"SELECT * FROM quiz WHERE quiz_id IN ({placeholders})",
        tuple(state["order"]),
    ).fetchall()
    quiz_map = {row["quiz_id"]: row for row in rows}

    questions: List[Dict[str, Any]] = []
    for quiz_id in state["order"]:
        row = quiz_map[quiz_id]
        options = state["options"][str(quiz_id)]
        questions.append(
            {
                "quiz_id": quiz_id,
                "question": row["question"],
                "options": options,
                "two_category": row["two_category"],
                "explanation": row["explanation"],
            }
        )
    return jsonify(
        {
            "attempt_id": state["attempt_id"],
            "total_questions": len(questions),
            "questions": questions,
        }
    )


@app.route("/submit", methods=["POST"])
@login_required
def submit_quiz() -> Any:
    student_id = current_student_id()
    if not student_id:
        return jsonify({"error": "Student session required."}), 400

    state = session.get("quiz_state")
    if not state:
        return jsonify({"error": "No active attempt."}), 400

    payload = request.get_json(silent=True) or {}
    answers: Dict[str, Dict[str, Any]] = payload.get("answers", {})
    conn = get_db()

    placeholders = ",".join("?" for _ in state["order"])
    quiz_rows = conn.execute(
        f"SELECT quiz_id, correct_answer FROM quiz WHERE quiz_id IN ({placeholders})",
        tuple(state["order"]),
    ).fetchall()
    quiz_map = {row["quiz_id"]: row for row in quiz_rows}

    attempt_id = state["attempt_id"]
    total_questions = len(state["order"])
    correct = 0
    response_inserts: List[Tuple[Any, ...]] = []

    conn.execute("DELETE FROM response WHERE attempt_id = ?", (attempt_id,))

    for quiz_id in state["order"]:
        quiz_row = quiz_map[quiz_id]
        option_list = state["options"].get(str(quiz_id), [])
        answer_info = answers.get(str(quiz_id)) or {}
        selected_key = answer_info.get("selected")
        response_time = answer_info.get("time")
        if isinstance(response_time, (int, float)):
            response_time_s = float(response_time)
        else:
            response_time_s = None

        selected_text = None
        if selected_key:
            for option in option_list:
                if option["key"] == selected_key:
                    selected_text = option["text"]
                    break

        score = 1 if selected_text and selected_text == quiz_row["correct_answer"] else 0
        if score:
            correct += 1
        response_inserts.append(
            (
                student_id,
                attempt_id,
                quiz_id,
                selected_text,
                score,
                response_time_s,
            )
        )

    conn.executemany(
        """
        INSERT INTO response (student_id, attempt_id, quiz_id, answer, score, response_time_s)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        response_inserts,
    )

    score_pct = round((correct / total_questions) * 100, 2) if total_questions else 0.0
    conn.execute(
        """
        UPDATE attempt
        SET items_total = ?, items_correct = ?, score_pct = ?, finished_at = ?, source = ?
        WHERE attempt_id = ?
        """,
        (
            total_questions,
            correct,
            score_pct,
            datetime.utcnow().isoformat(timespec="seconds"),
            "live",
            attempt_id,
        ),
    )
    conn.commit()

    session.pop("quiz_state", None)
    session.modified = True

    return jsonify({"redirect_url": url_for("review", attempt_id=attempt_id)})


@app.route("/review/<int:attempt_id>")
@login_required
def review(attempt_id: int) -> Any:
    conn = get_db()
    attempt = conn.execute("SELECT * FROM attempt WHERE attempt_id = ?", (attempt_id,)).fetchone()
    if not attempt:
        flash("Attempt not found.", "warn")
        return redirect(url_for("dashboard"))

    role = session.get("role")
    if role == "student" and attempt["student_id"] != session.get("user_id"):
        flash("You cannot access this review.", "warn")
        return redirect(url_for("dashboard"))

    responses = conn.execute(
        """
        SELECT r.*, q.question, q.correct_answer, q.explanation, q.two_category
        FROM response r
        JOIN quiz q ON q.quiz_id = r.quiz_id
        WHERE r.attempt_id = ?
        ORDER BY r.response_id
        """,
        (attempt_id,),
    ).fetchall()

    per_topic: Dict[str, Dict[str, float]] = {topic: {"correct": 0, "total": 0} for topic in TOPICS}
    detailed: List[Dict[str, Any]] = []
    for row in responses:
        topic = row["two_category"] or "Unassigned"
        detailed.append(
            {
                "question": row["question"],
                "answer": row["answer"],
                "correct_answer": row["correct_answer"],
                "score": row["score"],
                "explanation": row["explanation"],
                "topic": topic,
            }
        )
        if topic in per_topic:
            per_topic[topic]["total"] += 1
            per_topic[topic]["correct"] += row["score"]

    per_topic_pct = {
        topic: (round((values["correct"] / values["total"]) * 100, 2) if values["total"] else 0.0)
        for topic, values in per_topic.items()
    }

    best_by_topic = compute_best_topic_scores(conn, attempt["student_id"])
    unlocked = all(best_by_topic.get(topic, 0) >= 100 for topic in TOPICS)

    feedback_flag = request.args.get("feedback") == "1"

    return render_template(
        "review.html",
        attempt=attempt,
        responses=detailed,
        per_topic_pct=per_topic_pct,
        best_by_topic=best_by_topic,
        unlocked=unlocked,
        feedback_flag=feedback_flag,
    )


@app.route("/dashboard")
@login_required
def dashboard() -> Any:
    if session.get("role") != "student":
        return redirect(url_for("admin_home"))

    student_id = session["user_id"]
    conn = get_db()

    history_rows = conn.execute(
        """
        SELECT attempt_id, finished_at, score_pct
        FROM attempt
        WHERE student_id = ? AND finished_at IS NOT NULL
        ORDER BY datetime(finished_at) ASC
        """,
        (student_id,),
    ).fetchall()

    history = list(reversed(history_rows))
    latest_attempt = history[0] if history else None

    chart_labels = [f"A{idx + 1}" for idx, _ in enumerate(history_rows)]
    chart_scores = [round(row["score_pct"] or 0.0, 2) for row in history_rows]

    latest_split = {topic: 0.0 for topic in TOPICS}
    latest_topic_breakdown: List[Dict[str, Any]] = []
    if latest_attempt:
        topic_rows = conn.execute(
            """
            SELECT q.two_category AS topic, SUM(r.score) AS correct, COUNT(*) AS total
            FROM response r
            JOIN quiz q ON q.quiz_id = r.quiz_id
            WHERE r.attempt_id = ?
            GROUP BY q.two_category
            """,
            (latest_attempt["attempt_id"],),
        ).fetchall()
        for row in topic_rows:
            topic = row["topic"]
            total = row["total"] or 0
            correct = row["correct"] or 0
            pct = round((correct / total) * 100, 2) if total else 0.0
            if topic in latest_split:
                latest_split[topic] = pct
            latest_topic_breakdown.append(
                {
                    "topic": topic,
                    "correct": int(correct),
                    "total": int(total),
                    "pct": pct,
                }
            )

    best_by_topic = compute_best_topic_scores(conn, student_id)
    unlocked = all(best_by_topic.get(topic, 0) >= 100 for topic in TOPICS)

    attempt_count = len(history_rows)

    return render_template(
        "dashboard.html",
        latest_attempt=latest_attempt,
        latest_split=latest_split,
        history=history,
        unlocked=unlocked,
        best_by_topic=best_by_topic,
        chart_labels=chart_labels,
        chart_scores=chart_scores,
        latest_topic_breakdown=latest_topic_breakdown,
        attempt_count=attempt_count,
        next_topic_name="Database Development Process",
    )


@app.route("/thanks")
@login_required
def thanks() -> Any:
    if session.get("role") != "student":
        return redirect(url_for("admin_home"))
    return render_template("thanks.html")


@app.route("/api/feedback", methods=["POST"])
@login_required
def api_feedback() -> Any:
    student_id = current_student_id()
    if not student_id:
        return jsonify({"error": "Only students can submit feedback."}), 400

    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    comment = data.get("comment", "").strip()

    try:
        rating_int = int(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "Rating must be between 1 and 5."}), 400

    if rating_int < 1 or rating_int > 5:
        return jsonify({"error": "Rating must be between 1 and 5."}), 400

    conn = get_db()
    conn.execute(
        "INSERT INTO feedback (student_id, rating, comment, created_at) VALUES (?, ?, ?, ?)",
        (student_id, rating_int, comment, datetime.utcnow().isoformat(timespec="seconds")),
    )
    conn.commit()

    latest = conn.execute(
        """
        SELECT attempt_id FROM attempt
        WHERE student_id = ? AND finished_at IS NOT NULL
        ORDER BY datetime(finished_at) DESC
        LIMIT 1
        """,
        (student_id,),
    ).fetchone()
    redirect_url = url_for("dashboard")
    if latest:
        redirect_url = url_for("review", attempt_id=latest["attempt_id"], feedback=1)

    return jsonify({"redirect_url": redirect_url})


def compute_best_topic_scores(conn: sqlite3.Connection, student_id: int) -> Dict[str, float]:
    rows = conn.execute(
        """
        SELECT a.attempt_id, q.two_category AS topic,
               SUM(r.score) AS correct,
               COUNT(*) AS total
        FROM attempt a
        JOIN response r ON r.attempt_id = a.attempt_id
        JOIN quiz q ON q.quiz_id = r.quiz_id
        WHERE a.student_id = ?
        GROUP BY a.attempt_id, q.two_category
        """,
        (student_id,),
    ).fetchall()

    best: Dict[str, float] = {topic: 0.0 for topic in TOPICS}
    for row in rows:
        topic = row["topic"]
        if topic in best and row["total"]:
            pct = round((row["correct"] / row["total"]) * 100, 2)
            if pct > best[topic]:
                best[topic] = pct
    return best


# ---------------------------------------------------------------------------
# Lecturer experience
# ---------------------------------------------------------------------------


@app.route("/admin")
@login_required
@lecturer_required
def admin_home() -> Any:
    conn = get_db()
    counts = {
        "students": int(conn.execute("SELECT COUNT(*) FROM student").fetchone()[0]),
        "attempts": int(conn.execute("SELECT COUNT(*) FROM attempt").fetchone()[0]),
        "responses": int(conn.execute("SELECT COUNT(*) FROM response").fetchone()[0]),
        "attempts_with_responses": int(
            conn.execute("SELECT COUNT(DISTINCT attempt_id) FROM response").fetchone()[0]
        ),
    }

    accuracy_rows = conn.execute(
        """
        SELECT q.two_category AS topic,
               SUM(r.score) AS correct,
               COUNT(r.response_id) AS total
        FROM quiz q
        LEFT JOIN response r ON r.quiz_id = q.quiz_id
        GROUP BY q.two_category
        """,
    ).fetchall()
    accuracy = []
    for row in accuracy_rows:
        topic = row["topic"] or "Unassigned"
        total = row["total"] or 0
        pct = round((row["correct"] / total) * 100, 2) if total else 0.0
        accuracy.append({"topic": topic, "total": total, "pct": pct})

    today = datetime.utcnow().date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    day_labels = [day.strftime("%d %b") for day in days]

    attempts_per_day: List[int] = []
    attempted_with_responses: List[int] = []
    for day in days:
        day_str = day.isoformat()
        total = conn.execute(
            "SELECT COUNT(*) FROM attempt WHERE date(started_at) = ?",
            (day_str,),
        ).fetchone()[0]
        with_responses = conn.execute(
            """
            SELECT COUNT(DISTINCT a.attempt_id)
            FROM attempt a
            JOIN response r ON r.attempt_id = a.attempt_id
            WHERE date(a.started_at) = ?
            """,
            (day_str,),
        ).fetchone()[0]
        attempts_per_day.append(total)
        attempted_with_responses.append(with_responses)

    abandoned_attempts = max(counts["attempts"] - counts["attempts_with_responses"], 0)

    return render_template(
        "admin_home.html",
        counts=counts,
        accuracy=accuracy,
        day_labels=day_labels,
        attempts_per_day=list(attempts_per_day),
        attempted_with_responses=list(attempted_with_responses),
        abandoned_attempts=abandoned_attempts,
    )


@app.route("/admin/analytics")
@login_required
@lecturer_required
def admin_analytics() -> Any:
    conn = get_db()

    per_student = conn.execute(
        """
        SELECT s.student_id, s.name, s.email,
               AVG(r.response_time_s) AS avg_time,
               COUNT(r.response_id) AS responses
        FROM student s
        JOIN response r ON r.student_id = s.student_id
        WHERE r.response_time_s IS NOT NULL
        GROUP BY s.student_id
        ORDER BY avg_time DESC
        """,
    ).fetchall()

    per_question = conn.execute(
        """
        SELECT q.quiz_id, q.question, q.two_category,
               AVG(r.response_time_s) AS avg_time,
               MIN(r.response_time_s) AS min_time,
               MAX(r.response_time_s) AS max_time,
               COUNT(r.response_id) AS responses
        FROM quiz q
        LEFT JOIN response r ON r.quiz_id = q.quiz_id AND r.response_time_s IS NOT NULL
        GROUP BY q.quiz_id
        ORDER BY q.quiz_id
        """,
    ).fetchall()

    question_stats = [dict(row) for row in per_question]
    qualifying = [row for row in question_stats if (row["responses"] or 0) >= 5 and row["avg_time"]]
    slowest = sorted(qualifying, key=lambda r: r["avg_time"], reverse=True)[:5]
    fastest = sorted(qualifying, key=lambda r: r["avg_time"])[:5]

    return render_template(
        "admin_analytics.html",
        per_student=per_student,
        per_question=question_stats,
        slowest=slowest,
        fastest=fastest,
    )


@app.route("/admin/rankings")
@login_required
@lecturer_required
def admin_rankings() -> Any:
    conn = get_db()
    leaderboard = conn.execute(
        """
        SELECT s.student_id, s.name, s.email,
               COUNT(a.attempt_id) AS attempts,
               AVG(a.score_pct) AS average_score,
               MAX(a.score_pct) AS best_score,
               (
                   SELECT score_pct
                   FROM attempt
                   WHERE student_id = s.student_id AND finished_at IS NOT NULL
                   ORDER BY datetime(finished_at) DESC
                   LIMIT 1
               ) AS last_score
        FROM student s
        JOIN attempt a ON a.student_id = s.student_id AND a.finished_at IS NOT NULL
        GROUP BY s.student_id
        HAVING attempts > 0
        ORDER BY average_score DESC
        """,
    ).fetchall()

    return render_template("admin_rankings.html", leaderboard=leaderboard)


@app.route("/admin/questions")
@login_required
@lecturer_required
def admin_questions() -> Any:
    conn = get_db()
    rows = conn.execute(
        """
        SELECT q.quiz_id, q.question, q.two_category,
               COUNT(r.response_id) AS responses,
               SUM(r.score) AS correct
        FROM quiz q
        LEFT JOIN response r ON r.quiz_id = q.quiz_id
        GROUP BY q.quiz_id
        ORDER BY q.quiz_id
        """,
    ).fetchall()

    questions = []
    for row in rows:
        total = row["responses"] or 0
        correct = row["correct"] or 0
        pct = round((correct / total) * 100, 2) if total else 0.0
        questions.append({
            "quiz_id": row["quiz_id"],
            "question": row["question"],
            "topic": row["two_category"] or "Unassigned",
            "responses": total,
            "correct_pct": pct,
        })

    return render_template("admin_questions.html", questions=questions)


if __name__ == "__main__":
    app.run(debug=True)
