"""Protocol-neutral capability adapter boundaries and frozen shape parsers."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ardguard.models import ContractError, canonical_json


@dataclass(frozen=True)
class CapabilityDescription:
    protocol: str
    operation_ids: tuple[str, ...]
    schema_sha256: Mapping[str, str]
    original: Mapping[str, Any]


def _hash_schema(value: object) -> str:
    if not isinstance(value, Mapping):
        raise ContractError("operation input schema must be an object")
    return hashlib.sha256(canonical_json(value)).hexdigest()


def parse_mcp_tools(tools: object) -> CapabilityDescription:
    if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
        raise ContractError("MCP tools must be an array")
    rows: list[tuple[str, str]] = []
    for tool in tools:
        if not isinstance(tool, Mapping) or not isinstance(tool.get("name"), str):
            raise ContractError("MCP tool must contain a string name")
        rows.append((tool["name"], _hash_schema(tool.get("inputSchema", {}))))
    rows.sort()
    return CapabilityDescription(
        "mcp", tuple(row[0] for row in rows), dict(rows), {"tools": copy.deepcopy(list(tools))}
    )


def parse_a2a_agent_card(card: object) -> CapabilityDescription:
    if not isinstance(card, Mapping):
        raise ContractError("A2A agent card must be an object")
    skills = card.get("skills")
    if not isinstance(skills, list):
        raise ContractError("A2A agent card skills must be an array")
    names: list[str] = []
    hashes: dict[str, str] = {}
    for skill in skills:
        if not isinstance(skill, Mapping) or not isinstance(skill.get("id"), str):
            raise ContractError("A2A skill must contain a string id")
        identifier = skill["id"]
        names.append(identifier)
        hashes[identifier] = hashlib.sha256(canonical_json(skill)).hexdigest()
    return CapabilityDescription(
        "a2a", tuple(sorted(names)), dict(sorted(hashes.items())), copy.deepcopy(dict(card))
    )


def parse_openapi(document: object) -> CapabilityDescription:
    if not isinstance(document, Mapping) or not isinstance(document.get("paths"), Mapping):
        raise ContractError("OpenAPI document must contain paths")
    operations: dict[str, str] = {}
    for path, path_item in document["paths"].items():
        if not isinstance(path, str) or not isinstance(path_item, Mapping):
            raise ContractError("OpenAPI paths must map strings to objects")
        for method, operation in path_item.items():
            if method.casefold() not in {
                "get",
                "put",
                "post",
                "delete",
                "patch",
                "head",
                "options",
                "trace",
            }:
                continue
            if not isinstance(operation, Mapping):
                raise ContractError("OpenAPI operation must be an object")
            operation_id = operation.get("operationId", f"{method.casefold()} {path}")
            if not isinstance(operation_id, str) or not operation_id:
                raise ContractError("OpenAPI operationId must be a non-empty string")
            operations[operation_id] = hashlib.sha256(canonical_json(operation)).hexdigest()
    return CapabilityDescription(
        "openapi",
        tuple(sorted(operations)),
        dict(sorted(operations.items())),
        copy.deepcopy(dict(document)),
    )


def parse_skill_manifest(document: object) -> CapabilityDescription:
    if not isinstance(document, Mapping):
        raise ContractError("skill manifest must be an object")
    identifier = document.get("id") or document.get("name")
    if not isinstance(identifier, str) or not identifier:
        raise ContractError("skill manifest must contain a string id or name")
    return CapabilityDescription(
        "skill",
        (identifier,),
        {identifier: hashlib.sha256(canonical_json(document)).hexdigest()},
        copy.deepcopy(dict(document)),
    )
