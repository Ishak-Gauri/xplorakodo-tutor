"""Supervisor: decides what happens next and wires the agents together.

Everything here is plain Python so you can read the whole flow top to bottom.
graph_langgraph.py runs the same three steps as a LangGraph graph.
"""
from .content import loc
from .agents import ProgressAgent, TutorAgent
from .db import Database
from .errors import BadRequest, NotFound
from .guard import CostGuard, estimate_tokens


def choose_topic(heatmap: dict, answer_counts: dict[str, int], topic_order: list[str]) -> str:
    """Weakest topic if the student has any weak spot, otherwise the least practised topic."""
    if heatmap["weakest"]:
        return heatmap["weakest"][0]["topic"]
    return min(topic_order, key=lambda t: (answer_counts.get(t, 0), topic_order.index(t)))


def _level_for(score: int, levels: list[dict]) -> str:
    chosen = levels[0]["level"]
    for lv in levels:
        if score >= lv["min"]:
            chosen = lv["level"]
    return chosen


class TutorService:
    def __init__(self, db: Database, content, llm, guard: CostGuard):
        self.db, self.content, self.guard = db, content, guard
        self.tutor = TutorAgent(content, llm)
        self.progress = ProgressAgent(db, content)

    # students and placement
    def create_student(self, name: str, track: str, lang: str) -> dict:
        if not name.strip():
            raise BadRequest("Name is required.")
        return self.db.create_student(name.strip(), track, lang)

    def placement_questions(self, student_id: int | None, lang: str = "en") -> list[dict]:
        items = self.content.placement_items(student_id or 0)
        return [{"q": loc(i["q"], lang), "options": [loc(o, lang) for o in i["options"]]} for i in items]

    def submit_placement(self, student_id: int, answers: list[int]) -> dict:
        if not self.db.get_student(student_id):
            raise NotFound("Student not found.")
        items = self.content.placement_items(student_id)
        if len(answers) != len(items):
            raise BadRequest(f"Expected {len(items)} answers.")
        score = sum(1 for a, item in zip(answers, items) if a == item["answer"])
        level = _level_for(score, self.content.placement["levels"])
        self.db.set_level(student_id, level)
        return {"score": score, "total": len(items), "level": level}

    def get_student(self, student_id: int) -> dict:
        return self._student_or_404(student_id)

    def set_lang(self, student_id: int, lang: str) -> dict:
        self._student_or_404(student_id)
        self.db.set_lang(student_id, lang)
        return self.db.get_student(student_id)

    # sessions
    def _student_or_404(self, student_id: int) -> dict:
        student = self.db.get_student(student_id)
        if not student:
            raise NotFound("Student not found.")
        return student

    def _question_payload(self, q: dict, lang: str, index: int = 1, total: int = 1) -> dict:
        return {"id": q["id"], "skill": q["skill"], "prompt": loc(q["prompt"], lang),
                "prompt_en": q["prompt"]["en"], "index": index, "total": total}

    def start_session(self, student_id: int) -> dict:
        student = self._student_or_404(student_id)
        self.guard.check(student_id)
        heat = self.progress.heatmap(student_id)
        counts: dict[str, int] = {}
        for r in self.db.score_aggregates(student_id):
            counts[r["topic"]] = counts.get(r["topic"], 0) + r["n"]
        topic_id = choose_topic(heat, counts, [t["id"] for t in self.content.topics])
        session = self.db.create_session(student_id, topic_id)
        topic = self.content.topic(topic_id)
        pool = self.content.session_pool(topic_id, session["id"])
        q = self.tutor.next_question(topic_id, [], self.progress.averages(student_id), pool)
        self.db.add_message(session["id"], "tutor_question", q["prompt"]["en"], q["id"])
        return {"session_id": session["id"], "total": len(pool),
                "topic": {"id": topic_id, "title": topic["title"], "vocab": topic["vocab"]},
                "reason": "weak_spot" if heat["weakest"] else "least_practised",
                "question": self._question_payload(q, student["lang"], 1, len(pool))}

    # one answer = three steps: begin_turn -> grade -> record
    def begin_turn(self, session_id: int) -> dict:
        session = self.db.get_session(session_id)
        if not session:
            raise NotFound("Session not found.")
        if session["status"] != "active":
            raise BadRequest("This session is finished. Start a new one.")
        student = self._student_or_404(session["student_id"])
        self.guard.check(student["id"])
        question = self.content.question(self.db.current_question_id(session_id))
        return {"session": session, "student": student, "question": question}

    def grade(self, ctx: dict, text: str) -> dict:
        if not text.strip():
            raise BadRequest("Answer is empty.")
        result = self.tutor.grade(ctx["question"], text, ctx["student"]["lang"])
        self.guard.spend(ctx["student"]["id"],
                         estimate_tokens(ctx["question"]["prompt"]["en"], text, result["feedback"]))
        return result

    def record(self, ctx: dict, text: str, evaluation: dict) -> dict:
        session, student, q = ctx["session"], ctx["student"], ctx["question"]
        self.db.add_message(session["id"], "student", text, q["id"])
        self.db.add_message(session["id"], "tutor_feedback", evaluation["feedback"], q["id"])
        self.progress.record(student["id"], session["id"], q["topic"], q["skill"], evaluation["score"])
        asked = self.db.asked_question_ids(session["id"])
        pool = self.content.session_pool(q["topic"], session["id"])
        nxt = self.tutor.next_question(q["topic"], asked, self.progress.averages(student["id"]), pool)
        if nxt:
            self.db.add_message(session["id"], "tutor_question", nxt["prompt"]["en"], nxt["id"])
        else:
            self.db.finish_session(session["id"])
        return {
            "score": round(evaluation["score"], 2),
            "skill": q["skill"],
            "topic": q["topic"],
            "feedback": evaluation["feedback"],
            "probe": loc(q["probe"], student["lang"]),
            "answered": len(asked),
            "next_question": self._question_payload(nxt, student["lang"], len(asked) + 1, len(pool)) if nxt else None,
            "session_done": nxt is None,
            "heatmap": self.progress.heatmap(student["id"]),
        }

    def answer(self, session_id: int, text: str) -> dict:
        ctx = self.begin_turn(session_id)
        evaluation = self.grade(ctx, text)
        return self.record(ctx, text, evaluation)

    def heatmap(self, student_id: int) -> dict:
        self._student_or_404(student_id)
        return self.progress.heatmap(student_id)

    def session_state(self, session_id: int) -> dict:
        """Everything the UI needs to redraw a session (after a refresh or a language switch)."""
        session = self.db.get_session(session_id)
        if not session:
            raise NotFound("Session not found.")
        student = self._student_or_404(session["student_id"])
        lang, topic = student["lang"], self.content.topic(session["topic"])
        pool = self.content.session_pool(session["topic"], session_id)
        scores = self.db.session_scores(session_id)
        history, answer, i = [], None, 0
        for m in self.db.messages(session_id):
            if m["role"] == "student":
                answer = m["content"]
            elif m["role"] == "tutor_feedback":
                q = self.content.question(m["question_id"])
                history.append({"question": loc(q["prompt"], lang), "answer": answer, "feedback": m["content"],
                                "score": round(scores[i], 2) if i < len(scores) else None, "skill": q["skill"]})
                i += 1
        current = None
        if session["status"] == "active":
            qid = self.db.current_question_id(session_id)
            current = self._question_payload(self.content.question(qid), lang, len(history) + 1, len(pool))
        return {"session_id": session_id, "status": session["status"], "total": len(pool),
                "topic": {"id": topic["id"], "title": topic["title"], "vocab": topic["vocab"]},
                "question": current, "history": history}
