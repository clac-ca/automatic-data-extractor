# Troubleshooting

Common problems, symptoms, and fixes.

---

## “Config package could not be imported”
**Symptom:** `ConfigError: Config package '...' could not be imported`

**Causes:**
- `--config-package` points to a module name that is not importable.
- The filesystem path does not contain `ade_config/manifest.toml` or `src/ade_config/manifest.toml`.

**Fix:**
- Verify the path layout matches the expected structure.
- For module names, confirm the package is installed or on `PYTHONPATH`.

---

## “manifest.toml is now required”
**Symptom:** `manifest.json found; manifest.toml is now required`

**Fix:**
- Convert your manifest to TOML and name it `manifest.toml`.

---

## “script_api_version must be 3”
**Symptom:** `this ade_engine build requires script_api_version=3`

**Fix:**
- Update `script_api_version` in your manifest.

---

## Row detector returned wrong shape
**Symptom:** errors like:
- “must return a float or dict of label deltas”
- “returned a non-numeric score”
- “returned a bare score but no default label could be inferred”

**Fix:**
- Return `{"header": 0.7}` / `{"data": 0.4}` when ambiguous.
- If returning a float, set a default label via:
  - `__row_label__`, `row_label`, or `default_label`,
  - or place the detector in a module ending with `.header` or `.data`.

---

## Column detector returned non-numeric scores
**Symptom:** `Detector returned a non-numeric score`

**Fix:**
- Ensure detector returns `float` or `dict[str, float]`.
- If you return a dict, values must be numeric.

---

## Mapping patch errors
**Symptoms:**
- “Patch assigns unknown field(s)”
- “Patch assigns column index out of bounds”
- “Patch maps multiple fields to column …”
- “Patch cannot drop/rename non-passthrough columns”

**Fix:**
- Use 0-based column indexes when patching.
- Only drop/rename passthrough columns.

---

## NDJSON output is “corrupted”
**Symptom:** NDJSON consumer fails to parse output.

**Cause:** non-JSON text is printed to stdout (e.g. stray `print()` in config scripts).

**Fix:**
- Run the CLI in NDJSON mode; it redirects non-event stdout to stderr.
- Prefer `logger.event(...)` over `print()`.

---

## Output workbook is empty / missing sheets
**Causes:**
- Source workbook has no visible sheets (or `--input-sheet` filters them out).
- No table regions were detected (row detectors too strict).

**Fix:**
- Verify sheet visibility and names.
- Adjust row detectors or thresholds.

---

## Debugging tips

- Use `--log-format text` for readable progress while iterating.
- Use `--log-format ndjson --logs-dir ./logs` to capture an exact event stream for replay.
- Add temporary config events around tricky logic:
  `logger.event("debug.marker", ...)`
