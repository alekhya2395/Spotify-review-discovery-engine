# Implementation Guide

## AI-Powered Review Discovery Engine for Spotify

This document is the single source of truth for **how Phase 1 is built, configured, and operated**. It captures every input — env variables, sources, schemas, dependencies, commands, and outputs — so anyone can reproduce the pipeline end-to-end.

For *why* and *what*, see:
- [`problemstatement.md`](problemstatement.md) — business context
- [`architecture.md`](architecture.md) — 6-phase architectural blueprint
- [`edgecases.md`](edgecases.md) — failure modes & mitigations

---

## Table of Contents

1. [Implementation Status](#1-implementation-status)
2. [Project Layout](#2-project-layout)
3. [Dependencies](#3-dependencies)
4. [Environment Variables (Inputs)](#4-environment-variables-inputs)
5. [Data Sources & Connectors](#5-data-sources--connectors)
6. [Unified Output Schema](#6-unified-output-schema)
7. [Storage Layout](#7-storage-layout)
8. [How to Run](#8-how-to-run)
9. [Reliability Features](#9-reliability-features)
10. [Edge Cases Handled in Code](#10-edge-cases-handled-in-code)
11. [Current Corpus on Disk](#11-current-corpus-on-disk)
12. [Known Limitations](#12-known-limitations)
13. [Phase 3 — Topic Modeling & Clustering](#13-phase-3--topic-modeling--clustering)
14. [Phase 4 — Insight Generation (PM-ready cards)](#14-phase-4--insight-generation-pm-ready-cards)
15. [Phase 5 — Storage & Indexing](#15-phase-5--storage--indexing)
16. [Phase 6 — Visualization & Delivery](#16-phase-6--visualization--delivery)

---

## 1. Implementation Status

| Phase | Status | Notes |
|---|---|---|
| **Phase 1 — Data Collection** | ✅ Implemented | All 5 sources wired; ~2,540 records collected |
| **Phase 2 — AI Analysis (Groq)** | ✅ Implemented | Reads `data/raw/*.jsonl`, sends batches of reviews to Groq, extracts structured insights to `data/processed/insights.csv` (2,277 unique insights, 100% coverage) |
| **Phase 3 — Topic Modeling & Clustering** | ✅ Implemented | BERTopic on Phase-2 insights → `topics.csv` (59 clusters) |
| **Phase 4 — Insight Generation (PM-ready cards)** | ✅ Implemented | RAG-style Groq synthesis per cluster → `insight_cards.csv` + `.json` (53 cards) |
| **Phase 5 — Storage & Indexing** | ✅ Implemented | DuckDB warehouse + Chroma vector index + SQLite catalog → `data/index/` |
| **Phase 6 — Visualization & Delivery** | ✅ Implemented | Streamlit PM dashboard + export + RAG chat → `run_dashboard.py` |

### LLM choice

We use **[Groq](https://groq.com)** for every LLM call in Phases 2 and 4 (and optional labeling in Phase 3). Reasons:

- **Speed:** ~1 second per call vs. ~10 seconds on equivalent OpenAI tiers — critical when processing thousands of reviews
- **Cost:** generous free tier covers this project end-to-end at typical batch sizes
- **JSON mode:** `response_format={"type": "json_object"}` guarantees parseable output, eliminating a whole class of LLM failure modes
- **No vendor lock-in:** the SDK is OpenAI-compatible, so swapping back to OpenAI / Anthropic later is a one-line change

---

## 2. Project Layout

```
SPOTIFY PROJECT/
├── docs/                              ← architecture, problem, edge cases, this doc
│   ├── problemstatement.md
│   ├── architecture.md
│   ├── edgecases.md
│   └── implementation.md              ← you are here
│
├── src/
│   ├── phase1_collection/
│   │   ├── __init__.py                ← public exports: CollectionPipeline, RawReview, SourceType
│   │   ├── config.py                  ← env-driven Pydantic settings
│   │   ├── schemas.py                 ← RawReview + SourceType (the contract)
│   │   ├── storage.py                 ← RawDataLake (Parquet + JSONL + manifest)
│   │   ├── utils.py                   ← loguru setup + tenacity retry decorator
│   │   ├── pipeline.py                ← CollectionPipeline orchestrator
│   │   └── connectors/
│   │       ├── base.py                ← BaseConnector + ConnectorError
│   │       ├── play_store.py          ← google-play-scraper
│   │       ├── app_store.py           ← Apple iTunes RSS feed
│   │       ├── reddit.py              ← PRAW → public-JSON → RSS multi-surface fallback
│   │       ├── community_forum.py     ← polite HTML scraper (Cloudflare-aware UA)
│   │       └── social_media.py        ← Mastodon tag-timeline API (no auth)
│   │
│   ├── phase2_analysis/
│   │   ├── __init__.py                ← public exports: AnalysisPipeline, Insight
│   │   ├── config.py                  ← Groq settings (model, key, batch size)
│   │   ├── schemas.py                 ← Insight + enums (Sentiment, PainCategory, Segment)
│   │   ├── prompts.py                 ← System + user prompt templates
│   │   ├── loader.py                  ← Read all JSONL from data/raw/, dedup by review_id
│   │   ├── groq_client.py             ← Thin Groq SDK wrapper + JSON-mode + retry
│   │   ├── analyzer.py                ← Batch → Groq → parse → validate
│   │   ├── storage.py                 ← Append-safe CSV writer (data/processed/insights.csv)
│   │   └── pipeline.py                ← AnalysisPipeline orchestrator
│   │
│   └── phase3_clustering/
│       ├── __init__.py                ← public exports: ClusteringPipeline, Topic
│       ├── config.py                  ← embedding + BERTopic + I/O settings
│       ├── schemas.py                 ← Topic + TopicAssignment Pydantic models
│       ├── utils.py                   ← loguru + tenacity (mirrors Phase 1/2)
│       ├── loader.py                  ← Read insights.csv, dedup, build text-to-embed
│       ├── embedder.py                ← Sentence-Transformers wrapper + npy cache
│       ├── clusterer.py               ← BERTopic (UMAP + HDBSCAN + c-TF-IDF)
│       ├── labeler.py                 ← Groq-based topic naming (heuristic fallback)
│       ├── storage.py                 ← Writes topics.csv + insights_with_topics.csv
│       └── pipeline.py                ← ClusteringPipeline orchestrator
│   │
│   └── phase4_insights/
│       ├── __init__.py                ← public exports: GenerationPipeline, InsightCard
│       ├── config.py                  ← Phase-4 env settings + Groq reuse
│       ├── schemas.py                 ← InsightCard + TopicBundle models
│       ├── utils.py                   ← loguru setup
│       ├── loader.py                  ← Load topics.csv + insights_with_topics.csv + timestamps
│       ├── aggregator.py              ← Theme aggregation, segment compare, trend detect
│       ├── scorer.py                  ← Priority scoring (volume × severity × trend)
│       ├── prompts.py                 ← Groq RAG prompt templates
│       ├── generator.py               ← LLM card synthesis + rule-based fallback
│       ├── storage.py                 ← Writes insight_cards.csv + insight_cards.json
│       └── pipeline.py                ← GenerationPipeline orchestrator
│   │
│   └── phase5_storage/
│       ├── __init__.py                ← public exports: IndexingPipeline, QueryEngine
│       ├── config.py                  ← DuckDB / Chroma / catalog paths + search settings
│       ├── utils.py                   ← loguru setup
│       ├── loaders.py                 ← Load Phases 1–4 CSV/JSONL + embeddings.npy
│       ├── warehouse.py               ← DuckDBWarehouse (raw, insights, enriched, topics, cards)
│       ├── vector_index.py            ← Chroma persistent collection for review embeddings
│       ├── catalog.py                 ← SQLite MetadataCatalog (index runs + model versions)
│       ├── query.py                   ← QueryEngine: semantic search, filters, card lookups
│       └── pipeline.py                ← IndexingPipeline orchestrator
│   │
│   └── phase6_dashboard/
│       ├── __init__.py                ← public exports: DashboardData
│       ├── config.py                  ← Streamlit + chat + export settings
│       ├── data.py                    ← DashboardData analytics over QueryEngine
│       ├── charts.py                  ← Plotly chart builders (dark Spotify theme)
│       ├── export.py                  ← Markdown + JSON digest export
│       ├── chat.py                    ← RAG chatbot (semantic search + Groq)
│       └── app.py                     ← Streamlit multipage dashboard
│
├── data/raw/                          ← raw data lake (gitignored)
│   ├── app_store/run_date=<YYYY-MM-DD>/
│   ├── play_store/run_date=<YYYY-MM-DD>/
│   ├── reddit/run_date=<YYYY-MM-DD>/
│   ├── reddit/checkpoints/<YYYY-MM-DD>/   ← per-subreddit incremental saves
│   ├── community_forum/run_date=<YYYY-MM-DD>/
│   ├── social_media/run_date=<YYYY-MM-DD>/
│   └── <source>/manifest.jsonl            ← append-only audit log
│
├── data/processed/
│   ├── insights.csv                   ← Phase 2 output (append-safe, dedup by review_id)
│   ├── topics.csv                     ← Phase 3 output (one row per cluster)
│   ├── insights_with_topics.csv       ← Phase 3 output (insights joined with topic_id + label)
│   ├── embeddings.npy                 ← cached sentence-transformer vectors
│   ├── embedding_index.csv            ← row -> review_id map for embeddings.npy
│   ├── topic_model/                   ← serialized BERTopic model (safetensors)
│   ├── insight_cards.csv              ← Phase 4 output (PM-ready cards, ranked by priority)
│   └── insight_cards.json             ← same cards as JSON array (for dashboards/APIs)
│
├── data/index/                        ← Phase 5 output (gitignored)
│   ├── warehouse.duckdb               ← DuckDB analytical warehouse
│   ├── catalog.db                     ← SQLite index-run audit trail
│   └── chroma/                        ← Chroma persistent vector store
│
├── data/exports/                      ← Phase 6 digest exports (gitignored)
│
├── logs/phase1_collection.log         ← rotating log (10 MB × 14 days)
├── logs/phase2_analysis.log           ← rotating log
├── logs/phase3_clustering.log         ← rotating log
├── logs/phase4_insights.log           ← rotating log
├── logs/phase5_storage.log            ← rotating log
├── run_phase1.py                      ← CLI: collection
├── run_phase2.py                      ← CLI: AI analysis
├── run_phase3.py                      ← CLI: clustering
├── run_phase4.py                      ← CLI: insight card generation
├── run_phase5.py                      ← CLI: build DuckDB + Chroma + catalog
├── search_reviews.py                  ← CLI: semantic search + filters + cards
├── run_dashboard.py                   ← CLI: launch Streamlit PM dashboard
├── inspect_runs.py                    ← helper: show raw totals on disk
├── inspect_insights.py                ← helper: distributions in insights.csv
├── inspect_topics.py                  ← helper: pretty-print topics.csv
├── inspect_cards.py                   ← helper: pretty-print insight_cards.csv
├── check_coverage.py                  ← helper: Phase 2 coverage report
├── requirements.txt
├── .env.example
├── .env                               ← actual config (gitignored)
├── .gitignore
└── README.md
```

---

## 3. Dependencies

Pinned in `requirements.txt`:

| Package | Min version | Purpose |
|---|---|---|
| `pydantic` | 2.7.0 | Schema validation (`RawReview`) |
| `pydantic-settings` | 2.3.0 | Env-driven config loader |
| `python-dotenv` | 1.0.1 | `.env` file support |
| `loguru` | 0.7.2 | Structured logging w/ rotation |
| `tenacity` | 8.3.0 | Exponential-backoff retries |
| `pyyaml` | 6.0.1 | Reserved for future config files |
| `requests` | 2.32.0 | HTTP client for all scrapers |
| `beautifulsoup4` | 4.12.3 | HTML parsing (Community Forum, Mastodon) |
| `lxml` | 5.2.0 | Fast XML/HTML backend for bs4 |
| `google-play-scraper` | 1.2.7 | Google Play Store reviews |
| `praw` | 7.7.1 | Reddit (when credentials provided) |
| `pandas` | 2.2.2 | Parquet writer + dataframe ops |
| `pyarrow` | 16.1.0 | Parquet engine |
| `typer` | 0.12.3 | CLI framework |
| `rich` | 13.7.1 | CLI table/JSON rendering |
| `groq` | 0.11.0 | LLM client for Phase 2 + Phase 3 labeling |
| `sentence-transformers` | 3.0.0 | Phase 3 embeddings (MiniLM-L6-v2, CPU) |
| `bertopic` | 0.16.3 | Phase 3 topic modeling (bundles UMAP + HDBSCAN + c-TF-IDF) |
| `umap-learn` | 0.5.6 | Dimensionality reduction inside BERTopic |
| `hdbscan` | 0.8.33 | Density-based clustering inside BERTopic |
| `scikit-learn` | 1.4.0 | CountVectorizer for c-TF-IDF |
| `numpy` | 1.26.0 | Embedding array I/O |
| `duckdb` | 1.0.0 | Phase 5 analytical warehouse (local; swap for Postgres in prod) |
| `chromadb` | 0.5.0 | Phase 5 vector index for semantic search (local; swap for pgvector in prod) |
| `streamlit` | 1.33.0 | Phase 6 interactive PM dashboard |
| `plotly` | 5.18.0 | Phase 6 charts (priority bars, trends, segment heatmaps) |

> **Note:** `app-store-scraper` was originally listed but **dropped** because it pins `requests==2.23.0` (severe conflict). The App Store connector now uses Apple's public **iTunes RSS feed** directly via `requests` — zero third-party dependency.

Install:

```bash
python -m pip install -r requirements.txt
```

---

## 4. Environment Variables (Inputs)

All knobs are env-driven. Copy `.env.example` → `.env`, then edit. Loaded by `src/phase1_collection/config.py` via `pydantic-settings`.

### 4.1 Spotify identifiers

| Var | Default | What it is |
|---|---|---|
| `SPOTIFY_APP_STORE_ID` | `324684580` | Apple App Store numeric ID for Spotify |
| `SPOTIFY_PLAY_STORE_ID` | `com.spotify.music` | Android package name |

### 4.2 Reddit

| Var | Default | What it is |
|---|---|---|
| `REDDIT_CLIENT_ID` | *(empty)* | OAuth client id (free from https://www.reddit.com/prefs/apps) |
| `REDDIT_CLIENT_SECRET` | *(empty)* | OAuth secret |
| `REDDIT_USER_AGENT` | `spotify-review-engine/0.1 by u/yourname` | Required by Reddit when authenticated |
| `REDDIT_SUBREDDITS` | `spotify,truespotify` | Comma-separated subreddit list (no `r/` prefix) |

> Without credentials the connector falls back to public RSS (rate-limited by Reddit's WAF). With credentials, PRAW bypasses the WAF and unlocks unlimited submissions + comments.

### 4.3 Spotify Community Forum

| Var | Default | What it is |
|---|---|---|
| `COMMUNITY_BASE_URL` | `https://community.spotify.com` | Forum root URL |

### 4.4 Mastodon (Social Media)

| Var | Default | What it is |
|---|---|---|
| `MASTODON_INSTANCES` | `https://mastodon.social,https://mastodon.world,https://fosstodon.org,https://mas.to,https://hachyderm.io` | Comma-separated Mastodon instances to query |
| `MASTODON_TAGS` | `spotify,SpotifyWrapped,music,discoverweekly,nowplaying,playlist,SpotifyPodcast` | Comma-separated hashtags (no `#`) |

> Twitter/X requires paid API access since 2023; Mastodon is the free, public replacement that provides the same shape of data.

### 4.5 Collection settings

| Var | Default | What it is |
|---|---|---|
| `RAW_DATA_DIR` | `./data/raw` | Where Parquet + JSONL are written |
| `MAX_REVIEWS_PER_SOURCE` | `2000` | Safety cap; prevents runaway scrapes |
| `APP_STORE_COUNTRIES` | `us,gb,in,ca,au,de` | iOS storefronts to crawl |
| `PLAY_STORE_LANGS` | `en` | Play Store languages |
| `PLAY_STORE_COUNTRIES` | `us,gb,in,ca,au` | Play Store storefronts |

### 4.6 Reliability

| Var | Default | What it is |
|---|---|---|
| `REQUEST_TIMEOUT_SECONDS` | `20` | Per-request HTTP timeout |
| `RETRY_MAX_ATTEMPTS` | `4` | Max retries on transient failures |
| `RETRY_BACKOFF_SECONDS` | `2` | Base backoff (exponential growth, capped at 8× base) |

### 4.7 Logging

| Var | Default | What it is |
|---|---|---|
| `LOG_LEVEL` | `INFO` | One of `DEBUG / INFO / WARNING / ERROR` |
| `LOG_DIR` | `./logs` | Where the rotating log file is written |

---

## 5. Data Sources & Connectors

Each connector subclasses `BaseConnector` and is registered in `pipeline.py`. They all return objects conforming to `RawReview`.

### 5.1 Google Play Store — `PlayStoreConnector`

| Property | Value |
|---|---|
| Library | `google-play-scraper` |
| Auth required | No |
| Reads | `SPOTIFY_PLAY_STORE_ID` × `PLAY_STORE_LANGS` × `PLAY_STORE_COUNTRIES` |
| Per-locale fetch | `~max_records / (#langs × #countries)` newest reviews |
| Output meta | `thumbs_up`, `review_created_version`, `reply_content`, `replied_at` |
| Known quirk | Same `reviewId` returned across locales → heavy dedup at write time |

### 5.2 Apple App Store — `AppStoreConnector`

| Property | Value |
|---|---|
| Endpoint | `https://itunes.apple.com/<country>/rss/customerreviews/id=<id>/page=<n>/sortBy=mostRecent/json` |
| Auth required | No |
| Reads | `SPOTIFY_APP_STORE_ID` × `APP_STORE_COUNTRIES` |
| Capacity | ~10 pages × 50 reviews per country |
| Output meta | `vote_count`, `vote_sum`, `version` |
| Polite delay | 0.5 s between pages |

### 5.3 Reddit — `RedditConnector`

Three-layer fallback strategy:

| Layer | When used | Capacity |
|---|---|---|
| **1. PRAW** | If `REDDIT_CLIENT_ID/SECRET` set | Hundreds of submissions + comments per subreddit |
| **2. Public JSON** | No creds — `<base>/r/<sub>/new.json` | Currently blocked by Reddit's WAF (kept for future) |
| **3. Public RSS / Atom** | Final fallback | Up to ~100 entries per `(subreddit, sort_surface)` combo |

RSS strategy: `new` + `top?t=month` sort surfaces × 3 base URLs (`old.reddit.com`, `www.reddit.com`, `api.reddit.com`) × rotated browser UAs × fresh `requests.Session` per call.

**Incremental checkpoints:** every subreddit's reviews are written to `data/raw/reddit/checkpoints/<date>/<sub>.jsonl` the **instant** that subreddit finishes, so a Ctrl-C never loses progress.

| Output meta | `kind` (submission/comment), `subreddit`, `score`, `num_comments`, `upvote_ratio`, `discovered_via_sort`, `auth` (`praw` / `public_json` / `public_rss`) |

### 5.4 Spotify Community Forum — `CommunityForumConnector`

| Property | Value |
|---|---|
| Method | Polite HTML scrape with full Chrome UA + headers |
| Discovery paths | `/`, `/t5/Ongoing-Issues/...`, `/t5/Live-Ideas/...`, `/t5/Help/...`, `/t5/Spotify-Answers/...`, `/t5/Other-Podcasts-Audiobooks/...` |
| Parser | BeautifulSoup + lxml |
| Polite delay | 1.5 s between requests |
| Output meta | `thread_url`, `dom_id` |

### 5.5 Mastodon (Social Media) — `SocialMediaConnector`

| Property | Value |
|---|---|
| Endpoint | `/api/v1/timelines/tag/{tag}?limit=40` |
| Auth required | No |
| Reads | `MASTODON_INSTANCES` × `MASTODON_TAGS` |
| Page size | 40 statuses per request |
| Output meta | `platform`, `instance`, `discovered_via_tag`, `favourites_count`, `reblogs_count`, `replies_count`, `tags` |

---

## 6. Unified Output Schema

Every connector — regardless of source — returns objects matching `RawReview` (defined in `src/phase1_collection/schemas.py`). This is the **contract** downstream phases rely on.

```python
class RawReview(BaseModel):
    review_id:      str                # "<source>:<native_id>", deterministic
    source:         SourceType         # enum: app_store | play_store | reddit | community_forum | social_media
    source_region:  Optional[str]      # country/locale (e.g. "us", "in"); None for global sources
    text:           str                # non-empty
    title:          Optional[str]
    rating:         Optional[float]    # 0-10 normalized
    lang:           Optional[str]
    author:         Optional[str]      # already-public handle
    created_at:     Optional[datetime] # UTC
    url:            Optional[str]      # permalink
    source_meta:    Dict[str, Any]     # source-specific extras
    collected_at:   datetime           # UTC, when ingested
```

Validation rules enforced:

- `extra = "forbid"` → unknown fields are rejected (catches schema drift early)
- All datetimes auto-converted to UTC
- `review_id` is deterministic (`<source>:<native_id>`); long/whitespace IDs are hashed to 16 chars

---

## 7. Storage Layout

Filesystem-backed raw data lake (production: swap with S3/MinIO):

```
data/raw/
├── <source>/
│   ├── run_date=YYYY-MM-DD/
│   │   ├── <source>_<run_id>.parquet       ← columnar dump
│   │   └── <source>_<run_id>.jsonl         ← human-readable mirror
│   └── manifest.jsonl                      ← append-only audit log
└── reddit/checkpoints/<YYYY-MM-DD>/
    └── <subreddit>.jsonl                   ← per-subreddit incremental saves
```

### Manifest entry format

```json
{
  "run_id": "20260622T132703_8b59fb9b",
  "source": "play_store",
  "records_in": 500,
  "records_written": 100,
  "duplicates_dropped": 400,
  "parquet_path": "data/raw/play_store/run_date=2026-06-22/play_store_...parquet",
  "jsonl_path":   "data/raw/play_store/run_date=2026-06-22/play_store_...jsonl",
  "written_at":   "2026-06-22T13:27:04.123456+00:00"
}
```

### Idempotency guarantees

- Every run gets a unique `run_id` (timestamp + 8-char UUID) → no overwrites
- Within a run, dedup by `review_id` → no double-writes
- Manifest is append-only → full audit trail forever

### Phase 5 index layout

Queryable stores built from Phases 1–4 outputs (production: swap DuckDB → Postgres, Chroma → pgvector):

```
data/index/
├── warehouse.duckdb          ← raw_reviews, insights, reviews_enriched, topics, insight_cards
├── catalog.db                ← index_runs + model_versions (SQLite audit trail)
└── chroma/                   ← persistent Chroma collection (2070 review embeddings)
```

**DuckDB tables:**

| Table | Source | Rows (first run) |
|---|---|---|
| `raw_reviews` | Phase 1 JSONL | 2,277 |
| `insights` | Phase 2 CSV (deduped) | 2,277 |
| `reviews_enriched` | Phase 3 `insights_with_topics.csv` + raw join | 2,070 |
| `topics` | Phase 3 `topics.csv` | 60 |
| `insight_cards` | Phase 4 `insight_cards.csv` | 53 |

**View:** `v_cards_with_topics` — insight cards joined to topic labels/keywords.

---

## 8. How to Run

### One-time setup

```bash
# 1. Install deps
python -m pip install -r requirements.txt

# 2. Copy env template and fill it in
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
```

### CLI commands

```bash
# Run all 5 sources
python run_phase1.py

# List available sources
python run_phase1.py --list

# Run one source
python run_phase1.py -s play_store

# Run multiple sources
python run_phase1.py -s play_store -s app_store

# Machine-readable summary for schedulers
python run_phase1.py --json
```

### Helper

```bash
# Show total records on disk per source
python inspect_runs.py
```

### Scheduling (production)

Wrap `CollectionPipeline.run()` in an Airflow / Prefect DAG (one task per `SourceType`) or run nightly via Task Scheduler / cron:

```bash
python run_phase1.py --json >> data/runs.jsonl
```

---

## 9. Reliability Features

Built into the pipeline:

| Feature | Implementation |
|---|---|
| Retry with exponential backoff | `utils.with_retries` decorator (tenacity) |
| Per-source isolation | One source failing never aborts the run (try/except in `pipeline.py`) |
| Safety cap | `MAX_REVIEWS_PER_SOURCE` enforced in `BaseConnector.collect()` |
| Idempotent writes | Per-run UUID + in-batch dedup |
| Append-only audit log | `manifest.jsonl` per source |
| Rotating logs | 10 MB file rotation, 14-day retention |
| Multi-base fallback | Reddit tries `old.reddit.com` → `www.reddit.com` → `api.reddit.com` |
| Multi-instance fallback | Mastodon queries 5 instances × 7 tags |
| Browser UA rotation | Reddit + Community defeat WAF fingerprinting |
| Fresh session per request | Reddit RSS avoids cookie-based WAF profiling |
| Incremental checkpoints | Reddit writes per-subreddit JSONL the instant it completes |

---

## 10. Edge Cases Handled in Code

Cross-referenced against [`edgecases.md`](edgecases.md):

| # | Edge case | How we handle it |
|---|---|---|
| 1.1.1 / 1.1.4 | Rate limits, 5xx errors | `tenacity` exponential backoff |
| 1.1.5 | Auth missing | Reddit warns + falls back to RSS instead of crashing |
| 1.1.6 | Geo bias | Every record tagged with `source_region`; multi-country fetch |
| 1.2.1 | Volume spikes | `MAX_REVIEWS_PER_SOURCE` cap in `BaseConnector.collect()` |
| 1.3.3 | robots / polite scraping | Community connector uses real browser UA + sleep |
| 2.2.3 / 2.2.4 | Duplicates | Dedup-by-`review_id` in `RawDataLake.write` |
| Schema drift | Strict Pydantic schema (`extra="forbid"`) at boundary | |
| Source isolation | Pipeline-level try/except per connector | |
| Reproducibility | Unique `run_id` per run; append-only manifest | |
| Progress loss | Per-subreddit incremental checkpoints in Reddit | |

---

## 11. Current Corpus on Disk

As of the last successful run (2026-06-22):

| Source | Files | Records |
|---|---|---|
| Apple App Store | 5 | **1,100** |
| Mastodon (social media) | 3 | **733** |
| Spotify Community Forum | 3 | **342** |
| Google Play Store | 5 | **315** |
| Reddit | 2 | **50** |
| **TOTAL** | **18** | **2,540** |

Sample records (real text from disk):

- Play Store (5★, US): *"great app"* — Mark Chadwick
- Play Store (1★, US): *"okay this has been going on for long time now. why is my account telling me I'm offline despite my network connection being..."*
- Community Forum: *"Hey everyone, The World Cup is finally here, bringing the world together for an incredible month of football..."*

Run `python inspect_runs.py` any time to see updated totals.

---

## 12. Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| **Reddit WAF blocks unauthenticated requests** | Public JSON path returns 403; RSS rate-limits aggressively after a few pulls | Add Reddit OAuth credentials (free, 5-min signup) — PRAW path bypasses WAF entirely |
| **Twitter / X requires paid API** | Cannot collect tweets | Mastodon connector provides equivalent public-post data for free |
| **App Store RSS caps at 500/country** | Cannot pull years of history in one call | Run periodically; reviews accumulate in manifest over time |
| **Play Store returns same `reviewId` across locales** | Heavy in-batch dedup (~80% drop rate) | Expected behavior; dedup is correct |
| **Local FS storage (raw lake)** | Not suitable for multi-machine production | Swap `RawDataLake` for S3 / MinIO; Phase 5 adds DuckDB + Chroma locally |
| **No language detection yet** | Multilingual reviews not tagged | Added in Phase 2 (preprocessing) |
| **No PII redaction yet** | Authors stored as-is (already public) | Added in Phase 2 (preprocessing) |

---

## 13. Phase 3 — Topic Modeling & Clustering

Phase 3 turns the 2,277 atomic Phase-2 insights into a small set of named
**clusters of user pain** — exactly what Phase 4 needs to write PM-ready
insight cards. We use the stack named in [`architecture.md`](architecture.md):
**Sentence-Transformers + BERTopic (UMAP + HDBSCAN + c-TF-IDF)**, with an
optional **Groq** pass to generate human-friendly cluster names.

### 13.1 What runs end-to-end

| Step | Input | Tool | Output |
|---|---|---|---|
| 1. Load | `data/processed/insights.csv` | `loader.py` (pandas) | DataFrame, dedup, optional discovery-only filter |
| 2. Build text-to-embed | per row | `verbatim_quote :: Need: <unmet_need>` | one short string per review |
| 3. Embed | strings | `sentence-transformers/all-MiniLM-L6-v2` (CPU, 384 dims) | `embeddings.npy` (cached) |
| 4. Cluster | embeddings | BERTopic (UMAP 5d + HDBSCAN + c-TF-IDF) | per-row `topic_id` |
| 5. Per-cluster stats | rows in cluster | pure pandas | size, %, top pain/sentiment/segment/sources |
| 6. Label cluster | top keywords + 5 quotes | Groq (`openai/gpt-oss-20b`, JSON-mode) | 3-7 word title; falls back to keyword join |
| 7. Persist | all of the above | `storage.py` | `topics.csv`, `insights_with_topics.csv`, `topic_model/` |

Embeddings are cached: the cache is invalidated only when the `review_id`
ordering or the embedding model id changes. A second run is therefore
near-instant up to the BERTopic step.

### 13.2 Inputs (env variables)

All knobs live in `.env` (see `.env.example`). Defaults in parentheses.

| Var | Default | What it controls |
|---|---|---|
| `EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model (any ST-compatible id works) |
| `EMBED_BATCH_SIZE` | `64` | Embedding mini-batch |
| `MIN_CLUSTER_SIZE` | `8` | HDBSCAN `min_cluster_size`; lower → more, smaller topics |
| `UMAP_N_COMPONENTS` | `5` | Target dim after UMAP |
| `UMAP_N_NEIGHBORS` | `10` | UMAP neighborhood size (smaller = more local structure) |
| `TOP_DOCS_PER_TOPIC` | `5` | Number of verbatim quotes saved per cluster |
| `LLM_TOPIC_LABELS` | `true` | If true and `GROQ_API_KEY` is set, ask the LLM for a clean title |
| `CLUSTER_DISCOVERY_ONLY` | `false` | If true, drops rows where `discovery_related=False` before clustering |
| `TOPICS_CSV` | `topics.csv` | Output filename (one row per cluster) |
| `INSIGHTS_WITH_TOPICS_CSV` | `insights_with_topics.csv` | Output filename (per-review join) |
| `EMBEDDINGS_NPY` | `embeddings.npy` | Cached embedding matrix |
| `EMBEDDING_INDEX_CSV` | `embedding_index.csv` | Row → `review_id` map for `embeddings.npy` |
| `TOPIC_MODEL_DIR` | `topic_model` | Serialized BERTopic model (safetensors) |

`GROQ_API_KEY` / `GROQ_MODEL` / `GROQ_TEMPERATURE` / `GROQ_MAX_TOKENS` from
Phase 2 are reused as-is. If `GROQ_API_KEY` is empty, labels fall back to a
slash-joined list of the cluster's top-3 keywords — Phase 3 still completes
fully without any LLM.

### 13.3 Output schemas

**`topics.csv` — one row per cluster (the headline artifact):**

| Column | Type | Meaning |
|---|---|---|
| `topic_id` | int | BERTopic id (`-1` = noise / unclustered) |
| `label` | str | Human-friendly title (LLM-generated or keyword-derived) |
| `size` | int | Number of reviews in this cluster |
| `share_pct` | float | Cluster size as % of clustered reviews |
| `discovery_share_pct` | float | % of cluster's reviews flagged `discovery_related` in Phase 2 |
| `top_pain_category` | str | Most common Phase-2 pain category |
| `top_sentiment` | str | Most common Phase-2 sentiment |
| `top_segment` | str | Most common Phase-2 user segment |
| `top_sources` | list (`\|\|`-joined) | Top 3 originating sources |
| `keywords` | list (`\|\|`-joined) | Top c-TF-IDF terms |
| `representative_quotes` | list (`\|\|`-joined) | Verbatim user quotes (the "evidence panel" for Phase 4) |
| `representative_review_ids` | list (`\|\|`-joined) | Foreign keys for those quotes |
| `embedding_model` | str | Model id used to embed |
| `created_at` | datetime (UTC) | When this row was computed |

**`insights_with_topics.csv` — per-review join (Phase-2 insight ⨝ Phase-3 assignment):**

All Phase-2 columns plus:

- `topic_id` (int; `-1` = noise)
- `topic_label` (str; falls back to `"Noise / Unclustered"`)
- `topic_probability` (float or empty)

### 13.4 Module layout

```
src/phase3_clustering/
├── __init__.py        ← public exports
├── config.py          ← Pydantic settings (env-driven)
├── schemas.py         ← Topic + TopicAssignment models, CSV column orders
├── utils.py           ← logging + retry helpers (mirrors Phase 1/2)
├── loader.py          ← reads insights.csv, dedupes, builds text_to_embed
├── embedder.py        ← Sentence-Transformers wrapper + npy cache
├── clusterer.py       ← BERTopic (UMAP + HDBSCAN + c-TF-IDF)
├── labeler.py         ← Groq-based topic naming (heuristic fallback)
├── storage.py         ← writes both output CSVs
└── pipeline.py        ← ClusteringPipeline orchestrator
```

### 13.5 CLI

```bash
# Default run (settings from .env)
python run_phase3.py

# Only cluster discovery-related insights (~30% of corpus)
python run_phase3.py --discovery-only

# Finer-grained topics (more, smaller clusters)
python run_phase3.py --min-cluster-size 10

# Skip the LLM labeling pass (no Groq quota burned)
python run_phase3.py --no-llm-labels

# Force re-embedding from scratch (ignore the cache)
python run_phase3.py --rebuild

# Machine-readable summary for schedulers
python run_phase3.py --json
```

Inspect the results:

```bash
# Top 20 clusters at a glance
python inspect_topics.py

# Drill into one cluster (full keyword list + all evidence quotes)
python inspect_topics.py --topic 3
```

### 13.6 Why these specific choices

| Choice | Why |
|---|---|
| `all-MiniLM-L6-v2` for embeddings | 384-dim, ~80 MB, CPU-only, ~25 s for 2k docs, strong for short product-feedback text |
| Embed `verbatim_quote :: Need: <unmet_need>` (not raw review) | Phase 2 already distilled out the noise; embedding the distilled text gives tighter, more PM-relevant clusters |
| UMAP 5d + HDBSCAN | Standard BERTopic recipe; UMAP preserves local structure better than PCA, HDBSCAN auto-picks the number of topics and quarantines noise into `-1` |
| `min_cluster_size=8`, `umap_n_neighbors=10` | At 2k short-text docs the BERTopic defaults (15/15) produced one mega-cluster covering 97% of reviews. Tightening both gives ~25-50 meaningful clusters with healthy noise on the long tail |
| Custom domain stopwords (`spotify`, `music`, `app`, `song`, ...) | Without these, every cluster's top keywords were dominated by "spotify" — useless for naming themes |
| c-TF-IDF for keywords | Built into BERTopic; gives one ranked vocabulary per cluster without extra code |
| Groq labels (optional) | Keyword joins read like SEO tags; a 3-7 word LLM title reads like a Jira ticket — much better as a Phase 4 insight-card seed |
| Per-cluster `top_pain_category` / `top_sentiment` / `top_segment` | Carries Phase-2 structured signal forward so a PM can sort `topics.csv` by, e.g., "negative + premium + discovery" in Excel without further code |

### 13.7 Reliability features

| Feature | Implementation |
|---|---|
| Deterministic runs | UMAP `random_state=42`, embeddings normalized, `temperature=0` for labels |
| Cached embeddings | `data/processed/embeddings.npy` + index CSV; invalidated only on review_id reorder or model change |
| Schema-validated outputs | `Topic` and `TopicAssignment` Pydantic models enforced before CSV write |
| LLM label fallback | Any Groq failure (rate limit, decommissioned model, bad JSON) silently falls back to the keyword heuristic |
| Configurable strictness | `--no-llm-labels` for fully offline runs; `--rebuild` to invalidate embed cache; `--discovery-only` to focus on the project's primary theme |
| Lazy ML imports | `sentence_transformers`, `bertopic`, `umap`, `hdbscan` are imported only when needed — `import src.phase3_clustering` is cheap |

### 13.8 Edge cases handled

| # | Edge case | How we handle it |
|---|---|---|
| 3.E1 | Duplicate `review_id` rows in `insights.csv` (Phase 2 echoed across batches) | `loader.py` drops duplicates, keeping the first |
| 3.E2 | Empty / near-empty `verbatim_quote` + `unmet_need` | Rows with composed length `< 8` chars dropped before embedding |
| 3.E3 | Groq daily quota exhausted | `labeler.py` falls back to heuristic keyword labels per cluster — pipeline still completes |
| 3.E4 | Unsupported / decommissioned / reasoning-only LLM (e.g. `gpt-oss-20b` returning empty content under strict JSON mode) | Labeler does a **single-shot** call (no retries) and a **5-failure circuit breaker** that disables LLM for the rest of the run after 5 consecutive failures |
| 3.E5 | BERTopic produces no clusters (everything noise) | Pipeline still emits an empty `topics.csv` + an `insights_with_topics.csv` where everything has `topic_id=-1` |
| 3.E6 | Cached embeddings stale | Cache check compares saved `review_id` list AND `embed_model` — any mismatch triggers a fresh encode |
| 3.E7 | Missing `insights.csv` | `loader.py` raises `FileNotFoundError` with a clear "run `python run_phase2.py` first" message |
| 3.E8 | One mega-cluster covering ~all docs | Tuning: `min_cluster_size=8` + `umap_n_neighbors=10` + custom domain stopwords (`spotify`, `music`, `app`, ...) produce ~60 useful clusters at 2k docs |
| 3.E9 | Column collisions in the insights ⨝ assignment merge | `storage.py` drops `topic_id`/`topic_probability` from the left side before merging so the right side is authoritative |
| 3.E10 | Windows cp1252 console crashes on Unicode characters in user reviews | `inspect_topics.py` reconfigures stdout/stderr to UTF-8 on startup |

### 13.9 First-run results (2026-06-23)

Run against `data/processed/insights.csv` (2,277 unique insights from Phase 2):

| Metric | Value |
|---|---|
| Insights considered | 2,277 |
| After dedup + min-length filter | **2,070** docs |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` (384 dims, CPU) |
| Embedding time (cold) | ~25 s for 2,070 docs |
| BERTopic fit time | ~50 s |
| LLM labeling time | ~3-4 min (mix of LLM + heuristic fallback) |
| **Topics discovered** | **59** |
| Reviews clustered | 1,451 (70%) |
| Noise (`topic_id = -1`) | 619 (30%) — these are short, generic praise / non-actionable rants |
| Total runtime | ~5.5 min |

A few of the biggest, most actionable clusters:

| Topic | Size | Discovery% | Pain | Sent | Theme |
|---|---|---|---|---|---|
| 2 | 75 | 97% | discovery | positive | Users request personalized music recommendations |
| 7 | 47 | 91% | recommendation_quality | positive | Discover Weekly lacks genre filtering |
| 9 | 31 | 23% | ui_ux | negative | Restore 'What's New' feature |
| 11 | 30 | 3% | ads | negative | Reduce ad frequency in app |
| 12 | 29 | 59% | discovery | positive | Add pinned playlist folders |
| 16 | 28 | 86% | discovery | positive | Improve discovery of niche hip-hop mixes |
| 25 | 20 | 5% | pricing | negative | Users frustrated by premium restrictions and cost |
| 26 | 20 | 50% | listening_behavior | negative | Shuffle repeats same song rotation |
| 29 | 18 | 89% | discovery | positive | Increase playlist pin limit for dark themes |

These clusters are the direct input to Phase 4 insight card generation.

---

## 14. Phase 4 — Insight Generation (PM-ready cards)

Phase 4 turns each Phase-3 topic cluster into a **PM-ready insight card** — the deliverable described in [`architecture.md`](architecture.md) §Phase 4. Each card includes a title, narrative, severity, trend, affected segments, evidence quotes, and a suggested product opportunity.

### 14.1 What runs end-to-end

| Step | Input | Component | Output |
|---|---|---|---|
| 1. Load | `topics.csv`, `insights_with_topics.csv` | `loader.py` | DataFrames + optional review timestamps from raw JSONL |
| 2. Aggregate | per-cluster reviews | `aggregator.py` | `TopicBundle` (stats, distributions, quotes, trend) |
| 3. Score | bundles | `scorer.py` | `priority_score` 0–100 (volume × sentiment severity × discovery × trend) |
| 4. Synthesize | bundle + quotes (RAG) | `generator.py` + Groq | `InsightCard` via LLM (or rule-based fallback) |
| 5. Persist | cards | `storage.py` | `insight_cards.csv` + `insight_cards.json` |

Architecture components mapped:

| Architecture component | Implementation |
|---|---|
| Theme Aggregator | `aggregator.py` — cluster stats + pain/segment/source breakdowns |
| Pain Point Summarizer | Groq prompt → `narrative` field (2–3 sentences) |
| Unmet Needs Extractor | Aggregated from Phase-2 `unmet_need` + LLM refinement |
| Trend Detector | First-half vs second-half review volume using raw `created_at` timestamps |
| Segment Comparator | `segment_breakdown` in bundle + `segment_notes` in card |
| Evidence Linker | Up to 8 verbatim quotes + review_ids per card |
| Priority Scorer | `scorer.py` — ranks cards for PM triage |

### 14.2 Inputs (env variables)

| Var | Default | What it controls |
|---|---|---|
| `PHASE4_MIN_TOPIC_SIZE` | `10` | Skip clusters with fewer than N reviews |
| `PHASE4_MAX_EVIDENCE_QUOTES` | `8` | Max verbatim quotes attached per card |
| `PHASE4_INCLUDE_NOISE` | `false` | Include BERTopic noise bucket (`topic_id=-1`) |
| `PHASE4_DISCOVERY_ONLY` | `false` | Only synthesize discovery-heavy clusters |
| `PHASE4_MIN_DISCOVERY_SHARE_PCT` | `50` | Threshold when `PHASE4_DISCOVERY_ONLY=true` |
| `PHASE4_USE_LLM_CARDS` | `true` | Use Groq RAG; `false` or `--no-llm` → rule-based only |
| `INSIGHT_CARDS_CSV` | `insight_cards.csv` | Output CSV path |
| `INSIGHT_CARDS_JSON` | `insight_cards.json` | Output JSON path |
| `GROQ_API_KEY` / `GROQ_MODEL` | *(from Phase 2)* | Reused for card synthesis |

### 4.5 Phase 5 — Storage & Indexing

| Var | Default | What it controls |
|---|---|---|
| `INDEX_DATA_DIR` | `./data/index` | Root directory for DuckDB, Chroma, and catalog |
| `PHASE5_WAREHOUSE_DB` | `warehouse.duckdb` | DuckDB filename inside `INDEX_DATA_DIR` |
| `PHASE5_CATALOG_DB` | `catalog.db` | SQLite catalog filename inside `INDEX_DATA_DIR` |
| `PHASE5_CHROMA_DIR` | `chroma` | Chroma persistent directory inside `INDEX_DATA_DIR` |
| `PHASE5_CHROMA_COLLECTION` | `review_embeddings` | Chroma collection name |
| `PHASE5_DEFAULT_SEARCH_K` | `10` | Default top-k for semantic search |
| `EMBED_MODEL` | *(from Phase 3)* | Reused to embed query strings at search time |

### 4.6 Phase 6 — Visualization & Delivery

| Var | Default | What it controls |
|---|---|---|
| `PHASE6_APP_TITLE` | `Spotify Review Discovery Engine` | Browser tab / sidebar title |
| `PHASE6_DEFAULT_CARD_LIMIT` | `53` | Max cards loaded in dashboard |
| `PHASE6_DEFAULT_SEARCH_K` | `10` | Default semantic search results in UI |
| `PHASE6_CHAT_CONTEXT_K` | `8` | Reviews retrieved for RAG chat context |
| `PHASE6_ENABLE_CHAT` | `true` | Show/hide the Ask the Reviews page |
| `PHASE6_EXPORT_DIR` | `./data/exports` | Where one-click digest exports are saved |
| `GROQ_API_KEY` / `GROQ_MODEL` | *(from Phase 2)* | Reused for RAG chat synthesis |

### 14.3 Output schema (`InsightCard`)

Matches the architecture's insight card JSON:

```json
{
  "insight_id": "INS-007",
  "topic_id": 7,
  "title": "Discover Weekly lacks genre filtering",
  "theme": "Recommendation Quality",
  "narrative": "47 users discuss Discover Weekly customization...",
  "severity": "medium",
  "trend": "stable",
  "priority_score": 28.4,
  "affected_segments": ["unknown", "heavy"],
  "top_unmet_needs": ["genre filters for Discover Weekly"],
  "evidence_quotes": ["..."],
  "evidence_review_ids": ["reddit:rss_t3_..."],
  "supporting_review_count": 47,
  "discovery_share_pct": 91.5,
  "negative_share_pct": 12.0,
  "top_sources": ["social_media", "reddit"],
  "top_pain_category": "recommendation_quality",
  "suggested_opportunity": "Add genre/mood filters to Discover Weekly",
  "segment_notes": "Most vocal segments: unknown (40), heavy (3)",
  "model_used": "llama-3.1-8b-instant",
  "generated_at": "2026-06-23T..."
}
```

Cards are sorted by `priority_score` descending in both CSV and JSON outputs.

### 14.4 CLI

```bash
# Default — Groq RAG cards from all clusters >= 10 reviews
python run_phase4.py

# Offline / no API quota — rule-based cards from aggregated stats (~3 s)
python run_phase4.py --no-llm

# Only discovery-heavy clusters
python run_phase4.py --discovery-only

# Skip small clusters
python run_phase4.py --min-topic-size 20

# Override Groq model
python run_phase4.py -m llama-3.1-8b-instant

python run_phase4.py --json
```

Inspect results:

```bash
python inspect_cards.py              # top 15 by priority
python inspect_cards.py --top 30
python inspect_cards.py --card INS-026   # full detail for Shuffle topic
```

### 14.5 Reliability features

| Feature | Implementation |
|---|---|
| Rule-based fallback | Every topic gets a card even if Groq is down — `model_used=rule-based` |
| LLM circuit breaker | After 5 consecutive Groq failures, remaining topics use rule-based synthesis |
| Single-shot LLM calls | No retry loops on labeling (prevents 30+ min hangs on JSON-mode failures) |
| Timestamp-backed trends | Joins raw JSONL for `created_at`; falls back to `trend=unknown` gracefully |
| Schema validation | Pydantic `InsightCard` enforced before write; bad LLM JSON → rule-based card |

### 14.6 First-run results (2026-06-23)

| Metric | Value |
|---|---|
| Topics on disk | 60 (59 real + 1 noise) |
| Bundles synthesized (size ≥ 10) | **53** |
| Insight cards written | **53** |
| Timestamps loaded | 1,924 reviews from raw JSONL |
| Rule-based runtime | **2.8 s** |
| LLM runtime | ~3–8 min (53 Groq calls, model-dependent) |

Top priority cards (rule-based scoring):

| ID | Priority | Severity | Reviews | Title |
|---|---|---|---|---|
| INS-000 | 37.3 | low | 107 | Users switching to Tidal over Spotify Wrapped |
| INS-002 | 35.1 | low | 75 | Users request personalized music recommendations |
| INS-007 | 28.4 | low | 47 | Discover Weekly lacks genre filtering |
| INS-026 | 22.1 | medium | 20 | Shuffle repeats same song rotation |
| INS-025 | 21.8 | medium | 20 | Users frustrated by premium restrictions and cost |
| INS-011 | 21.5 | medium | 30 | Reduce ad frequency in app |

Re-run with LLM when Groq quota is available for richer narratives:

```bash
python run_phase4.py -m llama-3.1-8b-instant
```

---

## 15. Phase 5 — Storage & Indexing

Phase 5 consolidates all prior outputs into **queryable stores** — the foundation for Phase 6 dashboards and RAG chatbots. Per [`architecture.md`](architecture.md) §Phase 5, we implement:

| Architecture target | MVP implementation |
|---|---|
| Processed warehouse | **DuckDB** (`warehouse.duckdb`) |
| Vector DB for semantic search | **Chroma** (persistent, local) |
| Insight card store | `insight_cards` table in DuckDB |
| Metadata catalog | **SQLite** (`catalog.db`) — index runs + model versions |

Production upgrade path: DuckDB → Postgres/BigQuery, Chroma → pgvector.

### 15.1 What runs end-to-end

| Step | Input | Component | Output |
|---|---|---|---|
| 1. Load | raw JSONL, insights.csv, topics, cards, embeddings | `loaders.py` | DataFrames + numpy matrix |
| 2. Dedupe | insights.csv (409 duplicate rows) | `loaders.py` | 2,277 unique insights |
| 3. Enrich | insights_with_topics + raw timestamps | `loaders.py` | `reviews_enriched` with source/sentiment/topic |
| 4. Warehouse | all tables | `warehouse.py` | DuckDB rebuild (drop + reload) |
| 5. Vector index | `embeddings.npy` + metadata | `vector_index.py` | Chroma collection (2,070 vectors) |
| 6. Catalog | run stats + model versions | `catalog.py` | SQLite `index_runs` row |
| 7. Query | natural language / filters | `query.py` | ranked hits, card lists, stats |

Architecture components mapped:

| Architecture component | Implementation |
|---|---|
| Processed warehouse | `DuckDBWarehouse` — 5 tables + `v_cards_with_topics` view |
| Vector DB | `VectorIndex` — Chroma persistent client, cosine similarity |
| Insight card store | `insight_cards` table + `QueryEngine.list_cards()` / `get_card()` |
| Metadata catalog | `MetadataCatalog` — `index_runs`, `model_versions` in SQLite |
| Semantic search | `QueryEngine.semantic_search()` — embed query → Chroma → DuckDB join |
| Structured filters | `QueryEngine.filter_reviews()` — source, sentiment, topic, discovery |

### 15.2 Inputs (env variables)

See [§4.5](#45-phase-5--storage--indexing). No new API keys required — reuses Phase 3 embedder for query-time encoding.

### 15.3 CLI commands

```bash
# Build full index (DuckDB + Chroma + catalog)
python run_phase5.py

# DuckDB only — skip Chroma rebuild
python run_phase5.py --skip-vectors

# Machine-readable summary
python run_phase5.py --json

# Semantic search (loads embedder on first call ~90s, then fast)
python search_reviews.py "discover weekly genre filter"

# Structured filters
python search_reviews.py --filter --source reddit --sentiment negative
python search_reviews.py --filter --topic 26 --discovery-only

# Insight cards
python search_reviews.py --cards --severity high
python search_reviews.py --card INS-007

# Index statistics
python search_reviews.py --stats
```

### 15.4 Query API (`QueryEngine`)

Programmatic access for Phase 6 dashboard:

```python
from src.phase5_storage import QueryEngine

engine = QueryEngine()

# Natural-language search with optional metadata filters
hits = engine.semantic_search("shuffle repeats same songs", k=5, sentiment="negative")

# SQL-style filters over enriched reviews
df = engine.filter_reviews(source="reddit", topic_id=26, limit=20)

# PM triage — cards ranked by priority
cards = engine.list_cards(severity="high", min_priority=20.0)
card = engine.get_card("INS-007")

stats = engine.stats()  # row counts per store
engine.close()
```

### 15.5 First-run results (2026-06-23)

| Metric | Value |
|---|---|
| Index build time | **6.6 s** |
| Raw reviews indexed | 2,277 |
| Insights (deduped) | 2,277 |
| Enriched reviews | 2,070 |
| Topics | 60 |
| Insight cards | 53 |
| Vectors in Chroma | 2,070 |
| Catalog run id | 1 |

Semantic search sanity check — query `"discover weekly genre filter"` returned top hit at **0.843** similarity, correctly mapped to topic *Discover Weekly lacks genre filtering*.

Re-run after any Phase 1–4 refresh:

```bash
python run_phase5.py
```

---

## 16. Phase 6 — Visualization & Delivery

Phase 6 delivers insights in a **PM-usable format** — the delivery layer described in [`architecture.md`](architecture.md) §Phase 6. The MVP is a **Streamlit dashboard** backed by the Phase-5 `QueryEngine`, with Plotly charts and one-click export.

### 16.1 Architecture mapping

| Architecture component | Implementation |
|---|---|
| Insight Dashboard | `app.py` → **Overview** page (KPIs, priority bar, severity pie, themes) |
| Segment Explorer | **Segments** page — sentiment stacks, pain heatmap, source sunburst |
| Topic Trend Charts | **Trends** page — monthly volume per cluster (where timestamps exist) |
| Review Search UI | **Search** page — semantic search + structured filters |
| Insight Report Generator | **Export** page — Markdown download + save to `data/exports/` |
| Chatbot (optional) | **Ask the Reviews** — RAG via Chroma retrieval + Groq synthesis |
| Alerting | Not in MVP — future: Slack webhook on high-severity new cards |

### 16.2 Module layout

| File | Role |
|---|---|
| `config.py` | Dashboard title, search defaults, export dir, chat toggle |
| `data.py` | `DashboardData` — analytics SQL + wraps `QueryEngine` |
| `charts.py` | Plotly figures (Spotify-dark theme) |
| `export.py` | Weekly digest as Markdown + JSON |
| `chat.py` | `ReviewChatbot` — semantic retrieval + Groq answer |
| `app.py` | Streamlit UI with 8 sidebar pages |

### 16.3 Dashboard pages

| Page | What PMs see |
|---|---|
| **Overview** | Corpus KPIs, top cards by priority, severity/theme charts, increasing trends |
| **Insight Cards** | Filterable card table + full detail (narrative, evidence, opportunity) |
| **Topics** | Cluster size chart + drill-down into representative reviews |
| **Segments** | Sentiment by segment, source sunburst, pain-category heatmap |
| **Trends** | Multi-select time-series for top topic clusters |
| **Search** | Natural-language semantic search or structured filter mode |
| **Ask the Reviews** | Chat UI with retrieved review context |
| **Export** | Download Markdown digest or save to `data/exports/` |

### 16.4 CLI

```bash
# Prerequisites: Phases 1–5 complete (especially run_phase5.py)
python run_dashboard.py

# Custom port
python run_dashboard.py --port 8502
```

Opens `http://localhost:8501` by default.

### 16.5 Export format

The **Export** page generates a PM-ready digest:

- **Markdown** — headings per card, priority/severity/trend, narrative, opportunity, evidence quotes (paste into Notion/Confluence)
- **JSON** — `{ generated_at, stats, cards[] }` for APIs or scheduled jobs

Saved exports land in `data/exports/insight_digest_<timestamp>.{md,json}`.

### 16.6 Future enhancements (post-MVP)

Per architecture, production delivery may add:

- Slack/email alerting when new high-severity themes emerge
- PDF export (via WeasyPrint or reportlab)
- Next.js frontend for embedded analytics
- Scheduled weekly digest cron

The six-phase pipeline is now **end-to-end complete** from raw collection through PM-facing delivery.

---

## Quick Reference Card

```bash
# Setup
python -m pip install -r requirements.txt
copy .env.example .env           # then fill in REDDIT_CLIENT_ID/SECRET (optional)

# Run
python run_phase1.py             # all sources -> data/raw/*.jsonl
python run_phase2.py              # AI analysis -> data/processed/insights.csv
python run_phase3.py              # clustering   -> data/processed/topics.csv
python run_phase4.py              # insight cards -> data/processed/insight_cards.csv
python run_phase5.py              # index build   -> data/index/

# Inspect
python inspect_runs.py            # raw corpus totals (Phase 1)
python check_coverage.py          # Phase 2 coverage report
python inspect_topics.py          # top clusters (Phase 3)
python inspect_cards.py           # top insight cards by priority (Phase 4)
python inspect_cards.py --card INS-007
python search_reviews.py --stats  # index row counts (Phase 5)
python search_reviews.py "shuffle repeats same songs"
python search_reviews.py --cards --severity high
python run_dashboard.py           # Streamlit PM dashboard (Phase 6)
type logs\phase5_storage.log
```
