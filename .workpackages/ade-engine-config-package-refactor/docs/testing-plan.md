# docs/ade-engine/testing-plan.md
# ADE Engine — Testing Plan (Registry + Discovery + Pipeline)

This doc defines the test strategy for the ADE Engine refactor:
- **Registry-based config packages** (decorators register fields/detectors/transforms/validators/hooks)
- **Discovery by importing modules**
- **Pipeline rewired** to pull behavior from the registry
- **Output ordering simplified** (mapped columns preserve input order; unmapped appended if enabled)
- **Engine settings** via `pydantic-settings` (`.env` / env vars / optional TOML)

No backwards compatibility is required, so tests should validate **only the new behavior**.

---

## 1. Goals

### Must guarantee
1. **Deterministic behavior**
   - Registry iteration order is stable across machines/runs.
   - Mapping and output ordering are stable when scores tie.

2. **Correct scoring semantics**
   - Detectors can return either `float` or `{field: delta}` patches.
   - Multi-field patches correctly adjust multiple candidates.

3. **Correct pipeline integration**
   - Row detection selects header rows as expected.
   - Column detection → mapping chooses the right field per input column.
   - Transforms run on mapped columns.
   - Validators run and report issues (do not delete data).
   - Hooks run at the right times and can patch mapping/reorder output.

4. **Settings precedence**
   - Defaults work with no config.
   - `.env` / env vars / TOML override correctly and safely.

### Nice to have
- “Fuzz” tests for score patch normalization and tie breakers.
- A golden-file style integration test for output workbook structure.

---

## 2. Test Layers

### 2.1 Unit tests (fast, pure Python)
Focus: registry, decorators, normalization, ordering, settings.

- Registry ordering rules
- Score patch normalization
- Duplicate registration errors
- Discovery import recursion
- Settings precedence and parsing

### 2.2 Component tests (small pipeline slices)
Focus: row detection step, column detection/mapping step, transform step, hook step.

Use minimal table objects (or small synthetic workbook objects) to avoid full IO.

### 2.3 Integration tests (end-to-end)
Focus: run the whole pipeline on a small workbook fixture and a test config package fixture.

Assert:
- detected header row and table bounds (if applicable)
- mapping results
- transformed values
- validation results reported
- output workbook columns/order
- hook effects (reorder / patch mapping)

---

## 3. Test Structure (repo layout)

Recommended test tree under `apps/ade-engine/tests/`:

```text
tests/
  unit/
    test_registry_ordering.py
    test_score_patch_normalization.py
    test_decorators_registration.py
    test_discovery_imports.py
    test_settings_precedence.py
  component/
    test_row_detection.py
    test_column_detection_mapping.py
    test_transforms.py
    test_validators_reporting.py
    test_hooks_execution.py
    test_output_ordering.py
  integration/
    fixtures/
      workbooks/
        simple_people.xlsx
        remittances_min.xlsx
      config_packages/
        ade_config_min/
          pyproject.toml (optional; can be a plain package)
          ade_config_min/
            __init__.py
            rows.py
            columns_email.py
            hooks.py
    test_end_to_end_minimal.py
    test_end_to_end_hooks_reorder.py
````

Notes:

* Integration fixtures should be **tiny** (5–30 rows).
* Prefer “plain package” fixtures (no build step) by adding to `sys.path` in tests.

---

## 4. Unit Tests — What to test

### 4.1 Registry ordering rules

**Why:** Determinism is critical when multiple detectors exist.

**Test cases:**

* Two detectors with different priority → higher priority runs first.
* Same priority, different module path/qualname → stable ordering by `(priority desc, module_path asc, qualname asc)`.
* Hook ordering uses same rules.
* “Registration order” does *not* change results (ordering must not rely on import side effects alone).

**Assertions:**

* `registry.row_detectors(HookName/Kind)` returns in expected order.
* Ordering is stable across multiple calls.

---

### 4.2 Score patch normalization

**Why:** detectors can return `float` or `dict[str, float]`.

Define a single normalization function (example name):

* `normalize_score_patch(current_field: str, patch: ScorePatch) -> dict[str, float]`

**Test cases:**

* `patch = 0.8` → returns `{current_field: 0.8}`
* `patch = {"email": 1.0, "first_name": -0.2}` → returned unchanged
* `patch = None` (if allowed) → `{}` (or error; pick one and test it)
* invalid types → raises a clear exception (TypeError / ValueError)

---

### 4.3 Decorator registration

**Why:** decorators are the main public API.

**Test cases:**

* `@field(...)` registers a `FieldDef`
* `@row_detector(...)` registers row detector def
* `@column_detector(field="email")` registers detector bound to field (or global if allowed)
* `@column_transform(field="email")` attaches transform to field
* `@column_validator(field="email")` attaches validator to field
* `@hook(HookName.ON_TABLE_MAPPED)` registers hook to that hook name

**Edge cases:**

* Duplicate field name registration → error
* Detector referencing unknown field → warn or ignore (choose policy and test it)
* Multiple transforms for same field → allowed and ordered OR disallowed (choose and test)

---

### 4.4 Discovery imports

**Why:** “drop in a file and it works” depends on discovery.

If discovery is `import_all(package_name_or_path)`, test:

* Imports modules recursively under a package
* Imports do not crash on non-python files
* Repeat imports don’t double-register (idempotency policy):

  * Recommended: registry is created fresh per run; discovery imports modules once in-process.
  * If re-imports happen, ensure registry prevents duplicates or tests reset interpreter/module cache.

**Assertions:**

* After discovery, registry contains expected items.

---

### 4.5 Settings precedence

**Why:** engine behavior must be stable and overrideable.

Assuming `Settings` uses `pydantic-settings`, test:

* Defaults when nothing is set
* `.env` overrides default
* environment variables override `.env`
* TOML overrides default (and precedence vs `.env` is as designed)
* Invalid values fail with clear message (e.g. `unmapped_prefix` must be string)

**Tip:** Use `monkeypatch` to set env vars and temporary files for `.env`/TOML.

---

## 5. Component Tests — What to test

### 5.1 Row detection scoring

Create a minimal synthetic sheet representation (or use a small in-memory workbook).

* Provide a header-like row and a data-like row.
* Register two row detectors:

  * header detector boosts `"header"` label
  * data detector boosts `"data"` label
* Ensure pipeline selects correct header row index.

**Assertions:**

* computed row classification
* chosen header row index
* tie-break behavior is deterministic

---

### 5.2 Column detection + mapping

Set up:

* two input columns: `"Email Address"`, `"First Name"`
* column detectors that return score patches based on header tokens + sample values

**Assertions:**

* mapping chooses `email` for first column and `first_name` for second
* multi-field penalty logic works (e.g. email detector penalizes `work_email`)
* tie-breakers work (priority then stable ordering)

---

### 5.3 Transforms

Register a transform for `email` that normalizes case/whitespace.

**Assertions:**

* transform is applied only to mapped `email` column
* unmapped columns not transformed
* transforms apply in defined order if multiple exist

---

### 5.4 Validators (reporting only)

Register validator for `email` that flags invalid addresses.

**Assertions:**

* invalid values produce validation issues with `passed=False` and message
* data is preserved (no deletion/nulling)
* reporting structure is stable and testable (dicts with `passed`, optional `message/row_index/column_index/value`)

---

### 5.5 Hooks execution

Test hook points in isolation with minimal table/workbook objects.

* `ON_TABLE_MAPPED` hook can patch mapping (e.g. force a column to `member_id`)
* `ON_TABLE_MAPPED` hook can reorder output columns
* `ON_WORKBOOK_BEFORE_SAVE` hook can modify workbook metadata

**Assertions:**

* hook called exactly once per stage
* multiple hooks run in deterministic order
* exceptions policy: fail fast vs record issue (choose and test)

---

### 5.6 Output ordering (new rule)

Given mapping results and original input column indices:

**Expected behavior**

* output mapped columns appear in original input order
* unmapped columns appended (if enabled)
* prefixed unmapped column names use `unmapped_prefix`

**Assertions:**

* column order in output sheet matches rule
* disabling `append_unmapped_columns` drops unmapped columns from output
* mapping tie-resolution respects `mapping_tie_resolution` (`leftmost` winner vs `drop_all`)

---

## 6. Integration Tests — End-to-end scenarios

### 6.1 Minimal config package + simple workbook

Fixture workbook:

* header row with “Email Address”, “First Name”, plus an unknown “Foo”
* a few data rows

Fixture config package:

* defines fields: `email`, `first_name`
* row detectors: header/data
* column detectors: for email and first_name
* transform: trim + lower email
* validator: basic email check

**Assertions:**

* pipeline completes with no exceptions
* mapping: email + first_name mapped correctly
* output:

  * email and first_name columns appear in input order
  * “Foo” appended as `raw_foo` when `append_unmapped_columns=True`
* validator results contain expected failures
* transform applied

---

### 6.2 Hook-driven reorder

Same as above but add `ON_TABLE_MAPPED` hook:

* reorder columns to `[first_name, email]` regardless of input order
* or move all “raw_” columns to far right

**Assertions:**

* output columns reflect the hook’s reorder
* no other semantics regress

---

### 6.3 Mapping patch hook (LLM-style without LLM)

Simulate an “LLM mapping patch” by writing hook logic that:

* inspects unmapped headers
* assigns mapping for one extra field

**Assertions:**

* hook patch changes mapping outcome
* later stages respect patched mapping (transform/validator/render)

---

## 7. Fixtures Strategy

### Workbooks

* Keep fixtures small and human-inspectable.
* Prefer `.xlsx` files if the engine already depends on Excel IO (openpyxl, etc.).
* Name fixtures by scenario: `simple_people.xlsx`, `remittances_min.xlsx`.

### Config packages

* Store a minimal python package under `tests/integration/fixtures/config_packages/`.
* Ensure it’s importable by adding its parent directory to `sys.path` in the test.

Example pattern in tests:

* `sys.path.insert(0, str(config_package_parent_dir))`
* `import ade_config_min` (discovery then imports submodules)

---

## 8. Tooling & Conventions

### Test runner

* `pytest` + `pytest-xdist` optional.
* Use `pytest` fixtures for:

  * temporary dirs
  * env var isolation (`monkeypatch`)
  * creating registry fresh per test

### Determinism controls

* Avoid reliance on filesystem glob order (always sort paths).
* Avoid hash-randomization affecting ordering (don’t depend on dict order unless explicitly stable and created deterministically).
* Tie-breakers must be tested with known priorities/qualnames.

### Coverage targets (rough)

* Unit: ≥ 90% for `ade_engine/registry/*` and `settings.py`
* Component: meaningful coverage for pipeline stage glue
* Integration: at least 2 full scenarios (minimal + hook reorder)

---

## 9. Definition of Done (for tests)

The test suite is considered complete when:

* New registry/discovery/settings behavior is covered by unit tests.
* Each pipeline stage has at least one component test.
* At least two integration tests pass:

  1. default ordering rule (mapped input order + append unmapped)
  2. hook-driven reorder
* CI (or local run) can execute tests in a clean environment with no manual steps.

---

## 10. Practical recommendations (to keep tests cheap)

* Keep “engine run” integration tests small: 1 sheet, 1 table, < 20 rows.
* For pipeline stage tests, prefer “table objects” over real workbooks when possible.
* Fail fast on registration errors; tests should assert clear exceptions early rather than debugging later pipeline failures.
