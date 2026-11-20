"""全局异常处理器测试：直接调用处理器，避免依赖真实数据库。"""

from __future__ import annotations

import asyncio
import json

import pymysql
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.errors import not_found
from app.main import (
    handle_app_error,
    handle_db_error,
    handle_http_exception,
    handle_unexpected_error,
    handle_validation_error,
    handle_value_error,
    health,
)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1),
            "path": "/api/v1/test",
            "raw_path": b"/api/v1/test",
            "query_string": b"",
            "headers": [(b"x-request-id", b"req-unit")],
        }
    )


def _body(response) -> dict:
    return json.loads(response.body)


def test_app_error_handler() -> None:
    response = asyncio.run(handle_app_error(_request(), not_found("CUSTOMER_NOT_FOUND", "客户不存在")))
    assert response.status_code == 404
    assert _body(response)["code"] == "CUSTOMER_NOT_FOUND"


def test_validation_error_handler_is_structured() -> None:
    exc = RequestValidationError(
        [{"loc": ("body", "sender_id"), "msg": "Field required", "type": "missing"}]
    )
    response = asyncio.run(handle_validation_error(_request(), exc))
    body = _body(response)
    assert response.status_code == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"][0]["loc"] == "body.sender_id"


def test_value_error_handler() -> None:
    response = asyncio.run(handle_value_error(_request(), ValueError("页码越界")))
    assert response.status_code == 400
    assert _body(response)["message"] == "页码越界"


def test_db_error_handler() -> None:
    exc = pymysql.err.OperationalError(2003, "Can't connect to MySQL server")
    response = asyncio.run(handle_db_error(_request(), exc))
    assert response.status_code == 503
    assert _body(response)["code"] == "DEPENDENCY_UNAVAILABLE"


def test_unexpected_error_handler() -> None:
    response = asyncio.run(handle_unexpected_error(_request(), RuntimeError("bug")))
    assert response.status_code == 500
    assert _body(response)["code"] == "INTERNAL_ERROR"


def test_health_payload() -> None:
    payload = health()
    assert payload["code"] == 0
    assert payload["data"] == {"status": "ok"}


def test_http_404_uses_unified_body() -> None:
    response = asyncio.run(
        handle_http_exception(_request(), StarletteHTTPException(status_code=404, detail="Not Found"))
    )
    body = _body(response)
    assert response.status_code == 404
    assert body["code"] == "NOT_FOUND"


def test_http_401_keeps_default_semantics() -> None:
    exc = StarletteHTTPException(status_code=401, detail="unauthorized", headers={"WWW-Authenticate": "Bearer"})
    response = asyncio.run(handle_http_exception(_request(), exc))
    assert response.status_code == 401
    assert _body(response)["detail"] == "unauthorized"
    assert response.headers["WWW-Authenticate"] == "Bearer"
