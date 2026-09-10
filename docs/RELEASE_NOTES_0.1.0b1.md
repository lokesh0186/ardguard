# ARDGuard 0.1.0b1

Beta 1 provides a compact, installable eligibility and fallback layer for consumers of
ranked agentic resource discovery results.

## Highlights

- Deterministic JSON and Python APIs.
- Rank-preserving fallback across task-specific capability, evidence, and authority.
- Explicit uncertainty and operational-error handling.
- ARD v0.91 and hf-discover 1.3.7 compatibility fixtures.
- Stable reasons and explainable decision records.
- No automatic installation, invocation, telemetry, or implicit network access.

## Install

```bash
python -m pip install ardguard==0.1.0b1
ardguard demo
```

## Supported scope

The deterministic core, static typed observations, and current pinned adapters are
supported on CPython 3.10 through 3.13. The sandboxed offline PyPI and Sigstore command
provider is experimental. See `docs/SUPPORTED_SCOPE.md` for exact boundaries.

## Compatibility

- ARD v0.91, commit `aa3e598bb7752a9175897823234311216acfa864`
- hf-discover 1.3.7, commit `49c927439fcaa8f210cfd42186c0641acef579fa`

## Release assets

The GitHub release includes the wheel, source distribution, SHA-256 checksums, and
build provenance. PyPI publication uses GitHub OIDC Trusted Publishing.
