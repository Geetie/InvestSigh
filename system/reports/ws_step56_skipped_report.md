# `ws/step56-skipped` 交付报告 —— 收 `G-44`（step 5/6 幂等重跑如实上报 `skipped`）

- **分支**：`ws/step56-skipped`（基 `main` = `2a8ca32`）
- **工作树**：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-step56-skipped`
- **commit**：`5d0557c`（生产代码 + 测试）、`84f20f0`（本报告）
- **门禁**：`pre-commit` 11 道**全绿**（在 `git commit` 钩子内自动跑）；`run_all_gates.py --timeout 30` → `exit=1`，
  唯一红灯是 `traceback.py`（**既存**，见 §4.1，已用"修复前后逐字节对照"证明与本次改动无关）

---

## 0. 一句话

`step 5` / `step 6` 此前**从不填** `StepOutcome.skipped`，而适配器
`chain_steps._declare_incomplete_when_empty` **恰好只包装这两步** ⇒ 幂等重跑时
`produced=[] skipped=[]` ⇒ 被补 `incomplete_reason` ⇒ `STATUS_GAP` ⇒ **整轮 blocked**。
本次把"考察过、已存在故未写入"的对象引用**从下层唯一写入口带出**并填进 `skipped`。

★ 关键认知（决定了本次的观测量）：**幂等在写路径上本来就是好的** ——
两轮 `derived/derived_values.jsonl` 与 `facts/recommendations.jsonl` 行数**都没变**。
坏的只是**上报**：把"已完成、无新增"说成了"没做完"。

---

## 1. 改了什么

### 1.1 生产代码（6 个文件，全部在派单划定的落点内）

| 文件 | 改动 |
|---|---|
| `scripts/compute/store.py` | 新增 `AppendOutcome(written, skipped)`（`__post_init__` 自断言两者**互斥**）；新增 `append_derived_value_ids_detailed(...) -> AppendOutcome` 作为**唯一**幂等判定实现；既有 `append_derived_value_ids(...) -> list[str]` **降为其只取写入侧的视图**（对外契约逐字不变） |
| `scripts/compute/driver.py` | `DriverReport` 新增 `skipped_derived_ids`（并在 docstring 里把 `derived_ids` / `written_derived_ids` / `skipped_derived_ids` **三个不同集合**列成表）；`run_derived` 的 `persist` 分支改调 `_detailed`，把 `written` / `skipped` 分别落到两个字段；`as_dict()` 同步新增该键 |
| `scripts/compute/step.py` | `make_derived_handler` 的 `StepOutcome(...)` 新增 `skipped=list(report.skipped_derived_ids)`；docstring 写明**为何必须有它**（`G-44` 的机理）与**为何不在此重算幂等**（`G-06`） |
| `scripts/decision/rules.py` | 新增 `PersistOutcome(written_ids, skipped_ids)`（同样自断言互斥）；新增 `persist_recommendation_detailed(...) -> PersistOutcome` 作为唯一幂等判定实现；既有 `persist_recommendation(...) -> int` 降为计数视图 |
| `scripts/decision/run_decide.py` | `RunReport` 新增 `skipped_recommendation_ids`；`_run_core` 的落库分支改调 `_detailed`，幂等命中时把 `recommendation_id` 放进该字段（`recommendation_ids` 仍为空）；另**新增一条**"键此前不存在却一行未写入"的显式降级分支（`not_persisted`），不把它混成"幂等命中"；CLI summary 增加 `skipped_recommendation_ids` |
| `scripts/decision/step.py` | `make_decision_handler` 的 `StepOutcome(...)` 新增 `skipped=list(report.skipped_recommendation_ids)`；docstring 同上 |

**契约遵守**：

- `produced` = 本轮**真正新写入**（**未放宽**：`tests/compute/test_step_wiring.py:48` 的
  `assert second.produced == []` 照旧通过）；
- `skipped` = 本轮**考察过、已存在故未写入**；
- 两者**互斥** —— 由两处 `__post_init__` **自断言**（与主理人 `G-42` 在 `pipeline.py` 加的
  互斥校验同源、独立一层）；
- ★ **"哪些算已存在"只有一处判定**（`G-06`）：计算层 = `store.append_derived_value_ids_detailed`，
  决策层 = `rules.persist_recommendation_detailed`。`step.py` **零重算**，只转述；
- ★ **未改** `scripts/orchestrate/pipeline.py` 与 `scripts/orchestrate/chain_steps.py`（共享文件）。

**一处需要说明的设计取舍**：`AppendOutcome` 与 `PersistOutcome` 是**两个**类型而非共用一个。
理由写在 `PersistOutcome` 的 docstring 里：它们属不同层、承载不同对象
（`DerivedValue` vs `Recommendation`）的落库结果，各自随本人的幂等键演进；
合并只会造出一条**假的**跨层耦合。"模式相同"是**同构**（照 `scripts/evidence/independence.py`
的 `written_claim_ids` / `written_propagation_ids` 的做法），不是第二套实现。

### 1.2 测试（4 个文件，1 新增 + 3 扩充）

| 文件 | 新增/扩充内容 |
|---|---|
| `tests/injection/test_step56_skipped_wiring.py`（**新增**） | `G-44` 的**端到端机器绑定**：(a) 副本上连跑两次 `run_daily` 的判别式；(b) 清空 `facts/prices.jsonl` 的**反向对照**；(c) 夹具机制断言（防夹具漂移使用例空转）。同时**打印**每轮的 `status/produced/skipped/行数` 与 `blocked` 的**逐条成因** |
| `tests/compute/test_store.py`（+5 用例） | `AppendOutcome`：双跑判别式 / 互斥 / 无候选（`values=[]` → 两集合皆空）/ `skip_existing=False` / 自相矛盾被拒 |
| `tests/compute/test_step_wiring.py`（+1 用例，扩充 2 条） | 重跑 `skipped == 首轮 produced` 且互斥；空输入 `skipped` **必须也为空**；**新增**反向对照：经 `_declare_incomplete_when_empty` 后仍**必须**带 `incomplete_reason` |
| `tests/decision/test_persistence.py`（+4 用例） | `PersistOutcome`：双跑判别式 / 互斥 / 自相矛盾被拒 / `persist_recommendation` 与 `_detailed.written_ids` **同源**（计数视图不回归） |

---

## 2. 测了什么（真实输出 + 退出码）

### 2.1 `G-44` 主判据：双跑判别式（修复**前** vs **后**，同一夹具、同一命令）

夹具 = `system/` 的**副本**（复制规则与 `tests/conftest.py::code_root` 一致：**真源从空起步**），
再落两条**真实行情夹具**（`tests/compute/fixtures/agix_prices.jsonl` + `tests/decision/fixtures/demo_stock_prices.jsonl`）
与一条基准对象（**取 `rules/benchmark.yaml` 的原对象**、只补 `security_id`，不自造任何口径字段）。

**修复前**（生产文件临时回到 `2a8ca32`）：

```
[round1] blocked=True degraded=True gaps=9 signals=1
  step 5 status='ok' produced=3 skipped=0 gap=no
  step 6 status='ok' produced=1 skipped=0 gap=no
  derived_values.jsonl lines=3 recommendations.jsonl lines=1
[round2] blocked=True degraded=True gaps=13 signals=0          ← ★ 每次重跑 +4 条 gap
  step 5 status='gap' produced=0 skipped=0 gap=YES             ← ★ 被误判
  step 6 status='gap' produced=0 skipped=0 gap=YES             ← ★ 被误判
  derived_values.jsonl lines=3 recommendations.jsonl lines=1
BEFORE_POS_EXIT=0
```

（`+4` 的构成：2 条适配器补的 `step N (...)…` + 2 条 `assert_steps_complete` 对该两步发射的
`G1-05 第 N 步（…）未产出：status=gap`。）

**修复后**（同一命令）：

```
[round1] blocked=True degraded=True gaps=9 signals=1
  step 5 status='ok' produced=3 skipped=0 gap=no
  step 6 status='ok' produced=1 skipped=0 gap=no
  derived_values.jsonl lines=3 recommendations.jsonl lines=1
  blocked 成因（blocking 步且未 ok）=['step 2（blocking=True）status=gap', 'step 3（blocking=True）status=gap', 'step 4（blocking=True）status=gap', 'step 7（blocking=True）status=gap', 'step 8（blocking=True）status=gap']
[round2] blocked=True degraded=True gaps=9 signals=0           ← ★ 与首轮**持平**，不再增长
  step 5 status='ok' produced=0 skipped=3 gap=no               ← ★ ok + 命中如实上报
      skipped=['dv-benchmark_return-p01-compute-v1', 'dv-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1', 'dv-total_return-usDEMO-2026-04-01..2026-09-15-compute-v1']
  step 6 status='ok' produced=0 skipped=1 gap=no
      skipped=['rec-usDEMO-2026-04-01']
  derived_values.jsonl lines=3 recommendations.jsonl lines=1   ← ★ 行数不增
  blocked 成因（blocking 步且未 ok）=['step 2…gap', 'step 3…gap', 'step 4…gap', 'step 7…gap', 'step 8…gap']  ← 不含 step 5/6
AFTER_POS_EXIT=0
```

**逐条对照派单的期望**：

| 期望 | 实测 | 结论 |
|---|---|---|
| 首轮 `produced` 非空 | step5 `3`、step6 `1` | ✅ |
| 首轮 `skipped` 空 | 两步皆 `0` | ✅ |
| 重跑 step 5/6 `status == "ok"` | 两步皆 `ok` | ✅ |
| 重跑 `produced == []` | 两步皆 `0` | ✅ |
| 重跑 `skipped` 非空 | step5 `3`、step6 `1`，且**集合 == 首轮 `produced`** | ✅ |
| `derived_values.jsonl` 行数不增 | `3 → 3`（`recommendations.jsonl` 亦 `1 → 1`） | ✅ |
| **重跑 `result.blocked is False`** | ❌ **`True`（但首轮也是 `True`）** | **未做到 — 见下** |

★ **`blocked is False` 这一条我没有做到，且我认为在本批次里做不到** ——
`blocked` 由 step 2/3/4（模型侧未交付）与 step 7/8（未实现 hook）决定，它们
`blocking: true` 且**结构上恒为 gap**；修复前后**都是** `True`。
故我把成因**拆到步**打印（上面两行 `blocked 成因`）：修复后成因里**没有** step 5/6，
而修复前 round2 有。**若这条期望的本意是"整轮全绿"，它需要的是别的批次的交付内容，
不是本单**；若是"step 5/6 不再被误判"，则已达成。请主理人裁定（`R-04`：我不自裁）。

### 2.2 反向对照（派单证据 2 —— 整单的关键）

把副本 `facts/prices.jsonl` 清空 ⇒ 本步真的一件都没得做：

```
[round1] blocked=True degraded=True gaps=13 signals=0
  step 5 status='gap' produced=0 skipped=0 gap=YES
  step 6 status='gap' produced=0 skipped=0 gap=YES
  derived_values.jsonl lines=0 recommendations.jsonl lines=0
[round2] blocked=True degraded=True gaps=13 signals=0
  step 5 status='gap' produced=0 skipped=0 gap=YES
  step 6 status='gap' produced=0 skipped=0 gap=YES
AFTER_EMPTY_EXIT=0
```

- **修复后**：`produced=[]` **且** `skipped=[]` ⇒ **仍然**判 `gap`（两轮皆然）→ 守卫**未被削弱**；
- **修复前**同一条路径的实测输出**逐字相同**（`BEFORE_EMPTY_EXIT=0`，`step 5/6 = gap/0/0`）
  ⇒ 对照成立：这一侧**前后行为一致**，改动没有打开新口子。

### 2.3 持久器械（已提交，可复跑）

```
$ python -m pytest system/tests/injection/test_step56_skipped_wiring.py -q -p no:cacheprovider -s
[G-44 round1] blocked=True step5=(ok,3,0) step6=(ok,1,0) derived=3
[G-44 round2] blocked=True step5=(ok,0,3) step6=(ok,0,1) derived=3
[G-44 blocked 成因 r1] ['step 2（blocking=True）status=gap', 'step 3（blocking=True）status=gap', 'step 4（blocking=True）status=gap', 'step 7（blocking=True）status=gap', 'step 8（blocking=True）status=gap']
[G-44 blocked 成因 r2] ['step 2（blocking=True）status=gap', 'step 3（blocking=True）status=gap', 'step 4（blocking=True）status=gap', 'step 7（blocking=True）status=gap', 'step 8（blocking=True）status=gap']
[G-44 step5/6 gap r1] []
[G-44 step5/6 gap r2] []
[G-44 反向 round1] step 6 status='gap' produced=0 skipped=0
[G-44 反向 round2] step 5 status='gap' produced=0 skipped=0
[G-44 反向 round2] step 6 status='gap' produced=0 skipped=0
3 passed in 16.82s
TEST_EXIT=0
```

### 2.4 "复原即红"（证明新用例**有判别力**，不是恒真断言）

把 6 个生产文件临时退回 `2a8ca32`（`git checkout HEAD~1 -- <6 文件>`，事前已备份 + md5 记录）：

```
$ python -m pytest system/tests/injection/test_step56_skipped_wiring.py -q -p no:cacheprovider
E  AssertionError: ★ step 5 幂等重跑被误判为 'gap'（gap=本步处理器已执行但**无产出**（step 5 update_financial_and_valuation_assumptions）：…）
E  assert 'gap' == 'ok'
FAILED …::test_rerun_does_not_falsely_declare_step5_and_step6_incomplete
FAILED …::test_reverse_control_is_exercised_by_the_fixture
2 failed, 1 passed in 18.12s
```

★ **注意那个 `1 passed`**：它是 §2.2 的**反向对照用例** —— 它在修复前**也绿**，
这正是它要证的事（"空执行仍判 gap"不是本次新造的、也未被本次改动破坏）。
一红一绿成对，说明两个用例各自钉的是不同的东西，没有互相顶替。

`tests/compute/test_store.py` 在 pre-fix 下同样全红
（`AttributeError: module 'scripts.compute.store' has no attribute 'append_derived_value_ids_detailed'`，5 条）。

恢复后 md5 **逐字节一致**（`diff /tmp/g44-backup/md5.after /tmp/g44-backup/md5.restored4` 无输出）。

### 2.5 测试目录（派单证据 3 —— 一次只跑一个目录）

```
$ python -m pytest system/tests/compute  -q -p no:cacheprovider
101 passed in 26.58s          EXIT=0

$ python -m pytest system/tests/decision -q -p no:cacheprovider
97 passed in 18.83s           EXIT=0
```

相关目录/文件的追加回归（同一 worktree 内**串行**执行，未并发）：

```
$ python -m pytest system/tests/injection/test_chain_steps_wiring.py      -q
13 passed in 47.27s           EXIT=0
$ python -m pytest system/tests/injection/test_idempotency_rows.py        -q
9 passed in 37.60s            EXIT=0
$ python -m pytest system/tests/injection/test_criterion_effectiveness.py -q
23 passed in 120.96s          EXIT=0
$ python -m pytest system/tests/evidence -q
48 passed in 84.62s           EXIT=0
$ python -m pytest system/tests/unit     -q
42 passed in 37.72s           EXIT=0
$ python -m pytest system/tests/daily    -q
42 passed, 1 error in 158.99s （该 error 为**宿主 safe-delete shim** 在夹具 teardown 抛的
                               `OSError … FSMoveObjectToTrashSync failed (status -5000)`，
                               两次整目录运行落在**不同**用例上；两个被点名用例**单独跑均通过**）
```

### 2.6 门禁

```
$ sh system/scripts/ops/pre-commit.sh
pre-commit ✓ 全部门禁放行        EXIT=0        （11 道：append_only / rules_lock / registry_schema /
                                                schema_sync / conflict_scan / no_placeholder / injection /
                                                verification_policy / shell_var / graph_integrity / criterion_effectiveness）
提交时钩子内再跑一次：同样全绿，随后 `[ws/step56-skipped 5d0557c] 10 files changed, 604 insertions(+), 33 deletions(-)`

$ python system/scripts/ops/run_all_gates.py --timeout 30
  … 22 项 exit=0；traceback.py exit=1
  非零计数  1
GATES_EXIT=1
```

### 2.7 真仓库零污染

```
$ git status --short
（本单全部改动与本报告均已提交后：无任何输出 —— 未新增/修改/删除 facts/、derived/、state.json）
$ git log --oneline -2
84f20f0 docs(ws/step56-skipped): `G-44` 交付报告（本文件）
5d0557c fix(compute/decision): step 5/6 幂等重跑如实上报 skipped —— 收 `G-44`
```

★ 探针是**临时器械**（`system/tests/.probe-step56/`），**已在提交前删除**；
等价的**持久**器械是 §2.3 那个已提交的测试文件，它打印**同一组**观测量。

---

## 3. 派单每条要求 → 证据对照

| # | 要求 | 证据位置 | 结论 |
|---|---|---|---|
| 1 | 双跑判别式（`blocked` / 两步 `status` / `produced` / `skipped` / `derived` 行数） | §2.1（前/后两版输出）、§2.3 | ✅ 除 `blocked is False` 一项（见 §2.1 末尾，已如实上报） |
| 2 | 反向对照：空上游 ⇒ 两集合皆空 ⇒ **必须仍判 gap** | §2.2（前/后逐字相同）、§2.4 的 `1 passed` | ✅ |
| 3 | `tests/compute`、`tests/decision` 全绿（一次一个目录） | §2.5 | ✅ `101 passed` / `97 passed`，均 `EXIT=0` |
| 4 | 报告 + 实际输出 + 退出码 + commit hash + `git status --short` | 本文件（§2 全节、§2.6、§2.7） | ✅ |
| 5 | `produced` 保持严格 | §2.1（重跑 `produced=0`）+ `tests/compute/test_step_wiring.py:48` 未改且通过 | ✅ |
| 6 | `produced` / `skipped` 互斥 | 两处 `__post_init__` 自断言 + `test_*_are_disjoint` + 端到端用例的 `set(...) & set(...) == set()` | ✅ |
| 7 | "哪些算已存在"只有一处判定（`G-06`） | §1.1 的两个 `_detailed` 函数；`step.py` 只 `list(report.*)` 转述 | ✅ |
| 8 | 不改 `pipeline.py` / `chain_steps.py` | `git diff --name-only 2a8ca32..5d0557c` 不含这两个文件 | ✅ |
| 9 | 不碰真仓库 `facts/`、`derived/`、`state.json` | §2.7 `git status --short` 为空 | ✅ |
| 10 | `pre-commit` 全绿、不用 `--no-verify` | §2.6（脚本内与钩子内各一次） | ✅ |
| 11 | 不许 `git add -A` | §1 的暂存为**逐文件显式列举**（10 个文件），`git status --short` 中 `?? system/tests/.probe-step56/` **始终未被暂存** | ✅ |

---

## 4. 剩余不确定性与缺口（**如实登记，未自裁**）

### 4.1 `run_all_gates.py` 的唯一红灯是**既存**的（非本次引入）

`traceback.py` 在 `facts/recommendations.jsonl` 上报 `G1-03`（`rec-nvda-001` 四要素缺
`assumptions` / `computation`，反查成功率 0.0000）→ `exit=1`。
这是 `T-10` 裁决已知的**真实数据违例**（`2a8ca32` 的提交说明里已登记
"真实数据一进真源 → traceback 如实变红"）。

**证据（逐字节对照）**：把 6 个生产文件退回 `2a8ca32` 后重跑同一命令，输出与退出码
**完全相同**（同样的 2 条 `[FATAL] G1-03`、`RESULT: FAIL（2 violations）`、`EXIT=1`）。
⇒ 与本次改动**无关**。

### 4.2 ★ `result.blocked` 仍为 `True`（派单期望未达成）

见 §2.1 末尾。`blocked` 由 step 2/3/4/7/8 结构性地决定（`blocking: true` 且恒 gap）。
我用"逐条列出 blocked 成因"把这一项**可判别化**，但**没有**让 `blocked` 变 `False`。
需要的动作（若需求方要的是"整轮全绿"）：交付 step 2 的交叉验证/采纳、step 3 的关系抽取、
step 4 的增长护城河判断、step 7/8 的 hook —— 均**不在本单范围**。

### 4.3 `degraded` 的口径**前后未变，但与 step 1 不一致**（登记，未改）

- step 5：`degraded=bool(report.gap_ids)` ⇒ 重跑时仍 `True`（缺口每次都会重算出来）；
- step 6：`degraded=bool(report.degraded) or not report.recommendation_ids` ⇒
  **幂等命中时也 `True`**（因为 `recommendation_ids` 为空）；
- 而 **step 1 明确相反**：`ingest_step.py` 的 docstring 逐字写"**幂等命中不是降级**"，
  命中时 `degraded=False`。

三者对"幂等命中算不算降级"给了**两个答案**。我**没有**动 `degraded`，因为：
① 本单的契约只写 `produced` / `skipped`；② `degraded` 会流进 `check_record.degraded`
进而影响阶段④"降级保留上次有效结果"判据 —— 那正是 **`G-43`** 的作业面
（已由另一张单负责，且 `G-43` 的根因恰是那条判据空转）。若我在此顺手动它，
会与那张单互相掩盖。**请主理人裁定**（`R-04`）。

### 4.4 `G-42` 的已知边界同样适用于本次新增的 `skipped`

`assert_steps_complete` 拿不到 `root`，**无法**用真源核对 `skipped` 里的 id 是否真实存在。
故本次新增的出口与既有 `skipped`（step 1 / step 2）具有**同一强度**：
能抓"忘记产出的意外"，**不能**抓"蓄意灌水的自报"。我加的互斥自断言（`__post_init__`）
只堵住"把 `produced` 原样抄进 `skipped`"这一种最偷懒的伪造。
真正的兜底仍是**换人审计 + 读代码**。

### 4.5 `tests/daily` 的间歇性 `error` 是宿主环境的

见 §2.5 末行。两次整目录运行分别落在 `test_change_day_signal_is_counted` 与
`test_param_ref_mismatch_is_loud` 上，均是**夹具 teardown** 期间由宿主
`safe-delete` shim 抛出的 `OSError`（`SAFE_DELETE_FAIL_CLOSED` / `FSMoveObjectToTrashSync failed (-5000)`），
两个用例**单独跑都通过**。与 `G-RC-10`（夹具非确定性）同族，**非本次引入**，我未处置。

### 4.6 我没有覆盖到的

- **`run_decide.py` CLI 的 `--no-persist` 路径**：该分支下 `skipped` 恒空（因为**根本没做**幂等判定），
  我保留了这个语义并在 docstring 里写明；但没有为它新增用例（既有
  `tests/decision/test_run_decide_cli.py` 的 `--no-persist` 用例未被破坏）。
- **并发写者窗口**：`persist_recommendation_detailed` 与
  `append_derived_value_ids_detailed` 仍是"先读全量判键、再追加"**两次**独立操作
  （文件锁只覆盖追加）。这是**既存**且已登记的残留（`R-04`），我没有改变它，也没有解掉它。
- **`resume()` 路径**：它与 `run_daily` 共用同一套 `StepOutcome` 语义，理论上同样受益，
  但我**没有**为 `resume` 补双跑用例（`tests/unit` / `tests/daily` 里的既有 `resume` 用例全绿）。

---

## 5. 复跑指引（审查者用）

```bash
cd /Users/gaza/Developer/InvestSigh/.worktrees/ws-step56-skipped

# G-44 的持久器械（正向 + 反向对照，打印每轮观测值）
python -m pytest system/tests/injection/test_step56_skipped_wiring.py -q -p no:cacheprovider -s

# 落点目录
python -m pytest system/tests/compute  -q -p no:cacheprovider
python -m pytest system/tests/decision -q -p no:cacheprovider

# 门禁（提交时钩子会自动跑 pre-commit）
python system/scripts/ops/run_all_gates.py --timeout 30
```

★ 一次只跑一件事：本工作树的夹具带**排他会话锁**（`[V-05]`），并发 pytest 会互相删夹具。
