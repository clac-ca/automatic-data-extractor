"""Module entrypoint shim for ``python -m ade_engine``."""

from .entrypoint import console_entrypoint, main

__all__ = ["console_entrypoint", "main"]

if __name__ == "__main__":  # pragma: no cover - manual execution path
    console_entrypoint()
