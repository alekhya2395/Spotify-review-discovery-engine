"""SQLite metadata catalog — index runs and model version audit trail."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from .config import settings


class MetadataCatalog:
    """Track Phase-5 index runs and upstream model versions."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else settings.catalog_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS index_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    warehouse_path TEXT NOT NULL,
                    chroma_path TEXT NOT NULL,
                    row_counts_json TEXT NOT NULL,
                    vector_count INTEGER NOT NULL DEFAULT 0,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS model_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES index_runs(run_id)
                );
                """
            )

    def record_run(
        self,
        started_at: str,
        finished_at: str,
        duration_seconds: float,
        row_counts: Dict[str, int],
        vector_count: int,
        models: Dict[str, str],
        notes: Optional[str] = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO index_runs (
                    started_at, finished_at, duration_seconds,
                    warehouse_path, chroma_path, row_counts_json, vector_count, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at,
                    finished_at,
                    duration_seconds,
                    str(settings.warehouse_path),
                    str(settings.chroma_path),
                    json.dumps(row_counts),
                    vector_count,
                    notes,
                ),
            )
            run_id = cur.lastrowid
            now = datetime.now(timezone.utc).isoformat()
            for phase, model_name in models.items():
                conn.execute(
                    """
                    INSERT INTO model_versions (run_id, phase, model_name, recorded_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (run_id, phase, model_name, now),
                )
            conn.commit()

        logger.info("[catalog] recorded index run {id} at {p}", id=run_id, p=self.path)
        return run_id

    def latest_run(self) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM index_runs ORDER BY run_id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["row_counts"] = json.loads(d.pop("row_counts_json"))
        return d
