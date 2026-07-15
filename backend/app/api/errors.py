from pydantic import BaseModel


class ApiError(BaseModel):
    code: str
    message: str
    action: str | None = None
    field_errors: dict[str, str] | None = None
