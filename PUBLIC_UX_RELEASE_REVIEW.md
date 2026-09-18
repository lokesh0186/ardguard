# Public UX release review

Review date: 2026-09-18

Decision: `PUBLIC_UX_READY`

## Scope and product boundary

- Authoritative engine: public `ardguard==0.1.0b4`
- Beta 4 source commit: `7d6f3cffdad45372fdcb6b40253d6d9c90b49e96`
- Static UX source commit: `e5473ac4706ec3710bc8e29ed30ed5a22cb23f28`
- Final Pages workflow commit: `808e62aaebad48d55aeb1dbbda88270011ed10fb`
- Python package source, schemas, dependencies, and version: unchanged
- New Python package release: none

The browser renders precomputed input, decision, and DecisionReceipt fixtures. It does
not evaluate requirements, provider trust, evidence binding, eligibility, fallback,
reason codes, or hashes.

## Content gate

- The first screen states the discovery, eligibility, fallback, and caller-owned
  invocation boundary.
- Install and demo commands remain above advanced concepts in the README.
- The canonical example uses synthetic Server A/B/C candidates only.
- Stable, experimental, and demand-driven roadmap items are separated.
- No external endorsement, integration, impact, or adoption is claimed.
- Production ranks, facts, policies, and receipts are explicitly described as operator
  audit data that should not be published without review and appropriate redaction.

## Fixture provenance

- Scenario count: 12
- Generator: `scripts/generate_site_fixtures.py`
- Generator verification source: installed public PyPI wheel `ardguard==0.1.0b4`
- Hash manifest: `site/fixtures/hashes.sha256`
- Default scenario: `evidence-wrong-resource`
- Invocation field in every fixture: `NOT_PERFORMED`

The scenarios cover top-ranked selection, rank-preserving fallback, wrong-resource
evidence, unavailable access, excessive authority, unavailable and operationally failed
providers, conflicting trusted facts, stale evidence, all-ineligible candidates, missing
mandatory facts, and multiple eligible candidates.

## Automated quality results

| Gate | Result |
| --- | --- |
| Public-wheel fixture regeneration | PASS, 12 scenarios |
| Static build | PASS, 29 files, 232 KiB |
| Static links, CSP, content, and fixture integrity | PASS |
| Site unit tests | PASS, 5 tests |
| Full repository tests | PASS, 297 passed; 1 pre-existing socket-sandbox skip |
| Ruff | PASS |
| Strict mypy | PASS, 33 source files |
| JavaScript syntax | PASS, 4 files |
| Public repository boundary scan | PASS |
| Semantic Kernel community example | PASS, 1 test from pinned public dependencies |
| GitHub Pages validation and deployment | PASS |

The skipped core service test requires loopback socket binding and is unrelated to the
static Pages artifact. Browser verification ran with socket permission and had no skips.

## Browser and accessibility results

- Clean headless Chrome rendered the homepage and Explorer at desktop size.
- True mobile emulation used a 390 by 844 viewport; document width remained exactly 390
  pixels with no horizontal page overflow.
- All 12 scenarios loaded and exposed a 64-character receipt hash.
- Receipt Summary, Requirements, Candidates, Provenance, and Raw JSON views rendered.
- Keyboard-compatible tabs, semantic landmarks, table captions, skip links, visible
  focus, text status labels, and reduced-motion handling are present.
- The mobile scenario control uses a labeled native select.
- Documentation search returned the expected section for `operational error`.
- Copy-button behavior was verified with a deterministic browser clipboard stub; the UI
  copied `pip install ardguard` and reported `Copied`.
- Key light-theme text/status colors meet at least 4.5:1 contrast. The primary action
  uses `#0ecaf5` behind `#04202a`, a measured ratio of 8.66:1.

## Security and privacy results

- No live evaluator, account, credentials, persistence, analytics, telemetry, plugin
  loading, URL fetching, network provider, or resource invocation exists in the site.
- Fixture values render through DOM `textContent`; `innerHTML`, `document.write`,
  `eval`, and dynamic function construction are rejected by the site gate.
- The static CSP limits scripts, styles, images, and fixture fetches to bounded sources.
- The public artifact scanner rejects private paths, campaign references, credential-like
  strings, unsupported impact claims, and conference/submission material.
- There is no JavaScript package manager file or runtime dependency tree.
- GitHub Pages uses HTTPS and a separate workflow with read-only validation permissions;
  only the deploy job receives Pages and identity-token write permissions.
- GitHub Pages does not support a repository-defined response-header policy, so reliable
  `frame-ancestors` enforcement is not claimed.

## Deployment

- Public URL: `https://lokesh0186.github.io/ardguard/`
- Explorer: `https://lokesh0186.github.io/ardguard/explorer/`
- Documentation: `https://lokesh0186.github.io/ardguard/docs/`
- Workflow run: `https://github.com/lokesh0186/ardguard/actions/runs/35391599104`
- Workflow result: validation PASS, deployment PASS
- Pages mode: GitHub Actions workflow
- HTTPS enforced: yes

Post-deployment HTTPS and clean-browser checks confirmed the homepage, all scenarios,
receipt views, documentation search, copy behavior, and mobile layout.
