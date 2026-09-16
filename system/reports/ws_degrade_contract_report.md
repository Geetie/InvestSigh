# `ws/degrade-contract` 交付报告 —— 修 `G-43`（高）/ `G-45`（中高）

> 一句话：阶段④ 声明的判据 `degrade_keeps_last_valid` 此前**在真数据上空转**（把**所有**失败行
> 都当"首日"豁免 ⇒ **从不报任何真违规**）。本单让它在**真实字段形状**上真的成立、真的会拦，
> 并把"上次有效结果"的判定**收敛到唯一一处**。

- **工作树**：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-degrade-contract`
- **分支**：`ws/degrade-contract`（基点 `d5a37f8`）
- **代码 commit（评审对象）**：`abbe7b3` = `abbe7b367034c7987acb3d1660d82ab9d10b6c8c`
  （`fix(degrade): 修 G-43/G-45 —— 让「降级保留上次有效结果」在真数据上真的会拦`）
  —— **本单的功能性代码改动全在这一个 commit 里**
- **本单在 `abbe7b3` 之后的提交** —— **按判据写，不按清单写**（清单每次提交都自我过期；本单已因此改过一次）：
  ★ **核验判据**：`git log --no-merges --format='%h %s' abbe7b3..HEAD -- system/reports/ws_degrade_contract_report.md`
  列出的**每一个** commit（只有本单会改这个文件），其 `git show <c> --stat` 的**文件集合** ⊆
  { 本报告 · `system/scripts/orchestrate/pipeline.py` · `system/scripts/daily/degrade.py` }。
  **实测**：其中 `docs(report)` 型的提交**每个只改 1 个文件（本报告）**（`d34e6e5` · `4f03d7d` ·
  `44dee2e` · `de9a442` · `665cdb9` · `576c390` · `e6cdb67` —— 以上清单**截至 `e6cdb67`**，其后新增的提交以判据为准）；
  `docs(comment)` 型的提交（`e4da5e4` 及之后）= 本报告 + `pipeline.py` / `degrade.py` **各一处 docstring** ——
  就地改正被 `abbe7b3` **自身推翻**的句子（"`output_refs=` 零个生产赋值点" / "③ 当前无生产写入点"），见 §④-7。
  **零语义 = 机器证明，不是自称**：去掉 docstring 后比 `ast.dump` 相同 + hunk 逐行落在 docstring 区间内
  （非 docstring 行 = 0）；两条判据**各带正向对照**证明仪器可红（§④-7 末）。
  ★ **不得用区间 diff 作为本判据**：`abbe7b3..HEAD` **不是"本单的提交范围"** —— 本分支已并入主干
  （`2f62f5d` / `612cafe` 等 merge），该区间会**把别人的提交一并算进来**。
  实例（实测）：`2a8ca32` 对 `pipeline.py` 的 numstat = **`24 0`**，落在 `assert_steps_complete`；
  于是"拿 `abbe7b3` 当基线"会把**别人的 24 行**读成本单的改动 —— 见 §④-7 的双基线读数。
  ⇒ 本报告此前那句"`git diff abbe7b3..HEAD --stat` 只会列出本报告"**是错的，已就地更正**；
  同一教训另有他流在 `690f36c` 记过（"判断本单改动须用 `git show <本单commit>`，不能用 `本单commit..HEAD`
  —— 会把合并进来的他人改动算进来"）—— **本单曾独立踩中同一个坑，此处如实登记**。
- **改前基线（对照用）**：`d5a37f8`
- **已合并**：team-lead 的 **`6ee7121`**（`merge ws/degrade-contract: G-43/G-45 …`，8 文件 970+/86-；
  比 `abbe7b3` **多一个本报告文件**，代码逐字相同）；合并后主理人在主干**实跑全部 24 项门禁**：
  **23 绿 + 1 已知红（`traceback.py` = 真实覆盖缺口 · design-red）· 非零计数 1**
- **本报告的后续裁定（`T-18` / `G-52`）**：登记在 **`b7103b6`**
  （`system/reports/phase1_gap_register.md` + `system/reports/phase1_open_tensions.md`）
- **`git status --short`**：**（空）** —— 工作树干净（本报告已入库，故不在未跟踪列表里）
- **`$PY`** = `/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`
- **纪律声明**：全程**未**触碰真仓库 `system/facts/`、`system/derived/`、`system/state.json`
  （`git status --short` 为空即证据）；`system/rules/**`（0444 设计真相源）**未改**；
  一切实验在**副本**（`/tmp/wsdc/**`）中进行；本单所有提交的 `pre-commit` **均未被跳过**。
- **跑法口径**：跑 pytest 请用 `sh system/scripts/ops/run_pytest.sh tests/...`
  （裸 `pytest` 在宿主 FS broker 下会被 SIGTERM，见 §2.6 的对照实验）

---

## ① 改了什么

### 1.1 缺陷的两半（先分开看，它们不是一件事）

| # | 缺陷 | 那一半的位置 | 本单怎么修的 |
|---|---|---|---|
| `G-43` | 〔**改前态**〕首日豁免的**内层谓词**在真数据上**恒 False** ⇒ 全员豁免 ⇒ 判据空转 | `scripts/delivery/stage_gate.py::_holds_valid_result()`（只认 `last_valid_result_ref` / `output_refs`）+ 写入方 `pipeline._write_check_record()` **两个字段都不填** | **写路径补齐** + **谓词换真源** |
| `G-45` | 〔**改前态**〕"上次有效结果"**两个模块口径相反**；`output_refs=` **零个生产赋值点** | `degrade.last_valid_result_ref()`（认"一次成功的运行"） vs `stage_gate._holds_valid_result()`（认两个从不被填的字段） | **收敛到唯一一处**（`scripts/daily/degrade.py`） |

★ **本表两行右列描述的都是 `abbe7b3`「之前」的实测态**（左上角 〔改前态〕 标记即此意）——
`abbe7b3` **之后** `pipeline.py:415 output_refs=produced if valid_run else []` **已是生产赋值点**
⇒ 表中 "`output_refs=` **零个生产赋值点**" 与 "谓词在真数据上**恒 False**" 两句**作为当前态均已失效**。
★ 这是一条**通用记号约定**的落地（本单自审后引入，理由见 §④-7）：**凡是"只在本单改前成立"的断言，
标记必须落在该断言行自身**——因为复核工具（`grep -n`）**按行取数，邻行的限定词不构成限定**。

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
  > ★ **「零命中」结论按 `CONVENTIONS.md::V-10 / V-11` 补足三项（2026-09-16 复验）**：
  > ① **引擎指纹**：裸 `grep` = **toybox 0.8.13**（自报 "is not GNU grep"）；`/usr/bin/grep` = **BSD grep, GNU compatible 2.6.0-FreeBSD**；
  > ② **`rc` 原文**：两引擎均 **`rc=0`** —— 是**正命中**，不是"零命中 + `rc=1` + 无诊断"那种假阴；
  > ③ **地板真值**：Python `re` 独立扫全仓 `*.py` → **3 命中**，与两引擎**逐条一致**
  > （`daily/degrade.py:95`、`delivery/stage_gate.py:539`、`orchestrate/pipeline.py:364`），三条**全在注释/说明正文**里
  > （无 `def`、无调用形态）⇒ 「执行体零命中」**成立**。
  > 本条是本报告**唯一**一处零命中结论，已按新口径复验通过；模式为**纯字面**、未使用任何 GNU 扩展运算符。

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
因为**夹具**里的成功行 `status=done` + `output_refs` 非空，**它自己就落进了旧谓词的载体③**（`G-43`）。
**这不是"改前也守得住"**：这一例**不具判别力**（改前改后同红），但**理由不是**"载体③在生产数据上从不成立"
—— 那句是**本单改前的读数，现已失效**，就地更正于下。
★ **〔现态更正〕**原文"载体③在生产数据上**从不成立**（`output_refs=` 零个生产赋值点，`G-45`）"
**作为当前态已不成立**（对象 `main@2f62f5d`；`auditor-batch11` 先报，本单复核）：
`pipeline.py:415 output_refs=produced if valid_run else []` **就是一个生产赋值点**
（`/usr/bin/grep -rn 'output_refs=' system/scripts/` → 5 处 = 4 处注释/文档 + **1 处真赋值**，`rc=0`）。
★ **同一族的更细一步（本单追加）**：字段**有了**生产写入路径，但"载体③在**当前**生产数据上仍不成立"
—— 那个"仍不成立"现在的理由是 `T-18`（step 7/8 永不注册 ⇒ `blocked` 恒真 ⇒ **真仓库里没有一行
`status=done`**，见 §④-1），**不是**"字段没人写"。⇒ **结论侥幸仍对，理由已经换掉**。
这正是 `G-50`（"改了一半"）的形态：`T-18` 一旦裁定、`done` 行一出现，载体③**立刻变成活的**，
而那句旧理由**不会自己更新** —— 故此处按"理由"改，不止按"结论"改。
**承载 `G-43` 结论的是 §2.2 的 `audit_c1`（`output_refs=[]`）**——那一例改前 `exit=0`、改后 `exit=1`，
是本单**唯一**带反向对照的例子。

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

**定稿复核（报告最后提交后，在同一代码 commit `abbe7b3` 上逐条重跑，结果逐条一致）**：

| 命令 | 首次记录 | 定稿复核 |
|---|---|---|
| `tests/daily/test_daily_run.py` | 13 passed / 42.70s | **13 passed** in 48.84s |
| `tests/daily`（整目录） | 44 passed / 160.40s | **44 passed** in 152.71s |
| `tests/injection/test_wiring_guards.py` | 17 passed / 69.95s | **17 passed** in 55.85s |
| `tests/injection/test_criterion_effectiveness.py` | 23 passed / 98.99s | **23 passed** in 83.66s |
| `tests/injection/test_stage_gate.py tests/injection/test_audit_regressions.py` | 24 passed / 121.74s | **24 passed** in 124.56s |
| `tests/injection/test_idempotency_rows.py tests/injection/test_chain_steps_wiring.py tests/injection/test_append_only.py` | 28 passed / 81.30s | **28 passed** in 95.34s |
| `tests/injection/test_guards_reject.py tests/injection/test_guards_defensive.py` | 46 passed / 222.16s | **46 passed** in 223.81s |
| `tests/injection/test_prompt_injection.py tests/injection/test_rules_lock.py tests/injection/test_time_contract.py` | 32 passed / 137.21s | **32 passed** in 179.40s |

（用例数逐条不变，只有耗时随宿主负载波动。）

★ **跑法纠错（如实登记）**：定稿复核时，最后一组用 `$PY -m pytest <3 个文件>` 直接跑**被 SIGTERM（exit=137）掐死**，
输出只剩 conftest 的警告横幅：宿主 `sitecustomize.py` 的 **Bash 沙箱开关关不掉**（在解释器层）⇒
每个用例数百次 broker IPC ⇒ 在用例之间卡死且卡点漂移。**改用仓库自带脚本**：

```
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_prompt_injection.py \
    tests/injection/test_rules_lock.py tests/injection/test_time_contract.py -q
32 passed in 179.40s (0:02:59)      exit=0
```

该脚本导出的 `CODEBUDDY_SAFE_DELETE_SANDBOX=0` / `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0` 是**跑 pytest 的正确入口**；
前面几条用裸 `$PY -m pytest` 侥幸跑通，不代表那是最佳跑法。

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

**定稿复核（在同一代码 commit `abbe7b3` 上重跑，`gate exit=1`，逐条一致）**：

```
$ $PY system/scripts/ops/run_all_gates.py --timeout 30
  assert_gate_input.py               exit=0        0.39s
  freeze_guard.py                    exit=0        0.72s
  launch_guard.py                    exit=0        0.22s
  module_denylist.py                 exit=0        1.90s
  no_signal_day.py                   exit=0        0.19s
  no_placeholder_guard.py            exit=0        3.32s
  neutrality_check.py                exit=0        0.17s
  return_guard.py                    exit=0        0.21s
  anti_padding.py                    exit=0        0.75s
  gap_to_task.py                     exit=0        0.31s
  traceback.py                       exit=1        0.24s      ← 唯一非零
  pipeline.py                        exit=0        0.25s
  stage_gate.py --stage prep         exit=0        0.79s
  injection_guard.py                 exit=0        0.97s
  verification_policy_guard.py       exit=0        0.25s
  shell_var_guard.py                 exit=0        0.28s
  graph_integrity_guard.py           exit=0        1.15s
  locator_check.py                   exit=0        1.28s
  criterion_effectiveness_guard.py   exit=0        1.76s
  非零计数                               1
gate exit=1
```

★ 注意 `pipeline.py` 门禁本身 `exit=0`、`criterion_effectiveness_guard.py` `exit=0` —— 即
**本单唯一改动的共享文件与判据有效性门禁都是绿的**。

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

### ④-1 ★ 设计层自相矛盾（已登记 `T-18`）：step 7/8「既 `blocking` 又非首版实现」⇒ 首版**结构上不可能**不 `blocked`

> **本条不是「我的实现受限」，而是设计声明与现实自相矛盾。**我这里的实测只是把矛盾**钉成机器证据**。

**（a）设计真相源原文逐条**（`system/rules/pipeline.yaml`，由 `yaml.safe_load` 读出，非人工转录）：

| step | name | `blocking` | `implemented_in_first_version` |
|---|---|---|---|
| 1–6 | `ingest_public_information` / `trace_dedup_verify` / `update_company_and_industry_relations` / `revise_growth_and_moat_judgment` / `update_financial_and_valuation_assumptions` / `compare_company_vs_benchmark_expected_return` | **True** | **True** |
| **7** | `publish_recommendations` | **True** | **False** |
| **8** | `continuous_verification_and_history` | **True** | **False** |

**（b）矛盾在代码里的落点**（可复现）：

```
$ grep -rn "implemented_in_first_version" system/
system/scripts/orchestrate/ingest_step.py:4:      （注释）
system/scripts/orchestrate/pipeline.py:152:        （docstring）
system/scripts/orchestrate/chain_steps.py:6:       （docstring）
system/tests/injection/test_chain_steps_wiring.py:5:（docstring）
$ grep -rn 'cfg.get("blocking")' system/scripts/orchestrate/pipeline.py
215 / 225 / 249 / 302 / 324          ← blocking 被真读
```

★ **`implemented_in_first_version` 有零个「读该键的」代码**——措辞按 `auditor-batch11` 建议收窄
（原句"它只出现在注释与 docstring 里"**既偏窄又不准**：该键也出现在**真源本身**）。逐条清点（对象 `main@2f62f5d`）：
- `system/rules/pipeline.yaml` **8 处** = **声明本身**（真源数据，既非注释也非 docstring）；
- `.py` 里 **4 处** = `ingest_step.py:4`（注释）· `pipeline.py:152`（docstring）· `chain_steps.py:6`（docstring）
  · `test_chain_steps_wiring.py:5`（docstring）—— **全是注释/docstring**；
- 其余在 `reports/**` · `PROGRESS.md` · `skills/aichain-daily/SKILL.md`（文档）。
- **区分实验（按 `V-10` 三项）**：仪器 `grep (BSD grep, GNU compatible) 2.6.0-FreeBSD`；
  `/usr/bin/grep -rnE "[\"']implemented_in_first_version[\"']" --include='*.py' system/` → **零行 + `rc=1`**
  ＝该键**从未以字符串字面量出现**（＝无 `cfg[...]` / `cfg.get(...)` 这类读取形态）；
  地板真值：**同仪器、同范围**（`system/scripts/orchestrate/`）带引号标识符 **69 命中、`rc=0`**
  ⇒ 仪器在该范围**有产出**，故 `rc=1` **不是"仪器不响"**；交叉仪器 `-F` 纯字面（无扩展运算符）同结论。
**没有任何一行代码读它**。⇒ 这一列在首版**写 True 还是写 False，行为完全相同**（结论未受本次措辞更正影响）。
⇒ 与批次 13 的 `D1`（声明与现实矛盾）**同族**：声明了一条语义，实现里根本没有对应分支。

**（c）由此产生的必然链条**（本单实测）：

```
step 7/8 blocking=True 且无处理器
  ⇒ run_daily() 对未注册处理器的步记 gap
  ⇒ assert_steps_complete() 判「<name> 未注册且未显式记 gap（不得静默跳过）」（pipeline.py:496）
     —— 或按 blocking 置 blocked（pipeline.py:324）
  ⇒ result.blocked 恒为 True
  ⇒ _write_check_record 写出 status=TaskStatus.failed 恒成立
  ⇒ facts/tasks.jsonl 里**永远没有一行 status=done 的 check 行**
```

**（d）对本判据的后果**：真数据上 `last_valid_result_ref` 恒 `None`、`degrade_first_day_exempt=2` 是**正确的**
（确实没有可保留的旧结果），但这意味着**"有成功运行却丢引用 ⇒ FATAL"这一半在真仓库上无法自然发生**，
只能在受控输入上验证（§2.2 `audit_c1` exit 0→1 / §2.4 / §2.5 端到端）。
⇒ 判据两半的**判别力本身没有放松**（§2.2 与 §2.3 两向都证了），受限的是**真数据的可用形态**。

**（e）为啥这是设计层的事，不能在本单修**：

1. **铁律「卡死的信号 = 被关掉的信号」**：`blocked` 恒真 ⇒ `blocked` **失去判别力**
   —— 一个恒为真的信号等价于没有信号，与本单刚修的 `G-43`（判据恒空转）**是同一类病**。
2. `implemented_in_first_version` 零消费者 ⇒ 该列的**存在意义为零**，这是声明侧缺陷。
3. 但修它要动 `system/rules/pipeline.yaml`（设计真相源），**属需求方裁定，不属本卡**。

**（f）登记与建议**：已登记 **`T-18`**，交需求方裁定。
team-lead 的推荐（记录备查）：**首版不把 `implemented_in_first_version: False` 的步计入 `blocking` 判定，
但必须记 `gaps` 并显式标 `deferred_by_design`**——否则 `blocked` 恒真、判别力归零。

★ **本单只如实登记，不自行改 `rules/pipeline.yaml`（0444 只读 + 属设计裁定）。**
同理由：`chain_steps.py`（共享文件，不在本卡授权范围）本单**零改动**（§③-8 已证）。

### ④-2 ★ `G1-04`「终态 `done` ⇒ 必须有产出」与「无变化日」的语义冲突（**已单独立卡，本单不改**）

**（a）设计原文三条（逐字，冲突成立）**：

| 出处 | 原文 |
|---|---|
| `02_已确认的投资规则/01_需求拆解.md:149`（`C123-2`） | 「**更新 ≠ 信号**：每日维护（采集/核验/复查），仅变化时产信号，**无变化写 `check_record`**」 |
| `07_产业链传导与股票建议/01_需求拆解.md:51`（`N7.3-04`） | 「**无变化日不产生新信号，仅生成核查记录**」 |
| `08_产品入口与每日运行/02_实现方案.md:78` | 「每日运行**必写** `check_record`（**无论有无变化**）」 |

**（b）实现侧的冲突点**（`scripts/tasks/gap_to_task.py`）：

```
:43    TERMINAL_STATES = ("done",)          ← 只含 done，不含 failed
:190   if status in TERMINAL_STATES and not (row.get("output_refs") or []):
           → 判 G1-04「空执行」
```

★ 先排除一个**不存在**的假阳性：`TERMINAL_STATES` **只含 `done`**，**不含 `failed`**
⇒ **失败行不会被这条误判**，别把"失败行也被判空执行"当成问题（本单复核过）。
真正的问题是：**无变化日**（设计上**合法**）今天会长成 `done + output_refs=[]`
⇒ 被判 `G1-04` 空执行 ⇒ **FATAL**。本单补齐 `output_refs = 本轮真正新写入` 之后，
"成功运行但本次无新增产出"（幂等重跑日 / 无变化日）会**稳定**落进这个形状。
（本单之前 `done` 行恒 `output_refs=[]`，**更严重**——只是当时没有一行 `done`，见 §④-1。）

**（c）修法必须是"换成可判定的正向标记"，不是放松判据**（`R-06`）。
判决条件（team-lead 已批准此形态）：

> `done` 且 `output_refs` 为空 ⇒ **合法当且仅当** `check_record` **存在**
> 且 `check_record.changed is False`（无变化日）；否则仍按 `G1-04` 判空执行。

三条同时成立：① 每条 `done` 行**穷尽**落入"合法 / 违例"两态，无第三态、不靠任何名单（`R-06 ①`）；
② **判别力不放松**——"报了完成、既不产出、`changed` 也不是 False（或干脆没有 `check_record`）"照样红；
③ 字段全部**复用已有**（`check_record.changed` 由 `pipeline._write_check_record` 真实写出），**不新增真源**（`G-06`）。

**（d）本单状态**：**不改**。已单独立卡 `T-19`，工作树 `ws-daily-nochange` / 分支 `ws/daily-nochange-exit`，
交付正例（无变化日 ⇒ exit 0）+ 反例 A（`changed=True` ⇒ exit 1）+ 反例 B（缺 `check_record` ⇒ exit 1）。

### ④-3 `output_refs` 在"失败运行"上的语义是**本单的取舍**（非设计逐字规定）

设计区只逐字规定"失败 → **保留上次有效结果**"（`§E.1`）与"不得覆盖为无意义空值"（`§E.4`），
**未逐字规定**"失败轮的部分写入是否进 `output_refs`"。本单取"**失败 ⇒ 空**"，理由：
把本次的部分写入列进 `output_refs`，会让"本轮有没有有效产出"在**单看该字段**时不可区分
（`§E.1`：失败轮的有效结果 = `last_valid_result_ref` 指向的旧结果）。
**如需求方要"失败轮也如实列出部分写入"**，改动点只有一处（`pipeline.py` 的
`output_refs=produced if valid_run else []`），且**不会**影响本判据（失败行不满足载体③的 `done` 前提）。

### ④-4 载体①的语义边界（保留但已知其"弱"）

载体①（`last_valid_result_ref` 非空 ⇒ 持有有效结果）是 `stage_gate` 的旧口径，本单**保留不删**
（删即放松）。它的"弱"处：一条失败行**自带一个指针**并不等于它自己产出了结果。
本单的处理是**把它限制在豁免判定里**（`holds_valid_result`），而**定位引用**（`last_valid_result_ref()`）
**不用它**——只用 `is_valid_run_record()`，避免"指向一条失败运行的 `check_id`"。
⇒ 两处职责分工已写进 docstring；**未发现它导致任何误判**（§2.6 全绿，§2.2/2.3 两向对照成立）。

### ④-5 并发非原子（**已登记 `G-52`（低 · `OPEN`）· 记下不改**）

`_write_check_record` 的"读上一次成功运行 → 写本行"不是原子的。同一 `code_root` 上**并发**跑两次
`run_daily` 时，两行可能都指向同一个旧 `check_id`（**不会**产生悬空引用，但第二个失败行的
"上一次"可能不是紧邻的那次成功）。本项目当前是**单写者 + 会话锁**（`V-05`）语义，
**无并发写入点**；且 `pid + 存活` 守卫已能**响亮失败**（而不是静默错），在当前单机串行使用下够用。
⇒ 登记 **`G-52`（低 / `OPEN`）**，**超出本卡授权，明确不改**
——顺手改共享的会话锁 = 引入本单刚发现的**那类静默风险**（正是 `G-43` 的同族病）。

### ④-6 未做的（明确不在本单范围）

- 未改 `chain_steps.py` / `rules/pipeline.yaml`（见 ④-1 —— 0444 只读 + 属设计裁定）；
- 未改 `gap_to_task.py`（见 ④-2 —— 已单独立卡 `ws-daily-nochange-exit`）；
- 未与会话锁/并发相关的任何改动（见 ④-5 —— `G-52` 记下不改）；
- 未改 `registry/criterion_counterexamples.yaml`（该条目的 `blocked_hint`
  `"失败但未保留 last_valid_result_ref"` 逐字未变，登记**仍有效**且**现在才是真的**——
  `criterion_effectiveness_guard` 实测 `RESULT: PASS（0 violations）`）；
- 未更新 `reports/phase1_gap_register.md`（共享台账，留给主理人登记 `G-43`/`G-45` 的关闭）。

### ④-7 ★ 时效自审：本单自己写下的"当前态"断言，逐条复核（**触发者：`auditor-batch11`**）

**为什么做**：`auditor-batch11` 报出本报告有一处**已过期的无条件当前态断言**。既然本单交付的正是
`abbe7b3`，**最可能被它自己推翻的断言就是我自己写的那些** ⇒ 用机器把全报告扫一遍，而不是只改被点的那一行。

**仪器（`V-10` 三项齐备）**：`python 3.13.12` 的 `re`（**不经 grep 方言层**，见 `V-10` 规矩 6）；
对象 `system/reports/ws_degrade_contract_report.md`，**630 行 → 命中 28 行**（真值 = 命中行数本身，无抽样）；
模式（可复跑，逐行 `re.search`，纯字面 + 一个负向断言，**无 GNU 扩展运算符**）：
`零个|零命中|从不|恒(?!定)|永远|没有任何一行|没有.{0,6}读它`；
**地板真值**：同仪器、同对象、另取纯字面模式（`the`）→ **有命中** ⇒ 读数非空、仪器非死。

★ **行号口径（`V-11` 时间轴）**：下表行号一律是**自审当时 = 本提交改动前**的行号。本提交改写了 ①类那几行，
**改后行号已漂移**：重跑同一仪器得 **705 行 → 命中 40 行**。⇒ **同一仪器对同一对象，改前改后读数不可比**
（多出的 12 行是**改正文字本身**带了这些词）。**读数必须连着"对象版本"读**，否则会把自己的修订
误读成"断言变多了"。

**结论分四类**（不合并、不四舍五入）：

| 类 | 行（**改前**行号） | 处置 |
|---|---|---|
| **① 被 `abbe7b3` 自身推翻 → 本提交就地改正** | `L35` / `L36`（§1.1 表：`恒 False` / `零个生产赋值点`）、`L232`（§2.4） | 见上：表左上角 〔**改前态**〕 行内记号、§2.4 〔**现态更正**〕 |
| **② 自带历史限定词 → 判定历史态，不动** | `L4` · `L48` · `L72` · `L75` · `L113` · `L169` · `L172` · `L449` · `L560` | 逐行复核，确实带"改前 / 在本单之前 / 当时 / 此前"（`L4` 是**同行内**先叙旧后叙新，`L449` 是**引用的仪器输出原文**） |
| **③ ★ 本次未复核时效 → 不得读作"成立"** | `L513` / `L514` / `L515`（`result.blocked` 恒真 · `status` 恒 `failed` · **永远没有一行 `status=done`**）· `L518`（`last_valid_result_ref` 恒 `None`）· `L525` / `L526` / `L532` | **量不到 ≠ 不成立**（`V-11` 规矩 4 对本报告**自我适用**）：这些断言依赖 `T-18` 是否已被裁定落地，**本次未验** ⇒ 只报"未复核" |
| **④ 本次已复核、仍成立（与③分开列，避免一刀切）** | `L75` 一族（`_holds_valid_result` 执行体零命中 —— `V-10` 三项已在本报告内补足）· `L502` 一族（`implemented_in_first_version` **零个读该键的代码** —— 本节上方新增区分实验）· `L106` / `L107`（计数器 `rows_holding_valid_result` 的**设计理由**，属方法论陈述而非状态断言） | 保留，证据在原文与本节上方 |

**③ 里最该看的一条**：§④-1 的 `blocked` 恒真链条与 §2.4 是**同一根因果**——"真仓库没有一行 `status=done`"。
`T-18` 一旦裁定（主理人已给出推荐：`implemented_in_first_version: False` 的步不计入 `blocking`，
但必须记 `gaps` + 标 `deferred_by_design`），**这些"恒"字断言会成片失效**，且它们**不会自己更新**。
⇒ 建议把 §④-7 这张表并入 `T-18` 的**收口验收清单**（改一处、核一处）。

**★ 两条衍生发现（都属于"复核口径"本身，不只是内容）**：

1. **本报告在 §1.1 之前的写法证明：邻行的限定词不构成限定。** 我的第一版自动分类器按"命中行 ±4 行内
   是否有限定词"打标，它把 `:232` 判成了"历史态（有限定词）"——实际上那个 `改前` 出现在 `:230`，
   **限定的是另一条断言**（"这一例改前也会红"），与 `:232` 无关。**这是分类器的假阴性，我自曝**；
   它同时是一条通则：**复核工具按行取数（`grep -n` 的产出就是一行），故限定词必须在断言行自身。**
   ⇒ 已按此落地为本报告 §1.1 的 〔改前态〕 行内记号，并建议升格入 `CONVENTIONS.md`
   （与 `V-11`「举证半径 = 结论半径」同族：**限定词的半径 = 它所在的那一行**）。
2. **`auditor-batch11` 的引证里有一处同类偏差（同族，互相提醒）**：他们写"`:36` / `:48` 有『在本单之前』
   限定 ⇒ 属历史态，可保留"。**实测**：`:48` **有**（"`output_refs` 在本单之前**全仓库零个生产赋值点**"），
   `:36` **没有**（原句是"；`output_refs=` **零个生产赋值点** |"，同行的限定词为零）⇒ `:36` 属**① 类**
   而非 ② 类，本提交已一并加记号。**他们是对的结论（`:232` 要改）不受影响**；偏差只在"哪些行已被限定"
   这一项上，正是上一条通则的又一个实例。

**★ 本案的代码侧同族（本提交一并改，注释级、零语义）**：`abbe7b3` 同时在**两处 docstring 里**写下了
被它自己推翻的句子，二者都在我自己的交付面内：

| 位置 | 原句（改前态口吻，无标记） | 现改成 |
|---|---|---|
| `pipeline.py:365`（`_write_check_record` docstring 内，**距 `:415` 的真赋值仅 50 行**） | "且全仓库 `output_refs=` **零个生产赋值点**。" | 明写"当时全仓库无生产赋值点；**本方法下面 `output_refs=produced if valid_run else []` 就是补上的那一个**" |
| `degrade.py:127`（`holds_valid_result()` docstring 内，③ 的理由） | "**它当前无生产写入点**（`output_refs=` 在本单之前全仓库零个生产赋值点）" | 改为：③ 的**生效条件**依赖 `output_refs` **已被**写入（`pipeline.py:415`）⇒"将来有别的写入方"**已经发生**；但真仓库仍无 `done` 行（`T-18`）故 ③ 眼下仍不生效 —— **结论不变、理由已换** |

★ 承 §① 的 `pipeline.py` 授权边界（§1.3：**"diff 只在 `_write_check_record` 一个方法内"**）：
本表两处**都不扩大该边界**（`pipeline.py` 的改动仍在 `_write_check_record` 的 docstring 内；无任何语句被增删）。

**★「零语义改动」是机器证明的，不是自称的**（两条判据，各自带正向对照；口径：`python 3.13.12`）：

1. **AST 等价**：取 `HEAD` 版与工作树版，各自 `ast.parse` 后**显式剥除 docstring 节点**
   （`ast.Module` / `FunctionDef` / `ClassDef` 的 `body[0] = Expr(Constant(str))`），再比对完整 `ast.dump`
   ⇒ **`pipeline.py` / `degrade.py` 两文件：语义相同**。
   **正向对照（`G-05`）**：同一仪器拿 `HEAD` 版 `pipeline.py` 与一段无关源码相比 ⇒ **不同** ⇒ 仪器**可红**。
2. **hunk 落在 docstring 内**（= 报告头部那条可重算判据）：用 `ast` 求出新旧两版 docstring 的**精确行区间**，
   再解析 `git diff -U0 HEAD -- <file>` 的每个 hunk 头，逐行判定归属
   ⇒ **两文件「hunk 内非 docstring 行」均为 0**；改动文件集合 = **恰好** 3 个（本报告 + 两脚本）⊆ 允许集。
   **正向对照**：拿 `pipeline.py` 的 docstring 行区间去套一段无关代码 ⇒ **检出越界** ⇒ 仪器可红。
⇒ 本提交对两个脚本的改动**只在 docstring 层**，行为不可能变；`pipeline.py` 的改动也**仍在 `_write_check_record` 内**。

★★ **双基线读数 —— 上面那条"基线必须是本提交的父"不是推理，是实测出来的**（`V-11` 仪器轴：
**基线属于仪器**，换基线 = 换仪器）：

| 基线 | `pipeline.py` | `degrade.py` | 读法 |
|---|---|---|---|
| **`HEAD^`**（= `e6cdb67`，本提交的父） | **语义相同** | **语义相同** | ★ **这才是"本提交零语义"的读数** |
| `abbe7b3`（= "代码 commit"） | **★ 语义不同** | 语义相同 | **差额不是我的**：区间内含 `2a8ca32`（numstat **`24 0`**，落在 `assert_steps_complete`） |

⇒ 同一个问题（"本提交是否零语义"）换基线就换答案，而**只有一个基线问的是正确的问题**。
这正是报告头部那条更正（"不得用区间 diff"）的**机器版证据**，也说明
**"基线"和"被测对象"一样必须写明**：只写"与 `abbe7b3` 对比"而不写"这是谁的改动"，就会把别人的 24 行算给自己。

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
