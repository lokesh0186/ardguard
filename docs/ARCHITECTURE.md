# Architecture

ARDGuard is a consumer-side decision layer. It starts after a discovery backend has
produced ranked candidates and ends before any resource is installed or invoked.

```text
ARD SearchResponse or supported adapter
                |
                v
          Candidate adapter
                |
                v
  capability  evidence  authority observations
                |
                v
       task-specific composition
                |
                v
       rank-preserving selector
                |
                v
      SELECT / DEFER / ABSTAIN / ERROR
```

## Components

### Candidate adapters

Adapters preserve each resource identifier, discovery source, backend score, and
original opaque fields. List position becomes the preliminary rank because ARD v0.91
does not add a separate rank field. ARDGuard never creates or changes a relevance score.

### Task contract

A task contract names the required operation, independently verified capabilities,
evidence predicates and signers, and the operator's authority ceiling. At least one
eligibility dimension is required.

### Fact providers

Providers establish observations. They do not return final eligibility. A provider
observation is bound to a candidate identity, provider identity and version, state,
typed payload, and provenance. Provider trust is an explicit deployment boundary.

### Policy composer

The composer evaluates the configured dimensions independently. A definite failure
makes a candidate `INELIGIBLE`. A missing, unavailable, operational-error, or otherwise
uncertain required observation makes it `INDETERMINATE`. Only complete satisfaction of
all required checks produces `ELIGIBLE`.

### Selector

The default selector walks backend rank in order and returns the first eligible
candidate. Explicit equal ranks use resource identity only as a deterministic
tie-breaker. The top-ranked-only mode is available for integrations that require it,
but it does not fall back.

### Decision

The decision preserves all candidate verdicts and provider identities, includes a
stable reason code, and binds the canonical decision body with SHA-256. The decision is
an authorization input for the caller, not an invocation command.

## Determinism

ARDGuard performs no model call, live search, clock read, random choice, or resource
invocation during composition. Given the same candidates, task, facts, and policy, it
produces the same decision bytes. External providers may perform nondeterministic work,
but their final typed observations are explicit inputs.
