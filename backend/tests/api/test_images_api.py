from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.infrastructure.file_storage import LocalFileStorage
from backend.app.infrastructure.image_repository import ImageRepository
from backend.app.infrastructure.models import ImageModel
from backend.app.main import create_app


FIXTURES = Path(__file__).parents[1] / "fixtures"


def api_test_settings(data_dir: Path) -> Settings:
    database_path = data_dir / "database" / "app.db"
    return Settings(
        data_dir=data_dir,
        database_url=f"sqlite:///{database_path.as_posix()}",
    )


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    value = api_test_settings(tmp_path)
    monkeypatch.setenv("BAKERY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BAKERY_DATABASE_URL", value.database_url)
    command.upgrade(Config(Path(__file__).parents[3] / "alembic.ini"), "head")
    return value


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), raise_server_exceptions=False) as value:
        yield value


def create_brand(client: TestClient, name: str) -> dict:
    return client.post("/api/v1/brands", json={"name": name}).json()


def create_product(
    client: TestClient, brand_id: str, code: str, name: str
) -> dict:
    return client.post(
        f"/api/v1/brands/{brand_id}/products",
        json={"code": code, "name": name},
    ).json()


def upload(
    client: TestClient,
    brand_id: str,
    fixture: str,
    *,
    kind: str = "TRAY",
    product_id: str | None = None,
    filename: str | None = None,
):
    path = FIXTURES / fixture
    data = {"kind": kind}
    if product_id is not None:
        data["product_id"] = product_id
    return client.post(
        f"/api/v1/brands/{brand_id}/images",
        data=data,
        files={"file": (filename or path.name, path.read_bytes(), "application/octet-stream")},
    )


def assert_error_shape(response, code: str, status_code: int) -> None:
    assert response.status_code == status_code
    assert response.json()["code"] == code
    assert response.json()["message"]
    assert set(response.json()) <= {"code", "message", "action", "field_errors"}


def test_actual_multipart_upload_enforces_kind_product_contract_and_detects_mime(
    client: TestClient,
) -> None:
    brand = create_brand(client, "BIXOLON Bakery")
    product = create_product(client, brand["id"], "BREAD-001", "소금빵")

    product_response = upload(
        client,
        brand["id"],
        "valid.jpg",
        kind="PRODUCT",
        product_id=product["id"],
        filename="상품 사진.jpg",
    )
    tray_response = upload(client, brand["id"], "valid.png")

    assert product_response.status_code == 201
    assert product_response.json()["mime_type"] == "image/jpeg"
    assert product_response.json()["labeling_status"] == "COMPLETED"
    assert product_response.json()["product_id"] == product["id"]
    assert tray_response.status_code == 201
    assert tray_response.json()["mime_type"] == "image/png"
    assert tray_response.json()["labeling_status"] == "UNLABELED"
    assert tray_response.json()["product_id"] is None

    assert_error_shape(
        upload(client, brand["id"], "valid.webp", kind="PRODUCT"),
        "PRODUCT_REQUIRED",
        422,
    )
    assert_error_shape(
        upload(
            client,
            brand["id"],
            "valid.webp",
            kind="TRAY",
            product_id=product["id"],
        ),
        "TRAY_PRODUCT_FORBIDDEN",
        422,
    )


def test_upload_validation_and_duplicate_errors_use_shared_api_error_shape(
    client: TestClient,
) -> None:
    brand = create_brand(client, "BIXOLON Bakery")
    first = upload(client, brand["id"], "valid.jpg")
    duplicate = upload(client, brand["id"], "valid.jpg")
    invalid_kind = upload(client, brand["id"], "valid.png", kind="OTHER")
    missing_file = client.post(
        f"/api/v1/brands/{brand['id']}/images", data={"kind": "TRAY"}
    )

    assert first.status_code == 201
    assert duplicate.json() == {
        "code": "IMAGE_DUPLICATE",
        "message": "같은 이미지가 이미 등록되어 있어요.",
        "action": "기존 이미지를 확인해 주세요.",
    }
    assert duplicate.status_code == 409
    assert_error_shape(invalid_kind, "REQUEST_VALIDATION_ERROR", 422)
    assert invalid_kind.json()["field_errors"] == {"kind": "허용된 값만 입력해 주세요."}
    assert_error_shape(missing_file, "REQUEST_VALIDATION_ERROR", 422)
    assert missing_file.json()["field_errors"] == {"file": "필수 입력값이에요."}


def test_list_filters_paginates_without_storage_keys_or_bytes(client: TestClient) -> None:
    brand = create_brand(client, "BIXOLON Bakery")
    other_brand = create_brand(client, "Other Bakery")
    product = create_product(client, brand["id"], "BREAD-001", "소금빵")
    product_image = upload(
        client,
        brand["id"],
        "valid.jpg",
        kind="PRODUCT",
        product_id=product["id"],
        filename="salt-product.jpg",
    ).json()
    upload(client, brand["id"], "valid.png", filename="tray-alpha.png")
    upload(client, brand["id"], "valid.webp", filename="tray-beta.webp")
    upload(client, other_brand["id"], "valid.jpg", filename="other-brand.jpg")

    first_page = client.get(
        f"/api/v1/brands/{brand['id']}/images", params={"limit": 2}
    )
    second_page = client.get(
        f"/api/v1/brands/{brand['id']}/images",
        params={"limit": 2, "cursor": first_page.json()["next_cursor"]},
    )
    completed = client.get(
        f"/api/v1/brands/{brand['id']}/images",
        params={"status": "COMPLETED", "product_id": product["id"], "filename": "product"},
    )

    assert first_page.status_code == 200
    assert set(first_page.json()) == {"items", "next_cursor"}
    assert len(first_page.json()["items"]) == 2
    assert len(second_page.json()["items"]) == 1
    all_ids = [item["id"] for item in first_page.json()["items"] + second_page.json()["items"]]
    assert len(set(all_ids)) == 3
    ordered = first_page.json()["items"] + second_page.json()["items"]
    assert [(item["created_at"], item["id"]) for item in ordered] == sorted(
        [(item["created_at"], item["id"]) for item in ordered], reverse=True
    )
    assert completed.json()["items"] == [product_image]
    assert all(
        "storage_key" not in item and "sha256" not in item and "bytes" not in item
        for item in first_page.json()["items"]
    )


@pytest.mark.parametrize("limit", [0, 101])
def test_list_limit_boundaries_use_common_validation_error(
    client: TestClient, limit: int
) -> None:
    brand = create_brand(client, f"Bakery {limit}")
    response = client.get(
        f"/api/v1/brands/{brand['id']}/images", params={"limit": limit}
    )
    assert_error_shape(response, "REQUEST_VALIDATION_ERROR", 422)
    assert response.json()["field_errors"] == {"limit": "입력값을 확인해 주세요."}


@pytest.mark.parametrize("limit", [1, 100])
def test_list_accepts_inclusive_limit_boundaries(client: TestClient, limit: int) -> None:
    brand = create_brand(client, f"Accepted Bakery {limit}")
    response = client.get(
        f"/api/v1/brands/{brand['id']}/images", params={"limit": limit}
    )
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


def test_tampered_cursor_is_rejected_without_internal_details(client: TestClient) -> None:
    brand = create_brand(client, "Cursor Bakery")
    response = client.get(
        f"/api/v1/brands/{brand['id']}/images", params={"cursor": "not-a-cursor"}
    )
    assert response.json() == {
        "code": "IMAGE_CURSOR_INVALID",
        "message": "목록 위치 정보를 읽을 수 없어요.",
        "action": "목록을 처음부터 다시 불러와 주세요.",
        "field_errors": {"cursor": "유효하지 않은 목록 위치예요."},
    }
    assert response.status_code == 422


def test_list_rejects_product_filter_from_another_brand(client: TestClient) -> None:
    brand = create_brand(client, "Filter Owner Bakery")
    other = create_brand(client, "Filter Other Bakery")
    foreign_product = create_product(client, other["id"], "FOREIGN", "다른 상품")

    response = client.get(
        f"/api/v1/brands/{brand['id']}/images",
        params={"product_id": foreign_product["id"]},
    )

    assert_error_shape(response, "PRODUCT_BRAND_MISMATCH", 422)


def test_filename_filter_treats_like_wildcards_as_literal_text(
    client: TestClient,
) -> None:
    brand = create_brand(client, "Literal Search Bakery")
    percent_image = upload(
        client, brand["id"], "valid.png", filename="bread%photo.png"
    ).json()
    upload(client, brand["id"], "valid.webp", filename="plain-photo.webp")

    response = client.get(
        f"/api/v1/brands/{brand['id']}/images", params={"filename": "%"}
    )

    assert response.status_code == 200
    assert response.json()["items"] == [percent_image]


def test_detail_files_and_delete_require_matching_brand(client: TestClient) -> None:
    owner = create_brand(client, "Owner Bakery")
    other = create_brand(client, "Other Bakery")
    image = upload(client, owner["id"], "valid.jpg").json()

    for method, suffix in [
        (client.get, ""),
        (client.get, "/original"),
        (client.get, "/thumbnail"),
        (client.delete, ""),
    ]:
        response = method(
            f"/api/v1/images/{image['id']}{suffix}", params={"brand_id": other["id"]}
        )
        assert_error_shape(response, "IMAGE_NOT_FOUND", 404)

    still_exists = client.get(
        f"/api/v1/images/{image['id']}", params={"brand_id": owner["id"]}
    )
    assert still_exists.status_code == 200
    assert still_exists.json()["box_count"] == 0

    missing_scope = client.get(f"/api/v1/images/{image['id']}")
    assert_error_shape(missing_scope, "REQUEST_VALIDATION_ERROR", 422)
    assert missing_scope.json()["field_errors"] == {
        "brand_id": "필수 입력값이에요."
    }


def test_file_responses_detect_type_escape_filename_and_do_not_leak_paths(
    client: TestClient, settings: Settings
) -> None:
    brand = create_brand(client, "Files Bakery")
    image = upload(
        client,
        brand["id"],
        "valid.jpg",
        filename='빵 "사진".jpg',
    ).json()

    original = client.get(
        f"/api/v1/images/{image['id']}/original", params={"brand_id": brand["id"]}
    )
    thumbnail = client.get(
        f"/api/v1/images/{image['id']}/thumbnail", params={"brand_id": brand["id"]}
    )
    assert original.status_code == 200
    assert original.headers["content-type"].startswith("image/jpeg")
    assert "filename*=utf-8''" in original.headers["content-disposition"].lower()
    assert "\r" not in original.headers["content-disposition"]
    assert "\n" not in original.headers["content-disposition"]
    assert thumbnail.status_code == 200
    assert thumbnail.headers["content-type"].startswith("image/webp")

    with Session(client.app.state.session_factory.kw["bind"]) as session:
        model = session.get(ImageModel, image["id"])
        assert model is not None
        LocalFileStorage(settings).resolve("originals", model.storage_key).unlink()
    missing = client.get(
        f"/api/v1/images/{image['id']}/original", params={"brand_id": brand["id"]}
    )
    assert_error_shape(missing, "IMAGE_FILE_MISSING", 404)
    assert str(settings.data_dir) not in missing.text


def test_product_change_enforces_image_and_product_brand_kind_and_activity(
    client: TestClient,
) -> None:
    brand = create_brand(client, "Products Bakery")
    other = create_brand(client, "Other Products Bakery")
    first = create_product(client, brand["id"], "ONE", "첫 상품")
    second = create_product(client, brand["id"], "TWO", "둘째 상품")
    inactive = create_product(client, brand["id"], "OLD", "비활성 상품")
    foreign = create_product(client, other["id"], "FOREIGN", "다른 상품")
    client.patch(
        f"/api/v1/brands/{brand['id']}/products/{inactive['id']}",
        json={"status": "INACTIVE"},
    )
    product_image = upload(
        client, brand["id"], "valid.jpg", kind="PRODUCT", product_id=first["id"]
    ).json()
    tray_image = upload(client, brand["id"], "valid.png").json()
    url = f"/api/v1/images/{product_image['id']}/product"

    changed = client.patch(
        url, params={"brand_id": brand["id"]}, json={"product_id": second["id"]}
    )
    assert changed.status_code == 200
    assert changed.json()["product_id"] == second["id"]

    cases = [
        ({"product_id": None}, "PRODUCT_REQUIRED"),
        ({"product_id": inactive["id"]}, "PRODUCT_INACTIVE"),
        ({"product_id": foreign["id"]}, "PRODUCT_BRAND_MISMATCH"),
    ]
    for body, code in cases:
        assert_error_shape(
            client.patch(url, params={"brand_id": brand["id"]}, json=body), code, 422
        )
    assert_error_shape(
        client.patch(
            f"/api/v1/images/{tray_image['id']}/product",
            params={"brand_id": brand["id"]},
            json={"product_id": second["id"]},
        ),
        "TRAY_PRODUCT_CHANGE_FORBIDDEN",
        422,
    )
    assert_error_shape(
        client.patch(url, params={"brand_id": other["id"]}, json={"product_id": foreign["id"]}),
        "IMAGE_NOT_FOUND",
        404,
    )


def test_delete_moves_files_removes_row_and_cleans_trash(
    client: TestClient, settings: Settings
) -> None:
    brand = create_brand(client, "Delete Bakery")
    image = upload(client, brand["id"], "valid.jpg").json()

    response = client.delete(
        f"/api/v1/images/{image['id']}", params={"brand_id": brand["id"]}
    )

    assert response.status_code == 204
    with Session(client.app.state.session_factory.kw["bind"]) as session:
        assert session.get(ImageModel, image["id"]) is None
    assert list(settings.originals_dir.rglob("*.jpg")) == []
    assert list(settings.thumbnails_dir.rglob("*.webp")) == []
    assert list(settings.trash_dir.iterdir()) == []


def test_delete_commit_failure_restores_both_files_and_row(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    brand = create_brand(client, "Restore Bakery")
    image = upload(client, brand["id"], "valid.jpg").json()
    original_commit = ImageRepository.commit

    def fail_commit(self: ImageRepository) -> None:
        raise RuntimeError("forced database failure")

    monkeypatch.setattr(ImageRepository, "commit", fail_commit)
    response = client.delete(
        f"/api/v1/images/{image['id']}", params={"brand_id": brand["id"]}
    )
    monkeypatch.setattr(ImageRepository, "commit", original_commit)

    assert_error_shape(response, "INTERNAL_SERVER_ERROR", 500)
    with Session(client.app.state.session_factory.kw["bind"]) as session:
        model = session.get(ImageModel, image["id"])
        assert model is not None
        storage = LocalFileStorage(settings)
        assert storage.resolve("originals", model.storage_key).is_file()
        assert storage.resolve("thumbnails", model.thumbnail_storage_key).is_file()
    assert list(settings.trash_dir.iterdir()) == []


def test_delete_trash_cleanup_failure_is_logged_without_failing_request(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    brand = create_brand(client, "Cleanup Bakery")
    image = upload(client, brand["id"], "valid.jpg").json()

    def fail_cleanup(self: LocalFileStorage, entry) -> None:
        raise OSError("forced cleanup failure")

    monkeypatch.setattr(LocalFileStorage, "delete_trash", fail_cleanup)
    library_logger = logging.getLogger("backend.app.application.image_library")
    monkeypatch.setattr(library_logger, "disabled", False)
    with caplog.at_level(logging.ERROR, logger=library_logger.name):
        response = client.delete(
            f"/api/v1/images/{image['id']}", params={"brand_id": brand["id"]}
        )

    assert response.status_code == 204
    assert "trash cleanup failed" in caplog.text.lower()
