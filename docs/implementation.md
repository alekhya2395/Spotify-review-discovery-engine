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
14. [Next Steps (Phase 4+)](#14-next-steps-phase-4)

---

## 1. Implementation Status

| Phase | Status | Notes |
|---|---|---|
| **Phase 1 — Data Collection** | ✅ Implemented | All 5 sources wired; ~2,540 records collected |
| **Phase 2 — AI Analysis (Groq)** | ✅ Implemented | Reads `data/raw/*.jsonl`, sends batches of reviews to Groq, extracts structured insights to `data/processed/insights.csv` (2,277 unique insights, 100% coverage) |
| **Phase 3 — Topic Modeling & Clustering** | ✅ Implemented | Embeds insights with `sentence-transformers/all-MiniLM-L6-v2`, clusters with BERTopic (UMAP + HDBSCAN + c-TF-IDF), generates human-friendly topic labels via Groq |
| Phase 4 — Insight Generation (PM-ready cards) | ⏳ Pending | Aggregation + RAG via Groq, leveraging the clusters from Phase 3 |
| Phase 5 — Storage & Indexing | ⏳ Pending | Raw lake is the local FS today; upgrade to Postgres/Vector DB later |
| Phase 6 — Visualization & Delivery | ⏳ Pending | |

### LLM choice

We use **[Groq](https://groq.com)** with the `llama-3.3-70b-versatile` model for every LLM call in this project (Phase 2 today, Phase 4 later). Reasons:

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
│   └── topic_model/                   ← serialized BERTopic model (safetensors)
│
├── logs/phase1_collection.log         ← rotating log (10 MB × 14 days)
├── logs/phase2_analysis.log           ← rotating log
├── logs/phase3_clustering.log         ← rotating log
├── run_phase1.py                      ← CLI: collection
├── run_phase2.py                      ← CLI: AI analysis
├── run_phase3.py                      ← CLI: clustering
├── inspect_runs.py                    ← helper: show raw totals on disk
├── inspect_insights.py                ← helper: distributions in insights.csv
├── inspect_topics.py                  ← helper: pretty-print topics.csv
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
| **Local FS storage** | Not suitable for multi-machine production | Swap `RawDataLake` for S3 / MinIO in Phase 5 |
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

These are the exact PM-actionable themes Phase 4 will turn into insight cards.

---

## 14. Next Steps (Phase 4+)

Per [`architecture.md`](architecture.md):

- **Phase 4 — Insight Generation (PM-ready cards)**: feed each Phase-3 cluster's top quotes + stats to Groq → emit a JSON "insight card" with title, severity, evidence, affected segments, and a suggested opportunity.
- **Phase 5 — Storage & Indexing**: replace the local FS lake with Postgres + a vector DB (pgvector) so the embeddings from Phase 3 are queryable for "show me reviews like this".
- **Phase 6 — Visualization & Delivery**: Streamlit dashboard backed by `topics.csv` + the vector DB, with a "search by similarity" panel and PM-facing weekly digest export.

The current `data/processed/topics.csv` is the seed Phase 4 needs.

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

# Inspect
python inspect_runs.py            # raw corpus totals (Phase 1)
python check_coverage.py          # Phase 2 coverage report
python inspect_topics.py          # top clusters (Phase 3)
python inspect_topics.py --topic 0  # deep-dive into one cluster
type logs\phase3_clustering.log   # Windows (use `tail -f` on macOS/Linux)
```
