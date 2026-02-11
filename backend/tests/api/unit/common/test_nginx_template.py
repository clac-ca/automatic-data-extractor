from __future__ import annotations

from paths import REPO_ROOT


def test_nginx_template_proxies_api_root_and_prefix() -> None:
    template = (REPO_ROOT / "frontend" / "nginx" / "default.conf.tmpl").read_text(
        encoding="utf-8"
    )

    assert "location = /api {" in template
    assert "location /api/ {" in template
    assert "location = /docs {" in template
    assert "location = /redoc {" in template
    assert "location = /openapi.json {" in template
