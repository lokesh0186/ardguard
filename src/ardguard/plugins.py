"""Fail-closed discovery for third-party fact providers."""

from __future__ import annotations

from importlib import metadata
from typing import Any

from ardguard.kernel import GenericFactProvider, ProviderRegistry
from ardguard.models import ContractError

ENTRY_POINT_GROUP = "ardguard.fact_providers"


def discover_fact_provider_metadata() -> tuple[dict[str, str], ...]:
    """Inspect entry-point metadata without importing provider code."""

    entries = metadata.entry_points().select(group=ENTRY_POINT_GROUP)
    seen: set[str] = set()
    rows = []
    for entry in sorted(entries, key=lambda item: item.name):
        if not entry.name or entry.name in seen:
            raise ContractError(f"duplicate or empty provider entry point: {entry.name!r}")
        seen.add(entry.name)
        if not entry.value or ":" not in entry.value:
            raise ContractError(f"provider entry point has invalid target metadata: {entry.name}")
        rows.append({"provider_id": entry.name, "target": entry.value, "loaded": "false"})
    return tuple(rows)


def load_fact_providers(*, enabled: frozenset[str]) -> ProviderRegistry:
    """Load only explicitly enabled entry points in deterministic name order."""

    registry = ProviderRegistry()
    discovered = metadata.entry_points()
    entries = discovered.select(group=ENTRY_POINT_GROUP)
    by_name: dict[str, Any] = {}
    for entry in entries:
        if not entry.name or entry.name in by_name:
            raise ContractError(f"duplicate or empty provider entry point: {entry.name!r}")
        by_name[entry.name] = entry
    unknown = sorted(enabled - set(by_name))
    if unknown:
        raise ContractError(f"enabled providers are not installed: {', '.join(unknown)}")
    for name in sorted(enabled):
        try:
            loaded = by_name[name].load()
            provider: GenericFactProvider = loaded() if isinstance(loaded, type) else loaded
        except Exception as exc:
            raise ContractError(f"plugin provider operational error: {name}") from exc
        try:
            provider_id = provider.provider_id
        except Exception as exc:
            raise ContractError(f"plugin provider operational error: {name}") from exc
        if provider_id != name:
            raise ContractError("provider entry-point name must equal provider_id")
        registry.register(provider)
    return registry
