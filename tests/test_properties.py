from __future__ import annotations

import copy

import pytest

from ardguard.adapters import parse_search_response
from ardguard.decision import evaluate
from ardguard.models import CandidateVerdict, ContractError, FactSet, Policy, TaskContract


def test_all_scores_leave_eligibility_unchanged(fallback_documents) -> None:
    discovery, task_document, policy_document, fact_document = fallback_documents
    task = TaskContract.from_mapping(task_document)
    policy = Policy.from_mapping(policy_document)
    facts = FactSet.from_mapping(fact_document)
    for score in range(0, 101, 10):
        changed = copy.deepcopy(discovery)
        changed["results"][0]["score"] = score
        decision = evaluate(
            candidates=parse_search_response(changed), task=task, policy=policy, facts=facts
        )
        first = next(
            item for item in decision.evaluations if item.candidate_id.endswith("rank-one")
        )
        assert first.verdict is CandidateVerdict.INELIGIBLE
        assert decision.selected_candidate_id.endswith("rank-two")


def test_equal_explicit_rank_is_rejected(fallback_inputs) -> None:
    candidates, task, policy, facts = fallback_inputs
    first = candidates[0].__class__(
        candidates[0].resource_id,
        candidates[0].source,
        1,
        candidates[0].score,
        candidates[0].media_type,
        candidates[0].metadata,
        candidates[0].original,
    )
    second = candidates[1].__class__(
        candidates[1].resource_id,
        candidates[1].source,
        1,
        candidates[1].score,
        candidates[1].media_type,
        candidates[1].metadata,
        candidates[1].original,
    )
    with pytest.raises(ContractError, match="ranks must be unique"):
        evaluate(candidates=(first, second), task=task, policy=policy, facts=facts)
