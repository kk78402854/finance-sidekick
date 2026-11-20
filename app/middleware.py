"""HTTP 中间件：请求追踪、访问日志、指标、限流、审计。

顺序（由外到内）：RequestContext → RateLimit → Metrics → 路由。
最外层生成 request_id，保证 429 等提前返回的响应也带追踪号。
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from .audit import WRITE_METHODS, build_audit_entry, record_audit
from .logging_config import request_id_ctx
from .metrics import metrics
from .rate_limit import SlidingWindowLimiter, limiter_from_env

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-Id"
# 允许字母、数字与少量分隔符，避免日志注入和超长 header
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_AUDIT_PATH_PREFIX = "/api/v1"


def _resolve_request_id(incoming: str | None) -> str:
    """调用方传入合法 ID 则复用，否则生成新的。"""
    if incoming and _REQUEST_ID_PATTERN.match(incoming):
        return incoming
    return uuid.uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    """注入 request_id、输出访问日志、旁路记录写操作审计。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response: Response | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        except Exception:
            # 交给上层异常处理器，但要先记一条带堆栈的日志
            logger.exception(
                "http_unhandled_exception",
                extra={"method": request.method, "path": request.url.path},
            )
            raise
        finally:
            try:
                duration_ms = (time.perf_counter() - started) * 1000
                logger.info(
                    "http_access",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 3),
                    },
                )
                if request.method.upper() in WRITE_METHODS and request.url.path.startswith(_AUDIT_PATH_PREFIX):
                    # 显式传入解析后的 ID：客户端未带请求头时，审计记录也要能对上响应头
                    await record_audit(
                        build_audit_entry(request, status_code, duration_ms, request_id=request_id)
                    )
            finally:
                # 无论日志/审计是否异常，都必须释放上下文，避免 request_id 串到后续请求
                request_id_ctx.reset(token)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """写接口按主体限流，读接口不限制。"""

    def __init__(self, app, limiter: SlidingWindowLimiter | None = None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.limiter = limiter or limiter_from_env()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method.upper() not in WRITE_METHODS or self.limiter.limit <= 0:
            return await call_next(request)

        key = _client_key(request)
        allowed, remaining = self.limiter.allow(key)
        if not allowed:
            metrics.inc("rate_limited_total", {"path": request.url.path})
            logger.warning(
                "rate_limited",
                extra={"method": request.method, "path": request.url.path},
            )
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMITED",
                    "message": "请求过于频繁，请稍后重试",
                    "request_id": request_id_ctx.get(),
                    "data": None,
                },
                headers={"Retry-After": "60", "X-RateLimit-Remaining": "0"},
            )

        response = await call_next(request)
        if remaining >= 0:
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """记录请求量、状态码与耗时分布。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        route = request.scope.get("route")
        path = getattr(route, "path", None) or "unmatched"
        metrics.observe_http(
            method=request.method,
            path=str(path),
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


def _client_key(request: Request) -> str:
    """有登录凭证时按凭证摘要限流，否则按客户端 IP。

    注意不要把明文 token 当字典键：限流器是长期驻留的内存对象，
    明文凭证不应进入内存键空间。
    """
    authorization = request.headers.get("Authorization")
    if authorization:
        digest = hashlib.sha256(authorization.strip().encode("utf-8")).hexdigest()[:16]
        return f"token:{digest}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"
