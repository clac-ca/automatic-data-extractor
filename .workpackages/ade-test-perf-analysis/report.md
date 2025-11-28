# ADE test perf analysis

## Commands observed
- `source .venv/bin/activate && ade test` — timed out at 120s (partial backend run shown).
- `source .venv/bin/activate && cd apps/ade-api && pytest --durations=20` — completed in ~189.7s for 211 tests, surfaced slowest timings + failures.

## Findings (third-pass critical deep dive)
### Streaming runs (E2E) — primary bottleneck
- Four tests in `apps/ade-api/tests/integration/runs/test_runs_router.py` consume ~114s of the ~189s backend runtime:  
  - `test_stream_run_honors_input_sheet_override` — 31.98s  
  - `test_stream_run_processes_real_documents` — 30.24s  
  - `test_stream_run_limits_to_requested_sheet_list` — 28.25s  
  - `test_stream_run_processes_all_worksheets_when_unspecified` — 23.48s
- Shared setup pattern: each test calls `_seed_real_configuration` (lines ~300–360) which **creates a fresh venv per call**, then:
  - `python -m venv <workspace>/venvs/<config>/<build>` (unique `build_id` per test, so no reuse).
  - `pip install apps/ade-engine` → builds a wheel from source every time.
  - Copies default config template into workspace, then `pip install <config_src>` → builds config wheel every time.
  - Writes marker/build rows and sets config.active_build_* metadata.
- Logs confirm repeated `Building wheel for ade-engine` and `ade-config` on every streaming test. Even with `ADE_PIP_CACHE_DIR`, local source installs cause pip to rebuild wheels for each new venv.
- The actual engine run over CSV/XLSX input is comparatively cheap; the dominant cost is environment construction + two pip installs per test.
- Coverage overlap: all four are end-to-end streaming checks; three differ only in sheet-selection options (none / single name / list). They duplicate the same heavy setup and pipeline.
- Cost decomposition per test (approx, inferred from 23–32s durations): venv creation + two wheel builds/installations likely >20s; engine execution + assertions likely <5s. Eliminating repeated builds is the largest lever.

### User list test (secondary)
- `tests/integration/users/test_users_router.py::test_list_users_admin_success` took 5.48s.
- Likely contributors:
  - Uses per-test `seed_identity` fixture (function scope) which hashes six passwords with scrypt (N=2^14) every time; scrypt dominates CPU and can add multiple seconds.
  - Test loops through paginated `/api/v1/users` calls, but with `page_size=100` it should be a single page; the HTTP loop itself should be cheap.
- Not a large share of total time, but scrypt-heavy seeding repeats across many tests, so dialing it down yields broad small wins.

### Suite health
- The timings are from a failing run (6 failures: 4 streaming 409s, 2 AttributeErrors). Fixing failures may shift timings slightly, but the per-test venv + pip rebuilds remain the top cost.

## Why it’s slow
- `_seed_real_configuration` tears down any existing venv path, creates a new one, and performs two local pip installs per call. Each streaming test triggers a full engine build + config wheel build, incurring 20–30s of I/O and packaging work.
- The streaming tests do not share the built engine/config runtime or reuse a cached wheel, so cost scales linearly with test count.
- `seed_identity` hashes passwords with scrypt for six users on every test (function scope). That adds seconds to identity-heavy tests.

## Recommendations / next steps
- **Reuse the runtime once:** Add a module- or session-scoped fixture that builds the engine/config venv once; streaming tests reuse it while still creating fresh documents/runs. If per-test isolation is required, reuse the same venv path without rmtree when fingerprints match.
- **Install from cached wheels:** Build `ade_engine` and the default config into wheels once (temp dir) and `pip install <wheel>` inside workspace venvs to avoid repeated source builds. Even with separate venvs, wheel install should drop per-test setup from ~20–30s to a few seconds.
- **Reduce E2E count / mark slow:** Keep a single full streaming E2E (“processes real documents”) that proves real engine execution + artifact/log persistence. Move sheet-selection variants to faster coverage (service/unit tests asserting options mapping) or parameterize a single streaming test that shares the built runtime. If keeping all four, mark the three variants `@pytest.mark.slow`.
- **Consider stubbing the engine:** For API behaviors (sheet overrides, run metadata), use a fake engine runner that emits events quickly without venv creation. Reserve one true engine E2E for CI/nightly.
- **Tame password hashing in tests:** Allow lower-cost hashing when `ADE_TEST_FAST_HASH=1` (or similar), or use precomputed hashes and/or a session-scoped identity seed with reset between tests. This trims the 5s-level overhead for identity-heavy tests.
- **Fix current failures:** Resolve streaming 409s and unit AttributeErrors to stabilize measurements and ensure we’re not paying extra work from error paths.

## Do we need all four streaming tests as written?
- They all exercise the same run pipeline; differences are only input-sheet options. Maintaining four full E2E runs is likely unnecessary given the 20–30s setup cost each.
- Suggested split:
  - Keep one “happy path” streaming E2E validating real engine execution, artifact persistence, and logs.
  - Convert sheet-selection behaviors to lighter tests (unit/service with stubbed runner) or parameterize within a single streaming test that shares the built runtime.

## Candidate rewrites to make them faster
- Shared `_real_config` fixture (module/session scope) to build config/venv once; streaming tests consume it without rebuilding. Optionally pin a single `build_id` and skip `shutil.rmtree` if the marker matches.
- Prebuild wheels (`pip wheel apps/ade-engine`, `pip wheel <config_template>`) and install wheels instead of source on every test; stash wheels under `tmp_path_factory`/`ADE_PIP_CACHE_DIR`.
- Introduce a fast runner stub for option coverage; mark the single real engine E2E as `slow` for default skips.
- Lower scrypt params under a test flag or use pre-hashed credentials so identity seeding is cheap; consider session-scoping `seed_identity` if test isolation allows.
