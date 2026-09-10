# Changelog

All notable changes follow Keep a Changelog conventions. Versions follow semantic
versioning with Python prerelease identifiers.

## [Unreleased]

## [0.1.0b4] - 2026-09-10

### Fixed

- Canonicalize the public JSON representation of structured evidence facts before
  conflict comparison. Beta 3 could otherwise raise `TypeError` when an evidence fact
  had a non-null evidence identity and a structured value.

### Compatibility

- No public API, schema, provider, ranking, fallback, or successful decision behavior
  changes. Inputs affected by the defect now produce the documented evidence verdict
  instead of an operational exception.

## [0.1.0b3] - 2026-09-10

### Added

- Versioned v2 requirement, fact, provider, evaluator, and decision contracts.
- Opt-in fact-provider entry points and a working third-party provider example.
- Closed generic constraints, content-addressed decision receipts, and identity-bound
  fact caching.
- Explicit artifact resolution policy, generalized evidence fact composition, a
  deterministic publisher-identity pack, and bounded dependency evaluation.
- Experimental read-only MCP introspection plus A2A, OpenAPI, Skill, and Neuronto
  parsing boundaries.
- JSON stdin/stdout evaluation and a loopback-only versioned HTTP API.

### Security

- Requires explicit provider ID, version, and fact-namespace trust for v2 facts.
- Rejects provider identity spoofing, conflicting facts without policy precedence,
  unsafe diagnostics, duplicate explicit ranks, and prohibited URL-resolution targets.

### Compatibility

- Accepts sparse ARD v0.91 Search results whose only required field is `identifier`.
- Beta 2 v1 JSON, CLI, reason codes, and decision hash fixtures remain unchanged.

## [0.1.0b2] - 2026-09-10

### Changed

- Refreshed and schema-validated `CITATION.cff` metadata for software archival.
- Added release-specific archival notes for the Zenodo-enabled GitHub release path.

### Compatibility

- No runtime decision, public API, schema, provider, adapter, or policy behavior changed
  from `0.1.0b1`.

## [0.1.0b1] - 2026-09-09

### Added

- Versioned Candidate, TaskContract, FactSet, Policy, CandidateVerdict, and Decision
  contracts.
- Deterministic eligibility composition across capability, evidence applicability, and
  operator-defined authority facts.
- Rank-preserving fallback with explicit `SELECT`, `DEFER`, `ABSTAIN`, and `ERROR`
  outcomes.
- Stable reason codes and a deterministic decision body hash.
- ARD v0.91 and hf-discover 1.3.7 adapters pinned to exact upstream commits.
- Offline demo, doctor, validation, evaluation, explanation, support, and adapter CLI
  commands.
- Experimental network-denied PyPI and Sigstore command-provider boundary with exact
  artifact naming, explicit trust seeds, and typed operational errors.
- JSON Schemas, integration examples, security model, support matrix, contribution
  policy, package hygiene checks, and Trusted Publishing workflow.

### Security

- Relevance scores cannot establish eligibility.
- Input observations cannot assert final eligibility.
- Missing facts and provider failures fail closed.
- Operational verifier errors cannot become cryptographic invalidity.
- Evidence subject, selected resource, artifact digest, signer, trust, and predicate
  checks remain distinct.
- The package never installs or invokes a selected resource.
