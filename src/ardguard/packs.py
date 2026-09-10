"""Small eligibility packs built on the generic requirement kernel."""

from __future__ import annotations

from collections.abc import Mapping

from ardguard.constraints import evaluate_constraint
from ardguard.kernel import (
    EvaluatorRegistry,
    Fact,
    FactOperationalState,
    Requirement,
    RequirementStatus,
    RequirementVerdict,
)
from ardguard.models import canonical_json
from ardguard.requirement_packs import evaluate_dependency_graph


def _available(
    requirement: Requirement, facts: tuple[Fact, ...]
) -> tuple[Fact, ...] | RequirementVerdict:
    matches = tuple(item for item in facts if item.fact_type == requirement.requirement_type)
    if any(item.state is FactOperationalState.OPERATIONAL_ERROR for item in matches):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.ERROR,
            "fact.provider_operational_error",
            tuple(item.fact_id for item in matches),
        )
    available = tuple(item for item in matches if item.state is FactOperationalState.AVAILABLE)
    if not available:
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.INDETERMINATE,
            "fact.missing_or_unavailable",
            tuple(item.fact_id for item in matches),
        )
    return available


def evaluate_capability(
    requirement: Requirement, facts: tuple[Fact, ...], context: Mapping[str, object]
) -> RequirementVerdict:
    del context
    available = _available(requirement, facts)
    if isinstance(available, RequirementVerdict):
        return available
    required = requirement.parameters.get("required_capabilities")
    if not isinstance(required, tuple) or any(not isinstance(item, str) for item in required):
        return RequirementVerdict(
            requirement.requirement_id, RequirementStatus.ERROR, "capability.invalid_requirement"
        )
    results: list[bool] = []
    for fact in available:
        value = fact.value
        if isinstance(value, Mapping):
            value = value.get("verified_capabilities")
        if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
            return RequirementVerdict(
                requirement.requirement_id,
                RequirementStatus.ERROR,
                "capability.invalid_fact",
                (fact.fact_id,),
            )
        results.append(set(required).issubset(value))
    if all(results):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.SATISFIED,
            "capability.verified",
            tuple(item.fact_id for item in available),
        )
    if any(results):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.INDETERMINATE,
            "capability.conflicting_facts",
            tuple(item.fact_id for item in available),
        )
    return RequirementVerdict(
        requirement.requirement_id,
        RequirementStatus.UNSATISFIED,
        "capability.mismatch",
        tuple(item.fact_id for item in available),
    )


def evaluate_authority(
    requirement: Requirement, facts: tuple[Fact, ...], context: Mapping[str, object]
) -> RequirementVerdict:
    del context
    available = _available(requirement, facts)
    if isinstance(available, RequirementVerdict):
        return available
    required = requirement.parameters.get("required_permissions")
    maximum = requirement.parameters.get("maximum_permissions")
    if not isinstance(required, tuple) or not isinstance(maximum, tuple):
        return RequirementVerdict(
            requirement.requirement_id, RequirementStatus.ERROR, "authority.invalid_requirement"
        )
    results: list[bool] = []
    for fact in available:
        value = fact.value
        if isinstance(value, Mapping):
            value = value.get("granted_permissions")
        if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
            return RequirementVerdict(
                requirement.requirement_id,
                RequirementStatus.ERROR,
                "authority.invalid_fact",
                (fact.fact_id,),
            )
        granted = set(value)
        results.append(set(required).issubset(granted) and granted.issubset(maximum))
    if all(results):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.SATISFIED,
            "authority.within_policy",
            tuple(item.fact_id for item in available),
        )
    if any(results):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.INDETERMINATE,
            "authority.conflicting_facts",
            tuple(item.fact_id for item in available),
        )
    return RequirementVerdict(
        requirement.requirement_id,
        RequirementStatus.UNSATISFIED,
        "authority.excessive_or_insufficient",
        tuple(item.fact_id for item in available),
    )


def evaluate_evidence(
    requirement: Requirement, facts: tuple[Fact, ...], context: Mapping[str, object]
) -> RequirementVerdict:
    available = _available(requirement, facts)
    if isinstance(available, RequirementVerdict):
        return available
    evidence_identities = {
        item.evidence_identity for item in available if item.evidence_identity is not None
    }
    for identity in evidence_identities:
        rows = tuple(item for item in available if item.evidence_identity == identity)
        if len({canonical_json(item.value) for item in rows}) > 1:
            return RequirementVerdict(
                requirement.requirement_id,
                RequirementStatus.INDETERMINATE,
                "evidence.conflicting_facts",
                tuple(item.fact_id for item in rows),
            )
    candidate_id = context.get("candidate_id")
    candidate_digest = context.get("candidate_artifact_sha256")
    predicates = set(requirement.parameters.get("accepted_predicate_types", ()))
    trusted = set(requirement.parameters.get("trusted_signers", ()))
    for fact in available:
        if not isinstance(fact.value, Mapping):
            continue
        value = fact.value
        if value.get("authentic") is not True or value.get("trust_valid") is not True:
            continue
        if candidate_id is not None and value.get("resource_id") != candidate_id:
            continue
        if candidate_digest is not None and (
            value.get("artifact_sha256") != candidate_digest
            or candidate_digest not in set(value.get("subject_sha256", ()))
        ):
            continue
        if trusted and value.get("signer_identity") not in trusted:
            continue
        if not predicates.issubset(set(value.get("predicate_types", ()))):
            continue
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.SATISFIED,
            "evidence.applicable",
            (fact.fact_id,),
        )
    return RequirementVerdict(
        requirement.requirement_id,
        RequirementStatus.UNSATISFIED,
        "evidence.invalid_or_not_applicable",
        tuple(item.fact_id for item in available),
    )


def evaluate_evidence_bundle(
    requirement: Requirement, facts: tuple[Fact, ...], context: Mapping[str, object]
) -> RequirementVerdict:
    """Compose separate authenticity, applicability, and availability facts."""

    expected_types = {
        "evidence.envelope_authentic",
        "evidence.signer_identity",
        "evidence.statement_integrity",
        "evidence.predicate_type",
        "evidence.subject_digest",
        "evidence.resource_association",
        "evidence.verifier_available",
    }
    matching = tuple(item for item in facts if item.fact_type in expected_types)
    if any(item.state is FactOperationalState.OPERATIONAL_ERROR for item in matching):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.ERROR,
            "evidence.verifier_operational_error",
            tuple(item.fact_id for item in matching),
        )
    available = tuple(
        item for item in matching if item.state is FactOperationalState.AVAILABLE
    )
    grouped = {
        fact_type: tuple(item for item in available if item.fact_type == fact_type)
        for fact_type in expected_types
    }
    conflicting = tuple(
        item
        for rows in grouped.values()
        if len({canonical_json(item.value) for item in rows}) > 1
        for item in rows
    )
    if conflicting:
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.INDETERMINATE,
            "evidence.conflicting_facts",
            tuple(item.fact_id for item in conflicting),
        )
    by_type = {fact_type: rows[0] for fact_type, rows in grouped.items() if rows}
    if not expected_types.issubset(by_type):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.INDETERMINATE,
            "evidence.required_fact_unavailable",
            tuple(item.fact_id for item in matching),
        )
    if by_type["evidence.verifier_available"].value is not True:
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.INDETERMINATE,
            "evidence.verifier_unavailable",
            tuple(item.fact_id for item in matching),
        )
    candidate_id = context.get("candidate_id")
    candidate_digest = context.get("candidate_artifact_sha256")
    trusted = set(requirement.parameters.get("trusted_signers", ()))
    predicates = set(requirement.parameters.get("accepted_predicate_types", ()))
    checks = (
        by_type["evidence.envelope_authentic"].value is True,
        by_type["evidence.statement_integrity"].value is True,
        candidate_digest is not None
        and by_type["evidence.subject_digest"].value == candidate_digest,
        candidate_id is not None and by_type["evidence.resource_association"].value == candidate_id,
        not trusted or by_type["evidence.signer_identity"].value in trusted,
        not predicates or by_type["evidence.predicate_type"].value in predicates,
    )
    status = RequirementStatus.SATISFIED if all(checks) else RequirementStatus.UNSATISFIED
    return RequirementVerdict(
        requirement.requirement_id,
        status,
        "evidence.applicable"
        if status is RequirementStatus.SATISFIED
        else "evidence.invalid_or_not_applicable",
        tuple(item.fact_id for item in matching),
    )


def builtin_evaluators(extra_requirement_types: tuple[str, ...] = ()) -> EvaluatorRegistry:
    registry = EvaluatorRegistry()
    registry.register("capability", evaluate_capability)
    registry.register("evidence", evaluate_evidence)
    registry.register("evidence.applicable", evaluate_evidence_bundle)
    registry.register("authority", evaluate_authority)
    registry.register("dependency.graph", evaluate_dependency_graph)
    for requirement_type in sorted(
        set(extra_requirement_types)
        - {"capability", "evidence", "evidence.applicable", "authority", "dependency.graph"}
    ):
        registry.register(requirement_type, evaluate_constraint)
    return registry


POLICY_PACKS: Mapping[str, tuple[str, ...]] = {
    "basic-capability": ("capability",),
    "artifact-evidence": ("evidence",),
    "least-authority": ("authority",),
    "verified-resource": ("capability", "evidence", "authority"),
    "enterprise-basic": (
        "capability",
        "evidence",
        "authority",
        "identity.publisher_binding",
        "access.credential_available",
        "deployment.region",
    ),
}
