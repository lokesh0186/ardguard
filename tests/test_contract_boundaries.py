from __future__ import annotations

import copy

import pytest

from ardguard.adapters import parse_search_response
from ardguard.models import (
    AuthorityRequirement,
    Candidate,
    ContractError,
    EvidenceRequirement,
    FactSet,
    FactType,
    FinalDecision,
    Observation,
    ObservationState,
    Policy,
    ProviderIdentity,
    SelectionMode,
    TaskContract,
)


def _mutated(document: object, path: tuple[object, ...], value: object) -> object:
    changed = copy.deepcopy(document)
    target = changed
    for part in path[:-1]:
        target = target[part]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    return changed


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("schema_version",), "wrong", "schema_version"),
        (("task_id",), " ", "non-empty"),
        (("operation",), "", "non-empty"),
        (("required_capabilities",), "read", "array"),
        (("required_capabilities",), ["read", "read"], "duplicates"),
        (("evidence", "required"), "yes", "boolean"),
        (("evidence", "artifact_digest_field"), "", "non-empty"),
        (("evidence", "accepted_predicate_types"), ["p", "p"], "duplicates"),
        (("authority", "required"), 1, "boolean"),
        (("authority", "required_permissions"), ["records.write"], "within maximum"),
    ],
)
def test_task_contract_rejects_malformed_boundaries(
    fallback_documents, path: tuple[object, ...], value: object, message: str
) -> None:
    _, task, _, _ = fallback_documents
    with pytest.raises(ContractError, match=message):
        TaskContract.from_mapping(_mutated(task, path, value))


def test_task_requires_at_least_one_fact(fallback_documents) -> None:
    _, task, _, _ = fallback_documents
    changed = copy.deepcopy(task)
    changed["required_capabilities"] = []
    changed["evidence"]["required"] = False
    changed["authority"]["required"] = False
    with pytest.raises(ContractError, match="at least one"):
        TaskContract.from_mapping(changed)


def test_task_operation_must_be_authorized(fallback_documents) -> None:
    _, task, _, _ = fallback_documents
    changed = copy.deepcopy(task)
    changed["operation"] = "records.write"
    with pytest.raises(ContractError, match="operation"):
        TaskContract.from_mapping(changed)


def test_direct_requirement_constructors_are_guarded() -> None:
    with pytest.raises(ContractError, match="boolean"):
        EvidenceRequirement("yes", "digest", (), ())  # type: ignore[arg-type]
    with pytest.raises(ContractError, match="boolean"):
        AuthorityRequirement("yes", (), ())  # type: ignore[arg-type]
    with pytest.raises(ContractError, match="within maximum"):
        AuthorityRequirement(True, ("read",), ())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "wrong", "schema_version"),
        ("selection_mode", "random", "invalid policy enum"),
        ("required_checks", [], "at least one"),
        ("required_checks", ["capability", "capability"], "duplicates"),
        ("indeterminate_action", "SELECT", "DEFER or ABSTAIN"),
        ("operational_error_action", "SELECT", "DEFER, ABSTAIN, or ERROR"),
    ],
)
def test_policy_rejects_invalid_configuration(
    fallback_documents, field: str, value: object, message: str
) -> None:
    _, _, policy, _ = fallback_documents
    with pytest.raises(ContractError, match=message):
        Policy.from_mapping(_mutated(policy, (field,), value))


def test_direct_policy_constructor_is_guarded() -> None:
    with pytest.raises(ContractError, match="duplicates"):
        Policy(
            SelectionMode.FALLBACK,
            (FactType.CAPABILITY, FactType.CAPABILITY),
            FinalDecision.DEFER,
            FinalDecision.ERROR,
        )
    with pytest.raises(ContractError, match="DEFER or ABSTAIN"):
        Policy(
            SelectionMode.FALLBACK,
            (FactType.CAPABILITY,),
            FinalDecision.SELECT,
            FinalDecision.ERROR,
        )
    with pytest.raises(ContractError, match="DEFER, ABSTAIN, or ERROR"):
        Policy(
            SelectionMode.FALLBACK,
            (FactType.CAPABILITY,),
            FinalDecision.DEFER,
            FinalDecision.SELECT,
        )


def test_provider_identity_is_closed_and_nonempty() -> None:
    with pytest.raises(ContractError, match="unsupported"):
        ProviderIdentity.from_mapping({"id": "x", "version": "1", "trust": True})
    with pytest.raises(ContractError, match="non-empty"):
        ProviderIdentity("", "1")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"rank": 0}, "positive integer"),
        ({"rank": True}, "positive integer"),
        ({"score": -1}, "0 through 100"),
        ({"score": True}, "0 through 100"),
        ({"media_type": ""}, "non-empty"),
        ({"metadata": []}, "object"),
        ({"original": []}, "object"),
    ],
)
def test_direct_candidate_constructor_is_guarded(kwargs: dict[str, object], message: str) -> None:
    values: dict[str, object] = {
        "resource_id": "urn:example:candidate",
        "source": "https://example.org/catalog",
        "rank": 1,
        "score": 50,
    }
    values.update(kwargs)
    with pytest.raises(ContractError, match=message):
        Candidate(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("identifier", "", "non-empty"),
        ("source", "", "non-empty"),
        ("score", 101, "0 through 100"),
        ("score", True, "0 through 100"),
        ("type", "", "non-empty"),
        ("metadata", [], "object"),
    ],
)
def test_ard_candidate_parser_rejects_malformed_result(
    fallback_documents, field: str, value: object, message: str
) -> None:
    discovery, _, _, _ = fallback_documents
    row = _mutated(discovery["results"][0], (field,), value)
    with pytest.raises(ContractError, match=message):
        Candidate.from_ard_result(row, rank=1)


def test_candidate_artifact_digest_absence_and_validation(fallback_inputs) -> None:
    candidate = fallback_inputs[0][0]
    assert candidate.artifact_sha256("missing") is None
    changed = Candidate(
        candidate.resource_id,
        candidate.source,
        candidate.rank,
        candidate.score,
        candidate.media_type,
        {"artifact_sha256": "BAD"},
        {},
    )
    with pytest.raises(ContractError, match="SHA-256"):
        changed.artifact_sha256("artifact_sha256")


def test_nested_candidate_fields_are_immutable_and_serialize_plainly() -> None:
    metadata = {"nested": {"values": [1, 2]}}
    candidate = Candidate("urn:x", "https://example.org", 1, 1, metadata=metadata)
    metadata["nested"]["values"].append(3)
    assert tuple(candidate.metadata["nested"]["values"]) == (1, 2)


def test_observation_direct_enums_and_containers_are_guarded() -> None:
    provider = ProviderIdentity("test", "1")
    with pytest.raises(ContractError, match="FactType"):
        Observation("x", "capability", provider, ObservationState.AVAILABLE, {}, {})  # type: ignore[arg-type]
    with pytest.raises(ContractError, match="ObservationState"):
        Observation("x", FactType.CAPABILITY, provider, "AVAILABLE", {}, {})  # type: ignore[arg-type]
    with pytest.raises(ContractError, match="object"):
        Observation("x", FactType.CAPABILITY, provider, ObservationState.AVAILABLE, [], {})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("fact_type", "payload", "message"),
    [
        ("capability", {}, "array"),
        ("capability", {"verified_capabilities": [], "eligible": True}, "unsupported"),
        ("authority", {}, "array"),
        ("authority", {"granted_permissions": ["read", "read"]}, "duplicates"),
        ("evidence", {}, "invalid verifier outcome"),
    ],
)
def test_available_observation_payloads_are_closed(
    fact_type: str, payload: object, message: str
) -> None:
    with pytest.raises(ContractError, match=message):
        Observation.from_mapping(
            {
                "candidate_id": "candidate",
                "fact_type": fact_type,
                "provider": {"id": "test", "version": "1"},
                "state": "AVAILABLE",
                "payload": payload,
                "provenance": {},
            }
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"verifier_outcome": "UNAVAILABLE"}, "available verifier outcome"),
        ({"authentic": "yes"}, "true, false, or null"),
        ({"trust_valid": None}, "state trust_valid"),
        ({"signer_identity": ""}, "non-empty"),
        ({"subject_sha256": ["a" * 64, "a" * 64]}, "duplicates"),
        ({"artifact_sha256": "bad"}, "SHA-256"),
        ({"evidence_sha256": "bad"}, "SHA-256"),
        ({"predicate_types": [""]}, "non-empty"),
        ({"resource_id": ""}, "non-empty"),
    ],
)
def test_evidence_payload_validation_is_fail_closed(
    fallback_documents, change: dict[str, object], message: str
) -> None:
    _, _, _, facts = fallback_documents
    row = copy.deepcopy(facts["observations"][1])
    row["payload"].update(change)
    with pytest.raises(ContractError, match=message):
        Observation.from_mapping(row)


def test_invalid_evidence_requires_consistent_boolean_fields(fallback_documents) -> None:
    _, _, _, facts = fallback_documents
    row = copy.deepcopy(facts["observations"][1])
    row["payload"].update({"verifier_outcome": "AVAILABLE_INVALID", "authentic": False})
    assert Observation.from_mapping(row).payload["authentic"] is False


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ({}, "schema_version"),
        ({"schema_version": "wrong", "observations": []}, "schema_version"),
        ({"schema_version": "ardguard.dev/fact-set/v1", "observations": {}}, "array"),
    ],
)
def test_fact_set_shape_is_closed(value: object, message: str) -> None:
    with pytest.raises(ContractError, match=message):
        FactSet.from_mapping(value)


def test_nonmapping_contracts_and_nonstring_keys_fail() -> None:
    with pytest.raises(ContractError, match="object"):
        TaskContract.from_mapping([])
    with pytest.raises(ContractError, match="keys must be strings"):
        TaskContract.from_mapping({1: "value"})


def test_parse_search_response_still_accepts_frozen_current_fixture(fallback_documents) -> None:
    discovery, _, _, _ = fallback_documents
    assert len(parse_search_response(discovery)) == 2
