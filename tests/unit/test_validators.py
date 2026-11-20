"""分页与通用参数校验单元测试。"""

from __future__ import annotations

from datetime import date

import pytest

from app.utils import MAX_PAGE_NO, MAX_PAGE_SIZE, offset_limit
from app.validators import ensure_date_range, ensure_enum, ensure_max_length, ensure_non_blank


def test_offset_limit_normal() -> None:
    assert offset_limit(2, 20) == (20, 20)


def test_offset_limit_lower_bounds() -> None:
    assert offset_limit(0, 0) == (0, 1)
    assert offset_limit(-5, -1) == (0, 1)


def test_offset_limit_upper_bounds() -> None:
    offset, limit = offset_limit(MAX_PAGE_NO + 100, MAX_PAGE_SIZE + 100)
    assert offset == (MAX_PAGE_NO - 1) * MAX_PAGE_SIZE
    assert limit == MAX_PAGE_SIZE


def test_ensure_non_blank() -> None:
    assert ensure_non_blank("  ABC  ", "字段") == "ABC"
    with pytest.raises(ValueError):
        ensure_non_blank("   ", "字段")
    with pytest.raises(ValueError):
        ensure_non_blank(None, "字段")


def test_ensure_max_length() -> None:
    assert ensure_max_length("abc", "字段", 3) == "abc"
    with pytest.raises(ValueError):
        ensure_max_length("abcd", "字段", 3)


def test_ensure_enum() -> None:
    assert ensure_enum("active", "状态", {"active", "closed"}) == "active"
    with pytest.raises(ValueError):
        ensure_enum("unknown", "状态", {"active", "closed"})


def test_ensure_date_range() -> None:
    ensure_date_range(None, date(2026, 1, 1))
    ensure_date_range(date(2026, 1, 1), date(2026, 1, 2))
    with pytest.raises(ValueError):
        ensure_date_range(date(2026, 1, 2), date(2026, 1, 1))
