"""Explicit Beta 2 to v2 contract projection.

The Beta 2 evaluation path remains unchanged. This module makes the mapping
available to adopters without silently reinterpreting v1 JSON.
"""

from __future__ import annotations

import hashlib

from ardguard.kernel import (
    Fact,
    FactOperationalState,
    GenericFactSet,
    GenericTaskContract,
    Requirement,
)
from ardguard.models import FactSet, FactType, ObservationState, TaskContract, canonical_json


def task_v1_to_v2(task: TaskContract) -> GenericTaskContract:
    requirements: list[Requirement] = []
    if task.required_capabilities:
        requirements.append(
            Requirement(
                "beta2-capability",
                "capability",
                {"required_capabilities": list(task.required_capabilities)},
            )
        )
    if task.evidence.required:
        requirements.append(
            Requirement(
                "beta2-evidence",
                "evidence",
                {
                    "artifact_digest_field": task.evidence.artifact_digest_field,
                    "accepted_predicate_types": list(task.evidence.accepted_predicate_types),
                    "trusted_signers": list(task.evidence.trusted_signers),
                },
            )
        )
    if task.authority.required:
        requirements.append(
            Requirement(
                "beta2-authority",
                "authority",
                {
                    "required_permissions": list(task.authority.required_permissions),
                    "maximum_permissions": list(task.authority.maximum_permissions),
                },
            )
        )
    return GenericTaskContract(
        task.task_id, tuple(requirements), task.operation, {"migrated_from": "v1"}
    )


def facts_v1_to_v2(facts: FactSet) -> GenericFactSet:
    state_map = {
        ObservationState.AVAILABLE: FactOperationalState.AVAILABLE,
        ObservationState.UNAVAILABLE: FactOperationalState.UNAVAILABLE,
        ObservationState.INDETERMINATE: FactOperationalState.INDETERMINATE,
        ObservationState.OPERATIONAL_ERROR: FactOperationalState.OPERATIONAL_ERROR,
    }
    converted = []
    for index, observation in enumerate(facts.observations, start=1):
        fact_type = {
            FactType.CAPABILITY: "capability",
            FactType.EVIDENCE: "evidence",
            FactType.AUTHORITY: "authority",
        }[observation.fact_type]
        converted.append(
            Fact(
                f"beta2:{index}:{observation.candidate_id}:{fact_type}",
                observation.candidate_id,
                fact_type,
                observation.provider.provider_id,
                observation.provider.version,
                state_map[observation.state],
                dict(observation.payload)
                if observation.state is ObservationState.AVAILABLE
                else None,
                (
                    dict(observation.provenance)
                    if observation.state is ObservationState.AVAILABLE
                    else {
                        "diagnostic_sha256": hashlib.sha256(
                            canonical_json(dict(observation.provenance))
                        ).hexdigest(),
                        "provider_status": observation.state.value.lower(),
                    }
                ),
                extensions=(
                    {"migrated_from": "ardguard.dev/fact-set/v1"}
                    if observation.state is ObservationState.AVAILABLE
                    else {}
                ),
            )
        )
    return GenericFactSet(tuple(converted))
