"""Generic fact and evidence provider interfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from ardguard.artifacts import Artifact
from ardguard.kernel import (
    Fact,
    GenericFactProvider,
    GenericTaskContract,
    ProviderContext,
    Requirement,
)
from ardguard.models import Candidate


class EvidenceVerifier(Protocol):
    verifier_id: str
    verifier_version: str

    def verify(
        self,
        *,
        candidate: Candidate,
        artifact: Artifact,
        evidence: bytes,
        context: ProviderContext,
    ) -> Sequence[Fact]:
        """Establish separate evidence facts, never a final eligibility decision."""


class ArtifactCapabilityProvider(Protocol):
    provider_id: str
    provider_version: str
    protocol: str

    def inspect(
        self, candidate: Candidate, artifact: Artifact, context: ProviderContext
    ) -> Sequence[Fact]:
        """Return read-only capability facts without invoking the resource."""


@dataclass(frozen=True)
class StaticGenericProvider(GenericFactProvider):
    provider_id: str
    provider_version: str
    supported_fact_types: frozenset[str]
    facts: Mapping[str, tuple[Fact, ...]]

    def collect(
        self,
        candidate: Candidate,
        task: GenericTaskContract,
        requirements: tuple[Requirement, ...],
        context: ProviderContext,
    ) -> Sequence[Fact]:
        del task, requirements, context
        return self.facts.get(candidate.resource_id, ())


EVIDENCE_FACT_TYPES: frozenset[str] = frozenset(
    {
        "evidence.envelope_authentic",
        "evidence.signer_identity",
        "evidence.statement_integrity",
        "evidence.predicate_type",
        "evidence.subject_digest",
        "evidence.resource_association",
        "evidence.policy_sufficient",
        "evidence.verifier_available",
    }
)


def evidence_fact_schema() -> Mapping[str, Mapping[str, Any]]:
    return {
        "evidence.envelope_authentic": {
            "value_type": "boolean",
            "meaning": "cryptographic envelope validity",
        },
        "evidence.signer_identity": {"value_type": "string", "meaning": "verified signer identity"},
        "evidence.statement_integrity": {"value_type": "boolean", "meaning": "statement integrity"},
        "evidence.predicate_type": {"value_type": "string", "meaning": "verified predicate type"},
        "evidence.subject_digest": {
            "value_type": "sha256",
            "meaning": "verified statement subject",
        },
        "evidence.resource_association": {
            "value_type": "string",
            "meaning": "associated candidate identifier",
        },
        "evidence.policy_sufficient": {
            "value_type": "boolean",
            "meaning": "provider-observed proposition sufficiency",
        },
        "evidence.verifier_available": {
            "value_type": "boolean",
            "meaning": "verifier availability, not validity",
        },
    }
