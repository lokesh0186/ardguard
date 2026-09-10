# Changelog

All notable changes follow Keep a Changelog conventions. Versions follow semantic
versioning with Python prerelease identifiers.

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
