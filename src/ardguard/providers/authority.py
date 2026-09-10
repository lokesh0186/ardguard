"""Authority-provider helpers.

Least authority is an operator-defined profile, not an ARD requirement.
"""

from __future__ import annotations

from ardguard.models import Observation, ObservationState


def authority_is_available(observation: Observation) -> bool:
    return observation.state is ObservationState.AVAILABLE
