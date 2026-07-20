from collections.abc import Iterator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def mpo_bytes() -> bytes:
    output = BytesIO()
    primary = Image.new("RGB", (40, 20), "red")
    exif = primary.getexif()
    exif[274] = 6
    auxiliary = Image.new("L", (10, 10), 128)
    primary.save(
        output,
        format="MPO",
        save_all=True,
        append_images=[auxiliary],
        exif=exif,
    )
    return output.getvalue()


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    from backend.app.config import Settings
    from backend.app.main import create_app

    settings = Settings(data_dir=tmp_path)
    with TestClient(create_app(settings)) as test_client:
        yield test_client
