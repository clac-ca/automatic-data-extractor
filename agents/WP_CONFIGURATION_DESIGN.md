# Work Package: Column Pack Detection & Transform Script Contract (v1)

## Summary

This work package defines a simple, intuitive “**Column Pack**” scripting contract that lets us author detection and transformation logic for ADE’s column mapping in a way that is:

* easy to read and write,
* consistent across all columns,
* safe and deterministic at runtime.

A **Column Pack** is a single Python module for one canonical column key (e.g., `full_name`). The pack can include:

* an optional `setup(context)` that runs **once** and returns a `state` object,
* **one or more** `detect_*` functions (names must start with `detect_`) that run **per physical column** and return **score adjustments** (positive or negative) for `self` and/or other columns,
* an optional `transform_cell(...)` that runs **per cell** after mapping and returns **row cell outputs** for `self` and optionally other columns (fill-if-empty merge policy).

The host application handles discovery, merging, tie-breaking, and application of transforms. Authors only write small, obvious functions with a uniform return shape.

---

## Design goals

* **Instant readability:** Developers should grasp the contract and examples at a glance.
* **Uniform returns:** `detect_*` always returns `{"scores": {...}}`; `transform_cell` always returns `{"cells": {...}}`.
* **Multiple detects per script:** Keep all rules together; each detect adds (or subtracts) from the column’s scoreboard.
* **Deterministic runtime:** Internet allowed **only** in `setup`; `detect_*` and `transform_cell` are pure and fast.
* **Non-destructive transforms:** Upserts to other columns use a **fill-if-empty** policy by default.
* **Simple extension points:** Future features (params, explanations, strategies) can be added without breaking authors.

---

## Runtime model (how the app will use packs)

1. **Load & metadata:** Import the module; read `name`, `description`, `version` from the module docstring. `name` is the canonical column key (e.g., `full_name`).
2. **Setup (optional):** If `setup(context)` exists, call once; keep its return (dictionary) as `state` and pass it to all subsequent calls.
3. **Detection pass (per physical column):**

   * Discover all callables named `detect_*`.
   * Call each with a stable payload: `header, values, table, column_index, sheet_name, bounds, state, context`.
   * Each returns `{"scores": { "self": <delta>, "other_key": <delta>, ... }}`.
   * The app **sums** deltas into a scoreboard for that physical column; `"self"` is substituted with the pack’s canonical key.
   * After all packs run, choose the **winning canonical key** per physical column using a threshold & deterministic tie-break.
4. **Transform pass (after mapping):**

   * For each assigned pack, call `transform_cell(...)` for each row.
   * Each returns `{"cells": { "self": <normalized>, "other_key": <value>, ... }}`.
   * Write `cells["self"]` to the mapped output column for that row; apply other keys to the same row with **fill-if-empty** policy.
5. **Logging/telemetry:** In debug mode, log which detects contributed what deltas; keep `state` and values out of logs if sensitive.

---

## Authoring contract (what script authors implement)

* **File = one column pack** (canonical key taken from docstring `name:`).
* **Optional:** `setup(context) -> dict`
  Use this to precompute regexes, tables, or even install dependencies / open clients (if runtime allows). Whatever you return will be provided as `state` to detects and transform.
* **Required:** One or more `detect_*` functions
  Must return `{"scores": {...}}`. Use `"self"` to affect your own column score; you may also nudge other columns (e.g., `{"first_name": -1.0}`).
* **Optional:** `transform_cell(...) -> {"cells": {...}}`
  Must return a dict with `"cells"`. Write `"self"` for your own normalized value; provide other column values for the same row as needed (fill-if-empty merge).

### Return shapes (uniform):

* Detect:
  `{"scores": { "self": <float>, "other_column_key": <float>, ... } }`
* Transform:
  `{"cells": { "self": <value>, "other_column_key": <value>, ... } }`

---

## Merge & tie-break (engine responsibilities)

* **Scoreboard:** Per physical column, sum all deltas from all packs’ `detect_*`.
* **Threshold/ties:** Pick the max score ≥ threshold; if tied, use stable precedence (e.g., header match > most deltas > lexical key order).
* **Transform merge:** After mapping, call all needed `transform_cell` functions; apply `"self"` to the mapped column, apply other keys to the same row with **fill-if-empty**.

---

## Security & determinism

* **Network:** Allowed **only** in `setup` (dependencies, client initialization).
* **Detect/transform:** Must be pure, fast, and offline (no I/O, no randomness without seed).
* **Isolation:** Run packs in a controlled sandbox if possible.

---

## Future-proofing (not required now)

* Per-rule parameters via `context["params"]`.
* Transform strategies (e.g., override vs fill-if-empty).
* Explanations/confidence for UI (“why this column won”).
* Pack versioning/compat checks in `version:`.

---

## Acceptance criteria

* App loads the template pack, runs both `detect_*`, merges “scores”, maps the column, and applies `transform_cell` as described.
* `"self"` shorthand is correctly resolved to the pack’s canonical key.
* Upserts to other columns are applied **only if empty**.
* Debug logs show which detects fired (and their deltas) without leaking sensitive cell content.

---

## Reference implementation template (verbatim)

> Copy this into a new pack file and edit the docstring and code to suit your column.

```python
"""
name: full_name
description: Detect a “Full Name” column; transform can optionally split into first/last.
version: 1
"""

# -----------------------------------------------------------------------------
# HOW THIS PACK IS USED
# • ADE imports this file.
# • OPTIONAL setup(context) runs ONCE; its return is passed to every detect_* / transform_cell as `state`.
# • ADE calls EVERY top-level function whose name starts with `detect_`.
#   Each detect_* MUST return:
#     {
#       "scores": {
#         "self": <float>,            # boosts THIS pack’s score
#         # You can also nudge OTHER columns (optional):
#         # "first_name": -1.0, "last_name": -1.0
#       }
#     }
# • After columns are mapped, ADE calls transform_cell(...) per cell (if present).
#   transform_cell MUST return:
#     {
#       "cells": {
#         "self": <normalized value>,   # written to THIS column
#         # Optional: write to OTHER columns in the SAME row (fill-if-empty):
#         # "first_name": "<value>", "last_name": "<value>"
#       }
#     }
# • Special key "self" refers to THIS pack’s canonical column key (the `name:` above).
# • setup() can also install dependencies or open client connections if your runtime allows it.
# -----------------------------------------------------------------------------

import re

# OPTIONAL — runs ONCE; keep it simple. Whatever you return here is available as `state`.
def setup(*, context):
    return {
        "common_first_names": {"john", "jane", "michael", "sarah", "david"},
        "last_comma_first_pat": re.compile(r"^\s*(?P<last>[^,]+),\s*(?P<first>[^,]+)\s*$"),
    }

# --------------------------- DETECT FUNCTIONS ---------------------------------
# Keep them tiny and obvious. Names MUST start with `detect_`.
# Each returns: {"scores": {...}}

def detect_common_first_names(
    *, header=None, values=None, table=None, column_index=None,
    sheet_name=None, bounds=None, state=None, context=None, **_
):
    """Boost if any value begins with a common first name (very simple heuristic)."""
    names = (state or {}).get("common_first_names", set())
    vals  = [str(v).strip() for v in (values or []) if str(v).strip()]
    hit   = any((v.split(",", 1)[1].strip().split()[0] if "," in v else v.split()[0]).lower() in names
                for v in vals if v)
    return {
        "scores": { **({"self": 1.0} if hit else {}) }
    }

def detect_last_comma_first_pattern(
    *, header=None, values=None, table=None, column_index=None,
    sheet_name=None, bounds=None, state=None, context=None, **_
):
    """Boost if any value matches 'Last, First'; also gently reduce first_name/last_name to avoid confusion."""
    pat  = (state or {}).get("last_comma_first_pat") or re.compile(r"^\s*[^,]+,\s*[^,]+\s*$")
    vals = [str(v).strip() for v in (values or []) if str(v).strip()]
    hit  = any(pat.match(v) for v in vals)
    return {
        "scores": {
            **({"self": 1.0} if hit else {}),
            **({"first_name": -1.0, "last_name": -1.0} if hit else {}),
        }  # +1 to self, -1 to first_name and last_name to reduce false positives when we see “Last, First”.
    }

# ------------------------------ TRANSFORM CELL --------------------------------
# Always return the same simple structure: {"cells": {...}}.

def transform_cell(
    *, value=None, row_index=None, column_index=None, table=None,
    context=None, state=None, **_
):
    """
    Normalize to 'First Last' when possible, and suggest first_name/last_name for the same row.
    Keep this readable and minimal.
    """
    s   = ("" if value is None else str(value)).strip()
    pat = (state or {}).get("last_comma_first_pat") or re.compile(r"^\s*(?P<last>[^,]+),\s*(?P<first>[^,]+)\s*$")

    # Derive first/last in the simplest possible way:
    m = pat.match(s)
    first = (m.group("first").strip().title() if m else (s.split()[0].title()  if len(s.split()) == 2 else None))
    last  = (m.group("last").strip().title()  if m else (s.split()[1].title()  if len(s.split()) == 2 else None))

    return {
        "cells": {
            # For THIS column ("self"), prefer normalized "First Last" if we derived both parts:
            "self": (f"{first} {last}" if (first and last) else s),
            # If we extracted parts, also emit first_name / last_name for the SAME row (fill-if-empty):
            **({"first_name": first, "last_name": last} if (first and last) else {}),
        }
    }
```

---

## Next steps

* Adopt this work package as the **authoring guide** for Column Packs.
* Implement the loader/runner in ADE (discovery, merge, tie-break, transform merge).
* Create a simple “pack tester” CLI to execute `setup`, all `detect_*`, and `transform_cell` against a small sample table for quick iteration in the GUI.
* When needed, add a section to the pack authoring docs for recommended score scales and tie-break rules.
