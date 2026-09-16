# 修复报告 · `ws/decision` —— §九 阻断级 `P7-1` 及 `P7-2`~`P7-6` 根因修复

- **工作树**：`/Users/gaza/Developer/InvestSigh/.worktrees/fix-decision-production-inputs`
- **分支**：`fix/decision-production-inputs`（基点 `main = d03418a`）
- **提交**：`09ab08f`（本报告为随后一次提交）
- **范围**：`system/scripts/decision/**` · `system/tests/decision/**` · `system/reports/ws_decision_*.md`
- **依据**：`system/reports/ws_independent_audit_claim_decision.md §0-B / §4-P3 / §5-11 / §6`（`P7-1`~`P7-6`）
- **未动**：`scripts/orchestrate/**`（含 `chain_steps.py` 适配器，**归主理人**）· `scripts/ops/**` · `scripts/checks/**` · `schema/**` · `rules/**` · 设计区 · `CONVENTIONS.md`

---

## ① 做了什么（文件 + 位置 + 改动要点）

| # | 文件 | 改动要点（根因，非补丁） |
|---|---|---|
| `P7-2` | `scripts/decision/run_decide.py` | **删除**模块级硬编码夹具默认输入 `DEFAULT_BENCHMARK_PRICES` / `DEFAULT_STOCK_PRICES`（原 `:53-54`）。新增 `_load_truth_series`（读**真源** `<root>/facts/prices.jsonl`，复用 `scripts.compute.driver.load_price_points` 唯一解析路径，`G-06`）、`_load_primary_benchmark`（`facts/benchmarks.jsonl` 回落 `rules/benchmark.yaml`）、`_resolve_benchmark_security` / `_select_company_security` / `_as_of` / `_company_id` / `_benchmark_id`。`run_default(root, *, run_date, scope, prices_file, ...)` **真读 `root`**；`run(...)` 保留 `stock_prices_path` / `benchmark_prices_path` 作**显式注入**通道（测试夹具只由调用方显式传）。抽出 `_run_core`（已解析行情序列）供两条通道共用。 |
| `P7-3` | `scripts/decision/step.py` | `handler(run_date, scope)` **真实使用**二者：`run_date` 传 `run_default` 作 **as-of 上界**（只取 `day ≤ run_date` 的点）；`scope` 作**目标证券选取**。`handler.__doc__` 写清"输入窗口由真源行情 + run_date 决定"，不再用夹具窗口冒充。 |
| `P7-4` | `scripts/decision/rules.py::persist_recommendation` | 追加前**查幂等键** `(security_id, start_date, review_date, rule_version)`（= `Ch9 §3.5` 阶段⑤ `(security_id, issued_at, version)` 的**现有字段表达**）；命中 → **返回 0，不追加**。新增行填 `version = 同业务键 (security_id, start_date) 行数 + 1` 与 `recorded_seq = version`，使 `schema.store.as_of` 版本链对 `recommendations` 可用。**未新增冻结字段**（`version` / `recorded_seq` 均已在 `Recommendation` / `TimeMixin`）。 |
| `P7-5` | `scripts/decision/gate.py::assert_early_judgment_complete` | docstring 逐字引用 `Ch7 §D.7(:418)` 原文，**升级登记为"生产不可满足，需设计侧裁定"**（详见 ②-P7-5）。断言本体保留判别力（**不删、不恒真**）。 |
| `P7-6` | `scripts/decision/run_decide.py::main` | 无 `--stock-prices/--benchmark-prices` 时走**真源模式** `run_default`；真源缺输入 → 打印**可读** `[INPUT-ERROR] … inputs_unavailable:…` + `exit 2`（语义同 `scripts/_common.run_checker`：`0` 放行 / `1` 阻断 / `2` 输入异常）。`_run_core` 落库前 `mkdir facts/`，消除"无 `facts/` → `FileNotFoundError` 抛栈"。 |
| 测试 | `tests/decision/test_persistence.py` | **改掉弱断言**：旧 `test_persist_is_append_only`（不同 id / 同窗口 → 期望 2 行）→ 新 `test_persist_same_window_rerun_does_not_append`（同窗口重跑 → **不新增**，`== 0`）+ 反向对照 `test_persist_different_window_appends_new_row`（**不同窗口 → 应新增**）；新增 `test_version_chain_is_usable_via_as_of`。 |
| 测试 | `tests/decision/test_run_decide_cli.py` | 新增 `test_run_default_on_empty_root_produces_nothing`（★`P7-1` 单测）、`test_run_default_reads_truth_source_and_emits_buy`、`test_run_default_depends_on_root`（`P7-2`）、`test_run_default_run_date_bounds_window_and_scope_selects_security`（`P7-3`）、`test_cli_rerun_same_window_does_not_duplicate`（`P7-4`）、`test_cli_truth_mode_exits_2_on_empty_root`（`P7-6`）、`test_cli_truth_mode_emits_buy_from_truth`。 |
| 文档 | `reports/ws_decision_dod.md` | AC-01/AC-02/AC-03 更新；`P7-5` 由"条件化"升级为"生产不可满足，需设计侧裁定"；登记 `P7-1`~`P7-6` 修复。 |

---

## ② 怎么验证的（原样命令 + 原样输出 + 退出码）

> 全部在 `/tmp` **副本**上做；真仓库 `facts/` 全程零改动。Python = `/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`。

### ★ `P7-1` 空仓库验收（最重要）

**副本构造**：真仓库态等价 root = 18 个 JSONL 全 0 行 + `rules/`（10 个 yaml，内容同真仓库）。探针 `/tmp/probe_p71.py`（`Pipeline(root).run_daily(date(2026,9,16), scope="full")`）。

```
BEFORE  recommendations=0  benchmarks=0
  step 1 ingest_public_information                          status=ok       produced=[]
  step 2 trace_dedup_verify                                 status=gap      produced=[]
  step 3 update_company_and_industry_relations              status=gap      produced=[]
  step 4 revise_growth_and_moat_judgment                    status=gap      produced=[]
  step 5 update_financial_and_valuation_assumptions         status=gap      produced=[]
  step 6 compare_company_vs_benchmark_expected_return       status=gap      produced=[]
  step 7 publish_recommendations                            status=gap      produced=[]
  step 8 continuous_verification_and_history                status=gap      produced=[]
blocked=True  degraded=True  signals_emitted=0
AFTER   recommendations=0  benchmarks=0
STEP6_PRODUCED_IS_EMPTY = True
STEP6_STATUS = gap
STEP6_GAP_HEAD = 本步处理器已执行但**无产出**（step 6 compare_company_vs_benchmark_expected_return）：决策层（`scripts/decisio…
RECS_ROWS = 0
BENCH_ROWS = 0
P7-1_ACCEPT = True
PROBE_EXIT=0
```

**对照（审计原测）**：`step 6 … status=ok produced=['rec-usDEMO-2026-04-01']`、`signals_emitted=1`、`facts/recommendations.jsonl 1 行`。
**修复后**：`status=gap`、`produced=[]`、`signals_emitted=0`、两表**零新增行**。→ **满足 `produced == []`、`degraded == True`、`recommendations`/`benchmarks` 零新增行。**

真仓库 `facts/` 前后对比：

```
=== 真源 facts/ wc BEFORE ===   （… 44 total，recommendations/benchmarks 各 0）
=== 真源 facts/ wc AFTER  ===
      0 system/facts/recommendations.jsonl
      0 system/facts/benchmarks.jsonl
```

### `P7-2` —— 生产路径不再读测试夹具；`run_default` 真用 `root`

```
$ grep -rnE "tests/|fixtures|DEFAULT_STOCK_PRICES|DEFAULT_BENCHMARK_PRICES" system/scripts/decision/
run_decide.py:19:  `system/tests/**`。脚本**不再**在模块级硬编码任何仓库内夹具路径。     ← docstring
run_decide.py:63:# ── 真源相对路径（… **不**含任何 `tests/**` 路径）──                    ← 注释
gate.py:252:        （由 `tests/decision/test_gate.py::…_is_conditional`                   ← docstring 引用用例名
$ grep -rnE "\"[^\"]*tests[^\"]*\"" system/scripts/decision/*.py
(字符串字面量中无 tests 路径 —— 生产代码零引用)
```

**同一函数传不同 `root` → 不同结果**（`run_default`，原样输出）：

```
empty root  -> RunReport(recommendation_ids=(), gaps=('inputs_unavailable:facts/prices.jsonl',), signals_emitted=0, degraded=True, action=None, window=None)
truth root  -> RunReport(recommendation_ids=(), gaps=('already_persisted:rec-usDEMO-2026-04-01',), signals_emitted=0, degraded=False, action='buy', window=('2026-04-01', '2026-09-15'))
```

### `P7-3` —— 取舍与 `run_date` 语义

**选择**：`run_date` = **as-of 上界**（`Ch9 §3.4.1` 双时间轴：只取 `valid_time.day ≤ run_date` 的行情点），`scope` = **目标证券选取**。
**依据**：`Ch7 §F` 端到端时序以**行情点序列**为输入；`Ch9 §2.2/§3.4.1` 规定 system_time 的 as-of 语义 —— 用 `run_date` 作系统时间上界，避免"用未来数据"（双时间轴的直接落地）。**不**采用"窗口与 `run_date` 无关、仅记录"的弱路径，因为那无法满足"`run_date` 传什么都得到同一条建议"的判别要求。

**证据（原样输出，不同 `run_date` → 不同窗口 / 无产出）**：

```
truth+run_date=2026-06-01 -> RunReport(recommendation_ids=('rec-usDEMO-2026-04-01',), gaps=(), signals_emitted=1, degraded=False, action='buy', window=('2026-04-01', '2026-06-01'))
truth+run_date=2026-01-01 -> RunReport(recommendation_ids=(), gaps=('inputs_unavailable:insufficient_prices',), signals_emitted=0, degraded=True, action=None, window=None)
```

（`run_date` 落在窗口中部 → `finish=run_date`；`run_date` 早于首日 → 无可用窗口 → **无产出**。）

### `P7-4` —— 幂等键 + `version`/`recorded_seq` + 依赖方排查

**幂等键方案**：`(security_id, start_date, review_date, rule_version)`。
**对齐口径**：设计 `Ch9 §3.5` 阶段⑤ 幂等键 = `(security_id, issued_at, version)`。映射（**全落 `schema/models.py` 现有字段，零新增冻结字段**，`R-04`）：`security_id`↔`security_id`；`issued_at`↔判断输入窗口 `[start_date, review_date]`（`Ch2 §D.2`）；`version`↔规则版本 `rule_version`（`Ch7 §E`）。与 `compute` 侧 `(derived_id, version, method_version)` 的复合键思路一致。
**版本链**：新增行 `version = 同 (security_id,start_date) 行数 + 1`，`recorded_seq = version` → `as_of(rows, ["security_id","start_date"])` 取最新版本。

**依赖方排查**（谁按旧方式读 `recommendations`）：

```
$ grep -rn "recommendations" system/scripts/ | grep -v scripts/decision
trace/traceback.py:95,146        # 按 recommendation_id / evidence_version_ids / company_id / supersedes 读（不假设 version/行数）
graph/adjacency.py:48            # recommendation_id 映射
graph/propagate.py:31,78         # RECHECK_STEM_TYPES / recommendation_id
checks/no_signal_day.py          # 按 start_date / change_reason 读
compute/step.py:7                # 仅 docstring
```
→ **无依赖方**假设"一行一 id"或"无 `version`/`recorded_seq`"，故幂等化 + 填版本链**不破坏**任何既有消费方。

**同窗口重跑不新增（原样 CLI 输出）**：

```
--- CLI run #1 (真源模式, run_date=2026-09-30) ---
{"action": "buy", "degraded": false, "gaps": [], "recommendation_ids": ["rec-usDEMO-2026-04-01"], "signals_emitted": 1, "window": ["2026-04-01", "2026-09-15"]}   EXIT=0
--- CLI run #2 (同窗口重跑 → 幂等) ---
{"action": "buy", "degraded": false, "gaps": ["already_persisted:rec-usDEMO-2026-04-01"], "recommendation_ids": [], "signals_emitted": 0, "window": ["2026-04-01", "2026-09-15"]}   EXIT=0
--- facts/recommendations.jsonl 行数（应为 1）---
1
--- 落库行 ---
{"recommendation_id": "rec-usDEMO-2026-04-01", …, "recorded_seq": 1, "review_date": "2026-09-15", "rule_version": "decision-v1", …, "version": 1, …}
```

**改掉的那条弱断言（before / after）**：

```python
# [BEFORE] tests/decision/test_persistence.py::test_persist_is_append_only
for rid in ("rec-a", "rec-b"):
    … persist_recommendation(scratch, rec)
rows = read_models(scratch, "recommendations")
assert [r.recommendation_id for r in rows] == ["rec-a", "rec-b"]     # ← 把"重跑重复落库"写成期望
```

```python
# [AFTER] 新断言 + 反向对照
rec = _rec()
assert persist_recommendation(scratch, rec) == 1
assert persist_recommendation(scratch, rec) == 0        # 同窗口重跑 → 不新增行
assert [r.recommendation_id for r in read_models(scratch, "recommendations")] == ["rec-persist"]
# 反向对照：
assert persist_recommendation(scratch, _rec(recommendation_id="rec-a", start=START)) == 1
assert persist_recommendation(scratch, _rec(recommendation_id="rec-b", start=date(2026,6,1))) == 1   # 不同窗口 → 应新增
```

### `P7-5` —— 选 **(b) 生产不可满足，需设计侧裁定**

**设计原文逐字**（`07_产业链传导与股票建议/02_实现方案.md §D.7`，约 `:418`）：

```python
def assert_early_judgment_complete(rec) -> None:
    """提前判断建议：三要素任一为空 → 不出建议、记 gap。"""
    trio = {"assumptions": rec.assumptions, "evidence_gaps": rec.evidence_gaps,
            "verification_conditions": rec.verification_conditions}
    for name, val in trio.items():
        if not val:
            raise EarlyJudgmentIncomplete(name, action="记 gap（不出建议）")
    assert rec.trio_written_seq <= rec.version_seq   # 与第一章 G1-01 一致：同版本写入
```

**推理**：该断言引用 `trio_written_seq` 与 `version_seq` 两个字段；而冻结的 `schema.models.Recommendation`（`Ch9 §3.3.4` R-07）**两者皆无**（只有 `version: int` 与 `TimeMixin.recorded_seq`）。依 `CONVENTIONS.md::R-04`（设计未写的一律不新增）**不得**补造字段；而"fail-closed（缺字段即抛）"会让生产**永远出不了建议**。故：
- **保留断言本体与判别力**（对象**确暴露**该两字段时 `trio_written_seq > version_seq` → 抛 `EarlyJudgmentIncomplete`，由 `tests/decision/test_gate.py::test_early_judgment_same_version_assertion_is_conditional` 钉住，证明**非恒真**）；
- 对 `Recommendation` / `SimpleNamespace`（两字段皆缺）**生产恒 no-op** → **登记为"生产不可满足，需设计侧裁定"**（补字段 **或** 改写为结构性断言）。
`ws_decision_dod.md`「已知缺口」已由"条件化"升级为该措辞。

### `P7-6` —— 空 root CLI 行为

```
$ python system/scripts/decision/run_decide.py <空root>           # 无 --stock-prices
[INPUT-ERROR] run_decide: 真源输入缺失或不完整（inputs_unavailable:facts/prices.jsonl）；请提供 --stock-prices/--benchmark-prices 或填充 facts/prices.jsonl
EXIT=2
```
**可读**（非抛栈）+ `exit 2` = `scripts/_common.run_checker` 的"输入异常"约定（`0` 放行 / `1` 阻断 / `2` 输入异常）→ **语义一致，无例外**。

### 测试 / 门禁 / 引导

```
$ sh system/scripts/ops/run_pytest.sh tests/decision -q
93 passed in 4.62s
PYTEST_EXIT=0

$ sh system/scripts/ops/pre-commit.sh
（10 道门禁全部 RESULT: PASS）
pre-commit ✓ 全部门禁放行
PRECOMMIT_EXIT=0

$ sh system/scripts/ops/bootstrap_worktree.sh
bootstrap_worktree: 已把 10 个 rules 文件置为 0444（内容零改动）
bootstrap_worktree ✓ rules_lock_guard 通过（纪律 9 不变量已复原）
EXIT=0

$ git status --short system/rules system/registry
（空）      ← 期望为空
```

---

## ③ 结果

`P7-1`（阻断）**已闭合**：空仓库上 step 6 `produced=[]` / `status=gap` / `degraded=True` / `signals_emitted=0`，`facts/recommendations.jsonl` 与 `facts/benchmarks.jsonl` **零新增行**，真仓库 `facts/` 全程零改动。
`P7-2`/`P7-3`/`P7-4`/`P7-6` **已修**；`P7-5` **如实登记为"生产不可满足，需设计侧裁定"**（(b) 路线，保留判据、未删未恒真）。
`tests/decision`：**93 passed / exit 0**；`pre-commit.sh` 全部门禁 **PASS / exit 0**。
提交：`09ab08f`（代码 + 测试 + DoD），本报告随后一次提交。

---

## ④ 诚实登记的残留 / 不确定项

1. **`P7-5` 未闭合为"可满足"**（选 (b)）：设计要求的运行时字段断言在生产**不可满足**；结构上 `G1-01`（三要素与结论同一行、同一次写入生成）成立，但**不等于**设计写的那条断言。**需设计侧裁定**（补 `trio_written_seq`/`version_seq`，或改写为结构性断言）。未自造字段（`R-04`）。
2. **`Benchmark` 冻结模型无 `security_id`**：`Ch9 §3.3.4` 的 `Benchmark` 不含证券绑定字段，基准→行情证券的解析依赖"对象自带 `security_id`（raw）或行情仅一种证券"的回退（对齐 `compute.driver._resolve_security` 口径）。**多证券 + 无 `benchmarks` 真源**时基准证券无法确定 → 如实降级（`inputs_unavailable:securities_unresolved`）。属设计侧缺口，未自造字段。
3. **`company_id` 近似**：证券→公司映射读 `facts/securities.jsonl`（`Ch9 §2.1` 公司/证券分离）；无该真源时以**证券 id 代公司 id**（`_company_id` fallback）。当前真仓库 `securities.jsonl` 为空 → 该近似生效。已登记，未自造字段。
4. **幂等的并发窗口**（`R-04`，**不称为"原子"**）：`persist_recommendation` 是"先读全量判键、再追加"两次独立操作，`append_records` 的 `fcntl` 锁**只覆盖追加**；首版单写者约定（`Ch9 §3.10 J6`），与 `compute.store.append_derived_value_ids` **同形态**（未引入第二条锁，`G-06`）。
5. **`run_date` as-of 取舍**：我把 `run_date` 定为"窗口 end 的 as-of 上界"（`finish = min(max_day, run_date)`）—— 这是本任务允许的"数据决定窗口"合法情形，但**在同窗口内不同 run_date 会产生不同 `review_date`**（→ 属"不同窗口"→ 新增版本行）。若主理人期望"同业务窗口内 run_date 变化不产生新行"，需改幂等键（去掉 `review_date`）——**这是口径选择，已在上文写明，未擅改**。
6. **`P7-7`/`P7-9` 未动**（`step 6` 声明 `produces=[benchmarks, recommendations]` 只产 1 项；`pre-commit.sh` 收录问题）——**归主理人**，按要求不碰 `scripts/orchestrate/**` / `pre-commit.sh`。
7. **`step 5`（compute）在空 root 上仍为 `gap`** —— 属 compute 层，不在本单范围（本单只闭合 step 6 的伪造产出）。
8. **未跑全量 pytest**（`V-01`/`V-05`）：只跑相关子集 `tests/decision`。跨套件影响面经 grep 确认：仅 `tests/decision/**` 引用 `scripts.decision`（无其它套件受影响）。
9. **`stage_gate`/`verify.py`**：未跑（`verify.py::BATCHES` 属主理人集成面）。
