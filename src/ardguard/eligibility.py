"""Deterministic task-specific eligibility composition."""

from __future__ import annotations

from collections.abc import Mapping

from ardguard.models import (
    Candidate,
    CandidateEvaluation,
    CandidateVerdict,
    FactType,
    Observation,
    ObservationState,
    TaskContract,
    VerifierOutcome,
)
from ardguard.reasons import ReasonCode


def _state_reason(observation: Observation) -> ReasonCode:
    table = {
        FactType.CAPABILITY: {
            ObservationState.UNAVAILABLE: ReasonCode.CAPABILITY_UNAVAILABLE,
            ObservationState.OPERATIONAL_ERROR: ReasonCode.CAPABILITY_OPERATIONAL_ERROR,
            ObservationState.INDETERMINATE: ReasonCode.CAPABILITY_INDETERMINATE,
        },
        FactType.EVIDENCE: {
            ObservationState.UNAVAILABLE: ReasonCode.EVIDENCE_VERIFIER_UNAVAILABLE,
            ObservationState.OPERATIONAL_ERROR: ReasonCode.EVIDENCE_VERIFIER_OPERATIONAL_ERROR,
            ObservationState.INDETERMINATE: ReasonCode.EVIDENCE_INDETERMINATE,
        },
        FactType.AUTHORITY: {
            ObservationState.UNAVAILABLE: ReasonCode.AUTHORITY_UNAVAILABLE,
            ObservationState.OPERATIONAL_ERROR: ReasonCode.AUTHORITY_OPERATIONAL_ERROR,
            ObservationState.INDETERMINATE: ReasonCode.AUTHORITY_UNKNOWN,
        },
    }
    return table[observation.fact_type][observation.state]


def _capability(
    task: TaskContract, observation: Observation
) -> tuple[CandidateVerdict, ReasonCode]:
    verified = set(observation.payload["verified_capabilities"])
    if set(task.required_capabilities).issubset(verified):
        return CandidateVerdict.ELIGIBLE, ReasonCode.CAPABILITY_VERIFIED
    return CandidateVerdict.INELIGIBLE, ReasonCode.CAPABILITY_MISMATCH


def _evidence(
    candidate: Candidate, task: TaskContract, observation: Observation
) -> tuple[CandidateVerdict, ReasonCode]:
    payload = observation.payload
    outcome = VerifierOutcome(payload["verifier_outcome"])
    if outcome is VerifierOutcome.AVAILABLE_INVALID:
        return CandidateVerdict.INELIGIBLE, ReasonCode.EVIDENCE_INVALID
    candidate_digest = candidate.artifact_sha256(task.evidence.artifact_digest_field)
    trusted_signers = set(task.evidence.trusted_signers)
    failures = (
        (
            payload["resource_id"] != candidate.resource_id
            or candidate_digest is None
            or payload["artifact_sha256"] != candidate_digest,
            ReasonCode.EVIDENCE_RESOURCE_MISMATCH,
        ),
        (
            candidate_digest is None or candidate_digest not in payload["subject_sha256"],
            ReasonCode.EVIDENCE_SUBJECT_MISMATCH,
        ),
        (payload["trust_valid"] is not True, ReasonCode.EVIDENCE_SIGNER_UNTRUSTED),
        (
            bool(trusted_signers) and payload.get("signer_identity") not in trusted_signers,
            ReasonCode.EVIDENCE_SIGNER_UNTRUSTED,
        ),
        (
            not set(task.evidence.accepted_predicate_types).issubset(payload["predicate_types"]),
            ReasonCode.EVIDENCE_PREDICATE_INSUFFICIENT,
        ),
    )
    for failed, reason in failures:
        if failed:
            return CandidateVerdict.INELIGIBLE, reason
    return CandidateVerdict.ELIGIBLE, ReasonCode.EVIDENCE_AUTHENTIC


def _authority(task: TaskContract, observation: Observation) -> tuple[CandidateVerdict, ReasonCode]:
    granted = set(observation.payload["granted_permissions"])
    required = set(task.authority.required_permissions)
    permitted = set(task.authority.maximum_permissions)
    if not required.issubset(granted):
        return CandidateVerdict.INELIGIBLE, ReasonCode.AUTHORITY_UNKNOWN
    if not granted.issubset(permitted):
        return CandidateVerdict.INELIGIBLE, ReasonCode.AUTHORITY_EXCESSIVE
    return CandidateVerdict.ELIGIBLE, ReasonCode.AUTHORITY_WITHIN_POLICY


def evaluate_candidate(
    candidate: Candidate,
    task: TaskContract,
    required_checks: tuple[FactType, ...],
    observations: Mapping[FactType, Observation],
) -> CandidateEvaluation:
    reasons: list[ReasonCode] = []
    providers = []
    verdicts: list[CandidateVerdict] = []
    for fact_type in required_checks:
        observation = observations.get(fact_type)
        if observation is None:
            verdicts.append(CandidateVerdict.INDETERMINATE)
            missing = {
                FactType.CAPABILITY: ReasonCode.CAPABILITY_INDETERMINATE,
                FactType.EVIDENCE: ReasonCode.EVIDENCE_INDETERMINATE,
                FactType.AUTHORITY: ReasonCode.AUTHORITY_UNKNOWN,
            }[fact_type]
            reasons.append(missing)
            continue
        providers.append(observation.provider)
        if observation.state is not ObservationState.AVAILABLE:
            verdicts.append(CandidateVerdict.INDETERMINATE)
            reasons.append(_state_reason(observation))
            continue
        if fact_type is FactType.CAPABILITY:
            verdict, reason = _capability(task, observation)
        elif fact_type is FactType.EVIDENCE:
            verdict, reason = _evidence(candidate, task, observation)
        else:
            verdict, reason = _authority(task, observation)
        verdicts.append(verdict)
        reasons.append(reason)
    if CandidateVerdict.INELIGIBLE in verdicts:
        final = CandidateVerdict.INELIGIBLE
    elif CandidateVerdict.INDETERMINATE in verdicts:
        final = CandidateVerdict.INDETERMINATE
    else:
        final = CandidateVerdict.ELIGIBLE
    return CandidateEvaluation(
        candidate.resource_id,
        candidate.rank,
        candidate.score,
        final,
        tuple(reasons),
        tuple(providers),
    )
