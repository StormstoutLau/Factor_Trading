"""P-011 B5：run manifest（可恢复性 + 指纹确定性）。

DESIGN §4.4 / §5.2：任何输出目录都必须能自证"哪个 commit、哪份数据、哪份配置"。
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from _synth_fixture import write_factor, write_price_fixture
from core.config import BacktestConfig, OptimizerConfig, RebalanceConfig
from core.engine_v2 import BacktestEngineV2
from core.manifest import MANIFEST_SCHEMA_VERSION, build_manifest, write_manifest

DATES = pd.bdate_range("2024-01-02", periods=6)
CODES = ["000001", "600000"]


def _config(tmp_path, **overrides) -> BacktestConfig:
    return BacktestConfig(
        data_dir=tmp_path,
        output_dir=tmp_path / "out",
        factor_files=["factor_value.pkl"],
        optimizer=OptimizerConfig(method="equal_weight", target_count=2, max_weight=1.0),
        rebalance=RebalanceConfig(method="fixed", frequency="N_days", n_days=3),
        initial_capital=1_000_000.0,
        **overrides,
    )


def _fixture(tmp_path) -> None:
    prices = np.array(
        [[10.0, 20.0], [10.2, 19.8], [10.1, 20.3], [10.4, 20.1], [10.3, 20.5], [10.6, 20.2]]
    )
    write_price_fixture(tmp_path, DATES, CODES, prices)
    write_factor(tmp_path, "factor_value", prices, DATES, CODES)


def _manifest(tmp_path, cfg=None, data_files=("close.pkl", "missing.pkl")) -> dict:
    cfg = cfg or _config(tmp_path)
    return build_manifest(
        cfg,
        data_dir=tmp_path,
        data_files=data_files,
        caliber={"ruleset_version": "test", "api_version": "3.1.0"},
        started_at=pd.Timestamp("2024-01-02").to_pydatetime(),
        finished_at=pd.Timestamp("2024-01-02").to_pydatetime(),
    )


def test_manifest_written(tmp_path):
    """引擎运行后 output_dir/manifest.json 必须存在且 schema 正确。"""
    _fixture(tmp_path)
    engine = BacktestEngineV2(_config(tmp_path))
    engine.setup()
    results = engine.run()

    path = tmp_path / "out" / "manifest.json"
    assert path.is_file()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["input_fingerprint"].startswith("sha256:")
    assert manifest["input_fingerprint"] == results["additional_info"]["input_fingerprint"]


def test_manifest_fields(tmp_path):
    """键集覆盖 DESIGN §5.2：git/config/data/environment/caliber/timestamps/outputs。"""
    _fixture(tmp_path)
    manifest = _manifest(tmp_path)

    assert set(manifest) == {
        "schema_version",
        "run_id",
        "input_fingerprint",
        "git",
        "config",
        "data",
        "environment",
        "caliber",
        "benchmark",
        "timestamps",
        "outputs",
    }
    assert set(manifest["git"]) == {"commit", "dirty"}
    assert set(manifest["environment"]) == {"python", "platform", "numpy", "pandas", "numba"}
    assert set(manifest["timestamps"]) == {"started_at", "finished_at"}
    assert manifest["data"]["files"][0]["name"] == "close.pkl"


def test_sha256_matches_hashlib(tmp_path):
    """data.files 的 sha256 与 ``hashlib`` 直接计算结果一致。"""
    _fixture(tmp_path)
    manifest = _manifest(tmp_path, data_files=("close.pkl",))
    entry = manifest["data"]["files"][0]

    expected = hashlib.sha256((tmp_path / "close.pkl").read_bytes()).hexdigest()
    assert entry["exists"] is True
    assert entry["sha256"] == expected
    assert entry["bytes"] == (tmp_path / "close.pkl").stat().st_size


def test_missing_file_marked_absent(tmp_path):
    """缺失文件不抛异常：``exists=false``、``sha256=null``、``bytes=null``。"""
    _fixture(tmp_path)
    manifest = _manifest(tmp_path, data_files=("missing.pkl",))
    entry = manifest["data"]["files"][0]

    assert entry == {"name": "missing.pkl", "exists": False, "sha256": None, "bytes": None}


def test_fingerprint_stable(tmp_path):
    """同输入两次构造：``input_fingerprint`` 相同，``run_id`` 允许不同。"""
    _fixture(tmp_path)
    cfg = _config(tmp_path)
    first = _manifest(tmp_path, cfg=cfg)
    second = _manifest(tmp_path, cfg=cfg)

    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["run_id"] != second["run_id"]
    assert "started_at" not in json.dumps(first["input_fingerprint"])


def test_config_keys_match_dataclass(tmp_path):
    """I8：manifest.config 键集 == BacktestConfig 顶层字段集（无静默丢字段）。"""
    manifest = _manifest(tmp_path)
    assert set(manifest["config"]) == {field.name for field in dataclasses.fields(BacktestConfig)}


def test_callable_serialized(tmp_path):
    """可调用对象序列化为 ``"<callable>"``，不进入 fingerprint 的随机 repr。"""
    cfg = _config(tmp_path, execution_price_custom_callback=lambda *args: 1.0)
    manifest = _manifest(tmp_path, cfg=cfg)
    assert manifest["config"]["execution_price_custom_callback"] == "<callable>"
    json.dumps(manifest)  # 整体必须可 JSON 序列化

    paths = write_manifest(manifest, [tmp_path / "a", tmp_path / "b"])
    assert [path.name for path in paths] == ["manifest.json", "manifest.json"]
    assert all(isinstance(path, Path) and path.is_file() for path in paths)


def test_write_manifest_flag_disables(tmp_path):
    """``write_manifest=False`` → 不写文件、结果不含指纹（零 I/O）。"""
    _fixture(tmp_path)
    engine = BacktestEngineV2(_config(tmp_path, write_manifest=False))
    engine.setup()
    results = engine.run()

    assert not (tmp_path / "out" / "manifest.json").exists()
    assert "input_fingerprint" not in results["additional_info"]


def test_git_unavailable_returns_null(tmp_path, monkeypatch):
    """git 不可用（非仓库/超时）→ commit/dirty 均为 null，不抛异常。"""

    def _boom(*args, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr("core.manifest.subprocess.run", _boom)
    manifest = _manifest(tmp_path)
    assert manifest["git"] == {"commit": None, "dirty": None}
    assert manifest["input_fingerprint"].startswith("sha256:")
