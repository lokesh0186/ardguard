# ARDGuard

[![PyPI](https://img.shields.io/pypi/v/ardguard)](https://pypi.org/project/ardguard/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22691550.svg)](https://doi.org/10.5281/zenodo.22691550)
[![Python compatibility](https://github.com/lokesh0186/ardguard/actions/workflows/python-compat.yml/badge.svg?branch=main)](https://github.com/lokesh0186/ardguard/actions/workflows/python-compat.yml)
[![Python](https://img.shields.io/pypi/pyversions/ardguard)](https://pypi.org/project/ardguard/)
[![License](https://img.shields.io/pypi/l/ardguard)](LICENSE)

**ARDGuard adds an eligibility boundary between agentic resource discovery and final use.**

It consumes ranked discovery results, evaluates independently established task-specific
capability, evidence, and authority observations, and selects the highest-ranked
eligible resource or returns an explicit defer, abstain, or error decision. It never
installs or invokes the selected resource.

> **Status:** `0.1.0b4` Beta 3 patch release. The deterministic v1 path remains
> supported. The extensible v2 kernel and its protocol packs are experimental. See the
> [support matrix](docs/SUPPORTED_SCOPE.md) before production use.

```bash
python -m pip install ardguard==0.1.0b4
ardguard demo
```

```text
ARDGuard offline demo (illustrative)
rank 1: relevant but capability-ineligible
rank 2: eligible
top-ranked-only validation: ABSTAIN
ARDGuard: SELECT urn:air:example.org:tool:rank-two
reason: selection.fallback_to_lower_ranked_eligible
invocation: NOT PERFORMED
```

Relevance answers **which resource looks useful**. Eligibility answers **which resource
may this agent use for this task**.

## Put it after discovery

```text
ARD-compatible discovery backend
              |
              v
       ranked candidates
              |
              v
          ARDGuard
  facts + policy + fallback
              |
              v
 SELECT / DEFER / ABSTAIN / ERROR
              |
              v
      caller owns invocation
```

ARDGuard does not replace ARD, hf-discover, relevance ranking, Sigstore, OAuth, or
Kubernetes RBAC. It makes the consumer's final eligibility decision explicit.

## JSON in, decision JSON out

Prepare a task contract, policy, and observations, then evaluate any supported ARD
SearchResponse:

```bash
hf-discover search "read customer records" --json > discovery.json

ardguard evaluate \
  --adapter hf-discover \
  --discovery-response discovery.json \
  --task task.json \
  --policy policy.json \
  --facts facts.json \
  --output decision.json

ardguard explain decision.json
```

Example decision:

```json
{
  "outcome": "SELECT",
  "reason": "selection.fallback_to_lower_ranked_eligible",
  "selected_candidate_id": "urn:air:example.org:tool:rank-two",
  "selected_rank": 2
}
```

The actual decision document also contains every candidate verdict, stable reason
codes, provider identities, preserved backend scores, and a deterministic body hash.

## Python integration

```python
from ardguard import FactSet, Policy, TaskContract, evaluate
from ardguard.adapters import parse_search_response

candidates = parse_search_response(discovery_response)
decision = evaluate(
    candidates=candidates,
    task=TaskContract.from_mapping(task_document),
    policy=Policy.from_mapping(policy_document),
    facts=FactSet.from_mapping(fact_document),
)

if decision.outcome.value == "SELECT":
    # The caller may now decide whether and how to invoke the resource.
    print(decision.selected_candidate_id)
```

## Why fallback matters

A top-ranked-only validator can reject an ineligible first result, but it also abandons
the task when a lower-ranked candidate is eligible. ARDGuard evaluates the configured
candidate set, preserves the backend's rank among eligible candidates, and returns the
highest-ranked eligible candidate. It does not manufacture or reinterpret relevance
scores.

## Contracts, not self-asserted eligibility

Public callers supply observations, not `eligible: true`. ARDGuard derives candidate
verdicts from versioned contracts:

- `TaskContract` states required operations, evidence, and authority limits.
- `FactSet` binds typed observations to candidate and provider identities.
- `Policy` controls required checks, uncertainty, and fallback.
- `Decision` reports `SELECT`, `DEFER`, `ABSTAIN`, or `ERROR` with stable reasons.

Missing facts, unavailable verifiers, and operational errors fail closed. An
operational verifier failure is never reported as an invalid signature. Authentic
evidence for artifact A never makes candidate B eligible.

## Commands

| Command | Purpose |
| --- | --- |
| `ardguard demo` | Run the deterministic offline fallback example. |
| `ardguard doctor` | Report package, schema, adapter, and provider readiness. |
| `ardguard validate` | Validate task, fact, policy, decision, ARD, or hf-discover JSON. |
| `ardguard evaluate` | Produce a deterministic decision without invocation. |
| `ardguard explain` | Validate the decision hash and explain its reason. |
| `ardguard support` | Print the tested support matrix. |
| `ardguard adapters` | Print exact adapter compatibility records. |
| `ardguard providers list` | Describe provider and policy-pack extension boundaries. |
| `ardguard serve` | Run the experimental loopback-only JSON decision service. |

## Extensible kernel

Beta 3 includes an experimental v2 kernel for third-party fact types, typed
requirements, decision receipts, stdin/stdout integration, and a loopback HTTP API.
Beta 2 v1 contracts remain unchanged. Start with the existing commands above;
advanced integrators can read the [extensibility guide](docs/EXTENSIBILITY.md) and
[eligibility-pack matrix](docs/ELIGIBILITY_PACKS.md).

## Documentation

- [Five-minute integration guide](docs/INTEGRATION_GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security model](docs/SECURITY_MODEL.md)
- [Supported scope](docs/SUPPORTED_SCOPE.md)
- [Decision and reason codes](docs/DECISIONS.md)
- [Fact providers](docs/FACT_PROVIDERS.md)
- [Extensible kernel](docs/EXTENSIBILITY.md)
- [Eligibility packs](docs/ELIGIBILITY_PACKS.md)
- [ARD v0.91 compatibility](docs/ARD_COMPATIBILITY.md)
- [hf-discover integration](docs/HF_DISCOVER.md)
- [Evidence](docs/EVIDENCE.md)
- [Authority policy](docs/AUTHORITY.md)

## Examples

- [Basic capability decision](examples/basic/README.md)
- [Rank-preserving fallback](examples/fallback/README.md)
- [Authentic but non-applicable evidence](examples/evidence/README.md)
- [Authority-aware fallback](examples/authority/README.md)
- [ARD v0.91 SearchResponse](examples/ard_search_response/README.md)
- [Pinned hf-discover response](examples/hf_discover/search-response-1.3.7.json)

## Development

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy src/ardguard
```

Small compatibility fixtures, provider implementations, reason-code improvements,
and reproducible interoperability reports are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md)
and [SECURITY.md](SECURITY.md) first.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
