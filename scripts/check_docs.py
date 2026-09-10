#!/usr/bin/env python3
"""Validate local documentation links and JSON examples."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")


def main() -> int:
    failures: list[str] = []
    for path in sorted(ROOT.rglob("*.md")):
        if any(
            part in {".git", "dist", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
            for part in path.parts
        ):
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            target = raw_target.strip().split("#", 1)[0]
            if not target or target.startswith(("https://", "http://", "mailto:")):
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                failures.append(f"link escapes repository: {path.relative_to(ROOT)} -> {target}")
                continue
            if not resolved.exists():
                failures.append(f"broken local link: {path.relative_to(ROOT)} -> {target}")
    for path in sorted((ROOT / "examples").rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append(f"invalid example JSON: {path.relative_to(ROOT)}: {exc}")
    if failures:
        raise SystemExit("\n".join(failures))
    print("ARDGUARD_DOCUMENTATION_AND_EXAMPLES_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
