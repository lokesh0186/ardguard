# Tested support matrix

Beta 3 claims only the rows marked `SUPPORTED`.

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

Beta 3 adds the following deliberately scoped surfaces. They remain `EXPERIMENTAL`:

| Surface | Status | Qualified boundary |
| --- | --- | --- |
| Generic TaskContract, FactSet, Policy, Decision | `EXPERIMENTAL` | Versioned v2 schemas |
| Provider plugins | `EXPERIMENTAL` | Explicit `ardguard.fact_providers` entry points |
| Generic constraints and policy packs | `EXPERIMENTAL` | Closed predicate set; no arbitrary code |
| MCP introspection | `EXPERIMENTAL` | Read-only `initialize` and `tools/list` transport |
| A2A, OpenAPI, and Skill artifacts | `EXPERIMENTAL` | Offline parsing only |
| Neuronto SearchResponse | `EXPERIMENTAL` | Pinned response extension adapter |
| Local HTTP service | `EXPERIMENTAL` | Versioned `/v1` API on loopback only |
| JSON stdin/stdout | `EXPERIMENTAL` | One v2 bundle to one decision |
| OpenARD and MCP Gateway Registry | `ADVISORY` | Pinned negative or shape fixtures only |

`ardguard support --json` and `docs/support-matrix.json` provide machine-readable
records. Fixture parsing does not imply full upstream integration support.
