---
name: aichain-delivery
description: 阶段交付与发布契约——按五阶段判据逐项判定通过/未通过，未过即阻塞；发布时保持展示层中立。用于「这一阶段能不能进下一阶段」「能不能发布这一版」。
---

# `aichain-delivery` —— 发布与阶段交付

> **权威出处**
> - 名称与职责：`00_交付施工图 §3.3`（`skills/aichain-delivery`）
> - 五阶段路线 + 可测通过判据 + 顺序锁定：`registry/delivery.yaml`（出处 `Ch11 §A.4`）
> - 阶段判据守卫：`scripts/delivery/stage_gate.py`（出处 `Ch11 §B`）
> - 模块 I/O 契约：`Ch9 §3.5`（⑥ 发布 行）
> - 展示层中立：`Ch2 §B.2 P-10` / `Ch3 §D.1`

---

## 1. 五阶段与门禁（纪律 12：未过即阻塞）

```
① prep ─▶ ② nvidia_sample ─▶ ③ core_chain ─▶ ④ daily_run ─▶ ⑤ expansion
```

| 阶段 | 通过判据（浓缩） |
|---|---|
| ① `prep` | 四类交付物齐备 + 「已确认规则 vs 建议实现方式」**有显式区分** + 口径字段 `tbd` 占位 |
| ② `nvidia_sample` | **六步判断链完整**（Ch1 五问 + Ch10 六结果）+ 证据可定位 + 推导可复查 + 满足 `Ch4 §G` 深度 |
| ③ `core_chain` | 多公司传导跑通（`Ch7 §C.7`）+ **T01–T14 全过**（`10/01 §2.1`）+ 图谱/提问任务可追溯 |
| ④ `daily_run` | 时点可核 + 覆盖可核 + 任务状态可核 + **降级保留上次有效结果** |
| ⑤ `expansion` | 研究标准一致（`Ch4 §G`）+ 投资结果可核验 + 复盘 **append-only** |

★ **T01–T14 的唯一权威表 = `10/01 §2.1`**（施工图 §7 `N-01` 指出 `10/02 §I.2` 指向错误）。
**任一 ❌ 即阶段③ 整体不通过。** T 表是**门**，不是参考。

★ **阶段未过 → 不出该阶段交付物，不得静默跳过**。
`stage_gate.py` 对未到达的阶段返回 `passed=False`（**绝不返回 True 冒充通过**）。

## 2. 阶段① 的四类交付物

声明在 `registry/prep_deliverables.yaml`，含：

- 4 类交付物（每项带 `layer`）
- **17 条 `confirmed_rules`**（`cr01`–`cr17`，每条带 `design_anchor` / `implementation_carrier` / `layer`）
- **7 条 `implementation_proposals`**（`ip01`–`ip07`）

★ 通过判据的实质是**两层显式区分**：`confirmed_rule`（已确认规则，改它需要需求方）
与 `implementation_proposal`（实现方建议，改它实现方即可）。两者**混在一层**即不通过。

## 3. ⑥ 发布 I/O 契约（`Ch9 §3.5` 逐字）

| 输入 | 输出 | 幂等键 | 失败处理 |
|---|---|---|---|
| recommendations、views | `views/*` + `snapshots/*` | (`view_target`, `source_version`) | 渲染失败 → **保持旧视图，不发布半成品** |

## 4. 展示层中立（不可协商）

| 禁止 | 依据 |
|---|---|
| 买入置顶（`default_sort[0].field ∈ {action, recommendation, signal}`） | P-10 |
| 紧迫色 / 涨跌色隐性引导（`urgency_color` / `red_green_bias`） | P-10 |
| 默认折叠反证与缺口（`evidence_panel.collapsed_default`） | P-10 |
| **未完成研究渲染为"中性 / 无投资机会"** | `Ch3 §N3.2-05` |

★ **待判断 ≠ 未完成研究**：`pending` 可以展示；`position_listed`（尚未研究）
**不得**渲染成中性。守卫：`scripts/views/neutrality_check.py`（真跑拦截）。

## 5. 快照与分享

- 快照必须带**资料日期与版本**（不得让读者以为是最新）
- 三层权限：present_files + 快照 + 腾讯文档 + 白名单
- `J8` 脱敏清单**待法务口径** → 清单未到之前该处保留 `tbd`（`§十二 N-04`），
  **不要自定合规边界**

## 6. 交付前 10 问（自检，任一"否"即未完成）

1. 每个模块都能说出**谁调用它**吗？
2. `facts/` 每个 JSONL 都能说出**谁读它**吗？
3. 每条守卫**注入违例后真的 exit 非零**吗？（**跑过**，不是"应该会"）
4. 有没有空函数体 / `NotImplementedError` / 假数据？
5. `tbd` 的地方**代码路径完整、值一改就生效**吗？
6. 决策/排序函数里有没有 `weight` / `score` / `vote`？
7. 参数有没有被读进 `scripts/decision/**` 或 `scripts/graph/**`？
8. 关联公司的结论有没有混进 `RecommendationInput`？
9. 跨文件引用用的是**节号锚点**吗？
10. 报告里每个"完成"都**附了真实命令输出与退出码**吗？

## 7. 独立验收（**必须换人**）

实现方**不得自证完成**。每阶段末新开会话，以独立审计员身份：
先读原始任务与验收标准（DoD + 对应 `02_实现方案.md` 节）**再**读代码；
逐条判 PASS / FAIL / UNKNOWN / HUMAN_REVIEW；做三项探测
（write-read-reload / 让缺失层响亮失败 / 接线体检）；
逐项对照 `施工图 §8` 的 12 条纪律。

**铁律**：不改源码、不把缺失证据记为 PASS、不给部分分。

## 8. 本流程**不得**做的事

- ❌ 阶段未过就出该阶段交付物
- ❌ 把 `pending` / `boundary_unresolved` 渲染成中性或无机会
- ❌ 发布半成品视图
- ❌ 把"日报生成了 / 页面能打开 / 问答听起来合理"当作研究完成的充分条件
- ❌ 实现方自证完成
