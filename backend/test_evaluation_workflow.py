"""Evaluation success test — run 20x per question; answers must be identical."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from query_classifier import classify_query  # noqa: E402
from workflow_engine import generate_workflow_answer  # noqa: E402

SUCCESS_QUESTIONS = (
    "Why do users struggle to discover new music?",
    "What causes repetitive listening behavior?",
    "Which user segments experience discovery challenges?",
    "What unmet needs emerge consistently across reviews?",
    "What are the root causes behind discovery problems?",
    "Why do users rely heavily on playlists?",
    "What opportunities exist for AI-powered discovery?",
    "What product improvements should Spotify prioritize?",
)

REQUIRED_SECTIONS = (
    "Summary",
    "Evidence",
    "Key Pain Points",
    "Root Causes",
    "Affected User Segments",
    "Unmet Needs",
    "Product Focus Areas",
    "Recommended Actions",
)


def main() -> None:
    print("=" * 72)
    print("EVALUATION SUCCESS TEST (20 runs per question)")
    print("=" * 72)

    all_ok = True
    for question in SUCCESS_QUESTIONS:
        cat, score, label = classify_query(question)
        runs = [generate_workflow_answer(question)["answer"] for _ in range(20)]
        unique = {hashlib.sha256(r.encode()).hexdigest() for r in runs}
        ok = len(unique) == 1
        all_ok = all_ok and ok
        sample = runs[0]
        missing = [s for s in REQUIRED_SECTIONS if f"## {s}" not in sample]
        has_indicator = "Validated Review Analysis" in sample
        status = "PASS" if ok and not missing and has_indicator and cat else "FAIL"
        print(f"\n[{status}] {question}")
        print(f"  category={cat} ({label}) score={score:.1f} unique_hashes={len(unique)}")
        if missing:
            print(f"  missing sections: {missing}")
        if not ok:
            all_ok = False

    print("\n" + "=" * 72)
    print("SAMPLE OUTPUT (first success question)")
    print("=" * 72)
    sample_q = SUCCESS_QUESTIONS[0]
    print(generate_workflow_answer(sample_q)["answer"][:2500])
    print("\n... [truncated for display] ...\n")

    print("=" * 72)
    print("SAMPLE OUTPUT (segment question)")
    print("=" * 72)
    seg_q = SUCCESS_QUESTIONS[2]
    print(generate_workflow_answer(seg_q)["answer"][:2500])
    print("\n... [truncated for display] ...\n")

    if not all_ok:
        sys.exit(1)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
