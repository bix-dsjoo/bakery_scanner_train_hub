from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    from backend.app.config import Settings
    from backend.app.main import create_app

    settings = Settings(data_dir=tmp_path)
    with TestClient(create_app(settings)) as test_client:
        yield test_client
