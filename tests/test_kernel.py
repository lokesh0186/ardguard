from __future__ import annotations

import json
from pathlib import Path

import pytest

from ardguard.adapters.ard import parse_search_response
from ardguard.compat import facts_v1_to_v2, task_v1_to_v2
from ardguard.constraints import compare, default_evaluator_registry, resolve_candidate_field
from ardguard.decision import evaluate
from ardguard.kernel import (
    Fact,
    FactOperationalState,
    GenericFactSet,
    GenericTaskContract,
    KernelPolicy,
    ProviderTrust,
    Requirement,
    RequirementStatus,
    evaluate_kernel,
)
from ardguard.models import ContractError, FactSet, Policy, TaskContract
from ardguard.packs import builtin_evaluators
from ardguard.providers.generic import StaticGenericProvider
from ardguard.requirement_packs import evaluate_dependency_graph

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text())


def generic_inputs():
    return (
        parse_search_response(load("examples/generic/discovery.json")),
        GenericTaskContract.from_mapping(load("examples/generic/task.json")),
        KernelPolicy.from_mapping(load("examples/generic/policy.json")),
        GenericFactSet.from_mapping(load("examples/generic/facts.json")),
    )


def trusted(provider_id: str, *fact_types: str, preestablished: bool = False) -> KernelPolicy:
    return KernelPolicy(
        provider_trust=(ProviderTrust(provider_id, "1", frozenset(fact_types)),),
        preestablished_fact_mode=preestablished,
    )


def test_unrelated_fact_type_works_without_core_edit() -> None:
    candidates, task, policy, facts = generic_inputs()
    decision = evaluate_kernel(
        candidates=candidates,
        task=task,
        policy=policy,
        fact_set=facts,
        evaluators=default_evaluator_registry(("deployment.region",)),
    )
    assert decision.selected_candidate_id.endswith(":east")
    assert decision.reason_code == "selection.fallback_to_lower_ranked_eligible"
    assert len(decision.decision_sha256) == 64
    assert len(decision.receipt["receipt_sha256"]) == 64


def test_requirement_and_fact_cannot_assert_eligibility() -> None:
    with pytest.raises(ContractError, match="cannot assert"):
        Requirement("r", "x.fact", {"nested": {"eligible": True}})
    with pytest.raises(ContractError, match="cannot assert"):
        Fact(
            "f",
            "c",
            "x.fact",
            "provider.x",
            "1",
            FactOperationalState.AVAILABLE,
            {"final_decision": "SELECT"},
        )


def test_nonavailable_fact_cannot_carry_negative_value() -> None:
    with pytest.raises(ContractError, match="cannot carry"):
        Fact("f", "c", "x.fact", "provider.x", "1", FactOperationalState.OPERATIONAL_ERROR, False)


def test_fact_timestamps_require_rfc3339_timezone() -> None:
    with pytest.raises(ContractError, match="RFC3339"):
        Fact(
            "f",
            "c",
            "x.fact",
            "provider.x",
            "1",
            FactOperationalState.AVAILABLE,
            "x",
            observed_at="not-a-time",
        )
    with pytest.raises(ContractError, match="timezone"):
        Fact(
            "f",
            "c",
            "x.fact",
            "provider.x",
            "1",
            FactOperationalState.AVAILABLE,
            "x",
            observed_at="2026-09-10T10:00:00",
        )


def test_provider_failure_becomes_error_not_unsatisfied() -> None:
    candidates, task, _, _ = generic_inputs()

    class Broken:
        provider_id = "test.broken"
        provider_version = "1"
        supported_fact_types = frozenset({"deployment.region"})

        def collect(self, candidate, task, requirements, context):
            raise RuntimeError("boom")

    decision = evaluate_kernel(
        candidates=candidates,
        task=task,
        policy=trusted("test.broken", "deployment.region"),
        providers=(Broken(),),
        evaluators=default_evaluator_registry(("deployment.region",)),
    )
    assert decision.outcome.value == "ERROR"
    assert all(item.status is RequirementStatus.ERROR for item in decision.evaluations)


def test_duplicate_provider_id_fails_closed() -> None:
    candidates, task, policy, _ = generic_inputs()
    empty = StaticGenericProvider("test.same", "1", frozenset({"deployment.region"}), {})
    with pytest.raises(ContractError, match="duplicate provider"):
        evaluate_kernel(
            candidates=candidates,
            task=task,
            policy=policy,
            providers=(empty, empty),
            evaluators=default_evaluator_registry(("deployment.region",)),
        )


def test_provider_cannot_supply_fact_for_other_candidate() -> None:
    candidates, task, _, _ = generic_inputs()
    wrong = Fact(
        "wrong",
        "other",
        "deployment.region",
        "test.static",
        "1",
        FactOperationalState.AVAILABLE,
        "us-east-1",
    )
    provider = StaticGenericProvider(
        "test.static", "1", frozenset({"deployment.region"}), {candidates[0].resource_id: (wrong,)}
    )
    with pytest.raises(ContractError, match="different candidate"):
        evaluate_kernel(
            candidates=candidates,
            task=task,
            policy=trusted("test.static", "deployment.region"),
            providers=(provider,),
            evaluators=default_evaluator_registry(("deployment.region",)),
        )


def test_rank_changes_do_not_change_eligibility() -> None:
    candidates, task, policy, facts = generic_inputs()
    decision = evaluate_kernel(
        candidates=candidates,
        task=task,
        policy=policy,
        fact_set=facts,
        evaluators=default_evaluator_registry(("deployment.region",)),
    )
    changed = tuple(
        candidate.__class__(
            candidate.resource_id,
            candidate.source,
            3 - candidate.rank,
            candidate.score,
            candidate.media_type,
            candidate.metadata,
            candidate.original,
        )
        for candidate in candidates
    )
    reordered = evaluate_kernel(
        candidates=changed,
        task=task,
        policy=policy,
        fact_set=facts,
        evaluators=default_evaluator_registry(("deployment.region",)),
    )
    states = {item.candidate_id: item.status for item in decision.evaluations}
    assert states == {item.candidate_id: item.status for item in reordered.evaluations}
    assert reordered.selected_candidate_id.endswith(":east")


@pytest.mark.parametrize(
    ("predicate", "actual", "expected", "result"),
    [
        ("equals", "x", "x", True),
        ("not_equals", "x", "y", True),
        ("one_of", "x", ["x", "y"], True),
        ("subset_of", ["read"], ["read", "write"], True),
        ("contains", ["read", "write"], "read", True),
        ("numeric_min", 3, 2, True),
        ("numeric_max", 3, 4, True),
        ("semver_min", "1.2.3", "1.2.0", True),
        ("semver_max", "1.2.3", "2.0.0", True),
        ("digest_equals", "a" * 64, "a" * 64, True),
        ("identity_equals", "spiffe://example/workload", "spiffe://example/workload", True),
        ("scope_subset", ["read"], ["read", "write"], True),
        ("boolean_asserted_with_provenance", True, True, True),
    ],
)
def test_closed_constraint_primitives(predicate, actual, expected, result) -> None:
    assert compare(predicate, actual, expected) is result


def test_constraints_fail_on_incompatible_types_and_unknown_predicate() -> None:
    with pytest.raises(TypeError):
        compare("equals", 1, "1")
    with pytest.raises(ContractError, match="unsupported predicate"):
        compare("python_eval", "x", "x")


def test_safe_field_resolver_preserves_extension_and_rejects_jsonpath() -> None:
    candidate = generic_inputs()[0][0]
    assert resolve_candidate_field(candidate, "metadata.example:opaque") == "preserved"
    with pytest.raises(ContractError, match="literal path"):
        resolve_candidate_field(candidate, "metadata.*")


def test_beta2_contracts_map_without_changing_beta2_decision(fallback_documents) -> None:
    discovery, task_doc, policy_doc, facts_doc = fallback_documents
    candidates = parse_search_response(discovery)
    task = TaskContract.from_mapping(task_doc)
    facts = FactSet.from_mapping(facts_doc)
    old = evaluate(
        candidates=candidates, task=task, policy=Policy.from_mapping(policy_doc), facts=facts
    )
    mapped_task = task_v1_to_v2(task)
    mapped_facts = facts_v1_to_v2(facts)
    generic = evaluate_kernel(
        candidates=candidates,
        task=mapped_task,
        policy=KernelPolicy(
            provider_trust=tuple(
                ProviderTrust(provider_id, provider_version, frozenset(fact_types))
                for (provider_id, provider_version), fact_types in {
                    identity: {
                        item.fact_type
                        for item in mapped_facts.facts
                        if (item.provider_id, item.provider_version) == identity
                    }
                    for identity in {
                        (item.provider_id, item.provider_version) for item in mapped_facts.facts
                    }
                }.items()
            ),
            preestablished_fact_mode=True,
        ),
        fact_set=mapped_facts,
        evaluators=builtin_evaluators(),
    )
    assert generic.outcome == old.outcome
    assert generic.selected_candidate_id == old.selected_candidate_id


def test_unsupported_metadata_does_not_change_verdict() -> None:
    candidates, task, policy, facts = generic_inputs()
    baseline = evaluate_kernel(
        candidates=candidates,
        task=task,
        policy=policy,
        fact_set=facts,
        evaluators=default_evaluator_registry(("deployment.region",)),
    )
    first = candidates[0]
    mutated_original = dict(first.original)
    mutated_original["example:unrelated"] = {"eligible": True}
    changed = (
        first.__class__(
            first.resource_id,
            first.source,
            first.rank,
            first.score,
            first.media_type,
            first.metadata,
            mutated_original,
        ),
        candidates[1],
    )
    result = evaluate_kernel(
        candidates=changed,
        task=task,
        policy=policy,
        fact_set=facts,
        evaluators=default_evaluator_registry(("deployment.region",)),
    )
    assert [item.status for item in result.evaluations] == [
        item.status for item in baseline.evaluations
    ]


def test_advisory_requirement_does_not_block_selection() -> None:
    candidates, task, policy, facts = generic_inputs()
    advisory = Requirement(
        "advisory",
        "quota.remaining",
        {"predicate": "numeric_min", "expected": 1},
        mode=__import__("ardguard.kernel", fromlist=["RequirementMode"]).RequirementMode.ADVISORY,
    )
    expanded = GenericTaskContract(
        task.task_id, (*task.requirements, advisory), task.operation, task.context
    )
    decision = evaluate_kernel(
        candidates=candidates,
        task=expanded,
        policy=policy,
        fact_set=facts,
        evaluators=default_evaluator_registry(("deployment.region", "quota.remaining")),
    )
    assert decision.outcome.value == "SELECT"


def test_dependency_graph_is_bounded_and_cycle_safe() -> None:
    requirement = Requirement(
        "deps",
        "dependency.graph",
        {"root": "root", "max_depth": 3},
    )
    good = (
        Fact(
            "root",
            "candidate",
            "dependency.graph",
            "provider.dependencies",
            "1",
            FactOperationalState.AVAILABLE,
            {
                "identifier": "root",
                "available": True,
                "verified_usable": True,
                "dependencies": ["child"],
            },
        ),
        Fact(
            "child",
            "candidate",
            "dependency.graph",
            "provider.dependencies",
            "1",
            FactOperationalState.AVAILABLE,
            {"identifier": "child", "available": True, "verified_usable": True, "dependencies": []},
        ),
    )
    assert evaluate_dependency_graph(requirement, good, {}).status is RequirementStatus.SATISFIED
    cycle = (
        good[0],
        Fact(
            "child-cycle",
            "candidate",
            "dependency.graph",
            "provider.dependencies",
            "1",
            FactOperationalState.AVAILABLE,
            {
                "identifier": "child",
                "available": True,
                "verified_usable": True,
                "dependencies": ["root"],
            },
        ),
    )
    assert evaluate_dependency_graph(requirement, cycle, {}).status is RequirementStatus.ERROR
