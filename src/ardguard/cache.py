"""Identity-bound fact cache with explicit age and invalidation controls."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Mapping
from dataclasses import dataclass

from ardguard.kernel import Fact, Requirement
from ardguard.models import Candidate, canonical_json


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class CacheKey:
    candidate_sha256: str
    requirement_sha256: str
    provider_identity: str
    input_identity: str
    policy_context_sha256: str

    @classmethod
    def create(  # noqa: PLR0913 - every cache-binding identity is explicit
        cls,
        *,
        candidate: Candidate,
        requirement: Requirement,
        provider_id: str,
        provider_version: str,
        input_identity: str,
        policy_context: object,
    ) -> CacheKey:
        candidate_body = {
            "resource_id": candidate.resource_id,
            "source": candidate.source,
            "rank": candidate.rank,
            "score": candidate.score,
            "original": _plain(candidate.original),
        }
        return cls(
            hashlib.sha256(canonical_json(candidate_body)).hexdigest(),
            hashlib.sha256(canonical_json(requirement.to_dict())).hexdigest(),
            f"{provider_id}@{provider_version}",
            input_identity,
            hashlib.sha256(canonical_json(policy_context)).hexdigest(),
        )


@dataclass(frozen=True)
class CacheLookup:
    fact: Fact | None
    reason: str


class FactCache:
    """Small in-memory cache. It never broadens eligibility or performs I/O."""

    def __init__(self) -> None:
        self._values: dict[CacheKey, tuple[float, Fact]] = {}

    def put(self, key: CacheKey, fact: Fact, *, now: float | None = None) -> None:
        self._values[key] = (time.time() if now is None else now, fact)

    def get(
        self, key: CacheKey, *, max_age_seconds: float, now: float | None = None
    ) -> CacheLookup:
        row = self._values.get(key)
        if row is None:
            return CacheLookup(None, "cache.miss")
        timestamp, fact = row
        current = time.time() if now is None else now
        if max_age_seconds < 0 or current < timestamp or current - timestamp > max_age_seconds:
            return CacheLookup(None, "cache.stale")
        return CacheLookup(fact, "cache.hit")

    def invalidate(self, key: CacheKey | None = None) -> int:
        if key is None:
            count = len(self._values)
            self._values.clear()
            return count
        return int(self._values.pop(key, None) is not None)
