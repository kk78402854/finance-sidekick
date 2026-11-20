"""结构化日志与请求上下文。

设计目标：
1. 一条日志 = 一行 JSON，方便被 Loki / ELK 直接采集；
2. 每条日志自动带上 ``request_id``，把一次请求经过的所有模块串起来；
3. 通过环境变量 ``LOG_LEVEL`` 控制级别，默认 INFO。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

# 请求级上下文：仅在当前请求的协程/线程内可见，不会污染其他请求
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_LOCAL_TZ = ZoneInfo("Asia/Shanghai")

# 会作为结构化字段输出的额外属性，其余 extra 会被忽略，避免日志爆炸
_EXTRA_FIELDS = (
    "event",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "code",
    "channel_code",
    "operator_no",
    "principal_hash",
    "client_ip",
)


def get_request_id() -> str | None:
    """返回当前请求的追踪号；不在请求上下文中时返回 None。"""
    return request_id_ctx.get()


class RequestIdFilter(logging.Filter):
    """把 contextvar 中的 request_id 注入到 LogRecord。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    """最小可用的 JSON 日志格式器。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(_LOCAL_TZ).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", None),
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


_configured = False


def configure_logging(level: str | None = None) -> None:
    """初始化根日志器，重复调用安全。"""
    global _configured
    if _configured:
        return
    _configured = True

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel((level or os.getenv("LOG_LEVEL", "INFO")).upper())
    # uvicorn 自带 handler 会重复输出，交给根日志器统一处理
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    # 访问日志由中间件输出，关闭 uvicorn 默认访问日志避免重复
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False
