"""Correctly typed offline evidence-verifier integration.

This module preserves canonical artifact names and never treats verifier unavailability
or operational failure as cryptographic invalidity. It performs no network fallback.
The actual eligibility decision, including subject and predicate binding, remains in
the policy composer.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from ardguard.models import (
    Candidate,
    FactType,
    Observation,
    ObservationState,
    ProviderIdentity,
    TaskContract,
    VerifierOutcome,
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA256_BYTES = 32


@dataclass(frozen=True)
class EvidenceMaterial:
    candidate_id: str
    verifier_artifact: bytes
    artifact_name: str
    evidence: bytes
    predicate_types: tuple[str, ...]
    signer_identity: str

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.signer_identity:
            raise ValueError("candidate and signer identities are required")
        if Path(self.artifact_name).name != self.artifact_name or not self.artifact_name:
            raise ValueError("artifact_name must be one canonical basename")
        if not self.verifier_artifact or not self.evidence:
            raise ValueError("artifact and evidence bytes are required")


@dataclass(frozen=True)
class VerifierCommand:
    adapter_id: str
    executable: Path
    arguments: tuple[str, ...]
    invalid_stderr_markers: tuple[bytes, ...]
    trust_root_identity: str


CommandFactory = Callable[[EvidenceMaterial, Path, Path], VerifierCommand]


def pypi_command_factory(*, executable: Path, repository: str) -> CommandFactory:
    if not repository.startswith("https://github.com/"):
        raise ValueError("PyPI repository identity must be an exact GitHub HTTPS URL")

    def build(material: EvidenceMaterial, artifact: Path, evidence: Path) -> VerifierCommand:
        if not material.artifact_name.endswith((".whl", ".tar.gz", ".zip")):
            raise ValueError("PyPI verification requires the canonical distribution filename")
        return VerifierCommand(
            "pypi-attestations-offline-v1",
            executable,
            (
                "verify",
                "pypi",
                "--offline",
                "--repository",
                repository,
                "--provenance-file",
                str(evidence),
                str(artifact),
            ),
            (b"Invalid provenance:", b"Invalid JSON:"),
            "pypi-attestations:embedded-offline-roots",
        )

    return build


def sigstore_command_factory(
    *,
    executable: Path,
    certificate_identity: str,
    oidc_issuer: str,
    trust_root_identity: str,
) -> CommandFactory:
    if (
        not certificate_identity
        or not oidc_issuer.startswith("https://")
        or not trust_root_identity
    ):
        raise ValueError("Sigstore certificate identity and HTTPS OIDC issuer are required")

    def build(material: EvidenceMaterial, artifact: Path, evidence: Path) -> VerifierCommand:
        return VerifierCommand(
            "sigstore-bundle-offline-v1",
            executable,
            (
                "verify",
                "identity",
                "--offline",
                "--bundle",
                str(evidence),
                "--cert-identity",
                certificate_identity,
                "--cert-oidc-issuer",
                oidc_issuer,
                str(artifact),
            ),
            (b"The provided bundle is malformed", b"Invalid JSON:"),
            trust_root_identity,
        )

    return build


def _classify(
    completed: subprocess.CompletedProcess[bytes], markers: tuple[bytes, ...]
) -> VerifierOutcome:
    if completed.returncode == 0:
        return VerifierOutcome.AVAILABLE_VALID
    stderr = completed.stderr or b""
    if (
        completed.returncode < 0
        or b"Operation not permitted" in stderr
        or stderr.startswith(b"sandbox-exec:")
    ):
        return VerifierOutcome.OPERATIONAL_ERROR
    if markers and all(marker in stderr for marker in markers):
        return VerifierOutcome.AVAILABLE_INVALID
    return VerifierOutcome.OPERATIONAL_ERROR


def _safe_environment(scratch: Path) -> dict[str, str]:
    allowed = {"PATH", "LANG", "LC_ALL", "SYSTEMROOT", "WINDIR"}
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment.update(
        {
            "HOME": str(scratch / "home"),
            "XDG_CACHE_HOME": str(scratch / "cache"),
            "XDG_CONFIG_HOME": str(scratch / "config"),
            "XDG_DATA_HOME": str(scratch / "data"),
            "XDG_STATE_HOME": str(scratch / "state"),
            "TMPDIR": str(scratch / "tmp"),
            "NO_PROXY": "*",
            "no_proxy": "*",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return environment


def evidence_subject_digests(evidence: bytes) -> tuple[str, ...]:
    """Extract SHA-256 subjects from in-toto and Sigstore bundle structures."""

    found: set[str] = set()

    def walk(value: object) -> None:  # noqa: PLR0912 - handles two nested evidence formats
        if isinstance(value, dict):
            subject = value.get("subject")
            if isinstance(subject, list):
                for row in subject:
                    if isinstance(row, dict) and isinstance(row.get("digest"), dict):
                        digest = row["digest"].get("sha256")
                        if isinstance(digest, str) and SHA256_RE.fullmatch(digest.casefold()):
                            found.add(digest.casefold())
            message = value.get("messageDigest")
            if isinstance(message, dict) and message.get("algorithm") == "SHA2_256":
                encoded = message.get("digest")
                if isinstance(encoded, str):
                    try:
                        decoded = base64.b64decode(encoded, validate=True)
                    except ValueError:
                        decoded = b""
                    if len(decoded) == SHA256_BYTES:
                        found.add(decoded.hex())
            for encoded_field in ("payload", "statement"):
                encoded = value.get(encoded_field)
                if isinstance(encoded, str):
                    try:
                        decoded = base64.b64decode(encoded, validate=True)
                        nested = json.loads(decoded)
                    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    walk(nested)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    try:
        walk(json.loads(evidence))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ()
    return tuple(sorted(found))


def _sandboxed_argv(command: VerifierCommand, scratch: Path) -> tuple[str, ...]:
    executable = command.executable.resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise PermissionError("verifier executable is not an executable regular file")
    if os.uname().sysname == "Darwin":
        sandbox = Path("/usr/bin/sandbox-exec")
        if not sandbox.exists():
            raise RuntimeError("macOS sandbox-exec is unavailable")
        profile = _macos_profile(scratch)
        return (str(sandbox), "-p", profile, str(executable), *command.arguments)
    if os.uname().sysname == "Linux" and shutil.which("unshare"):
        return ("unshare", "--net", "--", str(executable), *command.arguments)
    raise RuntimeError("no supported network-denying verifier sandbox is available")


def _macos_profile(scratch: Path) -> str:
    """Build the closed macOS profile independently of host availability."""

    escaped = str(scratch.resolve()).replace("\\", "\\\\").replace('"', '\\"')
    return "\n".join(
        (
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            "(deny file-write*)",
            f'(allow file-write* (subpath "{escaped}"))',
        )
    )


class OfflineEvidenceProvider:
    """Run an explicitly configured verifier in a network-denied scratch."""

    provider_id = "ardguard.offline-evidence"
    version = "1"

    def __init__(
        self,
        materials: Mapping[str, EvidenceMaterial],
        command_factory: CommandFactory,
        *,
        scratch_parent: Path | None = None,
        trust_seed_files: Mapping[str, bytes] | None = None,
    ) -> None:
        self._materials = dict(materials)
        self._command_factory = command_factory
        self._scratch_parent = scratch_parent
        self._trust_seed_files = dict(trust_seed_files or {})
        for relative, content in self._trust_seed_files.items():
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("trust seed paths must stay relative to XDG_CACHE_HOME")
            if not isinstance(content, bytes):
                raise TypeError("trust seed content must be bytes")

    def observe(
        self, candidates: tuple[Candidate, ...], task: TaskContract
    ) -> tuple[Observation, ...]:
        return tuple(
            self._observe(candidate, task)
            for candidate in candidates
            if candidate.resource_id in self._materials
        )

    def _observe(self, candidate: Candidate, task: TaskContract) -> Observation:
        material = self._materials[candidate.resource_id]
        if material.candidate_id != candidate.resource_id:
            raise ValueError("evidence material candidate identity mismatch")
        verifier_artifact_sha256 = hashlib.sha256(material.verifier_artifact).hexdigest()
        candidate_artifact_sha256 = candidate.artifact_sha256(task.evidence.artifact_digest_field)
        if candidate_artifact_sha256 is None:
            return self._nonavailable(
                candidate, ObservationState.INDETERMINATE, "candidate-artifact-unbound"
            )
        evidence_sha256 = hashlib.sha256(material.evidence).hexdigest()
        scratch_path: Path | None = None
        try:
            scratch_path = Path(
                tempfile.mkdtemp(prefix="ardguard-verifier-", dir=self._scratch_parent)
            ).resolve()
            for name in ("home", "cache", "config", "data", "state", "tmp", "input"):
                (scratch_path / name).mkdir(mode=0o700)
            trust_seed_hashes: dict[str, str] = {}
            for relative, content in sorted(self._trust_seed_files.items()):
                target = scratch_path / "cache" / relative
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                target.write_bytes(content)
                target.chmod(0o400)
                trust_seed_hashes[relative] = hashlib.sha256(content).hexdigest()
            artifact_path = scratch_path / "input" / material.artifact_name
            evidence_path = scratch_path / "input" / "evidence.json"
            artifact_path.write_bytes(material.verifier_artifact)
            evidence_path.write_bytes(material.evidence)
            command = self._command_factory(material, artifact_path, evidence_path)
            argv = _sandboxed_argv(command, scratch_path)
            # The executable is an operator-configured, resolved regular file and the
            # command is wrapped in a network-denying OS sandbox above.
            completed = subprocess.run(  # noqa: S603
                argv,
                check=False,
                capture_output=True,
                env=_safe_environment(scratch_path),
                timeout=60,
            )
            outcome = _classify(completed, command.invalid_stderr_markers)
            if outcome is VerifierOutcome.OPERATIONAL_ERROR:
                return self._nonavailable(
                    candidate, ObservationState.OPERATIONAL_ERROR, command.adapter_id
                )
            authentic = outcome is VerifierOutcome.AVAILABLE_VALID
            payload = {
                "verifier_outcome": outcome.value,
                "authentic": authentic,
                "trust_valid": authentic,
                "signer_identity": material.signer_identity,
                "subject_sha256": list(evidence_subject_digests(material.evidence)),
                "artifact_sha256": candidate_artifact_sha256,
                "evidence_sha256": evidence_sha256,
                "predicate_types": list(material.predicate_types),
                "resource_id": candidate.resource_id,
            }
            provenance = {
                "adapter_id": command.adapter_id,
                "trust_root_identity": command.trust_root_identity,
                "trust_seed_hashes": trust_seed_hashes,
                "artifact_name": material.artifact_name,
                "candidate_artifact_sha256": candidate_artifact_sha256,
                "verifier_artifact_sha256": verifier_artifact_sha256,
                "evidence_sha256": evidence_sha256,
                "executable_sha256": hashlib.sha256(
                    command.executable.resolve(strict=True).read_bytes()
                ).hexdigest(),
                "exit_code": completed.returncode,
                "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
                "network_mode": "DENIED",
            }
            return Observation(
                candidate.resource_id,
                FactType.EVIDENCE,
                ProviderIdentity(self.provider_id, self.version),
                ObservationState.AVAILABLE,
                payload,
                provenance,
            )
        except (OSError, RuntimeError, subprocess.SubprocessError):
            return self._nonavailable(candidate, ObservationState.OPERATIONAL_ERROR, "not-executed")
        finally:
            if scratch_path is not None and scratch_path.exists():
                shutil.rmtree(scratch_path)

    def _nonavailable(
        self, candidate: Candidate, state: ObservationState, adapter_id: str
    ) -> Observation:
        return Observation(
            candidate.resource_id,
            FactType.EVIDENCE,
            ProviderIdentity(self.provider_id, self.version),
            state,
            {},
            {"adapter_id": adapter_id, "network_mode": "DENIED"},
        )
