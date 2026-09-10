from __future__ import annotations

import copy

import pytest

from ardguard.decision import evaluate
from ardguard.models import ContractError, FactSet, FactType, FinalDecision, Policy
from ardguard.providers.static import StaticFactProvider


def test_fallback_selects_rank_two(fallback_inputs) -> None:
    candidates, task, policy, facts = fallback_inputs
    decision = evaluate(candidates=candidates, task=task, policy=policy, facts=facts)
    assert decision.outcome is FinalDecision.SELECT
    assert decision.selected_rank == 2
    assert decision.reason.value == "selection.fallback_to_lower_ranked_eligible"
    assert decision.evaluations[0].score == 98
    assert decision.evaluations[1].score == 93


def test_top_ranked_only_abstains(fallback_inputs, fallback_documents) -> None:
    candidates, task, _, facts = fallback_inputs
    _, _, policy_document, _ = fallback_documents
    changed = copy.deepcopy(policy_document)
    changed["selection_mode"] = "top-ranked-only"
    decision = evaluate(
        candidates=candidates,
        task=task,
        policy=Policy.from_mapping(changed),
        facts=facts,
    )
    assert decision.outcome is FinalDecision.ABSTAIN
    assert decision.selected_candidate_id is None


def test_missing_fact_defers(fallback_inputs, fallback_documents) -> None:
    candidates, task, policy, _ = fallback_inputs
    _, _, _, facts_document = fallback_documents
    changed = copy.deepcopy(facts_document)
    changed["observations"] = [
        item
        for item in changed["observations"]
        if not (item["candidate_id"].endswith("rank-two") and item["fact_type"] == "evidence")
    ]
    decision = evaluate(
        candidates=candidates,
        task=task,
        policy=policy,
        facts=FactSet.from_mapping(changed),
    )
    assert decision.outcome is FinalDecision.DEFER


def test_operational_error_returns_error(fallback_inputs, fallback_documents) -> None:
    candidates, task, policy, _ = fallback_inputs
    _, _, _, facts_document = fallback_documents
    changed = copy.deepcopy(facts_document)
    for item in changed["observations"]:
        if item["fact_type"] == "capability":
            item["state"] = "OPERATIONAL_ERROR"
            item["payload"] = {}
    decision = evaluate(
        candidates=candidates,
        task=task,
        policy=policy,
        facts=FactSet.from_mapping(changed),
    )
    assert decision.outcome is FinalDecision.ERROR


def test_decision_hash_is_deterministic(fallback_inputs) -> None:
    candidates, task, policy, facts = fallback_inputs
    first = evaluate(candidates=candidates, task=task, policy=policy, facts=facts)
    second = evaluate(candidates=candidates, task=task, policy=policy, facts=facts)
    assert first.to_dict() == second.to_dict()


def test_fixed_explicit_ranks_remove_input_order_dependence(fallback_inputs) -> None:
    candidates, task, policy, facts = fallback_inputs
    first = evaluate(candidates=candidates, task=task, policy=policy, facts=facts)
    second = evaluate(candidates=tuple(reversed(candidates)), task=task, policy=policy, facts=facts)
    assert first.to_dict() == second.to_dict()


def test_adding_ineligible_candidate_does_not_displace_selected(fallback_inputs) -> None:
    candidates, task, policy, facts = fallback_inputs
    decision = evaluate(candidates=candidates, task=task, policy=policy, facts=facts)
    assert decision.selected_candidate_id == candidates[1].resource_id


def test_empty_and_duplicate_candidate_sets_fail(fallback_inputs) -> None:
    candidates, task, policy, facts = fallback_inputs
    with pytest.raises(ContractError, match="at least one"):
        evaluate(candidates=(), task=task, policy=policy, facts=facts)
    with pytest.raises(ContractError, match="unique"):
        evaluate(candidates=(candidates[0], candidates[0]), task=task, policy=policy, facts=facts)


def test_policy_cannot_omit_task_required_check(fallback_inputs) -> None:
    candidates, task, policy, facts = fallback_inputs
    reduced = Policy(
        policy.selection_mode,
        (FactType.CAPABILITY, FactType.EVIDENCE),
        policy.indeterminate_action,
        policy.operational_error_action,
    )
    with pytest.raises(ContractError, match="omits task-required checks: authority"):
        evaluate(candidates=candidates, task=task, policy=reduced, facts=facts)


def test_provider_input_is_revalidated(fallback_inputs) -> None:
    candidates, task, policy, facts = fallback_inputs
    provider = StaticFactProvider(facts)
    decision = evaluate(candidates=candidates, task=task, policy=policy, providers=(provider,))
    assert decision.outcome is FinalDecision.SELECT


def test_multiple_sources_cannot_supply_same_fact(fallback_inputs) -> None:
    candidates, task, policy, facts = fallback_inputs
    provider = StaticFactProvider(facts)
    with pytest.raises(ContractError, match="multiple observations"):
        evaluate(
            candidates=candidates,
            task=task,
            policy=policy,
            facts=facts,
            providers=(provider,),
        )


def test_observation_for_unknown_candidate_fails(fallback_inputs, fallback_documents) -> None:
    candidates, task, policy, _ = fallback_inputs
    _, _, _, facts_document = fallback_documents
    changed = copy.deepcopy(facts_document)
    changed["observations"][0]["candidate_id"] = "urn:example:unknown"
    with pytest.raises(ContractError, match="unknown candidates"):
        evaluate(
            candidates=candidates,
            task=task,
            policy=policy,
            facts=FactSet.from_mapping(changed),
        )


def test_top_ranked_eligible_has_explicit_reason(fallback_inputs, fallback_documents) -> None:
    candidates, task, policy, _ = fallback_inputs
    _, _, _, facts_document = fallback_documents
    changed = copy.deepcopy(facts_document)
    first_capability = next(
        item
        for item in changed["observations"]
        if item["candidate_id"].endswith("rank-one") and item["fact_type"] == "capability"
    )
    first_capability["payload"]["verified_capabilities"] = ["records.read"]
    decision = evaluate(
        candidates=candidates,
        task=task,
        policy=policy,
        facts=FactSet.from_mapping(changed),
    )
    assert decision.outcome is FinalDecision.SELECT
    assert decision.selected_rank == 1
    assert decision.reason.value == "selection.top_ranked_eligible"


def test_all_ineligible_abstains(fallback_inputs, fallback_documents) -> None:
    candidates, task, policy, _ = fallback_inputs
    _, _, _, facts_document = fallback_documents
    changed = copy.deepcopy(facts_document)
    for item in changed["observations"]:
        if item["fact_type"] == "capability":
            item["payload"]["verified_capabilities"] = ["records.write"]
    decision = evaluate(
        candidates=candidates,
        task=task,
        policy=policy,
        facts=FactSet.from_mapping(changed),
    )
    assert decision.outcome is FinalDecision.ABSTAIN
    assert decision.reason.value == "selection.no_eligible_candidate"


@pytest.mark.parametrize("action", ["DEFER", "ABSTAIN"])
def test_operational_error_policy_action_is_honored(
    fallback_inputs, fallback_documents, action: str
) -> None:
    candidates, task, _, _ = fallback_inputs
    _, _, policy_document, facts_document = fallback_documents
    changed_facts = copy.deepcopy(facts_document)
    for item in changed_facts["observations"]:
        if item["fact_type"] == "capability":
            item["state"] = "OPERATIONAL_ERROR"
            item["payload"] = {}
    changed_policy = copy.deepcopy(policy_document)
    changed_policy["operational_error_action"] = action
    decision = evaluate(
        candidates=candidates,
        task=task,
        policy=Policy.from_mapping(changed_policy),
        facts=FactSet.from_mapping(changed_facts),
    )
    assert decision.outcome.value == action
    assert decision.reason.value == "selection.eligibility_indeterminate"
