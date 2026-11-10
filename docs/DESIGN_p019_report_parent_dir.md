# DESIGN：P-019 报告写入父目录缺失修正

> **批次**: P-019 · T1
> **上游**: [RESEARCH_p019_report_parent_dir.md](RESEARCH_p019_report_parent_dir.md)（§5 方案矩阵 M-A）
> **下游**: [IMPL_p019_report_parent_dir.md](IMPL_p019_report_parent_dir.md)；[CHECKLIST_p019_report_parent_dir.md](CHECKLIST_p019_report_parent_dir.md)
> **代码证据时点**: HEAD `6149cc6`（E1 2026-11-10）
> **状态**: Step 3 完稿 + Step 4 Review 通过（§5）

---

## 1. 目标与边界

**目标**：`--report` 在父目录缺失时自动创建并写入；更正 P-018 探针 ⑥ 的覆盖声明并补真实读数。

**不覆盖**：权限类失败（`PermissionError` 不吞）；`endswith` 大小写敏感观察项；U-P015-1 / U-P016-1。

---

## 2. 设计决策（D1-D2）

| # | 决策 | 被拒方案 | 拒绝理由 | 代价 |
|---|------|----------|----------|------|
| **D1** | `write_report` 在 `write_text` 前插入 `target.parent.mkdir(parents=True, exist_ok=True)` | M-B 友好异常 / M-C 解析阶段 mkdir / M-D 仅改文档 | 异常方案仍是失败路径；解析函数混入 I/O 破坏纯判定；仅改文档不修行为 | 无写权限时仍抛 `PermissionError`（本批边界已声明） |
| **D2** | P-018 探针 ⑥ 记录**保留原句 + 追加 P-019 更正注**，并补「父目录不存在」真探针 | 静默改写原句 | 抹掉误判痕迹（同 F-R5-P017-2 处置原则） | 冻结文档追加注 |

---

## 3. 不变量（I1-I4，本批自证）

| ID | 不变量 | 形态 |
|----|--------|------|
| **I1** | 父目录存在时行为不变：四分支 + 无扩展名守卫读数与 P-018 一致 | 回归探针 |
| **I2** | 父目录不存在（含多级）→ 自动创建并写入，exit 0 | 新探针 |
| **I3** | 全链 `28 断言（失败 0）+ 豁免 1`，exit 0 | 全链复放 |
| **I4** | `:254/:268/:272` 锚点零位移（P-017/P-018 文档引用仍有效） | 逐行断言 |

---

## 4. 实现规格（D1）

```python
    target = _resolve_report_target(path)
    if target != path:
        print(...)
    target.parent.mkdir(parents=True, exist_ok=True)   # 新增（P-019 D1 / F-R5-P018-1）
    target.write_text("\n".join(lines), encoding="utf-8")
```

- 位置：`write_report` 内、`write_text` 前一行（`:323` 之前），位于 `_resolve_report_target` 定义（`:257-273`）之后 ⇒ **守卫锚点零位移**。
- 幂等：`exist_ok=True`；多级：`parents=True`。
- 不吞异常：`PermissionError` / `OSError` 照常抛出。

## 5. Step 4 Review（设计文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 设计基于已验证的调研结论（D1↔M-A，被拒方案理由来自 RESEARCH §5）
- [x] 无未经验证的假设（`mkdir(parents=True, exist_ok=True)` 语义为 stdlib 文档级事实；零位移由行号位置推导，Step 9 实测确认）
- [x] 无论证驱动的归因扭曲：行为修复与取证更正分别对应 D1/D2，未合并
- [x] 替代方案已列并被否决（M-B / M-C / M-D 三项）
- [x] 职责边界清晰（§1 区分不覆盖与能力边界）

**Step 4 Review 结论：通过**。
