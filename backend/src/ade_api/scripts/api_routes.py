"""Summarise backend API routes for CLI/agent consumption."""

from __future__ import annotations

import argparse
import csv
from io import StringIO
from typing import Any

from fastapi.routing import APIRoute

from ade_api.common.encoding import json_dumps

from ..main import API_PREFIX, create_app

EXCLUDED_METHODS = {"head", "options"}
METHOD_ORDER = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def _load_schema() -> tuple[dict[str, Any], dict[tuple[str, str], str]]:
    """Return the OpenAPI schema and a lookup of handlers by (path, method)."""

    app = create_app()
    schema = app.openapi()

    handler_lookup: dict[tuple[str, str], str] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or []:
            key = (route.path, method.lower())
            handler_lookup[key] = f"{route.endpoint.__module__}:{route.endpoint.__qualname__}"

    return schema, handler_lookup


def _primary_status(responses: dict[str, Any]) -> str | None:
    if not responses:
        return None

    def _sort_key(code: str) -> tuple[int, str]:
        if code.isdigit():
            return (0, f"{int(code):03d}")
        return (1, code)

    return next(iter(sorted(responses.keys(), key=_sort_key)))


def collect_routes(prefix: str) -> list[dict[str, Any]]:
    schema, handler_lookup = _load_schema()
    paths = schema.get("paths", {})
    collected: list[dict[str, Any]] = []

    for path in sorted(paths):
        if prefix and not path.startswith(prefix):
            continue

        operations = paths[path]
        methods: list[dict[str, Any]] = []
        for method_name, operation in operations.items():
            method_lower = method_name.lower()
            if method_lower in EXCLUDED_METHODS:
                continue
            method_upper = method_lower.upper()
            summary = operation.get("summary") or operation.get("operationId") or ""
            status = _primary_status(operation.get("responses", {}))
            security = operation.get("security")
            handler = handler_lookup.get((path, method_lower))
            methods.append(
                {
                    "method": method_upper,
                    "summary": summary,
                    "operationId": operation.get("operationId"),
                    "status": status,
                    "auth": "public" if not security else "protected",
                    "deprecated": bool(operation.get("deprecated", False)),
                    "handler": handler,
                },
            )

        if not methods:
            continue

        methods.sort(
            key=lambda item: (
                METHOD_ORDER.index(item["method"])
                if item["method"] in METHOD_ORDER
                else len(METHOD_ORDER),
                item["method"],
            ),
        )
        collected.append(
            {
                "path": path,
                "methods": methods,
            },
        )

    return collected


def render_csv(routes: list[dict[str, Any]]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["path", "method", "status", "auth", "handler", "summary"])
    for route in routes:
        for method in route["methods"]:
            writer.writerow(
                [
                    route["path"],
                    method["method"],
                    method["status"] or "",
                    method["auth"],
                    method["handler"] or "",
                    method["summary"],
                ],
            )
    return buffer.getvalue().rstrip("\n")


def render_text(routes: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for route in routes:
        lines.append(route["path"])
        for method in route["methods"]:
            extras: list[str] = []
            if method["status"]:
                extras.append(f"status {method['status']}")
            if method["auth"] == "public":
                extras.append("public")
            if method["deprecated"]:
                extras.append("deprecated")
            if method["handler"]:
                extras.append(method["handler"])
            suffix = f"  [{'; '.join(extras)}]" if extras else ""
            summary = method["summary"]
            lines.append(f"  {method['method']:<6} {summary}{suffix}")
        lines.append("")

    return "\n".join(lines).rstrip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise backend API routes.")
    parser.add_argument(
        "--prefix",
        default=API_PREFIX,
        help="Filter endpoints by path prefix (default: %(default)s).",
    )
    parser.add_argument(
        "--format",
        choices=("csv", "text", "json"),
        default="csv",
        help="Output format (default: %(default)s).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Shortcut for --format json.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output.",
    )
    args = parser.parse_args()

    routes = collect_routes(prefix=args.prefix or "")
    data = {"ok": True, "routes": routes}

    fmt = "json" if args.json else args.format
    if fmt == "json":
        indent = 2 if args.pretty else None
        separators = (",", ": ") if args.pretty else (",", ":")
        print(json_dumps(data, indent=indent, separators=separators))
        return

    if fmt == "csv":
        print(render_csv(routes))
        return

    print(render_text(routes))


if __name__ == "__main__":
    main()
