# P-013 Golden 基线固化（L4 判据）· 调研（Step 1）

> **文档编号**: RESEARCH_golden_baseline
> **阶段**: Phase 1 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **档位**: **T1**（新增 `tests/` + `tests/golden/` + `scripts/`，触及 CI 门禁）
> **证据时点**: 本仓读数 @ `6f583fc`（2026-11-10）；Python 3.12.10 / pytest 9.0.3
> **上游**: [PROGRESS §1.4 U-D1(P-011)](PROGRESS.md)（L4 golden 挂起项升格）；[AUDIT_SUMMARY §7.1](AUDIT_SUMMARY_backtest_validation.md)（U-D1 触发条件）；[RESEARCH_backtest_validation.md](RESEARCH_backtest_validation.md) §6.1 V-B / §6.6 分层路线
> **状态**: Step 1 完稿，待 Step 2 Review

---

## 1. 为什么现在做（前置条件核查）

P-011 曾明确「L4 golden 必须等口径修正落地后录制，否则基线作废或固化错误」（RESEARCH §6.6 U-1 = V-A 裁决）。三项前置现已满足：

| 前置 | 状态 | 证据 |
|------|------|------|
| 复权三口径分离（trade/valuation=raw、signal/return/limit=hfq） | ✅ 已实施 | P-012 B3a/B3b（`ad40490` / `79c4dea`），ADR-017 |
| 涨跌停掩码时点 + ST 规则表 | ✅ 已实施 | P-012 B2/B4（`4e2ab0b` / `3717246`） |
| 退市动态池（`list_date`/`delist`） | ✅ 已实施 | P-012 B5（`94018f2`），`core/universe_data.py` |
| 指标口径唯一（`compute_metrics` 单来源 + `metrics_method` 落盘） | ✅ 已实施 | P-011 B3（`9ec9f7d`）+ F-A1 修复（`a754a2d`） |
| RULE-5 异构复审确认无未归因行为 | ✅ pass | CHECKLIST_backtest_validation §9.6（`2d452fd`） |

**结论**：口径已稳定，此时录制的基线不会把已知缺陷焊死。若再推迟到下一位引擎行为变更之后，将失去「变更前基线」的对照价值。

## 2. 外部锚点（复用 P-011 已确立锚点，本批不新增外部检索）

| 锚点 | 来源 | 关键结论 | 对本批的约束 |
|------|------|----------|--------------|
| **A20** | Golden Master / Characterization Testing（Feathers） | 「不断言代码应该做什么，只断言它当前做什么」——golden 只锁行为，**不证明正确性** | 基线文档必须显式声明「非正确性证明」，正确性由 P-011 L1-L3 承担 |
| **A21** | OSTI · Testing of Scientific Software | 科学软件采用「单元 → 回归 → 系统」分层 | golden 属回归层，不得替代不变量/差分测试 |
| **A25** | NautilusTrader DST 契约 | 可复现性需**定义成立条件**并提供 source seams/checks | 基线必须绑定「数据指纹 + 配置指纹 + git commit」三要素 |
| **A26** | MLflow Experiment Tracking 最佳实践 | 每次 run 记录 git commit + 冻结配置 + 环境快照；检测脏工作区 | 录制脚本须记录 HEAD、配置全文、工作区状态 |

> 说明：A20 的「不证明正确性」与本批目标一致——本批交付的是**回归防护网**，不是准确性论证。P-011 已交付的 L1-L3（不变量 / 参考实现差分 / 事件级等价）才是准确性论证。

## 3. 本仓事实（E3 读码 / E1 命令，@`6f583fc`）

| ID | 事实 | 证据 |
|----|------|------|
| P1 | `tests/_synth_fixture.write_price_fixture` 可写 close/open/high/low/stock_adj/suspend/st/industry，但 **open/high/low 硬复用 close 矩阵** | `_synth_fixture.py:51-52`（`for name in ("close","open","high","low")` 同一 `matrix`） |
| P2 | 现有合成夹具规模为 3 日 × 2 股、常量价、零费用，仅够事件级等价 | `test_cross_engine_equivalence.py:33-38` |
| P3 | 退市夹具格式已有可用范例：`universe/list_date.csv`（stock,list_date）、`delist.csv`（stock,delist_date,delist_return）、`manifest.json` | `test_universe_delisting.py:33-55`；`core/universe_data.py:36-76` |
| P4 | V3 结果字段：`portfolio_value`/`returns`/`total_return`/`annual_return`/`volatility`/`sharpe_ratio`/`max_drawdown`（正值）/`risk_free_rate`/`metrics_method`/`final_value`/`initial_value` | `engine_v3_vector.py:409-423` |
| P5 | V2 结果经 `generate_report` 出 analytics（含 total/annual/vol/sharpe/mdd/win_rate/sortino/calmar/drawdown_duration）+ `additional_info`（config / invariant_report / validation_declaration / manifest） | `engine_v2.py:1022-1052` |
| P6 | `data/test_ashare` 与 `data/test_fixture_biased` 均被 `.gitignore` 忽略 → **CI 不可用** | `.gitignore` + P-009 教训（run `41970636863` 27 项数据测试失败） |
| P7 | **CI 三版本（3.10/3.11/3.12）均无 numba**——`pyproject.toml` 的 `dependencies` 与 `dev` 依赖均未声明 numba，CI 安装 `".[dev]"` 后走 `py_func` 回退路径；**本地**因环境预装 numba 走 `@njit` 路径。故同一基线需在**两条路径**上同时通过 | `.github/workflows/tests.yml:16/37`（矩阵 3.10-3.12 + `pip install ".[dev]"`）；`pyproject.toml:28-68`（无 numba）；AUDIT_SUMMARY §5 记 3.10 `602 passed, 1 skipped`（本地 609 − 7 为 numba 相关 importorskip） |
| P8 | `core/manifest.py` 已提供 `build_manifest` / `_fingerprint`（git commit + data sha256 + config 规范化 JSON） | `manifest.py:119/128/177` |
| P9 | 六层归因 `scripts/change_report.py` 已落地（残差 <1e-8 + `attribution_complete` 门） | P-012 B1/D6 |
| P10 | 当前门禁基线：`609 passed` / 68 测试文件 / black 167 / mypy 0（36 files）/ 盲区 4 errors 2 files | `6f583fc` 实测（本会话 E1） |

## 4. 关键约束推导

1. **必须用合成夹具**（P6）：任何依赖 `data/` 下 pkl 的基线在 CI 上必然失败；golden 夹具必须 100% 代码构造 + 写入 `tmp_path`。
2. **必须支持独立 OHLC**（P1）：若 `open ≡ close`，「T+1 开盘成交」与「同日收盘成交」无差异，V2/V3 的成交时点口径无法被基线覆盖；且涨跌停判定（P-012 D4 价格法用开盘价）无法触发。
3. **必须用容差而非比特相等**（P7）：CI 全程 `py_func` 路径、本地 `@njit` 路径，两者对同一输入存在末位差异（F-S9-2 实测 ~1e-10 量级）；比特锁死会导致「本地绿、CI 红」或反之。
4. **必须绑定指纹**（A25/A26 + P8）：否则数据或配置漂移会被误判为代码回归。
5. **基线不得声明正确性**（A20）：文档与测试命名须避免「验证正确性」措辞，只称「锁定当前行为」。

## 5. 方案矩阵

### 5.1 基线存储与录制方式

| 方案 | 内容 | 成本 | 可审计 | 防误录 | 评价 |
|------|------|------|--------|--------|------|
| **A 显式录制脚本 + JSON 入仓**（推荐） | `scripts/record_golden.py` 生成 `tests/golden/*.json`；测试只读比对 | 低 | 高（diff 可见） | 高（录制需显式命令 + 工作区检查） | 与 P-011 `change_report` 一致 |
| B 测试内 `--golden-record` flag | 测试自行可写基线 | 低 | 中 | 低（易误覆盖） | 拒绝：录制与断言混在一处 |
| C 内联常量于测试文件 | 期望值硬编码 | 低 | 高 | 中 | 体积大、字段多时不可读 |

### 5.2 容差策略

| 方案 | 内容 | 评价 |
|------|------|------|
| **A 分字段容差**（推荐） | 金额/收益/比率 `rtol=1e-9`；整数（trades 计数、股数）精确；权重 `rtol=1e-12` | 吸收 numba 末位差，又不掩盖真实漂移 |
| B 统一 `rtol=1e-6` | 全部字段同容差 | 过宽，可能漏掉真实小漂移 |
| C 分环境基线（本地/CI 各一份） | 两套期望值 | 拒绝：维护翻倍且掩盖环境差 |

### 5.3 基线内容粒度

| 方案 | 内容 | 评价 |
|------|------|------|
| **A 指标 + NAV 摘要 + 成交统计**（推荐） | 6-9 项指标 + NAV 首/末/最小值 + trades 笔数/成交额合计 | 漂移定位足够，体积小 |
| B 仅指标 | 只锁 6 项指标 | 无法发现「指标巧合相同但路径不同」 |
| C 全量逐日 NAV | 每日净值序列 | 体积大、对微小浮点噪声过敏 |

## 6. 六条基线定义（候选，待 Step 3 定稿）

| ID | 引擎 | 场景 | 触发点 | 关键断言 |
|----|------|------|--------|----------|
| G1 | V2 | 基础 | 常量价、零费用、3 日×2 股 | 对齐现有事件级等价夹具，作为基线自检锚 |
| G2 | V2 | 费用 | 真实波动 + 佣金(万3/下限5) + 印花税 + 滑点 + 整手 | 费用合计 == trades 逐笔之和 |
| G3 | V2 | 掩码 | 涨跌停（开盘价触及限幅）+ 停牌 + ST | 被掩码标的当日无成交；`additional_info` 记录 |
| G4 | V3 | 基础 | 常量价、零费用 | NAV 与 G1 逐日相等（已有等价结论的回归锁） |
| G5 | V3 | 费用 | 真实波动 + `cost_rate` | 成本 == `cost_rate × 成交额` |
| G6 | V2 | 退市 | `universe/{list_date,delist}` 触发动态池 | 退市日后该标的从可交易集合移除 |

> G3/G6 需要扩展 `_synth_fixture.py` 支持独立 OHLC（P1）与 universe CSV（P3）。G1/G4 复用现有能力即可。

## 7. 未决项（四元块）

| ID | 问题 | 选项 | 推荐 |
|----|------|------|------|
| **U-G1** | 基线文件是否带 `schema_version` | A 带 / B 不带 | **A**：字段增删时显式升级，避免静默兼容 |
| **U-G2** | 录制是否要求工作区干净 | A 强制（脏则拒录）/ B 警告 / C 不检查 | **A**：防止「未提交代码 + 已录基线」组合污染 |
| **U-G3** | 断言失败的报错粒度 | A 逐字段报告期望/实际/相对误差 / B 只报首个失败 | **A**：定位成本远低于实现成本 |
| **U-G4** | 基线与 `manifest` 指纹的关系 | A 基线内嵌指纹并在测试中比对 / B 只记录不比对 | **B**：指纹随数据/配置变，硬比对会让无害改动频繁失败；改为记录 + 告警 |

## 8. 文献与内部锚点清单

- **A20** Golden Master / Characterization Testing（Feathers 术语，工程实践，T3）
- **A21** OSTI · Testing of Scientific Software（美国能源部，T2）
- **A25** NautilusTrader · Deterministic Simulation Testing 官方契约（T1）
- **A26** MLflow · Experiment Tracking Best Practices（官方，T1）
- 内部：P-011 RESEARCH §6.1 V-B（方案定义）/ §6.6（U-1 裁决）/ A17（差分测试）
- 内部：P-011 DESIGN §4.2（指标口径）/ CHECKLIST §9.6（RULE-5 复审结论）

## 9. Step 2 待核项（供 Review 使用）

1. P1（open/high/low 复用 close）是否为真——需读 `_synth_fixture.py` 原文确认；
2. P6（`data/` 被 gitignore）需以 `.gitignore` 原文 + P-009 历史 run 双证；
3. P7（CI 无 numba 的范围）需以 `pyproject.toml` 依赖清单 + workflow 安装命令确认；
4. 六条基线的「触发点」是否都能在合成夹具上构造（尤其 G3 涨跌停：需开盘价精确等于前收×限幅）。

## 10. Step 2 Review 结论（2026-11-10）

**审查基座**: 本会话 DeepSeek-V4.1-Flash（与 Step 1 同基座；**异构 RULE-5 复审留待独立会话**，同 P-011 先例）

| 待核项 | 方法 | 结果 |
|--------|------|------|
| P1 | E3 读 `_synth_fixture.py:51-52` | ✅ 确认：`for name in ("close","open","high","low")` 共用同一 `matrix` |
| P6 | E1 `Select-String .gitignore` | ✅ 确认：`:62 data/`、`:63 !data/.gitkeep` |
| P7 | E1 读 `tests.yml:16/37` + `pyproject.toml` 依赖清单 | ⚠️ **修正**：原文写「3.10 无 numba」，实为 **CI 三版本均无 numba**（`dev` 依赖未声明），本地才有——见 F-R-G1 |
| G3 可构造性 | E3 读 `filter/limit_rules.py:103/129` | ✅ 确认：`resolve_limit` + `build_limit_prices` 可按 `(board,is_st,date)` 构造限价；夹具令 `open == limit_up` 即可触发 |

**发现（1 项 P2，已就地回写）**

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-R-G1 | P2 | RESEARCH P7 把「CI 无 numba」窄化为「仅 3.10 无 numba」，实际三版本 dev 依赖均未声明 numba → CI 全程 `py_func` | 已回写 P7 与约束 3；容差设计据此从「吸收个别版本差异」升级为「必须同时兼容两条路径」 |

**结论**：P1=0 / P2=1（已回写）/ P3=0；调研事实链完整，**可进入 Step 3 DESIGN**。
