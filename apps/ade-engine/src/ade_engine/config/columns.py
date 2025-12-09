"""Column registry for manifest-driven field modules."""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from types import ModuleType
from typing import Callable, cast

from ade_engine.config.validators import require_keyword_only
from ade_engine.exceptions import ConfigError
from ade_engine.schemas.manifest import FieldConfig

DetectorFn = Callable[..., float]
TransformerFn = Callable[..., object]
ValidatorFn = Callable[..., object]


@dataclass(frozen=True)
class ColumnModule:
    """Resolved column module and its callables."""

    field: str
    definition: FieldConfig
    module: ModuleType
    detectors: tuple[DetectorFn, ...]
    transformer: TransformerFn | None
    validator: ValidatorFn | None


def _load_module(module_path: str) -> ModuleType:
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise ConfigError(f"Column module '{module_path}' not found") from exc


def _discover_detectors(module: ModuleType, *, module_path: str) -> tuple[DetectorFn, ...]:
    detectors: list[DetectorFn] = []
    for name, attr in inspect.getmembers(module, callable):
        if name.startswith("detect_"):
            require_keyword_only(attr, label=f"Detector '{module_path}.{name}'")
            detectors.append(cast(DetectorFn, attr))
    detectors.sort(key=lambda fn: fn.__name__)
    return tuple(detectors)


def _optional_callable(module: ModuleType, name: str, *, module_path: str, kind: str) -> Callable[..., object] | None:
    attr = getattr(module, name, None)
    if attr is None:
        return None
    if not callable(attr):
        raise ConfigError(f"{kind} '{module_path}.{name}' is not callable")
    require_keyword_only(attr, label=f"{kind} '{module_path}.{name}'")
    return attr


class ColumnRegistry(dict[str, ColumnModule]):
    """Mapping of canonical field name to :class:`~ade_engine.config.columns.ColumnModule`."""

    @classmethod
    def from_manifest(cls, *, package: ModuleType, fields: list[FieldConfig]) -> "ColumnRegistry":
        registry = cls()

        for definition in fields:
            field = definition.name
            module_name = definition.module or f"column_detectors.{field}"
            module_path = f"{package.__name__}.{module_name}"

            module = _load_module(module_path)
            detectors = _discover_detectors(module, module_path=module_path)

            registry[field] = ColumnModule(
                field=field,
                definition=definition,
                module=module,
                detectors=detectors,
                transformer=_optional_callable(module, "transform", module_path=module_path, kind="Transformer"),
                validator=_optional_callable(module, "validate", module_path=module_path, kind="Validator"),
            )

        return registry
