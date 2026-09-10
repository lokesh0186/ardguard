#!/usr/bin/env python3
"""Validate wheel and sdist contents against the public product boundary."""

from __future__ import annotations

import argparse
import re
import tarfile
import zipfile
from pathlib import Path

BANNED_PATH_PARTS = {
    ".DS_Store",
    "__MACOSX",
    "__pycache__",
    ".git",
    ".github",
    "tests",
    "runs",
    "results",
    "paper",
    "manuscript",
}
BANNED_TEXT = (
    b"USENIX",
    b"HotCRP",
    b"4open.science",
    b"U3R17",
    b"U3R18",
    b"U3R22",
    b"/Users/",
    b"\\Users\\",
)
WHEEL_PREFIXES = (
    "ardguard/",
    "ardguard-0.1.0b2.dist-info/",
)
SDIST_ALLOWED_ROOTS = {
    ".gitignore",
    "src",
    "schemas",
    "examples",
    "docs",
    "README.md",
    "LICENSE",
    "NOTICE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "SUPPORT.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "CITATION.cff",
    "pyproject.toml",
    "PKG-INFO",
}
MIN_SDIST_PARTS = 2


def _bad_path(name: str) -> bool:
    parts = Path(name).parts
    return any(part in BANNED_PATH_PARTS or part.startswith("._") for part in parts)


def _check_bytes(name: str, data: bytes) -> None:
    if any(marker in data for marker in BANNED_TEXT):
        raise ValueError(f"private or research text found in package member: {name}")
    if re.search(rb"(?:ghp|github_pat|pypi)-[A-Za-z0-9_]{16,}", data):
        raise ValueError(f"credential-like text found in package member: {name}")


def check_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if any(_bad_path(name) for name in names):
            raise ValueError(f"wheel contains banned path: {path}")
        if any(not name.startswith(WHEEL_PREFIXES) for name in names):
            raise ValueError(f"wheel contains a path outside the allowlist: {path}")
        if not any(name == "ardguard/schemas/decision-v1.schema.json" for name in names):
            raise ValueError("wheel omits packaged schemas")
        for name in names:
            if not name.endswith("/"):
                _check_bytes(name, archive.read(name))


def check_sdist(path: Path) -> None:
    with tarfile.open(path, "r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        for member in members:
            parts = Path(member.name).parts
            if len(parts) < MIN_SDIST_PARTS:
                raise ValueError(f"sdist member lacks distribution root: {member.name}")
            relative = Path(*parts[1:])
            if _bad_path(str(relative)) or relative.parts[0] not in SDIST_ALLOWED_ROOTS:
                raise ValueError(f"sdist member outside allowlist: {relative}")
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"cannot read sdist member: {member.name}")
            _check_bytes(member.name, extracted.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist", type=Path)
    arguments = parser.parse_args()
    wheels = sorted(arguments.dist.glob("*.whl"))
    sdists = sorted(arguments.dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit("expected exactly one wheel and one sdist")
    check_wheel(wheels[0])
    check_sdist(sdists[0])
    print("ARDGUARD_PACKAGE_BOUNDARY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
