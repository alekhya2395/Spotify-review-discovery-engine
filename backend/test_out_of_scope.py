"""Out-of-scope gate — business and unrelated questions must always be rejected."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from query_classifier import MIN_CONFIDENCE, OUT_OF_SCOPE_MESSAGE, classify_query  # noqa: E402
from workflow_engine import generate_workflow_answer  # noqa: E402

OUT_OF_SCOPE_QUESTIONS = (
    "Who founded Spotify?",
    "What is Spotify revenue?",
    "Who is Spotify CEO?",
    "What is Apple's revenue?",
    "What is the weather?",
    "What is football?",
)


def main() -> None:
    print("=" * 72)
    print(f"OUT-OF-SCOPE GATE TEST (MIN_CONFIDENCE={MIN_CONFIDENCE})")
    print("=" * 72)

    all_ok = True
    for question in OUT_OF_SCOPE_QUESTIONS:
        cat, conf, _label = classify_query(question)
        result = generate_workflow_answer(question)
        ok = (
            cat is None
            and result["answer_mode"] == "out_of_scope"
            and result["answer"] == OUT_OF_SCOPE_MESSAGE
            and conf < MIN_CONFIDENCE
        )
        all_ok = all_ok and ok
        status = "PASS" if ok else "FAIL"
        print(f"\n[{status}] {question}")
        print(f"  category={cat!r} confidence={conf:.4f} mode={result['answer_mode']}")
        if not ok:
            print(f"  expected out_of_scope, got category={result.get('category')!r}")

    if not all_ok:
        sys.exit(1)
    print("\nALL OUT-OF-SCOPE TESTS PASSED")


if __name__ == "__main__":
    main()
