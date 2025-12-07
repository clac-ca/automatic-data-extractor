"""Column registry for manifest-driven field modules."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType
from typing import Callable

from ade_engine.config.validators import require_keyword_only
from ade_engine.core.errors import ConfigError
from ade_engine.schemas.manifest import FieldConfig


DetectorFn = Callable[..., float]
TransformerFn = Callable[..., object]
ValidatorFn = Callable[..., object]


@dataclass
class ColumnModule:
    """Resolved column module and its callables."""

    field: str
    definition: FieldConfig
    module: ModuleType
    detectors: list[DetectorFn]
    transformer: TransformerFn | None
    validator: ValidatorFn | None


class ColumnRegistry(dict[str, ColumnModule]):
    """Mapping of canonical field name to :class:`ColumnModule`."""

    @classmethod
    def from_manifest(cls, *, package: ModuleType, fields: dict[str, FieldConfig]) -> "ColumnRegistry":
        registry = cls()
        for field, definition in fields.items():
            module_path = f"{package.__name__}.{definition.module}"
            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError as exc:  # pragma: no cover - exercised via ConfigError
                raise ConfigError(f"Column module '{module_path}' not found") from exc

            detectors: list[DetectorFn] = []
            for name in sorted(dir(module)):
                attr = getattr(module, name)
                if not callable(attr):
                    continue
                if name.startswith("detect_"):
                    require_keyword_only(attr, label=f"Detector '{module_path}.{name}'")
                    detectors.append(attr)

            transformer = getattr(module, "transform", None)
            if transformer is not None:
                if not callable(transformer):
                    raise ConfigError(f"Transformer '{module_path}.transform' is not callable")
                require_keyword_only(transformer, label=f"Transformer '{module_path}.transform'")

            validator = getattr(module, "validate", None)
            if validator is not None:
                if not callable(validator):
                    raise ConfigError(f"Validator '{module_path}.validate' is not callable")
                require_keyword_only(validator, label=f"Validator '{module_path}.validate'")

            registry[field] = ColumnModule(
                field=field,
                definition=definition,
                module=module,
                detectors=detectors,
                transformer=transformer,
                validator=validator,
            )

        return registry
