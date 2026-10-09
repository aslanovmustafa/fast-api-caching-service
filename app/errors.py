import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI):
    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("Database operation failed", exc_info=exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable. Please try again."},
        )

    @app.exception_handler(OSError)
    async def storage_error(request: Request, exc: OSError):
        logger.error("Payload file operation failed", exc_info=exc)
        return JSONResponse(
            status_code=503, content={"detail": "Payload storage is unavailable."}
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error("Unexpected request failure", exc_info=exc)
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
