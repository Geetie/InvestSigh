# 批次 13-pre 方向 1 —— 「键对齐守卫」交付报告

> 对象：`system/scripts/checks/rule_key_alignment_guard.py`（新增）
> 提交：**`fd6dba4d927282d7cd02801488b9779fb35c8b73`**（分支 `ws/ch13-e-benchmark-fields`，
> 已合并 `main` `53de9a3`；提交时 `pre-commit` **全部门禁放行**）
> 依据：任务卡 `R5`「键对齐守卫：AST 抽代码实际读取键 ↔ `rules/*.yaml` 实有键，**单向缺失即红**」
> 纪律：所有读数**带树**（口径 9）+ 判词**带对象与 SHA**（口径 10）。

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

| 计数 | 含义 | 本树读数 |
|---|---|---|
| `py_files` | 扫过的 `scripts/**/*.py` | **113** |
| `rule_files` | 读到的 `rules/*.yaml` | **14** |
| `resolved_key_reads` | **解析出出处、且核对过**的读 | **47** |
| `unresolved_reads` | 接收者**已认定是规则文档**、但**键解析不出** | **0** |
| `ambiguous_doc_vars` | 经**多值返回**取得的文档变量（**盲区**） | **4** |
| `absent_rule_file_refs` | 引用了**不存在**的规则文件的 (文件,规则文件) 对 | **2** |
| `whitelisted_zero_key_reads` | 键缺失但**已登记** | **0** |
| `whitelisted_absent_rule_files` | 规则文件缺失但**已登记** | **2** |

★ **`unresolved_reads` 的口径是刻意收紧的**：它**只数**「接收者已认定是规则文档、但键解析不出」的读。
「读别的 mapping」（`row.get("price")`、`payload["x"]`）**不计入** —— 否则这个计数会被几千个
与规则无关的 `.get` 淹掉，读者再也看不出**覆盖面**在哪（初版就犯了这个错：**4162**，
一个毫无信息量的数）。每个有规则读的文件另各出一行 `reads::<文件>`、`unresolved::<文件>`、
`ambiguous::<文件>`、`rule_refs::<文件>`。

### 已知盲区（**如实登记，不静默**）

| 盲区 | 为什么现在不覆盖 | 后果 |
|---|---|---|
| **多值返回**（`raw, source, notes = _configured_source(...)`） | 返回值是"混装"，把它当文档会**误报** ⇒ 只认"恰好一个位置、该位置恰好一个规则文件" | 其后的 `raw.get(...)` **既不进 resolved 也不进 unresolved** ⇒ **单独计数** `ambiguous_doc_vars=4` 并打 note |
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

---

## §⑤ 白名单：按 `口径 13` 三条落实

`口径 13`（`batch13_taskbook.md:682`）要求白名单自带三条，缺一即退化成"永久豁免池"。
本守卫把豁免升格成**对象** `_Waiver`，四字段缺一即**导入时响亮失败**：

| `口径 13` 要求 | 本守卫的落法 | 机器绑定 |
|---|---|---|
| ① 逐条 `reason` + `owner` + **预期何时有消费者** | `_Waiver{reason, owner, expected_consumer_by, review_by}` | `_selfcheck_waivers()` 在**导入时**跑；空字段 ⇒ `ValueError`（**不是 `assert`** —— `python -O` 会剥离 assert ⇒ 检查器在优化模式下静默失效） |
| ② **过期机制**（`review_by`，到期未消 ⇒ 报警） | `_expired_waivers(today)` + `scanned.expired_waiver_entries` + `★★ EXPIRED` note | 抽成**带 `today` 入参的纯函数** ⇒ 可被**确定性**测试（否则"到期才炸"的判据不是判据） |
| ③ **输出白名单与被检集合的比值** | `scanned.waiver_ratio_keys_permille` / `waiver_ratio_absent_files_permille` + 汇总 note | 键 `0/47`（0.0%）· 规则文件 `2/4`（50.0%） |

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
`resolved_key_reads=47`、`0 violations`（即"读的键**全部存在**"，而**不是**"读的键被白名单盖住"）。
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

### ★★ 诚实声明：**本轮未能端到端跑完 pytest**

**现象**（树 `.worktrees/ws-schema-expand`；代码为提交 `fd6dba4` **之前**的同一份工作树，
与该提交的差异**仅**为 §⑦-2 那处 `except SyntaxError` 改法与用例 #5 的输入构造方式）：

```
collected 9 items
tests/guards/test_rule_key_alignment.py .E.E.E.EFE....
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
  {"count":100270,"threshold":99999,"scope":"turn","targets":[.../test_injecting_at_the_reading_side_is_blocked-af92f9df"],"targetCount":1}
```

**解读**（逐项落实，不猜）：

- `.E` × 4 + `FE` × 1：`E` 是 **fixture teardown 错误**（`code_root` 的
  `shutil.rmtree` 被宿主的**批量删除守卫**拒绝），不是用例失败；
- `F` = `test_missing_rules_directory…`（用例名对应的那份夹具**仍有 14 个 `rules` 文件** ⇒
  `shutil.rmtree(rules)` 被拒 ⇒ 它在造输入那一步就炸了）。**成因是宿主配额，与守卫逻辑无关。**
- 4 条不用夹具的用例（6~9）全 `.`。

⇒ 我**没有**把这当作"测试通过"。改用**只读**方式逐条复跑了这 9 例的**每一条断言**
（复用 pytest 留下的 5 份夹具副本 —— 它们的注入态正好就是对应断言要的对象；
"缺 `rules/`"那一臂改用现存的 `system/tests`（本就没有 `rules/`）作为根，
**零新建零删除**）：

```
=== 通过 36 / 失败 0 ===
```

★ 这一份**不是** pytest 的替代品：它证明了**断言的内容**成立，但**没有**证明
conftest 的夹具装配 / `run_gate_inproc` 接线在端到端路径上无误。**下一轮第一件事就是补跑**
`sh system/scripts/ops/run_pytest.sh tests/guards/test_rule_key_alignment.py`（删除预算按回合重置）。

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
   - **是否造成损害**：未造成实际删除（守卫在删除前就拒了）。但**回合级删除预算**（阈值 99999，
     `scope: "turn"`，全流共享）在我操作时**已经**被本回合的其他活动消耗到 100270
     （状态目录里有多条**早于**我这次操作、且指向**别的** tool-call 的 `confirmRequired` 记录，
     计数已达 84k~108k）⇒ **不是**（也**不能**说成）我造成的；但**我的操作是被拒的**这一点
     必须如实登记。⇒ 本轮所有流的夹具 teardown 都会被拒，**不是我的测试独有的现象**。
   - **处置**：本轮不再做任何删除；补跑放到下一轮。
2. **`no_placeholder_guard` 拦下了我写的守卫**（`SWALLOW_EXCEPTION_CONTINUE` @
   `rule_key_alignment_guard.py:709`，`except SyntaxError: continue`）。**那条判据抓得对**：
   跳过"无法解析的文件"= 该文件**根本没被检查**，而输出里看起来一切正常 ——
   正是本守卫自己要拦的那一族。已改为 `raise ValueError(… 无法解析 … 不得当作通过 …)`
   ⇒ `exit 2`（"我没法判"），并**把这条钉进用例 #5**（再有人改回 `continue` 就会红）。
3. **`grep` 的 `\|` 假零命中**（第 5 次）：核查锚点唯一性时用 BSD `grep` 拿不到结果，
   改用 Python/`Grep` 工具。**建议做成机器绑定**（只登记，未自行做）。
4. 只在自己的 worktree/分支改；`git add` **逐文件**（未用 `-A`）；提交经 `pre-commit` **全绿**；
   merge `main` 后按 `V-07` 重跑 `bootstrap_worktree.sh`（`rules_lock_guard` PASS）。
5. **未改任何设计区文件**；`rules/**` 未改内容（`bootstrap` 只复原权限位）。

---

## §⑧ 遗留 / 请主理人裁定

| # | 事项 | 我的默认处置 |
|---|---|---|
| 1 | **过期即红 or 只报警**：现为 note + 计数（按 `口径 13` 逐字"报警"） | 待裁；升为红只需改 `check()` 一处 |
| 2 | **`ambiguous_doc_vars=4` 是否要做"按返回位置"的生产者分析** | 本卡**未做**（如实登记 + 计数）；要做请给卡 |
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

# 测试（★ 需要宿主删除预算可用）
cd .worktrees/ws-schema-expand
sh system/scripts/ops/run_pytest.sh tests/guards/test_rule_key_alignment.py

# 门禁（两道都在）
sh system/scripts/ops/pre-commit.sh
```
