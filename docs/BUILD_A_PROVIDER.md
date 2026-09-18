# Build a third-party fact provider

A provider establishes facts about candidates. It does not rank candidates, return a
final eligibility decision, or invoke a resource. Installed provider code is not trusted
or enabled automatically.

## 1. Implement the provider

```python
from ardguard import Fact, FactOperationalState


class RegionProvider:
    provider_id = "example.region-provider"
    provider_version = "1"
    supported_fact_types = frozenset({"deployment.region"})

    def __init__(self, regions):
        self._regions = dict(regions)

    def collect(self, candidate, task, requirements, context):
        del task, requirements, context
        region = self._regions.get(candidate.resource_id)
        state = (
            FactOperationalState.AVAILABLE
            if isinstance(region, str)
            else FactOperationalState.INDETERMINATE
        )
        return (
            Fact(
                f"region:{candidate.resource_id}",
                candidate.resource_id,
                "deployment.region",
                self.provider_id,
                self.provider_version,
                state,
                region,
                provenance={"source": "configured-control-plane-observation"},
            ),
        )
```

Use independent observations. Do not convert unverified candidate metadata into a
security fact, and never emit `eligible=true`.

## 2. Register the entry point

```toml
[project.entry-points."ardguard.fact_providers"]
"example.region-provider" = "example_region_provider:RegionProvider"
```

The entry-point name must match `provider_id`. Discovery is metadata inspection only;
providers load solely from an explicit enable list.

## 3. Authorize the exact provider boundary

```python
from ardguard import ProviderTrust

trust = ProviderTrust(
    "example.region-provider",
    "1",
    frozenset({"deployment.region"}),
)
```

Trust binds provider ID, version, and allowed fact types. Enabling a provider does not
grant it authority over other fact namespaces.

## 4. Test the result

Test at least one available observation, one unavailable or indeterminate observation,
one unauthorized fact type, and one mismatched candidate identity. The framework binds
the provider identity and rejects spoofed provider or candidate facts.

The complete executable example is in
[`examples/provider_plugin`](../examples/provider_plugin/README.md), and its regression
is [`tests/test_third_party_provider.py`](../tests/test_third_party_provider.py).

Enabled Python providers execute inside the application trust boundary. Use process or
service isolation when your deployment requires a stronger boundary.
