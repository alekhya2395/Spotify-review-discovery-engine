"""Reddit connector.

Tries three strategies, in order:
  1. **PRAW** (preferred) — if REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are set.
  2. **Public JSON fallback** — `<path>.json` (often blocked by Reddit's WAF
     for unauthenticated clients, but worth trying).
  3. **Public RSS / Atom fallback** — `<path>/.rss` from multiple sort
     surfaces (new, top, hot, controversial) across multiple base URLs.
     A fresh requests session is created per call so Reddit's WAF cannot
     fingerprint us via session cookies.

A single connector instance picks whichever path is available so the
pipeline always returns data when Reddit is up.
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple

import requests
from loguru import logger

from ..config import settings
from ..schemas import RawReview, SourceType
from ..utils import with_retries
from .base import BaseConnector, ConnectorError

try:
    import praw
except ImportError:
    praw = None


# Rotated per request to avoid the WAF building a behavioral profile.
_BROWSER_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
)


class RedditConnector(BaseConnector):
    """Crawl Spotify-related subreddits for posts and comments."""

    source = SourceType.REDDIT
    PUBLIC_BASES = (
        "https://old.reddit.com",
        "https://www.reddit.com",
        "https://api.reddit.com",
    )
    RSS_SORT_SURFACES: Tuple[Tuple[str, dict], ...] = (
        ("new", {}),
        ("top", {"t": "month"}),
    )
    POLITE_DELAY_SECONDS = 1.0
    SUBREDDIT_COOLDOWN_SECONDS = 2.0
    SURFACE_DELAY_SECONDS = 1.0
    # Subreddits that have failed >= this many runs in a row are skipped.
    SKIP_AFTER_CONSECUTIVE_FAILURES = 1

    DISCOVERY_QUERIES = [
        "discover OR recommendation OR repetitive OR algorithm",
        "discover weekly OR release radar OR boring OR same songs",
        "stuck in loop OR repeat OR echo chamber OR filter bubble",
        "spotify recommendation bad OR spotify algorithm terrible",
    ]

    def __init__(self, max_records: int | None = None, comment_limit_per_post: int = 25) -> None:
        super().__init__(max_records or settings.max_reviews_per_source)
        self.subreddits = settings.reddit_subreddit_list
        self.comment_limit_per_post = comment_limit_per_post
        self.session = requests.Session()
        # Reddit's anti-bot blocks generic UAs on /r/*/.json. A real browser
        # UA passes the WAF for the unauthenticated public JSON endpoints.
        # If REDDIT_CLIENT_ID/SECRET are set, we still prefer PRAW above.
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def _fetch(self) -> List[RawReview]:
        if settings.reddit_enabled() and praw is not None:
            try:
                return self._fetch_via_praw()
            except Exception as exc:
                logger.warning("[reddit] PRAW path failed, falling back to RSS: {e}", e=exc)
        else:
            logger.info("[reddit] no credentials — using public RSS feeds")

        # Reddit's WAF blocks unauthenticated .json on every base — proven by
        # earlier runs. Skip the JSON path entirely and go straight to RSS,
        # which is reliably served (with rate limits) without auth.
        return self._fetch_via_rss()

    def _client(self):
        return praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            check_for_async=False,
        )

    @with_retries(Exception)
    def _submissions_for(self, reddit, subreddit_name: str, listing_size: int) -> Iterable:
        sub = reddit.subreddit(subreddit_name)
        seen = {}
        for submission in sub.new(limit=listing_size):
            seen[submission.id] = submission
        for submission in sub.top(limit=listing_size, time_filter="month"):
            seen.setdefault(submission.id, submission)
        return seen.values()

    @with_retries(Exception)
    def _search_submissions(self, reddit, subreddit_name: str, query: str, limit: int) -> Iterable:
        """Search a subreddit for discovery-specific posts."""
        sub = reddit.subreddit(subreddit_name)
        seen = {}
        for submission in sub.search(query, sort="relevance", time_filter="year", limit=limit):
            seen[submission.id] = submission
        return seen.values()

    def _fetch_via_praw(self) -> List[RawReview]:
        reddit = self._client()
        out: List[RawReview] = []
        seen_ids: set[str] = set()
        per_sub = max(5, self.max_records // max(1, len(self.subreddits)) // 5)

        for sub_name in self.subreddits:
            # 1. Browse new + top (existing behavior)
            try:
                submissions = list(self._submissions_for(reddit, sub_name, per_sub))
            except Exception as exc:
                logger.error("[reddit] failed r/{s}: {e}", s=sub_name, e=exc)
                submissions = []

            # 2. Search for discovery-specific posts
            for query in self.DISCOVERY_QUERIES:
                try:
                    search_results = list(self._search_submissions(reddit, sub_name, query, limit=50))
                    for s in search_results:
                        if s.id not in seen_ids:
                            submissions.append(s)
                except Exception as exc:
                    logger.debug("[reddit] search failed r/{s} q='{q}': {e}", s=sub_name, q=query, e=exc)

            logger.info("[reddit] r/{s}: {n} total submissions (browse + search)", s=sub_name, n=len(submissions))
            for submission in submissions:
                if submission.id in seen_ids:
                    continue
                seen_ids.add(submission.id)
                review = self._normalize_praw_submission(submission, sub_name)
                if review is not None:
                    out.append(review)
                out.extend(self._normalize_praw_comments(submission, sub_name))
                if len(out) >= self.max_records:
                    return out
        return out

    def _normalize_praw_submission(self, submission, subreddit_name: str) -> Optional[RawReview]:
        text_parts = [t for t in [submission.title, getattr(submission, "selftext", "")] if t]
        text = "\n\n".join(text_parts).strip()
        if not text:
            return None

        created = datetime.fromtimestamp(getattr(submission, "created_utc", 0), tz=timezone.utc)
        try:
            return RawReview(
                review_id=RawReview.make_id(self.source, f"sub_{submission.id}"),
                source=self.source,
                source_region=None,
                text=text,
                title=submission.title,
                rating=None,
                lang=None,
                author=str(submission.author) if submission.author else None,
                created_at=created,
                url=f"https://reddit.com{submission.permalink}",
                source_meta={
                    "kind": "submission",
                    "subreddit": subreddit_name,
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                    "upvote_ratio": getattr(submission, "upvote_ratio", None),
                },
            )
        except Exception as exc:
            logger.debug("[reddit] skipped submission {id}: {e}", id=submission.id, e=exc)
            return None

    def _normalize_praw_comments(self, submission, subreddit_name: str) -> List[RawReview]:
        reviews: List[RawReview] = []
        try:
            submission.comments.replace_more(limit=0)
            for comment in submission.comments.list()[: self.comment_limit_per_post]:
                body = (getattr(comment, "body", "") or "").strip()
                if not body or body in {"[deleted]", "[removed]"}:
                    continue
                created = datetime.fromtimestamp(getattr(comment, "created_utc", 0), tz=timezone.utc)
                try:
                    reviews.append(
                        RawReview(
                            review_id=RawReview.make_id(self.source, f"cmt_{comment.id}"),
                            source=self.source,
                            source_region=None,
                            text=body,
                            title=None,
                            rating=None,
                            lang=None,
                            author=str(comment.author) if comment.author else None,
                            created_at=created,
                            url=f"https://reddit.com{comment.permalink}",
                            source_meta={
                                "kind": "comment",
                                "subreddit": subreddit_name,
                                "parent_submission_id": submission.id,
                                "score": comment.score,
                            },
                        )
                    )
                except Exception as exc:
                    logger.debug("[reddit] skipped comment: {e}", e=exc)
        except Exception as exc:
            logger.warning("[reddit] could not expand comments for {id}: {e}", id=submission.id, e=exc)
        return reviews

    @with_retries(requests.RequestException)
    def _public_get_one(self, base: str, path: str, params: Optional[dict] = None) -> requests.Response:
        url = f"{base}{path}"
        resp = self.session.get(url, params=params, timeout=settings.request_timeout_seconds)
        if resp.status_code in (429, 503):
            raise ConnectorError(f"reddit throttled ({resp.status_code}) on {url}")
        return resp

    def _public_get(self, path: str, params: Optional[dict] = None):
        last_err: Optional[Exception] = None
        for base in self.PUBLIC_BASES:
            try:
                resp = self._public_get_one(base, path, params)
                if resp.status_code == 403:
                    logger.debug("[reddit] 403 from {b}{p} — trying next base", b=base, p=path)
                    last_err = ConnectorError(f"403 from {base}")
                    continue
                resp.raise_for_status()
                return resp.json() or {}
            except Exception as exc:
                last_err = exc
                logger.debug("[reddit] base {b} failed for {p}: {e}", b=base, p=path, e=exc)
                continue
        raise ConnectorError(f"all reddit bases failed for {path}: {last_err}")

    def _fetch_via_public_json(self) -> List[RawReview]:
        out: List[RawReview] = []
        seen_ids: set[str] = set()
        per_sub = max(5, self.max_records // max(1, len(self.subreddits)))

        for sub_name in self.subreddits:
            all_children: list[dict] = []

            # 1. Browse new (existing)
            try:
                listing = self._public_get(f"/r/{sub_name}/new.json", params={"limit": min(per_sub, 100)})
                all_children.extend(((listing.get("data") or {}).get("children")) or [])
            except Exception as exc:
                logger.error("[reddit] public listing failed r/{s}: {e}", s=sub_name, e=exc)

            # 2. Search for discovery-specific posts
            for query in self.DISCOVERY_QUERIES:
                try:
                    search_listing = self._public_get(
                        f"/r/{sub_name}/search.json",
                        params={"q": query, "restrict_sr": "on", "sort": "relevance", "t": "year", "limit": 50},
                    )
                    all_children.extend(((search_listing.get("data") or {}).get("children")) or [])
                    time.sleep(self.POLITE_DELAY_SECONDS)
                except Exception as exc:
                    logger.debug("[reddit] public search failed r/{s} q='{q}': {e}", s=sub_name, q=query, e=exc)

            logger.info("[reddit] r/{s}: {n} submissions (public browse + search)", s=sub_name, n=len(all_children))

            for child in all_children:
                data = child.get("data") or {}
                sub_id = data.get("id")
                if sub_id in seen_ids:
                    continue
                seen_ids.add(sub_id)

                review = self._normalize_public_submission(data, sub_name)
                if review is not None:
                    out.append(review)

                permalink = data.get("permalink")
                if permalink and self.comment_limit_per_post > 0:
                    out.extend(self._fetch_public_comments(permalink, sub_name, data.get("id", "")))

                if len(out) >= self.max_records:
                    return out
            time.sleep(self.POLITE_DELAY_SECONDS)
        return out

    def _fetch_public_comments(self, permalink: str, subreddit_name: str, submission_id: str) -> List[RawReview]:
        reviews: List[RawReview] = []
        try:
            payload = self._public_get(f"{permalink.rstrip('/')}.json", params={"limit": self.comment_limit_per_post})
        except Exception as exc:
            logger.debug("[reddit] public comments failed {p}: {e}", p=permalink, e=exc)
            return reviews

        if not isinstance(payload, list) or len(payload) < 2:
            return reviews

        for child in ((payload[1].get("data") or {}).get("children") or [])[: self.comment_limit_per_post]:
            if child.get("kind") != "t1":
                continue
            d = child.get("data") or {}
            body = (d.get("body") or "").strip()
            if not body or body in {"[deleted]", "[removed]"}:
                continue
            created = datetime.fromtimestamp(d.get("created_utc") or 0, tz=timezone.utc)
            try:
                reviews.append(
                    RawReview(
                        review_id=RawReview.make_id(self.source, f"cmt_{d.get('id')}"),
                        source=self.source,
                        source_region=None,
                        text=body,
                        title=None,
                        rating=None,
                        lang=None,
                        author=d.get("author"),
                        created_at=created,
                        url=f"https://reddit.com{d.get('permalink', '')}",
                        source_meta={
                            "kind": "comment",
                            "subreddit": subreddit_name,
                            "parent_submission_id": submission_id,
                            "score": d.get("score"),
                            "auth": "public_json",
                        },
                    )
                )
            except Exception as exc:
                logger.debug("[reddit] skipped public comment: {e}", e=exc)
        time.sleep(self.POLITE_DELAY_SECONDS)
        return reviews

    def _rss_get(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        """Fetch an RSS feed with a fresh session + rotated browser UA.

        Returns the XML text on 200, or None on any failure. Reddit's WAF
        appears to fingerprint by cookie + UA; a fresh session per request
        sidesteps that.
        """
        session = requests.Session()
        ua = random.choice(_BROWSER_USER_AGENTS)
        session.headers.update(
            {
                "User-Agent": ua,
                "Accept": "application/atom+xml,application/xml,text/xml,*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
        )
        try:
            resp = session.get(url, params=params, timeout=settings.request_timeout_seconds)
        except requests.RequestException as exc:
            logger.debug("[reddit-rss] {u} request error: {e}", u=url, e=exc)
            return None
        finally:
            session.close()

        if resp.status_code == 200 and resp.text and resp.text.strip().startswith("<"):
            return resp.text
        logger.debug("[reddit-rss] {u} -> {s}", u=url, s=resp.status_code)
        return None

    def _fetch_via_rss(self) -> List[RawReview]:
        """Pull from multiple sort surfaces per subreddit for max coverage.

        For each subreddit we try, in order:
            old.reddit.com   -> www.reddit.com    -> api.reddit.com
        for sort surfaces in `RSS_SORT_SURFACES`. Fresh session per request,
        rotated UA, jittered cool-down.

        Incremental save: after each subreddit completes, the partial result
        for that subreddit is written to a per-sub checkpoint parquet so
        progress survives a Ctrl-C or WAF block on the next subreddit.
        """
        try:
            from xml.etree import ElementTree as ET
        except ImportError:
            return []

        out: List[RawReview] = []
        seen_ids: set[str] = set()

        for sub_idx, sub_name in enumerate(self.subreddits):
            sub_added = 0
            sub_reviews: List[RawReview] = []

            for sort, params in self.RSS_SORT_SURFACES:
                xml_text: Optional[str] = None
                for base in self.PUBLIC_BASES:
                    url = f"{base}/r/{sub_name}/{sort}/.rss"
                    xml_text = self._rss_get(url, params={**params, "limit": 100})
                    if xml_text:
                        break

                if not xml_text:
                    logger.debug(
                        "[reddit-rss] r/{s}/{sort} unavailable across all bases",
                        s=sub_name,
                        sort=sort,
                    )
                    time.sleep(self.SURFACE_DELAY_SECONDS + random.uniform(0, 1.5))
                    continue

                try:
                    root = ET.fromstring(xml_text)
                except ET.ParseError as exc:
                    logger.warning("[reddit-rss] parse error r/{s}/{sort}: {e}", s=sub_name, sort=sort, e=exc)
                    continue

                ns = {"atom": "http://www.w3.org/2005/Atom"}
                entries = root.findall("atom:entry", ns)
                surface_added = 0

                for entry in entries:
                    review = self._normalize_rss_entry(entry, ns, sub_name, sort=sort)
                    if review is None:
                        continue
                    if review.review_id in seen_ids:
                        continue
                    seen_ids.add(review.review_id)
                    out.append(review)
                    sub_reviews.append(review)
                    sub_added += 1
                    surface_added += 1
                    if len(out) >= self.max_records:
                        logger.info(
                            "[reddit-rss] cap reached at r/{s}/{sort} (+{a})",
                            s=sub_name, sort=sort, a=surface_added,
                        )
                        self._checkpoint(sub_name, sub_reviews)
                        return out

                logger.info(
                    "[reddit-rss] r/{s}/{sort}: +{a} new (total this sub: {t})",
                    s=sub_name, sort=sort, a=surface_added, t=sub_added,
                )
                time.sleep(self.SURFACE_DELAY_SECONDS + random.uniform(0, 1.5))

            self._checkpoint(sub_name, sub_reviews)
            logger.info("[reddit-rss] r/{s} done: {n} unique submissions", s=sub_name, n=sub_added)

            if sub_idx < len(self.subreddits) - 1:
                cooldown = self.SUBREDDIT_COOLDOWN_SECONDS + random.uniform(0, 1.5)
                logger.debug("[reddit-rss] cooldown {c:.1f}s before next subreddit", c=cooldown)
                time.sleep(cooldown)

        return out

    def _checkpoint(self, sub_name: str, reviews: List[RawReview]) -> None:
        """Write partial per-subreddit progress to disk immediately.

        Survives Ctrl-C / WAF blocks on subsequent subreddits. Files land
        under: data/raw/reddit/checkpoints/<date>/<sub>.jsonl
        """
        if not reviews:
            return
        try:
            import json
            from datetime import datetime as _dt

            ckpt_dir = settings.raw_data_dir / "reddit" / "checkpoints" / _dt.utcnow().strftime("%Y-%m-%d")
            ckpt_dir.mkdir(parents=True, exist_ok=True)
            path = ckpt_dir / f"{sub_name}.jsonl"
            with path.open("a", encoding="utf-8") as f:
                for r in reviews:
                    f.write(json.dumps(r.model_dump(mode="json"), ensure_ascii=False, default=str) + "\n")
            logger.debug("[reddit-rss] checkpointed r/{s}: +{n} -> {p}", s=sub_name, n=len(reviews), p=path)
        except Exception as exc:
            logger.warning("[reddit-rss] checkpoint failed for r/{s}: {e}", s=sub_name, e=exc)

    def _normalize_rss_entry(
        self, entry, ns, subreddit_name: str, sort: str = "new"
    ) -> Optional[RawReview]:
        import re

        def _text(tag: str) -> Optional[str]:
            el = entry.find(f"atom:{tag}", ns)
            return el.text if (el is not None and el.text) else None

        title = _text("title") or ""
        summary_el = entry.find("atom:content", ns) or entry.find("atom:summary", ns)
        summary_html = summary_el.text if (summary_el is not None and summary_el.text) else ""
        summary = re.sub(r"<[^>]+>", " ", summary_html)
        summary = re.sub(r"\s+", " ", summary).strip()

        full_text = "\n\n".join(t for t in [title, summary] if t).strip()
        if not full_text:
            return None

        atom_id = _text("id") or ""
        native_id = atom_id.split("/")[-1] or atom_id or f"rss_{abs(hash(full_text)) & 0xFFFFFFFF:x}"

        link_el = entry.find("atom:link", ns)
        url = link_el.get("href") if link_el is not None else None

        updated = _text("updated")
        created = self._parse_iso(updated)

        author_el = entry.find("atom:author/atom:name", ns)
        author = author_el.text if (author_el is not None and author_el.text) else None

        try:
            return RawReview(
                review_id=RawReview.make_id(self.source, f"rss_{native_id}"),
                source=self.source,
                source_region=None,
                text=full_text,
                title=title or None,
                rating=None,
                lang=None,
                author=author,
                created_at=created,
                url=url,
                source_meta={
                    "kind": "submission",
                    "subreddit": subreddit_name,
                    "auth": "public_rss",
                    "discovered_via_sort": sort,
                },
            )
        except Exception as exc:
            logger.debug("[reddit-rss] skipped entry: {e}", e=exc)
            return None

    @staticmethod
    def _parse_iso(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _normalize_public_submission(self, d: dict, subreddit_name: str) -> Optional[RawReview]:
        text_parts = [t for t in [d.get("title"), d.get("selftext", "")] if t]
        text = "\n\n".join(text_parts).strip()
        sub_id = d.get("id")
        if not text or not sub_id:
            return None

        created = datetime.fromtimestamp(d.get("created_utc") or 0, tz=timezone.utc)
        try:
            return RawReview(
                review_id=RawReview.make_id(self.source, f"sub_{sub_id}"),
                source=self.source,
                source_region=None,
                text=text,
                title=d.get("title"),
                rating=None,
                lang=None,
                author=d.get("author"),
                created_at=created,
                url=f"https://reddit.com{d.get('permalink', '')}",
                source_meta={
                    "kind": "submission",
                    "subreddit": subreddit_name,
                    "score": d.get("score"),
                    "num_comments": d.get("num_comments"),
                    "upvote_ratio": d.get("upvote_ratio"),
                    "auth": "public_json",
                },
            )
        except Exception as exc:
            logger.debug("[reddit] skipped public submission {id}: {e}", id=sub_id, e=exc)
            return None
