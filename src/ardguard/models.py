"""Versioned public product contracts.

Facts are observations. Callers cannot supply a final eligibility verdict; ARDGuard
derives candidate and final decisions from the configured policy.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from ardguard.reasons import ReasonCode

TASK_SCHEMA = "ardguard.dev/task-contract/v1"
FACT_SET_SCHEMA = "ardguard.dev/fact-set/v1"
POLICY_SCHEMA = "ardguard.dev/policy/v1"
DECISION_SCHEMA = "ardguard.dev/decision/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_ARD_SCORE = 100


class ContractError(ValueError):
    """A public input does not satisfy its closed contract."""


class FactType(str, Enum):
    CAPABILITY = "capability"
    EVIDENCE = "evidence"
    AUTHORITY = "authority"


class ObservationState(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    OPERATIONAL_ERROR = "OPERATIONAL_ERROR"
    INDETERMINATE = "INDETERMINATE"


class VerifierOutcome(str, Enum):
    AVAILABLE_VALID = "AVAILABLE_VALID"
    AVAILABLE_INVALID = "AVAILABLE_INVALID"
    UNAVAILABLE = "UNAVAILABLE"
    OPERATIONAL_ERROR = "OPERATIONAL_ERROR"
    RESULT_INDETERMINATE = "RESULT_INDETERMINATE"


class CandidateVerdict(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    INDETERMINATE = "INDETERMINATE"


class FinalDecision(str, Enum):
    SELECT = "SELECT"
    DEFER = "DEFER"
    ABSTAIN = "ABSTAIN"
    ERROR = "ERROR"


class SelectionMode(str, Enum):
    FALLBACK = "fallback"
    TOP_RANKED_ONLY = "top-ranked-only"


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{label} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise ContractError(f"{label} keys must be strings")
    return value


def _closed(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ContractError(f"{label} contains unsupported fields: {', '.join(unknown)}")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty string")
    return value


def _text_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ContractError(f"{label} must be an array of non-empty strings")
    if len(value) != len(set(value)):
        raise ContractError(f"{label} contains duplicates")
    return tuple(value)


def _optional_bool(value: object, label: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ContractError(f"{label} must be true, false, or null")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ContractError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return copy.deepcopy(value)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass(frozen=True)
class ProviderIdentity:
    provider_id: str
    version: str

    def __post_init__(self) -> None:
        _text(self.provider_id, "provider.id")
        _text(self.version, "provider.version")

    @classmethod
    def from_mapping(cls, value: object) -> ProviderIdentity:
        row = _mapping(value, "provider")
        _closed(row, {"id", "version"}, "provider")
        return cls(
            _text(row.get("id"), "provider.id"), _text(row.get("version"), "provider.version")
        )

    def to_dict(self) -> dict[str, str]:
        return {"id": self.provider_id, "version": self.version}


@dataclass(frozen=True)
class Candidate:
    resource_id: str
    source: str | None
    rank: int
    score: int | None
    media_type: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    original: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        _text(self.resource_id, "candidate.resource_id")
        if self.source is not None:
            _text(self.source, "candidate.source")
        if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
            raise ContractError("candidate rank must be a positive integer")
        if self.score is not None and (
            isinstance(self.score, bool)
            or not isinstance(self.score, int)
            or not 0 <= self.score <= MAX_ARD_SCORE
        ):
            raise ContractError("candidate score must be an integer from 0 through 100")
        if self.media_type is not None:
            _text(self.media_type, "candidate.media_type")
        metadata = _mapping(self.metadata, "candidate.metadata")
        original = _mapping(self.original, "candidate.original")
        object.__setattr__(self, "metadata", _freeze(metadata))
        object.__setattr__(self, "original", _freeze(original))

    @classmethod
    def from_ard_result(cls, value: object, *, rank: int) -> Candidate:
        row = _mapping(value, "search result")
        resource_id = _text(row.get("identifier"), "search result.identifier")
        source_value = row.get("source")
        source = (
            _text(source_value, "search result.source") if source_value is not None else None
        )
        score = row.get("score")
        if score is not None and (
            isinstance(score, bool)
            or not isinstance(score, int)
            or not 0 <= score <= MAX_ARD_SCORE
        ):
            raise ContractError("search result.score must be an integer from 0 through 100")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
            raise ContractError("candidate rank must be a positive integer")
        media_type = row.get("type")
        if media_type is not None and (not isinstance(media_type, str) or not media_type):
            raise ContractError("search result.type must be a non-empty string when present")
        metadata = row.get("metadata", {})
        if not isinstance(metadata, Mapping) or any(not isinstance(key, str) for key in metadata):
            raise ContractError("search result.metadata must be an object")
        return cls(
            resource_id=resource_id,
            source=source,
            rank=rank,
            score=score,
            media_type=media_type,
            metadata=copy.deepcopy(dict(metadata)),
            original=copy.deepcopy(dict(row)),
        )

    def artifact_sha256(self, field_name: str) -> str | None:
        value = self.metadata.get(field_name)
        if value is None:
            value = self.original.get(field_name)
        if value is None:
            return None
        return _sha256(value, f"candidate {self.resource_id} {field_name}")


@dataclass(frozen=True)
class EvidenceRequirement:
    required: bool
    artifact_digest_field: str
    accepted_predicate_types: tuple[str, ...]
    trusted_signers: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.required, bool):
            raise ContractError("evidence.required must be boolean")
        _text(self.artifact_digest_field, "evidence.artifact_digest_field")
        _text_tuple(list(self.accepted_predicate_types), "evidence.accepted_predicate_types")
        _text_tuple(list(self.trusted_signers), "evidence.trusted_signers")

    @classmethod
    def from_mapping(cls, value: object) -> EvidenceRequirement:
        row = _mapping(value, "task.evidence")
        _closed(
            row,
            {"required", "artifact_digest_field", "accepted_predicate_types", "trusted_signers"},
            "task.evidence",
        )
        required = row.get("required", False)
        if not isinstance(required, bool):
            raise ContractError("task.evidence.required must be boolean")
        return cls(
            required,
            _text(
                row.get("artifact_digest_field", "artifact_sha256"),
                "task.evidence.artifact_digest_field",
            ),
            _text_tuple(
                row.get("accepted_predicate_types", []), "task.evidence.accepted_predicate_types"
            ),
            _text_tuple(row.get("trusted_signers", []), "task.evidence.trusted_signers"),
        )


@dataclass(frozen=True)
class AuthorityRequirement:
    required: bool
    required_permissions: tuple[str, ...]
    maximum_permissions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.required, bool):
            raise ContractError("authority.required must be boolean")
        _text_tuple(list(self.required_permissions), "authority.required_permissions")
        _text_tuple(list(self.maximum_permissions), "authority.maximum_permissions")
        if not set(self.required_permissions).issubset(self.maximum_permissions):
            raise ContractError("required permissions must be within maximum permissions")

    @classmethod
    def from_mapping(cls, value: object) -> AuthorityRequirement:
        row = _mapping(value, "task.authority")
        _closed(row, {"required", "required_permissions", "maximum_permissions"}, "task.authority")
        required = row.get("required", False)
        if not isinstance(required, bool):
            raise ContractError("task.authority.required must be boolean")
        required_permissions = _text_tuple(
            row.get("required_permissions", []), "task.authority.required_permissions"
        )
        maximum_permissions = _text_tuple(
            row.get("maximum_permissions", []), "task.authority.maximum_permissions"
        )
        if not set(required_permissions).issubset(maximum_permissions):
            raise ContractError("required permissions must be within maximum permissions")
        return cls(required, required_permissions, maximum_permissions)


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    operation: str
    required_capabilities: tuple[str, ...]
    evidence: EvidenceRequirement
    authority: AuthorityRequirement

    def __post_init__(self) -> None:
        _text(self.task_id, "task.task_id")
        _text(self.operation, "task.operation")
        _text_tuple(list(self.required_capabilities), "task.required_capabilities")
        if self.authority.required and self.operation not in self.authority.required_permissions:
            raise ContractError("task.operation must appear in required authority permissions")
        if not self.required_fact_types:
            raise ContractError("task must require at least one eligibility fact")

    @classmethod
    def from_mapping(cls, value: object) -> TaskContract:
        row = _mapping(value, "task")
        _closed(
            row,
            {
                "schema_version",
                "task_id",
                "operation",
                "required_capabilities",
                "evidence",
                "authority",
            },
            "task",
        )
        if row.get("schema_version") != TASK_SCHEMA:
            raise ContractError(f"task.schema_version must be {TASK_SCHEMA}")
        operation = _text(row.get("operation"), "task.operation")
        authority = AuthorityRequirement.from_mapping(row.get("authority", {}))
        if authority.required and operation not in authority.required_permissions:
            raise ContractError("task.operation must appear in required authority permissions")
        return cls(
            _text(row.get("task_id"), "task.task_id"),
            operation,
            _text_tuple(row.get("required_capabilities", []), "task.required_capabilities"),
            EvidenceRequirement.from_mapping(row.get("evidence", {})),
            authority,
        )

    @property
    def required_fact_types(self) -> tuple[FactType, ...]:
        required: list[FactType] = []
        if self.required_capabilities:
            required.append(FactType.CAPABILITY)
        if self.evidence.required:
            required.append(FactType.EVIDENCE)
        if self.authority.required:
            required.append(FactType.AUTHORITY)
        return tuple(required)


@dataclass(frozen=True)
class Policy:
    selection_mode: SelectionMode
    required_checks: tuple[FactType, ...]
    indeterminate_action: FinalDecision
    operational_error_action: FinalDecision

    def __post_init__(self) -> None:
        if not self.required_checks:
            raise ContractError("policy must require at least one eligibility check")
        if len(self.required_checks) != len(set(self.required_checks)):
            raise ContractError("policy.required_checks contains duplicates")
        if self.indeterminate_action not in {FinalDecision.DEFER, FinalDecision.ABSTAIN}:
            raise ContractError("policy.indeterminate_action must be DEFER or ABSTAIN")
        if self.operational_error_action not in {
            FinalDecision.DEFER,
            FinalDecision.ABSTAIN,
            FinalDecision.ERROR,
        }:
            raise ContractError("policy.operational_error_action must be DEFER, ABSTAIN, or ERROR")

    @classmethod
    def from_mapping(cls, value: object) -> Policy:
        row = _mapping(value, "policy")
        _closed(
            row,
            {
                "schema_version",
                "selection_mode",
                "required_checks",
                "indeterminate_action",
                "operational_error_action",
            },
            "policy",
        )
        if row.get("schema_version") != POLICY_SCHEMA:
            raise ContractError(f"policy.schema_version must be {POLICY_SCHEMA}")
        try:
            selection_mode = SelectionMode(row.get("selection_mode", SelectionMode.FALLBACK.value))
            checks = tuple(FactType(item) for item in row.get("required_checks", []))
            indeterminate = FinalDecision(
                row.get("indeterminate_action", FinalDecision.DEFER.value)
            )
            operational = FinalDecision(
                row.get("operational_error_action", FinalDecision.ERROR.value)
            )
        except (TypeError, ValueError) as exc:
            raise ContractError(f"invalid policy enum: {exc}") from exc
        if len(checks) != len(set(checks)):
            raise ContractError("policy.required_checks contains duplicates")
        if indeterminate not in {FinalDecision.DEFER, FinalDecision.ABSTAIN}:
            raise ContractError("policy.indeterminate_action must be DEFER or ABSTAIN")
        if operational not in {FinalDecision.DEFER, FinalDecision.ABSTAIN, FinalDecision.ERROR}:
            raise ContractError("policy.operational_error_action must be DEFER, ABSTAIN, or ERROR")
        return cls(selection_mode, checks, indeterminate, operational)


@dataclass(frozen=True)
class Observation:
    candidate_id: str
    fact_type: FactType
    provider: ProviderIdentity
    state: ObservationState
    payload: Mapping[str, Any]
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.candidate_id, "observation.candidate_id")
        if not isinstance(self.fact_type, FactType):
            raise ContractError("observation.fact_type must be a FactType")
        if not isinstance(self.state, ObservationState):
            raise ContractError("observation.state must be an ObservationState")
        payload = _mapping(self.payload, "observation.payload")
        provenance = _mapping(self.provenance, "observation.provenance")
        self._validate_payload(self.fact_type, self.state, payload)
        object.__setattr__(self, "payload", _freeze(payload))
        object.__setattr__(self, "provenance", _freeze(provenance))

    @classmethod
    def from_mapping(cls, value: object) -> Observation:
        row = _mapping(value, "observation")
        _closed(
            row,
            {"candidate_id", "fact_type", "provider", "state", "payload", "provenance"},
            "observation",
        )
        if "eligible" in row or "verdict" in row:
            raise ContractError("observations cannot assert final eligibility")
        try:
            fact_type = FactType(row.get("fact_type"))
            state = ObservationState(row.get("state"))
        except (TypeError, ValueError) as exc:
            raise ContractError(f"invalid observation enum: {exc}") from exc
        payload = dict(_mapping(row.get("payload", {}), "observation.payload"))
        provenance = dict(_mapping(row.get("provenance", {}), "observation.provenance"))
        cls._validate_payload(fact_type, state, payload)
        return cls(
            _text(row.get("candidate_id"), "observation.candidate_id"),
            fact_type,
            ProviderIdentity.from_mapping(row.get("provider")),
            state,
            copy.deepcopy(payload),
            copy.deepcopy(provenance),
        )

    @staticmethod
    def _validate_payload(
        fact_type: FactType, state: ObservationState, payload: Mapping[str, Any]
    ) -> None:
        if state is not ObservationState.AVAILABLE:
            if payload:
                raise ContractError(
                    "unavailable, operational-error, and indeterminate observations "
                    "must have empty payloads"
                )
            return
        if fact_type is FactType.CAPABILITY:
            _closed(payload, {"verified_capabilities"}, "capability payload")
            _text_tuple(
                payload.get("verified_capabilities"), "capability payload.verified_capabilities"
            )
        elif fact_type is FactType.AUTHORITY:
            _closed(payload, {"granted_permissions"}, "authority payload")
            _text_tuple(payload.get("granted_permissions"), "authority payload.granted_permissions")
        else:
            _closed(
                payload,
                {
                    "verifier_outcome",
                    "authentic",
                    "trust_valid",
                    "signer_identity",
                    "subject_sha256",
                    "artifact_sha256",
                    "evidence_sha256",
                    "predicate_types",
                    "resource_id",
                },
                "evidence payload",
            )
            try:
                outcome = VerifierOutcome(payload.get("verifier_outcome"))
            except (TypeError, ValueError) as exc:
                raise ContractError(f"invalid verifier outcome: {exc}") from exc
            if outcome not in {VerifierOutcome.AVAILABLE_VALID, VerifierOutcome.AVAILABLE_INVALID}:
                raise ContractError(
                    "available evidence payload requires an available verifier outcome"
                )
            authentic = _optional_bool(payload.get("authentic"), "evidence payload.authentic")
            trust_valid = _optional_bool(payload.get("trust_valid"), "evidence payload.trust_valid")
            if outcome is VerifierOutcome.AVAILABLE_INVALID and authentic is not False:
                raise ContractError("cryptographically invalid evidence must set authentic=false")
            if outcome is VerifierOutcome.AVAILABLE_VALID and authentic is not True:
                raise ContractError("cryptographically valid evidence must set authentic=true")
            if trust_valid is None:
                raise ContractError("available evidence must state trust_valid")
            signer = payload.get("signer_identity")
            if signer is not None:
                _text(signer, "evidence payload.signer_identity")
            _text_tuple(payload.get("subject_sha256", []), "evidence payload.subject_sha256")
            _sha256(payload.get("artifact_sha256"), "evidence payload.artifact_sha256")
            _sha256(payload.get("evidence_sha256"), "evidence payload.evidence_sha256")
            _text_tuple(payload.get("predicate_types", []), "evidence payload.predicate_types")
            _text(payload.get("resource_id"), "evidence payload.resource_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "fact_type": self.fact_type.value,
            "provider": self.provider.to_dict(),
            "state": self.state.value,
            "payload": _plain(self.payload),
            "provenance": _plain(self.provenance),
        }


@dataclass(frozen=True)
class FactSet:
    observations: tuple[Observation, ...]

    @classmethod
    def from_mapping(cls, value: object) -> FactSet:
        row = _mapping(value, "fact set")
        _closed(row, {"schema_version", "observations"}, "fact set")
        if row.get("schema_version") != FACT_SET_SCHEMA:
            raise ContractError(f"fact set.schema_version must be {FACT_SET_SCHEMA}")
        values = row.get("observations")
        if not isinstance(values, list):
            raise ContractError("fact set.observations must be an array")
        observations = tuple(Observation.from_mapping(item) for item in values)
        keys = [(item.candidate_id, item.fact_type) for item in observations]
        if len(keys) != len(set(keys)):
            raise ContractError("fact set contains duplicate candidate/fact observations")
        return cls(observations)


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    rank: int
    score: int | None
    verdict: CandidateVerdict
    reasons: tuple[ReasonCode, ...]
    providers: tuple[ProviderIdentity, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "rank": self.rank,
            "score": self.score,
            "verdict": self.verdict.value,
            "reasons": [reason.value for reason in self.reasons],
            "providers": [provider.to_dict() for provider in self.providers],
        }


@dataclass(frozen=True)
class Decision:
    task_id: str
    outcome: FinalDecision
    selected_candidate_id: str | None
    selected_rank: int | None
    reason: ReasonCode
    evaluations: tuple[CandidateEvaluation, ...]
    decision_sha256: str

    @classmethod
    def create(  # noqa: PLR0913 - closed decision fields are clearer than a loose mapping
        cls,
        *,
        task_id: str,
        outcome: FinalDecision,
        selected_candidate_id: str | None,
        selected_rank: int | None,
        reason: ReasonCode,
        evaluations: Sequence[CandidateEvaluation],
    ) -> Decision:
        body = {
            "schema_version": DECISION_SCHEMA,
            "task_id": task_id,
            "outcome": outcome.value,
            "selected_candidate_id": selected_candidate_id,
            "selected_rank": selected_rank,
            "reason": reason.value,
            "evaluations": [item.to_dict() for item in evaluations],
        }
        digest = hashlib.sha256(canonical_json(body)).hexdigest()
        return cls(
            task_id,
            outcome,
            selected_candidate_id,
            selected_rank,
            reason,
            tuple(evaluations),
            digest,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DECISION_SCHEMA,
            "task_id": self.task_id,
            "outcome": self.outcome.value,
            "selected_candidate_id": self.selected_candidate_id,
            "selected_rank": self.selected_rank,
            "reason": self.reason.value,
            "evaluations": [item.to_dict() for item in self.evaluations],
            "decision_sha256": self.decision_sha256,
        }
