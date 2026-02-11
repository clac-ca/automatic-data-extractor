from __future__ import annotations

from paths import REPO_ROOT


def test_vite_proxy_includes_api_docs_legacy_paths() -> None:
    vite_config = (REPO_ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")

    assert '"/api": {' in vite_config
    assert '"/docs": {' in vite_config
    assert '"/redoc": {' in vite_config
    assert '"/openapi.json": {' in vite_config
