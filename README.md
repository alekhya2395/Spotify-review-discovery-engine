# Spotify Review Discovery Engine

An AI-powered system that analyzes large-scale user feedback about Spotify to
surface music-discovery pain points, recommendation issues, and unmet user
needs.

See:
- [`docs/problemstatement.md`](docs/problemstatement.md) — the *what & why*
- [`docs/architecture.md`](docs/architecture.md) — the six-phase architecture
- [`docs/edgecases.md`](docs/edgecases.md) — failure modes & mitigations

---

## Phase 1 — Data Collection (implemented)

Phase 1 is the **ingestion layer**. It pulls raw user feedback from multiple
public sources, normalizes it into a unified schema, and writes the result to
a local raw data lake (Parquet + JSONL).

### Sources supported

| Source | Connector | Requirements |
|---|---|---|
| Google Play Store | `PlayStoreConnector` | none (public scraper) |
| Apple App Store | `AppStoreConnector` | none (public scraper) |
| Reddit | `RedditConnector` | Reddit app credentials |
| Spotify Community Forum | `CommunityForumConnector` | none (polite HTML scrape) |

### Setup

```bash
python -m venv .venv
.\.venv\Scripts\activate           # Windows
# source .venv/bin/activate          # macOS / Linux

pip install -r requirements.txt

copy .env.example .env               # Windows
# cp .env.example .env                 # macOS / Linux
```

Fill in `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` in `.env` if you want
Reddit data. All other sources work out of the box.

### Run

```bash
python run_phase1.py --list                       # show available sources
python run_phase1.py                              # run all sources
python run_phase1.py --source play_store          # one source
python run_phase1.py -s play_store -s app_store   # multiple
python run_phase1.py --json                       # machine-readable summary
```

### Output layout

```
data/raw/
  play_store/
    run_date=2026-06-22/
      play_store_20260622T...<id>.parquet
      play_store_20260622T...<id>.jsonl
    manifest.jsonl
  app_store/...
  reddit/...
  community_forum/...
logs/
  phase1_collection.log
```

Every record conforms to the unified `RawReview` schema:

```python
{
    "review_id":      "play_store:abcd1234",
    "source":         "play_store",
    "source_region":  "us",
    "text":           "Discover Weekly keeps recommending the same artists...",
    "title":          null,
    "rating":         2.0,
    "lang":           "en",
    "author":         "user_handle",
    "created_at":     "2026-06-20T11:24:00+00:00",
    "url":            null,
    "source_meta":    { "thumbs_up": 12, ... },
    "collected_at":   "2026-06-22T13:01:42+00:00"
}
```

### Reliability features

- **Retry with exponential backoff** on transient network errors (`tenacity`)
- **Per-source isolation** — one source failing never aborts the run
- **Idempotent writes** — every run gets its own `run_id`; in-batch dedup by `review_id`
- **Run manifest** — each source appends a JSON line summarizing every run
- **Safety cap** — `MAX_REVIEWS_PER_SOURCE` prevents runaway scrapes
- **Rotating logs** — file + stderr, 10 MB rotation, 14 day retention

### Scheduling

Locally:

```bash
# Windows Task Scheduler or cron-equivalent: run daily
python run_phase1.py --json >> data/runs.jsonl
```

For production, wrap `CollectionPipeline.run()` in an Airflow DAG (one task
per `SourceType`) — see `architecture.md` § Phase 1.

---

## Project layout

```
SPOTIFY PROJECT/
├── docs/                          # problem statement, architecture, edge cases
├── src/
│   └── phase1_collection/
│       ├── config.py              # env-driven settings
│       ├── schemas.py             # RawReview + SourceType
│       ├── storage.py             # raw data lake (Parquet + JSONL)
│       ├── utils.py               # logging + retry
│       ├── pipeline.py            # orchestrator
│       └── connectors/
│           ├── base.py
│           ├── play_store.py
│           ├── app_store.py
│           ├── reddit.py
│           └── community_forum.py
├── run_phase1.py                  # CLI entry point
├── requirements.txt
├── .env.example
└── README.md
```

Next up: Phase 2 (preprocessing & cleaning).
