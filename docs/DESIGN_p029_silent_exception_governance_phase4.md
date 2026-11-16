# DESIGN：P-029 静默失败治理第四批（`agents/` 9 处计量 · U-P027-1）

> **批次**: P-029 · **T1**（`agents/` 3 文件；零 fail-fast、零返回值语义变更、零既有文案改写、**零新增日志**）
> **上游**: [RESEARCH_p029](RESEARCH_p029_silent_exception_governance_phase4.md)（§3 八处清单 / §4 分类 / §5 E2 / §8 风险四元块 / §11 Step 2 异构 Review pass，F-S2-P029-1 当轮修正）
> **状态**: **Step 4 异构 Review pass**（2026-11-16，复核基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；0 P1/P2 + 3 P3 当轮回写 + 2 观察，见 §11）｜Step 3 完稿（作者 DeepSeek，HEAD `7045001`）
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

**计量点合计 9 处**（S1-S8 + S3b）+ **零改动 1 处**（`research_team_v2.py:25-28` 模块级 `except ImportError` 静默置 `None`——`agent_framework` 主路径经 L914 直连 import，失败时 L843-845 `logger.warning` 兜底，可观测；F-S4-P029-3 回写）；`except Exception` 合计恒 **22**（本批全部为 bare / 窄类型，不进入该口径；Step 4 E4 实测 41 文件 = 22）。

---

## 2. 调研结论 → 设计映射

| RESEARCH / Step 2 结论 | 设计落点 |
|------------------------|----------|
| S1-S3 E2：三缓存均 `None` + 0 条错误日志 | D1 只补计量；`None` 语义与后续 `_init_research_team` 条件判断不变 |
| S3b：L928 条件不满足时静默跳过分析器 | D2 以 `else` 分支计 1 次；**不加 warning**（合法缺失形态，F-S2-P029-1） |
| S4：`team_report` 静默缺键（同函数已有 `failure_counts` 出口） | D3 补计量 + L1152 下移 1 行（F-S4-P029-1）→ **同调可见**于既有出口 |
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

### D3 `agent_framework.py` S4：绩效摘要补计量 + 快照下移

**位置**：`get_performance_summary` L1149-L1161。两处微改（F-S4-P029-1）：

```python
        if self.fund_manager is not None:
            try:
                team_report = self.fund_manager.get_team_report()
                summary["team_report"] = team_report
            except:
                self._record_failure("performance_summary_team_report")

        summary["failure_counts"] = self.get_failure_stats()  # L1152 下移至 try/except 之后
        return summary
```

- `team_report` **仍不写入** summary（返回语义零变更，I3）。
- **L1152 下移**（原位于 try/except **之前**）：同调失败时计数进入本次返回值——否则 `performance_summary_team_report` 只在下一次调用可见，§6 V5「S1-S4 计数出现在出口」对 S4 同调不成立（F-S4-P029-1）。

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
| S1-S4（含 S3b） | `ResearchTeamAgent.get_performance_summary()` 的 `failure_counts`（P-027 已加） | 复用既有出口；S4 同函数 L1152 下移 1 行（F-S4-P029-1，同调可见） |
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
| `agents/agent_framework.py` | ≈ 9 | S1-S3 三处 `pass` → 1 行计量；S3b 新增 `else` 2 行；S4 `pass` → 1 行 + L1152 下移（−1/+1，F-S4-P029-1） |
| `agents/multi_strategy_engine.py` | 3 | 三处 except 首行各 +1 |
| `agents/strategy_allocator.py` | ≈ 12 | 计数器 + `_record_failure` + `get_failure_stats` + 1 行接入 |
| `tests/test_p029_silent_exception_governance.py`（新增） | ≈ 260 | 7 函数 / 11 实例 |

零改动面：`filter/` / `core/` / `strategy_evaluation/` / `scripts/` / `batch_backtest/` / `cli.py` / `pyproject.toml` / `.github/` / `tests/golden/*.json`。

### 4.2 测试规格（7 函数 / 11 实例，全部 `monkeypatch`，禁 mock 库）

| 用例 | 函数 | 实例 | 断言 |
|------|------|------|------|
| V1 | `test_cache_failure_counts` | 3（参数化 price/industry/mktcap） | 各计数 1；对应缓存 `None`；`caplog` WARNING+ 零记录。**触发注记（F-S4-P029-2）**：industry/mktcap 须提供**存在但损坏**的 pkl——路径不存在时 `if industry_path.exists()` 短路、不进 except、计数 0（合法缺失由 S3b `rotation_analyzer_skipped` 承接） |
| V2 | `test_rotation_analyzer_skipped` | 1 | 注入假 `research_team_v2` / `industry_rotation_v2`；`_industry_data=None` → `rotation_analyzer_skipped` 1、`rotation_analyzer is None` |
| V3 | `test_team_report_failure` | 1 | `team_report` 不在 summary；计数 1；summary 的 `failure_counts` **同调含** `performance_summary_team_report`（F-S4-P029-1） |
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

> 注（F-S6-P029-4，Step 6 回写）：本表 V1-V5 为**契约**局部编号，与 §4.2 / IMPL §5 的**测试用例** V1-V7 是两套 ID；「对应」列 T1-T7 即 §4.2 用例 V1-V7 的旧称（按序一一对应）。Step 7 CHECKLIST 以测试用例 V1-V7 为准。

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

1. **S4 出口同调滞后（F-S4-P029-1 修正）**：`get_performance_summary` 已在 P-027 追加 `failure_counts`，但 L1152 快照位于 S4 try/except **之前**——同调失败不计入本次返回值。修正：L1152 下移至 try/except 之后（D3），V5「计数出现在出口」对 S4 同调成立。
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

---

## 11. Step 4 异构 Review（GLM-5.3-Flash）

> **复核基座**: GLM-5.3-Flash（≠ 作者 DeepSeek-V4.1-Flash，RULE-5 合规）
> **基线**: HEAD `f802bbe`（代码与 `7045001` / `0afcfec` 一致，`f802bbe` 仅 docs 回填）
> **日期**: 2026-11-16
> **结论**: **PASS —— 0 P1 / 0 P2，3 P3 已当轮回写，2 观察登记**

### 11.1 E1 锚点机械核验（读码 @`f802bbe`，9/9 命中）

| 站点 | DESIGN 锚点 | 实测 | 判定 |
|------|-------------|------|------|
| S1 | L971 bare except + `pass` | try 体 `get_adj_price("close","forward")` L970 → `except:` L971 → `pass` L972 | ✓ |
| S2 | L981 | try L974-980（`industry.pkl` exists → pickle.load）→ `except:` L981 | ✓ |
| S3 | L991 | try L984-990（`mktcap.pkl`）→ `except:` L991 | ✓ |
| S3b | L928-L936 | `if` L928 → `try` L929 → `except Exception` L933-936（`rotation_analyzer_init`，P-027 既有）→ **无 else** | ✓ |
| S4 | L1154-L1159 | `if` L1154 → `try` L1155-1157 → bare `except:` L1158 → `pass` L1159 | ✓ |
| S5 | L330 | `try` L325 → 合法 `continue` L328-329 → `except (KeyError, IndexError):` L330 → `continue` L331 | ✓ |
| S6 | L390 | `try` L388-389 → `except KeyError:` L390 → `return` L391 | ✓ |
| S7 | L452 | `try` L449-451（open+close 双价）→ `except KeyError:` L452 → `return` L453 | ✓ |
| S8 | L625-L630 | `try` L625-627（`inv`）→ `except np.linalg.LinAlgError:` L628 → 注释 L629 → `pinv` L630 | ✓ |

键名 9 个互不冲突，且与 P-027 既有键（`rotation_analyzer_init` / `research_team_analysis` / `daily_process` / `directional_optimize` / `neutral_optimize` 等）零冲突；`get_failure_stats` 在 `strategy_allocator.py` 无同名（Grep 实查）；载体三件套已存在于 `ResearchTeamAgent`（L882/L891/L895）与 `StrategyEngine`（L111/L115/L119），B1/B2 无需新建。

### 11.2 E2 基线门禁实测（I8 四元对拍）

| 指标 | 实测基线 | I8 目标 | 算术 | 判定 |
|------|----------|---------|------|------|
| pytest collected | **711** | 722 | +11（V1 3 + V2 1 + V3 1 + V4 2 + V5 2 + V6 1 + V7 1） | ✓ |
| tests/ 全 .py | **80**（77 `test_*.py` + 3 `_` 辅助） | 81 | +1 新测试文件 | ✓ |
| black --check core tests | **117 files unchanged** | 118 | +1（117 = core 37 + tests 80，自洽） | ✓ |
| mypy core | **37 files, 0 issues** | 37 | `agents/` 不在 mypy 门禁路径 → 不变 | ✓ |

### 11.3 E4 独立扫描（自写 AST 脚本 `%TEMP%\p029_step4_scan.py`，不复用作者脚本）

- `agents/` 除处理器 **handlers=22 / silent=9**：S1-S8（8）+ `research_team_v2.py:27`（import 降级 1）——与 Step 2 复扫一致，**无遗漏、无新增**。
- `except Exception` 十文件范围（41 文件）= **22**，I1 成立；9 处目标均为 bare / 窄类型，实施后计数不变。
- 继承谱系：`BaseAllocator` 5 子类（Hedge L374 / FTRL L419 / UCB L495 / Thompson L536 / MeanVariance L582）**均有自有 `__init__`**，`BaseAllocator` 自身无 `__init__`（L354-371 仅抽象 `allocate`）——M-B 需改 6 类并承担子类漏调 `super().__init__()` 的运行期风险，**M-A 裁决维持**。

### 11.4 复核重点五项裁决

| # | 重点 | 裁决 |
|---|------|------|
| 1 | 9 锚点 + 键名 | **pass**（11.1 全命中；键名零冲突） |
| 2 | D2 `else` 挂 `if` 非 `try` | **pass**——L928 `if` 直下 L929 `try`，`else` 挂 `if` 在数据缺失时计数；若误挂 `try` 的 `else` 会在**成功**时误计（§9.3 判断正确）。语义链实测：`_price_data`/`_industry_data` 仅由 S1/S2 赋值 → `skipped` 与 `*_cache` 可对拍因果 |
| 3 | M-A vs M-B | **pass，维持 M-A**（11.3 实证：5 子类均有自有 `__init__`，M-B 改 6 类 + 漏 super 风险） |
| 4 | I8 四计数 | **pass**（11.2 实测算术成立） |
| 5 | 零新增日志裁定（D2 不加 warning） | **pass**——`industry.pkl` 属可选数据，缺失为合法形态；warning 将在无行业数据的部署中每次运行刷屏（与 R-P029-4 同源）；计数 + `*_cache` 对拍已提供因果可见性。S1-S3 静默面同理（补日志属 I6 违规） |

### 11.5 发现与回写

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-S4-P029-1 | P3 | **S4 同调出口滞后**：L1152 `summary["failure_counts"]` 快照位于 S4 try/except **之前**，同调失败只在下一次调用可见——§6 V5「S1-S4 计数出现在出口」对 S4 同调不成立 | **已回写**：D3 增第 2 项微改（L1152 下移至 `return summary` 前）；§2 / D6 / §4.1 / V3 / §9.1 同步 |
| F-S4-P029-2 | P3 | **V1 触发面歧义**：industry/mktcap 的 try 体在 `path.exists()` 为 False 时不进 except（缺失文件 → 计数 0，合法缺失由 S3b 承接）；V1 参数化须用**存在但损坏**的 pkl | **已回写**：§4.2 V1 补触发注记 |
| F-S4-P029-3 | P3 | **静默面清点缺口**：E4 复扫 silent=9（8 站点 + `research_team_v2.py:25-28` import 降级），§1「零改动 0 处」与清点不符 | **已回写**：§1 改「零改动 1 处」并注明下游可观测路径（L914 直连 import → L843 warning → `available=False`） |
| O-S4-P029-1 | 观察 | `MeanVarianceAllocator.allocate` L633-637 `sum(raw_weights) <= 0 → np.ones(n)/n` 等权回退为**非异常**静默降级，不在 except-判据扫描范围 | 登记：后续批次候选「非异常静默回退」判据扩展（与 U-P029-2 / R-P029-6 同列观察，不新增 U 项） |
| O-S4-P029-2 | 观察 | I8「81 文件」口径未定义（实为 tests/ 全部 .py = 80；black 117 = core 37 + tests 80 自洽） | 登记：Step 7 CHECKLIST 沿用同口径并在实测列注记 |

### 11.6 测试规格可行性抽核

- **V2**：`sys.modules` 注入假 `research_team_v2` / `industry_rotation_v2` → `_research_team_available=True`（P-027 T2 同范式已验证，test_p027 L159）；`_industry_data=None` → else 计数。✓
- **V4**：合法分支用空 `adj_close`（列/日期缺失 → L328-329 `continue` 计 0），异常分支注入 `KeyError` 计 1——双参数断言可落地。✓
- **V6**：`monkeypatch np.linalg.inv` 抛 `LinAlgError`（`pinv` 走 SVD/lstsq 不受影响）；evaluator 以简单对象提供 `n` / `get_expected_returns` / `correlation_matrix` / `get_expected_variances`。✓
- **V7**：`run()` 入口清零（L154）→ 正常数据全零计数；`MeanVarianceAllocator` 新鲜实例天然为空。✓

### 11.7 结论

**Step 4 PASS。** 3 P3 已当轮回写至本文件（§1 / §2 / D3 / D6 / §4 / §9），无 P1/P2；M-A / D2 / I8 / 零日志四项裁决维持。下一 **Step 5 IMPL** 以**回写后**的 D1-D7 与 I1-I8 为准，并继承两条观察（O-S4-P029-1/2）；IMPL 须覆盖 D3 的 L1152 下移（`agent_framework.py` 变更面 ≈9 行）与 V1 的损坏 pkl 触发注记。
