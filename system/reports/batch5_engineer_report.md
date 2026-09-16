# 批次 5 · 工程师报告 —— 接线 step 1 + `R-06` 能力白名单 + 收 `A-1`/`A-2`/`A-5` + 文字收口

- **工程师**：`software-engineer-3`（寇豆码 / Kou）
- **目标**（需求方钦定）：**让项目能真实开始干活** + **不留技术债** + **不鲁棒的方案一律不采用**
- **环境**：broker 关（`CODEBUDDY_SAFE_DELETE_SANDBOX=0` / `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`）；
  `python=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`；**逐批串行**，未并行。
- **引用规范**：一律节号锚点（`Ch9 §3.4.6` / `rules/pipeline.yaml::steps[1]` / `CONVENTIONS.md::R-06`），**无绝对行号**。
- **临时探针**：`/tmp/probe_batch5.py`、`/tmp/run_daily_accept.py`（**仓库外**，不入库）。

---

## 一、改了什么（文件 + 节号锚点）

| 文件 | 改动 | 节号锚点 |
|---|---|---|
| `scripts/orchestrate/ingest_step.py` | **新增**：step 1 handler `ingest_public_information(run_date, scope) -> StepOutcome`。默认从**投递口** `raw/inbox/` 读待采集外部文本 → 逐个 `scripts.guard.executor.process_raw_file(...)`（**复用**，不另写写库路径）；空样本显式 `degraded=True`；`signals_emitted=0` | `rules/pipeline.yaml::steps[1]` · `Ch9 §3.4.6` 措施① · `Ch1 §D.3` 反 KPI |
| `scripts/orchestrate/pipeline.py` | **新增** `Pipeline._register_default_steps()`，`__init__` 调用 → **默认注册 step 1**（不要求调用方额外注册）；更正 `D-14` 归因注释（原误述为"第二轮独立审计指出"，实为阶段① `gap_register` 的 `D-14`）；顺带把注释里的绝对行号 `rules/pipeline.yaml:68` 改为节号锚点 | `Ch1 §E` 注册面 · `D-14` · `R-01` |
| `scripts/checks/injection_guard.py` | B/C **改能力白名单**：新增 `ALLOWED_IMPORTS`（import 模块路径白名单，未列即 FATAL）+ `ALLOWED_DUNDERS`（dunder 名白名单，未列即 FATAL）+ **别名感知 C**（`from schema.store import append_records as ar` 解析回真实来源）；**删除 `KNOWN_STATIC_LIMIT` 措辞**；新增 scanned 字段 `import_outside_allowlist` / `dunder_outside_allowlist` | `CONVENTIONS.md::R-06` · `Ch9 §N9.2-01` |
| `scripts/guard/executor.py` | `process_raw_file`：**读侧复用** `rawsink._validate_name` + `rawsink.assert_within_raw`（`A-2`）；`except OSError` → `blocked/SOURCE_UNREADABLE`（`A-1`）；新增 `NOTE_RAW_PATH_REJECTED` / `NOTE_SOURCE_UNREADABLE`；顶部 docstring"生产接线属**阶段②**"改为**阶段①**并写明已接线（`A-6`） | `Ch9 §3.4.6` 措施① · `G-06` · `G-13` |
| `scripts/guard/rawsink.py` | 新增 `assert_within_raw(raw_dir, target)`（`raw/` 越界判定**唯一真源**，写侧+读侧共用）；把"同名不同内容"判定从 `read_external_text(...) == text` 改为 `_matches_existing(path, text)` —— 既有落点缺失/不可读/非 UTF-8 一律判"不一致"，**不再把 `ExternalTextDecodeError` 透传**（`A-5`）；`__all__` 增设 `assert_within_raw` | `G-06` · `A-5` |

**真实落库痕迹**（任务 1 要求，主理人已授权 `允许`）：

| 路径 | 变化 |
|---|---|
| `system/raw/inbox/2026-09-16_cloud_capex_note.txt` | **新增**（样例外部文本，投递口） |
| `system/raw/2026-09-16_cloud_capex_note.txt` | **新增**（执行器落盘：外部文本**只**进 `raw/`） |
| `system/facts/claims.jsonl` | `0 行 → 1 行`（主张化落库） |
| `system/facts/tasks.jsonl` | `0 行 → 1 行`（`run_daily` 必写的 `check_record`） |
| `system/state.json` | **新增**（断点续跑游标） |

**未触碰**：`rules/**`（仍 0444）、`tests/**`、`conftest.py`、`scripts/checks/` 下**其他**守卫、`00_*`~`11_*` 设计区（`git status` 证实无命中）。

---

## 二、测了什么（真实输出：命令 + 原始 stdout + 退出码）

> 引用证据一律读 `reports/verify_*_latest.log`，不必重跑。

### 1) `injection_guard` 在真实仓库上（exit code）

```
$ python system/scripts/checks/injection_guard.py system --no-report
== injection_guard.py ==
  scanned builtin_codeexec_hits: 0
  scanned chokepoints_wired: 2
  scanned data_path_modules: 7
  scanned dunder_outside_allowlist: 0
  scanned import_outside_allowlist: 0
  scanned recommendation_writes: 0
  scanned rules_files: 10
  scanned rules_files_on_disk: 10
  scanned unverifiable_stem_calls: 0
  note: CAPABILITY_ALLOWLIST: 数据路径的 import 模块（ALLOWED_IMPORTS）与 dunder 标识符（ALLOWED_DUNDERS）均受**显式白名单**约束，**未列入即 FATAL**；白名单对未列形式默认拒绝，故为**封闭集合**判定（CONVENTIONS.md::R-06）。
  note: AUX_LINT: builtin_codeexec_hits 为**辅助 lint**（eval/exec/compile 裸名），该集合**不可穷尽**，仅作附加绊线，**不得**据以判『已证明』（R-06 ④）。
  note: NO_RAW_EXTERNAL_TEXT：raw/ 无外部文本（数据路径不变式**真空成立**，须标注）
  note: data_path_globs=scripts/guard/** rules_suffixes=('.yaml', '.yml', '.json')
RESULT: PASS（0 violations）
EXIT=0
```

### 2) A-3 绕过矩阵 + 反向对照 + A-1/A-2/A-5（临时探针，真子进程）

```
$ python /tmp/probe_batch5.py
=== 注入守卫探针（期望 exit 码）===
  N1_builtins_subscript        expect=1 got=1  OK
  N2_builtins_exec             expect=1 got=1  OK
  N3_alias_append_reco         expect=1 got=1  OK
  N6_os_dict_system            expect=1 got=1  OK
  ok_literal_claims_stem       expect=0 got=0  OK
  ok_alias_literal_claims      expect=0 got=0  OK
  ok_receiver_concat           expect=0 got=0  OK
  ok_fstring_open              expect=0 got=0  OK
=== 执行器探针（A-1 / A-2 / A-5）===
  A-2 traversal  status='blocked' kind='raw_path' note="RAW_PATH_REJECTED: 外部文本名含路径穿越（..）: 'raw/"
      raw/scope.yaml exists=False (期望 False)  claims_lines=0 (期望 0)
  A-1 dir        status='blocked' kind='source_unreadable' note='SOURCE_UNREADABLE: IsADirectoryError: [E'
  A-1 perm0000   status='blocked' kind='source_unreadable' note='SOURCE_UNREADABLE: PermissionError: [Err'
  A-5 decode     store_raw OK -> 'same.6d97973518f83c03.txt' (期望不抛、加到更长前缀)
EXIT=0
```

探针源码（自造，逐个）：`N1 = __builtins__['__import__']('subprocess')`；`N2 = import builtins; builtins.exec('import subprocess')`；
`N3 = from schema.store import append_records as ar; ar(root,'recommendations',rows)`；`N6 = import os; os.__dict__['system'](cmd)`。

### 3) 任务 1 验收：在**真实** `system/` 跑 `run_daily`

```
$ python /tmp/run_daily_accept.py
=== BEFORE ===
  raw/: ['raw/.gitkeep', 'raw/inbox/2026-09-16_cloud_capex_note.txt']
  facts/claims.jsonl lines: 0
  facts/tasks.jsonl  lines: 0
  state.json exists: False
=== RUN RESULT ===
  step 1 ingest_public_information                  status=ok       produced=1
  step 2 trace_dedup_verify                         status=gap      produced=0 step 2 (trace_dedup_verify) 未注册处理器
  step 3 update_company_and_industry_relations      status=gap      produced=0 step 3 (...) 未注册处理器
  step 4 revise_growth_and_moat_judgment            status=gap      produced=0 step 4 (...) 未注册处理器
  step 5 update_financial_and_valuation_assumptions status=gap      produced=0 step 5 (...) 未注册处理器
  step 6 compare_company_vs_benchmark_expected_return status=gap    produced=0 step 6 (...) 未注册处理器
  step 7 publish_recommendations                    status=gap      produced=0 step 7 (...)；预留 hook = publish_hook
  step 8 continuous_verification_and_history        status=gap      produced=0 step 8 (...)；预留 hook = verify_hook
  blocked=True degraded=False signals_emitted=0 gaps=12
=== AFTER ===
  raw/: ['raw/.gitkeep', 'raw/2026-09-16_cloud_capex_note.txt', 'raw/inbox/2026-09-16_cloud_capex_note.txt']
  facts/claims.jsonl lines: 1
  facts/tasks.jsonl  lines: 1
  state.json exists: True
=== VERDICT ===
  step1.status == 'ok' : True
  claims.jsonl >= 1    : True
EXIT=0
```

**结论**：step 1 由 `gap` → **`ok`**；`raw/` 落盘；`facts/claims.jsonl` = 1 行。
step 2–6 仍 `gap`（实现体属阶段②③，张力 `T-08`）；step 7/8 预留 hook。故 `blocked=True` 属**预期**（step 2–6 `blocking:true` 且未注册）。

### 4) 分批验证（逐批串行，各自独立超时）

| 批次 | 结果 | 耗时/上限 |
|---|---|---|
| `unit` | ✓ exit=0，**42 passed** | 1.66s / 60s |
| `conflict` | ✓ exit=0，**6 passed** | 0.29s / 30s |
| `guards` | ✓ exit=0，**56 passed** | 3.35s / 60s |
| `injection` | ✓ exit=0，**109 passed** | 22.62s / 120s |
| `root` | ✓ exit=0，**8 passed** | 0.26s / 30s |
| `gates` | ✓ exit=0，**20 项门禁非零计数 = 0** | — |
| `stage` | ✓ **合格**（`prep: PASS` + `nvidia_sample/core_chain/daily_run/expansion: BLOCKED`，exit=1 设计预期） | 0.19s / 30s |

`skipped` / `xfail` / `error` / `failed`：**各批均为 0**（无静默跳过）。

---

## 三、每条任务的处理与证据

### 任务 1（P0）：接线 step 1 —— **判定：完成**

- **处理**：新增 `scripts/orchestrate/ingest_step.py`（step 1 handler，签名符合 `StepHandler = Callable[[date, str], StepOutcome]`）；`Pipeline.__init__` → `_register_default_steps()` **默认注册** step 1（不要求调用方额外注册）。
- **输入接缝（非 hack）**：默认投递口 `raw/inbox/`；docstring 明写"接缝在**投递侧**"——阶段② 连接器把采集到的文本投递到同一投递口即可，**处理侧（`scripts.guard.executor`）不变**。
- **空样本语义**：无 `raw/inbox/` 或无文件 → `StepOutcome(produced=[], degraded=True)`（**不静默当成功、不凭空造数据**）。注意：此时 `run_daily` 记 `ok` 但 `produced` 为空 → 会被 `assert_steps_complete` 判"空执行"并置 `blocked`（**这正是非静默**；happy path 明确产出非空）
- **证据**：§二.3 —— step 1 `status=ok`、`produced=1`、`raw/2026-09-16_cloud_capex_note.txt` 落盘、`claims.jsonl` 1 行；`gates`/`stage` 批次仍绿。

### 任务 2（P0）：`injection_guard` B/C 改**能力白名单** —— **判定：完成**

- **处理**：三条**封闭集合**判定（均为 allowlist，未列入即拒 → 可穷尽，合规 `R-06` ⑤）：
  1. `ALLOWED_IMPORTS`：`__future__` / `typing` / `dataclasses` / `pathlib` / `hashlib` / `contextlib` / `config.rules` / `schema.models` / `schema.store`（逐项理由见源码注释；相对导入只允许 `level==1`）。`os`/`subprocess`/`builtins`/`importlib`/… **一律 FATAL**。
  2. `ALLOWED_DUNDERS`：`__all__` / `__name__` / `__getattr__` / `__dir__` / `__init__` / `__post_init__`（dunder 为语言定义的**有限封闭集合**）。`__builtins__`/`__dict__`/`__globals__`/`__class__`/`__import__`/… **一律 FATAL**（并覆盖动态调用的 dunder 字符串字面量参数）。
  3. **别名感知 C**：预解析 import 表（局部名→完全限定名），`from schema.store import append_records as ar` → `ar(root,"recommendations",…)` 同样命中；stem 非字面量仍 **fail-closed**。
- **删 `KNOWN_STATIC_LIMIT`**：已彻底删除该措辞；scanned 字段改为 `import_outside_allowlist` / `dunder_outside_allowlist`。**不再宣称"已知静态局限"**——白名单下"未列入即拒"。
- **反向对照全绿**：真实 `scripts/guard/**`（7 模块）exit 0；探针反向对照 4/4 exit 0（§二.2）。
- **证据**：§二.1（真实仓库 PASS）+ §二.2（N1/N2/N3/N6 → exit 1，4 条反向对照 → exit 0）。

### 任务 3（P0）：收真漏洞 —— **判定：完成**

| 项 | 处理 | 证据 |
|---|---|---|
| **A-2**（安全） | 读侧 `process_raw_file` 复用 `rawsink._validate_name`（越界名/绝对路径）+ `rawsink.assert_within_raw`（`raw/` 落点；`G-06` 唯一真源，写/读两侧**同一判定**） | `raw/../rules/scope.yaml` → `blocked/raw_path`；**未**落 `raw/scope.yaml`；**未**产 claim（§二.2） |
| **A-1** | `except OSError`（在 `ExternalTextDecodeError` / `FileNotFoundError` 之后）→ `blocked/SOURCE_UNREADABLE` | 目录路径 → `IsADirectoryError` 收成 blocked；文件 0000 → `PermissionError` 收成 blocked（§二.2） |
| **A-5** | `store_raw` / `_content_addressed_sibling` 改 `_matches_existing(...) -> bool`：既有落点缺失/不可读/非 UTF-8 → 判"不一致" → 加长哈希前缀落新文件，**不再透传 `ExternalTextDecodeError`** | `store_raw(root,"same.txt","版本D")`（同名不同内容 + 8 位哈希落点已存在且非法 UTF-8）→ **不抛**，落 `same.6d97973518f83c03.txt`（16 位）（§二.2） |

### 任务 4（P1）：文字一致性 —— **判定：完成**

- **`A-6`**：`scripts/guard/executor.py` 顶部 docstring"生产接线属**阶段②** 采集层" → 改为**阶段①**并写明已接线路径（`G-13`：原判已纠正；`rules/pipeline.yaml::steps[1]` → `ingest_step.py` → `process_raw_file`）。
- **`A-13`**：`scripts/orchestrate/pipeline.py` 注释把 `D-14` 误述为"第二轮独立审计指出" → 更正为"**阶段① 缺口登记 `D-14` 指出**"；并把注释里的绝对行号 `rules/pipeline.yaml:68` 改为节号锚点（顺带满足 `R-01`）。
- **证据**：文件名与节号锚点见 §一；`no_placeholder_guard` 全树 PASS（含新 docstring）。

---

## 四、剩余不确定性与缺口（含"哪些既有测试断言需 QA 随之更新"）

### 4.1 既有测试断言**是否需要改** —— 实测结论：**无一条因本次改动失效**

- `injection` 批次 **109 passed / 0 failed**（与第二轮审计基线同为 109）→ **无断言失效**。
- **★ 重要校正（与主理人预判不符，据实上报）**：主理人预判"`test_guards_reject.py` 里 2 条断言『已知局限仍 exit 0』的用例，白名单化后**应当变成 exit 1**"。
  **实测：它们仍为 exit 0（用例仍通过）**。原因：这两条探针形态是**运行期计算得到的写入目标**——
  ① `(root/'facts'/('recommend'+'ations.jsonl')).write_text('x')`（接收者位字符串拼接）；
  ② `open(f'{root}/facts/{stem}.jsonl','a')`（f-string 变量目标）。
  二者**不含**任何白名单外 import、**不含**任何 dunder，也**未**调用 `append_records` → 三条封闭集合判定**都不覆盖**它们（这与 `R-06` 一致：白名单只对"能力"默拒，不假装能判运行期拼出的路径）。
  → 故**行为未变**，测试**无需改断言**。
- **但有一处"文字债"需 QA 随之更新**（不涉行为）：
  - `tests/injection/test_guards_reject.py` 中两条 `test_injection_guard_known_static_limit_*` 的 docstring 提到 `injection_guard.py` 的 `KNOWN_STATIC_LIMIT note`，而该 note 已被本次改动**删除**；
  - 其中 `test_injection_guard_known_static_limit_constant_in_receiver` 的**失败信息字符串**里含 `（并同步 injection_guard.py 的 KNOWN_STATIC_LIMIT note）`。
  → **建议 QA 的更新**：把上述两处"`KNOWN_STATIC_LIMIT note`"的措辞改为"能力白名单（`ALLOWED_IMPORTS`/`ALLOWED_DUNDERS`）**不覆盖**运行期计算的写入目标"；**退出码断言保持 exit 0 不变**。若 QA 希望把这两条"运行期拼接"形态**升级**为必须拦截，那需要**运行时效果断言**（`recommendations.jsonl` 行数不变，`test_prompt_injection.py` 效果三元组 (b) 已承担），**不应**在静态守卫里做形式枚举（`R-06` ③ 明令不采用）。

### 4.2 其他不确定性 / 缺口

1. **真实落库的运行期代价（记录留痕，供 `T-08` 裁定参考）**：本次在真实 `system/` 落了一条 `run_daily` 的 `check_record`（因 step 2–6 未注册 → `blocked=True` → 该 `Task.status="failed"`）。
   副作用：`stage_gate` 的 `daily_run` 阶段由"前置缺失→`_deferred`"变为"**有 `check_record` → 评估**"，并报一条 `daily_run` 违例
   （`task_check_2026-09-16_full 失败但未保留 last_valid_result_ref`，对齐 `Ch8 §E.4`）。
   **`stage` 批次判定仍为"合格"**（`daily_run` 仍显式标 `BLOCKED`，`prep: PASS`，exit=1 符合设计预期），故**未破坏任何批次**——但这条**真实运行即产生**的违例，正是第二轮审计 §7.2 建议在 `T-08` 处置列写清"运行期代价"的实证。
   （`pipeline._write_check_record` 对 `blocked` 运行置 `TaskStatus.failed` 且不填 `last_valid_result_ref`；是否应改为"降级保留上次有效结果引用"属 `T-08`/设计裁定，**本次不擅自改**。）
2. **重复运行会产生重复 claim**：`ingest_step` 未消费/未去重投递口文件；重跑同一投递文件会**追加**第二条同 `claim_id` 的 claim 行。幂等键去重（`Ch9 §3.5` 的 `(source_id, quote_hash)`）按设计属**阶段②**，故本次不实现（`R-04`：设计未写的不新增）。**建议**：阶段② 采集层接线时一并落地幂等去重。
3. **step 2–6 仍 `gap`**：属张力 `T-08`（`rules/` 0444 锁定，须需求方裁定）。本批次只接线 step 1，**未**触碰 2–6 的声明。
4. **`A-4`（D-2/D-6 零回归测试）不在本批次范围**：测试文件不归工程师改；请 QA 按审计 `A-4` 补 `SOURCE_MISSING` / `MISSING_PAYLOAD_FIELDS` / `DECODE_DEGRADED` / `_content_addressed_sibling` 的回归断言（建议同时覆盖本次新增的 `SOURCE_UNREADABLE` / `RAW_PATH_REJECTED`）。
5. **`A-7`/`A-10` 等**（`gap_register` 台账更新、`AC-05` 第 2 例退出码归类）属文档/裁定项，非本批次范围。

---

## 五、全局一致性审查

- **跨文件 import**：`ingest_step` ← `pipeline._register_default_steps`（真实调用方，非孤儿）；`executor` ← `rawsink.{_validate_name, assert_within_raw, _matches_existing...}`（均存在）；无循环导入。
- **接口契约**：`ingest_public_information(run_date: date, scope: str) -> StepOutcome` 与 `StepHandler` 一致；`assert_steps_complete` 未改语义。
- **数据流**：handler → `StepOutcome` → `run_daily` 读 `produced/…`；读侧与写侧共用同一 `raw/` 越界判定（`G-06`）。
- **无重复实现**：未新写第二套校验；`injection_guard` 复用 `rules_lock_guard` 同一 hash 出口。
- **无孤儿/无越界**：新模块有真实调用方；`rules/**`、`tests/**`、`conftest.py`、其他守卫、设计区**均未动**（`git status` 证实）。
- **性能**：AST 单遍；`injection_guard` 单次 **0.09s**（< 0.5s）；未急切导入 pydantic。

**IS_PASS: YES** —— 7 个批次全绿（unit 42 / conflict 6 / guards 56 / injection 109 / root 8 / gates 0 非零 / stage 合格），
`A-1`/`A-2`/`A-5`/`A-6`/`A-13` 逐条收口且有实测证据，`A-3` 四绕过全拦、反向对照全绿，任务 1 在真实仓库自证 step 1 = `ok`。
**唯一需下游注意**：本次改动**不使任何既有断言失效**（与主理人预判不同，见 §4.1）——仅 2 条用例的**措辞**需 QA 同步更新，退出码断言保持不变。
