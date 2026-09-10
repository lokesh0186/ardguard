from __future__ import annotations

import errno
import json
import os
import subprocess
import sys
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

from ardguard.models import ContractError
from ardguard.service import create_server, route, serve

ROOT = Path(__file__).resolve().parents[1]


def bundle():
    return json.loads((ROOT / "examples/generic/evaluate-bundle.json").read_text())


def test_pure_service_routes() -> None:
    assert route("GET", "/v1/health")[1]["status"] == "ok"
    assert route("GET", "/v1/version")[1]["api"] == "v1"
    status, decision = route("POST", "/v1/evaluate", bundle())
    assert status == 200
    assert decision["selected_candidate_id"].endswith(":east")
    explain_status, explanation = route("POST", "/v1/explain", decision)
    assert explain_status == 200
    assert explanation["invocation"] == "NOT_PERFORMED"


def test_stdin_json_integration() -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    completed = subprocess.run(
        [sys.executable, "-m", "ardguard", "evaluate", "--stdin", "--json"],
        input=json.dumps(bundle()),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["selected_candidate_id"].endswith(":east")


def test_serve_rejects_non_loopback() -> None:
    with pytest.raises(ContractError, match="loopback"):
        serve(host="0.0.0.0", port=0)  # noqa: S104 - verifies rejection


def test_real_loopback_http_health_and_evaluate() -> None:
    try:
        server = create_server(port=0)
    except PermissionError as exc:
        if exc.errno != errno.EPERM:
            raise
        pytest.skip("execution sandbox prohibits loopback socket binding")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        connection.request("GET", "/v1/health")
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["status"] == "ok"
        connection.request("GET", "/v1/health", headers={"Host": "attacker.example"})
        response = connection.getresponse()
        assert response.status == 421
        assert "Access-Control-Allow-Origin" not in response.headers
        response.read()
        body = json.dumps(bundle())
        connection.request(
            "POST",
            "/v1/evaluate",
            body=body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        )
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["selected_candidate_id"].endswith(":east")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
