# 批次 4 · QA 收口报告 2（`D-5` 非真空证据 + `D-3` 护栏回归）

> **谁写的**：QA 工程师（严过关 / Yan）。**只改测试**：`tests/injection/test_prompt_injection.py`、
> `tests/injection/test_guards_reject.py`。**未改** `scripts/guard/**`、`scripts/checks/**`、
> `conftest.py`、`rules/**`（并发提示：`injection_guard.py` / `executor.py` / `rawsink.py` 的改动**不是我做的**）。
> **依据**：`system/reports/batch4_independent_audit.md`（D-3 / D-5）· `system/CONVENTIONS.md`
> （§一 验证规范 · §二 G-02/G-03）· `system/tests/injection/test_append_only.py`（真 git 仓库范式）。
> **环境**：`CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`；逐批、串行；
> 临时脚本写在 `/tmp`（用后即删）；`git status` 结束时除既有改动外无新增。

---

## 改了什么（文件 + 对应 AC/缺陷编号）

| 文件 | 改动 | 对应 |
|---|---|---|
| `tests/injection/test_prompt_injection.py` | 新增真 git 仓库帮助函数（`_init_facts_git_repo` / `_run_append_only` / `_staged_facts_count` / `_assert_append_only_non_vacuous`）；把 `test_ac15` 与 `test_ac25` 的**真空** `run_gate(APPEND_ONLY, …) == 0` 换成**非真空**证据 | **D-5** · AC-15 · AC-25 |
| `tests/injection/test_prompt_injection.py` | **解耦措辞**：AC-16 / AC-19 的反事实断言去掉 `rule_hint=…`（原先锚定守卫输出文字 `哈希不符` / `工具原语`），**只断言退出码**；两处 docstring 补写"为何不断言文字" | 主理人复核要求（假失败地雷） |
| `tests/injection/test_guards_reject.py` | 末尾新增 **7 条** `injection_guard` B/C 静态判据回归探针（4 拦 / 1 放 / 2 已知局限），含 `_restore_rule_perms` / `_probe_guard` 两个局部助手 | **D-3** 护栏 · AC-11/AC-19 的结构性回归 |

**措辞解耦（本轮追加，主理人要求）**：`test_prompt_injection.py` 中**全部** `assert_rejected(...)` 现均为**退出码断言**，`grep -n "rule_hint" → NONE`：
- AC-16 反事实：`assert_rejected(run_gate_subprocess(RULES_LOCK, code_root))`
- AC-19 反事实：`assert_rejected(run_gate_subprocess(INJECTION_GUARD, code_root))`
- AC-15 反事实：`assert_rejected(_run_append_only(root))`
**为何用退出码而非结构化 key**：`injection_guard` 的 docstring **未**把 `tool_primitive_hits` 等 `scanned` 计数列为**对外契约**，
按"标识须是契约一部分"的前提，**不**引入新耦合；`exit 1` 已足判定（`exit 2` 才是输入异常），
且探针内容极小且已知（仅 `import subprocess`）、干净副本守卫为 `exit 0`，归因唯一。

`git diff --stat`：

```
 system/tests/injection/test_guards_reject.py    | 156 ++++++++++++++++++++++++
 system/tests/injection/test_prompt_injection.py | 126 ++++++++++++++++++-
 2 files changed, 276 insertions(+), 6 deletions(-)
```

**关键设计决定（并发安全）**：新增断言**一律只取退出码**，**不传 `rule_hint`**。
`injection_guard.py` 正被另一名工程师做"仅措辞"改动，锚定输出文字会因措辞变化产生**假失败**。
`exit 1` 已足以判定（`exit 2` 才是输入异常），故退出码即判别依据。

---

## 测了什么（命令 + 原始 stdout + 退出码）

### A. 独立复现 D-5 三步（真 git 仓库，临时脚本 `/tmp/qa_d5_probe.py`，已删）

```
git init rc: 0
git commit rc: 0
ingest status: ok claim_id: claim-src-inj-03-f3ebb8c62fb1
claims lines after ingest: 2

===== STEP A: pure append (git add) =====
exit code: 0
== append_only_guard.py ==
  scanned diff_bytes: 823
  scanned staged_facts_files: 1
  note: pathspec = system/facts/*.jsonl（相对仓库根 …/tests/.work/qa-probe-626efd71）
RESULT: PASS（0 violations）

===== STEP B: counterfactual — rewrite an existing (baseline) line =====
exit code: 1
== append_only_guard.py ==
  scanned diff_bytes: 901
  scanned staged_facts_files: 1
  note: pathspec = system/facts/*.jsonl（相对仓库根 …/tests/.work/qa-probe-626efd71）
  [FATAL] Ch9 §3.4.2 / 纪律 4 @ system/facts/*.jsonl:0 — system/facts/claims.jsonl: 存在被删除/改写的既有行 → {"claim_id": "baseline-claim-0"}
RESULT: FAIL（1 violations）

===== STEP C: vacuum (no staged facts change) — for contrast =====
exit code: 0
== append_only_guard.py ==
  scanned diff_bytes: 0
  scanned staged_facts_files: 0
  note: NO_STAGED_FACTS_CHANGES：暂存区没有 facts JSONL 的改动；本次**无被检对象**，不代表‘已验证追加式不可变’
RESULT: PASS（0 violations）
```

→ **`staged_facts_files` 实际计数 = 1**（STEP A，非真空）；反事实 **exit 1**；
STEP C 正是独立审计抓到的**真空（计数 0）**形态，新用例对 STEP C 会**红**（见下）。

### B. 独立复现 D-3 七条探针（临时脚本 `/tmp/qa_d3_probe.py`，已删）

```
probe                                            exit  verdict
baseline (no probe)                                 0  ALLOW
(1) import subprocess                               1  REJECT
    [FATAL] 措施3·工具白名单 @ scripts/guard/probe_d3.py:1 — 数据路径出现工具原语 'subprocess'（外部文本不得触发工具）
(2) getattr(os,'system')                            1  REJECT
    [FATAL] 措施3·工具白名单 @ scripts/guard/probe_d3.py:5 — 数据路径出现工具原语 'getattr:system'（外部文本不得触发工具）
(3) append_records(root, stem, rows)                1  REJECT
    [FATAL] 判据·不产生建议 @ scripts/guard/probe_d3.py:5 — append_records 的 stem 无法静态判定（append_records:Name）—— fail clos…
(4) append_records(root, f'{x}', rows)              1  REJECT
    [FATAL] 判据·不产生建议 @ scripts/guard/probe_d3.py:5 — append_records 的 stem 无法静态判定（append_records:JoinedStr）—— fail…
(rev) append_records(root, 'claims', rows)          0  ALLOW
(5) (root/'facts'/('recommend'+'ations.jsonl')).write_text    0  ALLOW
(6) open(f'{root}/facts/{stem}.jsonl','a')          0  ALLOW
```

### C. 回归测试（改动的两个文件）

```
tests/injection/test_guards_reject.py::test_injection_guard_rejects_subprocess_import_in_data_path PASSED
tests/injection/test_guards_reject.py::test_injection_guard_rejects_getattr_os_system PASSED
tests/injection/test_guards_reject.py::test_injection_guard_rejects_variable_append_stem PASSED
tests/injection/test_guards_reject.py::test_injection_guard_rejects_fstring_append_stem PASSED
tests/injection/test_guards_reject.py::test_injection_guard_allows_literal_non_recommendation_stem PASSED
tests/injection/test_guards_reject.py::test_injection_guard_known_static_limit_constant_in_receiver PASSED
tests/injection/test_guards_reject.py::test_injection_guard_known_static_limit_fstring_open_target PASSED
tests/injection/test_prompt_injection.py::test_ac15_delete_counterevidence_request_is_neutralized PASSED
tests/injection/test_prompt_injection.py::test_ac25_research_text_about_retraction_passes PASSED
======================= 9 passed, 53 deselected in 3.02s =======================
```

### D. `--batch injection` 完整摘要与退出码

```bash
PY=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python
$PY system/scripts/ops/verify.py --batch injection
```

```
✓ [injection] tests/injection/（注入 / 接线 / 审计回归）  exit=0  22.76s/120s  exit=0
------------------------------------------------------------------------------
........................................................................ [ 66%]
.....................................                                    [100%]
109 passed in 22.09s
------------------------------------------------------------------------------
证据留档: reports/verify_injection_latest.log
```

**批次退出码 = 0**（合格，22.76s / 上限 120s）。逐文件收集数：
`test_prompt_injection 21 · test_guards_reject 41 · test_append_only 6 · test_audit_regressions 14 ·
test_wiring_guards 11 · test_rules_lock 6 · test_stage_gate 10 = 109`
（本轮**净增 7 条**；AC-15/AC-25 为**就地改造**，不增用例数）。

**措辞解耦后复跑**（同一命令）：

```
✓ [injection] tests/injection/（注入 / 接线 / 审计回归）  exit=0  23.23s/120s  exit=0
109 passed in 22.69s
证据留档: reports/verify_injection_latest.log
```

### E. 反占位符守卫（自检新增注释/docstring，无违禁字符串）

```
== no_placeholder_guard.py ==
  scanned files: 83
RESULT: PASS（0 violations）
```

---

## 每条的处理与证据

### D-5（中）· AC-15 的"追加式不可变"证据曾是**真空放行**

| 项 | 内容 |
|---|---|
| **判定** | **已收口（非真空）** |
| **改法** | `test_ac15` 不再用夹具副本上"暂存区无改动"的 `exit 0`。改为：① 在 `code_root.parent` 建**真 git 仓库**（`git init` + `user.email/name` + 提交 `system/facts/claims.jsonl` 基线）；② 载荷真走 `process_external_text`（**追加**一行 claim）；③ `git add` 后跑 `append_only_guard`，断言 **`exit == 0` 且 `staged_facts_files > 0`**；④ 反事实：改写基线里**既有的那一行** → `git add` → 断言 **`exit == 1`** |
| **证据** | 上文 A：STEP A `staged_facts_files: 1`、exit 0；STEP B exit 1；C 组用例 `test_ac15_… PASSED`。**排除真空的关键断言**是 `_staged_facts_count(stdout) > 0` |
| **为何可信** | 仓库根放 `code_root.parent` —— 否则 `git rev-parse --show-toplevel` 会往上找到**外层真仓库**（夹具在 `tests/.work/` 内），根本测不到本夹具的暂存区。此点已在帮助函数 docstring 中写明 |
| **附带** | STEP C 展示的正是旧断言的**真空形态**：`staged_facts_files: 0` + `NO_STAGED_FACTS_CHANGES` note、exit 0 —— 与新用例的 `> 0` 断言构成对照 |

### AC-25（对照③）· 附加的追加式证据同源真空

| 项 | 内容 |
|---|---|
| **判定** | **已收口（非真空）** |
| **改法** | `test_ac25` 复用同一 `_assert_append_only_non_vacuous`：注入后**真 git 仓库**追加一行 → `exit 0` 且 `staged_facts_files > 0` → 反事实 `exit 1` |
| **证据** | 上文 A + C：`test_ac25_… PASSED` |

### D-3 护栏（中）· `injection_guard` 的 B/C 静态判据加固 → 回归测试

| 探针 | 期望 | 实测退出码 | 测试名 | 判定 |
|---|---|---|---|---|
| ① `import subprocess` | 拦 | **1** | `test_injection_guard_rejects_subprocess_import_in_data_path` | ✅ 已拦 |
| ② `getattr(os, 'system')(cmd)`（含 `import os`） | 拦 | **1** | `test_injection_guard_rejects_getattr_os_system` | ✅ 已拦 |
| ③ `append_records(root, stem, rows)`（stem 变量） | 拦 | **1** | `test_injection_guard_rejects_variable_append_stem` | ✅ 已拦 |
| ④ `append_records(root, f'{x}', rows)`（f-string） | 拦 | **1** | `test_injection_guard_rejects_fstring_append_stem` | ✅ 已拦 |
| **反向对照** `append_records(root, 'claims', rows)` | 放 | **0** | `test_injection_guard_allows_literal_non_recommendation_stem` | ✅ 未误杀 |
| ⑤ `(root/'facts'/('recommend'+'ations.jsonl')).write_text('x')` | **已知静态局限** → 放 | **0** | `test_injection_guard_known_static_limit_constant_in_receiver` | ✅ 记录事实 |
| ⑥ `open(f'{root}/facts/{stem}.jsonl','a')` | **已知静态局限** → 放 | **0** | `test_injection_guard_known_static_limit_fstring_open_target` | ✅ 记录事实 |

- **①②③④** 用 `assert_rejected`（exit 1，**不传 `rule_hint`**，只认退出码）。
- **反向对照** 断言 `exit 0`：证明 fail-closed **没有**退化成"见 `append_records` 就杀"。
- **⑤⑥** 断言 `exit 0`，测试名与 docstring **明说"已知静态局限"**，并注明：
  「完整保证由运行时**效果断言**承担（见 `test_prompt_injection.py` 的效果三元组 (b)：
  处理前后 `facts/recommendations.jsonl` 行数不变）」。→ 这两条**记录事实**而非假装缺口不存在；
  将来若静态判据做全了，它们会**变红**，逼后人**显式**更新预期（反回退机制）。
- **探针落点**：`code_root/scripts/guard/probe_d3_*.py`（**夹具副本**，被 `injection_guard` 扫描面覆盖），
  `finally` 删除；真实 `scripts/guard/**` **零残留**（见末行 `ls`）。

### 保护项 `git` / `bash` / `scripts/check` 守卫未回归

- **守卫本体未改**：`git diff --stat` 仅两个测试文件（+276/-6）；`scripts/guard/**` 未被本 QA 触碰。
- **既有守卫未受影响**：`no_placeholder_guard` 仍 `PASS（0 violations）`（83 files）。

---

## 剩余不确定性与缺口

1. **静态判据的固有边界（非缺陷）**：⑤⑥ 是**原理上不可判定**的形态（接收者位置的常量拼接、
   f-string 变量目标），当前静态判据**不覆盖**。**这是设计选择**（`injection_guard.py` 的
   `KNOWN_STATIC_LIMIT` note 已显式列出）；完整保证由运行时**效果断言 (b)** 承担。
   若将来引入"计算得到路径"的木马式伪装，静态绊线仍可能漏 —— 已用测试固定这一事实，不作为 PASS 冒充。
2. **措辞耦合已**彻底**解耦**：`test_prompt_injection.py` 现有 3 处 `assert_rejected(...)`（AC-15/AC-16/AC-19）
   **全部只断言退出码**，`grep -n "rule_hint" → NONE`。守卫的说明文字此后允许被自由改写（只要行为不变），
   不会再触发本文件的假失败。（`test_guards_reject.py` 中**其他守卫**的既有 `rule_hint` 锚点不在本次范围，
   本轮**未**改动，遵守"只改这两处、不扩大"。）
3. **`staged_facts_files > 0` 的语义**：该计数只证"有被检对象"，**不**证"注入内容本身"；
   真正的"注入未破坏追加式不可变"仍由 `exit 0`（纯追加）+ 反事实 `exit 1` 共同承担。三者缺一不可，
   已在 `_assert_append_only_non_vacuous` 中成组断言。
4. **未覆盖的 D-5 相邻面**：审计 `D-6`（`raw/` 无追加式保护、可静默覆盖）**不在**本次收口范围
   （属 `rawsink` 行为，非测试侧）；本轮只收口 `facts/*.jsonl` 的追加式证据。
5. **批次口径**：本轮实测 `injection = 109`；审计报告中的"98 passed"为**较早快照**，以本轮实测为准。

---

*（本报告的计数与退出码均为本轮 QA 实跑所得；临时脚本位于 `/tmp` 且已删除，仓库内无残留。）*
