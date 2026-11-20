"""限流器与限流中间件测试。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RateLimitMiddleware
from app.rate_limit import SlidingWindowLimiter, limiter_from_env


def test_sliding_window_allows_until_limit() -> None:
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
    assert limiter.allow("k", now=1.0) == (True, 1)
    assert limiter.allow("k", now=2.0) == (True, 0)
    assert limiter.allow("k", now=3.0) == (False, 0)


def test_sliding_window_expires_old_events() -> None:
    limiter = SlidingWindowLimiter(limit=1, window_seconds=10)
    assert limiter.allow("k", now=1.0)[0] is True
    assert limiter.allow("k", now=5.0)[0] is False
    assert limiter.allow("k", now=12.0)[0] is True


def test_sliding_window_keys_are_isolated() -> None:
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
    assert limiter.allow("a", now=1.0)[0] is True
    assert limiter.allow("b", now=1.0)[0] is True


def test_limit_zero_disables_limiter(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    assert limiter_from_env().limit == 0


def test_middleware_returns_429() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=SlidingWindowLimiter(limit=1, window_seconds=60))

    @app.post("/api/v1/write")
    def write() -> dict[str, int]:
        return {"ok": 1}

    with TestClient(app) as client:
        first = client.post("/api/v1/write")
        second = client.post("/api/v1/write")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == "RATE_LIMITED"
    assert second.headers["Retry-After"] == "60"


def test_get_requests_are_not_limited() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=SlidingWindowLimiter(limit=1, window_seconds=60))

    @app.get("/api/v1/read")
    def read() -> dict[str, int]:
        return {"ok": 1}

    with TestClient(app) as client:
        assert client.get("/api/v1/read").status_code == 200
        assert client.get("/api/v1/read").status_code == 200


def test_prune_evicts_stale_keys() -> None:
    limiter = SlidingWindowLimiter(limit=1000, window_seconds=10)
    limiter.allow("old", now=1.0)
    for _ in range(limiter._PRUNE_EVERY - 1):
        limiter.allow("new", now=100.0)
    # 恰好触发一次清理：old 的全部事件都已过期，应被移除
    assert "old" not in limiter._events
    assert "new" in limiter._events


def test_prune_keeps_current_key() -> None:
    """清理发生在取队列之前，当前 key 不能被删成孤立 deque，否则限流会失效。"""
    limiter = SlidingWindowLimiter(limit=1, window_seconds=10)
    limiter.allow("k", now=1.0)
    for _ in range(limiter._PRUNE_EVERY - 1):
        limiter.allow("k", now=100.0)
    result = limiter.allow("k", now=200.0)
    assert "k" in limiter._events
    assert result == (True, 0)
