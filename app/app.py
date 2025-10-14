import os
import json
import sqlite3
import secrets
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List

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

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    static_folder=os.path.join(_BASE_DIR, "static"),
    template_folder=os.path.join(_BASE_DIR, "templates"),
)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")
app.config["JSON_SORT_KEYS"] = False


# --- Database helpers ---

def ensure_schema_initialized(conn: sqlite3.Connection) -> None:
    """Create schema and seed data on first run.

    We consider the DB uninitialized if the `student` table is missing.
    In that case, execute `schema.sql` followed by `seed.sql` bundled with the app.
    """
    check = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='student'"
    ).fetchone()
    if check is not None:
        return

    base_dir = os.path.dirname(__file__)
    schema_path = os.path.join(base_dir, "schema.sql")
    seed_path = os.path.join(base_dir, "seed.sql")

    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    with open(seed_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = os.environ.get("PLA_DB", "pla.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        # Ensure schema exists for fresh databases
        ensure_schema_initialized(conn)
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
        cur = db.execute("SELECT student_id FROM student WHERE email=?", (email,))
        if cur.fetchone():
            flash("Email already registered.")
            return redirect(url_for("login"))

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
        mastered = 1 if (c_total >= 3 and acc_pct >= 80.0 and c_avg_time <= 20.0) else 0

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
        "SELECT attempt_id FROM attempt WHERE student_id=? AND items_total IS NOT NULL ORDER BY started_at DESC LIMIT 1",
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

    # Per-concept metrics (last attempt) plus mastery state
    per_concept: List[Dict[str, Any]] = []
    if last:
        cur = db.execute(
            """
            SELECT q.concept_tag AS concept_tag,
                   100.0 * SUM(r.score) / COUNT(*) AS acc_pct,
                   AVG(r.response_time_s) AS avg_time
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
            avg_t = float(row["avg_time"]) if row["avg_time"] is not None else 0.0
            mcur = db.execute(
                "SELECT mastered FROM student_mastery WHERE student_id=? AND concept_tag=?",
                (current_student_id, tag),
            )
            mrow = mcur.fetchone()
            per_concept.append(
                {
                    "concept_tag": tag,
                    "acc_pct": acc,
                    "avg_time": avg_t,
                    "mastered": int(mrow["mastered"]) if mrow else 0,
                }
            )

    # Next step: first not mastered in FD -> 1NF -> 2NF -> 3NF
    concept_order = [
        "Functional Dependency",
        "Atomic Values",
        "Partial Dependency",
        "Transitive Dependency",
    ]
    next_step = None
    for tag in concept_order:
        cur = db.execute(
            "SELECT mastered FROM student_mastery WHERE student_id=? AND concept_tag=?",
            (current_student_id, tag),
        )
        row = cur.fetchone()
        if not row or int(row["mastered"]) == 0:
            next_step = tag
            break

    return render_template(
        "student_dashboard.html",
        labels=labels,
        scores=scores,
        last_details=last_details,
        per_concept=per_concept,
        next_step=next_step,
    )


@app.route("/module/<int:module_id>")
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


if __name__ == "__main__":
    app.run(debug=True)  # for local development
