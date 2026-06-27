"""Semantic alias routing — validated questions must map before out-of-scope."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from query_classifier import classify_query  # noqa: E402
from workflow_engine import generate_workflow_answer  # noqa: E402

ALIAS_CASES = (
    ("What are the top frustrations with recommendations?", "discovery_frustrations"),
    ("What are the top frustrations?", "discovery_frustrations"),
    ("Why are users unhappy with recommendations?", "discovery_frustrations"),
    ("What are the root causes of discovery problems?", "root_causes"),
    ("Why does discovery fail?", "root_causes"),
    ("Which users struggle most?", "user_segments"),
    ("Who faces discovery issues?", "user_segments"),
    ("Why are recommendations repetitive?", "repetitive_listening_behavior"),
    ("Why does Spotify repeat songs?", "repetitive_listening_behavior"),
    ("What unmet needs emerge?", "unmet_needs"),
    ("What do users want from discovery?", "unmet_needs"),
    ("Why do users struggle to discover new music?", "music_discovery_challenges"),
    ("Why can't users find new artists?", "music_discovery_challenges"),
)


def main() -> None:
    print("=" * 72)
    print("SEMANTIC ALIAS TEST")
    print("=" * 72)

    all_ok = True
    for question, expected in ALIAS_CASES:
        cat, conf, _label = classify_query(question)
        result = generate_workflow_answer(question)
        ok = (
            cat == expected
            and result["answer_mode"] == "deterministic"
            and conf >= 0.55
            and "Validated Review Analysis" in result["answer"]
        )
        all_ok = all_ok and ok
        status = "PASS" if ok else "FAIL"
        print(f"\n[{status}] {question}")
        print(f"  expected={expected} got={cat!r} confidence={conf:.4f}")

    if not all_ok:
        sys.exit(1)
    print("\nALL ALIAS TESTS PASSED")


if __name__ == "__main__":
    main()
