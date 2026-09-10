from __future__ import annotations

from conftest import load

from ardguard.adapters import parse_search_response
from ardguard.decision import evaluate
from ardguard.models import FactSet, FinalDecision, Policy, TaskContract
from ardguard.schema import validate_document


def _evaluate_example(name: str):
    discovery = load(f"examples/{name}/discovery.json")
    task = load(f"examples/{name}/task.json")
    policy = load(f"examples/{name}/policy.json")
    facts = load(f"examples/{name}/facts.json")
    validate_document("task", task)
    validate_document("policy", policy)
    validate_document("facts", facts)
    return evaluate(
        candidates=parse_search_response(discovery),
        task=TaskContract.from_mapping(task),
        policy=Policy.from_mapping(policy),
        facts=FactSet.from_mapping(facts),
    )


def test_basic_example_selects_without_invocation() -> None:
    decision = _evaluate_example("basic")
    assert decision.outcome is FinalDecision.SELECT
    assert decision.selected_rank == 1


def test_evidence_example_falls_back_on_subject_mismatch() -> None:
    decision = _evaluate_example("evidence")
    assert decision.outcome is FinalDecision.SELECT
    assert decision.selected_rank == 2
    assert "evidence.subject_mismatch" in [
        reason.value for reason in decision.evaluations[0].reasons
    ]


def test_authority_example_falls_back_from_excess_authority() -> None:
    decision = _evaluate_example("authority")
    assert decision.outcome is FinalDecision.SELECT
    assert decision.selected_rank == 2
    assert "authority.excessive" in [reason.value for reason in decision.evaluations[0].reasons]


def test_ard_v091_response_example_validates() -> None:
    value = load("examples/ard_search_response/search-response-v0.91.json")
    assert len(parse_search_response(value)) == 1
