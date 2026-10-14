# XploraKōdo Tutor (Project 1, end to end)

A Socratic tutor for Nepali students preparing for Japanese caregiving work.

**What it does**
1. Student takes a 10-question placement test and gets a level.
2. The **Supervisor** picks a topic: the student's weakest one, or the least practised.
3. The **Tutor agent** asks a question (English or Nepali), grades the answer (any of English, Nepali, Japanese), gives feedback and a Socratic follow-up.
4. The **Progress agent** saves a score per topic and skill, and the **heatmap** updates.
5. The **Cost-guard** stops the tutor when a student's daily token budget is used, or when an admin hits the kill switch.
6. An **eval suite** checks the grader, so you can change prompts or models without breaking it.

## Run it in VS Code (about 3 minutes)

```bash
cd xplorakodo-tutor
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
uvicorn app.main:app --reload
```
Open http://localhost:8000. In VS Code you can also press **F5** and choose "Run API (uvicorn, reload)".

```bash
pytest                      # unit tests (+ an HTTP test)
python -m evals.run_evals   # grader evals
```

It runs offline by default (`LLM_PROVIDER=mock`, a keyword grader). That is a toy: it only checks that the right ideas appear. To use a real LLM:
```bash
pip install anthropic            # or: pip install openai
# in .env:  LLM_PROVIDER=anthropic   and   ANTHROPIC_API_KEY=...
python -m evals.run_evals        # re-run the evals against the real model
```

## Read the code in this order

| File | What to learn from it |
|---|---|
| `data/lessons.json` | Content as data: topics, vocab, questions, grading keywords |
| `app/supervisor.py` | The whole flow in plain Python: `choose_topic`, then begin → grade → record |
| `app/agents.py` | Tutor agent (grades) and Progress agent (heatmap, no LLM needed) |
| `app/llm.py` | One `.evaluate()` interface for mock / OpenAI / Anthropic, JSON parsing and fallback |
| `app/guard.py` | Per-student token budget and kill switch |
| `app/graph_langgraph.py` | The same flow as a LangGraph graph (nodes, edges, conditional stop) |
| `app/main.py` | FastAPI endpoints |
| `evals/` | Golden cases plus a runner with a pass threshold |

## Next steps (your learning path)

1. **Real LLM grading.** Switch the provider, run the evals, and fix failures by improving the prompt in `llm.py`. Add 20 more golden cases in Nepali and Japanese.
2. **PostgreSQL + pgvector.** `docker compose up -d`, swap `db.py` to psycopg or SQLAlchemy using `db/schema.postgres.sql`, and store an embedding per weak answer in the `memory` table so the tutor can recall old struggles.
3. **Tracing.** Add Langfuse around `grade()` to see every call, token count and cost.
4. **Interview Proctor.** Add a second agent with a visa-mode prompt and a rubric, then a `certificates` table with a signed QR payload.
5. **Voice.** Browser mic → Whisper → this same `/answer` endpoint → TTS.
6. **Course Factory.** An agent drafts new topics into `lessons.json` format; a human approves before publishing.

## Known limits

- The mock grader uses substring keywords, so it can be fooled (for example by an answer that lists every keyword). A real LLM plus evals is the fix.
- Nepali strings were written by an AI and need review by a native speaker before real students use them.
- Lesson content is a small sample (4 topics, 12 questions), not a Japanese-curriculum-accurate course.
- Student data is stored unencrypted in SQLite and the API has no login. Add auth and encryption before any real use.
- The token budget is in memory and resets when the server restarts.
