from __future__ import annotations

import pytest

from ardguard.kernel import (
    Fact,
    FactOperationalState,
    GenericTaskContract,
    ProviderContext,
    Requirement,
)
from ardguard.models import Candidate, ContractError
from ardguard.providers.identity import (
    ARDPublisherIdentityProvider,
    identity_domain,
    publisher_from_identifier,
)


def candidate(identity: str, identity_type: str = "spiffe") -> Candidate:
    original = {
        "identifier": "urn:air:example.org:tool:reader",
        "displayName": "Reader",
        "type": "application/json",
        "url": "https://example.org/reader.json",
        "source": "https://registry.example.org/",
        "score": 90,
        "trustManifest": {"identity": identity, "identityType": identity_type},
    }
    return Candidate(original["identifier"], original["source"], 1, 90, original=original)


def task() -> GenericTaskContract:
    return GenericTaskContract(
        "t",
        (
            Requirement(
                "publisher",
                "identity.publisher_binding",
                {"predicate": "equals", "expected": True},
            ),
        ),
    )


def test_static_publisher_identity_pack_aligns_spiffe_and_ard_publisher() -> None:
    item = candidate("spiffe://example.org/workload/reader")
    fact = ARDPublisherIdentityProvider().collect(
        item, task(), task().requirements, ProviderContext()
    )[0]
    assert fact.value is True
    assert fact.evidence_identity == "spiffe://example.org/workload/reader"
    assert publisher_from_identifier(item.resource_id) == "example.org"
    assert identity_domain("did:web:example.org:reader", "did") == "example.org"


def test_identity_mismatch_is_observation_not_self_asserted_eligibility() -> None:
    item = candidate("spiffe://other.example/workload/reader")
    fact = ARDPublisherIdentityProvider().collect(
        item, task(), task().requirements, ProviderContext()
    )[0]
    assert fact.value is False
    assert fact.evidence_identity is None


def test_identity_pack_missing_and_malformed_states() -> None:
    base = candidate("https://example.org/publisher", "https")
    no_manifest = Candidate(base.resource_id, base.source, 1, 90, original={})
    fact = ARDPublisherIdentityProvider().collect(
        no_manifest, task(), task().requirements, ProviderContext()
    )[0]
    assert fact.state is FactOperationalState.INDETERMINATE
    malformed = dict(base.original)
    malformed["trustManifest"] = {"identity": "https://example.org", "identityType": 1}
    with pytest.raises(ContractError, match="identityType"):
        ARDPublisherIdentityProvider().collect(
            Candidate(base.resource_id, base.source, 1, 90, original=malformed),
            task(),
            task().requirements,
            ProviderContext(),
        )


def test_identity_domain_formats_and_invalid_ard_identifier() -> None:
    assert identity_domain("https://example.org/id", "https") == "example.org"
    assert identity_domain("urn:other:identity", None) is None
    with pytest.raises(ContractError, match="publisher domain"):
        publisher_from_identifier("urn:air:localhost:tool:x")


@pytest.mark.parametrize("secret_key", ["token", "password", "api_key", "private_key"])
def test_fact_rejects_secret_material(secret_key: str) -> None:
    with pytest.raises(ContractError, match="secret material"):
        Fact(
            "f",
            "candidate",
            "access.credential_available",
            "provider.access",
            "1",
            FactOperationalState.AVAILABLE,
            {secret_key: "do-not-store"},
        )


def test_access_fact_carries_category_availability_without_secret() -> None:
    fact = Fact(
        "access",
        "candidate",
        "access.credential_available",
        "provider.access",
        "1",
        FactOperationalState.AVAILABLE,
        {"credential_category": "oauth", "available": True},
        provenance={"source": "caller-capability-inventory"},
    )
    assert fact.value["available"] is True
