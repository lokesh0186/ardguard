# Public UX baseline audit

Audit date: 2026-09-18

Public baseline: `ardguard==0.1.0b4`, repository commit
`7d6f3cffdad45372fdcb6b40253d6d9c90b49e96`

## First-time developer test

### What is clear

- The repository immediately states that ARDGuard sits between discovery and
  final use.
- Installation and `ardguard demo` are on lines 20–23 of the README.
- The README explicitly says ARDGuard never installs or invokes a resource.
- The offline demo demonstrates lower-ranked fallback with real CLI output.
- Security boundaries, supported scope, compatibility, and contribution policy
  are documented.

### What slows comprehension

- The first result appears on line 25, after the visitor has already met
  eligibility, capability, evidence, authority, defer, abstain, error, and the
  Beta-3/v1/v2 status distinction.
- The demo has two candidates, so the relationship among invalid applicability,
  an eligible fallback, and operational uncertainty is not visible together.
- The first screen explains the mechanism in prose but offers no visual
  candidate comparison or browser-based trial.
- The phrase “eligibility boundary” is accurate but still asks a new visitor to
  infer the practical before/after behavior.
- Integrations are dispersed across later README sections and individual files.
- DecisionReceipt is an advanced implementation detail rather than a visible
  auditability benefit.

## GitHub landing page

The current landing page answers the core problem and invocation boundary, but
not all first-visit questions within one screen:

| Question | Baseline answer |
| --- | --- |
| What problem does it solve? | Clear after reading two paragraphs. |
| Where does it sit? | Clear at the architecture diagram on line 38. |
| How do I try it? | Clear at line 20. |
| Does it invoke anything? | Clear in the opening paragraph and demo. |
| Product or research repository? | Product cues are strong, but the README leads with contract language rather than a guided product experience. |
| What does fallback mean? | Explained at line 112, after API examples. |
| What integrations exist? | Listed across documentation and examples, not visible as a compact integration map. |

Repository metadata at audit time:

- Description: `Eligibility-aware final selection and fallback for agentic resource discovery`
- Homepage: unset
- GitHub Pages: not configured
- Topics: `agentic-resource-discovery`, `fallback`, `policy`, `python`, `security`
- Social preview: not relied upon by this program

The description is accurate but does not contain common discovery terms such as
MCP, agent tools, access feasibility, or tool selection.

## README timing

- Total lines: 196
- First install command: line 21
- First runnable demo command: line 22
- First concrete output: line 25
- First fallback explanation in prose: line 112
- Technical concepts introduced before payoff: approximately nine
  (`eligibility boundary`, ranked discovery, capability, evidence, authority,
  defer, abstain, error, and v1/v2 status)

The README is disciplined and substantially better than a research repository,
but the visitor must read terminology before seeing the three-state decision
that makes ARDGuard distinctive.

## Documentation inventory

Current product documentation covers:

- architecture and integration;
- ARD v0.91 and hf-discover compatibility;
- decisions and stable reason codes;
- evidence and authority;
- FactProvider and extensibility boundaries;
- eligibility packs and supported scope;
- release notes and OpenAPI.

The missing public-experience layer is not technical documentation. It is:

- a browsable fallback demonstration;
- a receipt viewer;
- a short conceptual path from discovery to eligibility to caller-owned
  invocation;
- local documentation search;
- copyable integration starters grouped by integration shape.

## PyPI

PyPI `0.1.0b4` uses the repository README as its long description. It therefore
inherits the same strengths and first-screen density.

Current project links:

- Homepage: GitHub repository
- Repository: GitHub repository
- Documentation: README anchor
- Changelog: repository changelog
- Security: GitHub security policy

The package has correct Python compatibility and beta classifiers. There is no
dedicated documentation or Explorer link. Fixing PyPI project-link metadata
would require a package release; this UX program does not justify Beta 5, so the
existing PyPI metadata remains unchanged.

## Search discoverability

The repository is discoverable for `agentic resource discovery`, `fallback`,
and Python policy terms. A developer searching for `MCP eligibility`, `MCP
fallback`, `agent tool authorization`, `tool selection policy`, or `resource
discovery safety` receives little immediate lexical help from the description
or topics.

Accurate natural-language coverage should be added to the README and docs, not
as keyword pages. `MCP` must be described as an integration boundary, not an
official upstream integration claim.

## Baseline conclusion

The engine and product boundaries are credible. The adoption obstacle is trial
friction and invisible explainability, not missing eligibility mechanisms.
The correct next step is a static, receipt-backed Explorer plus a simpler
README and navigable documentation, not a new Python release.
