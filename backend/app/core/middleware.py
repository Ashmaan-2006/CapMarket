import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response


logger = logging.getLogger("app.request")


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid4())
    start_time = time.perf_counter()
    response: Response | None = None

    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        status_code = response.status_code if response else 500
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            request_id,
        )
        if response:
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-ms"] = f"{duration_ms:.2f}"
