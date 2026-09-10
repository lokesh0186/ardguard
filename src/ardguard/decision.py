"""Public evaluation API. This module never invokes a selected resource."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ardguard.eligibility import evaluate_candidate
from ardguard.models import (
    Candidate,
    CandidateVerdict,
    ContractError,
    Decision,
    FactSet,
    FinalDecision,
    Observation,
    ObservationState,
    Policy,
    TaskContract,
)
from ardguard.providers.base import FactProvider
from ardguard.reasons import ReasonCode
from ardguard.selectors import ranked, select


def _collect(
    candidates: Sequence[Candidate],
    task: TaskContract,
    facts: FactSet | None,
    providers: Iterable[FactProvider],
) -> tuple[Observation, ...]:
    observations = list(facts.observations if facts else ())
    for provider in providers:
        supplied = provider.observe(tuple(candidates), task)
        observations.extend(Observation.from_mapping(item.to_dict()) for item in supplied)
    keys = [(item.candidate_id, item.fact_type) for item in observations]
    if len(keys) != len(set(keys)):
        raise ContractError("multiple observations supplied for the same candidate and fact type")
    candidate_ids = {candidate.resource_id for candidate in candidates}
    unknown = sorted({item.candidate_id for item in observations} - candidate_ids)
    if unknown:
        raise ContractError(f"observations reference unknown candidates: {', '.join(unknown)}")
    return tuple(observations)


def evaluate(
    *,
    candidates: Sequence[Candidate],
    task: TaskContract,
    policy: Policy,
    facts: FactSet | None = None,
    providers: Iterable[FactProvider] = (),
) -> Decision:
    """Derive an explainable final decision without invoking any candidate."""

    if not candidates:
        raise ContractError("at least one candidate is required")
    ids = [candidate.resource_id for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ContractError("candidate identifiers must be unique")
    missing_checks = set(task.required_fact_types) - set(policy.required_checks)
    if missing_checks:
        names = ", ".join(sorted(item.value for item in missing_checks))
        raise ContractError(f"policy omits task-required checks: {names}")
    observations = _collect(candidates, task, facts, providers)
    indexed = {(item.candidate_id, item.fact_type): item for item in observations}
    evaluations = tuple(
        evaluate_candidate(
            candidate,
            task,
            policy.required_checks,
            {
                kind: indexed[(candidate.resource_id, kind)]
                for kind in policy.required_checks
                if (candidate.resource_id, kind) in indexed
            },
        )
        for candidate in candidates
    )
    ordered = ranked(evaluations)
    selected = select(evaluations, policy.selection_mode)
    if selected is not None:
        reason = (
            ReasonCode.SELECTION_TOP_RANKED_ELIGIBLE
            if selected.rank == ordered[0].rank and selected.candidate_id == ordered[0].candidate_id
            else ReasonCode.SELECTION_FALLBACK
        )
        return Decision.create(
            task_id=task.task_id,
            outcome=FinalDecision.SELECT,
            selected_candidate_id=selected.candidate_id,
            selected_rank=selected.rank,
            reason=reason,
            evaluations=ordered,
        )
    indeterminate = any(item.verdict is CandidateVerdict.INDETERMINATE for item in ordered)
    required_keys = {
        (candidate.resource_id, fact_type)
        for candidate in candidates
        for fact_type in policy.required_checks
    }
    operational = any(
        item.state is ObservationState.OPERATIONAL_ERROR
        and (item.candidate_id, item.fact_type) in required_keys
        for item in observations
    )
    if operational:
        outcome = policy.operational_error_action
        reason = (
            ReasonCode.SELECTION_ENGINE_ERROR
            if outcome is FinalDecision.ERROR
            else ReasonCode.SELECTION_INDETERMINATE
        )
    elif indeterminate:
        outcome = policy.indeterminate_action
        reason = ReasonCode.SELECTION_INDETERMINATE
    else:
        outcome = FinalDecision.ABSTAIN
        reason = ReasonCode.SELECTION_NO_ELIGIBLE
    return Decision.create(
        task_id=task.task_id,
        outcome=outcome,
        selected_candidate_id=None,
        selected_rank=None,
        reason=reason,
        evaluations=ordered,
    )
