"""The two specialist agents.

TutorAgent     picks questions and grades answers (uses the LLM).
ProgressAgent  turns every graded answer into skill data and builds the heatmap (pure SQL, no LLM).
"""
WEAK_BELOW = 0.6


class TutorAgent:
    def __init__(self, content, llm):
        self.content = content
        self.llm = llm

    def next_question(self, topic_id: str, asked: list[str], student_avg: dict, pool: list[str] | None = None):
        """Next unasked question (from the session pool), aiming at the student's weakest skill first."""
        remaining = [q for q in self.content.topic(topic_id)["questions"]
                     if q["id"] not in asked and (pool is None or q["id"] in pool)]
        remaining.sort(key=lambda q: student_avg.get((topic_id, q["skill"]), 0.5))
        return remaining[0] if remaining else None

    def grade(self, question: dict, answer: str, lang: str) -> dict:
        result = self.llm.evaluate(question, answer, lang)
        result["score"] = max(0.0, min(1.0, float(result["score"])))
        return result


class ProgressAgent:
    def __init__(self, db, content):
        self.db = db
        self.content = content

    def record(self, student_id: int, session_id: int, topic: str, skill: str, score: float) -> None:
        self.db.add_score(student_id, session_id, topic, skill, score)

    def averages(self, student_id: int) -> dict[tuple[str, str], float]:
        return {(r["topic"], r["skill"]): r["avg"] for r in self.db.score_aggregates(student_id)}

    def heatmap(self, student_id: int) -> dict:
        agg = {(r["topic"], r["skill"]): r for r in self.db.score_aggregates(student_id)}
        topics = [{"id": t["id"], "title": t["title"]} for t in self.content.topics]
        cells, weakest = {}, []
        for t in self.content.topics:
            cells[t["id"]] = {}
            for skill in self.content.skills:
                row = agg.get((t["id"], skill))
                if row is None:
                    cells[t["id"]][skill] = None
                    continue
                cells[t["id"]][skill] = {"avg": round(row["avg"], 2), "n": row["n"]}
                if row["avg"] < WEAK_BELOW:
                    weakest.append({"topic": t["id"], "skill": skill, "avg": round(row["avg"], 2)})
        weakest.sort(key=lambda w: w["avg"])
        return {"skills": self.content.skills, "topics": topics, "cells": cells, "weakest": weakest}
