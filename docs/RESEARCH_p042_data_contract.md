# RESEARCH：P-042 数据契约统一

> **批次**: P-042 · **Step 1 调研** · 日期 2026-11-17
> **判档**: **T1**（Layer-1：`core/`、`tests/`；契约变更）
> **上游**: [UPGRADE_MASTER_PLAN.md §5](UPGRADE_MASTER_PLAN.md) P-042；[PROGRESS §3.22](PROGRESS.md) P-004（数据层统一，done）；[RESEARCH_p004](RESEARCH_p004_data_layer_unification.md)（B4 / U-P004-1~4）；[PROGRESS §1.4](PROGRESS.md) 台账
> **代码证据时点**: HEAD `9f0dbeb`（总纲二轮复审后；工作区仅文档）
> **基座**: DeepSeek-V4.1-Flash（Step 2 Review 同源 → 登记 U-P042-1；终审须异构）

---

## 1. 触发与题干

- **触发**: 用户「开始 P-042 数据契约统一」；总纲 §5 P-042 要求「`IDataManager`/`DataProvider`/`IStreamingFeed` 三契约收敛；`data.py`/`data_v3.py`/`data_provider.py` 归并」。
- **前置事实（必须先读）**: **P-004 已完成数据层统一 B1-B3**（[PROGRESS §3.22](PROGRESS.md)）——`DataManager` 已注入 `DataProvider`、三个未使用 API 已删除、协议签名已对齐；并明确把 **B4（端口扩全）** 与 **agents 直读 `data_dir`（U-P004-4）** 后置。**本批不得重做 P-004**，只承接其 B4 与残余契约缺口。
- **题干收窄（不扩做）**:
  1. **端口收口**：`DataProvider` 增 `load_factor`，让因子读取不再绕过端口；
  2. **协议收口**：`IDataManager` 补齐 filter/factor 实际消费的矩阵属性（或引入只读视图协议）；
  3. **agents 越界收口**：`agent_framework` 两处 `data_dir` 直读改走端口/门面；
  4. **流式契约**：定义 `IStreamingFeed` + `MarketEvent` + 内存 fake（**不接实时源、不建 `live/`**）；
  5. **可审计**：`DataManager.data_fingerprint()` + 合成夹具 + golden 零重录；
  6. **明确不做**：`DataManager` ↔ `DataLoaderV3` 合并（P-004 M-C 已证伪）、复权/对齐/缺失语义变更、DuckDB、Tushare/AKShare 接入、任何 `live/` 代码。

- **职责外（不回答）**: 实时行情网关/柜台适配（P-053）；舆情数据源（P-049）；微服务部署（P-055）。
- **能力边界（回答不了）**: 无真实第二数据源，适配器可替换性只由 Mock provider + 合成夹具证明，不由生产切换证明。

---

## 2. 代码事实基线（E3 @`9f0dbeb`）

### 2.1 三层构件与角色（P-004 结论沿用）

| 层 | 构件 | 角色 | 公开面 |
|----|------|------|--------|
| L0 存储端口 | `core/data_provider.py` `DataProvider`（Protocol）+ `PklDataProvider` | 只读 I/O：价格 / 辅助 / 股票池 | **3 方法**：`load_price` / `load_aux` / `load_universe` |
| L1 业务门面 | `core/data.py` `DataManager` | 对齐 / 缓存 / 复权 / 收益率 / 因子 / 资产信息 / 股票池状态 | P-004 实测 **24 公开成员**（16 属性 + 8 方法） |
| L2 NumPy 物化器 | `core/data_v3.py` `DataLoaderV3` | 纯内存 DataFrame → NumPy 切片视图 | `from_pandas_dataframes` / `get_slice` / `save` / `load` / 索引映射 |

> **P-004 关键裁决**: 「`DataLoaderV3` 取代 `DataManager`」**已证伪**（V3 缺因子/复权/辅助/资产信息能力；`from_data_manager` 外部调用 0）。本批**不重试合并**，只定义单向投影：L1 矩阵 → `DataLoaderV3.from_pandas_dataframes`。

### 2.2 端口 / 门面 / 物化器能力矩阵

| 能力 | `DataProvider` | `DataManager` | `DataLoaderV3` |
|------|----------------|---------------|----------------|
| 原始价格 open/high/low/close | ✅ `load_price` | ✅ 属性 + 日期/列对齐 + 缓存 | ❌（由调用方喂 DataFrame） |
| 复权因子 | ✅ `load_price("adj_factor")` | ✅ 属性 + **三段式 ffill**（P-039） | ❌ |
| 辅助 suspend/st/industry/mktcap | ✅ `load_aux` | ✅ 安全默认值（缺失 0/None） | ❌ |
| 股票池快照 | ✅ `load_universe` | ✅ `universe` / `universe_status` | ❌ |
| 因子 | ❌ **缺口 G1** | ✅ `load_factor`，但**直接 `pd.read_pickle`（L564-569）绕过端口** | ✅ `factor_data`（由调用方喂） |
| 收益率 / 复权价 | ❌（派生留门面，P-004 U-P004-2 裁决） | ✅ `returns` / `get_adj_price` | ❌ |
| 资产信息 | ❌（配置面） | ✅ `get_asset_info` | ✅ `get_asset_info` |
| 流式增量 | ❌ **缺口 G4** | ❌ | ❌ |

### 2.3 消费方与契约泄漏

| 消费方 | 实际使用成员 | 是否在 `IDataManager` 协议 |
|--------|--------------|----------------------------|
| `filter/universe_filter_clean.py` | `trade_dates` / `stock_codes` / `close` / `open` / `adj_factor` / `suspend` / `st` / `industry` / `mktcap` / `universe` | **否（G2）**：`close/open/adj_factor/suspend/st/industry/mktcap/universe` 均未声明 |
| `core/factor.py` | `industry` / `mktcap` / `load_factor` / `get_adj_price` | 部分（`industry/mktcap` 未声明） |
| `core/engine_v2.py` | `trade_dates` / `stock_codes` / `n_stocks` / `returns` / `load_factor` / `get_adj_price` / `get_data_info` / `universe_status` | ✅（B3 已对齐） |
| `agents/agent_framework.py` | `data_manager.data_dir / "industry.pkl"` / `"mktcap.pkl"`（L979/L989） | **否（G3）**：绕过门面与端口 |
| `agents/multi_strategy_engine.py` | `DataManager(base_config)` 构造 | 构造点，不涉契约 |

> **G2 的影响**: `IDataManager` 只覆盖 9-10 个成员，而 filter/factor 依赖 8 个协议外属性——「面向 Protocol 编程」在数据层是**名义成立、实际泄漏**；`cast(DataManager, self.dm)`（engine_v2 L228）即泄漏证据。

### 2.4 已删除 / 不可达路径（P-004 结论，禁止复活）

- `DataLoaderV3.from_data_manager` / `_load_from_data_manager` / `to_data_manager_compatible` / `from_hdf5` 已删除（P-004 B2）。
- `AbstractDataManager` 已删除（P-004 B2 观察 1）。
- `DataManager` ↔ `DataLoaderV3` 合并不可达（P-004 M-C 证伪）；本批**不重新引入**上述 API。

---

## 3. E1 取证（可重放）

| 读数 | 命令 / 方法 | 结果 |
|------|-------------|------|
| A 端口方法数 | Read `core/data_provider.py` L18-31 | **3**：`load_price` / `load_aux` / `load_universe` |
| B 因子直读 | Read `core/data.py` L550-618 | **L564-569 `pd.read_pickle(file_path)`**，未调用 `self._provider` |
| C 端口注入 | Read `core/data.py` L37-46 / L81-103 | 构造参数 `provider`；缺省 `_build_provider(config)`；价格/辅助/universe 均走 `self._provider` |
| D agents 越界 | Read `agents/agent_framework.py` L979/L989 | `data_manager.data_dir / "industry.pkl"` / `"mktcap.pkl"` |
| E 协议成员 | Read `core/interfaces.py` L25-95 | `trade_dates/stock_codes/n_stocks/universe_status/returns/get_adj_price/load_factor/get_data_info/get_asset_info`；无矩阵属性 |
| F filter 消费 | Read `filter/universe_filter_clean.py` L183-371 | `close/open/adj_factor/suspend/st/industry/mktcap` 等协议外成员 |
| G factor 消费 | Read `core/factor.py` L337/L350 | `dm.industry` / `dm.mktcap` |
| H 契约测试 | Read `tests/test_contract_conformance.py` L140-201 | `MockDataProvider` 3 成员；`test_data_manager_accepts_injected_provider` 已存在 |
| I V3 兼容测试 | Read `tests/test_data_v3_compatibility.py` | 仅 `from_pandas_dataframes` / save/load / factor_dict；无 `from_data_manager` |
| J 清单指纹 | Read `core/manifest.py` L59-67 / L119-165 | 已有 `_sha256_file` 与 `build_manifest(data_dir, data_files)` |
| K 基线门禁 | P-041 关闭 CI（`44096505783` / `44101454276`） | pytest **778** / golden **13·765** / black **124·191** / mypy **103 files 0** / AST **22** / `tests/*.py` **87** / uv **0** |

> 本批 Step 1 为只读取证，未运行 pytest/git（工作区当前为 docs-only 修订态）；K 读数沿用 P-041 关闭基线，Step 9 必须本批复跑。

---

## 4. 缺口清单

| ID | 缺口 | 级别 | 证据 |
|----|------|------|------|
| **G1** | `DataManager.load_factor` 绕过 `DataProvider`，因子 I/O 仍是第二存储路径 | P2 | B |
| **G2** | `IDataManager` 未声明 filter/factor 实际消费的 8 个矩阵属性 → 契约泄漏 | P2 | E/F/G |
| **G3** | `agent_framework` 两处直读 `data_dir` 下的 `industry.pkl`/`mktcap.pkl`（U-P004-4 未关） | P2 | D |
| **G4** | 无 `IStreamingFeed` / `MarketEvent` 契约；实时路径无最小可测形态 | P2 | 2.2 能力矩阵 |
| **G5** | 无矩阵级数据指纹；golden 零重录只能靠人工比对 | P3 | J |
| **G6** | 无统一合成夹具；数据层测试各自临时写 pkl（`test_phase1_data` 等） | P3 | 读码 |

---

## 5. 方案矩阵

| 方案 | 内容 | 判定 |
|------|------|------|
| **M-A（推荐）** | **契约收口，不合并实现**：① `DataProvider` 增 `load_factor`，`DataManager.load_factor` 改走端口；② `IDataManager` 补齐矩阵属性；③ agents 两处直读改门面；④ 新增 `IStreamingFeed` + `InMemoryStreamingFeed`；⑤ `data_fingerprint()` + 合成夹具；⑥ 明确不合并 V1/V3 | ✅ 最小、零行为、可分批；直接关闭 G1-G6 |
| M-B | 端口扩全：`returns`/`get_adj_price`/`universe_status`/`data_dir` 全部进端口，消费方改依赖端口 | ❌ 端口会变成第二门面（P-004 U-P004-2 裁决）；改动 6 生产 + 19 测试，行为无法单批归因 |
| M-C | `DataLoaderV3` 取代 `DataManager` | ❌ P-004 M-C 已证伪；V3 缺 5 类能力、死 API 已删 |
| M-D | 仅文档标注契约，不改代码 | ❌ 不满足 P-042 验收（G1-G6 仍在） |
| M-E | 先做流式契约、数据端口后置 | ❌ G1-G3 是当前生产真实缺口；流式无消费方，优先会空转 |

**裁决**: **M-A**。理由：唯一同时满足「零行为变更 / 不复活 P-004 已删 API / 关闭真实缺口 / 保持端口为纯存储」的方案；与 D5「宜粗不宜细、先跑通」一致。

---

## 6. 批次切分（供 DESIGN 采用）

| 批次 | 内容 | 行为 | 验收 |
|------|------|------|------|
| **B1 端口收口** | `DataProvider.load_factor(name)`；`PklDataProvider` 实现；`DataManager.load_factor` 改走端口；`agent_framework` 两处改 `dm.industry`/`dm.mktcap`（或 `provider.load_aux`） | 零行为 | 因子读取经 provider（spy 断言）；pytest 778 持平；golden 13 零重录 |
| **B2 协议收口** | `IDataManager` 增 `close/open/high/low/adj_factor/suspend/st/industry/mktcap/universe` 属性声明；移除 engine_v2 的 `cast(DataManager, ...)`（如类型通过） | 类型面 | mypy 103 files 0；契约测试成员集合扩展；运行期零变化 |
| **B3 流式契约** | `core/streaming.py`：`MarketEvent` dataclass + `IStreamingFeed` Protocol + `InMemoryStreamingFeed` | 新增面 | seq 单调 / snapshot+delta 重放 / 空 poll 三组契约测试 |
| **B4 可审计** | `DataManager.data_fingerprint()`（矩阵 sha256）；`tests/_synthetic_data.py` 合成夹具；golden 零重录门禁 | 新增面 | 指纹稳定/变更敏感；合成夹具可独立跑通；golden 13 零重录 |

> 四批可独立提交；B1/B2 为「零行为」，B3/B4 为「新增只读面」，均不触碰复权/对齐/缺失语义。

---

## 7. 精确语义（实施规格输入）

| # | 语义 |
|---|------|
| S1 | `DataProvider.load_factor(name: str) -> pd.DataFrame`：按 `data_dir / name` 读取；文件不存在抛 `FileNotFoundError`（与 `DataManager.load_factor` 现文案一致） |
| S2 | `DataManager.load_factor` 保留现有对齐/缓存/列填充逻辑；仅把 `pd.read_pickle` 替换为 `self._provider.load_factor(factor_file)` |
| S3 | `DataProvider` 仍只做**存储读取**；`returns`/`get_adj_price`/`universe_status` 等派生**不进端口**（P-004 U-P004-2 裁决） |
| S4 | `IDataManager` 新增属性均为**只读**，类型与 `DataManager` 现有返回一致（`pd.DataFrame` / `Optional[pd.DataFrame]` / `UniverseSnapshot`） |
| S5 | `agent_framework` 两处直读改为 `data_manager.industry` / `data_manager.mktcap`；缺失时保持现有 `None` 跳过语义 |
| S6 | `MarketEvent` 字段：`symbol: str`、`ts: pd.Timestamp`、`kind: str`（`tick`/`bar`/`snapshot`）、`payload: dict`、`seq: int` |
| S7 | `IStreamingFeed`：`snapshot() -> dict[str, MarketEvent]`、`poll(timeout: float \| None = None) -> list[MarketEvent]`、`subscribe(symbols: Iterable[str]) -> None`、`close() -> None` |
| S8 | `InMemoryStreamingFeed`：`publish(event)` 追加到有界队列；`seq` 全局单调；`snapshot()` 返回每 symbol 最新事件；`poll()` 按序返回增量 |
| S9 | `data_fingerprint()`：对 `close/open/high/low/adj_factor/returns` 与已加载因子/辅助矩阵，按「index ISO 日期 + columns + float64 values」规范化后 sha256；同数据同指纹，任一值变则变 |
| S10 | 合成夹具：`build_synthetic_dataset(tmp_path, n_dates=20, n_stocks=5, seed=42)` 写全价格/辅助/factor/universe；供 P-042 测试独立使用，不改既有测试 |

> **DESIGN 覆盖（F-S4-P042-1，2026-11-18）**: **S5 已否决**——`dm.industry`/`dm.mktcap` 会引入两处零行为破坏（`mktcap_file` 默认 `None` 门控；对齐 `fill_value=0` 使 `_get_stock_industry` 由 `""` 变 `0`），改用门面薄方法 `load_aux_raw(kind)`；权威规格见 [DESIGN_p042 §D4](DESIGN_p042_data_contract.md)。

---

## 8. 行为变更与不变式

**零行为变更（B1/B2）**：价格/辅助/universe 读取路径不变；因子对齐/缓存/列填充不变；filter/factor 计算结果不变；golden G1-G7 零重录。
**新增只读面（B3/B4）**：`IStreamingFeed`、`InMemoryStreamingFeed`、`data_fingerprint`、合成夹具；无生产调用方（P-042 仅测试接入）。

| ID | 不变式 |
|----|--------|
| I1 | `DataManager` 的价格/辅助/universe 仍只经 `self._provider` 读取（grep 无直接 `read_pickle`） |
| I2 | `DataManager.load_factor` 不再直接 `pd.read_pickle`（grep 0） |
| I3 | 注入 `MockDataProvider` 后，价格与因子读取均被观测（spy 计数） |
| I4 | `IDataManager` 成员集合 ⊇ filter/factor 实际消费集合（静态检查） |
| I5 | 合成夹具下 `data_fingerprint()` 稳定；改一个价格值指纹变化 |
| I6 | `IStreamingFeed` seq 单调、snapshot+delta 重放一致、空 poll 返回 `[]` |
| I7 | pytest 基线 778 → 778+新增；golden 13 零重录；mypy 103 files 0；AST `except Exception` 恒 22；uv lock exit 0 |
| I8 | 不新增 `live/` 目录、不新增外部数据依赖、不复活 P-004 已删 API |

---

## 9. 未决项登记（四元块）

- **U-P042-1 异构终审**
  - 判据：Step 2/4/6/8/10 复审基座与作者不同
  - 触发条件：进入 Step 10
  - 当前倾向：作者 DeepSeek-V4.1-Flash；终审由 GLM-5.3-Flash 承接
  - 证据等级：E1（会话基座）

- **U-P042-2 协议拆分（A1 vs A2）**
  - 判据：`IDataManager` 直接扩属性（A1）是否导致协议过宽；若 filter/factor 需要独立只读视图则选 A2
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**A1**（最小改动；A2 留后续）
  - 证据等级：E3（G2）

- **U-P042-3 `IStreamingFeed` 放置位置**
  - 判据：放 `core/interfaces.py`（跨层协议唯一入口）还是 `core/streaming.py`（含 dataclass/fake）
  - 触发条件：Step 3 DESIGN
  - 当前倾向：`core/streaming.py`（协议 + dataclass + fake 同模块，避免 interfaces.py 膨胀）
  - 证据等级：E3（架构原则）

- **U-P042-4 指纹范围**
  - 判据：是否纳入 suspend/st/industry/mktcap（影响掩码/中性化）
  - 触发条件：Step 3 DESIGN
  - 当前倾向：纳入**已加载**矩阵；未加载不触发读取（避免副作用）
  - 证据等级：E3（G5）

- **U-P042-5 `DataLoaderV3` 投影**
  - 判据：是否需要生产级 `DataManager → DataLoaderV3` 适配器
  - 触发条件：V3 引擎出现真实生产调用方
  - 当前倾向：**不新增生产适配器**；仅测试用 `from_pandas_dataframes` 验证等价
  - 证据等级：E1（P-004 M-C 证伪）

---

## 10. 可重放命令

```powershell
$py = 'C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe'
# E3：端口/因子/agents/协议/消费方（只读）
& $py -c "import pathlib,re; ..."   # 探针见 §3 A-J（Step 9 落脚本）
# E1 基线（Step 9 必跑）
$env:MPLBACKEND='Agg'; & $py -m pytest tests -q -p no:cacheprovider
& $py -m pytest tests -k golden -q -p no:cacheprovider
& $py -m black --check core tests
& $py -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
& uv lock --check
```

> Step 1 未执行上述命令（只读取证）；读数 K 沿用 P-041 关闭基线，Step 9 回填红/绿。

---

## 11. Step 1 自查（RULE-4）

| # | 自查项 | 结论 |
|---|--------|------|
| 1 | 是否重做 P-004 | ✅ 明确不重做；只承接 B4 + U-P004-4；不复活已删 API |
| 2 | 题干是否收窄 | ✅ 六项收窄见 §1；合并/实时源/DuckDB/舆情均排除 |
| 3 | 事实与推测分离 | ✅ G1-G6 均有 E3 行号；P-004 结论标注来源；基线读数标注未复跑 |
| 4 | 是否以「跑通」代替正确性 | ✅ 验收含契约测试/指纹/golden 零重录，不以「能跑」为唯一判据 |
| 5 | 方案矩阵是否穷举 | ✅ M-A~M-E；M-B/M-C/M-D/M-E 均给拒绝理由 |
| 6 | 是否触碰复权/对齐/缺失语义 | ✅ 零变更（I1/I2/I7/I8） |
| 7 | 是否新增外部依赖 | ✅ 零新增（仅 stdlib） |

---

## 12. 判档

**T1**——变更面含 `core/` 与 `tests/`，且 `IDataManager` / `DataProvider` 属**契约变更**（判档规则 2 强制 T1）；非 T3 轻批。

---

## 13. Step 2 Review（同基座独立视角，2026-11-17）

> **基座披露（RULE-4）**: 复审 DeepSeek-V4.1-Flash = 作者**同源**；RULE-5 不成立 → U-P042-1 跟踪；终审须异构。

### 13.1 机械复核

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 端口方法数 | 3（`load_price`/`load_aux`/`load_universe`） | ✅ |
| 2 | 因子直读 | `data.py` L564-569 `pd.read_pickle`，未走 provider | ✅ G1 成立 |
| 3 | agents 越界 | `agent_framework.py` L979/L989 直读 `data_dir` | ✅ G3 成立 |
| 4 | 协议泄漏 | `IDataManager` 无 `close/open/adj_factor/suspend/st/industry/mktcap/universe` | ✅ G2 成立 |
| 5 | P-004 已删 API | `from_data_manager` / `AbstractDataManager` 全仓 0 命中 | ✅ 不复活 |
| 6 | 契约测试现状 | `MockDataProvider` 3 成员 + 注入测试已存在 | ✅ 可在其上扩展 |

### 13.2 发现与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S2-P042-1 | P2 | 总纲 P-042 写「data.py/data_v3.py 归并」，但 P-004 M-C 已证伪合并可行；照总纲直做会重蹈覆辙 | §1 题干收窄为「契约收口，不合并」；总纲 §5 P-042 应同步注记（Step 3 前回写） |
| F-S2-P042-2 | P3 | §3 基线 K 未本批复跑，读者可能误读为实测 | 已标注「沿用 P-041 关闭基线，Step 9 必跑」 |
| F-S2-P042-3 | P3 | `IStreamingFeed` 放置位置未定，可能造成 interfaces.py 膨胀 | 登记 U-P042-3，DESIGN 裁决 |

### 13.3 结论

**Step 2 Review pass（1 P2 + 2 P3 当轮处置）**——G1-G6 均有 E3 证据、方案矩阵穷举、P-004 边界未被推翻；**准予进入 Step 3 DESIGN**。
**RULE-5**: 同基座 → U-P042-1 pending（终审须 GLM-5.3-Flash）。
