from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.catalog import CatalogService
from backend.app.application.image_library import ImageLibraryService
from backend.app.application.image_upload import ImageUploadService
from backend.app.infrastructure.file_storage import LocalFileStorage
from backend.app.infrastructure.catalog_repository import CatalogRepository
from backend.app.infrastructure.database import session_scope
from backend.app.infrastructure.image_processor import ImageProcessor
from backend.app.infrastructure.image_repository import DiskSpaceProbe, ImageRepository


def get_session(request: Request) -> Iterator[Session]:
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_scope(session_factory) as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


def get_catalog_service(session: SessionDependency) -> CatalogService:
    return CatalogService(CatalogRepository(session))


CatalogServiceDependency = Annotated[CatalogService, Depends(get_catalog_service)]


def get_image_library_service(
    request: Request, session: SessionDependency
) -> ImageLibraryService:
    storage = LocalFileStorage(request.app.state.settings)
    return ImageLibraryService(
        catalog_repository=CatalogRepository(session),
        image_repository=ImageRepository(session),
        file_storage=storage,
    )


ImageLibraryServiceDependency = Annotated[
    ImageLibraryService, Depends(get_image_library_service)
]


def get_image_upload_service(
    request: Request, session: SessionDependency
) -> ImageUploadService:
    settings = request.app.state.settings
    return ImageUploadService(
        catalog_repository=CatalogRepository(session),
        image_repository=ImageRepository(session),
        file_storage=LocalFileStorage(settings),
        image_processor=ImageProcessor(),
        disk_space_probe=DiskSpaceProbe(settings.data_dir),
    )


ImageUploadServiceDependency = Annotated[
    ImageUploadService, Depends(get_image_upload_service)
]
