"""Raw data lake storage.

Layout under `RAW_DATA_DIR`:
    raw/
      <source>/
        run_date=YYYY-MM-DD/
          <source>_<run_id>.parquet     # main columnar dump
          <source>_<run_id>.jsonl       # human-readable mirror
        manifest.jsonl                  # append-only per-run summary

Writes are idempotent at the run level: each run gets a unique `run_id`
(timestamp + uuid). Within a run we deduplicate by `review_id` so the same
review is never written twice.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

import pandas as pd
from loguru import logger

from .config import settings
from .schemas import RawReview, SourceType


@dataclass
class WriteResult:
    """Summary of a single write operation for one source."""

    source: SourceType
    run_id: str
    records_in: int
    records_written: int
    duplicates_dropped: int
    parquet_path: Path
    jsonl_path: Path
    manifest_path: Path


class RawDataLake:
    """Filesystem-backed raw data lake. Swap with S3/MinIO in production."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else settings.raw_data_dir
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _new_run_id() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return f"{ts}_{uuid.uuid4().hex[:8]}"

    def _partition_dir(self, source: SourceType, when: datetime | None = None) -> Path:
        when = when or datetime.now(timezone.utc)
        partition = self.root / source.value / f"run_date={when.strftime('%Y-%m-%d')}"
        partition.mkdir(parents=True, exist_ok=True)
        return partition

    @staticmethod
    def _dedupe(reviews: Iterable[RawReview]) -> tuple[List[RawReview], int]:
        seen: set[str] = set()
        unique: List[RawReview] = []
        dupes = 0
        for r in reviews:
            if r.review_id in seen:
                dupes += 1
                continue
            seen.add(r.review_id)
            unique.append(r)
        return unique, dupes

    def write(self, source: SourceType, reviews: List[RawReview]) -> WriteResult:
        """Persist a batch of reviews for a single source."""
        run_id = self._new_run_id()
        partition = self._partition_dir(source)

        unique, dupes = self._dedupe(reviews)
        parquet_path = partition / f"{source.value}_{run_id}.parquet"
        jsonl_path = partition / f"{source.value}_{run_id}.jsonl"
        manifest_path = self.root / source.value / "manifest.jsonl"

        if not unique:
            logger.warning(
                "No records to write for {source} (input={n}, dupes={d}).",
                source=source.value,
                n=len(reviews),
                d=dupes,
            )
        else:
            records = [r.model_dump(mode="json") for r in unique]
            df = pd.DataFrame.from_records(records)
            df.to_parquet(parquet_path, index=False)

            with jsonl_path.open("w", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

            logger.info(
                "Wrote {n} {source} reviews ({d} duplicates dropped) -> {p}",
                n=len(unique),
                source=source.value,
                d=dupes,
                p=parquet_path,
            )

        manifest_entry = {
            "run_id": run_id,
            "source": source.value,
            "records_in": len(reviews),
            "records_written": len(unique),
            "duplicates_dropped": dupes,
            "parquet_path": str(parquet_path) if unique else None,
            "jsonl_path": str(jsonl_path) if unique else None,
            "written_at": datetime.now(timezone.utc).isoformat(),
        }
        with manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(manifest_entry, ensure_ascii=False) + "\n")

        return WriteResult(
            source=source,
            run_id=run_id,
            records_in=len(reviews),
            records_written=len(unique),
            duplicates_dropped=dupes,
            parquet_path=parquet_path,
            jsonl_path=jsonl_path,
            manifest_path=manifest_path,
        )
