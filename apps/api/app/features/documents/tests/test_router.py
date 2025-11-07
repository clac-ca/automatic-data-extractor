from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from apps.api.app.features.documents.router import _build_download_disposition
from apps.api.app.features.documents.service import DocumentsService
from apps.api.app.settings import Settings


def _make_documents_service(tmp_path: Path) -> DocumentsService:
    settings = Settings(documents_dir=tmp_path)
    session = MagicMock()
    return DocumentsService(session=session, settings=settings)


def test_build_download_disposition_strips_control_characters() -> None:
    header_value = _build_download_disposition("report\r\nSet-Cookie: evil.txt")

    assert "\r" not in header_value
    assert "\n" not in header_value
    assert header_value.startswith("attachment; filename=")
    assert "filename*=UTF-8''reportSet-Cookie%3A%20evil.txt" in header_value


def test_build_download_disposition_preserves_unicode_filename() -> None:
    header_value = _build_download_disposition("rêport ✅.pdf")

    assert 'filename="r_port _.pdf"' in header_value
    assert "filename*=UTF-8''r%C3%AAport%20%E2%9C%85.pdf" in header_value


def test_normalise_filename_removes_control_characters(tmp_path: Path) -> None:
    service = _make_documents_service(tmp_path)

    result = service._normalise_filename("evil \r\nname.txt")

    assert result == "evil name.txt"
    assert "\r" not in result
    assert "\n" not in result


def test_normalise_filename_falls_back_for_empty_values(tmp_path: Path) -> None:
    service = _make_documents_service(tmp_path)

    assert service._normalise_filename("   \r\n ") == "upload"
    assert service._normalise_filename(None) == "upload"
