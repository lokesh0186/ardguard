#!/usr/bin/env python3
"""Validate static-site integrity, security boundaries, links, and fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SCENARIOS = 12
EXPECTED_VERSION = "0.1.0b4"
MIN_HTML_PAGES = 3
SHA256_HEX_LENGTH = 64


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.scripts: list[str | None] = []
        self.stylesheets: list[str] = []
        self.inline_handlers: list[str] = []
        self.h1_count = 0
        self.main_count = 0
        self.skip_link = False
        self.csp = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
            if "skip-link" in (values.get("class") or ""):
                self.skip_link = True
        if tag == "script":
            self.scripts.append(values.get("src"))
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.stylesheets.append(values["href"] or "")
        if tag == "h1":
            self.h1_count += 1
        if tag == "main":
            self.main_count += 1
        if tag == "meta" and values.get("http-equiv", "").lower() == "content-security-policy":
            self.csp = True
        self.inline_handlers.extend(name for name, _ in attrs if name.lower().startswith("on"))
        if "style" in values:
            self.inline_handlers.append("style")


def fail(message: str) -> None:
    raise ValueError(message)


def resolve_local(page: Path, target: str, site: Path) -> Path | None:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith("mailto:"):
        return None
    clean = unquote(parsed.path)
    if not clean or clean.startswith("#"):
        return None
    resolved = (site / clean.lstrip("/")) if clean.startswith("/") else (page.parent / clean)
    if clean.endswith("/") or (not resolved.suffix and resolved.is_dir()):
        resolved = resolved / "index.html"
    return resolved.resolve()


def check_html(site: Path) -> None:
    pages = sorted(site.rglob("*.html"))
    if len(pages) < MIN_HTML_PAGES:
        fail("site must contain home, Explorer, and documentation pages")
    for page in pages:
        text = page.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(text)
        if parser.h1_count != 1:
            fail(f"{page}: expected exactly one h1")
        if parser.main_count != 1 or not parser.skip_link:
            fail(f"{page}: missing main landmark or skip link")
        if not parser.csp:
            fail(f"{page}: missing Content Security Policy")
        if parser.inline_handlers:
            fail(f"{page}: inline script/style surface is prohibited: {parser.inline_handlers}")
        if any(source is None for source in parser.scripts):
            fail(f"{page}: inline scripts are prohibited")
        for target in [*parser.links, *parser.scripts, *parser.stylesheets]:
            resolved = resolve_local(page, target, site)
            if resolved is not None and not resolved.exists():
                fail(f"{page}: broken local reference {target}")


def check_javascript(site: Path) -> None:
    prohibited = re.compile(r"\b(innerHTML|outerHTML|document\.write|eval|new Function)\b")
    for path in site.rglob("*.js"):
        source = path.read_text(encoding="utf-8")
        match = prohibited.search(source)
        if match:
            fail(f"{path}: prohibited rendering primitive {match.group(1)}")
        if "\\n+  " in source:
            fail(f"{path}: snippet contains a stray diff marker")
    if (site / "package.json").exists() or list(site.rglob("node_modules")):
        fail("static site must not have a runtime dependency tree")


def check_scenario(item: dict[str, str], fixture_dir: Path) -> None:
    fixture = json.loads((fixture_dir / item["file"]).read_text(encoding="utf-8"))
    decision = fixture["decision"]
    if fixture["package"]["version"] != EXPECTED_VERSION:
        fail(f"{item['id']}: wrong package version")
    if fixture["invocation"] != "NOT_PERFORMED":
        fail(f"{item['id']}: invocation boundary changed")
    ordered = sorted(decision["evaluations"], key=lambda row: row["rank"])
    if decision["outcome"] == "SELECT":
        selected = next(
            row for row in ordered if row["candidate_id"] == decision["selected_candidate_id"]
        )
        if selected["status"] != "SATISFIED" or selected["rank"] != decision["selected_rank"]:
            fail(f"{item['id']}: selected candidate is not satisfied at selected rank")
        if any(row["status"] == "SATISFIED" for row in ordered if row["rank"] < selected["rank"]):
            fail(f"{item['id']}: selection skipped a higher-ranked eligible candidate")
    if decision["receipt"]["software_version"] != EXPECTED_VERSION:
        fail(f"{item['id']}: receipt software version mismatch")
    if len(decision["receipt"]["receipt_sha256"]) != SHA256_HEX_LENGTH:
        fail(f"{item['id']}: invalid receipt hash")


def check_fixtures(site: Path) -> None:
    fixture_dir = site / "fixtures"
    index = json.loads((fixture_dir / "index.json").read_text(encoding="utf-8"))
    if index.get("package_version") != EXPECTED_VERSION:
        fail("fixture index does not name public Beta 4")
    scenarios = index.get("scenarios", [])
    if len(scenarios) != EXPECTED_SCENARIOS:
        fail(f"expected {EXPECTED_SCENARIOS} scenarios")
    ids = [item["id"] for item in scenarios]
    if len(ids) != len(set(ids)):
        fail("scenario IDs must be unique")
    for item in scenarios:
        check_scenario(item, fixture_dir)

    for line in (fixture_dir / "hashes.sha256").read_text(encoding="utf-8").splitlines():
        digest, filename = line.split("  ", 1)
        actual = hashlib.sha256((fixture_dir / filename).read_bytes()).hexdigest()
        if actual != digest:
            fail(f"fixture hash mismatch: {filename}")


def check_content(site: Path) -> None:
    public_text_suffixes = {".css", ".html", ".js", ".json", ".md", ".txt", ".xml", ".yaml"}
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in site.rglob("*")
        if path.is_file() and path.suffix in public_text_suffixes
    )
    required = (
        "ARDGuard adds task-specific eligibility and safe fallback",
        "ARDGuard does not replace",
        "NOT_PERFORMED",
        "DecisionReceipt",
        "provider unavailable",
        "Why not just filter?",
        "Why not just a trust score?",
        "no analytics",
    )
    for phrase in required:
        if phrase.casefold() not in combined.casefold():
            fail(f"missing required public explanation: {phrase}")
    prohibited = (
        "EB-1A",
        "US" + "ENIX",
        "Hot" + "CRP",
        "anonymous submission",
        "independent adoption",
        "ARDGUARD_EXTERNAL_IMPACT_CAMPAIGN",
        "/" + "Users/",
        "/private/" + "tmp",
        "FastMCP #5160",
        "Semantic Kernel #14032",
        "causal score",
    )
    for phrase in prohibited:
        if phrase.casefold() in combined.casefold():
            fail(f"prohibited public claim/material found: {phrase}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", nargs="?", type=Path, default=ROOT / "build" / "public-site")
    args = parser.parse_args()
    site = args.site.resolve()
    try:
        check_html(site)
        check_javascript(site)
        check_fixtures(site)
        check_content(site)
    except (OSError, ValueError, KeyError, StopIteration, json.JSONDecodeError) as exc:
        print(f"public site check failed: {exc}", file=sys.stderr)
        return 1
    print("public site integrity, security, accessibility, links, and fixtures: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
