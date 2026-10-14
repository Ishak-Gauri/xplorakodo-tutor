"""FastAPI app. Run: uvicorn app.main:app --reload   then open http://localhost:8000"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import get_settings
from .content import Content
from .db import Database
from .errors import BadRequest, BudgetExceeded, NotFound
from .guard import CostGuard
from .llm import make_llm
from .supervisor import TutorService

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    track: str = "caregiving"
    lang: str = Field(default="en", pattern="^(en|ne|ja)$")


class LangIn(BaseModel):
    lang: str = Field(pattern="^(en|ne|ja)$")


class PlacementIn(BaseModel):
    student_id: int
    answers: list[int]


class SessionIn(BaseModel):
    student_id: int


class AnswerIn(BaseModel):
    answer: str = Field(max_length=2000)


def create_app(db_path: str | None = None, llm=None) -> FastAPI:
    settings = get_settings()
    service = TutorService(
        Database(db_path or settings.db_path),
        Content(),
        llm or make_llm(settings),
        CostGuard(settings.daily_token_budget),
    )
    app = FastAPI(title="XploraKodo Tutor")

    @app.middleware("http")
    async def no_cache(request, call_next):
        # Always serve the latest UI: stops the browser showing an old index.html.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    @app.exception_handler(NotFound)
    async def _nf(_, e):
        return JSONResponse({"detail": str(e)}, status_code=404)

    @app.exception_handler(BadRequest)
    async def _br(_, e):
        return JSONResponse({"detail": str(e)}, status_code=400)

    @app.exception_handler(BudgetExceeded)
    async def _be(_, e):
        return JSONResponse({"detail": str(e)}, status_code=429)

    @app.get("/api/health")
    def health():
        return {"ok": True, "grader": service.tutor.llm.name}

    @app.post("/api/students")
    def create_student(body: StudentIn):
        return service.create_student(body.name, body.track, body.lang)

    @app.get("/api/students/{student_id}")
    def get_student(student_id: int):
        return service.get_student(student_id)

    @app.put("/api/students/{student_id}/lang")
    def set_lang(student_id: int, body: LangIn):
        return service.set_lang(student_id, body.lang)

    @app.get("/api/placement")
    def placement(student_id: int | None = None, lang: str = "en"):
        return {"questions": service.placement_questions(student_id, lang)}

    @app.post("/api/placement")
    def submit_placement(body: PlacementIn):
        return service.submit_placement(body.student_id, body.answers)

    @app.post("/api/sessions")
    def start_session(body: SessionIn):
        return service.start_session(body.student_id)

    @app.get("/api/sessions/{session_id}")
    def session_state(session_id: int):
        return service.session_state(session_id)

    @app.post("/api/sessions/{session_id}/answer")
    def answer(session_id: int, body: AnswerIn):
        return service.answer(session_id, body.answer)

    @app.get("/api/students/{student_id}/heatmap")
    def heatmap(student_id: int):
        return service.heatmap(student_id)

    @app.post("/api/admin/kill")
    def kill(on: bool = True):
        service.guard.killed = on
        return {"killed": on}

    # Static UI last, so it never shadows /api routes.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
    return app


app = create_app()
