"""P-054 延迟基准：三段采样（append→入队 / 入队→发送 / 端到端）。"""

from __future__ import annotations

import json
import statistics
import time


def sample_segments(n: int = 200, *, clock=time.perf_counter) -> dict:
    """无 I/O 的三段口径演示：返回 p50/p95/p99（秒）。"""
    append_to_enqueue: list[float] = []
    enqueue_to_send: list[float] = []
    end_to_end: list[float] = []
    for _ in range(n):
        start = clock()
        queued = clock()
        append_to_enqueue.append(queued - start)
        sent = clock()
        enqueue_to_send.append(sent - queued)
        end_to_end.append(sent - start)
    return {
        "n": n,
        "append_to_enqueue": _percentiles(append_to_enqueue),
        "enqueue_to_send": _percentiles(enqueue_to_send),
        "end_to_end": _percentiles(end_to_end),
        "note": "含客户端时钟，绝对值可能偏差（R8）",
    }


def _percentiles(values: list[float]) -> dict:
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    ordered = sorted(values)
    return {
        "p50": statistics.median(ordered),
        "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
        "p99": ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))],
    }


def main() -> None:  # pragma: no cover - CLI
    print(json.dumps(sample_segments(), ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
