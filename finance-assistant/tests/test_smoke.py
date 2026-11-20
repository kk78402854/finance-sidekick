"""冒烟测试：保证 CI 在业务测试补齐前也能验证客服工程可导入、映射正确。"""

from __future__ import annotations

from types import SimpleNamespace

from assistant.domain.object_slots import can_fill_slot, object_slot_values


def test_object_slot_mapping_smoke() -> None:
    assert can_fill_slot("account", "account_no") is True
    assert can_fill_slot("account", "card_no") is False

    focused = SimpleNamespace(type="card", id="6222", attributes={"account_no": "ACC1"})
    assert object_slot_values(focused) == {"card_no": "6222", "account_no": "ACC1"}
    assert object_slot_values(None) == {}
