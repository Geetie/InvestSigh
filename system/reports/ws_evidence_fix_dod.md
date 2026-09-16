# ws/evidence-fix · 证据层收口 Definition of Done（先写后做）

> **工作树**：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-evidence-fix` ｜ **分支**：`ws/evidence-fix` ｜ **基点**：`main = 960634d`
> **只改**：`system/scripts/evidence/**` · `system/tests/evidence/**` · **★`system/schema/models.py`（本次由需求方授权，仅限 T-11/T-12 两处契约变更）** + 生成的 `system/schema/jsonschema/facts.schema.json` · 本文件 + `ws_evidence_fix_report.md`
> **写 DoD 依据**：`00_开发Agent开工提示词 §5.1`（**未写出的标准 = 未满足的标准**）；本文件在写码前落盘。

**本单范围**：收口**批次 10 独立审计**对 Ch6 证据层的全部发现 + 执行**需求方已授权的两处契约变更**（T-11 / T-12）。
逐条对应审计发现：`G3`（CV3 覆盖目标集，违 `R-06` ①④ + 判据失效）、`G5`（`max_model_calls: 0` 静默当无上限）、`G6`（YAML 六进制陷阱）、`T01` 系统层缺口（`origin_claim_id` 无产出方）。

---

## 交付物清单

| # | 文件 | 性质 |
|---|---|---|
| 1 | `system/schema/models.py` | **改**（★授权）：`ClaimPropagation.kind`（T-11）+ `Claim.independent_evidence_count`（T-12） |
| 2 | `system/schema/jsonschema/facts.schema.json` | **重建**（`python -m schema.build_jsonschema`；由 `schema_sync_guard` 强制） |
| 3 | `system/scripts/evidence/independence.py` | **改**：⑥ `origin_claim_id` **产出方**（去重步骤落链）+ 更新已过期的"已知缺口"说明 |
| 4 | `system/scripts/evidence/budget_gate.py` | **改**：④ `max_model_calls: 0` / `max_searches: 0` **不静默**（`None`=未设上限，`0`=上限为 0） |
| 5 | `system/tests/evidence/test_contract_changes.py` | **新增**：T-11 / T-12 契约 + **旧行向后兼容** + `schema_sync_guard` |
| 6 | `system/tests/evidence/test_origin_attribution.py` | **新增**：⑥ (a)(b)(c) 三情形 |
| 7 | `system/tests/evidence/test_budget_gate.py` | **改**：④ 加正反用例（`0` 触限 / `None` 未设上限） |
| 8 | `system/reports/ws_evidence_fix_dod.md` | 本文件（**先写**） |
| 9 | `system/reports/ws_evidence_fix_report.md` | 收工四段式报告（`§5.2`） |

**复用声明（不重造，`G-06` 唯一真源）**：本单**新增 0 条**指纹 / 定位 / 状态机 / 写库路径 —— 全部**调用**既有原语
（`scripts/graph/fingerprint.py::event_fingerprint`、`schema/store.py::append_records` / `as_of` / `read_records`）。

---

## 逐条可测 AC（触发方式 + 可观察结果）

### ① T-11 · 人工去重覆盖的承载（`Ch6 §C.3`；已授权契约变更）

- **AC-T11-1（正向）**：`ClaimPropagation` 新增 `kind` 字段（`StrEnum`），含取值 `manual_alias_override`（人工别名覆盖）
  → 构造 `kind="manual_alias_override"` + 人工载荷（`is_independent` / `reason` / `operator` / `at`）的传播行，经 `append_records` 落库并读回 **不报错**；`Ch6 §C.3` 的 `claim_alias` 四要素可承载。
- **AC-T11-2（★向后兼容，硬约束）**：**旧行仍然合法** —— 既有 `claim_propagation` 行（**无 `kind` 字段**）`ClaimPropagation.model_validate(...)` **必须成功**，且 `kind` 取默认值。
  依据：`Ch9 §3.4.2` 追加式不可变（不得让既有行失效）。
- **AC-T11-3（★不新增第 19 个 JSONL）**：`JSONL_MODELS` 仍 **== 18**（`assert` 未触发）；`Ch9 §3.3.3`。
- **AC-T11-4（生成物一致）**：`python -m schema.build_jsonschema` 后 `schema_sync_guard.py` **绿**（生成物 == `models.py` 现算）。

### ② T-12 · 独立佐证数落表（`Ch6 §C.2`/`§C.4`；已授权契约变更）

- **AC-T12-1（正向）**：`Claim` 新增**可选**字段 `independent_evidence_count: int | None = None` →
  显式赋值可落库读回；`Ch6 §B.4` 口径（**基数**非权重）。
- **AC-T12-2（★向后兼容，硬约束）**：真仓库现有 **5 行 `claims`（真实数据）** 逐行 `Claim.model_validate` **必须成功**、字段默认 `None`。
- **AC-T12-3（生成物一致）**：同 AC-T11-4。

### ④ G5 · `max_model_calls: 0` 不得静默（`Ch6 §D.5` / `§6.1`）

- **AC-G5-1（正向：`0` = 上限为 0）**：`compute_limit == 0` 时，`usage.model_calls_used == 0` 即 **`exhausted=True`**、
  `COMPUTE_CLASS ∈ binding`（"不允许任何调用"，**不静默当无上限**）。`max_searches: 0` 同理。
- **AC-G5-2（反向对照：`None` = 未设上限）**：`compute_limit is None` 时，仅配 `research_cap` → 未到限 → **`exhausted=False`**（不得因 `None` 误报）。
- **AC-G5-3**：`ratios` 对 `limit == 0` 不得除零 / 不得为 0（可判定，不崩）。

### ⑥ `origin_claim_id` 的产出方（`T01` 系统层缺口；`Ch6 §C.2` 步骤③）

- **AC-ORIG-1（(a) 现实形态成立）**：去重步骤对"根主张在场 + 10 篇同根同指纹但**未标** `origin_claim_id`"的转述**产出** `origin_claim_id`（追加新版本，链到根）
  → 再判定 → `independent_evidence_count[根] == 1`（**系统层**已守住，非仅判定层）。
- **AC-ORIG-2（(b) 证不欠报）**：3 条**真独立**（无共同上游、且根来源未以主张形式在场）→ **不产出** `origin_claim_id`，佐证数 **== 3**。
- **AC-ORIG-3（(c) 如实登记）**：10 篇同指纹**但无 `origin_claim_id`**、**且根来源主张不在场** → 如实登记现状（若仍算 10，写清"这是判定层产物、残余未闭合"）。
- **AC-ORIG-4（幂等 + 不覆盖历史）**：重复跑 → 不重复追加版本（已有 `origin_claim_id` 者跳过）；真源**只追加、不改既有行**（`Ch9 §3.4.2`）。

### ⑦ `G-B10-07` · `classify_and_record` 真幂等（主理人实测 5→10→12 的收口）

- **AC-IDEM-1（幂等：复跑 0 新增）**：接线场景（`run_daily` → `classify_and_record`）**连跑两次** → **本模块 `run#2` 增量 == 0**（`claims` 与 `claim_propagation` 皆 0），且不重复追加版本。
- **AC-IDEM-2（★反向对照，`G-05` 成对，证非"一律不写"）**：造一条**真正需要新增**的场景（此前从未记 `count` 的全新独立主张）→ 该次**必须新增**（写入其 `count`）。
- **AC-IDEM-3（增量可解释）**：`run#1 = +5` 须**逐行可解释**（`claim_id` / `version_kind` / `recorded_seq`）：= `1`（step 1 既有重复版）+ `4`（本模块首写），**不存在"多算的第 5 个根"**。
- **AC-IDEM-4（根因归属如实）**：全链路残余 `+1`（若有）**只**来自 step 1 的重复版（`guard/executor` 缺 `(source_id, quote_hash)` 行幂等键），**由既有 `ws/idempotency` 修复** —— 本单**只读**验证"叠加后 `run#2` 两文件皆 0"，**不改其代码、不做分支操作**。

### 硬约束与纪律

- **AC-X1 错误路径（≥1）**：⑥ 产出方对**成环**的 `origin_claim_id` **响亮失败**（`IndependenceInputError`）；④ 非法输入不静默。
- **AC-X2 边界（≥1）**：空 `claims` → 真空成立（`G-03` note，不崩）；`limit == 0` 边界（AC-G5-1）。
- **AC-X3 不污染真源**：写入型探测**一律在夹具副本**；真仓库 `facts/` 计数保持 **5 claims / 3 edges / 2 companies / 3 tasks / 1 baseline / 1 recommendation**。
- **AC-X4 不跑全量**：只跑 `tests/evidence`（`V-08` 宿主删除配额）；单命令超时 ≤ 60s。
- **AC-X5 设计对齐**：逐条对应 `Ch6 §C.2`/`§C.3`/`§C.4`/`§B.4`/`§D.5`/`§F.3`，节号锚点（`R-01`）。

---

## 关键设计决策（预先声明 + 依据节号）

| # | 决策 | 依据 |
|---|---|---|
| D1 | **不新增第 19 个 JSONL**：人工别名覆盖**并入** `claim_propagation`，以其 `kind` 取值承载 | `Ch9 §3.3.3`（18 个不得增删改名）；需求方 2026-09-16 裁定 |
| D2 | `kind` 为**封闭 `StrEnum`**，默认 `restatement`（旧行无该字段 → 取默认 ⇒ 合法）；新增 `manual_alias_override` | `Ch6 §C.3`；纪律 7（枚举小写下划线） |
| D3 | `independent_evidence_count` 落为 `Claim` **可选字段**（`None` = 未计算），由去重步骤写入 | `Ch6 §C.2` 步骤⑤ / `§C.4`；`§B.4`（基数非权重） |
| D4 | ④ 语义：`None` = **未设上限**（走 `research_cap`）；`0` = **上限为 0**（不允许调用，`used>=0` 即到限）—— 二者**不得混同** | `Ch6 §D.5`；`00_开发Agent开工提示词 §6.1`（边界必须显式） |
| D5 | ⑥ 产出方**只在根来源主张在场时**才落链（`source_id == root_source_id`）；根不在场 → **不臆断**（残留如实登记） | `Ch6 §C.1`（回溯到**最早主张**）/`§C.2` 步骤③/`§F.3`（认定边界）；`R-04`（歧义上报，不自行裁决） |
| D6 | 落链 = **追加新版本行**（不改历史），经 `append_records` 唯一写入口 | `Ch9 §3.4.2`（追加式不可变） |
| D7 | 指纹 **调用** `fingerprint.event_fingerprint`，不重造 | `G-06`；`Ch9 §3.4.7` |

---

## 已知缺口 / 不做清单（如实登记）

1. **③ G3（CV3 覆盖目标集）与 ⑤ G6（YAML 时刻陷阱）的代码落点均在 `scripts/daily/**`（`coverage.py` / `schedule.py` + `tests/daily/`），
   超出本单「只改 `scripts/evidence/**`」的授权范围，且 `ws/daily-fix` 工作树可能在动同一域。**
   → 开工即**上报主理人**请求裁决（A 改 / B 跳过）。若未获授权：③⑤ **不在本单交付**，只在报告登记移交与理由；**不擅自越界**。
2. **⑥ 的 (c) 现形态**：`origin_claim_id` 全缺 + 根来源主张不在场时，**算法无法区分"真独立"与"未标链的转述"**（二者在 claim 字段上同构）
   → 产出方**不臆断**；该情形仍可能计为 N 份。**此为判定层产物，残余未闭合**，如实登记（不美化）。
3. **`independent_evidence_count` 由谁写入**：本单在 `scripts/evidence/independence.py` 提供写入路径（落链/计数）；
   **真实采集写 claim 的调用方是否接线**不在本单范围（如必须改采集层，报告主理人）。
4. **`rules/budget.yaml` 不存在**（`rules/` 0444）—— 本单只改**边界语义**（`0` vs `None`），不改参数来源。

---

> **说明**：AC 均含**触发方式 + 可观察结果**；**≥1 错误路径（AC-X1）** 与 **≥1 边界（AC-X2）** 已含。
