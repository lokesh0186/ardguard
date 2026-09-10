from __future__ import annotations

from ardguard.kernel import Fact, FactOperationalState, Requirement, RequirementStatus
from ardguard.packs import evaluate_evidence, evaluate_evidence_bundle

CANDIDATE = "urn:air:example.org:tool:reader"
DIGEST = "a" * 64


def requirement() -> Requirement:
    return Requirement(
        "evidence",
        "evidence.applicable",
        {
            "artifact_digest_field": "artifact_sha256",
            "trusted_signers": ["https://example.org/publisher"],
            "accepted_predicate_types": ["https://example.org/predicate/publish/v1"],
            "fact_types": [
                "evidence.envelope_authentic",
                "evidence.signer_identity",
                "evidence.statement_integrity",
                "evidence.predicate_type",
                "evidence.subject_digest",
                "evidence.resource_association",
                "evidence.verifier_available",
            ],
        },
    )


def facts(subject: str = DIGEST) -> tuple[Fact, ...]:
    values = {
        "evidence.envelope_authentic": True,
        "evidence.signer_identity": "https://example.org/publisher",
        "evidence.statement_integrity": True,
        "evidence.predicate_type": "https://example.org/predicate/publish/v1",
        "evidence.subject_digest": subject,
        "evidence.resource_association": CANDIDATE,
        "evidence.verifier_available": True,
    }
    return tuple(
        Fact(
            f"fact-{index}",
            CANDIDATE,
            fact_type,
            "provider.evidence",
            "1",
            FactOperationalState.AVAILABLE,
            value,
            provenance={"raw_receipt_sha256": str(index) * 64},
        )
        for index, (fact_type, value) in enumerate(values.items(), start=1)
    )


def context() -> dict[str, str]:
    return {"candidate_id": CANDIDATE, "candidate_artifact_sha256": DIGEST}


def test_matching_evidence_facts_are_satisfied() -> None:
    verdict = evaluate_evidence_bundle(requirement(), facts(), context())
    assert verdict.status is RequirementStatus.SATISFIED


def test_authentic_wrong_subject_is_unsatisfied() -> None:
    verdict = evaluate_evidence_bundle(requirement(), facts("b" * 64), context())
    assert verdict.status is RequirementStatus.UNSATISFIED


def test_unavailable_verifier_is_not_cryptographic_invalidity() -> None:
    rows = list(facts())
    last = rows[-1]
    rows[-1] = Fact(
        last.fact_id,
        last.candidate_id,
        last.fact_type,
        last.provider_id,
        last.provider_version,
        FactOperationalState.AVAILABLE,
        False,
    )
    verdict = evaluate_evidence_bundle(requirement(), tuple(rows), context())
    assert verdict.status is RequirementStatus.INDETERMINATE
    assert verdict.reason_code == "evidence.verifier_unavailable"


def test_operational_error_is_error_not_invalidity() -> None:
    rows = list(facts())
    rows[0] = Fact(
        "op-error",
        CANDIDATE,
        "evidence.envelope_authentic",
        "provider.evidence",
        "1",
        FactOperationalState.OPERATIONAL_ERROR,
    )
    verdict = evaluate_evidence_bundle(requirement(), tuple(rows), context())
    assert verdict.status is RequirementStatus.ERROR
    assert verdict.reason_code == "evidence.verifier_operational_error"


def test_conflicting_same_type_evidence_facts_are_indeterminate() -> None:
    rows = list(facts())
    original = rows[0]
    rows.append(
        Fact(
            "fact-conflict",
            CANDIDATE,
            original.fact_type,
            "provider.other",
            "1",
            FactOperationalState.AVAILABLE,
            False,
            provenance={"raw_receipt_sha256": "f" * 64},
        )
    )
    verdict = evaluate_evidence_bundle(requirement(), tuple(rows), context())
    assert verdict.status is RequirementStatus.INDETERMINATE
    assert verdict.reason_code == "evidence.conflicting_facts"


def test_structured_evidence_identity_is_canonicalized_before_conflict_check() -> None:
    aggregate_requirement = Requirement(
        "aggregate-evidence",
        "evidence",
        {
            "artifact_digest_field": "artifact_sha256",
            "trusted_signers": ["https://example.org/publisher"],
            "accepted_predicate_types": ["https://example.org/predicate/publish/v1"],
        },
    )
    aggregate = Fact(
        "aggregate-fact",
        CANDIDATE,
        "evidence",
        "provider.evidence",
        "1",
        FactOperationalState.AVAILABLE,
        {
            "authentic": True,
            "trust_valid": True,
            "resource_id": CANDIDATE,
            "artifact_sha256": DIGEST,
            "subject_sha256": [DIGEST],
            "signer_identity": "https://example.org/publisher",
            "predicate_types": ["https://example.org/predicate/publish/v1"],
        },
        evidence_identity="fixture:aggregate",
    )

    verdict = evaluate_evidence(
        aggregate_requirement,
        (aggregate,),
        context(),
    )

    assert verdict.status is RequirementStatus.SATISFIED
    assert verdict.reason_code == "evidence.applicable"
