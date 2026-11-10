# DESIGN：P-017 P-016 复审 E4 四项 P3 修正

> **批次**: P-017 · T1
> **上游**: [RESEARCH_p017_p016_review_fixes.md](RESEARCH_p017_p016_review_fixes.md)（§5 方案矩阵 N-A / M-A / G-A / C-A）
> **下游**: [IMPL_p017_p016_review_fixes.md](IMPL_p017_p016_review_fixes.md)；[CHECKLIST_p017_p016_review_fixes.md](CHECKLIST_p017_p016_review_fixes.md)
> **代码证据时点**: HEAD `4a34c49`（E1 2026-11-10）
> **状态**: Step 3 完稿 + Step 4 Review 通过（§7）

---

## 1. 目标与边界

**目标**：消除 RULE-5 复审 E4 的四项 P3——文档口径滞后（F-R5-P016-1）、占位残留（F-R5-P016-2）、生成物级联改名（F-R5-P016-3）、验收计数失实（F-R5-P016-4）。

**不覆盖（职责外）**：`MANUAL_MARKERS` 判据的生成态指纹化重构；U-P015-1 / U-P016-1 的任何语义定义。

**能力边界**：T-4 时点原始门禁读数无法回溯（RESEARCH §5.2 M-A 已声明为「未保全」）。

---

## 2. 设计决策（D1-D4）

| # | 决策 | 被拒方案 | 拒绝理由 | 代价 |
|---|------|----------|----------|------|
| **D1** | PROGRESS §3.17.1 终态行**只追加口径注**，原文「29 项断言」保留 | N-B 改写数字 / N-C 不动 | 改写抹掉 P-015 时点真实读数（冻结记录纪律）；不动则跨批索引继续传播错误口径 | PROGRESS 该行变长（两段口径并存，需读注） |
| **D2** | IMPL_p015 §8.5 回填为**读数表 + 出口指针 + 「T-4 原始读数未保全」声明** | M-B 删除小节 / M-C 保留占位 | 删除丢失缺口可见性；保留占位即本批要修的缺陷形态 | §8.5 的读数严格说来自 Step 10 时点（已标注，不冒称 T-4） |
| **D3** | `_resolve_report_target` 增**生成物命名空间守卫**：`stem` 以 `.generated` 结尾 ⇒ 原地重写 | G-B 占位指纹反转 / G-C 仅文档 | 指纹反转改变三条保护路径语义、需重验；仅文档不消除级联产物 | `.generated.*` 归生成器所有，人工策展该文件会被覆盖（写入 DESIGN §5 命名契约） |
| **D4** | CHECKLIST_p016 E-1 实测列**更正为 12 文件并加 P-017 注**；B-3 补「两分支」精确表述 | C-B 静默改数 / C-C 不动 | 静默改数丢可追溯性；不动削弱纪律面验收可信度 | 冻结文档被追加注（同 B-4 已有先例） |

---

## 3. 不变量（I1-I5，本批自证）

| ID | 不变量 | 形态 |
|----|--------|------|
| **I1** | **恒等式结论不变**：五 case 全跑仍 `28 断言（失败 0）+ 豁免 1`，exit 0 | 全链复放 |
| **I2** | **保护三路径语义不变**：策展版（含标记）→ 改名；目标不存在 → 原地；生成物 → 原地（本批新增，不再级联） | 三探针 |
| **I3** | **占位残留归零**：`docs/` 扫描无真实占位残留（仅 RULE-1 合法占位与历史引用） | 扫描读数 |
| **I4** | **冻结读数不改数值**：PROGRESS §3.17.1 原句逐字保留，仅追加注 | 逐字 diff |
| **I5** | **修复可追溯**：每处改动带 `F-R5-P016-N` / `P-017` 标记 | 文本检索 |

---

## 4. 生成物命名空间规格（D3）

```python
GENERATED_SUFFIX = ".generated"

def _resolve_report_target(path: Path) -> Path:
    if not path.exists():
        return path                                    # 分支 1：不存在 → 原地
    if path.stem.endswith(GENERATED_SUFFIX):
        return path                                    # 分支 2：生成物 → 原地重写（不级联）
    text = path.read_text(encoding="utf-8")
    if any(marker in text for marker in MANUAL_MARKERS):
        return path.with_name(f"{path.stem}{GENERATED_SUFFIX}{path.suffix}")  # 分支 3：策展版 → 改名
    return path                                        # 分支 4：存在且无标记 → 原地
```

**命名契约（本批新增声明）**：`<stem>.generated<suffix>` 为**生成器独占命名空间**——该路径内容随时可被重写；人工策展须合并回主文件 `<stem><suffix>`，不得直接编辑生成物。

分支可达性（对 F-R5-P016-3 的 B-3 精确化）：
- 分支 1：临时路径 / 首次生成（P-016 B-3 实际覆盖的形态）
- 分支 2：生成物再复放（本批新增守卫，P-016 时为级联）
- 分支 3：入库策展版再复放（P-016 B-1/B-2）
- 分支 4：存在但无人工标记的外部文件（P-017 探针 D 补覆盖）

---

## 5. 占位回填规格（D2）

IMPL_p015 §8.5 正文替换为：

| 项 | 读数 | 出口 |
|----|------|------|
| `pytest tests` | `635 passed` | CHECKLIST_p015 E-2 |
| `black --check scripts/external_benchmark/` | `5 files would be left unchanged` | CHECKLIST_p015 E-3 |
| 主环境 pip list | pandas 2.2.3 / numba 0.65.1，无 vectorbt | CHECKLIST_p015 E-1 / PROGRESS §3.17.1 |

并附「**P-017 说明**：T-4 时点（P-015 Step 9）的原始门禁读数未单独保全，上表为同批终态口径的读数出口指向，不冒称 T-4 时点证据。」

---

## 6. 文档更正规格（D1 / D4）

| 文件 | 位置 | 改动形态 |
|------|------|----------|
| PROGRESS.md | §3.17.1 终态行 | 原句保留 + 追加「（P-017 口径更正：含 B5 恒真豁免 1 项；P-016 D1 后口径 = 28 断言 + 1 豁免登记）」 |
| CHECKLIST_p016 | E-1 实测列 | 「docs/（6 文件）」→「`4a1cdb4` = scripts 2 + docs 9 + CHANGELOG 1（12 文件）」，附 P-017 更正注 |
| CHECKLIST_p016 | B-3 实测列 | 补「分支 1 覆盖；分支 4 由 P-017 探针 D 覆盖」 |

---

## 7. Step 4 Review（设计文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 设计基于已验证的调研结论（四项决策逐条对应 RESEARCH §5 推荐方案 + 被拒方案理由）
- [x] 无未经验证的假设（分支可达性由 RESEARCH §4 红读数 A 与 P-016 探针记录支撑；`.generated` 命名域为本批显式声明的新契约，非既有事实）
- [x] 无论证驱动的归因扭曲：四项独立成因（口径冻结 / 占位未回填 / 判据自指 / 计数失实），未合并为单因
- [x] 替代方案已列并被否决（N-B / N-C / M-B / M-C / G-B / G-C / C-B / C-C 八项）
- [x] 职责边界清晰（§1 区分职责外与能力边界）

**Step 4 Review 结论：通过**。
