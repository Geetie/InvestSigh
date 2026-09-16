# `ws/degrade-contract` 交付报告 —— 修 `G-43`（高）/ `G-45`（中高）

> 一句话：阶段④ 声明的判据 `degrade_keeps_last_valid` 此前**在真数据上空转**（把**所有**失败行
> 都当"首日"豁免 ⇒ **从不报任何真违规**）。本单让它在**真实字段形状**上真的成立、真的会拦，
> 并把"上次有效结果"的判定**收敛到唯一一处**。

- **工作树**：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-degrade-contract`
- **分支**：`ws/degrade-contract`（基点 `d5a37f8`）
- **代码 commit（评审对象）**：`abbe7b3` = `abbe7b367034c7987acb3d1660d82ab9d10b6c8c`
  （`fix(degrade): 修 G-43/G-45 —— 让「降级保留上次有效结果」在真数据上真的会拦`）—— **全部代码改动都在这一个 commit 里**
- **报告 commit**：`abbe7b3` 之后的所有 `docs(report):` 提交（`d34e6e5` / `4f03d7d` / `44dee2e` / …）
  —— **只改本文件、不动代码**；核对方式：`git diff abbe7b3..HEAD --stat` 只会列出本报告
- **改前基线（对照用）**：`d5a37f8`；后续任何新提交**只会是本报告文件**的修改
- **`git status --short`**：**（空）** —— 工作树干净（本报告已入库，故不在未跟踪列表里）
- **`$PY`** = `/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`
- **纪律声明**：全程**未**触碰真仓库 `system/facts/`、`system/derived/`、`system/state.json`
  （`git status --short` 为空即证据）；`rules/**` 未改（权限位由 `bootstrap_worktree.sh` 复原）；
  一切实验在**副本**（`/tmp/wsdc/**`）中进行；提交时 `pre-commit` **未被跳过**。

---

## ① 改了什么

### 1.1 缺陷的两半（先分开看，它们不是一件事）

| # | 缺陷 | 那一半的位置 | 本单怎么修的 |
|---|---|---|---|
| `G-43` | 首日豁免的**内层谓词**在真数据上**恒 False** ⇒ 全员豁免 ⇒ 判据空转 | `scripts/delivery/stage_gate.py::_holds_valid_result()`（只认 `last_valid_result_ref` / `output_refs`）+ 写入方 `pipeline._write_check_record()` **两个字段都不填** | **写路径补齐** + **谓词换真源** |
| `G-45` | "上次有效结果"**两个模块口径相反**；`output_refs=` **零个生产赋值点** | `degrade.last_valid_result_ref()`（认"一次成功的运行"） vs `stage_gate._holds_valid_result()`（认两个从不被填的字段） | **收敛到唯一一处**（`scripts/daily/degrade.py`） |

### 1.2 唯一真源：`scripts/daily/degrade.py`（**选择理由**）

**真源选 `degrade.py`，不选 `stage_gate.py`**，三条理由（逐条可核）：

1. **语义在它那里已经是"上一次成功运行"**：`Ch8 §E.2` 明写 `last_valid_result_ref` 的写者角色是
   "**失败时指向旧结果**"、读者是 `ops/diagnose.py` + 展示层；`degrade.py` 正是**降级契约**的归属模块
   （`ANCHOR = "Ch8 §E"`），而 `stage_gate` 只是**消费者**（判据守卫）。
2. **它同时是写入方的供体**：`pipeline._write_check_record()` 需要算出"该指向谁"——
   这个计算已经在 `degrade.py` 里存在（`G-06` 唯一真源 / 纪律 11：**不得重算第二套**）。
   若反过来让 `degrade` 依赖 `stage_gate`，就让守卫模块变成了数据的生产者（依赖倒置）。
3. **另一个候选口径已被证伪**：`output_refs` 在本单之前**全仓库零个生产赋值点**
   （`G-45` 实测），把它作为"是否有旧结果"的判据等于把判据建在一个**从不被写**的字段上。

新增/改造（`scripts/daily/degrade.py`）：

```python
def is_valid_run_record(row) -> bool:      # ★ 唯一原语：一条"成功的运行记录"
    record = row.get("check_record")
    if not isinstance(record, Mapping):
        return False
    return row.get("status") != "failed" and not record.get("degraded")

def holds_valid_result(row) -> bool:       # ★ 豁免判定的唯一真源（三条载体并集）
    if row.get("last_valid_result_ref"):   # ① 降级链上的显式引用
        return True
    if is_valid_run_record(row):           # ② 一次成功的运行（**新增**，消 G-45 分歧的那一条）
        return True
    return row.get("status") == "done" and bool(row.get("output_refs"))   # ③ 旧 stage_gate 口径

def last_valid_result_ref(root, *, scope="full") -> str | None:
    # 只认 is_valid_run_record()（= 旧行为逐字不变），取**最后一条**成功运行的 check_id
```

- **①③ 原样保留**（只增不减，`R-06`：不得放松判据）；**②是新加的**，它把"此前有过一次成功运行"
  这件事**从两个从不被写的字段上解偶**。
- `stage_gate.py` 删除自持的 `_holds_valid_result()`，改为
  `from scripts.daily.degrade import holds_valid_result`（第 513 行）。
  **机器可核**：全仓库 `_holds_valid_result` 的执行体**零命中**（仅 3 处注释在叙述历史），
  `holds_valid_result` **只有一个定义点**（`degrade.py:104`），`is_valid_run_record` 一个
  （`degrade.py:84`）—— 见 §③-2 的原始输出。

### 1.3 写路径补齐契约：`pipeline.py::_write_check_record`（**唯一被授权的共享文件改点**）

| 字段 | 填法 | 设计锚点 |
|---|---|---|
| `last_valid_result_ref` | 本次运行 `blocked or degraded`（= **未产出有效结果**）时，填 `degrade.last_valid_result_ref(self.root, scope=...)`；成功运行时为 `None`（本次结果**就是**有效结果）；**首日照实为 `None`** | `Ch8 §E.2`（"失败时指向旧结果"）/ `N9.2-13` / `Ch8 §E.4`（不得置空）/ `G-03`（不臆造） |
| `output_refs` | `result.steps[*].produced` 的**并集**（= 本轮**真正新写入**的对象引用），去重保序；**仅当本次运行产出有效结果时**填写；失败 / 降级 / 阻断时**如实为空** | `Ch8 §E.1`（失败 → 本次不产有效结果）+ `§E.4`（不覆盖为无意义空值） |

- 取值**必须在 `append_records` 之前**：本行尚未落库 ⇒ 读到的天然是"上一次"。
- `pipeline.py` 的 diff **只在 `_write_check_record` 一个方法内**（`git diff` 已复核，见 §③-5）。
- `chain_steps.py` **零改动**（无需改，未扩大）。

### 1.4 可观测性：新增成对计数 `rows_holding_valid_result`

`stage_gate --stage daily_run` 的输出新增 `scanned daily_run.rows_holding_valid_result: N`。
理由（`G-03` 同源）：单看 `degrade_first_day_exempt: 0` **分不清**"没有失败行"与"谓词恒 False"——
两者观测量完全相同。给出"按该谓词**真的**持有有效结果的行数"，任何一方的恒真 / 恒假都当场可见。

### 1.5 测试夹具改为**走真实写路径**（审计点名的那一半）

原夹具（`test_wiring_guards.py::_done_task_with_output()`、`test_criterion_effectiveness.py::_task()`）
手工拼 `{"status": "done", "output_refs": ["rec-nvda-001"]}` —— **生产代码从未写出过那个形状**
（`_write_check_record()` 当时两个字段都不填）⇒ 谓词在**夹具上**为 True、在**真数据上**恒 False
⇒ **测试全绿而判据空转**。现：

- 新增 `tests/conftest.py::write_check_records(root, runs)` = **唯一写入方**
  `Pipeline._write_check_record()`（`G-06`：不再造第二套形状）；
- 需要"契约被破坏"的形态时，只对**真实写入的行**做**定向违约注入**（把已填好的引用抹成 `null`）
  —— 注入 ≠ 夹具造假；
- 新增 4 条用例（其中 2 条就是审计反例本身）：
  `test_write_path_fills_last_valid_ref_and_output_refs`、
  **`test_audit_counterexample_real_shape_is_now_caught`**、
  `test_first_day_degrade_exemption_is_effective_and_counted`（反向对照）、
  `tests/daily/test_daily_run.py::test_writepath_really_fills_degrade_contract_fields`（端到端）。

**改动清单**（`git show --stat abbe7b3`）：

```
 system/scripts/daily/degrade.py                    |  69 ++++++++-
 system/scripts/delivery/stage_gate.py              |  49 +++---
 system/scripts/orchestrate/pipeline.py             |  41 +++++
 system/tests/conftest.py                           |  41 +++++
 system/tests/daily/test_daily_run.py               |  96 ++++++++++++
 system/tests/injection/test_criterion_effectiveness.py |  53 +++++--
 system/tests/injection/test_wiring_guards.py       | 172 ++++++++++++++-------
 7 files changed, 435 insertions(+), 86 deletions(-)
```

---

## ② 测了什么（贴真实输出）

### 2.1 ★ 证据 1：改前 / 改后对拍（**同一份数据**）

受控数据 = **真仓库** `facts/tasks.jsonl`（4 行：2 条 `queued` recheck + 2 条 `failed` check）。
"改前"= 本单改动前的提交 `d5a37f8` 的三个文件版本（`git show d5a37f8:…` 覆盖进副本）。

```
=== case=real mode=before ===
--- $ python scripts/delivery/stage_gate.py <copy> --no-report --stage daily_run
--- exit=0
== stage_gate[daily_run] ==
  scanned daily_run.check_records: 2
  scanned daily_run.degrade_first_day_exempt: 2
  scanned daily_run.tasks: 4
  note: daily_run: PASS
RESULT: PASS（0 violations）
=== case=real mode=after ===
--- exit=0
  scanned daily_run.check_records: 2
  scanned daily_run.degrade_first_day_exempt: 2
  scanned daily_run.rows_holding_valid_result: 0
  scanned daily_run.tasks: 4
  note: daily_run: PASS
RESULT: PASS（0 violations）
```

**读法（重要，如实说明）**：真仓库当前 2 条 check_record 行**都是 `failed` 且从未有过成功运行**
（步骤 7/8 未注册处理器 ⇒ `blocked` 恒真 ⇒ 状态恒 `failed`，见 §④-1），
故"2 条豁免"**是正确结论**（结构上确实没有可保留的旧结果），改前改后**一致、
无新增假红**。新增的 `rows_holding_valid_result: 0` 正是这个结论的**证据**——
改前它无法区分"确实没有"与"谓词恒 False"。

### 2.2 ★★ 证据 2a：审计反例必须"拦得住"（真实字段形状）

受控数据（**逐字采用审计的反例形状**，也是 `_write_check_record()` 当时写出的真形状）：

```
{"check_record": {"check_id": "check_d1_full", "degraded": false, …}, "status": "done",
 "output_refs": [], "last_valid_result_ref": null, …}          ← 成功行（无新增产出，合法）
{"check_record": {"check_id": "check_d1_full_r1", "degraded": true, …}, "status": "failed",
 "output_refs": [], "last_valid_result_ref": null, …}          ← 失败行**丢引用**（违约）
```

```
=== case=audit_c1 mode=before ===
--- exit=0
  scanned daily_run.degrade_first_day_exempt: 1
  scanned daily_run.tasks: 2
  note: daily_run: PASS
RESULT: PASS（0 violations）          ← ★ 真违规一条不报（G-43：判据空转）

=== case=audit_c1 mode=after ===
--- exit=1
  scanned daily_run.check_records: 2
  scanned daily_run.degrade_first_day_exempt: 0
  scanned daily_run.rows_holding_valid_result: 1
  scanned daily_run.tasks: 2
  note: daily_run: BLOCKED
  [FATAL] daily_run @ facts/tasks.jsonl:0 — task_check_d1_full_r1 失败但未保留 last_valid_result_ref（此前已有行持有有效结果 ⇒ 引用本该在，不得置空）
RESULT: FAIL（1 violations）          ← ★★ 拦住了（exit 1）
```

### 2.3 ★ 证据 2b：反向对照 —— **真首日**失败必须豁免且计数可见

（受控数据：仅一条 `failed` 行，此前**从来**没有任何成功运行）

```
=== case=first_day mode=before ===        === case=first_day mode=after ===
--- exit=0                                --- exit=0
  scanned daily_run.check_records: 1        scanned daily_run.check_records: 1
  scanned daily_run.degrade_first_day_exempt: 1
                                            scanned daily_run.degrade_first_day_exempt: 1
                                            scanned daily_run.rows_holding_valid_result: 0
  scanned daily_run.tasks: 1                scanned daily_run.tasks: 1
  note: daily_run: PASS                     note: daily_run: PASS
RESULT: PASS（0 violations）               RESULT: PASS（0 violations）
```

**两个方向都证了**：真首日 ⇒ 豁免（`exempt=1` + `rows_holding_valid_result: 0` ⇒ 豁免**归因明确**）；
有成功运行却丢引用 ⇒ **FATAL**（`exempt=0`）。

### 2.4 补充对照：真实写路径产出的行（成功行 `output_refs` 非空）

```
=== case=real_shape mode=after ===（成功行由 `Pipeline._write_check_record` 直写；失败行删引用）
{"…", "last_valid_result_ref": null, "output_refs": ["claim-a", "claim-b"], "status": "done", …}
{"…", "last_valid_result_ref": null, "output_refs": [], "status": "failed", …}   ← 注入：抹掉引用
--- exit=1
  scanned daily_run.degrade_first_day_exempt: 0
  scanned daily_run.rows_holding_valid_result: 1
  [FATAL] daily_run @ facts/tasks.jsonl:0 — task_check_2026-09-16_full_r1 失败但未保留 last_valid_result_ref（…）
RESULT: FAIL（1 violations）
```

★ **如实说明**：这一例**改前也会红**（`mode=before` 同样 `exit=1`）——
因为成功行的 `output_refs` 非空，命中旧谓词的载体③。
**这不是"改前也守得住"**：载体③在生产数据上**从不成立**（`output_refs=` 零个生产赋值点，`G-45`）。
**承载 G-43 结论的是 §2.2 的 `audit_c1`（`output_refs=[]`）**——那一例改前 `exit=0`、改后 `exit=1`。

### 2.5 ★ 证据 3：`run_daily` 端到端 —— 真源里的**真实行**证明字段真的被填了

走**真实入口** `scripts/daily/run.py::run_daily`（= `Pipeline.run_daily` + `degrade.mark_degraded`
+ `coverage.check` + `idempotency.duplicates`）。为把"第一次成功"造出来，只用**公开注册面**
（`Pipeline.register_step` / `register_*_hook`）把 8 步换成确定性桩 + **注入一次故障**；
**被验证的写入方 `_write_check_record()` 是真代码**。

```
═══ 第 1 次 run_daily（成功 → status=done）═══
  blocked=False degraded=False gaps=0  last_valid_result_ref='check_2026-09-16_full'
═══ 第 2 次 run_daily（step 3 抛异常 → failed + 保留上次有效结果）═══
  blocked=True  degraded=True  gaps=1  last_valid_result_ref='check_2026-09-16_full'

═══ facts/tasks.jsonl 的真实行（逐行原样）═══
[0] {"last_valid_result_ref": null,
     "output_refs": ["obj-step1-a","obj-step1-b", …, "obj-step8-a","obj-step8-b"],
     "parent_context": {"orchestrator": "pipeline.run_daily"},
     "status": "done", "task_id": "task_check_2026-09-16_full", "task_type": "verify"}
      check_record: {"check_id": "check_2026-09-16_full", "degraded": false, …, "run_date": "2026-09-16", "scope": "full"}
[1] {"last_valid_result_ref": "check_2026-09-16_full",     ← ★ 字段**真的被填了**
     "output_refs": [],
     "parent_context": {"orchestrator": "pipeline.run_daily"},
     "status": "failed", "task_id": "task_check_2026-09-16_full_r1", "task_type": "verify"}
      check_record: {"check_id": "check_2026-09-16_full_r1", "degraded": true, …, "run_date": "2026-09-16", "scope": "full"}
[2] {"last_valid_result_ref": "check_2026-09-16_full",     ← ★ 降级标记行（**另一个模块**）指向同一个 id
     "output_refs": [],
     "parent_context": {"anchor": "Ch8 §E", "degraded": true,
                        "gaps": ["G1-05 第 3 步（update_company_and_industry_relations）未产出：status=failed，error=RuntimeError: 注入故障：step 3 模型侧超时"],
                        "reason": "degraded_run", "run_date": "2026-09-16"},
     "status": "failed", "task_id": "task_degrade::2026-09-16::full", "task_type": "recheck"}
      check_record: null
```

**这张表同时证明了 §③-2 的"跨模块口径一致"**：`pipeline._write_check_record`（行 [1]）与
`degrade.mark_degraded`（行 [2]）对同一批行给出**同一个** `check_2026-09-16_full` ——
`G-45` 的"两个模块口径相反"消失。

再对这棵结果树跑门禁（证明补齐契约后**不产生假红**）：

```
== stage_gate[daily_run] ==
  scanned daily_run.check_records: 2
  scanned daily_run.degrade_first_day_exempt: 0
  scanned daily_run.rows_holding_valid_result: 3
  scanned daily_run.tasks: 3
  note: daily_run: PASS
RESULT: PASS（0 violations）   exit=0
```

### 2.6 证据 4：测试

**一次只跑一个目录 / 分次多文件**（`G-RC-08`）。逐条实测：

| 命令（在 `system/` 下，`$PY -m pytest … -q -p no:cacheprovider`） | 结果 |
|---|---|
| `tests/daily/test_daily_run.py` | **13 passed** in 42.70s |
| `tests/daily`（整目录） | **44 passed** in 160.40s |
| `tests/injection/test_wiring_guards.py` | **17 passed** in 69.95s |
| `tests/injection/test_criterion_effectiveness.py` | **23 passed** in 98.99s |
| `tests/injection/test_stage_gate.py tests/injection/test_audit_regressions.py` | **24 passed** in 121.74s |
| `tests/injection/test_idempotency_rows.py tests/injection/test_chain_steps_wiring.py tests/injection/test_append_only.py` | **28 passed** in 81.30s |
| `tests/injection/test_guards_reject.py tests/injection/test_guards_defensive.py` | **46 passed** in 222.16s |
| `tests/injection/test_prompt_injection.py tests/injection/test_rules_lock.py tests/injection/test_time_contract.py` | **32 passed** in 137.21s |

★ **一次环境性假红，如实登记**：`test_stage_gate.py + test_audit_regressions.py` 的**第一次**运行
报 `23 passed, 1 error`，错误是**夹具 setup** 里宿主的 safe-delete shim 失败：

```
[safe-delete][SAFE_DELETE_FAIL_CLOSED] {"reason": "trash-failed", "detail": "… FSMoveObjectToTrashSync failed (status -5000) for …/system/raw/2025-02-26-nvidia-q4-fy2025-results.txt"}
E  OSError: [safe-delete] 操作失败: …
```

**单独重跑该用例 `1 passed in 1.13s`；两个文件再次同跑 `24 passed in 121.74s`** ⇒
判为宿主删除代理的偶发故障（与本改动无关）。

### 2.7 证据 5：全量门禁 与 `pre-commit`（含**基线对拍**）

```
$ $PY system/scripts/ops/run_all_gates.py --timeout 30
  非零计数                               1
  traceback.py                       exit=1        0.12s
```

**这不是本单引入的**——用 `git stash` 把本单 7 个文件全部暂存后的**同一工作树基线**：

```
$ git stash push -- system/scripts/daily/degrade.py system/scripts/delivery/stage_gate.py \
    system/scripts/orchestrate/pipeline.py system/tests/conftest.py system/tests/daily/test_daily_run.py \
    system/tests/injection/test_criterion_effectiveness.py system/tests/injection/test_wiring_guards.py
Saved working directory and index state On ws/degrade-contract: ws-degrade-contract baseline probe
$ $PY system/scripts/ops/run_all_gates.py --timeout 30
  append_only_guard.py               exit=0        0.15s
  traceback.py                       exit=1        0.12s
  非零计数                               1          ← ★ 与改后**完全相同**
$ git stash pop   → 7 files restored
```

并且把 `traceback.py` 单独拿到**同数据的 HEAD 版副本**上跑，输出**逐字相同**：

```
=== AFTER（工作树）traceback.py ===            === BEFORE（HEAD 版三文件副本）traceback.py ===
  [FATAL] G1-03 @ facts/recommendations.jsonl:0 — rec-nvda-001 四要素（**适用项**）缺失: ['assumptions', 'computation']（…）
  [FATAL] G1-03 @ facts/recommendations.jsonl:0 — 四要素（适用项）反查成功率 0.0000 < 1.0 —— …
RESULT: FAIL（2 violations）  exit=1            RESULT: FAIL（2 violations）  exit=1
```

⇒ 唯一非零门禁是**真源既有的红**（`facts/recommendations.jsonl::rec-nvda-001` 缺四要素，
`traceback.py` 只读 `recommendations` + `derived/trace.jsonl`，与本改动无交集）。

`pre-commit`（**未跳过**，`git commit` 现场输出尾部）：

```
pre-commit → criterion_effectiveness_guard
== criterion_effectiveness_guard.py ==
  scanned criteria_bound: 12
  scanned criteria_registry_entries: 13
  scanned counterexample_entries: 11
  scanned ineffective_entries: 2
  scanned registry_entry_tests_resolved: 13
RESULT: PASS（0 violations）
pre-commit ✓ 全部门禁放行
[ws/degrade-contract abbe7b3] fix(degrade): 修 G-43/G-45 —— 让「降级保留上次有效结果」在真数据上真的会拦
 7 files changed, 435 insertions(+), 86 deletions(-)
```

---

## ③ 每条要求对应的证据（逐条对齐派单）

| # | 派单要求 | 落点 | 证据 |
|---|---|---|---|
| 1 | **写路径补齐契约**：`_write_check_record` 填两个字段；`last_valid_result_ref` **必须复用** `degrade.py` 的计算（`G-06`）；首日 `None` 合法（`G-03`） | `pipeline.py::_write_check_record` | §2.5（真源真行：成功行 `output_refs` 非空、失败行 `last_valid_result_ref="check_2026-09-16_full"`）+ `tests/daily/test_daily_run.py::test_writepath_really_fills_degrade_contract_fields`（首日 `None` 也断言了） |
| 2 | **消掉 `G-45` 两模块口径分歧**，收敛到一处 | 真源 = `scripts/daily/degrade.py`；`stage_gate` 改为 import | §2.5（行[1] 与行[2] 指向**同一个** `check_id`）+ 下面这段机器核对： |

```
$ $PY - <<'EOF'  （扫 system/**/*.py，打印 _holds_valid_result / holds_valid_result / is_valid_run_record 的全部出现）
=== A. 旧谓词 _holds_valid_result 是否还有定义/调用 ===
system/scripts/daily/degrade.py:95:  …此前 `stage_gate._holds_valid_result()`      ← 仅注释（叙述历史）
system/scripts/delivery/stage_gate.py:506: …此前这里另写了一个 `_holds_valid_result()`  ← 仅注释
system/scripts/orchestrate/pipeline.py:364: …`_holds_valid_result()`）**恒 False** ⇒ …  ← 仅注释
（**无可执行的定义点 / 调用点**）
=== B. holds_valid_result 的定义点 / 调用点 ===
system/scripts/daily/degrade.py:84: def is_valid_run_record(row) -> bool:          ← 唯一原语（1 个定义）
system/scripts/daily/degrade.py:104: def holds_valid_result(row) -> bool:           ← 唯一豁免谓词（1 个定义）
system/scripts/daily/degrade.py:132: if is_valid_run_record(row):                 ← 谓词载体②
system/scripts/daily/degrade.py:159: if not is_valid_run_record(row):             ← last_valid_result_ref 的判据
system/scripts/delivery/stage_gate.py:513: from scripts.daily.degrade import holds_valid_result  ← 唯一消费方
system/scripts/delivery/stage_gate.py:568: if not any(holds_valid_result(_prior) …)
system/scripts/delivery/stage_gate.py:579: elif holds_valid_result(t):
```

| # | 派单要求 | 落点 | 证据 |
|---|---|---|---|
| 3 | **首日豁免在补齐后的真实形状上仍正确**：真首日 ⇒ 豁免且计数可见；有成功运行却丢引用 ⇒ **FATAL** | `stage_gate.py::stage_daily_run_passed` + `degrade.holds_valid_result` | §2.3（真首日：`exempt=1` + `rows_holding_valid_result: 0`，exit 0）+ §2.2（`audit_c1`：`exempt=0` + FATAL，exit 1）。**两边都证了** |
| 3b | **审计反例必须变成"拦得住"** | 同上 | §2.2：改前 `exit=0 / exempt=1 / 真违规 0 条` → 改后 `exit=1 / exempt=0 / 命中 FATAL` |
| 4 | **夹具必须走真实写路径**（并**明说**这一点） | `tests/conftest.py::write_check_records` + 两处注入测试改写 | §1.5；`test_write_path_fills_last_valid_ref_and_output_refs` 直接断言**真行**的三态字段；`test_audit_counterexample_real_shape_is_now_caught` 用真实写路径行 + 定向违约注入 |
| 5 | `tests/daily` / `tests/injection` 相关用例全绿；一次一个目录 | — | §2.6（44 / 17 / 23 / 24 / 28 / 46 / 32） |
| 6 | 报告（本文件）：实际命令输出 + 退出码 + commit hash + `git status --short` | `system/reports/ws_degrade_contract_report.md` | 本文件 §②③④ + 抬头（`abbe7b3`+`d34e6e5` / `d34e6e5027fa83b91003e02b2ed02b735ddf0668` / `git status --short` 为空） |
| 7 | **不得放松判据** | 三载体**只增不减**（①②③，删掉任一条都会放松） | ①③ 原样保留；② 是新增 ⇒ 相对两侧旧口径是**超集**。`audit_c1`/`first_day` 两向对照证明"该拦的拦、该豁免的豁免" |
| 8 | 共享文件授权范围 | `pipeline.py` **仅** `_write_check_record` 一处 | 见下 |

```
$ git diff d5a37f8..abbe7b3 -U0 -- system/scripts/orchestrate/pipeline.py | grep '^@@'
@@ -349,0 +350,24 @@ class Pipeline:
@@ -352,0 +377 @@ class Pipeline:
@@ -360,0 +386,14 @@ class Pipeline:
@@ -375,0 +415,2 @@ class Pipeline:
$ git diff --numstat d5a37f8..abbe7b3 -- system/scripts/orchestrate/pipeline.py
41	0	system/scripts/orchestrate/pipeline.py      ← 纯新增 41 行、0 删除
$ git diff --numstat d5a37f8..abbe7b3 -- system/scripts/orchestrate/chain_steps.py
（空 —— chain_steps.py 零改动）
$ grep -n "def _write_check_record\|def _state_path" system/scripts/orchestrate/pipeline.py
342:    def _write_check_record(self, result: RunResult) -> None:
422:    def _state_path(self) -> Path:
```

**复核结论**：`-U0` 展开后是 **4 个纯新增 hunk（+41 / -0）**；带默认上下文的 `git diff` 会把相邻两块合并显示为 3 个 hunk
（首块 `@@ -347,9 +347,34 @@`）——两种视角说的是同一处改动。**所有新增行落在 350–416 行**，
而 `_write_check_record` 方法体是 **342–421 行**，下一个方法 `_state_path` 起于 422 行
⇒ **每一个新增行都在 `_write_check_record` 内部，没有一行逸出**（`chain_steps.py` 零改动）。

---

## ④ 剩余不确定性与缺口（**如实报出，不掩盖**）

### ④-1 ★ 真仓库当前**永远不会有"成功运行"** ⇒ 本判据在真数据上仍只能证"首日豁免"这一半

- **机器事实**：`rules/pipeline.yaml` 声明 step 7/8 `blocking: true` 且 `implemented_in_first_version: false`；
  `run_daily()` 对未注册处理器的步 **记 `gap` + 置 `blocked`**（`pipeline.py` 主流程），
  而 `_register_default_steps()` **从不注册 7/8 步的处理器**（只注册 1–6 + hook 接口）
  ⇒ **`blocked` 恒为真 ⇒ `status` 恒为 `failed` ⇒ 真仓库永远没有一次成功运行**。
- **后果**：真数据上 `last_valid_result_ref` 恒为 `None`、`degrade_first_day_exempt=2` **是正确的**
  （确实没有可保留的旧结果），但这意味着**"有成功运行却丢引用 ⇒ FATAL"这一半只能在受控输入上验证**
  （§2.2 / §2.5），**无法在真仓库上自然发生**——直到 step 7/8 被实现或 `blocking` 语义被裁定。
- **为何不改**：`rules/**` 是 0444 只读设计区；`chain_steps.py` 不在本单授权内；
  且"7/8 步未实现 ⇒ blocked"是 `rules/pipeline.yaml` + `T-08` 的**既有设计裁决**，
  不是本单可自裁的事。**⇒ 已按派单要求"停下来报"（留待需求方裁定）。**
- **旁证（同族缺口）**：`scripts/tasks/gap_to_task.py::check` 要求**终态 `done` 必须 `output_refs` 非空**
  （否则判"空执行" `G1-04`）。本单补齐 `output_refs = 本轮真正新写入` 之后，
  "成功运行且本次无新增产出"（幂等重跑日）会是 `done + output_refs=[]` ⇒ 该守卫会 FATAL。
  **这是既有行为**（本单之前 `done` 行恒 `output_refs=[]`，更严重），且与 `G-44`
  （"幂等被当成没做完"）**同族**：`StepOutcome.skipped` 的语义需要在 `output_refs` 上有一个
  明确口径（是否把"考察过、均已存在"计入）。**本单不改**（属 `G-44` 的裁定范围）。

### ④-2 `output_refs` 在"失败运行"上的语义是**本单的取舍**（非设计逐字规定）

设计区只逐字规定"失败 → **保留上次有效结果**"（`§E.1`）与"不得覆盖为无意义空值"（`§E.4`），
**未逐字规定**"失败轮的部分写入是否进 `output_refs`"。本单取"**失败 ⇒ 空**"，理由：
把本次的部分写入列进 `output_refs`，会让"本轮有没有有效产出"在**单看该字段**时不可区分
（`§E.1`：失败轮的有效结果 = `last_valid_result_ref` 指向的旧结果）。
**如需求方要"失败轮也如实列出部分写入"**，改动点只有一处（`pipeline.py` 的
`output_refs=produced if valid_run else []`），且**不会**影响本判据（失败行不满足载体③的 `done` 前提）。

### ④-3 载体①的语义边界（保留但已知其"弱"）

载体①（`last_valid_result_ref` 非空 ⇒ 持有有效结果）是 `stage_gate` 的旧口径，本单**保留不删**
（删即放松）。它的"弱"处：一条失败行**自带一个指针**并不等于它自己产出了结果。
本单的处理是**把它限制在豁免判定里**（`holds_valid_result`），而**定位引用**（`last_valid_result_ref()`）
**不用它**——只用 `is_valid_run_record()`，避免"指向一条失败运行的 `check_id`"。
⇒ 两处职责分工已写进 docstring；**未发现它导致任何误判**（§2.6 全绿，§2.2/2.3 两向对照成立）。

### ④-4 未覆盖：并发/多写者

`_write_check_record` 的"读上一次成功运行 → 写本行"不是原子的。同一 `code_root` 上**并发**跑两次
`run_daily` 时，两行可能都指向同一个旧 `check_id`（**不会**产生悬空引用，但第二个失败行的
"上一次"可能不是紧邻的那次成功）。本项目当前是**单写者 + 会话锁**（`V-05`）语义，
**无并发写入点**。⇒ 登记为**已知边界**，未改（也不该在本单引入锁机制）。

### ④-5 未做的（明确不在本单范围）

- 未改 `chain_steps.py` / `rules/**`（见 ④-1）；
- 未改 `gap_to_task.py`（见 ④-1 旁证）；
- 未改 `registry/criterion_counterexamples.yaml`（该条目的 `blocked_hint`
  `"失败但未保留 last_valid_result_ref"` 逐字未变，登记**仍有效**且**现在才是真的**——
  `criterion_effectiveness_guard` 实测 `RESULT: PASS（0 violations）`）；
- 未更新 `reports/phase1_gap_register.md`（共享台账，留给主理人登记 `G-43`/`G-45` 的关闭）。

---

## ⑤ 复现入口（最小）

```sh
cd /Users/gaza/Developer/InvestSigh/.worktrees/ws-degrade-contract/system
PY=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python

# 判据两向对照（in-repo，确定性，无需手工造数据）
$PY -m pytest tests/injection/test_wiring_guards.py -q -p no:cacheprovider
$PY -m pytest tests/daily/test_daily_run.py -q -p no:cacheprovider

# 门禁（与基线一致：唯一非零 traceback.py 为既有真源红）
cd .. && $PY system/scripts/ops/run_all_gates.py --timeout 30
sh system/scripts/ops/pre-commit.sh
```

`/tmp/wsdc/` 下的对拍脚本（`_case_probe.py` / `_e2e.py` / `_all_evidence.sh`，基线写死
`BASE=d5a37f8`）与原始输出（`evidence.log`）为**本轮实测的一次性工具**；
上述 in-repo 用例是它们的**可复跑版本**（同数据、同断言）。
