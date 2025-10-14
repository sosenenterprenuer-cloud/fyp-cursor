# Normalization Quiz (Flask + SQLite)

A self-contained Flask web app for practicing database normalization concepts with login, quizzes, scoring, mastery tracking, and recommendations.

## Features
- Auth (register/login/logout) with hashed passwords
- Progressive quiz assembly (10 Q: 3 FD, 3 1NF, 2 2NF, 2 3NF)
- Scoring and detailed feedback with time categories (Fast/Normal/Slow)
- Mastery per concept and recommendations
- Student dashboard with score chart and per-concept cards
- Modules page for learning resources

## Local setup

- Ensure Python 3.10+ and `pip` are installed.
- Install deps: `pip install -r requirements.txt` (if using a venv, activate it first).
- Initialize the SQLite database one of two ways:
  - Automatic: The app creates tables on first run when it can't find the `student` table.
  - Manual: Run `python -m app.init_db` (optionally set `PLA_DB=/path/to/db.sqlite`).

The database filename defaults to `pla.db` in the project root. Override with `PLA_DB` env var.

## Stack
- Python 3.11, Flask, Jinja2
- SQLite3 (no ORM), python-dotenv
- Chart.js (CDN)
- pytest

## Setup & Run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -c "import os,sqlite3; db=os.getenv('PLA_DB','pla.db'); con=sqlite3.connect(db); con.executescript(open('schema.sql').read()); con.executescript(open('seed.sql').read()); con.close()"
python app.py
# open http://localhost:5000
```

Environment variables:
- `FLASK_SECRET`: Flask secret key
- `PLA_DB`: SQLite database file (default `pla.db`)

## Endpoints
- `GET /` Home
- `GET/POST /register` Register
- `GET/POST /login` Login
- `GET /logout` Logout
- `GET /quiz` Quiz page (protected)
- `GET /api/quiz_progressive` Progressive quiz API (protected)
- `POST /submit` Submit answers API (protected)
- `GET /student/<student_id>` Student dashboard (protected)
- `GET /module/<module_id>` Module details

## Mastery & Recommendations
- Mastery per concept (within an attempt) when: total ≥ 3 AND accuracy ≥ 80% AND avg_time ≤ 20s.
- Recommendation when accuracy < 70% OR avg_time > 20s: "Review [tag] module."

## Notes
- All protected routes use a `@login_required` decorator
- Never trusts posted `student_id`; uses `session['student_id']`
- SQLite FKs are enabled per-connection
- CSRF token for HTML forms (session-based)

## Screenshots
- Dashboard chart and cards (placeholder)
- Quiz flow (placeholder)
