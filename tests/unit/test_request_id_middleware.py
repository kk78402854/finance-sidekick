"""请求 ID 中间件与指标端点测试。"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app import dependencies
from app.logging_config import request_id_ctx
from app.main import app

HEX_ID = re.compile(r"^[0-9a-f]{32}$")


def test_request_id_generated_when_missing() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    header_id = response.headers.get("X-Request-Id")
    assert header_id and HEX_ID.match(header_id)
    assert response.json()["request_id"] == header_id


def test_request_id_passthrough() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-Id": "trace-abc_123"})
    assert response.headers["X-Request-Id"] == "trace-abc_123"
    assert response.json()["request_id"] == "trace-abc_123"


def test_invalid_request_id_is_replaced() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-Id": "bad id!!"})
    header_id = response.headers["X-Request-Id"]
    assert header_id != "bad id!!"
    assert HEX_ID.match(header_id)


def test_overlong_request_id_is_replaced() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-Id": "a" * 100})
    assert HEX_ID.match(response.headers["X-Request-Id"])


def test_metrics_endpoint_exposes_series() -> None:
    with TestClient(app) as client:
        client.get("/health")
        response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration_ms_bucket" in body
    assert 'path="/health"' in body


def test_request_context_uses_resolved_request_id(monkeypatch) -> None:
    """业务响应体里的 request_id 要与中间件生成/透传的 ID 一致。"""
    monkeypatch.setattr(dependencies, "_ensure_channel", lambda code: None)
    monkeypatch.setattr(
        dependencies,
        "fetch_one",
        lambda sql, params: {"customer_no": params[0], "customer_status": "active"},
    )
    token = request_id_ctx.set("generated-id")
    try:
        ctx = dependencies.get_request_context(
            authorization="Bearer CUS00000001",
            x_channel_code="MOBILE_BANK",
        )
    finally:
        request_id_ctx.reset(token)
    assert ctx.request_id == "generated-id"
