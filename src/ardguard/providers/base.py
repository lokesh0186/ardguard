"""Fact-provider extension contract."""

from __future__ import annotations

from typing import Protocol

from ardguard.models import Candidate, Observation, TaskContract


class FactProvider(Protocol):
    provider_id: str
    version: str

    def observe(
        self, candidates: tuple[Candidate, ...], task: TaskContract
    ) -> tuple[Observation, ...]:
        """Return observations, never final eligibility assertions."""
