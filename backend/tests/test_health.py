def test_health_returns_ready(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_app_lifespan_creates_storage_directories(client):
    settings = client.app.state.settings

    assert all(path.is_dir() for path in settings.storage_directories)


def test_settings_uses_data_directory_for_storage_paths(tmp_path, monkeypatch):
    from backend.app.config import Settings

    monkeypatch.setenv("BAKERY_DATA_DIR", str(tmp_path))

    settings = Settings()

    assert settings.data_dir == tmp_path
    assert settings.database_path == tmp_path / "database" / "app.db"
    assert settings.database_url == f"sqlite:///{settings.database_path.as_posix()}"
    assert settings.originals_dir == tmp_path / "originals"
    assert settings.thumbnails_dir == tmp_path / "thumbnails"
    assert settings.imports_dir == tmp_path / "imports"
    assert settings.trash_dir == tmp_path / "trash"
    assert settings.logs_dir == tmp_path / "logs"


def test_api_error_has_the_shared_error_shape():
    from backend.app.api.errors import ApiError

    error = ApiError(code="EXAMPLE", message="문제가 발생했어요.")

    assert error.model_dump() == {
        "code": "EXAMPLE",
        "message": "문제가 발생했어요.",
        "action": None,
        "field_errors": None,
    }
