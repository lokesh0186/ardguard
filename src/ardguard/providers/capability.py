"""Capability-provider helpers."""

from __future__ import annotations

from ardguard.models import Observation, ObservationState


def capability_is_available(observation: Observation) -> bool:
    return observation.state is ObservationState.AVAILABLE
