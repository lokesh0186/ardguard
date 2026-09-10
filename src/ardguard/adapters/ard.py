"""Adapter for ARD v0.91 SearchResponse documents."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from ardguard.models import Candidate, ContractError

ARD_SPEC_VERSION = "v0.91"
ARD_SPEC_COMMIT = "aa3e598bb7752a9175897823234311216acfa864"
ARD_IDENTIFIER_RE = re.compile(r"^urn:air:[a-zA-Z0-9.-]+(:[a-zA-Z0-9._-]+)+$")
ARD_REGISTRY_MEDIA_TYPES = {"application/ai-registry", "application/ai-registry+json"}


def _absolute_uri(value: str, label: str) -> str:
    if any(character.isspace() for character in value) or not urlsplit(value).scheme:
        raise ContractError(f"{label} must be an absolute URI")
    return value


def _ard_identifier(value: str, label: str) -> str:
    if ARD_IDENTIFIER_RE.fullmatch(value) is None:
        raise ContractError(f"{label} must use the ARD domain-anchored URN form")
    return value


def _validate_referral(value: object, index: int) -> None:
    if not isinstance(value, Mapping):
        raise ContractError(f"ARD referral {index} must be an object")
    missing = sorted({"identifier", "displayName", "type", "url"} - set(value))
    if missing:
        raise ContractError(f"ARD referral {index} omits required fields: {', '.join(missing)}")
    identifier = value["identifier"]
    display_name = value["displayName"]
    media_type = value["type"]
    url = value["url"]
    if not isinstance(identifier, str):
        raise ContractError(f"ARD referral {index}.identifier must be a string")
    _ard_identifier(identifier, f"ARD referral {index}.identifier")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ContractError(f"ARD referral {index}.displayName must be a non-empty string")
    if media_type not in ARD_REGISTRY_MEDIA_TYPES:
        raise ContractError(f"ARD referral {index}.type is not a supported registry media type")
    if not isinstance(url, str):
        raise ContractError(f"ARD referral {index}.url must be a string")
    _absolute_uri(url, f"ARD referral {index}.url")


def parse_search_response(document: object) -> tuple[Candidate, ...]:
    if not isinstance(document, Mapping):
        raise ContractError("ARD SearchResponse must be an object")
    unknown = sorted(set(document) - {"results", "referrals", "pageToken"})
    if unknown:
        raise ContractError(f"unsupported ARD SearchResponse fields: {', '.join(unknown)}")
    results = document.get("results")
    if not isinstance(results, list):
        raise ContractError("ARD SearchResponse.results must be an array")
    candidates = tuple(
        Candidate.from_ard_result(row, rank=index) for index, row in enumerate(results, start=1)
    )
    identifiers = [candidate.resource_id for candidate in candidates]
    if len(identifiers) != len(set(identifiers)):
        raise ContractError("ARD SearchResponse contains duplicate identifiers")
    for candidate in candidates:
        _ard_identifier(candidate.resource_id, "search result.identifier")
        _absolute_uri(candidate.source, "search result.source")
    referrals = document.get("referrals", [])
    if not isinstance(referrals, list):
        raise ContractError("ARD SearchResponse.referrals must be an array")
    for index, referral in enumerate(referrals):
        _validate_referral(referral, index)
    token = document.get("pageToken")
    if token is not None and not isinstance(token, str):
        raise ContractError("ARD SearchResponse.pageToken must be a string")
    return candidates


def compatibility_record() -> dict[str, Any]:
    return {
        "adapter": "ard",
        "status": "SUPPORTED",
        "spec_version": ARD_SPEC_VERSION,
        "spec_commit": ARD_SPEC_COMMIT,
        "preserves_backend_order": True,
        "preserves_score": True,
    }
