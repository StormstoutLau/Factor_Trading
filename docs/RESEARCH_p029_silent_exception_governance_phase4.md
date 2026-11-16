# RESEARCH：P-029 静默失败治理第四批（`agents/` 8 处同类静默路径 · U-P027-1）

> **批次**: P-029 · **T1**（`agents/` 3 文件；零 fail-fast、零返回值语义变更、零既有文案改写）
> **上游**: [CHECKLIST_p027 §12.6](CHECKLIST_p027_silent_exception_governance_phase3.md)（Step 10 E4 AST 扫描：97 文件 21 项零可观测处理器中 8 项落 `agents/`）+ [PROGRESS §1.4 U-P027-1](PROGRESS.md)
> **状态**: **Step 1 RESEARCH 完成**（2026-11-16，HEAD `310998d`）
> **触发**: 用户 2026-11-16 指令「执行 U-P027-1」→ 立项 P-029；U-P027-1 触发条件「发起静默失败治理第四批」成立
> **代码证据时点**: HEAD `310998d`（P-028 收口）

---

## 0. 结论摘要（TL;DR）

1. U-P027-1 清单 8 处**全部 E2 复现**：注入异常后均**不抛出、0 条新增日志、0 计量**（基线 `_failure_counts` 保持 `{}`）。
2. 分类：**B 类 7 处**（S1-S7：有降级语义但零可观测）+ **待裁决 1 处**（S8 `LinAlgError → pinv`：有行内注释，按 O-S2-P027-1 判据字面属 A，但运行期不可见，本批建议判 B 并登记风险）。
3. 另有**新增观察 1 项**（S3b）：`_init_research_team` 在行业/价格缓存为 `None` 时**静默跳过**行业轮动分析器创建（无 `else` 日志），是 S1-S3 后果的放大器——不在 8 项口径内，交 Step 3 裁决是否纳入。
4. 治理形态沿用 P-027 范式：**只补计量（+ 可选 1 条 warning）**，不新增 `raise`、不改捕获类型、不动既有文案；`ResearchTeamAgent` 与 `StrategyEngine` 已有三件套可直接复用，唯一新载体是 `MeanVarianceAllocator`（建议自备三件套，不下沉 `BaseAllocator`）。
5. `except Exception` 合计仍 **22**（本批全为 bare `except:` 或窄类型 `KeyError`/`LinAlgError`，不在 I1 口径内）；I1 不受影响。

---

## 1. 触发判据与范围

| 项 | 内容 |
|----|------|
| 上游登记 | U-P027-1：`agents/` 8 处（bare `except: pass` ×4 / 窄类型 `KeyError` `continue`·`return` ×3 / `LinAlgError` 静默伪逆 ×1） |
| 触发 | 「任一处在实际运行中被复现为可观测错误，或发起静默失败治理第四批」——用户指令构成后者 |
| 范围 | `agents/agent_framework.py`（S1-S4）/ `agents/multi_strategy_engine.py`（S5-S7）/ `agents/strategy_allocator.py`（S8） |
| 不在范围 | P-027 已治理的 22 处 `except Exception`（16 计量 + 6 零改动）；E4 其余 13 项（import 降级 / core 既有 / 工具 / 展示层） |
| 硬约束（沿用 P-027） | 零 fail-fast、零返回值语义变更、零既有文案改写；允许新增日志（P-027 先例：新增 2 条 warning）与新增只读出口 |

---

## 2. 取证方法

| 等级 | 方法 |
|------|------|
| E1 | `Grep` / `Select-String` 定位 8 处行号；`git rev-parse HEAD` 固定 `310998d` |
| E2 | 仓库外探针 `%TEMP%\p029_probe.py`：`object.__new__` 构造最小实例 + 假数据管理器（`get_adj_price` 抛错）+ 根 logger `Handler` 计数；S8 以 `np.linalg.inv` 强制抛 `LinAlgError` |
| E3 | 逐行读码确认异常类型、降级返回值、调用链与消费者（`_price_data` → L1026 / `_industry_data` → L1139 / `_mktcap_data` → L931） |

**探针口径说明**：`prepare_factors` 以 `factor_files=[]` + `FactorCombiner.combine` 替身绕开因子构造；`_init_research_team` 置为 no-op（仓库缺 `industry_rotation_v2` 模块，见 P-027 F-S9-P027-2，与本站点无关）。

---

## 3. 8 处全量清单（@`310998d`）

| ID | 位置 | 函数 / 上下文 | 捕获 | 降级行为 | 静默后果 |
|----|------|---------------|------|----------|----------|
| **S1** | `agent_framework.py:969-972` | `ResearchTeamAgent.prepare_factors` | bare `except:` | `_price_data` 保持 `None` | 投研团队技术面分析无价格序列；`_init_research_team` L928 条件不满足 → 轮动分析器静默不建（见 S3b） |
| **S2** | `agent_framework.py:974-982` | 同上（`industry.pkl`） | bare `except:` | `_industry_data` 保持 `None` | 同上；行业分析角色缺失 |
| **S3** | `agent_framework.py:984-992` | 同上（`mktcap.pkl`） | bare `except:` | `_mktcap_data` 保持 `None` | 轮动分析器以 `None` 市值构造（若前两者成功）→ 结果口径降级但不可见 |
| **S4** | `agent_framework.py:1154-1159` | `ResearchTeamAgent.get_performance_summary` | bare `except:` | `team_report` 键**不写入** summary | 报告静默缺段；同函数已在 P-027 追加 `failure_counts`（L1152），但本处异常不计入 |
| **S5** | `multi_strategy_engine.py:325-331` | `StrategyEngine._generate_orders` | `(KeyError, IndexError)` → `continue` | 跳过该股票 | 目标权重部分未下单，组合偏离目标且无痕迹；与 L328 合法 `continue`（缺列/缺日）**同值**，仅计数可区分 |
| **S6** | `multi_strategy_engine.py:388-391` | `_execute_next_day_orders` | `KeyError` → `return` | 全部次日单**不执行**（队列保留） | 调仓延迟且无告警；若逐日持续则订单长期悬挂 |
| **S7** | `multi_strategy_engine.py:449-453` | `_process_pending_orders` | `KeyError` → `return` | 全部挂单**不处理**（队列保留） | 挂单静默滞留，成交结果与预期不符 |
| **S8** | `strategy_allocator.py:625-630` | `MeanVarianceAllocator.allocate` | `np.linalg.LinAlgError` | `np.linalg.pinv(Sigma) @ mu` | 数值路径静默切换（伪逆权重可能与直接求逆不同）；类无任何计数器 |

---

## 4. 分类统计

词表沿用 [RESEARCH_p026 §4](RESEARCH_p026_silent_exception_governance.md) / [RESEARCH_p027 §4](RESEARCH_p027_silent_exception_governance_phase3.md)：A 日志+结构化输出 / B 有日志或降级但无计量 / C 静默返回乐观默认值 / E 进程边界。

| 分类 | 数量 | 站点 | 判定依据 |
|------|------|------|----------|
| **B** | **7** | S1-S7 | 均有明确降级语义（`None` 缓存 / 缺键 / `continue` / `return`），但无计量、无日志 |
| **A?/B? 待裁决** | **1** | S8 | 行内注释「如果奇异，使用伪逆」是**静态说明**；按 O-S2-P027-1 判据字面（注释为载体）可判 A 零改动，但运行期无法得知降级发生，且结果数值会变 → 本批**建议判 B**，登记 R-P029-1 交 Step 3 DESIGN 定稿 |
| 观察 | 1 | S3b（`_init_research_team` L928） | 非 `except`，属条件分支缺日志；不在 U-P027-1 的 8 项口径内，交 Step 3 裁决 |

**与 I1 的关系**：8 处中 7 处为 bare `except:`、1 处为窄类型，均不计入 `except Exception` 统计 → 治理前后 I1 恒 **22**。

---

## 5. E2 复现结果（探针原始读数）

```text
S1-3 prepare_factors: return=None price=None industry=None mktcap=None log_delta=2 logs=['因子处理管道初始化完成', '因子合成器初始化: 无因子文件 (将由调用方注入)']
S3b _init_research_team skip branch: L928 仅构造条件，无 else 日志（E3 读码）
S4 get_performance_summary: has_team_report=False failure_counts={} log_delta=0
S5 _generate_orders: target_positions={} failure_counts={} log_delta=0
S6 _execute_next_day_orders: return=None queue_len=1 failure_counts={} log_delta=0
S7 _process_pending_orders: return=None failure_counts={} log_delta=0
S8 MeanVarianceAllocator: weights=[0.3333, 0.6667] has_counter=False log_delta=0
```

- S1-S3 的 `log_delta=2` 为管道/合成器**初始化日志**（与异常无关）——三个 `except` 各贡献 **0 条**日志。
- S8 探针矩阵为 `Sigma = I`，伪逆与求逆结果同值（`[1/3, 2/3]`）→ **数值不可区分**，故治理验收以「路径计数」而非权重差为判据。

---

## 6. 与 P-027 的关系（复用面）

| 站点 | 现有载体 | 可复用 |
|------|----------|--------|
| S1-S4 | `ResearchTeamAgent._failure_counts` / `_record_failure` / `get_failure_stats`（P-027 L882/L890/L895），出口 `get_performance_summary` 已含 `failure_counts` | 是，仅加 `_record_failure(key)` 一行 |
| S5-S7 | `StrategyEngine._failure_counts` / `_record_failure` / `get_failure_stats`（P-027 L111/L115/L119），`run()` 出口已含 `failure_counts` | 是，仅加 1 行 |
| S8 | 无 | 需新建；建议 `MeanVarianceAllocator` 自备三件套（见 §7 M-A） |

`get_failure_stats` 已在 P-027 验证为只读拷贝；本批不新增出口形态（除 S8 需 1 个 getter）。

---

## 7. 治理建议（供 Step 3 DESIGN）

### 7.1 方案矩阵

| 案 | 内容 | 变更面 | 评价 |
|----|------|--------|------|
| **M-A（推荐）** | 8 处各补 `_record_failure(key)`；S8 在 `MeanVarianceAllocator` 内自备三件套；S3b 追加 1 条 `warning`（可选，见 U-P029-2） | 3 文件 +1 测试，约 +35 行 | 最小面；与 P-027 形态一致；零 fail-fast |
| M-B | S8 下沉 `BaseAllocator.__init__`，5 子类补 `super().__init__()` | 1 文件 5 类 | 为 3 行抽象，跨类改动，违背 P-027「不抽 mixin」先例——**不推荐** |
| M-C | 仅补日志不补计量 | 3 文件 | 与「可机械统计」目标不符，且 S5 同值分支仍不可区分——**不推荐** |

### 7.2 键名草案（16 → 本批 8）

| 站点 | 键 |
|------|----|
| S1 | `price_cache` |
| S2 | `industry_cache` |
| S3 | `mktcap_cache` |
| S4 | `performance_summary_team_report` |
| S5 | `orders_missing_price` |
| S6 | `next_day_open_price` |
| S7 | `pending_open_price` |
| S8 | `pinv_fallback` |

### 7.3 低效排除（正常路径零新增指令）

- S1-S3：仅在异常分支执行 1 次 dict 自增；正常路径 0 指令。
- S5：仅在 `except` 分支自增；L328 合法 `continue` 不计数（保持区分度）。
- S6/S7：仅在 `except` 分支自增；正常路径 0 指令。
- S8：仅在 `except LinAlgError` 分支自增。

---

## 8. 风险与未决项（四元块）

- **R-P029-1（P3）S8 分类争议**
  - 判据：注释是否构成「可观测载体」
  - 触发：Step 3 DESIGN 定稿
  - 当前倾向：判 **B 并补计数**——注释说明「为什么降级」，不说明「本次是否降级」；且 pinv 改变数值路径
  - 证据等级：E2（探针 `has_counter=False`、0 日志）

- **U-P029-1（P3）S3b 是否纳入本批**
  - 判据：`_init_research_team` L928 条件不满足时是否新增可观测载体
  - 触发：Step 3 DESIGN 裁决
  - 当前倾向：**纳入**；**形态经 Step 2 异构裁定修正（F-S2-P029-1）**——采用**计量键 `rotation_analyzer_skipped`（`else` 分支 1 行 `_record_failure`），不加 warning**：跳过可能是合法形态（`industry.pkl` 为可选数据，S2 本身即容缺失），每次运行刷 warning 与 U-P026-4 限流关切同源；计数与 S1-S3 的 `*_cache` 键在出口相邻，运维可对拍「缓存失败 → 跳过」因果链，且零日志噪声
  - 证据等级：E3（读码 L928-L936 无 `else` 分支）+ E2（Step 2 复扫）

- **U-P029-2（P3）S6/S7 队列重试语义**
  - 判据：开盘价缺失后订单保留重试是否为有意设计
  - 触发：Step 3 DESIGN 或第 5 批
  - 当前倾向：**保持现状**（本批只加计量，不改重试/过期语义）
  - 证据等级：E3（`_next_day_orders` / `pending_queue` 均未清空）

- **R-P029-2（P3）S5 键粒度**
  - 判据：按股票记录（`orders_missing_price:{stock}`）还是聚合单键
  - 当前倾向：**聚合单键**（避免股票池规模导致键爆炸；P-027 的 `custom_mask_build:{name}` 有配置面枚举上界，此处无）
  - 证据等级：E2（单站点单次注入）

- **R-P029-3（P3）S8 类级 vs 实例级**
  - 判据：`MeanVarianceAllocator` 可能被多策略并行复用
  - 当前倾向：**实例级**（与 P-027 一致；本批无 `@classmethod`）
  - 证据等级：E3

---

## 9. 负向发现

1. **S5 两条 `continue` 同值**：L328（缺列/缺日，合法）与 L331（异常）返回值相同——治理只计后者；T 用例须同时断言「合法分支计数 0 / 异常分支计数 1」，否则无法证明治理有效。
2. **S8 数值不可区分**：探针矩阵为单位阵时 pinv 与 inv 同值 → 验收只认路径计数，不认权重差。
3. **S1-S3 与 S3b 的因果链**：缓存失败本身被计数后，S3b 的 warning 才能解释「为何没有轮动分析器」；若只做 S1-S3，运维仍会看到「无分析器但无原因」。

---

## 10. 下一 Step

**Step 2 独立 Review（异构基座）**。注意：本文件作者基座为 DeepSeek-V4.1-Flash；异构 Review 须由非作者基座执行（P-027 先例为 GLM-5.3-Flash），复核重点：

1. 8 处清单行号与异常类型（E1 重放）；
2. E2 读数原文重跑（`%TEMP%\p029_probe.py`）；
3. S8 分类裁决（R-P029-1）与 S3b 纳入裁决（U-P029-1）；
4. 是否遗漏 `agents/` 同型站点（E4 复扫）。

---

## 11. Step 2 独立 Review（异构，2026-11-16）

> **审计基座**: **GLM-5.3-Flash**（≠ RESEARCH_p029 作者 DeepSeek-V4.1-Flash）→ RULE-5 异构条件成立。
> **基线**: HEAD `eeec92b`（Step 1 回填提交）；Python312 + `MPLBACKEND=Agg`。
> **门禁**: 本步为 docs-only 回写，零 Python 改动；全量读数引用 Step 1 CI run `43787578197`（711 passed，三 job success）。

### 11.1 E1 重放：8 处行号与异常类型（全过）

| ID | §3 声明 | 本基座复现 | 结论 |
|----|---------|------------|------|
| S1-S3 | `agent_framework.py:969-972 / 974-982 / 984-992`，bare `except:` | `Select-String 'except:'` = L971 / L981 / L991，均落在声明区间 | **一致** |
| S4 | `agent_framework.py:1154-1159`，bare `except:` | L1158 | **一致** |
| S5 | `multi_strategy_engine.py:325-331`，`(KeyError, IndexError)` → `continue` | L330 | **一致** |
| S6 | `multi_strategy_engine.py:388-391`，`KeyError` → `return` | L390 | **一致** |
| S7 | `multi_strategy_engine.py:449-453`，`KeyError` → `return` | L452 | **一致** |
| S8 | `strategy_allocator.py:625-630`，`np.linalg.LinAlgError` → pinv | L628 | **一致** |
| S3b | `agent_framework.py:928` 条件分支无 `else` 日志 | L928 `if self._industry_data is not None and self._price_data is not None:` → L929 直接 `try`，L936 后即 L938 团队创建，无 `else` | **一致** |

bare ×4 / 窄类型 ×3 / `LinAlgError` ×1 的口径统计与 U-P027-1 登记完全吻合。

### 11.2 E2 探针重跑（逐字一致）

`%TEMP%\p029_probe.py` 重跑 7 行输出与 §5 原文**逐字一致**（S1-3 三缓存 `None` + log_delta=2 为管道/合成器初始化日志；S4 `has_team_report=False`；S5 目标持仓空；S6/S7 静默 `return` 且队列保留；S8 `weights=[0.3333, 0.6667]` + `has_counter=False`）。日志归因复核：2 条日志出自 `FactorPipeline` / `FactorCombiner` 构造器（`try` 块之前），与异常无关——§9 负向发现的归因正确。

### 11.3 E4 复扫（独立重写脚本，无遗漏）

本基座**不依赖 Step 10 脚本**，重写 AST 扫描（`%TEMP%\p029_rescan.py`，判据与 P-027 口径同形）：`agents/` 22 个 except 处理器中**零可观测 9 处** = U-P027-1 的 **8 项逐一命中**（行号与异常类型全同）+ `research_team_v2.py:27`（`ImportError → IndustryRotationAnalyzer = None`，属 P-027 §12.6 既有「显式 import 降级」分类，非同型站点）。**结论：`agents/` 无遗漏同型站点，8 项口径封闭。**

### 11.4 两项裁决

| 项 | RESEARCH 倾向 | 本基座裁定 | 依据 |
|----|---------------|------------|------|
| **R-P029-1（S8 分类）** | 判 B + 计量 | **维持判 B + 计量** | ① O-S2-P027-1 的「注释为载体」判据 formulated 于 C 类「同值降级」场景（返回乐观默认值，注释说明 what）；S8 的 pinv **改变数值路径**（近奇异矩阵下 inv 与 pinv 结果不同），属 P-025 F-D3-P025-1 同型「静默数值降级」——该先例已确立「文档说明 ≠ 运行期可观测」；② 行内注释说明设计意图（why），不说明本次是否发生（whether）；③ 治理成本 1 行 + 实例计数器，零行为变更 |
| **U-P029-1（S3b 纳入）** | 纳入 + 1 条 warning | **纳入，形态修正为计量键 `rotation_analyzer_skipped`（`else` 分支 1 行），不加 warning**（**F-S2-P029-1，P3，当轮回写 §8**） | ① `industry.pkl` 为可选数据（S2 的 try/except 即容缺失），跳过是合法形态 → 每次运行 warning 属日志刷屏，与 U-P026-4 限流关切同源；② 计数与 S1-S3 `*_cache` 键在 `failure_counts` 出口相邻，因果链（缓存失败 → 跳过）可对拍；③ 零日志噪声、零行为变更。R-P029-3 实例级裁定同时维持 |

**R-P029-2（S5 聚合单键）/ R-P029-3（S8 实例级）：均维持。** R-P029-2 补充：T 用例必须同时断言「L328 合法 `continue` 计数 0 / L330 异常 `continue` 计数 1」（§9 负向发现 1 的验收化）。

### 11.5 发现与分级

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-S2-P029-1 | **P3** | U-P029-1 形态：RESEARCH 建议 warning，异构裁定改为计量键（防合法缺失场景日志刷屏） | 当轮回写 §8 |
| O-S2-P029-1 | 观察 | `agents/` 唯一额外零可观测点 `research_team_v2.py:27` 属既有 import 降级分类，非本批范围 | 维持 P-027 §12.6 裁决 |
| O-S2-P029-2 | 观察 | S8 键名 `pinv_fallback` 与 P-027 C 类内联计数形态不同（将走 `_record_failure`）——Step 3 DESIGN 定稿时统一 | 移交 Step 3 |

**P1 = 0 / P2 = 0 / P3 = 1（当轮已修）。**

### 11.6 结论与下一 Step

**Review pass。** 五项复核重点全部完成：E1 重放 8/8 一致、E2 逐字复现、E4 无遗漏、S8 维持判 B、S3b 纳入（形态修正为计量）。RESEARCH §1-§9 的事实陈述、分类算术（B 7 + 待裁决 1 + 观察 1）、方案矩阵与键名草案均可支撑 Step 3 DESIGN。

**下一 Step**: **Step 3 DESIGN**——定稿口径：8 计量（S1-S8）+ S3b 计量键 `rotation_analyzer_skipped` = **9 计量 / 3 文件**；零新增日志（比 RESEARCH 原建议少 1 条 warning）、零 fail-fast、零返回值语义变更；新增载体仅 `MeanVarianceAllocator`（实例级三件套）；`except Exception` 合计恒 22。
