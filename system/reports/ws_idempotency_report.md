# ws/idempotency 报告：编排层「重复落库」的行幂等修复

> 分支 `ws/idempotency`（基点 `main` = `960634d`）· 工作树 `/Users/gaza/Developer/InvestSigh/.worktrees/ws-idempotency`
> 缺陷来源：批次 10 独立审计（在副本上重跑 `run_daily`，同一 `claim_id`（AMD）累积到 6 行）。
> 范围严格限于任务 ①~③（claim 写路径行幂等键 / tasks↔claims 幂等口径 / 有判别力的正反用例）。

---

## ① 做了什么

### 1.1 设计出处（逐字，先读后写）

任务要求的「**②行幂等键 = `(source_id, quote_hash)`**」逐字取自 `Ch9 §3.5`（文件
`09_数据与实现约束/09_需求拆解与实现方案_v1.md:779`，表「模块输入输出契约」第 ② 行）：

> | 阶段 | 输入 | 输出 | 幂等键 | 失败处理 | 依赖 |
> |---|---|---|---|---|---|
> | **② 核验** | 原始物 | `claims`（含定位、主张性质）+ `claim_propagation` | (`source_id`, `quote_hash`) | 无法定位 → 保留待核验任务 | ① |

### 1.2 实现落点（`文件:行号`）

| 落点 | 内容 |
|---|---|
| `system/scripts/guard/executor.py:42` | `from schema.store import append_records, read_records`（`read_records` 在守卫的 `ALLOWED_IMPORTS` 白名单内：`schema.store`） |
| `system/scripts/guard/executor.py:90` | 新增 `STATUS_SKIPPED = "skipped"`（幂等命中的**显式**状态） |
| `system/scripts/guard/executor.py:108` | 新增 `NOTE_DUPLICATE_CLAIM = "DUPLICATE_CLAIM_SKIPPED"`（`G-03`/`R-03`：命中带 note，不静默） |
| `system/scripts/guard/executor.py:140` | 新增 `_existing_claim_keys(root) -> set[tuple[str, str]]`：**单遍**读 `facts/claims.jsonl` 建 `(source_id, quote_hash)` 集合（`P-01`，不 O(n²)） |
| `system/scripts/guard/executor.py:246-254` | `process_external_text` 写库前的**行幂等闸门**：`if persist and (source_id, quote_hash) in _existing_claim_keys(root_path): return IngestResult(..., status=STATUS_SKIPPED, note=NOTE_DUPLICATE_CLAIM)` |
| `system/scripts/orchestrate/ingest_step.py:52` | 导入 `STATUS_SKIPPED` |
| `system/scripts/orchestrate/ingest_step.py:243-249` | 采集层消费 `skipped`：**不是降级**、对象引用仍入 `produced`（避免正常幂等重跑撞 `G1-05`「空执行」） |

### 1.3 设计要点

- **复用既有范式，不新造语义**：`_existing_claim_keys` 的写法（读全表一次 → 集合 → `in`）与
  `scripts/ingest/real_collector.py::_existing_claim_ids`、`scripts/graph/propagate.py::_idempotency_keys` **同源**；
  差异仅在**键的组成**——设计把阶段②的键逐字定为 `(source_id, quote_hash)`，此处按**二元组**建键
  （比 `claim_id` 里的 `quote_hash[:12]` 截断更强，无截断碰撞面）。
- **只新增判定，不改既有语义**：既有 `ok` / `degraded` / `blocked` 的全部分支逐字未动；
  新增的 `skipped` 是**纯新增**取值，只用于**新增的**幂等分支。`IngestResult` 的**字段集合未变**
  （不新增字段），`process_raw_file` / `process_external_text` 的签名、异常契约不变。
  `persist=False`（纯标注/预演）路径**不做**幂等判定，其「返回 `ok` + `claim_id`、不写库」语义逐字不变。
- **闸门位置正确性（关键）**：行幂等键 `(source_id, quote_hash)` 是**阶段②claim 创建**的幂等键，
  它**不能**下沉到存储层——因为 `scripts/claim/transition.py` 会**追加同一 claim 的新版本行**
  （同 `source_id`、同 `quote_hash`、仅 `status`/`recorded_seq` 变化）。若在 `append_records` 层按
  `(source_id, quote_hash)` 去重，**状态迁移会被误杀**。故闸门只放在**摄入写路径**（本缺陷点），
  与 `real_collector.py` 的现有幂等**同一层**、同一键。这一点是本修复的**结构性约束**，已核。
- **`G-03` 可见性**：命中返回 `status="skipped"` + `note="DUPLICATE_CLAIM_SKIPPED"`（**不静默**），
  采集层据 `skipped` **显式**分支处理。

### 1.4 ② tasks 与 claims 的幂等口径对比

| 项 | `tasks` | `claims` |
|---|---|---|
| 键字段 | **显式列** `idempotency_key`（`schema.models.Task.idempotency_key`） | 由 `(source_id, quote_hash)` **派生** `claim_id = claim-<source_id>-<quote_hash[:12]>` |
| 键构造 | 多种、按 `task_type`：`recheck::<ref>::<target>`（`graph/propagate.py:178`）、`<task_type>::<gap_id或claim_id>`（`tasks/gap_to_task.idempotency_key`）、`check::check_<date>_<scope>`（`pipeline.py::_write_check_record`） | 阶段②设计键 = `(source_id, quote_hash)`（`Ch9 §3.5`） |
| 设计锚点 | `Ch1 §C.3` / `Ch9 §N9.1-26` / `Ch8 §F.1` | `Ch9 §3.5` 阶段② |
| 写入去重口 | 各写者各自去重：`propagate._idempotency_keys`、`daily/idempotency.py::append_deduped`、`gap_to_task.IdempotentTaskQueue` | **修复前**：仅 `real_collector.py` 内；**修复后**：`guard/executor.py` 摄入写路径 |
| 后端校验 | `daily/idempotency.py::check_daily_idempotency`（对 events/recommendations 查重复键） | 无独立守卫（本次未新增，见 ④） |
| **强度（命中即跳过）** | **一致**：同键 → 跳过 | **修复后一致**：同 `(source_id, quote_hash)` → 跳过 |

**结论**：两者键的**格式**不同（这是**设计使然**——分别是「任务」与「主张」两类对象，键由对应章节各自定义，不可互换，
`R-04`），但**幂等强度已对齐**：都是「同业务键 ⇒ 跳过追加」。修复前的不一致**不在键格式**，而在
**claims 的写路径缺去重口**（真写库路径 `guard/executor` 无闸门，去重只藏在 `real_collector` 内部）；
本次把闸门补到 claims 的**真实写路径**上，即完成对齐。**不能**把两表键统一成同一格式——它们是不同对象的业务键，`Ch9 §3.5` 逐阶段各给一套。

---

## ② 怎么验证的（原样命令 + 原样输出 + 退出码）

> 全部在**工作树内**执行；写入型探测一律在**副本**（fixture 的 `code_root` / `/tmp` 拷贝）上做。
> 只跑相关子集（`tests/injection`、`tests/claim`），遵守 `V-08`（不跑全量）。

### 2.1 新增用例（工作树内，幂等正/反 + 端到端重跑）

```sh
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_idempotency_rows.py -q
......                                                                   [100%]
6 passed in 11.18s
EXIT=0
```

### 2.2 要求子集：`tests/injection` 与 `tests/claim`（证明**没误伤守卫**）

```sh
$ sh system/scripts/ops/run_pytest.sh tests/claim -q
........................                                                 [100%]
24 passed in 31.97s
EXIT=0
```
```sh
$ sh system/scripts/ops/run_pytest.sh tests/injection -q
=========================== short test summary info ============================
FAILED tests/injection/test_wiring_guards.py::test_unimplemented_criteria_are_listed_as_notes
1 failed, 135 passed in 217.36s (0:03:37)
EXIT=1
```
```sh
$ sh system/scripts/ops/run_pytest.sh tests/claim tests/injection -q
1 failed, 159 passed in 225.56s (0:03:45)
EXIT=1
```
> 无 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 告警（`grep -c` = 0）。

### 2.3 ★ 那 1 条红**不是本次改动引入**（在 HEAD 纯净树上复现）

`test_unimplemented_criteria_are_listed_as_notes` 是 **`stage_gate` 用例**，与 `executor.py` / `ingest_step.py`
无关。用 `git archive HEAD` 导出**纯净树**（无我的改动、无我的新用例）复跑，**同样红**：

```sh
$ git archive HEAD system | tar -x -C /tmp/idem_pristine
$ grep -c "_existing_claim_keys" /tmp/idem_pristine/system/scripts/guard/executor.py
0                                     # 纯净树里没有我的幂等代码
$ cd /tmp/idem_pristine/system && python -m pytest \
    "tests/injection/test_wiring_guards.py::test_unimplemented_criteria_are_listed_as_notes" -q
E           AssertionError: assert '判据台账[daily_run]' in '== stage_gate[all] ==\n  scanned core_chain...
FAILED tests/injection/test_wiring_guards.py::test_unimplemented_criteria_are_listed_as_notes
1 failed in 0.22s
```
→ **判定：与本次改动无关的既有红**（`stage_gate` 阶段台账输出缺 `daily_run`/`expansion` 台账行）。

### 2.4 ★ (a) 重跑不新增的 `wc -l` 前后对比

用例 `test_same_source_same_quote_hash_does_not_append`（见 `test_idempotency_rows.py`）实测：
首次 1 行 → 重跑后仍 1 行（`1 -> 1`，用例绿）；
加固用例 `test_rerun_many_times_stays_single_row`：连续 5 次 → `[1, 1, 1, 1, 1]`。

### 2.5 ★ (b) 反向对照：不同源 / 不同文本 → **必须新增行**

用例 `test_same_source_different_quote_hash_appends`（同源不同文本 → 2 行）与
`test_different_source_id_same_text_appends`（不同源同文本 → 2 行）均绿 —— 证明闸门**不是**「一律不写」。

### 2.6 ★ 复原对照：去掉幂等判断 → (a) 变红（原样输出）

在**副本** `/tmp/idem_control`（我的代码 + 我的用例，**仅删掉 `executor.py:246-254` 的闸门**）：

```sh
$ # 先确认副本【带】闸门时是绿的
$ cd /tmp/idem_control/system && python -m pytest tests/injection/test_idempotency_rows.py -q
......                                                                   [100%]
6 passed in 0.46s

$ # 仅删掉幂等闸门后，同一测试文件
$ cd /tmp/idem_control/system && python -m pytest tests/injection/test_idempotency_rows.py -q
FF...F                                                                   [100%]
=================================== FAILURES ===================================
_______________ test_same_source_same_quote_hash_does_not_append _______________
>       assert after_second == after_first, (
            f"★ 同源同 quote_hash 重跑**不得**新增行（缺陷复现点）：{after_first} -> {after_second}"
        )
E       AssertionError: ★ 同源同 quote_hash 重跑**不得**新增行（缺陷复现点）：1 -> 2
E       assert 2 == 1
____________________ test_rerun_many_times_stays_single_row ____________________
>       assert counts == [1, 1, 1, 1, 1], f"重跑 5 次应恒为 1 行，实得 {counts}"
E       AssertionError: 重跑 5 次应恒为 1 行，实得 [1, 2, 3, 4, 5]      # ← 审计「累积到 6 行」的同型
_____________ test_ingest_handler_rerun_is_idempotent_not_degraded _____________
>       assert n2 == n1, f"★ 重跑不得新增行：{n1} -> {n2}"
E       AssertionError: ★ 重跑不得新增行：1 -> 2
=========================== short test summary info ============================
FAILED tests/injection/test_idempotency_rows.py::test_same_source_same_quote_hash_does_not_append
FAILED tests/injection/test_idempotency_rows.py::test_rerun_many_times_stays_single_row
FAILED tests/injection/test_idempotency_rows.py::test_ingest_handler_rerun_is_idempotent_not_degraded
3 failed, 3 passed in 0.64s
EXIT=1
```
→ **判别力成立**：(a) 三项去掉闸门即红，加上即绿（`G-16`：无恒真断言）。

### 2.7 pre-commit（含 `injection_guard` 证明没违反能力白名单）

```sh
$ sh system/scripts/ops/pre-commit.sh
pre-commit → injection_guard
  scanned import_outside_allowlist: 0     # executor.py 只在白名单内 import（schema.store）
  scanned dunder_outside_allowlist: 0
RESULT: PASS（0 violations）
...
pre-commit ✓ 全部门禁放行
EXIT=0
```

### 2.8 真仓库真源**零污染**

```sh
$ git status --short system/facts
                             # 空 → 零污染
$ wc -l system/facts/{claims,dependency_edges,companies,tasks,baselines,recommendations}.jsonl
      5 system/facts/claims.jsonl
      3 system/facts/dependency_edges.jsonl
      2 system/facts/companies.jsonl
      3 system/facts/tasks.jsonl
      1 system/facts/baselines.jsonl
      1 system/facts/recommendations.jsonl
```
（与任务描述的 5/3/2/3/1/1 一致；未变。）

---

## ③ 结果

- **①** 完成：`(source_id, quote_hash)` 行幂等闸门落在 claims 的**真实写路径**（`guard/executor.py`），
  命中 → `status="skipped"` + `note="DUPLICATE_CLAIM_SKIPPED"`（`G-03` 可见），采集层显式消费。
- **②** 完成：`tasks`（显式 `idempotency_key`）与 `claims`（`(source_id, quote_hash)`）键格式**按设计不同**，
  幂等**强度已对齐**（同键 ⇒ 跳过）；对齐点 = 把去重口补到 claims 的写路径（见 1.4）。
- **③** 完成：正（同源同文本 → 不增）、反（不同源/不同文本 → 增）、端到端重跑、复原对照四组用例齐备且有判别力。
- **测试**：新增 `tests/injection/test_idempotency_rows.py`（6 passed）；`tests/claim` 24 passed（EXIT=0）；
  `tests/injection` 135 passed / 1 failed（该 failure 经纯净树复现，**既有**、与本次无关）。
- **门禁**：`pre-commit.sh` 全绿（含 `injection_guard` import 白名单 0 违例）。
- **真源**：零污染（`git status --short system/facts` 空 + 6 表行数不变）。

---

## ④ 诚实登记的残留 / 不确定项

1. **`skipped` 是新增状态取值 —— 一处需要主理人/审计知悉的判读**：任务书要求
   ①「返回**跳过**而不是写入」且「调用方看得见」，②「返回值形态、状态机一律不变」。
   两者在字面上有张力。本实现的取舍是：**不新增 `IngestResult` 字段**（守住「返回值**形态**不变」），
   而**新增一个状态取值** `skipped`（新增取值，用来满足「返回跳过而不是写入」+ `G-03` 可见）。
   **既有 `ok`/`degraded`/`blocked` 三分支逐字未动**。若审计认为「状态机不变」应严格到**取值域**也不增，
   请裁定：替代方案是保留 `ok` 而仅以 `note="DUPLICATE_CLAIM_SKIPPED"` 标注命中
   （代价：`status` 变成「写入 / 跳过」不可区分，与「返回跳过而不是写入」相悖）。**此处不自裁**（`R-04`）。
2. **未新增 claims 的重复键守卫**：`daily/idempotency.py::check_daily_idempotency` 只覆盖 `events`/`recommendations`；
   任务 ② 未要求为 claims 加守卫，且新增守卫须改 `scripts/checks/**`（**本单禁改**）。本次以「写路径闸门」
   保证「不再产出重复行」，但**存量**（若某副本/历史真源已有重复行）**无自动检测**。**未新增，如实登记**。
3. **`ingest_step` 把 `skipped` 计入 `produced` 的语义判断**：为使**正常幂等重跑**不被
   `G1-05`「报 ok 但 produced 为空（空执行）」误判为 blocked，命中对象仍入 `produced`。
   `produced` 语义因此扩为「本步负责保障存在的对象引用」。若审计认为 `produced` 应严格限于「本轮新写入」，
   则该判断需上调裁定（代价：重跑恒落 `G1-05` 空执行 → blocked）。**如实登记，非自裁**。
4. **性能形态**：`_existing_claim_keys` 每次 `process_external_text` 调用各读一次 `claims.jsonl`
   （O(n) 建集合；批次内 m 个文件即 m 次读）。这与既有 `real_collector` / `propagate` / `transition`
   的「每次操作读全表一次」**同一量级**，非 O(n²)。大表下若需进一步降，须改签名预索引，
   而签名变更触任务①「签名不变」约束 —— **本次不做**。
5. **未跑的验证**：按 `V-01`/`V-08` 只跑相关子集，**未跑全量** `verify.py --batch all`；
   `tests/guards`、`tests/graph`、`tests/daily` 等**未跑**（不在本单相关面）。`stage_gate` 的既有红
   **不在本单范围**，未处理。

---

## ⑤ 裁定与回修（第二轮）

主理人两条裁定 + 回修。回修**只动我自己的两个文件**（`scripts/orchestrate/pipeline.py` 属共享契约，**未动**）。

### 5.1 裁定 1：**允许** `executor.STATUS_SKIPPED` —— 采纳，`executor.py` 未改

理由（记录在案）：消费侧构造上 fail-safe —— `ingest_step` 的分支是
`if OK / elif SKIPPED / else: degraded=True`，未知取值落 `degraded`（"不算成功"一侧），
故新增取值**不可能凭沉默取得成功语义**。命名空间已注明：`executor` 的 `skipped` =
**对象粒度·行幂等命中**；`pipeline.STATUS_SKIPPED` = **整步被 resume 跳过**（不同粒度，勿混）。

### 5.2 裁定 2：**驳回**"命中对象计入 `produced`" —— 已按契约回修

- `scripts/orchestrate/ingest_step.py:244-249`：幂等分支由 `produced.append(...)` 改为
  `skipped.append(...)`（独立列表）；
- `:256`：`return StepOutcome(produced=produced, skipped=skipped, degraded=degraded, signals_emitted=0)`；
- `:197-201` docstring **逐字改正**（不再称"计入 produced"）。
- ★ **未**把命中**同时**放进 `produced` 与 `skipped`（那等于没改）。

### 5.3 合并 main

```
$ git merge main
a29ec90 (HEAD -> ws/idempotency, main) merge ws/idempotency: claim 写路径补行幂等键 ...
```
（快进；`StepOutcome.skipped` / `StepResult.skipped` / `G1-05` 判据修正由 main 的 `4f95c3d` 带入。）

### 5.4 新增/更新用例（三组，缺一不可）

**(a) 双跑端到端对照（`G-B10-07` 正解观测）** `test_run_daily_twice_produced_then_skipped`

```
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_idempotency_rows.py -q -s
[(a) round1] produced=['claim-inbox-2026-09-15_amd_q2.txt-7ccf4b51f693', 'claim-inbox-2026-09-16_nvda_q2.txt-ea86884f9f68'] skipped=[] claims_lines=2
[(a) round2] produced=[] skipped=['claim-inbox-2026-09-15_amd_q2.txt-7ccf4b51f693', 'claim-inbox-2026-09-16_nvda_q2.txt-ea86884f9f68'] claims_lines=2
9 passed in 12.52s
```
→ 两轮观测**不同**（`produced` N→0、`skipped` 0→N、`claims_lines` 不变）—— 正是"幂等 vs 非幂等"的判别式本体。

**(b) `G1-05` 修正判据的**双向**对照**
- `test_g1_05_still_flags_truly_empty_step`：桩 `produced=[] 且 skipped=[]` → **仍判**"空执行"违例（判据强度**未**削弱）；
- `test_g1_05_does_not_flag_idempotent_rerun`：桩 `produced=[] 但 skipped=["claim-x"]` → **不判**违例（幂等重跑不再误报）。
（二者含在上面同一 `9 passed` 内。）

**(c) 复原对照（去闸门，副本 `/tmp/idem_control2` 内）**

```
[(a) round1] produced=[2 claims] skipped=[] claims_lines=2
[(a) round2] produced=['claim-inbox-2026-09-15_amd_q2.txt-7ccf4b51f693', 'claim-inbox-2026-09-16_nvda_q2.txt-ea86884f9f68'] skipped=[] claims_lines=4
FAILED tests/injection/test_idempotency_rows.py::test_same_source_same_quote_hash_does_not_append
FAILED tests/injection/test_idempotency_rows.py::test_rerun_many_times_stays_single_row
FAILED tests/injection/test_idempotency_rows.py::test_ingest_handler_rerun_is_idempotent_not_degraded
FAILED tests/injection/test_idempotency_rows.py::test_run_daily_twice_produced_then_skipped
4 failed, 5 passed in 0.66s   (EXIT=1)
```
→ 去掉闸门后 round2 `produced` 非空、`skipped` 空（回到非幂等），(a) 用例**变红** —— 判别力成立。

### 5.5 验证（其他目录无受影响）

| 目录 | 结果 | 退出码 |
|---|---|---|
| `tests/injection` | **139 passed** | 0 |
| `tests/compute`（`test_step_wiring.py` 钉 `produced` 语义） | **95 passed** | 0 |
| `tests/daily` | **43 passed** | 0 |
| `tests/guards`（`test_exit_code_contract` 含 `pipeline`） | **56 passed** | 0 |

- ★ `tests/orchestrate/` **不存在**；编排器面由 `tests/injection/test_chain_steps_wiring.py`
  （step 1–6 接线 / `StepOutcome` / `G1-05`）与 `tests/compute/test_step_wiring.py` 覆盖，二者均在上述已跑目录内。
- 无 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 告警。
- 合并后 `tests/injection` 的 `stage_gate` **既有红已消失**（139 passed 全绿）。

### 5.6 pre-commit 与真源零污染

```
$ sh system/scripts/ops/pre-commit.sh
pre-commit ✓ 全部门禁放行          (EXIT=0，无需 --no-verify)

$ git status --short system/facts system/derived
                                   (空 = 零污染)
$ git diff HEAD --quiet -- system/facts system/derived && echo FACTS_MATCHES_HEAD=yes
FACTS_MATCHES_HEAD=yes
```
（注：工作树 `facts/tasks.jsonl` 现为 **4 行** —— 这是 main 上其它工作流合并带来的**已提交**状态，
**非本次写入**；本轮 `facts/`、`derived/` 与 HEAD **逐字一致**。）

### 5.7 本轮提交

- `d9fc241` 回修（`ingest_step.py` + `tests/injection/test_idempotency_rows.py`）；
- 其后一笔 `docs(report)` 更新本节（哈希见 `git log`）。

