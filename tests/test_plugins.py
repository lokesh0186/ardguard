from __future__ import annotations

import pytest

from ardguard.models import ContractError
from ardguard.plugins import discover_fact_provider_metadata, load_fact_providers
from ardguard.providers.generic import StaticGenericProvider


class Entry:
    def __init__(self, name, loaded, value="package.module:Provider"):
        self.name = name
        self._loaded = loaded
        self.value = value

    def load(self):
        return self._loaded


class Entries(list):
    def select(self, *, group):
        assert group == "ardguard.fact_providers"
        return self


def provider(name: str):
    return StaticGenericProvider(name, "1", frozenset({"example.fact"}), {})


def test_plugin_loading_is_explicit_and_deterministic(monkeypatch) -> None:
    entries = Entries(
        [Entry("z.provider", provider("z.provider")), Entry("a.provider", provider("a.provider"))]
    )
    monkeypatch.setattr("ardguard.plugins.metadata.entry_points", lambda: entries)
    registry = load_fact_providers(enabled=frozenset({"z.provider", "a.provider"}))
    assert [item.provider_id for item in registry.providers] == ["a.provider", "z.provider"]


def test_unknown_plugin_and_identity_mismatch_fail_closed(monkeypatch) -> None:
    entries = Entries([Entry("declared.provider", provider("actual.provider"))])
    monkeypatch.setattr("ardguard.plugins.metadata.entry_points", lambda: entries)
    with pytest.raises(ContractError, match="not installed"):
        load_fact_providers(enabled=frozenset({"missing.provider"}))
    with pytest.raises(ContractError, match="must equal"):
        load_fact_providers(enabled=frozenset({"declared.provider"}))


def test_duplicate_entry_point_metadata_fails_closed(monkeypatch) -> None:
    entries = Entries(
        [
            Entry("same.provider", provider("same.provider")),
            Entry("same.provider", provider("same.provider")),
        ]
    )
    monkeypatch.setattr("ardguard.plugins.metadata.entry_points", lambda: entries)
    with pytest.raises(ContractError, match="duplicate"):
        load_fact_providers(enabled=frozenset({"same.provider"}))


def test_metadata_discovery_does_not_import_plugins(monkeypatch) -> None:
    entries = Entries([Entry("provider.example", object())])
    monkeypatch.setattr("ardguard.plugins.metadata.entry_points", lambda: entries)
    assert discover_fact_provider_metadata() == (
        {
            "provider_id": "provider.example",
            "target": "package.module:Provider",
            "loaded": "false",
        },
    )


def test_invalid_plugin_metadata_fails_closed(monkeypatch) -> None:
    entries = Entries([Entry("provider.example", object(), value="bad-target")])
    monkeypatch.setattr("ardguard.plugins.metadata.entry_points", lambda: entries)
    with pytest.raises(ContractError, match="invalid target"):
        discover_fact_provider_metadata()


def test_plugin_import_failure_is_bounded_operational_error(monkeypatch) -> None:
    class BrokenEntry(Entry):
        def load(self):
            raise RuntimeError("secret internal import details")

    monkeypatch.setattr(
        "ardguard.plugins.metadata.entry_points",
        lambda: Entries([BrokenEntry("provider.example", None)]),
    )
    with pytest.raises(ContractError, match="plugin provider operational error") as failure:
        load_fact_providers(enabled=frozenset({"provider.example"}))
    assert "secret" not in str(failure.value)


def test_plugin_missing_identity_is_bounded_operational_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "ardguard.plugins.metadata.entry_points",
        lambda: Entries([Entry("provider.example", object())]),
    )
    with pytest.raises(ContractError, match="plugin provider operational error"):
        load_fact_providers(enabled=frozenset({"provider.example"}))
