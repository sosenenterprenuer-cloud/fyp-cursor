diff --git a/app/app.py b/app/app.py
index 182808a1216020eb3e8a4aabacaf1dd33e8a6f3b..cacf27af967f412ad391c1bff291ef81e3e37125 100644
--- a/app/app.py
+++ b/app/app.py
@@ -1,29 +1,30 @@
 import os
 import json
 import sqlite3
 import secrets
+import random
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
@@ -64,346 +65,754 @@ def get_db() -> sqlite3.Connection:
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
 
+        def ensure_table(table: str, ddl: str) -> None:
+            try:
+                exists = conn.execute(
+                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
+                    (table,),
+                ).fetchone()
+                if not exists:
+                    conn.executescript(ddl)
+                    conn.commit()
+            except Exception as e:
+                print(f"[DB MIGRATE] create {table}:", repr(e))
+
+        ensure_table(
+            "lecturer",
+            """
+CREATE TABLE IF NOT EXISTS lecturer (
+  lecturer_id   INTEGER PRIMARY KEY,
+  name          TEXT NOT NULL,
+  email         TEXT UNIQUE NOT NULL,
+  password_hash TEXT NOT NULL
+);
+""",
+        )
+
+        try:
+            conn.execute(
+                """
+                INSERT OR IGNORE INTO lecturer (name, email, password_hash)
+                VALUES (?, ?, ?)
+                """,
+                (
+                    "Admin Lecturer",
+                    "admin@lct.edu",
+                    "scrypt:32768:8:1$wTlANxNNLLoNn4Uq$6ccbf5f9217be922980d987781fad29737537e9918d31791911222b0b29e968a8b33d3a76ec72a35947ad940a72167c64d76c7e1645ca2b9d6a41fe2ea2cc7d8",
+                ),
+            )
+            conn.commit()
+        except Exception as e:
+            print("[DB SEED] lecturer:", repr(e))
+
         g.db = conn
+
+        stabilize_connection = None
+        try:
+            from scripts.stabilize_db_and_app import stabilize_connection as _stabilize
+
+            stabilize_connection = _stabilize
+        except ModuleNotFoundError:
+            try:
+                import importlib.util
+                from pathlib import Path
+
+                stabilizer_path = Path(__file__).resolve().parent.parent / "scripts" / "stabilize_db_and_app.py"
+                spec = importlib.util.spec_from_file_location("pla_stabilizer", stabilizer_path)
+                if spec and spec.loader:
+                    module = importlib.util.module_from_spec(spec)
+                    spec.loader.exec_module(module)  # type: ignore[arg-type]
+                    stabilize_connection = getattr(module, "stabilize_connection", None)
+            except Exception as e:
+                print("[DB STABILIZE] loader failed:", repr(e))
+        except Exception as e:
+            print("[DB STABILIZE] import failed:", repr(e))
+
+        if stabilize_connection:
+            try:
+                stabilize_connection(conn)
+            except Exception as e:
+                print("[DB STABILIZE] Failed:", repr(e))
+
+        try:
+            cnt = conn.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
+            if cnt < 30:
+                try:
+                    seed_import_questions(conn=conn)
+                except Exception as e:
+                    print("[SEED] import_questions failed:", repr(e))
+        except Exception as e:
+            print("[SEED] count failed:", repr(e))
+
     return g.db  # type: ignore[return-value]
 
 
 @app.teardown_appcontext
 def close_db(_: Any) -> None:
     db = g.pop("db", None)
     if db is not None:
         db.close()
 
 
+def seed_import_questions(csv_path: str = "data/quiz_30.csv", conn: Optional[sqlite3.Connection] = None) -> None:
+    import csv
+    import json
+    import os
+
+    EXPECTED_HEADERS = [
+        "q_no",
+        "question",
+        "options_text",
+        "correct_answer",
+        "nf_level",
+        "concept_tag",
+        "explanation",
+        "two_category",
+    ]
+    ALLOWED = {
+        "Data Modeling & DBMS Fundamentals",
+        "Normalization & Dependencies",
+    }
+
+    if not os.path.exists(csv_path):
+        return
+
+    def _seed(connection: sqlite3.Connection) -> None:
+        try:
+            current = connection.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
+        except Exception:
+            return
+        if current >= 30:
+            return
+
+        existing = {
+            row["question"]
+            for row in connection.execute("SELECT question FROM quiz")
+        }
+
+        inserted = 0
+        try:
+            with open(csv_path, newline="", encoding="utf-8-sig") as handle:
+                reader = csv.DictReader(handle)
+                if reader.fieldnames != EXPECTED_HEADERS:
+                    return
+                for raw in reader:
+                    question = (raw.get("question") or "").strip()
+                    if not question or question in existing:
+                        continue
+                    two_category = (raw.get("two_category") or "").strip()
+                    if two_category not in ALLOWED:
+                        continue
+                    options_raw = raw.get("options_text", "")
+                    try:
+                        options = json.loads(options_raw)
+                    except Exception:
+                        continue
+                    if not isinstance(options, list) or len(options) != 4:
+                        continue
+                    options = [str(opt) for opt in options]
+                    correct = str(raw.get("correct_answer", ""))
+                    if correct not in options:
+                        continue
+
+                    connection.execute(
+                        """
+                        INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation, two_category)
+                        VALUES (?,?,?,?,?,?,?)
+                        """,
+                        (
+                            question,
+                            json.dumps(options, ensure_ascii=False),
+                            correct,
+                            raw.get("nf_level", ""),
+                            raw.get("concept_tag", ""),
+                            raw.get("explanation", ""),
+                            two_category,
+                        ),
+                    )
+                    existing.add(question)
+                    inserted += 1
+                    current += 1
+                    if current >= 30:
+                        break
+        finally:
+            if inserted:
+                connection.commit()
+
+    if conn is not None:
+        _seed(conn)
+    else:
+        db = get_db()
+        try:
+            _seed(db)
+        finally:
+            # ensure pending inserts are saved
+            db.commit()
+
+
 # --- Security / Auth ---
 
 def ensure_csrf_token() -> None:
     if not session.get("csrf_token"):
         session["csrf_token"] = secrets.token_hex(16)
 
 
 @app.before_request
 def before_request() -> None:
     ensure_csrf_token()
 
 
+def _redirect_login(role_hint: Optional[str] = None):
+    login_url = url_for("login", role=role_hint) if role_hint else url_for("login")
+    if request.path.startswith("/api/") or request.path == "/submit":
+        return redirect(login_url)
+    flash("Please log in to continue.")
+    return redirect(login_url)
+
+
+def _require_role(expected: Optional[str]):
+    def decorator(view):
+        @wraps(view)
+        def wrapped(*args, **kwargs):
+            role = session.get("role")
+            student_ok = role == "student" and session.get("student_id")
+            lecturer_ok = role == "lecturer" and session.get("lecturer_id")
+
+            allowed = False
+            if expected == "student":
+                allowed = bool(student_ok)
+            elif expected == "lecturer":
+                allowed = bool(lecturer_ok)
+            else:
+                allowed = bool(student_ok or lecturer_ok)
+
+            if allowed:
+                return view(*args, **kwargs)
+
+            role_hint = None
+            if expected == "lecturer":
+                role_hint = "lecturer"
+            elif expected == "student":
+                role_hint = "student"
+            return _redirect_login(role_hint)
+
+        return wrapped
+
+    return decorator
+
+
 def login_required(view):
-    @wraps(view)
-    def wrapped(*args, **kwargs):
-        if not session.get("student_id"):
-            # For JSON API calls, return 302 redirect to /login to satisfy acceptance
-            if request.path.startswith("/api/") or request.path == "/submit":
-                return redirect(url_for("login"))
-            flash("Please log in to continue.")
-            return redirect(url_for("login"))
-        return view(*args, **kwargs)
+    return _require_role(None)(view)
+
+
+def student_required(view):
+    return _require_role("student")(view)
 
-    return wrapped
+
+def lecturer_required(view):
+    return _require_role("lecturer")(view)
 
 
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
-    """
-    Returns mastery for the two concepts using live attempts only.
-
-    points per concept = accuracy% * 0.5  (so 100% accuracy == 50 pts)
-    pass per concept    = points >= 17.5  (35% of 50)
-    unlock              = both passed AND overall_points > 70
-    """
-    q = """
-    SELECT q.two_category AS cat,
-           ROUND(AVG(r.score)*100.0, 1) AS acc_pct,
-           COUNT(*) AS n
-    FROM response r
-    JOIN quiz q     ON q.quiz_id = r.quiz_id
-    JOIN attempt a  ON a.attempt_id = r.attempt_id
-    WHERE r.student_id = ?
-      AND a.source = 'live'
-      AND q.two_category IN ('Data Modeling & DBMS Fundamentals','Normalization & Dependencies')
-    GROUP BY q.two_category
-    """
+    empty = {
+        "fund": {"pct": 0.0, "pts": 0.0, "total": 0, "correct": 0},
+        "norm": {"pct": 0.0, "pts": 0.0, "total": 0, "correct": 0},
+        "overall_points": 0.0,
+    }
+
     with get_db() as conn:
-        rows = conn.execute(q, (student_id,)).fetchall()
+        quiz_cols = [row[1] for row in conn.execute("PRAGMA table_info(quiz)")]
+        attempt_cols = [row[1] for row in conn.execute("PRAGMA table_info(attempt)")]
+        if "two_category" not in quiz_cols:
+            return empty
+
+        source_guard = "IFNULL(source,'live')" if "source" in attempt_cols else "'live'"
+        attempt_row = conn.execute(
+            f"""
+            SELECT attempt_id
+            FROM attempt
+            WHERE student_id=?
+              AND {source_guard}='live'
+            ORDER BY started_at DESC
+            LIMIT 1
+            """,
+            (student_id,),
+        ).fetchone()
 
-    fund = {"acc_pct": 0.0, "attempts": 0}
-    norm = {"acc_pct": 0.0, "attempts": 0}
-    for r in rows:
-        acc = float(r["acc_pct"] or 0.0)
-        n   = int(r["n"] or 0)
-        if r["cat"] == "Data Modeling & DBMS Fundamentals":
-            fund = {"acc_pct": acc, "attempts": n}
-        elif r["cat"] == "Normalization & Dependencies":
-            norm = {"acc_pct": acc, "attempts": n}
+        if not attempt_row:
+            return empty
 
-    fund_points = round((fund["acc_pct"] / 100.0) * 50.0, 1)
-    norm_points = round((norm["acc_pct"] / 100.0) * 50.0, 1)
+        attempt_id = int(attempt_row["attempt_id"])
+        rows = conn.execute(
+            """
+            SELECT q.two_category AS cat,
+                   SUM(r.score) AS correct,
+                   COUNT(*) AS total
+            FROM response r
+            JOIN quiz q ON q.quiz_id = r.quiz_id
+            WHERE r.student_id=? AND r.attempt_id=?
+            GROUP BY q.two_category
+            """,
+            (student_id, attempt_id),
+        ).fetchall()
+
+    fund_total = fund_correct = 0
+    norm_total = norm_correct = 0
+    for row in rows:
+        cat = row["cat"]
+        total = int(row["total"] or 0)
+        correct = int(row["correct"] or 0)
+        if cat == "Data Modeling & DBMS Fundamentals":
+            fund_total = total
+            fund_correct = correct
+        elif cat == "Normalization & Dependencies":
+            norm_total = total
+            norm_correct = correct
+
+    fund_pct = round(100.0 * fund_correct / fund_total, 1) if fund_total else 0.0
+    norm_pct = round(100.0 * norm_correct / norm_total, 1) if norm_total else 0.0
+    fund_points = round((fund_pct / 100.0) * 50.0, 1)
+    norm_points = round((norm_pct / 100.0) * 50.0, 1)
     overall_points = round(fund_points + norm_points, 1)
 
-    PASS = 17.5  # 35% of 50
-    unlocked_next = (fund_points >= PASS and norm_points >= PASS and overall_points > 70.0)
-
     return {
-        "fund": fund, "norm": norm,
-        "fund_points": fund_points,
-        "norm_points": norm_points,
+        "fund": {
+            "pct": fund_pct,
+            "pts": fund_points,
+            "total": fund_total,
+            "correct": fund_correct,
+        },
+        "norm": {
+            "pct": norm_pct,
+            "pts": norm_points,
+            "total": norm_total,
+            "correct": norm_correct,
+        },
         "overall_points": overall_points,
-        "pass_threshold": PASS,
-        "unlocked_next": unlocked_next,
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
-    """Find the next concept the student should focus on."""
-    concept_order = [
-        "Functional Dependency",
-        "Atomic Values", 
-        "Partial Dependency",
-        "Transitive Dependency",
-    ]
-    
-    db = get_db()
-    for tag in concept_order:
-        cur = db.execute(
-            "SELECT mastered FROM student_mastery WHERE student_id=? AND concept_tag=?",
-            (student_id, tag),
-        )
-        row = cur.fetchone()
-        if not row or int(row["mastered"]) == 0:
-            return tag
+    """Determine which concept still needs a perfect score."""
+    mastery = get_two_category_mastery(student_id)
+    fund = mastery.get("fund", {}) if isinstance(mastery, dict) else {}
+    norm = mastery.get("norm", {}) if isinstance(mastery, dict) else {}
+    if float(fund.get("pct", 0.0)) < 100.0:
+        return "Data Modeling & DBMS Fundamentals"
+    if float(norm.get("pct", 0.0)) < 100.0:
+        return "Normalization & Dependencies"
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
-        cur = db.execute("SELECT student_id FROM student WHERE email=?", (email,))
+        cur = db.execute(
+            "SELECT student_id, name FROM student WHERE email=?",
+            (email,),
+        )
         row = cur.fetchone()
+        session.clear()
+        session["role"] = "student"
         session["student_id"] = row["student_id"]
+        session["student_name"] = row["name"]
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
+        desired_role = request.args.get("role")
+
+        if not email or not password:
+            flash("Please provide email and password.")
+            return redirect(url_for("login", role=desired_role) if desired_role else url_for("login"))
+
         db = get_db()
-        cur = db.execute(
-            "SELECT student_id, password_hash FROM student WHERE email=?",
-            (email,),
-        )
-        row = cur.fetchone()
-        if not row or not check_password_hash(row["password_hash"], password):
-            flash("Invalid credentials.")
-            return redirect(url_for("login"))
 
-        session["student_id"] = row["student_id"]
-        flash("Logged in.")
-        return redirect(url_for("student_dashboard", student_id=row["student_id"]))
+        student = db.execute(
+            "SELECT student_id, name, password_hash FROM student WHERE lower(email)=?",
+            (email,),
+        ).fetchone()
+        if student:
+            stored = student["password_hash"] or ""
+            if stored == "" or check_password_hash(stored, password):
+                session.clear()
+                session["role"] = "student"
+                session["student_id"] = student["student_id"]
+                session["student_name"] = student["name"]
+                flash("Logged in.")
+
+                latest = db.execute(
+                    """
+                    SELECT attempt_id FROM attempt
+                    WHERE student_id=?
+                    ORDER BY started_at DESC
+                    LIMIT 1
+                    """,
+                    (student["student_id"],),
+                ).fetchone()
+
+                if latest:
+                    return redirect(url_for("review_attempt", attempt_id=latest["attempt_id"]))
+                return redirect(url_for("quiz"))
+
+        lecturer = db.execute(
+            "SELECT lecturer_id, name, password_hash FROM lecturer WHERE lower(email)=?",
+            (email,),
+        ).fetchone()
+        if lecturer:
+            stored_lect = lecturer["password_hash"] or ""
+            if stored_lect and check_password_hash(stored_lect, password):
+                session.clear()
+                session["role"] = "lecturer"
+                session["lecturer_id"] = lecturer["lecturer_id"]
+                session["lecturer_name"] = lecturer["name"]
+                flash("Welcome back.")
+                return redirect(url_for("admin_overview"))
+
+        flash("Invalid credentials.")
+        return redirect(url_for("login", role=desired_role) if desired_role else url_for("login"))
 
     return render_template("login.html")
 
 
 @app.route("/logout")
 def logout():
     session.clear()
     flash("Logged out.")
     return redirect(url_for("index"))
 
 
 @app.route("/quiz")
-@login_required
+@student_required
 def quiz():
-    return render_template("quiz.html")
+    student_id = int(session["student_id"])  # never trust posted ids
+    attempt_id = _get_or_create_open_attempt(student_id)
+    questions = _select_questions_payload()
+
+    if not questions:
+        flash("Quiz is not available right now. Please try again shortly.")
+        return redirect(url_for("student_dashboard", student_id=student_id))
+
+    db = get_db()
+    try:
+        db.execute(
+            "UPDATE attempt SET items_total=? WHERE attempt_id=?",
+            (len(questions), attempt_id),
+        )
+        db.commit()
+    except Exception as exc:
+        print("[QUIZ] Failed to store attempt length:", repr(exc))
+
+    return render_template(
+        "quiz.html",
+        questions=questions,
+        attempt_id=attempt_id,
+        student_id=student_id,
+    )
 
 
 @app.route("/reattempt")
-@login_required
+@student_required
 def reattempt():
     """Create a new attempt and redirect to quiz."""
     student_id = int(session["student_id"])
     attempt_id = _get_or_create_open_attempt(student_id)
     return redirect(url_for("quiz"))
 
 
 def _get_or_create_open_attempt(student_id: int) -> int:
     db = get_db()
+    try:
+        exists = db.execute(
+            "SELECT 1 FROM student WHERE student_id=?",
+            (student_id,),
+        ).fetchone()
+    except Exception:
+        exists = None
+    if not exists:
+        try:
+            db.execute(
+                """
+                INSERT OR IGNORE INTO student (student_id, name, email, program, password_hash)
+                VALUES (?,?,?,?,?)
+                """,
+                (
+                    student_id,
+                    f"Student {student_id}",
+                    f"student{student_id}@example.com",
+                    "",
+                    generate_password_hash("temp"),
+                ),
+            )
+            db.commit()
+        except Exception as exc:
+            print("[ATTEMPT] Failed to ensure student row:", repr(exc))
+
     cur = db.execute(
         "SELECT attempt_id FROM attempt WHERE student_id=? AND finished_at IS NULL ORDER BY started_at DESC LIMIT 1",
         (student_id,),
     )
     row = cur.fetchone()
     if row:
         return int(row["attempt_id"])
     started_at = datetime.utcnow().isoformat()
-    db.execute(
-        "INSERT INTO attempt (student_id, nf_scope, started_at, items_total, items_correct, score_pct) VALUES (?,?,?,?,?,?)",
-        (student_id, "FD+1NF+2NF+3NF", started_at, 10, 0, 0.0),
+    attempt_cols = [r[1] for r in db.execute("PRAGMA table_info(attempt)")]
+    params = (
+        student_id,
+        "Data Modeling & DBMS Fundamentals + Normalization & Dependencies",
+        started_at,
+        0,
+        0,
+        0.0,
     )
+    if "source" in attempt_cols:
+        db.execute(
+            """
+            INSERT INTO attempt (student_id, nf_scope, started_at, items_total, items_correct, score_pct, source)
+            VALUES (?,?,?,?,?,?,?)
+            """,
+            params + ("live",),
+        )
+    else:
+        db.execute(
+            "INSERT INTO attempt (student_id, nf_scope, started_at, items_total, items_correct, score_pct) VALUES (?,?,?,?,?,?)",
+            params,
+        )
     db.commit()
     cur = db.execute(
         "SELECT attempt_id FROM attempt WHERE student_id=? AND started_at=?",
         (student_id, started_at),
     )
     return int(cur.fetchone()["attempt_id"])  # type: ignore[index]
 
 
-def _select_questions_payload() -> List[Dict[str, Any]]:
+def _select_questions_payload(total: int = 30) -> List[Dict[str, Any]]:
     db = get_db()
-    blueprint = [("FD", 3), ("1NF", 3), ("2NF", 2), ("3NF", 2)]
+    categories = [
+        "Data Modeling & DBMS Fundamentals",
+        "Normalization & Dependencies",
+    ]
+    per_category = max(1, total // max(len(categories), 1))
     questions: List[Dict[str, Any]] = []
-    for nf_level, need in blueprint:
+    seen: set[int] = set()
+
+    for cat in categories:
         cur = db.execute(
-            "SELECT quiz_id, question, options_text, concept_tag FROM quiz WHERE nf_level=? ORDER BY RANDOM() LIMIT ?",
-            (nf_level, need),
+            """
+            SELECT quiz_id, question, options_text, concept_tag, nf_level
+            FROM quiz
+            WHERE two_category = ?
+            ORDER BY RANDOM()
+            LIMIT ?
+            """,
+            (cat, per_category),
         )
         for row in cur.fetchall():
-            options = safe_parse_options(row["options_text"]) if row["options_text"] else []
+            qid = int(row["quiz_id"])
+            if qid in seen:
+                continue
+            options = safe_parse_options(row["options_text"] or "[]")
+            if len(options) != 4:
+                continue
             questions.append(
                 {
-                    "quiz_id": int(row["quiz_id"]),
+                    "quiz_id": qid,
                     "question": row["question"],
                     "options": options,
-                    "nf_level": nf_level,
+                    "nf_level": row["nf_level"],
                     "concept_tag": row["concept_tag"],
                 }
             )
-    return questions
+            seen.add(qid)
+
+    if len(questions) < total:
+        remaining = total - len(questions)
+        placeholders = ",".join(["?"] * len(categories))
+        cur = db.execute(
+            f"""
+            SELECT quiz_id, question, options_text, concept_tag, nf_level
+            FROM quiz
+            WHERE two_category IN ({placeholders})
+            ORDER BY RANDOM()
+            LIMIT ?
+            """,
+            (*categories, remaining),
+        )
+        for row in cur.fetchall():
+            qid = int(row["quiz_id"])
+            if qid in seen:
+                continue
+            options = safe_parse_options(row["options_text"] or "[]")
+            if len(options) != 4:
+                continue
+            questions.append(
+                {
+                    "quiz_id": qid,
+                    "question": row["question"],
+                    "options": options,
+                    "nf_level": row["nf_level"],
+                    "concept_tag": row["concept_tag"],
+                }
+            )
+            seen.add(qid)
+            if len(questions) >= total:
+                break
+
+    random.shuffle(questions)
+    return questions[:total]
 
 
 @app.route("/api/quiz_progressive")
-@login_required
+@student_required
 def api_quiz_progressive():
     student_id = int(session["student_id"])  # never trust posted student_id
     attempt_id = _get_or_create_open_attempt(student_id)
     questions = _select_questions_payload()
+    if not questions:
+        return jsonify({"error": "quiz unavailable"}), 503
+
+    db = get_db()
+    try:
+        db.execute(
+            "UPDATE attempt SET items_total=? WHERE attempt_id=?",
+            (len(questions), attempt_id),
+        )
+        db.commit()
+    except Exception as exc:
+        print("[QUIZ] Failed to update attempt total:", repr(exc))
+
     return jsonify({"attempt_id": attempt_id, "questions": questions})
 
 
 @app.route("/submit", methods=["POST"]) 
-@login_required
+@student_required
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
@@ -487,245 +896,535 @@ def submit():
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
 
+    session["last_attempt_id"] = attempt_id
+
+    print(
+        f"[SUBMIT] sid={student_id} attempt={attempt_id} total={total} correct={correct} pct={round(score_pct, 1)}"
+    )
+
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
-@login_required
+@student_required
 def student_dashboard(student_id: int):
     current_student_id = int(session["student_id"])  # never trust URL param
     if student_id != current_student_id:
         flash("Access restricted to your own dashboard.")
         return redirect(url_for("student_dashboard", student_id=current_student_id))
 
     db = get_db()
 
-    # Attempts history
     cur = db.execute(
         "SELECT attempt_id, started_at, score_pct FROM attempt WHERE student_id=? AND score_pct IS NOT NULL ORDER BY started_at ASC",
         (current_student_id,),
     )
     attempts = cur.fetchall()
-    labels = [f"A{idx+1}" for idx, _ in enumerate(attempts)]
+    labels = [f"A{idx + 1}" for idx, _ in enumerate(attempts)]
     scores = [float(a["score_pct"]) for a in attempts]
 
-    # Last attempt details
     cur = db.execute(
-        "SELECT attempt_id, started_at, score_pct FROM attempt WHERE student_id=? AND items_total IS NOT NULL ORDER BY started_at DESC LIMIT 1",
+        "SELECT attempt_id, started_at, score_pct FROM attempt WHERE student_id=? ORDER BY started_at DESC LIMIT 1",
         (current_student_id,),
     )
     last = cur.fetchone()
-    last_details: List[Dict[str, Any]] = []
-    if last:
-        cur = db.execute(
+
+    two_cat = get_two_category_mastery(current_student_id)
+    fund = two_cat.get("fund", {})
+    norm = two_cat.get("norm", {})
+    unlocked_next = (
+        float(fund.get("pct", 0.0)) == 100.0 and float(norm.get("pct", 0.0)) == 100.0
+    )
+
+    return render_template(
+        "student_dashboard.html",
+        labels=labels,
+        scores=scores,
+        last_attempt=last,
+        two_cat=two_cat,
+        unlocked_next=unlocked_next,
+        next_topic_name="Next Topic (Prototype End)",
+    )
+
+
+@app.route("/review/<int:attempt_id>")
+@student_required
+def review_attempt(attempt_id: int):
+    sid = int(session["student_id"])
+    with get_db() as conn:
+        att = conn.execute(
+            """
+            SELECT attempt_id, started_at, finished_at, score_pct, items_total, items_correct,
+                   IFNULL(source,'live') AS source
+            FROM attempt
+            WHERE attempt_id=? AND student_id=?
+            """,
+            (attempt_id, sid),
+        ).fetchone()
+        if not att:
+            flash("Attempt not found.", "error")
+            return redirect(url_for("student_dashboard", student_id=sid))
+
+        rows = conn.execute(
             """
-            SELECT q.question, r.answer, q.correct_answer, q.explanation, q.concept_tag,
-                   r.response_time_s, r.score
+            SELECT q.quiz_id, q.question, q.correct_answer, q.explanation, q.two_category,
+                   r.answer AS your_answer, r.score AS is_correct, r.response_time_s
             FROM response r
             JOIN quiz q ON q.quiz_id = r.quiz_id
-            WHERE r.attempt_id = ?
-            ORDER BY r.response_id ASC
+            WHERE r.student_id=? AND r.attempt_id=?
+            ORDER BY q.quiz_id
             """,
-            (last["attempt_id"],),
-        )
-        for row in cur.fetchall():
-            t = float(row["response_time_s"]) if row["response_time_s"] is not None else 0.0
-            last_details.append(
-                {
-                    "question": row["question"],
-                    "answer": row["answer"],
-                    "correct_answer": row["correct_answer"],
-                    "explanation": row["explanation"],
-                    "concept_tag": row["concept_tag"],
-                    "response_time_s": t,
-                    "time_category": categorize_time(t),
-                    "score": int(row["score"]) if row["score"] is not None else 0,
-                }
-            )
+            (sid, attempt_id),
+        ).fetchall()
 
-    # Per-concept metrics (last attempt) plus mastery state - NO TIME DISPLAY
-    per_concept: List[Dict[str, Any]] = []
-    if last:
-        cur = db.execute(
+        split = conn.execute(
+            """
+            SELECT q.two_category AS cat, SUM(r.score) AS correct, COUNT(*) AS total
+            FROM response r JOIN quiz q ON q.quiz_id=r.quiz_id
+            WHERE r.student_id=? AND r.attempt_id=?
+            GROUP BY q.two_category
+            """,
+            (sid, attempt_id),
+        ).fetchall()
+
+    fund_total = fund_correct = norm_total = norm_correct = 0
+    for r in split:
+        if r["cat"] == "Data Modeling & DBMS Fundamentals":
+            fund_correct = int(r["correct"] or 0)
+            fund_total = int(r["total"] or 0)
+        elif r["cat"] == "Normalization & Dependencies":
+            norm_correct = int(r["correct"] or 0)
+            norm_total = int(r["total"] or 0)
+
+    fund_pct = round(100 * fund_correct / fund_total, 1) if fund_total else 0.0
+    norm_pct = round(100 * norm_correct / norm_total, 1) if norm_total else 0.0
+    unlocked_next = fund_pct == 100.0 and norm_pct == 100.0
+
+    return render_template(
+        "review.html",
+        attempt=att,
+        items=rows,
+        fund_pct=fund_pct,
+        norm_pct=norm_pct,
+        unlocked_next=unlocked_next,
+        next_topic_name="Next Topic (Prototype End)",
+    )
+
+
+@app.route("/admin")
+@lecturer_required
+def admin_overview():
+    with get_db() as conn:
+        totals = conn.execute(
+            """
+            SELECT
+              (SELECT COUNT(*) FROM student) AS students_total,
+              (SELECT COUNT(*) FROM attempt) AS attempts_total,
+              (SELECT COUNT(*) FROM response) AS responses_total,
+              (SELECT COUNT(DISTINCT attempt_id) FROM response) AS attempts_with_responses
+            """,
+        ).fetchone()
+
+        by_cat = conn.execute(
             """
-            SELECT q.concept_tag AS concept_tag,
-                   100.0 * SUM(r.score) / COUNT(*) AS acc_pct
+            SELECT q.two_category AS cat,
+                   ROUND(AVG(r.score) * 100, 1) AS acc_pct,
+                   COUNT(*) AS n_responses
             FROM response r
             JOIN quiz q ON q.quiz_id = r.quiz_id
-            WHERE r.attempt_id = ?
-            GROUP BY q.concept_tag
-            ORDER BY q.concept_tag
+            GROUP BY q.two_category
+            ORDER BY q.two_category
             """,
-            (last["attempt_id"],),
-        )
-        for row in cur.fetchall():
-            tag = row["concept_tag"]
-            acc = float(row["acc_pct"]) if row["acc_pct"] is not None else 0.0
-            mcur = db.execute(
-                "SELECT mastered FROM student_mastery WHERE student_id=? AND concept_tag=?",
-                (current_student_id, tag),
-            )
-            mrow = mcur.fetchone()
-            per_concept.append(
-                {
-                    "concept_tag": tag,
-                    "acc_pct": acc,
-                    "mastered": int(mrow["mastered"]) if mrow else 0,
-                }
+        ).fetchall()
+
+        recent_all = conn.execute(
+            """
+            SELECT substr(started_at, 1, 10) AS day, COUNT(*) AS n
+            FROM attempt
+            GROUP BY day
+            ORDER BY day DESC
+            LIMIT 14
+            """,
+        ).fetchall()
+
+        recent_with_resp = conn.execute(
+            """
+            SELECT t.day, COUNT(DISTINCT a.attempt_id) AS n
+            FROM (
+                SELECT substr(started_at, 1, 10) AS day, attempt_id
+                FROM attempt
+            ) a
+            JOIN response r ON r.attempt_id = a.attempt_id
+            JOIN (
+                SELECT substr(started_at, 1, 10) AS day
+                FROM attempt
+                GROUP BY 1
+            ) t ON t.day = a.day
+            GROUP BY t.day
+            ORDER BY t.day DESC
+            LIMIT 14
+            """,
+        ).fetchall()
+
+    all_map = {row["day"]: int(row["n"] or 0) for row in recent_all}
+    resp_map = {row["day"]: int(row["n"] or 0) for row in recent_with_resp}
+    days = sorted(set(all_map.keys()) | set(resp_map.keys()))
+    labels = days[-14:]
+    counts_all = [all_map.get(day, 0) for day in labels]
+    counts_resp = [resp_map.get(day, 0) for day in labels]
+
+    return render_template(
+        "admin_overview.html",
+        totals=totals,
+        by_cat=by_cat,
+        labels=labels,
+        counts_all=counts_all,
+        counts_resp=counts_resp,
+    )
+
+
+@app.route("/admin/students")
+@lecturer_required
+def admin_students():
+    with get_db() as conn:
+        students = conn.execute(
+            """
+            SELECT s.student_id, s.name, s.email,
+                   COALESCE(a.cnt, 0) AS attempts
+            FROM student s
+            LEFT JOIN (
+                SELECT student_id, COUNT(*) AS cnt
+                FROM attempt
+                GROUP BY student_id
+            ) a USING (student_id)
+            ORDER BY s.name
+            """,
+        ).fetchall()
+    return render_template("admin_students.html", students=students)
+
+
+@app.route("/admin/students/<int:sid>")
+@lecturer_required
+def admin_student_detail(sid: int):
+    with get_db() as conn:
+        stu = conn.execute(
+            "SELECT student_id, name, email FROM student WHERE student_id=?",
+            (sid,),
+        ).fetchone()
+        if not stu:
+            flash("Student not found.", "error")
+            return redirect(url_for("admin_students"))
+
+        attempts = conn.execute(
+            """
+            SELECT attempt_id, started_at, finished_at, score_pct, items_total, items_correct
+            FROM attempt
+            WHERE student_id=?
+            ORDER BY started_at DESC
+            """,
+            (sid,),
+        ).fetchall()
+
+        latest = conn.execute(
+            """
+            SELECT attempt_id
+            FROM attempt
+            WHERE student_id=?
+            ORDER BY started_at DESC
+            LIMIT 1
+            """,
+            (sid,),
+        ).fetchone()
+
+        split = []
+        if latest:
+            split = conn.execute(
+                """
+                SELECT q.two_category AS cat,
+                       SUM(r.score) AS correct,
+                       COUNT(*) AS total,
+                       ROUND(100.0 * SUM(r.score) / COUNT(*), 1) AS pct
+                FROM response r
+                JOIN quiz q ON q.quiz_id = r.quiz_id
+                WHERE r.student_id=? AND r.attempt_id=?
+                GROUP BY q.two_category
+                """,
+                (sid, latest["attempt_id"]),
+            ).fetchall()
+
+    return render_template(
+        "admin_student_detail.html",
+        stu=stu,
+        attempts=attempts,
+        split=split,
+    )
+
+
+@app.route("/admin/questions")
+@lecturer_required
+def admin_questions():
+    with get_db() as conn:
+        qs = conn.execute(
+            """
+            SELECT q.quiz_id, q.two_category, q.question,
+                   ROUND(AVG(r.score) * 100, 1) AS correct_rate,
+                   COUNT(r.response_id) AS n
+            FROM quiz q
+            LEFT JOIN response r ON r.quiz_id = q.quiz_id
+            WHERE q.two_category IN (
+                'Data Modeling & DBMS Fundamentals',
+                'Normalization & Dependencies'
             )
+            GROUP BY q.quiz_id
+            ORDER BY q.two_category, q.quiz_id
+            """,
+        ).fetchall()
+    return render_template("admin_questions.html", qs=qs)
 
-    # Next step concept
-    next_step = next_step_concept(current_student_id)
-    
-    # Get next step concept accuracy for gauge
-    next_step_accuracy = 0.0
-    if next_step and last:
-        cur = db.execute(
+
+@app.route("/admin/analytics")
+@lecturer_required
+def admin_analytics():
+    with get_db() as conn:
+        per_student_qtime = conn.execute(
             """
-            SELECT 100.0 * SUM(r.score) / COUNT(*) AS acc_pct
+            SELECT s.name AS student, s.email,
+                   q.quiz_id, q.question,
+                   ROUND(AVG(r.response_time_s), 2) AS avg_time_s,
+                   COUNT(*) AS n
             FROM response r
+            JOIN student s ON s.student_id = r.student_id
             JOIN quiz q ON q.quiz_id = r.quiz_id
-            WHERE r.attempt_id = ? AND q.concept_tag = ?
+            GROUP BY r.student_id, q.quiz_id
+            ORDER BY s.name, q.quiz_id
             """,
-            (last["attempt_id"], next_step),
-        )
-        row = cur.fetchone()
-        if row and row["acc_pct"] is not None:
-            next_step_accuracy = float(row["acc_pct"])
+        ).fetchall()
+
+        qtime_summary = conn.execute(
+            """
+            SELECT q.quiz_id, q.question,
+                   ROUND(AVG(r.response_time_s), 2) AS avg_time_s,
+                   ROUND(MIN(r.response_time_s), 2) AS min_time_s,
+                   ROUND(MAX(r.response_time_s), 2) AS max_time_s,
+                   COUNT(*) AS n
+            FROM response r
+            JOIN quiz q ON q.quiz_id = r.quiz_id
+            GROUP BY q.quiz_id
+            ORDER BY q.quiz_id
+            """,
+        ).fetchall()
+
+        slowest = conn.execute(
+            """
+            SELECT q.quiz_id, q.question,
+                   ROUND(AVG(r.response_time_s), 2) AS avg_time_s,
+                   COUNT(*) AS n
+            FROM response r
+            JOIN quiz q ON q.quiz_id = r.quiz_id
+            GROUP BY q.quiz_id
+            HAVING n >= 5
+            ORDER BY avg_time_s DESC
+            LIMIT 5
+            """,
+        ).fetchall()
+
+        fastest = conn.execute(
+            """
+            SELECT q.quiz_id, q.question,
+                   ROUND(AVG(r.response_time_s), 2) AS avg_time_s,
+                   COUNT(*) AS n
+            FROM response r
+            JOIN quiz q ON q.quiz_id = r.quiz_id
+            GROUP BY q.quiz_id
+            HAVING n >= 5
+            ORDER BY avg_time_s ASC
+            LIMIT 5
+            """,
+        ).fetchall()
 
-    two_cat = get_two_category_mastery(current_student_id)
     return render_template(
-        "student_dashboard.html",
-        labels=labels,
-        scores=scores,
-        last_details=last_details,
-        per_concept=per_concept,
-        next_step=next_step,
-        next_step_accuracy=next_step_accuracy,
-        last_attempt=last,
-        two_cat=two_cat,
+        "admin_analytics.html",
+        per_student_qtime=per_student_qtime,
+        qtime_summary=qtime_summary,
+        slowest=slowest,
+        fastest=fastest,
     )
 
 
+@app.route("/admin/rankings")
+@lecturer_required
+def admin_rankings():
+    with get_db() as conn:
+        rows = conn.execute(
+            """
+            WITH per_student AS (
+                SELECT a.student_id,
+                       COUNT(*) AS attempts,
+                       ROUND(AVG(a.score_pct), 1) AS avg_score,
+                       ROUND(MAX(a.score_pct), 1) AS best_score,
+                       (
+                           SELECT ROUND(a2.score_pct, 1)
+                           FROM attempt a2
+                           WHERE a2.student_id = a.student_id
+                           ORDER BY a2.started_at DESC
+                           LIMIT 1
+                       ) AS last_score
+                FROM attempt a
+                GROUP BY a.student_id
+            )
+            SELECT s.student_id, s.name, s.email,
+                   p.attempts, p.avg_score, p.best_score, p.last_score
+            FROM per_student p
+            JOIN student s ON s.student_id = p.student_id
+            ORDER BY p.avg_score DESC, p.attempts DESC, s.name
+            """,
+        ).fetchall()
+
+    return render_template("admin_rankings.html", rows=rows)
+
+
 @app.route("/modules")
-@login_required
+@student_required
 def modules():
     """Show all available modules."""
     db = get_db()
     cur = db.execute(
-        "SELECT module_id, title, description, nf_level, concept_tag, resource_url FROM module ORDER BY module_id"
+        """
+        SELECT title, description, resource_url
+        FROM module
+        WHERE resource_url IN ('/module/fundamentals','/module/norm')
+        ORDER BY title
+        """
     )
-    modules = cur.fetchall()
-    return render_template("modules.html", modules=modules)
+    rows = cur.fetchall()
+
+    modules = []
+    for row in rows:
+        link = row["resource_url"] or ""
+        title = row["title"]
+        if not link.startswith("/"):
+            link = "/module/fundamentals" if "fund" in (title or "").lower() else "/module/norm"
+        modules.append(
+            {
+                "title": title,
+                "description": row["description"],
+                "resource_url": link,
+            }
+        )
 
+    if not modules:
+        modules = [
+            {
+                "title": "Data Modeling & DBMS Fundamentals",
+                "description": "Understand core modeling concepts and DBMS components.",
+                "resource_url": "/module/fundamentals",
+            },
+            {
+                "title": "Normalization & Dependencies",
+                "description": "Practice normalization steps and dependency analysis.",
+                "resource_url": "/module/norm",
+            },
+        ]
 
-@app.route("/module/<int:module_id>")
-@login_required
-def module_page(module_id: int):
-    db = get_db()
-    cur = db.execute(
-        "SELECT module_id, title, description, nf_level, concept_tag, resource_url FROM module WHERE module_id=?",
-        (module_id,),
-    )
-    module = cur.fetchone()
-    if not module:
-        flash("Module not found.")
-        return redirect(url_for("index"))
-    return render_template("module.html", module=module)
+    return render_template("modules.html", modules=modules)
 
 
 @app.route("/module/fundamentals")
-@login_required
+@student_required
 def module_fundamentals():
     return render_template("module_fundamentals.html")
 
 
 @app.route("/module/norm")
-@login_required
+@student_required
 def module_norm():
     return render_template("module_norm.html")
 
 
 @app.route("/api/module_progress", methods=["POST"])
-@login_required
+@student_required
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
-@login_required
+@student_required
 def thanks_page():
     return render_template("thanks.html")
 
 
 @app.route("/api/feedback", methods=["POST"])
-@login_required
+@student_required
 def api_feedback():
     data = request.get_json(force=True) or {}
-    rating = int(data.get("rating", 0))
+    try:
+        rating = int(data.get("rating", 0))
+    except (TypeError, ValueError):
+        rating = 0
     comment = (data.get("comment") or "").strip()
     if rating < 1 or rating > 5:
         return jsonify({"ok": False, "error": "Invalid rating"}), 400
     sid = int(session.get("student_id"))
     with get_db() as conn:
         conn.execute("INSERT INTO feedback (student_id, rating, comment) VALUES (?,?,?)",
                      (sid, rating, comment))
         conn.commit()
+    print(f"[FEEDBACK] sid={sid} rating={rating} comment_len={len(comment)}")
     return jsonify({"ok": True})
 
 
 if __name__ == "__main__":
     app.run(debug=True)  # for local development
