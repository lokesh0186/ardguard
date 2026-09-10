from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ardguard.adapters import parse_search_response
from ardguard.models import FactSet, Policy, TaskContract

ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


@pytest.fixture
def fallback_documents() -> tuple[object, object, object, object]:
    return (
        load("examples/fallback/discovery.json"),
        load("examples/fallback/task.json"),
        load("examples/fallback/policy.json"),
        load("examples/fallback/facts.json"),
    )


@pytest.fixture
def fallback_inputs(fallback_documents: tuple[object, object, object, object]):
    discovery, task, policy, facts = fallback_documents
    return (
        parse_search_response(discovery),
        TaskContract.from_mapping(task),
        Policy.from_mapping(policy),
        FactSet.from_mapping(facts),
    )
