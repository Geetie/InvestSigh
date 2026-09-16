# `§九` 独立审计 — `ws/compute`

审计对象：`system/scripts/compute/**`（13 文件 / 1997 行）+ `system/tests/compute/**`（82 用例）
审计方：independent-auditor（换人、对抗性、不采信自报）
审计日期：2026-09-16　环境：`CODEBUDDY_SAFE_DELETE_SANDBOX=0`、`CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`
未执行：任何 `git` 命令（受硬约束禁止）→ 变更面证伪见 §6
临时探测根：`system/tests/.audit/compute/**`（**已整体删除**，仓库真源未被污染，见 §7）

## §0 结论摘要

| AC | 判定 | 一句话依据 |
|---|---|---|
| AC-01 真跑通 | **PASS** | 夹具行情真跑 `exit 0` / `values_written: 3`，3 条 `DerivedValue` 带 formula+operands+method_version+computed_at；值 = 44.53/33.11−1 逐字相符 |
| AC-02 持久化 | **PASS** | 独立复现：删整个 `index/` → `rebuild_index()` → 3 行 `derived/` 原样可读（读路径不经索引） |
| AC-03 真接线 | **FAIL** | `scripts/compute/**` **零生产调用方**；`pipeline.run_daily` 只注册 step 1；被引为"真消费者"的 `_find_derived` 既不可达、也不可能命中 compute 产物 |
| AC-04 守卫真拦 | **PASS** | `return_guard.py` 干净 exit 0 / 三类注入 exit 1；`--strict` 缺口 exit 1；完整性违例 exit 1；compute 未复制口径断言（G-06 ✓） |
| AC-05 错误路径 | **PARTIAL** | 驱动层 5 场景全缺口 ✓；但 `None`（缺失）型数值输入 → 裸 `TypeError` 而非 `ComputeGap`（含 AC-05 明列的"缺汇率"）；幂等键缺设计要求的 `version` 分量 → 上游重述静默沿用旧值 |
| AC-06 边界 | **PASS** | 空/单点/无数据 → 缺口；期初价 0、股本 0/负 → 缺口；非法 price → `ValueError` exit 2；NAV 混入 → `CaliberViolation` exit 2（不吞）；1e18 → 正常计算 |
| AC-07 无占位符 | **PASS**（按字面） | `no_placeholder_guard.py system --fail-on warn` → exit 0（107 文件）；`scripts/compute/**` 确在扫描域（种入即命中）。判别力有限，注释/docstring 内占位**不可见** |
| AC-08 设计对齐 | **PARTIAL** | 12 个设计锚点全部存在、锚点引用合规、`DerivedValue`/`Period` 真复用；但 `NumericClaim` 复用项在代码中**无对应实体**；`growth` 分档与 `Ch4 §D.3` 伪码不一致；估值顺序校验在双 `None` 时静默跳过 |

**合计：PASS 5 / FAIL 1 / PARTIAL 2 / UNKNOWN 0。结论：不通过验收（`ws/compute` 不可判 ACCEPTED）。**
最严重问题：AC-03 —— 一个 1997 行、82 用例全绿的模块，生产链路里没有任何调用方；且被当作接线证据的消费者结构上无法消费该模块产物。

## §1 三项探测原始证据

### P1 write-read-reload（命令原样、输出原样）

```
$ cd system && python - <<'EOF'    # 解释器 $HOME/.workbuddy/binaries/python/envs/default/bin/python
rows_before = list(read_rows(ROOT,"derived_values")); shutil.rmtree(ROOT/"index")
rebuild_index(ROOT); rows_after = list(read_rows(ROOT,"derived_values"))
EOF
=== P1 step1: BEFORE, derived rows via compute.store.read_rows ===
count = 3
   dv-benchmark_return-p01-compute-v1 | formula? True | operands? True | mv = compute-v1 | computed_at = 2026-09-16T06:17:13.275788Z
   dv-benchmark_return-tbd-compute-v1 | formula? True | operands? True | mv = compute-v1 | computed_at = 2026-09-16T06:17:13.276884Z
   dv-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1 | formula? True | operands? True | mv = compute-v1 | computed_at = 2026-09-16T06:17:13.276902Z

=== P1 step2: rm -rf index/ ===
index exists before: True | files: ['index/.locks/derived_derived_values.lock']
index exists after : False

=== P1 step3: schema.store.rebuild_index(code_root) ===
rebuild_index returned: tests/.audit/compute/r1/system/index/facts.sqlite
index tree after rebuild: ['index/facts.sqlite']

=== P1 step4: AFTER, re-read derived/ ===
count = 3
   dv-benchmark_return-p01-compute-v1 | formula? True | operands? True | mv = compute-v1 | computed_at = 2026-09-16T06:17:13.275788Z
   dv-benchmark_return-tbd-compute-v1 | formula? True | operands? True | mv = compute-v1 | computed_at = 2026-09-16T06:17:13.276884Z
   dv-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1 | formula? True | operands? True | mv = compute-v1 | computed_at = 2026-09-16T06:17:13.276902Z

=== P1 verdict ===
derived rows preserved across index deletion + rebuild: True | before/after = 3 / 3
```

★ 附带事实（`schema/store.py:157-201` 逐字）：`rebuild_index` 只遍历 `JSONL_MODELS`（= `facts/` 各 stem），**不索引 `derived/`**。故 P1 证明的是"**读路径不依赖索引**"；`derived/` 侧根本不存在可重建索引（并非"重建后仍在"）。

### P2 缺上游 → 必须响亮（缺口对象），不得 `None`/`0`/估计

命令：对 5 个场景根逐一 `python system/scripts/compute/run_derived.py <root>`，原样输出（节选交互重复行，退出码全列）：

```
################ s1_no_prices ################
{ "derived_ids": [], "gap_ids": ["dv-gap-benchmark-p01-compute-v1","dv-gap-benchmark-tbd-compute-v1"], "gaps_written": 2, "values_written": 0 }
RESULT: OK    EXIT=0
  {"gap_id": "dv-gap-benchmark-p01-compute-v1", "missing": ["security_id"], "reason": "p01: 无法解析基准对应证券（未声明 security_id，且行情非唯一证券）", ...}
################ s2_no_benchmark ################
{ "derived_ids": ["dv-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1"], "gap_ids": ["dv-gap-benchmark-<benchmark-set>-compute-v1"], "gaps_written": 1, "values_written": 1 }
RESULT: OK    EXIT=0
################ s3_one_point ################
{ "gap_ids": ["dv-gap-benchmark-p01-compute-v1","dv-gap-benchmark-tbd-compute-v1"], "missing": ["prices"], "reason": "p01: 证券 usAGIX 区间 [None..None] 内行情不足（<2 点）" }
RESULT: OK    EXIT=0
################ s4_nav ################
[INPUT-ERROR] run_derived: CaliberViolation: p01: 市场价总回报不得混入净值点（Ch3 §D.2 ③，共 2 个 is_nav 点）
EXIT=2     ← 口径冲突：响亮失败，且未生成 compute_gaps.jsonl（不当缺口吞掉）✓
################ s5_zero_price ################
{ "gap_ids": ["dv-gap-benchmark_return-p01-compute-v1","dv-gap-benchmark_return-tbd-compute-v1","dv-gap-total_return-usAGIX-2026-04-01..2026-09-15-compute-v1"], "values_written": 0 }
RESULT: OK    EXIT=0
  {"missing": ["prices"], "reason": "p01: 期初价非正（0），总回报无定义"}
```

算子级（`safe_compute` 折叠后）逐行原样：

```
-- (a) compute_yoy(base=0) --            RAISED UndefinedComputation : s: base（基期） 为 0，该计算无定义（Ch9 §2.4.3 边界）
-- (a2) 经 safe_compute --               -> ComputeGap | missing = ['base（基期）']
-- (b) compute_change_ratio(begin=0) --  -> ComputeGap | missing = ['begin（基期）']
-- (c) compute_diff_ratio(denom=0) --    -> ComputeGap | missing = ['denominator（分母）']
-- (d) compute_cagr(begin=-1) --         -> ComputeGap | missing = ['begin', 'end']
[(e) eps(shares=0)]                      GAP  missing=['shares']
[(e2) eps(shares=-5)]                    GAP  missing=['shares']
[(e4) share_change_ratio(begin=0)]       GAP  missing=['begin_shares（期初股数）']
[(f1) fx.convert_amount(rate=0)]         GAP  missing=['rate（汇率）']
[(f2) fx.convert_amount(rate=None)  # 缺汇率]  RAISED TypeError: unsupported operand type(s) for *: 'decimal.Decimal' and 'NoneType'
[(f3) fx.convert_amount(USD->USD)]       GAP  missing=['rate']
[(f5) fx_adjusted_return(rate_begin=None)] RAISED TypeError: unsupported operand type(s) for /: 'decimal.Decimal' and 'NoneType'
[(m1) gross_margin(revenue=0)]           GAP  missing=['revenue（收入）']
[(m2) gross_margin(revenue=None)]        RAISED TypeError: unsupported operand type(s) for /: 'decimal.Decimal' and 'NoneType'
[(g1) roiic(invested=0)]                 GAP  missing=['incremental_invested_capital（增量投入资本）']
[(g2) roiic(invested=None)]              RAISED TypeError: unsupported operand type(s) for /: 'decimal.Decimal' and 'NoneType'
```

静默兜底扫描（`scripts/compute/**` 全量 `except`）：仅 4 处 —— `contract.py:205`（按设计折叠缺口类异常）、`run_derived.py:67/79`（日期/输入异常 → exit 2）、`driver.py:132`（非法 price → 重抛 `ValueError`）、`store.py:76`（损坏行 → 抛 `ValueError`）。**无 `except: pass`、无 `return 0` 兜底**。
### P3 接线体检（命令原样、输出必要项原样）

```
$ grep -rn "make_derived_handler|register_into|scripts\.compute|scripts/compute" --include="*.py"
scripts/compute/step.py:30:  def make_derived_handler(root, *, step_no=5) -> Any
scripts/compute/step.py:59:  def register_into(pipeline, *, step_no=5) -> None
scripts/compute/step.py:64:      pipeline.register_step(step_no, make_derived_handler(pipeline.root, step_no=step_no))
tests/compute/test_step_wiring.py:28:  handler = step.make_derived_handler(scratch)
tests/compute/test_step_wiring.py:48:  step.register_into(pipeline, step_no=5)
scripts/benchmark/return_guard.py:89:  「`total_return_fn` 由调用方注入（`scripts/compute/` 于阶段② 交付）」   ← 仅 docstring 提及
（其余命中全部在 tests/** 与 reports/**）
```

```
$ python system/scripts/compute/run_derived.py system --no-persist     # 用仓库自身真源（facts/prices.jsonl = 0 行）
EXIT=0
{ "derived_ids": [], "gap_ids": ["dv-gap-benchmark-p01-compute-v1","dv-gap-benchmark-tbd-compute-v1"],
  "gaps_written": 0, "integrity_violations": [], "values_written": 0 }
RESULT: OK
```

**结论**：`scripts/compute/**` 的生产调用方 **= 0**。`pipeline.py:111-123 _register_default_steps()` 只 `register_step(1, ingest_public_information)`。且**仓库真源态下 `exit 0` 不代表有产出**（`values_written: 0` 也报 `RESULT: OK`）—— AC-01 的"真跑通"只有喂 `--prices-file` 夹具才成立。

## §2 逐条 AC 四态判定

**AC-01 真跑通 = PASS。** 证据：`run_derived.py` CLI 以 `--prices-file tests/compute/fixtures/agix_prices.jsonl` 跑 → `exit 0`、`values_written: 3`；`derived/derived_values.jsonl` 逐行（`store.py:133 _dump_row` → pydantic json 模式）之 p01 行原文：
`{"computed_at":"2026-09-16T06:17:13.275788Z","derived_id":"dv-benchmark_return-p01-compute-v1","formula":"benchmark_total_return(p01) […source=fund_market_price; fee_deducted_again=false]","method_version":"compute-v1","operands":["rules/benchmark.yaml#p01","prices(usAGIX)"],"value":"0.344910903050437934158864391"}`，与 44.53/33.11−1 精确一致。子项核对：真 CLI ✓、真输入（夹具声明于 DoD）✓、四要件齐备 ✓。**遗留**：`registry/corporate-actions.jsonl` = 0 字节 → 真实窗口仅走"纯价格"分支，分红/拆股仅由单测合成覆盖（§6）。

**AC-02 持久化 = PASS。** 见 §1 P1；另 `store.read_rows`（`store.py:63-78`）直读文件、损坏行抛 `ValueError`（`test_store.py:82`）。子项"为何不落 `facts/`"核对成立：`facts/` 实测恰 18 个 JSONL（`ls -1 system/facts/*.jsonl | wc -l` = 18），与 `Ch9 §3.3.3` 逐字一致。

**AC-03 真接线 = FAIL（不采信自报 PARTIAL）。** 三条独立事实：
1. **无生产调用方**：见 §1 P3。`step.py` 的两个出口函数只被 `tests/compute/test_step_wiring.py` 调用。
2. **签名"逐字一致"仅到参数层，语义未接**：`make_derived_handler` 内层 `handler(run_date, scope)` 对两参数**完全不用**。实测 `handler(date(2026,9,16),"full") == handler(date(2020,1,1),"full") == handler(date(2026,9,16),"partial")` 三者 `StepOutcome` 全等。
3. **`produced` 语义会击穿空执行守卫**：`step.py:49` `produced=list(report.derived_ids)`（= 全部重算 id，非本次新增）。实测幂等第 2 次调用 `values_written=0`（`derived/` 行数恒 3）但 `produced` 仍为 3 条。而 `pipeline.py:321` 的 G1-05"空执行"判据正是 `elif not step.produced:` → **只要 step 5 一接入，一个什么都没落库的运行也会判 ok 且不被拦**。
不合格 DoD 子项：AC-03 主体"真接线"（§一 底线 2）**未达成**；引为证据的"真消费者"不成立（见 §4）。**公平注记**：缺口是**已声明**的（`T-08` + DoD "honest note"），属"显式未完成"，不是隐瞒式假交付；但 §九 明令"未达成即 FAIL、不得部分给分"，且 PARTIAL 会被下游读成"接线已验证"。

**AC-04 守卫真拦 = PASS。** ① `return_guard.py` 四态实测：pristine → `RESULT: PASS（0 violations）` exit 0；`return_source='sp500_index'` → `[FATAL] N3.4-05/07 … 禁用替代指数` exit 1；`fee_deducted_again=True` → `禁止二次扣费` exit 1；`nav_return_role='primary'` → exit 1。② G-06：`scripts/compute/**` 内 `fund_market_price|fee_deducted_again|BenchmarkCaliberError` 命中**全部在 docstring 或 formula 字符串**，无第二份断言逻辑；`returns.py:246` 惰性导入 `return_guard.benchmark_return` 并以其结果构 `DerivedValue`。③ `--strict`：有缺口 → `RESULT: FAIL（--strict：存在 2 个缺口对象）` exit 1；无缺口 → exit 0。④ 完整性违例：手工塞入缺 `formula` 行 → `"integrity_violations": ["derived_values.jsonl#L4 缺 formula"]` + `RESULT: FAIL（完整性违例）` exit 1。

**AC-05 错误路径 = PARTIAL。** 合格部分：§1 P2 的驱动层 5 场景与算子层 13 例，全部输出 `ComputeGap`（带 `missing[]` + `reason`），无 `None`/`0`/估计；`safe_compute`（`contract.py:191-208`）只折叠 `MissingInput`/`UndefinedComputation`，`CaliberViolation`/`OrderViolation` 原样抛（`s4_nav` exit 2 已证）。不合格两条：
- **(C-01) `None` 型缺失输入未被折叠**：`require_nonzero`（`contract.py:167-174`）只判 `value == 0`，`None == 0 → False` 故放行，随后在算术里炸成裸 `TypeError`。实测 4 例（fx rate=None、fx rate_begin=None、margin revenue=None、roiic invested=None）。AC-05 明确列了"**缺汇率**"→ 此路必须是缺口对象。且 `run_derived.py:79` 不捕 `TypeError`，将来接上会以 traceback 形式退出且退出码 1 与"完整性违例"语义撞车。
- **(C-02) 幂等键缺设计要求的 `version` 分量**：设计权威 `Ch9 §3.5` 阶段④ 幂等键逐字 = `(company_id, version, method_version)`；实现为 `(derived_id, method_version)`（`store.py:89-109`），而 `derived_id_for`（`contract.py:150-153`）= `dv-<kind>-<subject>-<method_version>` **不含任何 version**。实测：首跑期初 33.11 → 落库 `0.3449…`；把上游重述为期初 40.00（`method_version` 不变）后重跑 → `values_written: 0`、`gap_ids: []`、`integrity_violations: []`、CLI 报 `RESULT: OK`，落库仍是旧值 `0.3449…`（真值应为 0.11325）。→ **上游重述被静默沿用旧值**，正是"分档/口径漂移"最该拦的一类。

**AC-06 边界 = PASS。** 空区间 → `MissingInput` 缺口；单点 → `UndefinedComputation`（`returns.py:118-129`）；期初价 0 → 缺口（`returns.py:178-183`）；股本 0/负 → 缺口（`shares.py:21-34`）；`low_multiple > high_multiple` → 缺口；非法 price `"abc"` → `ValueError: …price 非法: 'abc'` → CLI `[INPUT-ERROR]` exit 2；NAV 混入 → `CaliberViolation` exit 2；巨值 `yoy(1e18, 5e17) = 100`、`cagr(1e18, 4e18, 10) = 0.148698354997035006798626947` 正常。

**AC-07 无占位符 = PASS（按字面口径）。** 命令与输出：`python system/scripts/checks/no_placeholder_guard.py system --fail-on warn` → `scanned files: 107` / `RESULT: PASS（0 violations）` / `EXIT=0`。非真空对照：在临时根 `.../np3/system/scripts/compute/` 种 8 种形态 → `EXIT=1`，命中 `EMPTY_BODY`、`PLACEHOLDER-CN`、`NOT_IMPLEMENTED`、`SWALLOW_EXCEPTION_PASS`、`FAKE_DATA`（5 条）→ 证明 **`scripts/compute/**` 确在扫描域**。判别力边界（如实记录）：`docs/` 免扫；`.py` 内**注释与 docstring 被抹白（G-04）**，故 `# TODO: 待实现`（m6）与 `"""待实现：占位。"""`（m5）**不被命中**，标识符 `mock_rows`（m4）亦不命中。故本 PASS ≠"不存在隐蔽占位符"，只等于"可执行 token 层无占位符"。

**AC-08 设计对齐 = PARTIAL。** 合格部分：① 12 个锚点在设计区**全部存在**，实测 `09_需求拆解与实现方案_v1.md:678 ### 3.4.4`、`:696 ### 3.4.5`、`:744 ### 3.4.9`、`:570 ### 3.3.3`、`:772 ## 3.5`、`:343 ### 2.4.3`、`:659 ### 3.4.2`、`:767 ### 3.4.12`、`03_.../02_实现方案.md:117 ### D.2`、`04_.../02_实现方案.md:214 ### D.3`、`05_.../02_实现方案.md:86/162/174/202`。② `Ch9 §3.4.4` 目录逐字为 `core/growth/margin/returns/fx/shares/valuation` — 实测 compute 正是这 7 个算子模块 + 5 个基础设施文件。③ 接口示例兼容：设计 `compute_yoy(current, base, unit, period) -> DerivedValue` 的 4 个位置参数在实现中全部保留，新增项一律 keyword-only。④ `DerivedValue`/`Period` 从 `schema/models.py` 真复用（7 个模块 `from schema.models import DerivedValue`），compute 内无任何 `BaseModel` 子类。⑤ `Ch9 §3.4.9` 顺序（先复权 → 再总回报）在 `returns.py:105-185` 落地，动作排序键 `(effective_date, {"split":0,"spinoff":0,"div":1})` 确定性。不合格/不可判三条：
- **(C-03) DoD 子项"`numerics` ↔ `NumericClaim`（9 字段复用）"无对应实体**：`grep -rn "NumericClaim" scripts/compute/` 零命中，代码中不存在 `numerics`。该子项既不能判过、也不能判"已实现"，属**清单与代码脱节**。
- **(C-04) `growth` 分档与 `Ch4 §D.3` 伪码不一致**：设计伪码 `if roiic < wacc: return GrowthQuality("low", flag="value_destructive_growth")`；实现 `growth.py:97-123` 把它记为 1 个负分 → `negatives==1 → "medium"`。实测 `roiic=0.05, wacc=0.10` 其余三项中性 → `grade = medium | flags = ['value_destructive_growth']`。flag 对、**档位差一级**。
- **(C-05) 估值顺序约束在"双 None"时静默跳过并用当前时间兜底**：`valuation.py:114-123` 仅在 `baseline_analyzed_at is not None or computed_at is not None` 时才校验，否则 `compute_moment = computed_at or datetime.now(timezone.utc)`。实测三态：both None → **成功**，`compute_date = 2026-09-16`（= 当日 UTC）；只给 baseline → `MissingInput`；倒填 → `OrderViolation`。而同文件 `require_baseline_before_compute` 的 docstring 逐字写着"**不得**用'当前时间'兜底，否则倒填不可检" → **函数与自身声明的契约相反**，且 `Ch5 §D.3` 第四条规则要求"版本倒序 → 拒绝"。该路径恰是**默认路径**（调用方不传即中招）。
- 附：`Ch5 §D.2` 要求的 `share_count` + `compute_date` 落在**本地 frozen dataclass `ValuationRange`**（`valuation.py:60-77`），而 `schema/models.py` 的 `DerivedValue` 无 `inputs` 字段（设计示例里的 `inputs={..., share_count, compute_date}` 在冻结 schema 中不存在）；`store` 只接受 `DerivedValue`，故 `ValuationRange` **从未落库** → §D.2 的链字段未进 `derived/`。

## §3 `施工图 §8` 十二条纪律逐条对拍

| # | 纪律 | 判定 | 证据 |
|---|---|---|---|
| 1 | 零新增门槛 / 参数不进决策函数 | 无违例 | `rules/banned_tokens.yaml` 的 `decision_scope.include_paths` 仅 `scripts/decision/**`+`scripts/graph/**`，compute 不在域；`tests/injection/test_guards_reject.py:115-121` 反向对照正以 `scripts/compute/aggregate.py` 为"非决策域必放行"例证。注记：`growth.py:104 cash_threshold = 0.8` 为代码内嵌经验值，`freeze.yaml`（仅 11 项待冻结参数）未声明；作者标注"分档依据而非门槛"且档位不阻断结论 → 不判违例，建议锚定出处 |
| 2 | 命中即 fail，禁 warn-only | 无违例 | compute 无 warn 分支；`--strict`/完整性违例均 `exit 1`（§1 P2、§2 AC-04） |
| 3 | 禁词入库前 grep + 声明可执行 scope | 无违例 | `grep -rniE "\b(weight\|score\|vote\|sentiment\|follower_count)\b" scripts/compute/` 零命中 |
| 4 | 追加式不可变 | 无违例（有 C-02 附带风险） | `store.py:50-60` 只 `open(path,"a")`，无 UPDATE/DELETE；`test_store.py:47` 证 `method_version` 变更新增行。风险见 C-02（缺 `version` 分量 → 上游重述不新增行） |
| 5 | 参数值唯一真源 = `rules/freeze.yaml` | 无违例 | compute 不读 freeze.yaml；唯一硬编码阈值 0.8 非 11 项之一（见 #1 注记） |
| 6 | 节号锚点，禁绝对行号 | 无违例 | `grep -rnE "\.py:[0-9]+\|第 ?[0-9]+ ?行\|L[0-9]{2,}" scripts/compute/` 零命中；docstring 一律 `ChN §X` |
| 7 | 枚举 token 英文小写+下划线，待定 `tbd` | 无违例 | `grade ∈ {high,medium,low}`、`financing_dependence ∈ {none,low,high}`、`action_type ∈ {div,split,spinoff}`、异常类英文；`method_version="compute-v1"` 与设计示例 `val-v1` 同形 |
| 8 | 同名不同域必须消歧 | 无违例 | `compute_*` 统一前缀；`ValuationRange` vs `DerivedValue` vs `ComputeGap` 语义无重叠 |
| 9 | 单写者 + 文件锁；`rules/` 0444+SHA256 | 无违例 | `store.py:27` 复用 `schema.store._file_lock`（纪律 11 唯一锁路径）；实测 `rules/*.yaml` 全部 `-r--r--r--`（0444） |
| 10 | 模型对 `rules/` 无写权 | 无违例 | compute 内无任何 `rules/` 写路径，仅 `yaml.safe_load` 读 |
| 11 | 复用优先 | 无违例 | 复用 `DerivedValue`/`Period`/`_file_lock`；`ValuationRange`/`ComputeGap` 自造但 `schema/models.py` 无对应模型 |
| 12 | 阶段未过即阻塞，不得静默跳过 | **命中 1 处** | `valuation.py:114-123`：双 `None` 时静默跳过 `Ch5 §D.3` 顺序校验并以当前时间兜底（= C-05） |

## §4 自报判定复核（专章：AC-03 自报 `PARTIAL` 是否偏松）

**StepHandler 逐参数比对（两侧原文逐字）**

```
scripts/orchestrate/pipeline.py:85      StepHandler = Callable[[date, str], "StepOutcome"]
scripts/orchestrate/pipeline.py:88-95   @dataclass class StepOutcome:
                                            produced: list[str] = field(default_factory=list)
                                            judgment_change: dict[str, bool] = field(default_factory=dict)
                                            signals_emitted: int = 0
                                            degraded: bool = False
scripts/compute/step.py:30              def make_derived_handler(root: str | Path, *, step_no: int = 5) -> Any
scripts/compute/step.py:42              def handler(run_date: date, scope: str) -> Any
```

| 比对项 | `StepHandler` | `step.handler` | 结论 |
|---|---|---|---|
| 位置参数 1 | `date` | `run_date: date` | **一致** |
| 位置参数 2 | `str` | `scope: str` | **一致** |
| 参数个数/顺序 | 2 | 2 | **一致** |
| 返回值注解 | `"StepOutcome"` | `Any`（惰性导入 `StepOutcome`，`step.py:43`） | **不一致**（`Callable` 参数逆变/协变下 `Any` 可赋值 → 运行时兼容；故"逐字一致"的说法只对参数成立，对返回注解不成立） |
| 返回对象构造 | `produced/judgment_change/signals_emitted/degraded` | 只给 `produced/degraded/signals_emitted`，`judgment_change` 用默认 `{}` | 兼容 |
| `register_step` 签名 | `register_step(self, step: int, fn: StepHandler)`（`pipeline.py:131`） | `pipeline.register_step(step_no, handler)`（`step.py:64`） | **一致** |

**"真消费者" `traceback.py::_find_derived` 三点核查**

1. **是不是真消费者**：`_find_derived`（`traceback.py:119-130`）确实 `rglob("*.jsonl")` 遍历 `derived/` 并要求 `formula`+`operands`+`method_version` → 是**读路径**，不是"顺带一读"。
2. **是否被执行**：`run_all_gates.py:44` 注册了 `traceback.py` ✓；但 `check()`（`traceback.py:144-153`）在 `facts/recommendations.jsonl` 为空时**直接 early-return 并记 `NO_RECOMMENDATION_DATA`**；仓库真源实测 `recommendations.jsonl` = 0 行 → **`_find_derived` 从未在真数据上跑过**。
3. **能否命中**：`_find_derived` 的匹配条件是 `row.get("conclusion_id") == conclusion_id or row.get("derived_id") == conclusion_id`；而 `conclusion_id` 来自 `recommendation_id`。`DerivedValue`（`schema/models.py:400-412`）**没有 `conclusion_id` 字段**，compute 也从不写该字段；`derived_id`（`dv-…`）永不等于 `recommendation_id`（`rec-…`）。**独立实测**（构造 `derived/` 一行 compute 形态产物 + 一行 `recommendations.jsonl`）：

```
scanned = {'recommendations': 1, 'sample': 1, 'coverage_x100': 0}
violations = ["[FATAL] G1-03 @ facts/recommendations.jsonl:0 — rec-001 四要素缺失: ['computation']",
              "[FATAL] G1-03 @ facts/recommendations.jsonl:0 — 四要素覆盖率 0.0000 < 1.0"]
computation = None        # traceback(root,'rec-001') 的结果
_find_derived(root, "dv-benchmark_return-p01-compute-v1") = 该行（自身能找到）
但 traceback(root, "dv-benchmark_return-p01-compute-v1") → TraceabilityGap: 未找到结论/建议
```

→ 只要 `facts/` 里真出现一条建议，反查门禁就会因 `computation` 缺失而**红**。"这是真消费者因此接线成立"的推论不成立。

**总判**：① 签名匹配 = 成立（参数层）；② "真消费者" = **不成立**（既不可达、又结构上无法命中）；③ "无生产调用方" = 成立（§1 P3）。再加上 `handler` 丢弃 `run_date/scope` 与 `produced` 击穿 G1-05 空执行判据（§2 AC-03），**自报 `PARTIAL` 偏松，本条应为 `FAIL`**。**分歧点**：DoD 把 AC-03 的判据从"主流程真调用"降级为"提供与 `StepHandler` 同签名的接缝 + 存在一条读 `derived/` 的代码"，并以"改共享文件属阶段②③（`T-08`）"为免责。避让共享文件本身**合理**（避免与他人冲突），但"是否达成真接线"与"是否改共享文件"是两件事：前者是验收判据，后者是排期约束；§九 禁止以排期理由把 FAIL 升为 PARTIAL。建议的准确表述：**AC-03 未达成（FAIL）；已交付的是"接线接缝（`step.py`）+ 真实 CLI 入口（`run_derived.py`）"，属部分物证，不计分。**

## §5 缺口清单（N-5 converge）

| 编号 | 描述 | 证据 | 建议处置 |
|---|---|---|---|
| C-01 | `None`（缺失）型数值输入不被折叠为缺口，裸 `TypeError`（含 AC-05 明列的"缺汇率"） | §1 P2 的 `(f2)(f5)(m2)(g2)` 四行原样输出；根因 `contract.py:167-174` 只判 `== 0` | 在 `require_nonzero` 增 `None` 分支或在 4 个算子入口加 `require_present`；补 4 条单测（`rate=None` 等） |
| C-02 | 幂等键缺设计要求 `version` 分量 → 上游重述静默沿用旧值，CLI 仍 `RESULT: OK` | 设计 `Ch9 §3.5` 阶段④ 幂等键 `(company_id, version, method_version)`；实现 `store.py:89-109` + `contract.py:150-153`；实测重述后 `values_written=0` 且落库值不变 | 把 `version` 并入 `derived_id`/幂等键，或在 `DerivedValue.operands` 强制携带版本引用；补"上游重述 → 新行"回归 |
| C-03 | `produced` 语义（全部重算 id）会击穿 G1-05 空执行判据 | `step.py:49` vs `pipeline.py:321`；实测幂等第 2 次 `values_written=0` 而 `produced` 非空 | `produced` 改为"本次实际新增/变更的对象引用"（用 `values_written` 对齐），或额外回传 changed 集 |
| C-04 | `handler` 丢弃 `run_date`/`scope` → 接入后每日重算全量、非按日增量 | 实测三组不同 `(run_date, scope)` 的 `StepOutcome` 全等 | 传入 `start/end` 由 `run_date` 派生；或显式声明该步为"全量重算"并写进 `pipeline.yaml` |
| C-05 | 估值顺序校验在双 `None` 时静默跳过 + 当前时间兜底（与同文件 docstring 相反） | `valuation.py:114-123`；实测 both-None → 成功且 `compute_date=2026-09-16`；`Ch5 §D.3` 第四规则要求"倒序 → 拒绝" | 删去 `or datetime.now(...)`，两时间任一缺失即 `MissingInput`；补"双 None 必须拒"单测 |
| C-06 | `growth` 分档与 `Ch4 §D.3` 伪码不一致（roiic<wacc 唯一下 → 设计 `low` / 实现 `medium`） | `growth.py:97-123`；`04_.../02_实现方案.md:214+` 伪码 `return GrowthQuality("low", flag=…)`；实测 `grade=medium` | 请需求方/作者裁定档位映射；若维持实现，须在设计锚点旁注明"四项计负分"的覆盖规则 |
| C-07 | DoD 子项"`numerics` ↔ `NumericClaim`（9 字段复用）"在代码中无对应实体 | `grep -rn "NumericClaim" scripts/compute/` 零命中 | 删该子项或明确 compute 是否需要产出 `NumericClaim`（当前只产 `DerivedValue`） |
| C-08 | `ValuationRange`（含 `Ch5 §D.2` 要求的 `share_count`/`compute_date`）从不落库；`valuation.py` 全模块无生产调用方 | `valuation.py:60-148`；`store.py` 只接受 `DerivedValue` | 与 C-03 一并修：或给 `ValuationRange` 增加落库映射，或把链字段并入 `DerivedValue.operands` |
| C-09 | 反查链接断裂：`recommendation_id ↔ derived_id` 无任何机制可对上（门禁必红） | §4 实测 `G1-03 … 四要素缺失: ['computation']` | 由设计/需求方定链接键（compute 写 `conclusion_id`？还是反查按 company+window 匹配？）；当前状态不得宣称"反查已通" |
| C-10 | AC-01 真实数据分支未覆盖公司行动（`registry/corporate-actions.jsonl` = 0 字节），分红/拆股仅单测合成 | `wc -c` = 0；`returns.py:137-175` | 补一条带（登记为样本的）公司行动的端到端运行留档 |

## §6 未能证伪的项（UNKNOWN）

| 项 | 为什么证不了 |
|---|---|
| 变更面（是否越界改 `rules/**` / `conftest.py` / `verify.py` / `scripts/guard/**` / 设计区） | 硬约束**禁止我执行任何 `git` 命令**（`git log --name-only` 不可用）。旁证：`rules/*.yaml` 全 0444 且 mtime 均 ≤ 2026-09-16 00:00，compute 目录内无写 `rules/` 的代码路径；但**无法给出"本批次未改"的提交级证据** → 记 UNKNOWN |
| 82 用例的断言强度是否覆盖全部算子 | 我只逐行读了 `test_store/test_step_wiring/test_driver_real_run` 全文与其余文件的用例名清单；`test_operators/test_returns/test_valuation` 的函数体未逐行读完 → 这三文件的**逐断言强度**记 UNKNOWN（其"82 passed"复现结论不受影响） |
| G1-05 空执行判据在 step5 真接入后的实际表现 | 需改共享 `pipeline.py`（硬约束禁止改码）→ 只能用 C-03 的等价推理 + `pipeline.py:321` 逐字读证，未做端到端演示 |
| V-06（新测试目录必须新增批次）／`steps 4/5/6` 完整处理器（模型侧假设生成） | 前者未跑全量验证（V-01 禁止）故未核；后者属阶段②③、本批次不存在，无法审 |

## §7 审计过程自述

**读过**：`ws_compute_dod.md`（全）、`ws_compute_report.md`（全）、`00_开发Agent开工提示词.md`（§一/§5.1/§六/§七/§八/§九）、`system/CONVENTIONS.md`（R-01~06/P-01~05/G-01~07）、`scripts/compute/` 全 13 文件（逐行：contract/store/driver/returns/core/shares/fx/growth/valuation/step/run_derived；扫读：margin/`__init__`）、`tests/compute/` 中 `conftest.py`/`test_store.py`/`test_step_wiring.py`/`test_driver_real_run.py` 全文 + 其余 6 文件用例清单、`scripts/orchestrate/pipeline.py`（75-185、300-342）、`scripts/trace/traceback.py`（全）、`scripts/benchmark/return_guard.py`（全）、`schema/store.py`（150-205）、`schema/models.py`（348-413）、`rules/banned_tokens.yaml`/`rules/benchmark.yaml`/`rules/freeze.yaml`/`rules/pipeline.yaml`、设计区 `09_需求拆解与实现方案_v1.md`（343/570-600/659-700/744-800）、`03_覆盖范围与基准/02_实现方案.md:117+`、`04_公司价值研究与深度标准/02_实现方案.md:214+`、`05_价格与市场预期研究/02_实现方案.md:86/162-215`。

**跑过**（全部串行、broker 关、单命令 ≤60s）：P1 全流程（1）；P2 驱动层 5 场景 CLI（5）+ 算子层 17 例 + 非法 price + 巨值；P3 全树 `grep`（3）+ 仓库真源 `--no-persist`（1）；AC-04 `return_guard` CLI（4）+ `--strict`（3）+ 完整性违例（1）；AC-06 边界；AC-07 主扫描（1）+ 非真空/免扫对照（3）+ 判别力矩阵（8 形态）；幂等/上游重述（2）；`_find_derived` 可达性（1）；`step.handler` 语义（4 调用）；`sh system/scripts/ops/run_pytest.sh tests/compute` → `82 passed in 4.25s`（1，**未跑全量**）。

**未看**：`test_operators/test_returns/test_valuation/test_contract/test_package_laziness/test_return_guard_wiring` 的函数体逐行；`margin.py`/`__init__.py` 逐行；`scripts/_common.py` 与 `run_all_gates.py` 全文（仅确认相关两处）；`ws/graph`/`ws/claim`/`ws/decision`（不在本次范围）。

**合规声明**：仅写入本报告 `system/reports/ws_independent_audit_compute.md`；未执行任何 `git` 命令；未改动任何源码/测试/夹具/配置/设计文档；未联系其他成员；临时探测根 `system/tests/.audit/compute/**` 已**整体删除**（`ls system/tests/.audit` → `No such file or directory`）；仓库真源零污染（`system/derived/` 仅 `.gitkeep`；`facts/` 仍 18 个 JSONL，`prices.jsonl`/`benchmarks.jsonl` 均 0 行；`registry/corporate-actions.jsonl` 仍 0 字节）。
