"""Experimental Neuronto ARD response adapter.

Neuronto currently adds a top-level queryMatch diagnostic object. This adapter
preserves it separately and delegates standard results to the ARD parser. It does
not treat coverage or liveness diagnostics as eligibility facts.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ardguard.adapters.ard import parse_search_response
from ardguard.models import Candidate, ContractError

NEURONTO_COMMIT = "4d7ebc52036cc80b752f61e153c3bd1e2395741f"


@dataclass(frozen=True)
class NeurontoResponse:
    candidates: tuple[Candidate, ...]
    query_match: Mapping[str, Any]


def parse_neuronto_response(document: object) -> NeurontoResponse:
    if not isinstance(document, Mapping):
        raise ContractError("Neuronto response must be an object")
    unknown = sorted(
        set(document) - {"results", "referrals", "pageToken", "queryMatch", "federation"}
    )
    if unknown:
        raise ContractError(f"unsupported Neuronto response fields: {', '.join(unknown)}")
    query_match = document.get("queryMatch", {})
    if not isinstance(query_match, Mapping):
        raise ContractError("Neuronto queryMatch must be an object")
    federation = document.get("federation")
    if federation is not None and not isinstance(federation, Mapping):
        raise ContractError("Neuronto federation must be an object")
    projected = {
        key: value for key, value in document.items() if key not in {"queryMatch", "federation"}
    }
    return NeurontoResponse(parse_search_response(projected), copy.deepcopy(dict(query_match)))
