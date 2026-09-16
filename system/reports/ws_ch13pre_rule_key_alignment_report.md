# 批次 13-pre 方向 1 —— 「键对齐守卫」交付报告

> 对象：`system/scripts/checks/rule_key_alignment_guard.py`（新增）
> 提交：**`fd6dba4d927282d7cd02801488b9779fb35c8b73`**（分支 `ws/ch13-e-benchmark-fields`，
> 已合并 `main`；R2 的基线树为 **`e9a009b`**；提交时 `pre-commit` **全部门禁放行**）
> 依据：任务卡 `R5`「键对齐守卫：AST 抽代码实际读取键 ↔ `rules/*.yaml` 实有键，**单向缺失即红**」
> 纪律：所有读数**带树**（口径 9）+ 判词**带对象与 SHA**（口径 10）。

### 修订记录

| 轮次 | 基线树（HEAD） | 改了什么 | 为什么 |
|---|---|---|---|
| R1 | `d25bfed` | 首次交付 | — |
| R2 | `e9a009b` | ① ★ **收回 §⑦-3 的根因归因**（原写「BSD `grep` 的 `\|` 假零命中」）；<br>② ★ **关闭 §⑥ 的端到端 pytest 欠账**（E 口径，`9 passed` ×2）；<br>③ 订正 §⑦-1「回合级删除预算」这一措辞 | ① 该归因**是错的**；错话留在**已合入主干**的报告里 ⇒ 必须**显式收回**，不能只在新文档里纠正（否则读者读到的是旧结论）。<br>② R1 只是**承诺**"下一轮补跑"，承诺不是证据。③ 实测配额**不随轮次恢复**（`100270 → 108656`）|

---

## §① 一句话结论

`rules/*.yaml` 是唯一真源（`G-06`），而代码用一个**不存在的键**去读它时，
`dict.get()` **不报错** —— 返回 `None`，随后被 `or ""` / `or {}` / `or 0` 洗成一个
**看起来合法**的值。于是「这条规则其实没被读」在**任何输出里都不可见**。

本卡交付一道**双向**门禁把这件事变成红的，并给出**可执行反例**证明它会红。

---

## §② 形态定位：`T-18` 家族的**第六种**

| # | 形态 | 谁静止 |
|---|---|---|
| `G-50` | 有实现、有调用方，判据没绑 | 判据 |
| `T-18` | `rules/` 声明的列，代码零消费者 | 声明 |
| `G-55` | 同语义两种载体，彼此无绑定 | 两侧互不认识 |
| `G-57` | 同上，但同文件内成片 | — |
| `G-58` | 同语义三载体，**位置与类型都不同** | — |
| **本条** | **代码读的键在声明里根本不存在** | **读** |

### 两条断言（`R5` 的「单向缺失即红」）

| # | 断言 | 命中形态 | 缺的时候的后果 |
|---|---|---|---|
| ① | 代码**引用**的 `rules/<名>.yaml` 必须在 `rules/` 里**存在** | 整个文件缺失 | 读路径多半**响亮失败**（`FileNotFoundError`）—— **不是静默** |
| ② | 代码**读**的**键**必须在**实有键**里 | 文件在、键不在 | ★ **静默失效** |

★★ **两类分表登记，绝不共用一张白名单**。理由：一旦共用，②（静默失效）就会被
"值未冻结故暂不安装"这类①的合法理由**洗白** —— 那正好是本项目最忌的
「把**静默**失效伪装成**待安装**」。本守卫的两张表键形不同、理由字段各自要求写清
"缺它时**是否响亮失败**"。

---

## §③ 实现（有界 + fail-safe：宁可少报，绝不误报）

### 认哪些「规则文档出处」（能静态定死才认）

1. 模块级 `str` 常量（`SCENARIO_YAML = "rules/scenario.yaml"`、`BASELINE_RELPATH = ...`）；
2. `/` 拼接路径（`root / "rules" / "benchmark.yaml"`）；
3. ★ **作用域内的路径变量**（`path = Path(root) / SCENARIO_YAML`）——
   这一条**不能省**：漏掉它时 `scripts/benchmark/return_guard.py`（一个真正的规则消费者）
   会整块落在覆盖面之外（**实测踩到**：加之前它 0 条读）；
4. 三种装载点：`yaml.safe_load(...)` / `_cached_yaml(...)` / `load_yaml(...)`，
   外加 `_load_mapping(root, <常量>)` 这种"路径在第 2 个实参"的形态；
5. **同模块薄包装函数**取**一轮**不动点（`def baseline_doc(root): return _load_mapping(root, R)`）。

### 认哪些「读」

`doc.get("k")` / `doc["k"]`；**一层组别名**（`g = doc.get("group")` 之后 `g.get("k")`）；
**链式**（`doc.get("g", {}).get("k")` / `doc.get("g", {})["k"]`）。

### 判定

`k` 必须是该文件（或该分组）的**实有键**。整串字面量必须**恰好**是 `rules/<名>.yaml`
（严格 `^rules/…\.ya?ml$`）—— 故 `"详见 rules/baseline.yaml"` 这类**说明性字符串不算出处**，
否则守卫会开始对着文书报违例（"天天误报的门禁一定会被关掉"）。

### 覆盖面**必须可见**（`G-03`：跳过不是通过）

| 计数 | 含义 | R1（对象 `fd6dba4`） | R2（对象 `e9a009b`） |
|---|---|---|---|
| `py_files` | 扫过的 `scripts/**/*.py` | **113** | **113** |
| `rule_files` | 读到的 `rules/*.yaml` | **14** | **14** |
| `resolved_key_reads` | **解析出出处、且核对过**的读 | **47** | **54** |
| `unresolved_reads` | 接收者**已认定是规则文档**、但**键解析不出** | **0** | **0** |
| `ambiguous_doc_vars` | 经**多值返回**取得的文档变量（**盲区**） | **4** | **8** |
| `absent_rule_file_refs` | 引用了**不存在**的规则文件的 (文件,规则文件) 对 | **2** | **2** |
| `whitelisted_zero_key_reads` | 键缺失但**已登记** | **0** | **0** |
| `whitelisted_absent_rule_files` | 规则文件缺失但**已登记** | **2** | **2** |
| `violations` | — | **0** | **0** |

★ 两列是**两个不同对象**上的独立读数（见 §④ 末）；差值**不归因**（口径 12）。

★ **`unresolved_reads` 的口径是刻意收紧的**：它**只数**「接收者已认定是规则文档、但键解析不出」的读。
「读别的 mapping」（`row.get("price")`、`payload["x"]`）**不计入** —— 否则这个计数会被几千个
与规则无关的 `.get` 淹掉，读者再也看不出**覆盖面**在哪（初版就犯了这个错：**4162**，
一个毫无信息量的数）。每个有规则读的文件另各出一行 `reads::<文件>`、`unresolved::<文件>`、
`ambiguous::<文件>`、`rule_refs::<文件>`。

### 已知盲区（**如实登记，不静默**）

| 盲区 | 为什么现在不覆盖 | 后果 |
|---|---|---|
| **多值返回**（`raw, source, notes = _configured_source(...)`） | 返回值是"混装"，把它当文档会**误报** ⇒ 只认"恰好一个位置、该位置恰好一个规则文件" | 其后的 `raw.get(...)` **既不进 resolved 也不进 unresolved** ⇒ **单独计数** `ambiguous_doc_vars`（R1 `4` / R2 `8`）并打 note |
| **跨函数传键**（`_rules.py::baseline_threshold(root, key)` 的 `cfg[key]`） | 键由**调用方**以参数传入，要覆盖必须做真正的过程间分析 | 该路径的缺键行为由 13-A 自己用"缺键 ⇒ `MissingRuleInput` ⇒ `exit 2`"钉住（**不静默兜底**），故不构成静默失效 |
| `config/rules.py::load_yaml(relpath, root)` 的 `relpath` | 由调用方给；只有**同作用域静态绑定**时才能认（`BUDGET_RULES_RELPATH` 就是这种） | 已覆盖该形态 |
| 扫描范围 | 只扫 `scripts/`；`system/config/rules.py` 是通用只读读口、不含键名 | — |

---

## §④ 实测读数（★ 带树 + SHA，口径 9/10）

**树**：`.worktrees/ws-schema-expand`（分支 `ws/ch13-e-benchmark-fields`）**@ `fd6dba4d927282d7cd02801488b9779fb35c8b73`**
（该 SHA 的父提交为 `main@53de9a3` 的 merge）

```
== rule_key_alignment_guard.py ==
  scanned absent_rule_file_refs: 2
  scanned ambiguous_doc_vars: 4
  scanned expired_waiver_entries: 0
  scanned py_files: 113
  scanned resolved_key_reads: 47
  scanned rule_files: 14
  scanned unresolved_reads: 0
  scanned waiver_ratio_absent_files_permille: 500
  scanned waiver_ratio_keys_permille: 0
  scanned whitelisted_absent_rule_files: 2
  scanned whitelisted_zero_key_reads: 0
RESULT: PASS（0 violations）
```

耗时：两次读数 **1.49s**（`total`）与 **10.31s**（`total`，`user 0.85s` / CPU 8% —— 大部分时间不在
本进程上）。★ **未做受控实验**（两次的宿主负载与 SHA 都不完全相同）⇒ **只报这两个数，不归因**
（口径 12：两个变量同时变 ⇒ 不得归因）。

被覆盖到的**消费者文件**（**10** 个文件有规则读；其中 **9** 个计入 `resolved_key_reads=47`）：

| 文件 | 计入 47 | 解析出的读 |
|---|---|---|
| `scripts/pricelayer/scenario_guard.py` | 11 | 11 |
| `scripts/pricelayer/solver.py` | 11 | 11 |
| `scripts/pricelayer/daily_explain.py` | 6 | 6 |
| `scripts/pricelayer/valuation.py` | 6 | 6 |
| `scripts/benchmark/return_guard.py` | 4 | 4 |
| `scripts/valuelayer/_rules.py` | 4 | 4 |
| `scripts/orchestrate/pipeline.py` | 3 | 3 |
| `scripts/compute/driver.py` | 1 | 1 |
| `scripts/delivery/stage_gate.py` | 1 | 1 |
| `scripts/graph/stop.py` | **0** | 4（★ 指向**不存在的** `rules/transmission.yaml` ⇒ 走**断言①**，不进 `resolved`） |
| **合计** | **47** | 51 |

★ **零误报是我逐条人工核过的**：47 处里的每一处都回读了源码，确认"解析出的出处"与
"那行代码真正读的文件"一致（含 `return_guard.py:115/131/132/136`、`driver.py:126`、
`stage_gate.py:388`、`pipeline.py:540/553`、`valuation.py:104` 等）。
`pipeline.py:553` 的 `cfg.get("anti_kpi", {}).get("always_write_check_record")` 会报**两条**
（内层读 `anti_kpi`、外层读子键），这是**刻意的**：内层那次确实读了一个键。

### ★★ R2 复读：**同一守卫，不同对象**（树 `e9a009b`）

上表的读数是**对象 `fd6dba4`** 的。R2 期间 `main` 推进了 **42** 个提交
（`scripts/pricelayer/**` 拿进了 13-A / 13-B 的新代码）⇒ 同一守卫在**新对象**上：

```
== rule_key_alignment_guard.py ==   （树 .worktrees/ws-schema-expand @ e9a009b，--no-report）
  scanned py_files: 113              scanned rule_files: 14
  scanned resolved_key_reads: 54     scanned unresolved_reads: 0
  scanned ambiguous_doc_vars: 8      scanned absent_rule_file_refs: 2
  scanned whitelisted_zero_key_reads: 0    scanned whitelisted_absent_rule_files: 2
  scanned waiver_ratio_keys_permille: 0    scanned waiver_ratio_absent_files_permille: 500
  scanned expired_waiver_entries: 0
RESULT: PASS（0 violations）
```

| 文件 | R2 计入 **54** | R1 计入 47 |
|---|---|---|
| `scripts/pricelayer/scenario_guard.py` | **17** | 11 |
| `scripts/pricelayer/solver.py` | **12** | 11 |
| `scripts/pricelayer/daily_explain.py` | 6 | 6 |
| `scripts/pricelayer/valuation.py` | 6 | 6 |
| `scripts/benchmark/return_guard.py` | 4 | 4 |
| `scripts/valuelayer/_rules.py` | 4 | 4 |
| `scripts/orchestrate/pipeline.py` | 3 | 3 |
| `scripts/compute/driver.py` | 1 | 1 |
| `scripts/delivery/stage_gate.py` | 1 | 1 |
| `scripts/graph/stop.py` | **0**（4 处走**断言①**） | **0**（同上，4 处） |
| **合计（计入 `resolved`）** | **54** | **47** |

★★ **我拒绝把 `47 → 54` 解释成"守卫变松/变严"**：**两个变量同时变了**（对象从 `fd6dba4` 走到
`e9a009b`；被测代码面也换了一批）⇒ 按 **口径 12 不得归因**。可确定的只有一件事：
**两个对象上 `violations` 都是 `0`** —— 即"代码读的 `rules/` 键都存在"这条断言在
**两个互不相同、且相隔 42 个提交的对象上**都成立（`G-50` 类的"只测过一次"不成立）。
同理 `ambiguous_doc_vars: 4 → 8`，**只报数、不归因**（含义不变，见 §④ 末与 §⑧-2）。

---

## §⑤ 白名单：按 `口径 13` 三条落实

`口径 13`（`batch13_taskbook.md:682`）要求白名单自带三条，缺一即退化成"永久豁免池"。
本守卫把豁免升格成**对象** `_Waiver`，四字段缺一即**导入时响亮失败**：

| `口径 13` 要求 | 本守卫的落法 | 机器绑定 |
|---|---|---|
| ① 逐条 `reason` + `owner` + **预期何时有消费者** | `_Waiver{reason, owner, expected_consumer_by, review_by}` | `_selfcheck_waivers()` 在**导入时**跑；空字段 ⇒ `ValueError`（**不是 `assert`** —— `python -O` 会剥离 assert ⇒ 检查器在优化模式下静默失效） |
| ② **过期机制**（`review_by`，到期未消 ⇒ 报警） | `_expired_waivers(today)` + `scanned.expired_waiver_entries` + `★★ EXPIRED` note | 抽成**带 `today` 入参的纯函数** ⇒ 可被**确定性**测试（否则"到期才炸"的判据不是判据） |
| ③ **输出白名单与被检集合的比值** | `scanned.waiver_ratio_keys_permille` / `waiver_ratio_absent_files_permille` + 汇总 note | 键 `0/54`（0.0%）· 规则文件 `2/4`（50.0%）（对象 `e9a009b`；R1 对象为键 `0/47`） |

### 两处已登记欠账（都在②的"规则文件缺失"表里）

| 文件 | 规则文件 | owner | 预期消失条件 | `review_by` |
|---|---|---|---|---|
| `scripts/graph/stop.py` | `rules/transmission.yaml` | 主理人安装（值面归第十一章 `p04`） | `p04` 冻结后安装 | 2026-09-30 |
| `scripts/evidence/budget_gate.py` | `rules/budget.yaml` | 主理人安装（值面归 `p09`） | `p09` 冻结后安装 | 2026-09-30 |

★ **两条都是"刻意未安装"且读路径响亮失败**，逐字依据：
`.workbuddy/memory/2026-09-16.md:709/711`（"**不创建** `rules/budget.yaml` / `rules/transmission.yaml`：
设计原文说『参数冻结后填入』，而 `p09.budget = tbd`"）、`ws_graph_report.md:99`、
`ws_ch7_transmit_report.md:161`、`ws_independent_audit_batch8_integration_transmit.md:52-57`（实测
`FileNotFoundError`）。⇒ **不得**让它们把门禁变成恒红（那正是"门禁被关掉"的引信）。

★ **"到期即红"还是"到期只报警"**：本卡按 `口径 13` 第 2 条的**逐字**（"报警"）实现为
**note + 计数，不阻断**。理由：把它升为 `exit 1` 会让"某条欠账到期"拦住**全体成员**的提交。
**若主理人要求到期即红，改动点只有 `check()` 里调用 `_expired_waivers` 的那一处。**

### ★ 建表时那条活靶子已被关闭（留痕，不是"本来就空"）

建表时唯一一条是：

```
(scripts/pricelayer/scenario_guard.py, "rules/scenario.yaml::method_version")
```

`method_version=str(doc.get("method_version") or "")` —— `rules/scenario.yaml` **没有这个键**，
于是它**静默产出空串**（既没走 `value_source='design_default'` 那条显式通路，也没记 note）。
这正是 `phase1_open_tensions.md` 登记的第三条并行发现。

★ **13-B 已把它关闭**（合入 `main` 后本树 `scenario_guard.py` 里该路径已重写）：
改为 `_method_version_from_pointer()` 按 `scenario_consistency.param_ref` 指针解析，
**转正后取不到载体即响亮失败**（`scenario_guard.py:246-269`），并在 docstring 里逐字声明
「`method_version` **不读** `rules/scenario.yaml`（该文件没有这个键）」（`:289-290`）。

⇒ 覆盖它的**机器证据**：合入后本守卫 `whitelisted_zero_key_reads=0` 且
`resolved_key_reads>0`（R1 对象 `47`、R2 对象 `54`）、`0 violations`
（即"读的键**全部存在**"，而**不是**"读的键被白名单盖住"）。
⇒ 本表**现为空，但机制保留在位**；下一条欠账必须按 `口径 13` 四字段登记。
**不得**因为"现在空了"就把表和 `_selfcheck_waivers()` 一起删掉 —— 那等于把机制收走。

---

## §⑥ 测试证据

文件：`system/tests/guards/test_rule_key_alignment.py`（**9 例**）

| # | 用例 | 它证伪什么 |
|---|---|---|
| 1 | 干净副本 + **覆盖面四形态** | 反向对照（不改 ⇒ `exit 0`）；★ 同时钉死"**静默地一条都解析不出来**"这种退化 —— 四个文件各代表一种解析形态，任一种退化对应那行 `reads::…` 就消失 |
| 2 | **方向 A**：改**读的一侧**（`doc.get("thresholds_bogus")`） | 代码漂移必须红 |
| 3 | **方向 B**：改**声明的一侧**（`rules/baseline.yaml` 的 `thresholds:` → `thresholdz:`） | ★ 证伪"守卫拿快照/自己内置键表"：那种实现下改 `code_root` 里的规则文件**不会红** |
| 4 | 未登记的缺失规则文件引用必须红 + **已登记的必须绿** | 两臂并存，白名单才不是避难所 |
| 5 | 两种**输入异常** ⇒ `exit 2`（缺 `rules/`；`scripts/**` 有无法解析的 `.py`） | `G-03`：无被检对象 ≠ 已验证 |
| 6 | 白名单四字段缺一 / 日期不可解析 ⇒ `ValueError` | 口径 13 第 1 条（**导入时**就红） |
| 7 | 过期机制是 `today` 的**确定函数**（`review_by` 当天不过期） | 口径 13 第 2 条 |
| 8 | 无全局副作用（`sys.path` / `scripts*` 的 `sys.modules`） | 守护测试进程不被污染 |
| 9 | `G-07` 双落点登记 | 只进一处 = "提交时放行、CI 时拦" |

### ★★ 端到端 pytest：**R1 的欠账已在 R2 关闭（9 例全绿）**

#### R2 第一次尝试 —— **仍被同一个宿主守卫阻断**（树 `e9a009b`）

命令逐字：`sh system/scripts/ops/run_pytest.sh tests/guards/test_rule_key_alignment.py`

```
INTERNALERROR>   File ".../system/tests/conftest.py", line 416, in pytest_sessionstart
INTERNALERROR>     _clear_work_dir(loud=True)
INTERNALERROR>   File ".../system/tests/conftest.py", line 383, in _clear_work_dir
INTERNALERROR>     shutil.rmtree(child, ignore_errors=True)
INTERNALERROR>   File ".../shim/sitecustomize.py", line 1144, in _safe_shutil_rmtree
INTERNALERROR>   File ".../shim/sitecustomize.py", line 851, in _check_bulk_delete_guard
INTERNALERROR>   File ".../shim/sitecustomize.py", line 826, in _exit_bulk_guard_control
INTERNALERROR>     raise SystemExit(1)
```

★★ **只读取证**（`$CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR` 下逐桶回读，未做任何写/删）：

| 事实 | 读数（★ 只报我回读到的**原文**，桶键语义**我未查证、不猜**） |
|---|---|
| 计数**跨 worktree 共享** | 同一个 `signal-*.json` 目录（`075375d0…`）里**同时**存在指向 `ws-schema-expand` / `ws-verify-shard` / `ws-fixture-cost` / `ws-daily-nochange` / 主仓的 `confirmRequired` 记录 |
| **已越顶** | 指向**本树**的最近一条为 `count=108656` ≥ `threshold=99999` ⇒ 本会话**任何 ≥1 项的删除都会被拒**（`count` 在该目录内单调不减：`100073→100226→100483→102044→108656`） |
| 阈值**会被宿主改** | 同目录另见 `{"count":9999,"threshold":9999}` 的旧记录（∝ `CONVENTIONS.md:105-106`）；`threshold` 当前值取自宿主环境 `CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD=99999` |

⇒ 这**不是**我这一份测试的特例，而是**全体流的夹具同时不可用**。`口径 9/10`：上述读数**带树**
（`e9a009b`）+ 带**绝对路径**（`/var/folders/…/codebuddy-safe-delete-bulk/`）。

#### R2 第二次尝试 —— 按主理人裁定在 `E` 口径下跑：**通过**

依据 `batch13_taskbook.md:1154`「`E`（`CODEBUDDY_SAFE_DELETE_ENABLED=0`）= **(甲) 合法配置**，
而不是"绕过"」。

```bash
$ cd .worktrees/ws-schema-expand
$ CODEBUDDY_SAFE_DELETE_ENABLED=0 sh system/scripts/ops/run_pytest.sh tests/guards/test_rule_key_alignment.py
collected 9 items
tests/guards/test_rule_key_alignment.py .........                        [100%]
============================== 9 passed in 5.30s ===============================
# 独立复跑：9 passed in 5.33s ；进程退出码 EXIT=0
```

| # | 事实 | 读数（树 `e9a009b`，两次独立跑） |
|---|---|---|
| 1 | 9 例全过 | `9 passed` · `5.30s` / `5.33s` · `EXIT=0` |
| 2 | **夹具自清**（无残留） | `tests/.work` 跑前 **0** 项 → 跑后 **0** 项 |
| 3 | 这次删了什么 | 见下，逐条登记 |

★★ **删除量逐条登记**（不藏）：两次运行都走 conftest 的
`pytest_sessionstart → _clear_work_dir(loud=True)`，它清的是**本树**的 `system/tests/.work`：

- 首次（清掉 R1 遗留的 5 份夹具副本）：跑前 **1660 项 / 16M**。路径
  `.worktrees/ws-schema-expand/system/tests/.work`，被 `system/.gitignore:8`（`tests/.work/`）**覆盖**，
  且这是 **pytest 每次 `sessionstart` 的设计行为**（`conftest.py:416`）——
  **不是**我为"把灯弄绿"额外删的东西；
- 第二次：跑前 **0** 项 ⇒ **删除量为 0**。

★ **顺带上报一个阻塞全体流的缺口**（**只报不改**，改它属共享运维脚本，不在本卡范围）：
`run_pytest.sh:27` **只**关 `CODEBUDDY_SAFE_DELETE_SANDBOX` / `CODEBUDDY_BROKERED_FS_HOOK_ENABLED`，
**没有**关 `CODEBUDDY_SAFE_DELETE_ENABLED`；`verify.py:598` 同理
⇒ 主理人裁定的"三条条件"（`batch13_taskbook.md:1158-1160`）**尚未安装**。
装上 = 全体流的夹具测试立刻恢复（现在被同一个桶全量卡死）。

#### R1 那份只读复跑**保留在案**（独立第二法）

R1 因配额受阻时，我用**只读**方式逐条复跑了这 9 例的**每一条断言**
（复用 pytest 留下的 5 份夹具副本 —— 它们的注入态正好就是对应断言要的对象；
"缺 `rules/`"那一臂改用 `code_root/views` 这个**本来就没有 `rules/`** 的根，**零新建零删除**）：

```
=== 通过 36 / 失败 0 ===
```

它与上面的端到端结果**同结论** ⇒ 两条**互不相同的方法**（只读断点复跑 vs 真 pytest 装配）互证。

★ 顺带修掉一处**因这次环境事故才暴露的真脆弱性**：用例 #5 原用
`shutil.rmtree(code_root / "rules")` 造输入 —— 那是**同一份删除预算上的第二次消费**
（夹具 teardown 已经吃掉一次）。现改为指向一个**本来就没有 `rules/` 的根**
（`code_root/views`），**零删除、与宿主配额解耦**。理由写进用例 docstring。

---

## §⑦ 纪律留痕（含**一次我自己的事故**）

1. ★★ **我在 main 工作树里跑了一次 pytest（错树）**。原因：我把
   `cd /Users/gaza/Developer/InvestSigh && sh system/scripts/ops/run_pytest.sh …` 当成"跑官方入口"，
   而它跑的是 **main 工作树的 `system/tests`**，不是我的分支（口径 9：读数必须连"在哪个树上跑的"一起报）。
   - **后果**：main 的 `pytest_sessionstart` 去清它自己的 `tests/.work`（历史残留很大）⇒
     触发宿主的批量删除守卫 ⇒ `SystemExit` ⇒ `INTERNALERROR`；该次运行**不作数**。
   - **是否造成损害**：未造成实际删除（守卫在删除前就拒了）。但**删除配额桶**（阈值 99999，
     `scope: "turn"` 是**载荷字面标签**，实为**全流共享**）在我操作时**已经**被其他活动消耗到 100270
     （状态目录里有多条**早于**我这次操作、且指向**别的** tool-call 的 `confirmRequired` 记录，
     计数已达 84k~108k）⇒ **不是**（也**不能**说成）我造成的；但**我的操作是被拒的**这一点
     必须如实登记。⇒ 本轮所有流的夹具 teardown 都会被拒，**不是我的测试独有的现象**。
   - ★★ **R2 再订正一处措辞**：R1 把它叫"**回合级**删除预算"——**错**。
     `batch13_taskbook.md:1166` 已更正为「配额**不随用户轮次恢复**（跨多轮仍 `count≈100220`）
     ⇒ 边界是**「新会话」**」。R2 **实测吻合**：进了新一轮，`count` **不降反升**
     （`100270 → 108656`）⇒ 本会话内**等不回来**。R2 第一次尝试正是因此再次被拒（见 §⑥）。
   - **处置**：R1 不再做任何删除（**正确**）；R2 按主理人裁定改走 `E` 口径跑（见 §⑥），
     **仍未动共享运维脚本**（只上报，见 §⑥ 末）。
2. **`no_placeholder_guard` 拦下了我写的守卫**（`SWALLOW_EXCEPTION_CONTINUE` @
   `rule_key_alignment_guard.py:709`，`except SyntaxError: continue`）。**那条判据抓得对**：
   跳过"无法解析的文件"= 该文件**根本没被检查**，而输出里看起来一切正常 ——
   正是本守卫自己要拦的那一族。已改为 `raise ValueError(… 无法解析 … 不得当作通过 …)`
   ⇒ `exit 2`（"我没法判"），并**把这条钉进用例 #5**（再有人改回 `continue` 就会红）。
3. ★★ **`grep` 空真：我原来的根因归因是错的 —— 此处显式收回并订正**
   （原文：「`grep` 的 `\|` 假零命中：……用 **BSD `grep`** 拿不到结果」⇒ **错**）。

   **真因**：**Bash 工具里的 `grep` 命中的不是 `grep`，而是 WorkBuddy 的 broker 包装器**：

   ```
   $ which -a grep
   /Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/vendor/shim/brokered-bin/grep   ← PATH 优先
   /usr/bin/grep
   $ ls -la "$(which grep)"
   …/shim/brokered-bin/grep -> codebuddy-toybox-dispatch      # 一个重实现，非 GNU / BSD grep
   ```

   **取证**（**同文件 + 同模式 + 命令 + `rc` 原文**；树 = 本 worktree **`e9a009b`**；
   文件 = `scripts/checks/rule_key_alignment_guard.py`，852 行）：

   | 模式 | 包装器 | 真 `/usr/bin/grep` | 判定 |
   |---|---|---|---|
   | `def check`（纯字面） | `1` / rc 0 | `1` / rc 0 | 一致 |
   | `def _analyze_module\|class _ModuleReads`（BRE `\|`） | **`0` / rc 1** | **`2` / rc 0** | ★分歧 |
   | `CheckR[e]*port\|va_lid`（BRE `\|` + 字符类） | **`0` / rc 1** | **`4` / rc 0** | ★分歧 |
   | `tabl\+e`（BRE `\+`） | **`0` / rc 1** | **`6` / rc 0** | ★分歧 |
   | `def[[:space:]]\+check`（BRE `\+`） | **`0` / rc 1** | **`1` / rc 0** | ★分歧 |
   | `\<check\>`（词边界） | **`0` / rc 1** | **`4` / rc 0** | ★分歧 |
   | 上面第一条改写成 `-E '…|…'` | `2` / rc 0 | `2` / rc 0 | 一致 |
   | `rep\{1,2\}ort`（BRE `\{`） | `27` / rc 0 | `27` / rc 0 | 一致 |
   | `\(def\) .*\1`（组 + 反向引用） | `0` / rc 1 | `0` / rc 1 | 一致（真值即 0，**不构成证据**） |
   | `-r` 递归 / stdin 管道 / 缺文件（rc 2） | 与真 grep 逐位相同 | — | 一致 |

   ★ **一致性对照行是故意留的**：它把结论**收窄**到"包装器**不实现反斜杠转义的 BRE 算符那一族**
   （`\|`、`\+`、`\<`、`\>`），而**不是**"包装器坏了 / 字面量也失效"。

   **机制**：那一族算符不实现 ⇒ 模式**退化成字面量** ⇒ 永不匹配 ⇒ `count=0` **且 `rc=1`**。
   ★★ 而 **`rc=1` 正是 grep「无匹配」的合法码** ⇒ 它与"诚实零命中"**逐位不可区分** ⇒
   「`grep` 无匹配」被读成「**确实没有**」—— **把否定结论静默伪造出来**（`G-62`）。
   ★ 这也解释了为什么此前 4 次踩坑都发生在"核查锚点唯一性"这类**先验希望命中**的模式上。

   **与主干口径一致**（`batch13_taskbook.md:1213-1220`，对象 `e9a009b`）：触发条件更窄
   （只有含 `\` 转义的模式失效；纯字面 / `^` 锚点 / `-E` 正常）、且 `rc=1` 非 `0`
   ⇒ 我这份独立实测**逐条吻合**（我另跑了 14 种旗标形态 `-c/-l/-n/-i/-w/-F/-q/-oc/-cE/-rc/-rn/-rl/--count`
   **全部一致**，只有 `\` 转义族分歧）。

   ★★ **一处我复现不出的读数，如实登记、不替对方判定**：原广播称"**纯字面** `_safe_shutil_rmtree`：
   包装器**无输出** / 真 `grep` → **`4`**"。我在树 `e9a009b` 上的读数**不支持**"字面量也失效"：
   - 单文件 `system/reports/ws_fixture_cost_report.md` ⇒ 包装器 `2` / 真 grep `2`（**一致**）；
   - 三个 `.md` 一起给：两边逐文件全同（`batch13_taskbook.md:1`、`ws_fixture_cost_report.md:2`、
     `ws_schema_expand_report.md:1`）⇒ **合计恰为 `4`** —— 与那个"`4`"数值吻合，但它**不是**包装器空输出造成的差异；
   - `-r` 递归到 `system/reports`（真值 `1+8+1+2`）两边亦逐位相同。
   ⇒ 结论：**我只能支持"反斜杠转义族失效"，不能支持"字面量失效"**；两流 `rc` 分歧（`0` vs `1`）
   我这边读数是 **`1`**。按 `口径 10`，此处**只贴我的原文读数与命令**，
   **不替 `ws-verify-shard` 判定**（我无法复现它的树与状态，属 `口径 12` 的"变量不止一个"）。

   **处置**：核查"零命中"时**默认换工具**（内置 `Grep` 工具 / `/usr/bin/grep` / Python）——
   **不能靠"输出是否为空"察觉**（触发条件太窄，见上）；
   并采纳 `ws-verify-shard` 的同族两坑：**管道吞退出码**（写 `{ cmd; echo "EXIT=$?"; } 2>&1 | tail -3`）、
   **`head -N` 会截断 diff**（先看 `git diff --stat`）。
   **机器绑定**：主干已把 **卡 13-L** 的目标由"检出 pattern 含 `\|` 且未加 `-E`"
   **改为「检出 Bash 里裸 `grep`（未写绝对路径）的用法」**（`batch13_taskbook.md:1146-1148`）
   ⇒ 本条由该卡落地，本卡**不重复建**（原"只登记、未自行做"的判断不变）。
4. 只在自己的 worktree/分支改；`git add` **逐文件**（未用 `-A`）；提交经 `pre-commit` **全绿**；
   merge `main` 后按 `V-07` 重跑 `bootstrap_worktree.sh`（`rules_lock_guard` PASS）。
5. **未改任何设计区文件**；`rules/**` 未改内容（`bootstrap` 只复原权限位）。

---

## §⑧ 遗留 / 请主理人裁定

| # | 事项 | 我的默认处置 |
|---|---|---|
| 1 | **过期即红 or 只报警**：现为 note + 计数（按 `口径 13` 逐字"报警"） | 待裁；升为红只需改 `check()` 一处 |
| 2 | **`ambiguous_doc_vars`（R1 `4` / R2 `8`）是否要做"按返回位置"的生产者分析** | 本卡**未做**（如实登记 + 计数）；要做请给卡 |
| 3 | **方向 2（`rules/` 声明了语义但代码零消费者 ⇒ 报警）尚未开工** | 见下 |
| 4 | `G-07` 是否升格为通用规则（"`GATES` 里每条都必须进 `pre-commit.sh`"？） | 仍是"设计决定"：`pre-commit.sh` 只跑子集（现已 14 道）而 `GATES` 27 条 ⇒ 通用规则需要一次裁定，不该由本卡凭"看起来更严"自行发明 |

### ★ 关于方向 2（**尚未交付**，此处只如实说明状态）

我此前粗测（`rules/` 14 件 = 255 个叶键）得到 **(a) 运行时 84 / (b) 门禁·测试 32 / (c) 零消费者 139**，
但我在报告里已判定 **(c) 里混着大量分类错误**（例：`benchmark.yaml::return_guard.must_use_fund_market_price`
其实由 `scripts/benchmark/return_guard.py` 读，只是它不在 `scripts/checks/` 下）。
⇒ **当前方法精度不够**（误差 >20%），而"天天误报的门禁一定会被关掉" ⇒ 我**不交付**一个
我自己知道有 >20% 误报率的守卫。

★ 本卡已经为方向 2 铺好了两块地基（可直接复用）：
`_Waiver`（四字段 + 过期 + 比值，`口径 13` 三条全落）与 `_relpaths_referenced`（AST 级的
"谁引用了哪件规则文件"，**排除注释与散文**）。

★ 方向 2 的正确形态（`batch13_taskbook.md:467-473`）是**三态输出**并**各自计数**：
`有消费者(运行时)` / `有消费者(门禁·测试)` / **`零消费者 ⇒ 红`**（且必须把门禁 / schema / 测试算进消费者）。

---

## §⑨ 复现命令

```bash
# 单跑（真仓库，只读）
cd .worktrees/ws-schema-expand/system
$HOME/.workbuddy/binaries/python/envs/default/bin/python scripts/checks/rule_key_alignment_guard.py --no-report

# 测试（★ 本会话删除配额已越顶：`count 108656 ≥ threshold 99999` ⇒ 裸跑必 INTERNALERROR）
# 按主理人裁定（batch13_taskbook.md:1154）在 E 口径下跑：
cd .worktrees/ws-schema-expand
CODEBUDDY_SAFE_DELETE_ENABLED=0 sh system/scripts/ops/run_pytest.sh tests/guards/test_rule_key_alignment.py
# 期望：collected 9 items / 9 passed / EXIT=0（R2 实测 5.30s、5.33s 两次一致）

# 门禁（两道都在）
sh system/scripts/ops/pre-commit.sh

# §⑦-3 的取证（★ 跑前先做工具指纹；Bash 里裸 grep 不是 grep）
which -a grep && ls -la "$(which grep)"        # 应看到 …/shim/brokered-bin/grep -> codebuddy-toybox-dispatch
/usr/bin/grep -c 'def _analyze_module\|class _ModuleReads' \
  system/scripts/checks/rule_key_alignment_guard.py     # 真值 2 / rc 0
grep           -c 'def _analyze_module\|class _ModuleReads' \
  system/scripts/checks/rule_key_alignment_guard.py     # 包装器 0 / rc 1 ⇒ 假"无匹配"
```
