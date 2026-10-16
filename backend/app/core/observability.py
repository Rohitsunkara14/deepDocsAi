"""Request-local operational metrics; never retain content or credentials."""
from contextvars import ContextVar
import json
import logging
import re
from time import perf_counter
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send, Message

logger = logging.getLogger("uvicorn.error.deepdocs.requests")
request_metrics: ContextVar[dict | None] = ContextVar("request_metrics", default=None)


def record_metrics(**values: float | int | bool) -> None:
    metrics = request_metrics.get()
    if metrics is not None:
        metrics.update(values)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp, strategy: str, origins: list[str]) -> None:
        self.app, self.strategy, self.origins = app, strategy, origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        incoming = headers.get(b"x-request-id", b"").decode("ascii", errors="ignore")
        # Reject non-ASCII bytes rather than sanitizing two different IDs to the same value.
        valid = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", incoming)
        request_id = incoming if valid and incoming.encode() == headers.get(b"x-request-id") else str(uuid4())
        metrics: dict = {"request_id": request_id}
        token = request_metrics.set(metrics)
        started, status, sent = perf_counter(), 500, False

        async def send_with_id(message: Message) -> None:
            nonlocal status, sent
            if message["type"] == "http.response.start":
                status, sent = message["status"], True
                message["headers"] = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"] + [(b"x-request-id", request_id.encode())]
            await send(message)
        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            status = 500
            if not sent:
                safe_headers = {}
                origin = headers.get(b"origin", b"").decode("latin-1")
                if origin in self.origins:
                    safe_headers = {"Access-Control-Allow-Origin": origin, "Vary": "Origin", "Access-Control-Expose-Headers": "X-Request-ID"}
                await JSONResponse({"detail": "Internal server error. Use X-Request-ID when reporting this issue."}, status_code=500, headers=safe_headers)(scope, receive, send_with_id)
            # Do not emit exception messages/tracebacks that can contain private inputs.
        finally:
            route = scope.get("route")
            logger.info(json.dumps({"event": "http_request", **metrics,
                "path": getattr(route, "path", "<unmatched>"),
                "method": scope["method"] if scope["method"] in {"GET", "POST", "OPTIONS", "HEAD", "PUT", "DELETE", "PATCH"} else "OTHER",
                "status": status, "success": status < 400,
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                "retrieval_strategy": self.strategy}))
            request_metrics.reset(token)
