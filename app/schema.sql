PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS student (
  student_id INTEGER PRIMARY KEY,
  name TEXT,
  email TEXT UNIQUE,
  program TEXT,
  password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quiz (
  quiz_id INTEGER PRIMARY KEY,
  question TEXT NOT NULL,
  options_text TEXT,
  correct_answer TEXT NOT NULL,
  nf_level TEXT NOT NULL,
  concept_tag TEXT NOT NULL,
  explanation TEXT
);

CREATE TABLE IF NOT EXISTS attempt (
  attempt_id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL,
  nf_scope TEXT,
  started_at TEXT,
  finished_at TEXT,
  items_total INTEGER,
  items_correct INTEGER,
  score_pct REAL,
  FOREIGN KEY(student_id) REFERENCES student(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS response (
  response_id INTEGER PRIMARY KEY,
  attempt_id INTEGER NOT NULL,
  student_id INTEGER NOT NULL,
  quiz_id INTEGER NOT NULL,
  answer TEXT,
  score INTEGER,
  response_time_s REAL,
  FOREIGN KEY(attempt_id) REFERENCES attempt(attempt_id) ON DELETE CASCADE,
  FOREIGN KEY(student_id) REFERENCES student(student_id) ON DELETE CASCADE,
  FOREIGN KEY(quiz_id) REFERENCES quiz(quiz_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_mastery (
  student_id INTEGER NOT NULL,
  concept_tag TEXT NOT NULL,
  mastered INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(student_id, concept_tag),
  FOREIGN KEY(student_id) REFERENCES student(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS module (
  module_id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  nf_level TEXT NOT NULL,
  concept_tag TEXT NOT NULL,
  resource_url TEXT
);

CREATE TABLE IF NOT EXISTS recommendation (
  recommendation_id INTEGER PRIMARY KEY,
  student_id INTEGER NOT NULL,
  concept_tag TEXT NOT NULL,
  suggested_action TEXT NOT NULL,
  module_id INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY(student_id) REFERENCES student(student_id) ON DELETE CASCADE,
  FOREIGN KEY(module_id) REFERENCES module(module_id)
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_attempt_student_started ON attempt(student_id, started_at);
CREATE INDEX IF NOT EXISTS idx_response_attempt ON response(attempt_id);
CREATE INDEX IF NOT EXISTS idx_response_student ON response(student_id);
CREATE INDEX IF NOT EXISTS idx_response_quiz ON response(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quiz_concept ON quiz(concept_tag);
