# 交付报告 · `G-55`（跨载体绑定）+ 批次 13-E（`Benchmark` 5 字段）

> 分支 `ws/ch13-e-benchmark-fields`（基点 `4006663`）
> **13-E**：commit `64aed64`（已单独提交，报告见 `ws_ch13e_benchmark_fields_report.md`）
> **`G-55`**：本文件

---

## ① 交付物（`G-55`）

| 文件 | 改动 |
|---|---|
| `system/scripts/checks/scenario_tag_binding_guard.py` | **新增**检查器（跨载体取值域绑定） |
| `system/tests/guards/test_scenario_tag_binding.py` | **新增** 5 例（反例 + 反向对照 + 无副作用 + 双落点登记） |
| `system/scripts/ops/run_all_gates.py` | `GATES` **24 → 25**（+ 一条） |
| `system/scripts/ops/pre-commit.sh` | 第 **⑫** 道门 |
| `system/reports/ws_ch13e_benchmark_fields_report.md` | 13-E 报告（已提交） |
| `system/reports/ws_g55_binding_guard_report.md` | 本报告 |

---

## ② `G-55` 的形态，与它为什么**单流自检发现不了**

| 载体 | 内容 | 位置 |
|---|---|---|
| **A 声明面** | `scenario_tags: [bear, neutral, bull, custom]` | `rules/scenario.yaml:25` |
| **B 实现面** | `class ScenarioTag(str, Enum)`：bear / neutral / bull / custom | `scripts/pricelayer/scenario_guard.py:82` |

两侧**值相同、各自自洽、零绑定** ⇒ 改 A 少一个 `custom`，B 照样能构造 `custom`；删掉 B 的 `bear`，A 照样声明着它。
**漂移可以无限期存在而无人发现** —— 且 A 侧是 **0444 + SHA256 锁**过的规则文件，看起来比散文权威得多。

★ **这是"合并的产物"，不是任何一条流的错**（同 `G-55` 登记语）：13-B 自注册了 A 侧、实现侧原本就有枚举，
**两条流各自都自洽**。⇒ 单流自检不可能发现，**只有集成**才让它们变成两份可漂移的存储。

---

## ③ ★ 实现时按同一判据扫面，**发现同一形态还有第二处**（本卡新增，请裁定归属）

| 载体 | 内容 | 位置 |
|---|---|---|
| A′ | `scenario_method_status_domain: [pending, neutral, probability_weighted]` | `rules/scenario.yaml:41` |
| B′ | `SCENARIO_METHOD_STATUSES = ("pending", "neutral", "probability_weighted")` | `scripts/pricelayer/scenario_guard.py:91` |

同一对文件、同一判据（"同一语义 / 两种载体 / 零绑定"）、值同为那 3 个 token、**同样零绑定**。
**已一并绑定**（否则下一个人要把整卡重做一遍）。两处在 `BINDINGS` 表里**逐条列出**，
**不是**折叠成一条含糊的"情景取值域检查" —— 报告里能直接看出哪一对漂了。

⇒ 若你认为第二处超出本卡范围，**删 `BINDINGS` 的一个元组即可**（取值不写在表里，表只记"哪两样是同一语义"）。

---

## ④ 四条硬要求，逐条对照

### 要求 ① 两侧都从**真源实读**，不许手写清单；**双向**相等

- A 侧：`yaml.safe_load(<code_root>/rules/scenario.yaml)` 后按键取，**不内联任何 token**；
- B 侧：`importlib.import_module` **被检 `code_root`** 的 `scripts.pricelayer.scenario_guard`，
  从**枚举成员/常量对象**实读（`isinstance(obj, type)` ⇒ 枚举走 `.value`，否则按可迭代取）；
- 相等判据：`set(declared) == set(implemented)`，且**两侧差集分别报出**
  （"声明侧多出 X" 与 "实现侧多出 Y" 是两条不同违例 —— 报告要能直接看出改哪一侧）。

★ `BINDINGS` 里那张表**不是取值清单**，是「哪两样东西是同一语义」的绑定元数据。
**取值一律实读** —— 把取值写进代码就会重演 `G-28`（清单与真源各写一份 ⇒ 必然漂移）。

### 要求 ② 可执行反例 + 反向对照

`tests/guards/test_scenario_tag_binding.py`（**5 例**，实测 **`5 passed in 14.61s`**）：

| # | 用例 | 证什么 |
|---|---|---|
| 1 | `test_clean_copy_passes_then_injecting_into_the_declaring_side_is_blocked` | **同一条用例、同一份副本**：(a) 未改 ⇒ `exit 0`（反向对照）→ (b) 注入 A 侧多一个 `custom_x` ⇒ `exit 1` 且报"声明侧多出 ['custom_x']" |
| 2 | `test_injecting_into_the_implementing_side_is_blocked` | ★ 删 B 侧枚举的 `custom` ⇒ `exit 1` 且报"声明侧多出 ['custom']"。**这条同时证伪 `_load_checked_symbols()` 的设计**：若守卫从**自己所在仓库**导入枚举，本注入**不会红** |
| 3 | `test_absent_or_malformed_declaration_fails_loudly` | A 侧**缺键** / **退化成标量** ⇒ 各 `exit 2`（输入异常，不静默） |
| 4 | `test_guard_leaves_no_global_side_effects` | 跑完后 `sys.path` 与 `scripts*` 的 `sys.modules` **原样**（见 §⑤） |
| 5 | `test_gate_is_registered_in_both_places` | `G-07`：同时出现在 `run_all_gates.py` 与 `pre-commit.sh` |

★ **反向对照与注入放在同一条用例、同一份副本上**：两次运行之间**唯一的差别就是那次注入**；
分成两条用例会引入"两份副本可能有别"的杂音。

★ **无方向只测一个是不够的**：`G-55` 的形态是"**两侧都可漂移**"，
只测 A→B 方向的话，守卫完全可能只实现了一个方向而看起来是绿的 ⇒ 用例 1 测 A 侧、用例 2 测 B 侧。

### 要求 ③ `G-07` 双落点 + 矩阵自动覆盖（**实测数量变化**）

| 项 | 改动前（实测） | 改动后（实测） |
|---|---|---|
| `run_all_gates.py::GATES` 条数 | **24** | **25**（末条 = `scenario_tag_binding_guard.py`） |
| `tests/guards/test_exit_code_contract.py` 用例数 | **52 passed** | **54 passed**（+2：干净→0 / 缺 `code_root`→2） |
| `pre-commit.sh` 门数 | **11** | **12**（第 ⑫ 道） |

```
# ── 对象（口径 9/10：读数一律带树 + SHA）──
#   "改动前" = /Users/gaza/Developer/InvestSigh        @ 4006663                   (main)
#   "改动后" = .worktrees/ws-schema-expand             @ 7835c0b                   (ws/ch13-e-benchmark-fields)
#   ★ 取样后 main 已前进到 2fad7eb ⇒ 上面的"改动前"只在 4006663 这个对象上成立

$ python -c "…load GATES…"                       # @4006663(main) → 24
$ python -c "…load GATES…"                       # @7835c0b       → 25
$ run_pytest.sh tests/guards/test_exit_code_contract.py -q
  @4006663(main) → 52 passed in 18.50s
  @7835c0b       → 54 passed in 19.21s
$ run_all_gates.py . --timeout 60                # @7835c0b
  … scenario_tag_binding_guard.py      exit=0        0.22s      ← 已进汇总表
$ sh system/scripts/ops/pre-commit.sh            # @7835c0b
  pre-commit → scenario_tag_binding_guard
  RESULT: PASS（0 violations）
  pre-commit ✓ 全部门禁放行          ← 12 道门全绿
```

★ **矩阵是派生自 `GATES` 的**（`G-28` 的根治），故加一条 `GATES` 即**自动**受两条契约约束
（干净 → 0 / 缺 `code_root` → 2）⇒ 上面这两条**不是**我为本守卫手写的，是派生来的；
我实测的是"**派生确实覆盖到了它**"（52 → 54）。

★ 我**没有**顺手写一条"`GATES` 里每条都必须进 `pre-commit.sh`"的通用规则：
`pre-commit.sh` 跑 12 道而 `GATES` 有 25 条，**两者的包含关系是设计决定、不是缺陷**
⇒ 通用规则需要一次裁定，不该由本卡凭"看起来更严"发明（那会当场造出一条假红的门禁）。
本卡只把**本守卫**的这条义务变成可执行的（用例 5）。

### 要求 ④ 归我收口

`schema/**` 与我新建的检查器、测试、`GATES`/`pre-commit` 两处登记，改动的写入面全在本卡授权内。
**未动**：`rules/**`（0444 锁件）、`scripts/pricelayer/**`（13-B 写入面）、`verify.py`（与 13-A 争用，见 §⑦）。

---

## ⑤ 守卫的两处**设计要点**（各自都有可执行断言，不是注释里的承诺）

### 5.1 必须加载**被检 `code_root`** 的实现

否则对夹具副本做注入测试时，守卫会永远看着真仓库的枚举而"通过" ⇒ 注入测试**证伪不了它**
（同 `schema_sync_guard._load_builder` 的教训；`§5.1 AC-04` 要的正是"注入违例 ⇒ exit 1"这条可证伪性）。
由**用例 2** 证伪：改副本的 `scenario_guard.py` 必须变红。

### 5.2 带全局副作用的加载器**必须自己收尾**

为了从被检 root 读实现，必须**临时**删掉 `scripts*` 的 import 缓存并把被检 root 插到 `sys.path` 首位。
而本守卫在测试里是**进程内执行**的（`run_gate_inproc` 走 `runpy`）⇒ 不还原会污染整个测试进程：
后续检查器从**已被删除的夹具目录**导入，引发一批与本守卫毫无关系的失败
（`schema_sync_guard` 的 docstring 记录的正是这次实测事故，代价是 **16 条**无关失败）。
⇒ 由**用例 4** 把"必须收尾"变成可执行的（比对 `sys.modules` 条目集合 + **对象同一性** + `sys.path`）。

### 5.3 三道**真空/退化**防护（`G-03` 家族）

| 退化形态 | 不防会怎样 | 处置 |
|---|---|---|
| 任一侧为空 | "两个空集合相等" ⇒ 绑定断言**真空成立** | 违例（点明两侧计数） |
| A 侧**缺键** | `set()` vs 非空枚举 ⇒ 报成"实现侧多出全部 token"，**归因错** | `exit 2` + 点名缺哪个键 |
| A 侧**退化成标量** `scenario_tags: bear` | `set("bear") == {'b','e','a','r'}` ⇒ 拿**字符集合**与枚举比，"看着像在比、其实毫无意义" | `exit 2` + 说明形态错误 |

---

## ⑥ ★ 一个新发现：`guards` 批**超时是既存的**（与 `G-54` 同族，非本卡引入）

### 6.1 事实（同条件对拍）

★ **口径 9/10 订正（本报告初版只写了"本分支/main"，未带 SHA ⇒ 判词会随对象漂移而失真）**：
下列读数**一律带树 + SHA**；且取样时 `main` = `4006663`，此后 `main` 已前进到 `2fad7eb`
（含 13-A 合并与本轮新裁定）⇒ **下面的 `main` 读数只在 `4006663` 这个对象上成立**，
不得被引用为"当前 `main` 的状态"。

```
# 树 = .worktrees/ws-schema-expand @ 64aed64（ws/ch13-e-benchmark-fields）
$ verify.py --batch guards   → ✗ exit=124  60.01s/60s  **超时**

# 树 = /Users/gaza/Developer/InvestSigh @ 4006663（main，取样时刻同批次）
$ verify.py --batch guards   → ✗ exit=124  60.01s/60s  **超时**
```

**两个不同对象、同一条命令、同一时段** ⇒ 与本卡改动**无关**。

### 6.2 但"超时"不是"永远超时" —— 是**高方差**（`G-54` 的同一机理）

| 观测 | 树 + SHA | 命令 | 结果 |
|---|---|---|---|
| ①（宿主多流并发时） | `.worktrees/ws-schema-expand` @ **`64aed64`** | `run_pytest.sh tests/guards -q --durations=8` | **71 passed in 101.96s** ⇒ 越过 60s **1.7×** |
| ②（较静时，含本卡 +5 例） | 同树 @ **`7835c0b`** | `run_pytest.sh tests/guards -q` | **76 passed in 30.73s** ⇒ 只到 60s 的 **0.51×** |

★ 两次是**不同对象**（② 比 ① 多本卡的 5 例）且**不同宿主负载** ⇒ 3.3× 的跨度里，
**"负载"与"我加的 5 例"两个因子未被分离**；本卡只声明"读数跨度 3.3×"，**不声称**其中多少归因于哪一个。
要分离需在**同一 SHA** 上做差分实验 —— 属 13-F 的取证范围。

★ **合并 `main` 后的复跑**（对象 = 同树 @ **`664252f`**）：本守卫 `exit=0`；
`run_all_gates.py . --timeout 60` 非零计数仍为 **1**（仅既存 `traceback`）；
`run_pytest.sh tests/guards/test_scenario_tag_binding.py tests/unit/test_schema_expand.py -q`
→ **48 passed in 32.44s**（5 + 43）。⇒ 合并**未**使本卡失效。

`①` 的 `--durations=8` **全部是 `setup`**（5.15 ~ 6.49s/例），与 `G-54` 记录的 `unit` 批**逐字同形**：

```
6.49s setup  tests/guards/test_verification_policy.py::test_full_suite_batch_is_rejected
5.15s setup  tests/guards/test_exit_code_contract.py::test_guard_exits_zero_and_reports_scanned_on_pristine_tree[conflict_scan]
```

★ **根因同 `G-54`**：共享夹具（`conftest.py::code_root` 一族）**每例整树拷贝**，成本随仓库体积线性增长。
`guards` 批的 60s 上限对这个规模**本来就不够**，只是宿主不忙时才侥幸通过。

### 6.3 影响（为什么值得报）

★ **本节判词的作用域（口径 10）**：以下结论所依据的读数取自
`main@4006663` 与 `.worktrees/ws-schema-expand@64aed64 / @7835c0b`（见 §6.1/§6.2）。
**判词对这三个对象成立**；`main` 此后已前进到 `2fad7eb`，
**若要在新的 `main` 上引用本判词，应按新 SHA 重跑后再判**（不得把本判词当"当前 `main` 的状态"）。

`verify.py --batch guards` 会**随机**判 TIMEOUT ⇒ 该批的覆盖处于**不可信**状态
（同 `G-54` 对 `unit` 的判断：**它让这一批的门禁不可信**）。
按本项目自己的教训「**天天误报的门禁一定会被关掉**」，这是下一个会被 `--no-verify` 绕过的口子。

### 6.4 我**没有**做什么（边界，如实）

- **未改 `verify.py` 的 `guards` 超时**：① 不在本卡授权面；② `verify.py` 正被 13-A 争用
  （任务卡 `R2` 明令"13-A 只加 `valuelayer` 条目、不得动 `pricelayer`"—— 同源冲突）；
  ③ 超时值属 `V-02` 台账，改它应走 `G-54` 的同一条处置链。
- **未把用例搬去 `tests/injection/`**：那里有**分片用例配额**的机器绑定（`test_shard_coverage.py::MAX_CASES_PER_SHARD`），
  搬过去可能撞配额；且"守卫行为"的既有归属就是 `tests/guards/`。
- **未手搓更便宜的夹具**：那等于复刻 `conftest` 的复制逻辑，正是"同一事实两个存放处"的开端。

### 6.5 ★ 本卡的**边际成本**，如实报数（供你判断是否要我先降本）

我的 3 条夹具用例 = **3 次整树拷贝**（用例 4/5 不起夹具，用真仓库，成本 ≈ 0）。
单文件实测 **5 passed in 14.61s** ⇒ 3 次拷贝约占 **14s**，压在一条**已经逼近 60s** 的批上。
若你希望我先降本，可把用例 1~3 合并成 1 次拷贝（**代价**：三个不同的注入面失去独立归因）。
**我的建议：先不动**（正确性与归因优先），把 `guards` 批的超时/根因与 `G-54` **合并成一条**交给 13-F。

---

## ⑦ 建议（请裁定）

1. **`G-55` 覆盖范围**：是否把 §③ 的第二处（`scenario_method_status_domain` ↔ `SCENARIO_METHOD_STATUSES`）
   正式并入 `G-55` 的描述（现在的登记语只点了 `scenario_tags` 一处）。
2. **`guards` 批超时**：是否按 `G-54` 的先例上调（`V-02`：以较慢一次 101.96s 为基准 → 约 400s 会**超过 300s 上限**，
   故按上限取 **300s**，并把它并入 13-F 的"每批实测耗时 vs 超时对照表"）。
   ★ 这一步会改 `verify.py`，**需要你避开与 13-A 的冲突**后再派。
3. **`G-07` 是否升格为通用规则**（"哪些门必须两处都在"）：需要一次裁定定义包含关系，
   本卡只做了本守卫这一条。

---

## ⑧ 纪律留痕（本卡踩到的坑）

| # | 坑 | 处置 |
|---|---|---|
| 1 | ★ **注入型测试的 `no-op` 陷阱**：`rules/scenario.yaml` 那一行**带行尾注释**，我按 `"… [bear, neutral, bull, custom]\\n"`（**带换行**）替换 ⇒ **没匹配上** ⇒ `write_text` 写回原文 ⇒ "注入"什么都没做，守卫**照样绿**，而用例以含糊的"期望 1 实得 0"把**归因指向守卫**（假缺陷） | 抽出 `_inject()`：**先断言注入点存在、再断言替换前后文本不同、最后断言已落盘** —— 注入必须**自证已生效**。这条很可能是本项目"反例测试"的通用坑（反例若 no-op，"有反例"就是假的） |
| 2 | 两臂连续改同一文件：第二臂的锚点已被第一臂删掉 ⇒ `_inject` 报"注入点未找到"，把"形态检查没生效"混成"测试写坏了" | 每臂**各自从原文出发**（`path.write_text(original)`），不叠加 |
| 3 | `verify.py --batch unit` 报 `No module named pytest` | `python` 解析到的解释器无 pytest；官方入口 `run_pytest.sh` 用 `$HOME/.workbuddy/binaries/python/envs/default/bin/python` ⇒ 显式用该解释器 |
| 4 | ★ **BSD `grep` 的 BRE 不支持 `\|`**（本会话**第四次**踩到：核 `field_serializer` 位置时零命中）| 一律 `grep -E` / ripgrep。第三次的教训已写进 13-E 报告 §⑥，本次仍复现 ⇒ 说明"记下教训"不足以改变习惯，**应把它变成机器绑定**（如 `shell_var_guard` 那样加一道 `grep` 用法检查）——登记为一个观察，本卡不做 |
| 5 | 未 `git add -A` | 只 `git add` 具名文件；提交后 `git status --short` 应为空 |
