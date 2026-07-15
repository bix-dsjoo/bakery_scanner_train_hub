from typing import Protocol

from backend.app.domain.catalog import (
    Brand,
    CatalogConflict,
    CatalogNotFound,
    CatalogValidationError,
    DuplicateCatalogValue,
    Product,
)


class CatalogRepositoryProtocol(Protocol):
    def create_brand(self, name: str) -> Brand: ...
    def get_brand(self, brand_id: str) -> Brand | None: ...
    def update_brand(self, brand_id: str, *, name: str) -> Brand | None: ...
    def set_brand_status(self, brand_id: str, status: str) -> Brand | None: ...
    def list_brands(self, *, status: str | None, query: str | None) -> list[Brand]: ...
    def create_product(self, brand_id: str, code: str, name: str) -> Product: ...
    def get_product(self, brand_id: str, product_id: str) -> Product | None: ...
    def update_product(
        self, brand_id: str, product_id: str, *, code: str, name: str
    ) -> Product | None: ...
    def set_product_status(
        self, brand_id: str, product_id: str, status: str
    ) -> Product | None: ...
    def list_products(
        self, brand_id: str, *, status: str | None, query: str | None
    ) -> list[Product]: ...


class CatalogService:
    def __init__(self, repository: CatalogRepositoryProtocol) -> None:
        self._repository = repository

    def create_brand(self, name: str) -> Brand:
        normalized_name = self._required(name, "name")
        try:
            return self._repository.create_brand(normalized_name)
        except DuplicateCatalogValue as error:
            raise self._brand_name_conflict() from error

    def update_brand(self, brand_id: str, name: str) -> Brand:
        normalized_name = self._required(name, "name")
        try:
            brand = self._repository.update_brand(brand_id, name=normalized_name)
        except DuplicateCatalogValue as error:
            raise self._brand_name_conflict() from error
        if brand is None:
            raise self._brand_not_found()
        return brand

    def deactivate_brand(self, brand_id: str) -> Brand:
        brand = self._repository.set_brand_status(brand_id, "INACTIVE")
        if brand is None:
            raise self._brand_not_found()
        return brand

    def create_product(self, brand_id: str, code: str, name: str) -> Product:
        self._require_brand(brand_id)
        normalized_code = self._required(code, "code")
        normalized_name = self._required(name, "name")
        try:
            return self._repository.create_product(
                brand_id, normalized_code, normalized_name
            )
        except DuplicateCatalogValue as error:
            raise self._product_code_conflict() from error

    def update_product(
        self,
        brand_id: str,
        product_id: str,
        *,
        code: str | None = None,
        name: str | None = None,
    ) -> Product:
        self._require_brand(brand_id)
        existing = self._repository.get_product(brand_id, product_id)
        if existing is None:
            raise self._product_not_found()
        normalized_code = existing.code if code is None else self._required(code, "code")
        normalized_name = existing.name if name is None else self._required(name, "name")
        try:
            product = self._repository.update_product(
                brand_id,
                product_id,
                code=normalized_code,
                name=normalized_name,
            )
        except DuplicateCatalogValue as error:
            raise self._product_code_conflict() from error
        if product is None:
            raise self._product_not_found()
        return product

    def deactivate_product(self, brand_id: str, product_id: str) -> Product:
        self._require_brand(brand_id)
        product = self._repository.set_product_status(
            brand_id, product_id, "INACTIVE"
        )
        if product is None:
            raise self._product_not_found()
        return product

    def list_brands(
        self, status: str | None = None, query: str | None = None
    ) -> list[Brand]:
        return self._repository.list_brands(
            status=self._optional_status(status),
            query=self._optional_query(query),
        )

    def list_products(
        self,
        brand_id: str,
        status: str | None = None,
        query: str | None = None,
    ) -> list[Product]:
        self._require_brand(brand_id)
        return self._repository.list_products(
            brand_id,
            status=self._optional_status(status),
            query=self._optional_query(query),
        )

    def _require_brand(self, brand_id: str) -> Brand:
        brand = self._repository.get_brand(brand_id)
        if brand is None:
            raise self._brand_not_found()
        return brand

    @staticmethod
    def _required(value: str, field: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise CatalogValidationError(
                code="CATALOG_FIELD_REQUIRED",
                message="필수 입력값을 확인해 주세요.",
                action="비어 있는 항목을 입력해 주세요.",
                field_errors={field: f"{field} 값은 비워 둘 수 없어요."},
            )
        return normalized

    @staticmethod
    def _optional_query(query: str | None) -> str | None:
        if query is None:
            return None
        normalized = query.strip()
        return normalized or None

    @staticmethod
    def _optional_status(status: str | None) -> str | None:
        if status is None:
            return None
        normalized = status.strip().upper()
        if normalized not in {"ACTIVE", "INACTIVE"}:
            raise CatalogValidationError(
                code="CATALOG_STATUS_INVALID",
                message="상태 값을 확인해 주세요.",
                action="활성 또는 비활성 상태를 선택해 주세요.",
                field_errors={"status": "ACTIVE 또는 INACTIVE만 사용할 수 있어요."},
            )
        return normalized

    @staticmethod
    def _brand_name_conflict() -> CatalogConflict:
        return CatalogConflict(
            code="BRAND_NAME_DUPLICATE",
            message="이미 등록된 브랜드 이름이에요.",
            action="다른 브랜드 이름을 입력해 주세요.",
            field_errors={"name": "이미 사용 중인 이름이에요."},
        )

    @staticmethod
    def _product_code_conflict() -> CatalogConflict:
        return CatalogConflict(
            code="PRODUCT_CODE_DUPLICATE",
            message="같은 브랜드에 이미 등록된 상품 코드예요.",
            action="다른 상품 코드를 입력해 주세요.",
            field_errors={"code": "이미 사용 중인 코드예요."},
        )

    @staticmethod
    def _brand_not_found() -> CatalogNotFound:
        return CatalogNotFound(
            code="BRAND_NOT_FOUND",
            message="브랜드를 찾을 수 없어요.",
            action="브랜드 목록을 새로고침해 주세요.",
        )

    @staticmethod
    def _product_not_found() -> CatalogNotFound:
        return CatalogNotFound(
            code="PRODUCT_NOT_FOUND",
            message="상품을 찾을 수 없어요.",
            action="상품 목록을 새로고침해 주세요.",
        )
