from __future__ import annotations

import sys

from ade_cli.commands import common
from ade_cli.commands import bundle


def test_format_files_for_clipboard_uses_relative_paths_and_languages(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)

    alpha = tmp_path / "alpha.py"
    docs = tmp_path / "docs"
    docs.mkdir()
    notes = docs / "notes.txt"

    alpha.write_text("print('hi')\n")
    notes.write_text("hello")

    formatted = bundle.format_files_for_clipboard([alpha, notes])

    assert formatted == (
        "# Logical module layout (source -> sections below):\n"
        "# - alpha.py\n"
        "# - docs/notes.txt\n"
        "\n"
        "# alpha.py\n"
        "```python\n"
        "print('hi')\n"
        "```\n"
        "\n"
        "# docs/notes.txt\n"
        "```\n"
        "hello\n"
        "```\n"
    )


def test_run_bundle_uses_clipboard(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(common, "refresh_paths", lambda: None)
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)

    file_path = tmp_path / "foo.py"
    file_path.write_text("example = 1\n")

    class DummyPyperclip:
        data: str | None = None

        class PyperclipException(Exception):
            pass

        @staticmethod
        def copy(text: str) -> None:
            DummyPyperclip.data = text

    monkeypatch.setitem(sys.modules, "pyperclip", DummyPyperclip)

    formatted = bundle.run_bundle([file_path], clip=True, print_output=False)

    assert DummyPyperclip.data == formatted
    assert "Logical module layout" in formatted
    assert "example = 1" in formatted


def test_run_bundle_defaults_to_print_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(common, "refresh_paths", lambda: None)
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)

    file_path = tmp_path / "foo.py"
    file_path.write_text("example = 1\n")

    # Fail if clipboard is attempted.
    def _copy(_text: str) -> None:  # pragma: no cover - protective stub
        raise AssertionError("clipboard should not be used by default")

    monkeypatch.setattr(bundle, "copy_to_clipboard", _copy)

    formatted = bundle.run_bundle([file_path], print_output=False)

    assert "example = 1" in formatted


def test_tree_can_be_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)

    alpha = tmp_path / "alpha.py"
    alpha.write_text("print('hi')\n")

    formatted = bundle.format_files_for_clipboard([alpha], include_tree=False)

    assert formatted.startswith("# alpha.py")
    assert "Logical module layout" not in formatted


def test_tree_uses_docstring(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)

    alpha = tmp_path / "alpha.py"
    alpha.write_text('"""Shared pipe settings and defaults."""\nVALUE = 1\n')
    beta = tmp_path / "beta.ts"
    beta.write_text("// Session-aware logging helpers.\nconst x = 1;\n")

    formatted = bundle.format_files_for_clipboard([alpha, beta])

    assert "# - alpha.py" in formatted
    assert "Shared pipe settings and defaults." in formatted
    assert "# - beta.ts" in formatted
    assert "Session-aware logging helpers." in formatted


def test_bundle_excludes_pycache_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)

    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    compiled = pycache / "module.cpython-311.pyc"
    compiled.write_text("compiled\n")

    keep = tmp_path / "keep.py"
    keep.write_text("print('hi')\n")

    files = bundle.collect_bundle_files(
        [pycache, keep],
        dir_paths=[],
        extensions=None,
        include_patterns=None,
        exclude_patterns=None,
        max_depth=None,
        max_files=None,
    )

    assert files == [keep.resolve()]
