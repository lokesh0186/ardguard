from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from ardguard.adapters import parse_search_response
from ardguard.models import ObservationState, TaskContract, VerifierOutcome
from ardguard.providers.evidence import (
    EvidenceMaterial,
    OfflineEvidenceProvider,
    VerifierCommand,
    _classify,
    _safe_environment,
    _sandboxed_argv,
    evidence_subject_digests,
    pypi_command_factory,
    sigstore_command_factory,
)


def material(name: str = "sample-1.0-py3-none-any.whl") -> EvidenceMaterial:
    return EvidenceMaterial(
        candidate_id="urn:air:example.org:package:sample",
        verifier_artifact=b"artifact",
        artifact_name=name,
        evidence=b"{}",
        predicate_types=("https://docs.pypi.org/attestations/publish/v1",),
        signer_identity="https://github.com/example/project/.github/workflows/release.yml",
    )


def test_pypi_command_preserves_exact_filename(tmp_path: Path) -> None:
    artifact = tmp_path / material().artifact_name
    evidence = tmp_path / "evidence.json"
    command = pypi_command_factory(
        executable=Path("/usr/bin/true"), repository="https://github.com/example/project"
    )(material(), artifact, evidence)
    assert command.arguments[-1] == str(artifact)
    assert command.arguments[-2] == str(evidence)
    assert "--offline" in command.arguments


def test_pypi_command_rejects_non_distribution_basename(tmp_path: Path) -> None:
    bad = material("artifact.bin")
    factory = pypi_command_factory(
        executable=Path("/usr/bin/true"), repository="https://github.com/example/project"
    )
    with pytest.raises(ValueError, match="canonical distribution filename"):
        factory(bad, tmp_path / bad.artifact_name, tmp_path / "evidence.json")


def test_pypi_command_requires_exact_repository_identity() -> None:
    with pytest.raises(ValueError, match="exact GitHub HTTPS URL"):
        pypi_command_factory(executable=Path("/usr/bin/true"), repository="http://example.org")


def test_sigstore_command_is_explicitly_offline(tmp_path: Path) -> None:
    command = sigstore_command_factory(
        executable=Path("/usr/bin/true"),
        certificate_identity="https://github.com/example/project/.github/workflows/release.yml",
        oidc_issuer="https://token.actions.githubusercontent.com",
        trust_root_identity="sigstore-tuf:test-root",
    )(material("artifact.tar.gz"), tmp_path / "artifact.tar.gz", tmp_path / "bundle.json")
    assert "--offline" in command.arguments
    assert command.arguments[0:2] == ("verify", "identity")


@pytest.mark.parametrize(
    "identity,issuer,root",
    [
        ("", "https://issuer.example", "root"),
        ("id", "http://issuer.example", "root"),
        ("id", "https://issuer.example", ""),
    ],
)
def test_sigstore_command_requires_closed_identity_inputs(
    identity: str, issuer: str, root: str
) -> None:
    with pytest.raises(ValueError, match="HTTPS OIDC issuer"):
        sigstore_command_factory(
            executable=Path("/usr/bin/true"),
            certificate_identity=identity,
            oidc_issuer=issuer,
            trust_root_identity=root,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"candidate_id": ""},
        {"signer_identity": ""},
        {"artifact_name": "../artifact.whl"},
        {"artifact_name": ""},
        {"verifier_artifact": b""},
        {"evidence": b""},
    ],
)
def test_evidence_material_rejects_ambiguous_or_empty_inputs(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "candidate_id": "urn:example:candidate",
        "verifier_artifact": b"artifact",
        "artifact_name": "artifact.whl",
        "evidence": b"{}",
        "predicate_types": ("predicate",),
        "signer_identity": "signer",
    }
    values.update(kwargs)
    with pytest.raises(ValueError):
        EvidenceMaterial(**values)  # type: ignore[arg-type]


def test_valid_process_is_valid() -> None:
    completed = subprocess.CompletedProcess(["verifier"], 0, b"ok", b"")
    assert _classify(completed, ()) is VerifierOutcome.AVAILABLE_VALID


def test_reviewed_invalid_diagnostic_is_invalid() -> None:
    completed = subprocess.CompletedProcess(
        ["verifier"], 1, b"", b"Invalid provenance: Invalid JSON: broken"
    )
    outcome = _classify(completed, (b"Invalid provenance:", b"Invalid JSON:"))
    assert outcome is VerifierOutcome.AVAILABLE_INVALID


@pytest.mark.parametrize(
    "stderr,returncode",
    [
        (b"ModuleNotFoundError: dependency", 1),
        (b"Operation not permitted", 1),
        (b"sandbox-exec: sandbox_apply: Operation not permitted", 71),
        (b"terminated", -9),
    ],
)
def test_operational_failures_never_become_invalid(stderr: bytes, returncode: int) -> None:
    completed = subprocess.CompletedProcess(["verifier"], returncode, b"", stderr)
    outcome = _classify(completed, (b"Invalid provenance:", b"Invalid JSON:"))
    assert outcome is VerifierOutcome.OPERATIONAL_ERROR


def test_safe_environment_removes_proxy_and_python_injection(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid")
    monkeypatch.setenv("PYTHONPATH", "/untrusted")
    environment = _safe_environment(tmp_path)
    assert "HTTPS_PROXY" not in environment
    assert "PYTHONPATH" not in environment
    assert environment["NO_PROXY"] == "*"


def test_nonavailable_states_are_distinct() -> None:
    assert ObservationState.UNAVAILABLE is not ObservationState.OPERATIONAL_ERROR
    assert VerifierOutcome.UNAVAILABLE is not VerifierOutcome.AVAILABLE_INVALID


def test_extracts_in_toto_subject_digest() -> None:
    evidence = json.dumps(
        {
            "statement": base64.b64encode(
                json.dumps({"subject": [{"digest": {"sha256": "a" * 64}}]}).encode()
            ).decode()
        }
    ).encode()
    assert evidence_subject_digests(evidence) == ("a" * 64,)


def test_extracts_sigstore_message_digest() -> None:
    encoded = base64.b64encode(bytes.fromhex("b" * 64)).decode()
    evidence = json.dumps({"messageDigest": {"algorithm": "SHA2_256", "digest": encoded}}).encode()
    assert evidence_subject_digests(evidence) == ("b" * 64,)


def test_subject_extraction_recurses_and_rejects_bad_encoded_fields() -> None:
    valid = "A" * 64
    evidence = json.dumps(
        {
            "items": [{"subject": [{"digest": {"sha256": valid}}]}],
            "payload": "not-base64",
            "statement": base64.b64encode(b"not-json").decode(),
            "messageDigest": {"algorithm": "SHA2_256", "digest": "bad"},
        }
    ).encode()
    assert evidence_subject_digests(evidence) == (valid.casefold(),)


def test_subject_extraction_ignores_wrong_algorithm_and_shapes() -> None:
    evidence = json.dumps(
        {
            "subject": [None, {"digest": []}, {"digest": {"sha256": "bad"}}],
            "messageDigest": {"algorithm": "SHA-1", "digest": "anything"},
            "payload": 3,
        }
    ).encode()
    assert evidence_subject_digests(evidence) == ()


def test_malformed_evidence_has_no_subject() -> None:
    assert evidence_subject_digests(b"not-json") == ()


def test_macos_sandbox_profile_denies_network_and_scopes_writes(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "ardguard.providers.evidence.os.uname", lambda: SimpleNamespace(sysname="Darwin")
    )
    command = VerifierCommand("test", Path("/usr/bin/true"), ("arg",), (), "root")
    argv = _sandboxed_argv(command, tmp_path)
    assert argv[:2] == ("/usr/bin/sandbox-exec", "-p")
    assert "(deny network*)" in argv[2]
    assert f'(subpath "{tmp_path.resolve()}")' in argv[2]


def test_linux_sandbox_uses_network_namespace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "ardguard.providers.evidence.os.uname", lambda: SimpleNamespace(sysname="Linux")
    )
    monkeypatch.setattr("ardguard.providers.evidence.shutil.which", lambda name: "/usr/bin/unshare")
    command = VerifierCommand("test", Path("/usr/bin/true"), (), (), "root")
    assert _sandboxed_argv(command, tmp_path)[:3] == ("unshare", "--net", "--")


def test_sandbox_and_executable_fail_closed(tmp_path: Path, monkeypatch) -> None:
    command = VerifierCommand("test", tmp_path, (), (), "root")
    with pytest.raises(PermissionError, match="executable regular file"):
        _sandboxed_argv(command, tmp_path)
    command = VerifierCommand("test", Path("/usr/bin/true"), (), (), "root")
    monkeypatch.setattr(
        "ardguard.providers.evidence.os.uname", lambda: SimpleNamespace(sysname="Other")
    )
    with pytest.raises(RuntimeError, match="no supported"):
        _sandboxed_argv(command, tmp_path)


def _provider_material(candidate_id: str, subject: str) -> EvidenceMaterial:
    evidence = json.dumps({"subject": [{"digest": {"sha256": subject}}]}).encode()
    return EvidenceMaterial(
        candidate_id=candidate_id,
        verifier_artifact=b"authentic-artifact",
        artifact_name="sample-1.0-py3-none-any.whl",
        evidence=evidence,
        predicate_types=("https://docs.pypi.org/attestations/publish/v1",),
        signer_identity="https://github.com/example/project/.github/workflows/release.yml",
    )


def _test_factory(material, artifact, evidence) -> VerifierCommand:
    del material, artifact, evidence
    return VerifierCommand(
        "test-offline",
        Path("/usr/bin/true"),
        (),
        (b"Invalid provenance:", b"Invalid JSON:"),
        "test-root",
    )


def test_provider_preserves_valid_matching_observation(
    fallback_documents, monkeypatch, tmp_path: Path
) -> None:
    discovery, task_document, _, _ = fallback_documents
    candidate = parse_search_response(discovery)[1]
    monkeypatch.setattr(
        "ardguard.providers.evidence._sandboxed_argv", lambda command, scratch: ("true",)
    )
    monkeypatch.setattr(
        "ardguard.providers.evidence.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(["true"], 0, b"verified", b""),
    )
    provider = OfflineEvidenceProvider(
        {candidate.resource_id: _provider_material(candidate.resource_id, "b" * 64)},
        _test_factory,
        scratch_parent=tmp_path,
        trust_seed_files={"sigstore/test/root.json": b"root"},
    )
    observation = provider.observe((candidate,), TaskContract.from_mapping(task_document))[0]
    assert observation.state is ObservationState.AVAILABLE
    assert observation.payload["verifier_outcome"] == "AVAILABLE_VALID"
    assert observation.payload["artifact_sha256"] == "b" * 64
    assert observation.payload["subject_sha256"] == ("b" * 64,)
    assert observation.provenance["network_mode"] == "DENIED"
    assert observation.provenance["trust_root_identity"] == "test-root"
    assert observation.provenance["trust_seed_hashes"]["sigstore/test/root.json"]


def test_provider_keeps_authentic_wrong_subject_distinct(
    fallback_documents, monkeypatch, tmp_path: Path
) -> None:
    discovery, task_document, _, _ = fallback_documents
    candidate = parse_search_response(discovery)[1]
    monkeypatch.setattr(
        "ardguard.providers.evidence._sandboxed_argv", lambda command, scratch: ("true",)
    )
    monkeypatch.setattr(
        "ardguard.providers.evidence.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(["true"], 0, b"verified", b""),
    )
    provider = OfflineEvidenceProvider(
        {candidate.resource_id: _provider_material(candidate.resource_id, "a" * 64)},
        _test_factory,
        scratch_parent=tmp_path,
    )
    observation = provider.observe((candidate,), TaskContract.from_mapping(task_document))[0]
    assert observation.payload["verifier_outcome"] == "AVAILABLE_VALID"
    assert observation.payload["artifact_sha256"] == "b" * 64
    assert observation.payload["subject_sha256"] == ("a" * 64,)


def test_provider_operational_error_is_not_invalid(
    fallback_documents, monkeypatch, tmp_path: Path
) -> None:
    discovery, task_document, _, _ = fallback_documents
    candidate = parse_search_response(discovery)[1]
    monkeypatch.setattr(
        "ardguard.providers.evidence._sandboxed_argv", lambda command, scratch: ("false",)
    )
    monkeypatch.setattr(
        "ardguard.providers.evidence.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            ["false"], 1, b"", b"ModuleNotFoundError"
        ),
    )
    provider = OfflineEvidenceProvider(
        {candidate.resource_id: _provider_material(candidate.resource_id, "b" * 64)},
        _test_factory,
        scratch_parent=tmp_path,
    )
    observation = provider.observe((candidate,), TaskContract.from_mapping(task_document))[0]
    assert observation.state is ObservationState.OPERATIONAL_ERROR
    assert observation.payload == {}


def test_provider_preserves_reviewed_invalid_as_invalid(
    fallback_documents, monkeypatch, tmp_path: Path
) -> None:
    discovery, task_document, _, _ = fallback_documents
    candidate = parse_search_response(discovery)[1]
    monkeypatch.setattr(
        "ardguard.providers.evidence._sandboxed_argv", lambda command, scratch: ("false",)
    )
    monkeypatch.setattr(
        "ardguard.providers.evidence.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            ["false"], 1, b"", b"Invalid provenance: Invalid JSON: broken"
        ),
    )
    provider = OfflineEvidenceProvider(
        {candidate.resource_id: _provider_material(candidate.resource_id, "b" * 64)},
        _test_factory,
        scratch_parent=tmp_path,
    )
    observation = provider.observe((candidate,), TaskContract.from_mapping(task_document))[0]
    assert observation.state is ObservationState.AVAILABLE
    assert observation.payload["verifier_outcome"] == "AVAILABLE_INVALID"
    assert observation.payload["authentic"] is False


def test_provider_timeout_and_launch_failure_are_operational(
    fallback_documents, monkeypatch, tmp_path: Path
) -> None:
    discovery, task_document, _, _ = fallback_documents
    candidate = parse_search_response(discovery)[1]
    monkeypatch.setattr(
        "ardguard.providers.evidence._sandboxed_argv", lambda command, scratch: ("timeout",)
    )

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("verifier", 60)

    monkeypatch.setattr("ardguard.providers.evidence.subprocess.run", timeout)
    provider = OfflineEvidenceProvider(
        {candidate.resource_id: _provider_material(candidate.resource_id, "b" * 64)},
        _test_factory,
        scratch_parent=tmp_path,
    )
    observation = provider.observe((candidate,), TaskContract.from_mapping(task_document))[0]
    assert observation.state is ObservationState.OPERATIONAL_ERROR
    assert observation.provenance["adapter_id"] == "not-executed"


def test_provider_rejects_material_candidate_mismatch(fallback_inputs, tmp_path: Path) -> None:
    candidate = fallback_inputs[0][0]
    provider = OfflineEvidenceProvider(
        {candidate.resource_id: _provider_material("urn:example:other", "a" * 64)},
        _test_factory,
        scratch_parent=tmp_path,
    )
    with pytest.raises(ValueError, match="candidate identity mismatch"):
        provider.observe((candidate,), fallback_inputs[1])


def test_provider_returns_indeterminate_for_unbound_artifact(
    fallback_inputs, tmp_path: Path
) -> None:
    original = fallback_inputs[0][0]
    candidate = original.__class__(
        original.resource_id,
        original.source,
        original.rank,
        original.score,
        original.media_type,
        {},
        {},
    )
    provider = OfflineEvidenceProvider(
        {candidate.resource_id: _provider_material(candidate.resource_id, "a" * 64)},
        _test_factory,
        scratch_parent=tmp_path,
    )
    observation = provider.observe((candidate,), fallback_inputs[1])[0]
    assert observation.state is ObservationState.INDETERMINATE
    assert observation.provenance["adapter_id"] == "candidate-artifact-unbound"


def test_provider_ignores_candidates_without_material(fallback_inputs, tmp_path: Path) -> None:
    provider = OfflineEvidenceProvider({}, _test_factory, scratch_parent=tmp_path)
    assert provider.observe(fallback_inputs[0], fallback_inputs[1]) == ()


def test_provider_rejects_trust_seed_escape() -> None:
    with pytest.raises(ValueError, match="stay relative"):
        OfflineEvidenceProvider({}, _test_factory, trust_seed_files={"../root.json": b"root"})


def test_provider_requires_trust_seed_bytes() -> None:
    with pytest.raises(TypeError, match="must be bytes"):
        OfflineEvidenceProvider({}, _test_factory, trust_seed_files={"root.json": "root"})  # type: ignore[dict-item]
