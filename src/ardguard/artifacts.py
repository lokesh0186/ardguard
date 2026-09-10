"""Artifact resolution with explicit network and size policy."""

from __future__ import annotations

import hashlib
import ipaddress
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from ardguard.models import Candidate, ContractError, canonical_json


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class Artifact:
    content: bytes
    media_type: str | None
    source_identity: str
    final_url: str | None
    sha256: str


@dataclass(frozen=True)
class ResolutionPolicy:
    network_allowed: bool = False
    max_bytes: int = 8 * 1024 * 1024
    timeout_seconds: float = 10.0
    allowed_schemes: frozenset[str] = frozenset({"https"})
    allowed_hosts: frozenset[str] = frozenset()
    allow_cross_host_redirects: bool = False
    allow_private_networks: bool = False
    allow_environment_proxy: bool = False

    def __post_init__(self) -> None:
        if self.max_bytes < 1 or self.timeout_seconds <= 0:
            raise ContractError("artifact size and timeout limits must be positive")


class ArtifactResolver(Protocol):
    resolver_id: str

    def resolve(self, candidate: Candidate, policy: ResolutionPolicy) -> Artifact: ...


class InlineArtifactResolver:
    resolver_id = "ardguard.inline-data/v1"

    def resolve(self, candidate: Candidate, policy: ResolutionPolicy) -> Artifact:
        document = candidate.original.get("data")
        if not isinstance(document, Mapping):
            raise ContractError("candidate does not contain inline data")
        content = canonical_json(_plain(document))
        if len(content) > policy.max_bytes:
            raise ContractError("inline artifact exceeds configured size limit")
        digest = hashlib.sha256(content).hexdigest()
        return Artifact(
            content, candidate.media_type, f"inline:{candidate.resource_id}", None, digest
        )


Fetch = Callable[[str, float, int, bool], tuple[bytes, str, str | None, str]]


def _host_allowed(host: str, policy: ResolutionPolicy) -> bool:
    normalized = host.rstrip(".").lower()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return normalized in {item.rstrip(".").lower() for item in policy.allowed_hosts}
    special = (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
    return (
        normalized in {item.rstrip(".").lower() for item in policy.allowed_hosts}
        and (policy.allow_private_networks or not special)
    )


def _peer_allowed(peer_ip: str, policy: ResolutionPolicy) -> bool:
    try:
        address = ipaddress.ip_address(peer_ip)
    except ValueError:
        return False
    special = (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
    return policy.allow_private_networks or not special


def _validate_url(url: str, policy: ResolutionPolicy, label: str) -> tuple[str, str]:
    parsed = urlsplit(url)
    if parsed.scheme not in policy.allowed_schemes or not parsed.hostname:
        raise ContractError(f"{label} scheme or host is not permitted")
    if parsed.username is not None or parsed.password is not None:
        raise ContractError(f"{label} cannot contain credentials")
    if not _host_allowed(parsed.hostname, policy):
        raise ContractError(f"{label} host is not allowlisted or is a prohibited network target")
    return parsed.hostname.rstrip(".").lower(), parsed.scheme


class URLArtifactResolver:
    """Network resolver backed by an explicitly supplied fetch function.

    Core does not provide an implicit HTTP client. Deployments must enable network,
    allow exact hosts, and inject the transport.
    """

    resolver_id = "ardguard.explicit-url/v1"

    def __init__(self, fetch: Fetch) -> None:
        self._fetch = fetch

    def resolve(self, candidate: Candidate, policy: ResolutionPolicy) -> Artifact:
        if not policy.network_allowed:
            raise ContractError("network artifact resolution is disabled")
        url = candidate.original.get("url")
        if not isinstance(url, str):
            raise ContractError("candidate does not contain an artifact URL")
        initial_host, _ = _validate_url(url, policy, "artifact URL")
        content, final_url, media_type, peer_ip = self._fetch(
            url,
            policy.timeout_seconds,
            policy.max_bytes,
            policy.allow_environment_proxy,
        )
        if len(content) > policy.max_bytes:
            raise ContractError("resolved artifact exceeds configured size limit")
        final_host, _ = _validate_url(final_url, policy, "final artifact URL")
        if final_host != initial_host and not policy.allow_cross_host_redirects:
            raise ContractError("cross-host artifact redirect is prohibited")
        if not isinstance(peer_ip, str) or not _peer_allowed(peer_ip, policy):
            raise ContractError(
                "artifact transport peer address is not allowlisted or is prohibited"
            )
        return Artifact(
            content,
            media_type or candidate.media_type,
            url,
            final_url,
            hashlib.sha256(content).hexdigest(),
        )
