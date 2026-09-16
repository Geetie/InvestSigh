# DoD · 阶段④ `daily_run` —— 覆盖可核 + 降级保留 + 幂等 + `p07` 调度

> **工作流**：`ws-ch8-daily` ｜ **分支**：`ws/ch8-daily` ｜ **基点**：`main = d4f3aed`
> **范围（硬边界）**：仅新增 `system/scripts/daily/**` 与 `system/tests/daily/**`，并写本报告。
> **不改**：`scripts/orchestrate/**`、`scripts/ops/**`、`scripts/checks/**`、`scripts/delivery/**`、
> `scripts/guard/**`、`scripts/graph/**`、`system/schema/**`、`system/rules/**`、`system/config/**`、
> `system/tests/conftest.py`、`system/CONVENTIONS.md`、设计区、`registry/**`。
> **未写出的标准 = 未满足的标准**（本文件即验收标准；缺一条即本 DoD 不合规）。

---

## 0. 任务一句话

实现阶段④「每日持续研究」的第一硬判据 **`coverage_verifiable`（覆盖可核）**，
并补齐 **故障降级（保留上次有效结果）**、**同日重跑幂等** 与 **`p07` 配置化调度**，
全部**复用**既有组件（`pipeline.RunResult` / `graph.fingerprint` / `tasks.gap_to_task` /
`config.freeze.get_param` / `schema.store`），**不重造**（`G-06` 唯一真源、纪律 11）。

**当前状态（据 `stage_gate`）**：阶段④ `BLOCKED`，其中 `daily_run.criteria_not_implemented: 1`
—— 即 `coverage_verifiable` 未实现。本流把它做成可自动化判据。

---

## 1. 交付物清单

| # | 落位 | 作用 |
|---|---|---|
| 1 | `system/scripts/daily/__init__.py` | 包入口（PEP 562 惰性导入，`P-03`） |
| 2 | `system/scripts/daily/coverage.py` | **★ 第一交付物**：`coverage_verifiable` 判据（`check(root) -> CheckReport`） |
| 3 | `system/scripts/daily/degrade.py` | 故障降级：**保留上次有效结果** + 降级**可见**（复用 `RunResult.degraded/blocked/gaps`） |
| 4 | `system/scripts/daily/idempotency.py` | 同日重跑幂等（复用 `event_fingerprint` / 建议键 / `task` 幂等键） |
| 5 | `system/scripts/daily/schedule.py` | `p07` 配置化 rrule（**走 `get_param`**；缺文件/`tbd` 响亮） |
| 6 | `system/scripts/daily/run.py` | 每日运行**薄封装**（复用 `Pipeline.run_daily`） |
| 7 | `system/tests/daily/test_coverage_verifiable.py` | `coverage_verifiable` 正反两向 |
| 8 | `system/tests/daily/test_degrade_keeps_last_valid.py` | 降级保留 + 不置空 + 不标最新 |
| 9 | `system/tests/daily/test_idempotency.py` | 同日重跑不重复事件/建议 |
| 10 | `system/tests/daily/test_schedule_p07.py` | `p07` 走 `get_param` + 不写死时刻 + 缺文件响亮 |
| 11 | `system/tests/daily/test_daily_run.py` | 端到端薄封装 + 反 KPI（无变化日 `signals_emitted == 0`） |
| 12 | `system/reports/ws_ch8_daily_dod.md`（本文件） | 开工前 DoD |
| 13 | `system/reports/ws_ch8_daily_report.md` | 四段式验证报告 |

---

## 2. 逐条可测 AC

### AC-1 `coverage_verifiable` 判据定义（★ 第一交付物）

**判据 = 下列四条全部成立（0 违例）**；退出码 `0` 通过 / `1` 违例 / `2` 输入异常（`Ch2 §B.3` 纪律 2）。

输入真源：`facts/industry_nodes.jsonl`、`facts/business_positions.jsonl`、`facts/companies.jsonl`、
`registry/acceptance_input_set.yaml`（**若存在**）。读写一律走 `schema.store.read_records`。

| 子判据 | 语义 | 设计锚点 | 违例条件（可判定） |
|---|---|---|---|
| **CV1 三份量可分离** | 覆盖 / 深研 / 频率三分量**分别可表达** | `Ch3 §N3.2-03` | 任一条 `business_positions` 记录缺 `position_listed`（覆盖）/ `research_depth`（深研）/ `scan_frequency`（频率，非空）之一 |
| **CV2 深度四态合法** | `research_depth ∈ {position_listed, relations_verified, baseline_done, tracking}`（**可回退**） | `Ch3 §N3.2-04` | `companies`（同 `company_id` 取 `recorded_seq` 最大者）或 `business_positions` 任一条深度**不在四态内**（含缺失/自由串） |
| **CV3 无静默遗漏** | 覆盖**对齐验收输入**（`acceptance_input_set` 首批对象）逐对象可读出深度 | `00_交付施工图 §2 阶段④` / `10/01 §N10.1-06` | 目标集为验收输入时：某目标对象在覆盖台账（`companies` 深度 ∪ `business_positions.company_id`）中**不存在** |
| **CV4 真空不得判过** | 无被检对象 ≠ 已验证 | `CONVENTIONS.md §二 G-03` | 覆盖目标集为空 |

**覆盖目标集 `T` 取法（不静默）**：
1. `registry/acceptance_input_set.yaml` 存在且含 `first_list` / `first_list_version` / `first_list_members`（其一为**列表**）→ `T = 该列表`（对齐验收输入）；
2. 否则 → `T = facts/companies.jsonl` 的研究对象集合，并**显式记 note `ACCEPTANCE_INPUT_ABSENT`**（**不静默兜底**）。

**显式 note（R-03；空样本不得当已验证）**：
- `NO_BUSINESS_POSITION_RECORDS`：无逐节点覆盖记录 → "三份量可分离"一项真空，**不计为已核**；
- `INDUSTRY_NODES_WITHOUT_COVERAGE`：在册节点无 `business_positions` 覆盖记录数（**可见但不判违例**，理由见 §4）。

**正反两向可测**：造达标数据 → `passed == True`（0 违例）；分别注入 CV1/CV2/CV3/CV4 违例 → 各命中对应规则（`AC-1a..AC-1e`）。

### AC-2 故障降级：保留上次有效结果（`Ch8 §E`）
- 降级（`RunResult.degraded` 或 `blocked` 为真）时：
  - `last_valid_result_ref` 指向**上一次成功**运行的 `check_id`（若无 → `None`，**如实为空**，不臆造）；
  - 降级**可见**（`Ch8 §E` "不得静默"）：记 `parent_context.degraded=true` + `gaps`（来自 `RunResult.gaps`）；
  - 走**追加式**真源（`schema.store.append_records`），**不覆盖**任何既有行；
  - **幂等**：同一 `(run_date, scope)` 只落一条降级标记（键 `degrade::<date>::<scope>`）。
- **错误路径 AC-2e**：`assert_no_null_overwrite(old, new)` 在 `new` 把 `old` 的非空字段置空（`null/""/[]/{}`）时**抛** `NullOverwriteError`（`Ch8 §E.4` / N8.4-06）。
- **边界 AC-2f**：`old` 字段本就为空（`None`）时，`new` 为空**不**算覆盖违例（不得把"本来就是空"判成置空）。

### AC-3 幂等与增量不变量（`Ch8 §F`）
- **AC-3a**：同一份 `events` 记录重复入队 → 经 `append_deduped` 后 `events` 行数**不增**（`event_fingerprint`，`Ch9 §3.4.7`）；
- **AC-3b**：同一 `(security_id, start_date, version)` 建议重复入队 → `recommendations` 行数**不增**（`Ch9 §3.3.4`）；
- **AC-3c**：`check_daily_idempotency` 对**已存在重复键**的真源报违例（正反两向）；
- **AC-3d**：连跑 `run_daily` 三次（同日）→ `events` / `recommendations` 行数**前后相等**（`wc -l` 对比）。

### AC-4 调度：`p07` 配置化（`Ch8 §D` / `Ch9 §3.10 J3`）
- **AC-4a**：运行时刻/频率/时区**一律**经 `config.freeze.get_param("p07", root)` 读取 → 改 `rules/freeze.yaml::p07` 的值，`resolve_schedule()` 的对应字段随之变化（证明**未写死**）；
- **AC-4b**：`schedule.py` 源码内**不存在**硬编码时刻（`HH:MM`）/时区名/频率字面量（静态断言 + `grep` 证据）；
- **AC-4c（错误路径）**：删 `rules/schedule.yaml` → `resolve_schedule()` **响亮失败**（`ScheduleFileMissingError`），**不静默兜底**；
- **AC-4d（错误路径）**：`time_value == "tbd"` → `to_rrule()` **响亮失败**（`ScheduleUnresolvedError`），**不得写死一个时刻**。

### AC-5 反 KPI（`Ch1 §D.3`）
- **AC-5a**：无变化日（`judgment_change` 全 False）→ `RunResult.signals_emitted == 0`，且**不**发布（`changed == False`）；
- **AC-5b**：`run_daily`（本包薄封装）**如实回传** `changed` / `signals_emitted` / `degraded` / `blocked` / `gaps`，**不做乐观改写**。

### AC-6 复用证据（`G-06` 唯一真源 / 纪律 11）
- 状态机复用 `scripts.orchestrate.pipeline.Pipeline.run_daily`（本包 `run.py` 仅**薄封装**，不重写状态机）；
- 事件幂等键复用 `scripts.graph.fingerprint.fingerprint_of_event`；
- 任务幂等键复用 `scripts.tasks.gap_to_task.idempotency_key`；
- 参数读口复用 `config.freeze.get_param`；
- 真源读写复用 `schema.store.read_records` / `append_records`；
- **新增**的只有：覆盖判据、降级标记、幂等去重入口、调度解析 —— 均为**薄层**。

### AC-7 门禁与合规
- 不新增 `facts/` 的 JSONL（`Ch9 §3.3.3`：18 个不得增删改名）；
- `tests/daily/` 为**新目录** → `V-06` 会红（**预期**）；**需新增批次 `daily`**，由主理人统一加入 `verify.py`（本流**不改** `verify.py`）；
- 所有写入型探测在**副本**上做，**不污染**真仓库 `facts/`（现 5 claims / 3 edges / 3 tasks）。

---

## 3. 关键设计决策（**预先声明 + 依据节号**）

| # | 决策 | 依据 |
|---|---|---|
| D1 | `coverage_verifiable` = **三份量可分离 + 四态合法 + 对齐验收输入 + 非真空** 四条合取 | `Ch3 §N3.2-03/04` + `施工图 §2 阶段④`（`coverage_matches_acceptance_input`）+ `10/01 §N10.1-06` |
| D2 | `check(root) -> CheckReport` 作为判据入口 | 与 `scripts/trace/traceback.check`、`scripts/checks/*.check` 同构，便于 `stage_daily_run_passed` 复用（**接线方式见 §5**） |
| D3 | 降级**复用** `pipeline.RunResult` 的 `degraded/blocked/gaps` 语义，本流只做"保留上次有效 + 可见 + 幂等落一条标记" | `Ch8 §E`；`RunResult` 字段见 `pipeline.py` |
| D4 | 幂等键**复用**既有三类键（事件指纹 / 建议键 / 任务键） | `Ch8 §F.1` / `Ch9 §3.3.4 / §3.4.7` / `Ch1 §C.3` |
| D5 | 运行时刻/频率/时区**唯一真源 = `p07`**，经 `get_param` 读；`tbd` 即"不可解析"，**响亮失败** | `Ch9 §3.10 J3` / `Ch11 §D.2` / `rules/freeze.yaml::p07` |
| D6 | `rules/schedule.yaml` 缺文件 → **响亮失败**（默认），不得静默 | 需求口径；`config.rules.load_yaml` 缺文件即 `RuleFileMissingError` |
| D7 | 覆盖目标集缺 `acceptance_input_set` → **显式 note** 后退化为 `companies` | `R-03`（显式 note）/ `G-03`（空样本显式） |
| D8 | 建议幂等键用 `(security_id, start_date, version)` 表达 `Ch9 §3.3.4` 的 `(security_id, issued_at, version)` | 模型无 `issued_at`，`start_date` 为其落点（**登记为口径映射**，见 §4） |

---

## 4. 已知缺口 / 不做清单（**如实登记**）

| # | 事项 | 处理 |
|---|---|---|
| G-1 | **`coverage_verifiable` 尚未接进判据台账**（`stage_gate.py::stage_daily_run_passed` 内无 `criterion("daily_run","coverage_verifiable", v)`）。`scripts/delivery/**` **不在本流可改范围** | **报告对接方式**（§5），由主理人集成时加**一行**；本流不改 |
| G-2 | `industry_nodes`（44 节点）**无 `research_depth` 字段**；覆盖深度落在 `companies` / `business_positions`。故"在册节点无覆盖记录"**只记 note + 计数，不判违例**（节点↔公司映射由采集层给出，本层不臆造） | 记 note `INDUSTRY_NODES_WITHOUT_COVERAGE`；**登记为待明确项**（`R-04`） |
| G-3 | `registry/acceptance_input_set` 的**精确 schema 未在设计区定死** | 宽容读取 `first_list` / `first_list_version` / `first_list_members`（其一为列表即可）；否则 note + 退化。**登记为待明确项** |
| G-4 | `p07` 的 `suggested_value` **不含 `timezone` 值**（只有 `timezone_explicitly_recorded: true`） | 时区从 `rules/schedule.yaml::cadence.timezone`（`tbd`）读；故 `to_rrule` 在 `tbd` 时**响亮失败**，**不写死** |
| G-5 | 建议键 `issued_at` ↔ 模型 `start_date` 的映射 | 见 D8；**登记为口径映射**（不新增字段） |
| G-6 | `V-06`（新增测试目录必须有批次）**必红** —— `tests/daily/` 是新目录 | **预期**；报告"需新增批次 `daily` → `tests/daily/`"，**本流不改 `verify.py`** |
| G-7 | `V-08`（宿主删除配额）在本工作树 `CONVENTIONS.md` **实际不存在**（文件止于 `R-06`） | 如实登记；按任务口径**只跑 `tests/daily` 子集**，不跑全量 |
| G-8 | 本流**不**实现：三个阅读入口视图、`neutrality_check` 扩项、`trigger.yaml` 五类触发、`aichain-daily` Skill（超出本流范围） | 不做清单 |

---

## 5. 与既有判据台账的对接方式（**报主理人执行**，本流不改 `stage_gate.py` / `delivery.yaml`）

`registry/delivery.yaml`（设计真相源）已把 `daily_run.coverage_verifiable` 声明为 `automated`；
`stage_gate.py::bound_criteria()` 用 **AST 扫自身**校验"函数体内是否有字面量 `criterion(...)`"。
故集成时需在 `scripts/delivery/stage_gate.py::stage_daily_run_passed()` 内**加两行**：

```python
from scripts.daily.coverage import check as coverage_check

...
v += coverage_check(root).violations          # 真检查
criterion("daily_run", "coverage_verifiable", v)   # 台账绑定（字面量，供 AST 抽取）
```

加后 `daily_run.criteria_not_implemented` 由 `1 → 0`（其余三条已有绑定）。
**本流不改该文件**（越权），只提供可 `import` 的 `check(root) -> CheckReport` 入口。
