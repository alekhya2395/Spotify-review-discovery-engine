"""Social media connector.

Twitter/X now requires paid API access for review-style collection. As a
free, public alternative we use Mastodon's **public hashtag timeline**
endpoint, which exposes recent public posts without authentication.

Endpoint:  /api/v1/timelines/tag/{tag}?limit=40
Docs:      https://docs.joinmastodon.org/methods/timelines/#tag

Configurable via env:
    MASTODON_INSTANCES   comma-separated, default: mastodon.social,mastodon.world,fosstodon.org
    MASTODON_TAGS        comma-separated, default: spotify,SpotifyWrapped,music,discoverweekly
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import List, Optional

import requests
from loguru import logger

from ..config import settings
from ..schemas import RawReview, SourceType
from ..utils import with_retries
from .base import BaseConnector, ConnectorError


class SocialMediaConnector(BaseConnector):
    """Collect public Mastodon posts mentioning Spotify (no auth required)."""

    source = SourceType.SOCIAL_MEDIA
    POLITE_DELAY_SECONDS = 0.5
    PAGE_SIZE = 40

    def __init__(self, max_records: int | None = None) -> None:
        super().__init__(max_records or settings.max_reviews_per_source)
        self.instances = [
            i.strip().rstrip("/")
            for i in os.getenv(
                "MASTODON_INSTANCES",
                "https://mastodon.social,https://mastodon.world,https://fosstodon.org",
            ).split(",")
            if i.strip()
        ]
        self.tags = [
            t.strip().lstrip("#")
            for t in os.getenv(
                "MASTODON_TAGS",
                "spotify,SpotifyWrapped,music,discoverweekly",
            ).split(",")
            if t.strip()
        ]
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "spotify-review-engine/0.1 (research; respectful)"}
        )

    @with_retries(requests.RequestException)
    def _fetch_tag(self, instance: str, tag: str, limit: int) -> List[dict]:
        url = f"{instance}/api/v1/timelines/tag/{tag}"
        params = {"limit": min(limit, self.PAGE_SIZE)}
        resp = self.session.get(url, params=params, timeout=settings.request_timeout_seconds)
        if resp.status_code == 429:
            raise ConnectorError(f"mastodon throttled at {instance}/{tag}")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        return list(data) if isinstance(data, list) else []

    def _fetch(self) -> List[RawReview]:
        out: List[RawReview] = []
        budget_per_combo = max(
            5, self.max_records // max(1, len(self.instances) * len(self.tags))
        )

        for instance in self.instances:
            for tag in self.tags:
                try:
                    statuses = self._fetch_tag(instance, tag, budget_per_combo)
                except Exception as exc:
                    logger.warning(
                        "[social_media] failed {i} #{t}: {e}", i=instance, t=tag, e=exc
                    )
                    continue

                logger.info(
                    "[social_media] {i} #{t} -> {n} statuses",
                    i=instance,
                    t=tag,
                    n=len(statuses),
                )
                for s in statuses:
                    review = self._normalize(s, tag=tag, instance=instance)
                    if review is not None:
                        out.append(review)
                    if len(out) >= self.max_records:
                        return out
                time.sleep(self.POLITE_DELAY_SECONDS)
        return out

    def _normalize(self, s: dict, tag: str, instance: str) -> Optional[RawReview]:
        text = self._strip_html(s.get("content") or "").strip()
        native_id = str(s.get("id") or "").strip()
        if not text or not native_id:
            return None

        created = self._parse_dt(s.get("created_at"))
        account = s.get("account") or {}
        try:
            return RawReview(
                review_id=RawReview.make_id(self.source, f"mastodon_{instance}_{native_id}"),
                source=self.source,
                source_region=None,
                text=text,
                title=None,
                rating=None,
                lang=s.get("language"),
                author=account.get("acct"),
                created_at=created,
                url=s.get("url"),
                source_meta={
                    "platform": "mastodon",
                    "instance": instance,
                    "discovered_via_tag": tag,
                    "favourites_count": s.get("favourites_count"),
                    "reblogs_count": s.get("reblogs_count"),
                    "replies_count": s.get("replies_count"),
                    "tags": [t.get("name") for t in (s.get("tags") or [])],
                },
            )
        except Exception as exc:
            logger.debug("[social_media] skipped malformed status: {e}", e=exc)
            return None

    @staticmethod
    def _strip_html(html: str) -> str:
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        except Exception:
            return html

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
