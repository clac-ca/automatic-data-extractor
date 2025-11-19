"""Load and validate manifest-declared column modules."""

from __future__ import annotations

import inspect
from importlib import import_module
from typing import Any, Iterable, Mapping

from ade_schemas.manifest import ColumnMeta

from .models import ColumnModule


class ColumnRegistryError(RuntimeError):
    """Raised when column modules cannot be loaded or validated."""


class ColumnRegistry:
    """Load column modules defined in the manifest and validate signatures."""

    _DETECTOR_REQUIRED: tuple[str, ...] = ("field_name",)
    _DETECTOR_ALLOWED: tuple[str, ...] = (
        "job",
        "state",
        "field_name",
        "field_meta",
        "header",
        "column_values_sample",
        "column_values",
        "table",
        "column_index",
        "logger",
    )
    _TRANSFORM_REQUIRED: tuple[str, ...] = ("field_name", "value", "row")
    _TRANSFORM_ALLOWED: tuple[str, ...] = (
        "job",
        "state",
        "row_index",
        "field_name",
        "value",
        "row",
        "field_meta",
        "logger",
    )
    _VALIDATOR_REQUIRED: tuple[str, ...] = ("field_name", "value", "row_index")
    _VALIDATOR_ALLOWED: tuple[str, ...] = (
        "job",
        "state",
        "row_index",
        "field_name",
        "value",
        "row",
        "field_meta",
        "logger",
    )

    def __init__(self, meta: Mapping[str, ColumnMeta], *, package: str) -> None:
        self._modules: dict[str, ColumnModule] = {}
        for field, definition in meta.items():
            if not definition.enabled:
                continue
            script = definition.script
            if not script:
                continue
            module_name = _script_to_module(script, package=package)
            try:
                module = import_module(module_name)
            except ModuleNotFoundError as exc:  # pragma: no cover - import guard
                raise ColumnRegistryError(
                    f"Column module '{module_name}' could not be imported"
                ) from exc

            detectors = tuple(
                getattr(module, attr)
                for attr in dir(module)
                if attr.startswith("detect_") and callable(getattr(module, attr))
            )
            for detector in detectors:
                self._validate_callable(
                    detector,
                    required=self._DETECTOR_REQUIRED,
                    allowed=self._DETECTOR_ALLOWED,
                    kind="detector",
                    field=field,
                )

            transformer = getattr(module, "transform", None)
            if transformer is not None:
                if not callable(transformer):
                    raise ColumnRegistryError(
                        f"Transform callable for field '{field}' must be callable"
                    )
                self._validate_callable(
                    transformer,
                    required=self._TRANSFORM_REQUIRED,
                    allowed=self._TRANSFORM_ALLOWED,
                    kind="transformer",
                    field=field,
                )
            validator = getattr(module, "validate", None)
            if validator is not None:
                if not callable(validator):
                    raise ColumnRegistryError(
                        f"Validator callable for field '{field}' must be callable"
                    )
                self._validate_callable(
                    validator,
                    required=self._VALIDATOR_REQUIRED,
                    allowed=self._VALIDATOR_ALLOWED,
                    kind="validator",
                    field=field,
                )

            meta_payload: Mapping[str, Any] = definition.model_dump()
            self._modules[field] = ColumnModule(
                field=field,
                meta=meta_payload,
                definition=definition,
                module=module,
                detectors=detectors,
                transformer=transformer,
                validator=validator,
            )

    def modules(self) -> Mapping[str, ColumnModule]:
        """Return loaded modules keyed by field name."""

        return self._modules

    def get(self, field: str) -> ColumnModule | None:
        """Return the module for ``field`` if registered."""

        return self._modules.get(field)

    @classmethod
    def _validate_callable(
        cls,
        func,
        *,
        required: Iterable[str],
        allowed: Iterable[str],
        kind: str,
        field: str,
    ) -> None:
        signature = inspect.signature(func)
        parameters = signature.parameters
        has_kwargs = any(
            param.kind is inspect.Parameter.VAR_KEYWORD
            for param in parameters.values()
        )
        missing = [
            name
            for name in required
            if name not in parameters and not has_kwargs
        ]
        if missing:
            raise ColumnRegistryError(
                f"{kind.title()} for field '{field}' must accept parameters: {', '.join(required)}"
            )

        for name, param in parameters.items():
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.VAR_POSITIONAL,
            ):
                continue
            if name in allowed:
                continue
            if param.default is inspect._empty and not has_kwargs:
                raise ColumnRegistryError(
                    f"{kind.title()} for field '{field}' has unsupported parameter '{name}'"
                )


def _script_to_module(script: str, *, package: str) -> str:
    module = script[:-3] if script.endswith(".py") else script
    module = module.replace("/", ".").replace("-", "_")
    return f"{package}.{module}" if not module.startswith(package) else module


__all__ = ["ColumnRegistry", "ColumnRegistryError"]
