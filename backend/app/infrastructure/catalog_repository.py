from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.domain.catalog import Brand, DuplicateCatalogValue, Product
from backend.app.infrastructure.models import BrandModel, ProductModel


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_brand(self, name: str) -> Brand:
        model = BrandModel(name=name)
        self._change_unique(
            lambda: self._session.add(model),
            "brand_name",
        )
        return self._brand(model)

    def get_brand(self, brand_id: str) -> Brand | None:
        model = self._session.get(BrandModel, brand_id)
        return self._brand(model) if model is not None else None

    def update_brand(self, brand_id: str, *, name: str) -> Brand | None:
        model = self._session.get(BrandModel, brand_id)
        if model is None:
            return None
        self._change_unique(lambda: setattr(model, "name", name), "brand_name")
        return self._brand(model)

    def set_brand_status(self, brand_id: str, status: str) -> Brand | None:
        model = self._session.get(BrandModel, brand_id)
        if model is None:
            return None
        model.status = status
        self._session.flush()
        return self._brand(model)

    def list_brands(self, *, status: str | None, query: str | None) -> list[Brand]:
        statement: Select[tuple[BrandModel]] = select(BrandModel)
        if status is not None:
            statement = statement.where(BrandModel.status == status)
        if query is not None:
            statement = statement.where(
                func.lower(BrandModel.name).contains(query.lower())
            )
        statement = statement.order_by(BrandModel.created_at, BrandModel.id)
        return [self._brand(model) for model in self._session.scalars(statement)]

    def create_product(self, brand_id: str, code: str, name: str) -> Product:
        model = ProductModel(brand_id=brand_id, code=code, name=name)
        self._change_unique(
            lambda: self._session.add(model),
            "product_code",
        )
        return self._product(model)

    def get_product(self, brand_id: str, product_id: str) -> Product | None:
        model = self._session.scalar(
            select(ProductModel).where(
                ProductModel.id == product_id,
                ProductModel.brand_id == brand_id,
            )
        )
        return self._product(model) if model is not None else None

    def update_product(
        self,
        brand_id: str,
        product_id: str,
        *,
        code: str,
        name: str,
    ) -> Product | None:
        model = self._session.scalar(
            select(ProductModel).where(
                ProductModel.id == product_id,
                ProductModel.brand_id == brand_id,
            )
        )
        if model is None:
            return None
        def apply_changes() -> None:
            model.code = code
            model.name = name

        self._change_unique(apply_changes, "product_code")
        return self._product(model)

    def set_product_status(
        self, brand_id: str, product_id: str, status: str
    ) -> Product | None:
        model = self._session.scalar(
            select(ProductModel).where(
                ProductModel.id == product_id,
                ProductModel.brand_id == brand_id,
            )
        )
        if model is None:
            return None
        model.status = status
        self._session.flush()
        return self._product(model)

    def list_products(
        self,
        brand_id: str,
        *,
        status: str | None,
        query: str | None,
    ) -> list[Product]:
        statement: Select[tuple[ProductModel]] = select(ProductModel).where(
            ProductModel.brand_id == brand_id
        )
        if status is not None:
            statement = statement.where(ProductModel.status == status)
        if query is not None:
            lowered_query = query.lower()
            statement = statement.where(
                or_(
                    func.lower(ProductModel.code).contains(lowered_query),
                    func.lower(ProductModel.name).contains(lowered_query),
                )
            )
        statement = statement.order_by(ProductModel.created_at, ProductModel.id)
        return [self._product(model) for model in self._session.scalars(statement)]

    def _change_unique(
        self,
        change: Callable[[], None],
        field: Literal["brand_name", "product_code"],
    ) -> None:
        try:
            with self._session.begin_nested():
                change()
                self._session.flush()
        except IntegrityError as error:
            raise DuplicateCatalogValue(field) from error

    @staticmethod
    def _brand(model: BrandModel) -> Brand:
        return Brand(
            id=model.id,
            name=model.name,
            status=model.status,
            created_at=CatalogRepository._as_utc(model.created_at),
            updated_at=CatalogRepository._as_utc(model.updated_at),
        )

    @staticmethod
    def _product(model: ProductModel) -> Product:
        return Product(
            id=model.id,
            brand_id=model.brand_id,
            code=model.code,
            name=model.name,
            status=model.status,
            created_at=CatalogRepository._as_utc(model.created_at),
            updated_at=CatalogRepository._as_utc(model.updated_at),
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
