import logging
import re
import uuid
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class DuplicateIngestionJobError(Exception):
    """Raised when a pull request arrives while an ingestion job is already active."""

    def __init__(self, active_job_id: str, active_status: str) -> None:
        self.active_job_id = active_job_id
        self.active_status = active_status
        super().__init__(
            f"An ingestion job ({active_job_id}) is already {active_status.lower()}."
        )


class JobNotFoundError(Exception):
    """Raised when an ingestion job ID does not exist."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Ingestion job '{job_id}' was not found.")


class BSEUpstreamError(Exception):
    """Raised when the simulated BSE exchange feed encounters an upstream failure."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        self.retryable = retryable
        super().__init__(message)


def _request_id_from(request: Request) -> str:
    header_id: Optional[str] = request.headers.get("X-Request-ID")
    if header_id and _REQUEST_ID_PATTERN.match(header_id):
        return header_id
    return uuid.uuid4().hex[:12]


async def duplicate_job_exception_handler(
    request: Request, exc: DuplicateIngestionJobError
) -> JSONResponse:
    request_id = _request_id_from(request)
    return JSONResponse(
        status_code=409,
        content={
            "error": "ingestion_already_in_progress",
            "message": str(exc),
            "active_job_id": exc.active_job_id,
            "active_status": exc.active_status,
            "request_id": request_id,
        },
    )


async def job_not_found_exception_handler(
    request: Request, exc: JobNotFoundError
) -> JSONResponse:
    request_id = _request_id_from(request)
    return JSONResponse(
        status_code=404,
        content={
            "error": "job_not_found",
            "message": str(exc),
            "job_id": exc.job_id,
            "request_id": request_id,
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = _request_id_from(request)
    sanitized_errors = [
        {
            "field": ".".join(str(loc) for loc in err.get("loc", [])),
            "message": err.get("msg", "Invalid input"),
            "type": err.get("type", "validation_error"),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed.",
            "details": sanitized_errors,
            "request_id": request_id,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = _request_id_from(request)
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": detail,
            "request_id": request_id,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id_from(request)
    logger.exception(
        "Unhandled server exception",
        extra={"request_id": request_id, "path": str(request.url.path)},
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected internal error occurred. Please retry or contact support.",
            "request_id": request_id,
        },
    )
