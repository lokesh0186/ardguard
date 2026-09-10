"""Bounded ARD publisher identity fact provider."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from ardguard.kernel import (
    Fact,
    FactOperationalState,
    GenericTaskContract,
    ProviderContext,
    Requirement,
)
from ardguard.models import Candidate, ContractError, canonical_json

IdentityVerifier = Callable[[str, str | None, Candidate], str | None]
MIN_ARD_IDENTIFIER_PARTS = 5
MIN_DID_WEB_PARTS = 4


def publisher_from_identifier(identifier: str) -> str:
    parts = identifier.split(":")
    if len(parts) < MIN_ARD_IDENTIFIER_PARTS or parts[:2] != ["urn", "air"] or "." not in parts[2]:
        raise ContractError("candidate identifier does not contain an ARD publisher domain")
    return parts[2].casefold()


def identity_domain(identity: str, identity_type: str | None) -> str | None:
    kind = identity_type.casefold() if isinstance(identity_type, str) else urlsplit(identity).scheme
    parsed = urlsplit(identity)
    if kind == "https":
        return parsed.hostname.casefold() if parsed.hostname else None
    if kind == "spiffe":
        return parsed.netloc.casefold() or None
    if kind == "did":
        parts = identity.split(":")
        if len(parts) >= MIN_DID_WEB_PARTS and parts[1] == "web":
            return parts[2].replace("%3A", ":").casefold()
    return None


def static_identity_verifier(
    identity: str, identity_type: str | None, candidate: Candidate
) -> str | None:
    """Verify only deterministic syntax and publisher-domain alignment."""

    publisher = publisher_from_identifier(candidate.resource_id)
    return identity if identity_domain(identity, identity_type) == publisher else None


@dataclass(frozen=True)
class ARDPublisherIdentityProvider:
    verifier: IdentityVerifier = static_identity_verifier
    provider_id: str = "ardguard.ard-publisher-identity"
    provider_version: str = "1"
    supported_fact_types: frozenset[str] = frozenset({"identity.publisher_binding"})

    def collect(
        self,
        candidate: Candidate,
        task: GenericTaskContract,
        requirements: tuple[Requirement, ...],
        context: ProviderContext,
    ) -> Sequence[Fact]:
        del task, requirements, context
        manifest = candidate.original.get("trustManifest")
        if not isinstance(manifest, Mapping):
            return (self._unavailable(candidate, "trustManifest missing"),)
        identity = manifest.get("identity")
        identity_type = manifest.get("identityType")
        if not isinstance(identity, str) or not identity:
            return (self._unavailable(candidate, "identity missing"),)
        if identity_type is not None and not isinstance(identity_type, str):
            raise ContractError("trustManifest.identityType must be a string")
        verified = self.verifier(identity, identity_type, candidate)
        return (
            Fact(
                fact_id=self._fact_id(candidate),
                candidate_id=candidate.resource_id,
                fact_type="identity.publisher_binding",
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                state=FactOperationalState.AVAILABLE,
                value=verified is not None,
                provenance={
                    "publisher": publisher_from_identifier(candidate.resource_id),
                    "identity": identity,
                    "identity_type": identity_type,
                    "verification": "deterministic-static",
                },
                source_identity=candidate.source,
                evidence_identity=verified,
            ),
        )

    def _unavailable(self, candidate: Candidate, reason: str) -> Fact:
        return Fact(
            fact_id=self._fact_id(candidate),
            candidate_id=candidate.resource_id,
            fact_type="identity.publisher_binding",
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            state=FactOperationalState.INDETERMINATE,
            provenance={"provider_status": reason, "retryable": False},
            source_identity=candidate.source,
        )

    def _fact_id(self, candidate: Candidate) -> str:
        identity = hashlib.sha256(
            canonical_json(
                {
                    "candidate_id": candidate.resource_id,
                    "fact_type": "identity.publisher_binding",
                    "provider_id": self.provider_id,
                }
            )
        ).hexdigest()
        return f"identity:{identity}"
