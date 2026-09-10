# ARDGuard 0.1.0b4

Beta 3 patch release for structured evidence conflict evaluation.

## Fixed

- Structured evidence facts with a non-null `evidence_identity` are now compared using
  their canonical public JSON representation.
- This prevents an internal immutable mapping representation from causing `TypeError`
  before the evidence-applicability evaluator can return its documented verdict.

## Compatibility

- No public API or schema changes.
- No provider, ranking, fallback, or invocation behavior changes.
- Existing successful decisions remain unchanged.
- ARDGuard still never invokes the selected resource.
