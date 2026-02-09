"""Example ADE config package.

Drop modules into:
- ``ade_config/columns`` (fields + column detectors/transforms/validators)
- ``ade_config/row_detectors`` (row kind detectors)
- ``ade_config/hooks`` (lifecycle hooks)

The ADE engine auto-discovers any module in those folders that defines a top-level
``register(registry)`` function and invokes it in deterministic order.

This file exists primarily to mark ``ade_config`` as an importable Python package.
"""

from __future__ import annotations
