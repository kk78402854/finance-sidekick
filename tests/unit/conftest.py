"""单元测试不依赖 MySQL：覆盖父级 conftest 的数据库清理 fixture。"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_database():
    """空实现，覆盖 tests/conftest.py 中依赖数据库的同名自动 fixture。"""
    yield
