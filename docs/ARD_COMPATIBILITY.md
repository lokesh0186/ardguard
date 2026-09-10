# ARD compatibility

Beta 2 is qualified against ARD v0.91 at commit
`aa3e598bb7752a9175897823234311216acfa864`.

Supported SearchResponse behavior:

- top-level `results` is required;
- optional `referrals` and `pageToken` are validated structurally;
- each result requires `identifier`, integer `score` from 0 through 100, and `source`;
- list position becomes preliminary rank;
- scores and original entry fields are preserved;
- duplicate identifiers fail;
- unsupported top-level response fields fail clearly.

ARD v0.91 defines `score` as semantic relevance and explicitly says that it is not a
security or trust score. ARDGuard does not reinterpret it.

ARD entries may carry `trustManifest` and namespaced extensions. Those opaque fields
remain available in `Candidate.original`, but they become eligibility facts only after a
configured provider establishes an observation.

The adapter does not fetch referrals or candidate URLs. Feed each completed discovery
response to ARDGuard separately.
