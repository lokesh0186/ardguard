#!/usr/bin/env python3
"""Create a local compatibility-drift report without opening external issues."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

UPSTREAMS = {
    "ard-spec": (
        "https://github.com/ards-project/ard-spec.git",
        "aa3e598bb7752a9175897823234311216acfa864",
    ),
    "hf-discover": (
        "https://github.com/huggingface/hf-discover.git",
        "49c927439fcaa8f210cfd42186c0641acef579fa",
    ),
}


def main() -> int:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git executable is unavailable")
    records = []
    for name, (url, pinned) in sorted(UPSTREAMS.items()):
        completed = subprocess.run(  # noqa: S603
            [git, "ls-remote", url, "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        current = completed.stdout.split()[0] if completed.returncode == 0 else None
        records.append(
            {
                "name": name,
                "url": url,
                "pinned_commit": pinned,
                "current_commit": current,
                "status": "MATCH" if current == pinned else "DRIFT_OR_UNAVAILABLE",
                "error": completed.stderr.strip() or None,
            }
        )
    report = {
        "schema_version": "ardguard.dev/compatibility-watch/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "external_action": "NONE",
    }
    target = Path("compatibility-report.json")
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target)
    return int(any(item["status"] != "MATCH" for item in records))


if __name__ == "__main__":
    raise SystemExit(main())
