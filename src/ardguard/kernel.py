"""Extensible eligibility kernel for versioned v2 contracts.

The kernel accepts facts, evaluates requirements, and performs deterministic
rank-preserving fallback. Providers can establish facts but cannot select or
invoke resources.
"""

from __future__ import annotations

import copy
import hashlib
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol

from ardguard._version import __version__
from ardguard.models import Candidate, ContractError, FinalDecision, SelectionMode, canonical_json

TASK_V2_SCHEMA = "ardguard.dev/task-contract/v2"
FACT_SET_V2_SCHEMA = "ardguard.dev/fact-set/v2"
POLICY_V2_SCHEMA = "ardguard.dev/policy/v2"
DECISION_V2_SCHEMA = "ardguard.dev/decision/v2"
TYPE_RE = re.compile(r"^[a-z][a-z0-9_.:/-]{0,199}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
FORBIDDEN_ASSERTIONS = frozenset({"eligible", "eligibility", "final_decision", "selected"})
FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "api_key",
        "private_key",
        "authorization",
        "auth_header",
        "cookie",
        "set-cookie",
    }
)
SAFE_DIAGNOSTIC_KEYS = frozenset(
    {"error_code", "retryable", "provider_status", "timestamp", "diagnostic_sha256", "error_type"}
)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return copy.deepcopy(value)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ContractError(f"{label} must be an object with string keys")
    return value


def _identifier(value: object, label: str, pattern: re.Pattern[str] = ID_RE) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ContractError(f"{label} is not a valid identifier")
    return value


def _reject_assertions(value: object, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in FORBIDDEN_ASSERTIONS:
                raise ContractError(f"{label} cannot assert final eligibility or selection")
            _reject_assertions(item, label)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_assertions(item, label)


def _reject_secrets(value: object, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in FORBIDDEN_SECRET_KEYS:
                raise ContractError(f"{label} cannot carry secret material")
            _reject_secrets(item, label)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_secrets(item, label)


class RequirementMode(str, Enum):
    MANDATORY = "MANDATORY"
    ADVISORY = "ADVISORY"


class UnknownPolicy(str, Enum):
    INDETERMINATE = "INDETERMINATE"
    UNSATISFIED = "UNSATISFIED"
    ERROR = "ERROR"


class FactOperationalState(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INDETERMINATE = "INDETERMINATE"
    OPERATIONAL_ERROR = "OPERATIONAL_ERROR"


class RequirementStatus(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    INDETERMINATE = "INDETERMINATE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    requirement_type: str
    parameters: Mapping[str, Any]
    mode: RequirementMode = RequirementMode.MANDATORY
    unknown_policy: UnknownPolicy = UnknownPolicy.INDETERMINATE
    namespace: str | None = None
    schema_identity: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.requirement_id, "requirement_id")
        _identifier(self.requirement_type, "requirement_type", TYPE_RE)
        params = _object(self.parameters, "requirement.parameters")
        _reject_assertions(params, "requirement.parameters")
        if not isinstance(self.mode, RequirementMode):
            raise ContractError("requirement.mode must be a RequirementMode")
        if not isinstance(self.unknown_policy, UnknownPolicy):
            raise ContractError("requirement.unknown_policy must be an UnknownPolicy")
        for label, value in (
            ("namespace", self.namespace),
            ("schema_identity", self.schema_identity),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ContractError(f"requirement.{label} must be a non-empty string")
        object.__setattr__(self, "parameters", _freeze(params))

    @classmethod
    def from_mapping(cls, value: object) -> Requirement:
        row = _object(value, "requirement")
        allowed = {
            "requirement_id",
            "requirement_type",
            "parameters",
            "mode",
            "unknown_policy",
            "namespace",
            "schema_identity",
        }
        unknown = sorted(set(row) - allowed)
        if unknown:
            raise ContractError(f"requirement contains unsupported fields: {', '.join(unknown)}")
        try:
            mode = RequirementMode(row.get("mode", RequirementMode.MANDATORY.value))
            unknown_policy = UnknownPolicy(
                row.get("unknown_policy", UnknownPolicy.INDETERMINATE.value)
            )
        except ValueError as exc:
            raise ContractError(f"invalid requirement enum: {exc}") from exc
        return cls(
            _identifier(row.get("requirement_id"), "requirement_id"),
            _identifier(row.get("requirement_type"), "requirement_type", TYPE_RE),
            dict(_object(row.get("parameters", {}), "requirement.parameters")),
            mode,
            unknown_policy,
            row.get("namespace"),
            row.get("schema_identity"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_type": self.requirement_type,
            "parameters": _plain(self.parameters),
            "mode": self.mode.value,
            "unknown_policy": self.unknown_policy.value,
            "namespace": self.namespace,
            "schema_identity": self.schema_identity,
        }


@dataclass(frozen=True)
class GenericTaskContract:
    task_id: str
    requirements: tuple[Requirement, ...]
    operation: str | None = None
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _identifier(self.task_id, "task.task_id")
        if not self.requirements:
            raise ContractError("task must contain at least one requirement")
        ids = [item.requirement_id for item in self.requirements]
        if len(ids) != len(set(ids)):
            raise ContractError("task contains duplicate requirement IDs")
        if self.operation is not None and (
            not isinstance(self.operation, str) or not self.operation
        ):
            raise ContractError("task.operation must be a non-empty string")
        context = _object(self.context, "task.context")
        _reject_assertions(context, "task.context")
        object.__setattr__(self, "context", _freeze(context))

    @classmethod
    def from_mapping(cls, value: object) -> GenericTaskContract:
        row = _object(value, "task")
        allowed = {"schema_version", "task_id", "operation", "requirements", "context"}
        unknown = sorted(set(row) - allowed)
        if unknown:
            raise ContractError(f"task contains unsupported fields: {', '.join(unknown)}")
        if row.get("schema_version") != TASK_V2_SCHEMA:
            raise ContractError(f"task.schema_version must be {TASK_V2_SCHEMA}")
        values = row.get("requirements")
        if not isinstance(values, list):
            raise ContractError("task.requirements must be an array")
        return cls(
            _identifier(row.get("task_id"), "task.task_id"),
            tuple(Requirement.from_mapping(item) for item in values),
            row.get("operation"),
            dict(_object(row.get("context", {}), "task.context")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TASK_V2_SCHEMA,
            "task_id": self.task_id,
            "operation": self.operation,
            "requirements": [item.to_dict() for item in self.requirements],
            "context": _plain(self.context),
        }


@dataclass(frozen=True)
class Fact:
    fact_id: str
    candidate_id: str
    fact_type: str
    provider_id: str
    provider_version: str
    state: FactOperationalState
    value: Any = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    source_identity: str | None = None
    evidence_identity: str | None = None
    observed_at: str | None = None
    expires_at: str | None = None
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:  # noqa: PLR0912,PLR0915 - closed fact validation
        _identifier(self.fact_id, "fact.fact_id")
        _identifier(self.candidate_id, "fact.candidate_id")
        _identifier(self.fact_type, "fact.fact_type", TYPE_RE)
        _identifier(self.provider_id, "fact.provider_id", TYPE_RE)
        if not isinstance(self.provider_version, str) or not self.provider_version:
            raise ContractError("fact.provider_version must be a non-empty string")
        if not isinstance(self.state, FactOperationalState):
            raise ContractError("fact.state must be a FactOperationalState")
        if self.state is not FactOperationalState.AVAILABLE and self.value is not None:
            raise ContractError("non-available facts cannot carry a value")
        _reject_assertions(self.value, "fact.value")
        _reject_secrets(self.value, "fact.value")
        provenance = _object(self.provenance, "fact.provenance")
        extensions = _object(self.extensions, "fact.extensions")
        _reject_assertions(provenance, "fact.provenance")
        _reject_assertions(extensions, "fact.extensions")
        _reject_secrets(provenance, "fact.provenance")
        _reject_secrets(extensions, "fact.extensions")
        if self.state is not FactOperationalState.AVAILABLE:
            unknown_diagnostics = sorted(set(provenance) - SAFE_DIAGNOSTIC_KEYS)
            if unknown_diagnostics:
                raise ContractError(
                    "non-available fact provenance contains unsupported diagnostic fields: "
                    + ", ".join(unknown_diagnostics)
                )
            if extensions:
                raise ContractError("non-available facts cannot carry extension payloads")
            retryable = provenance.get("retryable")
            if retryable is not None and not isinstance(retryable, bool):
                raise ContractError("diagnostic retryable must be a boolean")
            diagnostic_hash = provenance.get("diagnostic_sha256")
            if diagnostic_hash is not None and (
                not isinstance(diagnostic_hash, str)
                or re.fullmatch(r"[0-9a-f]{64}", diagnostic_hash) is None
            ):
                raise ContractError("diagnostic_sha256 must be a lowercase SHA-256 digest")
            for key in {"error_code", "provider_status", "error_type"} & set(provenance):
                if not isinstance(provenance[key], str) or not provenance[key]:
                    raise ContractError(f"diagnostic {key} must be a non-empty string")
            diagnostic_time = provenance.get("timestamp")
            if diagnostic_time is not None:
                if not isinstance(diagnostic_time, str):
                    raise ContractError("diagnostic timestamp must be an RFC3339 string")
                try:
                    parsed_diagnostic_time = datetime.fromisoformat(
                        diagnostic_time.replace("Z", "+00:00")
                    )
                except ValueError as exc:
                    raise ContractError("diagnostic timestamp must be an RFC3339 string") from exc
                if parsed_diagnostic_time.tzinfo is None:
                    raise ContractError("diagnostic timestamp must include a timezone")
            if self.evidence_identity is not None:
                raise ContractError("non-available facts cannot claim an evidence identity")
        for label, value in (
            ("source_identity", self.source_identity),
            ("evidence_identity", self.evidence_identity),
            ("observed_at", self.observed_at),
            ("expires_at", self.expires_at),
        ):
            if value is not None and (not isinstance(value, str) or not value):
                raise ContractError(f"fact.{label} must be a non-empty string")
        for label, value in (("observed_at", self.observed_at), ("expires_at", self.expires_at)):
            if value is not None:
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ContractError(f"fact.{label} must be an RFC3339 timestamp") from exc
                if parsed.tzinfo is None:
                    raise ContractError(f"fact.{label} must include a timezone")
        object.__setattr__(self, "value", _freeze(self.value))
        object.__setattr__(self, "provenance", _freeze(provenance))
        object.__setattr__(self, "extensions", _freeze(extensions))

    @classmethod
    def from_mapping(cls, value: object) -> Fact:
        row = _object(value, "fact")
        allowed = {
            "fact_id",
            "candidate_id",
            "fact_type",
            "provider_id",
            "provider_version",
            "state",
            "value",
            "provenance",
            "source_identity",
            "evidence_identity",
            "observed_at",
            "expires_at",
            "extensions",
        }
        unknown = sorted(set(row) - allowed)
        if unknown:
            raise ContractError(f"fact contains unsupported fields: {', '.join(unknown)}")
        try:
            state = FactOperationalState(row.get("state"))
        except ValueError as exc:
            raise ContractError(f"invalid fact state: {exc}") from exc
        return cls(
            _identifier(row.get("fact_id"), "fact.fact_id"),
            _identifier(row.get("candidate_id"), "fact.candidate_id"),
            _identifier(row.get("fact_type"), "fact.fact_type", TYPE_RE),
            _identifier(row.get("provider_id"), "fact.provider_id", TYPE_RE),
            str(row.get("provider_version", "")),
            state,
            copy.deepcopy(row.get("value")),
            dict(_object(row.get("provenance", {}), "fact.provenance")),
            row.get("source_identity"),
            row.get("evidence_identity"),
            row.get("observed_at"),
            row.get("expires_at"),
            dict(_object(row.get("extensions", {}), "fact.extensions")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "candidate_id": self.candidate_id,
            "fact_type": self.fact_type,
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "state": self.state.value,
            "value": _plain(self.value),
            "provenance": _plain(self.provenance),
            "source_identity": self.source_identity,
            "evidence_identity": self.evidence_identity,
            "observed_at": self.observed_at,
            "expires_at": self.expires_at,
            "extensions": _plain(self.extensions),
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical_json(self.to_dict())).hexdigest()


@dataclass(frozen=True)
class GenericFactSet:
    facts: tuple[Fact, ...]

    def __post_init__(self) -> None:
        ids = [item.fact_id for item in self.facts]
        if len(ids) != len(set(ids)):
            raise ContractError("fact set contains duplicate fact IDs")

    @classmethod
    def from_mapping(cls, value: object) -> GenericFactSet:
        row = _object(value, "fact set")
        if set(row) != {"schema_version", "facts"}:
            raise ContractError("v2 fact set accepts only schema_version and facts")
        if row.get("schema_version") != FACT_SET_V2_SCHEMA:
            raise ContractError(f"fact set.schema_version must be {FACT_SET_V2_SCHEMA}")
        values = row.get("facts")
        if not isinstance(values, list):
            raise ContractError("fact set.facts must be an array")
        return cls(tuple(Fact.from_mapping(item) for item in values))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": FACT_SET_V2_SCHEMA,
            "facts": [item.to_dict() for item in self.facts],
        }


@dataclass(frozen=True)
class ProviderTrust:
    """Exact provider identity and bounded fact namespaces authorized by policy."""

    provider_id: str
    provider_version: str
    fact_types: frozenset[str]

    def __post_init__(self) -> None:
        _identifier(self.provider_id, "provider trust provider_id", TYPE_RE)
        if not isinstance(self.provider_version, str) or not self.provider_version:
            raise ContractError("provider trust provider_version must be a non-empty string")
        if not isinstance(self.fact_types, frozenset) or not self.fact_types:
            raise ContractError("provider trust fact_types must be a non-empty frozenset")
        for fact_type in self.fact_types:
            if fact_type.endswith(".*"):
                _identifier(fact_type[:-2], "provider trust fact namespace", TYPE_RE)
            else:
                _identifier(fact_type, "provider trust fact type", TYPE_RE)

    @classmethod
    def from_mapping(cls, value: object) -> ProviderTrust:
        row = _object(value, "provider trust")
        if set(row) != {"provider_id", "provider_version", "fact_types"}:
            raise ContractError(
                "provider trust requires only provider_id, provider_version, and fact_types"
            )
        fact_types = row.get("fact_types")
        if not isinstance(fact_types, list):
            raise ContractError("provider trust fact_types must be an array")
        return cls(
            _identifier(row.get("provider_id"), "provider trust provider_id", TYPE_RE),
            str(row.get("provider_version", "")),
            frozenset(fact_types),
        )

    def authorizes(self, fact_type: str) -> bool:
        return fact_type in self.fact_types or any(
            item.endswith(".*") and fact_type.startswith(item[:-1]) for item in self.fact_types
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "fact_types": sorted(self.fact_types),
        }


@dataclass(frozen=True)
class KernelPolicy:
    selection_mode: SelectionMode = SelectionMode.FALLBACK
    indeterminate_action: FinalDecision = FinalDecision.DEFER
    operational_error_action: FinalDecision = FinalDecision.ERROR
    provider_trust: tuple[ProviderTrust, ...] = ()
    preestablished_fact_mode: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.selection_mode, SelectionMode):
            raise ContractError("selection_mode must be a SelectionMode")
        if self.indeterminate_action not in {FinalDecision.DEFER, FinalDecision.ABSTAIN}:
            raise ContractError("indeterminate_action must be DEFER or ABSTAIN")
        if self.operational_error_action not in {
            FinalDecision.ERROR,
            FinalDecision.DEFER,
            FinalDecision.ABSTAIN,
        }:
            raise ContractError("operational_error_action must be ERROR, DEFER, or ABSTAIN")
        if not isinstance(self.preestablished_fact_mode, bool):
            raise ContractError("preestablished_fact_mode must be a boolean")
        identities = [(item.provider_id, item.provider_version) for item in self.provider_trust]
        if len(identities) != len(set(identities)):
            raise ContractError("policy contains duplicate provider trust identities")

    @classmethod
    def from_mapping(cls, value: object) -> KernelPolicy:
        row = _object(value, "policy")
        if set(row) - {
            "schema_version",
            "selection_mode",
            "indeterminate_action",
            "operational_error_action",
            "provider_trust",
            "preestablished_fact_mode",
        }:
            raise ContractError("v2 policy contains unsupported fields")
        if row.get("schema_version") != POLICY_V2_SCHEMA:
            raise ContractError(f"policy.schema_version must be {POLICY_V2_SCHEMA}")
        try:
            policy = cls(
                SelectionMode(row.get("selection_mode", SelectionMode.FALLBACK.value)),
                FinalDecision(row.get("indeterminate_action", FinalDecision.DEFER.value)),
                FinalDecision(row.get("operational_error_action", FinalDecision.ERROR.value)),
                tuple(
                    ProviderTrust.from_mapping(item)
                    for item in row.get("provider_trust", [])
                ),
                row.get("preestablished_fact_mode", False),
            )
        except ValueError as exc:
            raise ContractError(f"invalid policy enum: {exc}") from exc
        return policy

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": POLICY_V2_SCHEMA,
            "selection_mode": self.selection_mode.value,
            "indeterminate_action": self.indeterminate_action.value,
            "operational_error_action": self.operational_error_action.value,
            "provider_trust": [item.to_dict() for item in self.provider_trust],
            "preestablished_fact_mode": self.preestablished_fact_mode,
        }

    def authorizes(self, provider_id: str, provider_version: str, fact_type: str) -> bool:
        return any(
            item.provider_id == provider_id
            and item.provider_version == provider_version
            and item.authorizes(fact_type)
            for item in self.provider_trust
        )


@dataclass(frozen=True)
class ProviderContext:
    network_allowed: bool = False
    deadline_seconds: float | None = None
    values: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.network_allowed, bool):
            raise ContractError("provider context network_allowed must be a boolean")
        if self.deadline_seconds is not None and (
            isinstance(self.deadline_seconds, bool)
            or not isinstance(self.deadline_seconds, (int, float))
            or self.deadline_seconds <= 0
        ):
            raise ContractError("provider context deadline_seconds must be positive")
        values = _object(self.values, "provider context values")
        _reject_assertions(values, "provider context values")
        _reject_secrets(values, "provider context values")
        object.__setattr__(self, "values", _freeze(values))


class GenericFactProvider(Protocol):
    provider_id: str
    provider_version: str
    supported_fact_types: frozenset[str]

    def collect(
        self,
        candidate: Candidate,
        task: GenericTaskContract,
        requirements: tuple[Requirement, ...],
        context: ProviderContext,
    ) -> Sequence[Fact]: ...


@dataclass(frozen=True)
class RequirementVerdict:
    requirement_id: str
    status: RequirementStatus
    reason_code: str
    fact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.requirement_id, "verdict.requirement_id")
        if not isinstance(self.status, RequirementStatus):
            raise ContractError("verdict.status must be a RequirementStatus")
        _identifier(self.reason_code, "verdict.reason_code", TYPE_RE)
        if not isinstance(self.fact_ids, tuple):
            raise ContractError("verdict.fact_ids must be a tuple")
        for fact_id in self.fact_ids:
            _identifier(fact_id, "verdict.fact_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "fact_ids": list(self.fact_ids),
        }


RequirementEvaluator = Callable[
    [Requirement, tuple[Fact, ...], Mapping[str, Any]], RequirementVerdict
]


def requirement_fact_types(requirement: Requirement) -> frozenset[str]:
    configured = requirement.parameters.get("fact_types")
    if configured is None:
        single = requirement.parameters.get("fact_type", requirement.requirement_type)
        configured = (single,)
    if not isinstance(configured, tuple) or not configured:
        raise ContractError("requirement fact_types must be a non-empty array")
    result = frozenset(_identifier(item, "requirement fact type", TYPE_RE) for item in configured)
    if len(result) != len(configured):
        raise ContractError("requirement fact_types contains duplicates")
    return result


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, RequirementEvaluator] = {}

    def register(self, requirement_type: str, evaluator: RequirementEvaluator) -> None:
        _identifier(requirement_type, "requirement_type", TYPE_RE)
        if requirement_type in self._evaluators:
            raise ContractError(f"duplicate requirement evaluator: {requirement_type}")
        self._evaluators[requirement_type] = evaluator

    def evaluate(
        self, requirement: Requirement, facts: tuple[Fact, ...], context: Mapping[str, Any]
    ) -> RequirementVerdict:
        evaluator = self._evaluators.get(requirement.requirement_type)
        if evaluator is None:
            return RequirementVerdict(
                requirement.requirement_id,
                RequirementStatus.INDETERMINATE,
                "requirement.evaluator_unavailable",
            )
        verdict = evaluator(requirement, facts, context)
        if not isinstance(verdict, RequirementVerdict):
            raise ContractError("requirement evaluator returned an invalid verdict")
        if verdict.requirement_id != requirement.requirement_id:
            raise ContractError("requirement evaluator returned a verdict for another requirement")
        return verdict


class ProviderRegistry:
    def __init__(self, providers: Iterable[GenericFactProvider] = ()) -> None:
        self._providers: dict[str, GenericFactProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: GenericFactProvider) -> None:
        provider_id = _identifier(provider.provider_id, "provider_id", TYPE_RE)
        if provider_id in self._providers:
            raise ContractError(f"duplicate provider ID: {provider_id}")
        if not isinstance(provider.provider_version, str) or not provider.provider_version:
            raise ContractError("provider_version must be a non-empty string")
        if (
            not isinstance(provider.supported_fact_types, frozenset)
            or not provider.supported_fact_types
        ):
            raise ContractError("provider supported_fact_types must be a non-empty frozenset")
        for fact_type in provider.supported_fact_types:
            _identifier(fact_type, "supported_fact_type", TYPE_RE)
        self._providers[provider_id] = provider

    @property
    def providers(self) -> tuple[GenericFactProvider, ...]:
        return tuple(self._providers[key] for key in sorted(self._providers))

    def describe(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "provider_id": item.provider_id,
                "provider_version": item.provider_version,
                "fact_types": sorted(item.supported_fact_types),
            }
            for item in self.providers
        )


@dataclass(frozen=True)
class GenericCandidateEvaluation:
    candidate_id: str
    rank: int
    score: int | None
    status: RequirementStatus
    requirements: tuple[RequirementVerdict, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "rank": self.rank,
            "score": self.score,
            "status": self.status.value,
            "requirements": [item.to_dict() for item in self.requirements],
        }


@dataclass(frozen=True)
class GenericDecision:
    task_id: str
    outcome: FinalDecision
    selected_candidate_id: str | None
    selected_rank: int | None
    reason_code: str
    evaluations: tuple[GenericCandidateEvaluation, ...]
    receipt: Mapping[str, Any]
    decision_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DECISION_V2_SCHEMA,
            "task_id": self.task_id,
            "outcome": self.outcome.value,
            "selected_candidate_id": self.selected_candidate_id,
            "selected_rank": self.selected_rank,
            "reason_code": self.reason_code,
            "evaluations": [item.to_dict() for item in self.evaluations],
            "receipt": _plain(self.receipt),
            "decision_sha256": self.decision_sha256,
        }


def _compose(
    verdicts: tuple[RequirementVerdict, ...], requirements: tuple[Requirement, ...]
) -> RequirementStatus:
    required = {
        item.requirement_id: item for item in requirements if item.mode is RequirementMode.MANDATORY
    }
    statuses = [item.status for item in verdicts if item.requirement_id in required]
    if RequirementStatus.ERROR in statuses:
        return RequirementStatus.ERROR
    if RequirementStatus.UNSATISFIED in statuses:
        return RequirementStatus.UNSATISFIED
    if RequirementStatus.INDETERMINATE in statuses:
        return RequirementStatus.INDETERMINATE
    return RequirementStatus.SATISFIED


def _apply_unknown_policy(
    requirement: Requirement, verdict: RequirementVerdict
) -> RequirementVerdict:
    if verdict.status is not RequirementStatus.INDETERMINATE:
        return verdict
    mapped = {
        UnknownPolicy.INDETERMINATE: RequirementStatus.INDETERMINATE,
        UnknownPolicy.UNSATISFIED: RequirementStatus.UNSATISFIED,
        UnknownPolicy.ERROR: RequirementStatus.ERROR,
    }[requirement.unknown_policy]
    return RequirementVerdict(
        verdict.requirement_id,
        mapped,
        verdict.reason_code,
        verdict.fact_ids,
    )


def evaluate_kernel(  # noqa: PLR0912,PLR0913,PLR0915 - explicit security pipeline
    *,
    candidates: Sequence[Candidate],
    task: GenericTaskContract,
    policy: KernelPolicy,
    fact_set: GenericFactSet | None = None,
    providers: Iterable[GenericFactProvider] = (),
    evaluators: EvaluatorRegistry,
    provider_context: ProviderContext | None = None,
) -> GenericDecision:
    """Evaluate v2 facts and requirements without invoking any resource."""

    if not candidates:
        raise ContractError("at least one candidate is required")
    ids = [item.resource_id for item in candidates]
    if len(ids) != len(set(ids)):
        raise ContractError("candidate identifiers must be unique")
    ranks = [item.rank for item in candidates]
    if len(ranks) != len(set(ranks)):
        raise ContractError("candidate ranks must be unique")
    provider_registry = ProviderRegistry(providers)
    supplied_fact_set = fact_set or GenericFactSet(())
    if supplied_fact_set.facts and not policy.preestablished_fact_mode:
        raise ContractError(
            "pre-established facts require explicit preestablished_fact_mode"
        )
    for fact in supplied_fact_set.facts:
        if not policy.authorizes(fact.provider_id, fact.provider_version, fact.fact_type):
            raise ContractError("pre-established fact provider is not authorized by policy")
    active_context = provider_context or ProviderContext()
    collected = list(supplied_fact_set.facts)
    for provider in provider_registry.providers:
        relevant = tuple(
            requirement
            for requirement in task.requirements
            if requirement_fact_types(requirement) & provider.supported_fact_types
        )
        if not relevant:
            continue
        required_types = {
            fact_type
            for requirement in relevant
            for fact_type in requirement_fact_types(requirement)
            if fact_type in provider.supported_fact_types
        }
        unauthorized_types = sorted(
            fact_type
            for fact_type in required_types
            if not policy.authorizes(provider.provider_id, provider.provider_version, fact_type)
        )
        if unauthorized_types:
            raise ContractError(
                "provider is not authorized for required fact types: "
                + ", ".join(unauthorized_types)
            )
        for candidate in sorted(candidates, key=lambda item: (item.rank, item.resource_id)):
            try:
                supplied = provider.collect(candidate, task, relevant, active_context)
                if not isinstance(supplied, Sequence):
                    raise TypeError("provider result must be a sequence")
            except Exception as exc:  # provider failures become explicit facts
                failed_types = sorted(
                    {
                        fact_type
                        for requirement in relevant
                        for fact_type in requirement_fact_types(requirement)
                        if fact_type in provider.supported_fact_types
                    }
                )
                for fact_type in failed_types:
                    error_identity = hashlib.sha256(
                        canonical_json(
                            {
                                "candidate_id": candidate.resource_id,
                                "fact_type": fact_type,
                                "provider_id": provider.provider_id,
                            }
                        )
                    ).hexdigest()
                    collected.append(
                        Fact(
                            fact_id=f"provider-error:{error_identity}",
                            candidate_id=candidate.resource_id,
                            fact_type=fact_type,
                            provider_id=provider.provider_id,
                            provider_version=provider.provider_version,
                            state=FactOperationalState.OPERATIONAL_ERROR,
                            provenance={"error_type": type(exc).__name__},
                        )
                    )
                continue
            for fact in supplied:
                if not isinstance(fact, Fact):
                    raise ContractError("provider returned an object that is not a Fact")
                if fact.provider_id != provider.provider_id:
                    raise ContractError("provider returned a fact with a different provider ID")
                if fact.provider_version != provider.provider_version:
                    raise ContractError(
                        "provider returned a fact with a different provider version"
                    )
                if fact.candidate_id != candidate.resource_id:
                    raise ContractError("provider returned a fact for a different candidate")
                if fact.fact_type not in provider.supported_fact_types:
                    raise ContractError("provider returned an unsupported fact type")
                if not policy.authorizes(
                    fact.provider_id, fact.provider_version, fact.fact_type
                ):
                    raise ContractError("provider returned a fact outside its authorized namespace")
                collected.append(fact)
    facts = GenericFactSet(tuple(collected))
    candidate_ids = set(ids)
    unknown = sorted({item.candidate_id for item in facts.facts} - candidate_ids)
    if unknown:
        raise ContractError(f"facts reference unknown candidates: {', '.join(unknown)}")
    evaluations: list[GenericCandidateEvaluation] = []
    for candidate in candidates:
        candidate_facts = tuple(
            item for item in facts.facts if item.candidate_id == candidate.resource_id
        )
        evaluation_context = dict(task.context)
        evaluation_context["candidate_id"] = candidate.resource_id
        digest_field = next(
            (
                item.parameters.get("artifact_digest_field")
                for item in task.requirements
                if item.requirement_type in {"evidence", "evidence.applicable"}
            ),
            None,
        )
        if isinstance(digest_field, str):
            evaluation_context["candidate_artifact_sha256"] = candidate.artifact_sha256(
                digest_field
            )
        verdicts = tuple(
            _apply_unknown_policy(
                requirement,
                evaluators.evaluate(requirement, candidate_facts, evaluation_context),
            )
            for requirement in task.requirements
        )
        evaluations.append(
            GenericCandidateEvaluation(
                candidate.resource_id,
                candidate.rank,
                candidate.score,
                _compose(verdicts, task.requirements),
                verdicts,
            )
        )
    ordered = tuple(sorted(evaluations, key=lambda item: (item.rank, item.candidate_id)))
    selectable = ordered[:1] if policy.selection_mode is SelectionMode.TOP_RANKED_ONLY else ordered
    selected = next(
        (item for item in selectable if item.status is RequirementStatus.SATISFIED), None
    )
    if selected is not None:
        outcome = FinalDecision.SELECT
        reason = (
            "selection.top_ranked_eligible"
            if selected == ordered[0]
            else "selection.fallback_to_lower_ranked_eligible"
        )
    elif any(item.status is RequirementStatus.ERROR for item in ordered):
        outcome = policy.operational_error_action
        reason = "selection.engine_error"
    elif any(item.status is RequirementStatus.INDETERMINATE for item in ordered):
        outcome = policy.indeterminate_action
        reason = "selection.eligibility_indeterminate"
    else:
        outcome = FinalDecision.ABSTAIN
        reason = "selection.no_eligible_candidate"
    candidate_body = [
        {
            "resource_id": item.resource_id,
            "rank": item.rank,
            "score": item.score,
            "source": item.source,
        }
        for item in sorted(candidates, key=lambda row: (row.rank, row.resource_id))
    ]
    fact_provider_identities = {(item.provider_id, item.provider_version) for item in facts.facts}
    configured_provider_identities = {
        (item.provider_id, item.provider_version) for item in provider_registry.providers
    }
    receipt_body = {
        "task_sha256": hashlib.sha256(canonical_json(task.to_dict())).hexdigest(),
        "candidate_set_sha256": hashlib.sha256(canonical_json(candidate_body)).hexdigest(),
        "policy_sha256": hashlib.sha256(canonical_json(policy.to_dict())).hexdigest(),
        "provider_identities": [
            {"provider_id": provider_id, "provider_version": version}
            for provider_id, version in sorted(
                fact_provider_identities | configured_provider_identities
            )
        ],
        "fact_sha256": [item.sha256 for item in sorted(facts.facts, key=lambda row: row.fact_id)],
        "requirement_verdicts": [
            verdict.to_dict() for evaluation in ordered for verdict in evaluation.requirements
        ],
        "selected_candidate_id": selected.candidate_id if selected else None,
        "software_version": __version__,
    }
    receipt = {
        **receipt_body,
        "receipt_sha256": hashlib.sha256(canonical_json(receipt_body)).hexdigest(),
    }
    body = {
        "schema_version": DECISION_V2_SCHEMA,
        "task_id": task.task_id,
        "outcome": outcome.value,
        "selected_candidate_id": selected.candidate_id if selected else None,
        "selected_rank": selected.rank if selected else None,
        "reason_code": reason,
        "evaluations": [item.to_dict() for item in ordered],
        "receipt": receipt,
    }
    return GenericDecision(
        task.task_id,
        outcome,
        selected.candidate_id if selected else None,
        selected.rank if selected else None,
        reason,
        ordered,
        _freeze(receipt),
        hashlib.sha256(canonical_json(body)).hexdigest(),
    )
