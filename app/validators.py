"""通用参数校验工具。

Pydantic 负责请求模型的结构校验；这里补充跨字段、跨参数的业务级校验，
统一抛出 ``ValueError``，由全局 ``ValueError`` 处理器转成 400。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any


def ensure_non_blank(value: Any, field: str) -> str:
    """字符串必填且不能只有空白。"""
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} 不能为空")
    return text


def ensure_max_length(value: str, field: str, max_length: int) -> str:
    if len(value) > max_length:
        raise ValueError(f"{field} 长度不能超过 {max_length}")
    return value


def ensure_enum(value: str, field: str, allowed: Iterable[str]) -> str:
    allowed_set = {str(item) for item in allowed}
    if value not in allowed_set:
        raise ValueError(f"{field} 取值必须是 {sorted(allowed_set)} 之一")
    return value


def ensure_date_range(start: date | None, end: date | None, field: str = "时间范围") -> None:
    """起止日期必须同时提供，且起点不晚于终点。"""
    if start is None or end is None:
        return
    if start > end:
        raise ValueError(f"{field} 的起始时间不能晚于结束时间")
