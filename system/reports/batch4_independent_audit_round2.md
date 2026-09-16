# 批次 4 第二轮独立审计 —— 复核「5 条修复是否真闭合」+ 新绕过形式

- **审计员**：`independent-auditor`（与实现方、QA、主理人均不同人）
- **审计对象**：提交 `d870da7`（"收口批次4 独立审计 5 条 FAIL 中的 4 条 + 纠正 G-13 判据 + 登记张力 T-08"）
- **铁律遵守**：未修改任何源码 / 测试 / fixture / 配置；唯一写入物 = 本报告。临时目录建在 `system/tests/.work/audit-r2/`，**已删除**；`git status --porcelain` 在审计前后均为空。
- **证据来源**：**全部为本轮自造探针的实测输出**（探针脚本已随临时目录删除）。主理人给出的复核结论、工程师报告、QA 报告中的数字**一律未采信**。
- 环境：broker 关（`CODEBUDDY_SAFE_DELETE_SANDBOX=0` / `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`）；`/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`（3.13.12）；**逐批跑，严格串行**。

---

## 0. 一句话结论

**4 条修复里 `D-5` / `D-6` 真闭合、`D-2` / `D-3` 只闭合了被点名的那几例（同族残口与 4 个新绕过仍在）、`D-7` 字面已改但同一提交引入了新的错误陈述；`AC-01/AC-03` 依旧 FAIL。本轮新增 13 条发现，无 1 条是靠"改文字"能消掉的。**

修正后的判定统计：**PASS 31 / FAIL 3（`AC-01` `AC-03` `AC-05`）/ UNKNOWN 0 / HUMAN_REVIEW 1**（第一轮为 29 / 5 / 0 / 1）。

---

## 1. 变更面核验（第一步：先看越界）

```
d870da7 fix(system): 收口批次4 独立审计 5 条 FAIL 中的 4 条 + 纠正 G-13 判据 + 登记张力 T-08
 system/reports/batch4_fix_engineer_report.md        | 260 +++
 system/reports/batch4_qa_report2.md                 | 222 +++
 system/reports/phase1_gap_register.md               |   2 +-      ← 只改了 G-13 一行
 system/reports/phase1_open_tensions.md              |   1 +      ← 只加了 T-08 一行
 system/scripts/checks/injection_guard.py            | 132 +-
 system/scripts/guard/executor.py                    |  40 +-
 system/scripts/guard/rawsink.py                     |  39 +-
 system/tests/injection/test_guards_reject.py        | 156 +      ← 新增
 system/tests/injection/test_prompt_injection.py     | 142 +-
```

| 检查项 | 结论 |
|---|---|
| `rules/**` 是否被动 | **未动** ✓（`git diff --name-only` 无命中；`rules/` 仍 0444） |
| `conftest.py` 是否被动 | **未动** ✓ |
| 门禁注册点 `run_all_gates.py` / `pre-commit.sh` 是否被动 | **未动** ✓（第一轮已验证 `injection_guard` 在两者中） |
| 既有 17 个检查器语义是否被动 | **未动** ✓（`scripts/checks/` 下仅 `injection_guard.py` 变更，它是批次 4 新增项，不属既有 17） |
| 越界改动 | **无** ✓ |

★ 但"只改了一行"的 `phase1_gap_register.md` 正是本轮两个矛盾（`A-6`/`A-7`）的来源 —— 改一行不够，见 §6。

---

## 2. 五条修复的复核结论

| 原发现 | 本轮判定 | 关键证据（我的探针） |
|---|---|---|
| **D-2** `AC-05` 两条异常逃逸（`FileNotFoundError` / `KeyError`） | **PARTIAL**（点名两例闭合，同族仍有逃逸） | 缺文件→`blocked/SOURCE_MISSING`；`kind=data` 空 payload→`blocked/MISSING_PAYLOAD_FIELDS`；只缺 `tier`→同上；`rule_write` 空 payload→`blocked/RULE_WRITE_BLOCKED`（无 `KeyError`）。**但** `raw/<relpath>` 是**目录**→`IsADirectoryError` 逃逸；文件 0000 → `PermissionError` 逃逸 |
| **D-3** `injection_guard` B/C 可一次改写绕过 | **PARTIAL**（原 4 例全拦，**新增 4 个绕过**） | 原 4 例（`import subprocess` / `getattr(os,"system")` / 变量 stem / f-string stem）**全部 exit 1** 且归因正确；反向对照 4 条**全部 exit 0**（未退化成见词就杀）。**但** `__builtins__['__import__']('subprocess')`、`builtins.exec('import subprocess')`、`from schema.store import append_records as ar`、`os.__dict__['system']` **全部 exit 0** |
| **D-5** `AC-15`/`AC-25` 追加式证据真空 | **CLOSED** ✓ | ①未改动夹具：exit 0 + `staged_facts_files: 0` + `NO_STAGED_FACTS_CHANGES` note（**证明旧断言确为真空**）；②注入经真执行器落库：`claims 1→2` → exit 0 + `staged_facts_files: 1` 且**无真空 note**；③反事实·改写既有行 → **exit 1**；④反事实·删除整份 `claims.jsonl` → **exit 1**（此条是我自加的新反事实）；⑤`recommendations.jsonl` 全程 0 行 |
| **D-6** `raw/` 同名不同内容静默覆盖 | **CLOSED** ✓（1 处新残口见 `A-5`） | `same.txt`=版本A → 写版本B 落 `same.aff67a3d.txt`，**版本A 原样保留**；同内容重写→幂等同路径；版本C→`same.0b20b169.txt`；前缀碰撞时自动加长到 16 位（`same.6d97973518f83c03.txt`）；写侧穿越 `../../` / 绝对路径 → `ValueError`；经**真执行器** `raw_name` 同名不同内容同样落两份 |
| **D-7** docstring 强度 > 代码 | **PARTIAL / 文字层 REGRESSED** | ✓ "不再是变相孤儿"已删；✓ B/C 已如实降级为「静态绊线」，`KNOWN_STATIC_LIMIT` note **每次运行可见**（含 exit 0 时，我实测确认）。**但**同一提交新写的 `executor.py:12` 写"生产接线…**属阶段② 采集层**"，与本提交自己纠正的 `G-13`（**阶段①**）**相反**；`phase1_gap_register.md:103` 同一句话仍在 → 同一文件内 `G-13` 行与结论段**自相矛盾** |

### 2.1 D-2 复核细节（为什么只能给 PARTIAL）

```
process_raw_file(缺文件)                  OK    blocked/missing_source  SOURCE_MISSING: raw/nope.txt
process_raw_file(缺文件, 深层)            OK    blocked/missing_source
handle_external_request(kind=data, {})    OK    blocked/payload  MISSING_PAYLOAD_FIELDS: [claim_nature, claim_form, tier]
handle_external_request(kind=data, 缺tier) OK   blocked/payload  MISSING_PAYLOAD_FIELDS: ['tier']
handle_external_request(rule_write, {})   OK    blocked/rule_write  RULE_WRITE_BLOCKED
handle_external_request(kind='')          OK    blocked/unknown
process_raw_file(raw 路径是**目录**)      ★ESCAPED★ IsADirectoryError
process_raw_file(文件 0000 不可读)        ★ESCAPED★ PermissionError
process_raw_file('raw/../rules/scope.yaml') OK  status='ok'  ← 并把 rules 文件副本写进 raw/（见 A-2）
```

`FileNotFoundError` 被单独 catch（`executor.py:214`），因此 **`OSError` 减 `FileNotFoundError` 的其余成员全部逃逸**。这不是"边界模糊"，是 catch 粒度选窄了。

### 2.2 D-3 复核细节

见 §3 的完整矩阵。要点：**已修 4/4，但新绕过 4 个**；且新绕过的 token **全部是字面量、静态完全可见**，因此**不属于**守卫自己声明的 `KNOWN_STATIC_LIMIT`（该 note 只声明"**计算得到的路径**静态不可判定"，例：receiver 位置拼接、f-string 变量目标）。我实测的 N5/N11/N15/N16 落在声明的局限内（exit 0，**自洽**，不算缺陷）；N1/N2/N3/N6 **超出**声明的边界。

### 2.3 D-5 复核细节（这条是本轮质量最高的修复）

关键点是它**用真 git 仓库替代了夹具副本上的空跑**。我独立复现了「真空」与「非真空」两侧：

```
①未改动夹具           exit=0  staged_facts_files=0  真空note=True    ← 旧断言的真相
①'git add 但无内容变化  exit=0  staged_facts_files=0  真空note=True
②注入后纯追加          exit=0  staged_facts_files=1  真空note=False   claims 行数 1→2
③改写既有行            exit=1  [FATAL] 存在被删除/改写的既有行
④删除整份 JSONL        exit=1  [FATAL] 整个 JSONL 被删除（真源不得删除）
```

③④ 是我自造的反事实（团队只写了③）。**双向都可证伪** —— 这才叫证据。

### 2.4 D-6 复核细节

`store_raw` 的语义现在是「**永不覆盖既有原始物**」，且对**相同内容**保持幂等。我额外测了三个边界：
- hash 路径前缀碰撞 → 自动加长（8→16 位）✓
- hash 落点已存在**且是非法 UTF-8** → `ExternalTextDecodeError` **逃逸给调用方**（`A-5`）
- `dedup=False` 且内容相同 → 会多落一个副本文件（这是 `dedup=False` 的字面语义，**不判为缺陷**，仅备注）

---

## 3. 对抗性重测 D-3（我自造的绕过矩阵，共 24 个探针）

方法：把候选模块写进临时 root 的 `scripts/guard/`，跑**真子进程** `injection_guard.py`，记录退出码与命中的违例行；每个探针用完即删。基线（无探针）exit 0；夹具 `rules/` 保持 0444。

### 3.1 已修确认（团队声称修好的 4 例，我自己重造）

| 探针 | 期望 | 实得 | 命中的违例（用于归因） |
|---|---|---|---|
| `import subprocess` | exit1 | **exit1** ✓ | 措施3·工具白名单 `'subprocess'` / import 禁用模块 |
| `getattr(os, 'system')(cmd)` | exit1 | **exit1** ✓ | 措施3 `'getattr:system'`（字面量落工具原语集合） |
| `append_records(root, stem, rows)` | exit1 | **exit1** ✓ | 判据·不产生建议 `append_records:Name`（fail-closed） |
| `append_records(root, f'{x}', rows)` | exit1 | **exit1** ✓ | 判据·不产生建议 `append_records:JoinedStr`（fail-closed） |

### 3.2 我新造的绕过形式

| # | 形态 | 实得 | 归类 |
|---|---|---|---|
| **N1** | `__builtins__['__import__']('subprocess')` | **exit 0 ★绕过★** | **该拦没拦** —— `'__import__'` 与 `'subprocess'` 都是字面量，只是包在 Subscript 里（`_dotted` 对 Subscript 返回 `""`） |
| **N2** | `import builtins; builtins.exec('import subprocess')` | **exit 0 ★绕过★** | **该拦没拦** —— ① `_is_tool_primitive("builtins.exec")` 不匹配末段 `exec`；② `DYNAMIC_CALL_TOKENS` 用**全等**比较，`'import subprocess'` ≠ `'subprocess'` |
| **N3** | `from schema.store import append_records as ar` → `ar(root, stem, rows)` | **exit 0 ★绕过★** | **该拦没拦** —— `callee == "append_records"` 被别名一次改名绕过（**这正是"一次普通改写"**） |
| **N6** | `os.__dict__['system'](cmd)` | **exit 0 ★绕过★** | **该拦没拦** —— 同 N1（Subscript 的 slice 是字面量 `'system'`） |
| N5 | `m = getattr(os, 'sys' + 'tem'); m(cmd)` | exit 0 | **原理性静态边界**（运行期计算，与已声明的局限同类） |
| N11 | `getattr(os, name)`（变量名） | exit 0 | **原理性静态边界** |
| N15 | `(root/'facts'/('recommend'+'ations.jsonl')).write_text('x')` | exit 0 | **原理性静态边界**（且已有锁定测试 + note 声明） |
| N16 | `open(f'{root}/facts/{stem}.jsonl','a')` | exit 0 | **原理性静态边界**（同上） |
| N4 | `append_records(root, **{'stem': var})` | **exit1** ✓ | fail-closed（`MISSING_STEM_ARG`） |
| N7 | `importlib.import_module('subprocess')` | **exit1** ✓ | 措施3（`importlib.import_module` 属性访问） |
| N8 | `functools.partial(os.system, cmd)` | **exit1** ✓ | 措施3（`os.system` 属性访问） |
| N9 | `from os import system as sh` → `sh(cmd)` | **exit1** ✓ | 措施3（`ImportFrom` 还原为 `os.system`） |
| N10 | `__import__('subprocess')` | **exit1** ✓ | 措施3（`__import__:subprocess`） |
| N12 | `stem = 'recommendations'; append_records(root, stem, rows)` | **exit1** ✓ | fail-closed（`append_records:Name`） |
| N13 | `import subprocess as sp` | **exit1** ✓ | 措施3 |
| N14 | `import pty` | **exit1** ✓ | 措施3（import 禁用模块） |

反向对照（必须 **exit 0**，证明启用了 fail-closed 也没退化成见词就杀）：`append_records(root,'claims',rows)`、`os.path.join(a,b)`、`getattr(obj,'value')`、`mapping.get(key)` → **4/4 exit 0** ✓

**结论**：`B·①`（import 禁用）、`B·②`（属性访问）、`B·③`（动态调用字面量参数）、`C`（`append_records` stem fail-closed）的**设计方向正确且有效**；缺口集中在**"同一语义换一种 AST 形状就看不见"**：Subscript 取成员（N1/N6）、别名的导入改名（N3）、属性末段（N2）。修法都不需要新理论，成本低：
- Subscript：`visit_Subscript` 检查 `slice` 为字符串字面量且落在 `DYNAMIC_CALL_TOKENS` → 直接判违例；
- 别名：预扫描 `ImportFrom` 记录 `append_records` 的本地别名并一同匹配（或对 `schema.store` 的改名导入直接 fail-closed）；
- 属性末段：`Attribute.attr` 落在 `{eval,exec,compile}`（或 `TOOL_PRIMITIVES` 末段集合）即判违例；`eval/exec/compile` 的参数是**代码文本**，应改**包含**判定而非全等。

★ **为什么这些缺口不能只用"运行时效果断言兜底"**：效果三元组 (b) 断言的是「处理前后 `recommendations.jsonl` 行数不变」，它检验的是**当前这份代码在一次测试运行里的行为**；而 B/C 静态绊线守的是"**将来有人改了 `scripts/guard/**` 的代码**"。两者覆盖不同时间点，不能互相替代。

---

## 4. `exit 1` 归因唯一性 + D-7「零行为变更」

### 4.1 去掉 `rule_hint` 之后，`exit 1` 还能唯一归因吗？—— 能，但依据变了

- `tests/injection/test_prompt_injection.py` 中 `rule_hint` 残留 **0 处** ✓（我实测 `grep -c` = 0）。
- `assert_rejected` 仍然要求 `returncode == 1`（`exit 2` 判不通过），所以"断言退化成一个 '非零即可'"**不成立**。
- 归因唯一性现在建立在**同条件反向对照**上：`test_injection_guard_allows_literal_non_recommendation_stem` 与 4 条拒绝探针**共用** `_probe_guard` / `_restore_rule_perms` / 同一夹具形状 / 同一命令，它要求 exit 0。既然在同一条件下 exit 0 可达，则其余 4 条的 exit 1 就不是"环境/夹具导致的恒 1"。**这是成立的论证**（我已实测：同一夹具下反向对照确实 exit 0）。
- 我另外逐条核对了命中的**违例行文本**（见 3.1 表第 4 列），确认 4 条拒绝探针命中的分别是 `'subprocess'` / `'getattr:system'` / `Name` / `JoinedStr`，与探针一一对应。

**判定**：断言强度从「退出码 + 文字」降为「退出码 + 同批反向对照」，属**有意的解耦**，且**未退化**。可以接受。

### 4.2 「零行为变更」是否成立？—— 措辞解耦部分成立（有结构性证明）；D-3 部分**确实变了（故意）**

结构性证明（比跑两遍更硬）：
```
scripts/_common.py:51-52   def passed(self): return not self.violations
scripts/_common.py:131-137  if report.passed: return EXIT_OK  →  否则 EXIT_VIOLATION
scripts/_common.py:38-40   Violation.render() 只用于 print
```
`Violation.reason` / `render()` **不参与**退出码计算 → **改守卫的说明文字在原理上不可能改变退出码**。加上 `rule_hint` 残留 = 0，可判定"措辞解耦 = 零行为变更" ✓。

同时我必须指出：同一提交里 **`B`/`C` 的行为确实变了**（我实测原 4 个绕过形态从 exit 0 → exit 1）——这是 `D-3` 的**有意修复**，不是措辞副作用。两者不要混在"零行为变更"一句话里。

> 说明：我没法"跑一遍改动前的代码"来对比（那需要 checkout 旧提交 = 改工作区，违反铁律），故以**结构性证明 + 残留 0** 替代。此项在 §10 记为方法学限制。

---

## 5. AC 重新判定（只列受影响的 6 条；其余 29 条维持第一轮 PASS）

| AC | 第一轮 | 第二轮 | 依据 |
|---|---|---|---|
| `AC-15` | FAIL | **PASS** ✓ | 追加式证据已非真空：真 git 仓库 + `staged_facts_files: 1` + 反事实 exit 1（我自测③④两条反事实） |
| `AC-25` | FAIL | **PASS** ✓ | 同上（`AC-25` 的唯一问题就是那条真空附加断言） |
| `AC-05` | FAIL | **FAIL**（换了原因） | 被点名的两条逃逸已闭合；但**同族** `IsADirectoryError` / `PermissionError` 仍逃逸（`A-1`），且判据枚举的第 2 例 `rules/` 目录缺失实得 **exit 1** 而非判据写的 **exit 2**（`A-10`） |
| `AC-01` 真跑通 | FAIL | **FAIL** | 真实仓库 `raw/` 仍只有 `.gitkeep`、`facts/claims.jsonl` **0 行**（我本轮复核：`raw/` = `['.gitkeep']`） |
| `AC-03` 真接线 | FAIL | **FAIL** | `process_external_text` / `handle_external_request` 仍无生产调用方；`run_daily` 实跑 8 步全 `gap`（我实跑：`blocked=True`、`gaps=14`、step 1 gap 原文 = "step 1 (ingest_public_information) 未注册处理器"）。**注意** `AC-03` 自己给了"或注册为 CI/pre-commit 检查器"的替代分支 —— 该分支对 **守卫**（`injection_guard` ✓ 两处注册 + 门禁日志可见）成立，对**执行器**不成立（执行器不是检查器、未注册） |
| `AC-13~22` / `AC-23~32` | PASS（带保留） | **PASS（保留不变）** | 见下 |

### 5.1 `AC-13~22` / `AC-23~32` 的判别力（我先前提法的量化版）

我把 10 段注入文本 + 10 段对照文本 + 1 段无害文本 + 1 段空文本，全部喂进**真执行器**，比较结果元组 `(status, tool_calls, blocked_kind, claim_id, rules 不变, recommendations 行数)`：

```
22 段文本 → 只有 2 种结果元组
  ('ok',       0, '-', True,  True, 0)   ← 21 段（含全部 10 注入 + 全部 10 对照 + 无害文本）
  ('degraded', 0, '-', False, True, 0)   ← 1 段（空文本）
→ 20 段注入/对照文本的结果元组是否相同：True
→ 真正改变结果的只有「空文本」
```

**结论（与第一轮一致，但现在有量化证据）**：`AC-13~22` 与 `AC-23~32` 对"注入语义"的判别力为 **0** —— 把注入文本换成完全无害的文本，两组断言同样全绿；唯一真实判别子是"空文本"（`AC-34`）。它们真正证明的是「**该链路无副作用**」（规则 hash 不变、无工具调用、不写建议、文本仅作数据），这**是**有效且重要的断言，但**不能**表述为"系统识别 / 抵御了注入"。

★ **公平地说**：团队已把这条判断**如实**写进 `phase1_gap_register.md`（§"审计员最重要的概念判断"）并写明"这是设计取向的必然结果（`R-01` + `AC-33` 要求判据取效果、禁词面判定）"。**这一点我做对了被记录，故不重复记为缺陷**；本节的作用是给后继批次留下可复算的数字。

★ 与 `D-3` 的回归测试对比：新加的 7 条 `injection_guard` 探针**有真判别力**（4 拒 1 放 2 已知局限，条条对应不同代码形态）—— 这组是本批次新增测试里最能证伪的一组。

---

## 6. 新发现清单（按严重度排序）

### A-1（中）`process_raw_file` 同类异常仍逃逸 —— `AC-05` 修的是两个点，不是一类
- 位置：`scripts/guard/executor.py:201-225`
- 复现：`mkdir raw/adir.txt` 后 `process_raw_file(root, "raw/adir.txt", ...)` → `IsADirectoryError`；`chmod 000 raw/noperm.txt` 后读取 → `PermissionError`
- 期望 vs 实际：判据意图是"执行器侧明确降级（blocked），不吞异常、不 500"；实际异常直接抛给调用方
- 修法：`except OSError as exc:`（放在 `ExternalTextDecodeError` 之后）→ `blocked/SOURCE_UNREADABLE`

### A-2（中）读侧路径穿越未校验（与写侧不对称）
- 位置：`scripts/guard/executor.py:200`（`path = root_path / relpath`，直接读）；对照 `rawsink._validate_name` 只在**写**侧被调用
- 复现：`process_raw_file(root, "raw/../rules/scope.yaml", ...)` → **`status='ok'`**，且 `raw/` 下出现 `scope.yaml` 副本、`facts/claims.jsonl` 新增一行
- 影响：调用方可用 `../` 让执行器把**内部文件**（`rules/`、`facts/` 等）当"外部文本"摄入并主张化 —— 反转了"外部文本只从 `raw/` 来"的前提（`Ch9 §3.4.6` 措施①）
- 修法：读侧复用**同一个** `_validate_name`（`G-06` 唯一真源），不要新写第二套校验

### A-3（中）`injection_guard` B/C 的 4 个新绕过（token 全字面量，超出已声明的静态边界）
- 位置：`scripts/checks/injection_guard.py:106-113`（`_dotted` 不认 `Subscript`）、`:178`（`callee == "append_records"` 不吃别名）、`:117`（`_is_tool_primitive` 不匹配 `builtins.exec` 的末段）、`:185`（`arg.value in DYNAMIC_CALL_TOKENS` 为**全等**）
- 复现：见 §3.2 的 N1 / N2 / N3 / N6（全部 exit 0）
- 期望 vs 实际：`D-3` 的修复目标是「换变量/getattr/f-string/拼接就一次绕过」这一**类**；实际只覆盖了原报告的 4 个**具体形状**
- 分类：**该拦没拦**（非原理性边界）—— 因为 `'__import__'` / `'subprocess'` / `'exec'` / `'system'` / `'append_records'` 这些 token 在 AST 里**完全可见**

### A-4（中）`D-2` / `D-6` 的修复**零回归测试** → 声明与实现缺机器绑定
- 实测：`tests/` 中 `SOURCE_MISSING` / `MISSING_PAYLOAD_FIELDS` / `DECODE_DEGRADED` / `_content_addressed_sibling` 命中数 **全为 0**
- 意味着：本提交给 `D-3`（7 条探针）与 `D-4`（6 条）都配了回归测试，偏偏没给 `D-2`/`D-6` 配 —— 而这两个修复引入的新分支（新的 `except`、新的 `read_external_text` 调用点）一旦被后续重构删掉，**没有任何测试会红**
- 这与本项目自定铁律（`CONVENTIONS.md` 卷首："只写在文档里、没有检查器强制的规范等于不存在"）直接冲突

### A-5（低-中）`D-6` 新增调用点会把 `ExternalTextDecodeError` 抛给调用方
- 位置：`scripts/guard/rawsink.py:74`（`read_external_text(candidate)`，在 `store_raw` 内）
- 复现：先造 `raw/same.<sha256前8>.txt`（内容为非法 UTF-8），再 `store_raw(root,"same.txt","版本D")` → **`ExternalTextDecodeError` 逃逸**
- 期望 vs 实际：`store_raw` 的契约是"永不覆盖、返回落点路径"；实际在极端输入下变成"抛异常"
- 修法：碰撞检测失败时继续加长前缀 / 视为"不可判定"再换长前缀，而不是把解码异常透传

### A-6（低-中）`G-13` 纠正后的两处残留矛盾（同一提交内自相矛盾）
- `scripts/guard/executor.py:12`："生产接线（把本入口接进真实采集链路）**属阶段② 采集层**，见 `G-13`"
- `system/reports/phase1_gap_register.md:103`："其生产接线（`G-13`）**属阶段② 采集层**，阶段① 内不越阶实现（纪律 12）"
- 而**同一提交**把 `phase1_gap_register.md:25` 的 `G-13` 改成："★ **原判'属阶段② 采集层'是错的，已纠正**：…属**阶段① 编排缺陷 + 声明脱节**"
- 影响：这是本批次"声明强度 = 事实"主题的**镜像缺陷**；后续读者按 docstring 走会重新得出被推翻的旧结论

### A-7（低-中）`gap_register` 未随修复更新（修复记录只落在两份新报告里）
- `phase1_gap_register.md` 的「批次 4 独立审计 —— 结论与已处理项」表中，`D-2` / `D-3` / `D-5` / `D-6` / `D-7` 五行仍写 `OPEN —— 待工程师…` / `待 QA…`
- `:104` "结论一句话"仍写"独立审计另开 **4 条 OPEN**（`AC-05` 异常逃逸 / `B·C` 可绕过 / `AC-15` 证据真空 / `raw/` 静默覆盖）" —— 这 4 条本提交已修 3 条 + 1 条部分
- 影响：审计留痕文档与事实相反（此处是**少报完成**，不是虚报，故风险低于"假绿灯"，但登记册是下游采信的真源）

### A-8（低-中）`G-07` 规范在现行仓库上不成立，且**无机器强制**
- 规范原文：`每新增守卫必须**同时**注册进 run_all_gates.py 与 pre-commit.sh（防孤儿）`；强制手段列写"守卫注册在跑测器里可核对"
- 实测：`run_all_gates.py` 引用 **20** 个门禁；`pre-commit.sh` 只跑 **8** 个（append_only / rules_lock / registry_schema / schema_sync / conflict_scan / no_placeholder / **injection_guard** / **verification_policy_guard**）。**13 个守卫只在 run_all_gates 里**（含 `freeze_guard`、`launch_guard`、`anti_padding`、`return_guard`、`neutrality_check`、`module_denylist`、`no_signal_day`、`pipeline`、`stage_gate` 等）
- 机器强制：全仓**没有**任何测试/守卫核对"两个注册点集合一致"；唯一的注册断言是 `tests/injection/test_wiring_guards.py:42` 查 `registry_schema_guard.py` 在 `run_all_gates.py` 中（单点、单守卫）
- 建议：① 规范改为**明确的分层清单**（pre-commit = 快集、run_all_gates = 全集，并写明"新增守卫至少进全集；属纪律 2/4/9/10/12 的必须同时进 pre-commit"）；② 给"两集合关系"加机器断言；③ 若暂不做，按本文件自定规则标 `⚠️ 人工`

### A-9（低）`V-04` 的断言用**裸文本包含**，注释里的 `VAR=0` 也能通过
- 位置：`scripts/checks/verification_policy_guard.py:199-203`（`f"{var}=0" in text`，未抹白注释/字符串）
- 现状：`run_pytest.sh:27-28` 与 `verify.py:162-163` 都是**真设置**，故当前无假通过 ✓
- 风险：与 `G-04`（"注释与 docstring 在扫描前抹白"）的教训**反向** —— 将来把 `export` 挪进注释，守卫会继续放行。建议复用同一套抹白工具再判定

### A-10（低）`AC-05` 第 2 例枚举用例的退出码与判据不符（需裁定改哪边）
- 判据：`rules/` 目录缺失 → 检查器 **exit 2**
- 实际：`injection_guard` / `rules_lock_guard` 均 **exit 1**，10 条违例 "`rules/xxx.yaml` 已登记但文件不存在（真源不得删除）"（纪律 10）
- 评价：两者都**阻断**（无静默放行），实现的行为更贴合纪律 10 的语义。属"判据文字 vs 实现归类"的裁定项，**不宜由实现方自行裁决**（`R-04`）

### A-11（低）`CONVENTIONS.md §V-02` 批次表陈旧
- 表内写 `gates | run_all_gates.py（19 项门禁）` → 实际 **20 项**（`run_all_gates` 汇总行也是 20）
- 表内"实测"列：`injection 13.3s`（我实测 **21.8~22.3s**）、`guards 1.9s`（我实测 **2.9~3.2s**）、`unit 1.5s`（我实测 **1.63s**）
- 规范自己写了"超时随实测更新" → 该列应随之更新；本项不影响超时上限安全性（120s / 60s 仍有 3~5 倍余量）

### A-12（低）`V-01` 规范文字与"正确用法"的措辞张力
- 规范："**不得**用一条命令跑完整个测试套件 + 全部门禁 + 阶段判据"
- 正确用法里却允许 `verify.py --batch all`（确实是**一条命令**跑完全部批次）
- 机器强制只保证了两件更本质的事：无 `--batch` → exit 2；不存在以裸 `tests` 为目标的批次。**实质风险（单一超时吞掉一切）已被结构性消除**，但规范文字应改成"不得让多批共用**一个子进程/一个超时**"，否则规范与用法表面冲突

### A-13（nit）`pipeline.py:172-175` 的注释把 `D-14` 误述为"第二轮独立审计"
- 该注释写"第二轮独立审计指出：本函数此前**零调用**…现在它就在主流程里"
- 事实：`pipeline.py` 自 `8b41c94`（阶段① 首提交）**从未改动**；该发现是 `gap_register` 里的 `D-14`（前期阶段① 审计），与批次 4 的第二轮审计无关。措辞易被读成"批次 4 第二轮审计提的"，建议改标编号

---

## 7. 对 `G-13` 判据与 `T-08` 的独立意见

### 7.1 `G-13`：我**同意**新判据，并认为它比原判**更严**

我独立核实的四个事实（全部由我自己的命令/实跑得到）：

| # | 事实 | 我的证据 |
|---|---|---|
| 1 | `rules/pipeline.yaml` 声明 step **1–6** `implemented_in_first_version: true` + `blocking: true`，**且 step 1–6 没有 `hook`、没有 `gap_behavior`**；只有 step 7–8 是 `false` + `hook` + `gap_behavior: explicit_gap_when_hook_absent` | 直接读 `rules/pipeline.yaml`（0444 锁定；含 `completeness.on_missing: blocked`、"7/8 步…未实现时**显式标 gap**，不得静默跳过"） |
| 2 | `pipeline.py` 一个 handler 都没注册 → 实跑 8 步**全 `gap`** | 实跑 `Pipeline(root).run_daily(...)`：`blocked=True`、`gaps=14`、`steps=[(1,'gap')…(8,'gap')]`，step 1 gap 原文 "step 1 (ingest_public_information) 未注册处理器" |
| 3 | **没有静默成功**：未注册的 `blocking` 步会置 `blocked=True`，`assert_steps_complete` 另记违例 | 同上 + 读 `pipeline.py:150-152 / 176-178`；与 `on_missing: blocked` 一致 |
| 4 | `process_external_text` **确实能**当 step 1 的实现，判据可达 | 我按判据注册 step 1 handler 后实跑：step 1 → **`ok`**、`raw/step1_sample.txt` 落盘、`claims.jsonl` = **1 行**、`recommendations.jsonl` = **0 行** |

**判断**：`G-13` 的症结是「**编排器未兑现声明**」，而声明是**阶段① 的产物**（`pipeline.py` 属阶段①，`rules/pipeline.yaml` 是 0444 锁定的设计真相源，且被 `Ch1 §D.1` 引用）。因此归为**阶段① 编排缺陷 + 声明脱节**是正确的；原判"属阶段② 采集层"确实站不住（那会把它推出本批次验收范围）。

**并且这次改判是"变严"而非"变松"**：原判 = 出范围 → 不阻塞；新判 = 进范围 → `AC-01`/`AC-03` 保持 FAIL。**这不是把失败改判成别的以求脱身，而是把原来被推出范围的失败重新纳入。** 我认可。

唯一要补的：判据应显式写明"**handler 必须注册在 `run_daily`；仅提供可被调用的路由入口 ≠ 接线**"（否则 `handle_external_request` 又可以自称"有生产调用方"），并写明 `raw/` 与 `claims.jsonl` 的**真实 `system/`** 落库是**观测点**（不可用夹具代跑）。

### 7.2 `T-08`：**登记为张力是对的**，不是"把失败改判成张力"

我按四条可检验的标准逐一验证：

| 检验 | 结论 |
|---|---|
| ① `T-08` 是否**吸收/豁免**了任何批次 4 验收项？ | **否**。`G-13`（step 1）单独保留为 `OPEN` 并带可测判据；`AC-01`/`AC-03` 保持 FAIL |
| ② 是否**只能**由需求方裁定？ | **是**。`rules/` 0444 锁定 + 纪律 10 禁止实现方改；两个选项（把 step 2–6 改回 `false` + 补 `gap_behavior` ↔ 确认"8 步骨架首版真实现"）都会**改变项目范围**，超出实现/QA 权限（`R-04` 要求上报不自行裁决） |
| ③ 事实是否记录准确？ | **是**。声明与"全 gap"现实我都独立复核过（§7.1 事实 1、2） |
| ④ 是否**掩盖**了新的静默成功？ | **否**。step 2–6 未注册 → `blocked=True` + 记 `gap`，符合 `on_missing: blocked`；我实跑确认没有"报 ok 的空执行" |

**为何 step 1 与 step 2–6 可以不对称处理（实现方按声明实现 step 1、却把 2–6 记为张力）**：step 1 的实现体（数据/指令分离执行器）**本就是阶段① 的 C 档自建项**（`Ch9 §3.2.1`，即 `G-02` 的由来），因此不需要 ②③ 层组件就能做；而 step 2–6 的实现体（核验/传导/估值/决策）确实属 ②③ 层。**这个不对称是有实据的，不是任意选择。**

**我建议补一条（不影响判定）**：`T-08` 的"处置"列应写出**运行期代价** —— 因为 step 2–6 `blocking: true` 且无 `gap_behavior`，**每次 `run_daily` 都会 `blocked=True`**，`publish_hook` 永不触发、`check_record` 的 task 状态恒为 `failed`。需求方看不到这个代价就难判断选项 ② 的真实范围。

---

## 8. 全量分批复跑（我自己的数字，逐批串行）

| 批次 | 结果 | 耗时 / 上限 |
|---|---|---|
| `unit` | ✓ exit=0 | 1.63s / 60s |
| `conflict` | ✓ exit=0 | 0.29s / 30s |
| `guards` | ✓ exit=0 | 3.17s / 60s |
| `injection` | ✓ exit=0 | 22.27s / 120s |
| `root` | ✓ exit=0 | 0.26s / 30s |
| `gates` | ✓ exit=0，**20 项门禁非零计数 = 0** | 2.21s / 60s |
| `stage` | exit=1 = 阶段① `PASS` + 阶段②–⑤ 全 `BLOCKED`（纪律 12 预期） | 0.17s / 30s |

- 通过用例数（读我自己的 `reports/verify_*_latest.log`）：**42 + 6 + 56 + 109 + 8 = 221 passed**
- `skipped` / `xfail` / `error` / `failed`：**各批均为 0** ✓（无静默跳过）
- 全程无超时；未出现第一轮的 `exit 137`；临时目录已清理，`git status` 干净 ✓

> 对比：第一轮同批次合计 210 passed，本轮 221（增量来自 `D-4` 6 条 + `D-3` 7 条回归 —— 其中 `D-3` 的 7 条是本轮复核的重点对象，见 §3）。`batch4_injection_dod.md` 里"173 tests / 18 gates"的旧数字仍待更新（属既有登记问题，非本提交引入）。

---

## 9. `CONVENTIONS.md` V/G/P/R 可机器强制性复查

| 规范 | 声明强制手段 | 我的核验 | 结论 |
|---|---|---|---|
| **V-01** | `verification_policy_guard` 断言 ① 无 `--batch` 必须 exit 2；② 无裸 `tests` 批次 | **实证**：`verify.py`（无参）`exit=2` ✓，`--batch unit` `exit=0` ✓；守卫 `scanned no_batch_exit_code: 2`、`pytest_targets: 5` | **真机器强制** ✓（文字张力见 `A-12`） |
| **V-02** | 每批 `0 < timeout ≤ 300s`；`BATCHES` 与 `ORDER` 键集合一致 | 守卫 `scanned max_timeout_s: 120`，含 7 批；代码 `:145-164` 逐条判定 | **真机器强制** ✓（表陈旧见 `A-11`） |
| **V-03** | `124` 必然判不合格且说明文字含"超时" | 守卫 `:168-186` **对每批调用 `batch.verdict(124, "")`** 并同时断言"不 ok"且 `"超时" in why` —— 这是**真反事实**，不是空跑 | **真机器强制** ✓（本条与 `D-5` 的教训同标准，做对了） |
| **V-04** | `run_pytest.sh` 与 `verify.py` 都把两个 broker 变量置 0 | 实证：`run_pytest.sh:27-28` 真 `export …=0`；`verify.py:162-163` 真子进程 `env` 置 `"0"` ✓ | **真机器强制** ✓（判定方式偏松见 `A-9`） |
| **V-05** | ⚠️ 人工 | 确为人工 + `verify.py` 自动留档（`reports/verify_<批>_latest.log`，我本轮即读该文件） | **如实标注** ✓ |
| **V-06** | `tests/` 下每个测试文件必须被某批次覆盖 | 守卫 `scanned test_files: 14`、`test_files_uncovered: 0`；`tests/{unit,conflict,guards,injection}` + `test_ch11_invariants.py` 均有批次 | **真机器强制** ✓ |
| **G-01/G-02/G-03/G-05/G-06** | 各守卫自查 + `tests/guards|injection` 既有断言 | 引用的测试文件**全部存在** ✓（`test_exit_code_contract.py` / `test_verification_policy.py` / `test_audit_regressions.py` / `test_wiring_guards.py` / `test_append_only.py` / `test_guards_reject.py`）；`G-03` 的 `note` 机制我在 `injection_guard` 上实测可见 | 大体**成立**（但附录把它写成一整类"既有断言"偏含糊） |
| **G-04** | 抹白注释/docstring、保留普通字符串 | `tests/injection/test_guards_reject.py` 6 条字符串型回归**双向对照**齐全（我读文件确认：3 类字面量必须命中 + docstring/注释必须放行） | **成立** ✓ 且是本批次质量最高的一组 |
| **G-07** | "守卫注册在跑测器里可核对" | **实测不成立**：pre-commit 8 个 vs run_all_gates 20 个（13 个仅后者）；无任何断言核对两集合 | **⚠️ 实为人工 / 规范文字亦不成立** → `A-8` |
| **P-01~P-05** | 附录称"既有断言 + 各守卫自查" | `P-01`（单遍 AST）、`P-03`（不急切导入 pydantic）在 `injection_guard` 上有结构性体现；`P-02` 有 `_common._cached_yaml`；**但 `P-05`（新守卫 < 0.5s）没有任何断言**，只有日志里的耗时数字 | **部分成立**；`P-05` 与附录的整体表述应按自定规则标 `⚠️ 人工` |
| **R-01/R-02** | `tests/injection/test_guards_reject.py` + 各守卫 docstring 自检 | `R-01`（禁绝对行号）我未找到专门的锚点格式断言；`R-02`（docstring 只写代码做到的事）**本提交自己就违反**（`A-6`） | **部分成立** → 与 `A-6` 合看 |

**总评**：V 系列是**真机器强制**的典范（V-03 的反事实写法尤其正确，值得作为其他守卫的模板）；G/P/R 系列中，**G-07 与 P-05 属"规范文字 > 机器绑定"**，按该文件自己的铁律应标 `⚠️ 人工` 或补断言。

---

## 10. UNKNOWN / HUMAN_REVIEW / 方法学限制

**UNKNOWN：0**（所有探针与批次都跑成了，无"想跑跑不了"的项）。

**方法学限制（如实记录，不计为 PASS）**：
1. "**改动前**逐条对比"无法执行 —— 那需要 checkout 旧提交（改工作区，违反铁律）。我改用**结构性证明**（`CheckReport.passed = not violations`，消息不进入退出码路径）+ 残留检查，替代"跑两遍"。若需求方要求运行时双向对照，需授权在**独立 worktree** 里重放。

**HUMAN_REVIEW-1**：`G-13` 的阶段归属（阶段① vs 阶段②）**我判为阶段①且更严**，但最终以 `T-08` 的需求方裁定为准 —— 若需求方选"把 step 1–6 改回 `false`"，`G-13` 会随之降级，`AC-01/AC-03` 也会改写。**在该裁定作出前，`AC-01/AC-03` 必须维持 FAIL。**

**HUMAN_REVIEW-2**：`AC-05` 第 2 例（`rules/` 目录缺失 → 实得 exit 1，判据写 exit 2）需裁定改判据文字还是改守卫归类（`A-10`）。

**HUMAN_REVIEW-3**：`G-07` 的正确形态 —— pre-commit 跑哪一档守卫集（"最小纪律集"还是"全集"）是产品/流程决策（`A-8`）。

---

## 11. 一句话：现在该修什么

**先修 `A-1`（`except OSError`）与 `A-2`（读侧复用 `_validate_name`）这两处真漏洞并给 `D-2`/`D-6` 补上回归测试（`A-4`），再把 `A-3` 的四个字面量绕过补齐（Subscript / 别名 / 属性末段，都是低成本静态判据）；文字层面必须一口气把 `A-6`/`A-7` 的"阶段②"残留与五行 `OPEN` 改齐 —— 否则下一轮审计还会在同一处抓到"声明与事实不一致"。`AC-01/AC-03` 在 `T-08` 裁定前不得标完成。**

---

## 附录：本轮证据一览（可复算）

| 证据 | 位置 / 命令 |
|---|---|
| 变更面 | `git log --oneline -5`、`git show --stat HEAD`、`git diff HEAD~1 HEAD --name-only` |
| D-2/D-6 探针 | 临时脚本 `system/tests/.work/audit-r2/probe_d2_d6.py`（已删） |
| D-3 绕过矩阵 | 临时脚本 `.../probe_d3_bypass.py`，24 个探针 × 真子进程（已删） |
| D-5 非真空 | 临时脚本 `.../probe_d5.py`（真 git 仓库 + 4 步反事实，已删） |
| G-13 事实 | `rules/pipeline.yaml` 直读 + `Pipeline.run_daily` 实跑（含注册 step 1 handler 后的 `ok` 前向验证） |
| 判别力量化 | 22 段文本 × 真执行器结果元组（已删） |
| 批次证据 | `python system/scripts/ops/verify.py --batch {unit,conflict,guards,injection,root,gates,stage}` → `reports/verify_*_latest.log` |
| 门禁 | `run_all_gates.py` 20 项 exit 汇总，非零计数 0 |
| 洁净性 | 审计前后 `git status --porcelain` 均为空 |

*本报告的全部数字均为本轮实测；未引用主理人、工程师或 QA 报告中的任何数值。*
