# 批次 4 · 独立审计发现修复报告（工程师 · 寇豆码）

> **依据**：`system/reports/batch4_independent_audit.md`（独立审计缺陷清单 D-2/D-3/D-6/D-7）·
> `system/CONVENTIONS.md`（`G-02` 函数体级 AST 绑定 / `G-03` 空样本记 note / `P-01` 单遍 AST）·
> `Ch9 §3.4.6`（注入防护四措施）· `Ch9 §N9.1-10`（`raw/` 原始物留存）· `Ch9 §N9.2-01`（判据不变式）。
> **范围**：仅修 D-2 / D-3 / D-6 / D-7。D-1 / D-4 / D-5 不在本次范围（D-4 已由另一提交修复）。
> **引用一律节号锚点**，无绝对行号。

---

## 改了什么（文件 + 节号锚点）

只改 **3 个文件**（`git status --porcelain` 仅这三项，未触 `tests/**`、`rules/**`、既有守卫、`conftest.py`）：

| 文件 | 缺陷 | 改动（节号锚点） |
|---|---|---|
| `scripts/guard/executor.py` | D-2 / D-7 | ① 新增常量 `NOTE_SOURCE_MISSING` / `NOTE_MISSING_PAYLOAD_FIELDS` 并登记 `__all__`；② `process_raw_file` 增加 `except FileNotFoundError` 分支 → `blocked` + `SOURCE_MISSING`（`Ch9 §3.4.6` 措施①，`AC-05`）；③ `handle_external_request` 的 `kind="data"` 分支先校验必需键 `("claim_nature","claim_form","tier")`，缺失 → `blocked` + `MISSING_PAYLOAD_FIELDS`；④ 顶部 docstring 改为准确表述（去掉"不再是变相孤儿"，改为"可被生产调用的路由入口；生产接线属阶段② 采集层，见 `G-13`"） |
| `scripts/guard/rawsink.py` | D-6 | `store_raw` 改为**永不覆盖**：同名同内容幂等返回；同名**不同内容**落成**内容哈希后缀**新文件 `<stem>.<sha256前8位><suffix>`（新增 `_content_addressed_sibling` + `import hashlib`）；docstring 只写实现会做的事（`Ch9 §N9.1-10` / 纪律 4） |
| `scripts/checks/injection_guard.py` | D-3 / D-7 | 断言 B 结构化为三子规则（① import 禁用模块 `subprocess/pty/shlex/pickle/marshal`；② 属性访问 `os.system/os.popen/os.exec*/os.spawn*`；③ `getattr/__import__/eval/exec/compile` 的字面量字符串参数落工具原语集合）；断言 C 对 `append_records` 的 **stem 实参**实施 **fail-closed**（非字符串字面量 → FATAL）；新增报告字段 `import_deny_hits` / `unverifiable_stem_calls`；docstring 表 B/C 行重写、E 行改为与代码一致（按函数体**集合**判定，不要求同一函数） |

**新增 note 前缀（实现细节，特此说明）**：`SOURCE_MISSING`、`MISSING_PAYLOAD_FIELDS` 两个 note 前缀属新增常量的使用，非设计外实体。

---

## 测了什么（命令 + 原始 stdout + 退出码）

环境统一：`cd /Users/gaza/Developer/InvestSigh`；`export CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`；
`PY=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`；**逐批、串行**，无一条命令全量。

### 1) 守卫自跑（真实 `system/` 根）

```console
$ $PY system/scripts/checks/injection_guard.py --no-report
== injection_guard.py ==
  scanned chokepoints_wired: 2
  scanned data_path_modules: 7
  scanned import_deny_hits: 0
  scanned recommendation_writes: 0
  scanned rules_files: 10
  scanned rules_files_on_disk: 10
  scanned tool_primitive_hits: 0
  scanned unverifiable_stem_calls: 0
  note: NO_RAW_EXTERNAL_TEXT：raw/ 无外部文本（数据路径不变式**真空成立**，须标注）
  note: data_path_globs=scripts/guard/** rules_suffixes=('.yaml', '.yml', '.json')
RESULT: PASS（0 violations）
EXIT=0
```

### 2) 验证批次（逐批串行）

```console
$ $PY system/scripts/ops/verify.py --batch guards
✓ [guards] tests/guards/（20 守卫 × 退出码契约 + 验证规范）  exit=0  3.61s/60s  exit=0
56 passed in 3.18s
GUARDS_EXIT=0

$ $PY system/scripts/ops/verify.py --batch injection
✓ [injection] tests/injection/（注入 / 接线 / 审计回归）  exit=0  19.81s/120s  exit=0
102 passed in 19.26s
INJECTION_EXIT=0

$ $PY system/scripts/ops/verify.py --batch gates
✓ [gates] run_all_gates.py（20 项门禁）  exit=0  4.32s/60s  exit=0
  ... 20 项门禁逐项 exit=0（含 injection_guard.py exit=0 0.19s / rules_lock_guard.py exit=0 0.18s）
  非零计数                               0
GATES_EXIT=0

$ for b in unit conflict root stage; do $PY system/scripts/ops/verify.py --batch $b; done
✓ [unit]     exit=0  1.61s/60s   → 42 passed
✓ [conflict] exit=0  0.39s/30s   → 6 passed
✓ [root]     exit=0  0.36s/30s   → 8 passed
✓ [stage]    阶段① PASS + 阶段②–⑤ 全部阻塞（纪律 12 预期行为）→ 内部 exit=1（设计预期）；verify 判定合格
```

**回归汇总（串行实跑）**：unit 42 + conflict 6 + guards 56 + injection 102 + root 8 = **214 passed，0 失败**；
`gates` 20 项门禁 **非零计数 0**；`stage` 为设计预期的 ① PASS + ②–⑤ BLOCKED。

### 3) 反占位符守卫（D-7 docstring 改动相关）

```console
$ $PY system/scripts/checks/no_placeholder_guard.py system --fail-on warn
  scanned files: 83
RESULT: PASS（0 violations）
NP_EXIT=0
```

### 4) 守卫仍只经既有 hash 出口（无第二套 sha256）

```console
$ $PY system/scripts/checks/rules_lock_guard.py system --no-report   → RL_REAL_EXIT=0
$ grep -n "hashlib\|sha256" system/scripts/checks/injection_guard.py → 0 命中
```

---

## 每条缺陷的处理与证据

### D-2（中高）· AC-05 两条异常逃逸 → 收成 `blocked`

**处理**：`process_raw_file` 增捕 `FileNotFoundError` → `blocked` + `SOURCE_MISSING: <relpath>` + `blocked_kind="missing_source"`；
`handle_external_request` 的 `kind="data"` 先校验必需键，缺字段 → `blocked` + `MISSING_PAYLOAD_FIELDS: [...]` + `blocked_kind="payload"`。
`kind="rule_write"` 经核查原用 `.get("path","")` / `.get("content","")`，**原本就不会抛** `KeyError`。

**判定：已修复。**

**证据（真跑，临时 root 于工作区内，用后删除）**：

```console
== D-2.1 raw file missing ==
  status= blocked | blocked_kind= missing_source | note= SOURCE_MISSING: raw/DOES_NOT_EXIST.txt
  note.startswith(SOURCE_MISSING)= True
== D-2.2 kind=data missing fields ==
  status= blocked | blocked_kind= payload | note= MISSING_PAYLOAD_FIELDS: ['claim_nature', 'claim_form', 'tier']
  note.startswith(MISSING_PAYLOAD_FIELDS)= True
== D-2.3 kind=rule_write missing path/content ==
  status= blocked | blocked_kind= rule_write | note= RULE_WRITE_BLOCKED: …（不抛 KeyError）
```

修复前审计实测为 `RAISED FileNotFoundError` / `RAISED KeyError: 'claim_nature'`；现两条均**降级为 `blocked` 并带显式 note**，未再抛给调用方。

---

### D-3（中）· B / C 断言可被一次改写绕过 → 结构化 + fail-closed

**处理**：断言 B 结构化为三子规则（import 禁用模块 / `os.*` 属性访问 / 动态调用字面量参数）；
断言 C 对 `append_records` 的 stem 实参 fail-closed（`Name`/`Call`/`JoinedStr`/`BinOp`/缺参 → FATAL）。
两条判据均 **AST 级**（`ast.Import`/`ImportFrom`/`Attribute`/`Call` 节点），未退化为全文件字符串匹配（`G-02`）。
新增独立报告字段 `scanned.import_deny_hits` / `scanned.unverifiable_stem_calls`。

**判定：核心绕过已修复（14 探针逐条实测）。**

**证据（对 `scripts/guard/` 副本注入探针，`injection_guard` 真子进程退出码）**：

| 探针（`scripts/guard/probe_*.py`） | 退出码 | 期望 | 结论 |
|---|---|---|---|
| `append_records(root, STEM, [])`（stem 为变量） | **1** | 1 | 拦下（fail closed）|
| `append_records(root, f"{a}", [])`（f-string stem） | **1** | 1 | 拦下（fail closed）|
| `append_records(root, "recomm" + "endations", [])`（拼接 stem） | **1** | 1 | 拦下（fail closed）|
| `append_records(root, "claims", [])`（字面量对照） | **0** | 0 | 放行（**无误报**）|
| `append_records(root, "recommendations", [])` | **1** | 1 | 拦下 |
| `getattr(os, "system")(cmd)` | **1** | 1 | 拦下 |
| `import subprocess` / `import pty` / `from subprocess import run as r` | **1** | 1 | 拦下 |
| `os.system(cmd)`（属性访问） | **1** | 1 | 拦下 |
| `open(os.path.join(root,"facts","recommendations.jsonl"),"a")` | **1** | 1 | 拦下 |
| `import shutil`（不在禁用集合） | **0** | 0 | 放行（**降噪，`G-05`**）|

（`p12 f"{root}/facts/{stem}.jsonl"` / `p13 (root/"facts"/("recommend"+"ations.jsonl")).write_text` 为 exit 0 —— 见「剩余不确定性」。）

`scanned.import_deny_hits` / `scanned.unverifiable_stem_calls` 已作为独立计数字段出现在报告输出中（见「测了什么 · 1)」）。
空样本仍显式记 note（`NO_RAW_EXTERNAL_TEXT`），**未**判 PASS=已验证（`G-03`）。

**现状核查**：`scripts/guard/**` 中唯一 `append_records` 调用为 `executor.py` 的 `append_records(root_path, "claims", [claim])`（字面量）——
fail-closed **未产生任何误报**（守卫实跑 `unverifiable_stem_calls: 0`）。**未发现**别处的非字面量调用。

---

### D-6（低-中）· `rawsink.store_raw` 同名不同内容静默覆盖 → 永不覆盖

**处理**：目标已存在且内容不同 → 落成内容哈希后缀新文件 `<stem>.<sha256前8位><suffix>` 并返回该**实际路径**；内容相同仍幂等。
落点始终复核算在 `raw/` 内。docstring 只写实现会做的事。

**判定：已修复。**

**证据（真跑）**：

```console
first  path= raw/same.txt           content= A
second path= raw/same.df7e70e5.txt  content= B
DIFFERENT_PATH= True | FIRST_PRESERVED= True
idempotent(A again) path==first: True | files in raw: ['same.df7e70e5.txt', 'same.txt']
all under raw/: True
```

修复前审计实测为"版本A→版本B（路径相同，内容=B）"；现**既有原始物 A 不被替换**，新内容 B 落到哈希后缀新文件。

---

### D-7（低）· docstring 强度 > 代码

**处理**：
- `executor.py` 顶部：删去"使两个收口点……不再是'仅供测试调用'的变相孤儿"，改为"为两个收口点提供**可被生产调用的**路由入口；★ 生产接线（把本入口接进真实采集链路）属阶段② 采集层，见 `G-13`"。
- `injection_guard.py` 顶部断言 E 行：改为与代码一致 —— "`executor.py` 的**若干函数体内存在**对 `write_rule` 的调用，且**存在**对 `request_tool` 的调用（按函数体集合判定，**不要求**落在同一函数）"。

**判定：已修复（docstring 与代码事实一致）。**

**证据**：`no_placeholder_guard.py system --fail-on warn` → `RESULT: PASS（0 violations）` / exit 0；
人工比对 docstring 与 `_body_calls` / `body_calls_per_func` 的实际判定范围（按函数体**集合**而非"同一函数"）。

---

## 追加收口（主理人复核意见）· D-3 措辞：静态绊线不得自称证明

主理人复核确认四条修复均复现通过，但指出 **C 判据只覆盖 `append_records` 的 stem 实参**这一事实此前只在报告文档里说明，
**声明强度仍未与事实对齐**。按要求做**纯措辞收口**（不新增判据、不改 `scripts/guard/**` 行为、不动测试）：

1. **docstring 降级为准确表述**（`injection_guard.py` 顶部）：新增一段明确 ——
   "B / C 是**对常见形式的静态绊线**……**不构成完整证明**；任意**计算得到的路径**（receiver 位置拼接、f-string 变量目标）静态不可判定；
   **完整保证由运行时效果断言承担**：处理前后 `facts/recommendations.jsonl` 行数不变（效果三元组 (b)）"；
   表格 B/C 行标题加上"（**静态绊线**）"限定词；小标题由"机械断言"改为"静态绊线 / 断言"。
2. **两条已知残留形式写进 `report.notes`**（每次门禁运行可见，非只躺在文档里）：
   `note: KNOWN_STATIC_LIMIT: B/C 为**静态绊线**，不构成完整证明；**计算得到的路径**静态不可判定（例：receiver 位置拼接
   (root/'facts'/('recommend'+'ations.jsonl')).write_text(...) 与 f-string 变量目标 open(f'{root}/facts/{stem}.jsonl','a')）→ 不在 B/C 覆盖内。
   **完整覆盖由运行时效果断言承担**：处理外部文本前后 facts/recommendations.jsonl 行数不变（tests/injection/test_prompt_injection.py 效果三元组 (b)）。`

**证据（真实输出）**：

```console
$ $PY system/scripts/checks/injection_guard.py system --no-report
  scanned import_deny_hits: 0
  scanned unverifiable_stem_calls: 0
  note: KNOWN_STATIC_LIMIT: B/C 为**静态绊线**，不构成完整证明；…（两条残留形式显式列出）…（效果三元组 (b)）
  note: NO_RAW_EXTERNAL_TEXT：…
RESULT: PASS（0 violations）
IG_EXIT=0

$ $PY system/scripts/ops/verify.py --batch gates
✓ [gates] run_all_gates.py（20 项门禁）  exit=0  4.61s/60s  exit=0
  … 20 项门禁逐项 exit=0（含 injection_guard.py exit=0 0.20s）
  非零计数                               0
GATES_EXIT=0

$ $PY system/scripts/checks/no_placeholder_guard.py system --fail-on warn   → RESULT: PASS（0 violations） / exit 0
$ $PY system/scripts/ops/verify.py --batch injection                       → 102 passed / exit=0
```

---

## 剩余不确定性与缺口

1. **D-3 的 C 判据按任务定义**只覆盖 `append_records` 的 stem 实参。审计探针中**绕过 `append_records`** 的两类直接路径写
   （`(root/"facts"/("recommend"+"ations.jsonl")).write_text(...)`、`open(f"{root}/facts/{stem}.jsonl","a")`）
   **仍为 exit 0** —— 前者的 `recommendations` 常量位于**接收者**（非调用实参），后者的目标名在**变量**里（静态不可判定）。
   本批次未扩大 C 的范围（遵循任务"不要扩大范围"）。理论缓解：`schema/store.py` 声明 `append_records` 是 `facts/*.jsonl` 的**唯一写入口**，
   绕过它的直接写本身即设计违规；如需机器强制，建议单列一条判据（**G-02 之外的独立项**）并上报需求方裁定。
   ★ 该边界现已**随每次门禁运行以 `note: KNOWN_STATIC_LIMIT` 显式可见**（见「追加收口」），且 docstring 已声明 B/C 为**静态绊线、非完整证明**，**完整保证由运行时效果断言承担**。
2. **D-3 的 B 判据按任务定义**的 import 禁用集合为 `subprocess/pty/shlex/pickle/marshal`；`shutil`、`os` 等**不在集合内**，
   `import shutil; shutil.which("sh")` 仍 exit 0。若需覆盖更广的"外部命令/模块"，须先扩充并同步设计（`R-04`：不自行裁决）。
3. **D-2 的 `raw_ref`**：`missing_source` 分支 `raw_ref=""`（未产出 raw 物，避免指向不存在文件），源路径记在 note；`decode` 分支沿用原 `raw_ref=relpath`（其文件确实存在）。
4. **D-1（执行器一族无生产调用方）** 仍是本批次实质缺口（`G-13`），本报告**不主张**已解决；`handle_external_request` 目前仍只被测试调用。
5. **D-5（`append_only_guard` 真空放行）** 与 **D-4（反占位符字符串占位）** 不在本次范围（D-4 已由提交 `3ff85da` 处理）。

---

## 全局一致性审查（所有文件写完后一次）

| 检查项 | 结论 |
|---|---|
| 跨文件 import 一致（`executor` ← `rawsink`/`annotate`/`claims`/`rulewrite`/`toolwatch`） | ✅ 无缺失、无环；`rawsink` 新增 `hashlib` 不影响任何调用方 |
| 接口契约（`store_raw` / `process_raw_file` / `handle_external_request` 签名） | ✅ 签名未变；`store_raw` 返回值语义增强（实际路径），调用方 `executor` 只用返回值、不做路径假设 |
| 数据流正确（`IngestResult` 字段、`blocked_kind`、note 前缀） | ✅ `blocked_kind ∈ {decode, missing_source, payload, rule_write, tool_call, raw_name, unknown}` 与 note 前缀一一对应 |
| 无重复实现（hash 出口唯一） | ✅ `injection_guard` 不含 `hashlib/sha256`，仍只经 `rules_lock_guard.check()`（`grep` 0 命中）|
| 无孤儿（收口点有函数体调用） | ✅ 收口点判定 `chokepoints_wired: 2`；守卫 AST 级函数体绑定 |
| 无占位符 / 禁用词 / 绝对行号 | ✅ `no_placeholder_guard` 0 violations；三文件无 `TODO|占位|mock|fake|dummy`；引用均为节号锚点 |
| 未扩大范围 / 未污染仓库 | ✅ `git status --porcelain` 仅 3 个目标文件 |

**IS_PASS: YES**

理由：本次范围内的 4 条缺陷（D-2/D-3/D-6/D-7）逐条修复并留有真实复现证据；核心绕过探针（变量/f-string/拼接 stem、`getattr(os,"system")`）由 exit 0 → **exit 1**；
20 项门禁 0 非零，214 条测试全绿，反占位符守卫 0 violations；未修改设计外文件、未新增设计外实体、未引入第二套 hash 校验。
剩余缺口（D-1 接线、C 判据对"绕过 `append_records` 的直接写"的覆盖面）已在「剩余不确定性」如实登记，不属本次修复范围。
