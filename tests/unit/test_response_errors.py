"""统一响应体与错误对象单元测试。"""

from __future__ import annotations

from app.errors import AppError, bad_request, conflict, forbidden, not_found, unauthorized
from app.response import fail, ok


def test_ok_shape() -> None:
    body = ok({"x": 1}, "req-1")
    assert body == {"code": 0, "message": "ok", "request_id": "req-1", "data": {"x": 1}}


def test_fail_shape() -> None:
    body = fail("SOME_CODE", "失败", "req-2")
    assert body["code"] == "SOME_CODE"
    assert body["data"] is None
    assert body["request_id"] == "req-2"


def test_error_factories() -> None:
    cases = [
        (bad_request("C", "m"), 400),
        (unauthorized("C", "m"), 401),
        (forbidden("C", "m"), 403),
        (not_found("C", "m"), 404),
        (conflict("C", "m"), 409),
    ]
    for error, expected_status in cases:
        assert isinstance(error, AppError)
        assert error.status_code == expected_status
        assert str(error) == "m"
