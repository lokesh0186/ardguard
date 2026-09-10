from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ardguard import cli, decision


def run_cli(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - exact current interpreter and local module
        [sys.executable, "-m", "ardguard", *arguments],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def test_version() -> None:
    completed = run_cli("--version")
    assert completed.returncode == 0
    assert completed.stdout.strip() == "ardguard 0.1.0b4"


def test_demo_is_offline_and_does_not_invoke() -> None:
    completed = run_cli("demo")
    assert completed.returncode == 0
    assert "SELECT urn:air:example.org:tool:rank-two" in completed.stdout
    assert "invocation: NOT PERFORMED" in completed.stdout


def test_demo_json_validates_and_has_fallback() -> None:
    completed = run_cli("demo", "--json")
    assert completed.returncode == 0
    value = json.loads(completed.stdout)
    assert value["selected_rank"] == 2
    assert value["reason"] == "selection.fallback_to_lower_ranked_eligible"
    assert value["decision_sha256"] == (
        "05da070ad17d2dc3c98d38d8ca0d4c5f2a6838b8e6f696f5e8463dde1e98593f"
    )


def test_evaluate_and_explain(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "decision.json"
    completed = run_cli(
        "evaluate",
        "--discovery-response",
        str(root / "examples/fallback/discovery.json"),
        "--task",
        str(root / "examples/fallback/task.json"),
        "--policy",
        str(root / "examples/fallback/policy.json"),
        "--facts",
        str(root / "examples/fallback/facts.json"),
        "--output",
        str(output),
    )
    assert completed.returncode == 0
    explained = run_cli("explain", str(output))
    assert explained.returncode == 0
    assert "invocation: NOT PERFORMED" in explained.stdout


def test_output_refuses_overwrite(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "decision.json"
    output.write_text("existing", encoding="utf-8")
    completed = run_cli(
        "evaluate",
        "--discovery-response",
        str(root / "examples/fallback/discovery.json"),
        "--task",
        str(root / "examples/fallback/task.json"),
        "--policy",
        str(root / "examples/fallback/policy.json"),
        "--facts",
        str(root / "examples/fallback/facts.json"),
        "--output",
        str(output),
    )
    assert completed.returncode == 2
    assert output.read_text(encoding="utf-8") == "existing"


def test_input_symlink_is_rejected(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    link = tmp_path / "task.json"
    link.symlink_to(root / "examples/fallback/task.json")
    completed = run_cli("validate", "--kind", "task", str(link))
    assert completed.returncode == 2
    assert "must not be a symlink" in completed.stderr


def test_explain_rejects_tampered_hash(tmp_path: Path) -> None:
    completed = run_cli("demo", "--json")
    value = json.loads(completed.stdout)
    value["selected_rank"] = 1
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    explained = run_cli("explain", str(path))
    assert explained.returncode == 2
    assert "decision_sha256" in explained.stderr


def test_cli_source_has_no_resource_invocation_primitive() -> None:
    cli_source = Path(cli.__file__).read_text(encoding="utf-8")
    decision_source = Path(decision.__file__).read_text(encoding="utf-8")
    assert "requests." not in cli_source
    assert "urllib.request" not in cli_source
    assert "subprocess.run" not in decision_source
    assert "os.system" not in decision_source
    assert os.environ.get("ARDGUARD_AUTO_INVOKE") is None
