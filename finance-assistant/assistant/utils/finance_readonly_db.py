"""
中台业务库连接。

中台没有提供“客户列表 / 待审批贷款列表 / 工单列表 / 大盘汇总”这类管理端接口，
门户在 BFF 层用只读 SQL 补齐。这里只允许 SELECT，唯一的写入是合同文件记录：
中台同样缺少“生成合同文件”接口，审批通过后由门户补一条记录，供中台签署接口引用。
"""
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from assistant.conf.config import settings

_engine: AsyncEngine | None = None


def _get_engine() -> AsyncEngine:
    global _engine
    if not settings.finance_db_url:
        raise RuntimeError("未配置 FINANCE_DB_URL，管理端列表与大盘接口不可用。")
    if _engine is None:
        _engine = create_async_engine(
            settings.finance_db_url,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    return _engine


async def fetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict]:
    async with _get_engine().connect() as conn:
        result = await conn.execute(text(sql), params or {})
        return [dict(row) for row in result.mappings()]


async def fetch_one(sql: str, params: dict[str, Any] | None = None) -> dict | None:
    rows = await fetch_all(sql, params)
    return rows[0] if rows else None


async def ensure_contract_document(contract_id: int) -> str:
    """为审批新生成的合同补一条文件记录，已存在时复用，返回文件编号。"""
    document_no = f"LCD{contract_id:010d}"
    async with _get_engine().begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO loan_contract_document (
                    document_no, contract_id, document_type, document_version,
                    file_url, file_hash, sign_status, created_at, updated_at
                )
                VALUES (
                    :document_no, :contract_id, 'loan_contract', 1,
                    NULL, NULL, 'pending', NOW(), NOW()
                )
                ON DUPLICATE KEY UPDATE document_no = document_no
                """
            ),
            {"document_no": document_no, "contract_id": contract_id},
        )
    row = await fetch_one(
        """
        SELECT document_no
        FROM loan_contract_document
        WHERE contract_id = :contract_id
          AND document_type = 'loan_contract'
          AND document_version = 1
        """,
        {"contract_id": contract_id},
    )
    if not row:
        raise RuntimeError("合同文件记录生成失败。")
    return str(row["document_no"])


async def close_finance_db() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
