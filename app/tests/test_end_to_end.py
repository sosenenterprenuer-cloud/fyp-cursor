import os
import sqlite3
import json
import tempfile
import importlib.util
import pathlib
import pytest

APP_DIR = pathlib.Path(__file__).resolve().parents[1]
APP_PATH = APP_DIR / 'app.py'
SCHEMA = APP_DIR / 'schema.sql'
SEED = APP_DIR / 'seed.sql'


def load_app_with_db(tmp_path):
    db_path = tmp_path / 'test.db'
    os.environ['PLA_DB'] = str(db_path)
    os.environ['FLASK_SECRET'] = 'test-secret'

    # Initialize DB
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA.read_text())
    con.executescript(SEED.read_text())
    con.close()

    spec = importlib.util.spec_from_file_location('app_module', APP_PATH)
    app_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_module)  # type: ignore
    return app_module


def test_full_flow(tmp_path):
    app_module = load_app_with_db(tmp_path)
    app = app_module.app
    client = app.test_client()

    # Register
    with client as c:
      # Get CSRF from session by loading page
      c.get('/register')
      with c.session_transaction() as sess:
          csrf = sess['csrf_token']

      resp = c.post('/register', data={
          'csrf_token': csrf,
          'name': 'Test User',
          'email': 'test@example.com',
          'program': 'CS',
          'password': 'pass1234'
      }, follow_redirects=True)
      assert resp.status_code == 200

      # Login (should already be logged in after register, but test login path)
      c.get('/logout')
      c.get('/login')
      with c.session_transaction() as sess:
          csrf = sess['csrf_token']
      resp = c.post('/login', data={'csrf_token': csrf, 'email': 'test@example.com', 'password': 'pass1234'}, follow_redirects=True)
      assert resp.status_code == 200

      # Get quiz
      resp = c.get('/api/quiz_progressive')
      assert resp.status_code == 200
      data = resp.get_json()
      assert 'attempt_id' in data and 'questions' in data
      assert len(data['questions']) == 10
      # verify 3/3/2/2 by nf_level
      counts = {}
      for q in data['questions']:
          counts[q['nf_level']] = counts.get(q['nf_level'], 0) + 1
      assert counts.get('FD') == 3
      assert counts.get('1NF') == 3
      assert counts.get('2NF') == 2
      assert counts.get('3NF') == 2

      # Submit answers (choose first option, 5s each)
      attempt_id = data['attempt_id']
      answers = []
      for q in data['questions']:
          answer = q['options'][0] if q['options'] else ''
          answers.append({'quiz_id': q['quiz_id'], 'answer': answer, 'time_sec': 5.0})
      resp = c.post('/submit', data=json.dumps({'attempt_id': attempt_id, 'answers': answers}), content_type='application/json')
      assert resp.status_code == 200
      submission = resp.get_json()
      assert submission['attempt_id'] == attempt_id
      assert submission['total'] == 10
      assert 'details' in submission and len(submission['details']) == 10

      # Student dashboard
      with c.session_transaction() as sess:
          sid = sess['student_id']
      resp = c.get(f'/student/{sid}')
      assert resp.status_code == 200
