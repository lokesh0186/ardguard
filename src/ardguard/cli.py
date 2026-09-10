"""ARDGuard command-line interface."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ardguard import __version__
from ardguard.adapters.ard import compatibility_record as ard_compatibility
from ardguard.adapters.ard import parse_search_response
from ardguard.adapters.hf_discover import compatibility_record as hf_compatibility
from ardguard.adapters.hf_discover import parse_hf_discover_response
from ardguard.decision import evaluate
from ardguard.kernel import GenericFactSet, GenericTaskContract, KernelPolicy, evaluate_kernel
from ardguard.models import (
    ContractError,
    Decision,
    FactSet,
    FinalDecision,
    Policy,
    TaskContract,
    canonical_json,
)
from ardguard.packs import POLICY_PACKS, builtin_evaluators
from ardguard.plugins import discover_fact_provider_metadata
from ardguard.reasons import REASON_DEFINITIONS, ReasonCode
from ardguard.schema import validate_document
from ardguard.service import serve

MAX_INPUT_BYTES = 10 * 1024 * 1024


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(name: str) -> object:
    if name == "-":
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    else:
        if name is None:
            raise ContractError("input path is required")
        path = Path(name)
        if path.is_symlink():
            raise ContractError(f"input must not be a symlink: {path}")
        if not path.is_file():
            raise ContractError(f"input must be a regular file: {path}")
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise ContractError(f"input exceeds {MAX_INPUT_BYTES} bytes: {path}")
        raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ContractError(f"input exceeds {MAX_INPUT_BYTES} bytes")
    try:
        return json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid UTF-8 JSON: {exc}") from exc


def _write_json(value: object, name: str | None, *, force: bool = False) -> None:
    rendered = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if name in {None, "-"}:
        sys.stdout.write(rendered)
        return
    if name is None:
        raise ContractError("output path is required")
    target = Path(name)
    if target.is_symlink():
        raise ContractError(f"output must not be a symlink: {target}")
    if target.exists() and not force:
        raise ContractError(f"output exists; pass --force to replace it: {target}")
    if not target.parent.is_dir():
        raise ContractError(f"output parent does not exist: {target.parent}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _demo_documents() -> tuple[object, object, object, object]:
    first_digest = "a" * 64
    second_digest = "b" * 64
    discovery = {
        "results": [
            {
                "identifier": "urn:air:example.org:tool:rank-one",
                "displayName": "Rank One",
                "type": "application/mcp-server-card+json",
                "url": "https://example.org/rank-one.json",
                "score": 98,
                "source": "https://finder.example.org/",
                "metadata": {"artifact_sha256": first_digest},
            },
            {
                "identifier": "urn:air:example.org:tool:rank-two",
                "displayName": "Rank Two",
                "type": "application/mcp-server-card+json",
                "url": "https://example.org/rank-two.json",
                "score": 93,
                "source": "https://finder.example.org/",
                "metadata": {"artifact_sha256": second_digest},
            },
        ]
    }
    task = {
        "schema_version": "ardguard.dev/task-contract/v1",
        "task_id": "offline-demo-read",
        "operation": "records.read",
        "required_capabilities": ["records.read"],
        "evidence": {
            "required": True,
            "artifact_digest_field": "artifact_sha256",
            "accepted_predicate_types": ["https://example.org/predicate/publish/v1"],
            "trusted_signers": ["https://example.org/identity/publisher"],
        },
        "authority": {
            "required": True,
            "required_permissions": ["records.read"],
            "maximum_permissions": ["records.read"],
        },
    }
    policy = {
        "schema_version": "ardguard.dev/policy/v1",
        "selection_mode": "fallback",
        "required_checks": ["capability", "evidence", "authority"],
        "indeterminate_action": "DEFER",
        "operational_error_action": "ERROR",
    }
    observations = []
    for identifier, digest, capabilities in (
        ("urn:air:example.org:tool:rank-one", first_digest, ["records.write"]),
        ("urn:air:example.org:tool:rank-two", second_digest, ["records.read"]),
    ):
        provider = {"id": "demo.local", "version": "1"}
        observations.extend(
            [
                {
                    "candidate_id": identifier,
                    "fact_type": "capability",
                    "provider": provider,
                    "state": "AVAILABLE",
                    "payload": {"verified_capabilities": capabilities},
                    "provenance": {"fixture": "illustrative"},
                },
                {
                    "candidate_id": identifier,
                    "fact_type": "evidence",
                    "provider": provider,
                    "state": "AVAILABLE",
                    "payload": {
                        "verifier_outcome": "AVAILABLE_VALID",
                        "authentic": True,
                        "trust_valid": True,
                        "signer_identity": "https://example.org/identity/publisher",
                        "subject_sha256": [digest],
                        "artifact_sha256": digest,
                        "evidence_sha256": "c" * 64,
                        "predicate_types": ["https://example.org/predicate/publish/v1"],
                        "resource_id": identifier,
                    },
                    "provenance": {"fixture": "illustrative"},
                },
                {
                    "candidate_id": identifier,
                    "fact_type": "authority",
                    "provider": provider,
                    "state": "AVAILABLE",
                    "payload": {"granted_permissions": ["records.read"]},
                    "provenance": {"fixture": "illustrative"},
                },
            ]
        )
    facts = {"schema_version": "ardguard.dev/fact-set/v1", "observations": observations}
    return discovery, task, policy, facts


def _evaluate_documents(
    discovery: object, task_value: object, policy_value: object, facts_value: object, adapter: str
) -> Decision:
    validate_document("task", task_value)
    validate_document("policy", policy_value)
    validate_document("facts", facts_value)
    candidates = (
        parse_hf_discover_response(discovery)
        if adapter == "hf-discover"
        else parse_search_response(discovery)
    )
    return evaluate(
        candidates=candidates,
        task=TaskContract.from_mapping(task_value),
        policy=Policy.from_mapping(policy_value),
        facts=FactSet.from_mapping(facts_value),
    )


def _evaluate_v2_bundle(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("stdin evaluation bundle must be an object")
    if set(value) != {"discovery", "task", "policy", "facts"}:
        raise ContractError("stdin bundle requires discovery, task, policy, and facts")
    task = GenericTaskContract.from_mapping(value["task"])
    policy = KernelPolicy.from_mapping(value["policy"])
    facts = GenericFactSet.from_mapping(value["facts"])
    candidates = parse_search_response(value["discovery"])
    evaluators = builtin_evaluators(tuple(item.requirement_type for item in task.requirements))
    return evaluate_kernel(
        candidates=candidates,
        task=task,
        policy=policy,
        fact_set=facts,
        evaluators=evaluators,
    ).to_dict()


def _cmd_demo(args: argparse.Namespace) -> int:
    discovery, task, policy, facts = _demo_documents()
    decision = _evaluate_documents(discovery, task, policy, facts, "ard")
    if args.json:
        _write_json(decision.to_dict(), None)
    else:
        sys.stdout.write(
            "ARDGuard offline demo (illustrative)\n"
            "rank 1: relevant but capability-ineligible\n"
            "rank 2: eligible\n"
            "top-ranked-only validation: ABSTAIN\n"
            f"ARDGuard: {decision.outcome.value} {decision.selected_candidate_id}\n"
            f"reason: {decision.reason.value}\n"
            "invocation: NOT PERFORMED\n"
        )
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    payload = {
        "ardguard_version": __version__,
        "python": sys.version.split()[0],
        "schemas": sorted(
            (
                "task",
                "facts",
                "policy",
                "decision",
                "task-v2",
                "facts-v2",
                "policy-v2",
                "decision-v2",
            )
        ),
        "adapters": [ard_compatibility(), hf_compatibility()],
        "automatic_invocation": False,
        "implicit_network": False,
        "plugin_entry_point": "ardguard.fact_providers",
        "installed_provider_plugins": discover_fact_provider_metadata(),
        "policy_packs": sorted(POLICY_PACKS),
        "installed_plugins": discover_fact_provider_metadata(),
        "optional_evidence_sandbox": "/usr/bin/sandbox-exec"
        if sys.platform == "darwin"
        else "unshare --net",
    }
    if args.json:
        _write_json(payload, None)
    else:
        sys.stdout.write(
            f"ARDGuard {__version__}\nPython {payload['python']}\n"
            "ARD v0.91: SUPPORTED (pinned fixture)\n"
            "hf-discover 1.3.7: SUPPORTED (pinned fixture)\n"
            "automatic invocation: DISABLED\nimplicit network: DISABLED\n"
        )
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    value = _read_json(args.file)
    if args.kind in {
        "task",
        "facts",
        "policy",
        "decision",
        "task-v2",
        "facts-v2",
        "policy-v2",
        "decision-v2",
    }:
        validate_document(args.kind, value)
    elif args.kind == "ard":
        parse_search_response(value)
    else:
        parse_hf_discover_response(value)
    sys.stdout.write(f"VALID {args.kind}\n")
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    if args.stdin:
        value = _read_json("-")
        result = _evaluate_v2_bundle(value)
        _write_json(result, args.output, force=args.force)
        return {
            "SELECT": 0,
            "ABSTAIN": 1,
            "DEFER": 3,
            "ERROR": 4,
        }[result["outcome"]]
    if not all((args.discovery_response, args.task, args.policy, args.facts)):
        raise ContractError(
            "file mode requires --discovery-response, --task, --policy, and --facts"
        )
    decision = _evaluate_documents(
        _read_json(args.discovery_response),
        _read_json(args.task),
        _read_json(args.policy),
        _read_json(args.facts),
        args.adapter,
    )
    _write_json(decision.to_dict(), args.output, force=args.force)
    return {
        FinalDecision.SELECT: 0,
        FinalDecision.ABSTAIN: 1,
        FinalDecision.DEFER: 3,
        FinalDecision.ERROR: 4,
    }[decision.outcome]


def _cmd_explain(args: argparse.Namespace) -> int:
    value = _read_json(args.decision)
    if not isinstance(value, dict):
        raise ContractError("decision must be an object")
    schema = value.get("schema_version")
    validate_document("decision-v2" if schema == "ardguard.dev/decision/v2" else "decision", value)
    supplied_hash = value["decision_sha256"]
    body = {key: item for key, item in value.items() if key != "decision_sha256"}
    actual_hash = hashlib.sha256(canonical_json(body)).hexdigest()
    if supplied_hash != actual_hash:
        raise ContractError("decision_sha256 does not match the decision body")
    selected = value["selected_candidate_id"] or "none"
    reason = value.get("reason_code", value.get("reason"))
    if not isinstance(reason, str):
        raise ContractError("decision reason code is missing")
    try:
        meaning = REASON_DEFINITIONS[ReasonCode(reason)].meaning
    except ValueError:
        meaning = "A versioned requirement or selection rule produced this reason."
    sys.stdout.write(
        f"decision: {value['outcome']}\nselected: {selected}\nreason: {reason}\n"
        f"meaning: {meaning}\ninvocation: NOT PERFORMED\n"
    )
    return 0


def _cmd_support(args: argparse.Namespace) -> int:
    payload = {
        "python": {"status": "SUPPORTED", "versions": ["3.10", "3.11", "3.12", "3.13"]},
        "ard": ard_compatibility(),
        "hf_discover": hf_compatibility(),
        "static_facts": {"status": "SUPPORTED"},
        "offline_evidence_command_provider": {
            "status": "EXPERIMENTAL",
            "platforms": ["macOS", "Linux"],
        },
        "kubernetes_provider": {"status": "ADVISORY", "included": False},
        "automatic_invocation": {"status": "UNSUPPORTED"},
        "generic_requirements": {"status": "EXPERIMENTAL", "schema": "v2"},
        "provider_plugins": {"status": "EXPERIMENTAL", "entry_point": "ardguard.fact_providers"},
        "mcp_introspection": {"status": "EXPERIMENTAL", "operations": ["initialize", "tools/list"]},
        "a2a_openapi_skill": {"status": "EXPERIMENTAL", "mode": "offline artifact parsing"},
        "http_sidecar": {"status": "EXPERIMENTAL", "bind": "127.0.0.1"},
    }
    if args.json:
        _write_json(payload, None)
    else:
        sys.stdout.write(
            "SUPPORTED: Python 3.10-3.13, ARD v0.91, hf-discover 1.3.7, static observations\n"
            "EXPERIMENTAL: sandboxed offline PyPI/Sigstore command providers\n"
            "ADVISORY: external capability and authority providers\n"
            "UNSUPPORTED: automatic installation or invocation\n"
        )
    return 0


def _cmd_adapters(args: argparse.Namespace) -> int:
    _write_json({"adapters": [ard_compatibility(), hf_compatibility()]}, None)
    return 0


def _cmd_providers(args: argparse.Namespace) -> int:
    payload = {
        "entry_point_group": "ardguard.fact_providers",
        "automatic_loading": False,
        "built_in": [
            {
                "provider_id": "ardguard.offline-evidence",
                "status": "EXPERIMENTAL",
                "network": "DENIED",
            },
            {
                "provider_id": "ardguard.mcp-introspection",
                "status": "EXPERIMENTAL",
                "network": "EXPLICIT",
            },
        ],
        "policy_packs": sorted(POLICY_PACKS),
    }
    _write_json(payload, None)
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    serve(host=args.host, port=args.port)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ardguard", description="Eligibility-aware final resource selection"
    )
    parser.add_argument("--version", action="version", version=f"ardguard {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="run a deterministic offline fallback demo")
    demo.add_argument("--json", action="store_true")
    demo.set_defaults(handler=_cmd_demo)

    doctor = subparsers.add_parser("doctor", help="report local product readiness")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(handler=_cmd_doctor)

    validate = subparsers.add_parser("validate", help="validate an input document")
    validate.add_argument(
        "--kind",
        choices=(
            "task",
            "facts",
            "policy",
            "decision",
            "task-v2",
            "facts-v2",
            "policy-v2",
            "decision-v2",
            "ard",
            "hf-discover",
        ),
        required=True,
    )
    validate.add_argument("file")
    validate.set_defaults(handler=_cmd_validate)

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="derive a deterministic final decision"
    )
    evaluate_parser.add_argument("--discovery-response")
    evaluate_parser.add_argument("--task")
    evaluate_parser.add_argument("--policy")
    evaluate_parser.add_argument("--facts")
    evaluate_parser.add_argument(
        "--stdin", action="store_true", help="read one v2 evaluation bundle from stdin"
    )
    evaluate_parser.add_argument("--json", action="store_true", help="emit deterministic JSON")
    evaluate_parser.add_argument("--adapter", choices=("ard", "hf-discover"), default="ard")
    evaluate_parser.add_argument("--output", default="-")
    evaluate_parser.add_argument("--force", action="store_true")
    evaluate_parser.set_defaults(handler=_cmd_evaluate)

    explain = subparsers.add_parser("explain", help="validate and explain a decision")
    explain.add_argument("decision")
    explain.set_defaults(handler=_cmd_explain)

    support = subparsers.add_parser("support", help="print the tested support matrix")
    support.add_argument("--json", action="store_true")
    support.set_defaults(handler=_cmd_support)

    adapters = subparsers.add_parser("adapters", help="print adapter compatibility records")
    adapters.set_defaults(handler=_cmd_adapters)

    providers = subparsers.add_parser("providers", help="inspect provider extension support")
    providers_sub = providers.add_subparsers(dest="providers_command", required=True)
    providers_list = providers_sub.add_parser(
        "list", help="list built-in and plugin provider boundaries"
    )
    providers_list.set_defaults(handler=_cmd_providers)

    serve_parser = subparsers.add_parser("serve", help="run the loopback-only JSON service")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.set_defaults(handler=_cmd_serve)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
        return int(args.handler(args))
    except ContractError as exc:
        sys.stderr.write(f"ardguard: {exc}\n")
        return 2
    except KeyboardInterrupt:
        sys.stderr.write("ardguard: interrupted\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
