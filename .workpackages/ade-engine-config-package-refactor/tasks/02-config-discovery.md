# Task 02 – Config discovery (auto-import)

Checklist: B) Add **Config discovery** (import all modules under config package to auto-register detectors/transforms/validators/hooks).

Objective: Implement a single discovery path that imports every Python module under the configured package (e.g., `ade_config`) so decorator side effects populate the active Registry.

Implementation steps:
- [ ] Add `registry/discovery.py` with `import_all(package_name: str)` using `importlib.import_module` then `pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + '.')` to import submodules; skip if package has no `__path__` (single module).
- [ ] Ensure discovery is called after `set_current_registry(registry)` and before `registry.finalize()`.
- [ ] Add minimal logging/metrics (count modules imported) and surface import errors clearly (bubble or wrap).
- [ ] Guarantee deterministic behavior by sorting walk results (`sorted(pkgutil.walk_packages(...), key=lambda m: m.name)`).

Code sketch:
```py
# registry/discovery.py
def import_all(package: str) -> None:
    pkg = importlib.import_module(package)
    if not hasattr(pkg, "__path__"):
        return
    mods = sorted(pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."), key=lambda m: m.name)
    for mod in mods:
        importlib.import_module(mod.name)
```

Definition of done:
- [ ] Discovery imports all modules under a sample package (see `config_package_example`), registers items once, and is deterministic across runs.
- [ ] Called from engine startup and covered by unit tests (see Task 26).

References: `docs/pipeline-and-registry.md`, `docs/registry-spec.md`, `config_package_example/src/ade_config` structure.
