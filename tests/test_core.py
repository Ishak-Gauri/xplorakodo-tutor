"""Core tests: no web server and no API key needed. Run with: pytest"""
from app.content import Content
from app.db import Database
from app.errors import BadRequest, BudgetExceeded
from app.guard import CostGuard
from app.llm import MockLLM, keyword_score
from app.supervisor import TutorService, choose_topic


def make_service(budget=100000):
    return TutorService(Database(":memory:"), Content(), MockLLM(), CostGuard(budget))


def test_keyword_score_full_partial_empty():
    q = Content().question("bn3")
    assert keyword_score(q, "Blood pressure and temperature") == 1.0
    assert keyword_score(q, "pulse") == 0.5
    assert keyword_score(q, "") == 0.0


def test_placement_levels():
    svc = make_service()
    s = svc.create_student("Sita", "caregiving", "ne")
    items = svc.content.placement_items(s["id"])
    perfect = svc.submit_placement(s["id"], [i["answer"] for i in items])
    assert perfect["level"] == "N4-Ready" and perfect["score"] == 10
    wrong = svc.submit_placement(s["id"], [(i["answer"] + 1) % len(i["options"]) for i in items])
    assert wrong["level"] == "N5-Foundation" and wrong["score"] == 0


def test_placement_wrong_length_rejected():
    svc = make_service()
    s = svc.create_student("Ram", "caregiving", "en")
    try:
        svc.submit_placement(s["id"], [0, 1])
        assert False, "should have raised"
    except BadRequest:
        pass


def test_full_session_updates_heatmap_and_finishes():
    svc = make_service()
    s = svc.create_student("Sita", "caregiving", "en")
    started = svc.start_session(s["id"])
    sid = started["session_id"]
    done, turns = False, 0
    while not done:
        res = svc.answer(sid, "banana")  # always wrong
        done, turns = res["session_done"], turns + 1
        assert turns <= 4
    assert turns == 4
    heat = svc.heatmap(s["id"])
    topic = started["topic"]["id"]
    assert any(c and c["avg"] == 0 for c in heat["cells"][topic].values())
    assert heat["weakest"], "wrong answers must show up as weak spots"


def test_supervisor_targets_weak_topic():
    svc = make_service()
    s = svc.create_student("Sita", "caregiving", "en")
    first = svc.start_session(s["id"])
    for _ in range(4):
        svc.answer(first["session_id"], "banana")
    second = svc.start_session(s["id"])
    assert second["topic"]["id"] == first["topic"]["id"]
    assert second["reason"] == "weak_spot"


def test_choose_topic_without_weak_spots_picks_least_practised():
    heat = {"weakest": []}
    assert choose_topic(heat, {"a": 3, "b": 1}, ["a", "b", "c"]) == "c"


def test_budget_blocks_and_kill_switch():
    svc = make_service(budget=1)
    s = svc.create_student("Sita", "caregiving", "en")
    sid = svc.start_session(s["id"])["session_id"]
    svc.answer(sid, "something")  # first call is allowed, then the budget is spent
    try:
        svc.answer(sid, "again")
        assert False, "budget should block"
    except BudgetExceeded:
        pass
    svc2 = make_service()
    svc2.guard.killed = True
    s2 = svc2.create_student("Ram", "caregiving", "en")
    try:
        svc2.start_session(s2["id"])
        assert False, "kill switch should block"
    except BudgetExceeded:
        pass


def test_feedback_language():
    svc = make_service()
    s = svc.create_student("Sita", "caregiving", "ja")
    sid = svc.start_session(s["id"])["session_id"]
    res = svc.answer(sid, "banana")
    assert "ヒント" in res["feedback"]


def test_different_students_get_different_placement_tests():
    svc = make_service()
    a, b = svc.placement_questions(1), svc.placement_questions(2)
    assert len(a) == len(b) == 10 and a != b
    assert svc.placement_questions(1) == a  # stable for the same student


def test_sessions_use_different_question_subsets():
    c = Content()
    pools = {tuple(c.session_pool("basic_nursing", sid)) for sid in range(1, 12)}
    assert len(pools) > 1 and all(len(p) == 4 for p in pools)


def test_every_question_has_all_three_languages():
    c = Content()
    for q in c.questions.values():
        for field in ("prompt", "model_answer", "probe"):
            assert all(q[field].get(l) for l in ("en", "ne", "ja")), (q["id"], field)
    for t in c.topics:
        assert all(t["title"].get(l) for l in ("en", "ne", "ja"))


def test_session_state_and_language_switch():
    svc = make_service()
    s = svc.create_student("Sita", "caregiving", "en")
    sid = svc.start_session(s["id"])["session_id"]
    svc.answer(sid, "banana")
    svc.set_lang(s["id"], "ja")
    state = svc.session_state(sid)
    assert len(state["history"]) == 1 and state["question"]["index"] == 2 and state["total"] == 4
    assert any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in state["question"]["prompt"])
