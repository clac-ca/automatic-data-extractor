"""Copy formatted code from one or more files to the clipboard for LLM input."""

from __future__ import annotations

import ast
import fnmatch
import os
from pathlib import Path
from typing import Iterable, Sequence

import typer

from ade_cli.commands import common


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


def _pattern_match_path(path: Path) -> str:
    """Return a path string suitable for glob matching.

    Prefer repo-relative paths, fall back to absolute paths.
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(common.REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _should_include_file(
    path: Path,
    *,
    extensions: set[str],
    include_patterns: Sequence[str],
    exclude_patterns: Sequence[str],
) -> bool:
    """Return True if the file passes extension and glob filters."""
    if extensions:
        suffix = path.suffix.lower().lstrip(".")
        if suffix not in extensions:
            return False

    match_path = _pattern_match_path(path)

    if include_patterns:
        if not any(fnmatch.fnmatch(match_path, pat) for pat in include_patterns):
            return False

    if exclude_patterns and any(
        fnmatch.fnmatch(match_path, pat) for pat in exclude_patterns
    ):
        return False

    return True


def _iter_directory_files(
    roots: Sequence[Path],
    *,
    extensions: set[str],
    include_patterns: Sequence[str],
    exclude_patterns: Sequence[str],
    max_depth: int | None,
) -> Iterable[Path]:
    """Yield files from the given directory roots with basic filtering."""
    if not roots:
        return

    for root in roots:
        root = root.resolve()
        if not root.is_dir():
            continue

        base_depth = len(root.parts)

        for dirpath, dirnames, filenames in os.walk(root):
            current_depth = len(Path(dirpath).parts) - base_depth
            if max_depth is not None and current_depth > max_depth:
                # Stop descending beyond max_depth.
                dirnames[:] = []
                continue

            # Skip common junk directories.
            dirnames[:] = [
                d
                for d in dirnames
                if d not in {".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".venv"}
            ]

            for filename in filenames:
                path = Path(dirpath, filename)
                if _should_include_file(
                    path,
                    extensions=extensions,
                    include_patterns=include_patterns,
                    exclude_patterns=exclude_patterns,
                ):
                    yield path


def collect_bundle_files(
    paths: Sequence[Path],
    *,
    dir_paths: Sequence[Path],
    extensions: Sequence[str] | None,
    include_patterns: Sequence[str] | None,
    exclude_patterns: Sequence[str] | None,
    max_depth: int | None,
    max_files: int | None,
) -> list[Path]:
    """Collect file paths from explicit paths and directory roots."""
    ext_set: set[str] = {
        ext.lower().lstrip(".") for ext in (extensions or []) if ext
    }
    include_list: list[str] = [pat for pat in (include_patterns or []) if pat]
    exclude_list: list[str] = [pat for pat in (exclude_patterns or []) if pat]

    explicit_files: list[Path] = []
    dir_roots: list[Path] = []

    # Classify positional paths as files or dirs.
    for raw in paths:
        resolved = raw.resolve()
        if resolved.is_dir():
            dir_roots.append(resolved)
        else:
            explicit_files.append(resolved)

    # Add explicit --dir roots (avoid duplicates).
    for raw in dir_paths:
        resolved = raw.resolve()
        if resolved not in dir_roots:
            dir_roots.append(resolved)

    # Filter explicit files through the same rules.
    filtered_files = [
        p
        for p in explicit_files
        if _should_include_file(
            p,
            extensions=ext_set,
            include_patterns=include_list,
            exclude_patterns=exclude_list,
        )
    ]

    # Collect from directories.
    dir_files = list(
        _iter_directory_files(
            dir_roots,
            extensions=ext_set,
            include_patterns=include_list,
            exclude_patterns=exclude_list,
            max_depth=max_depth,
        )
    )

    combined = normalize_files(filtered_files + dir_files)

    if max_files is not None and max_files > 0 and len(combined) > max_files:
        combined = combined[:max_files]

    return combined


def truncate_bundle(
    text: str,
    *,
    max_lines: int | None,
    head: int | None,
    tail: int | None,
) -> tuple[str, bool]:
    """Optionally truncate the bundle for very large outputs.

    Returns (new_text, truncated_flag).

    - If head/tail are provided, they take precedence over max_lines.
    - If only max_lines is provided, keep the first max_lines lines.
    """
    lines = text.splitlines()
    total = len(lines)
    if total == 0:
        return text, False

    # head/tail mode
    if head is not None or tail is not None:
        head = head or 0
        tail = tail or 0

        if head <= 0 and tail <= 0:
            return text, False

        if total <= head + tail or total <= max(head, tail):
            return text, False

        new_lines: list[str] = []
        if head > 0:
            new_lines.extend(lines[:head])

        new_lines.append("# --- bundle truncated: middle lines omitted ---")

        if tail > 0:
            new_lines.extend(lines[-tail:])

        return "\n".join(new_lines) + "\n", True

    # max_lines mode
    if max_lines is not None and max_lines > 0 and total > max_lines:
        new_lines = lines[:max_lines]
        new_lines.append("# --- bundle truncated at max_lines ---")
        return "\n".join(new_lines) + "\n", True

    return text, False


def run_bundle(
    paths: Sequence[Path],
    *,
    dir_paths: Sequence[Path] | None = None,
    exts: Sequence[str] | None = None,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    depth: int | None = None,
    max_files: int | None = None,
    max_lines: int | None = None,
    head: int | None = None,
    tail: int | None = None,
    out: Path | None = None,
    clip: bool = True,
    print_output: bool = True,
    include_tree: bool = True,
    allow_truncate: bool = False,
) -> str:
    """Collect files, build an LLM bundle, and optionally copy/print/write it."""
    common.refresh_paths()

    dir_paths = dir_paths or []
    if not paths and not dir_paths:
        typer.echo(
            "⚠️ No paths provided. Specify files or directories, e.g.\n"
            "   ade bundle src/app.py\n"
            "   ade bundle --dir src --ext py",
            err=True,
        )
        raise typer.Exit(code=1)

    bundle_files = collect_bundle_files(
        paths,
        dir_paths=dir_paths,
        extensions=exts,
        include_patterns=include,
        exclude_patterns=exclude,
        max_depth=depth,
        max_files=max_files,
    )

    if not bundle_files:
        typer.echo(
            "⚠️ No files matched the given criteria.",
            err=True,
        )
        raise typer.Exit(code=1)

    formatted = format_files_for_clipboard(bundle_files, include_tree=include_tree)

    final_text, truncated = truncate_bundle(
        formatted,
        max_lines=max_lines,
        head=head,
        tail=tail,
    )

    if out is not None:
        try:
            out.write_text(final_text, encoding="utf-8")
        except OSError as exc:
            typer.echo(f"❌ Unable to write bundle to {out!s}: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    clipboard_ok = True
    if clip:
        try:
            copy_to_clipboard(final_text)
        except typer.Exit:
            clipboard_ok = False

    if print_output:
        typer.echo(final_text)

    if clip and not clipboard_ok:
        typer.echo(
            "⚠️ Clipboard copy failed; bundle printed instead.",
            err=True,
        )

    if truncated:
        msg = (
            "⚠️ Bundle was truncated based on line limits "
            "(see comments in the output)."
        )
        if allow_truncate:
            typer.echo(msg, err=True)
        else:
            typer.echo(msg, err=True)
            # Non-zero exit so agents / scripts can detect partial bundles.
            raise typer.Exit(code=2)

    if clip and clipboard_ok:
        typer.echo(
            f"📋 Copied formatted bundle for {len(bundle_files)} file(s) to the clipboard.",
            err=True,
        )

    if clip and not clipboard_ok:
        # Clipboard failure is still an error for scripting.
        raise typer.Exit(code=1)

    return final_text


def register(app: typer.Typer) -> None:
    """Register the `bundle` command with the ade-cli application."""

    @app.command(
        name="bundle",
        help=(
            "Bundle code from files and directories, format it for LLMs, "
            "and copy/print it."
        ),
    )
    def bundle(
        paths: list[Path] = typer.Argument(
            [],
            metavar="[PATH]...",
            help="Files or directories to include in the bundle.",
            exists=True,
            file_okay=True,
            dir_okay=True,
            readable=True,
            resolve_path=True,
        ),
        dir_paths: list[Path] = typer.Option(
            [],
            "--dir",
            help="Additional directories to scan for files (recursive).",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
        ),
        exts: list[str] | None = typer.Option(
            None,
            "--ext",
            "-e",
            help="Only include files with these extensions (no leading dot). Repeatable.",
        ),
        include: list[str] | None = typer.Option(
            None,
            "--include",
            help=(
                "Only include paths matching these glob patterns "
                "(matched against repo-relative paths). Repeatable."
            ),
        ),
        exclude: list[str] | None = typer.Option(
            None,
            "--exclude",
            help=(
                "Exclude paths matching these glob patterns "
                "(matched against repo-relative paths). Repeatable."
            ),
        ),
        depth: int | None = typer.Option(
            None,
            "--depth",
            min=0,
            help="Limit directory traversal depth (0 = only the given directory).",
        ),
        max_files: int | None = typer.Option(
            None,
            "--max-files",
            min=1,
            help="Maximum number of files to include in the bundle.",
        ),
        max_lines: int | None = typer.Option(
            None,
            "--max-lines",
            min=1,
            help="Maximum total lines in the bundle; truncates if exceeded.",
        ),
        head: int | None = typer.Option(
            None,
            "--head",
            min=0,
            help=(
                "Keep only the first N lines of the bundle "
                "(optionally combined with --tail)."
            ),
        ),
        tail: int | None = typer.Option(
            None,
            "--tail",
            min=0,
            help=(
                "Keep only the last N lines of the bundle "
                "(optionally combined with --head)."
            ),
        ),
        allow_truncate: bool = typer.Option(
            False,
            "--allow-truncate",
            help="Do not treat truncated bundles as an error.",
        ),
        out: Path | None = typer.Option(
            None,
            "--out",
            "-o",
            writable=True,
            resolve_path=True,
            help="Write the bundle to this file.",
        ),
        clip: bool = typer.Option(
            True,
            "--clip/--no-clip",
            help="Copy the bundle to the clipboard.",
        ),
        show: bool = typer.Option(
            True,
            "--show/--no-show",
            help="Print the bundle to stdout.",
        ),
        tree: bool = typer.Option(
            True,
            "--tree/--no-tree",
            help="Include a commented file overview above the code blocks.",
        ),
    ) -> None:
        """Bundle code and copy/print it for LLM use."""
        run_bundle(
            paths=paths,
            dir_paths=dir_paths,
            exts=exts,
            include=include,
            exclude=exclude,
            depth=depth,
            max_files=max_files,
            max_lines=max_lines,
            head=head,
            tail=tail,
            out=out,
            clip=clip,
            print_output=show,
            include_tree=tree,
            allow_truncate=allow_truncate,
        )
