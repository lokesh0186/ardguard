# Fact providers

A fact provider converts deployment-specific measurements into typed candidate
observations. It never selects a candidate and never asserts final eligibility.

```python
class MyProvider:
    provider_id = "example.capability"
    version = "1"

    def observe(self, candidates, task):
        return tuple(observations)
```

Each observation must bind:

- candidate ID;
- fact type;
- provider ID and version;
- `AVAILABLE`, `UNAVAILABLE`, `OPERATIONAL_ERROR`, or `INDETERMINATE` state;
- a closed type-specific payload when available;
- provider-specific provenance.

ARDGuard validates provider observations again before composition. A deployment must
authorize the exact provider ID, version, and permitted fact types in policy. Installed
does not mean trusted, discovered does not mean enabled, and enabled does not grant a
provider universal fact authority. Provider Python code runs in the application trust
boundary unless the deployment creates a stronger isolation boundary itself.

## Capability

Return verified executable capabilities, not catalog claims. The composer compares the
verified set with the task's required capabilities.

## Evidence

Report verifier outcome, authenticity, signer trust, exact subject digests, candidate
artifact digest, predicate types, resource association, and receipt provenance.
Authenticity and applicability remain separate.

## Authority

Return verified granted permissions. The composer requires the task permissions and
rejects any permission outside the operator-defined maximum set.

## Static provider

`StaticFactProvider` is suitable for offline replay and tests after a trusted transport
has delivered a validated FactSet. It does not make untrusted JSON authoritative.

## Development v2 provider SPI

The v2 provider protocol accepts one candidate, task, matching requirements, and an
explicit context, then returns generic `Fact` observations. Providers declare a stable
ID, version, and supported fact types. Entry-point loading is opt in, duplicate IDs
fail, emitted provider identity is framework-bound, provider errors remain operational
errors, and a provider cannot return a final decision. Pre-established fact input is
disabled unless both explicit mode and matching provider trust are configured. See
[EXTENSIBILITY.md](EXTENSIBILITY.md).
