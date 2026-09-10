"""Stable public reason codes and their operational meaning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReasonCode(str, Enum):
    CAPABILITY_VERIFIED = "capability.verified"
    CAPABILITY_MISMATCH = "capability.mismatch"
    CAPABILITY_UNAVAILABLE = "capability.unavailable"
    CAPABILITY_INDETERMINATE = "capability.indeterminate"
    CAPABILITY_OPERATIONAL_ERROR = "capability.operational_error"

    EVIDENCE_AUTHENTIC = "evidence.authentic"
    EVIDENCE_INVALID = "evidence.invalid"
    EVIDENCE_SUBJECT_MISMATCH = "evidence.subject_mismatch"
    EVIDENCE_PREDICATE_INSUFFICIENT = "evidence.predicate_insufficient"
    EVIDENCE_RESOURCE_MISMATCH = "evidence.wrong_resource_association"
    EVIDENCE_SIGNER_UNTRUSTED = "evidence.signer_untrusted"
    EVIDENCE_VERIFIER_UNAVAILABLE = "evidence.verifier_unavailable"
    EVIDENCE_VERIFIER_OPERATIONAL_ERROR = "evidence.verifier_operational_error"
    EVIDENCE_INDETERMINATE = "evidence.indeterminate"

    AUTHORITY_WITHIN_POLICY = "authority.within_policy"
    AUTHORITY_EXCESSIVE = "authority.excessive"
    AUTHORITY_UNKNOWN = "authority.unknown"
    AUTHORITY_UNAVAILABLE = "authority.unavailable"
    AUTHORITY_OPERATIONAL_ERROR = "authority.operational_error"

    SELECTION_TOP_RANKED_ELIGIBLE = "selection.top_ranked_eligible"
    SELECTION_FALLBACK = "selection.fallback_to_lower_ranked_eligible"
    SELECTION_NO_ELIGIBLE = "selection.no_eligible_candidate"
    SELECTION_INDETERMINATE = "selection.eligibility_indeterminate"
    SELECTION_ENGINE_ERROR = "selection.engine_error"


@dataclass(frozen=True)
class ReasonDefinition:
    meaning: str
    retry_may_help: bool
    rejects_candidate: bool
    fail_closed: bool


REASON_DEFINITIONS: dict[ReasonCode, ReasonDefinition] = {
    ReasonCode.CAPABILITY_VERIFIED: ReasonDefinition(
        "An independent provider verified every capability required by the task.",
        False,
        False,
        False,
    ),
    ReasonCode.CAPABILITY_MISMATCH: ReasonDefinition(
        "The verified executable capabilities do not satisfy the task.", False, True, True
    ),
    ReasonCode.CAPABILITY_UNAVAILABLE: ReasonDefinition(
        "The configured capability provider is unavailable.", True, False, True
    ),
    ReasonCode.CAPABILITY_INDETERMINATE: ReasonDefinition(
        "Capability could not be established from the supplied observation.", True, False, True
    ),
    ReasonCode.CAPABILITY_OPERATIONAL_ERROR: ReasonDefinition(
        "The capability provider failed operationally.", True, False, True
    ),
    ReasonCode.EVIDENCE_AUTHENTIC: ReasonDefinition(
        "Evidence is authentic, trusted, sufficient, and bound to this candidate.",
        False,
        False,
        False,
    ),
    ReasonCode.EVIDENCE_INVALID: ReasonDefinition(
        "A functioning verifier rejected the evidence cryptographically.", False, True, True
    ),
    ReasonCode.EVIDENCE_SUBJECT_MISMATCH: ReasonDefinition(
        "Authentic evidence names a different artifact digest.", False, True, True
    ),
    ReasonCode.EVIDENCE_PREDICATE_INSUFFICIENT: ReasonDefinition(
        "The verified statement lacks a predicate required by policy.", False, True, True
    ),
    ReasonCode.EVIDENCE_RESOURCE_MISMATCH: ReasonDefinition(
        "The evidence observation is associated with a different resource.", False, True, True
    ),
    ReasonCode.EVIDENCE_SIGNER_UNTRUSTED: ReasonDefinition(
        "The signer or trust root does not satisfy task policy.", False, True, True
    ),
    ReasonCode.EVIDENCE_VERIFIER_UNAVAILABLE: ReasonDefinition(
        "The configured cryptographic verifier is unavailable.", True, False, True
    ),
    ReasonCode.EVIDENCE_VERIFIER_OPERATIONAL_ERROR: ReasonDefinition(
        "The verifier failed operationally; this is not cryptographic invalidity.",
        True,
        False,
        True,
    ),
    ReasonCode.EVIDENCE_INDETERMINATE: ReasonDefinition(
        "Evidence validity or applicability could not be established.", True, False, True
    ),
    ReasonCode.AUTHORITY_WITHIN_POLICY: ReasonDefinition(
        "Verified permissions contain the required operation and stay within policy.",
        False,
        False,
        False,
    ),
    ReasonCode.AUTHORITY_EXCESSIVE: ReasonDefinition(
        "Verified permissions exceed the operator-defined maximum.", False, True, True
    ),
    ReasonCode.AUTHORITY_UNKNOWN: ReasonDefinition(
        "The candidate's authority could not be established.", True, False, True
    ),
    ReasonCode.AUTHORITY_UNAVAILABLE: ReasonDefinition(
        "The configured authority provider is unavailable.", True, False, True
    ),
    ReasonCode.AUTHORITY_OPERATIONAL_ERROR: ReasonDefinition(
        "The authority provider failed operationally.", True, False, True
    ),
    ReasonCode.SELECTION_TOP_RANKED_ELIGIBLE: ReasonDefinition(
        "The highest-ranked candidate is eligible.", False, False, False
    ),
    ReasonCode.SELECTION_FALLBACK: ReasonDefinition(
        "A higher-ranked candidate was not eligible, so selection fell back safely.",
        False,
        False,
        False,
    ),
    ReasonCode.SELECTION_NO_ELIGIBLE: ReasonDefinition(
        "No candidate was established as eligible.", False, False, True
    ),
    ReasonCode.SELECTION_INDETERMINATE: ReasonDefinition(
        "At least one required eligibility result remains indeterminate.", True, False, True
    ),
    ReasonCode.SELECTION_ENGINE_ERROR: ReasonDefinition(
        "ARDGuard could not complete the decision safely.", True, False, True
    ),
}
