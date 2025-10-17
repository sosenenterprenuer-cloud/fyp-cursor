"""Test configuration and fixtures."""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

APP_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = APP_DIR.parent

# Ensure both the package root and script directory are importable
sys.path.insert(0, str(REPO_ROOT))
if str(APP_DIR) not in sys.path:
    sys.path.insert(1, str(APP_DIR))

from app import app
from app.app import get_db


@pytest.fixture
def client():
    """Create test client with isolated database configuration."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.environ['PLA_DB'] = db_path

    try:
        base_dir = Path(__file__).resolve().parent.parent
        schema_sql = (base_dir / 'schema.sql').read_text(encoding='utf-8')
        seed_sql = (base_dir / 'seed.sql').read_text(encoding='utf-8')

        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(schema_sql)
            conn.executescript(seed_sql)
            cols = [row[1] for row in conn.execute("PRAGMA table_info(attempt)")]
            if 'source' not in cols:
                conn.execute("ALTER TABLE attempt ADD COLUMN source TEXT")
            cols = [row[1] for row in conn.execute("PRAGMA table_info(quiz)")]
            if 'two_category' not in cols:
                conn.execute("ALTER TABLE quiz ADD COLUMN two_category TEXT")
            conn.commit()

        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for tests
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['csrf_token'] = 'test-token'
            yield client
    finally:
        os.close(db_fd)
        os.unlink(db_path)
        os.environ.pop('PLA_DB', None)


@pytest.fixture
def logged_in_client(client):
    """Create client with logged in user."""
    with app.app_context():
        db = get_db()
        existing = db.execute("SELECT student_id FROM student WHERE student_id=1").fetchone()
        if not existing:
            db.execute(
                "INSERT INTO student (student_id, name, email, program, password_hash) VALUES (?,?,?,?,?)",
                (
                    1,
                    'Fixture Student',
                    'fixture@example.com',
                    'CS',
                    generate_password_hash('fixture-pass'),
                ),
            )
            attempt_id = db.execute(
                """
                INSERT INTO attempt (student_id, nf_scope, started_at, finished_at, items_total, items_correct, score_pct, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    'All',
                    '2024-01-01T10:00:00',
                    '2024-01-01T10:10:00',
                    4,
                    3,
                    75.0,
                    'live',
                ),
            ).lastrowid

            quiz_rows = db.execute("SELECT quiz_id FROM quiz ORDER BY quiz_id LIMIT 4").fetchall()
            categories = [
                ('Data Modeling & DBMS Fundamentals', 1),
                ('Normalization & Dependencies', 1),
                ('Data Modeling & DBMS Fundamentals', 0),
                ('Normalization & Dependencies', 0),
            ]
            for (quiz_id,), (category, score) in zip(quiz_rows, categories):
                db.execute(
                    "UPDATE quiz SET two_category=? WHERE quiz_id=?",
                    (category, quiz_id),
                )
                db.execute(
                    """
                    INSERT INTO response (attempt_id, student_id, quiz_id, answer, score, response_time_s)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (attempt_id, 1, quiz_id, 'Sample', score, 12.0),
                )

            for tag, mastered in [
                ('Functional Dependency', 1),
                ('Atomic Values', 0),
                ('Partial Dependency', 0),
                ('Transitive Dependency', 0),
            ]:
                db.execute(
                    """
                    INSERT OR REPLACE INTO student_mastery (student_id, concept_tag, mastered, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (1, tag, mastered, '2024-01-02T10:00:00'),
                )

            db.commit()

    with client.session_transaction() as sess:
        # Mock a logged in session
        sess['student_id'] = 1
        sess['csrf_token'] = 'test-token'

    return client


@pytest.fixture
def app_context():
    """Create application context for testing."""
    with app.app_context():
        yield app
