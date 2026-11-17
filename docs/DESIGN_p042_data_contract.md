# DESIGN：P-042 数据契约统一（B4 收口 + 流式契约）

> **批次**: P-042 · **Step 3 设计** · 日期 2026-11-18
> **判档**: **T1**（Layer-1：`core/`、`tests/`；`DataProvider` / `IDataManager` 属契约变更）
> **上游**: [RESEARCH_p042](RESEARCH_p042_data_contract.md)（§6 B1-B4 / §7 S1-S10 / §8 I1-I8 / §9 U-P042-1~5）；[PROGRESS §3.22](PROGRESS.md) P-004 B1-B3（done）
> **代码证据时点**: HEAD `9f0dbeb`（工作区仅文档）

---

## 1. 范围

| 项 | 内容 |
|----|------|
| 变更文件（生产 4） | [core/data_provider.py](file:///f:/Coding/Factor_Trading_v3.0/core/data_provider.py)（+`load_factor`）/ [core/data.py](file:///f:/Coding/Factor_Trading_v3.0/core/data.py)（`load_factor` 改走端口 / +`load_aux_raw` / +`data_fingerprint`）/ [core/interfaces.py](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py)（`IDataManager` +10 属性）/ [core/factor.py](file:///f:/Coding/Factor_Trading_v3.0/core/factor.py)（依赖倒置为 `IDataManager`） |
| 变更文件（生产 2） | [core/engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py)（移除 `cast`）/ [agents/agent_framework.py](file:///f:/Coding/Factor_Trading_v3.0/agents/agent_framework.py)（两处直读改门面） |
| 新建（生产 1） | `core/streaming.py`：`MarketEvent` + `IStreamingFeed` + `InMemoryStreamingFeed` |
| 新建（测试 4） | `tests/_synthetic_data.py`（夹具）、`tests/test_p042_data_contract.py`、`tests/test_p042_streaming_contract.py`、`tests/test_p042_fingerprint.py` |
| 订正（测试 2） | [tests/test_contract_conformance.py](file:///f:/Coding/Factor_Trading_v3.0/tests/test_contract_conformance.py)（成员集合 3→4、9→19）；[tests/test_p029_silent_exception_governance.py](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p029_silent_exception_governance.py)（`_FakeDM` 增 `load_aux_raw`） |
| 零改动面 | 复权/对齐/缺失语义、`filter/**`、`core/data_v3.py`、`core/manifest.py`、`tests/golden/**`、`pyproject.toml`、`uv.lock`、CI 命令 |
| 门禁口径 | pytest **778 → 794**（+16）/ golden **13 零重录** / mypy **103 → 104 files 0** / black `core tests` **124 → 129**（全仓 **191 → 196**）/ AST `except Exception` 恒 **22** / `tests/*.py` **87 → 91** / `uv lock` exit 0 |

---

## 2. 设计决策

### D1 分层与范围：契约收口，不合并实现

| 项 | 裁决 |
|----|------|
| `DataManager` ↔ `DataLoaderV3` | **不合并**（P-004 M-C 已证伪：V3 缺因子/复权/辅助/资产信息）；不复活 `from_data_manager` 等已删 API |
| L1 → L2 单向投影 | 仅测试用 `DataLoaderV3.from_pandas_dataframes` 验证等价；**不新增生产适配器**（U-P042-5） |
| 端口职责 | `DataProvider` 只做存储读取；`returns` / `get_adj_price` / `universe_status` **不进端口**（P-004 U-P004-2） |
| 被拒绝替代 | M-B「端口扩全」把门面能力灌入端口 → 端口成第二门面，改动 6 生产 + 19 测试，行为无法单批归因 |
| 代价 | agents 需要「原样辅助数据」时，门面新增 1 个薄方法 `load_aux_raw`（D4），而非把 `_provider` 暴露出去 |

### D2 `DataProvider.load_factor`：签名、错误语义、日志奇偶

[core/data_provider.py:18-31](file:///f:/Coding/Factor_Trading_v3.0/core/data_provider.py#L18-L31) 端口 3 → **4 方法**：

```python
    def load_factor(self, name: str) -> pd.DataFrame:
        """读取因子矩阵（data_dir 下的文件名）。"""
        ...
```

[core/data_provider.py:60-76](file:///f:/Coding/Factor_Trading_v3.0/core/data_provider.py#L60-L76) 同模块追加：

```python
    def load_factor(self, name: str) -> pd.DataFrame:
        path = self.data_dir / name
        if not path.exists():
            raise FileNotFoundError(f"因子文件不存在: {path}")
        return pd.read_pickle(path)
```

- **错误语义逐字保持**：`FileNotFoundError` 文案与 [data.py:564-566](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L564-L566) 完全一致（`config.data_dir` 为 `Path`，`Path / str` 结果相同）。
- **日志奇偶**：[data.py:568-618](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L568-L618) 的 `try` 现同时包住 `read_pickle` 与对齐；改后 `provider.load_factor` 仍在 `try` 内，但需新增 `except FileNotFoundError: raise` 分支——否则缺失文件也会被 `logger.error("加载因子数据 … 失败")`，与现状（存在性检查在 `try` 外、不记 error）不一致。
- **拒绝替代**：① 让 `DataManager` 保留 `file_path.exists()` 预检再调 provider → 双次 `stat`，且存在性判断分散两处；② 端口方法接受 `Path` 而非 `str` → 与现有 `load_factor(factor_file: str)` 公开签名冲突。
- **代价**：第三方自定义 provider 需补 1 方法（仓内实现仅 `PklDataProvider` + 2 个测试 Mock，均已覆盖）。

### D3 `IDataManager` 扩 10 属性（A1），拒绝协议拆分（A2）

[tests/test_contract_conformance.py:27-37](file:///f:/Coding/Factor_Trading_v3.0/tests/test_contract_conformance.py#L27-L37) 的 `EXPECTED_MEMBERS[IDataManager]` 由 9 → **19**：

| 属性 | 声明类型 | 依据 |
|------|----------|------|
| `close` / `open` / `high` / `low` / `adj_factor` | `pd.DataFrame` | filter L183-266 读价；factor 中性化经 `adj_price` |
| `suspend` | `Optional[pd.DataFrame]` | `cfg.suspend_file` 为 falsy 时实现可返回 `None`（[data.py:159-163](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L159-L163)）；消费方 L184 已判空 |
| `st` / `industry` / `mktcap` | `Optional[pd.DataFrame]` | [data.py:165-184](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L165-L184) 缺失保持 `None` |
| `universe` | `Optional[UniverseSnapshot]` | [data.py:193-199](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L193-L199)；filter L266 已 `getattr(..., None)` 判空 |
| `returns` | `pd.DataFrame` | 已在协议内，不重复 |

- `UniverseSnapshot` 走 `TYPE_CHECKING` 导入（[interfaces.py:17-18](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py#L17-L18) 新增一行），避免运行期依赖。
- **裁决 A1**（直接扩 `IDataManager`），拒绝 A2（新增 `IDataMatrixView` 只读子协议）：A2 会让 filter/factor 的构造参数类型再分叉，且当前只有一个实现；待出现第二个数据源（P-053）再拆（U-P042-2 关闭）。
- **代价**：协议变宽 10 成员；任何未来实现必须提供矩阵属性。仓内无第二实现（`APIDataManager` 仅存在于 docstring 示例）。

### D4 agents 越界：门面新增 `load_aux_raw`，不改用 `dm.industry` / `dm.mktcap`

**否决 RESEARCH S5 的 `dm.industry` / `dm.mktcap`**，理由是可证的零行为破坏：

| # | 差异 | 证据 |
|---|------|------|
| 1 | `dm.mktcap` 受 `cfg.mktcap_file` 门控，默认 `None` → 即使 `mktcap.pkl` 存在也返回 `None`；agents 现状「文件存在即读」 | [config.py:361](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L361) `mktcap_file: str \| None = None`；[data.py:179-184](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L179-L184) |
| 2 | `dm.industry` 经 `_load_and_align_data` 对齐：日期 `reindex(fill_value=0)`、列 `reindex(fill_value=0)`、日期范围过滤 → 原缺失日期/股票变成 `0`，`_get_stock_industry` 返回值由 `""` 变 `0` | [data.py:402-471](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L402-L471)；[agent_framework.py:1139-1146](file:///f:/Coding/Factor_Trading_v3.0/agents/agent_framework.py#L1139-L1146) |

**采纳**：[data.py](file:///f:/Coding/Factor_Trading_v3.0/core/data.py) 新增薄方法（不入 `IDataManager`，agents 形参本就是具体 `DataManager`）：

```python
    def load_aux_raw(self, kind: str) -> Optional[pd.DataFrame]:
        """按存储原样读取辅助数据（未对齐、不加默认值、缺失返回 None）。

        供 agents 等只读消费方替代 ``data_dir`` 直读（P-042 B1）；
        I/O 仍全部经 ``DataProvider``。
        """
        return self._provider.load_aux(kind)
```

[agent_framework.py:976-994](file:///f:/Coding/Factor_Trading_v3.0/agents/agent_framework.py#L976-L994) 两处替换（`import pickle` 一并删除）：

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

- 缺失文件 → `None`（现状 `path.exists()` 为假 → 跳过）；坏文件 → 抛错 → 计数 1（现状同理）。
- 已知代价：`load_aux_raw` 绕过 `_aux_loaded` 幂等 flag，若同进程后续访问 `dm.industry` 会二次读文件（只读、幂等、无行为差异）。

### D5 流式契约：`core/streaming.py`（U-P042-3）

放在 `core/streaming.py` 而非 `interfaces.py`：协议 + dataclass + 内存实现在一个模块，`interfaces.py` 继续只承载「引擎装配层」协议。

| 构件 | 规格 |
|------|------|
| `MarketEvent` | `@dataclass(frozen=True)`；字段 `symbol: str` / `ts: pd.Timestamp` / `kind: str`（`tick`\|`bar`\|`snapshot`）/ `payload: dict[str, Any]` / `seq: int` |
| `IStreamingFeed` | `snapshot() -> dict[str, MarketEvent]`；`poll(timeout: float \| None = None) -> list[MarketEvent]`；`subscribe(symbols: Iterable[str]) -> None`；`close() -> None` |
| `InMemoryStreamingFeed.__init__(maxlen: int = 10_000)` | `maxlen <= 0` → `ValueError`；内部 `deque(maxlen)` + 全局 `seq` 计数器 + `dict[symbol, MarketEvent]` 最新值 + `set[str]` 订阅 + `_closed` |
| `publish(symbol, ts, kind, payload) -> Optional[MarketEvent]` | 关闭后 `RuntimeError`；`kind` 不在三值内 `ValueError`；空 `symbol` `ValueError`；订阅集非空且 symbol 未订阅 → **不入队、返回 `None`、不消耗 seq**；否则 `seq += 1` 入队并返回事件 |
| `subscribe(symbols)` | **覆盖式**设置（非累加）；空列表 = 退化为「全订阅」 |
| `snapshot()` | 每 symbol 最新事件（当前已入队者）；关闭后返回 `{}` |
| `poll(timeout)` | 返回 `seq > cursor` 的已入队事件（按 seq 升序），并推进 cursor；无新事件返回 `[]`；关闭后返回 `[]`；**`timeout` 不阻塞**（内存实现无生产者线程，阻塞语义留给 P-053 实时适配器，参数仅为接口齐备） |
| `close()` | 幂等；不清理数据（`snapshot` 返回 `{}`、`poll` 返回 `[]` 即关闭语义） |

- **拒绝替代**：把 `timeout` 实现为 `threading.Condition.wait()` → 引入并发语义与测试复杂度，无消费方（B3 仅测试接入，无生产调用方）。
- **代价**：有界队列会丢最旧事件；`poll` 落后超过 `maxlen` 时静默丢事件——docstring 显式声明，不引入补偿。

### D6 `data_fingerprint()`：配置驱动的固定键集

```python
    def data_fingerprint(self) -> str:
        """返回数据矩阵指纹（同一数据同一指纹；任一值变化即变化）。"""
```

键集**由配置决定、与访问顺序无关**：
1. `_PRICE_KINDS` 五类（`close/open/high/low/adj_factor`）；
2. `returns`（派生，经 `get_adj_price`）；
3. `sorted(cfg.factor_files)`（逐个 `load_factor`）；
4. 四个辅助矩阵 `suspend/st/industry/mktcap`：`None` 记 `aux:<kind>:absent`，否则纳入。

单矩阵规范化（`_fingerprint_part`）：

```python
    @staticmethod
    def _fingerprint_part(label: str, frame: pd.DataFrame) -> str:
        rows = pd.util.hash_pandas_object(frame, index=True).to_numpy(dtype="<u8")
        head = (
            f"{label}|{frame.shape[0]}x{frame.shape[1]}|"
            + ",".join(map(str, frame.columns))
        ).encode("utf-8")
        return hashlib.sha256(head + rows.tobytes()).hexdigest()
```

最终 `"sha256:" + sha256("\n".join(parts))`（前缀风格与 [manifest.py:119-125](file:///f:/Coding/Factor_Trading_v3.0/core/manifest.py#L119-L125) 一致）。

- **裁决「配置驱动」**，拒绝「仅已加载矩阵」：后者使指纹依赖进程内访问顺序，两个加载顺序不同的同数据进程会得到不同指纹，直接违背「同数据同指纹」；配置驱动把「哪些矩阵属于本次运行」写死在配置里，跨进程可复现。
- **代价**：调用会触发懒加载（5 价格 + 因子 + 辅助），对已有缓存幂等；因子文件缺失时抛 `FileNotFoundError`（与 `preload_data` 一致）。
- **不复用** `_sha256_file`：文件哈希无法证明内存矩阵（对齐/填充后）一致（G5 要的是矩阵级）；文件哈希仍由 `build_manifest` 负责，两者互补。
- **不入 `IDataManager`**：当前无协议消费方；避免 B2 再扩 1 成员。

### D7 移除 `cast(DataManager, ...)`：`FactorPipeline` 依赖倒置

[engine_v2.py:228](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L228) 的 cast 是 G2 的泄漏证据。B2 同步：

| 文件 | 变更 |
|------|------|
| [core/factor.py:21](file:///f:/Coding/Factor_Trading_v3.0/core/factor.py#L21) | `from core.data import DataManager` → `from core.interfaces import IDataManager` |
| [core/factor.py:32](file:///f:/Coding/Factor_Trading_v3.0/core/factor.py#L32) | `data_manager: DataManager` → `IDataManager`（只用 `industry`/`mktcap`，均已入协议） |
| [core/engine_v2.py:13](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L13) | 若无其他 `cast` 调用，去掉 `cast` 导入 |
| [core/engine_v2.py:228](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L228) | `FactorPipeline(self.dm, self.cfg.factor)` |

- `self.dm` 声明为 `Optional[IDataManager]`（[engine_v2.py:164](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L164)）。若 mypy 报 Optional 实参：改用局部别名 + `assert dm is not None`（P-023 D4 手法），**不得回退为 `cast(DataManager, ...)`**。
- 循环导入检查：`interfaces.py` 只 import `core.config`（+ `TYPE_CHECKING` 两个类型），`factor.py` 不再 import `core.data`，无环。

---

## 3. 接口签名（逐字）

```python
# core/data_provider.py
class DataProvider(Protocol):
    def load_price(self, kind: str) -> pd.DataFrame: ...
    def load_aux(self, kind: str) -> Optional[pd.DataFrame]: ...
    def load_universe(self) -> Optional[UniverseSnapshot]: ...
    def load_factor(self, name: str) -> pd.DataFrame: ...

class PklDataProvider:
    def load_factor(self, name: str) -> pd.DataFrame: ...

# core/data.py（DataManager 新增公开成员）
    def load_aux_raw(self, kind: str) -> Optional[pd.DataFrame]: ...
    def data_fingerprint(self) -> str: ...

# core/interfaces.py（IDataManager 新增 10 属性）
    close: pd.DataFrame
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    adj_factor: pd.DataFrame
    suspend: Optional[pd.DataFrame]
    st: Optional[pd.DataFrame]
    industry: Optional[pd.DataFrame]
    mktcap: Optional[pd.DataFrame]
    universe: Optional[UniverseSnapshot]

# core/streaming.py（新建）
@dataclass(frozen=True)
class MarketEvent:
    symbol: str
    ts: pd.Timestamp
    kind: str
    payload: dict[str, Any]
    seq: int

class IStreamingFeed(Protocol):
    def snapshot(self) -> dict[str, MarketEvent]: ...
    def poll(self, timeout: Optional[float] = None) -> list[MarketEvent]: ...
    def subscribe(self, symbols: Iterable[str]) -> None: ...
    def close(self) -> None: ...

class InMemoryStreamingFeed:
    def __init__(self, maxlen: int = 10_000) -> None: ...
    def publish(
        self, symbol: str, ts: pd.Timestamp, kind: str, payload: dict[str, Any]
    ) -> Optional[MarketEvent]: ...
```

> 所有新签名带 `from __future__ import annotations` 语义；`streaming.py` 需 `from __future__ import annotations` 以支持 `list[...]` / `dict[...]`。

---

## 4. 批次规格（B1-B4）

### B1 端口收口

| # | 文件 / 锚点 | 改动 |
|---|-------------|------|
| 1 | [data_provider.py:18-31](file:///f:/Coding/Factor_Trading_v3.0/core/data_provider.py#L18-L31) | 协议 +`load_factor(name: str) -> pd.DataFrame` |
| 2 | [data_provider.py:34-76](file:///f:/Coding/Factor_Trading_v3.0/core/data_provider.py#L34-L76) | `PklDataProvider` +实现（存在性检查 + 逐字错误文案） |
| 3 | [data_provider.py:1-6](file:///f:/Coding/Factor_Trading_v3.0/core/data_provider.py#L1-L6) | 修正过期 docstring「本批不接线」「不接入 DataManager 调用路径」（P-004 已接线） |
| 4 | [data.py:564-569](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L564-L569) | `pd.read_pickle(file_path)` → `self._provider.load_factor(factor_file)`；`try` 加 `except FileNotFoundError: raise`；对齐/缓存/列填充零改动 |
| 5 | [data.py:160-185](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L160-L185) 后 | 新增 `load_aux_raw`（D4 代码块） |
| 6 | [agent_framework.py:976-994](file:///f:/Coding/Factor_Trading_v3.0/agents/agent_framework.py#L976-L994) | 两处 `data_dir` 直读 → `load_aux_raw`；删除方法内 `import pickle` |

回退点：单提交 revert 即回「因子直读 pkl + agents 直读 data_dir」。

### B2 协议收口

| # | 文件 / 锚点 | 改动 |
|---|-------------|------|
| 1 | [interfaces.py:25-95](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py#L25-L95) | +10 属性声明；`TYPE_CHECKING` +`UniverseSnapshot` |
| 2 | [factor.py:21](file:///f:/Coding/Factor_Trading_v3.0/core/factor.py#L21) / [:32](file:///f:/Coding/Factor_Trading_v3.0/core/factor.py#L32) | D7 依赖倒置 |
| 3 | [engine_v2.py:13](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L13) / [:228](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L228) | 去 cast（含导入清理） |
| 4 | [test_contract_conformance.py:27-37](file:///f:/Coding/Factor_Trading_v3.0/tests/test_contract_conformance.py#L27-L37) | `EXPECTED_MEMBERS[IDataManager]` 9 → 19 |

回退点：类型/成员声明，运行期零变化；revert 无副作用。

### B3 流式契约

| # | 文件 | 内容 |
|---|------|------|
| 1 | `core/streaming.py`（新建） | D5 全量规格；模块 docstring 声明「不接实时源、无生产调用方（P-053 接线）」 |
| 2 | `tests/test_p042_streaming_contract.py`（新建） | V8-V12 |

回退点：删除新模块与测试；零调用方。

### B4 可审计

| # | 文件 | 内容 |
|---|------|------|
| 1 | [data.py](file:///f:/Coding/Factor_Trading_v3.0/core/data.py) 尾部 | `data_fingerprint` + `_fingerprint_part`；`import hashlib` |
| 2 | `tests/_synthetic_data.py`（新建） | `build_synthetic_dataset(tmp_path, n_dates=20, n_stocks=5, seed=42) -> Path`；`build_synthetic_config(tmp_path) -> BacktestConfig`（`factor_files=["factor_value.pkl"]`、`mktcap_file="mktcap.pkl"`） |
| 3 | `tests/test_p042_fingerprint.py`（新建） | V13-V16 |

合成夹具写 9 个 pkl：`close/open/high/low/stock_adj/suspend/st/industry/mktcap` + `factor_value`；数值由 `np.random.default_rng(seed)` 生成，价格严格为正，`adj_factor=1.0`，`suspend/st=0`，`industry` 为 `0..3` 整数；不写 `universe/`（缺失走降级快照，`universe_status` 不参与指纹）。

回退点：删除方法与夹具；无生产调用方。

---

## 5. 测试策略（16 用例）

| ID | 文件 | 用例 | 红态（实施前） |
|----|------|------|----------------|
| V1 | data_contract | `test_pkl_provider_load_factor_roundtrip`：写 pkl → `PklDataProvider.load_factor` 逐值相等 | FAIL（`AttributeError`） |
| V2 | data_contract | `test_pkl_provider_load_factor_missing_raises`：缺文件 → `FileNotFoundError` 且文案含 `因子文件不存在:` | FAIL（`AttributeError`） |
| V3 | data_contract | `test_load_factor_goes_through_provider`：spy provider 记录 `load_factor` 调用 == `["factor_value.pkl"]` | FAIL（调用数 0） |
| V4 | data_contract | `test_load_factor_alignment_semantics_unchanged`：3 个因子日 → 对齐到 20 交易日（最近过去值）、首因子日前为 NaN、缺列填 0 | **PASS**（非回归护栏） |
| V5 | data_contract | `test_agent_framework_caches_industry_via_facade`：`load_aux_raw` 返回值被缓存、`failure_stats == {}` | FAIL（`_industry_data` 仍 `None`） |
| V6 | data_contract | `test_agent_framework_cache_failure_still_counted`：`load_aux_raw` 抛错 → `{"industry_cache": 1}` 且缓存 `None` | FAIL（计数 0） |
| V7 | data_contract | `test_idatamanager_covers_data_layer_consumers`：12 个消费成员 ⊆ `dir(IDataManager)` 且 ⊆ `dir(DataManager())` | FAIL（10 缺失） |
| V8 | streaming | `test_seq_monotonic_across_symbols`：跨 symbol 发布 seq 严格递增；`MarketEvent` 冻结（赋值抛 `FrozenInstanceError`） | FAIL（`ImportError`） |
| V9 | streaming | `test_snapshot_returns_latest_per_symbol`：A1/B1/A2 → `{A:A2, B:B1}` | FAIL（`ImportError`） |
| V10 | streaming | `test_poll_returns_delta_in_order_and_empty_after`：首次 3 条按序、二次 `[]`、第三次再发只返回新事件 | FAIL（`ImportError`） |
| V11 | streaming | `test_subscribe_limits_publish`：`subscribe(["A"])` 后发 B → `None`、snapshot 无 B；发 A → 事件 | FAIL（`ImportError`） |
| V12 | streaming | `test_close_is_idempotent_and_blocks_publish`：双 close 不抛；close 后 publish `RuntimeError`、poll `[]`、snapshot `{}` | FAIL（`ImportError`） |
| V13 | fingerprint | `test_fingerprint_stable_across_instances`：同夹具两实例指纹相等 | FAIL（`AttributeError`） |
| V14 | fingerprint | `test_fingerprint_changes_when_price_changes`：改 close 单值（重写 pkl + 新实例）→ 指纹不同 | FAIL（`AttributeError`） |
| V15 | fingerprint | `test_fingerprint_includes_factor_matrix`：改 `factor_value.pkl` 单值 → 指纹不同 | FAIL（`AttributeError`） |
| V16 | fingerprint | `test_synthetic_dataset_matches_config`：9 文件存在；`n_stocks==5`、`n_dates==20`、`suspend.shape==(20,5)`、`industry is not None` | FAIL（`ImportError`） |

**聚合红态**：V4 唯一 PASS，其余 15 FAIL（`1 passed, 15 failed`）。绿态：16 passed，全量 778 → **794**。

**既有测试订正（必然耦合，2 文件）**：
- `test_contract_conformance.py`：`EXPECTED_MEMBERS[IDataManager]` +10；`MockDataProvider` / `_MockProvider` +`load_factor`；`test_mock_data_provider_members` 期望集 3 → 4。
- `test_p029_silent_exception_governance.py::_FakeDM` +`load_aux_raw`（按 `kind` 读 `data_dir/<kind>.pkl`，缺失返回 `None`，损坏则抛错）——保持 V1 三用例的失败计数语义不变。

---

## 6. 不变式

| ID | 不变式 | 判据 |
|----|--------|------|
| I1 | 价格/辅助/universe 仍只经 `_provider` 读取 | `grep -n "read_pickle" core/data.py` = 0 |
| I2 | `load_factor` 不再直接 `pd.read_pickle` | 同上；且 `grep "_provider.load_factor"` = 1 |
| I3 | 注入 Mock provider 后价格与因子读取均被观测 | V3 + 既有 `test_data_manager_accepts_injected_provider` |
| I4 | `IDataManager` ⊇ filter/factor 实际消费集合 | V7（12 成员） |
| I5 | 同数据指纹稳定、单值变则变 | V13/V14/V15 |
| I6 | seq 单调、snapshot+delta 重放一致、空 poll `[]` | V8-V10 |
| I7 | golden 13 零重录；pytest 778 → 794；mypy 104 files 0；black 129/196；AST 22；uv exit 0 | Step 9 逐条复跑 |
| I8 | 不新增 `live/`、不新增外部依赖、不复活 P-004 已删 API | `git status` + `uv.lock` diff 空 |
| I9 | `load_aux_raw` / `data_fingerprint` 不入 `IDataManager` | V7 显式集合不含二者 |
| I10 | `agents/` 无 `data_dir` 直读 | `grep -n "data_dir" agents/agent_framework.py` = 0（`data_manager.data_dir` 两处消失） |
| I11 | `filter/**`、`data_v3.py`、`manifest.py`、`golden/**` 零 diff | `git diff --stat` |
| I12 | 复权/对齐/缺失语义零变更 | V4 + 既有 `test_adjustment*` / `test_data_aux_defaults` 全绿 |

---

## 7. 风险预案

| ID | 风险 | 预案 |
|----|------|------|
| R1 | `FileNotFoundError` 文案路径不一致（相对/绝对） | V2 断言 `str(tmp_path)` 子串；`config.data_dir` 为 `Path`，两侧同源 |
| R2 | 移除 cast 后 mypy 报 Optional 实参 | 局部别名 + `assert`（D7）；仍失败则保留 cast 并登记 U-P042-6（P3），不阻断 B1/B3/B4 |
| R3 | `data_fingerprint` 在只有 close 的 Mock provider 上被调用 → 缺文件抛错 | 仅 B4 测试用合成夹具；方法 docstring 声明「需要完整数据面」；无生产调用方 |
| R4 | `hash_pandas_object` 跨 pandas 版本变化 | 指纹只用于同锁文件内跨进程比较；`uv.lock` 钉版本；docstring 声明不跨版本承诺 |
| R5 | agents 双读（`load_aux_raw` + 后续 `dm.industry`） | 只读且幂等；D4 已声明 |
| R6 | P-029 测试 `_FakeDM` 改动引入假绿 | `load_aux_raw` 复刻真实 I/O（读同一 `data_dir`），三用例断言（计数/缓存 None/零 WARNING）逐字不变 |
| R7 | 新增文件破坏 black/mypy 计数 | 新建 5 文件均纳入既有命令；Step 9 以末行读数回填 |
| R8 | `streaming.py` 引入并发/时区语义 | 不做线程、不做 tz 转换；`ts` 原样保存 |

---

## 8. 已知局限

- O-P042-1：`IStreamingFeed` 无生产消费方，`InMemoryStreamingFeed` 只证明契约可测，不证明实时源可接（P-053）。
- O-P042-2：`timeout` 不阻塞；阻塞/背压语义后置。
- O-P042-3：指纹不覆盖 `universe` 快照与配置文件（分别由 `universe_status.data_version` 与 `manifest` 负责）。
- O-P042-4：`load_aux_raw` 是门面上的存储语义出口，属于「零行为」妥协；待 agents 改为消费对齐矩阵后可删。

---

## 9. Step 3 自查

| # | 项 | 结论 |
|---|----|------|
| 1 | 每个决策有被拒替代 + 代价 | ✅ D1-D7 均列 |
| 2 | 接口签名可机械核验 | ✅ §3 逐字；V1-V3/V8 逐签名断言 |
| 3 | 行为变更边界 | ✅ B1/B2 零行为（V4 护栏 + golden 零重录）；B3/B4 仅新增只读面 |
| 4 | 计数自洽 | ✅ 778+16=794；124+5=129；191+5=196；87+4=91；103+1=104 |
| 5 | 测试破坏面封闭 | ✅ 仅 2 个既有测试文件必改，均列出具体行与理由 |
| 6 | 不复活 P-004 已删 API | ✅ D1 明示 |
| 7 | 零外部依赖 | ✅ 仅 `hashlib` / `collections.deque` / `dataclasses`（stdlib） |

---

## 10. Step 4 设计 Review（同基座独立视角，2026-11-18）

> **基座披露（RULE-4）**: 复审 DeepSeek-V4.1-Flash = 作者**同源**；RULE-5 不成立 → U-P042-1 继续 pending（Step 10 须 GLM-5.3-Flash）。

### 10.1 机械复核

| 组 | 项 | 实测 | 判定 |
|----|----|------|------|
| A | 端口现状 3 方法；`load_factor` 无端口 | 读 [data_provider.py:18-31](file:///f:/Coding/Factor_Trading_v3.0/core/data_provider.py#L18-L31) | ✅ D2 依据成立 |
| A | 因子直读锚点 | [data.py:564-569](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L564-L569) `pd.read_pickle` | ✅ |
| A | `config.data_dir` 为 `Path` | [config.py:341](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L341) | ✅ R1 成立 |
| B | `mktcap_file` 默认 `None` | [config.py:361](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L361) | ✅ D4 理由 1 成立 |
| B | `dm.industry` 对齐会填 0 | [data.py:448-471](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L448-L471) | ✅ D4 理由 2 成立 |
| B | agents 消费原样索引 | [agent_framework.py:1139-1146](file:///f:/Coding/Factor_Trading_v3.0/agents/agent_framework.py#L1139-L1146) | ✅ 否决 S5 有据 |
| C | `FactorPipeline` 仅用 `industry`/`mktcap` | `grep "self.dm." core/factor.py` = 4 行 / 2 属性（L337-338、L350-351） | ✅ D7 可行 |
| C | `engine_v2` 仅 1 处 `cast(` | L13 导入 / L228 使用 | ✅ 导入可删 |
| C | 无 pandas-stubs → pandas 类型为 `Any` | `pyproject.toml` 无 stubs 项 | ✅ 协议扩展类型风险低 |
| D | 无第二生产 Provider 实现 | 生产侧 `class .*Provider` = 2（协议 + Pkl）；测试侧 2 Mock | ✅ 破坏面封闭 |
| E | 计数 | 778+16 / 124+5 / 191+5 / 87+4 / 103+1 | ✅ 自洽 |

### 10.2 发现与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S4-P042-1 | P2 | D4 初稿直接沿用 RESEARCH S5 的 `dm.industry/mktcap`，未核 `mktcap_file` 默认 `None` → 会让 agents 在默认配置下丢掉本可读到的市值数据（静默行为回退） | 改为 `load_aux_raw`（D4），逐条列出两处差异证据；RESEARCH S5 按 DESIGN 覆盖 |
| F-S4-P042-2 | P3 | `load_factor` 改走端口后，`FileNotFoundError` 会落入 `except Exception` 的 error 日志，破坏日志奇偶 | D2 显式增加 `except FileNotFoundError: raise`；B1 第 4 项写入规格 |
| F-S4-P042-3 | P3 | 指纹「仅已加载」会造成访问顺序依赖，V13 跨实例不稳定 | D6 改为配置驱动固定键集，并写明拒绝理由 |
| F-S4-P042-4 | P3 | P-029 `_FakeDM` 无 `load_aux_raw`，price 用例会多出 `industry_cache` 计数 | §5 明确 `_FakeDM` 必改及其 I/O 复刻语义（R6） |

### 10.3 结论

**Step 4 Review pass（1 P2 + 3 P3 当轮回写）**——接口签名逐字、计数自洽、行为边界可核验、测试破坏面封闭；**准予进入 Step 5 IMPL**。
**RULE-5**：同基座 → U-P042-1 pending（终审 GLM-5.3-Flash）。
