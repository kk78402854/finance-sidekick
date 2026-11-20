"""审计字段与脱敏逻辑测试。"""

from __future__ import annotations

from starlette.requests import Request

from app.audit import build_audit_entry, mask_principal


def _make_request(method: str = "POST") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "path": "/api/v1/customers",
            "raw_path": b"/api/v1/customers",
            "query_string": b"",
            "headers": [
                (b"authorization", b"Bearer CUS00000001"),
                (b"x-request-id", b"trace-1"),
                (b"x-channel-code", b"MOBILE_BANK"),
                (b"x-operator-no", b"EMP000001"),
            ],
        }
    )


def test_mask_principal_never_returns_plaintext() -> None:
    masked = mask_principal("Bearer CUS00000001")
    assert masked is not None
    assert "CUS00000001" not in masked
    assert len(masked) == 16


def test_mask_principal_handles_missing_values() -> None:
    assert mask_principal(None) is None
    assert mask_principal("") is None
    assert mask_principal("Bearer   ") is None


def test_build_audit_entry_fields() -> None:
    entry = build_audit_entry(_make_request(), status_code=201, duration_ms=12.6)
    assert entry["request_id"] == "trace-1"
    assert entry["method"] == "POST"
    assert entry["path"] == "/api/v1/customers"
    assert entry["status_code"] == 201
    assert entry["channel_code"] == "MOBILE_BANK"
    assert entry["operator_no"] == "EMP000001"
    assert entry["client_ip"] == "127.0.0.1"
    assert entry["duration_ms"] == 12
    assert entry["principal_hash"] and len(entry["principal_hash"]) == 16


def test_build_audit_entry_prefers_resolved_request_id() -> None:
    """客户端未带请求头时，审计要用中间件生成的那个 ID，保证与响应头一致。"""
    entry = build_audit_entry(_make_request(), status_code=200, duration_ms=1.0, request_id="generated-id")
    assert entry["request_id"] == "generated-id"
