"""Rank-preserving final selection and fallback."""

from __future__ import annotations

from ardguard.models import CandidateEvaluation, CandidateVerdict, SelectionMode


def ranked(evaluations: tuple[CandidateEvaluation, ...]) -> tuple[CandidateEvaluation, ...]:
    """Return deterministic backend-rank order.

    Resource identity is only a deterministic tie-breaker when a caller supplies the
    same explicit rank more than once. ARDGuard never changes or manufactures scores.
    """

    return tuple(sorted(evaluations, key=lambda item: (item.rank, item.candidate_id)))


def select(
    evaluations: tuple[CandidateEvaluation, ...], mode: SelectionMode
) -> CandidateEvaluation | None:
    ordered = ranked(evaluations)
    if not ordered:
        return None
    if mode is SelectionMode.TOP_RANKED_ONLY:
        return ordered[0] if ordered[0].verdict is CandidateVerdict.ELIGIBLE else None
    return next((item for item in ordered if item.verdict is CandidateVerdict.ELIGIBLE), None)
