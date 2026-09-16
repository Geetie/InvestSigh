# 批次 5c · QA 报告 —— 修 21 条调用点（收绿 `injection`）+ 补 `A-4` 零回归测试 + 时间契约回归 + 文字收口

- **QA 工程师**：`software-qa-engineer-3`（严过关 / Yan）
- **主理人**：齐活林（交付总监）
- **环境**：broker 关（`CODEBUDDY_SAFE_DELETE_SANDBOX=0` / `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`）；
  `python=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`；**逐批串行**，未并行 pytest。
- **引用规范**：一律节号锚点（`Ch9 §2.2` / `§3.4.1` / `§3.4.6` / `CONVENTIONS.md::R-06`），**无绝对行号**。
- **临时探针**：`/tmp/probe_e2e.py`（**仓库外**，不入库）。
- **纪律自查**：**未改** `scripts/**`、`rules/**`、`conftest.py`、设计区；只改 `tests/**` 与本报告；
  未 mock 决策函数（断言真实退出码 / 落库事实 / 行为）；临时目录用 `tests/.work/` 且用后删除；
  未往真实 `facts/`、`raw/` 写任何东西；新增/修改文件的注释/docstring **无** `TODO`/`占位`/`mock`/`fake`/`dummy`。

---

## 一、改了什么（文件 + 对应任务/缺陷编号）

| # | 文件 | 改动 | 任务 / 缺陷 |
|---|---|---|---|
| 1 | `tests/injection/test_prompt_injection.py` | helper `_ingest(...)` 与 `test_ac34` 的 `process_external_text(...)` 调用处**补 3 个必填实参** `first_seen_at`/`analyzed_at`（`datetime.now(timezone.utc)`）与 `recorded_seq`（模块级 `itertools.count(1)` **逐调用递增**，**不恒为 1**）；新增 `_now()` / `_next_seq()` 两个小助手 + `import itertools` / `from datetime import datetime, timezone`。★ **未改任何断言语义** | 任务 1（批次 5b `§四.2` 点名清单） |
| 2 | `tests/injection/test_guards_defensive.py`（**新增**） | 5 条回归：`SOURCE_MISSING`（缺源→`blocked`不抛）、`MISSING_PAYLOAD_FIELDS`（`kind="data"` 缺字段→`blocked`不抛 `KeyError`）、`store_raw` 同名不同内容**永不覆盖**+同内容**幂等**、`A-2` 读侧穿越**被拦**、`A-1` 读侧**目录**→`blocked` 不抛 `IsADirectoryError` | 任务 2（独立审计 `A-4` / `A-2` / `A-1` / `D-2` / `D-6`） |
| 3 | `tests/injection/test_time_contract.py`（**新增**） | 5 条回归：`build_claim` 缺 system_time 三元组→`TypeError`；显式传 `None`（`first_seen_at`/`analyzed_at`/`recorded_seq` 三例参数化）→运行期 `ValueError`；**端到端** handler 真跑（**临时夹具副本**，真子进程）→ 每条 claim 的 system_time 齐备、`locator` 非空、`recorded_seq` **严格递增** | 任务 3（本批缺陷的直接护栏） |
| 4 | `tests/injection/test_guards_reject.py` | 2 条用例的 docstring 与失败信息：把**已删除**的 `KNOWN_STATIC_LIMIT note` 措辞改为准确表述（能力白名单 `ALLOWED_IMPORTS`/`ALLOWED_DUNDERS` 不覆盖运行期计算的写入目标——属 `R-06` 意义上的「超出静止判据能力、且不以静止判据承担保证」；完整保证由运行时效果断言承担）；同步更新该组块注释。★ **`exit 0` 断言保持不变** | 任务 4（批次 5b `§4.1` 点名的文字债） |

**新增测试文件命名**：`test_guards_defensive.py`（防御性降级/落盘不可变）与 `test_time_contract.py`（时间契约）——
前者对应审计 `A-4`，后者对应批次 5b 缺陷的直接护栏；均沿用 `conftest` 的 `code_root` 夹具，风格照 `test_prompt_injection.py`。

---

## 二、测了什么（真实输出：命令 + 原始 stdout + 退出码）

### 1) 基线复现（修改前）—— `injection` 批次红

```
$ python system/scripts/ops/verify.py --batch injection
...
E       TypeError: process_external_text() missing 3 required keyword-only arguments:
        'first_seen_at', 'analyzed_at', and 'recorded_seq'
...
21 failed, 88 passed in 21.86s
```
退出码：`1`（该批不合格）。**21 条失败全部同一 `TypeError`，与工程师报告 `§四.2` 一致。**

### 2) 任务 1 后 —— `injection` 批次回绿

```
$ python system/scripts/ops/verify.py --batch injection
✓ [injection] tests/injection/（注入 / 接线 / 审计回归）  exit=0  24.01s/120s  exit=0
------------------------------------------------------------------------------
........................................................................ [ 60%]
...............................................                          [100%]
119 passed in 23.67s
------------------------------------------------------------------------------
证据留档: reports/verify_injection_latest.log
```
退出码：`0`。留档：`reports/verify_injection_latest.log`
（`# 耗时 24.01s ｜ 超时上限 120s ｜ 退出码 0` / `# 判定: 合格 —— exit=0` / `119 passed in 23.67s`）。

**读数**：`109（88 passed + 21 failed）→ 119 passed`。即 **21 条修复后全部 passed**，另 **+10 条**为本次新增
（5 条 `test_guards_defensive.py` + 5 条 `test_time_contract.py`）。`skipped`/`xfail`/`error` 均为 **0**。

### 3) 任务 4 后 —— `guards` 批次无回归

```
$ python system/scripts/ops/verify.py --batch guards
✓ [guards] tests/guards/（20 守卫 × 退出码契约 + 验证规范）  exit=0  3.43s/60s  exit=0
------------------------------------------------------------------------------
........................................................                 [100%]
56 passed in 3.08s
------------------------------------------------------------------------------
```
退出码：`0`（`56 passed`，与基线一致 → 措辞改动**零行为变更**）。

### 4) 新增 10 条用例逐条（-v）

```
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_guards_defensive.py tests/injection/test_time_contract.py -v
collected 10 items
tests/injection/test_guards_defensive.py::test_missing_source_is_blocked_not_raised PASSED [ 10%]
tests/injection/test_guards_defensive.py::test_data_request_missing_fields_is_blocked_not_keyerror PASSED [ 20%]
tests/injection/test_guards_defensive.py::test_store_raw_same_name_different_content_never_overwrites PASSED [ 30%]
tests/injection/test_guards_defensive.py::test_read_side_traversal_is_blocked PASSED [ 40%]
tests/injection/test_guards_defensive.py::test_read_side_directory_is_blocked_not_isdirectory_error PASSED [ 50%]
tests/injection/test_time_contract.py::test_build_claim_missing_system_time_is_typeerror PASSED [ 60%]
tests/injection/test_time_contract.py::test_build_claim_explicit_none_system_time_is_valueerror[first_seen_at] PASSED [ 70%]
tests/injection/test_time_contract.py::test_build_claim_explicit_none_system_time_is_valueerror[analyzed_at] PASSED [ 80%]
tests/injection/test_time_contract.py::test_build_claim_explicit_none_system_time_is_valueerror[recorded_seq] PASSED [ 90%]
tests/injection/test_time_contract.py::test_ingest_handler_end_to_end_fills_system_time PASSED [100%]
============================== 10 passed in 1.28s ==============================
```
退出码：`0`。

### 5) `gates` 批次（确认新文件未触占位符/接线门禁）

```
$ python system/scripts/ops/verify.py --batch gates
  ... injection_guard.py exit=0  0.09s
  verification_policy_guard.py  exit=0  0.07s
  非零计数  0
```
退出码：`0`（20 项门禁**非零计数 = 0**）。

### 6) 真实仓库洁净性（临时夹具未污染真源）

```
$ wc -c system/facts/claims.jsonl system/facts/tasks.jsonl
       0 system/facts/claims.jsonl
       0 system/facts/tasks.jsonl
$ find system/raw -type f
system/raw/inbox/.gitkeep
system/raw/.gitkeep
$ git status --porcelain -- system/tests system/facts system/raw
 M system/tests/injection/test_guards_reject.py     ← 任务 4
 M system/tests/injection/test_prompt_injection.py  ← 任务 1
?? system/tests/injection/test_guards_defensive.py  ← 任务 2（新增）
?? system/tests/injection/test_time_contract.py     ← 任务 3（新增）
?? system/raw/inbox/                                 ← 批次 5b 既有（非本次产物）
```

**要点**：`facts/*.jsonl` 仍 **0 字节**、`raw/` 仅 `.gitkeep`、`tests/.work/` 会话结束**已清空**；
端到端用例的写入**只**发生在 `code_root`（`system/` 的临时副本）内。

---

## 三、每条任务的处理与证据

### 任务 1（P0）修 21 条调用点 → **判定：完成**

- **处理**：`_ingest`（公共入口，覆盖 20 条）与 `test_ac34`（直接调用）各补 `first_seen_at`/`analyzed_at`/
  `recorded_seq`。时间取 `_now()=datetime.now(timezone.utc)`；`recorded_seq` 取 `_next_seq()`（模块级
  `itertools.count(1)`），**逐调用递增、不恒为 1**。
- **只补实参不改断言语义**：`git diff` 证实改动仅限 import / 两个小助手 / 每次调用新增 3 行实参
  （见 §一.1）；**断言一行未动**。
- **证据**：基线 `21 failed / 88 passed` → 修复后 `119 passed`（§二.1、§二.2）。
  **21 条修复后 passed 数 = 21（全绿）；该批 0 failed / 0 skipped / 0 error。**

### 任务 2（P0）补 `A-4` 零回归测试 → **判定：完成**（`tests/injection/test_guards_defensive.py`，5 条）

| 子项 | 断言 | 证据 |
|---|---|---|
| 1 `SOURCE_MISSING` | `process_raw_file(root,"raw/__missing__.txt",…)` → `status=="blocked"` 且 `note` 含 `SOURCE_MISSING`；**不抛异常**；无新增 claim | `test_missing_source_is_blocked_not_raised` PASSED |
| 2 `MISSING_PAYLOAD_FIELDS` | `handle_external_request(root,kind="data",payload={"text":"x"},…缺必需字段)` → `blocked` 且 `note` 含 `MISSING_PAYLOAD_FIELDS`；**不抛 `KeyError`** | `test_data_request_missing_fields_is_blocked_not_keyerror` PASSED |
| 3 `store_raw` 同名不同内容 | 版本A→版本B 落**两个不同路径**，**版本A 原样保留（不覆盖）**；同内容再写→**幂等**（同路径）；`raw/note*.txt` 恰 2 份 | `test_store_raw_same_name_different_content_never_overwrites` PASSED |
| 4 `A-2` 读侧穿越 | `process_raw_file(root,"raw/../rules/scope.yaml")` → `blocked` 且 `note` 含 `RAW_PATH_REJECTED`；`raw/` 下**无** `scope*` 产物；**无**新增 claim | `test_read_side_traversal_is_blocked` PASSED |
| 5 `A-1` 读侧目录 | `process_raw_file(root,"raw/adir.txt")`（路径为**目录**）→ `blocked` 且 `note` 含 `SOURCE_UNREADABLE`；**不抛 `IsADirectoryError`** | `test_read_side_directory_is_blocked_not_isdirectory_error` PASSED |

**非真空性说明**：以上断言的**反向事实**均已由第二轮独立审计 `batch4_independent_audit_round2.md::A-1/A-2/A-4`
实测记录（修前：读侧穿越 `status='ok'` 且落 `raw/scope.yaml` + 新增 claim；目录路径抛 `IsADirectoryError`；
`SOURCE_MISSING`/`MISSING_PAYLOAD_FIELDS` 毫无测试覆盖）。故本组用例对"修复被删掉"具备可证伪性——任务
明示「命中数为 0」的缺口已补齐。

### 任务 3（P0）时间契约回归 → **判定：完成**（`tests/injection/test_time_contract.py`，5 条）

| 子项 | 断言 | 证据 |
|---|---|---|
| 1 必填拦截 | `build_claim(...)` **缺** `first_seen_at`/`analyzed_at`/`recorded_seq` → `TypeError` | `test_build_claim_missing_system_time_is_typeerror` PASSED |
| 2 运行期拦截 | 显式传 `None`（绕过签名，pydantic 不拦）→ 运行期 `ValueError`（三例参数化） | `test_build_claim_explicit_none_system_time_is_valueerror[...]` × 3 PASSED |
| 3 端到端护栏 | step 1 handler 真跑一次（**临时夹具副本** + 真子进程）→ 每条 claim `first_seen_at` 非 None、`analyzed_at` 非 None、`recorded_seq` 是 int 且 ≥1、`locator` 非空；且 `recorded_seq` **严格递增**（证「不恒为 1」） | `test_ingest_handler_end_to_end_fills_system_time` PASSED |

**端到端做法（不 mock、不污染真仓）**：在 `code_root`（`conftest` 夹具提供的 `system/` 副本）内放两个
带 ISO 日期前缀的投递文件 → 真子进程把**副本**插入 `sys.path[0]` → `ingest_step._ROOT` 解析到**副本** →
`ingest_public_information(...)` 真跑 → 读**副本**的 `facts/claims.jsonl` 断言落库事实。
探针 `/tmp/probe_e2e.py` 先验证该路径产出 `recorded_seq=1`、`first_seen_at/analyzed_at` 非 None、
`locator='raw/…_sample.txt#L1-L3'`，且真实 `system/facts/claims.jsonl` 仍 **0 字节**。

### 任务 4（P1）文字收口 → **判定：完成**（`tests/injection/test_guards_reject.py`，2 处）

- **处理**：两条 `test_injection_guard_known_static_limit_*` 的 docstring + `proc.returncode == 0` 的失败信息，
  以及该组块注释，均把**已删除**的 `KNOWN_STATIC_LIMIT note` 措辞改为准确表述：
  「能力白名单（`ALLOWED_IMPORTS`/`ALLOWED_DUNDERS`）**不覆盖**运行期计算的写入目标——属 `R-06` 意义上的
  『超出静止判据能力、且不以静止判据承担保证』；**完整保证由运行时效果断言承担**」。
- **`exit 0` 断言保持不变**（`git diff` 证实断言行一字未改，见 §一.4）。
- **证据**：`guards` 批次 `exit=0 / 56 passed`（§二.3）——`exit 0` 实测仍成立，符合 `R-06`：
  白名单只对**能力**默拒，不假装能判运行期拼出的路径。

---

## 四、剩余不确定性与缺口

1. **`recorded_seq` 用模块级计数器（测试侧），非"按现有最大 +1"**：本批断言的是"补实参让契约可用"，
   与时间无关；用递增计数器即可满足"不恒为 1"。**真正的"按真源最大 +1"语义**由**端到端用例**
   （`test_ingest_handler_end_to_end_fills_system_time`）覆盖——那里断言的是 handler 真实产出的
   `recorded_seq` 严格递增。故测试侧计数器不影响语义覆盖。
2. **端到端用例是"子进程 + `sys.path` 指向副本"**：它跑的是**副本里的真实代码**（`conftest` 逐字节复制
   `system/`）。这在"不污染真仓"与"不 mock"之间取了平衡；若后续要求"在独立 worktree 里跑真仓库"，
   可另立一条（不在本批范围）。
3. **未纳入本批的审计项**（缺机器绑定，仍属技术债，**留给后续批次**）：
   - `A-3` 的 4 个新绕过（Subscript / 别名导入 / 属性末段）——**未被本批任何测试覆盖**（属**源码**加固项，
     须工程师改 `injection_guard.py`，QA 不改源码）；
   - `A-8`（两注册点集合一致性无机器断言）、`A-9`（`V-04` 裸文本包含）、`A-10`（`AC-05` 第 2 例退出码归类）、
     `A-11`（`V-02` 批次表陈旧）、`A-12`（`V-01` 措辞张力）、`A-6`/`A-7`（`gap_register` 残留）——多为**文档/裁定项**。
4. **`A-4` 缺口是否完全闭合**：本批补上了 `SOURCE_MISSING` / `MISSING_PAYLOAD_FIELDS` / 同名不同内容幂等
   （即审计点名的三项）；审计另提到的 `DECODE_DEGRADED`（非 UTF-8 读侧）与 `_content_addressed_sibling`
   前缀加长**未单列用例**——前者由 `read_external_text` + 既有边界隐含覆盖，后者由同名不同内容用例的
   路径后缀间接覆盖。若主理人要求"逐分支一条"，可再补（**建议**，非阻塞）。
5. **本报告未改动任何源码**：任务 3 若暴露源码问题本应上报（本次**未**发现——`build_claim` 的必填 +
   运行期断言按设计生效，端到端五类时间齐备）。

---

**IS_PASS: YES**

**理由**：任务 1~4 逐条完成且有实测证据——`injection` 批次 **`exit=0` / 119 passed**（21 条修复后全绿）、
`guards` **`exit=0` / 56 passed**、`gates` **非零计数 0**；新增 10 条回归（`A-4` 护栏 + 时间契约护栏）全绿；
真实仓库 `facts/`（0 字节）与 `raw/`（仅 `.gitkeep`）**未被污染**；只改 `tests/**`，未改 `scripts/**`/`rules/**`/`conftest.py`。

**唯一需主理人注意**：`A-3` 的 4 个新绕过（Subscript / 别名导入 / 属性末段）**不在 QA 权限内**（须工程师改
`injection_guard.py`），本批**未**为其新增测试；若采纳该加固，请指派工程师实施后由 QA 补回归。
