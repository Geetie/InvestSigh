# 判据有效性（`G9`）· 交付报告

> 代码提交哈希：`9eff294`（分支 `ws/criterion-effectiveness`；本报告为紧随其后的第二个提交）
> 工作树：`.worktrees/ws-criterion-effectiveness`　｜　基站：`main = 5a314a3`
> 交付人：`ws-criterion-effectiveness`（批次 12-C）

本报告遵 `§5.2` 四段式：① 做了什么 → ② 怎么验证（逐条命令 + 原样输出 + 退出码，**正反两向**）
→ ③ 结果 → ④ 如实登记的残余与不确定。

---

## ① 做了什么

### 1.1 要解决的问题（缺口 `G9` 的准确表述）

`stage_gate.py` 里 `criterion("<stage>", "<id>", v)` 是**机器绑定**：
`bound_criteria()` 用 AST 抽出"函数体内的 `criterion()` 字面量"，
`assert_criteria_implemented()` 据此把"`registry/delivery.yaml` 声明为 automated"与
"函数体真的绑了"做机器比对。删掉某一行 → `criteria_bound` 立刻 −1（审计已验证）。

**但绑定只证明「接了」，不证明「真的在查」。** 独立审计实测：把
`cv = coverage_check(root)` 换成空 `CheckReport` →
`scanned daily_run.criteria_bound: 4` **不变**，而不达标数据下阶段④门禁 **`exit=0`（变绿）**。

⇒ 本批次把义务从「接了」强化到「**有一条可执行的反例证明它会拦**」。

### 1.2 新增/改动（仅 5 个文件）

| 文件 | 类型 | 职责 |
|---|---|---|
| `system/registry/criterion_counterexamples.yaml` | 新增 | `(stage, criterion_id) → 可执行反例`登记表（13 条条目 / 12 条已绑定判据） |
| `system/scripts/checks/criterion_effectiveness_guard.py` | 新增 | 新门禁：**新绑一条判据却不登记反例 → `exit 1`**（H2 的核心义务） |
| `system/tests/injection/test_criterion_effectiveness.py` | 新增 | 23 用例：逐条反例 + H3 正反对照 + 空实现复现 + 无判别力探针 |
| `system/scripts/ops/run_all_gates.py` | 改 1 行 | 注册新门禁（`G-07` 防孤儿） |
| `system/scripts/ops/pre-commit.sh` | 改 | 注册新门禁（第 ⑪ 道） |

未改动：`facts/**`、`derived/**`、`rules/**`、`stage_gate.py`、`conftest.py`、`verify.py`。

### 1.3 登记表的两种 `kind`（义务的可判定形态）

| kind | 义务（测试必须断言的事） |
|---|---|
| `counterexample` | 存在不合规输入：该阶段门禁对它 `exit != 0`，**且输出里出现判据专属 `blocked_hint`**；同时断言**合规输入下该 hint 不出现**（判别力归因，防"靠别的判据顺带变红"） |
| `ineffective` | **实测无判别力**：断言"不合规输入下的**违例集合与合规输入完全相同**"，且必须给出 `reason` |

★ 同一判据**可以同时**有两者（三元组 `(stage, criterion_id, kind)` 唯一）：
前者证明"**所绑定的那个检查**会拦"，后者证明"其**字面语义的某个方面**没被守"。

### 1.4 门禁的六条断言

| # | 断言 | 依据 |
|---|---|---|
| A | **已绑定 ⊆ 已登记** —— `stage_gate` 函数体内已绑定的每条 automated 判据都必须有登记，否则 **FATAL** | `G9` / 铁律 5 |
| B | **登记 ⊆ 已绑定** —— 防"先把将来要绑的判据预登记"绕过 A | `R-06` allowlist |
| C | 登记指向的测试**真的存在**：**AST** 扫 `tests/**` 收集 `def test_*` 后比对（**非** grep / 字符串包含）；且**测试函数名必须含判据 id**（防把登记改指向一个无关的、恒过的用例） | `G-02` / `G-06` |
| D | `counterexample` 必带非空 `blocked_hint`；`ineffective` 必带非空 `reason` | `G-03` / `R-02` |
| E | **唯一真源自校**：本门禁算出的"声明 automated 但未绑定"必须与 `stage_gate.criteria_not_implemented()` **逐阶段相等** | `G-06` |
| F | **不可见不得当已核**：无判别力 / 无反例 / 未绑定的判据**逐条进 note 并计数**（`G-03`） | `G-03` |

实现约束：复用 `stage_gate.bound_criteria()`（**不另写第二套解析**，`G-06`）；
配置读取走 `scripts/_common._cached_yaml()`（`P-02`）；单文件一遍 `ast.parse` + 一遍 `ast.walk`（`P-01`）；
按**路径**加载被检 root 的 `stage_gate.py` 并用 `try/finally` 复原 `sys.path` / `sys.modules`（`P-04`）。

### 1.5 覆盖情况（实测计数，取自门禁 `scanned`）

- 声明为 automated：**18** 条；已在函数体内绑定：**12** 条；未绑定（阶段②③待交付）：**6** 条
- 登记条目：**13**（`counterexample` **11** + `ineffective` **2**）
- 无反例判据：**1** 条（`daily_run::task_state_auditable`，见 §3 G9-1）

---

## ② 怎么验证（逐条命令 + 原样输出 + 退出码）

### 2.1 逐条判据的反例（原始输出，在**副本**上采集）

采集脚本为一次性探针（`system/tests/.probe-ce/collect_evidence.py`，**已删除**；
只操作 `tests/.probe-ce/root/system` 副本，真仓库 `facts/` 零触碰）。

```
$ python tests/.probe-ce/collect_evidence.py
## 逐条判据反例（原始输出）

  [合规基线] prep exit=0
| prep::four_deliverables | `--stage prep` | `exit=1` | '交付物项数应为 4' |
    [FATAL] prep @ registry/prep_deliverables.yaml:0 — 交付物项数应为 4，实为 3
| prep::rule_vs_impl_split | `--stage prep` | `exit=1` | 'confirmed_rules 为空' |
    [FATAL] prep @ registry/prep_deliverables.yaml:0 — confirmed_rules 为空：无「已确认规则」层
| prep::caliber_tbd_placeholder | `--stage prep` | `exit=1` | 'frozen 但缺' |
    [FATAL] prep @ rules/freeze.yaml:0 — p01: frozen 但缺 ['confirmed_by', 'confirmed_at', 'version']（切换须原子）
| prep::no_paid_required | `--stage prep` | `exit=1` | '首版启动条件含付费订阅' |
    [FATAL] prep @ registry/launch_criteria.yaml:0 — 首版启动条件含付费订阅: public_information_sources
  [合规基线] nvidia_sample exit=1   ← 结构性红：该阶段另有 2 条未绑定判据（台账）
| nvidia_sample::six_step_chain_complete | `--stage nvidia_sample` | `exit=1` | '六项深度缺' |
    [FATAL] nvidia_sample @ facts/baselines.jsonl:0 — baseline-nvda-001 六项深度缺: ['driver_model']
| nvidia_sample::derivation_reviewable | `--stage nvidia_sample` | `exit=1` | '四要素' |
    [FATAL] G1-03 @ facts/recommendations.jsonl:0 — rec-1 四要素（**适用项**）缺失: ['computation']（适用=['evidence', 'assumptions', 'computation']，version=1）
| core_chain::multi_company_transmission | `--stage core_chain` | `exit=1` | '关系图公司数' |
    [FATAL] core_chain @ facts/relations.jsonl:0 — 关系图公司数 1 < 2：无法构成多公司传导
  [合规基线] daily_run exit=0（绿 ⇒ 反例有完整判别力归因）
| daily_run::timing_replayable | `--stage daily_run` | `exit=1` | '缺 run_date' |
    [FATAL] daily_run @ facts/tasks.jsonl:0 — check_1 缺 run_date：时点不可核
| daily_run::degrade_keeps_last_valid | `--stage daily_run` | `exit=1` | '未保留 last_valid_result_ref' |
    [FATAL] daily_run @ facts/tasks.jsonl:0 — check_1_r1 失败但未保留 last_valid_result_ref（此前已有行持有有效结果 ⇒ 引用本该在，不得置空）
| daily_run::coverage_verifiable | `--stage daily_run` | `exit=1` | 'CV2' |
    [FATAL] coverage_verifiable @ facts/companies.jsonl:0 — CV2 co_1: research_depth='bogus_depth' 不在四态内（Ch3 §N3.2-04）
| expansion::review_append_only | `--stage expansion` | `exit=1` | '三层复盘缺层' |
    [FATAL] expansion @ facts/tasks.jsonl:0 — 三层复盘缺层: investment_result
```

**归因说明（重要）**：阶段②/③/⑤ 在**合规输入**下也 `exit=1` —— 因为
`assert_criteria_implemented()` 的"未绑定判据台账"是**结构性**红（与数据无关）。
故这三阶段的反例**不靠"红/绿"归因**，而靠两件事：① 判据专属 `blocked_hint` 在合规输入下
**不出现**、不合规输入下**出现**；② **违例集合之差非空**（测试内断言）。
阶段①与阶段④在合规输入下 `exit=0`，因此它们的反例有**完整**判别力归因。

### 2.2 H3 三组正反对照

```
# ① 反例（登记完整）→ 必须绿
$ pytest tests/injection/test_criterion_effectiveness.py -q -p no:cacheprovider \
      -k "criterion_effectiveness_guard_passes_on_pristine_tree"
.......................                                                  [100%]
23 passed in 35.19s          ← 全文件 23 例（含该例）

$ python system/scripts/checks/criterion_effectiveness_guard.py . --no-report ; echo exit=$?
  scanned counterexample_entries: 11
  scanned criteria_bound: 12
  scanned criteria_registry_entries: 13
  scanned criteria_without_counterexample: 1
  scanned ineffective_entries: 2
  scanned registry_entry_tests_resolved: 13
  scanned stages: 5
RESULT: PASS（0 violations）
exit=0

# ② 正例：删掉任一条已绑定判据的登记 → 必须红
#    用例 test_removing_any_registry_entry_makes_guard_fail 对 13 条登记**逐条**删、
#    逐条跑门禁并断言退出码（含 review_append_only 有两条例目的退化情形：仍有条目 ⇒ 放行）。
# ③ 新绑定一条判据但不登记 → 必须红
#    用例 test_newly_bound_criterion_without_registration_makes_guard_fail：
#    在**副本**上往 delivery.yaml 的 prep 加一条 automated 判据 +
#    在副本 stage_gate.py 的 stage_prep_passed() 函数体内加一行 criterion(...)，
#    先跑**副本自己的** stage_gate 确认 `prep.criteria_bound: 5`（绑定确实生效），
#    再跑门禁 → exit=1 且输出点名该判据。
```

三组断言均已转成永久用例（`tests/injection/test_criterion_effectiveness.py`），随
`injection` 批次每次执行；另有两条加固用例：
`test_registry_entry_pointing_to_missing_test_makes_guard_fail`（登记指向不存在的测试 → 红）、
`test_registry_entry_for_unbound_criterion_makes_guard_fail`（给未绑定判据预登记 → 红）。

### 2.3 `coverage_verifiable` 空实现现象：**复现成功**

```
## coverage_verifiable 空实现复现（副本上掏空）

  掏空前：不合规数据 → exit=1  ['scanned daily_run.criteria_bound: 4']
  掏空后：**同一份不合规数据** → exit=0  ['scanned daily_run.criteria_bound: 4']
```

掏空方式：把副本 `scripts/delivery/stage_gate.py` 的
`    cv = coverage_check(root)\n` 替换为
`    cv = CheckReport(checker="gutted-for-probe")\n`（真仓库零改动）。

**结论**：
1. 审计员报告的现象**为真且可复现**：掏空后 `criteria_bound` 恒为 **4**（AST 绑定数对掏空
   **完全无感**），而不达标数据下门禁由 `exit=1` 变 `exit=0`。
2. **反例能抓住它**：`daily_run::coverage_verifiable` 的反例测试断言"不合规输入 → `exit != 0`
   **且**输出含 `CV2`"。掏空后该断言必然失败 ⇒ **这条反例在空实现下会红**，
   掏空不可能静默通过。
3. 该结论本身**被钉成永久用例**：`test_daily_run_coverage_verifiable_counterexample_is_load_bearing`
   在副本上做同一掏空，断言"掏空后 `exit=0` 且 `criteria_bound` 仍为 4"。
   —— 也就是说，**"这条反例的判别力确实来自那个检查"也被机器守着**，
   而不是只在我口头声称。

### 2.4 无判别力探针（`G-03`：不可见不得当已验证）

```
## 无判别力探针（违例集合对比）

  daily_run::task_state_auditable  合规=0 违例 ｜ status 非法=0 违例 ⇒ 违例集合相同 = True
  expansion::review_append_only  含 failure/pending=2 违例 ｜ 失败被选择性删除=2 违例 ⇒ 违例集合相同 = True
```

### 2.5 门禁与批次

```
$ python system/scripts/ops/run_all_gates.py --timeout 30      # 真仓库，24 项
  ...
  traceback.py                       exit=1        0.08s
  stage_gate.py --stage prep         exit=0        0.15s
  ...
  criterion_effectiveness_guard.py   exit=0        0.20s
  非零计数                               1
（整体 3.53s；新门禁自身 0.20s，满足 P-05 < 0.5s）

$ sh system/scripts/ops/pre-commit.sh ; echo exit=$?
pre-commit → criterion_effectiveness_guard
  ... RESULT: PASS（0 violations）
pre-commit ✓ 全部门禁放行
exit=0
```

`criterion_effectiveness_guard` 在真仓库的完整输出（原样）：

```
== criterion_effectiveness_guard.py ==
  scanned counterexample_entries: 11
  scanned criteria_bound: 12
  scanned criteria_declared_automated: 18
  scanned criteria_not_implemented: 6
  scanned criteria_registry_entries: 13
  scanned criteria_without_counterexample: 1
  scanned ineffective_entries: 2
  scanned registry_entry_tests_resolved: 13
  scanned stages: 5
  note: 判据有效性缺口[daily_run::task_state_auditable]：反例义务改由「该判据无判别力」的探针测试承担 —— 实测无可判别检查（除 registry/delivery.yaml 的声明与 stage_gate 的 criterion() 声明之外，全仓库无任何检查（AST 实测该 id 在代码区只出现 1 次：stage_gate.py:575 的声明本身）；把任务 status 置为非法值 totally_bogus_status 时，阶段④ 的违例集合与合规输入**完全相同**（都是 0 条））；实现检查后该探针测试会红，从而强制更新本登记
  note: 判据有效性缺口[expansion::review_append_only]：该判据另有 counterexample 条目（证明**所绑定的那个检查**会拦），本条只针对其**字面语义中未被绑定的方面** —— 实测无可判别检查（该 id 的**字面语义**（delivery.yaml：append-only，(success, failure, pending) ⊆ 记录集，禁选择性删除）没有任何检查：AST 实测该 id 在代码区只出现 1 次（stage_gate.py:606 的 criterion() 声明本身）。门禁唯一与复盘相关的判别轴是 eval_layer **取值集合**，故『含失败记录』与『失败记录被选择性删除』两种输入给出**完全相同**的违例集合）；实现检查后该探针测试会红，从而强制更新本登记
  note: 无反例判据（已绑定但只有 ineffective 条目）：1 条（['daily_run::task_state_auditable']）—— 逐条见上面的缺口 note，**不计为已验证**（`G-03`）
  note: 未绑定判据[core_chain]：2 条（['graph_and_ask_traceable', 't01_t14_all_pass']）—— 属后续阶段待交付，**不计为已验证**（`G-03`：无被检对象不得当成已核）
  note: 未绑定判据[daily_run]：0 条（[]）—— 属后续阶段待交付，**不计为已验证**（`G-03`：无被检对象不得当成已核）
  note: 未绑定判据[expansion]：2 条（['investment_result_verifiable', 'research_standard_consistent']）—— 属后续阶段待交付，**不计为已验证**（`G-03`：无被检对象不得当成已核）
  note: 未绑定判据[nvidia_sample]：2 条（['chapter4_g_depth', 'evidence_locatable']）—— 属后续阶段待交付，**不计为已验证**（`G-03`：无被检对象不得当成已核）
  note: 未绑定判据[prep]：0 条（[]）—— 属后续阶段待交付，**不计为已验证**（`G-03`：无被检对象不得当成已核）
RESULT: PASS（0 violations）
```

批次（逐目录，`CONVENTIONS §一`）：

| 批次 | 命令 | 结果 |
|---|---|---|
| `injection` | `pytest tests/injection` | **162 例全过**（**分 5 片**，原因见 §4 V-08）：23 + 38 + 28 + 32 + 41 = **162** = `--collect-only` 的收集数 |
| `guards` | `pytest tests/guards` | `56 passed in 28.25s` |
| `gates` | `run_all_gates.py` | 24 项，`非零计数 1`（`traceback.py exit=1`，**既有**，见 §4） |
| `stage` | `verify.py --batch stage` | `exit=1`，原因 `['daily_run'] 未显式标记 BLOCKED` —— **既有**（main 上完全相同，见 §4） |

分片逐条：

```
tests/injection/test_criterion_effectiveness.py                                          23 passed in 35.19s
tests/injection/{test_audit_regressions,test_wiring_guards,test_stage_gate}.py           38 passed in 57.31s
tests/injection/{test_rules_lock,test_idempotency_rows,test_append_only,
                 test_time_contract,test_guards_defensive}.py                            28 passed in 53.67s
tests/injection/{test_prompt_injection,test_chain_steps_wiring}.py                       32 passed in 77.41s
tests/injection/test_guards_reject.py                                                    41 passed in 122.63s
```

### 2.6 零污染

```
$ git status --short                                    # 本 worktree（两个提交之后）
（空）

$ cd /Users/gaza/Developer/InvestSigh && git status --short   # 真仓库（主工作树）
?? system/tests/.audit-b11/    ← **不是我的**：`auditor-batch11` 的工作目录

$ git log --oneline -3
81d8e2a docs(reports): 判据有效性（G9）交付报告 —— 逐条反例原始输出 + H3 三组对照 + 空实现复现
9eff294 feat(guards): 判据有效性门禁 —— 把"绑定"从「接了」强化到「真的会拦」（缺口 G9）
5a314a3 fix(fixture/gitignore): derived/ 纠正为非唯一真源 + 夹具不再复制真仓库派生输出（G-RC-07/08）
```

我的全部实验都在 `system/tests/.probe-ce/` 副本内完成（该目录**已删除**），
`facts/**`、`derived/**`、`scripts/delivery/stage_gate.py` 真仓库文件**零改动**
（`git status` 已证）。`rules/**` 未被修改（`rules_lock_guard` 通过）。

---

## ③ 结果与发现

### 3.1 交付成立

- **H1**：12 条已绑定判据中 **11 条**有可执行反例（不合规输入 → `exit != 0` + 专属 `blocked_hint`），
  第 12 条以 `ineffective` 如实登记（G9-1）。
- **H2**：义务有机器绑定 —— **新绑定一条判据却不登记反例 → 门禁 `exit 1`**，
  已在本 worktree 分支上被永久用例守住（副本构造，真仓库零改动）。
- **H3**：三组正反对照齐备，且各自都是**永久用例**而非一次性命令。
- **特别要求**：`coverage_verifiable` 空实现现象**复现成功**（`exit=1 → exit=0`、
  `criteria_bound` 恒为 4），并给出**会红的反例** + 把它钉成永久用例。

### 3.2 G9-1（新发现）：`daily_run::task_state_auditable` **已绑定但无任何检查**

**证据（AST / 源码层）**：遍历代码区 `*.py`（排除 `tests/`、`reports/`），

```
=== task_state_auditable：代码区命中 1 处 ===
    scripts/delivery/stage_gate.py:575  [criterion() 声明]  criterion("daily_run", "task_state_auditable", v)
```

而 `criterion()` 按设计是**空操作**（其 docstring 自述"本函数**不做检查**"）。
⇒ "任务状态可核（`Ch8 §C.2`）"当前**没有任何被检谓词**。

**行为证据**：把任务 `status` 置为 `totally_bogus_status` → 阶段④ **`exit=0`**，
违例集合与合规输入**完全相同**（都是 0 条）。

**处置**：登记为 `ineffective`（附 `reason` + 探针测试），门禁逐条列出并计数
（`criteria_without_counterexample: 1`）。**不假造反例**。
一旦有人实现检查，探针测试**当场变红**，强制把登记改成 `counterexample`。

### 3.3 G9-2（新发现）：`expansion::review_append_only` **语义错位**

- `delivery.yaml` 声明：复盘 **append-only**（`(success, failure, pending) ⊆ 记录集`，禁选择性删除）。
- 实际绑定的检查：**「三层复盘齐备」**（`eval_layer ∈ {research_quality, forecast_quality,
  investment_result}` 是三层全在）。AST 实测该 id 在代码区同样**只出现 1 次**（第 606 行的声明本身）。
- **行为证据**：`{含 failure/pending}` 与 `{失败记录被选择性删除}` 两份输入 →
  违例集合**完全相同**（各 2 条，且这 2 条都是"未绑定判据台账"，与复盘无关）。
  ⇒ append-only 语义**零判别力**。

**处置**：该判据**同时**登记两条 ——
`counterexample`（证明"所绑定的三层检查**有**判别力"：缺层即拦，且该检查被掏空时本条会红）
+ `ineffective`（证明"字面 append-only 语义**未被守**"，附探针测试）。
建议后续：要么实现 append-only 检查（比对 `eval_result_history` 的单调包含关系），
要么把该 id 的 `statement` 改为"三层复盘齐备"（属**设计区措辞**，须由 team-lead 裁决，`R-04`）。

### 3.4 判据 → 反例 对照总表

| 阶段 | 判据 | 反例（不合规输入） | 结果 | 门禁是否绿基线 |
|---|---|---|---|---|
| prep | `four_deliverables` | 交付物 4 → 3 类 | `exit=1` + `交付物项数应为 4` | ✅ 绿 |
| prep | `rule_vs_impl_split` | `confirmed_rules` 清空 | `exit=1` + `confirmed_rules 为空` | ✅ 绿 |
| prep | `caliber_tbd_placeholder` | `p01` 偷改 `frozen` 缺确认字段 | `exit=1` + `frozen 但缺` | ✅ 绿 |
| prep | `no_paid_required` | `required[0]` 置付费订阅 | `exit=1` + `首版启动条件含付费订阅` | ✅ 绿 |
| nvidia_sample | `six_step_chain_complete` | baseline 缺 `driver_model` | `exit=1` + `六项深度缺` | ✖ 结构性红 |
| nvidia_sample | `derivation_reviewable` | `derived/` 无计算底稿 | `exit=1` + `四要素` | ✖ 结构性红 |
| core_chain | `multi_company_transmission` | 关系图仅 1 家公司 | `exit=1` + `关系图公司数` | ✖ 结构性红 |
| daily_run | `timing_replayable` | `check_record.run_date` 缺失 | `exit=1` + `缺 run_date` | ✅ 绿 |
| daily_run | `degrade_keeps_last_valid` | 先持有产出、后失败丢引用 | `exit=1` + `未保留 last_valid_result_ref` | ✅ 绿 |
| daily_run | `coverage_verifiable` | `research_depth='bogus_depth'` | `exit=1` + `CV2` | ✅ 绿 |
| daily_run | `task_state_auditable` | `status='totally_bogus_status'` | **`exit=0`，违例集合不变** | — **G9-1** |
| expansion | `review_append_only` | 三层复盘缺一层 | `exit=1` + `三层复盘缺层` | ✖ 结构性红 |
| expansion | `review_append_only`（append-only 语义） | 失败记录被选择性删除 | **违例集合不变** | — **G9-2** |

---

## ④ 如实登记的残余与不确定

### 4.1 全量 `injection` 批次**无法在单轮内跑完**（宿主删除配额，`V-08`）

```
$ pytest tests/injection -q -p no:cacheprovider
.............E.E.E.E.E.E.E.EE.E.EEE....EEEEEEEEEEEEEEEEEEEEEEE..EEEEEEEE [ 38%]
...（后续全 E）
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":10218,"threshold":9999,"scope":"turn",
 "targets":[".../tests/.work/test_model_side_steps_are_recorded_as_gap_not_ok[2-trace_dedup_verify]-26e8dc80"]}
```

- **不是测试坏了**：那是宿主对**每轮**删除操作的累积配额（`threshold: 9999`）。
  一次全量 ≈ 162 用例 × 每例一份 `system/` 副本 ≈ 4 万项删除 ⇒ 必然中途越限，
  之后**连单个用例目录都被拒删** ⇒ 每个夹具 setup 直接 `E`。
- **处置**：按 `V-08` 第 1 条"迭代用单批/单文件"，把 `injection` 批**按文件分 5 片**跑完
  （见 §2.5），**5 片合计数 162 = `--collect-only` 收集数 162**，无遗漏。
- ★ 本次实测给 `V-08` 补了一个精确数字：**`count=10218 > threshold=9999`**。
  也就是说 **`tests/injection` 在单轮内根本不可能一次跑完**，
  `verify.py --batch injection` 的 120s 超时值本身不是瓶颈、**配额**才是。
  **建议上报 team-lead**：`injection` 批的 `argv` 应改为"分片批次"或把该批拆成两个批次，
  否则 `verify.py --batch all` 每次都会在这一批"看起来超时/看起来失败"。

### 4.2 `traceback.py exit=1` 与 `stage` 批 `exit=1` 都是**既有**状态（非本次引入）

- `traceback.py`：真仓库 `facts/recommendations.jsonl` 的 `rec-nvda-001` 缺
  `['assumptions','computation']` ⇒ `G1-03` 覆盖率 0.0。**在主工作树 main 上跑同一命令同样
  `exit=1`**（已实测）。这属既有 `T-10` 真实违例的可见化，不属本批次。
  `pre-commit.sh` 不跑 `traceback`，故**不阻塞提交**。
- `stage` 批：`verify.py --batch stage` 期望"①PASS + ②–⑤ 全部 BLOCKED"，
  但真仓库 `facts/tasks.jsonl` 现有 **2 行带 `check_record`** ⇒ 阶段④ 不再 `BLOCKED` 而是
  **`daily_run: PASS`** ⇒ 期望值函数判"未显式标记 BLOCKED" → `exit=1`。
  **在 main 上完全相同**（已实测：`main stage_gate exit=1`，`note: daily_run: PASS`）。
  ⇒ 是 `verify.py::_stage_gate_verdict()` 的**预期值随真实数据过期**，非本批次引入。
  **建议上报 team-lead**（属 `verify.py` 的维护者范围）。

### 4.3 未把新门禁加进 `tests/guards/test_exit_code_contract.py::GUARDS` 矩阵

- 该矩阵自带 `assert len(GUARDS) == 20`，而 `run_all_gates.GATES` 实有 **24** 项
  （`shell_var_guard` / `graph_integrity_guard` / `locator_check` 三个既有守卫**同样不在矩阵里**）。
  改矩阵要同时改 `len` 断言，与 `ws-guards-catchup` 的范围**直接重叠**（并行工作流冲突）。
- **等价覆盖已由本文件自带**：`test_criterion_effectiveness_guard_passes_on_pristine_tree`
  （干净输入 → 0 + 报 `scanned`）与 `test_guard_reports_input_error_for_missing_code_root`
  （`code_root` 缺失 → `2`），与矩阵的三条契约一致。
- ⇒ **残余**：本门禁未受矩阵的**参数化**约束（矩阵会逐个守卫跑同一条契约）。
  建议由 `ws-guards-catchup` 统一收纳（一并把既有三个守卫补进矩阵）。

### 4.4 `ineffective` 口子的强度（如实说明）

`ineffective` 是"已绑定但无判别力"的合法出口，**它本身可被滥用**：
把一条有判别力的判据标成 `ineffective` 即可免除"给反例"的义务。
本设计的防御是：**该条目的测试必须断言"不合规输入下违例集合与合规输入完全相同"**。
若该判据其实有判别力，这个测试**立即失败** ——
即"谎报"的代价是**写一个必然失败的测试**，而不是改一行数据（铁律 5）。

★ **残余**：理论上仍可把 `ineffective` 条目的 `test` 指向一个**恰好通过**的、与本判据无关的
函数。本门禁只能强制"测试函数名含判据 id"（提高门槛），**无法**验证该测试的断言语义。
彻底的解法是让门禁**自己**跑反例（成本高、且需要夹具），本次未做。
当前缺口规模已被钉住并逐条可见（`ineffective_entries: 2`、
`criteria_without_counterexample: 1`），任何增长都会在门禁输出里显形。

### 4.5 未做的事（明确边界）

- **未**修改 `stage_gate.py`（不新增/不删除任何 `criterion()` 绑定）—— 本批次只**守**绑定，不改语义。
- **未**为 G9-1 / G9-2 实现缺失的检查（那属 `stage_gate` 语义变更 + 设计区措辞问题，`R-04` 须上报）。
- **未**改 `verify.py` 的批次表（`CONVENTIONS §一 V-02` 注明：并行工作流的 Agent **不得**自行改
  `verify.py`，只报"需新增批次"）—— 本报告 §4.1 即为该上报。
- **未**改 `conftest.py`（夹具 1.4s/例 的 `raw/` 清理开销属既有实现，实测 main 上同样 1.4s，
  非本批次引入；不属我的范围）。

---

## 五、合并后复验（本节在分支并入 main 之后补写）

上面 §一~§四 的全部数字都测于本分支的基线 `5a314a3`。分支并入 main 后
（`bc26933 merge ws/criterion-effectiveness`），本节的数字**测于合并后的 main 树**，
以免"只在旧基线上绿"。

### 5.1 复验命令与实录

复验在 main 的**干净临时工作树**上做（`git worktree add <tmp> main --detach`，
用完 `git worktree remove` 删除），先按 `CONVENTIONS §一 V-07` bootstrap `rules/` 权限。

**① 门禁本身**
```
$ python system/scripts/checks/criterion_effectiveness_guard.py system
EXIT=0
  scanned criteria_bound: 12
  scanned criteria_declared_automated: 18
  scanned criteria_not_implemented: 6
  scanned criteria_registry_entries: 13
  scanned registry_entry_tests_resolved: 13
RESULT: PASS（0 violations）
```
四个扫描数与基线**完全一致**。另对两个输入做了直接比对，确认未漂移：
```
$ git diff ws/criterion-effectiveness main -- system/scripts/delivery/stage_gate.py
（空）
$ git diff ws/criterion-effectiveness main -- system/registry/delivery.yaml
（空）
```

**② 反例测试文件（23 条）**
```
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_criterion_effectiveness.py
collected 23 items
tests/injection/test_criterion_effectiveness.py .................
→ 打到第 17 条时被宿主 SIGTERM 掐断（环境问题，见 §5.2；**非测试失败**，17 个点全为通过）

$ sh system/scripts/ops/run_pytest.sh tests/injection/test_criterion_effectiveness.py \
    -k "makes_guard_fail or is_registered_in_runner or reports_input_error"
collected 23 items / 17 deselected / 6 selected
tests/injection/test_criterion_effectiveness.py ......                   [100%]
====================== 6 passed, 17 deselected in 32.56s =======================
RC=0
```
中断点前 17 条与续跑的 6 条**互不重叠**，合起来覆盖全部 23 条。
**续跑的 6 条正是 H2/H3 义务测试**（`H2`：删任一登记 → 门禁必红 / 新绑定未登记 → 必红 /
登记指向不存在的测试 → 必红 / 登记了未绑定判据 → 必红；`H3`：门禁已注册进
`run_all_gates.py` + `pre-commit.sh` / `code_root` 缺失 → 返 `2`）。

**③ 全门禁**
```
$ python system/scripts/ops/run_all_gates.py --timeout 30
  ...
  criterion_effectiveness_guard.py   exit=0        1.51s     ← 本次新增，24 条门禁
  非零计数                               1
```
唯一非零仍是 `traceback.py exit=1`（§4.2 已定性为既有 `T-10` 真实违例），与 G9 无关。
新门禁 1.51s，未显著拖慢（既有 18 条合计 ≈3.7s 的基线未变）。

**④ pre-commit**
```
$ sh system/scripts/ops/pre-commit.sh
pre-commit ✓ 全部门禁放行
RC=0        ← 11 条（含本次新增的第 ⑪ 条）
```

### 5.2 本节两次 SIGTERM 的定性（**环境，非代码**）

`pytest` **不能**在 Bash 沙箱内直接跑：`sitecustomize.py` 的 FS broker 在每次文件操作上
往宿主走 IPC，夹具每例 `copytree` 130 个文件 ⇒ 累积数万次往返后**进程卡死/被 SIGTERM**，
且**卡点漂移、无任何输出**，极易被误读成"测试挂了"。
正确跑法是 `sh system/scripts/ops/run_pytest.sh tests/<子目录>`（该脚本自行把 broker 关掉）。
另注意 PATH 上的 `python`（`versions/3.13.12`）**没有 pytest**，
`python -m pytest` 会报 `No module named pytest`（误导），不要据此判断环境坏了。

这与我早前实测到的宿主删除配额（`SAFE_DELETE_BULK_CONFIRM_REQUIRED {"count":10218,"threshold":9999}`）
是**两个独立**的环境限制；本文所有测试结论均已在这两类干扰之外取得。

### 5.3 §4.1 / §4.2 两条上报的**最新状态**（本报告写完后 main 已前进，故在此更正）

| 上报项 | 当前状态 |
|---|---|
| §4.1 `injection` 批一次跑不完（宿主删除配额） | main 的 `verify.py` 已被 team-lead 重构（`+61/-16`）。**我未在重构后复验该批** —— 本轮删除配额已被前面复验吃掉，再跑必然假红。**此条仍未经我复验**，如需请另行验证。 |
| §4.2 `stage` 批期望值随真实数据过期 | **已修**：`3f4c372 fix(verify): stage 批次判据改为数据驱动（原写法把"哪些阶段该阻塞"写死 → 已过期成假红）`。本报告 §4.2 的"建议上报"已完成。 |
| §4.2 `traceback.py exit=1` | **仍未修**（既有真实违例 `rec-nvda-001` 缺 `['assumptions','computation']`）。`pre-commit` 不跑它，故不阻塞提交。 |

### 5.4 G9-1 / G9-2 已被 team-lead 登记

我上报的两个缺口已在 main 的 `016f311` 中登记为 `G9-1` / `G9-2` / `G-28`。
**本批次未**自行修改 `delivery.yaml` 的判据措辞（字面语义属设计区 `R-04`），落点归 team-lead。

### 5.5 本节新增证据下的清洁性

- 两个临时工作树（复验 main 用）**均已 `git worktree remove` 删除**，`.worktrees/tmp-*` 无残留。
- 本分支工作树 `git status --short` **空**。
- 真实仓库 `git status --short` 仅见**他人**产物（` M system/tests/guards/test_exit_code_contract.py`
  —— 应为 `ws-guards-catchup` 在收编 `GUARDS` 矩阵；`?? system/tests/.audit-b11/` —— `auditor-batch11`）。
  **我未触碰这两者**，本节实验全部只在副本内进行，真实 `facts/`、`derived/`、`space/` 未被写入。

---

## 六、`G9-1` / `G9-2` 补实现（team-lead 两条裁定落地）

**提交**：`e15d894 feat(stage_gate): 补实现 G9-1/G9-2 —— task_state_auditable 与 review_append_only 从「有声明」到「真的会拦」`
（基线 `d74a829`，已 `git merge main` 取得 `append_only_guard` 的 `G-RC-12` 修复）

### 6.1 改了什么（逐条对裁定）

| 裁定 | 落地 |
|---|---|
| `G9-1`：`daily_run::task_state_auditable` **必须补实现**，不许以 `ineffective` 收尾 | 在 `stage_daily_run_passed()` 内实现 `施工图:203` 的 `all_tasks_have_status(run_window)`：每行 `status` **存在且 ∈ `TaskStatus` 五态**；违例带 `task_id` + 实际值 + 合法域。原 `ineffective` 探针如期变红 → 改成正向反例，并另加**判别力绑定**测试。 |
| `G9-2`：`review_append_only` **按设计实现 append-only**，不许改 id 措辞 | 按 `Ch10 §D.5` 补两个**互不重叠**的被检面（6.3）；`delivery.yaml` **一行未动**。 |
| `G9-2`：先查清 `expansion` 里有没有「三层齐备」自己的 id | **没有**：`delivery.yaml` 阶段⑤ `pass_criteria_testable` **恰好 3 条**、`exit_artifacts: ['三层复盘记录']` ⇒「三层齐备」**只在退出物里，无通过判据身份**（一手事实已自查复核）。裁定 = **保持中间态**，升级为 **`T-15`**（见 6.5.1）。 |
| `G9-2`：`(success, failure, pending)` 三类记录 | **全代码区无载体**（grep 只命中 `delivery.yaml:132` 那句声明本身）⇒ 按 `G-03` 保留为**临时 `ineffective`** + 探针。裁定 = **载体属设计范围**，升级为 **`T-17`**；已按要求附**推荐方案（只写未实现）**（见 6.5.2）。 |
| 现场变化：`append_only_guard` 在 worktree 里曾恒空放行（`G-RC-12`） | 已 `merge main` 取得修复，并**把它变成阶段⑤ 的可检项**（6.3 ①）。 |

### 6.2 `G9-1` 的可执行证据（**原始输出 + 退出码**）

实验在**隔离副本**上做（只复制 `facts/ registry/ rules/ scripts/ schema/ derived/ raw/ config/`，真实 `facts/` 零接触）：

```
═══ 1/4 合规输入（真实 4 行，status 全合法）═══
$ python <copy>/scripts/delivery/stage_gate.py <copy> --no-report --stage daily_run
EXIT=0
  scanned daily_run.criteria_bound: 4
  scanned daily_run.tasks: 4
  note: daily_run: PASS
RESULT: PASS（0 violations）

═══ 2/4 形态一：值非法 ═══
（把唯一一行的 status 改为 totally_bogus_status）
$ python <copy>/scripts/delivery/stage_gate.py <copy> --no-report --stage daily_run
EXIT=1
  scanned daily_run.criteria_bound: 4
  [FATAL] daily_run @ facts/tasks.jsonl:0 — check_1 的 status='totally_bogus_status'
          不在 TaskStatus 合法取值域内（合法值 = ['done', 'failed', 'pending_evidence',
          'queued', 'researching']）⇒ 任务状态不可核
RESULT: FAIL（1 violations）

═══ 3/4 形态二：整行无 status 键 ═══
$ python <copy>/scripts/delivery/stage_gate.py <copy> --no-report --stage daily_run
EXIT=1
  [FATAL] daily_run @ facts/tasks.jsonl:0 — check_1 的 status=None
          不在 TaskStatus 合法取值域内（合法值 = ['done', 'failed', 'pending_evidence',
          'queued', 'researching']）⇒ 任务状态不可核
RESULT: FAIL（1 violations）

═══ 4/4 判别力绑定：把副本里那条谓词掏空成恒假 ═══
（copy/scripts/delivery/stage_gate.py：if not isinstance(got, str) or got not in legal_status:
                                        → if False:  # gutted-for-probe）
$ python <copy>/scripts/delivery/stage_gate.py <copy> --no-report --stage daily_run
EXIT=0                      ← 同一条不合规输入**不再被拦**
  scanned daily_run.criteria_bound: 4      ← 而「绑定数」**没有任何变化**
  scanned daily_run.tasks: 1
RESULT: PASS（0 violations）
```

**4/4 是本批次的核心结论**：`criteria_bound` 恒为 4 而门禁由红变绿 —— 再次实测「绑定只证明接了，
不证明真的在查」；而 2/4 与 3/4 就是**唯一**能发现这件事的观测。

### 6.3 `G9-2` 的可执行证据（**原始输出 + 退出码**）

`review_append_only` 现绑定两个被检面，**互不重叠**：

**① append-only 路径真的覆盖本真源**（读 `append_only_guard` 的**判据**，不读输出文字，`G-06`）

```
═══ 基线（append_only_guard 原样）═══
$ python <copy>/scripts/delivery/stage_gate.py <copy> --no-report --stage expansion
EXIT=1     scanned expansion.aog_covers_carrier: 1
FATAL 条数=2        ← 两条都是既有的「未绑定判据台账」，与本判据无关

═══ 掏空：把副本的 append_only_guard.facts_pathspec() 改成 glob *.bak ═══
$ python <copy>/scripts/delivery/stage_gate.py <copy> --no-report --stage expansion
EXIT=1     scanned expansion.aog_covers_carrier: 0
  [FATAL] expansion @ scripts/checks/append_only_guard.py:0 — append-only 守卫的
     pathspec='…/facts/*.bak' 未覆盖本函数所读的 facts/*.jsonl ⇒ 复盘记录所在真源
     不在「既有行不得改写」的射程内（`Ch10 §D.5` 第 2 行 / `Ch9 §3.4.2`）

违例集合差（掏空后 − 基线）= **恰好这 1 条** ⇒ 归因干净
```

**② 已声明过的 `eval_layer` 层不得从记录集里消失**（`Ch10 §D.5` 第 3 行「禁'只留赢的'」）

```
═══ 合规（每 task 一层、三层齐备）═══
$ python <copy>/scripts/delivery/stage_gate.py <copy> --no-report --stage expansion
EXIT=1     scanned expansion.aog_covers_carrier: 1
           scanned expansion.tasks_with_eval_history: 3
RESULT: FAIL（2 violations）   ← **两条都是既有的未绑定判据台账**，专属 hint 不出现

═══ 反例：同一 task 在追加序上先声明三层、后只剩一层 ═══
（t1: eval_result_history=[research_quality, forecast_quality, investment_result]
  → 下一行 t1: eval_result={research_quality}）
$ python <copy>/scripts/delivery/stage_gate.py <copy> --no-report --stage expansion
EXIT=1
  [FATAL] expansion @ facts/tasks.jsonl:0 — t1 的复盘记录里层
    ['forecast_quality', 'investment_result'] 消失（此前已声明过） ⇒ 违反
    『已声明过的层不得从记录集里消失』（Ch10 §D.5 禁「只留赢的」）
RESULT: FAIL（3 violations）   ← 1 条本判据 + 2 条既有台账
```

★ **为什么这条不是「重造第二套 append-only 比对」（`G-06`）**：该反例在 **diff 层面完全合法**
（纯追加，没有任何既有行被改写）⇒ `append_only_guard` 对它**必然放行**。它违反的是**语义**
（用户看到的历史被悄悄收窄）。两者被检面**不重叠、互补**：前者管"行有没有被改"，
后者管"层有没有被丢"。

★ **阶段⑤ 的归因方式**：它在合规输入下**结构上就是 `exit 1`**（两条未绑定判据的台账条目），
故归因不靠 red/green，而靠**专属 hint + 违例集合差**（与阶段②③ 同一手法，见 §3.1）。

### 6.4 顺带修掉门禁自身的一处设计缺陷

补 `G9-2` 时，**门禁自己 FATAL 了**——这正是"反例必须可执行"的价值：

```
[FATAL] G9 @ registry/criterion_counterexamples.yaml:0 —
        #13: 判据 expansion::review_append_only 的 counterexample 条目重复登记
[FATAL] G9 @ registry/criterion_counterexamples.yaml:0 —
        #14: 判据 expansion::review_append_only 的 counterexample 条目重复登记
```

原实现把去重口径定为「`(stage, criterion_id, kind)` 三元组唯一」。但一条判据**本来就可能有多条
互不重叠的违反轴**（`review_append_only` 就有 ①三层缺层 ②已声明层消失 ③pathspec 没罩住 三个
独立被检面），把它们压成一条会**丢失证据**。

⇒ 去重口径改为「**测试路径全局唯一**」（防的是同一测试被登记多次冒充多条证据，而不是防同判据多轴）。
义务本身（A：每条已绑定判据 ≥1 条 `counterexample`）**不受影响**。

### 6.5 待裁定项与裁定结果（张力 `T-15` / `T-17`）

#### 6.5.1 ① 「三层齐备」的身份 —— 裁定：**保持中间态**，升级为需求方待裁项 `T-15`

**★ 可核的肯定事实**（`delivery.yaml` 是**实现区可核**的声明面；本节实测复核，非转述）：

```
$ python - <<'PY'   （读 registry/delivery.yaml，取 delivery_stages 里 key=expansion 的那条）
阶段⑤ key = expansion | delivery_stage = 5
pass_criteria_testable 条数 = 3
   - research_standard_consistent | automated | 研究标准**保持一致**（Ch4 §G）
   - investment_result_verifiable | automated | 投资结果**可核验**（`Ch10 §N10.3-04` 前向记录）
   - review_append_only           | automated | 复盘 **append-only**（`(success, failure, pending)` ⊆ 记录集，禁选择性删除）
exit_artifacts = ['三层复盘记录']
```

⇒ **「三层齐备」只在 `exit_artifacts` 里，没有通过判据身份**；`pass_criteria_testable` 里
**没有**它自己的 id。这正是现在它被 `review_append_only` 顶着的**结构性原因**。

★ **口径修正（采纳 team-lead 的裁定并自查）**：我原先的表述偏向「**全设计区**没有逐字出处」——
那是**穷举式否定**，易被「你搜漏了」反驳。现改为上面的**可核肯定事实**：
**`delivery.yaml` 阶段⑤ 的判据列表恰好 3 条 + 退出物实际清单**，任何人可复跑复核。
设计侧佐证（`Ch10 §C.1` 只定义 `eval_layer` 取值域、`§C.4:250` 的
`assert layer in VALID_LAYERS` 亦为取值域断言）**降为佐证**，不再作为主论据。

**裁定**（team-lead，选项 **(c)** —— 既非 (a) 也非 (b)）：
- **不批 (a) 新增 id**：新增 id 就必须让 `delivery.yaml` 声明它（否则会是"绑定了一条未声明的判据"，
  `assert_criteria_implemented` 与 `criterion_effectiveness_guard` 都会红）；而
  `pass_criteria_testable` 是 `施工图 §2 阶段⑤` **通过判据列表的转写**，
  **给它加一条 = 改需求面**，超出实现方权限。
- **不批 (b) 删检查**：那会让阶段⑤ 的退出物无人守，且已实现的真 append-only 语义白做。
- ⇒ **保持现状**：检查保留、仍挂 `review_append_only` 名下、在登记里**显式标"★ 待裁定"**。
  同时做到：不违 `R-04`（未新增 id）、不静默（待裁定白纸黑字进登记）、判别力不丢（真的会拦）。

**已落账**：该张力升级为 **`T-15`**（「退出物『三层复盘记录』是否升格为阶段⑤ 通过判据」），
本节的实测即是它最完整的一份证据陈述。登记表对应条目的 `note` 已同步补上上述一手事实。

#### 6.5.2 ② `(success, failure, pending)` 的载体 —— 裁定：**属设计范围**，待裁项 `T-17`

实测**全代码区无承载**：

```
═══ 证据 4/4：三类记录这条的判别力实测为 0 ═══
A 混搭(success/failure/pending) EXIT=1
B 只留赢的(全 success)           EXIT=1
→ 两份违例集合**完全相同**（2 条对 2 条）
```

`Ch10 §D.5:332` 逐字要求「成功 / 失败 / `pending`（待判断）各有结构性记录，不可选择性删除」，
但 `success`/`failure`/`pending` 三元组在代码区**只出现在 `delivery.yaml:132` 那句声明里**
（`schema/models.py` 无对应枚举、`facts/*.jsonl` 无对应字段）⇒ 按 `G-03` 只能显式记账为
**「无被检对象」**。已登记为**临时 `ineffective`** + 探针测试 —— 一旦有载体，探针**当场变红**，
强制更新登记（铁律 5）。

**裁定**：team-lead **不单方面指定载体**（载体决定**真源结构**，属设计范围）⇒ 升级为 **`T-17`**。

**★ 推荐方案（应 team-lead 要求给出；只写、未实现，供需求方拍板）**：

| 项 | 建议 |
|---|---|
| 载体 | **复用现有复盘记录真源**：`facts/tasks.jsonl` 的 `eval_result` / `eval_result_history`（`Ch10 §C.4:253` 已钉死 `append("facts/tasks", e)`） |
| 新字段 | `result_kind ∈ {success, failure, pending}`（**加在既有对象上**） |
| ★ 为什么**不**新建表 | `facts/` 的**表集合不得增删改名**（22 stem 已冻结） ⇒ 新建表 = 改真源结构，代价与风险都远大于加一个字段；且 `Ch10 §D.5` 说的是"**记录**"，不是"表" |
| 配套反例 | 断言 **`{success, failure, pending} ⊆ 记录集的 `result_kind` 取值集合**（即三类**各有**结构性记录）；反例 = 只留 `success`（或删掉 `failure` 行）⇒ 阶段⑤ 必须红 |
| 与现有 ② 的分工 | 现有 ② 判"**层**（`eval_layer`）不得消失"；新字段判"**复盘结果类别**（`result_kind`）不得消失"。两者轴不同 ⇒ 不重复，可并存为两条 `counterexample` |
| 落点归属 | 需需求方先定向（`T-17`）；定位后在 `scripts/review/record_eval.py` 写入侧与 `stage_gate` 读取侧各补一处（**同一字段**，`G-06`） |

★ 实现后**同一条探针测试会当场变红** —— 这是刻意设计的移交形态（铁律 5）。

### 6.6 诚实标注：`① append-only 覆盖性` 的判别力是**弱**的

必须说清楚：6.3 ① 的判据是「守卫的 pathspec 前缀 == 本函数所读的 facts 目录 + glob `*.jsonl`」。
它**近乎恒真**（pathspec 由 `root/facts` 推出，天然指向该目录）——它的价值是**把"机制真的罩住
这个真源"从假定变成可检项**，而不是提供强判别力。`review_append_only` 的**真判别力在 ②**。

同理，`aog_tracked_files` 在**夹具副本**里恒为 `0`（副本的 facts 不在 git 跟踪范围内），
故它只**记账**、不判红 —— 否则会把环境伪影误判成数据违例（与 `append_only_guard` 自身
`count_tracked_matches` docstring 里的既定口径一致）。

### 6.7 本节的验证汇总（**实测命令 + 退出码**）

| 验证 | 命令 | 结果 |
|---|---|---|
| 分片 B（含本文件 26 例） | `sh system/scripts/ops/run_pytest.sh tests/injection/test_criterion_effectiveness.py tests/injection/test_guards_defensive.py` | **31 passed**，`RC=0` |
| 分片 F（含分片配额断言） | `sh … tests/injection/test_stage_gate.py tests/injection/test_wiring_guards.py tests/injection/test_shard_coverage.py` | **29 passed**，`RC=0` |
| 门禁契约 | `sh … tests/guards` | **69 passed**，`RC=0` |
| 阶段④ 爆炸半径 | `sh … tests/daily` | **43 passed**，`RC=0` |
| 全门禁 24 条 | `python system/scripts/ops/run_all_gates.py --timeout 30` | 仅 `traceback.py exit=1`（既有 `T-10`）；`criterion_effectiveness_guard exit=0 (2.04s)`；`stage_gate --stage prep exit=0 (0.72s)` |
| 提交门禁 | `sh system/scripts/ops/pre-commit.sh` | `pre-commit ✓ 全部门禁放行`，`RC=0`（11 条） |

**性能**：`stage_gate --stage prep` 曾因我把 `schema.models`（pydantic 重模块）放模块顶层而
由 **0.51s → 0.86s**；已改**就地导入**（只有阶段④ 用得到它），`prep` 回到 **0.72s**，
差异只由 `daily_run` 承担。新门禁 `criterion_effectiveness_guard` 2.04s。

### 6.8 ⚠️ 分片余量约束与 team-lead 的处置裁定

`tests/injection/test_criterion_effectiveness.py` 由 23 → **26** 例，所属分片
`injection-b` 由 28 → **31** 例，而 `test_shard_coverage.py::test_shard_case_counts_within_quota`
的上限是 **32**：

```
$ PYTHONPATH=tests <py> -m pytest tests/injection/test_criterion_effectiveness.py \
      tests/injection/test_guards_defensive.py --collect-only -q --noconftest
31 tests collected
```

⇒ **往本文件再加 >1 个用例就会让分片配额断言变红**（这正是它该有的行为：防"某片单轮跑不完 ⇒
门禁被静默关掉"）。

**team-lead 裁定（已落账）**：
- **本卡继续做完，不动分片** —— 分片重组由 team-lead 做（`verify.py` 是**共享文件**，
  多方同时改必冲突，且属 `V-02` 保护范围）⇒ **我未改动 `verify.py`**。
- ★ **新增用例一律进新文件**，不得再往 `test_criterion_effectiveness.py` 里塞 ——
  因为 **13-A（`chapter4_g_depth`）与 13-C（`evidence_locatable`）都要各加一条反例用例**，
  该文件已无余量。
- 若确需再加：建 `tests/injection/test_criterion_effectiveness_expansion.py`，
  并登记进**有余量的片**（片内 ≤32 是硬约束，由 `test_shard_coverage.py` 核）。
- ⇒ **我不得为了让新用例有地方而去调别人的分片**（那是 team-lead 的活）。

### 6.9 本节清洁性

- 副本 `system/tests/.probe-g9/`（本节全部实验所在）**已 `rm -rf` 删除**，无残留。
- 本分支工作树 `git status --short` **空**；`git status --short system/facts/` **空**（真实真源未被写入）。
- `rules/**` 未被写入（副本内仅 `chmod u+w` 以便探针改 `append_only_guard`，真仓库 `rules/**` 仍 0444：
  由 `rules_lock_guard` + `injection_guard` 两条门禁各自复核过，均 `exit=0`）。
- 未触碰 `pipeline.py` / `chain_steps.py`（共享文件）与 `verify.py`。
