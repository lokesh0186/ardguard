# Contributing

ARDGuard welcomes small, reviewable improvements backed by deterministic tests.

## Useful contributions

- adapter compatibility fixes with pinned real wire fixtures;
- provider implementations with explicit observation and provenance contracts;
- reason-code and explanation improvements;
- malformed-input and fail-closed regressions;
- integration examples that preserve external ranking and caller-owned invocation;
- documentation and first-run ergonomics.

Open an issue before adding a new trust surface, network behavior, policy language,
registry, installer, or invocation mechanism.

## Development setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/mypy src/ardguard
.venv/bin/pytest --cov=ardguard --cov-branch
```

Run package checks before a pull request:

```bash
.venv/bin/python -m build
.venv/bin/python scripts/check_package.py dist
```

## Required boundaries

- Do not add automatic resource installation or invocation.
- Do not convert relevance scores into trust or eligibility.
- Do not let callers or providers submit a final eligibility verdict.
- Do not turn absence, unavailability, or operational error into success.
- Do not collapse evidence authenticity and applicability.
- Do not add implicit network access or telemetry.
- Do not commit credentials, private evidence, local absolute paths, or generated
  package artifacts.

Security-relevant changes need a failing-before and passing-after test. Changed
security-critical modules should retain at least 90 percent branch coverage. Do not
delete, skip, or weaken a regression to satisfy CI.

## Pull requests

Keep each pull request focused. State the exact contract or compatibility behavior,
include the pinned upstream version when applicable, and explain any public schema or
reason-code impact. Public claims should describe reproduced behavior without calling
an external project insecure.
