#!/usr/bin/env python3
"""Deterministic five-pass health check for TroyHokanson.com.

The fixer is intentionally narrow: it can repair CNAME formatting and missing
``noreferrer`` on links that already use ``target=_blank``. Career claims,
privacy decisions, and public content remain review-gated.
"""

from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = ("index.html", "credentials.html", "practice.html", "evidence.html")


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: Counter[str] = Counter()
        self.ids: list[str] = []
        self.links: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.meta: list[dict[str, str]] = []
        self.title_parts: list[str] = []
        self.visible_parts: list[str] = []
        self._in_title = False
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        self.tags[tag] += 1
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "a":
            self.links.append(values)
        elif tag == "img":
            self.images.append(values)
        elif tag == "meta":
            self.meta.append(values)
        elif tag == "title":
            self._in_title = True
        if tag in {"style", "script"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"style", "script"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if not self._hidden_depth:
            cleaned = " ".join(data.split())
            if cleaned:
                self.visible_parts.append(cleaned)

    @property
    def title(self) -> str:
        return " ".join(" ".join(self.title_parts).split())

    @property
    def text(self) -> str:
        return " ".join(self.visible_parts)


def load_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def add_issue(issues: list[dict[str, str]], level: str, audit_pass: str, message: str) -> None:
    issues.append({"level": level, "pass": audit_pass, "message": message})


def pass_structure(pages: dict[str, PageParser], issues: list[dict[str, str]]) -> None:
    for name, page in pages.items():
        if not page.title:
            add_issue(issues, "error", "structure", f"{name}: missing title")
        if page.tags["h1"] != 1:
            add_issue(issues, "error", "structure", f"{name}: expected one h1, found {page.tags['h1']}")
        if page.tags["main"] != 1:
            add_issue(issues, "error", "structure", f"{name}: expected one main landmark")
        descriptions = [m.get("content") for m in page.meta if m.get("name", "").lower() == "description"]
        if not any(descriptions):
            add_issue(issues, "error", "structure", f"{name}: missing meta description")
        duplicate_ids = [item for item, count in Counter(page.ids).items() if count > 1]
        if duplicate_ids:
            add_issue(issues, "error", "structure", f"{name}: duplicate ids {duplicate_ids}")
        for image in page.images:
            if "alt" not in image:
                add_issue(issues, "error", "structure", f"{name}: image missing alt text")


def pass_links(pages: dict[str, PageParser], issues: list[dict[str, str]]) -> None:
    for name, page in pages.items():
        for link in page.links:
            href = link.get("href", "").strip()
            if not href:
                add_issue(issues, "error", "links", f"{name}: anchor missing href")
                continue
            if link.get("target") == "_blank":
                rel = set(link.get("rel", "").split())
                if not {"noopener", "noreferrer"}.issubset(rel):
                    add_issue(issues, "error", "links", f"{name}: target=_blank link lacks noopener noreferrer: {href}")
            parsed = urlparse(href)
            if parsed.hostname in {"drive.google.com", "docs.google.com"}:
                add_issue(issues, "error", "links", f"{name}: unreviewed Google Drive link is not public-safe: {href}")
                continue
            if parsed.scheme or href.startswith("mailto:"):
                continue
            target_name, _, fragment = href.partition("#")
            target_name = target_name or name
            target_path = ROOT / target_name
            if not target_path.exists():
                add_issue(issues, "error", "links", f"{name}: missing local target {target_name}")
                continue
            if fragment:
                target_page = pages.get(target_name) or load_page(target_path)
                if fragment not in target_page.ids:
                    add_issue(issues, "error", "links", f"{name}: missing fragment #{fragment} in {target_name}")


def pass_contract(pages: dict[str, PageParser], contract: dict, issues: list[dict[str, str]]) -> None:
    combined = " ".join(page.text for page in pages.values())
    for name, rules in contract["pages"].items():
        text = pages[name].text
        for required in rules.get("required_text", []):
            if required not in text:
                add_issue(issues, "error", "facts", f"{name}: missing required public-safe fact: {required}")
    for pattern in contract.get("forbidden_patterns", []):
        if re.search(pattern, combined):
            add_issue(issues, "error", "facts", f"forbidden or unresolved public claim matched: {pattern}")


def pass_privacy(pages: dict[str, PageParser], issues: list[dict[str, str]]) -> None:
    combined = " ".join(page.text for page in pages.values())
    hard_blocks = {
        r"(?i)control\s*#\s*\d+": "internal case-control number",
        r"\b\d{2}[A-Z]{2}-[A-Z]{2}-\d{2}-\d{4}\b": "court case number",
        r"(?i)\bDOB\s*[:\-]?\s*\d{2}/\d{2}/\d{4}\b": "date of birth",
        r"(?i)\b(?:SSN|social security number)\b": "social-security identifier",
    }
    for pattern, label in hard_blocks.items():
        if re.search(pattern, combined):
            add_issue(issues, "error", "privacy", f"public site contains {label}")


def fetch(url: str) -> tuple[int, bytes]:
    request = Request(url, headers={"User-Agent": "TroyHokanson-Portfolio-Health/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.status, response.read()


def pass_deployment(contract: dict, issues: list[dict[str, str]]) -> None:
    base = f"https://{contract['canonical_domain']}/"
    for name in HTML_FILES:
        url = urljoin(base, "" if name == "index.html" else name)
        try:
            status, body = fetch(url)
        except (HTTPError, URLError, TimeoutError) as exc:
            add_issue(issues, "error", "deployment", f"{url}: {exc}")
            continue
        if status != 200:
            add_issue(issues, "error", "deployment", f"{url}: HTTP {status}")
            continue
        local = (ROOT / name).read_bytes()
        if body != local:
            add_issue(issues, "error", "deployment", f"{url}: deployed content differs from main checkout")


def apply_safe_fixes() -> list[str]:
    changed: list[str] = []
    cname = ROOT / "CNAME"
    expected = "TroyHokanson.com\n"
    if cname.read_text(encoding="utf-8") != expected:
        cname.write_text(expected, encoding="utf-8")
        changed.append("CNAME")
    for name in HTML_FILES:
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        fixed = re.sub(r'rel="noopener"(?=[^>]*target="_blank")', 'rel="noopener noreferrer"', source)
        fixed = re.sub(r'target="_blank"(?=[^>]*rel="noopener")', 'target="_blank"', fixed)
        if fixed != source:
            path.write_text(fixed, encoding="utf-8")
            changed.append(name)
    return changed


def run(check_live: bool, fix: bool) -> dict:
    changed = apply_safe_fixes() if fix else []
    contract = json.loads((ROOT / "portfolio_contract.json").read_text(encoding="utf-8"))
    pages = {name: load_page(ROOT / name) for name in HTML_FILES}
    issues: list[dict[str, str]] = []
    pass_structure(pages, issues)
    pass_links(pages, issues)
    pass_contract(pages, contract, issues)
    pass_privacy(pages, issues)
    if check_live:
        pass_deployment(contract, issues)
    return {
        "status": "failed" if any(i["level"] == "error" for i in issues) else "passed",
        "passes": ["structure", "links", "facts", "privacy", "deployment" if check_live else "deployment-skipped"],
        "safe_fixes_applied": changed,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-live", action="store_true")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = run(args.check_live, args.fix)
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
