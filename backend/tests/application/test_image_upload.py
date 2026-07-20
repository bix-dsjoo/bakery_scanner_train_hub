from __future__ import annotations

import hashlib
import io
import inspect
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.catalog import CatalogService
from backend.app.application.image_upload import ImageUploadError, ImageUploadService
from backend.app.config import Settings
from backend.app.domain.images import ImageKind, LabelingStatus
from backend.app.infrastructure.catalog_repository import CatalogRepository
from backend.app.infrastructure.database import create_engine_for
from backend.app.infrastructure.file_storage import (
    DEFAULT_MAX_BYTES,
    FileTooLargeError,
    LocalFileStorage,
)
from backend.app.infrastructure.image_processor import ImageProcessor, InvalidImageError
from backend.app.infrastructure.image_repository import (
    DiskSpaceProbe,
    DuplicateImage,
    ImageRepository,
)
from backend.app.infrastructure.models import Base, ImageModel


FIXTURES = Path(__file__).parents[1] / "fixtures"


class AcceptingDiskSpaceProbe:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def can_accept(self, byte_limit: int, reserve_bytes: int) -> bool:
        self.calls.append((byte_limit, reserve_bytes))
        return True


class RejectingDiskSpaceProbe:
    def can_accept(self, byte_limit: int, reserve_bytes: int) -> bool:
        return False


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        database_url=f"sqlite:///{(tmp_path / 'upload.db').as_posix()}",
    )


@pytest.fixture
def session(settings: Settings):
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


@pytest.fixture
def catalog(session: Session) -> CatalogService:
    return CatalogService(CatalogRepository(session))


def make_service(
    session: Session,
    settings: Settings,
    *,
    disk_space_probe=None,
    file_storage=None,
    image_processor=None,
    image_repository=None,
) -> ImageUploadService:
    return ImageUploadService(
        catalog_repository=CatalogRepository(session),
        image_repository=image_repository or ImageRepository(session),
        file_storage=file_storage or LocalFileStorage(settings),
        image_processor=image_processor or ImageProcessor(),
        disk_space_probe=disk_space_probe or AcceptingDiskSpaceProbe(),
    )


def fixture_stream(filename: str = "valid.jpg") -> io.BytesIO:
    return io.BytesIO((FIXTURES / filename).read_bytes())


def assert_no_request_files(settings: Settings) -> None:
    for directory in (
        settings.imports_dir,
        settings.originals_dir,
        settings.thumbnails_dir,
    ):
        assert not directory.exists() or not [path for path in directory.rglob("*") if path.is_file()]


def test_upload_has_exact_public_signature() -> None:
    signature = inspect.signature(ImageUploadService.upload)

    assert list(signature.parameters) == [
        "self",
        "brand_id",
        "kind",
        "product_id",
        "filename",
        "stream",
    ]
    assert signature.return_annotation == "ImageRecord"


def test_product_upload_creates_completed_record_and_real_files(
    session: Session, settings: Settings, catalog: CatalogService
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    product = catalog.create_product(brand.id, "BREAD-001", "소금빵")
    session.commit()
    probe = AcceptingDiskSpaceProbe()

    record = make_service(
        session, settings, disk_space_probe=probe
    ).upload(
        brand.id,
        ImageKind.PRODUCT,
        product.id,
        "salt-bread.jpg",
        fixture_stream(),
    )

    assert record.kind == ImageKind.PRODUCT
    assert record.product_id == product.id
    assert record.labeling_status == LabelingStatus.COMPLETED
    assert record.original_filename == "salt-bread.jpg"
    assert LocalFileStorage(settings).resolve("originals", record.storage_key).exists()
    assert LocalFileStorage(settings).resolve(
        "thumbnails", record.thumbnail_storage_key
    ).exists()
    assert session.get(ImageModel, record.id) is not None
    assert probe.calls == [(25 * 1024 * 1024, 10 * 1024 * 1024 * 1024)]


def test_tray_upload_creates_unlabeled_record_without_product(
    session: Session, settings: Settings, catalog: CatalogService
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()

    record = make_service(session, settings).upload(
        brand.id,
        ImageKind.TRAY,
        None,
        "tray.png",
        fixture_stream("valid.png"),
    )

    assert record.kind == ImageKind.TRAY
    assert record.product_id is None
    assert record.labeling_status == LabelingStatus.UNLABELED


@pytest.mark.parametrize(
    ("kind", "expected_status"),
    [
        (ImageKind.PRODUCT, LabelingStatus.COMPLETED),
        (ImageKind.TRAY, LabelingStatus.UNLABELED),
    ],
)
def test_mpo_jpeg_upload_preserves_original_and_existing_status_rules(
    session: Session,
    settings: Settings,
    catalog: CatalogService,
    mpo_bytes: bytes,
    kind: ImageKind,
    expected_status: LabelingStatus,
) -> None:
    brand = catalog.create_brand(f"MPO {kind.value} Bakery")
    product_id = None
    if kind == ImageKind.PRODUCT:
        product = catalog.create_product(brand.id, "MPO-001", "MPO 빵")
        product_id = product.id
    session.commit()

    record = make_service(session, settings).upload(
        brand.id,
        kind,
        product_id,
        "iphone.jpg",
        io.BytesIO(mpo_bytes),
    )

    original = LocalFileStorage(settings).resolve("originals", record.storage_key)
    assert original.read_bytes() == mpo_bytes
    assert record.sha256 == hashlib.sha256(mpo_bytes).hexdigest()
    assert record.mime_type == "image/jpeg"
    assert (record.width, record.height) == (40, 20)
    assert record.labeling_status == expected_status


def test_upload_processing_order_is_deterministic(
    session: Session,
    settings: Settings,
    catalog: CatalogService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()
    calls: list[str] = []
    storage = LocalFileStorage(settings)
    processor = ImageProcessor()
    repository = ImageRepository(session)
    probe = AcceptingDiskSpaceProbe()

    def wrap(target, method_name: str, label: str) -> None:
        original = getattr(target, method_name)

        def recorded(*args, **kwargs):
            calls.append(label)
            return original(*args, **kwargs)

        monkeypatch.setattr(target, method_name, recorded)

    wrap(probe, "can_accept", "disk")
    wrap(storage, "stream_import", "stream")
    wrap(processor, "inspect", "inspect")
    wrap(repository, "find_duplicate", "duplicate")
    wrap(processor, "create_thumbnail", "thumbnail")
    original_promote = storage.promote

    def recorded_promote(*args, **kwargs):
        calls.append(f"promote:{kwargs['collection']}")
        return original_promote(*args, **kwargs)

    monkeypatch.setattr(storage, "promote", recorded_promote)
    wrap(repository, "create", "database:create")
    wrap(repository, "commit", "database:commit")

    ImageUploadService(
        catalog_repository=CatalogRepository(session),
        image_repository=repository,
        file_storage=storage,
        image_processor=processor,
        disk_space_probe=probe,
    ).upload(brand.id, ImageKind.TRAY, None, "tray.jpg", fixture_stream())

    assert calls == [
        "disk",
        "stream",
        "inspect",
        "duplicate",
        "thumbnail",
        "promote:originals",
        "promote:thumbnails",
        "database:create",
        "database:commit",
    ]


def test_same_hash_is_rejected_inside_brand_without_leaving_files(
    session: Session, settings: Settings, catalog: CatalogService
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()
    service = make_service(session, settings)
    service.upload(
        brand.id, ImageKind.TRAY, None, "first.jpg", fixture_stream()
    )
    existing_files = {
        path: path.read_bytes()
        for root in (settings.originals_dir, settings.thumbnails_dir)
        for path in root.rglob("*")
        if path.is_file()
    }

    with pytest.raises(ImageUploadError) as caught:
        service.upload(
            brand.id, ImageKind.TRAY, None, "duplicate.jpg", fixture_stream()
        )

    assert caught.value.code == "IMAGE_DUPLICATE"
    assert {
        path: path.read_bytes()
        for root in (settings.originals_dir, settings.thumbnails_dir)
        for path in root.rglob("*")
        if path.is_file()
    } == existing_files
    assert not settings.imports_dir.exists() or not list(settings.imports_dir.iterdir())


def test_same_hash_is_allowed_for_another_brand(
    session: Session, settings: Settings, catalog: CatalogService
) -> None:
    first_brand = catalog.create_brand("First Bakery")
    second_brand = catalog.create_brand("Second Bakery")
    session.commit()
    service = make_service(session, settings)

    first = service.upload(
        first_brand.id, ImageKind.TRAY, None, "first.jpg", fixture_stream()
    )
    second = service.upload(
        second_brand.id, ImageKind.TRAY, None, "second.jpg", fixture_stream()
    )

    assert first.sha256 == second.sha256
    assert first.brand_id != second.brand_id


@pytest.mark.parametrize(
    ("product_state", "expected_code"),
    [
        ("other_brand", "PRODUCT_BRAND_MISMATCH"),
        ("inactive", "PRODUCT_INACTIVE"),
    ],
)
def test_product_must_be_active_and_inside_brand_before_files_are_created(
    session: Session,
    settings: Settings,
    catalog: CatalogService,
    product_state: str,
    expected_code: str,
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    other_brand = catalog.create_brand("Other Bakery")
    product_brand_id = other_brand.id if product_state == "other_brand" else brand.id
    product = catalog.create_product(product_brand_id, "BREAD-001", "소금빵")
    if product_state == "inactive":
        catalog.deactivate_product(brand.id, product.id)
    session.commit()

    with pytest.raises(ImageUploadError) as caught:
        make_service(session, settings).upload(
            brand.id,
            ImageKind.PRODUCT,
            product.id,
            "salt-bread.jpg",
            fixture_stream(),
        )

    assert caught.value.code == expected_code
    assert_no_request_files(settings)


def test_low_disk_space_stops_before_reading_stream_or_creating_files(
    session: Session, settings: Settings, catalog: CatalogService
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()
    stream = fixture_stream()

    with pytest.raises(ImageUploadError) as caught:
        make_service(
            session, settings, disk_space_probe=RejectingDiskSpaceProbe()
        ).upload(brand.id, ImageKind.TRAY, None, "tray.jpg", stream)

    assert caught.value.code == "DISK_SPACE_LOW"
    assert stream.tell() == 0
    assert_no_request_files(settings)


@pytest.mark.parametrize(
    ("filename", "fixture_name", "expected_code"),
    [
        ("disguised.jpg", "valid.png", "IMAGE_UNSUPPORTED"),
        ("corrupt.jpg", "corrupt.jpg", "IMAGE_CORRUPT"),
    ],
)
def test_processing_errors_have_stable_codes_and_clean_imports(
    session: Session,
    settings: Settings,
    catalog: CatalogService,
    filename: str,
    fixture_name: str,
    expected_code: str,
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()

    with pytest.raises(ImageUploadError) as caught:
        make_service(session, settings).upload(
            brand.id,
            ImageKind.TRAY,
            None,
            filename,
            fixture_stream(fixture_name),
        )

    assert caught.value.code == expected_code
    assert_no_request_files(settings)


def test_too_large_error_uses_the_25_mib_storage_boundary(
    session: Session, settings: Settings, catalog: CatalogService
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()

    class BoundaryStorage(LocalFileStorage):
        def stream_import(self, stream, *, max_bytes=DEFAULT_MAX_BYTES):
            assert max_bytes == 25 * 1024 * 1024
            raise FileTooLargeError("over default boundary")

    with pytest.raises(ImageUploadError) as caught:
        make_service(
            session,
            settings,
            file_storage=BoundaryStorage(settings),
        ).upload(brand.id, ImageKind.TRAY, None, "tray.jpg", fixture_stream())

    assert caught.value.code == "IMAGE_TOO_LARGE"


def test_partial_thumbnail_is_removed_when_processor_raises(
    session: Session, settings: Settings, catalog: CatalogService
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()

    class PartialWritingProcessor(ImageProcessor):
        def create_thumbnail(self, source, destination, *, max_edge=512):
            destination.write_bytes(b"partial thumbnail")
            raise InvalidImageError("thumbnail failed")

    with pytest.raises(ImageUploadError) as caught:
        make_service(
            session,
            settings,
            image_processor=PartialWritingProcessor(),
        ).upload(brand.id, ImageKind.TRAY, None, "tray.jpg", fixture_stream())

    assert caught.value.code == "IMAGE_CORRUPT"
    assert_no_request_files(settings)


def test_thumbnail_collision_preserves_preexisting_file(
    session: Session,
    settings: Settings,
    catalog: CatalogService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()
    settings.imports_dir.mkdir(parents=True)
    existing = settings.imports_dir / "fixed.thumbnail.webp"
    existing.write_bytes(b"preexisting thumbnail")
    monkeypatch.setattr(
        "backend.app.application.image_upload.uuid4",
        lambda: SimpleNamespace(hex="fixed"),
    )

    with pytest.raises(FileExistsError):
        make_service(session, settings).upload(
            brand.id, ImageKind.TRAY, None, "tray.jpg", fixture_stream()
        )

    assert existing.read_bytes() == b"preexisting thumbnail"
    assert [path for path in settings.imports_dir.iterdir() if path != existing] == []


@pytest.mark.parametrize("cleanup_failure", ["resolve", "unlink"])
def test_rollback_and_one_file_cleanup_failure_preserve_original_error_and_continue(
    session: Session,
    settings: Settings,
    catalog: CatalogService,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_failure: str,
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()
    storage = LocalFileStorage(settings)
    cleanup_started = False

    class FailingRepository:
        def find_duplicate(self, brand_id, sha256):
            return None

        def create(self, **kwargs):
            nonlocal cleanup_started
            cleanup_started = True
            raise DuplicateImage

        def commit(self):
            raise AssertionError("commit must not run")

        def rollback(self):
            raise RuntimeError("rollback unavailable")

    original_resolve = storage.resolve

    def controlled_resolve(collection, storage_key):
        if (
            cleanup_started
            and cleanup_failure == "resolve"
            and collection == "thumbnails"
        ):
            raise OSError("thumbnail resolve unavailable")
        return original_resolve(collection, storage_key)

    monkeypatch.setattr(storage, "resolve", controlled_resolve)
    original_unlink = Path.unlink

    def controlled_unlink(path, *args, **kwargs):
        if (
            cleanup_started
            and cleanup_failure == "unlink"
            and path.is_relative_to(settings.thumbnails_dir)
        ):
            raise OSError("thumbnail unlink unavailable")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", controlled_unlink)

    with pytest.raises(ImageUploadError) as caught:
        make_service(
            session,
            settings,
            file_storage=storage,
            image_repository=FailingRepository(),
        ).upload(brand.id, ImageKind.TRAY, None, "tray.jpg", fixture_stream())

    assert caught.value.code == "IMAGE_DUPLICATE"
    assert not [path for path in settings.originals_dir.rglob("*") if path.is_file()]
    assert not [path for path in settings.imports_dir.rglob("*") if path.is_file()]
    remaining_thumbnail = [
        path for path in settings.thumbnails_dir.rglob("*") if path.is_file()
    ]
    assert remaining_thumbnail
    notes = "\n".join(caught.value.__notes__)
    assert "rollback" in notes
    assert "thumbnail final" in notes
    assert remaining_thumbnail[0].relative_to(settings.thumbnails_dir).as_posix() in notes


def test_commit_failure_rolls_back_row_and_removes_promoted_files(
    session: Session, settings: Settings, catalog: CatalogService
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()

    def fail_commit(_session: Session) -> None:
        raise RuntimeError("commit unavailable")

    event.listen(session, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="commit unavailable"):
            make_service(session, settings).upload(
                brand.id, ImageKind.TRAY, None, "tray.jpg", fixture_stream()
            )
    finally:
        event.remove(session, "before_commit", fail_commit)

    assert session.scalar(select(func.count()).select_from(ImageModel)) == 0
    assert_no_request_files(settings)


def test_flush_failure_rolls_back_and_does_not_delete_preexisting_files(
    session: Session, settings: Settings, catalog: CatalogService, monkeypatch
) -> None:
    brand = catalog.create_brand("BIXOLON Bakery")
    session.commit()
    preexisting_original = settings.originals_dir / "keep.jpg"
    preexisting_thumbnail = settings.thumbnails_dir / "keep.webp"
    preexisting_original.parent.mkdir(parents=True)
    preexisting_thumbnail.parent.mkdir(parents=True)
    preexisting_original.write_bytes(b"existing original")
    preexisting_thumbnail.write_bytes(b"existing thumbnail")

    original_flush = session.flush

    def fail_image_flush(*args, **kwargs) -> None:
        if any(isinstance(value, ImageModel) for value in session.new):
            raise RuntimeError("flush unavailable")
        original_flush(*args, **kwargs)

    monkeypatch.setattr(session, "flush", fail_image_flush)

    with pytest.raises(RuntimeError, match="flush unavailable"):
        make_service(session, settings).upload(
            brand.id, ImageKind.TRAY, None, "tray.jpg", fixture_stream()
        )

    assert preexisting_original.read_bytes() == b"existing original"
    assert preexisting_thumbnail.read_bytes() == b"existing thumbnail"
    assert [path for path in settings.originals_dir.rglob("*") if path.is_file()] == [
        preexisting_original
    ]
    assert [
        path for path in settings.thumbnails_dir.rglob("*") if path.is_file()
    ] == [preexisting_thumbnail]


def test_disk_space_probe_reserves_space_after_accepting_maximum_file(
    tmp_path: Path, monkeypatch
) -> None:
    class Usage:
        total = 20_000
        used = 5_000
        free = 15_000

    monkeypatch.setattr("shutil.disk_usage", lambda _path: Usage())
    probe = DiskSpaceProbe(tmp_path)

    assert probe.can_accept(byte_limit=5_000, reserve_bytes=10_000)
    assert not probe.can_accept(byte_limit=5_001, reserve_bytes=10_000)


def test_image_repository_does_not_report_non_duplicate_integrity_errors_as_duplicates(
    session: Session,
) -> None:
    repository = ImageRepository(session)

    with pytest.raises(IntegrityError):
        repository.create(
            brand_id="missing-brand",
            kind=ImageKind.TRAY,
            product_id=None,
            storage_key="missing/original.jpg",
            thumbnail_storage_key="missing/thumbnail.webp",
            original_filename="tray.jpg",
            mime_type="image/jpeg",
            width=640,
            height=320,
            byte_size=100,
            sha256="a" * 64,
            labeling_status=LabelingStatus.UNLABELED,
        )


@pytest.mark.parametrize(
    ("detail", "expected_exception"),
    [
        (
            "UNIQUE constraint failed: images.brand_id, images.sha256",
            DuplicateImage,
        ),
        ("FOREIGN KEY constraint failed", IntegrityError),
    ],
)
def test_commit_only_translates_the_image_brand_hash_unique_violation(
    detail: str, expected_exception: type[Exception]
) -> None:
    class CommitFailingSession:
        def commit(self) -> None:
            raise IntegrityError("commit", {}, sqlite3.IntegrityError(detail))

    repository = ImageRepository(CommitFailingSession())  # type: ignore[arg-type]

    with pytest.raises(expected_exception):
        repository.commit()
