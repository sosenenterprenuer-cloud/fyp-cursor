diff --git a/app/schema.sql b/app/schema.sql
index e14d7130bf7f760b3781dd460df9790aa8a3f724..e704d92a55243255c680dc43b19ad7da1c0c5bbe 100644
--- a/app/schema.sql
+++ b/app/schema.sql
@@ -39,42 +39,49 @@ CREATE TABLE IF NOT EXISTS response (
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
 
+CREATE TABLE IF NOT EXISTS lecturer (
+  lecturer_id   INTEGER PRIMARY KEY,
+  name          TEXT NOT NULL,
+  email         TEXT UNIQUE NOT NULL,
+  password_hash TEXT NOT NULL
+);
+
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
