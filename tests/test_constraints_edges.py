from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ardguard.constraints import compare, evaluate_constraint, resolve_candidate_field
from ardguard.kernel import Fact, FactOperationalState, Requirement, RequirementStatus
from ardguard.models import Candidate, ContractError


def fact(state=FactOperationalState.AVAILABLE, value="x") -> Fact:
    return Fact(
        "fact",
        "candidate",
        "example.value",
        "provider.example",
        "1",
        state,
        value if state is FactOperationalState.AVAILABLE else None,
    )


def requirement(**parameters) -> Requirement:
    return Requirement("requirement", "example.value", parameters)


def test_field_resolver_missing_and_unapproved_roots() -> None:
    candidate = Candidate(
        "urn:air:example.org:tool:x",
        "https://registry.example.org/",
        1,
        1,
        original={"metadata": {}},
    )
    assert resolve_candidate_field(candidate, "metadata.missing") is None
    with pytest.raises(ContractError, match="core or namespaced"):
        resolve_candidate_field(candidate, "untrusted.path")


@pytest.mark.parametrize(
    ("predicate", "actual", "expected", "error"),
    [
        ("not_equals", 1, "1", TypeError),
        ("one_of", 1, ["1"], TypeError),
        ("subset_of", "x", ["x"], TypeError),
        ("subset_of", ["x", "x"], ["x"], ValueError),
        ("numeric_min", True, 1, TypeError),
        ("numeric_max", "1", 2, TypeError),
        ("semver_min", 1, "1.0.0", TypeError),
        ("semver_max", "version", "1.0.0", ValueError),
        ("fresh_within_seconds", "2026-09-10T00:00:00Z", True, TypeError),
        ("fresh_within_seconds", "2026-09-10T00:00:00", 10, ValueError),
        ("digest_equals", 1, "a" * 64, TypeError),
        ("digest_equals", "bad", "a" * 64, ValueError),
        ("boolean_asserted_with_provenance", "false", True, TypeError),
    ],
)
def test_predicates_fail_closed(predicate, actual, expected, error) -> None:
    with pytest.raises(error):
        compare(predicate, actual, expected)


def test_semver_prerelease_and_freshness() -> None:
    assert compare("semver_min", "1.0.0", "1.0.0-rc.1")
    now = datetime(2026, 9, 10, 0, 0, 10, tzinfo=timezone.utc)
    assert compare("fresh_within_seconds", "2026-09-10T00:00:05Z", 10, now=now)
    assert not compare("fresh_within_seconds", "2026-09-10T00:00:20Z", 30, now=now)


def test_constraint_state_mapping_and_invalid_predicates() -> None:
    req = requirement(predicate="equals", expected="x")
    assert evaluate_constraint(req, (), {}).status is RequirementStatus.INDETERMINATE
    assert (
        evaluate_constraint(req, (fact(FactOperationalState.OPERATIONAL_ERROR),), {}).status
        is RequirementStatus.ERROR
    )
    assert (
        evaluate_constraint(req, (fact(FactOperationalState.UNAVAILABLE),), {}).status
        is RequirementStatus.INDETERMINATE
    )
    assert (
        evaluate_constraint(requirement(expected="x"), (fact(),), {}).status
        is RequirementStatus.ERROR
    )
    assert (
        evaluate_constraint(
            requirement(predicate="numeric_min", expected=2), (fact(value="x"),), {}
        ).status
        is RequirementStatus.ERROR
    )
    assert (
        evaluate_constraint(requirement(predicate="equals", expected="y"), (fact(),), {}).status
        is RequirementStatus.UNSATISFIED
    )
