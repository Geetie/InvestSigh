# ws/evidence-fix · 证据层收口报告（`§5.2` 四段式）

> **工作树**：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-evidence-fix` ｜ **分支**：`ws/evidence-fix` ｜ **基点**：`main = 960634d`
> **DoD**：`system/reports/ws_evidence_fix_dod.md`（**先写**）
> **本报告为「范围内交付 + ③⑤ 按裁决移交」的收口报告**：①T-11 ②T-12 ④G5 ⑥已交付并验证；**③G3 / ⑤G6 的落点在 `scripts/daily/**`（范围外）→ 已开工即上报，主理人裁决「归属随模块走、移交 `ws/daily-fix`」，本流未动该域**（见 §④与文末附）。

---

## ① 做了什么

| # | 审计发现 | 处置 | 落点 |
|---|---|---|---|
| ① | `T-11` 人工去重覆盖无处承载（`Ch6 §C.3` vs `Ch9 §3.3.3` 18 JSONL） | **已授权契约变更**：`ClaimPropagation` 增 `kind`（`StrEnum`，默认 `restatement`）+ 新值 `manual_alias_override` + 载荷模型 `AliasOverride`（`is_independent/reason/operator/at`，逐字承载 §C.3）。**不新增第 19 个 JSONL**；**旧行取默认即合法**。 | `schema/models.py` + 生成物 |
| ② | `T-12` `independent_evidence_count` 落不进 `Claim` | **已授权契约变更**：`Claim` 增**可选**字段 `independent_evidence_count: int \| None = None`（默认 `None` = 未计算）；docstring 写清"基数非权重"口径与**不含**什么（转述/热度/自评分）。**真仓库 5 行旧 claim 仍合法**。 | `schema/models.py` + 生成物 |
| ④ | `G5` `max_model_calls: 0` 被静默当"无上限" | `evaluate_budget` 重写三分支：`None`=未设上限（不约束）／`<=0`=**上限为 0**（`used>=0` 即到限，**不静默**）／`>0` 原语义。**`None` 与 `0` 不再混同**。 | `scripts/evidence/budget_gate.py` |
| ⑥ | `origin_claim_id` 全仓无产出方（`T01` 系统层缺口） | 去重步骤新增**产出方**：`plan_origin_attribution`（纯函数，规划上游链）+ `record_claim_updates`（经唯一写入口追加新版本）+ `classify_and_record` 串起"产出→分类→落库"。根来源信号新增 `impact_capability.root_source_id` 载体（schema 合法）。**根来源主张不在场 ⇒ 不臆断**（`residual_groups` 如实登记）。 | `scripts/evidence/independence.py`、`__init__.py` |
| — | 三处已过期的旧说明 | 更新 `independence.py` 模块 docstring（原写"claim_alias 不做"）、`_propagation_row` 显式带 `kind`、`__init__.py` 导出新名字。 | 同上 |
| — | 测试 | 新增 `test_contract_changes.py`、`test_origin_attribution.py`；扩 `test_budget_gate.py`（G5 正反）；修正 `test_independence_t01.py` 的"claims 只读"断言为**追加式**断言（T-12 后去重步骤合法写 claim）。 | `tests/evidence/**` |
| **⑦** | **`G-B10-07`** 主理人实测：接线后 `classify_and_record` 非幂等（claims 5→10→12） | **已修**：`record_claim_updates` 幂等基线由"最新版本行的值"改为"**该 `claim_id` 最近记录到的非空值**"（新增 `_last_recorded_values`）—— 上游内容不变地再追加一版且丢派生字段时**不再触发重写**。自证连跑两次：run#2 本模块增量 **0**；反向对照（全新主张）**必写**。**残留 +1 系 step 1 既有重复版（非本模块），由 `ws/idempotency` `aa8a3ee` 修**（见 §②-8）。 | `scripts/evidence/independence.py`、`tests/evidence/test_origin_attribution.py` |
| **⑧** | 为接 step 2：`StepOutcome.produced`（`4f95c3d`）需"**本轮真正新写入**"的**对象引用** | **纯增量**：`IndependenceSummary` 增 `written_claim_ids` / `written_propagation_ids`（默认空 tuple，向后兼容）；`record_claim_updates` / `record_propagation` **保留 int 返回**、经**可选出参**带出 id；`classify_and_record` 填回并返回。★ "某对象是否已存在/是否需写"的判定**只此一处**（`G-06`）：`chain_steps.py` **不得**重算。 | `scripts/evidence/independence.py`、`tests/evidence/test_origin_attribution.py` |

**文件清单**（`git status --short`）：
```
 M system/schema/jsonschema/facts.schema.json
 M system/schema/models.py
 M system/scripts/evidence/__init__.py
 M system/scripts/evidence/budget_gate.py
 M system/scripts/evidence/independence.py
 M system/tests/evidence/test_budget_gate.py
 M system/tests/evidence/test_independence_t01.py
?? system/reports/ws_evidence_fix_dod.md
?? system/tests/evidence/test_contract_changes.py
?? system/tests/evidence/test_origin_attribution.py
```
> ★ 上表为**首个交付提交 `66422a8`** 的文件清单。之后**两轮增量**（均只两文件）：
> `G-B10-07` 硬化（`9ba54a8`）与 ⑧ 落库返回值（`written_*_ids`）—— 均为
> ` M system/scripts/evidence/independence.py`、` M system/tests/evidence/test_origin_attribution.py`（+ 本报告 / DoD）。

---

## ② 怎么验证的（原样命令 + 原样输出 + 退出码）

### ②-1 契约变更 + 生成物一致（①②）

```
$ cd system && python -m schema.build_jsonschema && python scripts/checks/schema_sync_guard.py
```
```
/Users/gaza/Developer/InvestSigh/.worktrees/ws-evidence-fix/system/schema/jsonschema/facts.schema.json
== schema_sync_guard.py ==
  scanned committed_defs: 49
  scanned fresh_defs: 49
  scanned objects: 18
RESULT: PASS（0 violations）
GUARD_EXIT=0
```
（`schema_sync_guard` **绿**；`objects: 18` —— 未新增第 19 个 JSONL。）

### ②-2 旧行向后兼容（①②）——真仓库**真实数据** + 旧形状传播行（只读 demo，原样输出）

```
$ python /tmp/ws_evidence_fix_demo.py system   # 只读，无任何写入
DEMO_EXIT=0
```
```
== ①T-11 旧 claim_propagation 行（无 kind/alias_override）仍合法 ==
   old_row_validates = True  kind = restatement  alias_override = None
   JSONL_MODELS 数量 = 18 （assert ==18 已过）
== ①T-11 人工别名覆盖（kind=manual_alias_override）承载 Ch6 §C.3 四要素 ==
   {..., 'kind': 'manual_alias_override', 'alias_override': {'is_independent': True, 'reason': '人工确认同一事件', 'operator': 'ops-1', 'at': '2026-09-16T12:00:00Z'}}
== ②T-12 真仓库现有 claims（真实数据）逐行仍合法 + 字段默认 None ==
   真仓库 claims 行数 = 5
   row#1 claim-nvidia-newsroom-q4-fy2025-4d13454fd8 independent_evidence_count=None
   row#2 claim-nvidia-newsroom-q3-fy2025-30d8b9bb6b independent_evidence_count=None
   row#3 claim-inbox-2026-09-10-tsmc-aug2026-revenu independent_evidence_count=None
   row#4 claim-nvidia-newsroom-q4-fy2025-4d13454fd8 independent_evidence_count=None
   row#5 claim-inbox-2026-08-04-amd-q2-2026-results independent_evidence_count=None
```
★ **旧行向后兼容证据**：无 `kind`/`alias_override` 的传播行 `model_validate` 成功（取默认）；真仓库 **5 行 claims（真实数据）** 逐行 `Claim.model_validate` 成功且新字段 = `None`。`Ch9 §3.4.2` 追加式不可变未被破坏。

### ②-3 ④G5：`0` 不再静默（纯函数，无写入；原样输出）

```
== ④G5 max_model_calls=0 不再静默当无上限（纯函数，无写入）==
   limit=0 used=999 -> exhausted = True binding = ('compute',)
   limit=0 used=0   -> exhausted = True binding = ('compute',) ratio = 1.0
   limit=None used=999 -> exhausted = False （None=未设上限，≠0）
```
★ 修复前 `limit=0 && used=999` ⇒ `exhausted=False`（审计实测）；修复后 `True`，且 `None` 仍为"不约束"（**不欠报**）。

### ②-4 ⑥(a)(b)(c)（原样输出）

```
== ⑥(a) 10 篇同根转述（含 origin）⇒ 独立佐证 1 ==
   root_count = 1  independent_evidence_count[root] = 1  propagation = 10
== ⑥(b) 3 条真独立（根来源主张不在场）⇒ 3 ==
   plan.links = {}  residual_groups = 1  count = 3
== ⑥(c) 10 篇同指纹但无 origin（根来源主张不在场）⇒ 现状如实登记 ==
   plan.links = {}  residual_groups = 1  count = 10 （仍算 10 ⇒ 判定层产物，残余）
```
★ 系统层证据（`test_a_prime_*`，真落库）：根来源主张**在场** + 10 篇**未标** origin 的转述 → 产出方补链 → `independent_evidence_count[root] == 1`、传播 10、且**读回**最新版本 `origin_claim_id == "root"`。

### ②-5 测试子集（**只跑 `tests/evidence`**，`V-08`）

```
$ sh system/scripts/ops/run_pytest.sh tests/evidence -q
```
```
................................................                         [100%]
48 passed in 46.99s
```
**`tests/evidence`：48 passed，退出码 0**（`46.99s`，批超时 60s 内）。累计 **+4**：`test_reappend_dropping_derived_field_does_not_trigger_rewrite`、`test_new_claim_still_gets_count_reverse_control`（`G-B10-07` / `G-05`）、`test_written_ids_nonempty_first_round_and_empty_on_rerun`、`test_written_claim_ids_reverse_control_true_change_rewrites`（⑧ `written_*_ids` 的 `produced` 判别式）。

### ②-6 提交前门禁

```
$ sh system/scripts/ops/pre-commit.sh
...
pre-commit → schema_sync_guard … RESULT: PASS（0 violations）
pre-commit → conflict_scan(L1-L5) … RESULT: PASS（0 violations）
pre-commit → no_placeholder_guard … RESULT: PASS（0 violations）
pre-commit → injection_guard … RESULT: PASS（0 violations）
pre-commit → verification_policy_guard … RESULT: PASS（0 violations）
pre-commit → graph_integrity_guard … RESULT: PASS（0 violations）
pre-commit ✓ 全部门禁放行
PC_EXIT=0
```
**全部门禁放行**（无 `--no-verify` 需要）。

### ②-7 未污染真仓库真源

```
claims: 5   claim_propagation: 0   companies: 2   tasks: 3   baselines: 1   recommendations: 1   dependency_edges: 3
```
**行数不变**；写入型探测一律在 `code_root` 夹具副本上。

### ②-8 补充 · `G-B10-07` 幂等硬化：连跑两次的自证（**副本上**，未碰真仓库）

> 方法（与主理人同法）：把真 `system/`（**含真 `facts/` 与 `raw/inbox/`**）整体复制到 `/tmp` 副本，
> 跑 `Pipeline.run_daily` 两次，每次后调 `classify_and_record`（＝接线后的 step 2）。全程真仓库 `facts/` **零写入**。

**A. 只跑 `run_daily`（不接线）—— 隔离 step 1 的既有行为（零证据层代码参与）**
```
[start]   claims wc-l = 5   claim_propagation wc-l = 0
[daily#1] claims wc-l = 6   claim_propagation wc-l = 0   (+1)
[daily#2] claims wc-l = 7   claim_propagation wc-l = 0   (+1)
[daily#3] claims wc-l = 8   claim_propagation wc-l = 0   (+1)
```
新增行**恒为同一条**：`claim_id = claim-inbox-2026-08-04-amd-q2-2026-results.txt-44ea5ab4089d`、`version_kind = None`、`recorded_seq = 6/7/8`、`count = None`。
→ **step 1 每跑 +1 版重复 claim**（`raw/inbox/` 投递文件常驻 + `guard/executor` 追加不判重，`Ch9 §3.5` 阶段②行幂等键缺位）。**此增量为既有编排行为，与证据层无关**（此段无任何证据层代码参与）。

**B. 接线后（本模块 + `run_daily`）连跑两次**
```
[start]   claims wc-l = 5    claim_propagation wc-l = 0
[run#1]   claims wc-l = 10   claim_propagation wc-l = 0   (+5)
[run#2]   claims wc-l = 11   claim_propagation wc-l = 0   (+1)
```
`run#1` 新增 **5** 行逐行（`claim_id` / `version_kind` / `recorded_seq`）：

| 行 | `claim_id` | `version_kind` | `recorded_seq` | 新写 `count` | 归属 |
|---|---|---|---|---|---|
| 6 | `claim-inbox-2026-08-04-amd…-44ea5ab4089d` | `None` | 6 | `None` | **step 1 重复版**（既有） |
| 7 | `claim-inbox-2026-08-04-amd…-44ea5ab4089d` | `None` | 7 | `0` | **本模块**（该 claim 此前从未记 `count`） |
| 8 | `claim-inbox-2026-09-10-tsmc…-afebc81420c1` | `None` | 8 | `0` | **本模块** |
| 9 | `claim-nvidia-newsroom-q3-fy2025-30d8b9bb6b87` | `None` | 9 | `0` | **本模块** |
| 10 | `claim-nvidia-newsroom-q4-fy2025-4d13454fd859` | `financial_restatement` | 10 | `0` | **本模块** |

→ **`run#1 = +5 = 1（step 1 重复版）+ 4（本模块首次写入：真仓库 4 条 claim 的 `count` 此前从未记录）**。
多出来的那 **1** 行**不是"第 5 个根"**，而是 step 1 的重复版（`version_kind=None`、`count=None`、`recorded_seq=6`）——由 A 段独立证实。

`run#2` 新增 **1** 行逐行：

| 行 | `claim_id` | `version_kind` | `recorded_seq` | `count` | 归属 |
|---|---|---|---|---|---|
| 11 | `claim-inbox-2026-08-04-amd…-44ea5ab4089d` | `None` | 11 | `None` | **step 1 重复版**（既有） |

→ **`run#2` 本模块增量 = 0**；`claim_propagation` 亦 = **0**。**非幂等的部分只剩 step 1 那 1 行**（见 A）。

**C. 反向对照（`G-05` 成对）—— 证"不是一律不写"**
```
[run#1 (首次，应写入)]         claims wc-l = 10  (+5)
[A) 复跑（应 0 新增）]         claims wc-l = 10  (+0)   ← 幂等
[B) 追加全新主张后]            claims wc-l = 11  (+1，上游写入)
[B) classify 之后（必须新增）] claims wc-l = 12  (+1)   ← 本模块写入
   新增行: claim-reverse-control-1 | version_kind=None | recorded_seq=9001 | count=1
```
→ 一条**此前从未有 `count`** 的全新独立主张 → 本模块**必须**为其写入 `count=1`（证明"值变即写、非一律不写"）。

**D. 合上 step 1 修复（`ws/idempotency`，同一基点 `960634d` 上的 `aa8a3ee`）后连跑两次**
> 说明：`ws/idempotency`（#38 已完成、未并主线）正是给 `guard/executor` 补 `(source_id, quote_hash)` 行幂等键。把其 `guard/executor.py` + `orchestrate/ingest_step.py` **只读 `git show` 取内容**、叠加到副本（**未做任何分支操作**）：
```
[start]  claims wc-l = 5   claim_propagation wc-l = 0
[run#1]  claims wc-l = 9   claim_propagation wc-l = 0   (+4 = 纯本模块)
[run#2]  claims wc-l = 9   claim_propagation wc-l = 0   (+0)   ← 两文件皆 0
```
→ **本模块 + step 1 修复 ⇒ `run#2` 两文件皆 0**（完全满足验收口径）。

**E. 修复内容（本模块，`G-B10-07`）**
`record_claim_updates` 的幂等基线由"**最新版本行的值**"改为"**该 `claim_id` 最近记录到的非空值**"（新增 `_last_recorded_values`，按 `recorded_seq` 升序取各字段**最后一个非空值**）：上游**内容不变地再追加一版、且丢掉派生字段**（`count`/`origin` 回 `None`）时，**不再触发重写** ⇒ 幂等。
（根因即主理人实测的 `run#1 +5 / run#2 +2`：旧基线被 step 1 的重复版"抹掉"派生字段 ⇒ 每次重写；`run#2 +2 = 1（step 1）+ 1（本模块被抹后重写）`。硬化后 `run#2 = 1（step 1 唯一残留）+ 0（本模块）`。）

### ②-9 ⑧ 落库返回值：`written_*_ids`（供 `StepOutcome.produced`，契约 `4f95c3d`）

**改动**：`IndependenceSummary` 增 `written_claim_ids` / `written_propagation_ids`（默认 `()`）；`record_claim_updates` / `record_propagation` **保留 `-> int`**，经**可选出参** `written_ids: list[str] | None` 带出本轮**真正写入**的 id（升降序 = 升序）；`classify_and_record` 用 `dataclasses.replace` 填回并返回。**"是否已存在"的判定只在两个 record 函数内**（`G-06`），`chain_steps.py` 侧**零重算**。

**测试（`tests/evidence`，新增 2 条，`G-05` 成对）**：
```
$ sh system/scripts/ops/run_pytest.sh tests/evidence -q
................................................                         [100%]
48 passed in 46.99s
```
- 首轮：`written_claim_ids` 非空（4 条需打补丁的 claim：`re1..re3` + `root`，升序）、`written_propagation_ids == {"re1","re2","re3"}`（非空）；
- 重跑：**两者皆 `()`** —— `G-B10-07` 在"模块返回值"层面的判别式（与"文件行数不增"互补；否则 `produced` 会误报本轮有产出、`G1-05` 判据失真）；
- ★ 反向对照：把 `root` 的 `independent_evidence_count` 改成与再判定结果不一致（99 ≠ 1）后 → `written_claim_ids == ("root",)` —— **该写的时候必写**（否则"永远不写"也能骗过"重跑为空"）。

### ②-10 §④-8 实测：最新版本行派生字段是否非 None（有/无 #38 对照）

命令（副本；`run_daily` + `classify_and_record` **连跑两次**；按 `claim_id` 取 `recorded_seq` **最大**版本行）：
```
$ python /tmp/evi_idem/meas.py {real|synthetic} {without38|with38} <dst>/system
```
```
# real · without38            # real · with38
[after ×2] claims wc-l = 11   [after ×2] claims wc-l = 9
 seq=11 count=None  amd…       seq=6 count=0  amd…
 seq=8  count=0     tsmc…      seq=7 count=0  tsmc…
 seq=9  count=0     nvidia-q3  seq=8 count=0  nvidia-q3
 seq=10 count=0     nvidia-q4  seq=9 count=0  nvidia-q4
```
→ **无 #38**：唯一被 step 1 重复的 `amd…` 最新行 `count=None`（**洞真实、可复现**）。**有 #38**：4 条最新行 `count` **皆非 None** ⇒ **洞口已闭合（实测）**。

```
# synthetic · with38（syn-root + 3 转述，声明 root_source_id）
 seq=208 count=None  origin=syn-root   syn-re1
 seq=209 count=None  origin=syn-root   syn-re2
 seq=210 count=None  origin=syn-root   syn-re3
 seq=211 count=1     origin=None       syn-root
```
→ 转述主张的**应写字段**（`origin_claim_id`）最新行**非 None**；根主张的**应写字段**（`count`）最新行**非 None**。转述的 `count=None` 属**设计**（`Ch6 §C.2` 步骤⑤ 只记在根主张），非缺口。

---

## ③ 结果

- **①T-11**：契约变更完成（`kind` + `manual_alias_override` + `AliasOverride`），旧行向后兼容，**18 JSONL 未变**，`schema_sync_guard` 绿。
- **②T-12**：`Claim.independent_evidence_count` 落表（可选，默认 `None`），真仓库 5 行真实数据仍合法，生成物一致。
- **④G5**：`0` = 上限为 0（**不再静默**），`None` = 未设上限，二者不再混同；正反用例齐。
- **⑥**：`origin_claim_id` 产出方建成；`T01` 的**系统层**现实形态（根在场 + 未标 origin 的转述）→ 独立佐证 **1**；(b) 真独立 **3**；(c) 无解时**残留如实登记**。
- **测试**：`tests/evidence` **48 passed / exit 0**（累计 +4）；`pre-commit` **全绿**。
- **⑦`G-B10-07`**：`classify_and_record` **已幂等**（`run#2` 本模块增量 = 0；反向对照必写）；`run#1 = +5` 逐行解释清楚（1 行 step 1 重复版 + 4 行本模块首写）；**唯一残留 +1 系 step 1 既有重复版，由 `ws/idempotency` 修**（叠加后 `run#2` 两文件皆 0，见 §②-8）。
- **⑧落库返回值**：`written_claim_ids` / `written_propagation_ids` 就绪（首轮非空 / 重跑皆空 / 真实变更必写）；**`produced` 语义可直接取用，不需第二条实现路径**（`G-06`）。
- **§④-8 洞口**：**已闭合（实测）**，功劳属 `ws/idempotency`（`a29ec90`）。
- **③G3 / ⑤G6**：落点在 `scripts/daily/**`，**已按主理人裁决（2026-09-16「归属随模块走」）移交 `ws/daily-fix`，本流未动该域**（见 §④）。

**提交哈希**：首交付 `66422a88ac0b15ce9e19af6f09c2f66239214d42`（11 files, +1220/-21）；`G-B10-07` 硬化 = `9ba54a8`（4 files, +159/-9）。分支 `ws/evidence-fix`。

---

## ④ 诚实登记的残留 / 不确定项

1. **③G3、⑤G6 —— 已按主理人裁决（2026-09-16）移交 `ws/daily-fix`，本流未动该域**：二者落点分别是 `system/scripts/daily/coverage.py`（CV3 覆盖目标集）与 `system/scripts/daily/schedule.py`（YAML 时刻装载），均在任务书「**禁止改**」清单的 `scripts/daily/**` 内，且与 `ws/daily-fix` 并发 → 裁决「**归属随模块走**」。→ 本流**未动 `scripts/daily/**`**；文末补丁降级为**参考资料**（供 `ws/daily-fix` 取用）。
2. **⑥ 的 (c) 情形未闭合（如实登记，不美化）**：当"根来源主张**不在场**"时，"真独立"（b）与"未标链的转述"（c）在 claim 字段上**同构** ⇒ 产出方**不臆断**，记为 `residual_groups`，该组仍可能计为 N 份。**这是判定层产物，残余未闭合**。要真正闭合需在**采集/标注层**为转述写入根来源信号（`root_source_id` / `origin_claim_id`）—— 该层不在本单范围。
3. **⑥ 的真实链路接线（主理人职守，本流不碰 `scripts/orchestrate/**`）**：`classify_and_record` 现**未被** `scripts/daily/**` / `scripts/orchestrate/**` 调用（全仓调用点仅测试）。★ **两项前置条件均已满足**：① 本模块幂等已修实（§②-8）；② `ws/idempotency` 已并入 `main`（`a29ec90`），本模块合并于 `35758a7`。接线时 `StepOutcome.produced` 直接取 `summary.written_claim_ids` / `written_propagation_ids`（＝**本轮真正新写入**的对象引用，升序），**幂等命中**者归 `StepOutcome.skipped` 语义（`4f95c3d`）；本模块的判定**只此一处**（`G-06`），`chain_steps.py` **不得**重算"哪些是新的"（见 §②-9）。
4. **`root_source_id` 的载体**：当前 `Claim` schema 无顶层 `root_source_id` 字段（`extra="forbid"`），故本单以 `impact_capability.root_source_id` 承载（与 `direct_knowledge` 同源落位，allowlist 取值口 `_declared_root_source`）。若需求方希望它是**顶层正式字段**，属**又一次契约变更**（超出本次 T-11/T-12 授权），请示下。
5. **`rules/budget.yaml` 不存在**（`rules/` 0444）：G5 只改**边界语义**，未改参数来源；预算具体数值仍为 `tbd`（不阻塞）。
6. **审计"真数据下 `classify_and_record` 全落存疑（4 根全 0）"** 与本单无关：那是 `direct_knowledge` 缺省（`unknown`）导致（`§F.3` 保守不计），非缺陷；本单未改该判定。
7. **已知未测**：`tests/evidence` 之外未跑（`V-08`）。`schema/models.py` 为共享文件，理论上可能影响 `claim`/`decision`/`graph` 等批次；本单只**新增可选字段**（均有默认值），未改既有字段与语义，风险低。
8. **`G-B10-07` 的残留边界（如实登记）**：本模块幂等**已成立**；`run_daily` 全链路 `run#2 = +1` 的**唯一来源是 step 1 的重复版**（`raw/inbox/` 常驻 + `guard/executor` 追加不判重，`Ch9 §3.5` 阶段②行幂等键缺位）。该缺陷**不在本单范围**（`scripts/guard/**`、`scripts/orchestrate/**` 均属「禁止改」），**已由 `ws/idempotency`（`aa8a3ee` → 并入 `main` `a29ec90`）修复**。本单**只读**取用其两个文件在 `/tmp` 副本上验证"叠加后 `run#2` 两文件皆 0"（§②-8 D），**未做任何分支操作、未改其代码**。
   - ★ **"`as_of` 可能读到 None"这一取舍的更新（实测，非推理）**：先前登记"基线取最近非空值 ⇒ 幂等，代价是 `as_of` 读最新版本行可能读到 None（step 1 的丢字段版本是最新的）"。**该代价随 `ws/idempotency` 并入 `main`（`a29ec90`）已闭合** —— 实测（副本，`run_daily`+`classify_and_record` **连跑两次**后，按 `claim_id` 取 `recorded_seq` **最大**版本行）：
     - 真数据 · **无** #38：`claim-inbox-…amd…`（**唯一**被 step 1 重复的 inbox 主张）最新行 `count=None` ⇒ **洞真实存在、可复现**；其余 3 条 `count=0`。
     - 真数据 · **有** #38：4 条最新行 `count` **皆 = 0（非 None）** ⇒ **洞口已闭合**（claims wc-l 5→9，无 step 1 重复版）。
     - 合成（`syn-root` + 3 转述，声明 `impact_capability.root_source_id`）· **有** #38：`syn-re1..3` 最新行 `origin=syn-root`（非 None）、`syn-root` 最新行 `count=1`。
   - **结论（实测）**：**洞口已闭合，功劳属 `ws/idempotency`**。机理（亦已实测）：`record_claim_updates` 追加的新版本行经 `dict(rec)` 复制了 `source_id` / `quote_hash` ⇒ 也被 step 1 的 `(source_id, quote_hash)` 行幂等键认作"已存在" ⇒ 不再产生丢字段版本。
   - **口径澄清（非缺口）**：`independent_evidence_count` 按 `Ch6 §C.2` 步骤⑤**只写在根主张**上 ⇒ **转述主张**该字段为 `None` 属**设计**（其应写字段是 `origin_claim_id`，实测非 None）；根主张/真数据 4 条根的最新行 `count` 均非 None。两端各自"应写出字段"皆落在最新版本行。

---

## 附：③G3 / ⑤G6 的**参考资料**（已移交 `ws/daily-fix`；本流未落地）

> 以下均**未执行**（范围外，已按裁决移交 `ws/daily-fix`）。仅记录分析结论，供 `ws/daily-fix` 取用。

### ③ G3 · CV3 覆盖目标集（`scripts/daily/coverage.py`）

- **缺陷**：`coverage_target()` 在无 `registry/acceptance_input_set.yaml` 时退化返回 `sorted(companies)`（`:165-166`），而 `known_covered = set(company_latest) | position_company_ids`（`:226`）⇒ `target ⊆ known_covered` **由构造成立** ⇒ CV3 **永不命中**（`10/01 §N10.1-06` 无人守）。且 `_ACCEPT_LIST_KEYS = ("first_list","first_list_version","first_list_members")`（`:72`）为**名单式判据**，触 `R-06 ①④`。
- **就绪改法**：目标集只能取**显式来源**；缺来源 ⇒ **不退化**，记显式 `note`（`COVERAGE_TARGET_UNDETERMINED`）+ **不判 PASS**（对齐 `G-03`：无被检对象 ≠ 已验证），**不得**退化为"公司与目标集同构"的恒真形态。用例：(a) 目标集已确定且一条目标无覆盖 → **命中**；(b) 目标集未确定 → 记 note 且不判 PASS。

### ⑤ G6 · YAML 六进制陷阱（`scripts/daily/schedule.py`）

- **缺陷**：未加引号的 `time_value: 21:15` 被 YAML 解析为**六十进制整数 1275**；`_parse_hhmm` 响亮失败但错误信息误报 `'1275'`（操作员在文件里找不到 1275）。AC-4a 之所以过，是因为测试用 `yaml.safe_dump` 落成**带引号**形态。
- **就绪改法**：装载期**显式校验类型**（必须 `str` 且形如 `HH:MM`），错误信息点明"**疑似 YAML 未加引号**（被解析为整数/六十进制）"；★ 测试**必须含一条手工书写、未加引号的 YAML 文本**用例（不得全用 `safe_dump` 生成）。
