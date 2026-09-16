# 阶段④ `daily_run`（每日持续研究）· 交付报告

> 提交哈希：`df311271f6147fa08db647d75b15959f18f66399`（代码 + DoD；本报告为紧随其后的第二个提交）
> 分支：`ws/ch8-daily`　｜　基站：`main = d4f3aed`　｜　工作树：`.worktrees/ws-ch8-daily`
> 交付人：`ws-ch8-daily-engineer`　｜　DoD：`system/reports/ws_ch8_daily_dod.md`（**先写**）

本报告遵 `§5.2` 四段式：① 做了什么 → ② 怎么验证（逐条命令 + 原样输出 + 退出码，**正反两向**）→ ③ 结果 → ④ 如实登记的残余与不确定。

---

## ① 做了什么

**范围**：仅**新增**（未改动任何既有文件、未新增 `facts/` JSONL、未改 `rules/**`）：

| 文件 | 职责 | 设计锚点 |
|---|---|---|
| `system/scripts/daily/__init__.py` | 包 + PEP 562 惰性子模块 | `CONVENTIONS §三 P-03` |
| `system/scripts/daily/coverage.py` | ★ **`coverage_verifiable`（覆盖可核）判据** | `Ch3 §N3.2-03/04` · `施工图 §2 阶段④` · `10/01 §N10.1-06` · `G-03` |
| `system/scripts/daily/degrade.py` | 故障降级：**保留上次有效结果** + **降级可见** | `Ch8 §E` · `Ch9 N9.2-13` |
| `system/scripts/daily/idempotency.py` | 同日重跑**幂等**（事件/建议/任务键） | `Ch8 §F` · `Ch9 §3.3.4/§3.4.7` · `Ch1 §C.3` |
| `system/scripts/daily/schedule.py` | `p07` **配置化 rrule**（唯一读口） | `Ch8 §D` · `Ch9 §3.10 J3` · `Ch11 §D.2` |
| `system/scripts/daily/run.py` | 每日运行**薄封装**（复用 `Pipeline.run_daily`） | `Ch1 §D.1` · `Ch8 §D/§E/§F` |
| `system/tests/daily/*.py` | **37 用例**（正反两向 + 错误路径 + 边界） | — |
| `system/reports/ws_ch8_daily_dod.md` | DoD（先写） | — |

**`coverage_verifiable` 判据定义（可判定 + 穷尽，`R-06`）**——`passed` 当且仅当下列**四条同时成立**：

- **CV1 三份量可分离**：任一 `business_positions` 记录不得缺 `position_listed` / `research_depth` / `scan_frequency`；且 `position_listed` 须为**布尔可判定值**（非"maybe"式含糊）。→ `Ch3 §N3.2-03`
- **CV2 深度四态合法**：`companies`（同键取 `recorded_seq` 最大者）与 `business_positions` 的 `research_depth ∈ {position_listed, relations_verified, baseline_done, tracking}`（**可回退**、非单调）。→ `Ch3 §N3.2-04`
- **CV3 无静默遗漏**：覆盖目标集 `T` 中每个对象都在覆盖台账（`companies` 深度 ∪ `business_positions.company_id`）内。
- **CV4 非真空**：`T` 非空（空 → **不得**判"已覆盖"，`G-03`）。

`T` 取法**不静默**：① `registry/acceptance_input_set.yaml` 含列表形态首批对象 → 用之；② 否则退化为 `facts/companies.jsonl` 对象集合，并记 note `ACCEPTANCE_INPUT_ABSENT`。

**复用优先（`G-06` 唯一真源 / 纪律 11）**：不重造状态机、幂等键、真源读写、参数读口——全部**调用**既有公开入口（`schema.store` / `Pipeline.run_daily` / `fingerprint_of_event` / `gap_to_task.idempotency_key` / `config.freeze.get_param`）。

---

## ② 怎么验证（逐条命令 + 原样输出 + 退出码；正反两向）

### ②-1 `coverage_verifiable`：**正向（达标 → PASS）**

```
$ python system/scripts/daily/coverage.py <scratch: companies=[c1], positions=[(c1,n1)], acceptance=[c1]> --no-report
== coverage_verifiable ==
  scanned business_positions: 1
  scanned companies: 1
  scanned coverage_known: 1
  scanned coverage_target: 1
  scanned industry_nodes: 0
  scanned nodes_without_coverage_record: 0
  note: ACCEPTANCE_INPUT_OK：取自 first_list_version（1 项）
RESULT: PASS（0 violations）
EXIT = 0
```

### ②-2 `coverage_verifiable`：**反向（静默遗漏 → FAIL）**

```
$ python system/scripts/daily/coverage.py <scratch: companies=[c1], acceptance=[c1,c2]> --no-report
== coverage_verifiable ==
  scanned business_positions: 0
  scanned companies: 1
  scanned coverage_known: 1
  scanned coverage_target: 2
  scanned industry_nodes: 0
  scanned nodes_without_coverage_record: 0
  note: ACCEPTANCE_INPUT_OK：取自 first_list_version（2 项）
  note: NO_BUSINESS_POSITION_RECORDS：无逐节点覆盖记录，CV1『三份量可分离』一项真空（G-03），**不计为已核**
  [FATAL] coverage_verifiable @ facts/companies.jsonl:0 — CV3 覆盖目标 'c2' 无任何覆盖记录（静默遗漏；target=acceptance_input_set，10/01 §N10.1-06）
RESULT: FAIL（1 violations）
EXIT = 1
```
（`scanned` 与 `note` 见上；CV4 真空反例另有 `tests/daily/test_coverage_verifiable.py::test_cv4_no_target_is_not_a_pass`。）

### ②-3 降级：**注入故障 → 保留上次有效结果 + 降级可见**

注入方式：`code_root` 副本空投递口（`raw/inbox` 空）→ step 1 `degraded=True`；预先落一条**有效**核查记录 `check_2026-01-01_full`。

```
$ python - <<'PY'  # 见下方原样输出
=== ④ 降级（注入故障：空投递口 → step1 降级）===
degraded=True  degradation_visible=True  kept_last_valid=check_2026-01-01_full
降级标记落真源（原样）:
{"idempotency_key": "degrade::2026-01-02::full", "input_refs": ["check_2026-01-01_full"],
 "last_valid_result_ref": "check_2026-01-01_full", "status": "failed", "task_id": "task_degrade::2026-01-02::full",
 "task_type": "recheck", "parent_context": {"anchor": "Ch8 §E", "degraded": true,
 "gaps": ["step 2 (...)…", "… 共 11 条如实缺口 …"], "reason": "degraded_run", "run_date": "2026-01-02"}}
degrade.check 守卫: PASS
```
**结论**：一次故障注入 → **`kept_last_valid=check_2026-01-01_full`（保留上次有效结果）** 且降级**可见**（追加式 `Task` 行，`parent_context.degraded=true` + `gaps` + `run_date`）。**未**覆盖为无意义空值、**未**把旧数据标为最新（由 `assert_no_null_overwrite` / `assert_not_labeled_latest` 断言，错误路径见 `test_degrade_keeps_last_valid.py`）。

> 首日降级（**无**上次有效结果）边界：`last_valid_result_ref` **如实为空**（`None`），守卫记 note `DEGRADE_NO_LAST_VALID` 而**不**判违例（`G-03`：不得把"如实为空"判成缺陷）。
> `degrade.check` 是可失败的守卫：降级标记"既无 ref 又无 gaps"或"缺 run_date" → **违例**（`test_guard_fails_on_invisible_mark` / `test_guard_fails_on_missing_run_date`）。

### ②-4 幂等：**同日重跑 3 次 → 行数不变（`wc -l` 语义）**

```
=== ⑤ 幂等（同日重跑 3 次）===
BEFORE  events=0  recommendations=0
AFTER   events=0  recommendations=0
duplicate_events=()  duplicate_recommendations=()
check_record keys unique: True  (n=3)
```
**结论**：3 次同日运行后 `events` / `recommendations` 行数 **0 → 0 不变**、无重复键；运行记录以 `_r<n>` 修订号追加、幂等键**唯一**（`n=3, unique=True`）。
另有**强**证据（去重追加行数稳定，`test_idempotency.py::test_append_deduped_keeps_line_count_stable`）：`append_deduped` 首次写 2 行、二次写 **0** 行，`events.jsonl` 保持 2 行。

### ②-5 `p07` 走 `get_param`（**未硬编码**）+ 缺文件响亮行为

**grep：源码内无写死的时刻/时区/rrule 频率值**
```
$ grep -nE "[0-9]{1,2}:[0-9]{2}|Asia/|America/|Europe/|UTC|GMT|FREQ=(DAILY|HOURLY|WEEKLY|MONTHLY)" scripts/daily/*.py
（无匹配：未发现写死的时刻/时区/rrule 频率字面量）
```
**唯一读口证据**（值来自配置，改配置则输出改变）：
```
get_param('p07').freeze_status=tbd  value_source=suggested_baseline
resolve_schedule: cadence=daily_and_event anchor=us_market_close timezone=tbd time_value=tbd non_trading_day_policy=tbd value_source=suggested_baseline freeze_status=tbd pointer=rules/schedule.yaml
to_rrule 响亮失败: time_value='tbd' / timezone='tbd' 仍为 tbd —— 不得写死运行时刻/时区（Ch9 §3.10 J3 / p07）
```
（`test_schedule_p07.py::test_spec_value_comes_from_config_not_hardcoded`：把 `p07.suggested_value.time_value` 由 `21:15` 改 `06:05` → rrule 由 `FREQ=DAILY;BYHOUR=21;BYMINUTE=15` 变为 `FREQ=DAILY;BYHOUR=6;BYMINUTE=5`，**证明非硬编码**。）

**缺 `rules/schedule.yaml` → 响亮失败（不静默兜底）**：
```
=== 缺 rules/schedule.yaml 时的响亮行为 ===
load_schedule_yaml -> ScheduleFileMissingError: 缺少调度文件 rules/schedule.yaml —— 不得静默兜底（Ch8 §D）
resolve_schedule   -> ScheduleFileMissingError: 缺少调度文件 rules/schedule.yaml —— 不得静默兜底（Ch8 §D）
--- 显式要求缺省时才回落（且时区如实为 tbd，不臆造）---
explicit_default   -> cadence=daily_and_event anchor=us_market_close timezone=tbd time_value=tbd non_trading_day_policy=tbd value_source=suggested_baseline freeze_status=tbd pointer=rules/schedule.yaml
=== CLI（缺文件）===
== daily_schedule ==
  [FATAL] 缺少调度文件 rules/schedule.yaml —— 不得静默兜底（Ch8 §D）
RESULT: FAIL（1 violations）
EXIT = 1
```

### ②-6 反 KPI 自测：**无变化日 → `signals_emitted == 0`**

```
=== ③ 反 KPI（无变化日）===
changed=False  signals_emitted=0  blocked=True  gaps=12
```
**结论**：无变化日**不产任何买卖信号**（`signals_emitted=0`、`changed=False`），且模型侧缺口**如实**以 12 条 `gaps` + `blocked=True` 报出（**不乐观改写**）。

### ②-7 复用证据（**未重造**）

```
=== ⑦ 复用（G-06 唯一真源，不重造）===
idempotency.task_key('g1',None,'research') = research::g1 (== scripts.tasks.gap_to_task.idempotency_key)
coverage.RESEARCH_DEPTH_STATES = ('position_listed', 'relations_verified', 'baseline_done', 'tracking')
```
代码级：`coverage` 经 `schema.store.read_records` 读真源；`idempotency` 的事件键经 `scripts.graph.fingerprint.fingerprint_of_event`；`run` 经 `scripts.orchestrate.pipeline.Pipeline.run_daily`；`schedule` 经 `config.freeze.get_param("p07")`。**均未新建第二条实现路径。**

### ②-8 测试子集（仅 `tests/daily`，遵 `V-08` 纪律）

```
$ sh system/scripts/ops/run_pytest.sh tests/daily -q
.....................................                                    [100%]
37 passed in 42.68s
EXIT=0
```

### ②-9 pre-commit 门禁

```
$ sh system/scripts/ops/pre-commit.sh
① append_only_guard            RESULT: PASS
② rules_lock_guard             RESULT: PASS
③ registry_schema_guard        RESULT: PASS
④ schema_sync_guard            RESULT: PASS
⑤ conflict_scan(L1-L5)         RESULT: PASS
⑥ no_placeholder_guard         RESULT: PASS   ← 新源码无占位符命中
⑦ injection_guard              RESULT: PASS
⑧ verification_policy_guard    RESULT: FAIL（1 violations）← ★ 唯一红门禁，见 ③
⑨ shell_var_guard              RESULT: PASS
⑩ graph_integrity_guard        RESULT: PASS
EXIT=1
```
⑧ 的唯一违例（原样）：
```
[FATAL] V-06 @ scripts/ops/verify.py:0 — 以下测试文件**不被任何批次覆盖**（写了却永远不被验证）:
['tests/daily/test_coverage_verifiable.py', 'tests/daily/test_daily_run.py',
 'tests/daily/test_degrade_keeps_last_valid.py', 'tests/daily/test_idempotency.py',
 'tests/daily/test_schedule_p07.py'] → 请在 `verify.py::BATCHES` 增加/扩展批次
```

---

## ③ 结果

1. **阶段④ 硬判据 `coverage_verifiable` 已实现且可核**：从 `criteria_not_implemented: 1` → 判据 `check(root) -> CheckReport` 就绪；正反两向各得 `PASS/EXIT=0` 与 `FAIL/EXIT=1`（②-1/②-2）。
2. **降级保留上次有效结果 + 可见**（②-3）；**同日重跑幂等**（②-4）；**p07 配置化、值未硬编码、缺文件/`tbd` 响亮失败**（②-5）；**反 KPI 无变化日零信号**（②-6）；**复用既有真源、无重造**（②-7）。
3. `tests/daily` **37 passed / EXIT=0**（②-8）。
4. **`pre-commit` 仅 ⑧ `verification_policy_guard`（V-06）红**，且**红因已知且预期**（新目录 `tests/daily/` 未被 `verify.py::BATCHES` 覆盖）。**未修改 `verify.py`**（共享文件，归主理人）。因这是**唯一**红门禁，依 `§1.5` 以 `--no-verify` 提交并在此**显式披露**。
5. **需主理人补两处（均在我范围外）**：
   - **(a) 新增测试批次 `daily` → `tests/daily`**：在 `system/scripts/ops/verify.py::BATCHES`/`ORDER` 增一条（含每批超时 ≤300s、`124` 不判通过）；此举即消 ⑧ 之红。
   - **(b) `stage_gate.py` 接线 2 行**（`scripts/delivery/**` 不在我的允许清单内）：在 `stage_daily_run_passed()` 内加
     ```python
     from scripts.daily.coverage import check as coverage_check
     v += coverage_check(root).violations
     criterion("daily_run", "coverage_verifiable", v)
     ```
     使阶段④ 的 `bound_criteria` 由 3 覆盖到 4（`delivery.yaml` 声明的第 4 条判据）。
6. 真源**零污染**：`facts/claims.jsonl=5`、`dependency_edges.jsonl=3`、`companies.jsonl=2`、`tasks.jsonl=3`（真实数据原样）；`tests/.work` 取证后已清空。

---

## ④ 如实登记的残余与不确定（**宁可少报，不许假报**）

- **U-1（V-06 红，已预期）**：⑧ 门禁红仅因新目录；未改 `verify.py`。**主理人补批次 `daily` 后应转绿**——未在本次验证（我无法改共享文件）。
- **U-2（`stage_gate` 未接线）**：`coverage_verifiable` 目前是**独立可核判据**，**尚未**被 `stage_daily_run_passed()` 绑定（`criteria_bound` 仍为 3）。已完成形态为 `check(root)->CheckReport`，接线即 §③-5(b) 两行。**未接线前，阶段④ 门禁不会因覆盖不达标而红。**
- **U-3（`V-08` 不存在）**：本工作树 `CONVENTIONS.md` 正文止于 `R-06`，**无 `V-08`**（登记为 DoD `G-7`）。我据主理人口头纪律"只跑 `tests/daily` 子集"执行；该纪律与 `V-06`/`V-02` 一致。
- **U-4（验收输入 schema 未在设计区定死）**：`registry/acceptance_input_set.yaml` 的结构在设计区**未逐字给出**，本实现**宽容读取**列表形态键（`first_list`/`first_list_version`/`first_list_members`），缺失时显式退化并记 note（**不静默**）。→ DoD `G-3`。**若需求方定死键名，需同步 `_ACCEPT_LIST_KEYS`。**
- **U-5（`industry_nodes` 无深度字段）**："在册节点无覆盖记录"记为**可见 note + 扫描计数**，**不**判违例（避免假红；节点↔公司映射由采集层给出，本层不臆造）。→ DoD `G-2`。
- **U-6（建议键口径映射）**：设计键 `(security_id, issued_at, version)` 中的 `issued_at` 在模型 `Recommendation` 上**无同名字段**，落点为 `start_date`；本模块以 `(security_id, start_date, version)` 表达并**显式登记**。→ DoD `G-5`。
- **U-7（`p07` 无时区值）**：`rules/freeze.yaml::p07.suggested_value` **不含** `timezone`；时区取 `rules/schedule.yaml::cadence.timezone`（`tbd`）。故 `to_rrule()` 在拍板前**必**响亮失败——这是**设计使然**（"不得写死"）。→ DoD `G-4`。
- **U-8（频率 token 的边界说明，主动披露）**：源码内有结构映射 `_CADENCE_FREQ = {"daily":"DAILY","daily_and_event":"DAILY"}`（`cadence` 值 → RRULE 频率 token）。**该"值"（`daily`/`daily_and_event`）来自 `p07.cadence` 配置**，映射表只是"配置取值 → RRULE 记号"的**结构翻译**，非写死频率。②-5 的 grep 已排除 `FREQ=<字面频率>`；此处如实说明以免被误读为"完全无频率相关字面量"。
- **U-9（未做，明确不做）**：第 7/8 步（发布/持续核验）hook 的**实现**、真实采集连接器、模型侧七步判定/关系抽取/增长护城河判断——**均不在本单范围**（属阶段②③⑤与其它 workstream）。
- **U-10（首日无上次有效结果）**：首日降级时 `last_valid_result_ref` 如实为 `None`；如需"降级也必须能核"，则该 note 升级为违例的策略需**需求方裁定**（当前按 `G-03` 判为"如实为空、非缺陷"）。
