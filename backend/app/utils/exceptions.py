"""
app/utils/exceptions.py

Custom application exceptions and FastAPI exception handlers.
All handlers return a consistent ErrorResponse envelope.
Register handlers by calling register_exception_handlers(app).
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.common import ErrorDetail, ErrorResponse


# ── Domain Exceptions ─────────────────────────────────────────────────────────

class AppException(Exception):
    """Base class for all application-level HTTP exceptions."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: object = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class InvalidCredentialsError(AppException):
    def __init__(self, message: str = "Invalid username or password.") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message=message,
        )


class InvalidTokenError(AppException):
    def __init__(self, message: str = "Invalid or expired token.") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_TOKEN",
            message=message,
        )


class ForbiddenError(AppException):
    def __init__(
        self, message: str = "You do not have permission to perform this action."
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=message,
        )


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"{resource} not found.",
        )


class ConflictError(AppException):
    def __init__(self, message: str = "Resource already exists.") -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
            message=message,
        )


# ── Exception Handlers ────────────────────────────────────────────────────────

def _error_response(code: str, message: str, details: object = None) -> dict:
    return ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details)
    ).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app instance."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_response(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        for err in errors:
            if 'input' in err and isinstance(err['input'], bytes):
                err['input'] = '<bytes>'
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_response(
                code="VALIDATION_ERROR",
                message="Request validation failed.",
                details=errors,
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_exception_handler(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_response(
                code="DATABASE_ERROR",
                message="A database error occurred. Please try again later.",
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_response(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
            ),
        )
