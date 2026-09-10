"""Packaged JSON Schema access and validation."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from ardguard.models import ContractError

SCHEMAS = {
    "task": "task-contract-v1.schema.json",
    "facts": "fact-set-v1.schema.json",
    "policy": "policy-v1.schema.json",
    "decision": "decision-v1.schema.json",
    "task-v2": "task-contract-v2.schema.json",
    "facts-v2": "fact-set-v2.schema.json",
    "policy-v2": "policy-v2.schema.json",
    "decision-v2": "decision-v2.schema.json",
}


def load_schema(kind: str) -> dict[str, Any]:
    try:
        name = SCHEMAS[kind]
    except KeyError as exc:
        raise ContractError(f"unknown schema kind: {kind}") from exc
    resource = resources.files("ardguard").joinpath("schemas").joinpath(name)
    if not resource.is_file():
        # Editable installs use the repository schema directory. Wheels receive the
        # same directory through Hatch's explicit force-include rule.
        resource = Path(__file__).resolve().parents[2] / "schemas" / name
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"packaged schema {name} is not an object")
    return value


def validate_document(kind: str, document: object) -> None:
    validator = Draft202012Validator(load_schema(kind))
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        error = errors[0]
        path = ".".join(str(item) for item in error.absolute_path) or "$"
        raise ContractError(f"{kind} schema violation at {path}: {error.message}")
