"""The same answer flow as TutorService.answer(), written as a LangGraph graph.

    pip install langgraph
    python -m app.graph_langgraph

Read this next to supervisor.py: each node is one step, state is a dict passed along edges,
and the conditional edge after "begin" is where a guard failure stops the run.
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .errors import BadRequest, BudgetExceeded, NotFound


class AnswerState(TypedDict, total=False):
    session_id: int
    text: str
    ctx: dict
    evaluation: dict
    result: dict
    error: str


def build_graph(service):
    def begin(state: AnswerState) -> dict:
        try:
            return {"ctx": service.begin_turn(state["session_id"])}
        except (NotFound, BadRequest, BudgetExceeded) as e:
            return {"error": str(e)}

    def grade(state: AnswerState) -> dict:
        try:
            return {"evaluation": service.grade(state["ctx"], state["text"])}
        except (BadRequest, BudgetExceeded) as e:
            return {"error": str(e)}

    def record(state: AnswerState) -> dict:
        return {"result": service.record(state["ctx"], state["text"], state["evaluation"])}

    def stop_on_error(state: AnswerState) -> str:
        return "stop" if state.get("error") else "continue"

    g = StateGraph(AnswerState)
    g.add_node("begin", begin)
    g.add_node("grade", grade)
    g.add_node("record", record)
    g.add_edge(START, "begin")
    g.add_conditional_edges("begin", stop_on_error, {"stop": END, "continue": "grade"})
    g.add_conditional_edges("grade", stop_on_error, {"stop": END, "continue": "record"})
    g.add_edge("record", END)
    return g.compile()


if __name__ == "__main__":
    from .config import get_settings
    from .content import Content
    from .db import Database
    from .guard import CostGuard
    from .llm import make_llm

    settings = get_settings()
    from .supervisor import TutorService

    svc = TutorService(Database(":memory:"), Content(), make_llm(settings), CostGuard(settings.daily_token_budget))
    student = svc.create_student("Demo", "caregiving", "en")
    session = svc.start_session(student["id"])
    print("Q:", session["question"]["prompt"])
    out = build_graph(svc).invoke({"session_id": session["session_id"], "text": "It means physical condition"})
    print(out.get("error") or out["result"]["feedback"])
