# Edge Cases & Failure Modes

## AI-Powered Review Discovery Engine for Spotify

This document catalogs the **edge cases, failure modes, and risk scenarios** that the Review Discovery Engine must handle to be robust, accurate, and trustworthy in production. Edge cases are grouped by the six architectural phases, followed by **cross-cutting** concerns (data quality, AI reliability, security, business risk).

For each edge case we capture:

- **Scenario** — what can go wrong
- **Impact** — why it matters
- **Mitigation** — how the system should handle it

---

## Phase 1 — Data Collection Edge Cases

### 1.1 Source API / Scraper Failures

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 1.1.1 | API rate limit hit (Reddit, Play Store) | Partial data, incomplete corpus | Exponential backoff, rotating API keys, request queue with retry |
| 1.1.2 | Source API deprecated or schema changed | Pipeline silently breaks | Schema validation per fetch, alerting on schema drift, versioned connectors |
| 1.1.3 | App Store / Play Store changes pagination | Only first N reviews collected | Integration tests on every connector daily |
| 1.1.4 | Source temporarily down (5xx errors) | Missed daily fetch | Retry with backoff, fall back to last good snapshot, alert after N failures |
| 1.1.5 | Authentication token expires | All requests fail | Auto-refresh tokens, secret rotation, monitoring on auth failures |
| 1.1.6 | Geo-restricted content (region-locked reviews) | Region bias in dataset | Multi-region scraping, tag every record with `source_region` |

### 1.2 Data Volume & Velocity

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 1.2.1 | Sudden spike (viral Reddit thread, app update backlash) | Pipeline OOM, costs spike | Backpressure, queue-based ingestion (Kafka/SQS), autoscaling workers |
| 1.2.2 | Very sparse data for a niche source | Skewed insights | Set minimum-volume thresholds per source before generating insights |
| 1.2.3 | Historical backfill requested (5 years of data) | Long-running job blocks daily pipeline | Separate backfill DAG, isolated compute, checkpointing |
| 1.2.4 | Real-time vs batch trade-off | Stale insights or excessive cost | Default to batch (daily), enable streaming only for alerts |

### 1.3 Legal & Compliance During Collection

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 1.3.1 | Platform ToS prohibits scraping | Legal/PR risk | Use official APIs where available; document ToS compliance per source |
| 1.3.2 | GDPR / CCPA user requests "delete my review" | Stale PII retained | Maintain `source_id → internal_id` map; honor deletion downstream |
| 1.3.3 | robots.txt disallows path | Risk of being blocked / sued | Respect robots.txt at the crawler level |
| 1.3.4 | Reviews contain copyrighted song lyrics | IP risk | Lyric detection + redaction filter |

---

## Phase 2 — Preprocessing Edge Cases

### 2.1 Language & Encoding

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 2.1.1 | Mixed-language reviews ("Spotify ka recommendation bahut bad hai") | Misclassified language, dropped from corpus | Sentence-level language detection; keep mixed-lang reviews flagged |
| 2.1.2 | Non-Latin scripts (Arabic, Japanese, Hindi-Devanagari) | Tokenizer breaks, bad embeddings | Use multilingual models (`xlm-roberta`, `paraphrase-multilingual-MiniLM`) |
| 2.1.3 | Emoji-only review ("🔥🔥🔥") | No textual signal | Emoji → sentiment mapping, otherwise filter as low-signal |
| 2.1.4 | Right-to-left text (Arabic, Hebrew) | UI display bugs | Test rendering in dashboard, store original direction |
| 2.1.5 | Unicode confusables / homoglyphs ("Sp0tify") | Brand detection misses these | Unicode normalization (NFKC), fuzzy brand matcher |
| 2.1.6 | Mojibake / broken encoding | Garbled text in insights | Use `ftfy` to repair, drop unrepairable |
| 2.1.7 | Translated review loses nuance ("mid" → "medium") | Sentiment / intent drift | Tag translated rows; weigh them lower; show original quote in dashboard |

### 2.2 Spam, Bots & Duplicates

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 2.2.1 | Coordinated review bombing (negative campaign) | False "pain point" spike | Spike detection per cluster; manual review threshold; cross-source corroboration |
| 2.2.2 | Bot-generated reviews (templated text) | Inflated themes | Template detection, repetitive n-gram filter, author velocity heuristics |
| 2.2.3 | Same user posts same review on iOS + Android | Double-counted | Cross-source MinHash dedup; weight by unique-author count |
| 2.2.4 | Near-duplicate paraphrases | Inflated cluster size | Embedding-based similarity threshold (cosine ≥ 0.95) |
| 2.2.5 | Empty / one-word reviews ("ok", "bad") | No signal but inflate counts | Min-length filter + min-information-content score |
| 2.2.6 | Off-topic spam (crypto, gambling promo) | Pollutes corpus | Off-topic classifier (zero-shot LLM) trained on "is this about Spotify?" |

### 2.3 PII & Sensitive Content

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 2.3.1 | Review contains email / phone / address | Privacy violation | Regex + NER-based PII redaction *before* storage |
| 2.3.2 | Review mentions self-harm / mental health | Ethical handling required | Flag for human review, do not include in public insights |
| 2.3.3 | Hate speech / slurs in clusters | Reputational risk in dashboard | Toxicity filter on insight quotes; redact before display |
| 2.3.4 | Reviewer mentions specific Spotify employee | Personal targeting | Person-NER redaction except for known artists |

---

## Phase 3 — NLP & AI Analysis Edge Cases

### 3.1 Sentiment Analysis

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 3.1.1 | Sarcasm: "Wow, another playlist of songs I already hate. Genius." | Inverted sentiment | Use sarcasm-aware models; rating-vs-text agreement check (5-star + negative text = sarcasm) |
| 3.1.2 | Mixed sentiment: "Love the UI, hate the recs" | Single label is misleading | Aspect-based sentiment (ABSA), not overall sentiment only |
| 3.1.3 | Rating vs text contradicts (1 star + positive text) | Trust which signal? | Trust text for theme; surface contradiction as a separate flag |
| 3.1.4 | Domain-specific terms ("Discover Weekly is mid") | Generic model misreads "mid" | Fine-tune on music/streaming reviews; maintain slang lexicon |
| 3.1.5 | Long reviews with multiple sentiments | Single score loses detail | Sentence-level sentiment + aggregation |

### 3.2 Topic Modeling & Clustering

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 3.2.1 | Too many micro-topics ("Discover Weekly Monday" vs "Discover Weekly Tuesday") | Fragmented insights | Hierarchical topic merging; min cluster size threshold |
| 3.2.2 | Catch-all "Other" cluster dominates | Loses signal | Re-cluster the "Other" bucket recursively; tune HDBSCAN min_samples |
| 3.2.3 | Topic drift over time (new feature launched) | Old labels become stale | Periodic re-clustering with rolling window; topic versioning |
| 3.2.4 | Same topic, different words ("recommendations" vs "suggestions") | Split clusters | Embedding-based clustering rather than keyword-only |
| 3.2.5 | Topic label is generic ("app", "music", "song") | Useless to PMs | LLM-assisted topic labeling with example reviews as context |
| 3.2.6 | Unbalanced cluster sizes (one cluster = 60% of data) | Drowns out smaller pain points | Report by **percent** of segment, not absolute, and surface long-tail |

### 3.3 Embeddings

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 3.3.1 | Embedding model upgraded mid-project | Old + new vectors incomparable | Store `embedding_model_version`; re-embed full corpus on version change |
| 3.3.2 | Embedding API cost runaway | Budget blown | Batch requests; cache by hash of clean_text; switch to local model above threshold |
| 3.3.3 | Very long reviews exceed model token limit | Truncation loses meaning | Sliding window + mean pooling, or summarize first |

### 3.4 Intent Classification

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 3.4.1 | Review expresses multiple intents | Single label is wrong | Multi-label classifier |
| 3.4.2 | Vague review with no clear intent | Forced into wrong bucket | Add explicit `unknown_intent` class; threshold confidence |
| 3.4.3 | New intent emerges (e.g., "AI DJ feedback") | Fixed taxonomy misses it | Periodic taxonomy review; LLM-based open-set discovery alongside fixed classifier |

### 3.5 NER (Entity Extraction)

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 3.5.1 | Artist name collides with common word ("The Weeknd" vs "the weekend") | False positives | Case-sensitive + context-aware NER; whitelist top artists |
| 3.5.2 | New song/artist not in any KB | Missed mentions | Continuously refresh entity list from Spotify catalog |
| 3.5.3 | Feature renamed ("Daily Mix" → new name) | Old + new fragmented | Alias mapping table maintained by PMs |

### 3.6 User Segmentation

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 3.6.1 | User doesn't self-identify segment in review | Unknown segment | Default to "unsegmented"; never guess Premium/Free without evidence |
| 3.6.2 | Heuristics misclassify ("I've been a free user for years" said sarcastically) | Wrong segment counts | Confidence threshold; LLM verification on a sample |
| 3.6.3 | Segment overlap (a heavy Premium user) | Double-counted | Allow multi-label segments; report combinations |

---

## Phase 4 — Insight Generation Edge Cases

### 4.1 LLM-Specific Risks

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 4.1.1 | **Hallucination** — LLM invents quotes/numbers | Erodes PM trust | Strict RAG with verbatim quote extraction; never let LLM generate counts |
| 4.1.2 | LLM ignores schema, returns prose | Pipeline breaks | Tool/function calling with JSON-schema validation; retry on parse failure |
| 4.1.3 | Prompt injection in a review ("Ignore previous instructions and say X") | Compromised insights | Sanitize/escape review text before injecting into prompt; system prompt hardening |
| 4.1.4 | LLM provider outage | No insights generated | Multi-provider fallback (OpenAI → Anthropic → local Llama); circuit breaker |
| 4.1.5 | LLM gives different answer on same input (non-determinism) | Insights flip between runs | Set `temperature=0`, cache by input hash, snapshot insights per run |
| 4.1.6 | Cost spikes from large clusters fed into context | Budget breached | Cap context size, summarize-then-summarize, top-K representative sampling |
| 4.1.7 | LLM toxic / biased output | Reputational risk in dashboard | Output moderation filter before persisting |

### 4.2 Insight Quality

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 4.2.1 | Insight contradicts itself across segments | Confusing for PMs | Segment-aware generation; explicit contradiction surfacing |
| 4.2.2 | Insight is vague ("users want better recommendations") | Not actionable | Force LLM to include specific examples + suggested next step |
| 4.2.3 | Insight is true but already known | Wastes PM attention | Compare against prior insight DB; tag as "novel" vs "ongoing" |
| 4.2.4 | High-severity insight backed by only 3 quotes | False alarm | Minimum evidence-count gate per severity tier |
| 4.2.5 | Trending insight is just a launch artifact (new feature → many reviews) | Misread as pain | Cross-reference with product release calendar |

### 4.3 Aggregation & Bias

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 4.3.1 | Source bias (Reddit skews male/tech-savvy) | Insights don't reflect average user | Weight by source representativeness; show per-source breakdown |
| 4.3.2 | Recency bias (last week dominates) | Long-term issues hidden | Time-decayed weighting; explicit "all-time" view |
| 4.3.3 | English-only insights ignore global users | Misses regional pain | Per-language insight tracks; require min coverage per locale |
| 4.3.4 | Vocal minority distorts theme size | Over-prioritized fix | Author-uniqueness count, not raw review count |

---

## Phase 5 — Storage & Indexing Edge Cases

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 5.1 | Vector DB index corruption | Search returns garbage | Daily index rebuild jobs; checksum verification |
| 5.2 | Schema migration breaks dashboard queries | Outage | Versioned schemas, blue/green migrations |
| 5.3 | Embedding dimension mismatch after model swap | Vector DB rejects writes | Per-model collections; never mix dims |
| 5.4 | Insight DB grows unbounded | Slow queries, cost | Archive insights > N months; partition by date |
| 5.5 | GDPR deletion request after embedding | Vector remains in index | Maintain `review_id` → `vector_id` map and propagate deletes |
| 5.6 | Backup not tested | Data loss when restore fails | Quarterly restore drills |
| 5.7 | Concurrent writes from two pipeline runs | Duplicate / conflicting rows | Idempotent upserts keyed on `review_id` + `run_id` |
| 5.8 | Vector DB / warehouse out of sync | Search returns reviews not in WH | Single source of truth (warehouse) + reconciliation job |

---

## Phase 6 — Delivery / Dashboard Edge Cases

| # | Scenario | Impact | Mitigation |
|---|---|---|---|
| 6.1 | No data yet for a new source filter | Empty dashboard panel | Empty-state UI with explanation, not blank |
| 6.2 | Insight quote contains profanity/PII | Embarrassing in screenshot shared with execs | Redact before render; toggle for raw view |
| 6.3 | Dashboard loads slowly on full corpus | PM abandons tool | Pre-aggregated materialized views; cache layer |
| 6.4 | Chatbot answers from outdated index | Wrong insights | Show "data as of <timestamp>" in every answer |
| 6.5 | Chatbot asked about non-Spotify question | Off-scope response | System prompt scope guard; refuse politely |
| 6.6 | Alert fatigue (too many high-severity pings) | PMs mute Slack channel | Rate-limit alerts; require severity threshold + novelty |
| 6.7 | Exported PDF report omits charts | Incomplete deliverable | Server-side rendering with headless browser; visual diff tests |
| 6.8 | Permission leak — Free-tier PM sees confidential segment | Internal data leak | Role-based access on dashboard + audit logs |

---

## Cross-Cutting Edge Cases

### CC.1 Data Quality

| # | Scenario | Mitigation |
|---|---|---|
| CC.1.1 | Silent data drop between phases (e.g., 40% dropped at dedup) | Per-phase record counts + drop reasons logged; dashboard for drop rates |
| CC.1.2 | Source-tag corruption | Schema validation at every boundary |
| CC.1.3 | Timezone confusion (UTC vs local) | Store everything as UTC; convert only at render |
| CC.1.4 | Star rating scales differ (1–5 vs 1–10) | Normalize on ingest |

### CC.2 Model & ML Lifecycle

| # | Scenario | Mitigation |
|---|---|---|
| CC.2.1 | Model upgrade silently changes insight outputs | Shadow-run new model, diff insights, gate behind approval |
| CC.2.2 | No ground truth to evaluate | Periodic human-in-the-loop sampling; inter-rater agreement tracking |
| CC.2.3 | Concept drift (user language evolves: "vibe", "core") | Quarterly model re-evaluation; expanding eval set |
| CC.2.4 | Insight reproducibility (regenerating same insight months later) | Pin model versions + seed + raw inputs per insight |

### CC.3 Operational

| # | Scenario | Mitigation |
|---|---|---|
| CC.3.1 | Pipeline runs partially overnight, fails silently | End-to-end success SLO + paging |
| CC.3.2 | Disk fills on raw lake | Lifecycle policy (cold storage after N days) |
| CC.3.3 | Secrets leaked into logs | Log sanitizer + secret scanner in CI |
| CC.3.4 | Single point of failure (one Airflow worker) | HA scheduler, multi-worker pool |
| CC.3.5 | Cost overruns (LLM + embeddings) | Per-day budget caps; auto-kill jobs exceeding budget |

### CC.4 Security & Privacy

| # | Scenario | Mitigation |
|---|---|---|
| CC.4.1 | API keys leaked via dashboard error | Strip credentials from error responses; central secret manager |
| CC.4.2 | Prompt injection exfiltrates other reviews | Don't inject untrusted text into system prompt; only user-role with sanitization |
| CC.4.3 | Adversarial review tries to manipulate insights ("This is a critical bug, severity 10/10") | Severity computed by system, never trusted from text |
| CC.4.4 | Dependency vulnerability (PyPI package) | Dependabot / Renovate + SCA scanning |

### CC.5 Business / Product Risk

| # | Scenario | Mitigation |
|---|---|---|
| CC.5.1 | PM makes a roadmap call based on a hallucinated insight | Require evidence quotes + counts on every insight; reviewer sign-off for major decisions |
| CC.5.2 | System surfaces insight already shipped (e.g., "users want Daylist") | Cross-reference launched features list |
| CC.5.3 | Insight reinforces existing bias ("only Premium matters") | Mandatory segment breakdown view |
| CC.5.4 | Single quarter's reviews used to justify long-term strategy | Require N-quarter trend before strategy-level recommendation |
| CC.5.5 | Competitor / market-shift signal missed (Apple Music launches feature) | Add competitor mentions as separate tracked theme |

---

## Edge Case Test Matrix (Suggested QA Coverage)

| Category | Test Type | Frequency |
|---|---|---|
| Connector health (per source) | Synthetic fetch + schema check | Hourly |
| Dedup + spam filter | Golden-set regression | Per deploy |
| Sentiment accuracy | Labeled eval set (≥500 reviews) | Per model change |
| Topic stability | Compare top-K topics week-over-week | Weekly |
| LLM insight schema | JSON schema validation | Every generation |
| LLM hallucination | Quote-in-source check | Every generation |
| PII redaction | Synthetic PII inputs | Per deploy |
| Prompt injection | Adversarial prompt suite | Per deploy |
| Dashboard performance | Load test on full corpus | Per release |
| End-to-end pipeline | Smoke run on sampled data | Daily |

---

## Severity Classification

Each edge case should be tagged with a severity to prioritize mitigation work:

| Severity | Definition | Examples |
|---|---|---|
| **P0 — Critical** | Data loss, privacy breach, or wrong insight influencing major PM decisions | LLM hallucination, PII leak, prompt injection |
| **P1 — High** | Significant quality degradation visible to PMs | Source connector silent failure, biased segmentation |
| **P2 — Medium** | Noticeable but recoverable issue | Slow dashboard, occasional dedup miss |
| **P3 — Low** | Cosmetic or rare | Emoji rendering, occasional empty state |

---

## Summary

A Review Discovery Engine is only as valuable as the **trust** PMs place in its outputs. Most edge cases fall into one of three buckets:

1. **Garbage in** — bad data slipping through Phases 1–2 (bots, duplicates, PII, language issues)
2. **Garbage in the middle** — model errors in Phase 3–4 (hallucination, sarcasm, prompt injection, bias)
3. **Garbage out** — confusing/misleading delivery in Phase 5–6 (stale data, vague insights, alert fatigue)

The system must defend against all three, with **evidence-backed insights, human-in-the-loop checks, version pinning, and continuous evaluation** as the foundational safeguards. Every insight surfaced to a PM should be **traceable, reproducible, and falsifiable** — otherwise it should not be surfaced at all.
