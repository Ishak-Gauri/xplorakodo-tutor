"""Eval suite: checks that the grader gives sensible scores on a golden set.

    python -m evals.run_evals                    # uses LLM_PROVIDER from .env (default: mock)
    LLM_PROVIDER=anthropic python -m evals.run_evals

Exit code is 1 if the pass rate is below EVAL_THRESHOLD (default 0.9), so you can run it in CI.
Run it every time you change a prompt, a model or the lesson content.
"""
import json
import os
import sys
from pathlib import Path

from app.config import get_settings
from app.content import Content
from app.llm import make_llm


def main() -> int:
    settings = get_settings()
    llm, content = make_llm(settings), Content()
    cases = json.loads((Path(__file__).parent / "golden.json").read_text(encoding="utf-8"))
    threshold = float(os.getenv("EVAL_THRESHOLD", "0.9"))
    passed = 0
    print(f"Grader: {llm.name}   cases: {len(cases)}\n")
    for c in cases:
        score = llm.evaluate(content.question(c["question"]), c["answer"], "en")["score"]
        ok = c["min"] <= score <= c["max"]
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {c['id']:<18} score={score:.2f}  expected {c['min']}-{c['max']}")
    rate = passed / len(cases)
    print(f"\n{passed}/{len(cases)} passed ({rate:.0%}), threshold {threshold:.0%}")
    return 0 if rate >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
