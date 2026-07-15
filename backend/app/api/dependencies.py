from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.catalog import CatalogService
from backend.app.infrastructure.catalog_repository import CatalogRepository
from backend.app.infrastructure.database import session_scope


def get_session(request: Request) -> Iterator[Session]:
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_scope(session_factory) as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]


def get_catalog_service(session: SessionDependency) -> CatalogService:
    return CatalogService(CatalogRepository(session))


CatalogServiceDependency = Annotated[CatalogService, Depends(get_catalog_service)]
