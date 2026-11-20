"""幂等控制单元测试。"""

from __future__ import annotations

import pytest

from app.errors import AppError
from app.idempotency import _RECORDS, idempotent_result, save_idempotent_result


@pytest.fixture(autouse=True)
def clear_records():
    _RECORDS.clear()
    yield
    _RECORDS.clear()


def test_first_request_returns_none() -> None:
    assert idempotent_result("CH", "account", "REQ1", {"a": 1}) is None


def test_replay_returns_saved_response() -> None:
    payload = {"customer_no": "C1", "amount": "100.00"}
    save_idempotent_result("CH", "loan", "REQ2", payload, {"code": 0})
    assert idempotent_result("CH", "loan", "REQ2", payload) == {"code": 0}


def test_payload_mismatch_raises_conflict() -> None:
    save_idempotent_result("CH", "loan", "REQ3", {"amount": "100"}, {"code": 0})
    with pytest.raises(AppError) as exc_info:
        idempotent_result("CH", "loan", "REQ3", {"amount": "200"})
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "IDEMPOTENCY_PAYLOAD_MISMATCH"


def test_business_type_isolation() -> None:
    save_idempotent_result("CH", "account", "REQ4", {"x": 1}, {"code": 0})
    # 同一个幂等号在另一个业务类型下应当是全新的请求
    assert idempotent_result("CH", "loan", "REQ4", {"x": 1}) is None


def test_channel_isolation() -> None:
    save_idempotent_result("CH1", "loan", "REQ5", {"x": 1}, {"code": 0})
    assert idempotent_result("CH2", "loan", "REQ5", {"x": 1}) is None


def test_hash_ignores_dict_order() -> None:
    save_idempotent_result("CH", "loan", "REQ6", {"a": 1, "b": 2}, {"code": 0})
    assert idempotent_result("CH", "loan", "REQ6", {"b": 2, "a": 1}) == {"code": 0}
