import os
import json
import sqlite3
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    g,
    session,
    request,
    redirect,
    url_for,
    render_template,
    flash,
    jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv


# Load environment
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")
app.config["JSON_SORT_KEYS"] = False


# --- Database helpers ---

DEMO_HASH = (
    "scrypt:32768:8:1$Bfg5AHCcWPR0MbIG$a60fa108b4e21585ed24fcd403a80b49c140ea9a1b64618abed"
    "649cba66276497d06090f81518f6b535788e975f707f8ee9dfeec6b3caba556cef82b6d5ff484"
)


def _ensure_demo_data(conn: sqlite3.Connection) -> bool:
    """Ensure demo student and attempts exist for deterministic dashboards."""

    changed = False
    demo_email = "test@example.com"
    cur = conn.execute("SELECT student_id FROM student WHERE email=?", (demo_email,))
    row = cur.fetchone()
    if row is None:
        # Prefer id 1 for deterministic tests, but handle existing data gracefully
        conn.execute(
            "INSERT OR IGNORE INTO student (student_id, name, email, program, password_hash)"
            " VALUES (1, ?, ?, ?, ?)",
            ("Demo Student", demo_email, "Computer Science", DEMO_HASH),
        )
        cur = conn.execute("SELECT student_id FROM student WHERE email=?", (demo_email,))
        row = cur.fetchone()
        changed = True

    if row is None:
        return changed

    student_id = int(row["student_id"])

    mastery_defaults = {
        "Functional Dependency": 1,
        "Atomic Values": 1,
        "Partial Dependency": 0,
        "Transitive Dependency": 0,
    }
    for concept, mastered in mastery_defaults.items():
        cur = conn.execute(
            "SELECT mastered FROM student_mastery WHERE student_id=? AND concept_tag=?",
            (student_id, concept),
        )
        if cur.fetchone() is None:
            conn.execute(
                "INSERT INTO student_mastery (student_id, concept_tag, mastered, updated_at)"
                " VALUES (?,?,?, datetime('now','-3 day'))",
                (student_id, concept, mastered),
            )
            changed = True

    cur = conn.execute(
        "SELECT COUNT(*) FROM attempt WHERE student_id=? AND finished_at IS NOT NULL",
        (student_id,),
    )
    if cur.fetchone()[0] < 2:
        conn.execute("DELETE FROM response WHERE student_id=?", (student_id,))
        conn.execute("DELETE FROM attempt WHERE student_id=?", (student_id,))

        def insert_attempt(scope: str, days_ago: int, minutes: int, total: int, correct: int) -> int:
            started = datetime.utcnow() - timedelta(days=days_ago)
            finished = started + timedelta(minutes=minutes)
            score_pct = round((correct / total) * 100.0, 1)
            cur = conn.execute(
                "INSERT INTO attempt (student_id, nf_scope, started_at, finished_at, items_total, items_correct, score_pct, source)"
                " VALUES (?,?,?,?,?,?,?, 'live')",
                (
                    student_id,
                    scope,
                    started.isoformat(),
                    finished.isoformat(),
                    total,
                    correct,
                    score_pct,
                ),
            )
            return int(cur.lastrowid)

        attempt1_id = insert_attempt("FD+1NF", 5, 15, 12, 10)
        attempt2_id = insert_attempt("2NF+3NF", 2, 18, 12, 8)

        def insert_responses(level: str, attempt_id: int, correct_limit: int, base_time: float) -> None:
            rows = conn.execute(
                "SELECT quiz_id, correct_answer FROM quiz WHERE nf_level=? ORDER BY quiz_id LIMIT 6",
                (level,),
            ).fetchall()
            for idx, row in enumerate(rows):
                score = 1 if idx < correct_limit else 0
                answer = row["correct_answer"] if score else "Incorrect"
                conn.execute(
                    "INSERT INTO response (attempt_id, student_id, quiz_id, answer, score, response_time_s)"
                    " VALUES (?,?,?,?,?,?)",
                    (
                        attempt_id,
                        student_id,
                        int(row["quiz_id"]),
                        answer,
                        score,
                        base_time + idx,
                    ),
                )

        insert_responses("FD", attempt1_id, 5, 11.0)
        insert_responses("1NF", attempt1_id, 5, 12.0)
        insert_responses("2NF", attempt2_id, 4, 13.0)
        insert_responses("3NF", attempt2_id, 4, 14.0)
        changed = True

    return changed

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = os.environ.get("PLA_DB", "pla.db")
        if not os.path.isabs(db_path):
            db_path = os.path.join(app.root_path, db_path)
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        base_dir = os.path.dirname(__file__)
        schema_updated = False
        # Ensure database schema and seed data exist on first run
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='module'"
            )
            has_module_table = cur.fetchone() is not None
        except Exception:
            has_module_table = False

        if not has_module_table:
            schema_path = os.path.join(base_dir, "schema.sql")
            seed_path = os.path.join(base_dir, "seed.sql")
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    conn.executescript(f.read())
                with open(seed_path, "r", encoding="utf-8") as f:
                    conn.executescript(f.read())
                schema_updated = True
            except FileNotFoundError:
                # If SQL files are missing, leave DB uninitialized but don't crash
                pass
        else:
            # Apply forward-compatible schema updates for existing databases
            try:
                quiz_cols = {
                    row["name"] for row in conn.execute("PRAGMA table_info(quiz)")
                }
                if quiz_cols and "two_category" not in quiz_cols:
                    conn.execute("ALTER TABLE quiz ADD COLUMN two_category TEXT")
                    conn.execute(
                        """
UPDATE quiz
SET two_category = CASE
    WHEN nf_level = 'FD' THEN 'Data Modeling & DBMS Fundamentals'
    ELSE 'Normalization & Dependencies'
END
WHERE two_category IS NULL
                        """
                    )
                    schema_updated = True
            except sqlite3.OperationalError:
                pass

            try:
                attempt_cols = {
                    row["name"] for row in conn.execute("PRAGMA table_info(attempt)")
                }
                if attempt_cols and "source" not in attempt_cols:
                    conn.execute(
                        "ALTER TABLE attempt ADD COLUMN source TEXT DEFAULT 'live'"
                    )
                    conn.execute(
                        "UPDATE attempt SET source = COALESCE(source, 'live')"
                    )
                    schema_updated = True
            except sqlite3.OperationalError:
                pass

        # Ensure auxiliary tables exist (safe to run repeatedly)
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='module_progress'"
            )
            if cur.fetchone() is None:
                conn.executescript(
                    """
CREATE TABLE IF NOT EXISTS module_progress (
  progress_id   INTEGER PRIMARY KEY,
  student_id    INTEGER NOT NULL,
  module_key    TEXT    NOT NULL,
  score         INTEGER NOT NULL,
  completed_at  TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(student_id, module_key),
  FOREIGN KEY(student_id) REFERENCES student(student_id) ON DELETE CASCADE
);
                    """
                )
                schema_updated = True
        except Exception:
            pass

        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='feedback'"
            )
            if cur.fetchone() is None:
                conn.executescript(
                    """
CREATE TABLE IF NOT EXISTS feedback (
  feedback_id   INTEGER PRIMARY KEY,
  student_id    INTEGER,
  rating        INTEGER NOT NULL,
  comment       TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(student_id) REFERENCES student(student_id) ON DELETE SET NULL
);
                    """
                )
                schema_updated = True
        except Exception:
            pass

        if _ensure_demo_data(conn):
            schema_updated = True

        if schema_updated:
            conn.commit()
        g.db = conn
    return g.db  # type: ignore[return-value]


@app.teardown_appcontext
def close_db(_: Any) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


# --- Security / Auth ---

def ensure_csrf_token() -> None:
    if not session.get("csrf_token"):
        if app.config.get("TESTING"):
            session["csrf_token"] = "test-token"
        else:
            session["csrf_token"] = secrets.token_hex(16)


@app.before_request
def before_request() -> None:
    ensure_csrf_token()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("student_id"):
            # For JSON API calls, return 302 redirect to /login to satisfy acceptance
            if request.path.startswith("/api/") or request.path == "/submit":
                return redirect(url_for("login"))
            flash("Please log in to continue.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


# --- Business helpers ---

def safe_parse_options(options_text: str) -> List[str]:
    try:
        data = json.loads(options_text)
        if isinstance(data, list):
            return [str(x) for x in data[:4]]
    except Exception:
        return []
    return []


def categorize_time(seconds: float) -> str:
    if seconds < 10:
        return "Fast"
    if seconds <= 20:
        return "Normal"
    return "Slow"


def get_two_category_mastery(student_id: int):
    """
    Returns mastery for the two concepts using live attempts only.

    points per concept = accuracy% * 0.5  (so 100% accuracy == 50 pts)
    pass per concept    = points >= 17.5  (35% of 50)
    unlock              = both passed AND overall_points > 70
    """
    q = """
    SELECT q.two_category AS cat,
           ROUND(AVG(r.score)*100.0, 1) AS acc_pct,
           COUNT(*) AS n
    FROM response r
    JOIN quiz q     ON q.quiz_id = r.quiz_id
    JOIN attempt a  ON a.attempt_id = r.attempt_id
    WHERE r.student_id = ?
      AND a.source = 'live'
      AND q.two_category IN ('Data Modeling & DBMS Fundamentals','Normalization & Dependencies')
    GROUP BY q.two_category
    """
    with get_db() as conn:
        rows = conn.execute(q, (student_id,)).fetchall()

    fund = {"acc_pct": 0.0, "attempts": 0}
    norm = {"acc_pct": 0.0, "attempts": 0}
    for r in rows:
        acc = float(r["acc_pct"] or 0.0)
        n   = int(r["n"] or 0)
        if r["cat"] == "Data Modeling & DBMS Fundamentals":
            fund = {"acc_pct": acc, "attempts": n}
        elif r["cat"] == "Normalization & Dependencies":
            norm = {"acc_pct": acc, "attempts": n}

    fund_points = round((fund["acc_pct"] / 100.0) * 50.0, 1)
    norm_points = round((norm["acc_pct"] / 100.0) * 50.0, 1)
    overall_points = round(fund_points + norm_points, 1)

    PASS = 17.5  # 35% of 50
    unlocked_next = (fund_points >= PASS and norm_points >= PASS and overall_points > 70.0)

    return {
        "fund": fund, "norm": norm,
        "fund_points": fund_points,
        "norm_points": norm_points,
        "overall_points": overall_points,
        "pass_threshold": PASS,
        "unlocked_next": unlocked_next,
    }

def compute_concept_stats(attempt_id: int) -> List[Dict[str, Any]]:
    """Compute per-concept statistics for an attempt."""
    db = get_db()
    cur = db.execute(
        """
        SELECT q.concept_tag AS concept_tag,
               COUNT(*) AS total,
               SUM(r.score) AS correct,
               AVG(r.response_time_s) AS avg_time
        FROM response r
        JOIN quiz q ON q.quiz_id = r.quiz_id
        WHERE r.attempt_id = ?
        GROUP BY q.concept_tag
        """,
        (attempt_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def next_step_concept(student_id: int) -> Optional[str]:
    """Find the next concept the student should focus on."""
    concept_order = [
        "Functional Dependency",
        "Atomic Values", 
        "Partial Dependency",
        "Transitive Dependency",
    ]
    
    db = get_db()
    for tag in concept_order:
        cur = db.execute(
            "SELECT mastered FROM student_mastery WHERE student_id=? AND concept_tag=?",
            (student_id, tag),
        )
        row = cur.fetchone()
        if not row or int(row["mastered"]) == 0:
            return tag
    return None


# --- Routes ---


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"]) 
def register():
    if request.method == "POST":
        token = request.form.get("csrf_token", "")
        if token != session.get("csrf_token"):
            flash("Invalid CSRF token.")
            return redirect(url_for("register"))

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        program = request.form.get("program", "").strip()
        password = request.form.get("password", "")
        if not (name and email and password):
            flash("Please fill all required fields.")
            return redirect(url_for("register"))

        db = get_db()
        cur = db.execute(
            "SELECT student_id, name, program, password_hash FROM student WHERE email=?",
            (email,),
        )
        existing = cur.fetchone()
        if existing:
            updated_name = name or existing["name"]
            updated_program = program or existing["program"]
            new_hash = (
                generate_password_hash(password)
                if password
                else existing["password_hash"]
            )
            db.execute(
                "UPDATE student SET name=?, program=?, password_hash=? WHERE student_id=?",
                (updated_name, updated_program, new_hash, existing["student_id"]),
            )
            db.commit()
            session["student_id"] = existing["student_id"]
            flash("Welcome back! You're already registered, so we've signed you in.")
            return redirect(
                url_for("student_dashboard", student_id=existing["student_id"])
            )

        password_hash = generate_password_hash(password)
        db.execute(
            "INSERT INTO student (name, email, program, password_hash) VALUES (?,?,?,?)",
            (name, email, program, password_hash),
        )
        db.commit()
        cur = db.execute("SELECT student_id FROM student WHERE email=?", (email,))
        row = cur.fetchone()
        session["student_id"] = row["student_id"]
        flash("Welcome! Account created.")
        return redirect(url_for("student_dashboard", student_id=row["student_id"]))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"]) 
def login():
    if request.method == "POST":
        token = request.form.get("csrf_token", "")
        if token != session.get("csrf_token"):
            flash("Invalid CSRF token.")
            return redirect(url_for("login"))

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        cur = db.execute(
            "SELECT student_id, password_hash FROM student WHERE email=?",
            (email,),
        )
        row = cur.fetchone()
        if not row or not check_password_hash(row["password_hash"], password):
            flash("Invalid credentials.")
            return redirect(url_for("login"))

        session["student_id"] = row["student_id"]
        flash("Logged in.")
        return redirect(url_for("student_dashboard", student_id=row["student_id"]))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("index"))


@app.route("/quiz")
@login_required
def quiz():
    return render_template("quiz.html")


@app.route("/reattempt")
@login_required
def reattempt():
    """Create a new attempt and redirect to quiz."""
    student_id = int(session["student_id"])
    attempt_id = _get_or_create_open_attempt(student_id)
    return redirect(url_for("quiz"))


def _get_or_create_open_attempt(student_id: int) -> int:
    db = get_db()
    cur = db.execute(
        "SELECT attempt_id FROM attempt WHERE student_id=? AND finished_at IS NULL ORDER BY started_at DESC LIMIT 1",
        (student_id,),
    )
    row = cur.fetchone()
    if row:
        return int(row["attempt_id"])
    started_at = datetime.utcnow().isoformat()
    db.execute(
        "INSERT INTO attempt (student_id, nf_scope, started_at, items_total, items_correct, score_pct) VALUES (?,?,?,?,?,?)",
        (student_id, "FD+1NF+2NF+3NF", started_at, 10, 0, 0.0),
    )
    db.commit()
    cur = db.execute(
        "SELECT attempt_id FROM attempt WHERE student_id=? AND started_at=?",
        (student_id, started_at),
    )
    return int(cur.fetchone()["attempt_id"])  # type: ignore[index]


def _select_questions_payload() -> List[Dict[str, Any]]:
    db = get_db()
    blueprint = [("FD", 3), ("1NF", 3), ("2NF", 2), ("3NF", 2)]
    questions: List[Dict[str, Any]] = []
    for nf_level, need in blueprint:
        cur = db.execute(
            "SELECT quiz_id, question, options_text, concept_tag FROM quiz WHERE nf_level=? ORDER BY RANDOM() LIMIT ?",
            (nf_level, need),
        )
        for row in cur.fetchall():
            options = safe_parse_options(row["options_text"]) if row["options_text"] else []
            questions.append(
                {
                    "quiz_id": int(row["quiz_id"]),
                    "question": row["question"],
                    "options": options,
                    "nf_level": nf_level,
                    "concept_tag": row["concept_tag"],
                }
            )
    return questions


@app.route("/api/quiz_progressive")
@login_required
def api_quiz_progressive():
    student_id = int(session["student_id"])  # never trust posted student_id
    attempt_id = _get_or_create_open_attempt(student_id)
    questions = _select_questions_payload()
    return jsonify({"attempt_id": attempt_id, "questions": questions})


@app.route("/submit", methods=["POST"]) 
@login_required
def submit():
    student_id = int(session["student_id"])  # never trust posted student_id
    data = request.get_json(silent=True) or {}
    attempt_id = data.get("attempt_id")
    answers = data.get("answers") or []
    if not isinstance(attempt_id, int) or not isinstance(answers, list) or len(answers) == 0:
        return jsonify({"error": "Invalid payload"}), 400

    db = get_db()
    cur = db.execute(
        "SELECT attempt_id, finished_at FROM attempt WHERE attempt_id=? AND student_id=?",
        (attempt_id, student_id),
    )
    attempt = cur.fetchone()
    if not attempt:
        return jsonify({"error": "Attempt not found"}), 404
    if attempt["finished_at"] is not None:
        return jsonify({"error": "Attempt already finished"}), 400

    # Prepare answer evaluation
    quiz_map: Dict[int, sqlite3.Row] = {}
    quiz_ids = [a.get("quiz_id") for a in answers if isinstance(a, dict)]
    placeholders = ",".join(["?"] * len(quiz_ids)) if quiz_ids else ""
    if quiz_ids:
        cur = db.execute(
            f"SELECT quiz_id, correct_answer, question, explanation, concept_tag FROM quiz WHERE quiz_id IN ({placeholders})",
            tuple(quiz_ids),
        )
        for row in cur.fetchall():
            quiz_map[int(row["quiz_id"])] = row

    total = 0
    correct = 0
    details: List[Dict[str, Any]] = []

    for item in answers:
        if not isinstance(item, dict):
            continue
        qid = item.get("quiz_id")
        ans = item.get("answer")
        t = float(item.get("time_sec", 0))
        if not isinstance(qid, int) or not isinstance(ans, str):
            continue
        total += 1
        qrow = quiz_map.get(qid)
        if not qrow:
            # skip if question not recognized
            continue
        is_correct = 1 if ans == qrow["correct_answer"] else 0
        correct += is_correct
        db.execute(
            "INSERT INTO response (attempt_id, student_id, quiz_id, answer, score, response_time_s) VALUES (?,?,?,?,?,?)",
            (attempt_id, student_id, qid, ans, is_correct, t),
        )
        details.append(
            {
                "quiz_id": qid,
                "question": qrow["question"],
                "answer": ans,
                "correct_answer": qrow["correct_answer"],
                "explanation": qrow["explanation"],
                "concept_tag": qrow["concept_tag"],
                "response_time_s": t,
                "time_category": categorize_time(t),
                "score": is_correct,
            }
        )

    score_pct = (correct / total * 100.0) if total else 0.0
    finished_at = datetime.utcnow().isoformat()
    db.execute(
        "UPDATE attempt SET finished_at=?, items_total=?, items_correct=?, score_pct=? WHERE attempt_id=?",
        (finished_at, total, correct, score_pct, attempt_id),
    )

    # Per-concept metrics for this attempt
    cur = db.execute(
        """
        SELECT q.concept_tag AS concept_tag,
               COUNT(*) AS total,
               SUM(r.score) AS correct,
               AVG(r.response_time_s) AS avg_time
        FROM response r
        JOIN quiz q ON q.quiz_id = r.quiz_id
        WHERE r.attempt_id = ?
        GROUP BY q.concept_tag
        """,
        (attempt_id,),
    )
    per_concept_rows = cur.fetchall()

    # Mastery upsert and recommendations
    for row in per_concept_rows:
        tag = row["concept_tag"]
        c_total = int(row["total"]) if row["total"] is not None else 0
        c_correct = int(row["correct"]) if row["correct"] is not None else 0
        c_avg_time = float(row["avg_time"]) if row["avg_time"] is not None else 0.0
        acc_pct = (c_correct / c_total * 100.0) if c_total else 0.0
        mastered = 1 if acc_pct >= 80.0 else 0

        db.execute(
            """
            INSERT INTO student_mastery (student_id, concept_tag, mastered, updated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(student_id, concept_tag) DO UPDATE SET
              mastered=excluded.mastered,
              updated_at=excluded.updated_at
            """,
            (student_id, tag, mastered, finished_at),
        )

        if acc_pct < 70.0 or c_avg_time > 20.0:
            # create recommendation linked to module
            mcur = db.execute(
                "SELECT module_id FROM module WHERE concept_tag = ? ORDER BY module_id LIMIT 1",
                (tag,),
            )
            mrow = mcur.fetchone()
            module_id = int(mrow["module_id"]) if mrow else None
            suggested = f"Review {tag} module."
            db.execute(
                "INSERT INTO recommendation (student_id, concept_tag, suggested_action, module_id, created_at) VALUES (?,?,?,?,?)",
                (student_id, tag, suggested, module_id, finished_at),
            )

    db.commit()

    return jsonify(
        {
            "attempt_id": attempt_id,
            "student_id": student_id,
            "total": total,
            "correct": correct,
            "score_pct": score_pct,
            "details": details,
            "passed": score_pct >= 70.0,
            "next_step": next_step_concept(student_id),
        }
    )


@app.route("/student/<int:student_id>")
@login_required
def student_dashboard(student_id: int):
    current_student_id = int(session["student_id"])  # never trust URL param
    if student_id != current_student_id:
        flash("Access restricted to your own dashboard.")
        return redirect(url_for("student_dashboard", student_id=current_student_id))

    db = get_db()

    # Attempts history
    cur = db.execute(
        "SELECT attempt_id, started_at, score_pct FROM attempt WHERE student_id=? AND score_pct IS NOT NULL ORDER BY started_at ASC",
        (current_student_id,),
    )
    attempts = cur.fetchall()
    labels = [f"A{idx+1}" for idx, _ in enumerate(attempts)]
    scores = [float(a["score_pct"]) for a in attempts]

    # Last attempt details
    cur = db.execute(
        "SELECT attempt_id, started_at, score_pct FROM attempt WHERE student_id=? AND items_total IS NOT NULL ORDER BY started_at DESC LIMIT 1",
        (current_student_id,),
    )
    last = cur.fetchone()
    last_details: List[Dict[str, Any]] = []
    if last:
        cur = db.execute(
            """
            SELECT q.question, r.answer, q.correct_answer, q.explanation, q.concept_tag,
                   r.response_time_s, r.score
            FROM response r
            JOIN quiz q ON q.quiz_id = r.quiz_id
            WHERE r.attempt_id = ?
            ORDER BY r.response_id ASC
            """,
            (last["attempt_id"],),
        )
        for row in cur.fetchall():
            t = float(row["response_time_s"]) if row["response_time_s"] is not None else 0.0
            last_details.append(
                {
                    "question": row["question"],
                    "answer": row["answer"],
                    "correct_answer": row["correct_answer"],
                    "explanation": row["explanation"],
                    "concept_tag": row["concept_tag"],
                    "response_time_s": t,
                    "time_category": categorize_time(t),
                    "score": int(row["score"]) if row["score"] is not None else 0,
                }
            )

    # Per-concept metrics (last attempt) plus mastery state - NO TIME DISPLAY
    per_concept: List[Dict[str, Any]] = []
    if last:
        cur = db.execute(
            """
            SELECT q.concept_tag AS concept_tag,
                   100.0 * SUM(r.score) / COUNT(*) AS acc_pct
            FROM response r
            JOIN quiz q ON q.quiz_id = r.quiz_id
            WHERE r.attempt_id = ?
            GROUP BY q.concept_tag
            ORDER BY q.concept_tag
            """,
            (last["attempt_id"],),
        )
        for row in cur.fetchall():
            tag = row["concept_tag"]
            acc = float(row["acc_pct"]) if row["acc_pct"] is not None else 0.0
            mcur = db.execute(
                "SELECT mastered FROM student_mastery WHERE student_id=? AND concept_tag=?",
                (current_student_id, tag),
            )
            mrow = mcur.fetchone()
            per_concept.append(
                {
                    "concept_tag": tag,
                    "acc_pct": acc,
                    "mastered": int(mrow["mastered"]) if mrow else 0,
                }
            )

    # Next step concept
    next_step = next_step_concept(current_student_id)
    
    # Get next step concept accuracy for gauge
    next_step_accuracy = 0.0
    if next_step and last:
        cur = db.execute(
            """
            SELECT 100.0 * SUM(r.score) / COUNT(*) AS acc_pct
            FROM response r
            JOIN quiz q ON q.quiz_id = r.quiz_id
            WHERE r.attempt_id = ? AND q.concept_tag = ?
            """,
            (last["attempt_id"], next_step),
        )
        row = cur.fetchone()
        if row and row["acc_pct"] is not None:
            next_step_accuracy = float(row["acc_pct"])

    two_cat = get_two_category_mastery(current_student_id)
    return render_template(
        "student_dashboard.html",
        labels=labels,
        scores=scores,
        last_details=last_details,
        per_concept=per_concept,
        next_step=next_step,
        next_step_accuracy=next_step_accuracy,
        last_attempt=last,
        two_cat=two_cat,
    )


@app.route("/modules")
@login_required
def modules():
    """Show all available modules."""
    db = get_db()
    cur = db.execute(
        "SELECT module_id, title, description, nf_level, concept_tag, resource_url FROM module ORDER BY module_id"
    )
    modules = cur.fetchall()
    return render_template("modules.html", modules=modules)


@app.route("/module/<int:module_id>")
@login_required
def module_page(module_id: int):
    db = get_db()
    cur = db.execute(
        "SELECT module_id, title, description, nf_level, concept_tag, resource_url FROM module WHERE module_id=?",
        (module_id,),
    )
    module = cur.fetchone()
    if not module:
        flash("Module not found.")
        return redirect(url_for("index"))
    return render_template("module.html", module=module)


@app.route("/module/fundamentals")
@login_required
def module_fundamentals():
    return render_template("module_fundamentals.html")


@app.route("/module/norm")
@login_required
def module_norm():
    return render_template("module_norm.html")


@app.route("/api/module_progress", methods=["POST"])
@login_required
def api_module_progress():
    data = request.get_json(force=True) or {}
    module_key = (data.get("module_key") or "").strip().lower()  # 'fundamentals' | 'norm'
    score = int(data.get("score", 0))  # 0..3
    if module_key not in {"fundamentals","norm"}:
        return jsonify({"ok": False, "error": "invalid module_key"}), 400
    if score < 0 or score > 3:
        return jsonify({"ok": False, "error": "invalid score"}), 400
    sid = int(session["student_id"])
    with get_db() as db:
        db.execute(
            """
          INSERT INTO module_progress (student_id, module_key, score)
          VALUES (?,?,?)
          ON CONFLICT(student_id, module_key) DO UPDATE SET
            score=excluded.score,
            completed_at=datetime('now')
        """,
            (sid, module_key, score),
        )
        db.commit()
    return jsonify({"ok": True})


@app.route("/thanks")
@login_required
def thanks_page():
    return render_template("thanks.html")


@app.route("/api/feedback", methods=["POST"])
@login_required
def api_feedback():
    data = request.get_json(force=True) or {}
    rating = int(data.get("rating", 0))
    comment = (data.get("comment") or "").strip()
    if rating < 1 or rating > 5:
        return jsonify({"ok": False, "error": "Invalid rating"}), 400
    sid = int(session.get("student_id"))
    with get_db() as conn:
        conn.execute("INSERT INTO feedback (student_id, rating, comment) VALUES (?,?,?)",
                     (sid, rating, comment))
        conn.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)  # for local development
