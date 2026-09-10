"""Pinned hf-discover JSON compatibility adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ardguard.adapters.ard import parse_search_response
from ardguard.models import Candidate, ContractError

HF_DISCOVER_VERSION = "1.3.7"
HF_DISCOVER_COMMIT = "49c927439fcaa8f210cfd42186c0641acef579fa"


def parse_hf_discover_response(document: object) -> tuple[Candidate, ...]:
    if not isinstance(document, Mapping):
        raise ContractError("hf-discover JSON must be an object")
    results = document.get("results")
    if not isinstance(results, list):
        raise ContractError("hf-discover JSON must contain a results array")
    for index, value in enumerate(results):
        if not isinstance(value, Mapping):
            raise ContractError(f"hf-discover result {index} must be an object")
        missing = sorted({"identifier", "displayName", "type", "score", "source"} - set(value))
        if missing:
            raise ContractError(
                f"hf-discover result {index} omits pinned fields: {', '.join(missing)}"
            )
        has_url = value.get("url") is not None
        has_data = value.get("data") is not None
        if has_url == has_data:
            raise ContractError(
                f"hf-discover result {index} must contain exactly one of url or data"
            )
    return parse_search_response(document)


def compatibility_record() -> dict[str, Any]:
    return {
        "adapter": "hf-discover",
        "status": "SUPPORTED",
        "distribution_version": HF_DISCOVER_VERSION,
        "commit": HF_DISCOVER_COMMIT,
        "command_shape": "hf-discover search QUERY --json",
        "preserves_backend_order": True,
        "preserves_score": True,
    }
