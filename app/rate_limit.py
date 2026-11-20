"""滑动窗口限流。

单机内存实现，适合演示与单实例部署；多实例生产环境应替换为 Redis
（同一套 ``allow`` 接口即可替换，不影响调用方）。
"""

from __future__ import annotations

import os
import time
from collections import deque


class SlidingWindowLimiter:
    """按 key 统计窗口内请求数，超过阈值即拒绝。"""

    # 每处理固定次数请求清理一次过期 key，避免长期运行后 key 无限增长
    _PRUNE_EVERY = 512

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._calls = 0

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """返回 (是否放行, 当前窗口内剩余额度)。"""
        if self.limit <= 0:
            return True, -1

        current = time.monotonic() if now is None else now
        boundary = current - self.window_seconds

        # 先清理过期 key，再取当前 key 的队列；否则当前 key 可能被清掉后继续写入孤立队列
        self._calls += 1
        if self._calls % self._PRUNE_EVERY == 0:
            self._prune(boundary)

        events = self._events.setdefault(key, deque())
        while events and events[0] <= boundary:
            events.popleft()

        if len(events) >= self.limit:
            return False, 0

        events.append(current)
        return True, self.limit - len(events)

    def _prune(self, boundary: float) -> None:
        """删除窗口外已无事件的 key，控制内存占用。"""
        stale_keys = [key for key, events in self._events.items() if not events or events[-1] <= boundary]
        for key in stale_keys:
            self._events.pop(key, None)

    def reset(self) -> None:
        self._events.clear()
        self._calls = 0


def limiter_from_env() -> SlidingWindowLimiter:
    """默认 240 次/分钟；设置为 0 表示关闭限流。"""
    raw = os.getenv("RATE_LIMIT_PER_MINUTE", "240")
    try:
        limit = max(int(raw), 0)
    except ValueError:
        limit = 240
    return SlidingWindowLimiter(limit=limit)
