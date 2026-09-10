# Security policy

ARDGuard `0.1.0b1` is a Beta 1 prerelease. The deterministic decision core, closed
contracts, ARD v0.91 adapter, hf-discover 1.3.7 adapter, and static observation path are
supported. The sandboxed offline verifier command provider is experimental.

## Supported versions

| Version | Security support |
| --- | --- |
| Latest `0.1.x` prerelease | Supported within its documented scope |
| Earlier or unreleased builds | Upgrade to the latest published prerelease |

## Report a vulnerability

Use the repository's private GitHub security-advisory channel for security-sensitive
reports. Do not post credentials, private resource metadata, unpublished third-party
evidence, or trust material in a public issue.

Include the ARDGuard version, Python version, operating system, provider identity, the
smallest shareable input, actual decision, and expected fail-closed behavior.

## High-priority correctness issues

The following are treated as security-boundary issues:

- relevance score influences eligibility;
- a caller can self-assert final eligibility;
- a missing or uncertain required fact produces `SELECT`;
- an operational verifier error is reported as invalid cryptography;
- evidence for artifact A authorizes candidate B;
- authority beyond the configured maximum is eligible;
- fallback selects a candidate that was not evaluated;
- malformed input fails open;
- the CLI installs or invokes a resource;
- a path escapes the authorized local boundary.

Security-sensitive fixes require a failing-before test, a passing-after test, and an
explicit explanation of the affected boundary. Assertions may not be weakened to make
a regression pass.

## Sensitive data

ARDGuard has no telemetry. Decisions and verifier receipts may still contain resource
identifiers, provider identities, paths, evidence digests, and diagnostics. Review them
before sharing.

The detailed trust and failure model is in
[`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md).
