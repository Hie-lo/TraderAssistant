import time
import uuid
import asyncio
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.exceptions import AppException
from app.core.logger import logger, TelegramLogNotifier


class GlobalErrorCatcherMiddleware(BaseHTTPMiddleware):
    """
    Middleware that catches all unhandled exceptions, logs them with a short trace ID,
    notifies the admin Telegram channel asynchronously with throttling,
    and returns a sanitized error message to the client.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = f"{process_time:.4f}s"
            return response
        except AppException as app_exc:
            # Domain-specific known application error
            return JSONResponse(
                status_code=app_exc.status_code,
                content={
                    "success": False,
                    "detail": app_exc.message,
                    "details": app_exc.details
                }
            )
        except Exception as exc:
            # Unhandled internal server error
            trace_id = uuid.uuid4().hex[:8]
            logger.exception(f"Unhandled server error [#{trace_id}] on {request.method} {request.url.path}: {exc}")

            # Non-blocking Telegram notification to admin channel
            asyncio.create_task(
                TelegramLogNotifier.notify_admin_channel(
                    trace_id=trace_id,
                    section=f"API / {request.method} {request.url.path}",
                    exc=exc,
                    user_info=f"IP: {request.client.host if request.client else 'Unknown'}",
                    extra_info=f"Query: {request.url.query}"
                )
            )

            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "detail": f"خطای داخلی سرور رخ داد. کد پیگیری: #{trace_id}"
                }
            )
