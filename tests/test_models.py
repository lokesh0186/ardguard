from __future__ import annotations

import copy

import pytest

from ardguard.models import ContractError, FactSet, Observation, Policy, TaskContract


def test_task_and_policy_parse(fallback_documents) -> None:
    _, task, policy, _ = fallback_documents
    assert TaskContract.from_mapping(task).operation == "records.read"
    assert [item.value for item in Policy.from_mapping(policy).required_checks] == [
        "capability",
        "evidence",
        "authority",
    ]


def test_unknown_task_field_fails(fallback_documents) -> None:
    _, task, _, _ = fallback_documents
    changed = copy.deepcopy(task)
    changed["eligible"] = True
    with pytest.raises(ContractError, match="unsupported fields"):
        TaskContract.from_mapping(changed)


def test_fact_set_cannot_assert_eligibility(fallback_documents) -> None:
    _, _, _, facts = fallback_documents
    changed = copy.deepcopy(facts)
    changed["observations"][0]["eligible"] = True
    with pytest.raises(ContractError, match="unsupported fields"):
        FactSet.from_mapping(changed)


def test_nonavailable_observation_cannot_carry_payload() -> None:
    with pytest.raises(ContractError, match="empty payloads"):
        Observation.from_mapping(
            {
                "candidate_id": "candidate",
                "fact_type": "evidence",
                "provider": {"id": "test", "version": "1"},
                "state": "OPERATIONAL_ERROR",
                "payload": {"authentic": False},
                "provenance": {},
            }
        )


def test_operational_error_cannot_be_encoded_as_invalid() -> None:
    with pytest.raises(ContractError, match="empty payloads"):
        Observation.from_mapping(
            {
                "candidate_id": "candidate",
                "fact_type": "evidence",
                "provider": {"id": "test", "version": "1"},
                "state": "OPERATIONAL_ERROR",
                "payload": {"verifier_outcome": "AVAILABLE_INVALID", "authentic": False},
                "provenance": {},
            }
        )


def test_invalid_evidence_requires_authentic_false(fallback_documents) -> None:
    _, _, _, facts = fallback_documents
    row = copy.deepcopy(facts["observations"][1])
    row["payload"]["verifier_outcome"] = "AVAILABLE_INVALID"
    with pytest.raises(ContractError, match="authentic=false"):
        Observation.from_mapping(row)


def test_duplicate_fact_key_fails(fallback_documents) -> None:
    _, _, _, facts = fallback_documents
    changed = copy.deepcopy(facts)
    changed["observations"].append(copy.deepcopy(changed["observations"][0]))
    with pytest.raises(ContractError, match="duplicate"):
        FactSet.from_mapping(changed)
