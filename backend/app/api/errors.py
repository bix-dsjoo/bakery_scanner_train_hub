import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from backend.app.domain.catalog import (
    CatalogConflict,
    CatalogError,
    CatalogNotFound,
    CatalogValidationError,
)
from backend.app.application.image_library import ImageLibraryError
from backend.app.application.image_upload import ImageUploadError


logger = logging.getLogger(__name__)


class ApiError(BaseModel):
    code: str
    message: str
    action: str | None = None
    field_errors: dict[str, str] | None = None


def _response(
    status_code: int,
    error: ApiError,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(exclude_none=True),
        headers=headers,
    )


def _catalog_response(status_code: int, error: CatalogError) -> JSONResponse:
    return _response(
        status_code,
        ApiError(
            code=error.code,
            message=error.message,
            action=error.action,
            field_errors=error.field_errors,
        ),
    )


def _validation_field_errors(error: RequestValidationError) -> dict[str, str]:
    field_errors: dict[str, str] = {}
    for detail in error.errors():
        location = detail.get("loc", ())
        field = str(location[-1]) if len(location) > 1 else "body"
        error_type = detail.get("type")
        context = detail.get("ctx") or {}
        if error_type == "missing":
            message = "필수 입력값이에요."
        elif error_type == "string_too_long":
            message = f"문자열은 {context.get('max_length')}자 이하여야 해요."
        elif error_type == "string_too_short":
            message = f"문자열은 {context.get('min_length')}자 이상이어야 해요."
        elif error_type == "literal_error":
            message = "허용된 값만 입력해 주세요."
        elif error_type == "json_invalid":
            field = "body"
            message = "요청 본문 JSON 형식을 확인해 주세요."
        else:
            message = "입력값을 확인해 주세요."
        field_errors[field] = message
    return field_errors


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ImageLibraryError)
    async def image_library_handler(
        _request: Request, error: ImageLibraryError
    ) -> JSONResponse:
        return _response(
            error.status_code,
            ApiError(
                code=error.code,
                message=error.message,
                action=error.action,
                field_errors=error.field_errors,
            ),
        )

    @app.exception_handler(ImageUploadError)
    async def image_upload_handler(
        _request: Request, error: ImageUploadError
    ) -> JSONResponse:
        status_code = 409 if error.code == "IMAGE_DUPLICATE" else 422
        if error.code == "DISK_SPACE_LOW":
            status_code = 507
        return _response(
            status_code,
            ApiError(code=error.code, message=error.message, action=error.action),
        )

    @app.exception_handler(CatalogConflict)
    async def catalog_conflict_handler(
        _request: Request, error: CatalogConflict
    ) -> JSONResponse:
        return _catalog_response(409, error)

    @app.exception_handler(CatalogNotFound)
    async def catalog_not_found_handler(
        _request: Request, error: CatalogNotFound
    ) -> JSONResponse:
        return _catalog_response(404, error)

    @app.exception_handler(CatalogValidationError)
    async def catalog_validation_handler(
        _request: Request, error: CatalogValidationError
    ) -> JSONResponse:
        return _catalog_response(422, error)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return _response(
            422,
            ApiError(
                code="REQUEST_VALIDATION_ERROR",
                message="입력값을 확인해 주세요.",
                action="오류가 표시된 항목을 수정해 주세요.",
                field_errors=_validation_field_errors(error),
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        _request: Request, error: HTTPException
    ) -> JSONResponse:
        if error.status_code == 404:
            api_error = ApiError(
                code="HTTP_NOT_FOUND",
                message="요청한 API를 찾을 수 없어요.",
                action="요청 주소를 확인해 주세요.",
            )
        elif error.status_code == 405:
            api_error = ApiError(
                code="HTTP_METHOD_NOT_ALLOWED",
                message="이 요청 방식은 사용할 수 없어요.",
                action="요청 방식을 확인해 주세요.",
            )
        else:
            api_error = ApiError(
                code=f"HTTP_{error.status_code}",
                message="요청을 처리할 수 없어요.",
                action="요청 내용을 확인해 주세요.",
            )
        return _response(error.status_code, api_error, headers=error.headers)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request, error: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled API error for %s %s",
            request.method,
            request.url.path,
            exc_info=error,
        )
        return _response(
            500,
            ApiError(
                code="INTERNAL_SERVER_ERROR",
                message="서버에서 요청을 처리하지 못했어요.",
                action="잠시 후 다시 시도해 주세요.",
            ),
        )
