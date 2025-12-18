"""ADE config hook: `on_workbook_start`

When this runs
--------------
- Once per input file, after ADE opens the *source* workbook.
- Before any sheets/tables are processed (`sheet` and `table` are `None`).

What it's useful for
--------------------
- Run-scoped setup (seed shared state, precompute flags, init reusable clients)
- Safe workbook inspection (sheet names, document properties, Excel "Tables")
- Failing fast with clear errors when required sheets/tables are missing

Return value
------------
- This hook MUST return `None` (returning anything else raises HookError).

Template goals
--------------
- Keep the default hook minimal and safe (no workbook edits, no heavy scanning).
- Keep examples self-contained and opt-in (uncomment in `register()`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Mapping, MutableMapping
import uuid

import openpyxl

if TYPE_CHECKING:  # pragma: no cover
    import polars as pl


# -----------------------------------------------------------------------------
# Shared state namespacing
# -----------------------------------------------------------------------------
# `state` is a mutable dict shared across the run.
# Best practice: store everything your config package needs under ONE top-level key.
#
# IMPORTANT: Keep this constant the same across *all* your hooks so they can share state.
STATE_NAMESPACE = "ade.config_package_template"
STATE_SCHEMA_VERSION = 1


def register(registry) -> None:
    """Register hook(s) with the ADE registry."""
    registry.register_hook(on_workbook_start, hook="on_workbook_start", priority=0)

    # ------------------------------------------------------------------
    # Optional examples (uncomment to enable)
    # ------------------------------------------------------------------
    # registry.register_hook(on_workbook_start_example_1_fail_fast_missing_sheets, hook="on_workbook_start", priority=10)
    # registry.register_hook(on_workbook_start_example_2_detect_workbook_flavor_and_flags, hook="on_workbook_start", priority=20)
    # registry.register_hook(on_workbook_start_example_3_emit_structured_event, hook="on_workbook_start", priority=30)
    # registry.register_hook(on_workbook_start_example_4_init_openai_client, hook="on_workbook_start", priority=40)
    # registry.register_hook(on_workbook_start_example_5_load_reference_sheet_into_polars, hook="on_workbook_start", priority=50)


def on_workbook_start(
    *,
    settings: Any,  # Engine settings (type depends on ADE)
    metadata: Mapping[str, Any],  # Run metadata (filenames, IDs, etc.)
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    workbook: openpyxl.Workbook,  # Source workbook (openpyxl Workbook)
    sheet: None,  # Always None for this hook
    table: None,  # Always None for this hook
    input_file_name: str | None,  # Input filename (basename) if known
    logger: Any,  # RunLogger (structured events + text logs)
) -> None:
    """Default hook: seed run state and log workbook basics (safe, no workbook edits)."""
    _ = (settings, sheet, table)  # unused by default

    # --- namespaced config state (shared across the run)
    cfg = state.get(STATE_NAMESPACE)
    if not isinstance(cfg, MutableMapping):
        cfg = {}
        state[STATE_NAMESPACE] = cfg

    # ------------------------------------------------------------------
    # 1) Establish run identity & timestamps (helpful for logs + debugging)
    # ------------------------------------------------------------------
    cfg.setdefault("schema_version", STATE_SCHEMA_VERSION)

    run_started_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    cfg.setdefault("run_started_at", run_started_at)
    cfg.setdefault("run_id", metadata.get("run_id") or uuid.uuid4().hex[:12])

    # ------------------------------------------------------------------
    # 2) Record the “best available” input label for logs/events
    # ------------------------------------------------------------------
    input_label = ""
    for key in ("input_file", "source_file", "filename", "path"):
        val = metadata.get(key)
        if isinstance(val, str) and val.strip():
            input_label = val.strip()
            break
    if not input_label:
        input_label = input_file_name or ""

    cfg.setdefault("input", {})
    if isinstance(cfg.get("input"), MutableMapping):
        cfg["input"].update({"file": input_label, "basename": input_file_name})  # type: ignore[union-attr]
    else:
        cfg["input"] = {"file": input_label, "basename": input_file_name}

    # ------------------------------------------------------------------
    # 3) Inspect workbook shape (safe + fast)
    # ------------------------------------------------------------------
    sheet_names = list(getattr(workbook, "sheetnames", []) or [])

    # Safe, compact document properties (avoid logging full objects).
    props_out: dict[str, Any] = {}
    props = getattr(workbook, "properties", None)
    if props is not None:
        for key in (
            "title",
            "subject",
            "creator",
            "description",
            "keywords",
            "category",
            "created",
            "modified",
            "lastModifiedBy",
            "revision",
        ):
            val = getattr(props, key, None)
            if val not in (None, ""):
                props_out[key] = val

    cfg["workbook"] = {
        "sheet_count": len(sheet_names),
        "sheet_names": sheet_names,
        "properties": props_out,
    }

    # (Optional) Collect Excel "Table" objects per sheet (Insert → Table).
    # These are NOT the same thing as ADE tables, but can be useful for validation/routing.
    excel_tables_by_sheet: dict[str, list[str]] = {}
    for ws in getattr(workbook, "worksheets", []) or []:
        ws_name = getattr(ws, "title", None) or "<unknown>"
        tables = getattr(ws, "tables", None)

        names: list[str] = []
        if tables is None:
            names = []
        elif hasattr(tables, "keys"):
            try:
                names = sorted([str(k) for k in tables.keys()])
            except Exception:
                names = []
        else:
            try:
                names = sorted([str(k) for k in tables])
            except Exception:
                names = []

        excel_tables_by_sheet[str(ws_name)] = names

    cfg["excel_tables_by_sheet"] = excel_tables_by_sheet

    # ------------------------------------------------------------------
    # 4) Seed shared state structures for downstream hooks
    # ------------------------------------------------------------------
    cfg.setdefault("notes", [])  # downstream hooks can append strings here

    counters = cfg.get("counters")
    if not isinstance(counters, MutableMapping):
        counters = {}
        cfg["counters"] = counters
    counters.setdefault("sheets_seen", 0)
    counters.setdefault("tables_seen", 0)

    # A good spot to keep reusable clients/resources.
    # (Avoid storing secrets here; store secrets in env vars or secure settings.)
    cfg.setdefault("clients", {})  # e.g., {"openai": <OpenAI>, "http": <httpx.Client>}

    # ------------------------------------------------------------------
    # 5) Emit a simple log line
    # ------------------------------------------------------------------
    if logger:
        logger.info(
            "Config hook: workbook start (input=%s, sheets=%d)",
            input_label,
            len(sheet_names),
        )

    return None


# -----------------------------------------------------------------------------
# Optional examples (disabled by default)
# -----------------------------------------------------------------------------


def on_workbook_start_example_1_fail_fast_missing_sheets(
    *,
    settings: Any,
    metadata: Mapping[str, Any],
    state: MutableMapping[str, Any],
    workbook: openpyxl.Workbook,
    sheet: None,
    table: None,
    input_file_name: str | None,
    logger: Any,
) -> None:
    """Example 1: Fail fast if required worksheets are missing."""
    _ = (settings, metadata, state, sheet, table, input_file_name, logger)

    required = {"Orders", "Customers"}  # customize
    sheet_names = set(getattr(workbook, "sheetnames", []) or [])
    missing = sorted(required - sheet_names)
    if missing:
        raise ValueError(
            "Input workbook is missing required worksheet(s): " + ", ".join(missing)
        )

    return None


def on_workbook_start_example_2_detect_workbook_flavor_and_flags(
    *,
    settings: Any,
    metadata: Mapping[str, Any],
    state: MutableMapping[str, Any],
    workbook: openpyxl.Workbook,
    sheet: None,
    table: None,
    input_file_name: str | None,
    logger: Any,
) -> None:
    """Example 2: Set workbook-level flags for later hooks/detectors."""
    _ = (settings, metadata, sheet, table, input_file_name)

    cfg = state.get(STATE_NAMESPACE)
    if not isinstance(cfg, MutableMapping):
        cfg = {}
        state[STATE_NAMESPACE] = cfg

    sheet_names = [str(s).lower() for s in (getattr(workbook, "sheetnames", []) or [])]

    # Toy heuristics (replace with your real template/vendor detection).
    if any("acme" in s for s in sheet_names):
        vendor = "acme"
    elif any("globex" in s for s in sheet_names):
        vendor = "globex"
    else:
        vendor = "unknown"

    flags = cfg.get("flags")
    if not isinstance(flags, MutableMapping):
        flags = {}
        cfg["flags"] = flags
    flags.update(
        {
            "vendor": vendor,
            "treat_blank_as_null": True,
        }
    )

    if logger:
        logger.info("Detected workbook vendor=%s", vendor)

    return None


def on_workbook_start_example_3_emit_structured_event(
    *,
    settings: Any,
    metadata: Mapping[str, Any],
    state: MutableMapping[str, Any],
    workbook: openpyxl.Workbook,
    sheet: None,
    table: None,
    input_file_name: str | None,
    logger: Any,
) -> None:
    """Example 3: Emit a config-scoped structured event (no strict schema required)."""
    _ = (settings, state, workbook, sheet, table)

    if not logger or not hasattr(logger, "event"):
        return None

    input_label = ""
    for key in ("input_file", "source_file", "filename", "path"):
        val = metadata.get(key)
        if isinstance(val, str) and val.strip():
            input_label = val.strip()
            break
    if not input_label:
        input_label = input_file_name or ""

    logger.event(
        "engine.config.workbook.start",
        data={
            "input_file": input_label,
            "sheet_count": len(getattr(workbook, "sheetnames", []) or []),
            "sheet_names": list(getattr(workbook, "sheetnames", []) or []),
        },
    )

    return None


def on_workbook_start_example_4_init_openai_client(
    *,
    settings: Any,
    metadata: Mapping[str, Any],
    state: MutableMapping[str, Any],
    workbook: openpyxl.Workbook,
    sheet: None,
    table: None,
    input_file_name: str | None,
    logger: Any,
) -> None:
    """Example 4: Initialize an OpenAI client once and store it in `state`.

    Notes:
    - This example does NOT make a network call. It just prepares the client.
    - The OpenAI SDK reads `OPENAI_API_KEY` from the environment automatically.
    """
    _ = (metadata, workbook, sheet, table, input_file_name)

    import os

    cfg = state.get(STATE_NAMESPACE)
    if not isinstance(cfg, MutableMapping):
        cfg = {}
        state[STATE_NAMESPACE] = cfg

    clients = cfg.get("clients")
    if not isinstance(clients, MutableMapping):
        clients = {}
        cfg["clients"] = clients

    if "openai" in clients:
        return None  # already initialized

    if not os.getenv("OPENAI_API_KEY"):
        if logger and hasattr(logger, "warning"):
            logger.warning("OPENAI_API_KEY is not set; skipping OpenAI client init.")
        return None

    try:
        # Official OpenAI Python SDK:
        #   pip install openai
        #   from openai import OpenAI
        from openai import OpenAI  # type: ignore
    except Exception as exc:
        if logger and hasattr(logger, "warning"):
            logger.warning("OpenAI SDK not installed; skipping OpenAI init (%s).", exc)
        return None

    clients["openai"] = OpenAI()

    # Store per-run defaults for downstream usage (detectors can read these).
    llm = cfg.get("llm")
    if not isinstance(llm, MutableMapping):
        llm = {}
        cfg["llm"] = llm
    llm.setdefault("model", getattr(settings, "openai_model", "gpt-4o-mini"))
    llm.setdefault(
        "system_prompt",
        "You are a helpful assistant that summarizes Excel workbooks for data processing.",
    )

    if logger:
        logger.info("Initialized OpenAI client for downstream use (model=%s)", llm["model"])

    return None


def on_workbook_start_example_5_load_reference_sheet_into_polars(
    *,
    settings: Any,
    metadata: Mapping[str, Any],
    state: MutableMapping[str, Any],
    workbook: openpyxl.Workbook,
    sheet: None,
    table: None,
    input_file_name: str | None,
    logger: Any,
) -> None:
    """Example 5: Load a small reference sheet into Polars and stash it in `state`.

    Pattern:
    - Read the lookup sheet with openpyxl (`iter_rows(values_only=True)`)
    - Build a small Polars DataFrame
    - Cache it in `state` so downstream hooks can join/enrich quickly

    Best practice:
    - Keep this small. For large sheets, defer reading until you need it.
    """
    _ = (metadata, sheet, table, input_file_name)

    cfg = state.get(STATE_NAMESPACE)
    if not isinstance(cfg, MutableMapping):
        cfg = {}
        state[STATE_NAMESPACE] = cfg

    # Only do this once per run.
    if "reference" in cfg:
        return None

    try:
        import polars as pl  # type: ignore
    except Exception as exc:
        if logger and hasattr(logger, "warning"):
            logger.warning("Polars is not installed; skipping reference load (%s).", exc)
        cfg["reference"] = {"df": None, "sheet": None}
        return None

    sheet_name = getattr(settings, "reference_sheet_name", "Reference")
    if sheet_name not in (getattr(workbook, "sheetnames", []) or []):
        if logger:
            logger.info("No %r sheet found; skipping reference load.", sheet_name)
        cfg["reference"] = {"df": None, "sheet": sheet_name}
        return None

    ws = workbook[sheet_name]

    # Beginner-friendly: read rows as values (no cell objects).
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if not header:
        cfg["reference"] = {"df": pl.DataFrame(), "sheet": sheet_name}
        return None

    # Normalize column names (avoid None and strip whitespace).
    columns = [
        str(c).strip() if c is not None else f"col_{i+1}"
        for i, c in enumerate(header)
    ]

    data_rows: list[list[Any]] = []
    for row in rows_iter:
        if row is None:
            continue
        # Skip completely empty rows.
        if not any(cell is not None and str(cell).strip() != "" for cell in row):
            continue
        data_rows.append(list(row))

    df: "pl.DataFrame" = pl.DataFrame(data_rows, schema=columns, orient="row")
    cfg["reference"] = {"df": df, "sheet": sheet_name}

    if logger:
        logger.info("Loaded reference sheet %r into Polars (%d rows).", sheet_name, df.height)

    return None
