# Decisions and reason codes

## Candidate verdicts

| Verdict | Meaning |
| --- | --- |
| `ELIGIBLE` | Every configured required fact passed. |
| `INELIGIBLE` | At least one configured required fact definitely failed. |
| `INDETERMINATE` | No definite failure exists, but at least one required fact is missing or uncertain. |

## Final decisions

| Decision | Meaning |
| --- | --- |
| `SELECT` | A specific candidate was established as eligible. |
| `DEFER` | Required eligibility remains uncertain and retry or external review may help. |
| `ABSTAIN` | No candidate will be selected under the configured policy. |
| `ERROR` | A provider or engine failure prevented a safe final decision. |

## Stable reason families

Capability reasons are `capability.verified`, `capability.mismatch`,
`capability.unavailable`, `capability.indeterminate`, and
`capability.operational_error`.

Evidence reasons are `evidence.authentic`, `evidence.invalid`,
`evidence.subject_mismatch`, `evidence.predicate_insufficient`,
`evidence.wrong_resource_association`, `evidence.signer_untrusted`,
`evidence.verifier_unavailable`, `evidence.verifier_operational_error`, and
`evidence.indeterminate`.

Authority reasons are `authority.within_policy`, `authority.excessive`,
`authority.unknown`, `authority.unavailable`, and `authority.operational_error`.

Selection reasons are `selection.top_ranked_eligible`,
`selection.fallback_to_lower_ranked_eligible`, `selection.no_eligible_candidate`,
`selection.eligibility_indeterminate`, and `selection.engine_error`.

Every code has a programmatic definition in `ardguard.reasons.REASON_DEFINITIONS`
covering retry, rejection, and fail-closed behavior.
