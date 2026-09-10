from __future__ import annotations

import json
from pathlib import Path

import pytest

from ardguard.models import ContractError
from ardguard.schema import SCHEMAS, load_schema, validate_document


def test_all_packaged_schemas_are_valid() -> None:
    for kind in SCHEMAS:
        schema = load_schema(kind)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_examples_validate(fallback_documents) -> None:
    _, task, policy, facts = fallback_documents
    validate_document("task", task)
    validate_document("policy", policy)
    validate_document("facts", facts)


def test_generic_examples_validate() -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "generic"
    for kind, filename in (
        ("task-v2", "task.json"),
        ("policy-v2", "policy.json"),
        ("facts-v2", "facts.json"),
    ):
        validate_document(kind, json.loads((root / filename).read_text(encoding="utf-8")))


def test_schema_rejects_final_eligibility(fallback_documents) -> None:
    _, _, _, facts = fallback_documents
    facts["observations"][0]["eligible"] = True
    with pytest.raises(ContractError):
        validate_document("facts", facts)


def test_top_level_schema_files_are_canonical_json() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in SCHEMAS.values():
        value = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
        assert isinstance(value, dict)
