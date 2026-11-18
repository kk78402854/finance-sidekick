"""
对象消息与流程槽位的映射。

前端发送的业务对象（账户、银行卡、信用卡、交易、贷款）会被放进
state.shared.focused_object，collect 步骤可以直接从这里取值，
不需要用户再用文字重复输入。
"""

# 每种对象能填哪些槽位
OBJECT_SLOT_MAP: dict[str, set[str]] = {
    "account": {"account_no"},
    "card": {"card_no", "account_no"},
    "credit_card": {"credit_card_no"},
    "transaction": {"transaction_no", "related_transaction_no", "account_no"},
    "loan": {"loan_application_no"},
}


def can_fill_slot(object_type: str | None, slot_name: str) -> bool:
    """当前聚焦对象能否填这个槽位。"""
    return slot_name in OBJECT_SLOT_MAP.get(object_type or "", set())


def object_slot_values(focused_object) -> dict[str, str]:
    """把聚焦对象转换成可以写入任务槽位的字典。"""
    if focused_object is None:
        return {}

    object_type = focused_object.type
    attributes = focused_object.attributes or {}
    values: dict[str, str] = {}

    if object_type == "account":
        values["account_no"] = focused_object.id

    elif object_type == "card":
        values["card_no"] = focused_object.id
        if attributes.get("account_no"):
            values["account_no"] = attributes["account_no"]

    elif object_type == "credit_card":
        values["credit_card_no"] = focused_object.id

    elif object_type == "transaction":
        values["transaction_no"] = focused_object.id
        values["related_transaction_no"] = focused_object.id
        if attributes.get("account_no"):
            values["account_no"] = attributes["account_no"]

    elif object_type == "loan":
        values["loan_application_no"] = focused_object.id

    return values
