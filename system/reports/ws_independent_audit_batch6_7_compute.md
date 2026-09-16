# 批次 7 · 独立审计（第二单）：`ws/compute` 静默缺陷修复 + `I-1` 集成接线

- 审计员 `independent-auditor`（`I-1` 作者=主理人，故本单对其逐条对抗）
- 对象：`5034beb`/`e1e5bc3`（C-01/C-02/C-03/C-05 修复）、`530c3cd`（`I-1` 接线）
- 手段：只读 `git`；写入型探针**一律在副本** `tests/.audit/batch7_compute/`（已整体删除）；pytest 通道独占
  `sh system/scripts/ops/run_pytest.sh tests/injection/test_chain_steps_wiring.py tests/compute -q` → **106 passed in 6.51s**
- 基线：上轮 `reports/ws_independent_audit_compute.md`（C-01~C-05 原始反例）

---

## §0 结论摘要

| # | 条目 | 判定 | 一句话依据 |
|---|---|---|---|
| 1 | `C-01` `None` 未折叠 | **PARTIAL** | 原 4 例（含旗舰「缺汇率」）已折成 `MissingInput`，但同族 **8 处**仍裸 `TypeError`（修了实例、未修类） |
| 2 | `C-02` 幂等键缺 `version` | **PARTIAL** | 机制与测试成立；但主流程恒传 `DEFAULT_VERSION="v1"` → 上游重述静默沿用旧值**仍会发生** |
| 3 | `C-03` `produced` 语义 | **FIXED** | `step.produced = report.written_derived_ids`；复原后新测试转红（§2） |
| 4 | `C-05` 双 `None` 静默跳过 | **FIXED** | 无条件调 `require_baseline_before_compute` + 删 `or now()`；复原后新测试转红（§2） |
| 5 | `I-1` 集成接线 | **NOT-ACCEPTED** | 核心机制（`incomplete_reason`/响亮失败/复用）成立；但 **step 6 用测试夹具造出 `buy` 信号**且每日触发 `G1-02①` **FATAL**（B1）；`resume()` 静默解阻塞（B2） |
| 6 | 四核心问题 | ① 成立（有更小替代）；② **PARTIAL**（step3 归属不严）；③ 成立（已独立复现）；④ `G-26`/`G-27` 均成立 | §5 |

**FIXED 2 / PARTIAL 2 / NOT-ACCEPTED 1；`I-1` 阻断 2 条（B1 严重、B2 中）。**

---

## §1 改前 / 改后对拍（原始输出）

「改前」= 上轮已记录的输出；本单用**副本复原**重建（§2 = 可复现的改前证据）。「改后」= 今日真仓/副本实跑。

### C-01（真仓实跑，逐个 `None` 位置）

```
--- 修复覆盖（期望 ✅） ---
[修] contract.require_nonzero(None)                      -> MissingInput ✅
[修] fx.convert_amount(rate=None)【C-01 原例·缺汇率】       -> MissingInput ✅
[修] fx.compute_fx_adjusted_return(rate_begin=None)      -> MissingInput ✅
[修] margin.compute_gross_margin(revenue=None)           -> MissingInput ✅
[修] growth.compute_roiic(invested=None)                 -> MissingInput ✅
[修] core.compute_cagr(begin=None)                       -> MissingInput ✅
[修] shares.compute_eps(shares=None)                     -> MissingInput ✅
[修] valuation.compute_implied_growth_ratio(price=None)  -> MissingInput ✅
[修] valuation.compute_enterprise_value(market_cap=None) -> MissingInput ✅
--- 同族未覆盖（期望仍 ❌） ---
[未] fx.convert_amount(amount=None)                  -> TypeError: unsupported operand type(s) for *: 'NoneType' ❌
[未] margin.compute_gross_margin(gross_profit=None)  -> TypeError: unsupported operand type(s) for /: 'NoneType' ❌
[未] core.compute_yoy(current=None)                  -> TypeError: unsupported operand type(s) for -: 'NoneType' ❌
[未] core.compute_diff_ratio(numerator=None)         -> TypeError: unsupported operand type(s) for /: 'NoneType' ❌
[未] core.compute_change_ratio(end=None)             -> TypeError: unsupported operand type(s) for -: 'NoneType' ❌
[未] shares.compute_eps(net_income=None)             -> TypeError: unsupported operand type(s) for /: 'NoneType' ❌
[未] shares.compute_value_per_share(equity=None)     -> TypeError: unsupported operand type(s) for /: 'NoneType' ❌
[未] growth.compute_roiic(nopat=None)                -> TypeError: unsupported operand type(s) for /: 'NoneType' ❌
```

### C-02 / C-03 / C-05（改后 = 真仓只读核对）

```
C-02 store.existing_keys() -> set[tuple[str,str,str]]，键 = (derived_id, version, method_version)
     store.append_derived_value_ids(root, values, version=...) -> list[str]（只回真正写入）
     driver.run_derived(..., version=DEFAULT_VERSION)；DriverReport.written_derived_ids
     调用方普查 existing_keys/append_derived_values/append_derived_value_ids/current_value/history_for
       → 除 scripts/compute/ 内部与 tests/ 外 零外部消费者（无人用旧键）
C-03 step.py:52       produced=list(report.written_derived_ids)
C-05 valuation.py:119 require_baseline_before_compute(...)  # 无条件
     valuation.py:124 compute_moment = computed_at          # 已删 or datetime.now(...)
```

---

## §2 ★ 复原对照（证明新测试有判别力，非同义反复）

方法：在**副本**（非仓库文件）把修复逐条退回旧行为 → 跑该缺陷对应的新测试 → 看是否转红。副本与真仓 `diff -r` 已复核 `scripts/`、`tests/injection/` **rc=0（逐字节一致）**；先建绿地基线 `4 passed in 0.58s`。

| 缺陷 | 复原动作（副本内） | 对应新测试 | 结果 |
|---|---|---|---|
| C-01 | 删 `contract.require_nonzero` 的 `if value is None:` 分支 | `test_contract.py::test_require_nonzero_none_is_missing_not_typeerror` | **RED** |
| C-02 | `existing_keys`/写入键退回 2 元组 `(derived_id, method_version)` | `test_store.py::test_version_change_creates_new_row_not_overwrite` | **RED** |
| C-03 | `step.py` 退回 `produced=list(report.derived_ids)` | `test_step_wiring.py::test_handler_produced_empty_on_idempotent_second_run` | **RED** |
| C-05 | 恢复 `if baseline_analyzed_at is not None or computed_at is not None:` + `computed_at or now()` | `test_valuation.py::test_value_range_double_none_is_rejected_not_now_default` | **RED** |

**四条原始输出（逐字）**：

```
C-01: E  Failed: DID NOT RAISE MissingInput        tests/compute/test_contract.py:74: Failed
      1 failed in 0.09s
C-02: >  assert len(rows) == 2, "上游重述必须新增行，新旧两行同时存在"
      E  assert 1 == 2                             tests/compute/test_store.py:67: AssertionError
      1 failed in 0.40s     ← 与改前同症：重述被静默吞掉，只留 1 行旧值
C-03: >  assert second.produced == [], "幂等重跑未新增落库 → produced 必须为空"
      E  assert ['dv-benchmar...5-compute-v1'] == []
      1 failed in 0.40s     ← 与改前同症：values_written=0 却回传非空 produced
C-05: E  Failed: DID NOT RAISE MissingInput      tests/compute/test_valuation.py:112: Failed
      1 failed in 0.10s     ← 与改前同症：双 None 静默跳过，仍以 now() 兜底
```

复原后副本重回 `4 passed` ⇒ 四条新测试**确有判别力**，退回旧行为即转红。

---

## §3 `C-01` ~ `C-05` 逐条判定

| 缺陷 | 判定 | 证据与理由 |
|---|---|---|
| **C-01** | **PARTIAL** | ✅ 9 处已折成缺口类（含 AC-05 点名的「缺汇率」`fx.convert_amount(rate=None)`）；❌ 同族 **8 处**仍裸 `TypeError`（§1）。**根因未除**：修法是逐点补 `require_nonzero`/`require_present`，而非在算子入口统一过一遍具名输入——设计已有现成手段 `require_present({...}, names, subject=...)`（本批已在 `compute_cagr`/`implied_growth`/`enterprise_value` 用它），可系统性扫完全部公开算子，本批未做。故按「缺陷类」判 PARTIAL；若仅按 AC-05 字面（缺汇率）读则 FIXED。 |
| **C-02** | **PARTIAL** | ✅ 键升级为 `(derived_id, version, method_version)`、`version` 落行级列、旧行按 `DEFAULT_VERSION` 归一（不改旧行字节）、CLI 有 `--version`、正反向测试齐（§2 证判别力）；✅ 旧键消费者普查为空。❌ **主流程恒传常量**：`chain_steps.py:255 make_derived_handler(root, step_no=5)` → `step.py:50 run_derived(root_path)`（**不传 version**）→ `driver.run_derived(version=DEFAULT_VERSION="v1")`。`version` 是「上游基线版本」，只有模型侧能供，阶段②③未交付 ⇒ 主流程里 `version` 永不变化 ⇒ **上游重述 + 同 `method_version` 时新键=旧键 → 静默沿用旧值**（C-02 原始症状）在生产路径上**依然成立**；仅 CLI `--version` 显式调用可避免。 |
| **C-03** | **FIXED** | `step.produced = report.written_derived_ids`（`step.py:52`），由 `append_derived_value_ids` 回填（`driver.py:315`）＝本次真正写入；`test_handler_produced_empty_on_idempotent_second_run` 首轮/次轮双向断言，复原即红（§2）；未发现第二实现。 |
| **C-05** | **FIXED** | 无条件 `require_baseline_before_compute`（`valuation.py:119`）+ `assert computed_at is not None` + `compute_moment = computed_at`（已删 `or datetime.now(timezone.utc)`）、`timezone` 导入已清；正反双向用例齐，复原即红（§2）。 |

---

## §4 `I-1` 三项探测原始证据

### P1 真跑 `Pipeline(root).run_daily(date(2026,9,16))`（副本，rsync 自真仓、干净初态）

```
注册的步 = [1, 2, 3, 4, 5, 6]
step 1 ingest_public_information                    status=ok   produced=0
step 2 trace_dedup_verify                           status=gap  produced=0  gap=Ch6 §6.3 七步判定…属模型侧、阶段②③…
step 3 update_company_and_industry_relations        status=gap  produced=0  gap=无依赖边数据（G-03）…
step 4 revise_growth_and_moat_judgment              status=gap  produced=0  gap=Ch4 §4.1~4.3 …属模型侧…
step 5 update_financial_and_valuation_assumptions   status=gap  produced=0  gap=本步处理器已执行但**无产出**…
step 6 compare_company_vs_benchmark_expected_return status=ok   produced=1
step 7 publish_recommendations                      status=gap  produced=0
step 8 continuous_verification_and_history          status=gap  produced=0
blocked=True degraded=True signals=1 gaps=11
```
gaps 含 `G1-05 第 1 步（ingest_public_information）报 ok 但 produced 为空（空执行）`（=`G-26` 现场）。

### P2 让缺失层响亮失败（副本内两次打断）

```
打断 A：chain_steps.py 的 locator_check 导入改为不存在的名字
  step 2 trace_dedup_verify  status=failed  error=ImportError: cannot import name
        'check_DOES_NOT_EXIST' from 'scripts.validators.locator_check' (…/locator_check.py)
  blocked=True  gaps=10，其中 gap[7] = G1-05 第 2 步（trace_dedup_verify）未产出：
        status=failed，error=ImportError: cannot import name 'check_DOES_NOT_EXIST' …
  → 未静默降级为 ok；异常进 StepResult.error，经 G1-05 进 result.gaps，并置 blocked。
打断 B：chain_steps.py 的 make_derived_handler 导入改为不存在的名字
  Traceback … pipeline.py:121 __init__ → :142 _register_default_steps → chain_steps.py:245 register_chain_steps
  ImportError: cannot import name 'make_derived_handler_DOES_NOT_EXIST' from 'scripts.compute.step'
  → Pipeline(root) 构造即硬失败（对象都不存在），比 A 更响亮。
```

### P3 接线体检（真仓只读 grep）

```
register_chain_steps 调用链（主流程，非孤儿）：
  pipeline.py:121 self._register_default_steps()          ← Pipeline.__init__ 内
  pipeline.py:138 from scripts.orchestrate.chain_steps import register_chain_steps
  pipeline.py:142 register_chain_steps(self)              → P1 运行时亦证：注册=[1..6]
step 5/6 复用唯一真源（无第二实现）：
  chain_steps.py:245 from scripts.compute.step  import make_derived_handler
  chain_steps.py:246 from scripts.decision.step import make_decision_handler
  chain_steps.py:255 make_derived_handler(root, step_no=5)   ← 全仓生产者调用点仅此一处
  chain_steps.py:267 make_decision_handler(root, step_no=6)  ← 同上
  → chain_steps.py 只做包装/登记，未重新实现任何业务逻辑（G-06 通过）
```
---

## §5 `I-1` 逐条判定 + 四个核心问题

### 5.1 判定：**NOT-ACCEPTED**

受理面（成立）：`rules/pipeline.yaml` 声明的 step 1–6 全注册（`G-13` 接线面闭合）；`incomplete_reason` 使「注册≠完成」在编排器侧可观测；缺失层**响亮失败**（P2）；step 5/6 复用唯一真源（P3）；`resume()`/`assert_steps_complete` 未被改；改动面 4 文件，纪律 9/10 无违例。

**B1（严重）step 6 接线以「测试夹具」为默认输入 → 每日伪造 `buy` 信号 + 违反反 KPI。**
链条 `chain_steps.py:267 → decision/step.py:51 run_default → run_decide.py:224-234`：`DEFAULT_BENCHMARK_PRICES = tests/compute/fixtures/agix_prices.jsonl`、`DEFAULT_STOCK_PRICES = tests/decision/fixtures/demo_stock_prices.jsonl`，硬编码 `company_id="co-demo"/security_id="usDEMO"/benchmark_id="usAGIX"`，`persist=True` → **真写** `facts/recommendations.jsonl`。干净副本受控实验（起始 `recommendations.jsonl` 0 行、`derived_values.jsonl` 0 行）：

```
run#1 后 recommendations = 1 行
  step 6 status = ok produced = ['rec-usDEMO-2026-04-01']    signals_emitted = 1
run#2（同日重跑）后 recommendations = 2 行      ← 幂等则应为 1
  落库行: action=buy | security_id=usDEMO | company_id=co-demo
          evidence_version_ids=['dv-total_return-co-demo-compute-v1']
  evidence 是否存在于 derived/ = False          （derived/ 实际 0 行）
```

四条后果：① `action=buy` 由**夹具行情**推出（`§一 底线 3` 不伪造产物）；② 同日重跑**重复追加**同一
`recommendation_id`（`Ch9 §3.5` 阶段④ 幂等；`persist_recommendation` 直调 `append_records`，无幂等过滤）；
③ `evidence_version_ids` 指向 `derived/` 中**不存在**的 `DerivedValue`（溯源链断裂，上轮 `C-09` 由潜伏转现役）；
④ 项目**自己的**反 KPI 守卫在副本上 FATAL：

```
Violation(rule='G1-02①', reason='无变化日产了新信号: run_date=2026-09-16 signals_emitted=1',
          file='facts/tasks.jsonl', severity='FATAL')      ← 每日运行各产出 1 条
成因：decision/step.py:54 judgment_change={} ⇒ result.changed=False，而 signals_emitted=1
```
⇒ 真仓 `no_signal_day` 现在绿灯**只因 `facts/tasks.jsonl` 为空**（守卫自注 `NO_CHECK_RECORD_DATA…本条**不构成**"已通过反 KPI 检查"`）=**空包假绿**；接线后的流水线一旦真跑日度任务，反 KPI **每天必红**。另 `chain_steps.py:23` 把 step 6 标「✅ **真实实现**」，与它复用的 `decision/step.py:13-14`「★ 诚实标注：step 6 的完整处理器…**本批次未实现**」**自相矛盾**；以夹具为默认输入的 `run_default` 不构成「真实实现」。

**B2（中）`resume()` 与 `run_daily()` 对同一次运行给出相反判定（静默解阻塞）。**
`pipeline.py:268` 在断点续跑里**硬编码** `STATUS_OK`，不读 `incomplete_reason`，不累计 `degraded`，从不调
`assert_steps_complete`、从不置 `blocked`。同一副本、同一批 handler：

```
== run_daily ==   step 2/3/4/5 = gap   blocked=True  degraded=True  gaps=11
== resume ==      step 2/3/4/5 = ok    blocked=False degraded=False gaps=2
                  gaps = ['step 7 未注册处理器（断点续跑）', 'step 8 未注册处理器（断点续跑）']
```
改前两入口**一致**（都硬编码 ok），`I-1` 只改了 `run_daily` ⇒ **分歧由本批引入**。`resume` 是已声明接口
（`skills/aichain-daily/SKILL.md:26`），全仓**零调用方、零测试** ⇒ 当前不可达，记为缺口而非 FAIL。

次要项（不阻断）：`verify.py:113` 把 `guards` 批描述由「20 守卫」改为「**23 门禁**」，而 `tests/guards`
矩阵 `GUARDS` 实测 **20** 条且自带 `assert len(GUARDS) == 20`（23 是 `run_all_gates.GATES` 的数，属另一批）；
同文件 docstring 另有 18/19 ⇒ 同一数字四种写法，改后那行**由对改错**（§7 G-35）。

### 5.2 四核心问题

**① `StepOutcome.incomplete_reason` 多余还是必要？——必要，但存在更小的替代方案。**
必要那半成立：改前 `run_daily` 对**所有** outcome 一律记 `STATUS_OK`，`StepOutcome` **无任何**「本步未完成」的表达力；「注册一个什么都不做的处理器」只能被 `assert_steps_complete` 的「报 ok 但 produced 为空」兜住，而那条记录**语义是错的**（本步并没有 ok）——`G1-05` 本意是**不变量兜底**，不是**主判据**；A 方案要求「显式、不静默」，处理器必须能自述「我没做完，原因是 X」。
**但**有更小的等价物且我实测可用：`degraded=True` 已存在，语义接近（「缺口是正常态，但显式标记」）。若把 `run_daily` 改为 `status = STATUS_GAP if (outcome.incomplete_reason or (not outcome.produced and outcome.degraded)) else STATUS_OK`，不新增字段也能让 step 2/3/4/5 记 gap。**代价**：`degraded` 语义被 overload（「有缺口」≠「本步未完成」，如 step 5 可能部分产出+缺口），且**丢失原因文案**（无法反查 `T-08`）。故判断：**新增字段是合理选择，但不是唯一选择**；主理人「只能靠 G1-05 兜住」的论证成立，若补一句「为何不用 `degraded` 派生」更完整。这是「论证不够充分」，不是「多余扩展」。

**② step 2/3/4 的模块归属是否「张冠李戴」？——step 2 成立；step 3 判 PARTIAL；step 4 成立。**
设计核对：`01_产品目标与核心闭环/01_需求拆解.md §2.2` = step 2 追源去重与核验/`Ch6 §6.3`；step 3 更新公司及产业关系/`Ch7 §7.1`；step 4 修订增长和护城河判断/`Ch4 §4.1~4.3`。
- **step 2 成立**：`06_公开信息与证据筛选/02_实现方案.md §D.1`（`:278`）七步 = ①保存出处 ②拆主张 ③追踪去重 ④质量判断 ⑤研究增量 ⑥核验 ⑦状态标注 —— **确无「定位」步**；但 `full_text_read` 定位校验器（`N6.1-11`）由 `00_交付施工图.md:159` 指派给 **`Ch6 §D`**，与 step 2 同章同节族，且 `chain_steps.py` **明写**「已实现=定位机械复查／未实现=七步判定」，未把「定位」冒充七步 ⇒ 属**支撑机制替代**，可接受。
- **step 3 PARTIAL（不严）**：`07_产业链传导与股票建议/01_需求拆解.md:12 §1.1 N7.1-01~`（即 `§7.1`）正文是**关系数据模型**（九类关系、`flow_kind`、两端对象、合作阶段、有效期），而 `graph_integrity_guard` 检查 `facts/dependency_edges.jsonl` 的**图结构**（自环/重复边/悬空端点/陈旧缓存），其规则表锚 `Ch9 §3.4.3`+`Ch7 §C.3`，**不是 `§7.1`**。两处失据：把 `§7.1` 的关系数据模型说成由图完整性承担；`produced=edge_ids` **不是本步声明的产物**（`relations`/`business_positions`/`impacts`）。诚实处：docstring 明说关系抽取未交付，且无边时主动加「无被检对象 ≠ 已验证（`G-03`）」。另 `graph_integrity_guard.py:2` 自称依据 `Ch2 §B.3`，而 `Ch2 §B.3`（`02_已确认的投资规则/02_实现方案.md:65`）是 Checker-1~5（AST+禁词/schema 字段/决策门/配置扫描/展示层中性）——**无依赖图检查器**；`chain_steps.py:114,136` 把错锚点抄了两遍（§7 G-34）。**裁定：不判 FAIL，但归属需改写。**
- **step 4 成立**：「无可算的确定性部分 → `produced` 恒空 + 显式原因」取向正确；`Ch4 §4.1~4.3` 的产物 `baselines` 本身是模型侧产出，`growth.assess_growth_quality` 以 baseline 为输入 ⇒ 无输入可算，论证成立。

**③ 新测试的判别力——独立复现成功，断言确会转红。**
副本内把 step 2/3/4 注册换成 `lambda d,s: StepOutcome()`（默认 `produced=[]`、`incomplete_reason=None`）：
```
FAILED …::test_model_side_steps_are_recorded_as_gap_not_ok[2-trace_dedup_verify]
FAILED …::test_model_side_steps_are_recorded_as_gap_not_ok[3-update_company_and_industry]
FAILED …::test_model_side_steps_are_recorded_as_gap_not_ok[4-revise_growth]
FAILED …::test_run_daily_records_gaps_and_blocks_on_incomplete_steps
FAILED …::test_no_step_claims_ok_without_output
  E  AssertionError: 以下步报 ok 但 produced 为空（空执行）：
     [(2,'trace_dedup_verify'),(3,'update_company_and_industry_relations'),(4,'revise_growth_and_moat_judgment')]
5 failed, 6 passed in 1.73s
```
⇒ 11 条中 **5 条**承担判别力（另 6 条在假处理器下仍绿：适配器 3 条是单元级、`test_incomplete_reason_defaults_to_none` 是契约，`test_default_pipeline_registers_steps_1_to_6` 与 `test_step_4_has_no_output` 只验单一面向 ⇒ **单独看无判别力**）。断言口径 = 编排器**对外结果**（`status`/`gaps`/`blocked`），非「函数被调用」，符合 `G-02`。
**一处钝角**：`test_no_step_claims_ok_without_output` 只查「`ok` ⇒ `produced` 非空」，故把**真源里已存在的 id** 当产出回传的 step 2/3 仍被判合规（§6-③）。

**④ `G-26`/`G-27` 是否成立、严重度是否合理、改词是否算「改词过关」——两者均成立。**
- **`G-26` 成立**（P1 现场：`step 1 … ok produced=0` + G1-05 空执行告警）。语义边界真实：「`raw/` 为空 ⇒ 当日无可采集输入」是**合法完成**，与「处理器是假的」不同类。严重度「中」合理：目前只制造**噪声型**告警，不掩盖真缺陷；但会让 `blocked` 长期为真时真正的空执行更易被忽略（告警疲劳）。处置选项（step 1 加「本日无输入」显式声明／给 G1-05「空执行」判据加白名单）都涉及批次 5 已验收组件与守卫语义 ⇒ 登记待裁定**正确**（`R-04`）。
- **`G-27` 成立且已实测证实**（副本内植入探针后跑 `no_placeholder_guard.py <copy>/system --fail-on warn`）：
```
# AUDIT-PROBE 注释区：…未实现（应被抹白 → 不命中）              ← 注释：未命中 ✅
    """AUDIT-PROBE docstring：本步未实现（应被抹白 → 不命中）。"""   ← docstring：未命中 ✅
    return "本步未实现（普通字符串字面量 → 期望命中）"                ← 字符串：命中 ❌
  [FATAL] PLACEHOLDER-CN @ scripts/orchestrate/chain_steps.py:59 — 中文占位标记（待实现/待补/占位/未实现）
  RESULT: FAIL（1 violations）
```
  即 `strip_comments_and_docstrings`（`no_placeholder_guard.py:251-277`）**抹注释+docstring、保留字符串** ⇒ `chain_steps.py:46-47` 的描述**属实**（我起初误疑其描述有误，实测后撤回）。`R-06 ①④` 冲突真实：关键词判据 + `--fail-on warn` 硬门禁 ⇒ 运行时缺口文案不许直白写「未实现」，逼向委婉语。**严重度「中」合理**：该规则**保护对象**（真占位/假数据）仍有效（`FAKE_DATA`/`DEMO_TALK`/`HARDCODED_FALLBACK` 同样依赖字符串），只是对运行时文案产生副作用。建议按 `R-06 ⑤` 走**白名单**（`EXEMPT_PATTERNS` 或「`incomplete_reason=` 实参内豁免」），优于降为 lint（会真丢掉「真占位」拦截力）。
- **不算「改词过关」，但成本要记账**：① **事实未变**——文案仍明写「属阶段②③，本批次未交付」，信息量不减，`incomplete_reason` 仍被记为 `gap`+`blocked`，未把任何未完成洗成完成；② **门禁未放松**（未加 `--fail-on` 例外、未动 `rules/`、未改守卫）；③ **代价被写进代码与缺口**（`chain_steps.py:43-53` 就地注明 + `G-27` 登记 + `R-04` 不自裁）。对照禁忌「改词掩盖真缺陷」：此处改的是**措辞**、记的是**同一事实**。**但**要正视二阶代价：本模块后续**真的**出现占位符时也只会被写成委婉语，该门禁在此文件的拦截力已被其自身过宽的关键词**实质削弱**——此点应写进 `G-27` 裁定材料。

---

## §6 是否引入新缺陷 / 破坏既有语义（逐项；全部已查）

| # | 检查项 | 结论 |
|---|---|---|
| ① | 新行级列 `version` 改变**读旧行**行为？ | **否**。`existing_keys` 用 `row.get("version", DEFAULT_VERSION)` 归一；`read_rows`/`history_for` 原样返回旧行。三提交 `--name-only` 中 **无** `facts/`、`derived/` ⇒ 旧行逐字节不变（追加式不可破） |
| ② | 有人用**旧键** `(derived_id, method_version)` 查询而静默漏读？ | **无**。五函数调用方普查：仅 `scripts/compute/` 内部 + `tests/`，零外部消费者。**残余**：`current_value(...)` **无 `version` 选择器** ⇒「当前值」只能按追加顺序决定，同一 `derived_id` 在 v1/v2 交错写入时不可表达（§7 G-36，低） |
| ③ | step 2/3 的 `produced` 是否「本次真正产出」？ | **否（新缺陷，潜伏）**。副本预置 2 条已存在依赖边后连调 step 3 两次：`produced=['e1','e2']` **两次相同**、文件行数恒为 2 ⇒ `produced` = **真源里已存在的对象**，而定义是「本次产出的对象引用」（`pipeline.py:90`）；step 2 同理（`produced=claims`=读到的全部既有 `claim_id`）。**与 `C-03` 同类**。潜伏性：两 handler **恒设** `incomplete_reason` ⇒ 恒记 `gap`，当前不会伪造出 `ok`（§7 G-33） |
| ④ | `G1-05` 是否被击穿（「什么都没做」能报 ok）？ | step 2–5 不能（恒 gap）；**step 6 可以**——`ok` + `produced=1`，而该产出是夹具推出的信号（B1）。step 1 报 `ok`+空 produced 但被 G1-05 拦住并记 gap（`G-26`） |
| ⑤ | 空包假绿（`G-03`） | **两处**：`no_signal_day` 在 `facts/tasks.jsonl` 为空时早退（自带 `NO_CHECK_RECORD_DATA` note，属诚实）；`graph_integrity_guard` 对「存在但为空」的边表 → `exit 0` + `NO_EDGE_DATA` note（`:24`）——但 `chain_steps.make_relation_handler` **主动补了**「无被检对象 ≠ 已验证（G-03）」⇒ 接线层处置正确 |
| ⑥ | 静默兜底 `except X: return default` | 未发现。`pipeline.py:189` 是 `except Exception → StepResult(STATUS_FAILED, error=…)` + `blocked`（**不是**静默默认值）；`chain_steps.py` 无 try/except；`run_decide.py:228` 的 `inputs_unavailable → degraded` 是显式降级且带 gap 名 |
| ⑦ | `append_only` / `derived/` 不可变 | 三提交均无 `facts/`/`derived/` 文件（`--name-only` 过滤为空） |
| ⑧ | 占位符（含**注释与 docstring 内部**） | 副本植入探针实测：注释/docstring 里的「未实现」不命中、字符串命中（§5 ④）。真仓 `chain_steps.py` 运行时文案已用设计词汇 ⇒ 真实占位**未发现**；未发现「假数据返回/mock/`except: pass`」类 |
| ⑨ | 纪律 9/10：是否有人改 `rules/**`、设计区、`conftest.py`、`CONVENTIONS.md`、守卫 | **无**。`530c3cd` 4 文件（`verify.py` 文本 1 行／`chain_steps.py` 新增／`pipeline.py`／`test_chain_steps_wiring.py` 新增）；`5034beb` 17 文件（9×`scripts/compute/*` + 6×`tests/compute/*` + 2 报告）；`e1e5bc3` 仅报告。`rules/**` 现 `-r--r--r--`（0444）✅。`scripts/checks/**` 未动 ⇒ `G-28`「契约矩阵未覆盖新增 3 守卫」在本批**未被修**（如实 OPEN） |
| ⑩ | `pipeline.py` 改动是否破坏既有语义（`resume()`/`assert_steps_complete`/`G1-02`） | `resume()`、`assert_steps_complete` **函数体未改**（`git show 530c3cd -- pipeline.py` 仅动 `StepOutcome`、`_register_default_steps`、outcome→StepResult 映射）⇒ **B2 分歧是本批副作用**。`G1-02` 分支未改；`blocked=True` 时跳过 publish/verify hook 与改前**行为等价**（改前 step 2–6 未注册也全 gap）。**新引入的是 `signals_emitted=1`（B1）** |
| ⑪ | 自我报告宽松（对照作者 `ws_compute_silent_defects_report.md`） | 抽查一致：`95 passed`（我实测 compute+injection=106，injection 11 ⇒ compute 95 ✅）；C-03 二次 `produced==[]` ✅；C-05 双 None → `MissingInput` ✅；`P2-2` `roiic<wacc→low` ✅（`growth.py:101,129`）；`P2-1` 理由 ✅（`rules/freeze.yaml` 实测**恰 11 项** p01–p11、**无** `cash_conversion`、文件 0444 + 头注「全 11 项只做基准/范围/口径/披露，**不进决策函数**」⇒ 加参数既越权又违纪律 1）；`P2-4` ✅（`ValuationRange` 仅出现于 `valuation.py`/tests/报告 ⇒ **从未落库**，根因是冻结 `schema/models.py::DerivedValue` 无 `inputs` 字段，跨阶段契约）。**DoD 改动不是放松**：删 `NumericClaim` 子项有据（`Ch9 §3.4.5` 的 `NumericClaim` 含 `raw_text`/`locator` ⇒ 属**证据层**非计算层返回值，且更正**写进 DoD** 而非静默删除）；`D5` 幂等键由 2 元组改 3 元组属**收紧**。`e1e5bc3` 是补 pre-commit 合规解除证据（仅 `chmod`、`git status` 空、未用 `--no-verify`）——诚实披露。**未见自我报告宽松** |

---

## §7 缺口清单（建议并入 `reports/phase1_gap_register.md`；`G-01`~`G-30` 已占用，故从 `G-31` 起）

| # | 缺口 | 设计锚点 | 严重度 | 建议 |
|---|---|---|---|---|
| **G-31** | **`I-1` 的 step 6 接线以测试夹具为默认输入**：`chain_steps.py:267 → decision/step.py:51 run_default → run_decide.py:224-234` 取 `tests/compute/fixtures/agix_prices.jsonl` + `tests/decision/fixtures/demo_stock_prices.jsonl`，硬编码 `co-demo/usDEMO/usAGIX`，`persist=True` **真写** `facts/recommendations.jsonl`（`action=buy`）。实测：同日重跑 **1→2 行**（无幂等）；`evidence_version_ids=['dv-total_return-co-demo-compute-v1']` 在 `derived/` 中**不存在**；`no_signal_day` 报 `G1-02① FATAL` **每日必红**。另 `chain_steps.py:23` 标 step 6「✅真实实现」与其复用的 `decision/step.py:13-14`「本批次未实现」自相矛盾 | `§一 底线 3` · `Ch1 §D.3`/`§F G1-02` · `Ch9 §3.5` 阶段④ · `G-06` | **高** | `OPEN`。step 6 暂**不注册**（回到 gap）直到阶段③产出真输入；或 `run_default` 无真输入时返回 `degraded`+空 `produced`（**不得**回落夹具）；并把 `produced`/`evidence_version_ids` 与 `derived/` 对齐 |
| **G-32** | **`resume()` 不尊重 `incomplete_reason`**（`pipeline.py:268` 硬编码 `STATUS_OK`；不累计 `degraded`、不调 `assert_steps_complete`、不置 `blocked`）⇒ 同批 handler：`run_daily`=gap/blocked，`resume`=ok/未阻塞。接口已声明（`skills/aichain-daily/SKILL.md:26`）但**零调用方、零测试** | `Ch1 §E` · A 方案「不静默」 | **中** | `OPEN`。`resume` 复用同一段 outcome→`StepResult` 映射（含 `incomplete_reason` ⇒ gap + blocked），并加「两入口判定一致」回归 |
| **G-33** | **step 2/3 的 `produced` 不是「本次产出」**：`make_verify_handler` 回传真源**全部既有** `claim_id`；`make_relation_handler` 回传 `dependency_edges` **全部既有** `edge_id`（实测连调两次 `produced` 相同、文件行数不变）。与 `C-03` 同类（计算层已修，接线层重现） | `Ch9 §3.5` 阶段⑤ · `G1-05` | **中**（潜伏：恒设 `incomplete_reason` ⇒ 恒 gap，当前无假 ok） | `OPEN`。`produced` 只放**本次真正写/真正改动**的引用；纯校验类步骤不产出即应为空 + 原因 |
| **G-34** | **`graph_integrity_guard` 权威锚点写错并被抄两遍**：`graph_integrity_guard.py:2` 自称依据 `Ch2 §B.3`，而 `Ch2 §B.3` 是 Checker-1~5，**无依赖图检查器**；其规则表实际锚 `Ch9 §3.4.3`/`Ch7 §C.3`/`Ch9 §3.3.2`。`chain_steps.py:114,136` 抄了错锚点 | `Ch9 §3.4.3` · `Ch7 §C.3` · 纪律 6 | **低**（文档锚点错，行为无影响） | `OPEN`。三处改为 `Ch9 §3.4.3 + Ch7 §C.3` |
| **G-35** | **`verify.py` 批描述数字自相矛盾**：`530c3cd` 把 `guards` 批由「20 守卫」改为「**23 门禁**」，但该批跑 `tests/guards/`，其矩阵 `GUARDS` 实测 **20** 且自带 `assert len(GUARDS)==20`；23 是 `run_all_gates.GATES` 的数（另一批）。同文件 docstring 另有 18/19 ⇒ 同一事实四种数字 | `CONVENTIONS.md::G-01` · 铁律 5 | **低**（不影响执行，注册表文本失真；与 `G-28` 同源） | `OPEN`。改为「20 守卫（另有 3 项门禁未纳入本矩阵，见 `G-28`）」；彻底修法是 `GUARDS` 从 `run_all_gates.GATES` 派生（=`G-28` 修法） |
| **G-36** | `current_value(root, derived_id, *, method_version=None)` **无 `version` 选择器**：C-02 引入 `version` 后「当前值」只能按追加顺序取末行；同一 `derived_id` 在 v1/v2 交错写入时无法表达「v2 的当前值」 | `Ch9 §3.5` 阶段④ · `Ch9 §3.4.2` | **低** | `OPEN`（消费方目前仅测试；真源为空） |

---

## §8 未能证伪的项（UNKNOWN，理由）

| # | 项 | 为何 UNKNOWN |
|---|---|---|
| U-1 | 报告 §2.4 的 `--version v1→v2→同 v2` 三段 CLI 数字；AC-01 的「`run_derived.py` EXIT=0／`values_written: 3`／`written_derived_ids` 恰 3 个」 | 我走 **store 层 + 测试层**（键机制、正反向用例、§2 复原对照均成立），**未**跑 CLI（会写 `derived/` 真源，触犯「不污染真源」）。机制可信，数字未独立复现 |
| U-2 | `P2-1`（`growth` 现金流转化率 `0.8` 硬编码）在阶段②③的正确修法 | 只核到「本批不可修」理由成立（`freeze.yaml` 11 项 + 0444 + 纪律 1）；正解需需求方定参数 |
| U-3 | `P2-4`（`share_count`/`compute_date` 未落库）的正解 | 只核到「确未落库」与「根因是冻结 `DerivedValue` 无 `inputs` 字段」（跨阶段契约变更） |
| U-4 | `G-26` 的正确裁定（step 1 加显式声明 vs 放宽 G1-05 判据） | 属需求方/守卫语义裁定，`R-04` 不自裁 |
| U-5 | `resume()`（B2）在**真实断点续跑场景**下的破坏力 | 全仓零调用方 ⇒ 无法在真实场景证伪；只证了「两入口判定相反」这一事实 |
| U-6 | `no_placeholder_guard` 除 `PLACEHOLDER-CN` 外是否还有其它过宽关键词 | 只实测了 `PLACEHOLDER-CN`（字符串命中、注释/docstring 不命中）；`FAKE_DATA`/`DEMO_TALK`/`HARDCODED_FALLBACK` 未逐条实测 ⇒ **不写 PASS** |

> 全文未把任何未取证项写成 PASS；U-1~U-6 不参与 §0 判定。

---

## §9 审计过程自述

- **只读纪律**：全部 `git` 操作为 `show/--stat/--name-only`；**零写命令**（无 add/commit/branch/checkout/stash/merge/worktree）。
- **写入位置**：仅 `system/tests/.audit/batch7_compute/`（点号前缀，被 `conftest` 的 `_ignore`/`_COPY_SKIP` 跳过、不进仓库扫描）；收尾**整体删除**；未触碰同级的 `batch7_claim_decision/`。
- **真源零污染**：探针全在 rsync 副本内跑；副本与真仓 `diff -r` 复核 `scripts/`、`tests/injection/` **rc=0**，复原全部还原（含撤掉探针函数）；`git status --short` 现状仅两份审计报告未跟踪，`facts/`/`derived/`/`rules/` 无改动。
- **pytest 通道**：独占 `run_pytest.sh tests/injection/test_chain_steps_wiring.py tests/compute -q` → `106 passed in 6.51s`（<60s，无超时）；未跑全量（`V-01`）。副本内因无 `.git`（`run_pytest.sh` 的 `git rev-parse --show-toplevel` 会解析到真仓），改用 venv python 直调。**每命令超时 ≤60s**，无超时事件。
- **失误与更正（如实记录）**：① 首轮 C-01 矩阵有两条是**我自己传错签名**（`missing N required arguments`），未计为缺陷，取真实签名后重跑（§1 为准）；② 用 Bash `grep --include` 查 `no_placeholder_guard` 抹白实现时**两次空结果**（zsh/BSD grep 的 `--include` 与 `\|` 交替问题），一度误判「无 tokenize 抹白」，改用 Grep 工具后**撤回**并以副本探针实测确证（§5 ④）；③ 探针函数一度覆盖 `_claim_ids` 的 `def` 行，已即时补回并 `diff -q` 复核。
- **未做**：未联系其他成员（按本单约束只回报 team-lead）；未改动任何仓库文件；未对 `rules/**` 解只读。**对 `I-1` 的态度**：机制（显式未完成／响亮失败／唯一真源复用）**方向正确、工程质量高**；`resume` 与 `verify.py` 是「只改了一半」的副作用。判 NOT-ACCEPTED 的**唯一硬理由**是 B1（step 6 以夹具产信号并触发自身反 KPI 门禁）；修掉（或暂缓注册 step 6）后可转「受理（附 B2 待修）」。
