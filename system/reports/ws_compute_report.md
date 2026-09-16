# 工程师报告 · 并行工作流 `ws/compute` —— 确定性计算层 `scripts/compute/`

> 角色：寇豆码（Kou）· 工程师　|　分支：`ws/compute`（基线 `775e714`）　|　工作区：`.worktrees/ws-compute`
> 依据：`00_开发Agent开工提示词.md §5.2`（四段式报告：改了什么 / 测了什么带真实输出与退出码 / 逐 AC 证据 / 遗留不确定）
> 配套：DoD `system/reports/ws_compute_dod.md`（先写后码）
> 一句话：**建 `scripts/compute/` 确定性计算层 —— 算术全由程序产出、可追到 operand；基准口径只经 `return_guard`（唯一真源）；输入缺失 → 缺口对象；`method_version` 变更 → 新 `DerivedValue`（追加式不可变）。**

---

## 一、改了什么（What changed）

**只动本工作流模块清单内的文件**；共享文件（`pipeline.py` / `verify.py` / `rules/**` / `conftest.py` / `CONVENTIONS.md` / `registry/**` / `facts/**`）**一律未改**（见第四节）。

### 1.1 新增：确定性计算层 `system/scripts/compute/`（13 文件）

| 文件 | 行锚（节） | 职责 | 设计对齐 |
|---|---|---|---|
| `contract.py` | 全文 | 契约层：异常族（`ComputeError`/`MissingInput`/`UndefinedComputation`/`CaliberViolation`/`OrderViolation`）、`ComputeGap` 缺口对象、`make_derived()`（强制 `formula`+`operands`+`method_version` 非空）、`derived_id_for()`、`require_present/require_nonzero`、`gap_for()`、`safe_compute()`（把异常**折叠**为缺口对象） | `Ch9 §3.4.4`；`METHOD_VERSION="compute-v1"` |
| `core.py` | 全文 | 基础算子：`compute_yoy` / `compute_cagr` / `compute_diff_ratio` / `compute_change_ratio`；复用 `schema.models.Period`、`DerivedValue` | `Ch9 §3.4.4` |
| `growth.py` | 全文 | `compute_roiic` + `GrowthQuality` + `assess_growth_quality`（**四项分档** high/medium/low，**不压成单一分数**）；`VALUE_DESTRUCTIVE_FLAG="value_destructive_growth"` | `Ch4 §D.3` |
| `margin.py` | `_margin` 全文 | `compute_gross_margin` / `compute_operating_margin` / `compute_net_margin`（共用 `_margin`，单一实现） | `Ch9 §3.4.4` |
| `fx.py` | 全文 | `convert_amount`（**拒绝同币种**）、`compute_fx_adjusted_return` | `Ch9 §3.4.4` |
| `shares.py` | `_require_positive_shares` | `compute_eps` / `compute_value_per_share` / `compute_share_change_ratio`（股本 ≤0 → 缺口） | `Ch9 §3.4.4` |
| `returns.py` | `_total_return_value` / `compute_benchmark_return` / `compute_nav_return_diagnostic` | `PricePoint`、`CorporateActionPoint`；先复权再总回报；**基准收益委托** `return_guard.benchmark_return()`；净值收益**仅** `diagnostic`；拒绝 `is_nav` 点混入市场价口径 | `Ch9 §3.4.9` + `Ch3 §D.2`；`G-06` |
| `valuation.py` | `require_baseline_before_compute` / `ValuationRange` | `require_baseline_before_compute`（Ch5 §D.3 顺序约束，禁倒填）、`ValuationRange`（`as_range()`；`probability` 默认 `None`）、`compute_value_per_share_range` / `compute_implied_growth_ratio` / `compute_enterprise_value` | `Ch5 §D.2/§D.3/§D.6` |
| `store.py` | `append_derived_values` / `append_gaps` | `derived/` 追加式持久化（`derived_values.jsonl` + `compute_gaps.jsonl`）；复用 `schema.store._file_lock`；幂等键 `(derived_id, method_version)`；`history_for`/`current_value`/`iter_all_values` | `Ch9 §3.3.3 / §3.4.2 / §3.5④` |
| `driver.py` | `run_derived` / `_add_gap` / `assert_derived_integrity` | 真实运行编排（真读 `facts/`+`rules/`+`registry/`）；`DriverReport`；`_add_gap` 为**唯一缺口入账口**；`assert_derived_integrity` 完整性自检 | `Ch9 §3.5④` |
| `run_derived.py` | `main` | CLI 入口；退出码 0 跑通 / 1 违例 / 2 输入异常 | `Ch9 §2.4.3`；`G-01` 退出码契约 |
| `step.py` | `make_derived_handler` / `register_into` | step ⑤/⑥ 可插拔处理器工厂；签名同 `pipeline.StepHandler` | `Ch9 §3.5⑤⑥` |
| `__init__.py` | `__getattr__`/`__dir__` | 惰性导入（PEP 562），声明 `_SUBMODULES` | `CONVENTIONS.md P-02/P-03` |

### 1.2 新增：测试 `system/tests/compute/`（10 文件 + 1 夹具，82 用例）

| 文件 | 用例数 | 覆盖 |
|---|---|---|
| `conftest.py` | — | 轻量工程根 `scratch`（复制真实 `rules/benchmark.yaml`）＋ 真子进程 `cli` |
| `test_contract.py` | 10 | 缺口对象、`make_derived` 强制字段、`safe_compute` 折叠 |
| `test_operators.py` | 21 | core/growth/margin/fx/shares 全算子 |
| `test_returns.py` | 14 | 总回报/复权/净值诊断/`is_nav` 拒绝 |
| `test_valuation.py` | 13 | 区间/顺序约束/概率默认 null/EV |
| `test_store.py` | 7 | 幂等、`method_version` 变更新增行、AC-02 删索引重建、损坏行响亮失败 |
| `test_driver_real_run.py` | 5 | AC-01 真跑、AC-05 缺行情缺口入账 |
| `test_return_guard_wiring.py` | 5 | AC-04 注入违例 → **真进程 exit 1**；`G-06` 委托断言 |
| `test_step_wiring.py` | 3 | step 工厂签名、缺口降级 |
| `test_package_laziness.py` | 4 | 惰性导入（不 eager 拉 pydantic） |
| `fixtures/agix_prices.jsonl` | — | **真实** usAGIX 日线（westock MCP `data_kline`，抓取日 2026-09-16，12 点，2026-04-01~2026-09-15） |

### 1.3 报告

- `system/reports/ws_compute_dod.md`（DoD，先写后码）
- `system/reports/ws_compute_report.md`（本文件）

---

## 二、测了什么（What tested —— 真实输出 + 退出码）

### 2.1 本模块测试批次（真跑，非模拟）

```console
$ cd .worktrees/ws-compute && sh system/scripts/ops/run_pytest.sh tests/compute
============================= test session starts ==============================
platform darwin -- Python 3.13.12, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/gaza/Developer/InvestSigh/.worktrees/ws-compute/system
collected 82 items
tests/compute/test_contract.py ..........                                [ 12%]
tests/compute/test_driver_real_run.py .....                              [ 18%]
tests/compute/test_operators.py .....................                    [ 43%]
tests/compute/test_package_laziness.py ....                              [ 48%]
tests/compute/test_return_guard_wiring.py .....                          [ 54%]
tests/compute/test_returns.py ..............                             [ 71%]
tests/compute/test_step_wiring.py ...                                    [ 75%]
tests/compute/test_store.py .......                                      [ 84%]
tests/compute/test_valuation.py .............                            [100%]
============================== 82 passed in 3.88s ==============================
EXIT=0
```

### 2.2 AC-01 真跑（`run_derived.py`，真行情 usAGIX）

```console
$ python system/scripts/compute/run_derived.py <scratch_root> --prices-file system/tests/compute/fixtures/agix_prices.jsonl
== run_derived.py（确定性计算层）==
{
  "derived_ids": [
    "dv-benchmark_return-p01-compute-v1",
    "dv-benchmark_return-tbd-compute-v1",
    "dv-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1"
  ],
  "gap_ids": [],
  "gaps_written": 0,
  "hard_errors": [],
  "integrity_violations": [],
  "values_written": 3
}
RESULT: OK
EXIT=0
```

落盘 `derived/derived_values.jsonl`（节选一行，`formula`+`operands`+`method_version`+`computed_at` 齐全）：

```json
{"computed_at": "2026-09-16T05:11:24.532616Z", "derived_id": "dv-benchmark_return-p01-compute-v1",
 "formula": "benchmark_total_return(p01) [2026-04-01..2026-09-15; ccy=USD; dividends_reinvested=True; source=fund_market_price; fee_deducted_again=false]",
 "method_version": "compute-v1", "operands": ["rules/benchmark.yaml#p01", "prices(usAGIX)"],
 "value": "0.344910903050437934158864391"}
```

### 2.3 AC-05 错误路径（缺行情 → 缺口对象，不置 null）

```console
$ python system/scripts/compute/run_derived.py <scratch_root_无行情>
== run_derived.py（确定性计算层）==
{
  "derived_ids": [],
  "gap_ids": ["dv-gap-benchmark-p01-compute-v1", "dv-gap-benchmark-tbd-compute-v1"],
  "gaps_written": 2,
  "hard_errors": [],
  "integrity_violations": [],
  "values_written": 0
}
RESULT: OK
EXIT=0
--- derived/derived_values.jsonl ---
<无值落盘：正确>          # 缺失输入**不**出数值
--- derived/compute_gaps.jsonl ---
{"gap_id": "dv-gap-benchmark-p01-compute-v1", "method_version": "compute-v1", "missing": ["security_id"],
 "reason": "p01: 无法解析基准对应证券（未声明 security_id，且行情非唯一证券）",
 "recorded_at": "2026-09-16T05:11:29.068075+00:00", "subject": "p01"}
```

### 2.4 AC-04 守卫真拦得住（注入 → exit 1，非 warn）

```console
# ① --strict 下有缺口 → exit 1
$ python system/scripts/compute/run_derived.py <scratch_root> --strict
RESULT: FAIL（--strict：存在 2 个缺口对象）
STRICT_EXIT=1

# ② 完整性违例（手写缺 operands 行）→ exit 1
$ python system/scripts/compute/run_derived.py <scratch_root3> --no-persist
RESULT: FAIL（完整性违例）
  derived_values.jsonl#L1 缺 operands
INTEG_EXIT=1

# ③ 反向对照：未注入 → return_guard 放行
$ python system/scripts/benchmark/return_guard.py <scratch_root4>
RESULT: PASS（0 violations）
GUARD_OK_EXIT=0

# ④ 注入二次扣费 → return_guard exit 1（既有真源，非新写第二套校验）
$ python system/scripts/benchmark/return_guard.py <scratch_root4_已注入>
  [FATAL] N3.4-05/07 @ rules/benchmark.yaml:0 — [p01] 基金费用已含在实际回报，禁止二次扣费：fee_deducted_again=True
RESULT: FAIL（1 violations）
GUARD_BAD_EXIT=1
```

### 2.5 门禁批次（`verify.py --batch guards` / `--batch gates`）

```console
$ python system/scripts/ops/verify.py --batch guards
5 failed, 51 passed in 4.07s
FAILED ...test_exit_code_contract.py::...[rules_lock_guard]        # 环境（0644），非本批 bug
FAILED ...test_exit_code_contract.py::...[injection_guard]         # 环境（0644），非本批 bug
FAILED ...test_exit_code_contract.py::...[verification_policy_guard]  # V-06，预期
FAILED tests/guards/test_verification_policy.py::test_policy_guard_passes_on_pristine_tree   # V-06，预期
FAILED tests/guards/test_verification_policy.py::test_new_file_inside_existing_batch_is_allowed  # V-06，预期
```

```console
$ python system/scripts/ops/verify.py --batch gates
  conflict_scan.py                   exit=0
  append_only_guard.py               exit=0
  rules_lock_guard.py                exit=1   # 环境（0644），非本批 bug
  registry_schema_guard.py           exit=0
  schema_sync_guard.py               exit=0
  assert_gate_input.py               exit=0
  freeze_guard.py                    exit=0
  launch_guard.py                    exit=0
  module_denylist.py                 exit=0
  no_signal_day.py                   exit=0
  no_placeholder_guard.py            exit=0   # 本模块无占位符（AC-07）
  neutrality_check.py                exit=0
  return_guard.py                    exit=0
  anti_padding.py                    exit=0
  gap_to_task.py                     exit=0
  traceback.py                       exit=0   # 真读 derived/ 的消费方
  pipeline.py                        exit=0
  stage_gate.py --stage prep         exit=0
  injection_guard.py                 exit=1   # 环境（0644），非本批 bug
  verification_policy_guard.py       exit=1   # V-06，预期
  非零计数                               3
```

**3 项非零全部归因于"非本批变更"**（见第四节），本模块自身相关门禁（`no_placeholder_guard` / `conflict_scan` / `append_only_guard` / `traceback` / `return_guard`）**全部 exit 0**。

---

## 三、逐 AC 证据（Evidence per AC）

| AC | 判据 | 证据 | 结论 |
|---|---|---|---|
| **AC-01** 真跑通 | 真命令行落真实 `DerivedValue`（4 字段齐）＋退出码 0 | §2.2：`EXIT=0`，落盘 `value="0.3449…"`、`formula`/`operands`/`method_version`/`computed_at` 齐 | **PASS** |
| **AC-02** 持久化 | 写 `derived/` → 删 `index/` → 重建 → 数据仍在 | `test_store.py::test_write_read_reload_survives_index_deletion`（`shutil.rmtree(index)` → `rebuild_index()` → `read_rows` 非空，82 通过中） | **PASS** |
| **AC-03** 真接线 | 提供 step 处理器 + 真实消费方；注册动作待集成 | `step.make_derived_handler` 签名同 `pipeline.StepHandler`（`test_step_wiring.py` 3 通过）；真实消费方 `scripts/trace/traceback.py::_find_derived()` 真读 `derived/*.jsonl`（gates `traceback.py exit=0`） | **PARTIAL**（step 4/5/6 主流程接线属阶段②③，张力 `T-08`；本批**不改** `pipeline.py`） |
| **AC-04** 守卫真拦 | 注入 → **exit 1**，非 warn | §2.4①②③④：`STRICT_EXIT=1` / `INTEG_EXIT=1` / `GUARD_OK_EXIT=0`（对照）/ `GUARD_BAD_EXIT=1`（`N3.4-05/07`） | **PASS** |
| **AC-05** 错误路径 | 输入缺失 → 缺口对象（不置 null/0） | §2.3：缺行情 → 2 个 `ComputeGap` 入 `compute_gaps.jsonl`，`derived_values.jsonl` **无值落盘** | **PASS** |
| **AC-06** 边界 | 空/超大/非法/口径冲突 | `test_returns.py`（空/单点/`is_nav` 拒绝）、`test_operators.py`（除零 1e18 量级）、`test_valuation.py`（`CaliberViolation` 响亮失败）——82 通过中 | **PASS** |
| **AC-07** 无占位符 | `no_placeholder_guard.py` exit 0 | §2.5：`no_placeholder_guard.py exit=0` | **PASS** |
| **AC-08** 设计对齐 | 节号锚点齐全 | 见 §1.1 表"设计对齐"列；`DerivedValue`/`NumericClaim` **复用** `schema/models.py`（D1） | **PASS** |

---

## 四、遗留不确定（Remaining uncertainties —— 如实登记，不掩饰）

### 4.1 【必须由主理人集成时处理】V-06 预期报红：需新增验证批次 `compute`

`verification_policy_guard.py` 报 V-06：`tests/compute/` 下 9 个测试文件**不被任何批次覆盖**。

- **原因**：`verify.py::BATCHES` 无 `compute` 批次；本模块新增了 `system/tests/compute/**`。
- **★ 需主理人加入的批次名**：`compute`，目标 `tests/compute/`，建议超时 `60s`（实测 `82 passed in 3.88s`，留足余量）。
- **本批次未改** `verify.py`（共享文件，越界）；这是**预期红**，非缺陷。

### 4.2 【环境问题，非本批 bug】`rules_lock_guard` / `injection_guard` 报 0644

两守卫在**工作区**报 10 个 `rules/*.yaml` 权限为 `0o644`（应为 `0o444`）：

```console
$ ls -l /Users/gaza/Developer/InvestSigh/system/rules/benchmark.yaml        # 主仓库
-r--r--r--  ... benchmark.yaml                                             # 0444 ✓
$ ls -l /Users/gaza/Developer/InvestSigh/.worktrees/ws-compute/system/rules/benchmark.yaml  # 工作区
-rw-r--r--  ... benchmark.yaml                                             # 0644 ✗
```

- **根因**：git **不跟踪只读位**；`0444` 是主仓库 ship 时由 `lock_rules.py` 落的，**新建工作区 checkout 后即为 0644**。与"文件被改动"无关（内容与主仓库一致：`8245 / 3985 / 2863` 字节）。
- **不是本批引入**：工作区**所有** `rules/*.yaml` 均为 0644，本批未触碰 `rules/**`。
- **建议**：主理人集成时在目标工作区跑一次 `lock_rules.py`（锁 `rules/` 0444）；或在**主仓库**跑同样批次 → `rules_lock_guard` PASS（已验证）。**本批次严禁自行改 `rules/**`**。

### 4.3 AC-03 为 PARTIAL（诚实标注）

`pipeline.py` 的 step 4/5/6 处理器属**阶段②③**（张力 `T-08`，已由主理人登记）。本批次提供寄存器（`step.register_into`）与真实消费方（`traceback.py`），但**注册动作**待主理人集成阶段执行。**本批次不改共享文件 `pipeline.py`。**

### 4.4 真实行情输入的分红金额为 `null`

连接器返回的 2024-12-17 / 2025-12-22 两个分红计划金额为 `null`（未披露）→ 本批真实总回报窗口（2026-04-01~2026-09-15）**不含**分红事件；分红再投资的算术由单测夹具覆盖。**不猜数**（`Ch9 §2.4.3`）。

### 4.5 本批**未修改**的共享文件清单（供审计核对）

`rules/**`（0444 锁定）· `system/tests/conftest.py` · `system/CONVENTIONS.md` · `system/scripts/ops/verify.py`（含其批次加载器）· `system/scripts/orchestrate/pipeline.py` · `registry/**` · `facts/**` · 设计区 `00_*`/`01_`~`11_` · 其余任何非本模块文件 —— **均未改**。

---

## 五、自检判定

- 全局跨文件一致性：**IS_PASS: YES**（导入链一致；`derived/` 读写契约一致；`G-06` 无第二套口径校验；`DerivedValue`/`ComputeGap` 类型在 driver/store 间一致）。
- 本模块测试：**82 passed**（exit 0）。
- 本模块相关门禁：`no_placeholder_guard` / `conflict_scan` / `append_only_guard` / `traceback` / `return_guard` 全 **exit 0**。
- 未闭合项：仅 §4.1（V-06 批次登记，主理人集成时加 `compute` 批次）与 §4.2（工作区 rules 权限，环境属性）。
