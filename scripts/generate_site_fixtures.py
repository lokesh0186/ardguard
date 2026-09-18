#!/usr/bin/env python3
"""Generate static Decision Explorer fixtures with public ARDGuard Beta 4.

The browser only renders these files. It never reimplements eligibility,
fallback, requirement evaluation, reason codes, or receipt hashing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from ardguard import __version__
from ardguard.adapters import parse_search_response
from ardguard.kernel import GenericFactSet, GenericTaskContract, KernelPolicy, evaluate_kernel
from ardguard.packs import builtin_evaluators

EXPECTED_VERSION = "0.1.0b4"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "site" / "fixtures"
INDEX_PATH = FIXTURE_DIR / "index.json"
HASH_PATH = FIXTURE_DIR / "hashes.sha256"

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64


def candidate(identifier: str, label: str, score: int, digest: str) -> dict[str, Any]:
    return {
        "identifier": identifier,
        "displayName": label,
        "type": "application/vnd.mcp.server+json",
        "url": f"https://catalog.example/{identifier.rsplit(':', 1)[-1]}.json",
        "score": score,
        "source": "https://catalog.example/",
        "metadata": {"artifact_sha256": digest},
    }


CANDIDATES = (
    candidate("urn:air:example.org:service:server-a", "Server A", 98, DIGEST_A),
    candidate("urn:air:example.org:service:server-b", "Server B", 91, DIGEST_B),
    candidate("urn:air:example.org:service:server-c", "Server C", 84, DIGEST_C),
)


def requirement(
    requirement_id: str,
    requirement_type: str,
    parameters: dict[str, Any],
    *,
    unknown_policy: str = "INDETERMINATE",
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "requirement_type": requirement_type,
        "parameters": parameters,
        "mode": "MANDATORY",
        "unknown_policy": unknown_policy,
        "namespace": f"https://ardguard.dev/facts/{requirement_type}/v1",
        "schema_identity": "ardguard.dev/requirement/v1",
    }


def fact(  # noqa: PLR0913 - mirrors the public Fact identity fields
    fact_id: str,
    candidate_id: str,
    fact_type: str,
    value: Any,
    *,
    state: str = "AVAILABLE",
    provider_id: str = "demo.verified-provider",
    evidence_identity: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "fact_id": fact_id,
        "candidate_id": candidate_id,
        "fact_type": fact_type,
        "provider_id": provider_id,
        "provider_version": "1",
        "state": state,
        "value": value,
        "provenance": provenance or {},
        "source_identity": "fixture:public-decision-explorer" if state == "AVAILABLE" else None,
        "evidence_identity": evidence_identity if state == "AVAILABLE" else None,
        "observed_at": None,
        "expires_at": None,
        "extensions": {},
    }


def capability_fact(index: int, capabilities: list[str]) -> dict[str, Any]:
    row = CANDIDATES[index]
    return fact(
        f"capability-{index + 1}",
        row["identifier"],
        "capability",
        {"verified_capabilities": capabilities},
    )


def evidence_fact(index: int, artifact_digest: str, *, state: str = "AVAILABLE") -> dict[str, Any]:
    row = CANDIDATES[index]
    if state != "AVAILABLE":
        return fact(
            f"evidence-{index + 1}",
            row["identifier"],
            "evidence",
            None,
            state=state,
            provenance={"provider_status": state.lower(), "retryable": True},
        )
    return fact(
        f"evidence-{index + 1}",
        row["identifier"],
        "evidence",
        {
            "authentic": True,
            "trust_valid": True,
            "resource_id": row["identifier"],
            "artifact_sha256": artifact_digest,
            "subject_sha256": [artifact_digest],
            "predicate_types": ["https://slsa.dev/provenance/v1"],
            "signer_identity": "https://publisher.example/workflow/release.yml",
        },
        evidence_identity=f"attestation:{artifact_digest[:12]}",
    )


def authority_fact(index: int, permissions: list[str]) -> dict[str, Any]:
    row = CANDIDATES[index]
    return fact(
        f"authority-{index + 1}",
        row["identifier"],
        "authority",
        {"granted_permissions": permissions},
    )


def boolean_fact(
    index: int,
    fact_type: str,
    value: bool | None,
    *,
    state: str = "AVAILABLE",
    fact_id_suffix: str = "",
) -> dict[str, Any]:
    row = CANDIDATES[index]
    return fact(
        f"{fact_type.replace('.', '-')}-{index + 1}{fact_id_suffix}",
        row["identifier"],
        fact_type,
        value,
        state=state,
        provenance=(
            {"provider_status": state.lower(), "retryable": True}
            if state != "AVAILABLE"
            else {"diagnostic_sha256": hashlib.sha256(f"{fact_type}:{index}".encode()).hexdigest()}
        ),
    )


def base_task(requirements: list[dict[str, Any]], task_id: str) -> dict[str, Any]:
    return {
        "schema_version": "ardguard.dev/task-contract/v2",
        "task_id": task_id,
        "operation": "records.read",
        "requirements": requirements,
        "context": {},
    }


def policy(fact_types: set[str], *, indeterminate: str = "DEFER") -> dict[str, Any]:
    return {
        "schema_version": "ardguard.dev/policy/v2",
        "selection_mode": "fallback",
        "indeterminate_action": indeterminate,
        "operational_error_action": "ERROR",
        "preestablished_fact_mode": True,
        "provider_trust": [
            {
                "provider_id": "demo.verified-provider",
                "provider_version": "1",
                "fact_types": sorted(fact_types),
            }
        ],
    }


def scenario_definitions() -> list[dict[str, Any]]:
    capability = requirement(
        "required-capability", "capability", {"required_capabilities": ["records.read"]}
    )
    access = requirement(
        "credential-available",
        "access.credential_available",
        {"predicate": "equals", "expected": True},
    )
    authority = requirement(
        "least-authority",
        "authority",
        {
            "required_permissions": ["records.read"],
            "maximum_permissions": ["records.read"],
        },
    )
    evidence = requirement(
        "artifact-evidence",
        "evidence",
        {
            "artifact_digest_field": "artifact_sha256",
            "accepted_predicate_types": ["https://slsa.dev/provenance/v1"],
            "trusted_signers": ["https://publisher.example/workflow/release.yml"],
        },
    )
    freshness = requirement(
        "evidence-freshness",
        "evidence.freshness",
        {"predicate": "fresh_within_seconds", "expected": 86400},
    )

    return [
        {
            "id": "top-ranked-eligible",
            "title": "Top-ranked candidate is eligible",
            "summary": "Discovery rank and eligibility agree, so Server A is selected.",
            "lesson": (
                "ARDGuard preserves the discovery system's first choice when it satisfies the task."
            ),
            "requirements": [capability],
            "facts": [capability_fact(0, ["records.read"]), capability_fact(1, [])],
            "candidates": CANDIDATES[:2],
            "display": [
                ["Verified", "Not required", "Not required"],
                ["Mismatch", "Not required", "Not required"],
            ],
        },
        {
            "id": "ranked-fallback",
            "title": "Top-ranked ineligible → fallback",
            "summary": (
                "Server A lacks the required capability; Server B is selected without reranking."
            ),
            "lesson": "Eligibility changes what may be selected, not the relevance order.",
            "requirements": [capability],
            "facts": [capability_fact(0, []), capability_fact(1, ["records.read"])],
            "candidates": CANDIDATES[:2],
            "display": [
                ["Capability mismatch", "Not required", "Not required"],
                ["Verified", "Not required", "Not required"],
            ],
        },
        {
            "id": "evidence-wrong-resource",
            "title": "Authentic evidence, wrong artifact",
            "summary": (
                "Evidence for Server A is authentic but names artifact B. "
                "Server B satisfies every requirement."
            ),
            "lesson": "Evidence authenticity and evidence applicability are separate questions.",
            "requirements": [evidence, access, authority],
            "facts": [
                evidence_fact(0, DIGEST_B),
                boolean_fact(0, "access.credential_available", True),
                authority_fact(0, ["records.read"]),
                evidence_fact(1, DIGEST_B),
                boolean_fact(1, "access.credential_available", True),
                authority_fact(1, ["records.read"]),
                evidence_fact(2, DIGEST_C, state="UNAVAILABLE"),
                boolean_fact(2, "access.credential_available", True),
                authority_fact(2, ["records.read"]),
            ],
            "candidates": CANDIDATES,
            "display": [
                ["Subject mismatch", "Available", "Within policy"],
                ["Applicable", "Available", "Within policy"],
                ["Provider unavailable", "Available", "Within policy"],
            ],
        },
        {
            "id": "access-unavailable",
            "title": "Discovery-visible, access unavailable",
            "summary": "Server A is visible but the caller lacks the required credential category.",
            "lesson": "Discovery visibility does not establish execution feasibility.",
            "requirements": [access],
            "facts": [
                boolean_fact(0, "access.credential_available", False),
                boolean_fact(1, "access.credential_available", True),
            ],
            "candidates": CANDIDATES[:2],
            "display": [
                ["Not required", "Unavailable", "Not required"],
                ["Not required", "Available", "Not required"],
            ],
        },
        {
            "id": "excessive-authority",
            "title": "Authority exceeds task policy",
            "summary": (
                "Server A asks for administrative authority; Server B needs only records.read."
            ),
            "lesson": (
                "A relevant candidate can still be ineligible because its authority exceeds policy."
            ),
            "requirements": [authority],
            "facts": [
                authority_fact(0, ["records.read", "admin"]),
                authority_fact(1, ["records.read"]),
            ],
            "candidates": CANDIDATES[:2],
            "display": [
                ["Not required", "Not required", "Exceeds policy"],
                ["Not required", "Not required", "Within policy"],
            ],
        },
        {
            "id": "provider-unavailable",
            "title": "Provider unavailable",
            "summary": (
                "Server A's access provider is unavailable; Server B has a verified access fact."
            ),
            "lesson": (
                "Unavailable is not false. ARDGuard preserves uncertainty and can "
                "still select an independent candidate."
            ),
            "requirements": [access],
            "facts": [
                boolean_fact(0, "access.credential_available", None, state="UNAVAILABLE"),
                boolean_fact(1, "access.credential_available", True),
            ],
            "candidates": CANDIDATES[:2],
            "display": [
                ["Not required", "Provider unavailable", "Not required"],
                ["Not required", "Available", "Not required"],
            ],
        },
        {
            "id": "provider-operational-error",
            "title": "Provider operational error",
            "summary": (
                "Server A's provider fails operationally; Server B remains independently evaluable."
            ),
            "lesson": (
                "An operational error is not a negative security fact and does not "
                "become a fabricated value."
            ),
            "requirements": [access],
            "facts": [
                fact(
                    "access-provider-error-1",
                    CANDIDATES[0]["identifier"],
                    "access.credential_available",
                    None,
                    state="OPERATIONAL_ERROR",
                    provenance={"error_type": "TimeoutError", "retryable": True},
                ),
                boolean_fact(1, "access.credential_available", True),
            ],
            "candidates": CANDIDATES[:2],
            "display": [
                ["Not required", "Operational error", "Not required"],
                ["Not required", "Available", "Not required"],
            ],
        },
        {
            "id": "conflicting-trusted-facts",
            "title": "Conflicting trusted facts",
            "summary": (
                "Two authorized facts disagree about Server A. ARDGuard does not "
                "majority-vote them."
            ),
            "lesson": (
                "Conflicting authoritative observations remain indeterminate until "
                "policy supplies precedence."
            ),
            "requirements": [access],
            "facts": [
                boolean_fact(0, "access.credential_available", True, fact_id_suffix="-a"),
                boolean_fact(0, "access.credential_available", False, fact_id_suffix="-b"),
                boolean_fact(1, "access.credential_available", False),
            ],
            "candidates": CANDIDATES[:2],
            "display": [
                ["Not required", "Conflicting facts", "Not required"],
                ["Not required", "Unavailable", "Not required"],
            ],
        },
        {
            "id": "stale-evidence",
            "title": "Stale evidence",
            "summary": (
                "Every candidate's evidence observation is outside the required freshness window."
            ),
            "lesson": (
                "A previously true observation is not automatically current enough for this task."
            ),
            "requirements": [freshness],
            "facts": [
                fact(
                    "freshness-1",
                    CANDIDATES[0]["identifier"],
                    "evidence.freshness",
                    "2000-01-01T00:00:00Z",
                ),
                fact(
                    "freshness-2",
                    CANDIDATES[1]["identifier"],
                    "evidence.freshness",
                    "2000-01-01T00:00:00Z",
                ),
            ],
            "candidates": CANDIDATES[:2],
            "display": [
                ["Stale", "Not required", "Not required"],
                ["Stale", "Not required", "Not required"],
            ],
        },
        {
            "id": "all-ineligible",
            "title": "All candidates ineligible",
            "summary": "No discovered candidate has the required capability.",
            "lesson": "ARDGuard abstains instead of selecting an ineligible resource.",
            "requirements": [capability],
            "facts": [capability_fact(0, []), capability_fact(1, [])],
            "candidates": CANDIDATES[:2],
            "display": [
                ["Capability mismatch", "Not required", "Not required"],
                ["Capability mismatch", "Not required", "Not required"],
            ],
        },
        {
            "id": "missing-mandatory-fact",
            "title": "Missing mandatory fact",
            "summary": "The required access fact was not supplied for either candidate.",
            "lesson": "Missing facts do not silently become a pass.",
            "requirements": [access],
            "facts": [],
            "candidates": CANDIDATES[:2],
            "display": [
                ["Not required", "Unknown", "Not required"],
                ["Not required", "Unknown", "Not required"],
            ],
        },
        {
            "id": "multiple-eligible-preserve-rank",
            "title": "Multiple eligible candidates",
            "summary": (
                "Servers A and B both satisfy the task; Server A remains selected "
                "because it was ranked first."
            ),
            "lesson": (
                "ARDGuard does not recompute relevance or prefer a lower-ranked eligible candidate."
            ),
            "requirements": [capability],
            "facts": [
                capability_fact(0, ["records.read"]),
                capability_fact(1, ["records.read"]),
                capability_fact(2, []),
            ],
            "candidates": CANDIDATES,
            "display": [
                ["Verified", "Not required", "Not required"],
                ["Verified", "Not required", "Not required"],
                ["Capability mismatch", "Not required", "Not required"],
            ],
        },
    ]


def render_scenario(definition: dict[str, Any]) -> dict[str, Any]:
    discovery = {"results": list(definition["candidates"])}
    task = base_task(definition["requirements"], f"explorer-{definition['id']}")
    fact_types = {
        fact_type
        for req in definition["requirements"]
        for fact_type in req["parameters"].get("fact_types", [req["requirement_type"]])
    }
    policy_document = policy(fact_types)
    facts = {
        "schema_version": "ardguard.dev/fact-set/v2",
        "facts": definition["facts"],
    }
    candidates = parse_search_response(discovery)
    decision = evaluate_kernel(
        candidates=candidates,
        task=GenericTaskContract.from_mapping(task),
        policy=KernelPolicy.from_mapping(policy_document),
        fact_set=GenericFactSet.from_mapping(facts),
        evaluators=builtin_evaluators(tuple(sorted(fact_types))),
    ).to_dict()
    evaluation_by_id = {row["candidate_id"]: row for row in decision["evaluations"]}
    display_candidates = []
    for index, row in enumerate(definition["candidates"]):
        evaluation = evaluation_by_id[row["identifier"]]
        display_candidates.append(
            {
                "candidate_id": row["identifier"],
                "label": row["displayName"],
                "rank": index + 1,
                "score": row["score"],
                "evidence": definition["display"][index][0],
                "access": definition["display"][index][1],
                "authority": definition["display"][index][2],
                "eligibility": evaluation["status"],
                "selected": row["identifier"] == decision["selected_candidate_id"],
            }
        )
    return {
        "fixture_schema": "ardguard.dev/decision-explorer-fixture/v1",
        "id": definition["id"],
        "title": definition["title"],
        "summary": definition["summary"],
        "lesson": definition["lesson"],
        "package": {"name": "ardguard", "version": __version__},
        "input": {
            "discovery": discovery,
            "task": task,
            "policy": policy_document,
            "facts": facts,
        },
        "decision": decision,
        "display": {"candidates": display_candidates},
        "invocation": "NOT_PERFORMED",
    }


def encoded(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def generated_files() -> dict[Path, bytes]:
    if __version__ != EXPECTED_VERSION:
        raise RuntimeError(
            f"fixture generation requires ardguard=={EXPECTED_VERSION}; found {__version__}"
        )
    rendered = [render_scenario(item) for item in scenario_definitions()]
    files = {FIXTURE_DIR / f"{item['id']}.json": encoded(item) for item in rendered}
    index = {
        "fixture_schema": "ardguard.dev/decision-explorer-index/v1",
        "package_version": __version__,
        "default_scenario": "evidence-wrong-resource",
        "scenarios": [
            {
                "id": item["id"],
                "title": item["title"],
                "summary": item["summary"],
                "file": f"{item['id']}.json",
                "outcome": item["decision"]["outcome"],
            }
            for item in rendered
        ],
    }
    files[INDEX_PATH] = encoded(index)
    lines = [
        f"{hashlib.sha256(content).hexdigest()}  {path.name}"
        for path, content in sorted(files.items(), key=lambda pair: pair[0].name)
    ]
    files[HASH_PATH] = ("\n".join(lines) + "\n").encode()
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if committed fixtures differ")
    args = parser.parse_args()
    files = generated_files()
    if args.check:
        mismatches = [
            path
            for path, content in files.items()
            if not path.exists() or path.read_bytes() != content
        ]
        if mismatches:
            for path in mismatches:
                print(f"fixture mismatch: {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        print(f"verified {len(files) - 2} Beta-4 scenarios and fixture hashes")
        return 0
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in files.items():
        path.write_bytes(content)
    print(f"generated {len(files) - 2} Beta-4 scenarios in {FIXTURE_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
