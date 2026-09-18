#!/usr/bin/env python3
"""Assemble the static GitHub Pages artifact without modifying source files."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site"
DESTINATION = ROOT / "build" / "public-site"


def main() -> None:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    shutil.copytree(SOURCE, DESTINATION)
    shutil.copy2(ROOT / "docs" / "openapi-v1.yaml", DESTINATION / "openapi-v1.yaml")
    shutil.copy2(ROOT / "docs" / "support-matrix.json", DESTINATION / "support-matrix.json")
    (DESTINATION / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built static site at {DESTINATION.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
