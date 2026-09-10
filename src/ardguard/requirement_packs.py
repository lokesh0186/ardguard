"""Bounded evaluators for optional eligibility requirement packs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ardguard.kernel import (
    Fact,
    FactOperationalState,
    Requirement,
    RequirementStatus,
    RequirementVerdict,
)

MAX_DEPENDENCY_DEPTH = 32


def evaluate_dependency_graph(
    requirement: Requirement, facts: tuple[Fact, ...], context: Mapping[str, Any]
) -> RequirementVerdict:
    """Evaluate supplied dependency facts with bounded depth and cycle detection."""

    del context
    matches = tuple(item for item in facts if item.fact_type == requirement.requirement_type)
    if any(item.state is FactOperationalState.OPERATIONAL_ERROR for item in matches):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.ERROR,
            "dependency.provider_operational_error",
            tuple(item.fact_id for item in matches),
        )
    available = tuple(item for item in matches if item.state is FactOperationalState.AVAILABLE)
    if not available:
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.INDETERMINATE,
            "dependency.facts_unavailable",
        )
    root = requirement.parameters.get("root")
    max_depth = requirement.parameters.get("max_depth", 4)
    if (
        not isinstance(root, str)
        or isinstance(max_depth, bool)
        or not isinstance(max_depth, int)
        or not 1 <= max_depth <= MAX_DEPENDENCY_DEPTH
    ):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.ERROR,
            "dependency.invalid_requirement",
        )
    nodes: dict[str, Mapping[str, Any]] = {}
    for fact in available:
        if not isinstance(fact.value, Mapping):
            return RequirementVerdict(
                requirement.requirement_id,
                RequirementStatus.ERROR,
                "dependency.invalid_fact",
                (fact.fact_id,),
            )
        identifier = fact.value.get("identifier")
        if not isinstance(identifier, str) or identifier in nodes:
            return RequirementVerdict(
                requirement.requirement_id,
                RequirementStatus.ERROR,
                "dependency.duplicate_or_invalid_identifier",
                tuple(item.fact_id for item in available),
            )
        nodes[identifier] = fact.value

    def walk(  # noqa: PLR0911 - closed recursive state machine
        identifier: str, depth: int, active: frozenset[str]
    ) -> RequirementStatus:
        if depth > max_depth or identifier in active:
            return RequirementStatus.ERROR
        node = nodes.get(identifier)
        if node is None:
            return RequirementStatus.INDETERMINATE
        if node.get("available") is not True or node.get("verified_usable") is not True:
            return RequirementStatus.UNSATISFIED
        dependencies = node.get("dependencies", ())
        if not isinstance(dependencies, Sequence) or isinstance(dependencies, (str, bytes)):
            return RequirementStatus.ERROR
        child_states = [
            walk(child, depth + 1, active | {identifier})
            for child in dependencies
            if isinstance(child, str)
        ]
        if len(child_states) != len(dependencies):
            return RequirementStatus.ERROR
        for status in (
            RequirementStatus.ERROR,
            RequirementStatus.UNSATISFIED,
            RequirementStatus.INDETERMINATE,
        ):
            if status in child_states:
                return status
        return RequirementStatus.SATISFIED

    status = walk(root, 1, frozenset())
    return RequirementVerdict(
        requirement.requirement_id,
        status,
        {
            RequirementStatus.SATISFIED: "dependency.satisfied",
            RequirementStatus.UNSATISFIED: "dependency.unavailable_or_ineligible",
            RequirementStatus.INDETERMINATE: "dependency.missing",
            RequirementStatus.ERROR: "dependency.cycle_or_depth_error",
        }[status],
        tuple(item.fact_id for item in available),
    )


PACK_REQUIREMENT_TYPES: Mapping[str, tuple[str, ...]] = {
    "publisher-identity": ("identity.publisher_binding",),
    "access-feasibility": (
        "access.authentication_mechanism",
        "access.credential_available",
        "access.anonymous",
        "access.interactive_required",
        "access.tier",
    ),
    "dependency-feasibility": ("dependency.graph",),
    "deployment-compliance": (
        "deployment.environment",
        "deployment.region",
        "deployment.residency",
        "deployment.compliance_assertion",
        "deployment.identity",
    ),
    "version-freshness": (
        "resource.version",
        "resource.updated_at",
        "resource.deprecated",
        "resource.replacement_identifier",
        "evidence.expires_at",
    ),
    "usage-sla": (
        "usage.quota_remaining",
        "usage.request_cost",
        "service.available",
        "service.sla_class",
        "service.degradation_mode",
    ),
    "observed-fitness": (
        "fitness.artifact_digest",
        "fitness.measurement_window",
        "fitness.issuer",
        "fitness.environment",
        "fitness.vantage",
        "fitness.observed_at",
    ),
    "federation-provenance": (
        "federation.canonical_source",
        "federation.observed_source",
        "federation.mirrored",
        "federation.digest_agreement",
        "federation.last_sync",
        "federation.trust_relationship",
    ),
}
