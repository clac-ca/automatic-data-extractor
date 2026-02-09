from __future__ import annotations

import httpx
import pytest

from ade_api.features.configs.exceptions import ConfigImportError
from ade_api.features.configs.github_import import (
    download_github_archive,
    normalize_github_import_url,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/octo/repo", ("octo", "repo", None)),
        ("https://github.com/octo/repo.git", ("octo", "repo", None)),
        ("https://github.com/octo/repo/tree/main", ("octo", "repo", "main")),
        (
            "https://github.com/octo/repo/tree/feature/config-updates",
            ("octo", "repo", "feature/config-updates"),
        ),
        (
            "https://github.com/octo/repo/archive/refs/heads/main.zip",
            ("octo", "repo", "main"),
        ),
        (
            "https://github.com/octo/repo/archive/refs/heads/feature/config-updates.zip",
            ("octo", "repo", "feature/config-updates"),
        ),
        (
            "https://github.com/octo/repo/archive/refs/tags/v1.2.3.zip",
            ("octo", "repo", "refs/tags/v1.2.3"),
        ),
        ("https://github.com/octo/repo/archive/abc123.zip", ("octo", "repo", "abc123")),
        ("https://api.github.com/repos/octo/repo/zipball", ("octo", "repo", None)),
        (
            "https://api.github.com/repos/octo/repo/zipball/feature%2Fconfig-updates",
            ("octo", "repo", "feature/config-updates"),
        ),
    ],
)
def test_normalize_github_import_url_supported_shapes(
    url: str,
    expected: tuple[str, str, str | None],
) -> None:
    assert normalize_github_import_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://github.com/octo/repo",
        "https://gitlab.com/octo/repo",
        "https://github.com/octo",
        "https://github.com/octo/repo/issues/1",
        "https://github.com/octo/repo/tree",
        "https://github.com/octo/repo/archive/refs/heads/main",
        "https://api.github.com/repos/octo/repo",
    ],
)
def test_normalize_github_import_url_rejects_unsupported_shapes(url: str) -> None:
    with pytest.raises(ConfigImportError) as exc_info:
        normalize_github_import_url(url)
    assert exc_info.value.code == "github_url_invalid"


def test_download_github_archive_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octo/repo/zipball/main"
        return httpx.Response(200, content=b"archive-bytes")

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    try:
        archive = download_github_archive("octo", "repo", "main", max_bytes=1024, client=client)
    finally:
        client.close()

    assert archive == b"archive-bytes"


def test_download_github_archive_rejects_over_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, content=b"123456")

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    try:
        with pytest.raises(ConfigImportError) as exc_info:
            download_github_archive("octo", "repo", "main", max_bytes=5, client=client)
    finally:
        client.close()

    assert exc_info.value.code == "archive_too_large"
    assert exc_info.value.limit == 5


@pytest.mark.parametrize(
    ("status_code", "headers", "expected"),
    [
        (401, {}, "github_not_found_or_private"),
        (404, {}, "github_not_found_or_private"),
        (403, {}, "github_not_found_or_private"),
        (403, {"x-ratelimit-remaining": "0"}, "github_rate_limited"),
        (429, {}, "github_rate_limited"),
        (500, {}, "github_download_failed"),
    ],
)
def test_download_github_archive_maps_upstream_errors(
    status_code: int,
    headers: dict[str, str],
    expected: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(status_code, headers=headers)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    try:
        with pytest.raises(ConfigImportError) as exc_info:
            download_github_archive("octo", "repo", "main", max_bytes=1024, client=client)
    finally:
        client.close()

    assert exc_info.value.code == expected


def test_download_github_archive_maps_http_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    try:
        with pytest.raises(ConfigImportError) as exc_info:
            download_github_archive("octo", "repo", "main", max_bytes=1024, client=client)
    finally:
        client.close()

    assert exc_info.value.code == "github_download_failed"

