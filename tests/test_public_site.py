from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "site" / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_public_explorer_has_twelve_beta4_scenarios() -> None:
    index = load("index.json")
    assert index["package_version"] == "0.1.0b4"
    assert index["default_scenario"] == "evidence-wrong-resource"
    assert len(index["scenarios"]) == 12


def test_hero_fixture_is_rank_preserving_fallback() -> None:
    fixture = load("evidence-wrong-resource.json")
    decision = fixture["decision"]
    assert decision["outcome"] == "SELECT"
    assert decision["selected_rank"] == 2
    assert decision["reason_code"] == "selection.fallback_to_lower_ranked_eligible"
    assert [item["status"] for item in decision["evaluations"]] == [
        "UNSATISFIED",
        "SATISFIED",
        "INDETERMINATE",
    ]
    assert decision["evaluations"][0]["requirements"][0]["reason_code"] == (
        "evidence.invalid_or_not_applicable"
    )
    assert fixture["invocation"] == "NOT_PERFORMED"


def test_every_selected_candidate_is_highest_ranked_satisfied_candidate() -> None:
    index = load("index.json")
    for item in index["scenarios"]:
        fixture = load(item["file"])
        decision = fixture["decision"]
        if decision["outcome"] != "SELECT":
            continue
        satisfied = [row for row in decision["evaluations"] if row["status"] == "SATISFIED"]
        assert satisfied
        assert (
            decision["selected_candidate_id"]
            == min(satisfied, key=lambda row: row["rank"])["candidate_id"]
        )


def test_fixture_hash_manifest() -> None:
    for line in (FIXTURES / "hashes.sha256").read_text().splitlines():
        digest, filename = line.split("  ", 1)
        assert hashlib.sha256((FIXTURES / filename).read_bytes()).hexdigest() == digest


def test_frontend_has_no_second_decision_engine() -> None:
    javascript = "\n".join(path.read_text() for path in (ROOT / "site" / "assets").glob("*.js"))
    prohibited = (
        "evaluate_requirement",
        "fallback_to_lower_ranked_eligible =",
        "provider_trust.authorizes",
        "eligible = facts",
    )
    assert all(item not in javascript for item in prohibited)
    assert "innerHTML" not in javascript
    assert "eval(" not in javascript
