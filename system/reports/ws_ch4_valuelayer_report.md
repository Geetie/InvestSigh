# 批次 13-A · Ch4 价值层（`scripts/valuelayer/**`）· 交付报告

> 分支：`ws/ch4-valuelayer`　｜　工作树：`.worktrees/ws-ch4-valuelayer`
> 基站：`main` 已前移到 **`bb8991a`**（含 13-B `ws/ch5-pricelayer`、13-R 四个规则文件、`ws/ch13-d-valuation-fields`）——
> 本单开工时基站在 `d74a829`，交付前**重新 `git merge main`** 并解冲突（见 §1.4）
> 交付人：`ws-ch4-valuelayer`　｜　任务卡：`system/reports/batch13_taskbook.md` 卡 13-A

本报告遵四段式：**① 改了什么 → ② 测了什么（真实输出 + 退出码，正反两向）→ ③ 每条 DoD 的证据 → ④ 剩余不确定性与缺口。**

---

## ① 改了什么

### 1.1 新增：`system/scripts/valuelayer/**`（8 个文件，本卡交付物）

| 文件 | 职责 | 设计锚点 |
|---|---|---|
| `__init__.py` | 包 + PEP 562 惰性子模块（避免 import 即拉 pydantic） | `CONVENTIONS §三 P-03` |
| `_rules.py` | ★ `rules/{baseline,metric-sets}.yaml` 的**唯一读口**（`G-06`）；缺文件/缺键**响亮失败**，**不内置任何默认值** | `Ch11 §D.2` · `Ch4 §G.2` · `§J.4 J3` |
| `route_guard.py` | 指标集绑定**防串味** + 段序不跳级 + `§C.3` 未注册兜底 | `Ch4 §C` |
| `rollup.py` | 分部 → 公司层加总（**不跨业务混用语义**）；三条约束**整次拒绝**，不给部分结果 | `Ch4 §C.2` 末句 |
| `growth_quality.py` | 增长质量 / ROIIC / **代价五类** + 驱动上限 + 收入增速 denylist | `Ch4 §D` |
| `moat_guard.py` | 护城河**反误判** + 六保护对象 + `§F.3` A1/A2/A3 硬隔离 | `Ch4 §F` |
| `state_machine.py` | 3×4 状态机 + 增量更新 + **无变化不产新版本** | `Ch4 §H` |
| `completeness.py` | ★ **形式完备性校验器**（`form_complete` 五项 + `§G.3` gap + `§G.4` 分支） | `Ch4 §G.2/§G.3/§G.4` |

### 1.2 新增：`system/tests/valuelayer/**`（7 个文件）

`_fixtures.py`（共享夹具，含"两套阈值取值"的用意见 §4.3）+ 六个模块各自的用例文件。
**206 个用例**（按 junit 实测，逐文件分布见 §2.6）。

### 1.3 改了 5 个**共享**文件（每一处都逐条说明改动面）

| 文件 | 改动面 | 为什么必须改 |
|---|---|---|
| `scripts/delivery/stage_gate.py` | ★ **只改 `stage_nvidia_sample_passed()` 函数体内**：加 2 行（`from scripts.valuelayer.completeness import g_depth_violations` / `v += g_depth_violations(root)`）+ 1 行 `criterion("nvidia_sample","chapter4_g_depth", v)` 字面量 | 任务卡明令的**判据绑定**；`stage_gate.py` 是共享文件，**只动这一处** |
| `scripts/orchestrate/chain_steps.py` | `make_growth_handler`（**step 4**）的处理器体 + 模块顶部映射表第 4 行 | 任务卡明令"新模块必须有生产调用方" |
| `scripts/ops/verify.py` | `BATCHES` 加 `"valuelayer"` 批（`_pytest("tests/valuelayer")`, 300.0s, `_exit_zero`）+ `ORDER` 里 `"pricelayer"` 之后插入 `"valuelayer"` | `V-06`：新测试目录必须入批次 |
| `registry/criterion_counterexamples.yaml` | 追加 1 条 `nvidia_sample::chapter4_g_depth` 反例条目 | 判据有效性门禁的义务（已绑定 ⊆ 已登记） |
| `tests/injection/test_criterion_effectiveness.py` | 追加 1 个反例用例（`_nvidia_ch4_compliant` + `test_nvidia_sample_chapter4_g_depth_blocks_on_incomplete_form`）；同步 5 个写死的台账计数 | 反例必须**真实存在**且函数名含判据 id（`AST` 校验） |

★ **`rules/**` 零内容改动**：`git diff --stat -- system/rules` 为空。

### 1.4 ★ 交付前的 `git merge main` 与两处冲突（**这里出了一个必须知道的事**）

开工时基站 `d74a829`，交付前 `main` 已到 `bb8991a`。合并结果：

- **冲突 2 处**，均已解：
  1. `verify.py::ORDER` —— main 加了 `"pricelayer"`，我加 `"valuelayer"`：**两条都保留**。
  2. `test_criterion_effectiveness.py` 的 5 个写死计数 —— main 已到
     `criteria_bound: 12 / registry_entries: 15 / counterexample_entries: 14 / ineffective: 1 / without_counterexample: 0`，
     我在其基础上各 +1（实测见 §2.5）。
- ★★ **合并带来一个**使本单代码在真仓库上**整体失效**的变化：**13-R 已把 `rules/baseline.yaml`
  与 `rules/metric-sets.yaml` 安装进 main**。我的读口初版是按设计里**扁平写法**读顶层键，
  真文件是 **`thresholds:` 分组**且键名不同 ⇒ 若不改，`chapter4_g_depth` 会因"阈值永远读不到"
  而**恒红**（`G-01`：恒红的门禁一定会被关掉）。**已按 `R8-1` 裁定改为读实有结构**，见 §4.2。
- 合并后需补 `sh system/scripts/ops/bootstrap_worktree.sh`：git 不跟踪只读位，merge 进来的
  4 个 `rules/*.yaml` 是 `0644` ⇒ `rules_lock_guard` 与 `injection_guard` 双双报"纪律 9"（4 条）。
  该脚本**只改权限位**、内容零改动，跑完两门禁即 PASS、`git status` 无额外变化。

---

## ② 测了什么（真实输出 + 退出码；正反两向）

> 命令一律在 `/Users/gaza/Developer/InvestSigh/.worktrees/ws-ch4-valuelayer/system` 下执行。
> CLI 证据的夹具根建在 `/tmp/ch4-cli-roots/`（**不进仓库**），驱动脚本 `/tmp/ch4_cli_evidence.py`。

### 2.1 六个模块的"注入违例 ⇒ exit 非零"（汇总表；逐个真实输出见 §2.2–§2.4）

```
  route_guard                        EXIT=1   ← 硬件业务绑了软件的指标集（§C.2 防串味）
  route_guard(合规对照)                 EXIT=0
  route_guard(注册类绑通用)               EXIT=1   ← 注册类型却绑 MS-GENERIC（字面比 model_class 会放它过去）
  route_guard(模板注册表)                EXIT=0   ← 未声明 owner_business_id ⇒ 归属判等"不可核"：note + 放行
  growth_quality                     EXIT=1   ← 驱动缺 §D.3 的五项代价
  growth_quality(合规对照)              EXIT=0
  moat_guard                         EXIT=1   ← 护城河条目缺 writer（A3 白名单默认拒，R-06 ⑤）
  moat_guard(合规对照)                  EXIT=0
  completeness                       EXIT=1   ← moat[] 被清空（形式完备性）
  completeness(合规对照)                EXIT=0
  completeness(缺阈值键)                EXIT=2   ← 输入异常，与"命中违例"刻意分开
  completeness(真规则文件)               EXIT=0   ← ★ 用真仓库安装的 rules/，六项全过
```

### 2.2 `route_guard` —— 正反两向（真实输出）

```
$ python3 scripts/valuelayer/route_guard.py <root> --no-report
== valuelayer_route_guard.py ==
  scanned businesses: 1
  scanned metric_sets: 4
  scanned stage_sequence_not_evaluable: 0
  note: OWNER_NOT_DECLARED: 1 个业务绑定的指标集在注册表里**未声明** metric.owner_business_id ⇒
        该指标集的'跨业务引用'检查**不可核**（不可核 ≠ 已核，G-03）…
  [FATAL] Ch4-C2 @ facts/businesses.jsonl:0 — BIZ-1: BIZ-1 的路由结果是 'MS-HW-6STAGE'，却绑定了
          'MS-SW-5STAGE'（Ch4 §C.2 外键一致性：绑定的必须正是路由到的那一个…）
  [FATAL] stage_unregistered @ facts/businesses.jsonl:0 — BIZ-1: conversion_chain 出现 MS-SW-5STAGE 的
          stages 里没有的段名 ['order', 'production_schedule', 'shipment']
RESULT: FAIL（2 violations）          EXIT=1

$ （把 metric_set_id 换回 MS-HW-6STAGE）→ RESULT: PASS（0 violations）   EXIT=0

$ （registered 类型 hardware 却绑 MS-GENERIC）
  [FATAL] Ch4-C2 … — BIZ-HW: BIZ-HW 的路由结果是 'MS-HW-6STAGE'，却绑定了 'MS-GENERIC' …
RESULT: FAIL（1 violations）          EXIT=1
```

★ 第 1 例与第 3 例同时钉住 §C.2×§C.3 冲突的收口：**注册类型绑通用会被拦**（"字面等 model_class"
会放它过去，因为 `generic` 谁都能匹配）。

### 2.3 `completeness` —— 五项**逐项可定位** + `tbd` 半项如实降级

```
$ python3 scripts/valuelayer/completeness.py <root> --no-report     # moat=[] 且 valuation_inputs={}
== valuelayer_completeness.py ==
  scanned baselines: 1
  scanned checks_total: 6
  scanned min_fields_undecided_sections: 1
  note: sections_nonempty[baseline-nvda-001]: MIN_FIELDS_UNDECIDED: `rules/baseline.yaml::thresholds
        .min_fields_per_section` 为 `tbd`（设计未给数值，13-R 如实转写）⇒ §G.2 项①的
        『达最小字段数』半项**不可核**（本次 6 个 section），已按下界 1（=『非空』）强制；不可核 ≠ 已核（G-03）
  note: gap[baseline-nvda-001]: required_input=['sections_nonempty'] （Ch4 §G.3：缺口可见…）
  note: form_complete[baseline-nvda-001]: sections_nonempty=fail；nonnull_rate=pass；has_locator=pass；
        has_derivation=pass；cross_section_consistent=pass；g4_profitability_branch=pass
  [FATAL] Ch4-G2-sections_nonempty @ facts/baselines.jsonl:0 — baseline-nvda-001: ④护城河 为空
          （0 个字段非空，§G.2 项①'六项 section 非空'）；空字段 ['moat']
RESULT: FAIL（1 violations）          EXIT=1

$ （恢复 moat/valuation_inputs）→ RESULT: PASS（0 violations）   EXIT=0

$ （从真发布的 rules 里拿掉 min_locator_count）
[INPUT-ERROR] valuelayer_completeness.py: MissingRuleInput: rules/baseline.yaml::thresholds 缺少键
  'min_locator_count' —— Ch4 §G.2/§D.2 要求该阈值参数化在规则文件里，代码不内置默认值
  （现有键：['max_primary_drivers_per_business', 'min_derivation_count', 'min_fields_per_section',
   'min_nonnull_rate']）
                                     EXIT=2
```

★ **`EXIT=2` 与 `EXIT=1` 是两件事**：前者"我不知道该按什么标准判"，后者"我知道标准、对象不达标"。
把两者混成一个出口会让"规则没装好"看起来像"数据不合格"。

### 2.4 两个**纯函数**模块（`rollup` / `state_machine`）—— 如实说明"它们没有 CLI"

★ 这两件**刻意不做 CLI**：它们没有"真源可扫"，是被调用方喂数据的**纯函数**
（加总 / 状态推进），做成 CLI 会是一个**扫不到任何东西的空壳**（正是"孤儿模块"的另一种形态）。
它们的违例契约是**抛异常**，故用真实解释器直接跑、贴真实异常：

```
  rollup[分部链未完成] → IncompleteSegmentRollup: 1 个分部尚未完成（['BIZ-1:revenue']）
                         —— Ch4 §C.2 要求'在分部层完成后合并'，不得先合并一个缺块的所谓公司层数字
  rollup[跨业务引用指标] → CrossBusinessSemanticMismatch: 禁止跨业务直接引用指标（Ch4 §C.2）：
                          BIZ-1:revenue 的指标归属为 'BIZ-2'
  rollup[同科目跨币种]  → CrossBusinessSemanticMismatch: 同一科目在不同分部使用了不同币种
                          {'revenue': ['cny', 'usd']} —— 跨币种换算属 scripts/compute/fx（Ch9 §3.4.4）
  rollup[合规对照]      → 放行 by_account={'cogs': Decimal('4'), 'revenue': Decimal('10')}
                          businesses=('BIZ-1',)

  无新信息      → changed=False wrote_new_version=False note='本次核查无变化'      ← §H.2 不写新版本
  有新信息      → growth=weakening changed=True judgment_change={'growth_momentum_state': True, …}
  state_machine[非法取值] → ValueError: direction='totally_bogus' 不在
                          ['strengthening','weakening','unchanged','tbd'] 内 —— 方向四值取自 DirectionState（§H.1）
  state_machine[越权写水平轴] → ValueError: dimension='moat_level' 不在三方向维度内 …（水平轴另有取值域）
```

### 2.5 判据绑定端到端（真仓库）

```
$ python3 scripts/delivery/stage_gate.py . --stage nvidia_sample --no-report
  scanned nvidia_sample.criteria_bound: 3                      ← 绑定前是 2
  note: 判据台账[nvidia_sample]：函数体内已绑定 3 条，**声明为 automated 但未绑定 1 条
        → ['evidence_locatable']**（…不得据声明判 PASS）
  [FATAL] nvidia_sample @ facts/baselines.jsonl:0 — Ch4 §G 形式完备性未过 [baseline-nvda-001][sections_nonempty]：…
  [FATAL] … [baseline-nvda-001][nonnull_rate]：必填字段非空率 0.1429 < 阈值 0.9（空字段 […]）
  [FATAL] … [baseline-nvda-001][has_derivation]：baseline 未引用任何 DerivedValue ⇒ 无被检对象…
  [FATAL] … [baseline-nvda-001][cross_section_consistent]：… ⇒ 无跨节引用可核…
  [FATAL] … [baseline-nvda-001][g4_profitability_branch]：is_profitable 未判定（None）…
RESULT: FAIL（13 violations）
```

★ **`chapter4_g_depth` 已从"未绑定"变成"会拦"，且违例逐项可定位。**
（阶段整体仍是 `BLOCKED`——那由 `six_step_chain_complete` / `evidence_locatable` 与真实数据缺口决定，
**不是**本判据的功劳或责任，如实记。）

```
$ python3 scripts/checks/criterion_effectiveness_guard.py .
  scanned counterexample_entries: 15      scanned criteria_bound: 13
  scanned criteria_registry_entries: 16   scanned registry_entry_tests_resolved: 16
  scanned ineffective_entries: 1          scanned criteria_without_counterexample: 0
RESULT: PASS（0 violations）          EXIT=0
```

### 2.6 测试

```
$ sh scripts/ops/run_pytest.sh tests/valuelayer -q --junitxml=/tmp/ch4_all.xml
tests=206  failures=0  errors=32  skipped=0
```

★ **32 个 `errors` **不是**测试失败**，是 `code_root` 夹具的 **setup** 阶段被宿主的
safe-delete 每轮批量删除阈值拦下（`SystemExit: 1`；junit 原文：`failed on setup with "SystemExit: 1"`）。
宿主消息：`[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":100266,"threshold":99999,"scope":"turn"}`。
**这一现象在本仓库已被登记过**（`tests/conftest.py::_empty_truth_template` 的 docstring：
"宿主对单次批量删除有数量阈值…该策略**按 turn 施加**，子进程环境变量关不掉"）。
⇒ 处置：把 32 个夹具用例**按 ≤10 例/批**分 6 批重跑，**全部通过**：

```
$ sh scripts/ops/run_pytest.sh tests/valuelayer/test_completeness.py -q \
    -k "missing_threshold or null_threshold or cli_reads or cli_exits or cli_reports or context_loader or seeded_fixture"
10 passed, 39 deselected in 46.85s                      EXIT=0

$ … tests/valuelayer/test_growth_quality.py -q -k "cli_"
6 passed, 28 deselected in 29.18s                       EXIT=0

$ … tests/valuelayer/test_moat_guard.py -q -k "cli_"
5 passed, 26 deselected in 3.07s                        EXIT=0

$ … tests/valuelayer/test_route_guard.py -q -k "registry_reads or registry_rejects or cli_exits_zero"
3 passed, 32 deselected in 13.80s                       EXIT=0
$ … tests/valuelayer/test_route_guard.py -q -k "cli_flags"
4 passed, 31 deselected in 18.25s                       EXIT=0
$ … tests/valuelayer/test_route_guard.py -q -k "cli_accepts or cli_reports or cli_treats"
4 passed, 31 deselected in 21.37s                       EXIT=0

$ … tests/valuelayer/test_rollup.py tests/valuelayer/test_state_machine.py -q
47 passed in 0.75s                                      EXIT=0
```

**10 + 6 + 5 + 3 + 4 + 4 = 32** —— 与 junit 报出的 32 个 `error` **一一对应**；
因此 **206 个用例全部通过，0 failure**。逐文件分布：

```
文件                                   共   夹具 error   本轮跑通
 test_completeness.py                  59       10         49
 test_growth_quality.py                34        6         28
 test_moat_guard.py                    31        5         26
 test_rollup.py                        14        0         14
 test_route_guard.py                   35       11         24
 test_state_machine.py                 33        0         33
 合计                                 206       32        174       ← 174 + 32（分批补跑全绿）= 206
```

### 2.7 注入层（我改动过的三处）

```
$ sh scripts/ops/run_pytest.sh tests/injection/test_criterion_effectiveness.py -q \
    -k "chapter4_g_depth or guard_passes_on_pristine_tree or removing_any_registry_entry"
3 passed, 24 deselected in 25.28s                       EXIT=0
$ … tests/injection/test_chain_steps_wiring.py tests/injection/test_shard_coverage.py -q
17 passed in 43.73s                                     EXIT=0
```

### 2.8 门禁（`run_all_gates.py`）

```
$ python3 scripts/ops/run_all_gates.py --timeout 40
  … 24 项 …            非零计数 1
  traceback.py                       exit=1        0.19s
```

★ **唯一非零项 `traceback.py` 是预先存在的，与本单无关** —— 用 `git archive HEAD` 造一份
**未含我任何改动**的快照对拍，输出**逐字相同**：

```
$ cd /tmp/maincheck/system && python3 scripts/trace/traceback.py . --no-report
  [FATAL] G1-03 @ facts/recommendations.jsonl:0 — rec-nvda-001 四要素（**适用项**）缺失: ['assumptions','computation']
  [FATAL] G1-03 @ facts/recommendations.jsonl:0 — 四要素（适用项）反查成功率 0.0000 < 1.0
RESULT: FAIL（2 violations）          EXIT_HEAD=1
```

★ 另两处曾短暂非零、**已定位并修复**（见 §1.4）：`rules_lock_guard` / `injection_guard`
报 merge 进来的 4 个 `rules/*.yaml` 是 `0644`；`bootstrap_worktree.sh` 复原 `0444` 后双双 PASS。

```
$ sh scripts/ops/run_all_gates.py --timeout 40   → 非零计数 1（同上）
$ python3 scripts/checks/verification_policy_guard.py .   → scanned batches: 22 / test_files_uncovered: 0
                                                             RESULT: PASS（0 violations）  EXIT=0
$ python3 scripts/checks/no_placeholder_guard.py . --fail-on warn
                                                             scanned files: 143（含我的 15 个新文件）
                                                             RESULT: PASS（0 violations）  EXIT=0
```

---

## ③ 每条 DoD 的证据

| # | DoD（任务卡原文） | 证据 | 结论 |
|---|---|---|---|
| 1 | 6 个模块建成，`import` 可跑，无 `pass`/`NotImplementedError`/假数据 | §2.1 六个模块全部有真实 CLI/异常路径；`no_placeholder_guard` 扫 143 文件 PASS（含我的 15 个）；`grep NotImplementedError\|pass\b` 于 `scripts/valuelayer/**` 为 0 | ✅ |
| 2 | `completeness` 五项**逐项**有正反用例；阈值**只**来自 `rules/baseline.yaml` | `tests/valuelayer/test_completeness.py` 59 例（49 纯逻辑 + 10 夹具），逐 `check_id` 断言 `pass`/`fail`；§2.3 的 `EXIT=2`（缺键即输入异常，代码不兜底）；§2.3 `EXIT=0`（真文件六项全过） | ✅ |
| 3 | `chapter4_g_depth` **已在 `stage_gate` 函数体内绑定**且**有反例登记**，门禁实测能被击穿 | §2.5：`criteria_bound: 3`（原 2）且真仓库输出 `Ch4 §G 形式完备性未过 […]`；`registry/criterion_counterexamples.yaml` 有 `nvidia_sample::chapter4_g_depth` 条目；`criterion_effectiveness_guard` PASS 且 `registry_entry_tests_resolved: 16`；§2.7 反例用例 `passed` | ✅ |
| 4 | 每个守卫**注入违例 → exit 非零**（贴真实输出） | §2.1–§2.4：4 个有 CLI 的模块注入违例 `EXIT=1`、反向对照 `EXIT=0`、配置缺失 `EXIT=2`；2 个纯函数模块贴真实异常类 | ✅ |
| 5 | `tests/valuelayer` 全绿；`run_all_gates` 无新增非零项 | §2.6：**206 用例 / 0 failure**（32 个夹具用例分 6 批补跑全绿）；§2.8：非零 1 项且已用 HEAD 快照证明**预先存在** | ✅ |
| 6 | 报告四段式 | 本文件 | ✅ |
| 7 | 新测试目录已同步入 `verify.py::BATCHES`（`V-06`） | `verify.py` 加 `"valuelayer"` 批 + `ORDER`；§2.8 `verification_policy_guard` → `batches: 22` / `test_files_uncovered: 0` / PASS | ✅ |
| 8 | 新模块有生产调用方（不留孤儿） | `chain_steps.make_growth_handler`（step 4）真的调用 `route_guard.check` / `growth_quality.check` / `moat_guard.check` / `g_depth_violations`；违例逐条进 `incomplete_reason`（**不静默**）；`produced` 恒空（价值层只核不产，`纪律 7`）+ `degraded=True` ⇒ 编排器记 `gap` + `blocked`。§2.7 `test_chain_steps_wiring.py` 17 passed | ✅ |
| 9 | `rules/**` 零改动 | `git diff --stat -- system/rules` 为空；`git status --short system/rules` 为空 | ✅ |

---

## ④ 剩余不确定性与缺口（**逐条登记，不猜**）

### 4.1 ★ 已由 13-R / `R8-1` 裁定，本单**照裁定实现**（初版猜的键名/深度已被推翻）

| 项 | 我的初版（当时设计只给语义） | **已安装真文件 / `R8-1` 裁定** | 处置 |
|---|---|---|---|
| `cfg` 的**深度** | 顶层扁平键 | **`baseline["thresholds"]`** 分组（`R8-1`："代码一律按本文件实有结构读"） | 已改 `_rules.baseline_cfg` |
| 定位数阈值键名 | `min_locators` | **`min_locator_count`** | 已改 |
| 推导数阈值键名 | `min_derivations` | **`min_derivation_count`** | 已改 |
| 最小字段数阈值 | 猜 `1`（占位） | 真文件为 **`tbd`**（设计未给值） | 见 §4.2 |
| 六项 section 名称 | `① 业务与产业位置`（多一个空格） | `①业务与产业位置`（`form_completeness.sections`） | 已逐字对齐 + 加漂移绊线用例 |

### 4.2 ★ `min_fields_per_section = tbd` 的处置（**本单唯一的"降级"决定，请复核**）

- **事实**：设计 `§G.2` 表格写"六项 section 非空**且达最小字段数**"，但**未给数值**；
  `00_待拍板项清单.md B5` 只定了非空率与定位数 ⇒ 13-R 如实转写 `tbd` + `basis`。
- **两难**：① 当成缺键 ⇒ 判据**恒红**（`G-01` 明禁）；② 代码里兜一个数 ⇒ "设计从未拍板"**不可观测**（`G-03` 明禁）。
- **我的处置（可判定、且两个禁则都不违）**：把该项拆成两半——
  **『非空』可核 ⇒ 照常强制**（不依赖任何阈值，`moat: []` 照样被拦）；
  **『达最小字段数』需阈值 ⇒ 记 `不可核` + 计数 + note**，既不放行也不恒红。
  - 机器可读计数：CLI `scanned["min_fields_undecided_sections"]`；
  - 人可读：`MIN_FIELDS_UNDECIDED: …` note（含"本次 6 个 section"）；
  - `g_depth_violations` 的**前置校验**刻意**不**要求该键已拍板（否则恒红）。
- **需要需求方做的**：给 `min_fields_per_section` 拍一个数（写进 `rules/baseline.yaml::thresholds`
  并重锁），此后该半项自动变成可核、note 消失、强制力自动生效 —— **不需要改代码**。

### 4.3 ★ 仍然没有裁定的（本单按"最小可判定"实现，供复核）

1. **`§C.1` 模板式注册表 vs `§C.2` 逐条归属断言**：真文件已佐证**模板式**
   （`metric_item_fields: [name, unit, source_class, linked_account]` **不含** `owner_business_id`；
   各 `metric_set` 的 `metrics` 全是 `tbd`）。但 `binding_guard.rule_metric_owner_must_be_own_business: true`
   又要求 `m.owner_business_id == business.business_id`。
   → 本实现的判据：**注册表声明了归属就严格判等；一条都没声明 ⇒ 该检查"不可核"**
   （`OWNER_NOT_DECLARED` note + 计数 + 放行，**不恒红**）。**待裁定**：`owner_business_id`
   到底该由谁写（注册表？还是业务侧另有一张"指标归属"表）。
2. **`§C.2` × `§C.3` 的冲突**：`§C.2` 字面用 `business.model_class != metric_set.model_class`，
   而 `§C.3` 让未注册类型归入 `model_class: generic` ⇒ 字面比较会让 `§C.3` 的**正常路径恒红**。
   → 本实现的判据（有注册表时）= **路由相等**（"你绑的必须正是你路由到的那一个"），
   比字面**更强**（"注册类却绑 `MS-GENERIC`"会被拦下，字面比较放它过去）。**待裁定**是否认可。
3. **`CLAIM_KINDS_KEY`**（护城河证据类别取自 claim 的哪个键）：真文件未定义，
   夹具用 `moat_evidence_kinds`。**待裁定**键名与取值域。
4. **`Ch4 §G.1⑥` 的循环接缝**：⑥"价格与行动"要 Ch5 三个判断 + Ch7 建议，
   Ch7 建议又要 Ch4 的 baseline ⇒ 互为输入。本实现以
   `facts/implied_requirements.jsonl`（`ch5:` 前缀）+ `facts/recommendations.jsonl`（`ch7:` 前缀）
   按 `company_id` 归并；**待裁定**这是否就是设计要的"跨章引用"口径。
5. **`Ch4 §J.4 J7` 的 AST 关键字扫描**：本单**刻意没做**（`R-06` 禁关键词规则作判据）。
   若设计确实要求，需要一份**封闭**的关键词集合与豁免清单，属另一件事。
6. **`rollup` / `state_machine` 无 CLI**：见 §2.4 的理由。若验收要求"每个守卫都有 exit 码"，
   请明确"给一个扫不到对象的空壳 CLI"与"孤儿模块"哪一边更不可接受 —— 我选了后者不做。

### 4.4 环境性缺口（**不是本单代码问题，但会影响复核**）

- ★ **宿主 safe-delete 每轮批量删除阈值**会让"一次跑完 `tests/valuelayer`"在**同一轮里跑到某个点**
  起批量失败（`SystemExit: 1`，夹具 setup 阶段）。本单的处置是**分批 ≤10 例**跑。
  复核者请勿把 `errors=32` 读成"测试坏了" —— 先用
  `--junitxml` 看 `failures`（本单为 **0**），再按 §2.6 的六条命令复核。
- `scripts/ops/verify.py::BATCHES["valuelayer"]` 的超时按 `V-02` 取上限 **300s**；
  本单实测全量 **88.5s**（合并 main 后）/ 170.2s（首次，含竞争的会话）。
  余量按 88.5s 计约 **3.4×**，但若同一工作树有第二个 pytest 会话（`V-05` 禁止的情形），
  仍可能被拖过 300s 而**假红**。见到超时的第一步是查并发会话，**不是**改断言。
