import os
import json
import sqlite3
import secrets
import random
from datetime import datetime
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


# --- Database helpers (hardened for Windows & first-run) ---

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        # 1) Resolve DB path safely
        raw = os.environ.get("PLA_DB", "pla.db")
        raw = raw.strip().strip('"').strip("'")           # strip stray quotes
        base_dir = os.path.dirname(__file__)
        db_path = raw if os.path.isabs(raw) else os.path.join(base_dir, raw)
        os.makedirs(os.path.dirname(db_path) or base_dir, exist_ok=True)

        # 2) Connect (row dicts + FK on)
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")

        # 3) Initialize schema only on true first run (no user tables yet)
        def table_exists(name: str) -> bool:
            try:
                cur = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
                )
                return cur.fetchone() is not None
            except Exception:
                return False

        has_any_core = table_exists("student") or table_exists("quiz") or table_exists("attempt")

        if not has_any_core:
            schema_path = os.path.join(base_dir, "schema.sql")
            seed_path   = os.path.join(base_dir, "seed.sql")
            try:
                if os.path.exists(schema_path):
                    with open(schema_path, "r", encoding="utf-8") as f:
                        conn.executescript(f.read())
                if os.path.exists(seed_path):
                    with open(seed_path, "r", encoding="utf-8") as f:
                        conn.executescript(f.read())
                conn.commit()
            except Exception as e:
                # Don't crash the app; log to console so you can see it
                print("[DB INIT] Failed to apply schema/seed:", repr(e))

        # 4) Post-init safety: ensure new columns exist (non-destructive)
        #    This prevents crashes on older DBs.
        def ensure_column(table: str, col: str, ddl: str) -> None:
            try:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
                if col not in cols:
                    conn.execute(ddl)
                    conn.commit()
            except Exception as e:
                print(f"[DB MIGRATE] {table}.{col}:", repr(e))

        ensure_column("attempt", "source", "ALTER TABLE attempt ADD COLUMN source TEXT")
        ensure_column("quiz",    "two_category", "ALTER TABLE quiz ADD COLUMN two_category TEXT")

        g.db = conn

        stabilize_connection = None
        try:
            from scripts.stabilize_db_and_app import stabilize_connection as _stabilize

            stabilize_connection = _stabilize
        except ModuleNotFoundError:
            try:
                import importlib.util
                from pathlib import Path

                stabilizer_path = Path(__file__).resolve().parent.parent / "scripts" / "stabilize_db_and_app.py"
                spec = importlib.util.spec_from_file_location("pla_stabilizer", stabilizer_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)  # type: ignore[arg-type]
                    stabilize_connection = getattr(module, "stabilize_connection", None)
            except Exception as e:
                print("[DB STABILIZE] loader failed:", repr(e))
        except Exception as e:
            print("[DB STABILIZE] import failed:", repr(e))

        if stabilize_connection:
            try:
                stabilize_connection(conn)
            except Exception as e:
                print("[DB STABILIZE] Failed:", repr(e))

        try:
            cnt = conn.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
            if cnt < 30:
                try:
                    seed_import_questions(conn=conn)
                except Exception as e:
                    print("[SEED] import_questions failed:", repr(e))
        except Exception as e:
            print("[SEED] count failed:", repr(e))

    return g.db  # type: ignore[return-value]


@app.teardown_appcontext
def close_db(_: Any) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def seed_import_questions(csv_path: str = "data/quiz_30.csv", conn: Optional[sqlite3.Connection] = None) -> None:
    import csv
    import json
    import os

    EXPECTED_HEADERS = [
        "q_no",
        "question",
        "options_text",
        "correct_answer",
        "nf_level",
        "concept_tag",
        "explanation",
        "two_category",
    ]
    ALLOWED = {
        "Data Modeling & DBMS Fundamentals",
        "Normalization & Dependencies",
    }

    if not os.path.exists(csv_path):
        return

    def _seed(connection: sqlite3.Connection) -> None:
        try:
            current = connection.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
        except Exception:
            return
        if current >= 30:
            return

        existing = {
            row["question"]
            for row in connection.execute("SELECT question FROM quiz")
        }

        inserted = 0
        try:
            with open(csv_path, newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames != EXPECTED_HEADERS:
                    return
                for raw in reader:
                    question = (raw.get("question") or "").strip()
                    if not question or question in existing:
                        continue
                    two_category = (raw.get("two_category") or "").strip()
                    if two_category not in ALLOWED:
                        continue
                    options_raw = raw.get("options_text", "")
                    try:
                        options = json.loads(options_raw)
                    except Exception:
                        continue
                    if not isinstance(options, list) or len(options) != 4:
                        continue
                    options = [str(opt) for opt in options]
                    correct = str(raw.get("correct_answer", ""))
                    if correct not in options:
                        continue

                    connection.execute(
                        """
                        INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category)
                        VALUES (?,?,?,?,?,?,?)
                        """,
                        (
                            question,
                            json.dumps(options, ensure_ascii=False),
                            correct,
                            raw.get("nf_level", ""),
                            raw.get("concept_tag", ""),
                            raw.get("explanation", ""),
                            two_category,
                        ),
                    )
                    existing.add(question)
                    inserted += 1
                    current += 1
                    if current >= 30:
                        break
        finally:
            if inserted:
                connection.commit()

    if conn is not None:
        _seed(conn)
    else:
        db = get_db()
        try:
            _seed(db)
        finally:
            # ensure pending inserts are saved
            db.commit()


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


def get_two_category_mastery(student_id: int):
    empty = {
        "fund": {"pct": 0.0, "pts": 0.0, "total": 0, "correct": 0},
        "norm": {"pct": 0.0, "pts": 0.0, "total": 0, "correct": 0},
        "overall_points": 0.0,
    }

    with get_db() as conn:
        quiz_cols = [row[1] for row in conn.execute("PRAGMA table_info(quiz)")]
        attempt_cols = [row[1] for row in conn.execute("PRAGMA table_info(attempt)")]
        if "two_category" not in quiz_cols:
            return empty

        source_guard = "IFNULL(source,'live')" if "source" in attempt_cols else "'live'"
        attempt_row = conn.execute(
            f"""
            SELECT attempt_id
            FROM attempt
            WHERE student_id=?
              AND {source_guard}='live'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (student_id,),
        ).fetchone()

        if not attempt_row:
            return empty

        attempt_id = int(attempt_row["attempt_id"])
        rows = conn.execute(
            """
            SELECT q.two_category AS cat,
                   SUM(r.score) AS correct,
                   COUNT(*) AS total
            FROM response r
            JOIN quiz q ON q.quiz_id = r.quiz_id
            WHERE r.student_id=? AND r.attempt_id=?
            GROUP BY q.two_category
            """,
            (student_id, attempt_id),
        ).fetchall()

    fund_total = fund_correct = 0
    norm_total = norm_correct = 0
    for row in rows:
        cat = row["cat"]
        total = int(row["total"] or 0)
        correct = int(row["correct"] or 0)
        if cat == "Data Modeling & DBMS Fundamentals":
            fund_total = total
            fund_correct = correct
        elif cat == "Normalization & Dependencies":
            norm_total = total
            norm_correct = correct

    fund_pct = round(100.0 * fund_correct / fund_total, 1) if fund_total else 0.0
    norm_pct = round(100.0 * norm_correct / norm_total, 1) if norm_total else 0.0
    fund_points = round((fund_pct / 100.0) * 50.0, 1)
    norm_points = round((norm_pct / 100.0) * 50.0, 1)
    overall_points = round(fund_points + norm_points, 1)

    return {
        "fund": {
            "pct": fund_pct,
            "pts": fund_points,
            "total": fund_total,
            "correct": fund_correct,
        },
        "norm": {
            "pct": norm_pct,
            "pts": norm_points,
            "total": norm_total,
            "correct": norm_correct,
        },
        "overall_points": overall_points,
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
    """Determine which concept still needs a perfect score."""
    mastery = get_two_category_mastery(student_id)
    fund = mastery.get("fund", {}) if isinstance(mastery, dict) else {}
    norm = mastery.get("norm", {}) if isinstance(mastery, dict) else {}
    if float(fund.get("pct", 0.0)) < 100.0:
        return "Data Modeling & DBMS Fundamentals"
    if float(norm.get("pct", 0.0)) < 100.0:
        return "Normalization & Dependencies"
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
    student_id = int(session["student_id"])  # never trust posted ids
    attempt_id = _get_or_create_open_attempt(student_id)
    questions = _select_questions_payload()

    if not questions:
        flash("Quiz is not available right now. Please try again shortly.")
        return redirect(url_for("student_dashboard", student_id=student_id))

    db = get_db()
    try:
        db.execute(
            "UPDATE attempt SET items_total=? WHERE attempt_id=?",
            (len(questions), attempt_id),
        )
        db.commit()
    except Exception as exc:
        print("[QUIZ] Failed to store attempt length:", repr(exc))

    return render_template(
        "quiz.html",
        questions=questions,
        attempt_id=attempt_id,
        student_id=student_id,
    )


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
    attempt_cols = [r[1] for r in db.execute("PRAGMA table_info(attempt)")]
    params = (
        student_id,
        "Data Modeling & DBMS Fundamentals + Normalization & Dependencies",
        started_at,
        0,
        0,
        0.0,
    )
    if "source" in attempt_cols:
        db.execute(
            """
            INSERT INTO attempt (student_id, nf_scope, started_at, items_total, items_correct, score_pct, source)
            VALUES (?,?,?,?,?,?,?)
            """,
            params + ("live",),
        )
    else:
        db.execute(
            "INSERT INTO attempt (student_id, nf_scope, started_at, items_total, items_correct, score_pct) VALUES (?,?,?,?,?,?)",
            params,
        )
    db.commit()
    cur = db.execute(
        "SELECT attempt_id FROM attempt WHERE student_id=? AND started_at=?",
        (student_id, started_at),
    )
    return int(cur.fetchone()["attempt_id"])  # type: ignore[index]


def _select_questions_payload(total: int = 30) -> List[Dict[str, Any]]:
    db = get_db()
    categories = [
        "Data Modeling & DBMS Fundamentals",
        "Normalization & Dependencies",
    ]
    per_category = max(1, total // max(len(categories), 1))
    questions: List[Dict[str, Any]] = []
    seen: set[int] = set()

    for cat in categories:
        cur = db.execute(
            """
            SELECT quiz_id, question, options_text, concept_tag, nf_level
            FROM quiz
            WHERE two_category = ?
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (cat, per_category),
        )
        for row in cur.fetchall():
            qid = int(row["quiz_id"])
            if qid in seen:
                continue
            options = safe_parse_options(row["options_text"] or "[]")
            if len(options) != 4:
                continue
            questions.append(
                {
                    "quiz_id": qid,
                    "question": row["question"],
                    "options": options,
                    "nf_level": row["nf_level"],
                    "concept_tag": row["concept_tag"],
                }
            )
            seen.add(qid)

    if len(questions) < total:
        remaining = total - len(questions)
        placeholders = ",".join(["?"] * len(categories))
        cur = db.execute(
            f"""
            SELECT quiz_id, question, options_text, concept_tag, nf_level
            FROM quiz
            WHERE two_category IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (*categories, remaining),
        )
        for row in cur.fetchall():
            qid = int(row["quiz_id"])
            if qid in seen:
                continue
            options = safe_parse_options(row["options_text"] or "[]")
            if len(options) != 4:
                continue
            questions.append(
                {
                    "quiz_id": qid,
                    "question": row["question"],
                    "options": options,
                    "nf_level": row["nf_level"],
                    "concept_tag": row["concept_tag"],
                }
            )
            seen.add(qid)
            if len(questions) >= total:
                break

    random.shuffle(questions)
    return questions[:total]


@app.route("/api/quiz_progressive")
@login_required
def api_quiz_progressive():
    student_id = int(session["student_id"])  # never trust posted student_id
    attempt_id = _get_or_create_open_attempt(student_id)
    questions = _select_questions_payload()
    if not questions:
        return jsonify({"error": "quiz unavailable"}), 503

    db = get_db()
    try:
        db.execute(
            "UPDATE attempt SET items_total=? WHERE attempt_id=?",
            (len(questions), attempt_id),
        )
        db.commit()
    except Exception as exc:
        print("[QUIZ] Failed to update attempt total:", repr(exc))

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

    cur = db.execute(
        "SELECT attempt_id, started_at, score_pct FROM attempt WHERE student_id=? AND score_pct IS NOT NULL ORDER BY started_at ASC",
        (current_student_id,),
    )
    attempts = cur.fetchall()
    labels = [f"A{idx + 1}" for idx, _ in enumerate(attempts)]
    scores = [float(a["score_pct"]) for a in attempts]

    cur = db.execute(
        "SELECT attempt_id, started_at, score_pct FROM attempt WHERE student_id=? ORDER BY started_at DESC LIMIT 1",
        (current_student_id,),
    )
    last = cur.fetchone()

    two_cat = get_two_category_mastery(current_student_id)
    fund = two_cat.get("fund", {})
    norm = two_cat.get("norm", {})
    unlocked_next = (
        float(fund.get("pct", 0.0)) == 100.0 and float(norm.get("pct", 0.0)) == 100.0
    )

    return render_template(
        "student_dashboard.html",
        labels=labels,
        scores=scores,
        last_attempt=last,
        two_cat=two_cat,
        unlocked_next=unlocked_next,
    )


@app.route("/modules")
@login_required
def modules():
    """Show all available modules."""
    db = get_db()
    cur = db.execute(
        """
        SELECT title, description, resource_url
        FROM module
        WHERE resource_url IN ('/module/fundamentals','/module/norm')
        ORDER BY title
        """
    )
    rows = cur.fetchall()

    modules = []
    for row in rows:
        link = row["resource_url"] or ""
        title = row["title"]
        if not link.startswith("/"):
            link = "/module/fundamentals" if "fund" in (title or "").lower() else "/module/norm"
        modules.append(
            {
                "title": title,
                "description": row["description"],
                "resource_url": link,
            }
        )

    if not modules:
        modules = [
            {
                "title": "Data Modeling & DBMS Fundamentals",
                "description": "Understand core modeling concepts and DBMS components.",
                "resource_url": "/module/fundamentals",
            },
            {
                "title": "Normalization & Dependencies",
                "description": "Practice normalization steps and dependency analysis.",
                "resource_url": "/module/norm",
            },
        ]

    return render_template("modules.html", modules=modules)


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
    try:
        rating = int(data.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
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
