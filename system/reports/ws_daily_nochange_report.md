# `ws/daily-nochange-exit` 交付报告 —— 收 `G1-04` 与「无变化日」的语义冲突

> 一句话：`G1-04` 的「终态 `done` ⇒ 必须有产出」是一刀切，而**设计正文明确规定了"无变化日"这个合法例外**
> （「仅变化时产信号，**无变化写 `check_record`**」）。本单把这条**换成可判定的正向标记**
> （`check_record.changed is False`），**判别力不放松**：`changed` 不是 `False`、或压根没有 `check_record`，
> **照样红**。

- **工作树**：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-daily-nochange`
- **分支**：`ws/daily-nochange-exit`
- **基点**：`4468da5`（`main`；开工时 `git merge main` 已并，本分支当时与 `main` 齐平）
- **`$PY`** = `/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`
- **纪律声明**：未触碰真仓库 `system/facts/`、`system/derived/`、`system/state.json`；
  `system/rules/**`（0444）未改；实验在**副本**（`/tmp/wsnc/**`）中进行；
  提交 `pre-commit` **不跳过**（**禁 `--no-verify`**）。
- ★ **并发流数披露**（团队口径：报告耗时/资源数据必须写当时的并发流数）：
  本报告所有 pytest 数据是在**宿主同时有 ≥3 条 pytest 流**的情况下采集的
  （实测依据见 §④-2(b)：同一时刻 3 个工作树各有刚写过锁的会话）。
  故**本文的耗时数字不可与其他并发窗口下的数字直接比较**；
  `tests/daily` 整目录与 `tests/guards` **因共享删除预算被打穿而未跑成**（§④-2）。

---

## ① 改了什么

**唯一改动文件**：`system/scripts/tasks/gap_to_task.py`（`67 insertions / 7 deletions`）。

### 1.1 设计正文（逐字复核过，非转录）

| 出处 | 原文 |
|---|---|
| `02_已确认的投资规则/01_需求拆解.md:149`（`C123-2`） | 「**更新 ≠ 信号**：每日维护（采集/核验/复查），仅变化时产信号，**无变化写 `check_record`**」 |
| `07_产业链传导与股票建议/01_需求拆解.md:51`（`N7.3-04`） | 「**无变化日不产生新信号，仅生成核查记录**」 |
| `08_产品入口与每日运行/02_实现方案.md:78` | 「每日运行**必写** `check_record`（**无论有无变化**）」 |
| `08_产品入口与每日运行/02_实现方案.md:76`（★ 本单新发现，更强的旁证） | 第 7 步发布「每日运行在 `judgment_change != False` 时调用；……**无变化时不触发**（反 KPI）」 |

★ **最后一条是本单额外找到的硬证据**：设计自己写明"**无变化时不触发**发布" ⇒
无变化日**第 7 步本来就不该有产出** ⇒ 该日 `output_refs` 为空是**结构性的**，不是疏漏。

### 1.2 实现侧的冲突点（改前）

```
scripts/tasks/gap_to_task.py:43    TERMINAL_STATES = ("done",)      ← 只含 done
scripts/tasks/gap_to_task.py:190   if status in TERMINAL_STATES and not (row.get("output_refs") or []):
                                       → 判 G1-04「空执行」
```

⇒ 无变化日（设计**合法**）当天长成 `done + output_refs=[]` ⇒ **被误报为空执行**。

★ **先排除一个不存在的假阳性**（免得后人误判）：`TERMINAL_STATES` **只含 `done`、不含 `failed`**
⇒ **失败行不会被这条误判**（本单有专门用例 `test_failed_row_with_empty_output_is_not_flagged` 钉住）。

### 1.3 判决条件（team-lead 批准的形态）

> `done` 且 `output_refs` 为空 ⇒ **合法当且仅当** `check_record` **存在**
> 且 `check_record.changed is False`（无变化日）；否则仍按 `G1-04` 判空执行。

落成新函数（`gap_to_task.py`）：

```python
def is_no_change_day(row: Mapping[str, Any]) -> bool:
    record = row.get("check_record")
    if not isinstance(record, Mapping):
        return False
    return record.get("changed") is False        # ← 严格同一性，不是真值性
```

★ **为什么必须是 `is False` 而不是 `not record.get("changed")`**：
后者会把「**缺字段**」「`None`」「`0`」「`""`」**全部**当成"无变化" ⇒
同族缺陷（判据被一个**恒真的谓词**空转）会**从缺字段这一侧复发** —— 这正是 `G-43` 的教训。
本单有两条专门用例钉死这一点（缺 `changed` / `changed=None`）。

### 1.4 为什么这是"换判据"，不是"放松判据"（`R-06`）

| 要求 | 怎么满足的 |
|---|---|
| ① 穷尽两态、不靠名单 | 每条 `done` 行**必然**落入「合法 / 违例」之一：豁免只看**字段取值**，不看任何 `task_id`（有用例 `test_exemption_is_not_id_based` 用一个**从未出现过的** id 验证） |
| ② 判别力不放松 | `changed` 不是 `False`、或没有 `check_record`、或 `check_record` 不是对象 ⇒ **exit 1**（反例 A–E 五条） |
| ③ 不新增真源（`G-06`） | 只用既有 `check_record.changed`，由 `pipeline._write_check_record()` 真实写出，**没有第二套形状** |

### 1.5 豁免**可见**（`G-43` 的教训，本单主动加的）

新增**配对计数**：

```
report.scanned["done_empty_output_rows"] = …   # 落进"done + 空产出"这个形状的行数
report.scanned["no_change_day_exempt"]   = …   # 其中被判为合法无变化日的行数
```

★ 理由与 `G-43` 完全同源：**只看"豁免 0 条"无法区分「没有这类行」与「判据恒假」**。
两颗计数**成对**报出后，"判据在真数据上是否真的被走通过"一眼可辨。

---

## ② 证据

### 2.1 改前 / 改后对拍（受控输入，真 CLI + 真退出码）

命令（探针在仓库外 `/tmp/wsnc/probe.py`，用 `4468da5` 版与工作树版**同一个 `_common.py`**）：

```
$ $PY /tmp/wsnc/probe.py <case> <before|after>
```

| case | 输入（`status` / `output_refs` / `check_record.changed`） | 期望 | **before** | **after** |
|---|---|---|---|---|
| `real` | 本工作树真源原样（4 行，无 `done`） | 0 | exit 0 | exit 0 |
| **`no_change`（正例）** | `done` / `[]` / `False` | **0** | **exit 1** ❌ 误报 | **exit 0** ✅ |
| **`cc_A`（反例 A）** | `done` / `[]` / `True` | **1** | exit 1 | **exit 1** ✅ |
| **`cc_B`（反例 B）** | `done` / `[]` / **无 `check_record`** | **1** | exit 1 | **exit 1** ✅ |
| `cc_C`（反例 C） | `done` / `[]` / **缺 `changed` 字段** | 1 | exit 1 | exit 1 ✅ |
| `changed_null`（反例 D） | `done` / `[]` / `None` | 1 | exit 1 | exit 1 ✅ |
| `normal_done`（对照） | `done` / `["obj-a","obj-b"]` / `True` | 0 | exit 0 | exit 0 ✅ |
| `failed_row`（对照） | `failed` / `[]` / `False` | 0 | exit 0 | exit 0 ✅（只含 `done`） |
| `mixed`（判别力） | 合法无变化日 **+** 反例 A | 1 条违例 | exit 1，**2 条违例** ❌ | exit 1，**1 条违例** ✅ |

**三组必需证据的原始输出**：

```
=== case=no_change mode=after ===
--- facts/tasks.jsonl（受控输入）---
  status='done' output_refs=[] check_record.changed=False
--- $ python scripts/tasks/gap_to_task.py <root> --no-report
--- exit=0
== gap_to_task.py ==
  scanned done_empty_output_rows: 1
  scanned no_change_day_exempt: 1
  scanned tasks: 1
  scanned terminal_states: 1
RESULT: PASS（0 violations）

=== case=cc_A mode=after ===
--- facts/tasks.jsonl（受控输入）---
  status='done' output_refs=[] check_record.changed=True
--- $ python scripts/tasks/gap_to_task.py <root> --no-report
--- exit=1
== gap_to_task.py ==
  scanned done_empty_output_rows: 1
  scanned no_change_day_exempt: 0
  scanned tasks: 1
  scanned terminal_states: 1
  [FATAL] G1-04 @ facts/tasks.jsonl:0 — task_check_2026-09-16_full 状态为终态 'done' 但 output_refs 为空，且不满足无变化日豁免（需 `check_record` 存在且 `check_record.changed is False`）（空执行：报了完成却没有产出）
RESULT: FAIL（1 violations）

=== case=cc_B mode=after ===
--- facts/tasks.jsonl（受控输入）---
  status='done' output_refs=[] check_record.changed=None      ← `check_record` 整体缺失；探针打印为 None
--- $ python scripts/tasks/gap_to_task.py <root> --no-report
--- exit=1
== gap_to_task.py ==
  scanned done_empty_output_rows: 1
  scanned no_change_day_exempt: 0
  scanned tasks: 1
  [FATAL] G1-04 @ facts/tasks.jsonl:0 — task_check_2026-09-16_full 状态为终态 'done' 但 output_refs 为空，且不满足无变化日豁免（需 `check_record` 存在且 `check_record.changed is False`）（空执行：报了完成却没有产出）
RESULT: FAIL（1 violations）
```

**改前（同一份受控输入、`4468da5` 版代码，逐字输出）**：

```
=== case=no_change mode=before ===
--- facts/tasks.jsonl（受控输入）---
  status='done' output_refs=[] check_record.changed=False
--- $ python scripts/tasks/gap_to_task.py <root> --no-report
--- exit=1
== gap_to_task.py ==
  scanned tasks: 1
  scanned terminal_states: 1
  [FATAL] G1-04 @ facts/tasks.jsonl:0 — task_check_2026-09-16_full 状态为终态 'done' 但 output_refs 为空（空执行：报了完成却没有产出）
RESULT: FAIL（1 violations）      ← ★ 合法的无变化日被误报成违例（本单要修的缺陷）
```

**`mixed` 的判别力对照（改前把合法行为也一起误报，这是本单要修的）**：

```
=== case=mixed mode=before ===  exit=1，2 条违例
== gap_to_task.py ==
  scanned tasks: 2
  scanned terminal_states: 1
  [FATAL] G1-04 @ facts/tasks.jsonl:0 — task_ok_nochange 状态为终态 'done' 但 output_refs 为空（空执行：报了完成却没有产出）   ← 合法无变化日，被误报
  [FATAL] G1-04 @ facts/tasks.jsonl:0 — task_bad 状态为终态 'done' 但 output_refs 为空（空执行：报了完成却没有产出）           ← 真违例
RESULT: FAIL（2 violations）

=== case=mixed mode=after ===   exit=1，1 条违例
== gap_to_task.py ==
  scanned done_empty_output_rows: 2
  scanned no_change_day_exempt: 1
  scanned tasks: 2
  scanned terminal_states: 1
  [FATAL] G1-04 @ facts/tasks.jsonl:0 — task_bad 状态为终态 'done' 但 output_refs 为空，且不满足无变化日豁免（需 `check_record` 存在且 `check_record.changed is False`）（空执行：报了完成却没有产出）
RESULT: FAIL（1 violations）      ← 只剩真违例
```

### 2.2 测试：`tests/daily/test_no_change_day.py`（新增，12 例）

**改后（工作树版）**：

```
$ sh system/scripts/ops/run_pytest.sh tests/daily/test_no_change_day.py -q
............                                                             [100%]
12 passed in 59.92s
```

**改前（把 `gap_to_task.py` 用 `git stash` 换回 `4468da5` 版，**同一个测试文件**，不改一行）**：

```
$ git stash push -- system/scripts/tasks/gap_to_task.py
$ sh system/scripts/ops/run_pytest.sh tests/daily/test_no_change_day.py -q
8 failed, 4 passed in 10.91s
FAILED …::test_no_change_day_done_with_empty_output_is_legal
FAILED …::test_no_change_day_is_counted_so_the_exemption_is_not_vacuous
FAILED …::test_no_rows_of_that_shape_means_both_counters_are_zero
FAILED …::test_done_with_empty_output_and_no_check_record_is_a_violation
FAILED …::test_changed_field_missing_does_not_exempt
FAILED …::test_changed_none_does_not_exempt
FAILED …::test_mixed_rows_flag_only_the_real_violation
FAILED …::test_exemption_is_not_id_based
$ git stash pop   → 与备份逐字一致（diff -q 无输出）
```

★ **如实区分这两类失败（别混为一谈）**：

| 用例 | 在改前代码上为何红 | 性质 |
|---|---|---|
| `test_no_change_day_done_with_empty_output_is_legal`<br>`…_is_counted_so_the_exemption_is_not_vacuous`<br>`…_both_counters_are_zero`<br>`…_flag_only_the_real_violation`<br>`…_is_not_id_based` | 改前代码**真的把合法无变化日判成 exit 1** | **承重反例**（证明缺陷存在、修复有效） |
| `test_done_with_empty_output_and_no_check_record_is_a_violation`<br>`test_changed_field_missing_does_not_exempt`<br>`test_changed_none_does_not_exempt` | 改前代码**本来就拦得住**这三条；红是因为它们断言了**新文案**（"不满足无变化日豁免"）与新计数 | **文案/结构回归护栏**，**不**构成"改前漏拦"的证据 |

★ **夹具纪律**（`G-43`/`G-45` 的教训）：正例与反例 A **走真实写路径**
（`conftest.write_check_records` → `Pipeline._write_check_record`），
即"无变化日"（`judgment_change={}` ⇒ `changed=False`）与"有变化却无产出"
（`judgment_change={"moat": True}` ⇒ `changed=True`）两种形状由**唯一写入方**产出。
**反例 B/C/D/E 只能手工构造**（真实写路径写不出"缺 `check_record` / 缺 `changed` / `changed=None` / 非对象"），
这一点已在测试文件 docstring 里**明说**。

### 2.3 真源实测（改动后）

```
$ $PY system/scripts/tasks/gap_to_task.py system/
== gap_to_task.py ==
  scanned done_empty_output_rows: 0
  scanned no_change_day_exempt: 0
  scanned tasks: 4
  scanned terminal_states: 1
RESULT: PASS（0 violations）        exit=0
```

`done_empty_output_rows: 0` ⇒ 真源里**根本没有 `done` 行**（原因见 §④-1），所以豁免**尚未在真数据上被走通**
——两个计数**成对报出**正是为了让这一点**可见**（而不是伪装成"判据已验证"）。

### 2.4 全量门禁（`--timeout 30`，改动后）

```
$ $PY system/scripts/ops/run_all_gates.py --timeout 30
  conflict_scan.py                   exit=0        6.44s
  append_only_guard.py               exit=0        0.19s
  rules_lock_guard.py                exit=0        0.85s
  registry_schema_guard.py           exit=0        1.30s
  schema_sync_guard.py               exit=0        1.08s
  assert_gate_input.py               exit=0        0.37s
  freeze_guard.py                    exit=0        1.29s
  launch_guard.py                    exit=0        0.29s
  module_denylist.py                 exit=0        7.11s
  no_signal_day.py                   exit=0        0.16s
  no_placeholder_guard.py            exit=0       11.62s
  neutrality_check.py                exit=0        0.10s
  return_guard.py                    exit=0        0.19s
  anti_padding.py                    exit=0        1.31s
  gap_to_task.py                     exit=0        0.13s      ← 本单改的脚本本身
  traceback.py                       exit=1        0.42s      ← 唯一非零（既有 design-red）
  pipeline.py                        exit=0        0.30s
  stage_gate.py --stage prep         exit=0        1.59s
  injection_guard.py                 exit=0        1.48s
  verification_policy_guard.py       exit=0        0.39s
  shell_var_guard.py                 exit=0        0.39s
  graph_integrity_guard.py           exit=0        2.24s
  locator_check.py                   exit=0        1.84s
  criterion_effectiveness_guard.py   exit=0        4.83s
  非零计数                               1
```

与 `main` 基线**同为"非零计数 1"**，唯一红是 `traceback.py`
（`facts/recommendations.jsonl::rec-nvda-001` 缺四要素 —— 真实覆盖缺口，已被需求方接受为 design-red，
与本改动无交集：本单只碰 `system/scripts/tasks/gap_to_task.py`）。

### 2.5 回归分片（`tests/daily` 整目录 / `tests/guards`）—— **未能跑成，原因见 §④-2；本节省下的是可跑的替代证据**

**（a）跑不成的机器事实**（详见 §④-2）：宿主"批量删除守卫"被触发后，**任何** pytest 会话在启动阶段即
`INTERNALERROR → SystemExit(1)`，连单文件都进不去。**没有用任何环境变量绕过该闸门。**

**（b）替代证据：直接验「退出码契约」的三条性质**（不建任何 `copytree` 夹具）

`tests/guards/test_exit_code_contract.py` 对**每个**门禁断言三条：
干净输入 → `0`、`code_root` 缺失 → `2`、必报 `scanned`。该矩阵**从 `run_all_gates.py::GATES` 派生**
（单例真源，`G-28` 的根治）。我用**同一进程内入口** `run_checker(name, check, argv=[...])`
（即该测试所用的调用方式）对 `gap_to_task.py` 逐条验：

```
$ $PY /tmp/wsnc/contract.py
=== ① 干净输入（真源为空文件）→ 期望 0 ===
exit = 0
== gap_to_task.py ==
  scanned done_empty_output_rows: 0
  scanned no_change_day_exempt: 0
  scanned tasks: 0
  scanned terminal_states: 1
  note: NO_TASK_DATA：阶段① 真源为空；断言已就绪，阶段③/④ 起作用于真数据
RESULT: PASS（0 violations）
→ 0 ✅ 且报 scanned ✅

=== ①b 干净输入（真源 4 行原样）→ 期望 0 ===
exit = 0
  scanned done_empty_output_rows: 0
  scanned no_change_day_exempt: 0
  scanned tasks: 4
  scanned terminal_states: 1
RESULT: PASS（0 violations）
→ 0 ✅

=== ② code_root 不存在 → 期望 2 ===
exit = 2
[INPUT-ERROR] code_root 不存在: /tmp/wsnc/definitely-not-here
→ 2 ✅

=== ③ 注入违例（changed=True）→ 期望 1 ===
exit = 1
  scanned done_empty_output_rows: 1
  scanned no_change_day_exempt: 0
  [FATAL] G1-04 @ facts/tasks.jsonl:0 — t 状态为终态 'done' 但 output_refs 为空，且不满足无变化日豁免（…）
RESULT: FAIL（1 violations）
→ 1 ✅

★ 三条契约性质全部成立（且未建任何 copytree 夹具）
```

★ **顺带实测到一条既有的行为**（不是本单引入，但值得记）：`check()` 对
**`facts/tasks.jsonl` 文件缺失**抛 `FileNotFoundError` ⇒ `run_checker` 折叠成 **exit 2（输入异常）**；
故"干净输入"必须是**空文件**而不是"没有该文件"。这与 `§5.1 AC-04`/`N-2` 的口径一致
（输入异常必须与"通过"分开），**不是缺陷**，但写在这里免得后人踩。

**（c）静态排查：本改动**能**影响到哪些既有用例**（逐个核过，非推测）

| 候选 | 结论 |
|---|---|
| `tests/guards/test_exit_code_contract.py` | 断言的是**契约三条**（上文 (b) 已逐条直验）+ 从 `GATES` 派生 ⇒ 不受文案变化影响 |
| `tests/daily/test_idempotency.py:35` | 只 `from scripts.tasks.gap_to_task import idempotency_key` ⇒ **未碰**该函数 |
| `tests/graph/test_propagate_t12.py:131` | 注释提到 `G1-04`，断言的是"不重复建单"（幂等键）⇒ **未碰** |
| 全仓库 `Grep "gap_to_task|G1-04|空执行"` | **没有任何既有用例断言本门禁的违例文案** ⇒ 改文案（本单）不会打破既有断言 |

★ **如实标注**：(b)(c) 是**替代证据，不能代替** `tests/daily` 整目录与 `tests/guards` 的实跑。
**这两批仍是"未跑"，不是"已验证"**（`G-03`）。

---

## ③ 逐条对派单要求

| # | 要求 | 落点 | 证据 |
|---|---|---|---|
| 1 | 改成**可判定的正向标记**，不放松判据 | `gap_to_task.py::is_no_change_day` | §1.3/§1.4；反例 A–E 五条全 exit 1 |
| 2 | 正例：无变化日 ⇒ **exit 0** | 同上 | §2.1 `no_change`：exit 1 → **exit 0**；§2.2 用例 |
| 3 | 反例 A：`changed=True` ⇒ **exit 1** | 同上 | §2.1 `cc_A` 原始输出 exit=1 |
| 4 | 反例 B：缺 `check_record` ⇒ **exit 1** | 同上 | §2.1 `cc_B` 原始输出 exit=1 |
| 5 | 报告贴**真实输出 + 退出码** | 本文件 | §2.1–§2.4 全部为粘贴的原始 stdout（含 `exit=`） |
| 6 | 写明"这是把一刀切改成可判定条件，不是放松" | 本文件 + 代码 docstring | §1.4 三条 + `R-06 ①` |
| 7 | 点明 `TERMINAL_STATES` 只含 `done`（无"失败行误判"假阳性） | 本文件 + 用例 | §1.2 末段；`test_failed_row_with_empty_output_is_not_flagged` |
| 8 | 只 add 自己改的文件 | 见 §⑤ | `git status --short` 只列 3 个文件（1 改 + 1 新增测试 + 1 报告） |
| 9 | `pre-commit` 全绿、**禁 `--no-verify`** | — | 见 §⑤ 提交现场输出 |
| 10 | **回归分片**（`tests/daily` / `tests/guards` / injection 相关片） | — | ★ **未跑成**（宿主共享删除预算被打穿，§④-2）；替代证据见 §2.5，**如实登记为"未跑"而非"已验证"** |

---

## ④ 剩余不确定性与缺口（**如实报出**）

### ④-1 ★ 真源里根本没有 `done` 行 ⇒ 豁免**在真数据上走不通**（与 `T-18` 同源）

- **机器事实**：`system/facts/tasks.jsonl` 4 行 = 2 `queued`（recheck）+ 2 `failed`（check），
  **`done` 行 0 条**。原因是 `T-18`：`system/rules/pipeline.yaml` 的 step 7/8
  「既 `blocking: true` 又不首版实现」⇒ `run_daily` 恒 `blocked` ⇒ `status` 恒 `failed`。
- **后果**：本判据的**两态在真数据上都只有一态可走**（能走"违例"侧的前提也不成立——
  没有 `done` 行就没有 `G1-04` 形态）。**受限的是真数据的可用形态，不是判据的判别力**
  （§2.1 九例 + §2.2 正反两向都证了）。
- **两个计数成对报出**正是为这条服务的：`done_empty_output_rows: 0` + `no_change_day_exempt: 0`
  一眼可见"真数据还没走到这里"，**而不是**被读成"判据已通过"（`G-03`：无被检对象不得当成已核）。
- **不改**：`system/rules/pipeline.yaml` 是 0444 设计真相源 + 属需求方裁定（已由 team-lead 登记 `T-18`）。
- ★ **待 `T-18` 裁定后可在真数据上复验**：team-lead 已把 `T-18` 交需求方，推荐 = 首版**不把**
  `implemented_in_first_version: False` 的步计入 `blocking` 判定，**但必须**记 `gaps` + 标 `deferred_by_design`。
  **若采纳，真源就会开始出现 `done` 行**，届时本单的正例（无变化日）与反例 A（有变化却无产出）
  **都能在真数据上跑通**，本报告的"只能受控验证"这一限制随之解除。
  ⇒ 在此之前，**不许为了"真数据也绿"去改真源**（那正是 `G-03` 禁止的"用无对象冒充已验证"）。

### ④-2 ★ 环境阻塞（**未跑成**）：宿主"批量删除守卫"被触发 ⇒ 本会话内**任何** pytest 都进不去

**（a）机器事实**

```
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
  {"count":100113,"threshold":99999,"scope":"turn",
   "targets":["…/system/tests/.work/test_value_source_marks_suggested_baseline-11eda3c8"],"targetCount":1}

INTERNALERROR>   File "…/cli/vendor/shim/sitecustomize.py", line 826, in _exit_bulk_guard_control
INTERNALERROR>     raise SystemExit(1)
INTERNALERROR> SystemExit: 1
```

触发点：`tests/daily` 整目录跑到第 ~20 例时，夹具 `copytree`（每用例复制一份 `system/`，实测 ≈785 计数/例）
累积删除计数越过 `threshold: 99999` ⇒ 此后**连单个目标都被拒删** ⇒ 夹具 setup 集体 `E`；
再跑**单文件**也立刻 `INTERNALERROR`。

**（b）★ 两条新发现（推翻了"下一轮就能跑"的假设）**

1. **配额不是"我的回合"级的**：跨过一次消息边界（team-lead 回信 → 我的新回合）后**仍然**被拒
   ⇒ 它的 `scope: "turn"` 指的是**宿主回合**，**不随单个 agent 的对话轮次重置**。
2. **它是宿主级共享的**（这是关键）。实测同一时刻的并发情况：

```
$ ps -eo pid,command | grep pytest | grep -v grep | wc -l
0                                       ← 此刻没有存活的 pytest
$ for d in …/.worktrees/*/; do f="$d/system/tests/.pytest-session.lock"; [ -f "$f" ] && echo "$(basename $d): pid=$(cat $f)"; done
ws-daily-nochange: pid=95289
ws-fixture-cost:   pid=95264            ← 我开工时还不存在的新工作树
ws-schema-expand:  pid=94703
```

⇒ 当时**至少 3 个并发流**（3 个工作树各有刚写过锁的会话，pid 落在 94700–95300 区间），
而 **`V-05` 会话锁是 per-worktree 的、删除配额却是宿主共享的**
—— 于是"每个工作树各自串行"**并不能**防止它们**合起来**把这份共享删除预算打穿。
**这正是团队口径"`unit` 耗时数据被 6 条并发流污染"的同一个机制。**

**（c）判据：这不是本单的代码缺陷**

- 同一时刻、**不建夹具**的探针**照常跑通**：`probe.py no_change after` → `exit=0 / exempt=1 / PASS`；
- `run_all_gates.py --timeout 30` 24 项**照常全部跑完**（`非零计数 1`）；
- `run_checker` 的进程内契约三验（§2.5(b)）**照常跑通**。
⇒ 受影响的**只有**依赖 `copytree` 夹具的 pytest 批次。

**（d）处置（不含任何绕过）**

- ✗ **没有**设 `CODEBUDDY_SAFE_DELETE_BULK_GUARD=""` / 其它环境变量去关掉闸门
  —— 读了 shim 源码（`sitecustomize.py:828-852` 可见该开关）**但没使用**：那属于**绕过安全机制**，
  且按团队口径"**绕过它得到的绿不算证据**"。
- ✗ **没有**改夹具去规避 `copytree`（那会篡改被测对象）。
- ✓ 已跑的：受控对拍九例、新测试文件（**改后 12 passed / 改前 8 failed 4 passed**）、
  真源门禁、24 项全量门禁、退出码契约直验、静态影响面排查。
- ✓ **未跑的 = 如实登记为未跑**：`tests/daily` 整目录、`tests/guards`、
  以及 `injection-a`/`injection-f` 等相关分片 —— **留给能跑的时刻（见 (e)）**。

**（e）恢复条件与建议**（交 team-lead 定）

1. **串行窗口**：让其他流在**同一回合内**不要跑 pytest（`V-05` 只保证 per-worktree，不保证预算）；
2. **换一个宿主回合**（重启会话/应用）后再跑；
3. **用户对批量删除授权**（守卫名就叫 `BULK_CONFIRM_REQUIRED`）—— 这是设计好的通道，不算绕过。
★ 建议把这三条写成口径：**"删除预算是宿主共享资源，跑 pytest 的并发流数必须被记入报告"**
（恰好与你在 13-F 里要求的"报告耗时数据时必须写并发流数"是同一条）。

### ④-3 新增测试文件为何**不改** `verify.py`

`verify.py` 的 `daily` 批次是**目录粒度**（`tests/daily/`，超时 180s），
新增文件落在该目录内 ⇒ **自动被既有批次覆盖**，故**不需要**改 `verify.py` 的分片清单
（改它反而要动共享文件）。本单**没有**改 `verify.py`。

### ④-4 与 step 7 的联动（`08_产品入口与每日运行/02_实现方案.md:76`）

设计写「第 7 步发布……**无变化时不触发**」。本单据此认定"无变化日无产出"是**结构性**的。
但 step 7 目前 `blocking: true` 且未实现（`T-18`）⇒
**"无变化日能否真的跑出 `done + 空产出`"要等 `T-18` 裁定后才可能在真数据上出现**。
本单**不预设**该裁定的结果，只按设计正文实现判据。

### ④-5 未做的（明确不在本单范围）

- 未改 `system/rules/pipeline.yaml`（0444 + `T-18` 裁定）；未改 `verify.py`；未改 `gap_to_task.py` 之外任何文件；
- 未动 `IdempotentTaskQueue` / 状态机 / 幂等键（本单只碰 `check()` 与新增的谓词）；
- 未与其他守门的 `G1-04` 判定（如 `scripts/daily/idempotency.py`）做口径对齐 —— 若需求方认为该同源，请另行派单。

---

## ⑤ 复现入口（最小）

```sh
cd /Users/gaza/Developer/InvestSigh/.worktrees/ws-daily-nochange
PY=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python

# 1) 受控对拍（9 例 × 改前/改后，含真实退出码）
for mode in before after; do for c in real no_change cc_A cc_B cc_C changed_null normal_done failed_row mixed; do
  $PY /tmp/wsnc/probe.py $c $mode; done; done

# 2) 测试（★ 必须用 run_pytest.sh，裸 pytest 会被宿主 broker 掐死）
sh system/scripts/ops/run_pytest.sh tests/daily/test_no_change_day.py -q

# 3) 退出码契约三验（不建 copytree 夹具；宿主删除预算被占满时仍可跑）
$PY /tmp/wsnc/contract.py

# 4) 对真源直接跑本门禁
$PY system/scripts/tasks/gap_to_task.py system/

# 5) 全量门禁
$PY system/scripts/ops/run_all_gates.py --timeout 30
```

★ `/tmp/wsnc/**` 是**仓外**的对拍台（`probe.py` 九例对拍 / `contract.py` 契约三验），
**刻意不入库**（避免把实验装置混进交付物）；**可复现的判据本体已入库**为
`system/tests/daily/test_no_change_day.py`（12 例，改后全绿 / 改前 8 红）。
