# Extensible eligibility kernel

This document describes the Beta 3 experimental v2 contract. Beta 2 v1 contracts
remain supported without reinterpretation.

## Separation of responsibilities

A provider establishes typed facts. A requirement evaluator compares those facts with
a task requirement. The kernel composes mandatory requirements with logical AND,
records advisory results without letting them block selection, and selects the
highest-ranked satisfied candidate. Multiple concordant facts are retained. Conflicting
authoritative facts produce `INDETERMINATE`; they are never majority-voted. No provider
can return a decision or invoke a resource.

An unavailable or indeterminate fact does not become a negative fact. A provider
exception becomes an explicit operational error. The requirement's `unknown_policy`
can map an indeterminate result to `INDETERMINATE`, `UNSATISFIED`, or `ERROR`; this is
an explicit operator choice rather than an implicit default.

## Third-party providers

Packages may publish an entry point in the `ardguard.fact_providers` group. Loading is
opt in. Discovery does not enable a provider. The entry-point name must exactly equal
the provider ID, duplicate IDs fail, and providers run in deterministic ID order. The
policy must authorize the exact provider ID, version, and fact type or bounded namespace.
A provider declares fact types and may only return facts for the candidate it was asked
to inspect.

```toml
[project.entry-points."ardguard.fact_providers"]
"example.region-provider" = "example_provider:RegionProvider"
```

Enabled provider code executes inside the application trust boundary. The provider
returns `Fact` values, not `eligible=true`. A separate evaluator handles
the matching requirement type. An unrelated package can therefore add a new fact and
requirement type without changing the kernel.

## Closed predicates

The built-in constraint evaluator supports equality, inequality, membership, set
containment, numeric bounds, semantic-version bounds, timestamp freshness, digest
and identity equality, scope subsets, and provenance-backed booleans. Incompatible
types fail closed. There is no expression language, JSONPath interpreter, or arbitrary
code evaluation.

## Integration surfaces

`ardguard evaluate --stdin --json` accepts one v2 bundle and emits one decision.
`ardguard serve` exposes the versioned endpoints in `openapi-v1.yaml` and binds only
to loopback. It validates the local Host header and request size. Plugins and network
providers remain disabled unless explicitly enabled.

Every decision includes a content-addressed receipt over the task, candidate set,
policy, provider identities, facts, requirement verdicts, and selected candidate.
Signing is outside the current scope.
