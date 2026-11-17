# IMPL：P-042 数据契约统一（B4 收口 + 流式契约）

> **批次**: P-042 · **Step 5 实施规划** · 日期 2026-11-18
> **判档**: **T1**（Layer-1：`core/`、`tests/`；契约变更）
> **上游**: [DESIGN_p042](DESIGN_p042_data_contract.md)（D1-D7 / I1-I12 / §10 Step 4 pass：1 P2 + 3 P3）
> **代码证据时点**: HEAD `9f0dbeb`（工作区仅文档）

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 生产改动 6 | `core/data_provider.py` / `core/data.py` / `core/interfaces.py` / `core/factor.py` / `core/engine_v2.py` / `agents/agent_framework.py` |
| 生产新建 1 | `core/streaming.py`（`MarketEvent` + `IStreamingFeed` + `InMemoryStreamingFeed`） |
| 测试新建 4 | `tests/_synthetic_data.py` / `tests/test_p042_data_contract.py`（V1-V7）/ `tests/test_p042_streaming_contract.py`（V8-V12）/ `tests/test_p042_fingerprint.py`（V13-V16） |
| 测试订正 2 | `tests/test_contract_conformance.py`（成员集合 3→4、9→19）；`tests/test_p029_silent_exception_governance.py`（`_FakeDM` +`load_aux_raw`） |
| 零改动面 | `filter/**`、`core/data_v3.py`、`core/manifest.py`、`tests/golden/**`、`pyproject.toml`、`uv.lock`、CI 命令、复权/对齐/缺失语义 |
| 门禁 | pytest **778 → 794** / golden **13·765** 零重录 / mypy **103 → 104 files 0** / black **124 → 129**（全仓 **191 → 196**）/ AST `except Exception` **22** / `tests/*.py` **87 → 91** / `uv lock` exit 0 |

**五条前提**：① B1/B2 零行为（golden 零重录）；② 零新增外部依赖（仅 stdlib `hashlib` / `collections.deque` / `dataclasses`）；③ 新增 `except Exception` = 0（仅 `except FileNotFoundError: raise` 1 处）；新增 `# type: ignore` = 0；④ 不复活 P-004 已删 API（`from_data_manager` 等）；⑤ `agents/` 两处 `data_dir` 直读归零。

---

## 2. 任务拆解（4 个独立能力）

| 批次 | 步骤 | 依赖 | 提交边界 | 回退点 |
|------|------|------|----------|--------|
| **B1 端口收口** | T-B1.1 端口协议 + 实现 → T-B1.2 `DataManager.load_factor` 改走端口 → T-B1.3 `load_aux_raw` → T-B1.4 agents 两处替换 → T-B1.5 两个 Mock 补方法 | 无 | 可独立提交 | revert → 因子直读 pkl、agents 直读 `data_dir` 恢复 |
| **B2 协议收口** | T-B2.1 `IDataManager` +10 属性 → T-B2.2 `FactorPipeline` 依赖倒置 → T-B2.3 去 `cast` → T-B2.4 契约测试成员集合 | B1（`load_factor` 已在协议外，无耦合） | 可独立提交 | 纯类型/声明，revert 无副作用 |
| **B3 流式契约** | T-B3.1 `core/streaming.py` → T-B3.2 V8-V12 | 无 | 可独立提交 | 删除模块 + 测试；零调用方 |
| **B4 可审计** | T-B4.1 `data_fingerprint` + `_fingerprint_part` → T-B4.2 `tests/_synthetic_data.py` → T-B4.3 V13-V16 | 无（B1 完成后因子经端口，指纹自动覆盖） | 可独立提交 | 删除方法 + 夹具；零生产调用方 |

> 推荐提交顺序 **B1 → B2 → B3 → B4**；B1 单独提交以便 golden 零重录可归因。

---

## 3. 接口签名与实现规格

### 3.1 B1：`DataProvider.load_factor`（`core/data_provider.py`）

**协议**（L18-31 末尾追加）：

```python
    def load_factor(self, name: str) -> pd.DataFrame:
        """读取因子矩阵（data_dir 下的文件名）。"""
        ...
```

**实现**（L34-76 `PklDataProvider` 末尾追加）：

```python
    def load_factor(self, name: str) -> pd.DataFrame:
        path = self.data_dir / name
        if not path.exists():
            raise FileNotFoundError(f"因子文件不存在: {path}")
        return pd.read_pickle(path)
```

**模块 docstring（L1-6）**：删除过期句「**本批不接线**：生产代码不得 import 本模块（P-004 负责迁移，V15）」与类 docstring「（只读；不接入 DataManager 调用路径）」，改为「只读存储适配器；`DataManager` 经此端口读取（P-004 B1 / P-042 B1）」。

**回退点**：删除该两处方法 + docstring 复原。

### 3.2 B1：`DataManager.load_factor` 改走端口（`core/data.py` L550-618）

**改前**（L564-569）：

```python
        file_path = self.data_dir / factor_file
        if not file_path.exists():
            raise FileNotFoundError(f"因子文件不存在: {file_path}")

        try:
            factor_data = pd.read_pickle(file_path)
```

**改后**：

```python
        try:
            factor_data = self._provider.load_factor(factor_file)
```

**同步改**（L616 前）：

```python
        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"加载因子数据 {factor_file} 失败: {e}")
            raise
```

- 对齐 / 缓存 / `reindex(columns=..., fill_value=0)` 全部不动。
- 新增 `except FileNotFoundError: raise` 为日志奇偶必需（DESIGN D2 / F-S4-P042-2）。
- **回退点**：还原 L564-569 与删除新增 `except` 分支。

### 3.3 B1：`DataManager.load_aux_raw`（`core/data.py`，`mktcap` 属性之后 / `returns` 之前）

```python
    def load_aux_raw(self, kind: str) -> Optional[pd.DataFrame]:
        """按存储原样读取辅助数据（未对齐、不加默认值、缺失返回 None）。

        供 agents 等只读消费方替代 ``data_dir`` 直读（P-042 B1）；
        I/O 仍全部经 ``DataProvider``。
        """
        return self._provider.load_aux(kind)
```

**回退点**：删除方法。

### 3.4 B1：`agents/agent_framework.py` 两处直读（L976-994）

**改前**：

```python
        try:
            import pickle

            industry_path = data_manager.data_dir / "industry.pkl"
            if industry_path.exists():
                with open(industry_path, "rb") as f:
                    self._industry_data = pickle.load(f)
        except:
            self._record_failure("industry_cache")

        try:
            import pickle

            mktcap_path = data_manager.data_dir / "mktcap.pkl"
            if mktcap_path.exists():
                with open(mktcap_path, "rb") as f:
                    self._mktcap_data = pickle.load(f)
        except:
            self._record_failure("mktcap_cache")
```

**改后**：

```python
        try:
            self._industry_data = data_manager.load_aux_raw("industry")
        except:
            self._record_failure("industry_cache")

        try:
            self._mktcap_data = data_manager.load_aux_raw("mktcap")
        except:
            self._record_failure("mktcap_cache")
```

- 保留裸 `except:`（P-029 治理口径；AST 计数不变）。
- **回退点**：还原 18 行原实现。

### 3.5 B2：`IDataManager` +10 属性（`core/interfaces.py` L49 之后 / `returns` 之前）

```python
    @property
    def close(self) -> pd.DataFrame:
        """收盘价矩阵 (dates x stocks)"""
        ...

    @property
    def open(self) -> pd.DataFrame:
        """开盘价矩阵"""
        ...

    @property
    def high(self) -> pd.DataFrame:
        """最高价矩阵"""
        ...

    @property
    def low(self) -> pd.DataFrame:
        """最低价矩阵"""
        ...

    @property
    def adj_factor(self) -> pd.DataFrame:
        """复权因子矩阵"""
        ...

    @property
    def suspend(self) -> Optional[pd.DataFrame]:
        """停牌矩阵（1=停牌，0=正常；未配置时为 None）"""
        ...

    @property
    def st(self) -> Optional[pd.DataFrame]:
        """ST 矩阵（1=ST，0=正常）"""
        ...

    @property
    def industry(self) -> Optional[pd.DataFrame]:
        """行业矩阵（缺失时为 None）"""
        ...

    @property
    def mktcap(self) -> Optional[pd.DataFrame]:
        """市值矩阵（缺失时为 None）"""
        ...

    @property
    def universe(self) -> Optional[UniverseSnapshot]:
        """股票池快照（缺失时降级快照）"""
        ...
```

`TYPE_CHECKING` 块（L17-18）追加：

```python
    from core.universe_data import UniverseSnapshot
```

**回退点**：删除 10 属性 + 该 import。

### 3.6 B2：`FactorPipeline` 依赖倒置（`core/factor.py`）

**改前**：

```python
from core.data import DataManager
...
    def __init__(self, data_manager: DataManager, config: FactorConfig):
```

**改后**：

```python
from core.interfaces import IDataManager
...
    def __init__(self, data_manager: IDataManager, config: FactorConfig):
```

**回退点**：还原 import 与注解。

### 3.7 B2：移除 `cast`（`core/engine_v2.py`）

**改前**（L13 / L228）：

```python
from typing import Any, Optional, cast
...
            self.pipeline = FactorPipeline(cast(DataManager, self.dm), self.cfg.factor)
```

**改后**：

```python
from typing import Any, Optional
...
            self.pipeline = FactorPipeline(self.dm, self.cfg.factor)
```

**若 mypy 报 `Optional[IDataManager]` 实参**（降级链，R2）：

```python
            dm = self.dm
            assert dm is not None
            self.pipeline = FactorPipeline(dm, self.cfg.factor)
```

不得回退为 `cast(DataManager, ...)`；若仍失败，保留原 cast 并登记 U-P042-6（P3）。

**回退点**：还原导入与 L228 单行。

### 3.8 B3：`core/streaming.py`（新建，完整代码）

```python
"""流式数据契约（P-042 B3）。

- ``MarketEvent``：最小事件（symbol / ts / kind / payload / seq）；
- ``IStreamingFeed``：订阅、快照、增量拉取、关闭四方法；
- ``InMemoryStreamingFeed``：内存实现（仅测试与回放，不接实时源）。

**边界**：本批不建 ``live/``、不接行情网关；实时适配器由 P-053 实现。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Protocol

import pandas as pd


@dataclass(frozen=True)
class MarketEvent:
    """不可变市场事件（payload 为浅冻结：内部 dict 仍可变更）。"""

    symbol: str
    ts: pd.Timestamp
    kind: str
    payload: dict[str, Any]
    seq: int


class IStreamingFeed(Protocol):
    """流式数据源端口。"""

    def snapshot(self) -> dict[str, MarketEvent]:
        """返回每个 symbol 的最新事件。"""
        ...

    def poll(self, timeout: Optional[float] = None) -> list[MarketEvent]:
        """返回上次 poll 之后的增量事件（按 seq 升序）。"""
        ...

    def subscribe(self, symbols: Iterable[str]) -> None:
        """设置订阅集合（覆盖式）。"""
        ...

    def close(self) -> None:
        """关闭数据源（幂等）。"""
        ...


class InMemoryStreamingFeed:
    """内存流实现：seq 单调、有界队列、snapshot + 增量。

    ``poll(timeout)`` 不阻塞：内存实现没有生产者线程，参数仅为接口齐备；
    阻塞/背压语义由 P-053 的实时适配器实现。
    """

    _KINDS = ("tick", "bar", "snapshot")

    def __init__(self, maxlen: int = 10_000) -> None:
        if maxlen <= 0:
            raise ValueError(f"maxlen 必须为正整数: {maxlen}")
        self._maxlen = maxlen
        self._seq = 0
        self._cursor = 0
        self._buffer: deque[MarketEvent] = deque(maxlen=maxlen)
        self._latest: dict[str, MarketEvent] = {}
        self._symbols: set[str] = set()
        self._closed = False

    def subscribe(self, symbols: Iterable[str]) -> None:
        """设置订阅集合；空集合表示全部订阅。"""
        self._symbols = {str(symbol) for symbol in symbols}

    def publish(
        self, symbol: str, ts: pd.Timestamp, kind: str, payload: dict[str, Any]
    ) -> Optional[MarketEvent]:
        """发布事件；未订阅返回 None（不消耗 seq）。"""
        if self._closed:
            raise RuntimeError("feed 已关闭，禁止 publish")
        if not symbol:
            raise ValueError("symbol 不能为空")
        if kind not in self._KINDS:
            raise ValueError(f"未知事件类型: {kind}")
        if self._symbols and symbol not in self._symbols:
            return None

        self._seq += 1
        event = MarketEvent(
            symbol=symbol,
            ts=pd.Timestamp(ts),
            kind=kind,
            payload=dict(payload),
            seq=self._seq,
        )
        self._buffer.append(event)
        self._latest[symbol] = event
        return event

    def snapshot(self) -> dict[str, MarketEvent]:
        return {} if self._closed else dict(self._latest)

    def poll(self, timeout: Optional[float] = None) -> list[MarketEvent]:
        if self._closed:
            return []
        events = [event for event in self._buffer if event.seq > self._cursor]
        if events:
            self._cursor = events[-1].seq
        return events

    def close(self) -> None:
        self._closed = True
```

**回退点**：删除文件。

### 3.9 B4：`DataManager.data_fingerprint`（`core/data.py`，`get_data_info` 之后）

顶部 import 追加 `import hashlib`（stdlib，按字母序置于 `from __future__` 之后）。

```python
    def data_fingerprint(self) -> str:
        """返回数据矩阵指纹（配置驱动的固定键集；同数据同指纹）。

        覆盖：五类价格矩阵、``returns``、``cfg.factor_files`` 中的因子矩阵、
        四个辅助矩阵（缺失记 ``absent``）。不做文件级哈希——那份职责属于
        ``core.manifest``。
        """
        parts = [
            self._fingerprint_part(f"price:{kind}", self._load_price_data(kind))
            for kind in _PRICE_KINDS
        ]
        parts.append(self._fingerprint_part("returns", self.returns))
        for name in sorted(self.cfg.factor_files):
            parts.append(self._fingerprint_part(f"factor:{name}", self.load_factor(name)))
        for kind, frame in (
            ("suspend", self.suspend),
            ("st", self.st),
            ("industry", self.industry),
            ("mktcap", self.mktcap),
        ):
            if frame is None:
                parts.append(f"aux:{kind}:absent")
            else:
                parts.append(self._fingerprint_part(f"aux:{kind}", frame))

        payload = "\n".join(parts).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _fingerprint_part(label: str, frame: pd.DataFrame) -> str:
        """单矩阵规范化哈希：标签 + 形状 + 列名 + 行哈希（含索引值）。"""
        rows = pd.util.hash_pandas_object(frame, index=True).to_numpy(dtype="<u8")
        head = (
            f"{label}|{frame.shape[0]}x{frame.shape[1]}|"
            + ",".join(map(str, frame.columns))
        ).encode("utf-8")
        return hashlib.sha256(head + rows.tobytes()).hexdigest()
```

**回退点**：删除两方法 + `hashlib` import。

### 3.10 B4：`tests/_synthetic_data.py`（新建，完整代码）

```python
"""P-042 合成数据夹具（B4）：生成完整的最小 pkl 数据集。

仅测试使用；不写 ``universe/``（缺失走降级快照，不参与指纹）。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from core.config import BacktestConfig

FACTOR_FILE = "factor_value.pkl"


def build_synthetic_dataset(
    tmp_path: Path,
    n_dates: int = 20,
    n_stocks: int = 5,
    seed: int = 42,
) -> Path:
    """写入价格 / 辅助 / 因子 pkl，返回数据目录。"""
    rng = np.random.default_rng(seed)
    data_dir = Path(tmp_path)
    data_dir.mkdir(parents=True, exist_ok=True)

    dates = pd.bdate_range("2024-01-02", periods=n_dates)
    codes = [f"S{i:03d}" for i in range(n_stocks)]

    returns = rng.normal(0.0, 0.01, size=(n_dates, n_stocks))
    close = 10.0 * np.exp(np.cumsum(returns, axis=0))
    close_df = pd.DataFrame(close, index=dates, columns=codes)
    open_df = close_df * (1.0 + rng.normal(0.0, 0.002, size=close_df.shape))
    high_df = pd.DataFrame(
        np.maximum(close_df.values, open_df.values) * 1.005, index=dates, columns=codes
    )
    low_df = pd.DataFrame(
        np.minimum(close_df.values, open_df.values) * 0.995, index=dates, columns=codes
    )
    adj_df = pd.DataFrame(1.0, index=dates, columns=codes)
    zero_df = pd.DataFrame(0, index=dates, columns=codes)
    industry_df = pd.DataFrame(
        np.tile(np.arange(n_stocks) % 4, (n_dates, 1)), index=dates, columns=codes
    )
    mktcap_df = pd.DataFrame(
        rng.uniform(1e9, 1e10, size=(n_dates, n_stocks)), index=dates, columns=codes
    )

    # 因子：3 个月度截面，首日故意晚于交易日首日（验证 asof 对齐）
    factor_dates = pd.DatetimeIndex([dates[5], dates[12], dates[-1]])
    factor_df = pd.DataFrame(
        rng.normal(0.0, 1.0, size=(len(factor_dates), n_stocks)),
        index=factor_dates,
        columns=codes,
    )

    files = {
        "close.pkl": close_df,
        "open.pkl": open_df,
        "high.pkl": high_df,
        "low.pkl": low_df,
        "stock_adj.pkl": adj_df,
        "suspend.pkl": zero_df,
        "st.pkl": zero_df,
        "industry.pkl": industry_df,
        "mktcap.pkl": mktcap_df,
        FACTOR_FILE: factor_df,
    }
    for name, frame in files.items():
        frame.to_pickle(data_dir / name)
    return data_dir


def build_synthetic_config(data_dir: Path) -> BacktestConfig:
    """返回指向合成数据的配置（因子 + 市值均显式开启）。"""
    return BacktestConfig(
        data_dir=Path(data_dir),
        factor_files=[FACTOR_FILE],
        mktcap_file="mktcap.pkl",
    )
```

**回退点**：删除文件。

---

## 4. 测试规格（V1-V16）

### 4.1 `tests/test_p042_data_contract.py`（V1-V7）

```python
"""P-042 B1/B2 数据契约测试（V1-V7）。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import agents.agent_framework as agent_framework_module
from agents.agent_framework import ResearchTeamAgent
from core.config import BacktestConfig
from core.data import DataManager
from core.data_provider import PklDataProvider
from core.interfaces import IDataManager


def test_v1_pkl_provider_load_factor_roundtrip(tmp_path):
    """V1：端口读取因子逐值相等。"""
    frame = pd.DataFrame({"A": [1.0, 2.0]}, index=pd.date_range("2024-01-02", periods=2))
    frame.to_pickle(tmp_path / "f.pkl")

    loaded = PklDataProvider(tmp_path).load_factor("f.pkl")

    pd.testing.assert_frame_equal(loaded, frame)


def test_v2_pkl_provider_load_factor_missing(tmp_path):
    """V2：缺失文件抛 FileNotFoundError，文案含路径。"""
    with pytest.raises(FileNotFoundError, match="因子文件不存在:"):
        PklDataProvider(tmp_path).load_factor("missing.pkl")


class _SpyProvider:
    def __init__(self, close: pd.DataFrame, factor: pd.DataFrame) -> None:
        self._close = close
        self._factor = factor
        self.factor_calls: list[str] = []

    def load_price(self, kind):
        return self._close

    def load_aux(self, kind):
        return None

    def load_universe(self):
        return None

    def load_factor(self, name):
        self.factor_calls.append(name)
        return self._factor


def test_v3_load_factor_goes_through_provider():
    """V3：DataManager.load_factor 经端口读取。"""
    dates = pd.bdate_range("2024-01-02", periods=3)
    close = pd.DataFrame({"A": [1.0, 1.1, 1.2]}, index=dates)
    factor = pd.DataFrame({"A": [0.1, 0.2]}, index=dates[:2])
    provider = _SpyProvider(close, factor)
    dm = DataManager(BacktestConfig(factor_files=["f.pkl"]), provider=provider)

    _ = dm.trade_dates
    result = dm.load_factor("f.pkl")

    assert provider.factor_calls == ["f.pkl"]
    assert list(result.index) == list(dates)
    assert result["A"].iloc[2] == 0.2


def test_v4_load_factor_alignment_semantics(tmp_path):
    """V4：asof 对齐 / 首因子日前 NaN / 缺列填 0 零变更（非回归护栏）。"""
    dates = pd.bdate_range("2024-01-02", periods=6)
    pd.DataFrame({"A": [1.0] * 6, "B": [1.0] * 6}, index=dates).to_pickle(
        tmp_path / "close.pkl"
    )
    pd.DataFrame(
        {"A": [1.0, 2.0]}, index=pd.DatetimeIndex([dates[2], dates[4]])
    ).to_pickle(tmp_path / "f.pkl")

    dm = DataManager(BacktestConfig(data_dir=tmp_path, factor_files=["f.pkl"]))
    _ = dm.trade_dates
    aligned = dm.load_factor("f.pkl")

    assert list(aligned.columns) == ["A", "B"]
    assert aligned["B"].eq(0).all()
    assert aligned["A"].iloc[:2].isna().all()
    assert list(aligned["A"].iloc[2:4]) == [1.0, 1.0]
    assert list(aligned["A"].iloc[4:]) == [2.0, 2.0]


class _Pipe:
    def __init__(self, data_manager, factor_config):
        pass

    def process(self, raw):
        return raw


class _Comb:
    def __init__(self, factor_files, factor_weights):
        pass

    def combine(self, processed):
        return next(iter(processed.values()))


class _AuxDM:
    def __init__(self, industry=None, mktcap=None, fail_industry=False):
        self.data_dir = Path("./__missing__")
        self._industry = industry
        self._mktcap = mktcap
        self._fail_industry = fail_industry

    def load_factor(self, name):
        return pd.DataFrame({"A": [1.0]}, index=pd.DatetimeIndex(["2024-01-02"]))

    def get_adj_price(self, price_type, adjustment_type):
        return pd.DataFrame({"A": [1.0]}, index=pd.DatetimeIndex(["2024-01-02"]))

    def load_aux_raw(self, kind):
        if kind == "industry":
            if self._fail_industry:
                raise RuntimeError("boom")
            return self._industry
        return self._mktcap


def _agent(monkeypatch):
    monkeypatch.setattr(agent_framework_module, "FactorPipeline", _Pipe)
    monkeypatch.setattr(agent_framework_module, "FactorCombiner", _Comb)
    agent = ResearchTeamAgent()
    monkeypatch.setattr(agent, "_init_research_team", lambda dm: None)
    return agent


def test_v5_agent_framework_caches_industry_via_facade(monkeypatch):
    """V5：agents 经门面读行业/市值，成功路径零失败计数。"""
    index = pd.DatetimeIndex(["2024-01-02"])
    industry = pd.DataFrame({"A": [1]}, index=index)
    mktcap = pd.DataFrame({"A": [1e9]}, index=index)

    agent = _agent(monkeypatch)
    agent.prepare_factors(_AuxDM(industry=industry, mktcap=mktcap))

    assert agent._industry_data is industry
    assert agent._mktcap_data is mktcap
    assert agent.get_failure_stats() == {}


def test_v6_agent_framework_cache_failure_still_counted(monkeypatch):
    """V6：行业读取抛错仍计 1，缓存保持 None。"""
    agent = _agent(monkeypatch)
    agent.prepare_factors(_AuxDM(fail_industry=True))

    assert agent._industry_data is None
    assert agent._mktcap_data is None
    assert agent.get_failure_stats() == {"industry_cache": 1}


_CONSUMERS = {
    "trade_dates",
    "stock_codes",
    "close",
    "open",
    "high",
    "low",
    "adj_factor",
    "suspend",
    "st",
    "industry",
    "mktcap",
    "universe",
}


def test_v7_idatamanager_covers_data_layer_consumers():
    """V7：filter/factor 实际消费集合 ⊆ 协议 ⊆ 实现；两个具体方法不入协议。"""
    protocol_members = {name for name in dir(IDataManager) if not name.startswith("_")}
    assert _CONSUMERS <= protocol_members
    assert "load_aux_raw" not in protocol_members
    assert "data_fingerprint" not in protocol_members

    dm = DataManager(BacktestConfig())
    impl_members = {name for name in dir(dm) if not name.startswith("_")}
    assert _CONSUMERS <= impl_members
```

### 4.2 `tests/test_p042_streaming_contract.py`（V8-V12）

```python
"""P-042 B3 流式契约测试（V8-V12）。"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from core.streaming import IStreamingFeed, InMemoryStreamingFeed, MarketEvent

TS = pd.Timestamp("2024-01-02 09:30:00")


def test_v8_seq_monotonic_and_frozen():
    """V8：跨 symbol seq 严格递增；事件不可变；协议四方法齐备。"""
    feed = InMemoryStreamingFeed()
    first = feed.publish("A", TS, "tick", {"px": 1.0})
    second = feed.publish("B", TS, "tick", {"px": 2.0})
    third = feed.publish("A", TS, "bar", {"px": 3.0})

    assert first is not None and second is not None and third is not None
    assert [first.seq, second.seq, third.seq] == [1, 2, 3]
    assert isinstance(first, MarketEvent)

    with pytest.raises(FrozenInstanceError):
        setattr(first, "seq", 99)

    expected = {"snapshot", "poll", "subscribe", "close"}
    assert expected <= {name for name in dir(IStreamingFeed) if not name.startswith("_")}


def test_v9_snapshot_latest_per_symbol():
    """V9：snapshot 返回每 symbol 最新事件。"""
    feed = InMemoryStreamingFeed()
    feed.publish("A", TS, "tick", {"px": 1.0})
    b1 = feed.publish("B", TS, "tick", {"px": 2.0})
    a2 = feed.publish("A", TS, "tick", {"px": 3.0})

    assert feed.snapshot() == {"A": a2, "B": b1}


def test_v10_poll_delta_and_empty():
    """V10：poll 按序返回增量；无新事件返回 []。"""
    feed = InMemoryStreamingFeed()
    events = [
        feed.publish("A", TS, "tick", {"i": 1}),
        feed.publish("B", TS, "tick", {"i": 2}),
        feed.publish("A", TS, "tick", {"i": 3}),
    ]

    assert feed.poll() == events
    assert feed.poll() == []

    extra = feed.publish("B", TS, "bar", {"i": 4})
    assert feed.poll() == [extra]


def test_v11_subscribe_filters_publish():
    """V11：订阅集非空时，未订阅 symbol 不入队且不消耗 seq。"""
    feed = InMemoryStreamingFeed()
    feed.subscribe(["A"])

    assert feed.publish("B", TS, "tick", {"px": 1.0}) is None
    assert feed.snapshot() == {}

    allowed = feed.publish("A", TS, "tick", {"px": 2.0})
    assert allowed is not None and allowed.seq == 1
    assert feed.snapshot() == {"A": allowed}
    assert feed.poll() == [allowed]


def test_v12_close_semantics():
    """V12：close 幂等；关闭后 publish 拒绝、poll []、snapshot {}。"""
    feed = InMemoryStreamingFeed()
    feed.publish("A", TS, "tick", {"px": 1.0})
    feed.close()
    feed.close()

    with pytest.raises(RuntimeError):
        feed.publish("A", TS, "tick", {"px": 2.0})
    assert feed.poll() == []
    assert feed.snapshot() == {}
```

### 4.3 `tests/test_p042_fingerprint.py`（V13-V16）

```python
"""P-042 B4 数据指纹与合成夹具测试（V13-V16）。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from _synthetic_data import FACTOR_FILE, build_synthetic_config, build_synthetic_dataset
from core.data import DataManager


def test_v13_fingerprint_stable(tmp_path):
    """V13：同数据两实例指纹相等。"""
    build_synthetic_dataset(tmp_path)
    cfg = build_synthetic_config(tmp_path)

    first = DataManager(cfg).data_fingerprint()
    second = DataManager(cfg).data_fingerprint()

    assert first == second
    assert first.startswith("sha256:")


def test_v14_fingerprint_changes_with_price(tmp_path):
    """V14：改一个价格值 → 指纹变化。"""
    build_synthetic_dataset(tmp_path)
    cfg = build_synthetic_config(tmp_path)
    before = DataManager(cfg).data_fingerprint()

    close_path = tmp_path / "close.pkl"
    close = pd.read_pickle(close_path)
    close.iloc[0, 0] = float(close.iloc[0, 0]) + 1.0
    close.to_pickle(close_path)

    assert DataManager(cfg).data_fingerprint() != before


def test_v15_fingerprint_changes_with_factor(tmp_path):
    """V15：改一个因子值 → 指纹变化。"""
    build_synthetic_dataset(tmp_path)
    cfg = build_synthetic_config(tmp_path)
    before = DataManager(cfg).data_fingerprint()

    factor_path = tmp_path / FACTOR_FILE
    factor = pd.read_pickle(factor_path)
    factor.iloc[-1, -1] = float(factor.iloc[-1, -1]) + 1.0
    factor.to_pickle(factor_path)

    assert DataManager(cfg).data_fingerprint() != before


def test_v16_synthetic_dataset_contract(tmp_path):
    """V16：夹具写全 10 个 pkl，DataManager 可加载。"""
    data_dir = build_synthetic_dataset(tmp_path)
    expected = {
        "close.pkl",
        "open.pkl",
        "high.pkl",
        "low.pkl",
        "stock_adj.pkl",
        "suspend.pkl",
        "st.pkl",
        "industry.pkl",
        "mktcap.pkl",
        FACTOR_FILE,
    }
    assert {path.name for path in Path(data_dir).glob("*.pkl")} == expected

    dm = DataManager(build_synthetic_config(data_dir))
    assert dm.n_stocks == 5
    assert dm.n_dates == 20
    assert dm.suspend.shape == (20, 5)
    assert dm.industry is not None
    assert dm.mktcap is not None
```

### 4.4 既有测试订正

| 文件 | 改动 |
|------|------|
| `tests/test_contract_conformance.py` | `EXPECTED_MEMBERS[IDataManager]` +10；`MockDataProvider` / `_MockProvider` +`load_factor`（返回 `pd.DataFrame()`）；`test_mock_data_provider_members` 期望集 3 → 4；相关 docstring 数字同步 |
| `tests/test_p029_silent_exception_governance.py` | `_FakeDM` +`load_aux_raw`：按 `kind` 读 `self.data_dir / f"{kind}.pkl"`，缺失返回 `None`，损坏则 `pd.read_pickle` 抛错（保持 V1 三用例语义） |

### 4.5 红态预期（Step 9 首跑）

| 结果 | 用例 | 原因 |
|------|------|------|
| FAIL | V1/V2/V3 | `PklDataProvider.load_factor` / `DataManager` 端口调用不存在 |
| PASS | V4 | 非回归护栏（现状即正确） |
| FAIL | V5/V6 | agents 仍读 `data_dir`，`_AuxDM` 无该文件 → 缓存 `None` / 计数 0 |
| FAIL | V7 | 协议缺 10 属性 |
| FAIL | V8-V12 | `core.streaming` 不存在 |
| FAIL | V13-V16 | `data_fingerprint` / `_synthetic_data` 不存在 |

**聚合**：`1 passed, 15 failed`。

---

## 5. 低效排除表

| # | 低效操作 | 排除方式 | 判据 |
|---|----------|----------|------|
| 1 | 指纹逐单元格 `astype(str)` / CSV 规范化（1460×5688 → 千万级字符串） | 用 `pd.util.hash_pandas_object` 的 C 实现行哈希 | V13-V15 单次调用 < 1s（合成 20×5）；真实数据由缓存摊薄 |
| 2 | `load_factor` 先 `exists()` 再 `read_pickle`，provider 内再 `exists()` | 只保留 provider 内一次 `exists()`（D2 拒绝替代①） | `grep "因子文件不存在" core/data.py` = 0；`data_provider.py` = 1 |
| 3 | 指纹内重复触发 `get_adj_price` | `self.returns` 一次 + 五类价格各一次，全部走 `_cache` | 同实例二次 `data_fingerprint()` 无新增读盘（缓存命中） |
| 4 | 流式 `poll` 每次全量扫描 | 有界 `deque(maxlen=10_000)` + seq 游标；无生产消费方 | 扫描上限 = `maxlen`，不随累计事件数增长 |
| 5 | agents 为读两个 pkl 引入 `import pickle` | 改为门面薄方法，模块级无新增 import | `grep "import pickle" agents/agent_framework.py` = 0 |
| 6 | 测试各自临时写 pkl（重复代码 + 磁盘布局漂移） | 统一合成夹具一次写 10 文件 | 仅 `_synthetic_data.py` 出现 `to_pickle`（测试侧） |

---

## 6. 兼容性与版本

| 项 | 结论 |
|----|------|
| Python | `>=3.10`（[pyproject.toml:10](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L10)）；本机 3.12 |
| pandas | 锁 `3.0.3`（`uv.lock` L2533，marker `>=3.11,<3.14`）；`pd.util.hash_pandas_object` 存在（site-packages `pandas/util/__init__.py` L7-10，E3） |
| numpy | 锁 `2.4.6`（`uv.lock` L2316，marker `>=3.11`） |
| 新增依赖 | **0**（`hashlib` / `collections.deque` / `dataclasses` 均 stdlib） |
| Provider 兼容 | 3 → 4 方法：仓内仅 `PklDataProvider` + 2 个测试 Mock，全部覆盖；无第三方实现 |
| 协议兼容 | `IDataManager` +10 只读属性：运行期零变化；结构类型放宽 |
| 门面兼容 | `load_aux_raw` / `data_fingerprint` 为新增方法，无覆盖冲突 |
| 流式兼容 | 新模块，全仓零 import（`grep "core.streaming"` 仅测试） |
| 数据语义 | 复权 / 对齐 / 缺失 / 列填充零变更（V4 + golden 零重录） |

---

## 7. 门禁终态（Step 9 目标）

| 项 | 目标 |
|----|------|
| pytest | **794 passed**（778 + 16） |
| golden | **13 passed, 765 deselected**；`tests/golden/` 工作区干净 |
| mypy | `Success: no issues found in 104 source files` |
| black | `129`（core tests）/ `196`（全仓） |
| AST `except Exception` | **22**（新增 `except FileNotFoundError` 不计） |
| `tests/*.py` | **91** |
| `uv lock --check` | exit **0** |
| 新增 `# type: ignore` / `except Exception` | 0 / 0 |

---

## 8. 回退点（汇总）

| 批次 | 单提交 revert 后 |
|------|------------------|
| B1 | 因子读取回到 `pd.read_pickle` 直读；agents 回到 `data_dir` 直读；错误文案与计数语义不变 |
| B2 | 协议回到 9 成员；`FactorPipeline` 注解回 `DataManager`；`cast` 复原；运行期无差异 |
| B3 | `core/streaming.py` 与 5 用例消失；无生产引用 |
| B4 | 指纹与夹具消失；无生产引用 |

**跨批依赖**：B2 的 V7 依赖 B2 自身；B4 的指纹覆盖因子依赖 B1（B1 未合入时 `load_factor` 仍可读，指纹仍成立）。四批均可独立 revert。

---

## 9. Step 6 实施 Review（同基座独立视角，2026-11-18）

> **基座披露（RULE-4）**: 复审 DeepSeek-V4.1-Flash = 作者**同源**；RULE-5 不成立 → U-P042-1 继续 pending（Step 10 须 GLM-5.3-Flash）。

### 9.1 复核读数

| 组 | 项 | 实测 | 判定 |
|----|----|------|------|
| A | 变更锚点 | `data_provider.py` L18-31/L34-76；`data.py` L564-569/L616；`interfaces.py` L49-51；`factor.py` L21/L32；`engine_v2.py` L13/L228；`agent_framework.py` L976-994 | ✅ 全部命中 |
| A | `mktcap_file` 默认 | [config.py:361](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L361) `None` | ✅ D4 前提成立 |
| B | 签名可实现 | `PklDataProvider.load_factor` 仅用 `Path.exists` + `pd.read_pickle`，均在既有依赖内 | ✅ |
| B | `IDataManager` 属性名与实现逐名一致 | `close/open/high/low/adj_factor/suspend/st/industry/mktcap/universe` 与 `DataManager` 属性同名 | ✅ 无拼写漂移 |
| C | 版本可查 | pandas 3.0.3 / numpy 2.4.6 / pytest 9.0.3 / mypy 2.4.1 / black 26.5.1（`uv.lock`） | ✅ |
| C | `hash_pandas_object` 存在 | site-packages `pandas/util/__init__.py` L7-10 | ✅ |
| D | 计数 | 778+16=794；124+5=129；191+5=196；87+4=91；103+1=104 | ✅ 自洽 |
| E | 测试破坏面 | 仅 `test_contract_conformance.py` 与 `test_p029_...` 两文件 | ✅ |

### 9.2 发现与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S6-P042-1** | **P2** | V4 初稿拟用合成夹具验证「首因子日前 NaN」，但夹具因子首日 = 交易日首日（`dates[0]`）→ 该分支永不被覆盖，形成假绿 | V4 改为自带 6 日迷你数据集（因子从 `dates[2]` 起）+ 缺列 B 填 0；夹具因子首日同步改为 `dates[5]` |
| F-S6-P042-2 | P3 | `data_fingerprint` 中 `suspend`/`st` 在「文件缺失」时返回 0 填充帧而非 `None`，`absent` 仅在配置为 falsy 时出现 | 指纹 docstring 明示「缺失记 absent」指配置关闭；文件缺失由 0 帧参与哈希（确定性不变） |
| F-S6-P042-3 | P3 | `MarketEvent` 冻结为浅冻结：`payload` 内部可变 | 类 docstring 显式声明「payload 为浅冻结」；V8 只断言属性赋值失败 |
| F-S6-P042-4 | P3 | `poll(timeout)` 接受但忽略 `timeout`，易被误读为阻塞实现 | 类 docstring + DESIGN D5 + §5 低效表第 4 行三处一致声明 |

### 9.3 结论

**Step 6 Review pass（1 P2 + 3 P3 当轮回写）**——接口签名可实现、依赖版本可查、测试红态可观测、计数自洽；**准予进入 Step 7 CHECKLIST**。
**RULE-5**：同基座 → U-P042-1 pending（终审 GLM-5.3-Flash）。

---

## 10. Step 9 实施记录（2026-11-18）

### 10.1 落码

| 批次 | 文件 | 读数 |
|------|------|------|
| B1 | [data_provider.py](file:///f:/Coding/Factor_Trading_v3.0/core/data_provider.py) / [data.py](file:///f:/Coding/Factor_Trading_v3.0/core/data.py) / [agent_framework.py](file:///f:/Coding/Factor_Trading_v3.0/agents/agent_framework.py) | 端口 +`load_factor`（L33-35 / L82-86）；`load_factor` 改走端口 + `except FileNotFoundError`（L573-574 / L621-622）；`load_aux_raw`（L187-193）；agents L976-984 |
| B2 | [interfaces.py](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py) / [factor.py](file:///f:/Coding/Factor_Trading_v3.0/core/factor.py) / [engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py) | 10 属性（L52-100）+ TYPE_CHECKING L19；注解/import L21/L32；去 cast L13/L228 |
| B3 | [streaming.py](file:///f:/Coding/Factor_Trading_v3.0/core/streaming.py)（新建） | 105 行：`MarketEvent` / `IStreamingFeed` / `InMemoryStreamingFeed` |
| B4 | [data.py](file:///f:/Coding/Factor_Trading_v3.0/core/data.py) / [tests/_synthetic_data.py](file:///f:/Coding/Factor_Trading_v3.0/tests/_synthetic_data.py) | `data_fingerprint` + `_fingerprint_part`（L648-683）；夹具 96 行 |
| 测试 | 4 新建 + 2 订正 | `test_p042_data_contract.py`（7）/ `test_p042_streaming_contract.py`（5）/ `test_p042_fingerprint.py`（4）/ `_synthetic_data.py`；契约测试（3→4、9→19）/ P-029 `_FakeDM` |

### 10.2 红 → 绿

| 阶段 | 范围 | 读数 |
|------|------|------|
| 红（实现前） | `test_p042_data_contract.py test_p042_fingerprint.py` | **`9 failed, 2 passed in 2.17s`**（V1/V2/V3/V5/V6/V7/V13/V14/V15 FAIL；V4/V16 PASS） |
| 红（实现前） | `test_p042_streaming_contract.py` | **`1 error`**：`ModuleNotFoundError: No module named 'core.streaming'` |
| 红（实现前） | 既有 `test_contract_conformance.py` + `test_p029_...` | **`2 failed, 15 passed`**（协议成员集合 / Mock provider 缺 `load_factor`；P-029 全绿） |
| 绿（实现后） | 同五文件 | **`33 passed in 3.00s`** |

### 10.3 门禁（E1）

| 项 | 读数 |
|----|------|
| pytest 全量 | **`794 passed, 172 warnings in 48.96s`** |
| golden | **`13 passed, 781 deselected`**；`git status --short tests/golden/` 空 |
| mypy | **`Success: no issues found in 104 source files`** |
| black | `core tests` **129** / 全仓 **196** unchanged |
| AST `except Exception` | **22** |
| `tests/*.py` | **91** |
| `uv lock --check` | exit **0** |
| 不变式 grep | `pd.read_pickle` in `data.py` = **0**；`data_dir` in agents = **0**；`cast(` in `engine_v2` = **0**；`from_data_manager\|AbstractDataManager` = **0** |

### 10.4 实施期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P042-1 | P3 | IMPL §4.5 预测红态「1 passed, 15 failed」失准：**V16 仅依赖夹具 + 既有 `DataManager`，实现前即 PASS**；且 streaming 是**收集期 1 error**（非 5 个 FAIL） | 本节按实测拆分记录红态；CHECKLIST B17 按实测回填；DESIGN/IMPL 的预测行保留为历史口径并在本节订正 |
| F-S9-P042-2 | P3 | `data_fingerprint` 对同实例二次调用走缓存（低效表第 3 行承诺），但未单独立用例 | 记为观察；V13 已覆盖跨实例稳定性，缓存路径由 `_cache` 既有测试保护 |

**结论**：**Step 9 pass**——红 → 绿成立（16 新用例 + 2 既有文件），九项门禁全绿；B1-B4 全部落地。
