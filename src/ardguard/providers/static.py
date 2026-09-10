"""Explicit trusted-input provider for offline use and deterministic tests."""

from __future__ import annotations

from dataclasses import dataclass

from ardguard.models import Candidate, FactSet, Observation, TaskContract


@dataclass(frozen=True)
class StaticFactProvider:
    fact_set: FactSet
    provider_id: str = "ardguard.static"
    version: str = "1"

    def observe(
        self, candidates: tuple[Candidate, ...], task: TaskContract
    ) -> tuple[Observation, ...]:
        del candidates, task
        return self.fact_set.observations
