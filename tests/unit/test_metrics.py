"""指标注册表测试。"""

from __future__ import annotations

from app.metrics import MetricsRegistry


def test_counter_and_histogram_render() -> None:
    registry = MetricsRegistry()
    registry.observe_http("GET", "/api/v1/ping", 200, 3.2)
    registry.observe_http("GET", "/api/v1/ping", 200, 180.0)
    registry.observe_http("POST", "/api/v1/ping", 500, 42.0)
    registry.inc("rag_retrieve_total", {"result": "hit"}, 2)

    text = registry.render()
    assert 'http_requests_total{method="GET",path="/api/v1/ping",status="200"} 2' in text
    assert 'http_requests_total{method="POST",path="/api/v1/ping",status="500"} 1' in text
    assert 'le="5"' in text
    assert "http_request_duration_ms_count" in text
    assert 'app_counter{name="rag_retrieve_total",result="hit"} 2.0' in text


def test_reset_clears_series() -> None:
    registry = MetricsRegistry()
    registry.observe_http("GET", "/x", 200, 1.0)
    registry.reset()
    assert registry.snapshot()["requests"] == {}


def test_bucket_is_cumulative() -> None:
    registry = MetricsRegistry()
    registry.observe_http("GET", "/x", 200, 3.0)
    registry.observe_http("GET", "/x", 200, 60.0)
    data = registry.snapshot()["latency"][("GET", "/x")]
    # 3ms 落在 5ms 桶，60ms 落在 100ms 桶；bucket 是累积口径
    assert data["buckets"][0] == 1  # le=5
    assert data["buckets"][5] == 2  # le=250
    assert data["count"] == 2
