"""Loads lessons and the placement test from data/*.json, and picks per-student question sets."""
import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSION_QUESTIONS = 4  # questions asked per practice session (out of the topic's bank)


def loc(value, lang: str) -> str:
    """Pick the text for a language from {"en":..,"ne":..,"ja":..}; fall back to English."""
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or next(iter(value.values()))
    return value


def _norm(q: dict) -> dict:
    for key in ("model_answer", "probe"):
        if isinstance(q.get(key), str):
            q[key] = {"en": q[key]}
    return q


class Content:
    def __init__(self, data_dir: Path = DATA_DIR):
        lessons = json.loads((data_dir / "lessons.json").read_text(encoding="utf-8"))
        self.skills: list[str] = lessons["skills"]
        self.topics: list[dict] = lessons["topics"]
        self.questions: dict[str, dict] = {
            q["id"]: _norm({**q, "topic": t["id"]}) for t in self.topics for q in t["questions"]
        }
        self.placement: dict = json.loads((data_dir / "placement.json").read_text(encoding="utf-8"))

    def topic(self, topic_id: str) -> dict:
        for t in self.topics:
            if t["id"] == topic_id:
                return t
        raise KeyError(topic_id)

    def question(self, question_id: str) -> dict:
        return self.questions[question_id]

    def placement_items(self, student_id: int) -> list[dict]:
        """A different 10-question test for each student (stable for the same student)."""
        items = self.placement["items"]
        n = min(self.placement.get("per_test", 10), len(items))
        return [items[i] for i in sorted(random.Random(student_id * 7919).sample(range(len(items)), n))]

    def session_pool(self, topic_id: str, session_id: int) -> list[str]:
        """Which questions a given session may ask: a random subset of the topic, fixed per session."""
        ids = [q["id"] for q in self.topic(topic_id)["questions"]]
        return random.Random(session_id * 104729).sample(ids, min(SESSION_QUESTIONS, len(ids)))
