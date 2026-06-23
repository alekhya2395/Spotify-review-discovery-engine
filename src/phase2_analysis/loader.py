"""Load raw reviews from Phase 1's `data/raw/` JSONL files.

Scans every source directory under `RAW_DATA_DIR`, reads every `.jsonl` file
(both the per-run mirrors and the Reddit checkpoints), deduplicates by
`review_id`, and yields minimal dicts the analyzer needs.

We intentionally don't re-validate against `RawReview` here — the goal is to
be tolerant of any reasonable JSONL we find on disk, and to fail soft on
malformed lines.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterator, List, Set

from loguru import logger

from .config import settings


_REQUIRED_FIELDS = ("review_id", "text", "source")


def iter_jsonl_files(root: Path | None = None) -> Iterator[Path]:
    """Yield every `.jsonl` file under the raw data lake."""
    base = Path(root) if root else settings.raw_data_dir
    if not base.exists():
        logger.warning("[loader] raw data dir does not exist: {p}", p=base)
        return
    yield from sorted(base.rglob("*.jsonl"))


def _load_one(path: Path) -> Iterator[Dict]:
    try:
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.debug("[loader] {p}:{ln} JSON error: {e}", p=path.name, ln=line_no, e=exc)
                    continue
                if not all(rec.get(k) for k in _REQUIRED_FIELDS):
                    continue
                yield rec
    except OSError as exc:
        logger.warning("[loader] could not open {p}: {e}", p=path, e=exc)


def load_all_reviews(skip_ids: Set[str] | None = None) -> List[Dict]:
    """Load every unique review from `data/raw/`.

    Parameters
    ----------
    skip_ids:
        Set of `review_id`s to exclude (e.g. ones already analyzed).
    """
    skip = skip_ids or set()
    seen: Set[str] = set()
    out: List[Dict] = []
    file_count = 0
    raw_count = 0
    dup_count = 0
    skipped_count = 0

    for path in iter_jsonl_files():
        file_count += 1
        for rec in _load_one(path):
            raw_count += 1
            rid = rec["review_id"]
            if rid in skip:
                skipped_count += 1
                continue
            if rid in seen:
                dup_count += 1
                continue
            seen.add(rid)
            out.append(
                {
                    "review_id": rid,
                    "source": rec.get("source"),
                    "text": rec.get("text"),
                    "rating": rec.get("rating"),
                    "lang": rec.get("lang"),
                    "source_region": rec.get("source_region"),
                }
            )

    logger.info(
        "[loader] files={f}  raw_records={r}  unique={u}  dupes={d}  already_analyzed={s}",
        f=file_count,
        r=raw_count,
        u=len(out),
        d=dup_count,
        s=skipped_count,
    )
    return out
