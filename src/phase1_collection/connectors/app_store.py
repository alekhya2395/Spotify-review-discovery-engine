"""Apple App Store connector.

Uses Apple's **public iTunes RSS customer reviews feed**:
    https://itunes.apple.com/<country>/rss/customerreviews/id=<appId>/page=<n>/sortBy=mostRecent/json

The RSS feed is the official, documented way to retrieve App Store reviews
without authentication. Apple caps it at ~10 pages × 50 entries per country.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import List, Optional

import requests
from loguru import logger

from ..config import settings
from ..schemas import RawReview, SourceType
from ..utils import with_retries
from .base import BaseConnector, ConnectorError


class AppStoreConnector(BaseConnector):
    """Pull Spotify iOS reviews via Apple's iTunes RSS feed."""

    source = SourceType.APP_STORE
    MAX_PAGES = 10
    POLITE_DELAY_SECONDS = 0.5

    def __init__(self, max_records: int | None = None) -> None:
        super().__init__(max_records or settings.max_reviews_per_source)
        self.app_id = settings.spotify_app_store_id
        self.countries = settings.app_store_country_list
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "spotify-review-engine/0.1 (research)"}
        )

    def _feed_url(self, country: str, page: int) -> str:
        return (
            f"https://itunes.apple.com/{country}/rss/customerreviews/"
            f"id={self.app_id}/page={page}/sortBy=mostRecent/json"
        )

    @with_retries(requests.RequestException)
    def _fetch_page(self, country: str, page: int) -> List[dict]:
        url = self._feed_url(country, page)
        resp = self.session.get(url, timeout=settings.request_timeout_seconds)
        if resp.status_code == 429:
            raise ConnectorError(f"app store throttled (country={country}, page={page})")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        try:
            payload = resp.json() or {}
        except ValueError:
            return []
        feed = payload.get("feed") or {}
        entries = feed.get("entry") or []
        if isinstance(entries, dict):
            entries = [entries]
        return [e for e in entries if "im:rating" in e]

    def _fetch_country(self, country: str, target_per_country: int) -> List[dict]:
        out: List[dict] = []
        for page in range(1, self.MAX_PAGES + 1):
            try:
                entries = self._fetch_page(country, page)
            except Exception as exc:
                logger.warning(
                    "[app_store] page fetch failed country={c} page={p}: {e}",
                    c=country, p=page, e=exc,
                )
                break
            if not entries:
                break
            out.extend(entries)
            if len(out) >= target_per_country:
                break
            time.sleep(self.POLITE_DELAY_SECONDS)
        return out

    def _fetch(self) -> List[RawReview]:
        per_country = max(1, self.max_records // max(1, len(self.countries)))
        out: List[RawReview] = []

        for country in self.countries:
            try:
                entries = self._fetch_country(country, per_country)
            except Exception as exc:
                logger.error("[app_store] failed country={c}: {e}", c=country, e=exc)
                continue

            logger.info("[app_store] fetched {n} reviews country={c}", n=len(entries), c=country)
            for entry in entries:
                review = self._normalize(entry, country=country)
                if review is not None:
                    out.append(review)
        return out

    def _normalize(self, e: dict, country: str) -> Optional[RawReview]:
        text = self._label(e.get("content"))
        if not text:
            return None

        native_id = self._label(e.get("id"))
        if not native_id:
            return None

        rating_str = self._label(e.get("im:rating"))
        try:
            rating = float(rating_str) if rating_str else None
        except ValueError:
            rating = None

        created = self._parse_dt(self._label(e.get("updated")))

        title = self._label(e.get("title"))
        author_obj = e.get("author") or {}
        author = self._label((author_obj.get("name") or {}))
        link = e.get("link") or {}
        url = None
        if isinstance(link, dict):
            url = (link.get("attributes") or {}).get("href")
        elif isinstance(link, list) and link:
            url = (link[0].get("attributes") or {}).get("href")

        try:
            return RawReview(
                review_id=RawReview.make_id(self.source, native_id),
                source=self.source,
                source_region=country,
                text=text,
                title=title,
                rating=rating,
                lang=None,
                author=author,
                created_at=created,
                url=url,
                source_meta={
                    "vote_count": self._label(e.get("im:voteCount")),
                    "vote_sum": self._label(e.get("im:voteSum")),
                    "version": self._label(e.get("im:version")),
                },
            )
        except Exception as exc:
            logger.debug("[app_store] skipped malformed entry: {e}", e=exc)
            return None

    @staticmethod
    def _label(node) -> Optional[str]:
        """RSS JSON wraps scalar values in {'label': '...'} objects."""
        if node is None:
            return None
        if isinstance(node, str):
            return node
        if isinstance(node, dict):
            v = node.get("label")
            return v if isinstance(v, str) else None
        return None

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
