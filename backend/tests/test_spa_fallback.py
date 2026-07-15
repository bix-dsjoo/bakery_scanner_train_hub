from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


@pytest.fixture
def spa_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<html><body>temporary SPA</body></html>", encoding="utf-8"
    )
    (assets_dir / "app.js").write_text(
        'console.log("temporary asset")', encoding="utf-8"
    )

    monkeypatch.setenv("BAKERY_FRONTEND_DIST_DIR", str(dist_dir))
    settings = Settings(data_dir=tmp_path / "data")
    with TestClient(create_app(settings)) as client:
        yield client


def test_spa_route_returns_temporary_index(spa_client: TestClient) -> None:
    response = spa_client.get("/products")

    assert response.status_code == 200
    assert "temporary SPA" in response.text


def test_asset_route_returns_asset_file(spa_client: TestClient) -> None:
    response = spa_client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.text == 'console.log("temporary asset")'


def test_unknown_api_route_does_not_fall_back_to_spa(spa_client: TestClient) -> None:
    response = spa_client.get("/api/v1/unknown")

    assert response.status_code == 404
    assert "temporary SPA" not in response.text


def test_missing_asset_does_not_fall_back_to_spa(spa_client: TestClient) -> None:
    response = spa_client.get("/assets/missing.js")

    assert response.status_code == 404
    assert "temporary SPA" not in response.text


def test_api_response_does_not_allow_wildcard_cors(spa_client: TestClient) -> None:
    response = spa_client.get(
        "/api/v1/health",
        headers={"Origin": "http://different-origin.example"},
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") != "*"
