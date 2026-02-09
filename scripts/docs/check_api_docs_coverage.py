#!/usr/bin/env python3
"""Validate API docs coverage and quality gates for top workflow docs."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = REPO_ROOT / "backend" / "src" / "ade_api" / "openapi.json"

REFERENCE_FILES: dict[str, Path] = {
    "auth": REPO_ROOT / "docs" / "reference" / "api" / "authentication.md",
    "workspaces": REPO_ROOT / "docs" / "reference" / "api" / "workspaces.md",
    "configurations": REPO_ROOT / "docs" / "reference" / "api" / "configurations.md",
    "documents": REPO_ROOT / "docs" / "reference" / "api" / "documents.md",
    "runs": REPO_ROOT / "docs" / "reference" / "api" / "runs.md",
}

HOWTO_FILES: list[Path] = [
    REPO_ROOT / "docs" / "how-to" / "api-authenticate-with-api-key.md",
    REPO_ROOT / "docs" / "how-to" / "api-manage-configurations.md",
    REPO_ROOT / "docs" / "how-to" / "api-upload-and-queue-runs.md",
    REPO_ROOT / "docs" / "how-to" / "api-create-and-monitor-runs.md",
]

METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
BANNED_SUMMARY_PATTERNS = [re.compile(r"\bEndpoint\b", re.IGNORECASE)]

TABLE_ENDPOINT_PATTERN = re.compile(
    r"\|\s*`?(GET|POST|PUT|PATCH|DELETE)`?\s*\|\s*`?(/api/v1/[^`|\s]+)`?\s*\|"
)
INLINE_ENDPOINT_PATTERN = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/api/v1/[^\s`]+)")


def infer_domain(tags: set[str]) -> str | None:
    if tags.intersection({"auth", "me"}):
        return "auth"
    if "workspaces" in tags:
        return "workspaces"
    if "configurations" in tags:
        return "configurations"
    if "documents" in tags:
        return "documents"
    if "runs" in tags:
        return "runs"
    return None


def parse_reference_endpoints(text: str) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for method, path in TABLE_ENDPOINT_PATTERN.findall(text):
        found.add((method.upper(), path))
    for method, path in INLINE_ENDPOINT_PATTERN.findall(text):
        found.add((method.upper(), path))
    return found


def load_top_workflow_operations(schema: dict) -> dict[tuple[str, str], str]:
    operations: dict[tuple[str, str], str] = {}

    for path, path_item in schema.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            method_upper = method.upper()
            if method_upper not in METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            tags = {str(tag) for tag in operation.get("tags", []) if isinstance(tag, str)}
            domain = infer_domain(tags)
            if domain is None:
                continue
            operations[(method_upper, path)] = domain

    return operations


def check_reference_coverage(schema: dict) -> list[str]:
    errors: list[str] = []
    expected = load_top_workflow_operations(schema)

    missing_files = [path for path in REFERENCE_FILES.values() if not path.exists()]
    if missing_files:
        for path in missing_files:
            errors.append(f"Missing reference file: {path.relative_to(REPO_ROOT)}")
        return errors

    parsed_by_file: dict[str, set[tuple[str, str]]] = {}
    file_hits: defaultdict[tuple[str, str], list[str]] = defaultdict(list)

    for domain, file_path in REFERENCE_FILES.items():
        endpoints = parse_reference_endpoints(file_path.read_text(encoding="utf-8"))
        parsed_by_file[domain] = endpoints
        for endpoint in endpoints:
            file_hits[endpoint].append(domain)

    for endpoint, domain in sorted(expected.items(), key=lambda item: (item[0][1], item[0][0])):
        method, path = endpoint
        if endpoint not in parsed_by_file[domain]:
            errors.append(
                f"Missing endpoint in expected reference page: {method} {path} -> {domain}"
            )
            continue

        domains = file_hits.get(endpoint, [])
        wrong_domains = sorted({entry for entry in domains if entry != domain})
        if wrong_domains:
            errors.append(
                "Endpoint appears in multiple domain pages: "
                f"{method} {path} (expected {domain}, also in {', '.join(wrong_domains)})"
            )

    return errors


def check_howto_examples() -> list[str]:
    errors: list[str] = []

    for file_path in HOWTO_FILES:
        rel = file_path.relative_to(REPO_ROOT)
        if not file_path.exists():
            errors.append(f"Missing API how-to file: {rel}")
            continue

        content = file_path.read_text(encoding="utf-8")
        if "curl " not in content and "curl\\n" not in content:
            errors.append(f"Missing curl example in {rel}")
        if "```python" not in content:
            errors.append(f"Missing Python example block in {rel}")
        if "```powershell" not in content:
            errors.append(f"Missing PowerShell example block in {rel}")

    return errors


def check_banned_summaries(schema: dict) -> list[str]:
    errors: list[str] = []

    expected = load_top_workflow_operations(schema)
    for (method, path), _domain in sorted(expected.items(), key=lambda item: (item[0][1], item[0][0])):
        operation = schema["paths"][path][method.lower()]
        summary = str(operation.get("summary", "")).strip()
        for pattern in BANNED_SUMMARY_PATTERNS:
            if pattern.search(summary):
                errors.append(
                    f"Banned summary pattern in OpenAPI: {method} {path} -> {summary!r}"
                )
                break

    return errors


def main() -> int:
    if not OPENAPI_PATH.exists():
        print(f"error: missing OpenAPI schema at {OPENAPI_PATH.relative_to(REPO_ROOT)}")
        print("run: cd backend && uv run ade api types")
        return 1

    schema = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    errors: list[str] = []
    errors.extend(check_reference_coverage(schema))
    errors.extend(check_howto_examples())
    errors.extend(check_banned_summaries(schema))

    if errors:
        print("API docs coverage check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("API docs coverage check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
