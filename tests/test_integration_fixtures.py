from __future__ import annotations

import json
from pathlib import Path

import pytest

from ardguard.adapters.ard import parse_search_response
from ardguard.adapters.neuronto import NEURONTO_COMMIT, parse_neuronto_response
from ardguard.models import ContractError

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / "tests" / "fixtures" / "integrations" / name).read_text())


def test_neuronto_explicit_adapter_preserves_rank_and_opaque_fields() -> None:
    assert NEURONTO_COMMIT == "4d7ebc52036cc80b752f61e153c3bd1e2395741f"
    parsed = parse_neuronto_response(load("neuronto-search-response.json"))
    assert [item.rank for item in parsed.candidates] == [1, 2]
    assert [item.score for item in parsed.candidates] == [94, 87]
    assert parsed.candidates[0].original["matchedTool"] == "read_pdf"
    assert parsed.query_match["coverage"] == "partial"


def test_standard_ard_adapter_does_not_silently_accept_neuronto_extensions() -> None:
    with pytest.raises(ContractError, match="queryMatch"):
        parse_search_response(load("neuronto-search-response.json"))


def test_mcp_gateway_shape_is_not_misrepresented_as_ard_search_response() -> None:
    with pytest.raises(ContractError, match="unsupported"):
        parse_search_response(load("mcp-gateway-search-registry.json"))


def test_openard_non_uri_source_remains_rejected() -> None:
    with pytest.raises(ContractError, match="absolute URI"):
        parse_search_response(load("openard-nonconforming-source.json"))
