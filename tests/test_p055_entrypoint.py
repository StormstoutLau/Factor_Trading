"""P-055 T4：api_worker 真实启动（明文 loopback / TLS 握手）+ 入口守卫（3 例）。"""

from __future__ import annotations

import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from live.ledger_store import SqliteLedgerStore

ROOT = Path(__file__).resolve().parents[1]
READER = "reader-key-1234567890"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _seed_db(path: Path) -> None:
    store = SqliteLedgerStore(path)
    store.set_meta("recovery_state", "complete")
    store.close()


def _base_env(tmp_path: Path, port: int) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "P054_API_KEY": READER,
            "P054_API_HOST": "127.0.0.1",
            "P054_API_PORT": str(port),
            "P054_SQLITE_PATH": str(tmp_path / "ledger.db"),
            "P054_WORKERS": "1",
            "P054_REDIS_URL": "redis://127.0.0.1:6399/0",
            "MPLBACKEND": "Agg",
        }
    )
    return env


def _wait_health(url: str, *, context=None, timeout: float = 20.0) -> int:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0, context=context) as response:
                return int(response.status)
        except Exception as exc:  # 启动窗口内连接拒绝属预期
            last = exc
            time.sleep(0.2)
    raise AssertionError(f"health check timeout: {last}")


def _terminate(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover - 兜底
        proc.kill()


def test_entry_modules_have_main_guard():
    """Step 10 实跑修正回归（F-B9）：三个入口必须可 ``python -m`` 直接启动。

    缺 ``__main__`` 守卫时 ``python -m services.X`` 只导入模块即退出（code 0 零输出），
    Dockerfile CMD / compose 服务 / RUNBOOK 命令全部空转。
    """
    for module in ("trading_worker", "market_gateway", "api_worker"):
        source = (ROOT / "services" / f"{module}.py").read_text(encoding="utf-8")
        assert 'if __name__ == "__main__":' in source, f"services/{module}.py 缺 __main__ 守卫"
        assert "    main()" in source, f"services/{module}.py 守卫未调用 main()"


def test_plaintext_loopback_health_live(tmp_path):
    _seed_db(tmp_path / "ledger.db")
    port = _free_port()
    env = _base_env(tmp_path, port)
    env["P054_ALLOW_PLAINTEXT_LOOPBACK"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "services.api_worker"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        assert _wait_health(f"http://127.0.0.1:{port}/health/live") == 200
    finally:
        _terminate(proc)


def test_tls_handshake(tmp_path):
    assert shutil.which("openssl") is not None, "openssl 缺失：这是环境错误（RULE-3 不 skip）"
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    conf = tmp_path / "openssl.cnf"
    conf.write_text(
        "[req]\n"
        "distinguished_name = dn\n"
        "x509_extensions = v3_req\n"
        "prompt = no\n"
        "[dn]\n"
        "CN = localhost\n"
        "[v3_req]\n"
        "subjectAltName = @alt\n"
        "[alt]\n"
        "DNS.1 = localhost\n"
        "IP.1 = 127.0.0.1\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-config",
            str(conf),
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    _seed_db(tmp_path / "ledger.db")
    port = _free_port()
    env = _base_env(tmp_path, port)
    env["P054_TLS_CERTFILE"] = str(cert)
    env["P054_TLS_KEYFILE"] = str(key)
    proc = subprocess.Popen(
        [sys.executable, "-m", "services.api_worker"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    context = ssl._create_unverified_context()  # noqa: S323 - 自签测试证书
    try:
        assert _wait_health(f"https://127.0.0.1:{port}/health/live", context=context) == 200
    finally:
        _terminate(proc)
