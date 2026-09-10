# Security model

## Protected decision boundary

ARDGuard protects the transition from ranked discovery output to the resource a caller
may consider for final use. Relevance is retained as ordering information. It is never
treated as capability, evidence, authority, or trust.

## Trusted components

- The operator controls the task contract and policy.
- Configured fact providers are trusted to establish the observations they claim.
- The caller supplies the intended candidate set and preserves the returned decision
  before invoking anything.
- Cryptographic verifier roots and signer policies are deployment-specific trusted
  configuration.
- The local Python interpreter and operating system are not malicious.

A static FactSet is appropriate for replay, tests, and observations obtained through a
trusted transport. It is not a proof that an untrusted caller measured those facts.

## Untrusted or uncertain inputs

- Discovery metadata, descriptions, tags, scores, and advertised capabilities do not
  establish eligibility.
- A fact cannot contain `eligible` or a candidate verdict. ARDGuard derives both.
- Missing facts do not pass.
- An unavailable provider does not pass.
- An operational verifier error is distinct from cryptographic invalidity.
- Authentic evidence for one digest does not apply to another digest.
- Authority outside the operator's maximum cannot become eligible because it can still
  complete the requested task.

## Fail-closed rules

A definite failed predicate produces `INELIGIBLE`. Unavailable or uncertain facts
produce `INDETERMINATE`. Policy may convert indeterminacy to `DEFER` or `ABSTAIN` and may
convert a provider operational error to `DEFER`, `ABSTAIN`, or `ERROR`. It cannot convert
uncertainty into `SELECT`.

Malformed JSON, duplicate keys, unknown contract fields, duplicate candidate/fact
observations, invalid digests, and omitted task-required checks are rejected.

## Evidence execution

The experimental offline command provider:

- retains the canonical distribution filename;
- uses a fresh per-call HOME, XDG, input, and temporary directory;
- removes Python injection and proxy environment variables;
- invokes the verifier with its offline option;
- requires an OS network-denying sandbox;
- permits writes only inside its scratch on macOS;
- accepts explicit trust-seed files under a path-safe cache root;
- records executable, artifact, evidence, standard-output, standard-error, and trust
  seed hashes;
- treats unrecognized nonzero exits, signals, sandbox failures, and denied operations as
  operational errors;
- treats a nonzero exit as invalid evidence only for the exact configured verifier
  rejection markers.

This provider is experimental because OS sandbox availability and verifier CLI
stability differ by platform. The deterministic receipt-consumption and eligibility
composition paths remain supported.

## Filesystem handling

The CLI rejects symlink inputs and outputs, limits each JSON input to 10 MiB, refuses to
overwrite by default, and writes through a same-directory temporary file followed by an
atomic replace. It does not traverse candidate URLs or paths.

## Network and telemetry

The core and CLI make no network request and emit no telemetry. Discovery is performed
before ARDGuard. The experimental evidence provider refuses to run without a supported
network-denying sandbox and uses verifier offline mode.

## Out of scope

- A malicious local interpreter, kernel, root user, or same-UID process.
- Proving that a configured provider is honest.
- Trust-root compromise.
- Registry integrity outside the supplied candidate document.
- Installing, invoking, sandboxing, or remediating the selected resource.
- A universal trust score or universal least-authority policy.
