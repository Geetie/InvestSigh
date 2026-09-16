# 修复报告 · `ws/daily-fix` —— 批次 10 独立审计 `ch8 AC-5 = FAIL`（反 KPI 测试在空真源上恒真）

> 修复者：工程师（`ws-daily-fix-engineer`）｜ 工作树 `ws-daily-fix`，分支 `ws/daily-fix`，基点 `main = 960634d`
> 范围：**仅** `system/tests/daily/**`（+ 本报告）。未动 `scripts/**`、`rules/**`、设计区、`conftest.py`、`CONVENTIONS.md`。
> 真仓库 `facts/` **零改动**（收工复核：`claims=5 / dependency_edges=3 / companies=2 / tasks=3 / baselines=1 / recommendations=1 / prices=0`）。

---

## ① 做了什么（文件 + 位置 + 改动要点）

**唯一改动文件**：`system/tests/daily/test_daily_run.py`

### 缺陷复述（审计原文，属实）

> `ch8` 声称覆盖反 KPI 的用例建在**空真源**夹具上（`conftest.py` 契约"真源为空"）
> ⇒ **无主张 ⇒ 无第 6 步 ⇒ `signals_emitted == 0` 恒真**，**不构成守卫**。

### 修法（`CONVENTIONS.md §二 G-03` 的精神同样适用于测试：空样本不得当"已核"）

按 `G-RC-02`（**测试自己声明自己的数据**）在夹具副本里**播种**能走到 step 6 的最小真源，
把 `test_no_change_day_emits_zero_signals` 从"真空断言"改成**有判别力的守卫**：

| 用例 | 方向 | 断言要点 |
|---|---|---|
| `test_no_change_day_emits_zero_signals`（改） | **(a) 无交易信号的运行日** | `signals_emitted == 0` **且** step 6 **确实产出了建议**（`action=pending`）→ 零信号是"决策结论"而非"路径缺失" |
| `test_change_day_signal_is_counted`（**新**） | **(b) 有交易信号的运行日** | `signals_emitted == 1` + 建议 `action=buy` → **反向对照**，证明它不是"永远 0" |
| `test_anti_kpi_guard_discriminates`（**新·参数化**） | 守卫两向 | 四组合 `(changed, signals)` 逐一定位 `G1-02①` 命中与否；含真仓库形态 `(False, 1)` |
| `test_no_signal_assertion_has_discrimination`（**新**） | 判别力反证 | **故意注入违规** → (a) 的断言必红 **且** 守卫必命中（`G-05` / `G-16`） |

**播种的最小数据集**（见 `_seed_step6_inputs()`，**2 张真源表**，不新增 JSONL —— 守 `Ch9 §3.3.3` 的 18 文件不变）：

- `facts/prices.jsonl`：2 证券 × 2 行情点（同起止日 `2026-09-01`..`2026-09-10`）：
  个股 `usNVDA`（`100 → 110` 或 `100 → 130`）、基准 `usAGIX`（`100 → 110`）；
- `facts/benchmarks.jsonl`：1 行**主基准对象**，**显式 `security_id: usAGIX`**。

**为什么"这些够走到 step 6"**（按 `scripts/decision/run_decide.py::run_default` 实际步序走查，
**先读代码后写测试，未凭猜**）：

```
_load_truth_series(读 facts/prices.jsonl)              # 每个证券 ≥2 点，否则 inputs_unavailable
  → _load_primary_benchmark(读 facts/benchmarks.jsonl)  # 主基准对象，缺 → 退化/securities_unresolved
  → _resolve_benchmark_security(用显式 security_id)
  → _select_company_security(行情里除基准外的**唯一**证券)
  → _run_core: compute_total_return(个股) × compute_total_return(基准)
      → 前置门 can_apply_return_comparison → 5 规则 decide(JudgmentChange(fact_set_changed=True))
      → 落 facts/recommendations.jsonl
```

收益率只由**终点价**决定（起点价恒 `100`）：两价相等 ⇒ 相对 `uncertain` ⇒ R3 `pending`（**0 信号**）；
个股 > 基准且绝对为正 ⇒ R1 `buy`（**1 信号**）。→ 恰好覆盖 (a)/(b) 两向。

**未改**：`scripts/decision/**`、`scripts/orchestrate/**` 等（见 `④`，根因 `G-RC-04` 不在本流写入域）。

---

## ② 怎么验证的（原样命令 + 原样输出 + 退出码）

### ★ 最小数据集真跑（正反两向）：探针原样输出

命令（探针脚本一次构建两个副本，一个 (a)、一个 (b)）：

```
$ CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0 \
    /Users/gaza/.workbuddy/binaries/python/envs/default/bin/python /tmp/probe_seed.py
```

输出（原样，节选到关键字段）：

```
== (a) no-signal day (equal returns) ==
  signals_emitted=0 changed=False blocked=True degraded=True
  recommendations=[('pending', 'rec-usNVDA-2026-09-01')]
  check_records=[{'changed': False, 'check_id': 'check_2026-09-16_full', 'degraded': True, 'judgment_change': {}, 'run_date': '2026-09-16', 'scope': 'full', 'signals_emitted': 0}]
  no_signal_day.passed=True violations=[]
== (b) buy day (company outperforms) ==
  signals_emitted=1 changed=False blocked=True degraded=True
  recommendations=[('buy', 'rec-usNVDA-2026-09-01')]
  check_records=[{'changed': False, 'check_id': 'check_2026-09-16_full', 'degraded': True, 'judgment_change': {}, 'run_date': '2026-09-16', 'scope': 'full', 'signals_emitted': 1}]
  no_signal_day.passed=False violations=['无变化日产了新信号: run_date=2026-09-16 signals_emitted=1']
```

**判读**：

- **(a)**：`signals_emitted=0`，且**真产出一条 `pending` 建议** ⇒ 路径走到了 step 6，零信号是**决策结论**（非真空）；
  其 `check_record` = `changed=False + signals=0` ⇒ 守卫放行。
- **(b)**：`signals_emitted=1` + `buy` 建议 ⇒ **信号正常计数**（反向对照成立）。
- ★ **(b) 的 `check_record` = `changed=False + signals=1`，与真仓库 `G-RC-04` 是同一形态**，
  `no_signal_day` 对它 FATAL —— 证明**本层能发现"无变化却产信号"**（根因见 `④`）。

### ★ 判别力反证（`③`）：故意制造违规 → (a) 必红

**注入动作**（临时、一次性，已还原）：把被测链路的 step 6 处理器改为恒报 `signals_emitted=1`
（`system/scripts/decision/step.py`：`signals_emitted=int(report.signals_emitted)` → `signals_emitted=1`），
即"无变化时也产 1 个信号"，然后跑 (a) 用例：

```
$ sh system/scripts/ops/run_pytest.sh tests/daily/test_daily_run.py -q -k "no_change_day_emits_zero_signals"
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_no_change_day_emits_zero_signals _____________________

code_root = PosixPath('.../system/tests/.work/test_no_change_day_emits_zero_signals-660daba7/system')

    def test_no_change_day_emits_zero_signals(code_root: Path) -> None:
        _seed_step6_inputs(code_root, company_end_price="110", benchmark_end_price="110")
        report = daily_run.run_daily(code_root, _RUN_DAY)
>       assert report.signals_emitted == 0
E       AssertionError: assert 1 == 0
E        +  where 1 = DailyRunReport(run_date='2026-09-16', scope='full', blocked=True, degraded=True,
E                changed=False, signals_emitted=1, gap...).signals_emitted
tests/daily/test_daily_run.py:160: AssertionError
=========================== short test summary info ============================
FAILED tests/daily/test_daily_run.py::test_no_change_day_emits_zero_signals
1 failed, 11 deselected in 2.41s
EXIT=1
```

⇒ **(a) 不是恒真断言**：注入 1 个信号即红。**注入已完全还原**（`git diff --stat system/scripts/decision/step.py` 为空，
`grep TEMP-DISCRIMINATION` 无残留；`git status` 仅余 `tests/daily/test_daily_run.py`）。

### ★ 修复后最终子集（`V-08`：只跑本子集）

```
$ sh system/scripts/ops/run_pytest.sh tests/daily -q
...........................................                              [100%]
43 passed in 44.39s
EXIT=0
```

反 KPI 相关用例逐条（`-v`，原样）：

```
tests/daily/test_daily_run.py::test_no_change_day_emits_zero_signals PASSED      [ 14%]
tests/daily/test_daily_run.py::test_change_day_signal_is_counted PASSED          [ 28%]
tests/daily/test_daily_run.py::test_anti_kpi_guard_discriminates[False-0-False] PASSED [ 42%]
tests/daily/test_daily_run.py::test_anti_kpi_guard_discriminates[True-1-False]  PASSED [ 57%]
tests/daily/test_daily_run.py::test_anti_kpi_guard_discriminates[False-1-True]  PASSED [ 71%]
tests/daily/test_daily_run.py::test_anti_kpi_guard_discriminates[True-0-False]  PASSED [ 85%]
tests/daily/test_daily_run.py::test_no_signal_assertion_has_discrimination       PASSED [100%]
======================= 7 passed, 5 deselected in 5.70s ========================
EXIT=0
```

---

## ③ 结果

- **`tests/daily`：`43 passed`，退出码 `0`**（基线 37 → 新增 6 条：1 条 (b) + 4 条参数化守卫 + 1 条判别力反证）。
- **修复达成审计要求**：反 KPI 用例由"空真源恒真"变为**有判别力的两向守卫** —— (a) 零信号 + 真产出、
  (b) 信号正常计数、守卫四组合判定、故意注入必红。
- **无扩展设计**（`R-04`）：未新增 JSONL、未改 schema/rules/设计区、未触碰共享编排层。
- **真仓库真源零污染**：收工复核 `claims=5 / dependency_edges=3 / companies=2 / tasks=3 / baselines=1 / recommendations=1 / prices=0`，行数不变。
- **提交哈希**：`__COMMIT__`（提交后由主理人核对）。

---

## ④ 诚实登记的残留 / 不确定项

### 4.1 缺口 `G-RC-04`（真仓库反 KPI 已破）—— **本层不修，但本层能发现**

真仓库 `facts/tasks.jsonl` 现有 `check_record = {changed: false, …, signals_emitted: 1}`，
根因是 `pipeline` 的 step 6 处理器**恒回传 `judgment_change={}`**（`scripts/decision/step.py`，属**共享编排层**，本流写入域之外，归主理人）。
⇒ 任何"买/卖"日写出的记录都是 `changed=False + signals=1` —— 这正是 `no_signal_day` 在真仓库 FATAL 的原因。
**本文件不修该缺口**；但已用 `test_anti_kpi_guard_discriminates[False-1-True]` 与
`test_no_signal_assertion_has_discrimination` 钉住"该形态**能被发现**"。

### 4.2 本层**能**覆盖 / **无法**覆盖的违规类型（如实登记）

| 违规形态 | 本层能否发现 | 依据 |
|---|---|---|
| **无变化却产信号**（`G1-02①`，即真仓库形态） | ✅ **能** | 守卫参数化 `(False, 1) → 命中`；判别力反证注入即红 |
| **有变化却零信号**（"路径根本没走到"） | ✅ **能**（反向对照） | `test_change_day_signal_is_counted`：买日必须计数为 1，若为 0 即红 |
| **有变化却零信号**（`G1-02①` 语义之外） | ❌ **不能**，且**反 KPI 本不覆盖** | 铁律 `Ch1 §D.3` 是**单向**的：只禁"无变化产信号"，不禁"有变化零信号"；仓库无此判据。见参数化用例第 4 行 `(True, 0) → 不命中` |

★ **`judgment_change` 有真变化的"有变化日"无法经 `run_daily` 端到端构造**：
`pipeline.run_daily` 只聚合各步 `StepOutcome.judgment_change`，而 step 2–6 的处理器**全部不外传**
该字段（step 6 硬编码 `{}`）⇒ `result.changed` **恒为 `False`**。故 (b) 的"信号计数"用**交易决策日**
（R1 `buy`）构造；"`judgment_change` 有真变化"这一分支**只能在守卫层**用合成 `check_record`
（`(True, 1)`）覆盖。此非本层可实现，**与 4.1 同源**。

### 4.3 其它残留 / 不确定项

- **(a) 的"无变化"是"无新交易信号"，不是"`judgment_change` 全 False"**：受 4.2 约束，
  端到端只能构造前者。故 (a) 如实命名为"无交易信号的运行日"，断言的是 `signals_emitted == 0`
  与非真空（真产出 `pending` 建议），**不**声称 `judgment_change` 已回传真值。
- **未做反向对照覆盖"守卫自身误报"之外的门禁联动**：本层只验 `check_no_signal_day` / `no_signal_day.check`
  的判定力，未验它是否被接入阶段④门禁（审计 `G2` 指出阶段④ 4 条判据均不发现反 KPI —— 属主理人接线范围，本流不动）。
- **`tests/daily` 批超时**：批次超时 60s vs 实测 ~44s（≈1.4×，违 `V-02` 的 8–30×）—— 属 `verify.py`（主理人范围），
  本流**未改**，仅在报告中登记（审计 `G8` 同项）。
- **未跑全量**：遵 `V-08`（宿主删除配额），**只跑 `tests/daily`**；其余批次是否受影响**未验**（`UNKNOWN`）。
- **未做 `pre-commit` 之外的整树复核**：以 `run_all_gates` 为准，见提交时门禁输出。
