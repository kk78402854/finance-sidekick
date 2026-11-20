"""FastAPI entrypoint."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import pymysql
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .audit import ensure_audit_table
from .config import APP_PORT
from .errors import AppError
from .logging_config import configure_logging, get_request_id
from .metrics import metrics
from .middleware import MetricsMiddleware, RateLimitMiddleware, RequestContextMiddleware
from .response import fail
from .routers.accounts import router as accounts_router
from .routers.collections import router as collections_router
from .routers.customers import router as customers_router
from .routers.foundation import router as foundation_router
from .routers.loans import router as loans_router
from .routers.operations import router as operations_router
from .routers.repayments import router as repayments_router
from .routers.risk import router as risk_router
from .routers.wealth import router as wealth_router

OPENAPI_TAGS = [
    {"name": "foundation", "description": "基础配置接口"},
    {"name": "customers", "description": "客户接口"},
    {"name": "accounts", "description": "账户与交易接口"},
    {"name": "wealth", "description": "理财接口"},
    {"name": "loans", "description": "信贷接口"},
    {"name": "repayments", "description": "还款与逾期接口"},
    {"name": "risk", "description": "风控与反洗钱接口"},
    {"name": "collections", "description": "催收接口"},
    {"name": "operations", "description": "运营支撑接口"},
]

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 审计表是旁路能力，建表失败不阻止服务启动
    ensure_audit_table()
    yield


app = FastAPI(title="Finance Data API", version="0.1.0", openapi_tags=OPENAPI_TAGS, lifespan=lifespan)

# 注册顺序与执行顺序相反：最后注册的最外层
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)

app.include_router(foundation_router)
app.include_router(customers_router)
app.include_router(accounts_router)
app.include_router(wealth_router)
app.include_router(loans_router)
app.include_router(repayments_router)
app.include_router(risk_router)
app.include_router(collections_router)
app.include_router(operations_router)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(exc.code, exc.message, get_request_id()),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # 只返回字段路径与提示，避免把内部异常对象直接序列化给调用方
    details = [
        {
            "loc": ".".join(str(part) for part in error.get("loc", ())),
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=fail("VALIDATION_ERROR", "请求参数校验失败", get_request_id())
        | {"details": details},
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """404/405 也使用统一响应体；其余 HTTP 异常保留 FastAPI 默认语义。"""
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "接口不存在", get_request_id()),
        )
    if exc.status_code == 405:
        return JSONResponse(
            status_code=405,
            content=fail("METHOD_NOT_ALLOWED", "请求方法不被允许", get_request_id()),
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=fail("BAD_REQUEST", str(exc), get_request_id()),
    )


@app.exception_handler(pymysql.err.OperationalError)
async def handle_db_error(request: Request, exc: pymysql.err.OperationalError) -> JSONResponse:
    # 数据库不可用时返回 503，调用方可按“稍后重试”处理
    return JSONResponse(
        status_code=503,
        content=fail("DEPENDENCY_UNAVAILABLE", "数据库暂不可用，请稍后重试", get_request_id()),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # ServerErrorMiddleware 会保留堆栈日志；这里只负责给调用方统一的 500 结构
    return JSONResponse(
        status_code=500,
        content=fail("INTERNAL_ERROR", "服务内部异常，请稍后重试", get_request_id()),
    )


@app.get("/health", summary="健康检查")
def health() -> dict[str, object]:
    return {"code": 0, "message": "ok", "request_id": get_request_id(), "data": {"status": "ok"}}


@app.get("/metrics", summary="Prometheus 指标", include_in_schema=False)
def prometheus_metrics() -> PlainTextResponse:
    if os.getenv("METRICS_ENABLED", "1") == "0":
        return PlainTextResponse("metrics disabled\n", status_code=404)
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4; charset=utf-8")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=APP_PORT, reload=False)
