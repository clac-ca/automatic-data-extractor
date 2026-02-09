"""Helpers for importing configuration archives from GitHub URLs."""

from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlparse

import httpx

from .exceptions import ConfigImportError

_GITHUB_WEB_HOSTS = {"github.com", "www.github.com"}
_GITHUB_API_HOSTS = {"api.github.com"}
_OWNER_REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_GITHUB_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=30.0)


def normalize_github_import_url(url: str) -> tuple[str, str, str | None]:
    """Parse a supported GitHub URL into ``(owner, repo, ref)``."""

    text = url.strip()
    if not text:
        raise ConfigImportError("github_url_invalid")
    parsed = urlparse(text)
    if parsed.scheme.lower() != "https":
        raise ConfigImportError("github_url_invalid")

    host = parsed.netloc.lower().strip()
    segments = [segment for segment in parsed.path.split("/") if segment]

    if host in _GITHUB_WEB_HOSTS:
        return _parse_github_web_segments(segments)
    if host in _GITHUB_API_HOSTS:
        return _parse_github_api_segments(segments)
    raise ConfigImportError("github_url_invalid")


def download_github_archive(
    owner: str,
    repo: str,
    ref: str | None,
    *,
    max_bytes: int,
    client: httpx.Client | None = None,
) -> bytes:
    """Download a GitHub repository zip archive with an upper byte limit."""

    archive_url = _build_github_archive_url(owner, repo, ref)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ADE-Config-Import",
    }

    if client is not None:
        return _download_archive_with_client(client, archive_url, headers, max_bytes)

    try:
        with httpx.Client(follow_redirects=True, timeout=_GITHUB_TIMEOUT) as local_client:
            return _download_archive_with_client(local_client, archive_url, headers, max_bytes)
    except ConfigImportError:
        raise
    except httpx.HTTPError as exc:
        raise ConfigImportError("github_download_failed") from exc


def _parse_github_web_segments(segments: list[str]) -> tuple[str, str, str | None]:
    if len(segments) < 2:
        raise ConfigImportError("github_url_invalid")
    owner = segments[0].strip()
    repo = segments[1].strip()
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    _validate_owner_repo(owner, repo)

    if len(segments) == 2:
        return owner, repo, None

    if segments[2] == "tree" and len(segments) >= 4:
        ref = "/".join(segments[3:]).strip()
        if not ref:
            raise ConfigImportError("github_url_invalid")
        return owner, repo, unquote(ref)

    if segments[2] == "archive" and len(segments) >= 4:
        return owner, repo, _parse_archive_ref(segments[3:])

    raise ConfigImportError("github_url_invalid")


def _parse_github_api_segments(segments: list[str]) -> tuple[str, str, str | None]:
    if len(segments) < 4:
        raise ConfigImportError("github_url_invalid")
    if segments[0] != "repos" or segments[3] != "zipball":
        raise ConfigImportError("github_url_invalid")

    owner = segments[1].strip()
    repo = segments[2].strip()
    _validate_owner_repo(owner, repo)

    if len(segments) == 4:
        return owner, repo, None

    ref = "/".join(segments[4:]).strip()
    if not ref:
        raise ConfigImportError("github_url_invalid")
    return owner, repo, unquote(ref)


def _parse_archive_ref(segments: list[str]) -> str:
    if not segments:
        raise ConfigImportError("github_url_invalid")

    if segments[:2] == ["refs", "heads"] and len(segments) >= 3:
        leaf = "/".join(segments[2:])
        if not leaf.endswith(".zip"):
            raise ConfigImportError("github_url_invalid")
        ref = leaf[: -len(".zip")]
        if not ref:
            raise ConfigImportError("github_url_invalid")
        return unquote(ref)

    if segments[:2] == ["refs", "tags"] and len(segments) >= 3:
        leaf = "/".join(segments[2:])
        if not leaf.endswith(".zip"):
            raise ConfigImportError("github_url_invalid")
        ref = f"refs/tags/{leaf[: -len('.zip')]}"
        if ref.endswith("/"):
            raise ConfigImportError("github_url_invalid")
        return unquote(ref)

    if len(segments) == 1 and segments[0].endswith(".zip"):
        ref = segments[0][: -len(".zip")]
        if not ref:
            raise ConfigImportError("github_url_invalid")
        return unquote(ref)

    raise ConfigImportError("github_url_invalid")


def _validate_owner_repo(owner: str, repo: str) -> None:
    if not owner or not repo:
        raise ConfigImportError("github_url_invalid")
    if not _OWNER_REPO_PATTERN.fullmatch(owner):
        raise ConfigImportError("github_url_invalid")
    if not _OWNER_REPO_PATTERN.fullmatch(repo):
        raise ConfigImportError("github_url_invalid")


def _build_github_archive_url(owner: str, repo: str, ref: str | None) -> str:
    base_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
    if not ref:
        return base_url
    encoded_ref = quote(ref, safe="")
    return f"{base_url}/{encoded_ref}"


def _download_archive_with_client(
    client: httpx.Client,
    archive_url: str,
    headers: dict[str, str],
    max_bytes: int,
) -> bytes:
    try:
        with client.stream("GET", archive_url, headers=headers) as response:
            _raise_for_download_status(response)
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ConfigImportError("archive_too_large", limit=max_bytes)
                chunks.append(chunk)
            return b"".join(chunks)
    except ConfigImportError:
        raise
    except httpx.HTTPError as exc:
        raise ConfigImportError("github_download_failed") from exc


def _raise_for_download_status(response: httpx.Response) -> None:
    status_code = response.status_code
    if status_code < 400:
        return

    if status_code == 429:
        raise ConfigImportError("github_rate_limited")

    if status_code == 403:
        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining == "0":
            raise ConfigImportError("github_rate_limited")
        raise ConfigImportError("github_not_found_or_private")

    if status_code in {401, 404}:
        raise ConfigImportError("github_not_found_or_private")

    raise ConfigImportError("github_download_failed")


__all__ = ["download_github_archive", "normalize_github_import_url"]

