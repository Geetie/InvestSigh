# 交付报告 · 并行工作流 `ws/decision` —— 决策层 `scripts/decision/`

> 分支：`ws/decision`（基线 `516d644`）· 工作树：`.worktrees/ws-decision`
> 四段式（`00_开发Agent开工提示词.md §5.2`，缺一段视为未完成）。
> 设计锚点：`Ch6 §B.2/§B.3`（三维正交决策函数 + 反加权）· `Ch7 §D.1~§D.7`（5 规则 / 前置门 / `boundary_unresolved` / 关系隔离）· `§E`（建议 schema）·
> `Ch2 §B.2 P-02/P-06/P-09` · `Ch2 §C.1/§C.3` · `Ch2 §D.1/§D.2` · `Ch9 §3.3.4 / §3.4.4 / §3.4.2` · `system/CONVENTIONS.md`（`R-06` 等）。

---

## 改了什么

**新增/填充 `scripts/decision/`（决策层，唯一新增模块）**

| 文件 | 内容 | 节号锚点 |
|---|---|---|
| `scripts/decision/__init__.py`（M） | 包级 **PEP 562 惰性导入**（`_SUBMODULES` + `__getattr__`/`__dir__`），导入期不拉 pydantic | `CONVENTIONS.md P-03` |
| `scripts/decision/triage.py`（新） | 三维正交决策函数：`priority_order`（字典序）/ `research_cap`（仅重要性）/ `is_adoptable`（仅质量）+ `DecisionView`（**物理不含热度字段**）+ `view_from_record`（**allowlist**） | `Ch6 §B.2 / §B.3`；`R-06` |
| `scripts/decision/gate.py`（新） | 前置门：`research_complete` / `has_explainable_forecast` / `require_derived_worksheet`（`DerivedValue` 强制）/ `can_apply_return_comparison` / `assert_early_judgment_complete`；`RecommendationInput`（**不含 `relations`**）/ `ExplainableForecast` / `ReturnValue` / `JudgmentChange` | `Ch7 §D.2 / §D.5 / §D.7`；`Ch2 §D.1 A-06` |
| `scripts/decision/rules.py`（新） | 5 规则引擎 `decide()`（R1/R2/R3/R4/R5 + R8 + `boundary_unresolved`）+ `build_recommendation` / `persist_recommendation` + `classify_opportunity`（标注非准入）+ `assert_horizon` | `Ch7 §D.1 / §D.3 / §D.4 / §D.6 / §E`；`Ch2 §D.2` |
| `scripts/decision/step.py`（新） | 编排器**接线接缝** `make_decision_handler(root)` / `register_into(pipeline)`（签名 = `StepHandler`） | `Ch9 §3.5` 阶段④ |
| `scripts/decision/run_decide.py`（新） | **真实运行**入口：行情点 → `compute` 真算 `DerivedValue` → 门 → 5 规则 → 落 `facts/recommendations.jsonl` → 重建 `index/`；缺口对象 → 显式降级 | `Ch7 §F` 端到端时序 |

**新增测试 `system/tests/decision/`（86 用例）**

`conftest.py`（`scratch` / `cli` 夹具）· `decision_builders.py`（真 `DerivedValue` 构造器）·
`test_triage_no_weighting.py`（18）· `test_gate.py`（19）· `test_rules.py`（29）· `test_no_relation_contagion.py`（4）· `test_persistence.py`（7）· `test_package_laziness.py`（4）· `test_run_decide_cli.py`（5）。

**报告**：`system/reports/ws_decision_dod.md`（DoD，先写）· `system/reports/ws_decision_report.md`（本文件）。

**未改动的共享文件（清单）**：`rules/**`（仅 `chmod 444` 恢复只读位，内容零改动）· `system/tests/conftest.py` · `system/CONVENTIONS.md` · `system/scripts/ops/verify.py` · `system/scripts/{guard,compute,graph,validators,claim}/**` · `system/schema/**` · `system/scripts/orchestrate/pipeline.py` · 全部设计区 `00_*` / `01_`~`11_`。

---

## 测了什么（贴真实输出）

### ① 决策层测试批次（86 用例）

```
$ cd system && sh scripts/ops/run_pytest.sh tests/decision
platform darwin -- Python 3.13.12, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/gaza/Developer/InvestSigh/.worktrees/ws-decision/system
collected 86 items

tests/decision/test_gate.py ...................                          [ 22%]
tests/decision/test_no_relation_contagion.py ....                        [ 26%]
tests/decision/test_package_laziness.py ....                             [ 31%]
tests/decision/test_persistence.py .......                               [ 39%]
tests/decision/test_rules.py .............................               [ 73%]
tests/decision/test_run_decide_cli.py .....                              [ 79%]
tests/decision/test_triage_no_weighting.py ..................            [100%]

============================== 86 passed in 3.07s ==============================
$ echo $?   → 0
```

### ② `verify.py --batch guards`（**预期红**：仅 V-06）

```
✗ [guards] tests/guards/（20 守卫 × 退出码契约 + 验证规范）  exit=1  0.07s/60s  exit=1
  [FATAL] V-06 @ scripts/ops/verify.py:0 — 以下测试文件**不被任何批次覆盖**（写了却永远不被验证）:
    ['tests/decision/test_gate.py', 'tests/decision/test_no_relation_contagion.py',
     'tests/decision/test_package_laziness.py', 'tests/decision/test_persistence.py',
     'tests/decision/test_rules.py', 'tests/decision/test_run_decide_cli.py',
     'tests/decision/test_triage_no_weighting.py'] → 请在 `verify.py::BATCHES` 增加/扩展批次
3 failed, 53 passed in 4.38s
```

3 条失败**全部**指向 `verification_policy_guard` 的 `V-06`（新 `tests/decision/` 未入批）——`verify.py` 是**禁改文件**，留待主理人集成时新增批次。除此以外 **53 passed**。

### ③ `verify.py --batch gates`（**预期红**：仅 1 项）

```
════════ 退出码汇总 ════════
  conflict_scan.py                   exit=0        0.31s
  append_only_guard.py               exit=0        0.10s
  rules_lock_guard.py                exit=0        0.08s
  registry_schema_guard.py           exit=0        0.17s
  schema_sync_guard.py               exit=0        0.18s
  assert_gate_input.py               exit=0        0.08s
  freeze_guard.py                    exit=0        0.14s
  launch_guard.py                    exit=0        0.08s
  module_denylist.py                 exit=0        0.11s
  no_signal_day.py                   exit=0        0.07s
  no_placeholder_guard.py            exit=0        0.34s
  neutrality_check.py                exit=0        0.07s
  return_guard.py                    exit=0        0.08s
  anti_padding.py                    exit=0        0.12s
  gap_to_task.py                     exit=0        0.08s
  traceback.py                       exit=0        0.07s
  pipeline.py                        exit=0        0.09s
  stage_gate.py --stage prep         exit=0        0.15s
  injection_guard.py                 exit=0        0.10s
  verification_policy_guard.py       exit=1        0.08s   ← 仅 V-06
  非零计数                               1
```

### ④ **新落地的 L4 / 决策作用域**：从 "SKIPPED" 变为**真扫**（本交付的正向副作用）

```
$ python scripts/checks/assert_gate_input.py . --no-report --require-gate
== assert_gate_input.py ==
  scanned gate_files: 5
  scanned gate_objects_declared: 1
RESULT: PASS（0 violations）          exit=0
# ← 此前是 "NO_GATE_DECLARED / 无被检对象"，现门对象真的存在（DecisionView / Decision）

$ python scripts/checks/freeze_guard.py . --no-report
== freeze_guard.py ==
  scanned decision_scope_files_scanned: 13
  scanned freeze_params: 11
RESULT: PASS（0 violations）          exit=0
# ← 此前是 "DECISION_SCOPE_EMPTY / 无被检对象"，现真扫 scripts/decision/**（AST 断言：不读参数）

$ python scripts/checks/conflict_scan.py . --timing ci --no-report --require-l4
== conflict_scan.py（timing=ci）==
  scanned l1_recommendation_field_count: 31
  scanned l2_py_files: 119
  scanned l2_token_count: 12
  scanned l3_config_files: 16
  scanned l4_gate_files: 5
  scanned l4_gate_objects_declared: 1
RESULT: PASS（0 violations）          exit=0
# ← L4 此前是 "L4_SKIPPED_NO_GATE_MODULE"，现真扫并 PASS（含 --require-l4 硬门）
```

### ⑤ 其余批次**全绿**（证明本模块对既有链路无回归）

```
✓ [unit]        exit=0  2.48s/60s      ✓ [compute]    exit=0  4.88s/60s
✓ [conflict]    exit=0  0.42s/30s      ✓ [graph]      exit=0  4.00s/60s
✓ [injection]   exit=0 36.06s/120s     ✓ [validators] exit=0  5.06s/30s
✓ [root]        exit=0  0.28s/30s      ✓ [claim]      exit=0  4.21s/30s
```

### ⑥ AC-01 真实 CLI（**真命令行的原样 stdout + 退出码**）

```
$ python scripts/decision/run_decide.py <root> \
    --stock-prices tests/decision/fixtures/demo_stock_prices.jsonl \
    --benchmark-prices tests/compute/fixtures/agix_prices.jsonl
{"action": "buy", "degraded": false, "gaps": [], "recommendation_ids": ["rec-usDEMO-2026-04-01"], "signals_emitted": 1}
exit=0

$ cat <root>/facts/recommendations.jsonl
{"action": "buy", "change_reason": "meets_buy_conditions", "company_id": "co-demo",
 "early_judgment": false, "evidence_version_ids": ["dv-total_return-co-demo-compute-v1"],
 "horizon": "2q", "recommendation_id": "rec-usDEMO-2026-04-01", "review_date": "2026-09-15",
 "rule_version": "decision-v1", "security_id": "usDEMO", "start_date": "2026-04-01", "status": "active", ...}

$ ls <root>/index/ → facts.sqlite（16384 bytes）
```

> `evidence_version_ids` 指向的是 `scripts.compute` **真算**出的 `DerivedValue.derived_id` —— 收益值可追到 `formula` + `operands` + `method_version`，**非包装裸数字**。

---

## 每条 AC 的证据

| AC | 判定 | 证据（文件:行 / 命令输出 / 路径） |
|---|---|---|
| **AC-01** 真跑通 | **PASS** | §⑥：CLI `exit=0` + stdout JSON `action=buy`；`facts/recommendations.jsonl` 落**真实** `Recommendation`；`index/facts.sqlite` 生成。测试 `tests/decision/test_run_decide_cli.py` |
| **AC-02** 持久化 | **PASS** | `tests/decision/test_persistence.py::test_persist_appends_and_rebuilds_index`（写 1 行 → `read_models` 回读 → `rebuild_index` 生成非空 `index/facts.sqlite`）；`::test_persist_is_append_only`（2 行） |
| **AC-03** 真接线（**PARTIAL**） | **PARTIAL** | `scripts/decision/step.py::make_decision_handler`（签名 = `StepHandler`）；真实消费方 = `run_decide.py` CLI（§⑥）+ `tests/decision/**`。**未**注册进 `pipeline.py`（禁改共享文件，属阶段③） |
| **AC-04** 守卫真拦（injected→exit 1） | **PASS** | ① `test_gate.py::test_gate_rejects_raw_number_and_decide_returns_none`（裸数字 → `RawNumberRejected` + `decide()==None`）；② L4/`freeze_guard`/`conflict_scan` 现**真扫** `scripts/decision/**`（§④）且 `--require-gate`/`--require-l4` 皆 `exit=0`；③ P-09 令牌扫描 L2 命中即 fail（0 violations） |
| **AC-05** 错误路径 | **PASS** | `test_rules.py::test_boundary_unresolved_*`（3 条）· `::test_r3_pending_when_relative_uncertain_never_sell`（**≠ 卖出**）· `::test_r8_negative_absolute_blocks_new_buy` · `::test_r4_maintain_when_judgment_unchanged` · `test_gate.py::test_gate_rejects_incomplete_baseline_and_decide_returns_none` · `::test_early_judgment_incomplete_raises[3 参数]` |
| **AC-06** 边界 | **PASS** | `test_gate.py::test_unknown_research_depth_raises` / `test_return_value_rejects_inverted_range`（`low>high`）/ `test_return_value_rejects_float` · `test_triage_no_weighting.py::test_unknown_tier_raises` / `::test_unknown_importance_raises` / `::test_naive_and_aware_timestamps_are_comparable` · `test_rules.py::test_assert_horizon_rejects_out_of_range`（`1m`/`18m`/``） |
| **AC-07** 无占位符 | **PASS** | `no_placeholder_guard.py` `exit=0`（§③）；`scripts/decision/**` 内无 `TODO/FIXME/HACK/待实现/占位/mock/fake/dummy/NotImplementedError/except: pass` |
| **AC-08** 设计对齐 | **PASS** | `triage`↔`Ch6 §B.2/§B.3`（字典序 + 字典表，`test_triage_no_weighting.py`）· `gate`↔`Ch7 §D.2/§D.5/§D.7`（`test_gate.py`）· `rules`↔`Ch7 §D.1/§D.3/§D.4/§D.6/§E`（`test_rules.py`）· `test_no_relation_contagion.py`（`§D.5` 不变性）· `test_persistence.py::test_recommendation_action_enum_is_four_values_only`（P-05） |

**两条**预期红**（非本模块缺陷，需主理人集成时处理）：**
1. `verification_policy_guard` **V-06** —— 因新增 `tests/decision/` 未入 `verify.py::BATCHES`（`verify.py` 为**禁改文件**）→ **需主理人集成时新增批次 `tests/decision/`**（命令 `sh scripts/ops/run_pytest.sh tests/decision`）。
2. `rules_lock_guard` 依赖 `rules/**` 的 `0444` 权限（git 不记录只读位）→ 已 `chmod 444 rules/*.yaml` bootstrap（§③ 中 `rules_lock_guard.py exit=0`）。

**新增批次建议（供主理人）**：`verify.py::BATCHES` 增
`"decision": Batch("decision", "tests/decision/（决策层）", _pytest("tests/decision"), 60.0, _exit_zero)` 并加进 `ORDER`。

---

## 剩余不确定性与缺口

1. **未接进主流程（AC-03 PARTIAL）**：`pipeline.py` 的 step 6 处理器属**阶段③**，本批次**不改**共享文件 → 只交付接线接缝 `step.register_into(pipeline)` 与真跑 CLI；注册动作待主理人集成。
2. **`R5` 阈值未判定**：价格"明显下跌"的**数值阈值**属实施参数（未冻结）；本层**不读参数**、只接受**已判定布尔** `price_drop_triggered` 并置 `recheck_required`，**不**自动止损/抄底（对齐 `Ch11 §E.1`）。
3. **`Ch7 §D.2` 口径对齐登记**：设计文本写 `research_baseline_done`，而 `Ch9 §N9.1-05` / `schema.models.ResearchDepth` 的**权威 token** 为 `baseline_done` → 本层**对齐 schema 权威枚举**（`>= baseline_done` 视为已完成基线研究），未自造 token。
4. **"同版本写入"断言的条件性**：`schema.models.Recommendation` 带 `version` 但**无** `trio_written_seq` → `assert_early_judgment_complete` 的"同版本"断言仅在对象暴露该字段时生效（`test_gate.py::test_early_judgment_same_version_assertion_is_conditional`）；A-06 的**三要素非空**核心拦截**不受影响**。
5. **机会类型标注的展示层消费**：`classify_opportunity` 只产出 token（`"A"`/`"B"`），**不进买入门**；其展示（`Ch8 views/**`）属阶段④，本层不涉。
6. **`scripts/graph` 消费**：`forward_closure`（T12 传播）为**下游复查**输入，本层仅在其上层提供接口位，未在本批次串起（属编排器职责）。
7. **`views/**` 渲染**：`conflict_scan` 的 L5 记 `L5_SKIPPED_NO_VIEW_CONFIG`（阶段④交付），非本模块范围。
