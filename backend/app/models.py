"""Database models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import ulid
from sqlalchemy import Boolean, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.mutable import MutableDict, MutableList

from .db import Base


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_ulid() -> str:
    return str(ulid.new())

_MISSING: object = object()


class MutableJSONDict(MutableDict):
    """Mutable dictionary that recursively tracks nested JSON changes."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        initial = dict(*args, **kwargs)
        coerced = {key: _coerce_nested(value) for key, value in initial.items()}
        super().__init__(coerced)
        self._parent: MutableJSONDict | MutableJSONList | None = None
        self._sync_child_parent_links()

    @classmethod
    def coerce(cls, key: str, value: Any) -> MutableJSONDict | None:
        """Ensure plain dictionaries are converted to :class:`MutableJSONDict`."""

        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(value)
        return super().coerce(key, value)

    def changed(self) -> None:  # type: ignore[override]
        super().changed()
        parent = getattr(self, "_parent", None)
        if parent is not None:
            parent.changed()

    def _sync_child_parent_links(self) -> None:
        for child in dict.values(self):
            _assign_parent(child, self)

    def _clear_child_parent_links(self) -> None:
        for child in dict.values(self):
            _clear_parent(child)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self:
            _clear_parent(dict.__getitem__(self, key))
        coerced = _coerce_nested(value)
        super().__setitem__(key, coerced)
        _assign_parent(coerced, self)

    def update(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        data: dict[str, Any] = {}
        if args:
            if len(args) > 1:
                msg = "update expected at most 1 positional argument"
                raise TypeError(msg)
            data.update(dict(args[0]))
        if kwargs:
            data.update(kwargs)
        if not data:
            return
        for key, value in data.items():
            self[key] = value

    def setdefault(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        if key in self:
            return dict.__getitem__(self, key)
        self[key] = default
        return dict.__getitem__(self, key)

    def __delitem__(self, key: str) -> None:
        if key in self:
            _clear_parent(dict.__getitem__(self, key))
        super().__delitem__(key)

    def pop(self, key: str, default: Any = _MISSING) -> Any:  # type: ignore[override]
        if key in self:
            value = dict.__getitem__(self, key)
            _clear_parent(value)
            result = dict.pop(self, key)
            self.changed()
            return result
        if default is _MISSING:
            raise KeyError(key)
        return default

    def popitem(self) -> tuple[str, Any]:  # type: ignore[override]
        key, value = dict.popitem(self)
        _clear_parent(value)
        self.changed()
        return key, value

    def clear(self) -> None:  # type: ignore[override]
        self._clear_child_parent_links()
        super().clear()


class MutableJSONList(MutableList):
    """Mutable list that tracks nested JSON changes."""

    def __init__(self, iterable: Iterable[Any] | None = None) -> None:
        items = [] if iterable is None else list(iterable)
        coerced = [_coerce_nested(value) for value in items]
        super().__init__(coerced)
        self._parent: MutableJSONDict | MutableJSONList | None = None
        self._sync_child_parent_links()

    @classmethod
    def coerce(cls, index: str, value: Any) -> MutableJSONList | None:
        if isinstance(value, cls):
            return value
        if isinstance(value, (list, tuple)):
            return cls(value)
        return super().coerce(index, value)

    def changed(self) -> None:  # type: ignore[override]
        super().changed()
        parent = getattr(self, "_parent", None)
        if parent is not None:
            parent.changed()

    def _sync_child_parent_links(self) -> None:
        for child in list(self):
            _assign_parent(child, self)

    def _clear_child_parent_links(self) -> None:
        for child in list(self):
            _clear_parent(child)

    def append(self, value: Any) -> None:  # type: ignore[override]
        coerced = _coerce_nested(value)
        super().append(coerced)
        _assign_parent(coerced, self)

    def extend(self, values: Iterable[Any]) -> None:  # type: ignore[override]
        coerced_values = [_coerce_nested(value) for value in values]
        super().extend(coerced_values)
        for item in coerced_values:
            _assign_parent(item, self)

    def insert(self, index: int, value: Any) -> None:  # type: ignore[override]
        coerced = _coerce_nested(value)
        super().insert(index, coerced)
        _assign_parent(coerced, self)

    def __setitem__(self, index: Any, value: Any) -> None:  # type: ignore[override]
        if isinstance(index, slice):
            old_values = list(self)[index]
            for item in old_values:
                _clear_parent(item)
            coerced = [_coerce_nested(item) for item in list(value)]
            super().__setitem__(index, coerced)
            for item in coerced:
                _assign_parent(item, self)
        else:
            try:
                existing = list.__getitem__(self, index)
            except IndexError:
                existing = None
            else:
                _clear_parent(existing)
            coerced = _coerce_nested(value)
            super().__setitem__(index, coerced)
            _assign_parent(coerced, self)

    def __delitem__(self, index: Any) -> None:  # type: ignore[override]
        if isinstance(index, slice):
            old_values = list(self)[index]
            for item in old_values:
                _clear_parent(item)
        else:
            value = list.__getitem__(self, index)
            _clear_parent(value)
        super().__delitem__(index)

    def pop(self, *args: Any) -> Any:  # type: ignore[override]
        result = super().pop(*args)
        _clear_parent(result)
        return result

    def remove(self, value: Any) -> None:  # type: ignore[override]
        index = list.index(self, value)
        _clear_parent(list.__getitem__(self, index))
        super().remove(value)

    def clear(self) -> None:  # type: ignore[override]
        self._clear_child_parent_links()
        super().clear()


def _assign_parent(value: Any, parent: MutableJSONDict | MutableJSONList) -> None:
    if isinstance(value, (MutableJSONDict, MutableJSONList)):
        value._parent = parent
        value._sync_child_parent_links()


def _clear_parent(value: Any) -> None:
    if isinstance(value, (MutableJSONDict, MutableJSONList)):
        value._clear_child_parent_links()
        value._parent = None


def _coerce_nested(value: Any) -> Any:
    """Convert nested containers into their mutable counterparts."""

    if isinstance(value, (MutableJSONDict, MutableJSONList)):
        return value
    if isinstance(value, dict):
        return MutableJSONDict(value)
    if isinstance(value, (list, tuple)):
        return MutableJSONList(value)
    return value


class Snapshot(Base):
    """Snapshot metadata and payloads."""

    __tablename__ = "snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(26), primary_key=True, default=_generate_ulid)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        MutableJSONDict.as_mutable(JSON), default=MutableJSONDict, nullable=False
    )
    created_at: Mapped[str] = mapped_column(String(32), default=_timestamp, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), default=_timestamp, onupdate=_timestamp, nullable=False)

    def __repr__(self) -> str:
        return f"Snapshot(snapshot_id={self.snapshot_id!r}, document_type={self.document_type!r})"


__all__ = ["Snapshot"]
