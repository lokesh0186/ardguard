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
decide which provider identities and transports it trusts. Provider Python code runs in
the application trust boundary unless it creates a stronger isolation boundary itself.

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
