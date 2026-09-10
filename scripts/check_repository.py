#!/usr/bin/env python3
"""Check the public repository for private material and artifact hygiene."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "dist", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
BANNED_NAMES = {".DS_Store", "__MACOSX"}
BANNED_TEXT = (
    "USENIX",
    "HotCRP",
    "4open.science",
    "U3R17",
    "U3R18",
    "U3R19",
    "U3R20",
    "U3R21",
    "U3R22",
    "/Users/",
    "/private/tmp",
    "anonymous artifact",
    "manuscript",
)


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if relative in {
            Path("scripts/check_repository.py"),
            Path("scripts/check_package.py"),
        }:
            continue
        if any(part in SKIP for part in relative.parts):
            continue
        if path.name in BANNED_NAMES or path.name.startswith("._"):
            failures.append(f"banned path: {relative}")
            continue
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for marker in BANNED_TEXT:
            if marker.casefold() in text.casefold():
                failures.append(f"banned text {marker!r}: {relative}")
        if "\N{EM DASH}" in text:
            failures.append(f"em dash: {relative}")
        if re.search(
            r"(?:gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|pypi-[A-Za-z0-9_]{16,}|AKIA[0-9A-Z]{16})",
            text,
        ):
            failures.append(f"credential-like text: {relative}")
    if failures:
        raise SystemExit("\n".join(sorted(failures)))
    print("ARDGUARD_PUBLIC_REPOSITORY_BOUNDARY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
