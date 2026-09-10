from __future__ import annotations

import importlib.util
from pathlib import Path

from ardguard.constraints import default_evaluator_registry
from ardguard.kernel import (
    GenericTaskContract,
    KernelPolicy,
    ProviderTrust,
    Requirement,
    evaluate_kernel,
)
from ardguard.models import Candidate

ROOT = Path(__file__).resolve().parents[1]


def test_external_provider_adds_fact_type_without_core_change() -> None:
    path = ROOT / "examples" / "provider_plugin" / "example_region_provider" / "__init__.py"
    spec = importlib.util.spec_from_file_location("example_region_provider", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidate = Candidate(
        "urn:air:example.org:service:reader",
        "https://registry.example.org/",
        1,
        90,
        metadata={"example:region": "eu-west-1"},
    )
    task = GenericTaskContract(
        "task",
        (
            Requirement(
                "region",
                "deployment.region",
                {"predicate": "equals", "expected": "eu-west-1"},
            ),
        ),
    )
    decision = evaluate_kernel(
        candidates=(candidate,),
        task=task,
        policy=KernelPolicy(
            provider_trust=(
                ProviderTrust(
                    "example.region-provider", "1", frozenset({"deployment.region"})
                ),
            )
        ),
        providers=(module.RegionProvider({candidate.resource_id: "eu-west-1"}),),
        evaluators=default_evaluator_registry(("deployment.region",)),
    )
    assert decision.selected_candidate_id == candidate.resource_id
