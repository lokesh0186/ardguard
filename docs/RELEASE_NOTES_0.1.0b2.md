# ARDGuard 0.1.0b2

Beta 2 is an archival metadata and release-integration update to the Beta 1 product.

## Changes

- Refreshes and schema-validates `CITATION.cff` for software archives.
- Emits a new GitHub release event after the repository's Zenodo integration was enabled.
- Records the archival-only update in the changelog and release notes.

## Compatibility

There are no runtime decision, public API, schema, provider, adapter, or policy behavior
changes from `0.1.0b1`. Existing Beta 1 inputs and integrations remain compatible.

## Install

```bash
python -m pip install ardguard==0.1.0b2
ardguard demo
```

## Supported scope

The deterministic core, static typed observations, and current pinned adapters are
supported on CPython 3.10 through 3.13. The sandboxed offline PyPI and Sigstore command
provider is experimental. See `docs/SUPPORTED_SCOPE.md` for exact boundaries.

## Compatibility pins

- ARD v0.91, commit `aa3e598bb7752a9175897823234311216acfa864`
- hf-discover 1.3.7, commit `49c927439fcaa8f210cfd42186c0641acef579fa`

## Release assets

The GitHub release includes the wheel, source distribution, SHA-256 checksums, and build
provenance. PyPI publication uses GitHub OIDC Trusted Publishing.
