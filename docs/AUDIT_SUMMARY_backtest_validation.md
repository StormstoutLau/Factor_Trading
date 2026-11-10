# P-011 回测准确性验证、学术规范与基准比较 · 审计总结（Step 11）

> **文档编号**: AUDIT_SUMMARY_backtest_validation
> **阶段**: Phase 3 - 收口（SPEC_PROCESS 十步之外的用户指令扩展步：对 Step 1-10 全流程做交叉总结）
> **日期**: 2026-11-10
> **状态**: **P-011 done（Step 1-10 全通过 + RULE-5 异构复审 pass）**；本总结为 Step 11 交叉复核产物，不改变任何 Step 10 结论（Step 12 RULE-5 复审见时间线）
> **上游**: [RESEARCH](RESEARCH_backtest_validation.md) · [DESIGN](DESIGN_backtest_validation.md) · [IMPL](IMPL_backtest_validation.md) · [CHECKLIST](CHECKLIST_backtest_validation.md)（§9 ADD 审计 / §10 验收结论）
> **台账**: [PROGRESS §3.12](PROGRESS.md) · [CHANGELOG](../CHANGELOG.md)
> **解释器 / 门禁**: Python 3.12.10；session `factorv3-p011-backtest-validation-20261110`（`replay: 10 rows OK`）
> **审查者**: 本总结由单 Agent 自查产出（DeepSeek-V4.1-Flash，与实施同基座——见 §7.1 限定）；数据全部取自四文档已登记读数，无新增结论性判断

---

## 1. 批次目标与回答

用户四问（立项输入）→ 本批交付映射：

| # | 用户问题 | 本批交付 | 残余边界 |
|---|----------|----------|----------|
| Q1 | 如何判断回测准确性 | 四层判据 L1-L4（RESEARCH §5）落地 L1-L3：不变量 I1-I7 + 参考实现差分 + 事件级等价 + 三口径唯一（I9） | L4 golden 挂起（U-D1） |
| Q2 | 如何验证符合学术规范 | 偏差声明（PIT / 多重检验 / 幸存者 / benchmark / walk-forward 逐项显式 false 或 true，附 5 条 `known_limitations`）+ 指标单一口径（`metrics_method` 随结果落盘） | DSR/PBO 无 trials 数据可算（U-2 裁决挂起） |
| Q3 | 是否具备断点排查能力 | `--trace-dir` 逐日六层快照 + `manifest.json`（git/数据 sha256/配置/指纹）——从「事后可查、过程不可查」升级为「过程可复放」 | trace 体积无采样策略（U-D3，触发条件未触发） |
| Q4 | 是否需要 Qlib/Backtrader/VectorBT 基准 | [BACKTEST_CALIBER_MAPPING.md](BACKTEST_CALIBER_MAPPING.md)：口径矩阵 + 残差恒等式，**只声明可解释差异、不声称一致**（A27/A28：默认参数对拍必败） | 不引入外部依赖（D9） |

## 2. 流程时间线（Step 1-11）

| Step | 产出 | Verdict | 审查基座 |
|------|------|---------|----------|
| 1 调研 | RESEARCH（A1-A30 锚点 + P1-P18 仓事实 + 四层判据 + U-1~U-4） | — | DeepSeek-V4.1-Flash |
| 2 Review | E1/E3 抽检 5 处全命中；F-R4 回写 | P1=0 通过 | GLM-5.3-Flash（异构） |
| 3 DESIGN | D1-D9 / I1-I10 / B1-B6；F-D1~F-D6 读码发现 | — | DeepSeek-V4.1-Flash |
| 4 Review | E2 探针证伪「年化分母不一致」+ 实证 V3 回撤缺锚点；F-R1（P1）重写 D5/F-D3 | P1 回写后残差 0，通过 | GLM-5.3-Flash（异构） |
| 5 IMPL | T-0~T-14 / V1-V16 / 52 用例预测 | — | DeepSeek-V4.1-Flash |
| 6 Review | E2 证实 numba 默认参数可编译；1 项证伪（`get_all_trades`）；F-I1~I3（P2） | P1=0 通过 | GLM-5.3-Flash（异构） |
| 7 CHECKLIST | 76 项验收清单，零预填 | — | DeepSeek-V4.1-Flash |
| 8 一致性 Review | 13 链接 0 broken / 76 ID 连续 / 术语 7 组 / V↔G 16 项归宿；F-S8-1~3（P3） | P1=P2=0 通过 | GLM-5.3-Flash（异构） |
| 9 实施 | 6 批 + 3 补丁（§4）；**609 passed / black 167 / mypy 0 / 68 测试文件**；B3 双证 | 验收通过 | DeepSeek-V4.1-Flash |
| 10 ADD 审计 | 四阶段全过；F-A1（P2）修复 `a754a2d`；门禁 `replay: 10 rows OK` | P1=0 / P2=1（已修复）/ P3=2 | DeepSeek-V4.1-Flash（**同基座限定**） |
| **11 审计总结（本档）** | 交叉复核 + 台账归并 | 无新发现（§3 注记 2 项 P3 归并） | DeepSeek-V4.1-Flash |
| **12 RULE-5 异构复审（用户指令，收口步）** | 按 CHECKLIST §9.3 取证矩阵独立重放 E1-E5（[CHECKLIST §9.6](CHECKLIST_backtest_validation.md)） | **pass**——7/7 命中，0 P1/P2，2 项 P3 文档修正（F-R5-1/F-R5-2），审计结论维持 | GLM-5.3-Flash（**异构**） |

> 流程有效性观察：**异构 Review（Step 2/4/6/8）全部命中实质问题**（含 1 项 P1 F-R1）；实施期发现（F-S9-1 P1）由不变量观测网自身暴露——观测网在接入首日即兑现设计价值；Step 10 审计捕获的 F-A1 是唯一逃过前 8 步的 P2，根因为「设计交付物无对应验收行」（§7.3 教训）。

## 3. 发现台账（28 项，全部闭环）

按发现阶段与等级汇总（P1=2 / P2=7 / P3=19；P1/P2 全部修复或回写，P3 全部披露）：

| 阶段 | ID | 等级 | 一句话 | 回写位置 |
|------|----|------|--------|----------|
| Step 3 | F-D1 | P3 | V2 无「关闭 T+1」配置 → 全历史对拍不可实现，降级事件级等价 | DESIGN §4.5 / IMPL T-5 |
| Step 3 | F-D2 | P3 | V2 整数股 + `value_buffer=0.985`（夹具构造依据） | DESIGN §4.5 |
| Step 3 | F-D3 | P3 | 「年化分母不一致」被 Step 4 E2 **证伪**（两引擎均 252/N） | DESIGN §4.2（重写） |
| Step 3 | F-D4 | P3 | `commission_min=5` 零费率下仍生效（夹具需显式置 0） | IMPL T-5 |
| Step 3 | F-D5 | P3 | 层 dump 为 CSV 且 pyarrow 未声明 → trace 复用 CSV | DESIGN D8 |
| Step 3 | F-D6 | P3 | V3 信号不经 FactorPipeline（对拍夹具规避） | IMPL T-5 |
| Step 4 | **F-R1** | **P1** | V3 回撤缺初始锚点低估幅度（pv=[100,90,81] 报 10% 应 19%）+ 量级约定统一 | DESIGN §4.2/§5.4/I9/§7.3（重写） |
| Step 4 | F-R2 | P2 | F-D1 锚点行号不精确 | DESIGN §7.2 |
| Step 4 | F-R3/F-R4 | P3 | §4.5-3 措辞；B3 消费方清单（唯一需更新断言 = test_v3_engine_integration:217） | DESIGN 对应节 |
| Step 6 | F-I1 | P2 | `get_all_trades` 不存在（实际 `get_trades`） | IMPL T-1 / interfaces.py:201 |
| Step 6 | F-I2 | P2 | R7 夹具低于脚本下限 → 31 股×60 日 | IMPL §3.1 R7 |
| Step 6 | F-I3 | P2 | 失败骨架破坏零数值批次绿性 → T-0 收窄 | IMPL §3.2 |
| Step 6 | F-I4/F-I5 | P3 | 悬空引用；DESIGN §4.1 签名缺参 | IMPL §1.2 / DESIGN §4.1 |
| Step 8 | F-S8-1~3 | P3 | 头注含 T-2；C5 锚点指向错误文档；预填判据精确化 | CHECKLIST §1/§3/§8 |
| Step 9 | **F-S9-1** | **P1** | `_take_snapshot` 浅拷贝共享 `Position` → 引擎实跑 53 项 I1/I2 违规 | tracker.py:261 逐 Position `replace()` |
| Step 9 | F-S9-2 | P2 | numba 顺序累加 vs NumPy pairwise（含 CI 无 numba 场景） | `_seq_sum` + JIT 判定（`7bcdd57`） |
| Step 9 | F-S9-3 | P2 | 末日强平同日第二快照 → I2 跳过同日多快照 | invariants + ambiguous 用例 |
| Step 9 | F-S9-4~7 | P3 | 阴性对照 3_000；trace 容差 1e-8；B3 回退冲突注记；`check_v3_*` 无直接单测 | DESIGN/IMPL/CHECKLIST |
| Step 10 | **F-A1** | **P2** | `metrics_method` 声明未落地（测试全绿仍缺失——Iron Law 反例） | `a754a2d` 修复 + 断言并入 2 用例 |
| Step 10 | F-A2/F-A3 | P3 | manifest `benchmark` 键设计补注；analytics `<2` 返回 `{}` 边界披露 | DESIGN §4.4/§5.2 / IMPL §9.5 |

**归因观察**：P1 两项均非「测试没写」而是「观测量缺失」——F-R1 靠 E2 数值探针（对拍两引擎同一 pv）、F-S9-1 靠 I1/I2 恒等式（对账快照与成交）。四层判据的 L1/L2 层（对账类）捕获的是 L3 层（差分类）测不到的缺陷类别，两者互补的设想被实测证实。

## 4. 交付物与提交链

**提交链（13 个，`dc71c1a..2e2cf6e`）**：

| 类型 | 提交 |
|------|------|
| 批次 ×6 | B1 `cd6d619` → B2 `26929c6` → **B3 `9ec9f7d`（唯一行为批）** → B4 `e59dee2` → B5 `beaa3a1` → B6 `b6bcee3` |
| 修复 ×3 | `d270511`（manifest E1/E7 用例）· `7bcdd57`（无 numba 兼容，CI 首跑暴露）· `a754a2d`（F-A1 metrics_method） |
| 文档 ×4 | `f043e94`（Step 9 回填）· `b9c7d75`（CI 回填）· `955f06a`（Step 10 回填）· `2e2cf6e`（终态 run 回填） |

**产物**：`core/` 新增 4 模块（invariants 354 行 / metrics 105 / validation 70 / manifest 187）+ 改 4（engine_v2、engine_v3_vector、analytics、config、tracker、interfaces）；`tests/` 新增 2 辅助 + 8 测试文件（59 用例）+ 改 3 既有；`cli.py --trace-dir`；文档 5 份（四文档 + [BACKTEST_CALIBER_MAPPING](BACKTEST_CALIBER_MAPPING.md)）+ 本总结。

## 5. 末态指标与证据

| 维度 | 读数 | 证据 |
|------|------|------|
| 测试 | **609 passed**（550+59，0 fail / 0 新 skip）/ 68 文件 | `pytest tests -q`（本地与 CI 双跑） |
| 格式 / 类型 | black **167 unchanged**；mypy **Success: 36 files**；盲区 4 errors 2 files（不劣化） | E1 门禁链 |
| B3 行为归因 | Δ 表逐字段 + `change_report residual 0.0` / `attribution_complete true` / 六层 `changed` 全 0；NAV/trades 逐值不变 | E2（`[未入仓-不可重放]`，场景=R7 夹具 31×60） |
| 零数值批次 | B1/B2/B4/B5/B6 diff 不含执行路径；`execution.py`/`data.py`/`filter/` 零改动 | E1 git diff |
| 远端 CI | run `42768525717`（三 job success）→ `42768882526` → **`42771058634`（终态，含 F-A1 修复远端首跑）**；3.10 `602 passed, 1 skipped`（本地 609 − 7 为 numba 相关 importorskip，既有基线同构） | `gh run view` |
| 门禁会话 | `replay: 10 rows OK`（probe + 3 gates ×2 轮） | F:\Spec_Runner\sessions\ JSONL |

## 6. 能力声明与边界（对报告消费者的诚实清单）

`validation_declaration` 已随每次回测落盘，要点复述：**未做**多重检验校正、**无** PIT 数据版本轴、**基准指数未实现**（benchmark 占位）、V2 目标持仓为整数股且含 0.985 现金缓冲、V3 为筛选器定位（同日收盘、无风控/待执行队列）；walk-forward 可用但本次未使用；`rf=0.03`、年化 `252/N`、回撤非负量级、Sharpe=`(annual-rf)/vol` 均可经 `metrics_method` 复核。跨引擎差异（V2 次日开盘 vs V3 同日收盘）经事件级等价与口径映射声明为**可解释常数**，不声称一致。

## 7. 遗留与建议

### 7.1 未决项

| 项 | 状态 | 触发条件 |
|----|------|----------|
| RULE-5 异构第二会话复审（Step 9/10） | **已闭合**（2026-11-10，[CHECKLIST §9.6](CHECKLIST_backtest_validation.md)：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash，E1-E5 独立重放 7/7 命中，0 P1/P2，2 项 P3 文档修正 F-R5-1/F-R5-2） | — |
| U-D1 golden 回归（L4） | 挂起（设计裁决） | 下一次引擎行为变更前，或需对外发布回测结论 |
| U-D2 V2 同日收盘模式 | 挂起（倾向不做） | 第三方要求逐日净值一致 |
| U-D3 trace 采样/保留策略 | 挂起 | 长区间/全市场 trace（体积 > 500 MB） |
| U-D4 manifest CI 完整性 | **实际已闭合**：CI 三 job 均通过 manifest 9 用例（git 可用、指纹稳定、E7 降级路径单测覆盖）；建议下一批次顺手在 DESIGN §11.1 标注闭合 |

### 7.2 对后续批次的流程建议

1. **Phase 0 验收行映射前置**：Step 7 起草 CHECKLIST 时对 DESIGN 每个「报告新增 X」类交付物逐条建行（F-A1 的直接教训）——可机械检查：DESIGN 数据流图中的 `additional_info` 键集合 == CHECKLIST 出现过的键集合。
2. **观测网先行**：F-S9-1 证明把 I1-I7 接入引擎跑一次真实样本即可暴露历史缺陷；后续任何触及 tracker/执行路径的批次，应把 `invariant_mode="raise"` 的一次全量跑列为取证步骤。
3. **CI 无 numba 是一等场景**：本地 `NUMBA_DISABLE_JIT=1` 双跑应成为涉及 `@njit` 函数测试的固定取证项（本次 CI 首跑才暴露）。

### 7.3 本总结注记（2 项 P3 归并，无新发现）

- CHECKLIST §10.0 补丁行已含 `a754a2d`，但 §10.1 统计表的 76 项判定不因 Step 11 改变（F-A1 属 D5 交付，覆盖由 C1-C3 + E 组承担，无行级变化）。
- §2 时间线中 Step 9 验收写「验收通过」对应 CHECKLIST §10.2；Step 10 后维持不变。

## 8. 结论

P-011 以 T1 完整管线走完 SPEC_PROCESS 十步 + 本总结步：四文档链互引闭环、28 项发现全部登记回写、四层判据落地 L1-L3、行为批次（B3）经 Δ 表与六层归因双证、远端 CI 终态全绿。批次交付的观测网（不变量 + trace + manifest）自此构成后续任何引擎变更的回归与断点排查基础设施。**P-011 收口。**
