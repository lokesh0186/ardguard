"""Experimental read-only MCP capability provider."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from ardguard.kernel import (
    Fact,
    FactOperationalState,
    GenericTaskContract,
    ProviderContext,
    Requirement,
)
from ardguard.models import Candidate, ContractError, canonical_json


class MCPReadOnlyTransport(Protocol):
    def initialize(self, candidate: Candidate) -> Mapping[str, Any]: ...

    def tools_list(self, candidate: Candidate) -> Sequence[Mapping[str, Any]]: ...


@dataclass(frozen=True)
class MCPProvider:
    """Collect initialize and tools/list facts. It never calls tools/call."""

    transport: MCPReadOnlyTransport
    provider_id: str = "ardguard.mcp-introspection"
    provider_version: str = "1"
    supported_fact_types: frozenset[str] = frozenset(
        {
            "mcp.endpoint_reachable",
            "mcp.authentication_required",
            "mcp.tool_names",
            "mcp.input_schema_hashes",
            "mcp.tool_hints",
        }
    )

    def collect(
        self,
        candidate: Candidate,
        task: GenericTaskContract,
        requirements: tuple[Requirement, ...],
        context: ProviderContext,
    ) -> Sequence[Fact]:
        del task, requirements
        if not context.network_allowed:
            return (
                self._fact(
                    candidate, "mcp.endpoint_reachable", None, FactOperationalState.UNAVAILABLE
                ),
            )
        initialized = self.transport.initialize(candidate)
        tools = tuple(self.transport.tools_list(candidate))
        normalized: list[tuple[str, str, Mapping[str, Any]]] = []
        for tool in tools:
            name = tool.get("name")
            schema = tool.get("inputSchema", {})
            annotations = tool.get("annotations", {})
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(schema, Mapping)
                or not isinstance(annotations, Mapping)
            ):
                raise ContractError("MCP tools/list returned an unsupported tool shape")
            normalized.append(
                (name, hashlib.sha256(canonical_json(schema)).hexdigest(), annotations)
            )
        normalized.sort(key=lambda item: item[0])
        auth_required = initialized.get("authenticationRequired", False)
        if not isinstance(auth_required, bool):
            raise ContractError("MCP initialize authenticationRequired must be boolean")
        return (
            self._fact(candidate, "mcp.endpoint_reachable", True),
            self._fact(candidate, "mcp.authentication_required", auth_required),
            self._fact(candidate, "mcp.tool_names", [item[0] for item in normalized]),
            self._fact(
                candidate, "mcp.input_schema_hashes", {item[0]: item[1] for item in normalized}
            ),
            self._fact(
                candidate, "mcp.tool_hints", {item[0]: dict(item[2]) for item in normalized}
            ),
        )

    def _fact(
        self,
        candidate: Candidate,
        fact_type: str,
        value: object,
        state: FactOperationalState = FactOperationalState.AVAILABLE,
    ) -> Fact:
        identity = hashlib.sha256(
            canonical_json(
                {
                    "candidate_id": candidate.resource_id,
                    "fact_type": fact_type,
                    "provider_id": self.provider_id,
                }
            )
        ).hexdigest()
        return Fact(
            fact_id=f"mcp:{identity}",
            candidate_id=candidate.resource_id,
            fact_type=fact_type,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            state=state,
            value=value,
            provenance=(
                {"provider_status": "network_disabled", "retryable": False}
                if state is not FactOperationalState.AVAILABLE
                else {"operations": ["initialize", "tools/list"], "tools_call": False}
            ),
            source_identity=candidate.source,
        )
