# DESIGN：P-016 P-015 复审 P3 修正

> **批次**: P-016 · T1
> **上游**: [RESEARCH_p016_p015_review_fixes.md](RESEARCH_p016_p015_review_fixes.md)（§5 方案矩阵 N-A / W-A / X-A / R-A）
> **下游**: [IMPL_p016_p015_review_fixes.md](IMPL_p016_p015_review_fixes.md)；[CHECKLIST_p016_p015_review_fixes.md](CHECKLIST_p016_p015_review_fixes.md)
> **代码证据时点**: HEAD `90eb879`（E1 2026-11-10）
> **状态**: Step 3 完稿 + Step 4 Review 通过（§7）

---

## 1. 目标与边界

**目标**：以最小结构改动消除 P-015 复审的三项 P3 形式缺口，并堵住同路径的静默数据丢失（F-S9-P016-1）。

**不覆盖（职责外）**：U-P015-1 第二例框架对拍；U-P016-1 的 rate>0 费用语义定义。

**能力边界**：本批不新增任何 case、不新增恒等式，故不改变「准确性校准」的结论域。

---

## 2. 设计决策（D1-D4）

| # | 决策 | 被拒方案 | 拒绝理由 | 代价 |
|---|------|----------|----------|------|
| **D1** | `Checks` 引入三态状态词表 `pass / fail / waiver`：`waiver` 从断言计数中结构性排除，stdout 与报告均渲染为独立标记 | W-B 删除豁免行 / W-C 仅加注释 | 删除丢登记；注释不改「恒真即 PASS」的形式 | 报告 schema 变更，历史读数需重述口径（见 §3 I5） |
| **D2** | `write_report` 增加**人工章节保护**：目标已存在且含人工标记（`## 1. vectorbt 权威签名核验` / `## 3. 口径映射实测结论`）时，改写 `<stem>.generated<ext>` 并打印保护提示 | R-B 仅文档告警 / R-C 读回拼接 | 告警晚于覆盖；拼接脆弱且混淆生成/人工边界 | 复放命令需知道「保护会改名」——写入报告 §4 与 CHECKLIST F-1 |
| **D3** | `simulate_vbt_spec` 在 `cost_rate > 0` 时 `raise NotImplementedError`（文案含 case 与费率，指向 U-P015-1） | X-B 仅文档 / X-C 本批定义语义 | 未定义语义不得静默产出；定义需新 case 与独立取证，超出 P3 | 未来启用 rate>0 时须先解 U-P016-1 |
| **D4** | I2a 命名映射**只补文档**（C-2 判据列 + DESIGN §3.2 交叉引用），不拆独立断言行 | N-B 拆 `I2a.qty` 行 | 与 G1.qty 数学恒等，重复断言虚增计数 | 读者需经文档映射才能对上 I2a ↔ G1 |

---

## 3. 不变量（I1-I6，本批自证）

| ID | 不变量 | 形态 |
|----|--------|------|
| **I1** | 全链恒等式**结论不变**：五 case 全跑时所有断言仍 0 失败、exit 0 | 复放对比 |
| **I2** | **断言数守恒剔除豁免**：29 行记录 = 28 断言 + 1 豁免（改前误计为 29 断言） | 计数读数 |
| **I3** | **PASS/FAIL 语义不变**：任何原本 FAIL 的场景仍 FAIL（B5 单跑 I5 仍 exit 1） | 负路径探针 |
| **I4** | **报告 §2 数值不变**：除豁免行的结果列渲染方式外，逐行读数与改前一致 | 逐行 diff |
| **I5** | **人工章节保全**：对已入库报告执行 `--report`，§1/§3/§4 内容零改动（写入改名文件） | 前后哈希比对 |
| **I6** | **fail-fast 精确**：`simulate_vbt_spec` 仅对 `cost_rate > 0` 拒绝，B2（rate=0）行为不变 | 正负双探针 |

---

## 4. 状态词表与渲染规格（D1）

| 状态 | 产生方式 | 计入断言 | 计入失败 | stdout | 报告「结果」列 |
|------|----------|----------|----------|--------|----------------|
| `pass` | `Checks.add(..., ok=True, ...)` | ✅ | — | `PASS` | `✅ PASS` |
| `fail` | `Checks.add(..., ok=False, ...)` | ✅ | ✅ | `FAIL` | `❌ FAIL` |
| `waiver` | `Checks.waive(...)` | ❌ | ❌ | `WAIVER(非断言)` | `— 豁免（非断言）` |

汇总行格式：`共 {N} 项断言（失败 {M} 项）+ 豁免登记 {K} 项`。退出码仅由 `M > 0` 决定（与改前一致）。

## 5. 人工章节保护规格（D2）

- 标记常量：`MANUAL_MARKERS = ("## 1. vectorbt 权威签名核验", "## 3. 口径映射实测结论")`
- 判定：目标文件存在 **且** 命中任一标记 ⇒ 写入 `path.with_name(f"{path.stem}.generated{path.suffix}")`
- 提示：`[verify] [保护] {name} 含人工章节（§1/§3），改写 {new_name}；请人工比对 §2 后再合并`
- 未命中 ⇒ 原路径直接写（保持临时路径的常规用法）。

## 6. fail-fast 规格（D3）

```python
def simulate_vbt_spec(close, factor, spec) -> dict:
    if spec.cost_rate > 0:
        raise NotImplementedError(
            "simulate_vbt_spec 的费用语义未定义（F-R5-P015-3 / U-P016-1）："
            f"case={spec.case} cost_rate={spec.cost_rate}；rate>0 的 targetpercent "
            "规格待 U-P015-1（Backtrader 第二例）立项时定义"
        )
    return _simulate(...)
```

## 7. Step 4 Review（设计文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 设计基于已验证的调研结论（四项决策逐条对应 RESEARCH §5 的推荐方案 + 其被拒方案的拒绝理由）
- [x] 无未经验证的假设（D2 的标记文本取自入库报告实际标题，E3 核对；D3 的调用点唯一性由 P3 行号确认）
- [x] 无论证驱动的归因扭曲：未把「三项 P3」简化为单一成因——四项发现各有独立触发路径（计数口径 / 恒真形式 / 语义未定义 / 文件覆盖）
- [x] 替代方案已列并被否决（N-B / W-B / W-C / X-B / X-C / R-B / R-C 七项）
- [x] 职责边界清晰（§1 已区分职责外与能力边界）

**Step 4 Review 结论：通过**。
