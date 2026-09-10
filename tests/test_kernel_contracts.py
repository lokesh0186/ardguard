from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ardguard.adapters.ard import parse_search_response
from ardguard.constraints import default_evaluator_registry
from ardguard.kernel import (
    EvaluatorRegistry,
    Fact,
    FactOperationalState,
    GenericFactSet,
    GenericTaskContract,
    KernelPolicy,
    ProviderContext,
    ProviderRegistry,
    ProviderTrust,
    Requirement,
    RequirementMode,
    RequirementStatus,
    RequirementVerdict,
    UnknownPolicy,
    evaluate_kernel,
    requirement_fact_types,
)
from ardguard.models import ContractError, FinalDecision, SelectionMode

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / "examples" / "generic" / name).read_text())


def trusted_pre(fact_type: str = "deployment.region") -> KernelPolicy:
    return KernelPolicy(
        provider_trust=(ProviderTrust("provider.x", "1", frozenset({fact_type})),),
        preestablished_fact_mode=True,
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"requirement_id": ""}, "identifier"),
        ({"requirement_type": "BAD TYPE"}, "identifier"),
        ({"mode": "bad"}, "enum"),
        ({"unknown_policy": "bad"}, "enum"),
        ({"namespace": ""}, "non-empty"),
        ({"unsupported": True}, "unsupported"),
    ],
)
def test_requirement_parser_boundaries(change, message) -> None:
    row = copy.deepcopy(load("task.json")["requirements"][0])
    row.update(change)
    with pytest.raises(ContractError, match=message):
        Requirement.from_mapping(row)


def test_task_parser_boundaries() -> None:
    row = load("task.json")
    for change, message in (
        ({"schema_version": "wrong"}, "schema_version"),
        ({"requirements": {}}, "array"),
        ({"extra": True}, "unsupported"),
    ):
        changed = copy.deepcopy(row)
        changed.update(change)
        with pytest.raises(ContractError, match=message):
            GenericTaskContract.from_mapping(changed)
    requirement = Requirement("same", "x.fact", {"predicate": "equals", "expected": 1})
    with pytest.raises(ContractError, match="duplicate"):
        GenericTaskContract("task", (requirement, requirement))
    with pytest.raises(ContractError, match="at least one"):
        GenericTaskContract("task", ())


def test_fact_set_and_fact_parser_boundaries() -> None:
    row = load("facts.json")["facts"][0]
    for change, message in (
        ({"state": "bad"}, "state"),
        ({"provider_version": ""}, "non-empty"),
        ({"extra": True}, "unsupported"),
    ):
        changed = copy.deepcopy(row)
        changed.update(change)
        with pytest.raises(ContractError, match=message):
            Fact.from_mapping(changed)
    with pytest.raises(ContractError, match="only"):
        GenericFactSet.from_mapping({"schema_version": "x", "values": []})
    with pytest.raises(ContractError, match="schema_version"):
        GenericFactSet.from_mapping({"schema_version": "x", "facts": []})
    with pytest.raises(ContractError, match="array"):
        GenericFactSet.from_mapping({"schema_version": "ardguard.dev/fact-set/v2", "facts": {}})
    item = Fact.from_mapping(row)
    with pytest.raises(ContractError, match="duplicate"):
        GenericFactSet((item, item))


def test_policy_parser_boundaries() -> None:
    row = load("policy.json")
    for change, message in (
        ({"schema_version": "wrong"}, "schema_version"),
        ({"selection_mode": "bad"}, "enum"),
        ({"extra": True}, "unsupported"),
        ({"indeterminate_action": "SELECT"}, "DEFER or ABSTAIN"),
        ({"operational_error_action": "SELECT"}, "ERROR, DEFER, or ABSTAIN"),
    ):
        changed = copy.deepcopy(row)
        changed.update(change)
        with pytest.raises(ContractError, match=message):
            KernelPolicy.from_mapping(changed)
    with pytest.raises(ContractError, match="DEFER or ABSTAIN"):
        KernelPolicy(indeterminate_action=FinalDecision.SELECT)
    with pytest.raises(ContractError, match="ERROR, DEFER, or ABSTAIN"):
        KernelPolicy(operational_error_action=FinalDecision.SELECT)


def test_provider_context_rejects_secret_or_decision_assertions() -> None:
    with pytest.raises(ContractError, match="secret"):
        ProviderContext(values={"access_token": "do-not-store"})
    with pytest.raises(ContractError, match="eligibility"):
        ProviderContext(values={"eligible": True})
    with pytest.raises(ContractError, match="positive"):
        ProviderContext(deadline_seconds=0)


def test_registry_and_fact_type_boundaries() -> None:
    registry = EvaluatorRegistry()

    def evaluator(requirement, facts, context):
        del requirement, facts, context

    registry.register("x.fact", evaluator)
    with pytest.raises(ContractError, match="duplicate"):
        registry.register("x.fact", evaluator)
    missing = Requirement("r", "missing.fact", {})
    assert registry.evaluate(missing, (), {}).status is RequirementStatus.INDETERMINATE
    with pytest.raises(ContractError, match="non-empty array"):
        requirement_fact_types(Requirement("r", "x.fact", {"fact_types": []}))
    with pytest.raises(ContractError, match="duplicates"):
        requirement_fact_types(Requirement("r", "x.fact", {"fact_types": ["x.fact", "x.fact"]}))

    class Bad:
        provider_id = "bad.provider"
        provider_version = "1"
        supported_fact_types = frozenset()

    with pytest.raises(ContractError, match="frozenset"):
        ProviderRegistry((Bad(),))

    class BadVersion:
        provider_id = "bad.version"
        provider_version = ""
        supported_fact_types = frozenset({"x.fact"})

    with pytest.raises(ContractError, match="provider_version"):
        ProviderRegistry((BadVersion(),))


def test_evaluator_cannot_return_verdict_for_another_requirement() -> None:
    registry = EvaluatorRegistry()

    def evaluator(requirement, facts, context):
        del requirement, facts, context
        return RequirementVerdict(
            "other-requirement", RequirementStatus.SATISFIED, "requirement.satisfied"
        )

    registry.register("x.fact", evaluator)
    with pytest.raises(ContractError, match="another requirement"):
        registry.evaluate(Requirement("expected", "x.fact", {}), (), {})


def test_verdict_contract_rejects_invalid_plugin_output() -> None:
    with pytest.raises(ContractError, match="RequirementStatus"):
        RequirementVerdict("requirement", "SATISFIED", "requirement.satisfied")  # type: ignore[arg-type]


def test_boolean_assertion_requires_fact_provenance() -> None:
    candidates = parse_search_response(load("discovery.json"))
    requirement = Requirement(
        "assertion",
        "control.asserted",
        {"predicate": "boolean_asserted_with_provenance", "expected": True},
    )
    facts = GenericFactSet(
        tuple(
            Fact(
                f"assertion-{index}",
                candidate.resource_id,
                "control.asserted",
                "provider.x",
                "1",
                FactOperationalState.AVAILABLE,
                True,
            )
            for index, candidate in enumerate(candidates)
        )
    )
    decision = evaluate_kernel(
        candidates=candidates,
        task=GenericTaskContract("assertion-task", (requirement,)),
        policy=trusted_pre("control.asserted"),
        fact_set=facts,
        evaluators=default_evaluator_registry(("control.asserted",)),
    )
    assert decision.outcome is FinalDecision.ERROR


def test_kernel_empty_duplicate_unknown_and_outcome_paths() -> None:
    candidates = parse_search_response(load("discovery.json"))
    task = GenericTaskContract.from_mapping(load("task.json"))
    evaluators = default_evaluator_registry(("deployment.region",))
    with pytest.raises(ContractError, match="at least one"):
        evaluate_kernel(candidates=(), task=task, policy=KernelPolicy(), evaluators=evaluators)
    with pytest.raises(ContractError, match="unique"):
        evaluate_kernel(
            candidates=(candidates[0], candidates[0]),
            task=task,
            policy=trusted_pre(),
            evaluators=evaluators,
        )
    unknown = Fact(
        "unknown",
        "not-a-candidate",
        "deployment.region",
        "provider.x",
        "1",
        FactOperationalState.AVAILABLE,
        "us-east-1",
    )
    with pytest.raises(ContractError, match="unknown candidates"):
        evaluate_kernel(
            candidates=candidates,
            task=task,
            policy=trusted_pre(),
            fact_set=GenericFactSet((unknown,)),
            evaluators=evaluators,
        )

    unavailable = tuple(
        Fact(
            f"missing-{i}",
            item.resource_id,
            "deployment.region",
            "provider.x",
            "1",
            FactOperationalState.UNAVAILABLE,
        )
        for i, item in enumerate(candidates)
    )
    defer = evaluate_kernel(
        candidates=candidates,
        task=task,
        policy=trusted_pre(),
        fact_set=GenericFactSet(unavailable),
        evaluators=evaluators,
    )
    assert defer.outcome is FinalDecision.DEFER

    rejected = tuple(
        Fact(
            f"bad-{i}",
            item.resource_id,
            "deployment.region",
            "provider.x",
            "1",
            FactOperationalState.AVAILABLE,
            "other",
        )
        for i, item in enumerate(candidates)
    )
    abstain = evaluate_kernel(
        candidates=candidates,
        task=task,
        policy=trusted_pre(),
        fact_set=GenericFactSet(rejected),
        evaluators=evaluators,
    )
    assert abstain.outcome is FinalDecision.ABSTAIN


def test_unknown_policy_and_top_rank_only() -> None:
    candidates = parse_search_response(load("discovery.json"))
    base = GenericTaskContract.from_mapping(load("task.json"))
    requirement = Requirement(
        "unknown",
        "missing.fact",
        {},
        RequirementMode.MANDATORY,
        UnknownPolicy.UNSATISFIED,
    )
    task = GenericTaskContract(base.task_id, (requirement,))
    decision = evaluate_kernel(
        candidates=candidates,
        task=task,
        policy=KernelPolicy(SelectionMode.TOP_RANKED_ONLY),
        evaluators=EvaluatorRegistry(),
    )
    assert decision.outcome is FinalDecision.ABSTAIN
