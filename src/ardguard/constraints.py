"""Closed, fail-closed constraint primitives for generic requirements."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ardguard.kernel import (
    EvaluatorRegistry,
    Fact,
    FactOperationalState,
    Requirement,
    RequirementStatus,
    RequirementVerdict,
    requirement_fact_types,
)
from ardguard.models import Candidate, ContractError

_CORE_FIELDS = frozenset(
    {
        "identifier",
        "type",
        "url",
        "data",
        "capabilities",
        "version",
        "updatedAt",
        "trustManifest",
        "metadata",
        "@context",
    }
)
_LITERAL_PATH = re.compile(r"^[A-Za-z_@][A-Za-z0-9_@:-]*(\.[A-Za-z_@][A-Za-z0-9_@:-]*){0,7}$")
_SEMVER = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?$"
)


def resolve_candidate_field(candidate: Candidate, path: str) -> Any:
    """Resolve a permitted literal field path without JSONPath execution."""

    if not isinstance(path, str) or _LITERAL_PATH.fullmatch(path) is None:
        raise ContractError("field path must be a permitted literal path")
    parts = path.split(".")
    if parts[0] not in _CORE_FIELDS and ":" not in parts[0]:
        raise ContractError("field path must name a core or namespaced ARD term")
    current: Any = candidate.original
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _semver(value: object) -> tuple[int, int, int, tuple[tuple[int, object], ...]]:
    if not isinstance(value, str):
        raise TypeError("semantic version must be a string")
    match = _SEMVER.fullmatch(value)
    if match is None:
        raise ValueError("unsupported semantic version")
    prerelease: list[tuple[int, object]] = []
    if match.group("pre") is None:
        prerelease.append((1, ""))
    else:
        for part in match.group("pre").split("."):
            prerelease.append((0, int(part)) if part.isdigit() else (0, part))
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        tuple(prerelease),
    )


def _as_set(value: object) -> set[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("value must be an array")
    result = set(value)
    if len(result) != len(value):
        raise ValueError("array contains duplicates")
    return result


def compare(  # noqa: PLR0911,PLR0912 - closed predicate dispatcher
    predicate: str, actual: object, expected: object, *, now: datetime | None = None
) -> bool:
    """Apply one closed primitive and reject incompatible types."""

    if predicate == "equals":
        if type(actual) is not type(expected):
            raise TypeError("equals operands must have the same type")
        return actual == expected
    if predicate == "not_equals":
        if type(actual) is not type(expected):
            raise TypeError("not_equals operands must have the same type")
        return actual != expected
    if predicate == "one_of":
        values = _as_set(expected)
        if any(type(item) is not type(actual) for item in values):
            raise TypeError("one_of operands must have the same type")
        return actual in values
    if predicate in {"subset_of", "scope_subset"}:
        return _as_set(actual).issubset(_as_set(expected))
    if predicate == "contains":
        return expected in _as_set(actual)
    if predicate in {"numeric_min", "numeric_max"}:
        if isinstance(actual, bool) or isinstance(expected, bool):
            raise TypeError("numeric operands cannot be booleans")
        if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
            raise TypeError("numeric operands are required")
        return actual >= expected if predicate == "numeric_min" else actual <= expected
    if predicate in {"semver_min", "semver_max"}:
        return (
            _semver(actual) >= _semver(expected)
            if predicate == "semver_min"
            else _semver(actual) <= _semver(expected)
        )
    if predicate == "fresh_within_seconds":
        if (
            not isinstance(actual, str)
            or isinstance(expected, bool)
            or not isinstance(expected, int)
            or expected < 0
        ):
            raise TypeError("freshness requires an RFC3339 timestamp and non-negative integer")
        observed = datetime.fromisoformat(actual.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("freshness timestamp must include a timezone")
        reference = now or datetime.now(timezone.utc)
        return 0 <= (reference - observed).total_seconds() <= expected
    if predicate in {"digest_equals", "identity_equals"}:
        if not isinstance(actual, str) or not isinstance(expected, str):
            raise TypeError("identity operands must be strings")
        if predicate == "digest_equals" and (
            re.fullmatch(r"[0-9a-f]{64}", actual) is None
            or re.fullmatch(r"[0-9a-f]{64}", expected) is None
        ):
            raise ValueError("digest equality requires lowercase SHA-256 values")
        return actual == expected
    if predicate == "boolean_asserted_with_provenance":
        if not isinstance(actual, bool) or expected is not True:
            raise TypeError("boolean assertion requires actual and expected true booleans")
        return actual
    raise ContractError(f"unsupported predicate: {predicate}")


def evaluate_constraint(  # noqa: PLR0911 - explicit fail-closed verdict paths
    requirement: Requirement, facts: tuple[Fact, ...], context: Mapping[str, Any]
) -> RequirementVerdict:
    """Evaluate a requirement against facts of the same exact type."""

    expected_fact_types = requirement_fact_types(requirement)
    matching = tuple(item for item in facts if item.fact_type in expected_fact_types)
    if not matching:
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.INDETERMINATE,
            "fact.missing",
        )
    if any(item.state is FactOperationalState.OPERATIONAL_ERROR for item in matching):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.ERROR,
            "fact.provider_operational_error",
            tuple(item.fact_id for item in matching),
        )
    available = tuple(item for item in matching if item.state is FactOperationalState.AVAILABLE)
    if not available:
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.INDETERMINATE,
            "fact.unavailable_or_indeterminate",
            tuple(item.fact_id for item in matching),
        )
    parameters = requirement.parameters
    predicate = parameters.get("predicate")
    expected = parameters.get("expected")
    if not isinstance(predicate, str):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.ERROR,
            "requirement.invalid_predicate",
            tuple(item.fact_id for item in available),
        )
    if predicate == "boolean_asserted_with_provenance":
        without_provenance = tuple(item for item in available if not item.provenance)
        if without_provenance:
            return RequirementVerdict(
                requirement.requirement_id,
                RequirementStatus.ERROR,
                "requirement.provenance_required",
                tuple(item.fact_id for item in without_provenance),
            )
    try:
        results = [
            compare(predicate, item.value, expected, now=context.get("now")) for item in available
        ]
    except (ContractError, TypeError, ValueError, OverflowError):
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.ERROR,
            "requirement.type_or_value_error",
            tuple(item.fact_id for item in available),
        )
    if all(results):
        status = RequirementStatus.SATISFIED
    elif not any(results):
        status = RequirementStatus.UNSATISFIED
    else:
        return RequirementVerdict(
            requirement.requirement_id,
            RequirementStatus.INDETERMINATE,
            "fact.conflict",
            tuple(item.fact_id for item in available),
        )
    return RequirementVerdict(
        requirement.requirement_id,
        status,
        "requirement.satisfied"
        if status is RequirementStatus.SATISFIED
        else "requirement.unsatisfied",
        tuple(item.fact_id for item in available),
    )


def default_evaluator_registry(requirement_types: Sequence[str]) -> EvaluatorRegistry:
    registry = EvaluatorRegistry()
    for requirement_type in sorted(set(requirement_types)):
        registry.register(requirement_type, evaluate_constraint)
    return registry
