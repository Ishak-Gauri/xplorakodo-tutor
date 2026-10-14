"""Tiny SQLite data layer (standard library only).

SQLite keeps the first run zero-setup. db/schema.postgres.sql has the same tables for
PostgreSQL when you are ready to move (step 2 in the README).
"""
import sqlite3
import threading
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  track TEXT NOT NULL DEFAULT 'caregiving',
  lang TEXT NOT NULL DEFAULT 'en',
  level TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  topic TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  question_id TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skill_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  topic TEXT NOT NULL,
  skill TEXT NOT NULL,
  score REAL NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scores_student ON skill_scores(student_id, topic, skill);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def _run(self, sql: str, params: tuple = ()):
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def _one(self, sql: str, params: tuple = ()):
        with self.lock:
            row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _all(self, sql: str, params: tuple = ()):
        with self.lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # students
    def create_student(self, name: str, track: str, lang: str) -> dict:
        cur = self._run(
            "INSERT INTO students(name, track, lang, created_at) VALUES (?,?,?,?)",
            (name, track, lang, _now()),
        )
        return self.get_student(cur.lastrowid)

    def get_student(self, student_id: int):
        return self._one("SELECT * FROM students WHERE id=?", (student_id,))

    def set_level(self, student_id: int, level: str) -> None:
        self._run("UPDATE students SET level=? WHERE id=?", (level, student_id))

    def set_lang(self, student_id: int, lang: str) -> None:
        self._run("UPDATE students SET lang=? WHERE id=?", (lang, student_id))

    # sessions and messages
    def create_session(self, student_id: int, topic: str) -> dict:
        cur = self._run(
            "INSERT INTO sessions(student_id, topic, created_at) VALUES (?,?,?)",
            (student_id, topic, _now()),
        )
        return self.get_session(cur.lastrowid)

    def get_session(self, session_id: int):
        return self._one("SELECT * FROM sessions WHERE id=?", (session_id,))

    def finish_session(self, session_id: int) -> None:
        self._run("UPDATE sessions SET status='done' WHERE id=?", (session_id,))

    def add_message(self, session_id: int, role: str, content: str, question_id: str | None = None) -> None:
        self._run(
            "INSERT INTO messages(session_id, role, content, question_id, created_at) VALUES (?,?,?,?,?)",
            (session_id, role, content, question_id, _now()),
        )

    def messages(self, session_id: int) -> list[dict]:
        return self._all("SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,))

    def asked_question_ids(self, session_id: int) -> list[str]:
        rows = self._all(
            "SELECT question_id FROM messages WHERE session_id=? AND role='tutor_question' ORDER BY id",
            (session_id,),
        )
        return [r["question_id"] for r in rows]

    def current_question_id(self, session_id: int):
        row = self._one(
            "SELECT question_id FROM messages WHERE session_id=? AND role='tutor_question' ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        return row["question_id"] if row else None

    # scores
    def add_score(self, student_id: int, session_id: int, topic: str, skill: str, score: float) -> None:
        self._run(
            "INSERT INTO skill_scores(student_id, session_id, topic, skill, score, created_at) VALUES (?,?,?,?,?,?)",
            (student_id, session_id, topic, skill, score, _now()),
        )

    def score_aggregates(self, student_id: int) -> list[dict]:
        return self._all(
            "SELECT topic, skill, AVG(score) AS avg, COUNT(*) AS n "
            "FROM skill_scores WHERE student_id=? GROUP BY topic, skill",
            (student_id,),
        )

    def session_scores(self, session_id: int) -> list[float]:
        rows = self._all("SELECT score FROM skill_scores WHERE session_id=? ORDER BY id", (session_id,))
        return [r["score"] for r in rows]
