# DESIGN：P-029 静默失败治理第四批（`agents/` 9 处计量 · U-P027-1）

> **批次**: P-029 · **T1**（`agents/` 3 文件；零 fail-fast、零返回值语义变更、零既有文案改写、**零新增日志**）
> **上游**: [RESEARCH_p029](RESEARCH_p029_silent_exception_governance_phase4.md)（§3 八处清单 / §4 分类 / §5 E2 / §8 风险四元块 / §11 Step 2 异构 Review pass，F-S2-P029-1 当轮修正）
> **状态**: **Step 3 DESIGN 完稿**（2026-11-16，作者基座 DeepSeek-V4.1-Flash，HEAD `7045001`）
> **设计口径**: 8 站点（S1-S8）+ S3b 跳过计量 = **9 计量 / 3 文件 / 0 新增日志 / 0 新增 raise**
> **代码证据时点**: HEAD `7045001`（P-029 Step 2 收口）

---

## 1. 决策总览

| ID | 决策 | 覆盖处 | 一句话 |
|----|------|--------|--------|
| **D1** | `ResearchTeamAgent.prepare_factors` 三处 bare except：补计量、保留 `None` 缓存 | 3 | 键 `price_cache` / `industry_cache` / `mktcap_cache`；`pass` 被 1 行计量替换 |
| **D2** | `ResearchTeamAgent._init_research_team`：新增 `else` 分支补「跳过」计量 | 1 | 键 `rotation_analyzer_skipped`；**不加日志**（Step 2 F-S2-P029-1 裁定） |
| **D3** | `ResearchTeamAgent.get_performance_summary`：补计量、保留缺键语义 | 1 | 键 `performance_summary_team_report`；`team_report` 仍不写入 |
| **D4** | `StrategyEngine` 三处窄类型 except：补计量、保留 `continue`/`return` 与队列 | 3 | 键 `orders_missing_price` / `next_day_open_price` / `pending_open_price` |
| **D5** | `MeanVarianceAllocator`：**新建**实例三件套 + pinv 计量 | 1 | 键 `pinv_fallback`；`BaseAllocator` **不下沉**（M-A） |
| **D6** | 出口与生命周期：复用既有 `failure_counts`；仅 S8 新增只读 getter | — | S1-S4 → `get_performance_summary`；S5-S7 → `run()`；S8 → `get_failure_stats()` |
| **D7** | 约定：不新增 raise、不改捕获类型、不改既有文案、**不新增日志** | — | 唯一文本增量是 3 个新方法的 docstring |

**计量点合计 9 处**（S1-S8 + S3b）+ **零改动 0 处**；`except Exception` 合计恒 **22**（本批全部为 bare / 窄类型，不进入该口径）。

---

## 2. 调研结论 → 设计映射

| RESEARCH / Step 2 结论 | 设计落点 |
|------------------------|----------|
| S1-S3 E2：三缓存均 `None` + 0 条错误日志 | D1 只补计量；`None` 语义与后续 `_init_research_team` 条件判断不变 |
| S3b：L928 条件不满足时静默跳过分析器 | D2 以 `else` 分支计 1 次；**不加 warning**（合法缺失形态，F-S2-P029-1） |
| S4：`team_report` 静默缺键（同函数已有 `failure_counts` 出口） | D3 补计量后自动出现在既有出口，**零出口改动** |
| S5：异常 `continue` 与合法 `continue` 同值 | D4 只计异常分支；T4 双参数断言（合法 0 / 异常 1） |
| S6/S7：`return` 后队列保留（可能次日重试） | D4 只补计量，**不改队列与重试语义**（U-P029-2 维持） |
| S8：`LinAlgError → pinv`，类无计数器 | D5 自备三件套；M-A（不下沉 `BaseAllocator`） |
| R-P029-2：S5 聚合单键 | 键 `orders_missing_price`（不按股票展开，避免键爆炸） |
| R-P029-3 / O-S2-P029-2：S8 实例级、走 `_record_failure` | D5 实例级三件套，与 P-027 C 类形态统一 |

---

## 3. 决策详述

### D1 `agent_framework.py` S1-S3：三处 bare except 补计量

**位置**：`ResearchTeamAgent.prepare_factors`（L969-992）。三处 `except:` 的 body 均为 `pass`——以 1 行计量替换（`pass` 删除，无语义差异）。

| 站点 | 锚点 | 键 | 保留行为 |
|------|------|----|----------|
| S1 | `agent_framework.py:971`（`get_adj_price("close","forward")`） | `price_cache` | `self._price_data` 保持 `None` |
| S2 | `agent_framework.py:981`（`industry.pkl`） | `industry_cache` | `self._industry_data` 保持 `None` |
| S3 | `agent_framework.py:991`（`mktcap.pkl`） | `mktcap_cache` | `self._mktcap_data` 保持 `None` |

```python
        try:
            self._price_data = data_manager.get_adj_price("close", "forward")
        except:
            self._record_failure("price_cache")
```

**不改成 `except Exception:`**：bare except 还捕获 `KeyboardInterrupt` / `SystemExit`，改捕获类型属语义变更（D7 禁止）；风格问题不在本批。

### D2 `agent_framework.py` S3b：`else` 分支补「跳过」计量

**位置**：`_init_research_team` L928-L936。条件不满足时**新增 `else`**（唯一新增分支）：

```python
        if self._industry_data is not None and self._price_data is not None:
            try:
                self.rotation_analyzer = IndustryRotationAnalyzer(
                    self._industry_data, self._price_data, self._mktcap_data
                )
            except Exception as e:
                self._record_failure("rotation_analyzer_init")   # P-027 既有
                logger.warning(f"行业轮动分析器初始化失败: {e}")
                self.rotation_analyzer = None
        else:
            self._record_failure("rotation_analyzer_skipped")
```

**不加 warning**（F-S2-P029-1 裁定）：`industry.pkl` 属可选数据，跳过为合法形态；计数可与 S1-S3 的 `*_cache` 键对拍因果链。`self.rotation_analyzer` 保持 `__init__` 的 `None`，不新增赋值。

### D3 `agent_framework.py` S4：绩效摘要补计量

**位置**：`get_performance_summary` L1154-L1159。

```python
        if self.fund_manager is not None:
            try:
                team_report = self.fund_manager.get_team_report()
                summary["team_report"] = team_report
            except:
                self._record_failure("performance_summary_team_report")
```

`team_report` **仍不写入** summary；既有 `summary["failure_counts"]`（L1152，P-027）自动包含该键 → 零出口改动。

### D4 `multi_strategy_engine.py` S5-S7：三处窄类型 except 补计量

| 站点 | 锚点 | 键 | 保留行为 |
|------|------|----|----------|
| S5 | L330 `except (KeyError, IndexError):` | `orders_missing_price` | `continue`（跳过该股票；L328 合法分支**不计数**） |
| S6 | L390 `except KeyError:` | `next_day_open_price` | `return`（`_next_day_orders` 保留） |
| S7 | L452 `except KeyError:` | `pending_open_price` | `return`（`pending_queue` 保留） |

三处均在 `except` 块首行插入 `self._record_failure(KEY)`，其后语句逐字保留。`StrategyEngine.run()` 入口清零（P-027 D6）→ 每轮回测独立计数。

### D5 `strategy_allocator.py` S8：新建实例三件套

**M-A（采纳）**：只在 `MeanVarianceAllocator` 内自备，不下沉 `BaseAllocator`。

```python
class MeanVarianceAllocator(BaseAllocator):
    def __init__(self, risk_aversion: float = 1.0, turnover_penalty: float = 0.0,
                 min_weight: float = 0.0, max_weight: float = 1.0):
        self.lambda_risk = risk_aversion
        self.lambda_turnover = turnover_penalty
        self.min_w = min_weight
        self.max_w = max_weight
        self._failure_counts: dict[str, int] = {}        # 新增

    def _record_failure(self, key: str) -> None:          # 新增
        """记录一次降级失败（只增不清）"""
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1

    def get_failure_stats(self) -> dict[str, int]:        # 新增
        """只读失败计量快照"""
        return dict(self._failure_counts)

    def allocate(self, evaluator, current_weights=None):
        ...
        try:
            Sigma_inv = np.linalg.inv(Sigma)
            raw_weights = Sigma_inv @ mu
        except np.linalg.LinAlgError:
            self._record_failure("pinv_fallback")         # 新增
            # 如果奇异，使用伪逆
            raw_weights = np.linalg.pinv(Sigma) @ mu
```

**不选 M-B**：下沉 `BaseAllocator` 需为其新增 `__init__` + 5 个子类补 `super().__init__()`，为 3 行抽象改 5 个类，违背 P-027「不为 3 行抽 mixin」先例。

### D6 出口与生命周期

| 站点组 | 出口 | 是否改动 |
|--------|------|----------|
| S1-S4（含 S3b） | `ResearchTeamAgent.get_performance_summary()` 的 `failure_counts`（P-027 已加） | **零改动** |
| S5-S7 | `StrategyEngine.run()` 返回值的 `failure_counts`（P-027 已加） | **零改动** |
| S8 | 新增 `MeanVarianceAllocator.get_failure_stats()`（只读拷贝） | +1 getter |

- **生命周期**: 实例累计；`StrategyEngine.run()` 入口既有清零覆盖 S5-S7；`ResearchTeamAgent` 与 `MeanVarianceAllocator` 不新增清零（与 P-027 一致）。
- **不做**: 不新增 `failure_counts` 字典出口（S8 无报告对象）；不改 `MetaPolicy` / 其他分配器。

### D7 文案与异常传播约定

1. **零新增日志**：本批不新增任何 `logger.*` 调用，也不提升既有级别（P-027 唯一级别改动已收口）。
2. **零文案改写**：既有日志字符串逐字不变。
3. **零新增 `raise`**、**零捕获类型变更**（bare except 保持 bare）。
4. **唯一文本增量**：3 个新方法的 docstring（`_record_failure` / `get_failure_stats` / `rotation_analyzer_skipped` 无 docstring，仅注释性键名）。

---

## 4. 实现规格

### 4.1 变更面（3 代码文件 + 1 测试）

| 文件 | 新增行 | 变更性质 |
|------|--------|----------|
| `agents/agent_framework.py` | ≈ 8 | S1-S3 三处 `pass` → 1 行计量；S3b 新增 `else` 2 行；S4 `pass` → 1 行 |
| `agents/multi_strategy_engine.py` | 3 | 三处 except 首行各 +1 |
| `agents/strategy_allocator.py` | ≈ 12 | 计数器 + `_record_failure` + `get_failure_stats` + 1 行接入 |
| `tests/test_p029_silent_exception_governance.py`（新增） | ≈ 260 | 7 函数 / 11 实例 |

零改动面：`filter/` / `core/` / `strategy_evaluation/` / `scripts/` / `batch_backtest/` / `cli.py` / `pyproject.toml` / `.github/` / `tests/golden/*.json`。

### 4.2 测试规格（7 函数 / 11 实例，全部 `monkeypatch`，禁 mock 库）

| 用例 | 函数 | 实例 | 断言 |
|------|------|------|------|
| V1 | `test_cache_failure_counts` | 3（参数化 price/industry/mktcap） | 各计数 1；对应缓存 `None`；`caplog` WARNING+ 零记录 |
| V2 | `test_rotation_analyzer_skipped` | 1 | 注入假 `research_team_v2` / `industry_rotation_v2`；`_industry_data=None` → `rotation_analyzer_skipped` 1、`rotation_analyzer is None` |
| V3 | `test_team_report_failure` | 1 | `team_report` 不在 summary；计数 1；summary 仍含 `failure_counts` |
| V4 | `test_order_missing_price` | 2（合法缺列 / 异常） | 合法分支计数 **0**；异常分支计数 **1**；均无订单 |
| V5 | `test_open_price_failures` | 2（S6 / S7 参数化） | 各计数 1；队列长度不变；返回 `None`；零 WARNING+ |
| V6 | `test_pinv_fallback` | 1 | `pinv_fallback` 1；`get_failure_stats()` 为拷贝（改写返回值不影响内部）；权重归一 |
| V7 | `test_normal_path_zero_counts` | 1 | 正常价格 + 正常求逆 → 两个载体的 `get_failure_stats() == {}` |

**红态预期**：7 函数在实施前全部失败（`KeyError` / 属性缺失 / 断言计数缺失），逐批见 Step 9。

### 4.3 新增文案

**无。** 仅新增 docstring（不计日志文案）；既有日志字符串零改动。

---

## 5. 不变式

| ID | 不变式 | 验证 |
|----|--------|------|
| **I1** | `except Exception` 合计仍 **22**（本批 9 处均非该类型） | `Grep -c` 十文件对拍 |
| **I2** | 零新增 `raise` / 零 fail-fast | `git diff` 关键词扫描 |
| **I3** | 返回值语义零变更：缓存 `None` / 缺 `team_report` 键 / `continue` / `return` / pinv 权重 | T1-T6 断言 |
| **I4** | 零改动面 diff 为空 | `git diff --name-only` 九面 |
| **I5** | 既有签名不变：`prepare_factors` / `get_performance_summary` / `_generate_orders` / `_execute_next_day_orders` / `_process_pending_orders` / `allocate` / `MeanVarianceAllocator.__init__` 形参逐字 | `git diff` def 行 |
| **I6** | 零新增日志 + 既有文案逐字不变 | `git diff` 中 `logger.` 行 = 0 增 0 删 |
| **I7** | golden G1-G7 零重录 | `git status tests/golden/` 空 |
| **I8** | 测试 **711 → 722**（+11）；测试文件 80 → 81；black **117 → 118**；mypy 37 files 0 | `pytest` / `black --check` / mypy |

---

## 6. 验证契约（V1-V5）

| ID | 契约 | 对应 |
|----|------|------|
| V1 | S1-S3 三缓存失败各计 1 次且零 WARNING 日志 | T1 |
| V2 | S3b 跳过计 1 次；S4 缺键计 1 次且不影响其他 summary 键 | T2 / T3 |
| V3 | S5 合法 `continue` 计 0 / 异常计 1；S6/S7 各计 1 且队列语义不变 | T4 / T5 |
| V4 | S8 pinv 计 1；getter 返回拷贝；正常路径零计数 | T6 / T7 |
| V5 | 出口自洽：S1-S4 计数出现在 `get_performance_summary`，S5-S7 出现在 `run()` | T3 / T5 + 读码 |

---

## 7. 风险登记

| ID | 级别 | 风险 | 处置 |
|----|------|------|------|
| R-P029-4 | P3 | `rotation_analyzer_skipped` 在行业数据长期缺失的部署中每次运行均 >0，可能被视为噪声 | 语义为「跳过次数」而非错误；Step 7 CHECKLIST 明确文案；若后续需要可加 `debug`（本批不做） |
| R-P029-5 | P3 | `MeanVarianceAllocator` 的 `_failure_counts` 为实例属性，若未来被子类复用需自行初始化 | DESIGN 明示；`MeanVarianceAllocator` 当前无子类（E3 复核） |
| R-P029-6 | P3 | bare except 保留 → 捕获 `KeyboardInterrupt` 的既有风险未消除 | 改捕获类型属语义变更，本批不做；登记为第五批候选（不新增 U 项，随 U-P029-2 观察） |
| R-P029-7 | P3 | `prepare_factors` 多次调用时 S1-S3 计数累计 | 与 P-027 实例累计口径一致；如需单次语义，调用方入口清零另立需求 |

---

## 8. 回退点

| 批次 | 内容 | 测试 | 可独立回退 |
|------|------|------|------------|
| **B1** | `agent_framework.py`：S1-S3 + S3b + S4（5 计量） | T1 / T2 / T3（5 实例） | 是 |
| **B2** | `multi_strategy_engine.py`：S5-S7（3 计量） | T4 / T5（4 实例） | 是 |
| **B3** | `strategy_allocator.py`：S8 载体 + 1 计量 | T6 / T7（2 实例） | 是 |

批次顺序 B1 → B2 → B3；每批独立提交、独立红绿、独立可回退。

---

## 9. 设计期发现

1. **S4 零出口改动**：`get_performance_summary` 已在 P-027 追加 `failure_counts`，本批 D3 的计数自动出现在出口——无需修改 D6 形态。
2. **S5 双分支同值**：L328 合法 `continue` 与 L330 异常 `continue` 返回同值，T4 必须双参数断言才能证明「只计异常」。
3. **S3b 语法落点**：`else` 必须挂在 L928 的 `if` 上（而非 L929 `try` 的 `else`），否则会在 `try` 成功时误计。
4. **`MeanVarianceAllocator.__init__` 形参零变更**：只追加属性赋值，I5 成立。
5. **`BaseAllocator` 无 `__init__`**：若选 M-B 需同时改 5 个子类；M-A 只改 1 个类，回退面最小。

---

## 10. 结论

**DESIGN 完稿，可进入 Step 4 独立 Review。** 9 计量 / 3 文件 / 0 新增日志 / 0 新增 raise；三批独立可回退；I1-I8 全可机械核验。Step 4 复核重点：

1. 9 处锚点行号与键名逐项（E3 读码 @`7045001`）；
2. D2 `else` 挂载点语法正确性（挂 `if` 非 `try`）；
3. M-A 与 M-B 的取舍复核（`BaseAllocator` 无 `__init__` 的实证）；
4. I8 计数（722 / 81 / 118 / 37）与测试规格函数数一致；
5. 零新增日志是否与「可观测性」目标冲突（D2 只计量不加日志的裁定复核）。
