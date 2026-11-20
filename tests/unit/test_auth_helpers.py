"""鉴权辅助函数测试（不访问数据库）。"""

from __future__ import annotations

import pytest

from app.dependencies import _parse_bearer_token, _require_header
from app.errors import AppError


def test_parse_bearer_token_ok() -> None:
    assert _parse_bearer_token("Bearer CUS00000001") == "CUS00000001"
    assert _parse_bearer_token("Bearer   EMP000001  ") == "EMP000001"


@pytest.mark.parametrize("value", [None, "", "   ", "Basic abc", "Bearer   "])
def test_parse_bearer_token_invalid(value: str | None) -> None:
    with pytest.raises(AppError) as exc_info:
        _parse_bearer_token(value)
    assert exc_info.value.status_code == 401


def test_require_header_trims() -> None:
    assert _require_header("  MOBILE_BANK ", "X-Channel-Code") == "MOBILE_BANK"


def test_require_header_missing() -> None:
    with pytest.raises(AppError) as exc_info:
        _require_header(None, "X-Channel-Code")
    assert exc_info.value.code == "MISSING_HEADER"
