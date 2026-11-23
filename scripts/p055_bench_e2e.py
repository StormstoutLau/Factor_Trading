#!/usr/bin/env python3
"""P-055 跨进程端到端基准（C-15/D14）。

四段口径：
  T1 submit → outbox.created_ts（writer + SQLite）
  T2 created_ts → sent_ts（relay → Redis Streams）
  T3 sent_ts → publish（consumer → Pub/Sub）
  T4 publish → 独立 client 进程收到

用法：
  python scripts/p055_bench_e2e.py run --n 1000
  python scripts/p055_bench_e2e.py client --recv-log .bench/recv.jsonl --duration 30
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _TimedBus:
    """委托包装：publish 前记录 (seq, ts)，不改 ``services/*``（C-15）。"""

    def __init__(self, inner, *, publish_log: Path | None = None) -> None:
        self._inner = inner
        self._publish_log = publish_log
        self._lock = threading.Lock()
        if publish_log is not None:
            publish_log.parent.mkdir(parents=True, exist_ok=True)
            publish_log.write_text("", encoding="utf-8")

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def publish(self, channel: str, message: dict) -> None:
        if self._publish_log is not None:
            entry = {"seq": int(message.get("seq", 0)), "ts": time.time(), "channel": channel}
            with self._lock:
                with self._publish_log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry) + "\n")
        self._inner.publish(channel, message)


def _percentiles(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "p50": None, "p95": None, "p99": None}
    ordered = sorted(values)

    def _pct(q: float) -> float:
        index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
        return ordered[index]

    return {
        "n": len(values),
        "p50": _pct(0.50),
        "p95": _pct(0.95),
        "p99": _pct(0.99),
        "mean": statistics.fmean(values),
    }


def _build_writer(store, *, n: int) -> list[float]:
    """单写者：组合写 order + accepted 事件，返回每次 submit 起点时间戳。"""
    from live.events import OutboxEventType, order_event
    from live.orders import OrderRequest, from_request

    submit_ts: list[float] = []
    for i in range(n):
        ts = time.time()
        request = OrderRequest(
            asset="600000.SH",
            side="BUY",
            quantity=100.0,
            price=10.0,
            client_order_id=f"bench-{i}",
            account_id="BENCH",
            strategy_id="S1",
            signal_ts=ts,
        )
        record = from_request(request, ts=ts)
        store.upsert_order_with_events(
            record,
            [order_event(record, OutboxEventType.ORDER_ACCEPTED, version=1, ts=ts)],
        )
        submit_ts.append(ts)
    return submit_ts


def _run_client(args) -> int:
    from services.bus import SyncRedisBus

    bus = SyncRedisBus(args.redis_url)
    pubsub = bus.subscribe("p054:orders:events")
    Path(args.recv_log).parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + args.duration
    with open(args.recv_log, "a", encoding="utf-8") as handle:
        while time.time() < deadline:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if not message:
                continue
            try:
                payload = json.loads(message["data"])
            except (TypeError, ValueError, KeyError):
                continue
            handle.write(json.dumps({"seq": int(payload.get("seq", 0)), "ts": time.time()}) + "\n")
            handle.flush()
    return 0


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _run_bench(args) -> int:
    from live.ledger_store import SqliteLedgerStore
    from services.bus import SyncRedisBus
    from services.outbox_relay import ConsumerLoop, RelayLoop

    sqlite_path = Path(args.sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        sqlite_path.unlink()
    store = SqliteLedgerStore(sqlite_path)
    store.set_meta("recovery_state", "complete")

    publish_log = Path(args.publish_log)
    recv_log = Path(args.recv_log)
    recv_log.write_text("", encoding="utf-8")
    client = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "client",
            "--recv-log",
            str(recv_log),
            "--duration",
            str(args.client_duration),
            "--redis-url",
            args.redis_url,
        ],
        cwd=str(ROOT),
    )
    bus = _TimedBus(SyncRedisBus(args.redis_url), publish_log=publish_log)
    # 跨跑复位：消费组游标/旧条目残留会让 consumer 先扇出上一轮事件，seq 空间错位
    # （Step 10 实跑修正）；组由 _ensure_group 在首个 stream 操作时幂等重建（id=0）。
    bus.delete_key("p054:orders")
    bus.delete_key("p054:consumer:heartbeat")
    relay = RelayLoop(store, bus, batch=200, poll_interval=0.01)
    consumer = ConsumerLoop(store, bus)
    stop = threading.Event()
    threads = [
        threading.Thread(target=relay.run, args=(stop,), daemon=True),
        threading.Thread(target=consumer.run, args=(stop,), daemon=True),
    ]
    for thread in threads:
        thread.start()

    if args.writer_delay > 0:  # 等 client 完成 Pub/Sub 订阅（无保留队列，先订后发是三零前提）
        time.sleep(args.writer_delay)
    submit_ts = _build_writer(store, n=args.n)
    deadline = time.time() + args.drain_timeout
    while time.time() < deadline and store.pending_outbox(1):
        time.sleep(0.01)
    unsent_after = len(store.pending_outbox(args.n + 10))
    # 扇出等待：consumer 每事件一次 SQLite 提交（~30ms），drain 只保证 relay 完成；
    # 若不等 consumer 扇出至 n 条即停线程，client 必然少收（dropped 虚高，Step 10 实跑修正）
    fanout_deadline = time.time() + args.fanout_timeout
    last_progress = time.time()
    while time.time() < fanout_deadline:
        published_lines = 0
        if publish_log.exists():
            with publish_log.open(encoding="utf-8") as handle:
                published_lines = sum(1 for _ in handle)
        if published_lines >= args.n:
            break
        if time.time() - last_progress >= 5.0:  # 吞吐曲线观测（Step 10 实跑）
            last_progress = time.time()
            print(
                json.dumps(
                    {
                        "event": "bench_fanout_progress",
                        "published": published_lines,
                        "pending": len(store.pending_outbox(args.n + 10)),
                    }
                ),
                file=sys.stderr,
                flush=True,
            )
        time.sleep(0.05)
    time.sleep(0.5)  # 留出 client 收包时间

    stop.set()
    for thread in threads:
        thread.join(timeout=5.0)
    client.terminate()
    client.wait(timeout=10)

    rows = store.outbox_after(0, args.n + 10)
    rows.sort(key=lambda row: row.seq)
    t1 = [row.created_ts - submit_ts[i] for i, row in enumerate(rows) if i < len(submit_ts)]
    t2 = [row.sent_ts - row.created_ts for row in rows if row.sent_ts is not None]
    publish = {int(item["seq"]): float(item["ts"]) for item in _read_jsonl(publish_log)}
    recv = {int(item["seq"]): float(item["ts"]) for item in _read_jsonl(recv_log)}
    sent = {row.seq: row.sent_ts for row in rows if row.sent_ts is not None}
    t3 = [publish[seq] - sent[seq] for seq in sent if seq in publish]
    t4 = [recv[seq] - publish[seq] for seq in publish if seq in recv]

    report = {
        "n": args.n,
        "sqlite": str(sqlite_path),
        "redis": args.redis_url,
        "segments": {
            "T1_submit_to_outbox": _percentiles(t1),
            "T2_outbox_to_sent": _percentiles(t2),
            "T3_sent_to_publish": _percentiles(t3),
            "T4_publish_to_client": _percentiles(t4),
        },
        "dropped": max(0, len(sent) - len(recv)),
        "pending_after": len(store.pending_outbox(args.n + 10)),
        "unsent_after": unsent_after,
    }
    _write_report(report, Path(args.report_dir))
    store.close()

    if args.assert_p99:
        limits = {
            "T1_submit_to_outbox": 0.050,
            "T2_outbox_to_sent": 0.050,
            "T3_sent_to_publish": 0.100,
            "T4_publish_to_client": 0.100,
        }
        for name, limit in limits.items():
            p99 = report["segments"][name]["p99"]
            if p99 is not None and p99 > limit:
                print(f"FAIL {name} p99={p99:.4f}s > {limit:.3f}s", file=sys.stderr)
                return 1
    print(json.dumps(report["segments"], ensure_ascii=False, indent=2))
    return 0


def _write_report(report: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# P-055 跨进程基准报告",
        "",
        f"- n = {report['n']}",
        f"- dropped = {report['dropped']}",
        f"- pending_after = {report['pending_after']}",
        f"- unsent_after = {report['unsent_after']}",
        "",
        "| 段 | n | p50 (ms) | p95 (ms) | p99 (ms) |",
        "|----|---|----------|----------|----------|",
    ]
    for name, stats in report["segments"].items():
        if not stats.get("n"):
            lines.append(f"| {name} | 0 | - | - | - |")
            continue
        lines.append(
            "| {name} | {n} | {p50:.2f} | {p95:.2f} | {p99:.2f} |".format(
                name=name,
                n=stats["n"],
                p50=stats["p50"] * 1000,
                p95=stats["p95"] * 1000,
                p99=stats["p99"] * 1000,
            )
        )
    (directory / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse(argv=None):
    parser = argparse.ArgumentParser(prog="p055_bench_e2e")
    sub = parser.add_subparsers(dest="cmd")
    run = sub.add_parser("run")
    run.add_argument("--n", type=int, default=1000)
    run.add_argument(
        "--writer-delay", type=float, default=2.0, help="writer 起跑前等待 client 订阅的秒数"
    )
    run.add_argument("--sqlite-path", default=".bench/bench.db")
    run.add_argument(
        "--redis-url", default=os.environ.get("P054_REDIS_URL", "redis://127.0.0.1:6379/0")
    )
    run.add_argument("--publish-log", default=".bench/publish.jsonl")
    run.add_argument("--recv-log", default=".bench/recv.jsonl")
    run.add_argument("--report-dir", default=".bench")
    run.add_argument("--drain-timeout", type=float, default=30.0)
    run.add_argument(
        "--fanout-timeout", type=float, default=120.0, help="等待 consumer 扇出至 n 条的秒数"
    )
    run.add_argument("--client-duration", type=float, default=20.0)
    run.add_argument("--assert-p99", action="store_true", dest="assert_p99")
    client = sub.add_parser("client")
    client.add_argument("--recv-log", required=True)
    client.add_argument("--duration", type=float, default=20.0)
    client.add_argument(
        "--redis-url", default=os.environ.get("P054_REDIS_URL", "redis://127.0.0.1:6379/0")
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse(argv)
    if args.cmd == "client":
        return _run_client(args)
    return _run_bench(args)


if __name__ == "__main__":
    sys.exit(main())
