"""Regression guard: chat answers must be identical and question-relevant.

Run before deploy:
    python test_chat_deterministic.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from format_labels import detect_question_intent  # noqa: E402
from rag import build_review_context  # noqa: E402
from routers.chat import CHAT_STABLE_MODE, _build_data_grounded_answer  # noqa: E402

CASES = (
    "Which user segments experience different discovery challenges?",
    "Why do users complain about repetitive recommendations?",
    "What unmet needs exist in music discovery?",
)


def main() -> None:
    assert CHAT_STABLE_MODE is True, "CHAT_STABLE_MODE must stay True (no Groq chat rewriting)"

    for question in CASES:
        payload, _, _ = build_review_context(question)
        a1 = _build_data_grounded_answer(question, payload)
        a2 = _build_data_grounded_answer(question, payload)
        assert a1 == a2, f"non-deterministic answer for: {question!r}"
        assert "## Summary" in a1, f"missing Summary for: {question!r}"

        intent = detect_question_intent(question)
        if intent == "segment_question":
            assert "Affected User Segments" in a1, question
            assert "alan watts" not in a1.lower(), question

    print("OK — chat answers are deterministic and segment questions include segments.")


if __name__ == "__main__":
    main()
