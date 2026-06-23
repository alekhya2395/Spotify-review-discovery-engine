"""Google Play Store connector (uses `google-play-scraper`)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from loguru import logger

from ..config import settings
from ..schemas import RawReview, SourceType
from ..utils import with_retries
from .base import BaseConnector, ConnectorError

try:
    from google_play_scraper import Sort, reviews as gps_reviews
except ImportError:
    gps_reviews = None
    Sort = None


class PlayStoreConnector(BaseConnector):
    """Pull Spotify Android reviews across configured countries/languages."""

    source = SourceType.PLAY_STORE

    def __init__(self, max_records: int | None = None) -> None:
        super().__init__(max_records or settings.max_reviews_per_source)
        self.app_id = settings.spotify_play_store_id
        self.countries = settings.play_store_country_list
        self.languages = settings.play_store_lang_list

    @with_retries(Exception)
    def _fetch_one(self, lang: str, country: str, count: int):
        if gps_reviews is None or Sort is None:
            raise ConnectorError("google-play-scraper is not installed")
        return gps_reviews(
            self.app_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=count,
        )

    def _fetch(self) -> List[RawReview]:
        if gps_reviews is None:
            raise ConnectorError("google-play-scraper is not installed; `pip install google-play-scraper`")

        per_locale = max(1, self.max_records // max(1, len(self.countries) * len(self.languages)))
        out: List[RawReview] = []

        for lang in self.languages:
            for country in self.countries:
                try:
                    result, _ = self._fetch_one(lang=lang, country=country, count=per_locale)
                except Exception as exc:
                    logger.error("[play_store] failed lang={l} country={c}: {e}", l=lang, c=country, e=exc)
                    continue

                logger.info(
                    "[play_store] fetched {n} reviews lang={l} country={c}",
                    n=len(result),
                    l=lang,
                    c=country,
                )
                for r in result:
                    review = self._normalize(r, lang=lang, country=country)
                    if review is not None:
                        out.append(review)
        return out

    def _normalize(self, r: dict, lang: str, country: str) -> RawReview | None:
        text = (r.get("content") or "").strip()
        native_id = str(r.get("reviewId") or "").strip()
        if not text or not native_id:
            return None

        created = r.get("at")
        if isinstance(created, datetime) and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        score = r.get("score")
        try:
            return RawReview(
                review_id=RawReview.make_id(self.source, native_id),
                source=self.source,
                source_region=country,
                text=text,
                rating=float(score) if score is not None else None,
                lang=lang,
                author=r.get("userName"),
                created_at=created,
                url=None,
                source_meta={
                    "thumbs_up": r.get("thumbsUpCount"),
                    "review_created_version": r.get("reviewCreatedVersion"),
                    "reply_content": r.get("replyContent"),
                    "replied_at": str(r.get("repliedAt")) if r.get("repliedAt") else None,
                },
            )
        except Exception as exc:
            logger.debug("[play_store] skipped malformed review: {e}", e=exc)
            return None
