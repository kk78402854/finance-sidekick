"""进程内指标注册表（Prometheus 文本格式）。

不引入额外依赖：计数器 + 直方图足够覆盖本项目关心的四个信号：
请求量、错误率、延迟分布、限流命中次数。
"""

from __future__ import annotations

import threading
from typing import Any

# 延迟分桶，单位毫秒；覆盖 5ms ~ 10s
_LATENCY_BUCKETS: tuple[float, ...] = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 10000)


class _Histogram:
    __slots__ = ("buckets", "sum", "count")

    def __init__(self) -> None:
        self.buckets = [0] * len(_LATENCY_BUCKETS)
        self.sum = 0.0
        self.count = 0

    def observe(self, value: float) -> None:
        self.sum += value
        self.count += 1
        for index, upper in enumerate(_LATENCY_BUCKETS):
            if value <= upper:
                self.buckets[index] += 1


class MetricsRegistry:
    """线程安全的指标容器，同一进程内全局唯一。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str, int], int] = {}
        self._latency: dict[tuple[str, str], _Histogram] = {}
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}

    # ---------- 写入 ----------
    def observe_http(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            key = (method.upper(), path, int(status_code))
            self._requests[key] = self._requests.get(key, 0) + 1
            histogram = self._latency.setdefault((method.upper(), path), _Histogram())
            histogram.observe(duration_ms)

    def inc(self, name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
        normalized = tuple(sorted((labels or {}).items()))
        with self._lock:
            key = (name, normalized)
            self._counters[key] = self._counters.get(key, 0.0) + value

    # ---------- 读取 ----------
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "requests": dict(self._requests),
                "latency": {
                    key: {
                        "buckets": list(hist.buckets),
                        "sum": hist.sum,
                        "count": hist.count,
                    }
                    for key, hist in self._latency.items()
                },
                "counters": dict(self._counters),
            }

    def reset(self) -> None:
        """仅供测试使用。"""
        with self._lock:
            self._requests.clear()
            self._latency.clear()
            self._counters.clear()

    def render(self) -> str:
        """输出 Prometheus 文本格式。"""
        lines: list[str] = []
        snapshot = self.snapshot()

        lines.append("# HELP http_requests_total 按方法/路由/状态码统计的请求数")
        lines.append("# TYPE http_requests_total counter")
        for (method, path, status), count in sorted(snapshot["requests"].items()):
            lines.append(
                f'http_requests_total{{method="{method}",path="{_escape(path)}",status="{status}"}} {count}'
            )

        lines.append("# HELP http_request_duration_ms 请求耗时直方图（毫秒）")
        lines.append("# TYPE http_request_duration_ms histogram")
        for (method, path), data in sorted(snapshot["latency"].items()):
            base = f'method="{method}",path="{_escape(path)}"'
            for upper, count in zip(_LATENCY_BUCKETS, data["buckets"], strict=True):
                lines.append(f'http_request_duration_ms_bucket{{{base},le="{upper}"}} {count}')
            lines.append(f'http_request_duration_ms_bucket{{{base},le="+Inf"}} {data["count"]}')
            lines.append(f"http_request_duration_ms_sum{{{base}}} {data['sum']:.3f}")
            lines.append(f"http_request_duration_ms_count{{{base}}} {data['count']}")

        if snapshot["counters"]:
            lines.append("# HELP app_counter 业务自定义计数器")
            lines.append("# TYPE app_counter counter")
            for (name, labels), value in sorted(snapshot["counters"].items()):
                parts = [f'name="{_escape(name)}"']
                parts.extend(f'{key}="{_escape(label_value)}"' for key, label_value in labels)
                lines.append(f"app_counter{{{','.join(parts)}}} {value}")

        return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    return "{" + ",".join(f'{key}="{_escape(value)}"' for key, value in labels) + "}"


# 全局单例：应用与中间件共享
metrics = MetricsRegistry()
