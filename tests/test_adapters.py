from __future__ import annotations

import copy

import pytest
from conftest import load

from ardguard.adapters.ard import ARD_SPEC_COMMIT, ARD_SPEC_VERSION, parse_search_response
from ardguard.adapters.hf_discover import (
    HF_DISCOVER_COMMIT,
    HF_DISCOVER_VERSION,
    parse_hf_discover_response,
)
from ardguard.models import ContractError


def test_current_ard_contract_is_pinned() -> None:
    assert ARD_SPEC_VERSION == "v0.91"
    assert ARD_SPEC_COMMIT == "aa3e598bb7752a9175897823234311216acfa864"


def test_ard_order_scores_and_opaque_fields_are_preserved(fallback_documents) -> None:
    discovery, _, _, _ = fallback_documents
    candidates = parse_search_response(discovery)
    assert [(item.rank, item.score) for item in candidates] == [(1, 98), (2, 93)]
    assert candidates[0].original["displayName"] == "Rank One"


def test_ard_rejects_score_as_boolean(fallback_documents) -> None:
    discovery, _, _, _ = fallback_documents
    changed = copy.deepcopy(discovery)
    changed["results"][0]["score"] = True
    with pytest.raises(ContractError, match="integer"):
        parse_search_response(changed)


def test_ard_rejects_duplicate_ids(fallback_documents) -> None:
    discovery, _, _, _ = fallback_documents
    changed = copy.deepcopy(discovery)
    changed["results"][1]["identifier"] = changed["results"][0]["identifier"]
    with pytest.raises(ContractError, match="duplicate"):
        parse_search_response(changed)


def test_ard_rejects_nonconforming_identifier_and_source(fallback_documents) -> None:
    discovery, _, _, _ = fallback_documents
    changed = copy.deepcopy(discovery)
    changed["results"][0]["identifier"] = "https://example.org/tool"
    with pytest.raises(ContractError, match="domain-anchored URN"):
        parse_search_response(changed)
    changed = copy.deepcopy(discovery)
    changed["results"][0]["source"] = "relative/path"
    with pytest.raises(ContractError, match="absolute URI"):
        parse_search_response(changed)


def test_ard_validates_referrals(fallback_documents) -> None:
    discovery, _, _, _ = fallback_documents
    changed = copy.deepcopy(discovery)
    changed["referrals"] = [
        {
            "identifier": "urn:air:example.org:registry:public",
            "displayName": "Example registry",
            "type": "application/ai-registry+json",
            "url": "https://finder.example.org/search",
        }
    ]
    assert len(parse_search_response(changed)) == 2
    del changed["referrals"][0]["url"]
    with pytest.raises(ContractError, match="omits required fields"):
        parse_search_response(changed)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("identifier", "not-a-urn", "domain-anchored URN"),
        ("displayName", "", "non-empty"),
        ("type", "application/json", "registry media type"),
        ("url", "relative", "absolute URI"),
    ],
)
def test_ard_rejects_malformed_referral(
    fallback_documents, field: str, value: object, message: str
) -> None:
    discovery, _, _, _ = fallback_documents
    changed = copy.deepcopy(discovery)
    changed["referrals"] = [
        {
            "identifier": "urn:air:example.org:registry:public",
            "displayName": "Example registry",
            "type": "application/ai-registry+json",
            "url": "https://finder.example.org/search",
        }
    ]
    changed["referrals"][0][field] = value
    with pytest.raises(ContractError, match=message):
        parse_search_response(changed)


def test_hf_discover_pinned_fixture() -> None:
    candidates = parse_hf_discover_response(load("examples/hf_discover/search-response-1.3.7.json"))
    assert len(candidates) == 1
    assert candidates[0].score == 91
    assert HF_DISCOVER_VERSION == "1.3.7"
    assert HF_DISCOVER_COMMIT == "49c927439fcaa8f210cfd42186c0641acef579fa"


def test_hf_discover_rejects_missing_media_type() -> None:
    value = load("examples/hf_discover/search-response-1.3.7.json")
    del value["results"][0]["type"]
    with pytest.raises(ContractError, match="omits pinned fields"):
        parse_hf_discover_response(value)


def test_hf_discover_rejects_url_and_data_together() -> None:
    value = load("examples/hf_discover/search-response-1.3.7.json")
    value["results"][0]["data"] = {"name": "duplicate"}
    with pytest.raises(ContractError, match="exactly one"):
        parse_hf_discover_response(value)
