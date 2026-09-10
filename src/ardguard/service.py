"""Loopback-only standard-library HTTP integration service."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from ardguard import __version__
from ardguard.adapters.ard import parse_search_response
from ardguard.kernel import GenericFactSet, GenericTaskContract, KernelPolicy, evaluate_kernel
from ardguard.models import ContractError, canonical_json
from ardguard.packs import builtin_evaluators
from ardguard.schema import validate_document

MAX_REQUEST_BYTES = 10 * 1024 * 1024
MAX_PORT = 65535


def _decision_from_bundle(payload: object) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ContractError("evaluation request must be an object")
    if set(payload) != {"discovery", "task", "policy", "facts"}:
        raise ContractError("evaluation request requires discovery, task, policy, and facts")
    task = GenericTaskContract.from_mapping(payload["task"])
    facts = GenericFactSet.from_mapping(payload["facts"])
    policy = KernelPolicy.from_mapping(payload["policy"])
    candidates = parse_search_response(payload["discovery"])
    registry = builtin_evaluators(tuple(item.requirement_type for item in task.requirements))
    return evaluate_kernel(
        candidates=candidates,
        task=task,
        policy=policy,
        fact_set=facts,
        evaluators=registry,
    ).to_dict()


def route(  # noqa: PLR0911 - a small closed route table
    method: str, path: str, payload: object | None = None
) -> tuple[int, dict[str, Any]]:
    """Pure routing function used by HTTP and unit tests."""

    if method == "GET" and path == "/v1/health":
        return 200, {"status": "ok", "network_providers_enabled": False}
    if method == "GET" and path == "/v1/version":
        return 200, {"version": __version__, "api": "v1"}
    if method == "GET" and path == "/v1/providers":
        return 200, {"providers": [], "plugins_enabled": False}
    if method == "POST" and path == "/v1/evaluate":
        return 200, _decision_from_bundle(payload)
    if method == "POST" and path == "/v1/validate":
        if not isinstance(payload, Mapping) or set(payload) != {"kind", "document"}:
            raise ContractError("validation request requires kind and document")
        kind = payload["kind"]
        if not isinstance(kind, str):
            raise ContractError("validation kind must be a string")
        validate_document(kind, payload["document"])
        return 200, {"valid": True, "kind": kind}
    if method == "POST" and path == "/v1/explain":
        if not isinstance(payload, Mapping):
            raise ContractError("decision must be an object")
        supplied = payload.get("decision_sha256")
        if not isinstance(supplied, str):
            raise ContractError("decision_sha256 is required")
        body = {key: value for key, value in payload.items() if key != "decision_sha256"}
        if hashlib.sha256(canonical_json(body)).hexdigest() != supplied:
            raise ContractError("decision_sha256 does not match the decision body")
        return 200, {
            "outcome": payload.get("outcome"),
            "selected_candidate_id": payload.get("selected_candidate_id"),
            "reason_code": payload.get("reason_code", payload.get("reason")),
            "invocation": "NOT_PERFORMED",
        }
    return 404, {"error": "not_found"}


class _Handler(BaseHTTPRequestHandler):
    server_version = "ARDGuard"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(10)

    def _host_is_local(self) -> bool:
        value = self.headers.get("Host")
        if not value:
            return False
        parsed = urlsplit(f"//{value}")
        return parsed.hostname in {"127.0.0.1", "::1", "localhost"}

    def _send(self, status: int, body: Mapping[str, Any]) -> None:
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _dispatch(self, payload: object | None = None) -> None:
        if not self._host_is_local():
            self._send(421, {"error": "misdirected_request"})
            return
        try:
            status, body = route(self.command, self.path, payload)
        except ContractError as exc:
            status, body = 400, {"error": "invalid_request", "message": str(exc)}
        self._send(status, body)

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        length = self.headers.get("Content-Length")
        if length is None or not length.isdigit() or int(length) > MAX_REQUEST_BYTES:
            self._send(413, {"error": "request_size"})
            return
        raw = self.rfile.read(int(length))
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, {"error": "invalid_json"})
            return
        self._dispatch(payload)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def create_server(
    *, host: str = "127.0.0.1", port: int = 8765
) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ContractError("ardguard serve binds to loopback only")
    if not 0 <= port <= MAX_PORT:
        raise ContractError("port must be from 0 through 65535")
    return ThreadingHTTPServer((host, port), _Handler)


def serve(*, host: str = "127.0.0.1", port: int = 8765) -> None:
    create_server(host=host, port=port).serve_forever()
