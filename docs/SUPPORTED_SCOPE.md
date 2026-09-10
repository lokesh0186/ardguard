# Tested support matrix

Beta 2 claims only the rows marked `SUPPORTED`.

| Surface | Status | Qualified version or boundary |
| --- | --- | --- |
| Python | `SUPPORTED` | CPython 3.10, 3.11, 3.12, 3.13 |
| Operating systems | `SUPPORTED` | Linux and macOS for core composition and CLI |
| ARD SearchResponse | `SUPPORTED` | ARD v0.91 at `aa3e598bb7752a9175897823234311216acfa864` |
| hf-discover JSON | `SUPPORTED` | 1.3.7 at `49c927439fcaa8f210cfd42186c0641acef579fa` |
| Static typed observations | `SUPPORTED` | Task, FactSet, Policy, and Decision v1 |
| Capability provider protocol | `SUPPORTED` | Python provider interface and typed observation |
| Authority policy | `SUPPORTED` | Exact required and maximum permission sets |
| Evidence receipt composition | `SUPPORTED` | authenticity, trust, subject, resource, and predicate checks |
| PyPI offline command provider | `EXPERIMENTAL` | Explicit `pypi-attestations` executable and repository policy |
| Sigstore offline command provider | `EXPERIMENTAL` | Explicit `sigstore` executable, identity, issuer, and trust seed |
| Kubernetes or cloud authority discovery | `ADVISORY` | Implement through an external trusted provider |
| Automatic network discovery | `UNSUPPORTED` | Feed a completed SearchResponse instead |
| Automatic installation or invocation | `UNSUPPORTED` | Caller-owned by design |
| Universal trust score | `UNSUPPORTED` | Not part of the product model |

`ardguard support --json` emits the machine-readable subset used by compatibility
checks. A new version is not claimed until a pinned fixture and CI coverage exist.
