"""Copy formatted code from one or more files to the clipboard for LLM input."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable, Sequence

import typer

from ade_tools.commands import common


LANGUAGE_HINTS: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".json": "json",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "bash",
    ".txt": "",
}


def language_from_suffix(path: Path) -> str:
    """Return a language hint for code fences based on the file extension."""
    return LANGUAGE_HINTS.get(path.suffix.lower(), "")


def display_path(path: Path) -> str:
    """Return a stable, human-readable path (repo-relative when possible)."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(common.REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def extract_description(path: Path) -> str | None:
    """Extract a short, single-line description from the top of a file.

    For Python modules this prefers the module docstring.
    For other file types it looks for the first non-empty comment line,
    skipping shebangs and common comment prefixes.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    suffix = path.suffix.lower()

    if suffix == ".py":
        try:
            module = ast.parse(text)
        except SyntaxError:
            module = None
        else:
            docstring = ast.get_docstring(module, clean=True)
            if docstring:
                for line in docstring.splitlines():
                    stripped = line.strip()
                    if stripped:
                        return stripped

    lines = text.splitlines()
    idx = 0

    def strip_comment_prefix(line: str) -> str | None:
        stripped = line.strip()
        prefixes = ("#", "//", "/*", "*", "--", ";", "<!--", '"""', "'''")
        for prefix in prefixes:
            if stripped.startswith(prefix):
                content = stripped[len(prefix) :].strip()
                content = content.removesuffix("*/").removesuffix("-->").strip()
                return content or None
        return None

    # Skip leading blank lines.
    while idx < len(lines) and not lines[idx].strip():
        idx += 1

    # Skip shebang if present.
    if idx < len(lines) and lines[idx].lstrip().startswith("#!"):
        idx += 1

    # First real comment line becomes the description.
    while idx < len(lines):
        comment_text = strip_comment_prefix(lines[idx])
        if comment_text is not None:
            return comment_text
        if lines[idx].strip():  # hit code or other text
            break
        idx += 1

    return None


def normalize_files(paths: Iterable[Path]) -> list[Path]:
    """Resolve, de-duplicate, and sort files for deterministic output."""
    seen: set[Path] = set()
    unique: list[Path] = []

    for raw in paths:
        resolved = raw.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)

    unique.sort(key=display_path)
    return unique


def build_tree_summary(paths: Sequence[Path]) -> str:
    """Render a simple commented overview for the LLM at the top of the bundle."""
    lines = ["# Logical module layout (source -> sections below):"]

    for path in paths:
        label = display_path(path)
        desc = extract_description(path)
        if desc:
            lines.append(f"# - {label} - {desc}")
        else:
            lines.append(f"# - {label}")

    return "\n".join(lines)


def format_files_for_clipboard(
    paths: Sequence[Path],
    *,
    include_tree: bool = True,
) -> str:
    """Format files as a single LLM-friendly Markdown bundle.

    Each file is wrapped in its own fenced code block and prefixed with a small
    header so that LLMs and code agents can easily understand which file
    they're looking at.
    """
    blocks: list[str] = []

    for path in paths:
        try:
            content = path.read_text(encoding="utf-8").rstrip("\n")
        except OSError as exc:
            typer.echo(f"❌ Unable to read {path!s}: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        language = language_from_suffix(path)
        title = display_path(path)

        block_lines = [
            f"# {title}",
            f"```{language}".rstrip(),  # handles the empty-language case
            content,
            "```",
        ]
        blocks.append("\n".join(block_lines))

    body = "\n\n".join(blocks) + "\n"

    if not include_tree:
        return body

    tree = build_tree_summary(paths)
    return f"{tree}\n\n{body}"


def copy_to_clipboard(text: str) -> None:
    """Copy text to the system clipboard."""
    try:
        import pyperclip
    except ImportError as exc:  # pragma: no cover - import guard
        typer.echo(
            "❌ Clipboard support requires the 'pyperclip' package. "
            "Install ade-cli into your environment.",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    try:
        pyperclip.copy(text)
    except pyperclip.PyperclipException as exc:
        typer.echo(f"❌ Unable to copy to the clipboard: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def run_copy_code(
    files: Sequence[Path],
    *,
    print_output: bool = False,
    include_tree: bool = True,
) -> str:
    """Format and copy files, returning the formatted text.

    This function is usable from both the Typer CLI and from other Python code
    (e.g. tests or editor/editor-integrations).
    """
    common.refresh_paths()
    normalized_files = normalize_files(files)

    if not normalized_files:
        typer.echo("⚠️ No files provided to copy.", err=True)
        raise typer.Exit(code=1)

    formatted = format_files_for_clipboard(
        normalized_files,
        include_tree=include_tree,
    )

    try:
        copy_to_clipboard(formatted)
        clipboard_ok = True
    except typer.Exit:
        # We already printed an error message in copy_to_clipboard.
        clipboard_ok = False

    # Always print if requested, or if clipboard failed so the user
    # can still manually copy from stdout.
    if print_output or not clipboard_ok:
        if not clipboard_ok:
            typer.echo(
                "⚠️ Clipboard copy failed; printing formatted bundle instead.",
                err=True,
            )
        typer.echo(formatted)

    if clipboard_ok:
        typer.echo(
            f"📋 Copied formatted code for {len(normalized_files)} file(s) to the clipboard.",
            err=True,
        )
    else:
        # Preserve a non-zero exit status for scripting.
        raise typer.Exit(code=1)

    return formatted


def register(app: typer.Typer) -> None:
    """Register the `copy-code` command with the ade-cli application."""

    @app.command(
        name="copy-code",
        help=(
            "Bundle code from one or more files, format it for LLMs, "
            "and copy it to the clipboard."
        ),
    )
    def copy_code(
        files: list[Path] = typer.Argument(
            ...,
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            metavar="FILE...",
            help="One or more files to bundle.",
        ),
        show: bool = typer.Option(
            False,
            "--show",
            "--stdout",
            help="Also print the formatted bundle to stdout.",
        ),
        tree: bool = typer.Option(
            True,
            "--tree/--no-tree",
            help="Include a commented file overview above the code blocks.",
        ),
    ) -> None:
        """Copy formatted code for the given FILEs to the clipboard."""
        run_copy_code(files, print_output=show, include_tree=tree)
