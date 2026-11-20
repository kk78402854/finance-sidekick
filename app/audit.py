"""操作审计。

审计是旁路能力：写库失败只记日志，绝不阻断业务请求。
只保存登录凭证的摘要，不落明文 token。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Any

from fastapi import Request

from .database import db_cursor, fetch_all

logger = logging.getLogger(__name__)

AUDIT_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS operation_audit_log (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    request_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '请求追踪号',
    method VARCHAR(8) NOT NULL COMMENT 'HTTP 方法',
    path VARCHAR(255) NOT NULL COMMENT '请求路径',
    status_code INT NOT NULL COMMENT '响应状态码',
    channel_code VARCHAR(64) DEFAULT NULL COMMENT '渠道编码',
    operator_no VARCHAR(64) DEFAULT NULL COMMENT '操作员编号',
    principal_hash VARCHAR(32) DEFAULT NULL COMMENT '登录凭证摘要，禁止存明文',
    client_ip VARCHAR(64) DEFAULT NULL COMMENT '客户端 IP',
    duration_ms INT NOT NULL DEFAULT 0 COMMENT '耗时（毫秒）',
    created_at DATETIME NOT NULL COMMENT '创建时间',
    PRIMARY KEY (id),
    KEY idx_audit_created_at (created_at),
    KEY idx_audit_request_id (request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='写操作审计日志'
"""

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def mask_principal(authorization: str | None) -> str | None:
    """把 Authorization 转成不可逆短摘要；缺失时返回 None。"""
    if not authorization or not authorization.strip():
        return None
    token = authorization.strip()
    if token.lower().startswith("bearer"):
        token = token[6:].strip()
    if not token:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def build_audit_entry(
    request: Request,
    status_code: int,
    duration_ms: float,
    request_id: str | None = None,
) -> dict[str, Any]:
    """从请求对象提取审计字段。

    ``request_id`` 优先使用中间件实际生成/透传的 ID：调用方未带请求头时，
    审计记录里也必须能关联到响应头中的那个 ID，否则排障时链路会断。
    """
    headers = request.headers
    client = request.client
    return {
        "request_id": request_id or headers.get("X-Request-Id", ""),
        "method": request.method.upper(),
        "path": request.url.path,
        "status_code": int(status_code),
        "channel_code": headers.get("X-Channel-Code"),
        "operator_no": headers.get("X-Operator-No"),
        "principal_hash": mask_principal(headers.get("Authorization")),
        "client_ip": client.host if client else None,
        "duration_ms": int(duration_ms),
        "created_at": datetime.now().replace(microsecond=0),
    }


def ensure_audit_table() -> None:
    """启动时确保审计表存在；失败只告警，不影响服务启动。"""
    try:
        with db_cursor() as (_, cursor):
            cursor.execute(AUDIT_TABLE_DDL)
    except Exception:  # pragma: no cover - 依赖真实数据库
        logger.warning("ensure_audit_table_failed", exc_info=True)


def write_audit_entry(entry: dict[str, Any]) -> None:
    """同步写入审计表，供线程池调用。"""
    try:
        with db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO operation_audit_log (
                    request_id, method, path, status_code, channel_code,
                    operator_no, principal_hash, client_ip, duration_ms, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    entry["request_id"],
                    entry["method"],
                    entry["path"][:255],
                    entry["status_code"],
                    entry["channel_code"],
                    entry["operator_no"],
                    entry["principal_hash"],
                    entry["client_ip"],
                    entry["duration_ms"],
                    entry["created_at"],
                ),
            )
    except Exception:  # pragma: no cover - 依赖真实数据库
        logger.warning("write_audit_entry_failed", exc_info=True)


async def record_audit(entry: dict[str, Any]) -> None:
    """异步旁路写审计，失败不抛出。"""
    try:
        await asyncio.to_thread(write_audit_entry, entry)
    except Exception:  # pragma: no cover - asyncio.to_thread 本身极少失败
        logger.warning("record_audit_failed", exc_info=True)


def fetch_audit_logs(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """按时间倒序查询审计记录。"""
    return fetch_all(
        """
        SELECT id, request_id, method, path, status_code, channel_code,
               operator_no, principal_hash, client_ip, duration_ms, created_at
        FROM operation_audit_log
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    )
