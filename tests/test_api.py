"""HTTP-level test. Needs: pip install -r requirements.txt (fastapi + httpx)."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.llm import MockLLM  # noqa: E402
from app.main import create_app  # noqa: E402


def test_full_flow_over_http():
    client = TestClient(create_app(":memory:", MockLLM()))
    assert client.get("/api/health").json()["ok"] is True

    student = client.post("/api/students", json={"name": "Sita", "lang": "ne"}).json()
    questions = client.get("/api/placement", params={"student_id": student["id"], "lang": "ne"}).json()["questions"]
    assert len(questions) == 10 and "answer" not in questions[0]

    placed = client.post("/api/placement", json={"student_id": student["id"], "answers": [0] * 10}).json()
    assert placed["level"] in ("N5-Foundation", "N5", "N4-Ready")

    session = client.post("/api/sessions", json={"student_id": student["id"]}).json()
    res = client.post(f"/api/sessions/{session['session_id']}/answer", json={"answer": "banana"}).json()
    assert res["score"] == 0 and res["heatmap"]["weakest"]

    assert client.post("/api/sessions/999/answer", json={"answer": "x"}).status_code == 404
    assert client.post("/api/sessions/1/answer", json={"answer": "  "}).status_code == 400

    client.post("/api/admin/kill?on=true")
    assert client.post("/api/sessions", json={"student_id": student["id"]}).status_code == 429
