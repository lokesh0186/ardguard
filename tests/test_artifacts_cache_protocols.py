from __future__ import annotations

import pytest

from ardguard.adapters.protocols import (
    parse_a2a_agent_card,
    parse_mcp_tools,
    parse_openapi,
    parse_skill_manifest,
)
from ardguard.artifacts import InlineArtifactResolver, ResolutionPolicy, URLArtifactResolver
from ardguard.cache import CacheKey, FactCache
from ardguard.kernel import (
    Fact,
    FactOperationalState,
    GenericTaskContract,
    ProviderContext,
    Requirement,
)
from ardguard.models import Candidate, ContractError
from ardguard.providers.mcp import MCPProvider


def candidate(**original):
    body = {
        "identifier": "urn:air:example.org:tool:x",
        "source": "https://registry.example.org",
        "score": 1,
        **original,
    }
    return Candidate(body["identifier"], body["source"], 1, 1, original=body)


def test_inline_artifact_resolution_is_offline_and_content_addressed() -> None:
    item = candidate(data={"message": "hello"})
    artifact = InlineArtifactResolver().resolve(item, ResolutionPolicy(network_allowed=False))
    assert artifact.content == b'{"message":"hello"}'
    assert len(artifact.sha256) == 64


def test_url_resolution_requires_explicit_network_and_host() -> None:
    item = candidate(url="https://artifact.example/x")
    resolver = URLArtifactResolver(
        lambda url, timeout, limit, proxy: (b"x", url, "application/json", "93.184.216.34")
    )
    with pytest.raises(ContractError, match="disabled"):
        resolver.resolve(item, ResolutionPolicy())
    artifact = resolver.resolve(
        item, ResolutionPolicy(network_allowed=True, allowed_hosts=frozenset({"artifact.example"}))
    )
    assert artifact.content == b"x"


def test_cross_host_redirect_fails_closed() -> None:
    item = candidate(url="https://artifact.example/x")
    resolver = URLArtifactResolver(
        lambda url, timeout, limit, proxy: (
            b"x", "https://other.example/x", None, "93.184.216.34"
        )
    )
    with pytest.raises(ContractError, match="cross-host"):
        resolver.resolve(
            item,
            ResolutionPolicy(
                network_allowed=True, allowed_hosts=frozenset({"artifact.example", "other.example"})
            ),
        )


def test_artifact_resolution_limits_and_url_validation() -> None:
    with pytest.raises(ContractError, match="positive"):
        ResolutionPolicy(max_bytes=0)
    with pytest.raises(ContractError, match="does not contain inline"):
        InlineArtifactResolver().resolve(
            candidate(url="https://artifact.example/x"), ResolutionPolicy()
        )
    with pytest.raises(ContractError, match="size limit"):
        InlineArtifactResolver().resolve(
            candidate(data={"large": "x" * 20}), ResolutionPolicy(max_bytes=2)
        )

    resolver = URLArtifactResolver(
        lambda url, timeout, limit, proxy: (b"too large", url, None, "93.184.216.34")
    )
    with pytest.raises(ContractError, match="scheme or host"):
        resolver.resolve(
            candidate(url="http://artifact.example/x"),
            ResolutionPolicy(network_allowed=True, allowed_hosts=frozenset({"artifact.example"})),
        )
    with pytest.raises(ContractError, match="allowlisted"):
        resolver.resolve(
            candidate(url="https://artifact.example/x"),
            ResolutionPolicy(network_allowed=True, allowed_hosts=frozenset({"other.example"})),
        )
    with pytest.raises(ContractError, match="size limit"):
        resolver.resolve(
            candidate(url="https://artifact.example/x"),
            ResolutionPolicy(
                network_allowed=True, allowed_hosts=frozenset({"artifact.example"}), max_bytes=1
            ),
        )


def test_explicit_cross_host_redirect_can_be_allowlisted() -> None:
    resolver = URLArtifactResolver(
        lambda url, timeout, limit, proxy: (
            b"x", "https://other.example/final", None, "93.184.216.34"
        )
    )
    artifact = resolver.resolve(
        candidate(url="https://artifact.example/x"),
        ResolutionPolicy(
            network_allowed=True,
            allowed_hosts=frozenset({"artifact.example", "other.example"}),
            allow_cross_host_redirects=True,
        ),
    )
    assert artifact.final_url == "https://other.example/final"


def test_cache_key_binds_candidate_requirement_provider_input_and_context() -> None:
    item = candidate(url="https://artifact.example/x")
    requirement = Requirement("r", "deployment.region", {"predicate": "equals", "expected": "us"})
    key = CacheKey.create(
        candidate=item,
        requirement=requirement,
        provider_id="p",
        provider_version="1",
        input_identity="sha256:x",
        policy_context={"tenant": "a"},
    )
    fact = Fact(
        "f", item.resource_id, "deployment.region", "p", "1", FactOperationalState.AVAILABLE, "us"
    )
    cache = FactCache()
    assert cache.get(key, max_age_seconds=10, now=10).reason == "cache.miss"
    cache.put(key, fact, now=10)
    assert cache.get(key, max_age_seconds=5, now=12).reason == "cache.hit"
    assert cache.get(key, max_age_seconds=1, now=12).reason == "cache.stale"
    assert cache.invalidate(key) == 1


def test_protocol_capability_parsers_are_read_only() -> None:
    assert parse_mcp_tools([{"name": "read", "inputSchema": {"type": "object"}}]).operation_ids == (
        "read",
    )
    assert parse_a2a_agent_card({"skills": [{"id": "summarize"}]}).operation_ids == ("summarize",)
    assert parse_openapi({"paths": {"/x": {"get": {"operationId": "getX"}}}}).operation_ids == (
        "getX",
    )
    assert parse_skill_manifest({"id": "local.read"}).operation_ids == ("local.read",)


def test_mcp_provider_uses_only_initialize_and_tools_list() -> None:
    class Transport:
        def __init__(self):
            self.calls = []

        def initialize(self, candidate):
            self.calls.append("initialize")
            return {"authenticationRequired": True}

        def tools_list(self, candidate):
            self.calls.append("tools/list")
            return [
                {
                    "name": "read",
                    "inputSchema": {"type": "object"},
                    "annotations": {"readOnlyHint": True},
                }
            ]

    transport = Transport()
    provider = MCPProvider(transport)
    item = candidate(url="https://artifact.example/x")
    facts = provider.collect(
        item,
        GenericTaskContract(
            "t",
            (Requirement("r", "mcp.tool_names", {"predicate": "contains", "expected": "read"}),),
        ),
        (),
        ProviderContext(network_allowed=True),
    )
    assert transport.calls == ["initialize", "tools/list"]
    assert {fact.fact_type for fact in facts} == provider.supported_fact_types


def test_mcp_provider_does_not_use_network_without_explicit_permission() -> None:
    class Never:
        def initialize(self, candidate):
            raise AssertionError

        def tools_list(self, candidate):
            raise AssertionError

    fact = MCPProvider(Never()).collect(
        candidate(url="https://artifact.example/x"),
        GenericTaskContract(
            "t",
            (
                Requirement(
                    "r", "mcp.endpoint_reachable", {"predicate": "equals", "expected": True}
                ),
            ),
        ),
        (),
        ProviderContext(),
    )[0]
    assert fact.state is FactOperationalState.UNAVAILABLE
