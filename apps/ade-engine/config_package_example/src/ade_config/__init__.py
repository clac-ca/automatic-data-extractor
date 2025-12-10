"""Example ADE config package (registry-based)."""

from importlib import import_module
from pkgutil import walk_packages
from typing import Callable, Iterator


def _iter_register_fns() -> Iterator[Callable]:
    """Yield any register(registry) functions exposed by submodules."""
    if not globals().get("__path__"):
        return iter(())
    for mod in walk_packages(__path__, prefix=__name__ + "."):
        leaf = mod.name.rsplit(".", 1)[-1]
        if leaf.startswith("_") or "tests" in mod.name:
            continue
        module = import_module(mod.name)
        fn = getattr(module, "register", None)
        if callable(fn):
            yield fn


def register(registry) -> None:
    """Auto-discover submodules exposing register(registry) and wire them up."""
    for fn in _iter_register_fns():
        fn(registry)
