# Evidence

ARDGuard keeps four questions separate:

1. Did a functioning verifier accept the evidence cryptographically?
2. Does the signer and trust root satisfy this task's policy?
3. Does the statement contain the required predicate?
4. Does the evidence name the exact selected resource and artifact digest?

Authentic evidence may still be inapplicable. A valid statement for artifact A cannot
authorize artifact B.

## Typed verifier outcomes

- `AVAILABLE_VALID`
- `AVAILABLE_INVALID`
- `UNAVAILABLE`
- `OPERATIONAL_ERROR`
- `RESULT_INDETERMINATE`

Only the first two are cryptographic conclusions. The others keep authenticity nullable
or absent and fail closed. In particular, an import error, sandbox failure, timeout,
signal, unavailable trust seed, or unrecognized nonzero exit is operational, not an
invalid signature.

## Offline command provider

The experimental provider supplies command factories for `pypi-attestations verify
pypi --offline` and `sigstore verify identity --offline`. It materializes the authentic
evidence-bound artifact under its canonical filename. This matters for package tools
whose verifier semantics include the distribution basename.

The provider may verify authenticity against evidence-bound artifact A while recording
that the selected candidate refers to artifact B. The composer then returns
`evidence.subject_mismatch`; it does not mislabel the valid evidence as cryptographically
invalid.

Sigstore deployments must supply the exact offline trust-seed files expected beneath
`XDG_CACHE_HOME` and declare the trust-root identity used by policy. Raw verifier
transcript and executable hashes remain in provenance.
