-- Same tables as app/db.py, in PostgreSQL syntax, plus a pgvector table for step 2 (memory).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS students (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  track TEXT NOT NULL DEFAULT 'caregiving',
  lang TEXT NOT NULL DEFAULT 'en',
  level TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sessions (
  id SERIAL PRIMARY KEY,
  student_id INT NOT NULL REFERENCES students(id),
  topic TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS messages (
  id SERIAL PRIMARY KEY,
  session_id INT NOT NULL REFERENCES sessions(id),
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  question_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS skill_scores (
  id SERIAL PRIMARY KEY,
  student_id INT NOT NULL REFERENCES students(id),
  session_id INT NOT NULL REFERENCES sessions(id),
  topic TEXT NOT NULL,
  skill TEXT NOT NULL,
  score REAL NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scores_student ON skill_scores(student_id, topic, skill);

-- Step 2: lifetime memory. Store an embedding of each student answer so the tutor can recall
-- "where did this student struggle before?" by similarity search.
CREATE TABLE IF NOT EXISTS memory (
  id SERIAL PRIMARY KEY,
  student_id INT NOT NULL REFERENCES students(id),
  note TEXT NOT NULL,
  embedding vector(1536),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
