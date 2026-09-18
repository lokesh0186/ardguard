"""Community example: ARDGuard selection followed by Semantic Kernel invocation."""

# ruff: noqa: S101 - executable pytest interoperability example

from __future__ import annotations

import pytest
from mcp import types
from semantic_kernel import Kernel
from semantic_kernel.connectors.mcp import MCPStreamableHttpPlugin

from ardguard import (
    Candidate,
    Fact,
    FactOperationalState,
    GenericFactSet,
    GenericTaskContract,
    KernelPolicy,
    ProviderTrust,
    Requirement,
    evaluate_kernel,
)
from ardguard.constraints import default_evaluator_registry
from ardguard.models import FinalDecision

PROVIDER_ID = "example.access-provider"
FACT_TYPE = "access.credential_available"
PREFERRED_ID = "urn:air:example.org:mcp:preferred"
FALLBACK_ID = "urn:air:example.org:mcp:fallback"
EXPECTED_FALLBACK_RANK = 2


class FakeMcpSession:
    """Minimum local MCP session used by Semantic Kernel's plugin."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._request_id = 0
        self.initialize_count = 0
        self.list_tools_count = 0
        self.call_tool_count = 0

    async def initialize(self) -> None:
        self.initialize_count += 1
        self._request_id = 1

    async def list_tools(self) -> types.ListToolsResult:
        self.list_tools_count += 1
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name="read_customer",
                    description=f"Read through {self.label}",
                    inputSchema={"type": "object", "properties": {}},
                )
            ]
        )

    async def call_tool(self, tool_name: str, arguments: dict[str, object]) -> types.CallToolResult:
        self.call_tool_count += 1
        assert tool_name == "read_customer"
        assert arguments == {}
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"{self.label}-result")]
        )


def access_fact(candidate_id: str, value: bool) -> Fact:
    return Fact(
        fact_id=f"access-{candidate_id.rsplit(':', 1)[-1]}",
        candidate_id=candidate_id,
        fact_type=FACT_TYPE,
        provider_id=PROVIDER_ID,
        provider_version="1",
        state=FactOperationalState.AVAILABLE,
        value=value,
        provenance={"source": "local-reference-fixture"},
    )


def select_candidate():
    candidates = (
        Candidate(PREFERRED_ID, "https://preferred.example/mcp", 1, 99),
        Candidate(FALLBACK_ID, "https://fallback.example/mcp", 2, 91),
    )
    task = GenericTaskContract(
        task_id="semantic-kernel-mcp-read",
        operation="customer.read",
        requirements=(
            Requirement(
                "credential-ready",
                FACT_TYPE,
                {"predicate": "equals", "expected": True},
            ),
        ),
    )
    return evaluate_kernel(
        candidates=candidates,
        task=task,
        policy=KernelPolicy(
            provider_trust=(ProviderTrust(PROVIDER_ID, "1", frozenset({FACT_TYPE})),),
            preestablished_fact_mode=True,
        ),
        fact_set=GenericFactSet(
            (
                access_fact(PREFERRED_ID, False),
                access_fact(FALLBACK_ID, True),
            )
        ),
        evaluators=default_evaluator_registry((FACT_TYPE,)),
    )


@pytest.mark.asyncio
async def test_only_selected_fallback_plugin_connects_and_invokes() -> None:
    preferred_session = FakeMcpSession("preferred")
    fallback_session = FakeMcpSession("fallback")
    plugins = {
        PREFERRED_ID: MCPStreamableHttpPlugin(
            "preferred_server",
            "https://preferred.example/mcp",
            session=preferred_session,
            load_prompts=False,
        ),
        FALLBACK_ID: MCPStreamableHttpPlugin(
            "fallback_server",
            "https://fallback.example/mcp",
            session=fallback_session,
            load_prompts=False,
        ),
    }

    decision = select_candidate()
    assert decision.outcome is FinalDecision.SELECT
    assert decision.selected_candidate_id == FALLBACK_ID
    assert decision.selected_rank == EXPECTED_FALLBACK_RANK
    assert decision.reason_code == "selection.fallback_to_lower_ranked_eligible"

    selected = plugins[decision.selected_candidate_id]
    await selected.connect()
    try:
        kernel = Kernel()
        kernel.add_plugin(selected, plugin_name=selected.name)
        result = await kernel.invoke(
            plugin_name=selected.name,
            function_name="read_customer",
        )
        assert str(result) == "fallback-result"
    finally:
        await selected.close()

    assert preferred_session.initialize_count == 0
    assert preferred_session.list_tools_count == 0
    assert preferred_session.call_tool_count == 0
    assert fallback_session.initialize_count == 1
    assert fallback_session.list_tools_count == 1
    assert fallback_session.call_tool_count == 1
