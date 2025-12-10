# Task 01 – Registry core (models, decorators, ordering)

Checklist: B) Add **Registry** core (models + decorators + ordering rules).

Objective: Stand up `apps/ade-engine/src/ade_engine/registry/` with FieldDef, HookName, RegisteredFn, context objects, decorator helpers, deterministic sort/finalize, and score-patch normalization so config packages can register capabilities without manifest wiring.

Implementation steps:
- [ ] Create `registry/models.py` with `FieldDef`, `HookName` enum, contexts (RowDetectorContext, ColumnDetectorContext, TransformContext, ValidateContext, HookContext) and `ScorePatch = float | dict[str, float]` (see `docs/registry-spec.md`).
- [ ] Add `registry/registry.py` holding `RegisteredFn` dataclass, bucket lists (row_detectors, column_detectors, column_transforms, column_validators, hooks: dict[HookName, list]), `_sort_key` = `(-priority, module, qualname)`, `finalize()` to sort buckets, `register_field()` duplicate guard, `normalize_patch(current, patch)` casting to float and dropping NaN/unknown keys.
- [ ] Add `registry/current.py` using `contextvars` to set/get the active Registry; raise `RegistryNotActiveError` if decorators called without a registry.
- [ ] Add `registry/decorators.py` exposing `field_meta/define_field`, `row_detector`, `column_detector`, `column_transform`, `column_validator`, `hook` that read the active registry and append RegisteredFn entries with module/qualname metadata.

Code sketch:
```py
# registry/registry.py
class Registry:
    def _sort_key(self, r: RegisteredFn):
        return (-r.priority, r.module, r.qualname)

    def finalize(self):
        self.row_detectors.sort(key=self._sort_key)
        ...
        for hook in self.hooks:
            self.hooks[hook].sort(key=self._sort_key)

    def normalize_patch(self, current: str, patch: ScorePatch) -> dict[str, float]:
        if isinstance(patch, (int, float)):
            return {current: float(patch)}
        return {k: float(v) for k, v in patch.items() if math.isfinite(float(v))}
```

Definition of done:
- [ ] Registry package exists and is importable; decorators register into the active Registry with deterministic ordering; duplicate fields raise; normalize_patch handles float/dict/no-op cases.
- [ ] Docs in `docs/registry-spec.md` align with implemented API.

References: `docs/summary.md`, `docs/architecture.md`, `docs/registry-spec.md`, config examples under `config_package_example/src/ade_config/`.
