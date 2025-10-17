# Personalized Learning Recommendation AI

A Flask + SQLite prototype that delivers a 30-question assessment covering two database topics: **Data Modeling & DBMS Fundamentals** and **Normalization & Dependencies**. Students complete randomized attempts, review their answers with explanations, and progress toward a personalized recommendation. Lecturers receive read-only dashboards for activity tracking and analytics.

## Features

- 🔐 Unified login for students and lecturers with secure password hashing.
- 🧑‍🎓 Student flow with randomized 30-question attempts, per-question review, topic splits, history, and lifetime-best unlock logic.
- 🧑‍🏫 Lecturer dashboards summarizing attempts, responses, rankings, timing analytics, and question accuracy.
- 💬 Feedback capture route that redirects back to the latest review with confirmation messaging.
- 🛡️ Defensive database initialization that is idempotent and enforces schema guards.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r app/requirements.txt
export FLASK_APP=app.app  # Windows: set FLASK_APP=app.app
python -m flask run --app app.app --debug
```

The application stores data in `pla.db` by default. Override the location with `PLA_DB=/path/to/pla.db`. Set `PLA_RESET=1` for a clean rebuild on the next launch.

## Runbook (Windows)

```cmd
cd app
set PLA_DB=%cd%\pla.db
set PLA_RESET=1
python app.py

:: stop, then
set PLA_RESET=
python scripts\cleanup_legacy.py
python scripts\seed_demo.py
python app.py

:: Later, to import the MS Forms sample
python scripts\backup_db.py
python scripts\seed_from_msforms_csv.py
```

## Reset + Seed 17 (text-only, no binaries)

Use the scripted reset when you need a clean slate with the 30-question bank preserved but refreshed student data.

```cmd
cd app
set PLA_DB=%cd%\pla.db
python scripts\backup_db.py
python scripts\reset_and_seed_17.py
```

The script wipes all students, attempts, responses, and feedback entries, then seeds 17 named students with one completed
attempt each (varied accuracy). It leaves the quiz table untouched and aborts if the question bank is not exactly 30 rows.

## Included scripts

| Script | Description |
| ------ | ----------- |
| `app/scripts/cleanup_legacy.py` | Removes quiz rows outside the two supported topics and prints the remaining question count. |
| `app/scripts/seed_demo.py` | Ensures the default lecturer and a `demo@student.edu / demo123` student exist. |
| `app/scripts/backup_db.py` | Copies the active database to `backups/pla_YYYYMMDD_HHMM.db`. |
| `app/scripts/seed_from_msforms_csv.py` | Imports 30-question attempts for 17 students from `app/data/msforms_30q_17students.csv`. |
| `app/scripts/reset_and_seed_17.py` | Wipes student data and seeds 17 students with one attempt each using embedded records. |
| `app/scripts/selftest.py` | Smoke test that validates schema, quiz count, and the review route. |

All scripts assume the same environment variables as the application (`PLA_DB`, optional `PLA_RESET`).

## Self-test

Run the bundled smoke test after provisioning:

```bash
python app/scripts/selftest.py
```

Expected output: `SELFTEST OK`.

## Data files

- `app/data/msforms_30q_17students.csv` – sample MS Forms export with 17 students and 30 point columns.

## Default credentials

- Lecturer: `admin@lct.edu` / `Admin123!`
- Demo student: `demo@student.edu` / `demo123`
