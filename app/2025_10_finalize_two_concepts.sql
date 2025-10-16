-- quiz: add two_category if missing
ALTER TABLE quiz ADD COLUMN two_category TEXT;

-- attempts: mark live vs historical (if missing)
ALTER TABLE attempt ADD COLUMN source TEXT DEFAULT 'live';

-- mini-module badge storage (exists? then keep)
CREATE TABLE IF NOT EXISTS module_progress (
  progress_id   INTEGER PRIMARY KEY,
  student_id    INTEGER NOT NULL,
  module_key    TEXT    NOT NULL,  -- 'fundamentals' | 'norm'
  score         INTEGER NOT NULL,  -- 0..3
  completed_at  TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(student_id, module_key),
  FOREIGN KEY(student_id) REFERENCES student(student_id) ON DELETE CASCADE
);

-- feedback for /thanks page (exists? then keep)
CREATE TABLE IF NOT EXISTS feedback (
  feedback_id   INTEGER PRIMARY KEY,
  student_id    INTEGER,
  rating        INTEGER NOT NULL,   -- 1..5
  comment       TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(student_id) REFERENCES student(student_id) ON DELETE SET NULL
);



