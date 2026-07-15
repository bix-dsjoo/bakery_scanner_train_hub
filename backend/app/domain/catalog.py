from dataclasses import dataclass
from datetime import datetime
from typing import Literal


CatalogStatus = Literal["ACTIVE", "INACTIVE"]


@dataclass(frozen=True)
class Brand:
    id: str
    name: str
    status: CatalogStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Product:
    id: str
    brand_id: str
    code: str
    name: str
    status: CatalogStatus
    created_at: datetime
    updated_at: datetime


class CatalogError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        action: str | None = None,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.action = action
        self.field_errors = field_errors


class CatalogConflict(CatalogError):
    pass


class CatalogNotFound(CatalogError):
    pass


class CatalogValidationError(CatalogError):
    pass


class DuplicateCatalogValue(Exception):
    """Persistence-level uniqueness signal translated by the application service."""

    def __init__(self, field: Literal["brand_name", "product_code"]) -> None:
        super().__init__(field)
        self.field = field
