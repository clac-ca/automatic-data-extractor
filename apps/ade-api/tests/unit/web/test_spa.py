from pathlib import Path

from fastapi.testclient import TestClient

from ade_api.main import create_app
from ade_api.settings import Settings


def _build_settings(web_dir: Path) -> Settings:
    return Settings(web_dir=web_dir)


def test_spa_fallback_serves_index(tmp_path):
    web_root = tmp_path / "web"
    static_dir = web_root / "static"
    static_dir.mkdir(parents=True)

    index = static_dir / "index.html"
    index.write_text("<html><body>SPA shell</body></html>", encoding="utf-8")

    app = create_app(_build_settings(web_root))
    with TestClient(app) as client:
        response = client.get("/workspaces/abc/config-builder", headers={"accept": "text/html"})
        assert response.status_code == 200
        assert "SPA shell" in response.text

        api_response = client.get("/api/unknown", headers={"accept": "text/html"})
        assert api_response.status_code == 404
