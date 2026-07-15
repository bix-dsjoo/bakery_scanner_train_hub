from datetime import datetime
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from backend.app.api.dependencies import CatalogServiceDependency


router = APIRouter(prefix="/api/v1", tags=["catalog"])

Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
ProductCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
]
CatalogStatus = Literal["ACTIVE", "INACTIVE"]
DeactivationStatus = Literal["INACTIVE"]


class BrandCreate(BaseModel):
    name: Name


class BrandPatch(BaseModel):
    name: Name | None = None
    status: DeactivationStatus | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.name is None and self.status is None:
            raise ValueError("변경할 브랜드 정보를 입력해 주세요.")
        return self


class ProductCreate(BaseModel):
    code: ProductCode
    name: Name


class ProductPatch(BaseModel):
    code: ProductCode | None = None
    name: Name | None = None
    status: DeactivationStatus | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.code is None and self.name is None and self.status is None:
            raise ValueError("변경할 상품 정보를 입력해 주세요.")
        return self


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: CatalogStatus
    created_at: datetime
    updated_at: datetime


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brand_id: str
    code: str
    name: str
    status: CatalogStatus
    created_at: datetime
    updated_at: datetime


@router.post(
    "/brands",
    response_model=BrandResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_brand(
    request: BrandCreate, service: CatalogServiceDependency
) -> BrandResponse:
    return BrandResponse.model_validate(service.create_brand(request.name))


@router.get("/brands", response_model=list[BrandResponse])
def list_brands(
    service: CatalogServiceDependency,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    query: str | None = None,
) -> list[BrandResponse]:
    return [
        BrandResponse.model_validate(brand)
        for brand in service.list_brands(status=status_filter, query=query)
    ]


@router.patch("/brands/{brand_id}", response_model=BrandResponse)
def patch_brand(
    brand_id: str,
    request: BrandPatch,
    service: CatalogServiceDependency,
) -> BrandResponse:
    if request.name is not None:
        brand = service.update_brand(brand_id, request.name)
    else:
        brand = service.deactivate_brand(brand_id)
    if request.status == "INACTIVE" and brand.status != "INACTIVE":
        brand = service.deactivate_brand(brand_id)
    return BrandResponse.model_validate(brand)


@router.post(
    "/brands/{brand_id}/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    brand_id: str,
    request: ProductCreate,
    service: CatalogServiceDependency,
) -> ProductResponse:
    return ProductResponse.model_validate(
        service.create_product(brand_id, request.code, request.name)
    )


@router.get(
    "/brands/{brand_id}/products",
    response_model=list[ProductResponse],
)
def list_products(
    brand_id: str,
    service: CatalogServiceDependency,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    query: str | None = None,
) -> list[ProductResponse]:
    return [
        ProductResponse.model_validate(product)
        for product in service.list_products(
            brand_id, status=status_filter, query=query
        )
    ]


@router.patch(
    "/brands/{brand_id}/products/{product_id}",
    response_model=ProductResponse,
)
def patch_product(
    brand_id: str,
    product_id: str,
    request: ProductPatch,
    service: CatalogServiceDependency,
) -> ProductResponse:
    if request.code is not None or request.name is not None:
        product = service.update_product(
            brand_id,
            product_id,
            code=request.code,
            name=request.name,
        )
    else:
        product = service.deactivate_product(brand_id, product_id)
    if request.status == "INACTIVE" and product.status != "INACTIVE":
        product = service.deactivate_product(brand_id, product_id)
    return ProductResponse.model_validate(product)
