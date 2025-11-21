"""Plugin utilities."""

from .utils import _script_to_module
from ade_engine.telemetry.types import _load_event_sink_factories, _load_event_sink_factory

load_event_sink_factories = _load_event_sink_factories
load_event_sink_factory = _load_event_sink_factory

__all__ = ["_script_to_module", "load_event_sink_factories", "load_event_sink_factory"]
