"""Base class shared by all source connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from loguru import logger

from ..schemas import RawReview, SourceType


class ConnectorError(Exception):
    """Raised when a connector cannot fetch data after retries."""


class BaseConnector(ABC):
    """Abstract base. Subclasses implement `_fetch` and declare a `source`.

    The pipeline calls `collect()`, which wraps `_fetch` with logging and a
    safety cap on the number of records returned.
    """

    source: SourceType

    def __init__(self, max_records: int) -> None:
        if max_records < 1:
            raise ValueError("max_records must be >= 1")
        self.max_records = max_records

    @abstractmethod
    def _fetch(self) -> List[RawReview]:
        """Fetch and return normalized reviews. Must respect `self.max_records`."""

    def collect(self) -> List[RawReview]:
        logger.info("[{src}] starting collection (cap={cap})", src=self.source.value, cap=self.max_records)
        try:
            reviews = self._fetch()
        except ConnectorError:
            raise
        except Exception as exc:
            logger.exception("[{src}] unhandled error during fetch", src=self.source.value)
            raise ConnectorError(str(exc)) from exc

        capped = reviews[: self.max_records]
        if len(reviews) > self.max_records:
            logger.warning(
                "[{src}] truncated {n} -> {cap} (raise MAX_REVIEWS_PER_SOURCE to keep more)",
                src=self.source.value,
                n=len(reviews),
                cap=self.max_records,
            )
        logger.info("[{src}] collected {n} reviews", src=self.source.value, n=len(capped))
        return capped
