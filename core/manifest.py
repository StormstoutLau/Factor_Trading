"""运行清单（P-011 D7）。

设计依据：DESIGN_backtest_validation.md §4.4 / §5.2。目标：任何一个输出目录都能
自证"它是用哪个 commit、哪份数据、哪份配置跑出来的"。

``input_fingerprint`` 只覆盖 ``git.commit`` / 数据 sha256 / 配置，**不含**时间戳与
``run_id`` —— 同一输入两次运行的指纹必须相同。
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import platform
import subprocess
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MANIFEST_SCHEMA_VERSION = "1.0"
_SHA_CHUNK = 1024 * 1024


def _jsonable(value: Any) -> Any:
    """把任意配置值转成 JSON 可序列化对象。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if callable(value):
        return "<callable>"
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    logger.warning("manifest: 无法序列化的配置值 %r，退化为 repr", type(value))
    return repr(value)


def _sha256_file(path: Path) -> str | None:
    """文件 sha256（1 MiB 分块）；不存在返回 ``None``。"""
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_SHA_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_info(root: Path) -> dict[str, Any]:
    """``{commit, dirty}``；git 不可用或非仓库时返回 ``None`` 值，不抛异常。"""
    info: dict[str, Any] = {"commit": None, "dirty": None}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if commit.returncode == 0:
            info["commit"] = commit.stdout.strip() or None
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if status.returncode == 0:
            info["dirty"] = bool(status.stdout.strip())
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - 环境依赖
        logger.warning("manifest: 读取 git 状态失败（%s），commit/dirty 记 null", exc)
    return info


def _environment() -> dict[str, Any]:
    try:
        import numba

        numba_version: str | None = numba.__version__
    except ImportError:  # pragma: no cover - numba 为可选依赖
        numba_version = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "numba": numba_version,
    }


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(git_commit: str | None, data_files: list[dict[str, Any]], config: Any) -> str:
    payload = {
        "git_commit": git_commit,
        "data": {item["name"]: item["sha256"] for item in data_files},
        "config": config,
    }
    return "sha256:" + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def build_manifest(
    cfg: Any,
    *,
    data_dir: Path,
    data_files: Sequence[str],
    caliber: Mapping[str, Any],
    started_at: datetime,
    finished_at: datetime,
    outputs: Mapping[str, str] | None = None,
    benchmark: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """构造运行清单（键集见 DESIGN §5.2）。"""
    data_dir = Path(data_dir)
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]

    files: list[dict[str, Any]] = []
    for name in data_files:
        path = data_dir / name
        files.append(
            {
                "name": name,
                "exists": path.is_file(),
                "sha256": _sha256_file(path),
                "bytes": path.stat().st_size if path.is_file() else None,
            }
        )

    git = _git_info(root)
    config = _jsonable(cfg)

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "input_fingerprint": _fingerprint(git.get("commit"), files, config),
        "git": git,
        "config": config,
        "data": {"dir": str(data_dir), "files": files},
        "environment": _environment(),
        "caliber": _jsonable(caliber),
        "benchmark": benchmark,
        "timestamps": {
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
        },
        "outputs": dict(outputs or {}),
    }


def write_manifest(manifest: Mapping[str, Any], paths: Sequence[Path]) -> list[Path]:
    """把同一份 manifest 写入 0..n 个目录（目录不存在则创建）。"""
    payload = json.dumps(manifest, ensure_ascii=False, indent=2)
    written: list[Path] = []
    for path in paths:
        directory = Path(path)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "manifest.json"
        target.write_text(payload, encoding="utf-8")
        written.append(target)
    return written
