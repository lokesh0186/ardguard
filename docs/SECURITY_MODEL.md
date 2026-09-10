# Security model

## Protected decision boundary

ARDGuard protects the transition from ranked discovery output to the resource a caller
may consider for final use. Relevance is retained as ordering information. It is never
treated as capability, evidence, authority, or trust.

## Trusted components

- The operator controls the task contract and policy.
- Only explicitly enabled providers authorized by exact ID, version, and fact namespace
  are trusted to establish the observations they claim.
- The caller supplies the intended candidate set and preserves the returned decision
  before invoking anything.
- Cryptographic verifier roots and signer policies are deployment-specific trusted
  configuration.
- The local Python interpreter and operating system are not malicious.

A static FactSet is accepted only in explicit pre-established-fact mode with matching
provider trust. It is appropriate for replay, tests, and observations obtained through
a trusted transport. It is not proof that an untrusted caller measured those facts.

## Untrusted or uncertain inputs

- Discovery metadata, descriptions, tags, scores, and advertised capabilities do not
  establish eligibility.
- A fact cannot contain `eligible` or a candidate verdict. ARDGuard derives both.
- Generic facts reject common secret-bearing keys. Access facts describe credential
  categories and availability, never token or key values.
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

Malformed JSON, duplicate keys, unknown contract fields, duplicate candidate or fact
identifiers, duplicate explicit ranks, invalid digests, and omitted task-required checks
are rejected. Multiple distinctly identified facts are retained. Unresolved conflicts
produce a deterministic indeterminate result rather than a vote.

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

The v2 URL artifact resolver requires explicit network enablement, exact host
allowlisting, size and timeout limits, redirect revalidation, public peer-IP validation,
and proxy opt-in. Credential-bearing URLs and local, private, link-local, reserved, and
metadata-service targets fail closed by default. Core provides no implicit HTTP
transport. Injected transports must enforce the byte limit while streaming and after
decompression. The MCP provider is read-only and exposes only `initialize`
and `tools/list`; it never calls a tool. The local decision service binds only to
loopback, validates local Host headers, applies a 10-second connection timeout, limits
request bodies to 10 MiB, enables no plugins or network providers by default, sends no
permissive CORS header, and has no telemetry.

Third-party provider Python code executes inside the application trust boundary.
Entry-point discovery does not imply loading. Operators must explicitly enable a
provider and trust its package, identity, and transport. Provider output is revalidated,
bound to the requested candidate, and cannot directly issue `SELECT`.

## Out of scope

- A malicious local interpreter, kernel, root user, or same-UID process.
- Proving that a configured provider is honest.
- Trust-root compromise.
- Registry integrity outside the supplied candidate document.
- Installing, invoking, sandboxing, or remediating the selected resource.
- A universal trust score or universal least-authority policy.
