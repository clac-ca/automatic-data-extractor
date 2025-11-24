from __future__ import annotations

import pytest
import typer

from ade_tools.commands import common


def test_run_parallel_handles_keyboard_interrupt(monkeypatch):
    class FakeProc:
        def __init__(self):
            self.terminated = False
            self.waited = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=5):
            self.waited = True

    fake_proc = FakeProc()

    monkeypatch.setattr(common.subprocess, "Popen", lambda *args, **kwargs: fake_proc)

    def raise_interrupt(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(common.time, "sleep", raise_interrupt)

    with pytest.raises(typer.Exit) as excinfo:
        common.run_parallel([("test", ["echo", "hi"], None, {})])

    assert excinfo.value.exit_code == 130
    assert fake_proc.terminated is True
    assert fake_proc.waited is True
