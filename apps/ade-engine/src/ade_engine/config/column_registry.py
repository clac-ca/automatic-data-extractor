"""Column registry for manifest-driven field modules."""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from types import ModuleType
from typing import Callable

from ade_engine.core.errors import ConfigError
from ade_engine.schemas.manifest import FieldConfig


DetectorFn = Callable[..., float]
TransformerFn = Callable[..., object]
ValidatorFn = Callable[..., object]


def _validate_keyword_only(func: Callable[..., object], *, label: str) -> None:
    """Ensure a callable uses keyword-only parameters and allows future kwargs."""

    signature = inspect.signature(func)
    invalid_params = [
        p
        for p in signature.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY)
    ]
    if invalid_params:
        names = ", ".join(p.name for p in invalid_params)
        raise ConfigError(f"{label} must declare keyword-only parameters (invalid: {names})")

    if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()):
        raise ConfigError(f"{label} must accept **_ for forwards compatibility")

    missing = [name for name in ("logger", "event_emitter") if name not in signature.parameters]
    if missing:
        raise ConfigError(
            f"{label} must accept logger and event_emitter keyword arguments (missing: {', '.join(missing)})"
        )


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
            for name, attr in inspect.getmembers(module, predicate=callable):
                if name.startswith("detect_"):
                    _validate_keyword_only(attr, label=f"Detector '{module_path}.{name}'")
                    detectors.append(attr)

            transformer = getattr(module, "transform", None)
            if transformer is not None:
                if not callable(transformer):
                    raise ConfigError(f"Transformer '{module_path}.transform' is not callable")
                _validate_keyword_only(transformer, label=f"Transformer '{module_path}.transform'")

            validator = getattr(module, "validate", None)
            if validator is not None:
                if not callable(validator):
                    raise ConfigError(f"Validator '{module_path}.validate' is not callable")
                _validate_keyword_only(validator, label=f"Validator '{module_path}.validate'")

            registry[field] = ColumnModule(
                field=field,
                definition=definition,
                module=module,
                detectors=detectors,
                transformer=transformer,
                validator=validator,
            )

        return registry
