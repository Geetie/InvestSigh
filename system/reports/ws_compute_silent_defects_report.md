# 工程师报告 · `fix/compute-silent-defects` —— 修 `ws/compute` 四条静默缺陷

> 角色：寇豆码（Kou）· 工程师　|　分支：`fix/compute-silent-defects`（基点 `main` = `4756028`）
> 工作区：`.worktrees/fix-compute-silent-defects`　|　依据：`00_开发Agent开工提示词.md §5.2`（四段式）
> 上游：`§九` 独立审计 `system/reports/ws_independent_audit_compute.md`（not accepted：FAIL 1 / PARTIAL 2）
> 范围：只修 C-01 / C-02 / C-03 / C-05 四条静默缺陷（root cause）；P2 四项逐条判定；**不碰** `pipeline.py`（AC-03 真接线由主理人集成）。

---

## 一、做了什么（What changed）

### C-01 `None`（缺失）型数值输入被静默放过 → 裸 `TypeError`

**根因**：`contract.require_nonzero` 只判 `value == 0`；`None == 0` 为 `False` → `None` 被放行，随后算术抛裸 `TypeError`（不是缺口对象，AC-05 明列的"缺汇率"正踩此路）。

**改法（算子层折叠，非 CLI 兜底）**：

- `system/scripts/compute/contract.py::require_nonzero`（现 `:178-201`）：**先**拦 `None` → `MissingInput`（缺失），**再**拦 `0` → `UndefinedComputation`（无定义）。`None` vs `0` 语义分开（`Ch9 §3.5` 阶段④）。
- `system/scripts/compute/shares.py::_require_positive_shares`（`:21-30`）：同型缺陷（`shares is None` → `MissingInput`），一并修。
- `system/scripts/compute/core.py::compute_cagr`（`:74-86`）：三参数 `None` → `require_present` → `MissingInput`。
- `system/scripts/compute/valuation.py::compute_implied_growth_ratio`（`:157-166`）/`compute_enterprise_value`（`:196-200`）：`None` → `require_present` → `MissingInput`。

**为何在算子层而非 CLI**：`safe_compute`（`contract.py`）已把 `MissingInput`/`UndefinedComputation` 折叠为 `ComputeGap`；根因在算子守卫，故在此修；`run_derived.py` 无需补 `except TypeError`。

### C-02 幂等键缺 `version` 分量 → 上游重述静默沿用旧值

**根因**：`Ch9 §3.5` 阶段④ 幂等键逐字 = `(company_id, version, method_version)`；实现为 `(derived_id, method_version)`，而 `derived_id_for` = `dv-<kind>-<subject>-<method_version>` **不含 version** → 上游重述（同 `method_version`、新 `version`）被静默去重，`values_written=0` 且报 `OK`。

**方案（二选一）—— 选「保留 `derived_id`，把幂等键升级为复合键 `(derived_id, version, method_version)`」**：

- **理由 + 依赖方排查**：查清 `derived_id` 的**唯一外部消费方**是 `scripts/trace/traceback.py:126`（`row.get("derived_id") == conclusion_id`），为**精确字符串匹配**、**不解析格式**。故两种方案都不会破坏该消费者；但**保留 `derived_id` 格式**（不改 `dv-…` 外部稳定 id）对已落库历史行与反查链更安全，故选复合键方案，`version` 作为 `derived/` 真源的**行级列**落库（不改冻结的 `schema/models.py::DerivedValue`）。
- `system/scripts/compute/contract.py`：新增 `DEFAULT_VERSION = "v1"`（`:39-48`，含依据）。
- `system/scripts/compute/store.py`：`existing_keys` → `(derived_id, version, method_version)`；`_dump_row(value, version)` 补 `version` 列；新增 `append_derived_value_ids(...) -> list[str]`（回写实际写入 id）；`append_derived_values(...)` 降为计数视图。
- `system/scripts/compute/driver.py::run_derived`：新增 `version: str = DEFAULT_VERSION` 参数。
- `system/scripts/compute/run_derived.py`：新增 `--version` CLI 参数。

### C-03 `step.py` 的 `produced` 语义错 → 击穿编排器空执行守卫（G1-05）

**根因**：`produced=list(report.derived_ids)`（"本次重算的全部 id"），幂等重跑 `values_written=0` 时 `produced` 仍非空 → `pipeline.py` 的 `elif not step.produced` 永不触发。

**改法**：

- `system/scripts/compute/driver.py::DriverReport`：新增 `written_derived_ids`（本次**真正新增落库**的 id 集合），`values_written = len(written_derived_ids)`；`as_dict()` 相应增列。
- `system/scripts/compute/step.py::make_derived_handler`（`:48-53`）：`produced=list(report.written_derived_ids)`。
- `degraded=bool(report.gap_ids)` **未改**（该逻辑正确）。

### C-05 `valuation.py` 双 `None` 时静默跳过顺序校验 + 静默注入 `now()`

**根因**：`compute_value_per_share_range` 仅在 `baseline_analyzed_at is not None or computed_at is not None` 时才校验，双 `None` 时整个跳过，随后 `computed_at or datetime.now(timezone.utc)` 静默注入当前时间 —— 与同文件 `require_baseline_before_compute` 自身 docstring 相反。

**改法**：`system/scripts/compute/valuation.py::compute_value_per_share_range`（`:114-124`）：**无条件**调用 `require_baseline_before_compute`（`None` → `MissingInput`；倒挂 → `OrderViolation`），`compute_moment = computed_at`（**删去** `or datetime.now(...)`）；删去不再使用的 `timezone` 导入。

### P2 四项

- **P2-1 `growth.py` `cash_threshold=0.8` 硬编码** → **登记为缺口**（见第四节 4.1）。
- **P2-2 `Ch4 §D.3` 增长分档不一致** → **实现问题，已修**：`growth.assess_growth_quality`（`:97-128`）改为 `roiic < wacc` → **直接 `low`**（伪码硬规则），否则按四项负分计数。
- **P2-3 `NumericClaim` 零命中** → **DoD 表述过期，已更正**：改 `ws_compute_dod.md` AC-08 子项（见第四节 4.2）。
- **P2-4 `share_count`/`compute_date` 未落库** → **如实登记**（见第四节 4.3）。

### 测试新增/更新

- `tests/compute/test_contract.py`：`test_require_nonzero_none_is_missing_not_typeerror`。
- `tests/compute/test_operators.py`：`test_none_inputs_are_missing_not_typeerror`（6 调用点）+ `test_none_inputs_fold_to_compute_gap_via_safe_compute` + `test_none_reverse_control_valid_numbers_still_compute`；`test_growth_quality_roiic_below_wacc_forces_low`（原 `…_flag_when_roiic_below_wacc`，断言 `medium`→`low`）。
- `tests/compute/test_store.py`：`test_version_change_creates_new_row_not_overwrite` + `test_same_version_rerun_is_idempotent` + `test_append_derived_value_ids_returns_only_written`。
- `tests/compute/test_step_wiring.py`：`test_handler_produced_empty_on_idempotent_second_run`。
- `tests/compute/test_valuation.py`：`test_value_range_double_none_is_rejected_not_now_default` + `test_value_range_valid_times_compute_normally` + `test_implied_growth_none_input_is_missing_not_typeerror` + `test_enterprise_value_none_input_is_missing_not_typeerror`；3 个既有用例补显式 `baseline_analyzed_at`/`computed_at`。
- `tests/compute/test_driver_real_run.py`：`test_run_derived_version_restatement_writes_new_row`（端到端）。

**测试数**：82 → **95**（+13）。

---

## 二、怎么验证的（原样命令 + 原样输出 + 退出码）

### 2.1 本模块测试批次

```console
$ sh system/scripts/ops/run_pytest.sh tests/compute
tests/compute/test_contract.py ...........                               [ 11%]
tests/compute/test_driver_real_run.py ......                             [ 17%]
tests/compute/test_operators.py ........................                 [ 43%]
tests/compute/test_package_laziness.py ....                              [ 47%]
tests/compute/test_return_guard_wiring.py .....                          [ 52%]
tests/compute/test_returns.py ..............                             [ 67%]
tests/compute/test_step_wiring.py ....                                   [ 71%]
tests/compute/test_store.py ..........                                   [ 82%]
tests/compute/test_valuation.py .................                        [100%]
============================== 95 passed in 4.97s ==============================
EXIT=0

$ python system/scripts/ops/verify.py --batch compute
✓ [compute] tests/compute/（确定性计算层）  exit=0  5.53s/60s  exit=0
95 passed in 5.13s
```

### 2.2 AC-01 真实运行重跑（证明修改未破坏既有真实路径）

```console
$ python system/scripts/compute/run_derived.py <scratch> --prices-file system/tests/compute/fixtures/agix_prices.jsonl --start 2026-04-01 --end 2026-09-15
== run_derived.py（确定性计算层）==
{
  "derived_ids": [
    "dv-benchmark_return-p01-compute-v1",
    "dv-benchmark_return-tbd-compute-v1",
    "dv-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1"
  ],
  "gap_ids": [], "gaps_written": 0, "hard_errors": [], "integrity_violations": [],
  "values_written": 3,
  "written_derived_ids": [
    "dv-benchmark_return-p01-compute-v1",
    "dv-benchmark_return-tbd-compute-v1",
    "dv-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1"
  ]
}
RESULT: OK
EXIT=0
```

落库行（`derived_id | version | value`），真值 = 44.53/33.11−1：

```
dv-benchmark_return-p01-compute-v1 | version= v1 | value= 0.344910903050437934158864391
dv-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1 | version= v1 | value= 0.344910903050437934158864391
```

### 2.3 C-01 —— `None` → 缺口对象（原样输出）

```console
$ python - <<'EOF'   # PYTHONPATH=system，逐算子经 safe_compute
  fx.convert_amount(rate=None)                   -> ComputeGap missing=['rate（汇率）']
  fx.compute_fx_adjusted_return(rate_begin=None) -> ComputeGap missing=['rate_begin（期初汇率）']
  margin.compute_gross_margin(revenue=None)      -> ComputeGap missing=['revenue（收入）']
  growth.compute_roiic(invested=None)            -> ComputeGap missing=['incremental_invested_capital（增量投入资本）']
反向对照：fx(100*7.2) = 720.0 ; gross_margin(60/100) = 0.6
```
对照审计原文（缺陷态）：这 4 行原本 `RAISED TypeError: unsupported operand type(s)`。现全部折叠为 `ComputeGap`，**无裸 `TypeError`**。

### 2.4 C-02 —— 上游重述端到端（原样输出）

```console
# 首跑 v1
$ python system/scripts/compute/run_derived.py <scratch> --prices-file <agix> --start … --end …
  "values_written": 3, "written_derived_ids": [3 条]         EXIT=0
# 上游重述：新 version v2（method_version 不变）
$ python system/scripts/compute/run_derived.py <scratch> --prices-file <agix> --start … --end … --version v2
  "values_written": 3, "written_derived_ids": [3 条]         EXIT=0     ← 曾为 values_written=0（静默沿用旧值）
# 同 version v2 重跑
$ python system/scripts/compute/run_derived.py <scratch> --prices-file <agix> --start … --end … --version v2
  "values_written": 0, "written_derived_ids": []             EXIT=0     ← 反向对照：幂等
```
落库 6 行（v1×3 + v2×3，旧行逐字节保留）：
```
dv-benchmark_return-p01-compute-v1 | version= v1 | value= 0.3449…
dv-benchmark_return-p01-compute-v1 | version= v2 | value= 0.3449…
（… 共 6 行，v1 三行 + v2 三行同时存在）
```

### 2.5 C-03 —— step handler 两次运行（原样输出）

```console
$ python -c '… step.make_derived_handler(<scratch>) 连调两次 …'
首轮 produced = ['dv-benchmark_return-p01-compute-v1', 'dv-benchmark_return-tbd-compute-v1', 'dv-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1'] | degraded = False
二轮 produced = [] | degraded = False
落库行数 = 3 | 二轮新增 = 0
反向对照：首轮 produced == 实际落库集合 ? True
```
对照审计原文（缺陷态）：幂等第 2 次 `values_written=0` 但 `produced` 仍为 3 条。

### 2.6 C-05 —— 双 `None` 拒绝（原样输出）

```console
$ python -c '… valuation.compute_value_per_share_range(…无时间参数…)'
MissingInput: s: 顺序校验需 baseline.analyzed_at 与 compute_time（不得默认当前时间）
反向对照（两时间齐且 baseline 早于 compute）：range = {'low': '100', 'high': '120'} compute_date = 2026-09-10
```

### 2.7 P2-2 —— `Ch4 §D.3` 分档（原样输出，修复后）

```console
$ pytest tests/compute/test_operators.py -k growth_quality
test_growth_quality_roiic_below_wacc_forces_low PASSED   # roiic=0.05<wacc=0.10 → grade=low（曾=medium）
test_growth_quality_is_graded_not_single_score PASSED    # high / low 两分支
```

### 2.8 门禁（沙箱外，逐条；与本批相关的全绿）

```console
append_only_guard.py          → RESULT: PASS（0 violations）  EXIT=0
registry_schema_guard.py      → RESULT: PASS（0 violations）  EXIT=0
schema_sync_guard.py          → RESULT: PASS（0 violations）  EXIT=0
no_placeholder_guard.py system --fail-on warn → RESULT: PASS（0 violations）  EXIT=0（107 文件）
conflict_scan.py system --timing pre_commit → RESULT: PASS（0 violations）  EXIT=0
verification_policy_guard.py  → RESULT: PASS（0 violations）  EXIT=0（V-06 已解：verify.py 已有 compute 批次）
rules_lock_guard.py           → RESULT: FAIL（10 violations） EXIT=1  ← 环境（rules 0644），非本批
injection_guard.py            → EXIT=1                                ← 同因 rules 0644
```

---

## 三、结果（逐条 AC / 缺陷判定）

| 项 | 判定 | 证据 |
|---|---|---|
| **C-01** `None` → 缺口对象 | **FIXED** | §2.3：4 调用点 `ComputeGap`（无 `TypeError`）；反向对照正常算出 |
| **C-02** 幂等键含 `version` | **FIXED** | §2.4：重述（新 version）→ 新增行（旧行保留）；同 version 重跑 → 0 新增 |
| **C-03** `produced` = 真落库 id | **FIXED** | §2.5：二轮 `produced == []`；首轮 = 实际落库集合 |
| **C-05** 双 `None` 拒绝 | **FIXED** | §2.6：双 `None` → `MissingInput`；反向对照正常；倒挂仍 `OrderViolation` |
| **P2-1** `growth` 0.8 硬编码 | **登记缺口（4.1）** | `freeze.yaml` 11 项无此参数；`rules/**` 只读不可锚 |
| **P2-2** `Ch4 §D.3` 分档 | **FIXED** | §2.7：`roiic<wacc` → `low` |
| **P2-3** `NumericClaim` 零命中 | **DoD 表述已更正（4.2）** | DoD AC-08 该子项已删并说明 |
| **P2-4** `share_count`/`compute_date` 未落库 | **登记缺口（4.3）** | 见 4.3 |
| **AC-01 真实路径未破坏** | **PASS** | §2.2：`run_derived.py` `EXIT=0` + 落真实 `DerivedValue` |
| **测试** | **PASS** | 82 → 95 passed；`verify.py --batch compute` exit=0 |

**最关键一条**：C-02 / C-05 是"该响的时候没响"的最危险形态——C-02 让**上游重述被静默沿用旧值且报成功**，C-05 让**倒填约束在默认路径（不传时间）上整体失效**。二者根因均已闭合，并各带**反向对照**证明未误伤。

### C-05 的 `Ch5 §D.3` 原文依据

`05_价格与市场预期研究/02_实现方案.md:174-183`：

```
### D.3 顺序约束的程序化
def compute_valuation(baseline_version, params, *, compute_time):
    assert baseline_version.system_time.analyzed_at < compute_time, \
        "估值计算时间必须晚于 baseline 版本时间（禁止倒填）"
- 单测：baseline_version 时间晚于 compute_time → 断言 OrderViolation。
```
另 `05_.../02_实现方案.md:192`（`§D.4` 版本倒序）："baseline 版本时间晚于估值时间 → **拒绝**"。设计将 `compute_time` 定义为**必填 kwarg**、且 `§D.2` 要求 `compute_date` 为链字段 → 两时间**都必须显式**；双 `None` 不得静默跳过，故取 `MissingInput`（缺口类，非静默）。

---

## 四、诚实登记的残留 / 不确定项

### 4.1 P2-1 `growth.py` 的现金转化率阈值 `0.8` —— 登记为缺口（不修）

- 证据：`rules/freeze.yaml` 的 `freeze_params` 恰 **11 项**（p01–p11），**无**"现金转化率阈值 / cash_conversion"项；`growth.py:104` 的 `cash_threshold = Decimal("0.8")` 无真相源锚点。
- 为何不修：`rules/**` 为 **0444 只读且被禁改**（纪律 9/10）；`lock_rules.py` 是唯一授权改 `rules/` 的工具，但它同时改 `registry/rules.lock.json`（越界）。故**无法在本批**把该值锚到 `rules/` 或 `freeze.yaml`。
- 处置建议：由主理人/需求方决定该阈值是否入 `rules/freeze.yaml`（作为待冻结参数）或落 `rules/` 其他真源；在锚定前，该值属"实现内嵌经验值"。
- 附：作者 docstring 已自述其为"**分档依据而非门槛**"，且档位**不阻断**结论 → 与纪律 1"参数不进决策函数"不构成硬违例（与审计 §3 #1 一致）。

### 4.2 P2-3 `NumericClaim` —— DoD 表述过期（已更正）

- 核实：`grep -rn "NumericClaim" system/scripts/compute/` → **0 命中**；compute 内**无** `numerics`。
- 判定：**DoD 表述过期**（清单与代码脱节），**非**"违反纪律 11"——计算层真复用 `DerivedValue` / `Period`（`schema/models.py`），数值保真走 `Decimal`；`NumericClaim`（`Ch9 §3.4.5` 9 字段）是**证据/声明层**（`facts/` 中 `is_derived` 的引用型数字）模型，**不是**计算层返回值。
- 修法：已改 `system/reports/ws_compute_dod.md` AC-08 该子项（删去不实主张 + 注明职责边界）。

### 4.3 P2-4 `share_count` / `compute_date` 未落库 —— 登记为缺口

- 证据：`Ch5 §D.2`（`02_实现方案.md:162-172`）示例 `DerivedValue(value, formula, operands, method_version, inputs={…, share_count, compute_date})`，且 `§N5.3-02`（P0）"价格区间 → 公式/操作数/股本/日期可反查"。
- 现状：`valuation.ValuationRange`（本地 frozen dataclass）携带 `share_count` + `compute_date`，但 `store` 只接受 `DerivedValue` → **该 dataclass 从不落库**；冻结 schema 的 `DerivedValue` **无 `inputs` 字段**。
- **部分承载**（非零）：`compute_date` ↔ `DerivedValue.computed_at`（**已落库**，逐行可见）；`share_count` 已出现在 `formula` 串内（如 `((1000 - 200) / 100) * 10`），但**非独立字段**。
- 判定：`§N5.3-02` 列为**必需**链字段；独立字段未落库为**真缺口**。修它需**改冻结的 `schema/models.py::DerivedValue`**（跨工作流共享模型）→ 超本批范围，**登记**。可选方案：把 `share_count`/`compute_date` 并入 `DerivedValue.operands`（审计建议），或给 `DerivedValue` 增 `inputs` 字段——二者均需设计/需求方裁定。

### 4.4 提交与 pre-commit（阻断已按主理人指示合规解除）

- **提交阻断根因（与本次改动无关）**：`rules_lock_guard` / `injection_guard` 报 `rules/*.yaml` 为 `0o644`（应 `0o444`）。系统性伪影：**git 只跟踪可执行位、不跟踪只读位** → 新 `worktree add` checkout 出的 `rules/` 即 `0644`；本批**未触碰 `rules/**`**（`rules_lock_guard` 三条断言中，② SHA256 与 `registry/rules.lock.json` 一致、③ 无未登记文件，**仅** ① 权限不符）。
- **合规解除（主理人选 `(b)`）**：仅 `chmod 0444 system/rules/*.yaml`（**只改权限、不改内容、不动 `registry/rules.lock.json`**）。证据：

```console
$ ls -l system/rules/*.yaml
-r--r--r-- … system/rules/banned_tokens.yaml     （10 个文件全部 0444）
$ git status --short system/rules registry        # 空 → 无改动
$ git diff --stat -- system/rules registry        # 空 → 无改动
$ sh system/scripts/ops/pre-commit.sh
  append_only / rules_lock_guard / registry_schema / schema_sync /
  conflict_scan / no_placeholder_guard / injection_guard / verification_policy_guard
  → 全 RESULT: PASS（0 violations）
pre-commit ✓ 全部门禁放行        EXIT=0
```

- **提交（钩子开启、未用 `--no-verify`）**：`ws(fix-compute): 修 ws/compute 四条静默缺陷（…）`，**17 files changed, +625 / −52**。本报告文件即该提交一部分；本节证据随后续小提交并入。
- **提交哈希**：`5034beb`（代码+报告主体）；证据增补见下一条提交。

### 4.5 未触及（明确不在本批）

- `pipeline.py`（AC-03 真接线）——主理人集成时做。
- 审计 C-04（`handler` 丢弃 `run_date`/`scope`）、C-09（反查链接断裂）、C-10（公司行动样本）——本批未派、未改。
- `rules/**` · `verify.py` · `schema/models.py` · `conftest.py` · `registry/**` · `facts/**` · 设计区 —— **一律未改**。
