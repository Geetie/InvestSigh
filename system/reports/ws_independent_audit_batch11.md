# 批次 11 · 独立审计报告（`auditor-batch11`）

- **审计对象**：`main` 分支 `f0d9ee2..016f311` 共 **11 个提交**（原派单 8 个 `f0d9ee2..23f78db` + 追加 3 个 `3f4c372` / `bc26933` / `016f311`）
- **实现方**：主理人本人（含 `ws/idempotency` / `ws/evidence-fix` / `ws/criterion-effectiveness` 三条合并流）
- **依据**：`system/CONVENTIONS.md §九`（实现方不得自证完成）
- **审计员立场**：**尽力证伪**。凡我构造过用例但**未能**推翻的，逐条明说"我试了 X、Y，未推翻"。
- **审计时 HEAD**：审计开始为 `1c35154`，主体收尾时为 **`d1efa1d`**；**报告定稿时 `main` 已推进到 `d5a37f8`**（`git reflog` 实测：`d5a37f8 ← c2933c3 ← d1efa1d ← 1c35154`）。三者**均已超出被审范围**。本报告只对被审的 11 个提交下结论；范围外的改动只在 §⑥ 以"环境事实"登记，不作为交付结论。
- **定稿前复验（在本轮会话内重跑，非引用记忆）**：`G-42`（A1 击穿）在**当前 HEAD 的副本上重跑仍成立**（违例 6 → 0）；并新增一条 `G-RC-12`（夹具副本不完整时**静默继续**）。见 §③ 第 4 条与 §⑥ 第 6–7 条。
- **纪律遵守声明**：全程**未修改任何被审文件**；一切实验在副本（仓库外的 `/tmp/investsigh-audit-b11/`，以及该目录在仓库内的旧位置 `system/tests/.audit-b11/`）中进行；**真仓库真源未被我触碰**：实测 `git status --porcelain system/registry system/audit system/facts system/state.json` 为**空**，`system/derived/` 下唯一一条 `?? system/derived/compute_gaps.jsonl` 系**他人**跑 `run_daily` 所留（见 §⑥ 第 7 条），**非我所为**。

---

## ① 总评

| # | 被审主张（批次 11 的核心交付） | 判定 |
|---|---|---|
| 1 | `StepOutcome.skipped` 字段 + `G1-05` 判据改为 `not produced and not skipped`（`4f95c3d`） | **不够** |
| 2 | `produced` / `skipped` 语义切分（裁定 R2）在 step 2 真的接上了（`790643c`） | **好**（step 2）／**不够**（step 5/6 反被这一改动搞坏） |
| 3 | `stage_gate` 首日豁免从"死代码"改为"追加序判定"（`fd49a20`） | **不够**（修好了"恒为 0"，但豁免条件与真实 `Task` 形状不匹配 ⇒ 转向"恒误豁免"） |
| 4 | `derived/` 纠正为"非唯一真源"（`5a314a3`） | **错**（同一提交范围内存在逐字相反的两套声明；且"可重算"的理由不成立） |
| 5 | 夹具不再继承运行态 `state.json`（`23f78db`） | **好**（就 `state.json` 而言）／**不够**（同族缺陷尚有 **4 个登记层真源**未覆盖、**无机器绑定**；且**副本不完整时静默继续**，无任何完整性断言 —— `G-RC-11` / `G-RC-12`） |
| 6 | `_stage_gate_verdict` 改数据驱动（`3f4c372`） | **不够**（两个方向确实都查了；但有**无歧义检查缺失**的误判空间） |
| 7 | 第 11 道 pre-commit `criterion_effectiveness_guard`（`bc26933`） | **好**（三条机器绑定实测都成立）／**不够**（`blocked_hint` 的语义级核对仍为零） |
| 8 | 登记 `G-RC-09` / `G9-1` / `G9-2` / `G-28`，`G9-1` 可独立复现（`016f311`） | **好**（`G9-1` 我独立复现成功，输出逐字一致） |

**一句话总评：方向对、修实了一半、但"改完就信"的老毛病仍在两处复发。**

- ✅ **真修好的**：step 2 的 `produced`/`skipped` 判别力（我三连跑复现：两轮观测量确实不同了）；首日豁免从"计数恒 0 的静默失效"变成"可见计数 2"；`criterion_effectiveness_guard` 的三条绑定我用注入法逐条打穿了它——**没打穿**；`G9-1` 独立复现成功。
- ❌ **没做/不够的**：`skipped` 是**处理器自报、零校验**的字段，`G1-05` 的"双空才判违例"可被一个**凭空字符串**击穿（实测 6 条违例 → 0 条）；首日豁免的谓词 `_holds_valid_result()` 与**真实生产代码写出的行形状**不匹配 ⇒ 真违规被当"首日"放过；`_declare_incomplete_when_empty` 里那个 `not outcome.skipped` 分支**对它包装的两步（step 5/6）恒为真**，于是**第二次 `run_daily` 必然 `blocked`**——这正是 `4f95c3d` 自己在 docstring 里承诺要防的事，**机器上不生效**。
- ⚠️ **错**：`.gitignore` 逐字写"`derived/` **非**唯一真源、可由 `facts/` + `method_version` **确定性重算**"，而 `scripts/compute/store.py` 三处 docstring 逐字写"`derived/derived_values.jsonl` —— `DerivedValue` 的**追加式真源**"、"`derived/` 是**计算层自有真源**"；且 `contract.py:157` 的 `computed_at=datetime.now(timezone.utc)` 使该"确定性重算"**实测不成立**。

---

## ② 逐条结论表

> 所有命令均在 `system/` 下执行。`$PY` = `/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`。
> 前缀 `CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0` 用于避开宿主 FS broker（见 §④ 环境说明）。

### A 组：`skipped` 字段与 `G1-05`（`4f95c3d`）

| 主张 | 判定 | 证据（命令 + 输出 + 退出码） |
|---|---|---|
| A1 `skipped` 是受校验的真值，只有"幂等命中"才能填 | ❌ **证伪成功** | 桩处理器返回 `StepOutcome(produced=[], skipped=["claim-我瞎编的-不存在于真源"])`：<br>`--- 反向对照：桩什么都不做（produced=[] skipped=[]） ---`<br>`  G1-05 违例总数 = 6（其中『空执行』= 6）`（step 1–6 各一条）<br>`--- 证伪点：桩什么都不做，但编造 skipped=['claim-我瞎编的-不存在于真源'] ---`<br>`  G1-05 违例总数 = 0（其中『空执行』= 0）`<br>`exit=0`<br>⇒ `skipped` 仅由处理器**自报**，全仓库**无任何**与真源/幂等键的交叉核对 ⇒ `G1-05` 的强度可被一个**不存在的字符串**抹平。见 **G-42**。<br>**★ 定稿前在当前 HEAD（`d5a37f8` 的 `system/` 副本）上重跑**（`exp_recheck_current.py`，`exit=0`）：<br>`[反向对照] 双空：produced=[] skipped=[]  → G1-05 违例总数=6 其中『空执行』=6 blocked=True`<br>`[证伪点] 编造 skipped：produced=[] skipped=['claim-我瞎编的-不存在于真源']  → G1-05 违例总数=0 其中『空执行』=0 blocked=True`<br>`[加强方案反向对照] skipped 复用真源里**真实存在**的 id：produced=[] skipped=['claim-nvidia-newsroom-q4-fy2025-4d13454fd859']  → G1-05 违例总数=0 其中『空执行』=0 blocked=True`<br>⇒ **不只"瞎编的串"能过，"要求 skipped 的 id 真实存在于真源"这个加强方案也不闭合**（复用一条真源里既有的 claim id 同样 0 违例）——因为任何**真实存在**的对象引用都能被任意步冒领。**正解必须绑到"本步输入集∩真源"或"本步写入凭据"，见 G-42 修法。** |
| A2 非合法 `status` 值必须 fail-safe 落 degraded | ✅ **主张成立** | 注入 `weird_unknown_value` / `""` / `"OK"` 三种非合法值 ⇒ `degraded=True`、`produced=[]`；`degraded=False` 时 `skipped` 才计入 `produced`。fail-safe（`if OK / elif SKIPPED / else: degraded=True`）成立。**我未推翻。** |
| A3 `skipped` 在 step 1 不计入 `produced`（裁定 R2） | ❌ **证伪成功** | `system/scripts/orchestrate/ingest_step.py:242-249`：`elif result.status == STATUS_SKIPPED and result.claim_id: produced.append(result.claim_id)` —— 幂等命中**仍计入 `produced`**，与裁定 R2（"`produced` = 本轮真正新写入"）及 step 2 的实现**逐字相反**，也与同文件 docstring 的声明冲突。后果：**step 1 的 `produced` 在幂等重跑时恒非空 ⇒ `G1-05` 对 step 1 恒假**（守卫失效）。见 **G-42**（同族）。 |

### B 组：`stage_gate` 首日豁免（`fd49a20`）

| 主张 | 判定 | 证据 |
|---|---|---|
| B3 修好了"死代码"：`degrade_first_day_exempt` 从恒 0 → 可见，`daily_run` 从 `BLOCKED` → `PASS`，`--stage all` FATAL 9 → 7 | ✅ **三条全部复现** | 真仓库副本（61 行真数据：claims 5 / industry_nodes 44 / tasks 4 …），命令 `$PY <copy>/scripts/delivery/stage_gate.py <copy> --no-report --stage daily_run`：<br>**当前实现（HEAD）**：`exit=0  note: daily_run: PASS  degrade_first_day_exempt=2  FATAL=0`；`--stage all`：`exit=1 FATAL=7`<br>**旧实现（`git show 4f95c3d:system/scripts/delivery/stage_gate.py` 覆盖后）**：`exit=1  note: daily_run: BLOCKED  degrade_first_day_exempt=0  FATAL=2`；`--stage all`：`exit=1 FATAL=9`<br>⇒ 主理人"0→2 / BLOCKED→PASS / 9→7"**逐项复现**。 |
| B1 豁免不可被绕过 | ❌ **证伪成功（1 个绕过输入）** | 用例 c1：两行 `[status=done + output_refs=[] + last_valid_result_ref=null, status=failed]`（**这正是 `pipeline._write_check_record()` 写出的真实字段形状**）<br>`exit=1  degrade_first_day_exempt=1  FATAL=['CV4 覆盖目标集为空…']`<br>唯一 FATAL 是**无关的 CV4**；预期的"降级未保留上次有效结果"FATAL **没有出现** ⇒ 后续 `failed` 行被当成"首日"**误豁免**。见 **G-43**。 |
| B2 `_holds_valid_result()` 的两载体已穷尽 | ❌ **证伪成功** | `Task` 模型（`schema/models.py:953`）确实只有 `last_valid_result_ref` / `output_refs` 两个载体——**载体是穷尽的**；但**全仓库 `output_refs=` 零个生产赋值点**（`grep -rn "output_refs=" system/scripts/` 只命中测试）⇒ 两个载体在真实 `run_daily` 里**恒为空** ⇒ 谓词**恒 False**。语义上"载具穷尽 ≠ 判定有效"。见 **G-43** / **G-45**。 |
| B1-c4 跨模块口径一致 | ❌ **证伪成功** | 同一批行 `[done(output_refs=[]), failed]`：<br>`degrade.last_valid_result_ref(copy) = 'check_d1_full'   ← 认为有`<br>`stage_gate._holds_valid_result(row0) = False   ← 认为无`<br>⇒ 两处"上次有效结果"谓词**互相矛盾**。见 **G-45**。 |
| B1-c3 乱序输入不得豁免 | ⚠️ **未构成绕过（我的用例设计有误，如实登记）** | 我把 `failed` 放在 idx 0，其前无任何行 ⇒ 豁免本身**符合设计**，不是缺陷。同用例的旁证"`append_only_guard` 对该乱序文件 exit=0"**不成立**：该守卫只看 `git diff --cached`（`append_only_guard.py:38-44`），副本中无暂存内容 ⇒ exit=0 属**正常空转**，不能据此说"守卫不管行序"。**此条我撤回，不计入结论。** |

### C 组：`derived/` 归属（`5a314a3`）

| 主张 | 判定 | 证据 |
|---|---|---|
| C1 "`derived/` 非唯一真源"在仓库内表述一致 | ❌ **证伪成功（找到逐字矛盾）** | 根 `.gitignore:17-21,28`：`★ 唯一真源 = system/facts/ 的 18 个追加式 JSONL … **不含** derived/`、`派生输出：可由 facts/ + method_version **确定性重算**，故非唯一真源`。<br>`scripts/compute/store.py:42`：`"""derived/derived_values.jsonl —— DerivedValue 的追加式真源。"""`；`:47`：`derived/compute_gaps.jsonl —— 缺口对象的追加式真源（缺口也留痕）`；`:115`：`（derived/ 是计算层自有真源…）`；`:171` 同。见 **G-48**。 |
| C2 `derived/` 可由 `facts/` + `method_version` 确定性重算 | ❌ **证伪成功** | `scripts/compute/contract.py:157`：`computed_at=computed_at or datetime.now(timezone.utc)` ⇒ 默认取**墙钟**；同输入两次写出的行**逐字节不同**。`version` 是 `run_derived --version` 的 **CLI 参数**（不来自 `facts/`；`facts/` 中 `"computed_at"` 出现 0 次）⇒ **仅凭 `facts/ + method_version` 复现不出 `derived/` 的内容**。⇒ `.gitignore` 给出的"为何不跟踪"的**理由本身不成立**。见 **G-48**。 |
| C3 忽略（删除）`derived/` 后门禁行为变化 | ✅ **未证伪** | 21 个守卫 + `run_derived`（含 `--strict`）在"有/无 `derived/*.jsonl`"下**输出与退出码完全一致**；唯一差异是 `append_only_guard` 的 pathspec 字符串（副本路径不同所致）。**我试了 21 个守卫与 `run_derived`，未推翻**"无门禁因该文件不存在而改变行为"。 |

### D 组：step 2 接线（`790643c`）

| 主张 | 判定 | 证据 |
|---|---|---|
| D2 判别式成立：幂等与非幂等**可区分** | ✅ **独立复现成功** | 种子投递口后连跑 3 轮：run#1 `produced=1 skipped=0`；run#2/3 `produced=[] skipped=1`，且 `set(skipped) == set(首轮 produced)` → `True`；`facts/claims.jsonl` 行数 `0→2→2→2`（不增）。真仓库那 5 条真实 claim 的副本上：run#1 `+4`、run#2 `+0`，`skipped` = 首轮那 4 条。<br>官方入口 `run_pytest.sh tests/injection/test_chain_steps_wiring.py` → `13 passed in 37.53s`；`tests/injection/test_prompt_injection.py` → `21 passed in 39.27s`。⇒ **step 2 的接线是真的。** |
| D1 幂等重跑不会触发 `G1-05` 假红 | ❌ **证伪成功，但换到了 step 5/6** | **step 5**：首轮 `produced=3 skipped=0`；**重跑 `produced=0 skipped=0`** ⇒ `_declare_incomplete_when_empty` 补 `incomplete_reason` ⇒ 编排器记 `STATUS_GAP` ⇒ 整轮 `blocked`。未包装的原始 handler 重跑则 `incomplete_reason=无`（对照成立）。<br>根因**机器可验**：`grep -rn "skipped=" system/scripts/` 全仓库**只有一处**赋值 —— `scripts/orchestrate/chain_steps.py:132`（step 2）；`scripts/compute/step.py:54` 与 `scripts/decision/step.py:67` 的 `StepOutcome(...)` **都没有 `skipped`**（已逐字读过构造现场）。而适配器**恰好只包装这两步**（`chain_steps.py:306/318`），两步 `blocking: true`（`rules/pipeline.yaml`）⇒ **第二次 `run_daily` 恒 `blocked`**。见 **G-44**。 |
| D3 `produced` 非空 + `status=gap` 的连带误判 | ❌ **不够** | `chain_steps.py:132` 的 step 2 用的是 `skipped = sorted(considered - written)`——`considered` 是"核验通过集合"，与"是否写了行"**有关**（这点比旧实现强）。但同一文件里 step 1 的 `ingest_step.py` 走的是相反口径（A3）⇒ **同一契约两个方向的口径并存**，`G1-05` 的强度取决于走哪条路。见 **G-42**。 |

### E 组：夹具与运行态（`5a314a3` / `23f78db`）★

| 主张 | 判定 | 证据 |
|---|---|---|
| E1 `_COPY_SKIP` / `_TRUTH_STEMS` 已穷尽全部真源 | ❌ **证伪成功（本轮最重要的发现）** | ① `REGISTRY_MODELS` 共 **4 条登记层真源**：`registry/corporate-actions`、`registry/quality-labels`、`registry/idempotency`、`audit/rule_changes`（实测枚举）。<br>② `_COPY_SKIP = {__pycache__, .pytest_cache, .venv, .work, index, reports, derived, .locks, state.json}` —— **不含 `registry`、不含 `audit`**；`_TRUTH_STEMS` **18 个全在 `facts/`**（实测枚举）。<br>③ 实测：给这 4 个文件各写 1 行后跑 `registry_schema_guard`，输出 `lines_validated: 4`（空时为 `0`）⇒ **门禁观测量随真仓库内容改变**；`_reset_truth_source()` 之后这 4 个文件**各仍剩 1 行**（随 `copytree` 复制进来的）。<br>⇒ 夹具的**真源清单是手工台账，且漏了 4 个已登记真源**。见 **G-RC-11**。 |
| E1 附：`_TRUTH_STEMS` 与模型注册表一致 | ⚠️ **今日恰好一致，但无机器绑定** | 实测：`JSONL_MODELS` 18 条，`_TRUTH_STEMS` 18 条，`models == stems` → `True`，两侧差集均为 `[]`。**但**：全仓库**没有任何断言**把两者绑起来（`grep -rn "_TRUTH_STEMS" tests/` 只命中 `tests/conftest.py` 自身）；且 `T-13` 正在裁定"扩表 18→22" ⇒ 漂移风险**即将放大**。 |
| E1 附：`derived` 有机制层断言吗 | ❌ **未做** | `tests/injection/test_wiring_guards.py:167` 有一条 `assert "state.json" in _COPY_SKIP`（`state.json` 的机器绑定）。`grep -rn "derived" tests/ --include='*.py' \| grep "_COPY_SKIP"` → **空**。⇒ `_COPY_SKIP` 里 9 项只有 1 项被断言。 |
| E2 `pristine_code_root` 会被测试写入吗 | ✅ **未证伪** | 完全复刻其三步变换（`copytree` → `_make_writable` → `_reset_truth_source` → `_lock_rules_perms`）后在进程内逐条跑 `tests/guards` 的 **20 条守卫**（参数逐字一致）：**新增 0 / 修改 0 / 删除 0 项**，20 条全部 `exit=0`。**我试了 20 条守卫，未推翻。** |
| E 附：夹具副本是否稳定完整 | ✅ **未证伪** | 复刻 `code_root` 创建流程连做 **6 次**：`[1]..[6] OK  文件数 副本=217`，`==> 6 次中 0 次不完整`；`facts/*.jsonl`（18）、`registry/*.jsonl`（3）、`audit/`、`rules/`、`scripts/`、`schema/` 全部齐备。 |

### F 组：覆盖性

| 主张 | 判定 | 证据 |
|---|---|---|
| F1 新字段/新分支都有测试覆盖 | ❌ **证伪成功** | ① `_declare_incomplete_when_empty` 的 `not outcome.skipped` 分支**零覆盖**：`tests/injection/test_chain_steps_wiring.py` 的 4 条适配器用例分别传 `StepOutcome(produced=[], degraded=True)` / `produced=["dv-1"]` / `produced=[], incomplete_reason=...` / `StepOutcome()` —— **没有一条**设 `skipped`。（这也是 G-44 的反面：分支存在但从不生效、也从不被测。）<br>② `_COPY_SKIP` 9 项只有 `state.json` 有断言（见 E）。<br>③ 根 `.gitignore` 的 `system/derived/*.jsonl` **无测试**。 |
| F2 `test_idempotency_rows.py` 三组断言独立可复现 | ✅ **成立** | 官方入口单文件跑：`test_wiring_guards.py` `15 passed in 35.90s`；`test_chain_steps_wiring.py` `13 passed`；`test_prompt_injection.py` `21 passed`。`test_idempotency_rows.py` 的三组断言（不新增行 / 显式 `skipped` / `skipped` 集合 = 首轮 `produced`）与 D2 的独立复现结果**一致**。 |

### 追加 3 个提交

| 主张 | 判定 | 证据 |
|---|---|---|
| `3f4c372` `_stage_gate_verdict` 数据驱动，**两个方向**都查 | ✅ **两个方向都查了**；⚠️ 有误判空间 | 实测：`PASS` + `exit 1` → 判 `False`；`BLOCKED` + `exit 0` → 判 `False`。**未推翻**"阶段缺失 / 未标注"的检测。两点**不够**：① **无歧义检查** —— 同一阶段**同时**出现 `PASS` 与 `BLOCKED` 时，`seen[stage] = "PASS"` 在 `elif` 之前写，**静默取 PASS**；② 阶段名出现在**无关 note 文字**里会被当取值读。建议登记 `G-47`（低）。 |
| `bc26933` 三条机器绑定真的成立（穷尽 / 不重复 / 每条反例实测拦得住） | ✅ **实测成立** | 基线：`$PY scripts/checks/criterion_effectiveness_guard.py . --no-report` → `RESULT: PASS（0 violations）`，`exit=0`；`scanned registry_entry_tests_resolved: 13`、`counterexample_entries: 11`、`ineffective_entries: 2`、`criteria_bound: 12`、`stages: 5`。<br>**A 注入**（新增绑定判据但不登记）⇒ `exit=1` FATAL；**B 注入**（删掉已绑定判据而登记仍在）⇒ `exit=1` FATAL。**两个方向都拦得住，未推翻。** |
| `016f311` `G9-1`（`daily_run::task_state_auditable` 已绑定但零检查）可独立复现 | ✅ **独立复现成功** | 输出逐字一致：`note: 判据有效性缺口[daily_run::task_state_auditable]：… 实测无可判别检查（… AST 实测该 id 在代码区只出现 1 次：stage_gate.py:575 的声明本身；把任务 status 置为非法值 totally_bogus_status 时，阶段④ 的违例集合与合规输入**完全相同**（都是 0 条））`；`note: 无反例判据（已绑定但只有 ineffective 条目）：1 条（['daily_run::task_state_auditable']）`。 |
| `bc26933` 的 `blocked_hint` 是否也有语义级核对 | ❌ **未做** | `grep -rn "blocked_hint" system/` 只命中 `criterion_effectiveness_guard.py:204`（**仅非空字符串校验**）与测试文件的 docstring/一处 `"blocked_hint": "x"` 注入。`registry/criterion_counterexamples.yaml` 的 11 条 `blocked_hint` **值本身没有任何机械核对**（没有遍历登记表逐条核对"该提示串在输出中出现 / 不出现"的元测试）。⇒ 与 `4f95c3d` 的**伪造 `skipped`** 是**同一族**缺陷（"登记了文字、没人核对文字"）。见 **G-46**。 |

---

## ③ 我构造过但**没能证伪**的尝试（同样界定结论强度）

1. **A2 fail-safe**：注入 `weird_unknown_value` / `""` / `"OK"` 三种非合法 `status` ⇒ `degraded=True`、`produced=[]`。**未推翻。**
2. **E2 `pristine_code_root` 不被写**：在进程内逐条跑 `tests/guards` 的 20 条守卫（参数逐字一致），**新增 0 / 修改 0 / 删除 0 项**，20 条全部 `exit=0`。**未推翻。**
3. **C3 忽略 `derived/` 后门禁行为不变**：21 个守卫 + `run_derived`（含 `--strict`）在"有/无 `derived/*.jsonl`"下输出与退出码完全一致。**未推翻**（差异只有 `append_only_guard` 的 pathspec 字符串，属副本路径不同）。
4. **E 附：夹具副本稳定完整** —— ⚠️ **这条我要修正，我先前"未证伪"的结论站不住**。
   - **第一次实测（6 次）**：`6/6 OK`（217 文件，18 真源 + `registry/`/`audit/`/`rules/`/`scripts/`/`schema/` 齐备）⇒ 当时结论"未推翻"。
   - **第二次实测（30 次，同一脚本、同一宿主默认环境）**：**7/30 副本不完整**，每次都缺约 **30 项**（`facts/`、`raw/`、`rules/`、`registry/`、`audit/` 目录及其下文件），**且 `copytree` 未抛任何异常**；伴随 stderr `[safe-delete][SAFE_DELETE_FAIL_CLOSED] {"target": ".../raw/inbox", "reason": "trash-failed", "detail": "FSPathMakeRefWithOptions failed (status -43)"}`。
   - **对照实测（10 次，`CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`）**：`10/10 OK`（`==> 10 次中 0 次不完整`）。
   - **我试图再测时的失败**：在宿主默认环境下重跑（N=6 与 N=30 各一次）**两次都在打印任何输出之前被宿主 SIGKILL**（`Exit Code: 137`，`-u` 无缓冲仍无 stdout）⇒ **本轮未能再次复现**。
   - ⇒ **修正后的结论**：我**不能**说"未证伪"。正确表述是"**夹具完整性依赖宿主 FS broker 状态；broker 关闭时 10/10 完整，broker 开启时我 30 次里见到 7 次静默缺件**"。（这同时说明：`run_pytest.sh` 之所以稳，不只是因为关掉了 broker 的**删除**干扰，也因为关掉了它的**复制**干扰。）已登记为 **`G-RC-12`**（§④）。
5. **`3f4c372` 的方向检测**：`PASS+exit1`、`BLOCKED+exit0` 两种"自相矛盾输出"都被判 `False`。**未推翻**。
6. **`bc26933` 的 A/B 两个注入方向**：都 `exit=1` FATAL。**未推翻。**
7. **F2 四个关键测试文件**：单文件逐一跑全绿（15 / 13 / 21 / 及 `test_idempotency_rows.py`）。**未推翻**其"断言真的在守"。
8. **我撤回的一条**：B1-c3 的"乱序不得豁免"。我的期望写错了（`failed` 在 idx 0，其前无行 ⇒ 豁免符合设计），且旁证的 `append_only_guard exit=0` 是**空转**（该守卫只看 `git diff --cached`）。**此条不作为结论。**

---

## ④ 新发现的缺陷

> 编号约定沿用 `reports/phase1_gap_register.md`（当前已用到 `G-41` / `G-RC-10`），本报告使用 `G-42` ~ `G-48` / `G-RC-11` / `G-RC-12`。
> 所有复现步骤**均在我实测通过的命令序列**上给出；实验脚本与副本存放在**仓库之外**（`/tmp/investsigh-audit-b11/`，含一式 `base/` 副本），**仓库工作树内不留任何我产生的中间产物**（见 §⑥ 第 5 条）。

### G-42 —— `skipped` 是自报字段、零校验：`G1-05` 可被一个凭空字符串击穿 【严重度：**高**】

- **位置**：`system/scripts/orchestrate/pipeline.py:440`（判据 `not step.produced and not step.skipped`）；`system/scripts/orchestrate/ingest_step.py:242-249`（反向口径）
- **复现**：
  1. 桩处理器返回 `StepOutcome(produced=[], skipped=["claim-我瞎编的-不存在于真源"])`
  2. `assert_steps_complete()` 的 `G1-05` 违例由 **6 条 → 0 条**
- **为什么是缺陷而不是设计**：裁定 R2 把 `skipped` 定义为"**行幂等命中**（`Ch9 §3.5` 阶段②，键 `(source_id, quote_hash)`）"——这是一个**可与真源交叉核对**的性质（`executor._existing_claim_keys(root)` 就能核）。当前实现把它降级为**处理器自报的自由文本**，等于把判据的强度交给被检对象自己声明。**同族**：B 组的 `degrade_first_day_exempt`（G-43）与 `bc26933` 的 `blocked_hint`（G-46）。
- **建议修法（★ 定稿前我已实测推翻了本报告初稿给的第一版修法，故此处给的是修订版）**：
  - ❌ **不闭合的修法（实测）**："要求 `skipped` 中每个 id 在真源中可解析" —— 我构造反向对照：桩把 `skipped` 填成**真源里真实存在**的 `claim-nvidia-newsroom-q4-fy2025-4d13454fd859`（**这不是我瞎编的串，是随副本复制进来的真实 claim id**），`G1-05` 违例同样 `6 → 0`。原因：任何**真实存在**的对象引用都可被**任意一步冒领**，"存在性"根本不等于"归属性"。⇒ **这条加强方案不闭合，不要再照它改。**
  - ✅ **闭合的那一半（`produced` 方向）**：`produced` 是**可判定**的——每个 ref 必须是本轮**新出现在真源里的行**（`created_at ∈ [run_started_at, run_ended_at]`）。桩报 `produced=[]` 时该条自然通过，但"**编造 `produced` 骗过完整性判据**"这一反向攻击被彻底封死。**这一条建议立即加**（成本低、无假阳性）。
  - ⚠️ **闭合不了的那一半（`skipped` 方向）**：`skipped` 的语义是"**我读了、判定无需写入**"，而"读了什么"**只能由处理器自述**——`considered` 集无论由处理器返回还是由编排器派生，最终来源都是处理器。⇒ **纯 in-band 校验不可能闭合**。
  - ⇒ **因此我建议的不是"再加一条断言"，而是把声明降格 + 留痕**：① 在 `pipeline.py` 的 docstring 与判据台账里**明确写**：`G1-05` 是"**不得静默空转**"（liveness / 记账格式）判据，**不是**"产物真实齐备"判据 —— 删掉现文中"判据强度**未削弱**"这句**会被下一次审计当成已闭合**的表述；② 让幂等命中**真实留痕**到**已登记的真源** `registry/idempotency.jsonl`（该表已在 `REGISTRY_MODELS` 里、且目前**无写入方**）记 `(step, object_ref, decision, run_id)`，把"自报"变成"**跨轮可核对的账**"；③ 把"处理器可伪造 `skipped`"作为**已知残留**登记进 `CONVENTIONS.md`，避免轮次间重复发现同一条。
- **另一处同族（`ingest_step.py`）**：声明与实现相反（docstring 说命中"仍计入 `produced`"，裁定 R2 说计入 `skipped`）⇒ **step 1 的 `G1-05` 恒假**。这一条**必须由需求方裁定走哪个口径**，我不自裁。

### G-43 —— 首日豁免的谓词与真实 `Task` 形状不匹配 ⇒ 真违规被误豁免 【严重度：**高**】

- **位置**：`system/scripts/delivery/stage_gate.py:493-508`（`_holds_valid_result`）、`:557-566`（豁免分支）；生产侧 `system/scripts/orchestrate/pipeline.py::_write_check_record()`
- **复现**（实测输出逐字）：
  ```
  用例：[{"status":"done","output_refs":[],"last_valid_result_ref":null},
         {"status":"failed"}]
  $PY <copy>/scripts/delivery/stage_gate.py <copy> --no-report --stage daily_run
  → exit=1  degrade_first_day_exempt=1  FATAL=['CV4 覆盖目标集为空…']
  ```
  唯一 FATAL 是**无关的 CV4**；预期的那条"降级未保留上次有效结果"FATAL **没有出现**。
- **为什么必然发生**：`_write_check_record()` **不填 `output_refs`、不填 `last_valid_result_ref`**（两载体同时为空），而 `_holds_valid_result` 要求 `last_valid_result_ref` 真值 **或** (`status=="done"` **且** `output_refs` 非空) ⇒ 对**所有**生产写入的行**恒返回 `False`** ⇒ `any(...)` 恒 `False` ⇒ 每个 `failed` 行都被判"首日"。
- **量级**：`daily_run` 阶段真仓库当前 `degrade_first_day_exempt=2`（实测）。也就是说，**"2 条豁免"里没有一条能证明前序真有有效结果** —— 计数可见了，但**含义不可信**。
- **建议修法**：豁免谓词改为"**真源里确实存在该 `task_id` 的更早 `done` 行且其 `check_record.changed` 有记录**"，而不是依赖两个**从不被填**的字段；或在 `_write_check_record()` 补填 `output_refs`。二者**必须选一**，否则"改完还是恒误豁免"。

### G-44 —— `_declare_incomplete_when_empty` 的 `skipped` 分支对 step 5/6 **恒为真**：第二次 `run_daily` 必然 `blocked` 【严重度：**高**】

- **位置**：`system/scripts/orchestrate/chain_steps.py:241-270`（`not outcome.produced and not outcome.skipped and ...`）、`:306` / `:318`（只包装 step 5/6）
- **机器可验的根因**：`grep -rn "skipped=" system/scripts/` → **全仓库仅 1 处**：`chain_steps.py:132`（step 2）。`scripts/compute/step.py:54` 与 `scripts/decision/step.py:67` 的 `StepOutcome(...)` **都不设 `skipped`** ⇒ 对这两步 `not outcome.skipped` **恒真** ⇒ docstring 承诺的"正常幂等重跑不会被误标"**不生效**。
- **复现**（实测）：
  - step 5 首轮：`produced=3 skipped=0`
  - step 5 重跑：`produced=0 skipped=0` ⇒ 适配器补 `incomplete_reason` ⇒ 编排器记 `STATUS_GAP`；而 `rules/pipeline.yaml` 里 step 5/6 `blocking: true` ⇒ **整轮 `blocked`**
  - 对照：未包装的原始 handler 重跑 → `incomplete_reason=无`
- **为什么会发生 `produced=0`**：`scripts/compute/` 的计算层本身是幂等的（`derived/` 行已存在 ⇒ `written_derived_ids` 为空）。⇒ **"幂等"在这里被当成了"没做完"。**
- **建议修法**：让 `compute/step.py` / `decision/step.py` 也按裁定 R2 填 `skipped`（计算层有能力报"本轮读入 N 个、均无需追加"）；或在 `derived`/`decision` 层返回"considered 数"作为 `skipped` 的上界。**这是 G-44 的正解，也是 `4f95c3d` 未完成的一半。**

### G-45 —— "上次有效结果"两个模块口径互相矛盾 + `output_refs` 零生产赋值点 【严重度：中高】

- **证据**（同一批行，实测）：
  ```
  degrade.last_valid_result_ref(copy)   = 'check_d1_full'   ← 认为有
  stage_gate._holds_valid_result(row0)  = False              ← 认为无
  ```
- **另一条**：`Task`（`schema/models.py:953`）只有 `last_valid_result_ref` / `output_refs` 两个载体（**载具穷尽**这一点我确认了），但**全仓库 `output_refs=` 零个生产赋值点**（只出现在测试里）⇒ 两个"穷尽"的载体在真实运行中**都是空的**。
- **为什么是缺陷**：`G1-04`（`gap_to_task.py`）对同一行判 `exit 1` FATAL（"空执行"），`stage_gate` 却判"不持有有效结果" ⇒ **同一行、两个守卫、相反结论**。这正是"声明与实现脱节"的跨模块版本。
- **建议修法**：把"上次有效结果"的判定**收口到唯一一处**（`scripts/daily/degrade.py`），`stage_gate` 改为调用它；并补一条**反向对照测试**（`output_refs` 空 / 非空两态必须给出可区分结论）。

### G-46 —— 判据登记表的 `blocked_hint` 无机器核对（`bc26933` 的缺口） 【严重度：中】

- **证据**：`grep -rn "blocked_hint" system/` 只命中 `criterion_effectiveness_guard.py:204`（**仅非空**）与测试文件。`registry/criterion_counterexamples.yaml` 的 **11 条** `blocked_hint` 值**无任何机械核对**（没有遍历登记表、逐条检查该提示在命中/未命中两种输入下出现/不出现的元测试）。
- **为什么是缺陷**：`bc26933` 的卖点正是"把'接了'强化到'真的会拦'"。三条绑定（A/B/C/E）我实测都成立，**但绑定的是函数名与 id，不是提示语义** ⇒ 一条 `blocked_hint` 可以写成任何字符串并通过全部门禁（**与 G-42 的伪造 `skipped` 同族**）。
- **建议修法**：仿照 `criterion_counterexamples.yaml` 的 counterexample 语义，加一条"逐条 `blocked_hint` ⊆ 该判据 counterexample 探针实测输出"的断言（或给每条 `blocked_hint` 指定一个必须命中的探针测试名）。

### G-47（建议登记，低）—— `_stage_gate_verdict` 无歧义检查 【严重度：低】

- `3f4c372` 的两个方向我都验证了（未推翻）。残留两点：① 同一阶段**同时**出现 `PASS` 与 `BLOCKED` 时 `seen[stage] = "PASS"` **静默取 PASS**（`elif` 顺序所致），无"自相矛盾输出必须判 fail"的检查；② 阶段名出现在**无关 note 文字**里会被当取值读。建议补一条"同阶段取值集合大小必须为 1，否则判 fail"。

### G-48 —— `derived/` 归属：仓库内两套逐字相反的声明，且"可重算"的理由实测不成立 【严重度：中】

- **矛盾原文**：
  - 根 `.gitignore:17-21`：`★ 唯一真源 = system/facts/ 的 **18 个**追加式 JSONL … **不含** derived/`；`:26-28`：`派生输出：可由 facts/ + method_version **确定性重算**，故非唯一真源、不进版本库`
  - `scripts/compute/store.py:42`：`"""derived/derived_values.jsonl —— DerivedValue 的追加式真源。"""`；`:47`：`缺口对象的追加式真源（缺口也留痕）`；`:115`：`（derived/ 是计算层自有真源…）`；`:171` 同
- **"可重算"实测不成立**：`scripts/compute/contract.py:157` `computed_at=computed_at or datetime.now(timezone.utc)` ⇒ 同输入两次写出的行**逐字节不同**；`version` 是 `run_derived --version` 的 **CLI 参数**，不来自 `facts/`（`facts/` 中 `"computed_at"` 出现 0 次）⇒ **`facts/ + method_version` 复现不出 `derived/` 的内容**。
- **补一条旁证**：`DerivedValue`（`schema/models.py:400`）**不在** `JSONL_MODELS` 里，而 `store.py` 的 docstring 把 `JSONL_MODELS` 描述为"18 JSONL → 模型映射（**唯一真源**）" ⇒ 三处口径（`.gitignore` / `store.py` / `JSONL_MODELS`）**互不一致**。
- **建议修法**：若 `derived/` 确非唯一真源，则 `store.py` 的"真源"措辞**必须改**（改为"计算层**自有持久化**"），并在 `.gitignore` 注明 `computed_at` 的不确定性（或把 `computed_at` 从"可重算"承诺里排除）。**这是文档级改动，但属于"声明的可核性"，不是措辞洁癖。**

### G-RC-11 —— 夹具真源豁免清单是手工台账：**4 个已登记真源**既不被清空、也不被排除 【严重度：中高】

- **位置**：`system/tests/conftest.py:57`（`_COPY_SKIP`）、`:77`（`_TRUTH_STEMS`）、`:84`（`_reset_truth_source`）
- **实测**（逐条）：
  1. `REGISTRY_MODELS` 4 条：`registry/corporate-actions`、`registry/quality-labels`、`registry/idempotency`、`audit/rule_changes`
  2. `_COPY_SKIP` 不含 `registry` / `audit`；`_TRUTH_STEMS` 18 条**全在 `facts/`**
  3. 给 4 个文件各写 1 行 → `registry_schema_guard` 输出 `lines_validated: 4`（空时 `0`）；`_reset_truth_source()` 之后**各仍剩 1 行**（随 `copytree` 进来）
  ⇒ **门禁观测量随真仓库内容改变**（`G-RC-02` / `G-RC-07` 的**同一形态**）
- **今天为什么还没炸**：这 4 个文件在真仓库**各 0 行**（实测），且 `grep` 显示**生产代码里没有写入点**（`audit/rule_changes.jsonl` 只在 `registry_models.py` 被登记为真源，尚无写入方）。⇒ 属**潜伏**缺陷。
- **为什么必须现在修**：`T-13` 正在裁定"facts 扩表 18→22"，`_TRUTH_STEMS` 与 `JSONL_MODELS` 的**手工一致**（我实测今日 18=18 相等）**没有任何机器绑定**（`grep -rn "_TRUTH_STEMS" system/tests/` 只命中 conftest 自身）⇒ 下一次扩表就会出现"新真源没被清空"。
- **建议修法**（两处机器绑定，**这正是别人正在做的任务 #55**，我只做审计登记）：① `_TRUTH_STEMS` 从 `JSONL_MODELS` **派生**（不写字面量）；② 断言 `_COPY_SKIP ∪ _TRUTH_STEMS` 覆盖 `JSONL_MODELS ∪ REGISTRY_MODELS` 的**全部**真源。
- ★★ **合并前复核（2026-09-16，我在 `.worktrees/ws-schema-expand`（`1d09ae0`）上实测）：这条只被闭合了**一半**，且**恰好漏掉我点名的那个 case**。**
  - ✅ **已闭合的一半（`facts/` 侧，做得对）**：`_TRUTH_STEMS` 已**不写字面量**，改为 `from schema.stems import JSONL_STEMS; _TRUTH_STEMS = tuple(JSONL_STEMS)`（`conftest.py:89-91`）；`schema/stems.py` 把清单独立成**不依赖 pydantic** 的模块（省 conftest 每批 ≈1.2s 导入），并让 `schema/models.py` **在导入期断言** `JSONL_MODELS` 键集合与它相等 ⇒ 漂移即 `AssertionError`。**这正是我建议的 ①**，而且额外解决了"pydantic 拖慢最轻批次"这个我没提到的问题。
  - ❌ **没闭合的一半（我点名的 4 条登记层真源）**：该分支的 `_COPY_SKIP` 仍是 `{__pycache__, .pytest_cache, .venv, .work, index, reports, derived, .locks, state.json}` —— **不含 `registry`、不含 `audit`**；`_ENSURE_DIRS` 仍是 `(views, raw, derived, snapshots, index)` —— **不含 `facts`/`registry`/`audit`**；全树 `grep -n "REGISTRY_MODELS" system/ --include='*.py'` 在 **tests 侧零命中**，`_COPY_SKIP` 也**没有任何测试引用**（只有 `conftest.py:57/117` 自身）。⇒ **`registry/corporate-actions.jsonl`、`registry/quality-labels.jsonl`、`registry/idempotency.jsonl`、`audit/rule_changes.jsonl` 依然既不被清空、也不被排除、也不被断言覆盖。**
  - ⇒ **判定**：任务 #55 的交付范围是"**4 张事实表**（18→22）+ `_TRUTH_STEMS`↔注册表绑定"，与我说的"**4 条登记层真源**"是**两回事** —— 不是虚报，而是**范围错过**。**建议在 `ws/schema-expand` 合并前补上我建议的 ②**（一条断言即可：`(_COPY_SKIP ∪ set(_TRUTH_STEMS)) ⊇ {所有 JSONL_MODELS 与 REGISTRY_MODELS 的真源相对路径}`），否则 `G-RC-11` 在"18→22 扩表"落地后**仍然是敞着的**，而扩表恰恰是放大它的动作。

### G-RC-12 —— 夹具副本**不完整时静默继续**：`_ENSURE_DIRS` 不含 `facts/`/`registry/`/`audit/`，且 `_reset_truth_source` 用 `if facts.is_dir()` 静默跳过 【严重度：**中高**（未闭合的环境风险）】

- **位置**：`system/tests/conftest.py:62`（`_ENSURE_DIRS = ("views", "raw", "derived", "snapshots", "index")` —— **不含 `facts` / `registry` / `audit`**）、`:84-102`（`_reset_truth_source`：`if facts.is_dir(): …` / `if raw.is_dir(): …` —— **目录缺失即静默跳过，不报错不计次**）、`:147-164`（`code_root`：`copytree` → `_ENSURE_DIRS` → `_make_writable` → `_reset_truth_source`，**全程无一条"副本是否完整"的断言**）
- **实测（命令 + 输出）**：
  ```
  # 复刻 code_root 的三步，连做 30 次，逐次核对 6 个必备目录 + 18 个 facts stem + 3 个 registry 真源
  [5]  BAD  缺失 30 项: ['facts', 'raw', 'rules', 'registry', ...]
  [7]  BAD  缺失 30 项: [...]
  [12] BAD  [13] BAD  [21] BAD  [22] BAD  [27] BAD
  ==> 30 次中 7 次不完整
  stderr: [safe-delete][SAFE_DELETE_FAIL_CLOSED] {"target": ".../raw/inbox", "reason": "trash-failed",
          "detail": "FSPathMakeRefWithOptions failed (status -43)"}

  # 对照：同一脚本、同一 Python、只把宿主 broker 关掉
  ==> 10 次中 0 次不完整
  ```
- **为什么这是缺陷（与宿主无关的那一半）**：**代码侧没有任何"副本必须完整"的守卫**。`facts/` 不在 `_ENSURE_DIRS` 里（不会被补出来），`_reset_truth_source` 用 `is_dir()` 守卫（**缺了就跳过、不响**），`code_root` 也不断言。⇒ **一旦复制缺件，测试会以"`FileNotFoundError: .../facts/claims.jsonl`"或"某守卫 `exit=1`"的形式失败，而这两者看起来都像产品缺陷。** 这正是本项目自己的铁律 **V-07「测试失败必须先区分『产品坏了』与『夹具坏了』」** 要防的事，而当前夹具**没有能力**做这个区分。
- **可判定复现步骤**：见上框（脚本 `/tmp/investsigh-audit-b11/exp_fixture_integrity2.py`，逻辑即 `copytree(SYSTEM_ROOT, t, ignore=_ignore)` → `_ENSURE_DIRS` → `_make_writable` → `_reset_truth_source`，然后逐项核对 `_TRUTH_STEMS` + `registry/{corporate-actions,quality-labels,idempotency}.jsonl` + `audit/rule_changes.jsonl`；`N` 由 `sys.argv[1]` 给定）。
- **贡献向量（实测发现）**：`system/tests/probe-f177bb76/` 是**不受 `.gitignore` 忽略的非点号目录**（`git status` 显示 `?? system/tests/probe-f177bb76/`，**1.7 MB**，内含 `system/tests/probe-f177bb76/system/tests/probe-f177bb76/…` **5 层递归自嵌套**）。而 `_ignore()` 只排除 `_COPY_SKIP` 与**以 `.` 开头**的名字 ⇒ **这个目录会被原样复制进每一个夹具副本**，且在源目录里它把"待复制项数"抬高 —— 而宿主对**单轮批量删除**有阈值（`G-RC-09`：`threshold: 9999, scope: "turn"`）。⇒ 它**同时**加重"复制更可能缺件"与"清理更可能被拒"两件事。（`system/tests/.probe-step56/` 因以 `.` 开头**不会**进副本 — 见 `_ignore()` 的 `n.startswith(".")`。）
- **建议修法**：① `code_root` / `pristine_code_root` 在 `yield` 前加一条**响亮的完整性断言**（`for s in _TRUTH_STEMS: assert (target/"facts"/f"{s}.jsonl").exists()`，`registry`/`audit` 同理）—— 缺件时**报"夹具不完整"而不是报"产品坏了"**；② `_ENSURE_DIRS` 补 `facts`/`registry`/`audit`（或把它改为**从真源注册表派生**）；③ 清理 `probe-*` / `.probe-*` 之类实验残留，或把 `_ignore()` 改为按**前缀/白名单**排除（当前"非点号即复制"对在制品不设防）。

### G-50 —— `G-48` 收口后**残留一处与 `.gitignore` 逐字相反**的注释（`conftest.py:47-49`）【严重度：**低**，但形态与 `G-48` 同族】

- **背景**：实现方在 `2a8ca32` 采纳了我的 `G-48`（证伪"`derived/` 可由 `facts/ + method_version` 确定性重算"），但**按相反方向收口**：把 `derived/` **改回入库**（`.gitignore` 的忽略块整段移除、改写成"★ 关于 `system/derived/`：**它是真源，必须入库**（此结论经独立审计证伪后更正，缺口 `G-48`）…"）。这是需求方在两种正当收口之间的选择，**我接受**。
- **但残留了相反声明**：`system/tests/conftest.py:47-49` 至今写着 ——
  ```
  #   `derived` 已定为**非唯一真源**（见 `.gitignore` 的更正注释与
  #   `append_only_guard` 的 pathspec = `system/facts/*.jsonl`），
  #   故与 `index` / `reports` 同等待遇：**不复制**；`_ENSURE_DIRS` 会把空目录补回来。
  ```
  ⇒ 三处问题：① 它**引用的 `.gitignore` 现在说的正好相反**（"它是真源，必须入库"）；② 它把 `append_only_guard` 的 pathspec **当成"非真源"的证据** —— 而这**恰是提交信息里自己点名撤回的那个推理错误**（"把'守卫没覆盖'读成'该性质不成立'"）；③ 它对 `.gitignore` 的"更正注释"的**转述已过期**。
- **判定**：`_COPY_SKIP` 含 `derived` 这个**行为本身仍然正确**（夹具必须从**空真源**起步），错的只是**理由**。⇒ 无需改行为，**只需改注释**。
- **建议修法**：把 `:47-49` 改为"`derived` 是**真源**（`G-48` 更正），但夹具契约要求**空真源** ⇒ 与 `index`/`reports` **同等待遇：不复制**；`_ENSURE_DIRS` 补回空目录"。
- **★ 为什么仍要登记**：这已经是本项目**第三次**出现"同一件事两处相反声明"（`G-48` 的 `.gitignore` vs `store.py`；`G-42` 的裁定 R2 vs `ingest_step.py`；本轮这条）。**同一形态反复出现，说明缺的不是某一条注释，而是"改一处必须扫全仓同主题措辞"的机制。** 我在 §⑧ 第 3 条给了可判定的做法。

---

## ⑤ 对主理人可能自相矛盾之处的检查

| # | 可疑的自相矛盾 | 检查结果 |
|---|---|---|
| 1 | `4f95c3d` 既说"`produced` = 本轮真正新写入、命中走 `skipped`"，`ingest_step.py` 又把命中**计入 `produced`** | **坐实**（`ingest_step.py:242-249`）。同一个契约在同一批提交里**两个方向并存**。→ **G-42** |
| 2 | `4f95c3d` 说 `skipped` 用于"防幂等重跑被误标"，但只有 step 2 填 `skipped` | **坐实**（全仓库唯一赋值点 `chain_steps.py:132`；适配器包装的 step 5/6 从不填）⇒ 承诺**机器上不生效**。→ **G-44** |
| 3 | `fd49a20` 说豁免"不依赖任何关键词或名单，只依赖行序"，但 `_holds_valid_result` 依赖两个**从不被填**的字段 | **坐实**。行序只是**外层**条件，**内层谓词**恒 False ⇒ "修好了死代码"的同时引入了"恒误豁免"。→ **G-43** / **G-45** |
| 4 | `5a314a3`（`.gitignore`）说 `derived/` **非**唯一真源 vs `scripts/compute/store.py` 说它是"**追加式真源**"、"计算层**自有真源**" | **坐实**，逐字相反。→ **G-48** |
| 5 | `.gitignore` 说 `derived/` 可由 `facts/ + method_version` **确定性重算** | **证伪**（`contract.py:157` 取墙钟；`version` 不来自 `facts/`）。→ **G-48** |
| 6 | `23f78db` 的 docstring 说"`copytree` 复制的是**磁盘上的一切**（不只是 git 跟踪的东西）"⇒ 真源契约靠 `_reset_truth_source` 保证 | **部分不成立**：这条推理对 `state.json` / `derived` 成立，但**漏了 4 个登记层真源**（既不在 `_COPY_SKIP`，也不在 `_TRUTH_STEMS`）。→ **G-RC-11** |
| 7 | `bc26933` 说"把'绑定'从『接了』强化到『真的会拦』" | **三条绑定成立**（A/B 注入都被拦）✅；**但** `blocked_hint` 的语义仍无核对 ⇒ 强化只到"函数名 + id"层。→ **G-46** |
| 8 | `3f4c372` 说 `_stage_gate_verdict` 已"数据驱动、不再写死" | **成立**（两方向都查）✅；残留"同阶段同时 PASS+BLOCKED 静默取 PASS"的无歧义缺口。→ **G-47** |

---

## ⑥ 环境事实与审计过程说明（含我自己的失误，如实登记）

1. **`G-RC-09` 量化核对（我答应过要核）**：`165 tests collected` 与主理人给的用例数**一致**（实测 `pytest tests/injection --collect-only -q` → `165 tests collected`）。单副本项数我实测为 **286 项/副本（233 文件 + 53 目录）**（排除 `_COPY_SKIP` 后逐项枚举）。⇒ 165 × 286 ≈ **47,190 项删除**，远超宿主单轮阈值 **9999**。**主理人的 271 项/副本口径与我的 286 差 15 项**（可能因提交推进 / 是否计目录），但**量级与结论完全一致**：`verify.py --batch injection` 在单轮内**事实上跑不完**，越过阈值后单个用例目录也会被拒删 ⇒ `copytree setup` 报 E，**看起来像"测试坏了"**，**实测症状与我遇到的一致**。⇒ **你的量化：✅ 成立。**
2. **我自己犯的错，必须登记**：审计中我一度得到"`tests/injection` 多文件同会话 **6 failed**"、"两文件 **2 failed 1 error**"，症状是副本里 `facts/claims.jsonl` / `registry/quality-labels.jsonl` **凭空消失**。**根因是我自己违反了 `V-05`**：我起了后台 pytest 会话后又起前台会话，两者共用 `system/tests/.work/`，`pytest_sessionstart` 的 `_clear_work_dir()` **互删对方正在用的夹具副本**。证据：我随后被新落地的守卫拦住并给出处置 ——
   ```
   Exit: [V-05] 本工作树已有 pytest 会话在跑（pid=30713）… ⇒ 随机假红，且看起来像『守卫坏了』
   ```
   **单文件逐一跑全部通过**（`15 passed` / `13 passed` / `21 passed`）。⇒ **那些失败不是产品缺陷，是我的方法缺陷。**（该守卫的实现 `conftest._acquire_session_lock` 与 `tests/guards/test_session_lock.py` 在我审计时为**未提交的在制品**，**不在被审 11 个提交内**，故不作为交付结论；但我如实记录：它**修掉了我实际踩到的坑**，缺口登记为 `G-RC-10`。）
   - **独立旁证**：该修复随后合入为 **`d1efa1d`**（**在我被审范围之外**），其提交信息**独立复述了我上面这个诊断**——"`ps` 显示当时**至少 5 个 pytest 会话并发**，其中**两个在同一工作树**里跑 `tests/injection`…而 `conftest.pytest_sessionstart` **会整个清空同一个 `system/tests/.work/`** ⇒ **互删对方正在用的夹具副本**"。⇒ 我的结论与实现方的复核**互相印证**。
3. **一致性旁注（登记时**仍**成立，故登记为可判定缺陷，**不计入被审 11 个提交**）**：`CONVENTIONS.md:132`「V-05 **强制手段**：⚠️ **人工**（守卫无法可靠检测并发进程）」与 `:241` 表格行 `| V-05 | ⚠️ 人工（并发不可靠检测）；…`，**在 `d1efa1d` 落地后仍未被更新**（实测 `grep -n "V-05" system/CONVENTIONS.md` 仍是原文），而同提交已交付 `tests/guards/test_session_lock.py`（PID 存活检测 + 陈旧锁自愈 + 专用测试）⇒ **规范条文与实现相反**（此处方向是**代码强于文档**）。按本项目自己的铁律第 5 条（"声明与实现必须有机器绑定"），**建议由 `d1efa1d` 作者顺手把 V-05 的"强制手段"改为"机器 + `tests/guards/test_session_lock.py`"**。★ **该条已闭合**：`2a8ca32` 已把 `CONVENTIONS.md:257` 改为"**人工（动测前 `ps`）+ 机器（`tests/.work/.session.lock` 排他会话锁，`returncode=4`）**"，我在收口前复验通过（见 §⑧ 第 4 条）。
4. **我的实验目录被外部清空**：审计中途 `system/tests/.audit-b11/` 下除我**刚写的一个文件**外的全部内容（`base/`、全部 `case-*/`、全部 `exp_*.py`）被**外部清空**（目录 mtime 20:06–20:07）。我**没有**任何脚本会删这个目录（我的脚本只删自己创建的 `case-*/probe-*` 子目录）。**为不引用"记忆里的数字"，我把关键结论（A1 击穿、B1 绕过、B3 新旧对比）在本轮用重建的脚本 + `git show 4f95c3d:…` **全部重跑了一遍**，报告中的数字**全部来自本轮的实测输出**。顺带确认：`.audit-b11` 以 `.` 开头 ⇒ 被 `_ignore()` 排除，**从未**污染夹具副本。
5. **审计纪律**：未修改任何被审文件（`git status` 中被审范围内的文件无我的改动）；真仓库真源未被我触碰 —— 实测 `git status --porcelain system/registry system/audit system/facts system/state.json` **为空**；`system/derived/` 下唯一一条 `?? system/derived/compute_gaps.jsonl` 是**他人**跑 `run_daily` 落下的（见下第 7 条），**非我所为**（我的全部实验在副本内进行）。我自己的实验目录**全部在仓库之外**（`system/tests/.audit-b11/` 与 `/tmp/investsigh-audit-b11/`），**其中 `.audit-b11` 以 `.` 开头、被 `_ignore()` 排除，从未污染夹具副本**；该目录我在定稿前**移出仓库**（`mv system/tests/.audit-b11/* /tmp/investsigh-audit-b11/`，随后 `rmdir`），现 `git status` 中由我新增的文件**只有本报告**。
6. **★ 定稿前新增的两条实测（本轮会话内，非引用记忆）**：
   - **A1 在当前 HEAD 上重跑仍成立**：违例 `6 → 0`；且**"要求 skipped 的 id 真实存在于真源"这一加强方案也不闭合**（见 §② A 组 A1 行与 `G-42` 修法）。
   - **`G-RC-12`（夹具副本静默不完整）**：broker 开启 30 次 **7 次**缺件 / broker 关闭 10 次 **0 次**缺件；**代码侧无完整性断言**。⇒ 我因此**撤回**本报告初稿里"E 附：夹具副本稳定完整 —— 未证伪"这条（§③ 第 4 条已改写）。
7. **范围外的环境事实（不作为交付结论，仅供主理人排期参考）**：
   - `main` 在被审范围外继续推进：`1c35154 → d1efa1d → c2933c3 → d5a37f8`（`git reflog` 实测）。
   - **`G-44` 已被在制品覆盖**：`git branch` 显示存在分支 **`ws/step56-skipped`**，且定稿瞬间 `git status` 有 `M system/scripts/orchestrate/pipeline.py`、`M system/scripts/ops/verify.py`、`M system/CONVENTIONS.md`（**均为他人正在编辑的文件，我一个字未改**）。⇒ 我对 `G-44` 的结论**只对 `790643c` 那一刻的 `chain_steps.py` / `compute/step.py` / `decision/step.py` 成立**；若 `ws/step56-skipped` 已让计算层/决策层按裁定 R2 回填 `skipped`，请以该分支的实测输出为准，并把本条按"已闭合 / 未闭合"在台账上更新。
   - **真仓库出现一条新的未跟踪产物**：`?? system/derived/compute_gaps.jsonl`（他人跑的 `run_daily` 落下的）。⇒ 说明 **`derived/` 在真仓库里是"活的"**：它现在有内容，而它**不在** `_reset_truth_source` 的清空清单里 —— 好在 `_COPY_SKIP` 已含 `derived`，夹具因此不受影响。**这一条我在 `G-48` 收口后已复核为"已闭合"**（详见 §⑧ 第 3 条）。

---

## ⑦ 结论（五档）

| 交付 | 档位 |
|---|---|
| `4f95c3d` `skipped` 字段与 `G1-05` | **不够**（字段是自报、无校验；step 1 口径反向 ⇒ 判据在一半的步上恒假）→ ★ **`G-42` 已按"如实降格 + 加互斥校验"收口，我复验：互斥校验生效、原攻击仍成立（残余已由实现方声明）** —— 见 §⑧ 第 1 条 |
| `790643c` step 2 接线 | **好**（判别式成立，我三连跑复现） |
| `fd49a20` 首日豁免 | **不够**（死代码修好了，谓词却恒误豁免；计数可见但含义不可信） |
| `5a314a3` `derived/` 归属 | **错**（"真源/非真源"两套声明逐字共存；"可重算"理由实测不成立）→ ★ **该结论已被实现方采纳并按相反方向收口**（`derived/` 改回入库），我复验后**判定为"已闭合（残留一处注释未清，见 `G-50`）"** —— 见 §⑧ 第 3 条 |
| `23f78db` 夹具不继承 `state.json` | **好**（就该文件而言）／**不够**（同族 4 个登记层真源未覆盖、无机器绑定；副本完整性**无断言** ⇒ 缺件时静默继续） |
| `3f4c372` `_stage_gate_verdict` | **不够**（方向检测成立；缺无歧义检查）→ ★ **`G-47` 已修，我复验生效**（见 §⑧ 第 2 条） |
| `bc26933` 判据有效性门禁 | **好**（三条绑定实测拦得住）／**不够**（`blocked_hint` 无语义核对） |
| `016f311` 缺口登记 | **好**（`G9-1` 可独立复现，输出逐字一致） |

**给主理人的一句话**：本批次**有真修实**（step 2 的判别力、判据有效性门禁的两向绑定），但 `G-42` / `G-43` / `G-44` 三条都属于**同一形态**——"**判据/字段有了，但校验它的那一侧没有接上**"，因此三个关键守卫**当前都能被机器证明失效**（`G1-05` 6→0；首日豁免真违规被放过；第二次 `run_daily` 恒 `blocked`）。这三条**建议按"高"优先级进下一批**，`G-44` 尤其紧急——它意味着**生产上第二次跑 `run_daily` 就会 `blocked`**。

**还有一条必须单独说的（`G-RC-12`）**：`G-42`/`G-43`/`G-44` 的结论**全部依赖"夹具副本是真的"**。而我实测：broker 开启时 30 次夹具构造里 **7 次静默缺件**（缺 `facts/`/`registry/`/`audit/` 等约 30 项，`copytree` **不抛异常**），broker 关闭时 10 次 0 次缺件；**代码侧没有任何"副本必须完整"的断言**（`facts` 不在 `_ENSURE_DIRS`，`_reset_truth_source` 用 `if facts.is_dir()` 静默跳过）。⇒ 请把"**夹具缺件 ⇒ 报『夹具不完整』而不是报『产品坏了』**"当作**独立一条**排期：否则本批次我与前几批审计员**都可能在读一份被悄悄改了输入的实验**，而每一次这样的失败都会被记成产品缺陷。

---

## ⑧ 审计后复核：实现方 `2a8ca32` 的收口，我**不采信提交信息**、逐条在机器上复验

> **为什么单开一节**：本报告定稿时发现实现方已把本报告作为交付物入库（`2a8ca32`），并在同一提交里宣称处置了 `G-42` / `G-47` / `G-48` / `V-05`。按 `§九`（**实现方不得自证完成**），**提交信息不是证据**。我用当前 HEAD 的 `system/` 副本重跑了五组输入（脚本 `/tmp/investsigh-audit-b11/exp_recheck_fixes.py`，`exit=0`）。

| # | 实现方宣称 | 我的独立复验 | 判定 |
|---|---|---|---|
| 1 | `G-42`：新增 `produced ∩ skipped ≠ ∅` 互斥校验；并把"判据强度未削弱"改为**如实降格**（"自报式不变量兜底，不能抓蓄意伪造"） | **互斥校验真的生效**：<br>`produced=['x-1'] skipped=['x-1'] → 违例 6 条`（报"第 1 步…的 produced 与 skipped **相交**：['x-1']"）<br>`produced=[x-1,x-2] skipped=[x-2,x-3] → 违例 6 条`（**部分相交也拦得住**）<br>`produced=['x-1'] skipped=['y-1'] → 违例 0 条`（**无误伤**）<br>**原攻击仍成立**：`produced=[] skipped=['claim-我瞎编的-不存在于真源'] → 违例 0 条`<br>**反向对照仍成立**：`produced=[] skipped=[] → 违例 6 条`（空执行照样被拦） | ✅ **修复生效、且残余已如实登记** ⇒ 按我现在掌握的信息，`G-42` 可判为**"已按可接受方式收口"**（不再要求它"闭合"—— 我在 §④ 已证明 `skipped` 方向**不可能** in-band 闭合）。 |
| 1-附 | 未修 `skipped` 存在性核对，理由是"`assert_steps_complete` 拿不到 `root`…要加需改共享签名，不在本次自裁范围" | **这条理由比真实理由弱，且未穷尽替代方案**：① **真实理由是**"**存在性 ≠ 归属性**"—— 我已实测：把 `skipped` 填成真源里**真实存在**的 id，违例同样 `6 → 0` ⇒ **即便拿得到 `root`，这条核对也不闭合**；② 替代方案确实存在且**不破坏共享签名**：给 `assert_steps_complete(result, registered_hooks, *, root: Path \| None = None)` 加**可选 kwarg**（调用点只有 `pipeline.py` 自身的 2 处 + 测试），默认 `None` 时行为逐字不变。 | ⚠️ **请实现方把理由改成真实理由**（避免下一位读者以为"改个签名就能闭合"而白做一轮）。**但结论不因此改变**：`G-42` 的残余**只能靠换人审计 + 读代码**，这一点实现方写对了。 |
| 2 | `G-47`：`_stage_gate_verdict` 歧义即响亮失败 | **五组输入实测**：<br>`② 有 BLOCKED + exit 1` → `ok=True`（合规，正确通过）<br>`③ 同阶段 daily_run 同时 PASS+BLOCKED + exit 0` → `ok=False  why=…**同时**出现…判据不自洽，无法据以判定（**不得静默取其一**，尤其不得取 PASS）` ← **原实现此处静默取 PASS，已堵住**<br>`④ 缺一个阶段` → `ok=False  why=以下阶段既未标 PASS 也未标 BLOCKED（可能静默跳过）：['daily_run']`<br>`⑤ 全 BLOCKED + exit 0` → `ok=False  why=存在阻塞阶段 … 却 exit=0 —— 疑似把阻塞阶段判成通过` | ✅ **生效**（我上面第 ① 组输入是我自己构造有误——`head.replace()` 漏造了 `daily_run`，与代码无关，如实登记）。 |
| 3 | `G-48`：采纳我的证伪，但**按相反方向**收口 —— `derived/` **改回入库**（`.gitignore` 的忽略块整段删除） | 实测：`git ls-files system/derived` → `system/derived/.gitkeep`、`system/derived/compute_gaps.jsonl`（**已跟踪**）；`.gitignore` 的新注释**逐字引用了我的三条论据**并写明"该前提是错的，已撤回"，且**明确不把 `append_only_guard` 的覆盖缺口当作"非真源"的证据**（这正是它自己上次的推理错误）。<br>**夹具侧一致性我单独查了**：`_COPY_SKIP` 仍含 `derived`（**行为正确** —— 夹具契约是"空真源"）；`_reset_truth_source` 不清 derived stem，但因不复制故副本里必为空 ⇒ **`G-RC-11` 同族缺口在 `derived/` 上恰好不成立**。 | ✅ **收口有效，我接受这个方向**（在"改 `store.py` 措辞"与"`derived/` 入库"之间选后者是需求方权限）。⚠️ **但残留一处相反注释** → **`G-50`**（`conftest.py:47-49` 仍写"`derived` 已定为**非唯一真源**（见 `.gitignore` 的更正注释…）"，而 `.gitignore` 现在说的正好相反）。 |
| 4 | `V-05` 规范已从"⚠️ 人工"同步为"人工 + 机器" | 实测 `grep -n "V-05" system/CONVENTIONS.md` → `:257 \| V-05 \| **人工（动测前 ps）+ 机器（tests/.work/.session.lock 排他会话锁，returncode=4，见 G-RC-10）**；留档由 verify.py 自动完成 \|` | ✅ **已同步**（原为"⚠️ 人工（守卫无法可靠检测并发进程）"）⇒ 我在 §⑥ 第 3 条登记的"规范与实现相反"**已闭合**。 |

**3-附：一条机制建议（对 §④ `G-50` 收尾）** —— 本轮已第三次出现"同一件事两处相反声明"。建议加一条**可判定**的收口动作，而不是靠人记得：**凡修改某条声明的提交，必须在提交信息里列出 `grep -rn "<被改措辞>" system/` 的全部命中并逐条说明"已同步 / 不适用"**。这不需要新守卫（人类可读即可判定），但能让 `G-48`/`G-50` 这类"改了一半"在**提交那一刻**就暴露，而不是等下一轮审计。
