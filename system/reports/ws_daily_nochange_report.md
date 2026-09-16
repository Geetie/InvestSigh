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
  `tests/daily` 整目录与 `tests/guards` **因共享删除预算见底而未跑成**（§④-2）；
  **已按 `CONVENTIONS.md::V-09` 逐条试过压缩单次删除量 ⇒ 全被拒 ⇒ 当前回合不可恢复**（§2.6）；
  ★ **报文级直证：连"删 1 个文件"都被拒**（§2.6(c)-1），故**粒度不改变预算**，"逐文件"不是出路；
  引用守卫模型时请只引 §2.6(b) 的**可核实部分** —— 我**已撤回**"累计值 ≈ 99,998"（§2.6(b-2)）。

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

### 2.6 ★ 按 `CONVENTIONS.md::V-09` 复跑尝试：**结论 = 当前回合不可恢复**（附守卫的**可核实部分**与我**撤回的部分**）

按 V-09「优先单文件、分片、多轮次，把单次删除量压到阈值以下」逐条试过，**全部失败**，
并顺带把这条闸门的**判定规则实测清楚了**（下面每条都只有我自己建的探针目录，未碰任何既有夹具残留）。

**（a）试过的手段与结果**

| # | 手段 | 结果 |
|---|---|---|
| 1 | **0 夹具** 用例（`test_null_overwrite_error_path_and_boundaries`，**不建任何 `copytree`**） | ★ 仍 `INTERNALERROR` |
| 2 | 单文件（`tests/daily/test_no_change_day.py`） | ★ 仍 `INTERNALERROR` |
| 3 | 单用例 node（`…::test_done_with_output_is_not_affected`） | ★ 仍 `INTERNALERROR` |
| 4 | 删 **1 个** 目标（自建探针目录，1 文件） | ★ 被拒 |
| 5 | ★ **单文件**目标（`gp-1-10274/f0.txt`，1 byte，**现场核验且至今仍在**）——即为**报文级直证** | ★ 被拒（报文原值见 (c)-1） |

★ 第 1 条是**决定性**的：**连"零夹具"的会话都进不去** ⇒ 卡点不在"我要跑多少用例"，
而在 `pytest_sessionstart` → `_clear_work_dir()` → `shutil.rmtree(<残留子项>)`
（`conftest.py:384 / :351`）。**只要 `.work/` 里还有任何残留子项，会话启动即被拒。**

**（b）★ 守卫的判定规则（**只保留可核实的，撤回不可核实的**）**

**（b-1）我自建探针**（规模由我自己构造并数出，8 次拒绝；报文只摘 `count`）：

| 目标内含（**我自报，非报文原值**） | 报文里的 `count` |
|---|---|
| 1 项 | `99999` |
| 2 项 | `100000` |
| 3 项 | `100001` |
| 10 项 | `100008` |
| 38 项 | `100036` |
| 75 项 | `100073` |
| 150 项 | `100148` |
| 250 项 | `100248` |

这 8 点**完美线性拟合** `count = 99,998 + 项数`，斜率恰为 1。

**（b-2）★ 但同一模型对「非我构造的」目标不成立**。下表左列 = 我事后用 `os.walk` 数出的真实条目数
（**被拒 ⇒ 目标未删 ⇒ 现在仍可数**），右列 = 该目标被拒时报文里的 `count`（全部 `threshold: 99999`）：

| 目标规模（文件+目录） | 报文 `count` | 残差 `count − 规模` |
|---|---|---|
| 1~4 项（`gp-1-10274/f0.txt` 等） | `99,999` / `100,001` | **99,997 ~ 99,998** |
| 251 项 | `100,168` | 99,917 |
| 307 项（**同一目标**，21:49→22:17 四次） | `100,113` → `100,116` | 99,806 → **99,809** |
| 308 项 | `100,211` ~ `100,221` | 99,903 ~ **99,913** |
| 330 项 | `100,267` | 99,937 |
| 332 项 | `100,270` | 99,938 |

⇒ **两个混杂效应，且无法从报文里分离**：
1. **累计量自身在缓慢增长**：同一个 307 项目标（项数不变）在 21:49→22:17 的 `count` 从 `100113` 爬到 `100116`；
2. **守卫计数的"规模"口径 ≠ 我的"文件+目录"计数**：22:45 的 332 项目标残差 `99,938` 与 22:47 的 1 项目标残差
   `99,998` **只隔 2 分钟却差 60** ⇒ 不是时间造成的，是**口径本身不同**。

⇒ ★ **判据只保留可核实的部分**：
**`count = 该桶已累计 + 本次（守卫口径的）规模`，且 `count >= threshold(99999)` 即拒**
（比较**含等号** —— 依据 (b-1) 首行：`count = 99999` 已被拒，边界值即拒）。
**"该桶已累计"只能表述为「长期贴近天花板（≈99,8xx~99,9xx）且单调不减」。**
★ **撤回**本节初版写下的"已累计 ≈ 99,998"：它只在**我自建探针**上成立，**不是报文原值，不得作为判据被下游引用**
（team-lead 已同步在登记里更正）。

**（b-3）★ 字段语义（`G-62` 家族，我的订正）**：报文里只有 `targetCount`，它是**目标个数**
（1 个目录 / 1 个文件），**不是条目数**。我初版把 `100001 − 99998 = 3` 讲成"体积 3"，
那是**把 `targetCount: 1` 当成体积、再用差值反推**——**字段语义未验明就代入模型**，
正是 `G-62`「静默等价态」的形态。**报文不打印规模，故规模只能由提交者自报**（本报告所有"项数"均为我自报）。

**（c）由此得出的三条硬结论**（第 1 条已按 (b-2) 重写，**不再依赖任何具体累计值**）

1. ★ **粒度不改变预算**：可删总量只由"累计量距天花板还剩多少"决定，与"一次删 1 项还是 250 项"**无关**。
   ⇒ 本回合累计量已贴近天花板，**任何**仓库内删除（**包括删 1 个文件**）都过不去。
   ★ **报文级直证（不依赖任何模型、也不依赖我的自报项数）**：
   ```
   $ 报文原值   {"count":99999,"threshold":99999,"scope":"turn","targetCount":1,
                 "targets":["…/ws-daily-nochange/system/tests/.work/gp-1-10274/f0.txt"]}
   $ ls -la  …/gp-1-10274/    →  -rw-r--r--  1 byte  f0.txt     ← 单个文件，且【至今仍在】（被拒=未删）
   ```
   ⇒ ★ 这条同时**反证了"逐文件删除是出路"**：逐文件在本回合**连第一项都删不掉**。
2. ★ **逐文件还改变失败形态，因而更差**（`ws-ch2-rules` 提出，我采纳）：当 `累计 < 阈值` 但 `累计 + 规模 ≥ 阈值` 时 ——
   - **批量删除** = 一次**原子拒绝** ⇒ 夹具**原封不动**，下回合可原样重试；
   - **逐文件删除** = 先删掉一部分、**然后开始被拒** ⇒ 夹具停在**半清空**状态，
     而 `pytest` 只看得见一个 `E` ⇒ **"清了一半"与"清干净了"在观测上不可区分**，
     下一条用例会拿到**脏且残缺**的夹具 ⇒ 比"完全没清"**更容易**产出假绿/假红。
   ⇒ 归入"静默变空"家族。
3. **它解释了我早先那次"1 项/50 项通过、250 项被拒"的观测**：当时距天花板的余量**恰好**容得下 1 与 50、容不下 250。
   ⇒ ★ **那次观测不能被读成"分片可行"**（余量是**全流共享**的、我无法控制），特此更正以免误导。

**（d）V-09 三选一的现状**：① 「同一回合内其他流停跑 pytest」—— 我无法为全队保证；
② 「换宿主回合」—— 试过了，**不保证**（我在本轮跨了多次消息边界仍在天花板）；③ **用户对批量删除授权** ⇒ **只剩这条**。

**（e）★ 我自己留下的残留（如实登记）**

探针在 `system/tests/.work/` 留下 **24 个** `gp-*` / `guardprobe-*` 目录。
**有界尽力清理已试：24 次尝试、成功 0**（全被拒）。**不绕过**，故如实留在此处。

```
$ ls system/tests/.work/ | wc -l
34                       ← 24 项是我的探针残留 + 10 项是更早各卡留下的夹具残留
$ find system/tests/.work/ -type f | wc -l
4041
$ git status --short
（空）                    ← `.work/` 已被 `system/.gitignore:8` 忽略，**不进仓库**
```

无害性依据（**引既有代码而非我自创**）：`conftest.py::_clear_work_dir` 的 docstring 明写
「残留目录**无害**：每个用例的目录名都带 uuid，不会串用」。
⇒ **授权批量删除时，请把 `.work/` 一并清掉**（这也正是本条守卫要征得同意的那件事）。

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
| 10 | **回归分片**（`tests/daily` / `tests/guards` / injection 相关片） | — | ★ **未跑成**（宿主共享删除预算见底，§④-2）；已按 `V-09` 试过单文件/单用例/**0 夹具**压缩体量 ⇒ 全被拒 ⇒ **当前回合不可恢复**；替代证据见 §2.5、守卫的**可核实部分与我撤回的部分**见 §2.6；**如实登记为"未跑"而非"已验证"** |

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

**（e）★ 按 `V-09` 复跑尝试后的最终结论：当前回合**不可恢复**（详见 §2.6）**

- V-09 让试的三条压缩手段（单文件 / 分片 / 多轮次）**全部失败**，
  连 **0 夹具** 的用例与 **单用例 node** 都进不去 ⇒ 卡点是 `pytest_sessionstart` 的 `.work/` 清理；
- 守卫规则**只保留可核实的部分**：**`count = 该桶已累计 + 本次（守卫口径的）规模`，`count >= 99999` 即拒**；
  累计量**长期贴近天花板**（≈99,8xx~99,9xx、单调不减，**具体值不可从报文定出**，见 §2.6(b-2)）
  ⇒ ★ **粒度不改变预算**：**删 1 个文件也过不去**（报文级直证见 §2.6(c)-1）
  ⇒ **压缩单次删除量的三条手段在原理上均无效**（且"逐文件"还会造成"半清空"，见 §2.6(c)-2）；
- ⇒ V-09 三选一只剩 **③ 用户对批量删除授权**（守卫名即 `BULK_CONFIRM_REQUIRED`，是设计好的通道，不算绕过）；
- 我遗留的 24 个探针目录**已如实登记且未绕过**（§2.6(e)），请授权清删时**把 `.work/` 一并清掉**。

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

---

## ⑥ 提交现场（命令 + 退出码 + 哈希 + `git status --short`）

```
$ git merge main --no-edit           # 提交前并主干（当时落后 15 个提交）
15 files changed, 1408 insertions(+), 62 deletions(-)          exit=0

$ git add system/scripts/tasks/gap_to_task.py \
          system/tests/daily/test_no_change_day.py \
          system/reports/ws_daily_nochange_report.md
$ git commit -F /tmp/wsnc/commit_msg.txt
[ws/daily-nochange-exit f86542c] fix(g1-04): 无变化日不再误判空执行 —— 换成可判定正向标记
 3 files changed, 792 insertions(+), 7 deletions(-)
 create mode 100644 system/reports/ws_daily_nochange_report.md
 create mode 100644 system/tests/daily/test_no_change_day.py
★ commit exit=0          ← pre-commit **未被跳过**，全部门禁放行（阻断计数 0）
```

- **本单 commit（评审对象）**：`f86542c` = `f86542cb0183ca5a3165bbb33ffcfe52b1e75713`
- **基点**：`90e7c94`（`main`，提交前 `git merge main` 已并）
- **本分支相对 `main` 只有一个提交**（`git log --oneline main..HEAD` 只列 `f86542c`）
- **本单 diff**：`65/7`（`gap_to_task.py`）+ `228/0`（新测试）+ `499/0`（本报告）
- **`git status --short`**：**（空）** —— 工作树干净
- **`pre-commit`**：**未使用 `--no-verify`**（team-lead 已明确本项为明令禁止）

★ **首次提交被拒，如实记录**（`pre-commit: 有门禁阻断，提交被拒。`）：
`rules_lock_guard` 与 `injection_guard` 各报 1 条 FATAL，**同一根因** ——
`rules/valuation-methods.yaml` 权限为 `0o644`（应为 `0o444`）。
成因：**我在 `bootstrap_worktree.sh` 之后才 `git merge main`**，而主干那次合并**更新了该规则文件的权限位**
（内容来自主干，权限位由合并写盘时重置）。
处置：重跑 `sh system/scripts/ops/bootstrap_worktree.sh`（**该脚本只改权限位、内容零改动**，
是"step 0"的既有工具；**没有**用 `lock_rules.py`，因为它会顺带重写 `registry/rules.lock.json`
—— 那会变成对共享 registry 的内容写入，本单不做）：

```
$ sh system/scripts/ops/bootstrap_worktree.sh
bootstrap_worktree: 已把 14 个 rules 文件置为 0444（内容零改动）
bootstrap_worktree ✓ rules_lock_guard 通过（纪律 9 不变量已复原）      exit=0
$ git status --short system/rules system/registry
（空 —— 内容未动）
```

★ **教训（建议入团队口径）**：**`bootstrap_worktree.sh` 必须在每次 `git merge` 之后再跑一次**，
否则合并带来的 `rules/` 改动会让权限位退回 0644，`rules_lock_guard` / `injection_guard` 双双阻断。
**本单后面又实测到一次**（`6f94a55` 之后再次 `git merge main` → 仍按此流程重跑 bootstrap ⇒ 才恢复绿）。

### ⑥.1 定稿状态（**主干是移动靶，故记录最终一次核验**）

```
$ git merge main --no-edit                     # ★ 提交后又并了 2 次：main 在本单工作期间前移了 3 次
$ sh system/scripts/ops/bootstrap_worktree.sh  # ★ 每次 merge 之后都要重跑（见上）
$ git rev-list --count HEAD..main
0                                              ← 最终与 main 齐平
$ git diff --numstat main..HEAD
545	0	system/reports/ws_daily_nochange_report.md
 65	7	system/scripts/tasks/gap_to_task.py
228	0	system/tests/daily/test_no_change_day.py     ← ★ 净改动**只有**这 3 个文件
$ git status --short
（空）
$ git rev-parse HEAD
127d8a12f96a0e822719a55ec0b3652d1ef45bf2      ← 合并提交（HEAD）

$ sh system/scripts/ops/pre-commit.sh
pre-commit ✓ 全部门禁放行                        exit=0   阻断计数 0

$ $PY system/scripts/ops/run_all_gates.py --timeout 30
  gap_to_task.py                     exit=0        0.13s      ← 本单改的脚本
  pipeline.py                        exit=0        0.16s
  rules_lock_guard.py                exit=0        0.40s
  criterion_effectiveness_guard.py   exit=0        0.87s
  traceback.py                       exit=1        0.17s      ← 唯一非零（既有 design-red）
  非零计数                               1

$ $PY system/scripts/tasks/gap_to_task.py system/ --no-report
  scanned done_empty_output_rows: 0
  scanned no_change_day_exempt: 0
  scanned tasks: 4
RESULT: PASS（0 violations）                     exit=0
```

★ **代码 commit（评审对象）** = `f86542c`（`f86542cb0183ca5a3165bbb33ffcfe52b1e75713`，3 文件 +792/−7）。
之后的 `258902f` / `14dc6ac`（本报告）与两次 `Merge branch 'main'` **不含本单的代码改动**。
核验方式（**注意别用错命令**）：

```
$ git show --numstat --oneline f86542c | tail -4
f86542c fix(g1-04): 无变化日不再误判空执行 —— 换成可判定正向标记
499	0	system/reports/ws_daily_nochange_report.md
 65	7	system/scripts/tasks/gap_to_task.py
228	0	system/tests/daily/test_no_change_day.py          ← 本单只碰这 3 个

$ git diff --numstat main..HEAD
545	0	system/reports/ws_daily_nochange_report.md
 65	7	system/scripts/tasks/gap_to_task.py
228	0	system/tests/daily/test_no_change_day.py          ← 相对 main 的**净**改动，同样只有这 3 个
```

★ **一个容易写错的坑，如实记下**：`git diff f86542c..HEAD -- system/tests` **不是空的** ——
它显示 `system/tests/unit/test_schema_expand.py | 164 +++…`。
那**不是我的改动**，而是两次 `git merge main` 带进来的**别人的**提交。
⇒ 判断"某单改了哪些代码"必须用 `git show <本单commit> --numstat` 或 `git diff main..HEAD --numstat`，
**不能**用「本单 commit..HEAD」，否则会把合并进来的他人改动算到自己头上（或反过来漏看）。

---

## ⑦ 外单输入：`13-F` / `13-M` 的**验收判据**（可测写法，供其采纳；**本单不改 `tests/conftest.py`**）

team-lead 批准起草。三条判据都写成**可执行、可观测、且能被反例证伪**的形式；采纳与否由 `13-F`/`13-M` 持有方决定。
**每条都给出"必须能判红的反例"**（`R-06` 风格：不只报"绿了"）。

### 判据 A —— 单次删除**目标规模 ≤ 1**（治"粒度"）
- ★ **不能把"逐文件"当判据**：它描述的是**做法**，不是**可观测结果**（`R-06 ①`：判据必须两态穷尽、可判定）。
- **可测写法**（择一，且必须能自证）：
  1. **首选**：每次删除调用**只传 1 个条目**，且**首次被拒即停止**（不得继续尝试）；
  2. **退路**：若守卫口径无法自测，则断言**"本次会话内删除调用次数与通过次数"**，
     并把两者与 `count/threshold` 原值一起打印。
- ★ **为什么必须写"首次被拒即停止"**：见判据 C 的"半清空"。
- **反例（必须判红）**：用替身让删除在**第 3 项**抛拒绝 ⇒ 验收必须**失败**，**不能**因为"已删掉前 2 项"而放行。

### 判据 B —— 余量充足时，**一次会话全程跑完**（治"能不能用"）
- **可测写法**：在**已知余量充足**的回合里，把一个**含 `code_root` 夹具**的用例文件跑到底；
  断言 `exit == 0` **且** 会话结束时 `.work/` **除会话锁外为空**。
- ★ **必须同时记录当时余量**，否则本条不可复现：`count` 原值 + `threshold` 原值 + 时刻 + **并发流数**（`口径 9/10/12`）。
- ★ **本条在"余量已顶死"的回合里必然红，这是正确的** —— 它测的是"能不能用"，不是"修没修好"。
  **不得**为了让它在顶死回合变绿而改判据（这正是本报告 §2.6 记的那条教训）。

### 判据 C —— **部分删除之后必须响亮失败，且夹具状态可判定**（治"半清空"，`G-62` 家族）
- **可测写法**（两条都要）：
  1. **响亮**：删除被拒 ⇒ **必须**抛出/上报，且消息里带「**已删 k 项 / 共 N 项 / 剩余 M 项**」三个数；
     **禁止**以"`print` 之后继续"收场。
     ⇒ 依据：现行 `_clear_work_dir` 的注释声称"刻意不 raise、响亮告警但继续"，
     而守卫抛的是 **`SystemExit`**（`sitecustomize.py:819 → :826`），
     `shutil.rmtree(..., ignore_errors=True)` **只吞 `OSError`** ⇒ **该设计从未生效**（详见 §④-2(c)）。
  2. **可判定**：会话**开始与结束各记一次** `.work/` 状态摘要（条目数 + 子项名集合），
     并**显式区分三态**：`空` / `完整残留` / `部分残留`。
- **反例（必须判红）**：构造"删到一半被拒"的场景 ⇒ 验收必须报出**部分残留**（既不是 `空`，也不是静默通过）。
- ⇒ 一句话判据：**"清了一半"与"清干净了"必须在观测上可分。**

### 三条判据共用的取证要求
1. 每条都要有 **`count` 原值 + 时刻 + 阈值 + 并发流数**（少一项即不可复核）；
2. 每条都要有一个**能判红的反例**；
3. ★ **不得用 `/tmp` 夹具的绿替代 A/C 的验收**：team-lead 已裁定 `/tmp` 属**合法工程取舍**，
   但附**四条约束**（先验可行性 / **不得设为默认** / **每次启用打 note + 计数** / **不得替代 `G-60` 的修复**）。
   它的绿**来自"工作在管辖域之外"**，故**不能**用来证明"仓库内删除已修好"。
   ⇒ 另记：`/tmp` 有系统独立清理 ⇒ 夹具可能被动消失 ⇒ **偶发假红**（`G-62` 家族），
   实现时**必须检测工作目录是否仍在并响亮失败**。
