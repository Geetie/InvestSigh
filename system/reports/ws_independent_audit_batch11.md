# 批次 11 · 独立审计报告（`auditor-batch11`）

- **审计对象**：`main` 分支 `f0d9ee2..016f311` 共 **11 个提交**（原派单 8 个 `f0d9ee2..23f78db` + 追加 3 个 `3f4c372` / `bc26933` / `016f311`）
- **实现方**：主理人本人（含 `ws/idempotency` / `ws/evidence-fix` / `ws/criterion-effectiveness` 三条合并流）
- **依据**：`system/CONVENTIONS.md §九`（实现方不得自证完成）
- **审计员立场**：**尽力证伪**。凡我构造过用例但**未能**推翻的，逐条明说"我试了 X、Y，未推翻"。
- **审计时 HEAD**：审计开始为 `1c35154`，主体收尾时为 **`d1efa1d`**；**报告定稿时 `main` 已推进到 `d5a37f8`**（`git reflog` 实测：`d5a37f8 ← c2933c3 ← d1efa1d ← 1c35154`）。三者**均已超出被审范围**。本报告只对被审的 11 个提交下结论；范围外的改动只在 §⑥ 以"环境事实"登记，不作为交付结论。
- **基线对齐（口径 10：报"当前态"必须带【对象 + 取样时刻】）**：
  - 本报告**全部结论的对象 = `f0d9ee2..016f311` 这 11 个提交**；§⑧ 的复核对象 = `2a8ca32`；**§⑨ 的复核对象 = `main@e9a009b`（工作树那份 `system/`），取样时刻 2026-09-16 23:1x CST**；**§⑩ 的对象 = `main@2f62f5d` 的 `system/reports/`（67 份），取样时刻 23:3x–23:5x**；**§⑪ 的对象 = 工作树 `main@1dd87f3a24af9d3d34528b8f455dee2c39b46842`，取样时刻 `2026-09-16 23:38:57 CST`**；**§⑮ 的对象 = 工作树 `main@af20ebc83dc1798d5c4dec738b64ccece23bfd3a`，取样时刻 `2026-09-17 00:08:21–00:2x CST`**；§⑥ 第 7 条与 `G-RC-11` 末尾复核的对象分别在各自条目标注。
  - **`main` 稳态基线（我独立核验，非引用广播）**：对象 `69e0090`，取样时刻 **2026-09-16 22:44:57 +0800**。实测四项：`HEAD = 69e0090` ✅ · `.git/MERGE_HEAD` **不存在** ✅ · `git status --short` **0 项** ✅ · `G-61` 两要件均在 main（`cat-file -e HEAD:system/scripts/checks/scenario_tag_binding_guard.py` 命中 + `pre-commit.sh` 命中 1 处）✅。
  - ⇒ **凡本报告中读到的 `git status` / `HEAD` 数字，一律以该时刻为界**；此后 `main` 继续推进属正常，不构成本报告任何结论的变更。
- **定稿前复验（在本轮会话内重跑，非引用记忆）**：`G-42`（A1 击穿）在**当前 HEAD 的副本上重跑仍成立**（违例 6 → 0）；并新增一条 `G-RC-12`（夹具副本不完整时**静默继续**）。见 §③ 第 4 条与 §⑥ 第 6–7 条。
- **★ 最新一轮（按 team-lead 裁决顺序执行）**：**§⑩** = "grep 依赖型结论全量重证"（裁决第 2 项，10 条载荷逐条两引擎复算，**2 条判假零/归因错**）；**§⑪** = `G-44` 端到端**独立**复验（裁决第 1 项）—— 判定 `G-44` 修复**【好】**（5 场景 × 9 断言全绿，含 3 条我自造的对抗输入），并**附带掉出两条新发现**（官方正例的 step 6 半边前提是 schema 判非法的行；`run_decide.py:462-463` 承诺的降级分支不可达）。**§⑫** = 批次 14（裁决第 3 项）：`stage_gate` **5 条已绑定判据**的"注入违例⇒变红 + 合法态⇒仍绿 + **掏空⇒反例失效**"三段实测 —— **5 格全过**（第 4 格 `task_state_auditable` 能做完整 `exit 0/1/0` 三段对照），附新发现 `G-67` 与**对我接到的范围描述的一处机器更正**（`nvidia_sample` 是 **3 已绑 + 1 未绑**，不是四条）；**§⑬** = `#69` **四条命令重跑**（裁决第 4 项）—— 旧读数**整体漂移、方向全是"已修"**（`rc=1`→`rc=0` 等），据此把 `ws_ch2_rules_consumption_review.md §12.2(b)(d)` **按 `V-11` 降级为历史态**；**§⑭** = `ws/verify-shard` 在当前 HEAD **重判**（结构不变量 ✅ 好）+ **悬挂引用逐条排除**（22/22 在 main，**并已按独立路径 `git ls-tree` 扩面复算到 85 条**）+ `x13r` 明写**未验收、不予举证**。**§⑮** = 按 `V-11` **规矩 9** 的**引用级自审**（`main@af20ebc`，`2026-09-17 00:0x–00:2x CST`）—— 97 条引用的**存在性**全过，但**手检语义**发现 **6 条行号引用已漂移**（根因 `bd66025`：**修 `G-64` 的那条提交把我 §⑨ 的引用改位了**），其中 `degrade.py:130` 现落在**别的函数**的 docstring 上；★ 并据此指出 **`#105` 派单原文的 `degrade.py:136` 会引导出方向错误的修复**（在 HEAD 它指向**已经正确的那一半**），给出符号锚点。另如实登记我自己的**五处仪器错误**（路径型假零、掏空副本复用、neuter 相位喂错输入、扫描器前缀拼错、★ **zsh 的 `$var:m` 修饰符静默吃掉 `git` 对象路径** —— 后者会使 `git cat-file -e $sha:path` **恒 rc=0**）。
- **纪律遵守声明**：全程**未修改任何被审文件**；一切实验在副本（仓库外的 `/tmp/investsigh-audit-b11/`，以及该目录在仓库内的旧位置 `system/tests/.audit-b11/`）中进行。
  ★ **"真源未被我触碰"的可核对表述（含时点，避免被后来的他人改动误读）**：
  - 审计期间（2026-09-16）实测 `git status --porcelain system/registry system/audit system/facts system/state.json` 为**空**。
  - **交付后该状态会变** —— 例如 `ws-real-collect-2` 会把真实采集结果落库（实测出现 `M system/facts/claims.jsonl`、`M system/facts/sources.jsonl`、`A system/raw/2026-*.txt`，且与 `A system/scripts/ingest/public_fetcher.py`、`A system/reports/ws_real_collect_2_report.md` 同批）—— **那些不是我的改动**，属另一条流的正常交付。
  - **判断依据（不依赖我的自述）**：我在整份报告中只产出 `system/reports/ws_independent_audit_batch11.md` **一个**文件；我没有任何脚本写 `facts/`、`registry/`、`audit/`、`state.json`（我的脚本只在自己的副本目录下 `copytree`/`rmtree`）。

---

## ① 总评

| # | 被审主张（批次 11 的核心交付） | 判定 |
|---|---|---|
| 1 | `StepOutcome.skipped` 字段 + `G1-05` 判据改为 `not produced and not skipped`（`4f95c3d`） | **不够** |
| 2 | `produced` / `skipped` 语义切分（裁定 R2）在 step 2 真的接上了（`790643c`） | **好**（step 2）／**不够**（step 5/6 反被这一改动搞坏） |
| 3 | `stage_gate` 首日豁免从"死代码"改为"追加序判定"（`fd49a20`） | **不够**（修好了"恒为 0"，但豁免条件与真实 `Task` 形状不匹配 ⇒ 转向"恒误豁免"）→ ★ **`abbe7b3` 已收口，我独立复现：六条正向主张全部成立、我的原始反例被拦住** ⇒ 判为**主体已闭合**；但同一修复**只覆盖"字段为空"一种形态**、**只枚举了合法空产出的一个态** ⇒ 我继续证伪出 **`G-63`**（引用可伪造/悬空，中高）与 **`G-64`**（**降级日被误判"空执行"**，**高**）—— 见 §⑨ |
| 4 | `derived/` 纠正为"非唯一真源"（`5a314a3`） | **错**（同一提交范围内存在逐字相反的两套声明；且"可重算"的理由不成立） |
| 5 | 夹具不再继承运行态 `state.json`（`23f78db`） | **好**（就 `state.json` 而言；且已补**机制层断言**防用例空转）／**不够**（同族缺陷尚有 **4 个登记层真源**未覆盖、**无机器绑定**；且**副本不完整时静默继续**，无任何完整性断言 —— `G-RC-11` / `G-RC-12`） |
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
| B2 `_holds_valid_result()` 的两载体已穷尽 | ❌ **证伪成功** | `Task` 模型（`schema/models.py:953`）确实只有 `last_valid_result_ref` / `output_refs` 两个载体——**载体是穷尽的**；但**全仓库 `output_refs=` 零个生产赋值点**（`grep -rn "output_refs=" system/scripts/` 只命中测试）⇒ 两个载体在真实 `run_daily` 里**恒为空** ⇒ 谓词**恒 False**。语义上"载具穷尽 ≠ 判定有效"。见 **G-43** / **G-45**。<br>★★ **本节结论已被后续复核更新（就地更正，避免"改了一半"——`G-50` 同族）**：对象 `main@2f62f5d`（2026-09-16 23:3x）实测 `pipeline.py:415 output_refs=produced if valid_run else []` ⇒ **"零个生产赋值点"已不成立**（该断言的真源现为 1 个，见 §⑩ 第 2 条）。**当时的证伪有效**（对 `fd49a20` 那一刻成立），但**不得再作为当前态引用**。 |
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
| `bc26933` 的 `blocked_hint` 是否也有语义级核对 | ❌ **未做** | `grep -rn "blocked_hint" system/` 只命中 `criterion_effectiveness_guard.py` 的 **`:25`（门禁规则表）与 `:218`（**仅非空字符串校验**）** 与测试文件的 docstring/一处 `"blocked_hint": "x"` 注入。`registry/criterion_counterexamples.yaml` 的 **15 条** `blocked_hint` **值本身没有任何机械核对**（没有遍历登记表逐条核对"该提示串在输出中出现 / 不出现"的元测试）。⇒ 与 `4f95c3d` 的**伪造 `skipped`** 是**同一族**缺陷（"登记了文字、没人核对文字"）。见 **G-46**。<br>★ **本节两处读数已在 §⑩ 就地更正**（我原先写 `:204`、**11 条**）：行号实为 `:25`/`:218`，条数实为 **15**，且**另有第三个落点** `scripts/valuelayer/completeness.py:1133`（注释自称该短语"**专属**于 `chapter4_g_depth`"，却无任何断言绑定 —— 结论方向不变、**更强**）。 |

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

> 编号约定沿用 `reports/phase1_gap_register.md`（当时已用到 `G-41` / `G-RC-10`），本报告使用 `G-42` ~ `G-48` / `G-RC-11` / `G-RC-12`。
> **追加编号（§⑨，对象 `main@e9a009b`，2026-09-16 23:1x）**：**`G-63`**（`degrade_keeps_last_valid` 只判真值性 ⇒ 引用可伪造/悬空）、**`G-64`**（`is_no_change_day()` 漏了"降级"这第二个合法空产出态 ⇒ 降级日被误判"空执行"）。编号落在 `G-62` 之后以避免与他人冲突；若 `G-49`~`G-62` 已有他人占用，请以台账实际分配为准。
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
- **另一条**：`Task`（`schema/models.py:953`）只有 `last_valid_result_ref` / `output_refs` 两个载体（**载具穷尽**这一点我确认了），但**全仓库 `output_refs=` 零个生产赋值点**（只出现在测试里）⇒ 两个"穷尽"的载体在真实运行中**都是空的**。<br>★★ **就地更正（对象 `main@2f62f5d`，2026-09-16 23:3x）**：`pipeline.py:415 output_refs=produced if valid_run else []` 已是**生产赋值点** ⇒ **"零个"已不成立**；`last_valid_result_ref` 亦在 `:416` 被生产填写。本条作为**当前态断言作废**（作为"`fd49a20` 那一刻"的历史态仍然成立），详见 §⑨ 第一节与 §⑩ 第 2 条。
- **为什么是缺陷**：`G1-04`（`gap_to_task.py`）对同一行判 `exit 1` FATAL（"空执行"），`stage_gate` 却判"不持有有效结果" ⇒ **同一行、两个守卫、相反结论**。这正是"声明与实现脱节"的跨模块版本。
- **建议修法**：把"上次有效结果"的判定**收口到唯一一处**（`scripts/daily/degrade.py`），`stage_gate` 改为调用它；并补一条**反向对照测试**（`output_refs` 空 / 非空两态必须给出可区分结论）。
- ★★ **本条已由 `abbe7b3 fix(degrade): 修 G-43/G-45` 收口，我在 `main@e9a009b` 上独立复现（不采信提交信息）：三处主张全部成立** —— ① `stage_gate._holds_valid_result` 的**定义已删净**（全文件只剩 `:539` 一处注释），改 `:546 from scripts.daily.degrade import holds_valid_result`（调用点 `:601`/`:612`）⇒ **口径收口到唯一真源**；② 写路径补齐：`pipeline.py:415 output_refs=produced if valid_run else []`、`:416 last_valid_result_ref=None if valid_run else last_ref` ⇒ **我"零生产赋值点 / 两载体恒为空"两条均不再成立**；③ 我 `B1-c1` 的原始反例形状（`[done + output_refs=[] + ref=null, failed]`）**现在拦得住**（实测 `exit=1`，命中"失败但未保留 `last_valid_result_ref`"）⇒ 见 **§⑨ 第一节**。
- ⚠️ **但同一节里我又证伪出两条**（**本条的修复只覆盖了"字段为空"这一种失败形态**）：**`G-63`**（引用只判真值性 ⇒ 可伪造/悬空，同族于 `G-42`）与 **`G-64`**（`is_no_change_day()` 漏了"降级"这第二个合法空产出态 ⇒ 降级日被误判"空执行"，**高**）—— 见 **§⑨ 第二节**。

### G-46 —— 判据登记表的 `blocked_hint` 无机器核对（`bc26933` 的缺口） 【严重度：中】

- **证据**：`grep -rn "blocked_hint" system/` 只命中 `criterion_effectiveness_guard.py` 的 **`:25`（门禁规则表）与 `:218`（仅非空）**、测试文件、以及 **`scripts/valuelayer/completeness.py:1133`（第三处，注释自称该短语"专属"于 `chapter4_g_depth`）**。`registry/criterion_counterexamples.yaml` 的 **15 条** `blocked_hint` 值**无任何机械核对**（没有遍历登记表、逐条检查该提示在命中/未命中两种输入下出现/不出现的元测试）。
- ★ **本节读数已在 §⑩ 就地更正（我自己先前的两处错）**：行号原写 `:204`（实为 `:25`/`:218`）、条数原写 **11**（实为 **15**）。**结论方向不变且更强**（15 条无核对 + 第三个自称"专属"却无绑定的落点）。
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
- ★★ **再次复核（2026-09-16 23:1x CST，对象 = `main@e9a009b` 工作树那份 `system/`，非 worktree）**：这条现在是**半闭合**，方向对但**恰好还是漏掉我点名的那个 case**。
  - ✅ **facts 侧已闭合**：`conftest.py:102-104` 已是 `from schema.stems import JSONL_STEMS` / `_TRUTH_STEMS: tuple[str, ...] = tuple(JSONL_STEMS)`（**不写字面量**）；`tests/unit/test_schema_expand.py:369-382` 四条绑定断言齐备（`set(_TRUTH_STEMS)==set(JSONL_STEMS)`、`==set(M.JSONL_MODELS)`、无重复、`_TRUTH_STEMS == JSONL_STEMS`）。⇒ 我原文"全仓库没有任何断言把两者绑起来"**已不成立（已闭合）**，建议 ① **已落地**。
  - ✅ **`_COPY_SKIP` 现有机制层断言，但只覆盖一个条目**：`tests/injection/test_wiring_guards.py:165-167` `assert "state.json" in _COPY_SKIP`，注释明写"防本用例因真仓库恰好没有该文件而变成**空转**" ⇒ **形态正确**（正是我建议的写法，`G-03` 同源）。我原文"`_COPY_SKIP` 也**没有任何测试引用**"**已不成立（已闭合）**。
  - ❌ **登记层那一半仍敞着（实测量，非引用）**：`conftest.py:70-73 _COPY_SKIP = {__pycache__, .pytest_cache, .venv, .work, index, reports, derived, .locks, state.json, raw}` —— **不含 `registry`、不含 `audit`**；`:104` 的 `_TRUTH_STEMS` 仍**全在 `facts/`**；tests 侧对 `REGISTRY_MODELS` 的引用**只在** `test_wiring_guards.py:38/39/98`（判 guard **源码接线** + `REGISTRY_GUARD` 的 `rule_hint`），**没有任何一条**断言 `(_COPY_SKIP ∪ _TRUTH_STEMS) ⊇ REGISTRY_MODELS 的真源`。
  - ⇒ `registry/corporate-actions.jsonl`、`registry/quality-labels.jsonl`、`registry/idempotency.jsonl`、`audit/rule_changes.jsonl` **依然既不被清空、也不被排除、也不被断言覆盖**。**建议把建议 ② 作为独立一条排期**（`REGISTRY_MODELS` 里已有 `registry_model_for`，取相对路径不需要新真源）。

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
- **★ 与 `G-60`（`ws-ch2-rules` 的独立实测）的关系 —— 同一个宿主闸门、两种拒绝形态**（我**不**声称因果已证，只登记为**待闭合的假设**）：
  | | 我的 `G-RC-12` 观测 | `G-60` 观测（`ws/ch2-rules` 的树，22:32） |
  |---|---|---|
  | 宿主消息 | `SAFE_DELETE_FAIL_CLOSED` + `trash-failed` + `FSPathMakeRefWithOptions failed (status -43)` | `SAFE_DELETE_BULK_CONFIRM_REQUIRED` `{"count":100267,"threshold":99999,"scope":"turn","targetCount":1}` |
  | 后果 | `copytree` **静默**少拷（30 次里 7 次，各缺约 30 项） | 连**删 1 项**都被拒 ⇒ `_clear_work_dir()` 必失败 ⇒ 需夹具的用例集体 `ERROR` |
  | 我实测到其**代码级放大器** | `_ENSURE_DIRS` 不含 `facts`/`registry`/`audit`；`_reset_truth_source` 用 `if facts.is_dir()` 静默跳过；`code_root` 无完整性断言 | `pytest_sessionstart` 的 `_clear_work_dir()` 无降级路径 |
  - **共同点（这才是关键）**：**两者的失败都不会被代码侧识别** —— 一个静默少文件、一个直接 `E`，但**都没有任何一处说"是宿主闸门拒了我，不是产品坏了"**。⇒ `G-RC-12` 与 `G-60` **应合并排期**：`_clear_work_dir()` 改**逐文件删除**（`ws-ch2-rules` 提议的方向）能同时压掉两侧的量级；再加一条**夹具完整性断言**即可把"静默少文件"变成响亮报错。
  - ⚠️ **我保留的不确定项（如实写）**：我这 7 次的缺件发生在**复制**阶段（每轮用新 uuid 目录、`rmtree` 在其后），而**复制侧为何会少拷，我没有证明其机制**（`copytree` 未抛异常）。⇒ 登记为**假设**："宿主闸门处于 fail-closed 时，同一轮内的文件系统操作会**静默部分失败**"。**闭合它需要一条直接的因果实验**（在闸门被拒的状态下反复 `copytree` 并逐次比对），这一条我**没做成**（重测时进程被宿主 SIGKILL，见下）。
- **为什么这是缺陷（与宿主无关的那一半）**：**代码侧没有任何"副本必须完整"的守卫**。`facts/` 不在 `_ENSURE_DIRS` 里（不会被补出来），`_reset_truth_source` 用 `is_dir()` 守卫（**缺了就跳过、不响**），`code_root` 也不断言。⇒ **一旦复制缺件，测试会以"`FileNotFoundError: .../facts/claims.jsonl`"或"某守卫 `exit=1`"的形式失败，而这两者看起来都像产品缺陷。** 这正是本项目自己的铁律 **V-07「测试失败必须先区分『产品坏了』与『夹具坏了』」** 要防的事，而当前夹具**没有能力**做这个区分。
- **可判定复现步骤**：见上框（脚本 `/tmp/investsigh-audit-b11/exp_fixture_integrity2.py`，逻辑即 `copytree(SYSTEM_ROOT, t, ignore=_ignore)` → `_ENSURE_DIRS` → `_make_writable` → `_reset_truth_source`，然后逐项核对 `_TRUTH_STEMS` + `registry/{corporate-actions,quality-labels,idempotency}.jsonl` + `audit/rule_changes.jsonl`；`N` 由 `sys.argv[1]` 给定）。
- **贡献向量（实测发现）**：`system/tests/probe-f177bb76/` 是**不受 `.gitignore` 忽略的非点号目录**（`git status` 显示 `?? system/tests/probe-f177bb76/`，**1.7 MB**，内含 `system/tests/probe-f177bb76/system/tests/probe-f177bb76/…` **5 层递归自嵌套**）。而 `_ignore()` 只排除 `_COPY_SKIP` 与**以 `.` 开头**的名字 ⇒ **这个目录会被原样复制进每一个夹具副本**，且在源目录里它把"待复制项数"抬高 —— 而宿主对**单轮批量删除**有阈值（`G-RC-09`：`threshold: 9999, scope: "turn"`）。⇒ 它**同时**加重"复制更可能缺件"与"清理更可能被拒"两件事。（`system/tests/.probe-step56/` 因以 `.` 开头**不会**进副本 — 见 `_ignore()` 的 `n.startswith(".")`。）
- **建议修法**：① `code_root` / `pristine_code_root` 在 `yield` 前加一条**响亮的完整性断言**（`for s in _TRUTH_STEMS: assert (target/"facts"/f"{s}.jsonl").exists()`，`registry`/`audit` 同理）—— 缺件时**报"夹具不完整"而不是报"产品坏了"**；② `_ENSURE_DIRS` 补 `facts`/`registry`/`audit`（或把它改为**从真源注册表派生**）；③ 清理 `probe-*` / `.probe-*` 之类实验残留，或把 `_ignore()` 改为按**前缀/白名单**排除（当前"非点号即复制"对在制品不设防）。
- ★ **④ 补一条断言（这条是 `ws-ch2-rules` 补的，我原来的方案不够，如实归他）——"清空有效性"**：
  我原来的①只能抓**缺件**。但 `G-60` 的实测形态是 **`SAFE_DELETE_BULK_CONFIRM_REQUIRED {"count":100267,"threshold":99999,"scope":"turn","targetCount":1}`** —— **`count` 越顶后连删 1 项也被拒**，于是 `pytest_sessionstart` 的 `_clear_work_dir()` 必失败。**这个形态下文件仍然在**（只是陈旧/不干净）⇒ **①抓不到**。
  - ⇒ 必须再加一条：**sessionstart 之后断言工作目录确实为空**。否则观测上「**0 个文件被删**」与「**一切正常**」**不可区分**。
  - ⇒ **两条断言各管一种失败**：① 管"**静默少文件**"，④ 管"**静默没删成**"。**缺任一条，那一半的失败就仍会被记成产品缺陷。**
- **★ 同族归纳（这条比单个缺陷更值钱）**：`G-RC-12`（①/④）与我在本批次报的 **`G-42`（`skipped` 自报零校验）**、**`G-44`（适配器 `not outcome.skipped` 对 step 5/6 恒真）** 是**同一族** ——
  **判据的强度不得建立在"被检对象自报"或"环境恰好为空"之上。** 三处的失败方式不同（自报可伪造 / 分支恒真 / 环境静默变空），但**都是"观测不到失败"**。建议在 `CONVENTIONS.md` 里给这一族一个**正式名字**（如"**静默等价态**"：两种语义相反的状态在观测上不可区分），并在守卫评审时逐条问"**这个判据失败时会不会静默？**"

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
5. **审计纪律**：未修改任何被审文件（`git status` 中被审范围内的文件无我的改动）。**真仓库真源未被我触碰**，但这条**必须带时点**才可核对 —— 审计期间实测 `git status --porcelain system/registry system/audit system/facts system/state.json` **为空**；**交付后**该状态会被**他人的正常交付**改变（实测：`ws-real-collect-2` 把真实采集落库，出现 `M system/facts/claims.jsonl`、`M system/facts/sources.jsonl`、`A system/raw/2026-*.txt`，与 `A system/scripts/ingest/public_fetcher.py` 同批；更早还有他人跑 `run_daily` 留下的 `system/derived/compute_gaps.jsonl`）—— **均非我所为**。**不依赖我自述的判据**：整份审计我只产出本报告**一个**文件，且我没有任何脚本会写 `facts/`/`registry/`/`audit/`/`state.json`（我的脚本只在仓库外副本里 `copytree`/`rmtree`）。我自己的实验目录**全部在仓库之外**（`system/tests/.audit-b11/` 与 `/tmp/investsigh-audit-b11/`），**其中 `.audit-b11` 以 `.` 开头、被 `_ignore()` 排除，从未污染夹具副本**；该目录我在定稿前**移出仓库**（`mv system/tests/.audit-b11/* /tmp/investsigh-audit-b11/`，随后 `rmdir`）。
6. **★ 定稿前新增的两条实测（本轮会话内，非引用记忆）**：
   - **A1 在当前 HEAD 上重跑仍成立**：违例 `6 → 0`；且**"要求 skipped 的 id 真实存在于真源"这一加强方案也不闭合**（见 §② A 组 A1 行与 `G-42` 修法）。
   - **`G-RC-12`（夹具副本静默不完整）**：broker 开启 30 次 **7 次**缺件 / broker 关闭 10 次 **0 次**缺件；**代码侧无完整性断言**。⇒ 我因此**撤回**本报告初稿里"E 附：夹具副本稳定完整 —— 未证伪"这条（§③ 第 4 条已改写）。
7. **范围外的环境事实（不作为交付结论，仅供主理人排期参考）**：
   - `main` 在被审范围外继续推进：`1c35154 → d1efa1d → c2933c3 → d5a37f8`（`git reflog` 实测）。
   - **`G-44` 已被在制品覆盖**：`git branch` 显示存在分支 **`ws/step56-skipped`**，且定稿瞬间 `git status` 有 `M system/scripts/orchestrate/pipeline.py`、`M system/scripts/ops/verify.py`、`M system/CONVENTIONS.md`（**均为他人正在编辑的文件，我一个字未改**）。⇒ 我对 `G-44` 的结论**只对 `790643c` 那一刻的 `chain_steps.py` / `compute/step.py` / `decision/step.py` 成立**；若 `ws/step56-skipped` 已让计算层/决策层按裁定 R2 回填 `skipped`，请以该分支的实测输出为准，并把本条按"已闭合 / 未闭合"在台账上更新。
   - **真仓库出现一条新的未跟踪产物**：`?? system/derived/compute_gaps.jsonl`（他人跑的 `run_daily` 落下的）。⇒ 说明 **`derived/` 在真仓库里是"活的"**：它现在有内容，而它**不在** `_reset_truth_source` 的清空清单里 —— 好在 `_COPY_SKIP` 已含 `derived`，夹具因此不受影响。**这一条我在 `G-48` 收口后已复核为"已闭合"**（详见 §⑧ 第 3 条）。

8. **★ 环境缺陷：本会话的 `grep` 是 broker 包装器（**toybox 0.8.13，非 GNU grep**），在**模式含 BRE `\|` 交替（及 `\+` `\?` `\<…\>`）**时静默返回空 —— 会污染整条证据链**（由 `ws-verify-shard` 首先告警，我把失效条件精确定位；**★ 我自己的第一版读数写错了一个值，见本节末尾的自我更正**）
   - **现象**：`which -a grep` → **第一命中是** `/Applications/WorkBuddy.app/…/shim/brokered-bin/grep`（broker shim），`/usr/bin/grep` 排在第二 ⇒ **bash 里的 bare `grep` 不是真 grep**。`grep --version` 自报 `toybox 0.8.13 (is not GNU grep 9.0)`（`command -v grep` 同路径）。
   - **精确失效条件（我的 2×2 实测，`F=system/tests/conftest.py`）**：
     | 用例 | 模式/参数 | bare `grep` | `/usr/bin/grep` |
     |---|---|---|---|
     | A | `"_TRUTH_STEMS\|_COPY_SKIP"`（BRE 交替，无 `-A`） | **0** ❌ | 6 ✅ |
     | B | `"_TRUTH_STEMS"` + `-A2`（无交替） | 2 ✅ | 2 ✅ |
     | C | BRE 交替 + `-A2` | **0** ❌ | 6 ✅ |
     | D | BRE 交替 + 选项前置（`-c -A2`） | **0** ❌ | 6 ✅ |
     | 对照 | `grep -rn "skipped="`（无交替）· `-E "a\|b"` · 中文模式 · `-c` | 一致 ✅ | 一致 ✅ |
     ⇒ **失效条件 = 模式里出现 BRE 的 `\|`**（与 `-A`、与选项位置**无关**）。**不是"grep 坏了"，是"带 `\|` 的模式坏了"** —— 这解释了为什么它是**间歇性**出现的（多数命令正常、只有带交替的那几条静默为空）。
   - **为什么极其危险**：它**不报错、无任何诊断**，且**退出码是 `rc=1` —— 也就是 grep「确实零匹配」的合法退出码**（★ 我第一版这里写成"退出码 0"，**是错的**，已在末尾自我更正）⇒ **"模式不被支持"与"真的没有匹配"在观测上完全不可区分**。这正是我在 §④ 归纳的 **"静默等价态"** 家族的第 4 个实例（前三个：`G-42` 自报可伪造 / `G-44` 分支恒真 / `G-RC-12` 环境静默变空）。
   - **★ 我自己的受害记录（如实登记）**：本报告与我上一轮给主理人的消息里，**至少 3 处**载荷证据来自 bare `grep` + `\|`：
     1. `grep -n "_TRUTH_STEMS\|REGISTRY_MODELS\|_reset_truth_source" -A14 tests/conftest.py` → **假空**（我当时察觉异常，改用 Grep 工具复核，结论**未受影响**）；
     2. `grep -n "derived\|唯一真源\|facts" .gitignore` → **假空**（我随后用 `sed` 直读文件内容独立复核，结论**未受影响**；后经 `/usr/bin/grep -n "derived" .gitignore` 复验：`derived/*.jsonl` 的忽略规则确已移除 ✅）；
     3. ★ `grep -n "pytest\|run_pytest\|verify.py\|--batch" system/scripts/ops/pre-commit.sh` → **假空**，我据此写下了"**0 命中**"并报给主理人。**重验后为 2 命中**（`run_all_gates.py` 出现在 **117/125 行的注释**里）。
   - **第 3 条的处置（实质结论不变、证据行已更正）**：那 2 处**是注释不是执行**；`pre-commit.sh` 实际执行的是"解析 python 解释器 + `run_gate` 调用"，这些守卫无一起 pytest ⇒ **`口径 16`（pre-commit 不跑 pytest）仍然成立**。**但"字符串出现 ≠ 会被执行"** ⇒ 我原先提的护栏（`grep -c "pytest\|run_all_gates\|verify.py"` 必须为 0）**实测 = 2、会误报**，**修正为剔注释后再判**：
   - ★★ **同一条里我另一个数字也错了（`§⑩` 第 3 条就地更正）**：我写的"**13 个 `run_gate`**"在对象 `main@2f62f5d`（2026-09-16 23:3x）实测为 **14 个 `run_gate` 调用**（`/usr/bin/grep -nE '^\s*run_gate ' system/scripts/ops/pre-commit.sh | wc -l` = **14**，末条 = `:126 rule_key_alignment_guard`）；写成"13"是我在更早时刻的读数。**剔注释后 `run_gate` 宽匹配 = 15**（含函数定义处）—— 两个数字口径不同，引用时必须写明用的是哪一个。
     ```sh
     grep -vE "^\s*#" system/scripts/ops/pre-commit.sh | grep -c -E "pytest|run_all_gates|verify\.py"   # 实测 0 ✅
     ```
   - **规矩（已由主理人写入 `CONVENTIONS.md::V-10`，我复验一致）**：① bash 里**一律用 `/usr/bin/grep`（绝对路径）或内置 Grep 工具**；② **禁用 `a\|b` 这种 BRE 交替**，要交替就用 `-E "a|b"`（★ 但 **`-E` 会弄坏 `\(…\)\1` 反向引用**、`\<…\>` 词边界则要用 `-w` —— **没有"一律 `-E`"的安全写法**，见 V-10 的语法矩阵）；③ 任何"**无匹配 ⇒ 不存在**"型结论，**必须换一条独立路径复算**（换工具、换参数、或直读文件）—— 这条对**审计员**尤其硬：**"我没搜到"从来不是"它不存在"的证据。**
   - ★★ **上述 ①② 我后来实测**仍不充分**（`-E` 与 **Grep 工具（ripgrep）** 也各有自己的静默零/改语义），已收紧为一条**没有例外**的规矩 —— 见 **§⑨ 第六节（7）**：**任何零命中结论必须附"地板真值" + 标引擎/方言**。
   - **同族旁注（`ws-verify-shard` 同时提醒的两条，我认可）**：**管道会吞退出码**（`cmd | tail -3; echo $?` 报的是 `tail` 的码；要取真码写成 `{ cmd; echo "EXIT=$?"; } 2>&1 | tail -3`）；**`head -N` 会截断 diff** 从而漏看 hunk。
   - **★ 受控复测（2026-09-16 23:2x，对象 = 探针文件 `/tmp/grepprobe.txt`（`aaa/bbb/ccc` 三行，我自建、**零写入被审树**），取样时刻同一分钟）** —— 这一次我**同时取退出码**（用 `{ cmd; echo "rc=$?"; }` 形式，不经管道后取值）：
     | # | 命令（逐字） | 输出 | rc |
     |---|---|---|---|
     | A | `grep "aaa\|bbb" /tmp/grepprobe.txt`（**bare**，BRE 交替） | **（空）** ❌ | **1** |
     | B | `/usr/bin/grep "aaa\|bbb" /tmp/grepprobe.txt` | `aaa` `bbb` ✅ | 0 |
     | C | `grep -E "aaa|bbb" /tmp/grepprobe.txt`（**bare**，`-E` 交替） | `aaa` `bbb` ✅ | 0 |
     | D | `grep "bbb" /tmp/grepprobe.txt`（**bare**，纯字面 = **地板真值**） | `bbb` ✅ | 0 |
     ⇒ 失效集合**不止 `\|`**：`CONVENTIONS.md::V-10`（**我定稿时主理人正在同一工作树写入的那 92 行**）以双引擎 + Python `re` 地板真值实测出 **`\|` / `\+` / `\?` / `\<…\>` / `\b`** 五类在 bare 下返回 `0` 命中；而 **`-E` 会反过来弄坏 `\(…\)\1` 反向引用**，`-w` 才是词边界的正解。⇒ **没有"一律改成 X"的安全写法**，与我的 A–D 表一致：**唯一安全的做法是绝对路径 `/usr/bin/grep` 或内置 Grep 工具**。
   - **★ 自我更正（本节第 1 版写错的那个值）**：我在给主理人的消息与本报告初稿里写过"静默返回空、**退出码 0**"。实测（上表 A + `grep --version`）**真值是 `rc=1` 且工具自报 `toybox 0.8.13`**。我按"引文/正例不豁免"的纪律把它当作**我自己的二次编造观测值**登记在此：**根因是"工具不是 GNU grep、不支持该语法"，不是"退出码被吞"**；`rc=1` 恰好是"确实零匹配"的合法码，所以**危险程度不降反升**（无法靠检查退出码识破）。

9. **★ 流程事实（我审计期间再次发生）：主仓工作树同时有 ≥2 个写入方** —— 实证（非推断）：我在 `2026-09-16 23:16:02` 写本报告时，`git status --short` 除本报告外还出现 **`M system/CONVENTIONS.md`**，其 mtime = **`23:15:53`（比我早 9 秒）**，`git diff --numstat` = **`92 0`**（新增 V-10 整节）。**我一个字未改该文件**（我全程只写本报告）。⇒ `d33d08d` 记录的"**主仓工作树只能有一个写入方**"这一竞态**再次发生**；因此 **`git status` 的"我的改动"与"别人的改动"在本回合内无法从工具输出单独区分**，我给主理人的任何"当前态"读数都带上了时刻（口径 10）。**处置**：我不提交、不 `add`、不 `stash`、不清理，把入库交回主理人。<br>★ **附带证据价值**：那条与我**同分钟**产生的 `M system/CONVENTIONS.md` 正是 `V-10`（工具输出即证据 / 零命中必须附地板真值），与本节第 8 条**同一发现** —— 我把它当作**独立第二来源**，并据此更正了我自己写错的退出码（见第 8 条末尾的自我更正）。

---

## ⑦ 结论（五档）

| 交付 | 档位 |
|---|---|
| `4f95c3d` `skipped` 字段与 `G1-05` | **不够**（字段是自报、无校验；step 1 口径反向 ⇒ 判据在一半的步上恒假）→ ★ **`G-42` 已按"如实降格 + 加互斥校验"收口，我复验：互斥校验生效、原攻击仍成立（残余已由实现方声明）** —— 见 §⑧ 第 1 条 |
| `790643c` step 2 接线 | **好**（判别式成立，我三连跑复现） |
| `fd49a20` 首日豁免 | **不够**（死代码修好了，谓词却恒误豁免；计数可见但含义不可信）→ ★ **`abbe7b3` 已收口，我独立复现：正向主张全部成立、我的原始反例被拦住**（`exit=1`，`exempt=0`）⇒ 判为**"主体已闭合"**；但同一修复**只覆盖"字段为空"一种形态** ⇒ 我继续证伪出 **`G-63`**（引用可伪造）与 **`G-64`**（降级日被误判"空执行"，**高**）—— 见 §⑨ |
| `5a314a3` `derived/` 归属 | **错**（"真源/非真源"两套声明逐字共存；"可重算"理由实测不成立）→ ★ **该结论已被实现方采纳并按相反方向收口**（`derived/` 改回入库），我复验后**判定为"已闭合（残留一处注释未清，见 `G-50`）"** —— 见 §⑧ 第 3 条 |
| `23f78db` 夹具不继承 `state.json` | **好**（就该文件而言；且 `tests/injection/test_wiring_guards.py:165-167` 已补**机制层断言**，防用例空转）／**不够**（同族 **4 个登记层真源**未覆盖、无机器绑定；副本完整性**无断言** ⇒ 缺件时静默继续） |
| `3f4c372` `_stage_gate_verdict` | **不够**（方向检测成立；缺无歧义检查）→ ★ **`G-47` 已修，我复验生效**（见 §⑧ 第 2 条） |
| `bc26933` 判据有效性门禁 | **好**（三条绑定实测拦得住）／**不够**（`blocked_hint` 无语义核对） |
| `016f311` 缺口登记 | **好**（`G9-1` 可独立复现，输出逐字一致） |

**给主理人的一句话（定稿时）**：本批次**有真修实**（step 2 的判别力、判据有效性门禁的两向绑定），但 `G-42` / `G-43` / `G-44` 三条都属于**同一形态**——"**判据/字段有了，但校验它的那一侧没有接上**"，因此三个关键守卫**当时都能被机器证明失效**（`G1-05` 6→0；首日豁免真违规被放过；第二次 `run_daily` 恒 `blocked`）。这三条**建议按"高"优先级进下一批**，`G-44` 尤其紧急——它意味着**生产上第二次跑 `run_daily` 就会 `blocked`**。

**★ 定稿后各条的最新状态（我逐条复核，见 §⑧ / §⑨）** —— 请以这一块覆盖上段的"当时"：
| 原结论 | 现状（对象 `main@e9a009b`，2026-09-16 23:1x CST） |
|---|---|
| `G-42`（`skipped` 自报零校验，**高**） | **按可接受方式收口**：互斥校验生效（相交即拦、部分相交也拦、无误伤）；**残余已由实现方如实声明**（"自报式不变量兜底，不能抓蓄意伪造"）。★ 我已证明**不可能 in-band 闭合**（"存在性 ≠ 归属性"），不要再照"加存在性核对"去改 |
| `G-43`（首日豁免谓词恒误豁免，**高**） | ✅ **已闭合**（`abbe7b3`）。我独立复现：正向六条主张全部成立；**我的原始反例 `B1-c1` 被拦住**（`exit=1`、`exempt=0`）；首日豁免未被误伤（`exempt=1`/`holding=0`） |
| `G-44`（适配器 `skipped` 分支对 step 5/6 恒真，**高**） | ✅ **代码侧已闭合**（`5d0557c fix(compute/decision): step 5/6 幂等重跑如实上报 skipped —— 收 G-44`，属 `016f311..HEAD`）：`compute/step.py:71 skipped=list(report.skipped_derived_ids)`、`decision/step.py:81 skipped=list(report.skipped_recommendation_ids)`、`pricelayer/step.py:180 skipped=list(report.checked_ids)`（后者由 `9552e8c` 落地），语义**符合裁定 R2**（"本轮读入、确认无需追加"）；`chain_steps.py:315` 的判据 `not produced and not skipped and incomplete_reason is None` 我逐字复核未变。⚠️ **我尚未端到端复验"重跑时真的不再 block"**（需跑 `run_daily` 真实二连跑）—— 排他窗口内我没跑 pytest ⇒ **这条按"代码侧已闭合 / 未端到端复验"标记，不按"已验收"** |
| `G-45`（两模块口径矛盾 + `output_refs` 零生产赋值点，中高） | ✅ **已闭合**（`abbe7b3`）：`stage_gate` 的定义删净、改调 `degrade.holds_valid_result()`；写路径补齐（`pipeline.py:415/416`）。★ **但同一修复的边界外我又证伪出两条** → **`G-63`**（中高）/ **`G-64`**（**高**），见 §⑨ |
| `G-RC-11`（夹具漏 4 条登记层真源） | **半闭合**：facts 侧 ✅ + `_COPY_SKIP` 有机制层断言 ✅；**4 条登记层真源仍敞着** ❌（`_COPY_SKIP` 不含 `registry`/`audit`、tests 侧无覆盖断言） |
| **`G-64`（新增，高）** | **降级日被 `G1-04` 误判"空执行"**：行由真实写路径产出（`status='done'`、`output_refs=[]`、`changed=True`、`degraded=True`）⇒ `gap_to_task` `exit=1` 报违例，而 `Ch8 §E.4` 明令降级日 `output_refs` **必须**为空 ⇒ **两条判据对同一行相反结论**。修法**升级后**（`ws-ch2-rules` 独立复核 + 我逐格复现）：**不要只加 `or degraded`，应从 `degrade` 真源派生**（根因是 `G-06` 单一真源违反，`gap_to_task.py` 对 `degrade.py` 零引用）+ **必须分列计数**（硬证据：`B2`（合法）与 `C`（违规）当前**都记 `exempt=0`**）+ 谓词改名。见 §⑨ 第六节 |
| **`G-63`（新增，中高）** | **两个落点、失效方向相反**：`stage_gate.py:600`（漏报：垃圾引用让判据闭嘴）／`scripts/daily/degrade.py::holds_valid_result` 载体①（误报：前序垃圾引用让合法的首日降级行被判 FATAL；HEAD `:184`，**当时读数**）。可达性**我按 `G-03` 不主张**（唯一写入方填真 `check_id`）⇒ 强度 = "判据边界可被机器证明不严" |

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

---

## ⑨ 审计后复核（二）：`abbe7b3 fix(degrade): 修 G-43/G-45` —— 正向主张 ✅ 全部成立，但我**继续证伪**出两条新缺陷

> **对象** = `main@e9a009b` 工作树那份 `system/` 的副本（`/tmp/investsigh-audit-b11/base-e9a009b/`，`rsync -a --exclude tests/.work --exclude __pycache__`，6.2 MB）；**取样时刻** = 2026-09-16 23:1x CST。脚本 `/tmp/investsigh-audit-b11/exp_close_43_45.py`，`exit=0`。
> **纪律**：除**明示的"违约注入 / 定向篡改"**外，所有行一律由**唯一写入方** `Pipeline._write_check_record` 产出（不手工拼第二套字段形状，`G-06`）；`grep` 一律走 `/usr/bin/grep`（§⑥ 第 8 条）；未跑 pytest（本轮全部用直调脚本，与门禁口径无关）。

### 一、正向复核 —— 我逐条在机器上重跑，**不采信提交信息**

| # | 实现方主张 | 我的独立复现（命令 + 输出） | 判定 |
|---|---|---|---|
| 1 | `stage_gate` 不再自持一套判定，改调 `degrade.holds_valid_result()` | `/usr/bin/grep -n "_holds_valid_result" system/scripts/delivery/stage_gate.py` → **仅 `:539` 一处注释**（定义已删净）；`:546 from scripts.daily.degrade import holds_valid_result`；调用点 `:601`（`any(holds_valid_result(_prior) for _prior in tasks[:_idx])`）、`:612` | ✅ **口径收口到唯一真源**（= 我 `G-45` 建议的"收口到唯一一处"） |
| 2 | 写路径补齐两载体 | `pipeline.py:415 output_refs=produced if valid_run else []`、`:416 last_valid_result_ref=None if valid_run else last_ref`、`:393 last_ref = last_valid_result_ref(self.root, scope=…)`（**复用**唯一真源）。实测真行：`row0(done) output_refs=[] ref=None`；`row1(failed) output_refs=[] ref='check_2026-09-16_full'` | ✅ 我 `G-45` 的"**零生产赋值点**""**两载体恒为空**"**两条均不再成立** |
| 3 | 真实形状 + 抹掉失败行引用 ⇒ 必须 FATAL | **C1**：`exit=1  rows_holding_valid_result=1  degrade_first_day_exempt=0`，FATAL = `task_check_2026-09-16_full_r1 失败但未保留 last_valid_result_ref（此前已有行持有有效结果 ⇒ 引用本该在，不得置空）` | ✅ 成立 |
| 4 | 首日豁免仍有效、计数可见（`G-43` 的另一半） | **C2**：`exit=1  rows_holding_valid_result=0  degrade_first_day_exempt=1`；唯一 FATAL 是无关的 `CV4 覆盖目标集为空`（`G-03` 那条，与本单无关） | ✅ 成立（**豁免没有被这次修复误伤**） |
| 5 | ★ 我批次 11 的原始反例已被拦住 | **C3**（手工拼我 `B1-c1` 的确切形状 `[done + output_refs=[] + ref=null, failed]`）：`exit=1  rows_holding_valid_result=1  degrade_first_day_exempt=0`，FATAL=`check_d1_full_r1 失败但未保留 last_valid_result_ref…` | ✅ **我 `B1-c1` 的反例已闭合**（`stage_gate.py:585` 逐字引用了这条用例） |
| 6 | 夹具改走真实写路径（`G-06`：不造第二套形状） | `conftest.py:604-642 write_check_records()` 内**确实调用** `Pipeline(root, config={"steps": []})._write_check_record(res)`，并 `read_records(root, "tasks")` 返回真行 —— 未发现第二套字段形状 | ✅ 符合 `G-06` |

⇒ **`abbe7b3` 的六条主张我全部复现，无一条被我推翻。** 这一节的结论与提交信息一致，但**是我的实测读数，不是引用**。

### 二、★★ 我继续证伪出的两条新缺陷

#### `G-63`（建议登记）—— `degrade_keeps_last_valid` 只判**真值性**：引用可**伪造 / 悬空** 【严重度：中高】

**复现（C4/C5/C6，三组，行均由真实写路径产出后做"定向篡改"）**：
```
C4 失败行 last_valid_result_ref='check_不存在的_id_9f3a'        → exit=1  FATAL 只有 CV4（无关）  豁免=0  未报任何违例
C5 失败行 last_valid_result_ref='task_check_2026-09-16_full_r1'（自指：指向**自己**那一行）→ 同上
C6 失败行 last_valid_result_ref='task_check_2026-09-16_full_r2'（指向**另一条失败行**）  → 同上
```
- **判据原文**（`stage_gate.py:600`）：`if t.get("status") == "failed" and not t.get("last_valid_result_ref"):` —— **只做真值性**。
- **全仓无第二处校验**（三条独立路径复算）：① `scripts/checks/` 内 `grep` 对 `last_valid_result_ref` **零命中**；② `facts.schema.json:4712` 对该字段只要求 `anyOf[string, null]`，**无引用完整性**；③ `scripts/ops/`、`scripts/delivery/` 内除 `stage_gate` 外无其它引用点。
- ⇒ 把引用换成**任何非空字符串**（不存在的 id / 自指 / 指向失败行）即令判据**完全闭嘴**（`exempt=0` 是因为 `not ref` 为假，所以**既不计豁免、也不报违例** —— 静默穿过）。**与 `G-42`（`skipped` 自报零校验）逐字同族**：判据强度建立在"**被检对象自报**"之上。
- ★ **附伤（同一族第 7 例）**：C4/C5/C6 里 `rows_holding_valid_result` 变成 **2 / 2 / 5**。而 `rows_holding_valid_result` 与 `degrade_first_day_exempt` 是**成对仪器**，设立目的正是"让恒真 / 恒假当场可见"（`stage_gate.py:593-596`）—— **伪造的引用会同时把仪器读数推高** ⇒ **仪器本身被同一份自报数据污染**。
- **可判定修法**（不需要新真源）：`ref = t.get("last_valid_result_ref")`；若 `status == "failed"` 且 `ref` 非空 ⇒ 断言 `ref ∈ {row["check_record"]["check_id"] for row in tasks if is_valid_run_record(row)}`，否则 `Violation("引用悬空：last_valid_result_ref 未解析到任何**有效运行**的 check_id")`。`scripts/daily/degrade.py::is_valid_run_record` 已有该原语（HEAD `:129`，**当时读数**；本报告原写 `degrade.py:80-101`，为 `abbe7b3` 期读数，见 §⑮）。

#### ★★ `G-64`（建议登记）—— `is_no_change_day()` 漏了**第二个合法空产出态（降级）** ⇒ **降级日被误判"空执行"** 【严重度：**高**】

**复现（C7 —— 行由真实写路径产出，不是手工拼）**：
```
真行：status='done'  output_refs=[]  last_valid_result_ref=None
      check_record.changed=True  check_record.degraded=True
$ python scripts/tasks/gap_to_task.py <root>   → exit=1
  scanned done_empty_output_rows: 1   /   scanned no_change_day_exempt: 0
  !! task_check_2026-09-16_full 状态为终态 'done' 但 output_refs 为空，且不满足无变化日豁免
     （需 `check_record` 存在且 `check_record.changed is False`）（空执行：报了完成却没有产出）
```
**对照 C8**（`changed=False` 的无变化成功日）：`exit=0`，`no_change_day_exempt: 1` ⇒ 这次红**不是**"判据整体坏了"，而是**"降级"这一态在豁免谓词里完全没有表达**。

- **为什么这是真缺陷（跨模块相反结论，且第二个结论违反成文契约）**：
  - 写侧：`pipeline.py:391 valid_run = not (result.blocked or result.degraded)`、`:415 output_refs=produced if valid_run else []` ⇒ **降级运行 `output_refs` 必为空**；这正是 `Ch8 §E.4` 的**明令**（"失败 / 阻断 / 降级时如实为空，**不得把部分写入冒充成有效产出**"），`pipeline.py:387-390` 逐字复述了这条。
  - 判侧：`gap_to_task.py:240-254` 对**同一行**判 `G1-04` 违例"空执行：报了完成却没有产出"。
  - ⇒ **两条判据对同一行给出相反结论** —— 与我的 `G-45` **逐字同形态**；区别是**这次的行由生产写路径自己造出**，不是我手工拼的。
- **可达性（两个条件来自两处独立累加器，可同时为真）**：
  - `pipeline.py:254 result.degraded = result.degraded or bool(outcome.degraded)` —— **任一步**降级即置真；而 `ingest_step.py:260-262` 在**投递口为空**时 `degraded = True`（**空样本 = 常态**）。
  - `pipeline.py:251-252 result.judgment_change[k] = bool(v) or …`；`RunResult.changed`（`:84-86`）是 `any(self.judgment_change.values())` 的**属性**，不是可独立设置的字段 ⇒ 只要当日任一步报告了判断变化即为 `True`。
  - ⇒ 场景"**今天没有新投递（空样本 ⇒ `degraded=True`），但既有事实的重算改变了某条判断（⇒ `changed=True`）**"会**稳定产出**该形状。
- ★ **它同时证伪了实现方的三处书面声明**（`gap_to_task.py:73`、`tests/daily/test_no_change_day.py:16`、本单报告 §1.4）："`done` 行**穷尽**落入'合法 / 违例'两态，**无第三态**"。实测**存在第三态**：`done + output_refs=[] + degraded is True`，它**合法**（`§E.4`）却被判违例。
- ★★ **本次修复的方法学问题（比缺陷本身更值钱）**：把判据从"一刀切"换成"一个正向标记"，方向**正确**；但它**只枚举了合法态的一个**。这正是 §④ 归纳的「**静默等价态**」第 **8** 例 —— `done + output_refs=[]` 有**两个语义相反**的真源（无变化日 / 降级日），而 `is_no_change_day()` 只看 `changed` ⇒ **观测上不可区分**，于是降级日被当成"空执行"。
- **可判定修法**（**不要只加一个 `or` 就算完**）：豁免改为"`changed is False` **或** `degraded is True`"，并**分列计数**（`no_change_day_exempt` / `degraded_empty_output`），否则立刻回到"两个相反状态观测量相同"的老坑。**并补一条正例（走真实写路径）**：`write_check_records(root, [{"produced": [], "judgment_change": {"x": True}, "degraded": True}])` ⇒ 必须 `exit 0`。
- ★ **我已核对：该测试文件没有这个 case** —— `tests/daily/test_no_change_day.py:61-70` 的 `_rec()` **硬写 `"degraded": False`**；全文件唯一用 `changed=True` 的"反例 A"（`:116`）那行**不降级** ⇒ 本单的 10 个用例 + 报告**全部漏掉了降级这一支**。

### 三、我试了但**没能推翻**的（如实登记）

| 尝试 | 结果 |
|---|---|
| 试 `holds_valid_result` 的**载体②**是否"过宽"（把"成功但无产出"也认成持有有效结果） | **不构成缺陷，未推翻**：**C9 实测**（真实写路径产出的无变化成功日 `status='done' output_refs=[] ref=None changed=False`）→ `is_valid_run_record=True`、`holds_valid_result=True`、`last_valid_result_ref(root)='check_2026-09-16_full'`（**三处一致**）。它落**保守**方向（更容易报违例），且理由有明文（`scripts/daily/degrade.py::holds_valid_result` docstring 的"★ **② 为什么不看 `output_refs`**"段，逐字句位于 HEAD `:171-172`，**当时读数**；本报告原写 `degrade.py:121-124`，为 `abbe7b3` 期读数，见 §⑮）—— 我认为这个取舍正确 |
| 试 `_holds_valid_result` 是否还有**残留调用点**（口径没收干净） | **未推翻**：`grep -rn "_holds_valid_result" system/scripts/` 只剩注释，无定义、无调用 |
| 试 `_COPY_SKIP` 新增 `raw` 是否改变了既有 20 条守卫的行为 | **未推翻**：`G-RC-11` 的登记层那一半不受影响（见下节） |
| 试 `write_check_records()` 是否偷偷造了第二套字段形状 | **未推翻**：它**确实调用** `Pipeline._write_check_record`，`G-06` 符合 |
| 试 C4 的悬空引用是否会被**别的守卫**（schema / checks / ops）拦住 | **未推翻（= 缺陷成立）**：三条独立路径复算均无任何校验点 |

### 四、`G-RC-11` 的当前状态（我在 `main@e9a009b` 重验，**半闭合**）

- ✅ **facts 侧已闭合**：`conftest.py:102-104` 已是 `from schema.stems import JSONL_STEMS` / `_TRUTH_STEMS = tuple(JSONL_STEMS)`（**不写字面量**）；`tests/unit/test_schema_expand.py:369-382` 四条绑定断言齐备。
- ✅ **`_COPY_SKIP` 现有机制层断言，但只覆盖一个条目**：`tests/injection/test_wiring_guards.py:165-167 assert "state.json" in _COPY_SKIP` —— **形态正确**（正是我建议的写法）。
- ❌ **登记层那一半仍敞着**：`_COPY_SKIP`（`conftest.py:70-73`）**不含 `registry` / `audit`**；`_TRUTH_STEMS` 仍**全在 `facts/`**；tests 侧对 `REGISTRY_MODELS` 的引用**只在** `test_wiring_guards.py:38/39/98`（说 guard 源码接线 + `rule_hint`），**无一条**断言 `(_COPY_SKIP ∪ _TRUTH_STEMS) ⊇ REGISTRY_MODELS 的真源`。⇒ 4 条登记层真源**依然既不被清空、也不被排除、也不被断言覆盖**（详见 `G-RC-11` 条目末尾的二次复核）。

### 五、五档结论（本轮新增部分）

| 对象 | 判定 |
|---|---|
| `abbe7b3` 对 `G-43` / `G-45` 的收口（正向主张） | **好** —— 六条主张全部独立复现，**无一条被推翻**；我的原始反例被拦住；首日豁免未被误伤；夹具改走真实写路径符合 `G-06` |
| 同一条修复的**覆盖边界** | **不够** —— 只覆盖"字段为空"一种失败形态：引用可伪造（`G-63`，中高）、**降级这一合法态未枚举**（`G-64`，**高**） |
| `G-RC-11` | **半闭合**：facts 侧 **好**；登记层 4 条**仍是敞着的缺口**（**不够**） |
| `G-64` / `G-63` 的**根因层** | **不够（且不止一处）** —— `gap_to_task.py` 对 `degrade.py` 的**零引用**（两条独立路径复算）⇒ 这是 **`G-06` 单一真源违反**；`G-63` **两个落点且失效方向相反**（`stage_gate.py:600` 漏报 / `scripts/daily/degrade.py::holds_valid_result` 载体① 误报，HEAD `:184`，**当时读数**）⇒ 修法须"从 `degrade` 派生 + 两侧都改"，**我原"只加一个 `or`"的建议被此覆盖**（见第六节 3/4） |

**给主理人的一句话**：`abbe7b3` 是**本批次质量最高的一次收口**（正向主张我一条都没推翻），但它的判据**只枚举了"合法空产出"的一个态、只覆盖了"引用为空"一种破坏形态** —— `G-64` 尤其紧急，因为它意味着**降级日（空样本是常态）会被 `G1-04` 判成"空执行"**，即"**判据修好了，却把一个合法运行态判成违例**"。两条都建议进下一批，`G-64` 按**高**。

### 六、交叉复核：`ws-ch2-rules` 对 `G-64` / `G-63` 的独立复核，我**逐格复现**，并给出三处更正/升级

> **来源标注（引用他人读数必须标来源）**：以下"对方读数"引自 `ws/ch2-rules` 报告 §17.15（提交 `6f35153`）；**我只把它当"待验证线索"，每格都用我自己的仪器重跑**。
> **时效核对（口径 10，必做）**：对方取样时 `main` 为 `439e8d0`（23:23:24）；我复核时 **`HEAD = 2f62f5d`（2026-09-16 23:25:11 CST）**。`git log --oneline e9a009b..HEAD -- system/scripts/tasks/gap_to_task.py system/scripts/daily/degrade.py system/scripts/delivery/stage_gate.py` **为空** ⇒ 这三个文件在我 §⑨ 的对象之后**未被改动**⇒ **§⑨ 全部结论在当前 HEAD（`2f62f5d`）上依然成立**。

**（1）四态表我逐格复现，含对方新增的 `B2` 格** —— 仪器：`/tmp/investsigh-audit-b11/exp_close_43_45.py` 同族脚本，**每态一个全新 root**（★ 对方自曝第一版让四态共用 root 造成"现场被前一态污染"⇒ 我按此纪律写），行**全部由唯一写入方产出**：

| 态 | `status` | `changed` | `degraded` | `last_valid_result_ref` | `output_refs` | 我的读数 `exit` | `no_change_day_exempt` | 应然 |
|---|---|---|---|---|---|---|---|---|
| A 无变化日 | `done` | `False` | `False` | `None` | `[]` | **0** ✅ | 1 | 0 |
| B 降级（此前**有**成功） | `done` | `True` | `True` | `check_2026-09-16_full` | `[]` | **1** ❌ | 0 | 0 |
| **B2 降级（此前**无**成功）** | `done` | `True` | `True` | **`None`** | `[]` | **1** ❌ | 0 | 0 |
| C 真违规 | `done` | `True` | `False` | `None` | `[]` | **1** ✅ | 0 | 1 |
⇒ **四格与对方逐格一致**（含 `B2` 那一格），`G-64` 成立。

**（2）★ 我确认对方由 `B2` 得出的关键推论，并把它写到更明确**：`B2` 与 `C` 在行上**字段逐一相同，唯一差异是 `check_record.degraded`** ⇒
  - **`check_record.degraded` 是把"降级"与"真违规"分开的**唯一**字段**；
  - ⇒ **排除候选修法 `last_valid_result_ref is not None`**（`B2` 的该字段是 `None`，用它做豁免会把假红从 `B` 挪到 `B2` —— **换个字段复发**，正是 `G-43` 的形状）；
  - ⇒ 我原建议"`changed is False` **或** `degraded is True`"是**经此检查后唯一成立的那支**。

**（3）★ 我把 `G-63` 的落点从"数量"推进为"两个落点且失效方向相反"**（这条是我对对方结论的**增量**）：
| 落点 | 代码 | 只看 | 垃圾引用（不存在的 id / 自指 / 指向失败行）的后果 | 方向 |
|---|---|---|---|---|
| ① | `delivery/stage_gate.py:600` `and not t.get("last_valid_result_ref")` | 真值性 | 判据**完全闭嘴** ⇒ 真违规被放过 | **漏报** |
| ② | `scripts/daily/degrade.py::holds_valid_result` **载体①**（`if row.get("last_valid_result_ref"): return True`；写出位置 HEAD `:184`，**当时读数**）| 真值性 | **前序**行带垃圾引用 ⇒ `any(prior)` 为真 ⇒ 后续丢引用的失败行**被判 FATAL**（而它本该按首日豁免） | **误报** |

⇒ 两个落点**不是同一个 bug 的两份拷贝**，而是**同一族缺陷在相反方向上各错一次**；修法必须**同时**覆盖两侧（都改为"引用可解析为一条 `is_valid_run_record()` 为真的 `check_id`"）。
⇒ ★ 但**可达性我按 `G-03` 明确不主张**：唯一写入方填的是真实 `check_id`；**"生产数据里会出现垃圾引用"我未证**（与对方口径一致）。故 `G-63` 的强度是"**判据边界可被机器证明不严**"，不是"已发生的违规"。
> ★★ **锚点已按 `V-11` 规矩 9 改写（2026-09-17 补）**：本表原写死 `daily/degrade.py:130`，那是我在 **`abbe7b3` 期**的读数；`bd66025`（`G-64` 收口，+50/-2）在 `is_valid_run_record` **之前**插入了两个函数 ⇒ 该行号**已漂到 `:184`**，且 `:130` 现在落在**另一个函数的 docstring** 上（"匹配到了别的东西"形态）。**同一处漂移波及本报告 5 条 `degrade.py` 引用**，完整对照与根因见 **§⑮**。凡本报告中 `degrade.py` / `gap_to_task.py` 的行号，**一律以符号锚点为准**。

**（4）★ 根因升级：这是 `G-06`（单一真源）违反 —— 我两条独立路径复算确认**
```
$ /usr/bin/grep -nE 'degrade|holds_valid_result|is_valid_run_record' system/scripts/tasks/gap_to_task.py
  （无输出）rc=1
$ Grep 工具（ripgrep）同模式            → No matches found        ← 第二条独立路径，防"零命中即不存在"的静默等价态
```
⇒ `gap_to_task.py` **完全不引用** `scripts/daily/degrade.py`。而 `scripts/daily/degrade.py::is_valid_run_record` 的 docstring 自称本判定的「**唯一判定原语**」（HEAD `:85`，**当时读数**；本报告原写 `degrade.py:95`，为 `abbe7b3` 期读数，见 §⑮）⇒ **"唯一真源"与另一个同题谓词（`is_no_change_day()`）对同一行相反结论**。两个模块各自回答"这一行算不算一次合法运行"：
| 模块 | 谓词 | 看哪个字段 |
|---|---|---|
| `scripts/tasks/gap_to_task.py::is_no_change_day` | 只看 `changed` |
| `scripts/daily/degrade.py::is_valid_run_record`（HEAD `:129`，**当时读数**）| 看 `degraded` ← **正确的那半早就存在** |
⇒ **接受对方的修法升级建议**：不要只往 `is_no_change_day()` 里加 `or degraded`（那会变成**第 4 个**同族局部谓词），应让它**从 `degrade` 的真源派生**。**我原建议（只加 `or` + 分列计数）应在这一点上被这条覆盖。**

**（5）★ 分列计数，硬证据我独立复现**：上表 `B2` 与 `C` 的 `no_change_day_exempt` **都是 `0`** ⇒ 一个**合法态**与一个**违规态**在读数上**完全合并**。这正是"必须分列"的判据（`G-03`：观测量相同 ⇒ 不可区分）。
**（6）命名**：我同意对方的"`is_no_change_day()` / `no_change_day_exempt` 只承诺了两个子类中的一个，加了降级之后**名字就开始撒谎**" ⇒ 建议按"**合法空产出**"命名（`G-42` 同族：名字承诺的语义 ≠ 实现）。

**（7）★★ 对我自己 §⑥ 规矩的再修正：`-E` 与 **Grep 工具（ripgrep）** 同样有静默零 —— 我原规矩 ①②"用绝对路径 / 用 `-E` / 用 Grep 工具"**都不充分**。受控复测（探针 `/tmp/gp.txt` = `ab/aab/abb/a{2}b` 四行，我做、零写入被审树；退出码用 `{ cmd; echo "rc=$?"; }` 取）：
| # | 命令 | 输出 | rc | 判定 |
|---|---|---|---|---|
| E1 | `grep -E '\<ab\>'`（**bare**） | （空） | **1** | ❌ **静默零**（`-E` 救不了词边界） |
| E2 | `/usr/bin/grep -E '\<ab\>'` | `ab` | 0 | ✅ |
| E3 | `/usr/bin/grep -w 'ab'` | `ab` | 0 | ✅ **词边界的正解是 `-w`**（与 `V-10` 一致） |
| E4 | **Grep 工具**（ripgrep）`pattern: aab\|abb` | **No matches found** | — | ❌ **静默零**（ripgrep 方言里 `\|` 是**字面量**） |
| E5 | **Grep 工具** 对照（ERE 交替，无反斜杠）：pattern = `aab|abb` | `aab` / `abb` | — | ✅ 正常（⇒ E4 是**方言**问题，不是"工具坏"） |
| E6 | `grep 'a\{2\}b'`（**bare**，BRE 区间） | `aab` | 0 | ✅ BRE 区间在 bare 下**正常** |
| E7 | `grep -E 'a\{2\}b'`（**bare**，ERE） | **`a{2}b`**（匹配到**字面**那行） | 0 | ⚠️ **不是零命中，是"静默匹配了另一个东西"** —— 机械加 `-E` 把区间变成字面量 |
| E8 | `/usr/bin/grep -E 'a\{2\}b'` | `a{2}b` | 0 | ⚠️ **与 bare 行为一致** ⇒ **E7 不是 bare-grep 的缺陷** |
⇒ ★★ **我先前把这一格框成"对 `ws-ch2-rules` 的数值更正"，那个框法是**错的**，现就地更正（我本轮第 3 次自收紧）**：对方的 `0` 与我的"错配命中"**不是矛盾，是输入不同** —— 受控复测（探针 `/tmp/gp2.txt` = `ab/aab/abb`，**无字面行**）：`grep -E 'a\{2\}b'` → **rc=1 零命中**；`/usr/bin/grep -E 'a\{2\}b'` → **rc=1 零命中**。而含字面 `a{2}b` 行时两者都"命中"那行。⇒ **同一语义变化（`-E` 下 `\{` 变字面 `{`）在两个输入上的两种表现**，两个读数**都对**。
⇒ 真正该记的教训比"谁的数字对"更硬：**一条零命中结论若不写清"输入是什么"，它连"是否被搜过"都不可判定** ⇒ 零命中结论必须附 **(输入 + 模式 + 引擎)** 三元组。**结论方向不变**：ERE 里 `\{` 是字面 `{`，正确写法 `a{2}b`；且 **"匹配到了别的东西"比"零命中"更坏**（零命中至少让人起疑，错配**看起来像成功**、不进任何 `rc` 判据）。
⇒ **因此我把自己 §⑥ 的规矩收紧为一条（不再给"一律改成 X"的安全解，因为不存在）**：
> **任何"零命中 / 不存在"型结论，必须同时给出"地板真值"**（同一模式在**已知含该内容**的输入上必须命中；或换一条**独立路径**复算），并标注**引擎 + 方言**（bare toybox / BSD grep / ripgrep 三者语义不同）。**"我没搜到"从来不是"它不存在"的证据 —— 而"工具静默失效"与"确实零命中"在观测上完全等价。**

**（8）对方的两条自曝我认可并登记其方法学价值**（供我报告引用）：① `V-10` 落地不到 10 分钟，他本人**第一个中招**（`grep -n 'V-10\|V-11'` 假空 ⇒ 误得"我的树里没有 V-10"）；② 他第一版探针让**四态共用同一个 root** ⇒ `B` 的 `last_valid_result_ref` 被 `A` 那行污染 ⇒ **假证据**，改成每态新 root 才暴露出决定修法的 `B2` 格。⇒ 这两条都是「**静默等价态**」的新形态：**"现场被前一态污染"与"零命中式失效"同族**，建议一并进 `CONVENTIONS`。

---

## ⑩ 全量重证：各流报告里的"零命中 / 不存在"型断言（team-lead 裁决第 2 项）

> **对象**：`main` **`2f62f5d`** 的 `system/reports/`（67 份报告）+ 被这些断言点到的工作树文件；**取样时刻** 2026-09-16 23:3x–23:5x CST。**引擎指纹**（每次复算前先取，`V-10`）：`command -v grep` = `…/shim/brokered-bin/grep`；`grep --version` = **`toybox 0.8.13 (is not GNU grep 9.0)`**；`/usr/bin/grep --version` = **`grep (BSD grep, GNU compatible) 2.6.0-FreeBSD`**；Grep 工具 = **ripgrep**。
> **方法（4 步）**：① 用两个模式（窄：`零命中|无匹配|未命中|零个`；宽：`没有任何|不存在于|零引用|没有引用|全仓库没`）筛出"否定型"行约 **130** 处；② **人工分流**为"**载荷型**"（把零命中当**证据**用）与"叙述型"（散文用法）；③ 对**载荷型逐条**换独立引擎复算 + **必附地板真值**（同模式在**已知含该内容**的输入上必须命中）；④ 标 **rc**。

### 一、逐条复算结果（10 条载荷）

| # | 载荷（原文） | 出处 | 我的复算（引擎 + rc + 地板真值） | 判定 |
|---|---|---|---|---|
| 1 | "全仓库 `_holds_valid_result` 的**执行体零命中**（仅 3 处注释）" | `ws_degrade_contract_report.md:75` | `/usr/bin/grep -rnE 'def _holds_valid_result' system/scripts/` → **rc=1**；地面真值 `/usr/bin/grep -cE '^def \|^    def ' stage_gate.py` = **22 / rc=0** | ✅ **复现** |
| 2 | "`output_refs=` **零个生产赋值点**" | **我的 `:61`/`:180`** + `ws_degrade_contract_report.md:48`/**:232** | `/usr/bin/grep -rn 'output_refs=' system/scripts/` → **`pipeline.py:415 output_refs=produced if valid_run else []`**（其余 4 处均为注释/文档）；地板 `output_refs` 宽匹配 = 3 | ⚠️ **过期**（`:48` 有"在本单之前"限定，属历史态；**`:232` 是当前态断言，需其作者更正**）→ 我自己的两处**已就地更正** |
| 3 | "`implemented_in_first_version` 有**零个代码消费者**" | `ws_degrade_contract_report.md:502` | `/usr/bin/grep -rn` → 15 处命中：**真源 `rules/pipeline.yaml`（6×true + 2×false）+ 5 处注释/docstring + 1 测试注释 + PROGRESS/SKILL 各 1** ⇒ **零处"读该键"的代码**（无 `cfg["…"]` / `.get("…")`） | ✅ **复现**，但措辞应精确为"**零个读该键的代码**"（命中全是注释、docstring 与真源自身） |
| 4 | "`blocked_hint` 只命中 `criterion_effectiveness_guard.py:204`…**11 条**" | **我的 `:105`/`:188`** | `/usr/bin/grep -rn` → 代码落点实为 **`:25`（规则表）+ `:218`（仅非空校验）**，**另有第三处 `scripts/valuelayer/completeness.py:1133`**（注释自称"专属"）；`criterion_counterexamples.yaml` 的 `blocked_hint:` = **15 条**（`/usr/bin/grep -c` = 15 / rc=0） | ⚠️ **我错**（行号、条数、落点数三处）→ **已就地更正**；结论方向不变且**更强** |
| 5 | "`grep -n \"injection\\|verify.py\" run_all_gates.py / pre-commit.sh` → **无匹配**" | `ws_audit_quota11_recheck_report.md:170,171` | **按原文写法**（bare + `\|`）→ **rc=1、无输出（假零）**；换 `/usr/bin/grep -nE 'injection\|verify\.py'` → **`run_all_gates.py:47` 命中 `("injection_guard.py", …)`**、**`pre-commit.sh:95` 命中 `run_gate "injection_guard" …`**；地板 `guard` = 17 / `run_gate` = 15 | ❌ **假零（新发现）**。★ **该假零支撑的结论方向恰好正确**（这两处确实没有 `verify.py`），⇒ **"碰巧正确的假证据"**（见下） |
| 6 | 两引擎对照："真值 2 / rc 0" vs "包装器 0 / rc 1 ⇒ 假'无匹配'" | `ws_ch13pre_rule_key_alignment_report.md:478-481` | `/usr/bin/grep -c 'def _analyze_module\|class _ModuleReads' rule_key_alignment_guard.py` = **2 / rc=0**；bare `grep -c` 同模式 = **0 / rc=1** | ✅ **逐字复现** ⇒ **范式样例**（两引擎并列 + 真值） |
| 7 | "`05_价格与市场预期研究/02_实现方案.md:21` **逐字就有**这三个键名"（= 自己给出的地板真值） | `x13r_dual_transcription_diff_audit.md:345` | `git cat-file -e HEAD:<path>` **存在** ✅；`/usr/bin/grep -n 'scenario_tag\|independent_judgment\|implied_ref'` → **`:21` 命中，逐字含 `independent_judgment`/`implied_ref`/`scenario_tag`**；地板 `wc` = 479 行 | ✅ **复现** ⇒ **范式样例**（零命中**自带**地板真值） |
| 8 | "macOS `grep` 的 BRE **不支持 `\|`**"／"**BSD `grep`** 的 BRE 不支持 `\|`" | `x13r_dual_transcription_diff_audit.md:338-342`、`ws_ch13e_benchmark_fields_report.md:225` | `/usr/bin/grep --version` = **`BSD grep, GNU compatible`**；`/usr/bin/grep -c 'a\|b'` → **4 / rc=0** ⇒ **BSD grep 的 BRE 完全支持 `\|`** | ❌ **归因错（新发现）**：真因是 **broker shim 的 `toybox`**（"Bash 里的裸 `grep` 不是 `/usr/bin/grep`"），**不是 BSD grep** |
| 9 | `口径 16`：pre-commit 不跑 pytest（我在 §⑥ 第 8 条也引用过） | 我的 §⑥ + `ws_audit_quota11_recheck_report.md` | **剔注释后** `/usr/bin/grep -vE '^[[:space:]]*#' pre-commit.sh \| /usr/bin/grep -cE 'pytest\|run_all_gates\|verify\.py'` → **0 / rc=1**；地板同行 `run_gate` = 15；`run_all_gates.py` 内 `pytest` **rc=1**、地板 `guard` = 17 | ✅ **成立**（但顺带更正我"**13** 个 `run_gate`"→ 对象 `2f62f5d` 实测 **14 个 `run_gate` 调用**） |
| 10 | "第一次报'成功'但复核时**内容未变**（`grep` 无匹配、`len(GUARDS)` 仍为 20）" | `ws_real_collect_2_report.md:580` | 属**自曝事故**，不是对代码库的缺陷断言；且它自带**独立旁证**（Python `len(GUARDS)`）⇒ 该 grep 零命中不是唯一证据 | ⚠️ **不需改判**；建议其作者补一句"该零命中由 Python 读数独立支撑" |

⇒ **汇总：✅ 复现 4 条（含 2 条范式）、⚠️ 过期/需精化 4 条、❌ 假零或归因错 2 条**。**我自己的报告里有 3 处过期/错读数**（#2、#4、#9 的"13"）—— **已全部就地更正**（正是 `G-50`"改了一半"的反面：不留相反声明）。

### 二、★ 本轮新发现（比单条更正更值钱）

**（1）`Grep 工具（ripgrep）`也有自己的静默零 —— 对"不支持的语法"不报错、只给零**
```
Grep 工具 pattern = 零命中(?!X)   →  No matches found        ← 但不支持的 lookahead 本应报错
Grep 工具 pattern = 零命中        →  ws_degrade_contract_report.md:75/78/80/83/84 … 有命中（同目录）
```
⇒ **第三个引擎也有静默零**："换工具"**不是解药** —— bare toybox（`\|` 等 5 类）、BSD grep（`-E` 改语义：把 `\{2\}` 变字面）、ripgrep（lookahead/lookbehind + `\|` 是字面量）**三者各有各的坏法**，且**都表现为"看起来像零命中/看起来像成功"**。

**（2）★「碰巧正确的假证据」是一种新的传播形态（#5）**
`quota11` 那两条"无匹配"是**假零**，但它们支撑的结论**方向恰好正确** ⇒ 于是这条假证据**会一路被下游复用而不被察觉**（我 §⑥ 第 8 条引用的同一族结论就是这类）。⇒ 与 `G-62`/`G-63`/`G-64` 同族但**更隐蔽**：前几例是"判据恒真/恒假"，这一例是"**结论对、论证无效**"——**结论对所以没人去查论证**。

**（3）零命中结论的**最小可判定形式** = 五元组**
> **(输入 + 模式 + 引擎 + rc + 地板真值)**
只有"输入 + 模式 + 引擎"齐了，`0` 才有意义（#8 的两个"矛盾"读数**其实是同一语义在两个输入上的两种表现** —— 见 §⑨ 第六节 (7) 的就地更正）。建议 `V-10` 把这条写成**可检查的形式**（我 §⑥ 的"一条无例外规矩"即其摘要）。

### 三、★ 我不改他人文件 —— 需其作者（或 team-lead 派单）执行的更正清单

| 报告 | 位置 | 问题 | 建议动作 |
|---|---|---|---|
| `ws_audit_quota11_recheck_report.md` | `:170-171` | **假零**（bare `grep` + `\|`）；结论方向对但**论证无效** | 换 `/usr/bin/grep -nE` 重取读数（我已给出命中行 `run_all_gates.py:47` / `pre-commit.sh:95`），或**保留原读数并标明"该零命中系工具假零，结论另由…支撑"** |
| `ws_ch13e_benchmark_fields_report.md` | `:225` | **归因错**（BSD grep）+ **补救法不安全**（"一律 `grep -E`"） | 改为"**真因 = Bash 里裸 `grep` 是 broker 的 toybox**"，补救法改为 **`V-10`：地板真值 + 标引擎/方言** |
| `x13r_dual_transcription_diff_audit.md` | `:338-342` | 同上；**但它的载荷本身有地板真值（#7 ✅）**，故**只改归因与标题** | 标题"`macOS grep` 的 BRE 不支持 `\|`"→"**Bash 里裸 `grep`（toybox）不支持 `\|`**" |
| `ws_degrade_contract_report.md` | `:232` | "载体③在生产数据上**从不成立**"**已过期**（写路径现填 `output_refs`） | 标为历史态或改述；`:48` 的"在本单之前"可保留 |

### 四、覆盖声明（`G-03` 自用：不得把"未核"当"已核"）

- ✅ **已核**：上表 **10 条载荷**（逐条两引擎复算 + 地板真值 + rc）。
- ⚠️ **未核**：67 份报告中**其余"不存在 / 没有任何 / 未发现"型散句（数百处，多为叙述型用法）** —— **我一条都没有复算**，因此**不得**被读成"这些也没问题"。若 team-lead 要穷尽，建议按"**是否被下游引用为证据**"排序后分批（我的 4 步法可直接复用，单条成本 ≈ 2 条命令）。
- ⚠️ **方法学局限**：我的分流（载荷型 vs 叙述型）**含人工判断**；若有异议，请按 `§②` 的原文行号复核，不采信我的分类结论本身。

---

## ⑪ `G-44` 端到端**独立**复验（team-lead 裁决第 1 项；排在 §⑩ 之后执行）

### 〇、对象 / 取样时刻 / 方法与独立性声明（口径 10）

| 项 | 值 |
|---|---|
| 对象 | 工作树 `/Users/gaza/Developer/InvestSigh`，`git rev-parse HEAD` = **`1dd87f3a24af9d3d34528b8f455dee2c39b46842`** |
| 取样时刻 | `2026-09-16 23:38:57 CST`（`date '+%Y-%m-%d %H:%M:%S %Z'`） |
| 器具 | `/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`（**不用 pytest**，不跑任何测试目录 —— 排他窗口与本单无关） |
| 被测面 | `Pipeline(root).run_daily(date(2026,9,16))` × 2，**直接读 `RunResult` / `StepResult`** |

**独立性**（实现方不得自证；`ws-daily-fix-engineer` / `ws-step56-skipped` 都不做本项）：

- 我**不 import** `tests/injection/test_step56_skipped_wiring.py`，也**不调用**它的 `_seed_prices` / `_seed_benchmark_object` / `_blocking_causes`；
  seed 逻辑是我据夹具与规则原文**自己转写**（`/tmp/investsigh-audit-b11/g44_run.py`）。
- 副本契约（`code_root`）也是我自己转写的（`g44_build.py`）：22 条 stem 归零 + `_ENSURE_DIRS` + 全树可写。
- **绝不碰真仓库**：所有写入都在 `/tmp/investsigh-audit-b11/g44-*/system/`；真仓库 `git status --short` 除我那份报告外无改动。

副本构建的**地板真值**（`g44_build.py` 实测输出）：

```
[build] JSONL_STEMS=22 条；写空 22 条；原本就不存在（由本步骤新建）=[]
[build] 清空后仍非空的 stem=（无）
[build] ★ 落在 stem 清单之外的 facts/*.jsonl（清空不到）=（无）
[build] raw/ 内容=[]
```

### 一、五个场景 × 实测读数（全部逐条附退出码）

每条命令形如 `cd /tmp/investsigh-audit-b11/g44-<case>/system && python g44_run.py <case> > out.txt 2>&1; echo EXIT=$?`，
五个 case 的 **EXIT 全为 `0`**（脚本自身判定通过；`rv-*` 的 `✅` 由脚本内断言给出）。

| # | 场景 | 输入（真源） | run#1 step5 / step6 | run#2 step5 / step6 | 结论 |
|---|---|---|---|---|---|
| 1 | `main`（**官方正例前提**） | prices 24 行 / 2 证券（`usAGIX`+`usDEMO`）+ benchmark 补 `security_id=usAGIX` | `ok` 3/+0 ；`ok` 1/+0 | `ok` **0 / skipped 3** ；`ok` **0 / skipped 1** | ✅ |
| 2 | `rv-noprices`（反向①） | benchmark 在、**prices 空** | `gap` 0/0；`gap` 0/0 | `gap` 0/0；`gap` 0/0 | ✅ 仍判 gap |
| 3 | `rv-noboth`（反向②） | **两者都空** | `gap` 0/0；`gap` 0/0 | `gap` 0/0；`gap` 0/0 | ✅ 仍判 gap |
| 4 | `nosecid`（**生产可达态**） | prices 24 行 / 2 证券 + benchmark **原样**（**不加** `security_id`） | `ok` **2**/0 ；`gap` 0/0 | `ok` **0 / skipped 2**；`gap` 0/0 | ✅ |
| 5 | `pfail`（部分上游失败） | prices **仅 usDEMO** + benchmark 带 `security_id=usAGIX` | `ok` 1/0 ；**`failed`** | `ok` 0/**skipped 1**；**`failed`** | ⚠ 见 §三-2 |

（表头记法：`status` + `produced 数` / `skipped 数`。第 1 行的 `3/+0` 即 `produced=3, skipped=0`。）

**场景 1（`main`）的逐字读数**（节选，完整见 `/tmp/investsigh-audit-b11/out-*`）：

```
[run#1] blocked=True degraded=True changed=False signals=1
    step 5 ok     produced=3  skipped=0     step 6 ok     produced=1  skipped=0
    [step 5 明细] produced=['dv-benchmark_return-p01-compute-v1',
                            'dv-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1',
                            'dv-total_return-usDEMO-2026-04-01..2026-09-15-compute-v1']  skipped=[]
    [step 6 明细] produced=['rec-usDEMO-2026-04-01']  skipped=[]
    blocked 成因=['step 2…gap','step 3…gap','step 4…gap','step 7…gap','step 8…gap']   ← **不含 5/6**
    step5/6 gap=[]        {'derived_rows': 3, 'recommendation_rows': 1}
[run#2] blocked=True degraded=True changed=False signals=0
    step 5 ok     produced=0  skipped=3     step 6 ok     produced=0  skipped=1
    [step 5 明细] produced=[]  skipped=['dv-benchmark_return-p01-compute-v1',
                                        'dv-total_return-usAGIX-…','dv-total_return-usDEMO-…']  gap=None
    [step 6 明细] produced=[]  skipped=['rec-usDEMO-2026-04-01']  gap=None
    blocked 成因=['step 2…','step 3…','step 4…','step 7…','step 8…']   ← **不含 5/6**
    step5/6 gap=[]        {'derived_rows': 3, 'recommendation_rows': 1}   ← 重跑**一行未增**
==> main 判定：✅ 全部成立（无一条被推翻）
```

**这是我第一轮做失败的地方**，如实登记：我最初拿**主仓真数据**（91 行 `facts`）当 `G-44` 场景，
三组输入下 step 5 全是 `produced=0 skipped=0` ⇒ **没有一例是"幂等命中"** ⇒ 那版场景**无法判别** `G-44`。
主仓真数据不满足 step 5 前置（`chain_steps.py:357-361` 的上游说明：需要基准对象 + `prices`）。
**"我跑了端到端"不等于"我跑到了要测的那条路径"** —— 这一条与 `G-03`、与 `§⑩` 的"假零"同族。

### 二、判定：四条断言逐条成立，我**没能推翻** `G-44` 的修复

我在脚本里写的是**自己的**断言（不是抄官方用例文本），全部落在同一批观测量上：

| 断言 | `main` | `nosecid`（生产可达态） |
|---|---|---|
| 首轮 `status=='ok'` 且 `produced` 非空（**判别力前提**：一个永不写的实现骗不过） | ✅ 3 / 1 | ✅ 2 |
| 重跑 `status=='ok'`（不再被误判 `gap`） | ✅ | ✅ |
| 重跑 `produced==[]` | ✅ | ✅ |
| 重跑 `skipped` 非空 **且 `set(skipped)==set(首轮 produced)`** | ✅ 3=3 / 1=1 | ✅ 2=2 |
| `produced ∩ skipped == ∅`（`G-42` 互斥） | ✅ | ✅ |
| `result.gaps` 里 **step 5/6 的条目为空**（旧缺陷下重跑会多 4 条：2 适配器 + 2 `G1-05`） | ✅ r1/r2 都 `[]` | ✅ |
| `blocked` 成因**不含** step 5/6，且含 2/3/4/7/8（前提未漂移） | ✅ | ✅ |
| 重跑不新增 `derived`/`recommendation` 行 | ✅ 3→3 / 1→1 | ✅ |

**反向对照（关键，证明 `skipped` 出口没把"空执行"守卫削弱成恒真）**：

- `rv-noprices`：`assert _lines(facts/prices.jsonl)==0` 通过；两轮 step5/6 **`produced=[] 且 skipped=[]`**、`status=='gap'`、`gap` 非空；
  每轮 `step5/6 gap` **4 条**（`G1-05 第 5/6 步…` + `step 5/6 (…): …`）⇒ **真·空执行仍被拦**。
- `rv-noboth`：连基准也没有，同样两轮都 `gap` 且两集空 ⇒ **"无被检对象"这一支也没被 `skipped` 洗白**。

**分布判别（官方用例没有的一条，我自己加的）**：
副本上跑完 `main` 两次后，**只删掉 1 行 `derived/derived_values.jsonl`**（`dv-benchmark_return-p01-compute-v1`）再跑：

```
已删 1 行（derived_id='dv-benchmark_return-p01-compute-v1'）→ 剩 2 行
[分布判别] step5 第三次：produced=['dv-benchmark_return-p01-compute-v1']
                          skipped=['dv-total_return-usAGIX-…','dv-total_return-usDEMO-…']  status='ok'
✅ skipped 是**逐对象**判定（不是'全都算命中'的齐量出口）
```

—— 这一格是**专为证伪设计的**：若实现方把 `skipped` 写成"凡本轮考察过的对象一律算命中"，那么在"3 个对象里缺 1 个"的输入上，
它会给 `skipped=[3 个]` + `produced=[]` 并照样 `ok`，从而把**真实的缺失**藏掉。实测**不是**这种实现。

**结论（五档）：`G-44` 修复 = 【好】** —— 正向成立、反向成立、分布判别成立、生产可达态成立；我试了 5 个场景、含 3 个我自己构造的对抗输入，**没有一条能推翻它**。

### 三、★ 本轮**新发现**两条（都是我在构造"能证伪的输入"时掉出来的）

#### 新-1（**中高**）`G-44` 官方正例的 **step 6 半边**，其前提是一条 **schema 判为非法、且全仓无生产者**的基准行

> ★ **编号更正（2026-09-17 00:1x 补，对象 `main@8f3298d`）**：我在回报里曾提议本条编号为 **`G-65`**。实测 **`G-65` 已被他人占用**（`a797b28 feat(#96): G-65 可见性修复`，落在 `scripts/ops/gate_set_diff.py` / `pre-commit.sh` / `tests/guards/test_gate_set_visibility.py`）。`git grep -l "G-6x\b" HEAD -- system/` 实测：**`G-65` 占用；`G-66`/`G-67`/`G-68`/`G-69` 均空**。⇒ **本条建议改用 `G-68`**；另两条（`run_decide.py:462-463` 死代码 → **`G-66`**；`traceback.py:163` 认非真源 → **`G-67`**，本报告 §⑫ 已在用）不冲突。编号以 team-lead 裁定为准。

证据链（每条都有独立复算）：

1. **官方 seed 补的那个字段不在冻结模型里**：`test_step56_skipped_wiring.py:77` 写 `benchmark["security_id"]="usAGIX"`。
   实测（副本上直调 pydantic）：

   ```
   s1 = json.loads(open('facts/benchmarks.jsonl').read())
   Benchmark(**s1)  → ERR: benchmark_id Field required ; security_id Extra inputs are not permitted
   ```
   `schema/models.py:70-73`：`_Base.model_config = ConfigDict(extra="forbid", …)`。
2. **第二份 schema 同判**：`schema/jsonschema/facts.schema.json:384-604` 的 `Benchmark` 定义 —— `"additionalProperties": false`，
   `required: ["benchmark_id"]`，**`properties` 里没有 `security_id`**（两条独立路径一致）。
3. **没有任何生产者写这张表**：`/usr/bin/grep -rn '"benchmarks"' scripts/ schema/`（rc=0，8 条）逐条为
   `graph/adjacency.py:47`（边定义）、`compute/driver.py:251`（missing 列表）、`pricelayer/history_guard.py:353-354`（读）、
   `pricelayer/step.py:148`（扫描表）、`schema/models.py:1999` / `jsonschema:10089`（stem→模型表）、`stems.py:72`（清单）
   —— **全是读方/登记表，无一处写入**（地板真值：`scripts/`+`schema/` 里出现 `benchmarks` 字样的文件共 **12** 个，我已逐条枚举其字面量命中）。
   真仓库 `system/facts/benchmarks.jsonl` 当前 **0 行**。
4. **合规身份链断在一半**：`rules/benchmark.yaml:17` 注释逐字"指针：身份值只在 `rules/freeze.yaml::p01`"，
   而 `rules/freeze.yaml:28-40` 的 `p01` = `param: benchmark_id` / `suggested_value: AGIX`。
   `/usr/bin/grep -rn "benchmark_id_param_ref" scripts/ schema/ rules/`（rc=0，**7 条**）—— **无一处解引用**，
   全部只当**标签**用（`return_guard.py:121`、`returns.py:262`、`driver.py:194`、`run_decide.py:279-281`）。
5. **实测后果（`nosecid`）**：契约合规态（2 证券、基准行原样）下 —— step 5 `ok` 且 `produced=2`（两只 `total_return` 算得出，
   **`G-44` 的正向在这里是成立的**），但 **step 6 = `gap` / `produced=0`**：`_resolve_benchmark_security` 拿不到 `security_id`、
   行情又非唯一证券 ⇒ 返回 `None` ⇒ `securities_unresolved`。
   另一支兜底（行情里恰好只有 1 个证券）下 `_select_company_security` 必然返回 `None`（`others` 为空）⇒ **同样出不了建议**。

⇒ 合起来：**在契约合规态下，step 6 结构性无法产出建议**；官方那个"重跑不再被误判"的**step 6 半边**，
其成立条件是一条 **schema 两份载体都禁止的行**。这不是"测试写错了"，而是
**"测试的正例态落在契约之外"** —— 与 `G-48`/`G-50` 同族的形态：**实现/契约/验证三者对同一事实各说各的**。

★ 我**不主张**结论是"该加 `security_id` 字段"（那是设计裁定，不是审计能定的）；我主张的是三条可证事实：
（a）该行非法；（b）无生产者；（c）**step 6 的正向在合规态不可达** —— 因此**不能**用这条用例宣称"step 6 的 `G-44` 已验收"。
建议动作（给 team-lead 派单）：把该用例的 step 6 半边**显式降级**为"前提为契约外构造态"，或先裁定基准身份字段的载体再谈验收。

#### 新-2（**中**）`run_decide.py:462-463` 未捕获下标：承诺的优雅降级分支**不可达**，改为裸 `KeyError`

- 观测（`pfail` 场景，两轮都一样）：`step 6 status='failed'`，`error="KeyError: 'usAGIX'"`。
- 位点：`scripts/decision/run_decide.py:462-463` `company_prices = _as_of(series[company_security], …)` /
  `bench_prices = _as_of(series[benchmark_security], …)` —— **先下标、后判空**；
  保护分支 `if len(…)<2: return RunReport((), ("inputs_unavailable:insufficient_prices",)…)` 在 `:464`，**永远轮不到**。
- 而同文件 `:445-447` 的 docstring 逐字承诺："真源行情缺失 / 证券无法解析 / 窗口不足 2 点 → 返回
  `degraded=True` + `gaps=("inputs_unavailable:…",)`" ⇒ **承诺的分支是死代码**（对"证券在 `series` 里根本不存在"这一支）。
- **对照（同一情形、两层两做法）**：compute 层 `driver.py:279-292` 对同一情形（`scoped=[]` → `_resolve_window` 返回 `None`）
  **正确**记缺口 ⇒ `derived/compute_gaps.jsonl` 实测 **1 行**：
  `{"gap_id":"dv-gap-benchmark-p01-compute-v1","missing":["prices"],"reason":"p01: 证券 usAGIX 区间 [None..None] 内行情不足（<2 点）",…}`。
  即 **step 5 优雅降级、step 6 崩** —— 又一个"**同一语义、两处各写一套**"（`G-06` 家族）。
- **归因（不夸大）**：`git blame -L 455,466` 全部指向 **`09ab08f7`**（2026-09-16，`fix(decision): 生产输入改读真源…`），
  且 `git merge-base --is-ancestor 09ab08f7 f0d9ee2` 成立 ⇒ **本审计批次（`f0d9ee2..`）之前就存在**，不是本批引入。
  严重度不判高：`STATUS_FAILED` **不是** `ok`（`pipeline.py:219-226` 捕获后 `degraded=True` + blocking ⇒ `blocked`），
  属**响亮的失败**，只损失诊断质量（操作者看到 `KeyError: 'usAGIX'` 而非 `inputs_unavailable:insufficient_prices`）。
  ★ 触发前提是基准行带 `security_id` ⇒ 与"新-1"耦合：**靠一条契约外的行才能触发**。所以我把它记为**中**而不是高。

### 四、我自己的一处**仪器错误**（如实登记，`V-10` 自用）

`pfail` 首跑我打印了 `derived/gaps.jsonl 行数=0`，并据此写下"缺口**没有**静默"——
**这一半是我的路径写错**：缺口真源 stem 是 `DERIVED_GAPS_STEM = "compute_gaps"`（`scripts/compute/store.py:63`），
文件是 `derived/compute_gaps.jsonl`。改路径后实测 **1 行**（内容见上），结论方向恰好相同，但**当时的论证是无效的**。
—— 这正是"**匹配/未匹配到了别的东西、却当成证据**"的又一次现场（`V-10` 补充条的**第三形态：路径型假零**）。
我已把 `g44_run.py` 就地改正并**重跑**取新读数（上表场景 5 用的是改正后的输出）。

### 五、五档结论（本轮新增部分）

| 对象 | 判定 | 依据 |
|---|---|---|
| `G-44` 修复本身（step 5 / step 6 的 `skipped` 接线 + 适配器判据） | ✅ **好** | 5 场景 × 9 条断言全绿；含 3 条我自造的对抗输入（反向①②、分布判别）**均未推翻** |
| `G-44` 官方正例的 **step 6 半边** | ⚠️ **不够** | 前提是 schema 两份载体都禁止、且无生产者的基准行 ⇒ **合规态下 step 6 的正向不可达**（新-1） |
| `run_decide.py` 的"行情缺失"降级承诺 | ❌ **错**（分支不可达）/ 归因：**批次之前既存** | 实测 `KeyError`，承诺的 `inputs_unavailable:insufficient_prices` 是死代码（新-2） |
| 我对 `G-44` 的验收主张 | **✅ 采信**（仅就 step 5，以及 step 6 在"契约外构造态"下） | 见上表；**不**声称 step 6 在合规态已验收 |

**我试了但没能推翻的**（如实登记，界定结论强度）：① 我试图让 `skipped` 变成"齐量出口"（删 1 行 → 期望它骗过）——**未能**；
② 我试图用"基准与行情都不给"让守卫变恒真——**未能**；③ 我试图让重跑多写 `derived` 行——**未能**（3→3）。
④ 我**没有**跑到的：`resume` / 整步 `STATUS_SKIPPED`（裁定 `R1` 的整步粒度）、`scope` 参数分支、多基准对象（`benchmark_objects` 有 2 条，我只喂了第 1 条）、
以及 step 6 在**合规态下的正向**——因为它按新-1 判定为**不可达**，我**无法**给出"它其实能用"的对照。

---

## ⑫ 批次 14：`stage_gate` 已绑定判据的**双向实测**（team-lead 裁决第 3 项）

### 〇、对象 / 时刻 / 方法（口径 10）

| 项 | 值 |
|---|---|
| 对象 | 工作树 `main@1dd87f3a24af9d3d34528b8f455dee2c39b46842`，取样/执行 `2026-09-16 23:5x – 2026-09-17 00:1x CST` |
| 器具 | 副本内 `subprocess` 跑 **门禁本体**：`python scripts/delivery/stage_gate.py . --stage <stage>`（黑盒，**不 import 官方用例、不调 `run_gate_inproc`**） |
| 资产 | `/tmp/investsigh-audit-b11/b14_{build,run}.py` + `b14-*/system/`（均为副本；真仓库只被我读） |

**三相位**（每相位都先清空 22 条真源 stem 再播种）：
`legal`（合规输入）/ `inject`（**只**破坏该判据那一条轴）/ `neuter`（**同一 inject 输入** + 把该判据的检查**掏空**）。

★ `neuter` 是**判别力的关键**：它回答的不是"会不会红"，而是"**红是不是这处检查干的**"。
`G-16` 意义上，一个"永远红"的阶段什么都不证明；**掏空后反例失效**才证明这条判据是承重的。

### 一、★ 先更正**我自己接到的范围描述**（机器读数，不是我猜的）

`bound_criteria()` / `declared_criteria()` / `criteria_not_implemented()` 三函数地板真值（实跑）：

```
prep           declared(automated)=4   bound=4   not_implemented=[]
nvidia_sample  declared(automated)=4   bound=3   not_implemented=['evidence_locatable']
core_chain     declared(automated)=3   bound=1   not_implemented=['graph_and_ask_traceable','t01_t14_all_pass']
daily_run      declared(automated)=4   bound=4   not_implemented=[]
expansion      declared(automated)=3   bound=1   not_implemented=['investment_result_verifiable','research_standard_consistent']
```

⇒ 裁决里写的"`nvidia_sample` **四条**"应更正为 **3 条已绑定 + 1 条（`evidence_locatable`）声明为 automated 却未绑定**。
该未绑定条目**在合规数据下就是阶段② 那条唯一的 `[FATAL]`**（`G11-04`，`assert_criteria_implemented` 阻断）。
**⇒ 阶段② 的「合法态 ⇒ 仍绿」在 exit 级不可测量**（结构上不可能绿）；反向对照只能做在**判据级**：
"合规输入下该判据的**专属 hint 不出现**"。这与 `CONVENTIONS.md §二 G-03` 一致：**无被检对象 ⇒ 记 note，不计已核**。
另：`core_chain` / `expansion` 都各有 2 条未绑定 ⇒ 它们的 `exit` 同样**结构性≠0**。

### 二、五格实测结果（✅/❌ 逐格）

| # | 判据 | legal（专属 hint 缺席？） | inject（专属 hint 出现？） | neuter+inject（反例**失效**？） | 判定 |
|---|---|---|---|---|---|
| 1 | `nvidia_sample::six_step_chain_complete` | ✅ 缺席（`exit=1`，仅 1 条台账 FATAL） | ✅ 出现，且**只有本判据**（FATAL 1→2） | ✅ 掏空后 hint **消失**（FATAL 2→1） | **好** |
| 2 | `nvidia_sample::derivation_reviewable` | ✅ 缺席 | ✅ 出现（FATAL 1→4）**但同时打红 `ch4_depth`**（见 §三-3） | ✅ 掏空后本 hint **消失**（FATAL 4→2，ch4 那条仍在） | **好**（附共享载体观察） |
| 3 | `nvidia_sample::chapter4_g_depth` | ✅ 缺席 | ✅ 出现，且**只有本判据**（FATAL 1→3） | ✅ 掏空后 hint **消失**（FATAL 3→1） | **好** |
| 4 | `daily_run::task_state_auditable` | ✅ **`exit=0` / `FATAL 0`** —— **完整反向对照成立**（本批唯一能整绿的阶段） | ✅ `exit=1` / hint 出现；**两种违反形态都红**（值非法 + 整键缺失，见下） | ✅ 掏空后 `exit=1 → 0` | **好**（本批最强） |
| 5 | `expansion::review_append_only`（"三层复盘缺层"轴） | ✅ 缺席（`exit=1`，3 条结构性 FATAL） | ✅ 出现（FATAL 3→4） | ✅ 掏空后 hint **消失**（FATAL 4→3） | **好** |
| 6 | `nvidia_sample::evidence_locatable` | — | — | — | **未做**：**声明 automated 但未绑定** ⇒ **无被检对象**（`G-03`）⇒ 记 note，**不计已核** |

**第 4 格的逐字读数**（`daily_run`，唯一能整绿的阶段）：

```
[legal ]  exit=0  FATAL 行数=0    hint 出现=False
          note: daily_run: PASS   /  scanned daily_run.tasks: 1  criteria_bound: 4
[inject]  exit=1  FATAL 行数=1    hint 出现=True
          [FATAL] daily_run @ facts/tasks.jsonl:0 — task_check_2026-09-16_full 的
                  status='totally_bogus_status' 不在 TaskStatus 合法取值域内
                  （合法值 = ['done','failed','pending_evidence','queued','researching']）⇒ 任务状态不可核
[neuter]  exit=0  FATAL 行数=0    hint 出现=False        ← 注入仍在，检查被掏空 ⇒ 反例失效
[第二形态] exit=1  FATAL 行数=1   hint 出现=True
          [FATAL] … 的 status=None 不在 TaskStatus 合法取值域内 …         ← **整键缺失也被抓**
```

**注入与掏空的大前提**（可核）：每条 inject 都先证明"deviation 只加在我要测的那条轴上"——
`six_step` 我**刻意避开** `driver_model`（它同时喂 traceback 的 `assumptions` 要素，会顺带打红 `derivation_reviewable`；
我第一次正是这样失手的，见 §四），改用 `business_mechanism`；`neuter` 每次都**断言恰好替换 1 处**（`occurrences=1`），否则报"我的仪器无效"。

### 三、本轮新发现

#### `G-67`（**中**）`derivation_reviewable` 的「计算」载体判定**比声明的真源宽**：认**非真源**文件

- 声明（`Ch9 §3.3.3`）：`DerivedValue` 唯一真源 = `derived/derived_values.jsonl`（`scripts/compute/store.py::values_path()`）。
- 实现（`scripts/trace/traceback.py:159-168`）：`_find_derived()` 用 **`for path in sorted(ddir.rglob("*.jsonl"))`** ——
  扫 `derived/` 下**任何** `.jsonl`，只要有一行 `derived_id` 命中且带 `formula/operands/method_version` 就算"有计算底稿"。
- **判别探针（我自造，官方没有）**：真源 `derived_values.jsonl` **置空**，只在一个**非真源**文件 `derived/trace.jsonl` 里放同 id 同形状的一行：

  ```
  [seed] {'derived_values_rows': 0, 'trace_rows': 1, 'inject': '仅非真源 trace.jsonl 有该行'}
  [gate] exit=1  FATAL 行数=2
        hint[derivation] '四要素' 出现=False      ← ★ 判据**放行**了
        hint[ch4_depth]  'Ch4 §G 形式完备性未过' 出现=True（`has_derivation`：合格推导 0 条 < 1）
  ```
  ⇒ **同一个事实，两条判据给出相反结论**（四要素说"有计算"，`Ch4 §G` 说"合格推导 0 条"）——`G-06` 家族。
- 而 `derived/trace.jsonl` 在本仓**既无生产者、也无消费者**（两条独立路径：`/usr/bin/grep -rn "trace\.jsonl" scripts/ schema/ registry/ rules/ tests/` → rc=0，仅 **3** 条且**全在测试文件**；
  `Grep` 工具全 `system/` 搜 → 只多一条报告散文。`stage_gate` 那次 `FATAL` 就是 `_find_derived` 的 glob 顺带读到的）。
- ★ 附带事实（更值钱）：官方 `derivation_reviewable` 反例的**合规侧**（`_nvidia_compliant`，`tests/…:110-116`）
  **只写** `derived/trace.jsonl`、**不写** `derived_values.jsonl` ⇒ 它"合规"与"违例"两态在 **`facts/` 真源层面完全相同**，
  差异只在一个**无消费者的派生文件**上。该反例**确实**能红（因为清空后 `derived/` 里一行都没有），
  但它证明的是"`derived/` 下任何 jsonl 都没有该行 ⇒ 红"，**不能**证明"**真源**里没有该计算 ⇒ 红"。
- 严重度记**中**：生产不会写 `trace.jsonl`（无生产者），故真实触发概率低；但它是"**判据的被检面比声明的宽**"的实体，
  且已把官方反例的因果链**钉在一个非真源文件上**——该文件一旦被清理，反例会漂移。

#### 观察（**非缺陷**，但会影响今后归因）`derivation_reviewable` 与 `chapter4_g_depth` **共享被检载体**

注入 `derived/` 缺失时**两条**判据同时红（实测 FATAL 1→4）。二者都读"`derived/` 中的合格推导"，
一个是建议侧反查、一个是 baseline 侧形式完备性。⇒ 该载体上的注入**无法只在一条判据上归因**；
判据级归因必须靠 **hint**（`blocked_hint`），不能靠"阶段变红"。这条已写进本节口径，供 `V-11` 一类核对件复用。

### 四、我自己的两处**仪器错误**（如实登记，`V-10` 自用）

1. **`neuter` 相位第一版喂的是 `legal` 输入** —— 那样"hint 消失"是**必然**的（本来就没注入），**零判别力**。
   改法：`neuter` 必须与 `inject` **同输入**，只掏空检查。改后第 1/3/4/5 格才真正证明"承重"。
2. **在**已经被掏空的副本**上跑第二违反形态 → 得到假绿（`exit=0 / FATAL 0`）**，
   我一度以为抓到了门禁缺陷（"整键缺失不被抓"）。**根因是我自己**：`neuter` 已把该副本的
   `stage_gate.py` 改成 `if False:`，我又拿它测"检查是否生效"。在**干净副本**（`b14-ts2`）重测：
   `exit=1`、`status=None` 被抓 ⇒ **官方登记表"两种形态都 → exit 1"的说法成立**。
   —— 与 §⑪-四 同族：**我的仪器状态被我自己污染，却当成被测对象的属性**。

### 五、五档结论（批次 14）

| 对象 | 判定 | 依据 |
|---|---|---|
| `nvidia_sample` 三条**已绑定**判据（`six_step` / `derivation` / `ch4_depth`） | ✅ **好** | 三格 legal 缺席 + inject 出现 + neuter 失效；`ch4_depth` 是批次 13-A 新绑的，判别力**已独立证实** |
| `daily_run::task_state_auditable` | ✅ **好**（本批最强） | **唯一**能做完整"合规 `exit=0` / 违例 `exit=1` / 掏空 `exit→0`"三段对照的判据；两种违反形态都红 |
| `expansion::review_append_only`（三层缺层轴） | ✅ **好**（判据级） | legal 缺席 / inject 出现 / neuter 失效；阶段级 `exit` 因两条未绑定判据结构性≠0 |
| `nvidia_sample::evidence_locatable` | ⚠️ **未做**（`G-03` 记 note） | 声明 automated 但**未绑定** ⇒ 无被检对象；它同时是阶段②结构性红的唯一成因 |
| `G-67` | ⚠️ **不够**（新，中） | 载体判定 `rglob("*.jsonl")` 过宽，实测真源空而判据放行；官方反例的合规侧只靠非真源文件 |

### 六、★ 时效核对件（`V-11` 规矩 5）——**并给该规矩一处机器更正**

★ **先说一件当晚发生的事**：我做完 §⑫ 后复核时效，发现 **`main` 已从 `1dd87f3` 推进到 `472b17c`**
（`472b17c58e13179bb03b760e502aea12bca160e8`，`2026-09-17 00:02:13 +0800`，`Merge branch 'ws/fixture-cost'`；
分支 `main`；`git log --oneline 1dd87f3..HEAD` = **81 条**）。**这正是 `V-11` 要防的事** —— 所以我没有"顺手沿用旧读数"，而是逐对象做了核对。

**核对结果（两口径并列，我采内容级）**：

| 对象文件 | ① 含合并 `git log <SHA>..HEAD -- f` | ② `--no-merges` | ③ 内容级 `git diff <SHA> HEAD -- f`（行数） |
|---|---|---|---|
| `system/scripts/delivery/stage_gate.py` | **1** | **0** | **0** |
| `system/registry/criterion_counterexamples.yaml` | **1** | **0** | **0** |
| `system/schema/models.py` | **1** | **0** | **0** |
| `system/schema/jsonschema/facts.schema.json` | **1** | **0** | **0** |
| `system/scripts/decision/run_decide.py` | 0 | 0 | 0 |
| `system/scripts/trace/traceback.py` | 0 | 0 | 0 |
| `system/registry/delivery.yaml` / `rules/benchmark.yaml` / `rules/freeze.yaml` | 0 | 0 | 0 |

那 4 个"1 条"**全部是同一个提交**：`9c775ca Merge branch 'main' into ws/ch2-rules`。

★★ **结论（对 `V-11` 规矩 5 的更正建议，正是我"没能力自证时先收紧自己"的那一类）**：
`V-11` 规矩 5 现在写作"形如 `git log <结论SHA>..HEAD -- <对象文件>` 输出为空；不为空则重取或降级"。
本仓实测：**合并提交会让它假阳性**（该文件的内容在两棵树里逐字相同，`git diff` 0 行）。
建议改为**内容级**：

```
git diff --quiet <结论SHA> HEAD -- <对象文件>     # 退出码 0 = 内容未变 ⇒ 结论仍时效
# 或退一步：git log --no-merges <结论SHA>..HEAD -- <对象文件>
```

**我自己的处置**：§⑪ / §⑫ 的**生产侧**对象（`stage_gate.py` / `traceback.py` / `run_decide.py` / `registry/*` / `schema/*` / `rules/*`）
按上述内容级核对 = **0 行差异 ⇒ 时效通过**，结论**不需要**降级为历史态；
但那 4 个文件的**提交计数**读数是"1"，**我不采信它**（已诊断出真因是合并提交，不是内容漂移）。
★ 另：`§⑪` 里引用的 **测试侧**文件（`test_step56_skipped_wiring.py` / `test_criterion_effectiveness.py`）
**不在我副本内**（我 build 时跳过 `tests/`）⇒ 这两份的"我没测到"与"我没比对过当前 HEAD 版本"**都要说清**：
§⑪/§⑫ 中凡引用它们的内容，**只作"我读过并转写其前提"的用途，不作已验收证据**。

★ **第二次核对（更晚的 HEAD）**：此后 `main` 又推进两次 —— `472b17c` → `d4a6d5b` → **`018f4c3`**
（`git log --oneline 1dd87f3..HEAD` 现为 **83** 条；`018f4c3` 标题即 `docs(conventions): V-10 补「注入实验必须先断言注入成功」+ V-11 规矩5 机制改为内容级（路径级会假阳性）` —— 即本轮更正已被采纳入纸）。
**内容级复核（`00:04:14 CST`，对象 `018f4c3`）**：`stage_gate.py` / `traceback.py` / `run_decide.py` / `chain_steps.py` / `compute/driver.py` / `compute/store.py`
的 `git diff 1dd87f3 HEAD -- <f>` **全部 0 行** ⇒ **§⑪ / §⑫ 结论在新 HEAD 下仍时效**，不需要降级。

---

## ⑬ `#69` 四条命令**重跑**（team-lead 裁决第 4 项）—— 结论：**旧读数已整体漂移，方向全部是"已修"**

### 〇、对象与时刻（口径 10）

| 项 | 值 |
|---|---|
| 对象 | 工作树 `main` @ **`d4a6d5be6dddd1996f950a04187ed4decfde541a`**（四条命令执行时；随后又推进到 `018f4c3`） |
| 取样时刻 | **`2026-09-17 00:03:57 CST`** |
| 被复核对象 | `system/reports/ws_ch2_rules_consumption_review.md`（**他人文件，我不改**）§12.1 / §12.2 |
| 方法 | **逐条重跑原命令**，与旧读数逐字对照，**不复用旧读数** |

### 一、逐条对照

| # | 命令 | 旧读数（该报告原文） | **新读数（`d4a6d5b`，00:03:57）** | 判定 |
|---|---|---|---|---|
| 1 | `git show main:system/rules/valuation-methods.yaml \| sed -n '74,78p'` | 4 行：`default_count: 3` / `max_count: 5` / `selection: "代表解 + 区间包络"` / `overflow: fold` | **5 行**，多出 **`must_show_multiple: true  # ★ 语义键（§B.1 逐字）…`** | **★ 漂移（已修）** |
| 2 | `git show main:system/scripts/pricelayer/solver.py \| sed -n '79,85p'` | `DEFAULT_DISPLAY_CAP = 3` + 一句 docstring | 同一常量，docstring 改为 **"★ 真值取自 `rules/valuation-methods.yaml::solution_set_display.default_count`（现为 `3`）；本常量仅作规则文件/该键缺失时的回落，并由 `check` 的绑定断言核『代码默认值 == 文件真值』"** | **★ 漂移（已修）** |
| 3 | `PYTHONPATH=. python3 -c "…inspect.signature(solve_implied_requirements)…"` | `3 5 2` / `{'max_grid_points': 256, 'display_cap': 3, 'computed_at': None, …}` | `3 5 2` / `{'max_grid_points': 256, **'display': None, 'display_cap': None**, …}` | **★ 漂移（已修）**：`display_cap` 默认值由**硬编 `3`** → **`None`**（值改由**规则读口**注入） |
| 4 | `git grep -n 'solution_set_display' main -- system/scripts system/tests` | **`exit=1`（零命中）** ⇒ 报告据此判"`rules` 那份装了、**零消费者**"、"`G-06 双份`当场成立" | **`rc=0`，40+ 命中**：`solver.py`（`RULE_KEY_SOLUTION_SET_DISPLAY` / `load_solution_set_display` / `check` 绑定断言）、`order_guard.py:423/433/435/461/466`、`tests/pricelayer/test_solver.py`（12+ 处，含"删键 ⇒ `exit 1`"反例）、`test_order_guard.py` | **★ 漂移（已修）**：**"零消费者"已不成立** |

### 二、归因

```
$ git log --oneline -3 -S "load_solution_set_display" -- system/scripts/pricelayer/solver.py
9552e8c fix(pricelayer): 修「夹具与真文件不同源」两处（G-43/G-45 同族）+ 四组规则↔代码机器绑定

$ git log --oneline -3 -S "must_show_multiple" -- system/rules/valuation-methods.yaml
bef9628 feat(rules)+docs: R8-3 收口 —— (1) solution_set_display 增语义键 must_show_multiple=true（§B.1 逐字），
        数值下界 2 改由该键派生（避免同事实两处）；(2) 订正任务卡：删除被证伪的「grep 零引用 = 死常量」括注
        + 落点由 scenario.yaml 更正为 valuation-methods.yaml + 记 max_grid_points 前瞻风险
```

- `9552e8c` 引入**唯一读口** `load_solution_set_display` ⇒ 命令 4 由 `rc=1` 变 `rc=0`。
- `bef9628` 加 `must_show_multiple: true`（`§B.1` 逐字）、**数值下界改由该键派生**、并**订正了任务卡里那句被证伪的括注** ⇒ 命令 1/2/3 的漂移。

### 三、判定与处置

| 对象 | 判定 |
|---|---|
| 该报告 **§12.2(b)**（"代码侧 ❌ 未做 / `rules` 那份一行代码都不读 / `G-06 双份`当场成立"） | ❌ **已失效 ⇒ 按 `V-11` 显式降级为历史态** |
| 同报告 **§12.2(d)**（"`§B.1` 的『必须展示多组解』在 `rules/` 里没有任何载体"） | ❌ **已失效 ⇒ 历史态**（`bef9628` 已落该键，且下界 `2` 改为**派生**） |
| §12.2(a)/(c)/(e) | **未复核**（裁决只点四条命令）⇒ **不计已核**（`G-03`） |
| 命令 1–4 本身 | ✅ **全部重跑完毕**，逐字对照如上 |

★ **我不改他人文件** ⇒ 上述"降级为历史态"**需其作者（或 team-lead 派单）**在该报告两处就地加一句时效标注，
形如：**"本节对象 = `<该报告写作时的 main SHA>`；截至 `bef9628`/`9552e8c`，(b)(d) 两条已闭合，本条为历史态。"**

★ 本格再次印证 `V-11` 的必要性：**该报告写成到我复核之间 `main` 至少推进了 83 条提交**。
若按裁决前的习惯引用旧读数，我会把两条**已修好**的缺陷继续当"当前缺陷"报出去 —— 这是**双向**的错：
既冤枉实现方，也让真正当前的缺陷失去注意力。

---

## ⑭ `ws/verify-shard` 在当前 HEAD 重判 + 悬挂引用排除（team-lead 裁决第 5 项）

### 〇、对象与时刻（口径 10）

| 项 | 值 |
|---|---|
| 对象 | 工作树 `main` @ **`018f4c367160fc9917df4a7da1a4790510188d39`**（`git log --oneline -1` 实测） |
| 取样时刻 | **`2026-09-17 00:04–00:07 CST`** |
| 被重判对象 | `system/reports/ws_verify_shard_report.md`（906 行，**在 main**）+ `CONVENTIONS.md::V-02` 的批次表 |
| 方法 | **不跑 pytest**（排他窗口）⇒ 只做**可静态复算**的项：`verify.py --list`、`INJECTION_SHARDS`/`BATCHES` 现读、AST 计数、`.git` 视角核对 |

### 一、逐条重判（可静态证的四项）

| 断言 | 现读数（`018f4c3`，00:04 CST） | 判定 |
|---|---|---|
| "`tests/injection/` 切成多片"——**片数** | `INJECTION_SHARDS` = **7**（`injection-a`…`g`）；`verify.py --list` 也逐行列出 7 片 | ✅ **好**（与 `V-02` 表 7 行一致） |
| **每片 300s** | `BATCHES[各片].timeout = 300.0` ×7；`V-02` 表 7 行均为 300s | ✅ **好** |
| **文件集**：目录里的用例文件是否**全被覆盖**、片间**不重复** | 7 片去重文件 = **16**；`tests/injection/` 下 `test_*.py` 实际 = **16**；**未被任何片覆盖的文件 = 无** | ✅ **好**（这条最关键：`G-03` 意义上的"没有静默漏跑的文件"成立） |
| **用例数** | 我的 AST 口径（`def test_*`，不跑 pytest）= **195**（27 片分布：a24/b34/c31/d29/e30/f24/g23） | ⚠️ **与其报告所写 205 相差 10**（见 §三） |

### 二、机器绑定是否真的在守（这才是"重判"的重点）

`tests/injection/test_shard_coverage.py`（390 行，**在 main**）实测断言面：
`INJECTION_SHARDS` 非空 / 名字都在 `BATCHES` / 都在 `ORDER`（否则 `--batch all` 会**静默跳过**）/
每片目标是**显式文件路径** / **每个注入测试文件都被某片覆盖**（`:266`）/ **片间两两不相交**（`:293`）/ **每片用例数在配额内**（`:309`）/ 配额归因与缺 pytest 归因**绝不放行**（`:340`/`:369`）。

⇒ **它钉的是"结构不变量"（覆盖、不相交、配额），刻意不钉绝对数字** —— 这与 `V-02` 表头自述"**刻意不写批次数**，数字只留在各自真源里"是同一教训（批次 7 审计）。
**这个设计我判 ✅ 好**：它使"新增片/移动文件"必须同步真源，而不是同步一句文案。

### 三、★ 由此得到的一条**具体缺口**（属报告级，非机器绑定级）

`ws_verify_shard_report.md` 与若干引用它的文字里出现过 **"205 例 / 16 文件 / 7 片"** 这样的**数字三连**。
其中 **7 片 ✅、16 文件 ✅** 我复现；**205 例我复算不得**（AST 口径 195）。
两种可能我**不下断言**（无法区分）：① 口径不同（他们可能数的是 pytest **收集数**，含参数化展开；我数的是 `def test_` 个数）；
② 期间真的删/并了 10 例。
⇒ 按 `V-02` 表自己的教训（**"手写的数会随新增批次静默过期"**），建议：**把"205 例"改成口径声明**（例如"截至 `<SHA>`：7 片 / 16 文件；用例数见 `pytest --collect-only`，不在文案里写死"）。
★ **我不改他人文件** ⇒ 这条同样需要其作者或 team-lead 派单执行。

### 四、悬挂引用排除（我报告里的**逐条**核对）

**方法**：把我报告里所有形如 `` `xxx.py:12` `` / `` `reports/yyy.md:34` `` 的路径抽取出来，逐条 `git cat-file -e HEAD:<path>`。

```
共抽取候选路径 22 条（去重后）；在 main: 22 / 不在 main: 0
```

⇒ **我报告里没有悬挂引用**（22/22 都在 `main@018f4c3`）。

★★ **换独立路径复算（2026-09-17 补做，对象 `main@af20ebc`，与上法是两条独立路径）**：上法只抽了 22 条，且用 `git cat-file -e`（**答"这个路径在这个 commit 里有没有 blob"**）。补做改用 **`git ls-tree -r --name-only <SHA>`** 建**全量清单**再判**集合归属**，并把抽取面**扩到全部反引号路径（85 条去重）**：
```
抽取去重路径 = 85
在 main（含经 basename 消歧的简写）= 72
不在 main（工作树有、main 无）= 1        ← system/state.json，见下
歧义（多份同名且都在 main 中）= 2        ← conftest.py(4 份) / store.py(2 份)，靠上下文消歧
无法解析（仓内无此文件）= 10
```
**那 1 条"不在 main" + 10 条"无法解析"逐条解释，全部为合法，非悬挂**：
| 路径 | 为何不在 main | 性质 |
|---|---|---|
| `system/state.json` | `.gitignore:16` 逐字排除（运行态，`_COPY_SKIP` 同名单） | ✅ **我引用它是对的**；"必须在 main"这条判据**对运行态文件本身是错的** ⇒ 这是**我的检查器的假阳性**（与第 4 处同族：**先怀疑自己的判据**） |
| `derived/derived_values.jsonl` / `derived/trace.jsonl` / `trace.jsonl` / `derived_values.jsonl` | 该 stem 指向的文件**全仓尚未创建**（`main` 的 `system/derived/` 只有 `.gitkeep` 与 `compute_gaps.jsonl`；工作树同） | ⚠️ **我引用的是"符号所指"、不是"已存在的文件"** ⇒ **本行即该口径的登记处**：凡本报告出现这两个名字，**所指 = `scripts/compute/store.py::DERIVED_VALUES_STEM`（`"derived_values"`，`store.py:62`）所命名的真源文件**；§⑪/§⑫ 的实验中它们**确实存在**，因为那是在**我的副本**里由写路径创建的（非主仓文件） |
| `citesweep2.py` / `drift.py` / `linecheck.py` / `g44_build.py` / `g44_run.py` / `exp_recheck_current.py` | 它们是**我 `/tmp/investsigh-audit-b11/` 下的仪器**，**本就不该入仓** | ✅ 合法（且正是"我的仪器不进被审树"的证据） |
⇒ **结论不变：无悬挂引用**；但口径更严了 —— **上一句的"22/22"是"我抽到的那 22 条"，这一句的"72/85 + 13 条逐条有解"才是我乐意的表述**（`V-11` 规矩 1：主语不得比样本更宽）。

★ **但我必须登记一次我自己的假阳性**：第一次扫描时报出 1 条"不在 main" —— `reports/phase1_gap_register.md`；
复核发现**是我的扫描脚本拼错了前缀**（该文件在仓库里的真路径是 `system/reports/phase1_gap_register.md`，
我的脚本拿 `reports/…` 直接去问 git）。`git cat-file -e HEAD:system/reports/phase1_gap_register.md` ⇒ **命中**。
—— 这是我本轮**第 4 处**仪器错误，形态与 `V-10` 同族：**"零命中/未命中"必须先排除"我的输入路径错了"**。
（这也是我为什么坚持每条"不存在"型结论都要**换一条独立路径复算 + 附地板真值**。）

### 五、`x13r`（卡 13-R 双转写审计）——**未验收，不予举证**

裁决：**不做整体复验**（未并入 ⇒ 未验收），但要求把这句话写清。现状与我的处置：

| 项 | 实测 |
|---|---|
| 报告 `system/reports/x13r_dual_transcription_diff_audit.md` | **在 main** ✅（`git cat-file -e HEAD:` 命中） |
| 它审计的**A 版产物**（`ws/ch13r-rule-candidates`，`b2e269c`/`ad33a6d`） | 该报告自述"**未进 main**"；我实测 `git ls-tree -r HEAD -- system/rules/` 中 **`rule-candidate` 相关文件数 = 0**（工作树 `find` 也为空）⇒ **A 版确实不在 main** |
| 它审计的 **B 版**（`ws/ch2-rules` 的 `3e5bc27`/`77df944`，经 `2b13cbf` 合并、`bb32863` 安装） | 在 main（`rules/` 已装）—— 但那是**另一条流**的产物，**不在本批次 11 的审计范围** |

**我的处置（写清，避免读者误读）**：
- 我**没有**复验 `x13r` 报告的任何**实质结论**（§3/§4/§5 的逐键对照、它主张的"已安装投入物里的一处真实缺陷"）⇒ **不予举证**。理由：裁决已定"不做整体复验（未并入 ⇒ 未验收）"，且其被审的 A 版不在 main。**"未验收"≠"有问题"**，只是**我不能替它背书**。
- 我在 §⑩ 的两处引用**只涉及它的"仪器"**，不涉及它的结论：
  - **#7**（`x13r:345`）：我复算的是它**自带地板真值**的做法（`wc`=479 行 + `:21` 命中）⇒ 判为**范式样例**；
  - **#8**（`x13r:338-342`）：我复算的是它**归因错**（把 toybox 的坏法写成 "BSD grep 不支持 `\|`"）⇒ 我自己给出了正确的归因。
  这两条**都是我自己的读数**（引擎版本 + `a\|b` 计数），**不以 `x13r` 的结论为证据**。
- 需要更正的那处归因（`§⑩-三` 已列）**仍待其作者或 team-lead 派单**；我不越界改他人文件。

### 六、五档结论（本轮）

| 对象 | 判定 | 依据 |
|---|---|---|
| `ws/verify-shard` 的**结构不变量**（7 片 / 300s / 16 文件全覆盖 / 片间不相交 / 绑定测试在守） | ✅ **好**（在当前 HEAD 重判成立） | 四项静态复算全部复现；绑定测试刻意不钉绝对数，设计正确 |
| 该流的**报告级数字**（"205 例"） | ⚠️ **不够** | 我复算 195（AST 口径）；差额 10 未归因；建议改为口径声明 |
| 我报告的**悬挂引用** | ✅ **无**（22/22 在 main） | 附一次我自己的扫描器假阳性已更正 |
| `x13r` 的**实质结论** | ⛔ **未验收，不予举证** | 未并入/A 版不在 main；我只引用其仪器级观察且均已自行复算 |

---

## ⑮ 按 `V-11` 规矩 9 的**引用级自审**：我报告里 6 条行号引用已漂移（含 `G-63` 两个落点）+ 第 5 处仪器错误

- **触发**：team-lead 采纳"时效核对件"为常态并立 **`V-11` 规矩 5**（机制改**内容级**）+ **规矩 9**（引用位置/数字须**指真源符号**，给数字则须紧跟"（当时读数）"）。规矩 5 我只做到**文件级**（`git diff --quiet <SHA> HEAD -- <f>`），规矩 9 我**一条都没做**。本轮是我在**没有裁判要求的情况下**自己按规矩 9 回头审自己。
- **对象与取样时刻**：工作树 `main` @ **`af20ebc83dc1798d5c4dec738b64ccece23bfd3a`**（`git rev-parse HEAD` 实测），取样 **2026-09-17 00:08:21 CST–00:2x CST**。工作树唯一改动 = 本报告（`git status --short` = ` M system/reports/ws_independent_audit_batch11.md`）。
- **时效核对件（`V-11` 规矩 5，内容级）**：本节写完时 HEAD 已推进到 **`8f3298d`**（12 条提交，改动面 = `CONVENTIONS.md` / `ops/{gate_set_diff.py,pre-commit.sh,verify.py}` / `tests/guards/*` / 两份报告 —— **不含本节的任何锚点文件**）。逐文件实测：
  ```
  git diff --quiet af20ebc HEAD -- system/scripts/daily/degrade.py        → rc=0 ✅ 内容未变
  git diff --quiet af20ebc HEAD -- system/scripts/tasks/gap_to_task.py    → rc=0 ✅ 内容未变
  git diff --quiet af20ebc HEAD -- system/scripts/delivery/stage_gate.py  → rc=0 ✅ 内容未变
  ```
  ⇒ 本节给出的 `degrade.py:184` / `:152` / `:129`、`gap_to_task.py:66` / `:83` / `:315`、`stage_gate.py:600` **在 `main@8f3298d` 上依然成立**。★ 但按本节二·补的教训，**"现在成立"不等于"永远成立"** —— 下一次有人改这三个文件时，锚点必须重取；这也是我坚持写**符号**而非行号的原因。
- **仪器**（全部在 `/tmp/investsigh-audit-b11/`，零写入被审树）：`citesweep2.py`（按 basename 建索引 + 逐条判"文件在否/行在否"+ 打出该行原文）、`drift.py`（把每条引用的**当前行文本**回搜"当时版本 blob"，给出**当时读数 → 现读数**）、`linecheck.py`（对带语义锚点的引用做**断言式**对拍）。

### 一、结果 A：97 条引用**全部**解析成功 —— 但**这不等于语义正确**

`citesweep2.py` 实测：**引用总条数 97；无法解析/越界 = 6**，那 6 条**全部是报告自身简写 `conftest.py`**（仓内 4 份同名，需靠上下文消歧；本报告中另有全路径写法 `system/tests/conftest.py` 可消歧）⇒ **按"文件存在 + 行存在"口径，97/97 合格**。

★ **我明确不把这一条当成"引用没问题"**：`citesweep2.py` 只回答"**那一行存在**"，**不回答"那一行是不是我说的那个东西"** —— 这是 `V-11` 规矩 9 的核心，也正是本节的第二节。

### 二、结果 B（手检语义）：**6 条引用已漂移，且全部指向了"别的东西"**

根因**单一且可归因**：`bd66025`（`fix(#95): G-64 收口`，对 `system/scripts/daily/degrade.py` **`+50/-2`**、对 `gap_to_task.py` 同步改动）在 `is_valid_run_record` **之前**插入了 `_check_record()` 与 `is_degraded_run_record()` 两个函数块。
★★ **这条提交修的正是我 §⑨ 在交叉复核的那个 `G-64`** —— 也就是说：**修缺陷的那条提交，把我审计报告里指向同一函数的行号改掉了。** 这是"时效核对件"必须做到**逐引用（而非逐文件）**的最有力理由：文件级 `git diff --quiet` 当时返回 0（我确实没读错），**但内容早已位移**。

| # | 我写的引用 | 我当时的语义 | 在**当时版本**的真值 | 在 **HEAD（`af20ebc`）** 的真值 | 判定 |
|---|---|---|---|---|---|
| 1 | `degrade.py:130`（3 处）| `holds_valid_result()` **载体①** | `abbe7b3:130` = `if row.get("last_valid_result_ref"):` ✅ **正是载体①** | **`:184`**（函数 def 在 `:152`）—— **漂 +54**；`:130` 现落在 `is_valid_run_record` 的 **docstring 首行** | ❌ **漂移且指向别的函数** |
| 2 | `degrade.py:80-101` | `is_valid_run_record()` 原语 | `abbe7b3`：def `:84`、body `:98-101` ✅ | def **`:129`**、body `:144-149` —— **漂 +45**；`:80-101` 现覆盖 `_check_record():84` + `is_degraded_run_record():95` | ❌ **漂移且指向新增函数** |
| 3 | `degrade.py:121-124` | 载体②"为什么不看 `output_refs`"那段理由 | `abbe7b3:121-124` ✅ 逐字 | **`:169-172`** —— **漂 +48**；`:121-124` 现是 `★ 不与之混同的对象：parent_context.degraded…`（**另一段论证**） | ❌ **漂移，内容也不是同一条理由** |
| 4 | `degrade.py:95` | `is_valid_run_record` docstring 自称「唯一判定原语」 | `abbe7b3:85` 为 docstring 首行、`:94-96` 为"唯一判定原语"句 ✅ | docstring 首行 **`:130`**、"唯一判定原语"句 **`:139-141`**；`:95` 现为 `def is_degraded_run_record` | ❌ **漂移** |
| 5 | `daily/degrade.py:98` | `is_valid_run_record()`「看 `degraded`」 | `abbe7b3:98-101` = `record = row.get("check_record")` … `return … and not record.get("degraded")` ✅ | `:98` 现是 `is_degraded_run_record` docstring 的"（**严格同一性**）"行；`is_valid_run_record` 的对应行在 **`:144-149`** | ❌ **漂移**（只是**侥幸**语义仍沾边） |
| 6 | `gap_to_task.py:73` / `:54` / `:240-254` | ①「`done` 行**穷尽**落入合法/违例两态、无第三态」的书面声明；②`is_no_change_day()` 定义；③判侧发违例处 | `e9a009b`：声明 `:73` ✅、def `:54` ✅、判侧 `:240-254` ✅ | 声明 **`:83`**（并已被就地标 ⚠️"已被 `G-64` 证伪"）、def **`:66`**、判侧 **`:315-336`** —— 漂 **+10 / +12 / 大幅** | ❌ **三条全漂** |

**样例（第 1 条的"别的东西"，逐字）** —— 在 HEAD 上 `degrade.py:130` 读到的是：
```
"""该行是否**一条成功的运行记录** —— "上次有效结果"的**唯一原语**（`G-45` 收口）。
```
它**看起来完全合理**（同一文件、同一主题、同一族词），但它是**载体②的原语**，不是载体①。⇒ 这正是 team-lead 升格入纸的那句「**匹配到了别的东西比零命中更危险**」的又一实例；也与 `V-10` 的 grep 族**同源但反向**：grep 族给的是"**空**"，行号漂移给的是"**非空且看似相关**"。

**在 HEAD 上核对通过（未漂 / 语义仍对）的关键引用**（我逐条手验，非仅靠文本匹配）：`scripts/delivery/stage_gate.py:600`（`if t.get("status") == "failed" and not t.get("last_valid_result_ref"):` ✅ 逐字）、`scripts/decision/run_decide.py:462-463`（`_as_of(series[...], run_date)` 先下标 ✅ 逐字）、`scripts/trace/traceback.py:163`（`for path in sorted(ddir.rglob("*.jsonl")):` ✅ 逐字）、`tests/injection/test_step56_skipped_wiring.py:77`（`benchmark["security_id"] = "usAGIX"` ✅ 逐字）、`schema/models.py:70-73`（`extra="forbid"` ✅）、`schema/jsonschema/facts.schema.json:384` 起（`"Benchmark"` ✅）。

#### 二·补 ★★ 新形态：**"两端同号、中间漂移"** —— 行号在**中段**是错的，而**首尾都对**

追 `stage_gate.py:600` 时实测到一个**与漂移相反**的形态（**三条 SHA 逐条读数**）：
```
[e9a009b :600] if t.get("status") == "failed" and not t.get("last_valid_result_ref"):   ← ✅ 对
[abbe7b3 :600] （空行）                                                                  ← ❌ 该行号处是空白，真值在 :567
[af20ebc :600] if t.get("status") == "failed" and not t.get("last_valid_result_ref"):   ← ✅ 又对了
```
机制：`abbe7b3`（`G-43`/`G-45` 收口）把 `stage_gate` 里那份**本地** `_holds_valid_result()` 换成 `from scripts.daily.degrade import holds_valid_result` ⇒ 删掉约 33 行**在 `:600` 之前** ⇒ 该行**上移到 `:567`**；其后 `bd66025` 等提交又在其前方补回约 33 行 ⇒ **回到 `:600`**。
⇒ **两条推论，都与我自己的口径有关**：
1. **"现在对得上"不能证明"当时也对得上"**，反之亦然 ⇒ 凡引用行号，**当时/现 两个读数都要给**（这就是 `V-11` 规矩 9 加"（当时读数）"的原因，也与我建议的"跨提交引用须成对给 SHA + 行号"同一条）。
2. 我 §⑨ 写 `stage_gate.py:600` 时对象是 `e9a009b` ⇒ **该引用在其取样 SHA 上是正确的**；但它**在中间的 `abbe7b3` 期不成立**。⇒ **一条引用"合格"是相对某个 SHA 的判定，不是绝对属性**。
★ 同时这条也说明**为什么我不把 `drift.py` 的机械数字当结论**：它把 `stage_gate.py:600` 报成"漂 +33"，而**语义上它两端都对** —— 机械漂移量 ≠ 结论失效。

**处置（已做，就地）**：第 1–6 条已按规矩 9 全部改写为 **符号锚点 + 「（当时读数）」行号**（`scripts/daily/degrade.py::holds_valid_result` 载体①／`::is_valid_run_record`／`scripts/tasks/gap_to_task.py::is_no_change_day`／`::check` 的空执行判侧），并在 §⑨ 表下加锚点改写说明。

### 三、★★ 这一节对**在办的 `G-63` 派单**有直接影响（请 team-lead 处置）

任务册 **#105** 的规格原文写 落点② = **`degrade.py:136`**。它与我报告的 `:130` 是**同一处漂移的两个刻度**（都是 `abbe7b3` 期读数）。**在 HEAD（`af20ebc`）上 `:136` 的实际内容是**：

```
135:    2. `status != "failed"`（本次运行没有失败）;
136:    3. `check_record.degraded` 为假（**降级运行的结果不是"有效结果"** —— 它本身就是在
137:       声明"本次结果不完整，请用上一次的"）。
```

⇒ 它落在 **`is_valid_run_record` 的判据第 3 条**，即**载体②** —— 而 `G-63` 落点② 的缺陷恰恰在**载体①**（`last_valid_result_ref` 非空即可信 ⇒ 垃圾引用让 `any(prior)` 为真 ⇒ 误报）。**照抄这个行号做修复，实现方会去动"已经正确的那一半"**（`check_record.degraded` 那一支是 `G-45` 收口时**已经修对**的），而**真正该动的载体①不会被动到**。这不是"行号不准"的瑕疵，而是**会引导出方向错误的修复**。

**建议的派单锚点（我实测，可逐字引用）**：
| 落点 | 符号锚点（真源） | HEAD 行号（**当时读数**，对象 `main@af20ebc`，`2026-09-17 00:2x CST`） | 失效方向 |
|---|---|---|---|
| ① | `scripts/delivery/stage_gate.py::stage_daily_run_passed` 内 `and not t.get("last_valid_result_ref")` | `:600` | **漏报**（垃圾引用令判据闭嘴） |
| ② | `scripts/daily/degrade.py::holds_valid_result` **载体①** `if row.get("last_valid_result_ref"): return True` | `:184`（函数 def `:152`） | **误报**（前序垃圾引用让合法首日行被判 FATAL） |
| 参考（已正确的对照） | `scripts/daily/degrade.py::is_valid_run_record` | `:129`（body `:144-149`） | —— |

**并建议把 `V-11` 规矩 9 再补半句**：**跨提交的引用（改前/改后、"当时/现"）必须成对给出 SHA + 行号**；只给一个行号时，读者**无法判断它是本态还是历史态** —— 与本轮 `#69`（§⑬）漂移、`G-61`（中间态被当本态）**同一成因**。

### 四、第 5 处仪器错误（我自抓）：**zsh 的 `$var:m` 修饰符把 `git` 的对象路径**静默**吃掉**

在追第 1 条的漂移时我写了 `git show $sha:system/scripts/daily/degrade.py`（**未加花括号**），得到 `wc -l` = **7 / 38 / 63** 与 `git cat-file -s` = **297 / 455 / 301** 这类"小得可疑"的读数，一度以为文件极短。**受控复现**（探针仅回显，零写入）：
```
$ sha=af20ebc
$ echo "A 未加花括号 : [$sha:system/scripts/daily/degrade.py]"
A 未加花括号 : [af20ebc]                                        ← ★ 路径被整段吃掉
$ echo "B 加花括号   : [${sha}:system/scripts/daily/degrade.py]"
B 加花括号   : [af20ebc:system/scripts/daily/degrade.py]          ← ✅
```
⇒ `git show $sha:path` 实际执行的是 **`git show <sha>` = 整个提交的 diff**（7/38/63 行 = 各提交 diff 行数，且行首都带 `+`）；`git cat-file -s $sha:path` 返回的是**提交对象的字节数**（297/455/301）；据此落盘核对后真值 = **425 行 / 20004 字节**。

**为什么这条比 grep 族更险（三种同形）**：
1. **零报错、`rc=0`** —— 没有任何一声"你参数错了"；
2. **读数看着合理** —— 几十行的 diff、`+` 前缀、几百字节的对象大小，全都像正常输出；
3. **★ 最危险的一格**：`git cat-file -e $sha:path` 退化为 `git cat-file -e $sha` ⇒ **只要 SHA 有效就恒 `rc=0`** ⇒ **"路径存在性检查"变成恒真的假阳性**。而 team-lead 恰好在本轮广播里把"判存在性"的推荐做法定为 `git cat-file -e`（替代不能判存在性的 `git rev-parse main:<path>`）⇒ **这个惯用法会把新推荐的判据也一起打穿**。
   - **实测我的报告没中这一枪**：我 §⑭ 用的是**字面量**形式 `git cat-file -e HEAD:<path>`（报告 §⑭ 逐字可查），**不含 `$var:` 展开** ⇒ §⑭ 的 22/22 结论**不受这条影响**。
- **修法（两条任选）**：`"${sha}:${path}"`（花括号）或先 `p="${sha}:${path}"` 再传。**判据**：凡命令里出现 `$`/`${}` 后紧跟 `:` 的 git 对象路径，一律按花括号或拼接处理。
- **全仓排查（我做了，结论相反方向）**：`system/` 内扫 `$var:...` 形态，**命中 5 处全是 `${VAR:-default}`**（`pre-commit.sh:45`、`run_pytest.sh:40`、`bootstrap_worktree.sh:50`、`probe_grep_engine.sh:25`、`tests/guards/test_hook_same_source.py:56`）—— 花括号 + `:-` 是**参数默认值**语义，**安全**；⇒ **风险只存在于"临时敲的审计命令"里**，不在仓库脚本里（故我不建议改任何脚本，只建议入纪律）。

### 五、**局限声明（`V-11` 规矩 1：「举证半径 = 结论半径」）**

- 本节的**结论主语**是：**我报告里那 6 条**指向 `scripts/daily/degrade.py` / `scripts/tasks/gap_to_task.py` 的行号引用。**不扩展到**"我报告所有行号都漂了"——第二节的手检只覆盖了带**语义断言**的引用（`linecheck.py` 的 22 条 SPEC + 上述 6 条）。
- `drift.py` 的机械扫描给出**已漂 32 / 未漂 39 / 跳过 15**，**但我不把它当结论**：它用"**当前行文本回搜旧 blob**"定位，对**短行 / 样板行**会发生**巧合匹配**（例如 `CONVENTIONS.md:257` 检出 +128、`facts.schema.json:4712` 检出 +1364，我**未逐条手验，故不予举证**）。
- ⇒ 对**未手验的那批**，我的表述是：**"我量到了漂移候选，但没核语义，不予举证"**，而不是"它们没问题"。这半句是 `V-11` 规矩 4 的自我适用（**不得把"量不到"读成"不成立"，也不得把"量到候选"读成"已证漂移"**）。

### 六、五档结论（本节）

| 对象 | 判定 | 依据 |
|---|---|---|
| 我报告 **97 条引用的"文件/行存在性"** | ✅ **好** | `citesweep2.py`：97/97 解析成功（6 条歧义为 `conftest.py` 简写，有全路径可消歧） |
| 我报告**指向 `degrade.py` / `gap_to_task.py` 的 6 条行号引用** | ❌ **错**（已就地更正为符号锚点 + 当时读数） | 全部为 `abbe7b3` / `e9a009b` 期读数；根因 `bd66025`（`+50/-2`）；`:130` 现落在**别的函数**的 docstring |
| `#105` 派单原文的 `degrade.py:136` | ❌ **会引导出方向错误的修复**（建议改用符号锚点，见第三节表） | HEAD `:136` = 载体② 判据第 3 条（**已正确的那一半**）；`G-63` 落点② 在载体①（`:184`） |
| 我 §⑭ 的 22/22 存在性结论 | ✅ **好**（不受第 5 处仪器错误影响） | 我 §⑭ 用字面量 `git cat-file -e HEAD:<path>`，无 `$var:` 展开；本轮另用 `git ls-tree -r --name-only` 独立复算 |
| 未手验的 32 条"漂移候选" | ⛔ **不予举证** | 机械口径对短行有巧合匹配；按规矩 1 不收窄也不上推 |
