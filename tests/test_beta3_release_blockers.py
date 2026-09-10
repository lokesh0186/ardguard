from __future__ import annotations

import pytest

from ardguard.adapters.ard import parse_search_response
from ardguard.artifacts import ResolutionPolicy, URLArtifactResolver
from ardguard.constraints import default_evaluator_registry
from ardguard.kernel import (
    Fact,
    FactOperationalState,
    GenericFactSet,
    GenericTaskContract,
    KernelPolicy,
    ProviderTrust,
    Requirement,
    RequirementStatus,
    evaluate_kernel,
)
from ardguard.models import Candidate, ContractError
from ardguard.providers.generic import StaticGenericProvider


def candidate() -> Candidate:
    return Candidate("urn:air:example.org:tool:x", None, 1, None)


def task(fact_type: str = "deployment.region") -> GenericTaskContract:
    return GenericTaskContract(
        "task",
        (Requirement("requirement", fact_type, {"predicate": "equals", "expected": "EU"}),),
    )


def fact(
    fact_id: str = "fact-1",
    *,
    provider_id: str = "provider.example",
    provider_version: str = "1",
    fact_type: str = "deployment.region",
    value: object = "EU",
) -> Fact:
    return Fact(
        fact_id,
        candidate().resource_id,
        fact_type,
        provider_id,
        provider_version,
        FactOperationalState.AVAILABLE,
        value,
        provenance={"observation_sha256": "a" * 64},
    )


def policy(
    *,
    provider_id: str = "provider.example",
    provider_version: str = "1",
    fact_types: frozenset[str] = frozenset({"deployment.region"}),
    preestablished: bool = False,
) -> KernelPolicy:
    return KernelPolicy(
        provider_trust=(ProviderTrust(provider_id, provider_version, fact_types),),
        preestablished_fact_mode=preestablished,
    )


def evaluate_with(
    *, active_policy: KernelPolicy, facts: GenericFactSet | None = None, providers=()
):
    return evaluate_kernel(
        candidates=(candidate(),),
        task=task(),
        policy=active_policy,
        fact_set=facts,
        providers=providers,
        evaluators=default_evaluator_registry(("deployment.region",)),
    )


def test_preestablished_fact_mode_is_explicit_and_trust_bounded() -> None:
    supplied = GenericFactSet((fact(),))
    with pytest.raises(ContractError, match="explicit preestablished"):
        evaluate_with(active_policy=policy(), facts=supplied)
    with pytest.raises(ContractError, match="not authorized"):
        evaluate_with(
            active_policy=policy(provider_id="provider.other", preestablished=True),
            facts=supplied,
        )
    decision = evaluate_with(active_policy=policy(preestablished=True), facts=supplied)
    assert decision.selected_candidate_id == candidate().resource_id


def test_trusted_provider_cannot_exceed_fact_namespace() -> None:
    provider = StaticGenericProvider(
        "provider.example",
        "1",
        frozenset({"deployment.region"}),
        {candidate().resource_id: (fact(),)},
    )
    with pytest.raises(ContractError, match="not authorized"):
        evaluate_with(
            active_policy=policy(fact_types=frozenset({"deployment.other"})),
            providers=(provider,),
        )


@pytest.mark.parametrize("spoof", ["provider_id", "provider_version"])
def test_provider_identity_and_version_spoofing_fail_closed(spoof: str) -> None:
    emitted = fact(
        provider_id="provider.other" if spoof == "provider_id" else "provider.example",
        provider_version="2" if spoof == "provider_version" else "1",
    )
    provider = StaticGenericProvider(
        "provider.example",
        "1",
        frozenset({"deployment.region"}),
        {candidate().resource_id: (emitted,)},
    )
    with pytest.raises(ContractError, match="different provider"):
        evaluate_with(active_policy=policy(), providers=(provider,))


def test_multiple_identical_facts_are_retained_and_satisfy() -> None:
    supplied = GenericFactSet((fact("fact-1"), fact("fact-2", provider_id="provider.second")))
    active = KernelPolicy(
        provider_trust=(
            ProviderTrust("provider.example", "1", frozenset({"deployment.region"})),
            ProviderTrust("provider.second", "1", frozenset({"deployment.region"})),
        ),
        preestablished_fact_mode=True,
    )
    decision = evaluate_with(active_policy=active, facts=supplied)
    verdict = decision.evaluations[0].requirements[0]
    assert verdict.status is RequirementStatus.SATISFIED
    assert verdict.fact_ids == ("fact-1", "fact-2")


def test_conflicting_authorized_facts_are_not_majority_voted() -> None:
    supplied = GenericFactSet(
        (
            fact("fact-1"),
            fact("fact-2", value="US"),
            fact("fact-3"),
        )
    )
    decision = evaluate_with(active_policy=policy(preestablished=True), facts=supplied)
    assert decision.evaluations[0].requirements[0].status is RequirementStatus.INDETERMINATE
    assert decision.evaluations[0].requirements[0].reason_code == "fact.conflict"


def test_cross_candidate_fact_cannot_satisfy_requirement() -> None:
    wrong = Fact(
        "wrong",
        "urn:air:example.org:tool:other",
        "deployment.region",
        "provider.example",
        "1",
        FactOperationalState.AVAILABLE,
        "EU",
    )
    with pytest.raises(ContractError, match="unknown candidates"):
        evaluate_with(
            active_policy=policy(preestablished=True), facts=GenericFactSet((wrong,))
        )


@pytest.mark.parametrize(
    "provenance,extensions",
    [
        ({"verified": True}, {}),
        ({"authorization": "positive"}, {}),
        ({}, {"passed": True}),
        ({"retryable": "yes"}, {}),
    ],
)
def test_nonavailable_diagnostics_cannot_smuggle_positive_payloads(provenance, extensions) -> None:
    with pytest.raises(ContractError):
        Fact(
            "unavailable",
            candidate().resource_id,
            "deployment.region",
            "provider.example",
            "1",
            FactOperationalState.UNAVAILABLE,
            provenance=provenance,
            extensions=extensions,
        )


def test_safe_nonavailable_diagnostics_are_bounded() -> None:
    item = Fact(
        "unavailable",
        candidate().resource_id,
        "deployment.region",
        "provider.example",
        "1",
        FactOperationalState.UNAVAILABLE,
        provenance={
            "error_code": "TIMEOUT",
            "retryable": True,
            "diagnostic_sha256": "f" * 64,
        },
    )
    assert item.value is None


def test_provider_trust_namespace_is_bounded_and_versioned() -> None:
    trust = ProviderTrust("provider.example", "1", frozenset({"deployment.*"}))
    assert trust.authorizes("deployment.region")
    assert not trust.authorizes("deploymentx.region")


def test_nonavailable_fact_cannot_claim_evidence_identity() -> None:
    with pytest.raises(ContractError, match="evidence identity"):
        Fact(
            "unavailable",
            candidate().resource_id,
            "deployment.region",
            "provider.example",
            "1",
            FactOperationalState.UNAVAILABLE,
            evidence_identity="verified:evidence",
        )


@pytest.mark.parametrize(
    "url,hosts",
    [
        ("file:///etc/passwd", frozenset()),
        ("https://localhost/x", frozenset({"localhost"})),
        ("https://127.0.0.1/x", frozenset({"127.0.0.1"})),
        ("https://169.254.169.254/latest", frozenset({"169.254.169.254"})),
        ("https://[::1]/x", frozenset({"::1"})),
        ("https://user:pass@artifact.example/x", frozenset({"artifact.example"})),
    ],
)
def test_url_resolver_blocks_common_ssrf_targets(url: str, hosts: frozenset[str]) -> None:
    item = Candidate(candidate().resource_id, None, 1, None, original={"url": url})
    resolver = URLArtifactResolver(
        lambda url, timeout, limit, proxy: (b"x", url, None, "93.184.216.34")
    )
    with pytest.raises(ContractError):
        resolver.resolve(item, ResolutionPolicy(network_allowed=True, allowed_hosts=hosts))


def test_url_resolver_revalidates_redirect_peer_and_disables_environment_proxy() -> None:
    observed: list[bool] = []

    def fetch(url: str, timeout: float, limit: int, proxy: bool):
        del timeout, limit
        observed.append(proxy)
        return b"x", url, None, "10.0.0.1"

    item = Candidate(
        candidate().resource_id,
        None,
        1,
        None,
        original={"url": "https://artifact.example/x"},
    )
    with pytest.raises(ContractError, match="peer address"):
        URLArtifactResolver(fetch).resolve(
            item,
            ResolutionPolicy(
                network_allowed=True,
                allowed_hosts=frozenset({"artifact.example"}),
            ),
        )
    assert observed == [False]


def test_identifier_only_result_does_not_trigger_full_entry_or_network_resolution() -> None:
    sparse = parse_search_response(
        {"results": [{"identifier": "urn:air:example.org:tool:sparse"}]}
    )[0]
    called = False

    def fetch(url: str, timeout: float, limit: int, proxy: bool):
        nonlocal called
        called = True
        return b"", url, None, "93.184.216.34"

    with pytest.raises(ContractError, match="does not contain"):
        URLArtifactResolver(fetch).resolve(sparse, ResolutionPolicy(network_allowed=True))
    assert called is False
