# ARD compatibility

ARDGuard is qualified against ARD v0.91 at commit
`aa3e598bb7752a9175897823234311216acfa864`.

Supported SearchResponse behavior:

- top-level `results` is required;
- optional `referrals` and `pageToken` are validated structurally;
- each result requires only `identifier`, as specified by the pinned normative prose,
  CDDL, and conformance checker;
- optional `displayName`, `type`, integer `score` from 0 through 100, `source`, `url`,
  and inline object `data` are validated when present;
- an identifier-only result is valid and does not trigger any invented full-entry lookup;
- list position becomes preliminary rank;
- scores and original entry fields are preserved;
- duplicate identifiers fail;
- unsupported top-level response fields fail clearly.

ARD v0.91 defines `score` as semantic relevance and explicitly says that it is not a
security or trust score. ARDGuard does not reinterpret it.

ARD entries may carry `trustManifest` and namespaced extensions. Those opaque fields
remain available in `Candidate.original`, but they become eligibility facts only after a
configured provider establishes an observation.

ARDGuard preserves namespaced extension terms. It does not claim full semantic JSON-LD
expansion, retrieve remote contexts, resolve aliases, execute JSONPath, or reinterpret
unknown extension values. The bounded field resolver accepts canonical terms,
namespaced terms, and literal paths under `metadata` or `trustManifest`.

The adapter does not fetch referrals, candidate URLs, or full entries by identifier.
Inline data, an explicit URL resolver, or a configured fact provider may add facts.
When information is absent, eligibility remains indeterminate according to policy.
