"""Minimal third-party ARDGuard fact provider example."""

from __future__ import annotations

from ardguard import Fact, FactOperationalState


class RegionProvider:
    provider_id = "example.region-provider"
    provider_version = "1"
    supported_fact_types = frozenset({"deployment.region"})

    def __init__(self, regions=None):
        self._regions = dict(regions or {})

    def collect(self, candidate, task, requirements, context):
        del task, requirements, context
        region = self._regions.get(candidate.resource_id)
        if not isinstance(region, str):
            return (
                Fact(
                    f"region:{candidate.resource_id}",
                    candidate.resource_id,
                    "deployment.region",
                    self.provider_id,
                    self.provider_version,
                    FactOperationalState.INDETERMINATE,
                    provenance={"provider_status": "region_unavailable", "retryable": False},
                ),
            )
        return (
            Fact(
                f"region:{candidate.resource_id}",
                candidate.resource_id,
                "deployment.region",
                self.provider_id,
                self.provider_version,
                FactOperationalState.AVAILABLE,
                region,
                provenance={"source": "configured-control-plane-observation"},
            ),
        )
