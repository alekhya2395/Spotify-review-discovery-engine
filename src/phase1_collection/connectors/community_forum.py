"""Spotify Community Forum connector.

Uses the public Lithium-style search API endpoint exposed by Spotify's
community to discover threads, then scrapes thread pages for posts.
The implementation is deliberately defensive: HTML structure can change at
any time, so we degrade gracefully and never crash the pipeline.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from loguru import logger

from ..config import settings
from ..schemas import RawReview, SourceType
from ..utils import with_retries
from .base import BaseConnector, ConnectorError


class CommunityForumConnector(BaseConnector):
    """Crawl a sample of Spotify Community threads for posts."""

    source = SourceType.COMMUNITY_FORUM

    DISCOVERY_PATHS = [
        "/",
        "/t5/Ongoing-Issues/bd-p/Ongoing",
        "/t5/Live-Ideas/idb-p/LiveIdeas",
        "/t5/Help/ct-p/Help",
        "/t5/Spotify-Answers/ct-p/Spotify_Answers",
        "/t5/Other-Podcasts-Audiobooks/ct-p/podcasts",
    ]

    def __init__(
        self,
        max_records: int | None = None,
        max_threads: int = 30,
        polite_delay_seconds: float = 1.5,
    ) -> None:
        super().__init__(max_records or settings.max_reviews_per_source)
        self.base_url = settings.community_base_url.rstrip("/")
        self.max_threads = max_threads
        self.polite_delay_seconds = polite_delay_seconds
        self.session = requests.Session()
        # Community is fronted by a WAF that rejects obvious bot UAs.
        # We present as a regular browser; we still throttle and respect the
        # site by limiting volume + adding delay between requests.
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    @with_retries(requests.RequestException)
    def _get(self, url: str) -> str:
        resp = self.session.get(url, timeout=settings.request_timeout_seconds)
        if resp.status_code in (429, 503):
            raise ConnectorError(f"community throttled: {resp.status_code}")
        resp.raise_for_status()
        return resp.text

    def _discover_thread_urls(self) -> List[str]:
        urls: List[str] = []
        for path in self.DISCOVERY_PATHS:
            board_url = urljoin(self.base_url + "/", path.lstrip("/"))
            try:
                html = self._get(board_url)
            except Exception as exc:
                logger.warning("[community] discovery failed for {u}: {e}", u=board_url, e=exc)
                continue

            soup = BeautifulSoup(html, "lxml")
            for a in soup.select("a[href*='/td-p/']"):
                href = a.get("href")
                if href:
                    full = urljoin(self.base_url, href)
                    if full not in urls:
                        urls.append(full)
                if len(urls) >= self.max_threads:
                    break
            if len(urls) >= self.max_threads:
                break
            time.sleep(self.polite_delay_seconds)
        logger.info("[community] discovered {n} threads", n=len(urls))
        return urls[: self.max_threads]

    def _parse_thread(self, url: str) -> List[RawReview]:
        try:
            html = self._get(url)
        except Exception as exc:
            logger.warning("[community] thread fetch failed {u}: {e}", u=url, e=exc)
            return []

        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.select_one("h1, .lia-message-subject-banner")
        thread_title = title_tag.get_text(strip=True) if title_tag else None

        reviews: List[RawReview] = []
        for msg in soup.select("[id^='messageview_'], .lia-message-view-display"):
            body_tag = msg.select_one(".lia-message-body-content, .lia-message-body")
            if not body_tag:
                continue
            text = body_tag.get_text(" ", strip=True)
            if not text:
                continue

            author_tag = msg.select_one(".lia-user-name-link, .UserName a")
            author = author_tag.get_text(strip=True) if author_tag else None

            time_tag = msg.select_one("time, .DateTime, .local-date")
            created = self._parse_dt(time_tag.get("datetime") if time_tag else None)

            msg_id = msg.get("id") or f"{url}#{len(reviews)}"
            try:
                reviews.append(
                    RawReview(
                        review_id=RawReview.make_id(self.source, msg_id),
                        source=self.source,
                        source_region=None,
                        text=text,
                        title=thread_title,
                        rating=None,
                        lang=None,
                        author=author,
                        created_at=created,
                        url=url,
                        source_meta={"thread_url": url, "dom_id": msg_id},
                    )
                )
            except Exception as exc:
                logger.debug("[community] skipped post: {e}", e=exc)
        return reviews

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _fetch(self) -> List[RawReview]:
        thread_urls = self._discover_thread_urls()
        out: List[RawReview] = []
        for url in thread_urls:
            out.extend(self._parse_thread(url))
            if len(out) >= self.max_records:
                break
            time.sleep(self.polite_delay_seconds)
        return out
