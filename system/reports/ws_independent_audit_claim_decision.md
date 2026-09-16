# `§九` 独立审计 — 批次 7（`fix/claim-propagation` + `ws/decision`）

- **审计员**：独立审计员-2（对抗性、换人视角；不采信实现方完成声明）
- **审计对象**：`fix/claim-propagation`（`69f485b`，已并入 `main`，merge `436df2d`）· `ws/decision`（`2f7f243`，已并入 `main`）· 集成 `I-1`（`530c3cd`）
- **判分基准**：`reports/ws_claim_dod.md`（§D 新增 `AC-N2-1~6`）· `reports/ws_decision_dod.md`（AC-01~AC-08）
- **环境**：`CODEBUDDY_SAFE_DELETE_SANDBOX=0` / `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`；`python=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`
- **方法**：全部 raw CLI / 短脚本；**未运行 pytest**（`conftest.py::pytest_sessionstart` 清空 `tests/.work/`，与另一审计员并发必互删夹具）
- **真源保护**：写入型探测一律在副本 `system/tests/.audit/batch7_claim_decision/`（收尾整目录删除）；真仓库 `facts/` 18 文件行数与探测前**逐一致**（15 个 0 行 + `industry_nodes.jsonl` 44 行）

---

## §0 结论摘要

### A. `fix/claim-propagation` —— **accepted**（`N-2` 阻断级缺陷已根治）

| 条 | 判定 | 一句话依据 |
|---|---|---|
| `N-2-a/b` 签名 + 返回形状 | **FIXED** | 真实签名 `(code_root, start, *, max_depth, source, edges, known_refs, valid_asof)`；旧形 `forward_closure('c1', max_depth=3, detect_cycle=True)` **仍抛** `TypeError`（证明旧码必死），新路径真跑通 `downstream=['b1','r1']`（`list`，graph 口径裸 ref） |
| `N-2-c` 先写后传播 | **PARTIAL** | 解析/预飞（`apply=False`）确已前移到 `_append_claim` 之前 → 解析类失败**零写入**（★复原对照已证判别力）；`apply=True` 的 **I/O 残留窗口**客观存在且**如实登记为 `R-04`、未称"原子"**（docstring:54-57 + DoD §B:126-128 + 报告 §7.4 + 专门用例钉住） |
| `N-2-d` 重复幂等键 | **FIXED** | 全库只剩 3 段键 `recheck::<ref>::<target>`（实测落库键 `recheck::c1::b1` / `recheck::c1::r1`）；旧 4 段键载体 `_propagate`/`_normalize_ref`/`_append_recheck_task`/`resolve_forward_closure`/`_RECHECK_OBJECT_TYPES`/`_GRAPH_CANDIDATE_MODULES` 在 `transition.py` 中**出现 0 次** |
| `G-15` 自建遍历/入队 | **FIXED** | `transition.py` 中 `tarjan`/`queue`/`deque`/`def _walk` 均 0 次；**只有 3 处** `prop`/`propagate_retraction` 调用（`as prop` 导入 + `apply=False` + `apply=True`）→ **真复用**而非复制（`G-06`） |
| `G-16` 吞参数测试桩 | **FIXED** | `_closure_fn` 出现 0 次；现存 `_boom`/`_fail_on_apply` 仅用于**失败注入**（正当）；新增**不注入**的真实路径用例 `test_superseded_real_path_enqueues_graph_recheck`，★复原对照已证其判别力 |
| `G-22` DoD `active` 别名/迁移表过期 | **FIXED** | `ws_claim_dod.md:140`（C-4 行）已改为"默认值**已为** `pending_verification`，`active` **已非合法取值**"（`5c5d033`）；全文余下 `active`/`detect_cycle`/`requires_recheck` 命中**全部**为「修复后叙述」或显式标注**过期**（:111-113/:123/:153/:170-175），无残留过期表述 |

→ **FIXED 5 / PARTIAL 1 / NOT-FIXED 0 / UNKNOWN 0**

### B. `ws/decision` —— **merged-but-not-accepted**（最严重项：空仓库伪造产物）

| AC | 判定 | 一句话依据 |
|---|---|---|
| AC-01 真跑通 | **PARTIAL** | 真 CLI `exit 0` + 输出 JSON 含 `action/recommendation_id` + 真落 1 行 `Recommendation`；收益确由 `compute_total_return` 真算（`formula/operands/method_version` 齐）——**但**门输入 `research_depth="tracking"`/`baseline_complete=True`/`JudgmentChange(True)` 是 `run_decide.py:186-197` 的**硬编码字面量**，非从真源读 → "研究完成"前置门**未被真验** |
| AC-02 持久化 | **PASS** | P1 实测：真源 sha256 `379a6721…099e` → **删整个 `index/`** → `rebuild_index()` → 重读仍 1 行、`model_validate` 通过 → 重建后 sha256 **逐字节相同** |
| AC-03 真接线 | **PARTIAL** | 接线**真实存在且唯一**：`pipeline.py:142 → chain_steps.py:246 → scripts.decision.step::make_decision_handler`（`G-06` 无第二套）；**但**该处理器在**完全空**的仓库上返回 `produced=['rec-usDEMO-2026-04-01']`、`degraded=False`、`incomplete_reason=None`、`signals_emitted=1`，并把一条 `buy` 建议**真写进 `facts/recommendations.jsonl`** —— 违反 `§一 底线 3`（不伪造产物）与 `chain_steps.py` 自订线上 27-28 行 |
| AC-04 守卫真拦得住 | **PASS** | 裸数字底稿 → `RawNumberRejected` 且 `decide()`→`None`；★反注入 `moat_required`/`min_confidence`/`threshold` → `assert_gate_input.py` **exit 1**（移除即回 exit 0）；★反注入 `weight`/`score` → `conflict_scan.py --timing ci` **exit 1**（同件放 `scripts/compute/` → exit 0）；`freeze_guard.py` 扫 `decision_scope_files_scanned:13` → exit 0 |
| AC-05 错误路径 | **PARTIAL** | `boundary_unresolved`（`pending`/`boundary_unresolved`）与 R8（`pending`/`uncertain`）**实测分离**、均 `is_new_signal=False`；"无法判断 ≠ 卖出"成立；门拒绝 → `None`；三要素缺项 → `EarlyJudgmentIncomplete` —— **但** `Ch7 §D.7:418` 的"同版本写入"断言被条件化为**生产恒 no-op**（见 AC-08） |
| AC-06 边界 | **PASS** | 空深度→`UnknownResearchDepthError`；`low>high`→`ReturnRangeError`；`Decimal("1e18")` 正常判定 `positive`；`tier='bogus'`→`UnknownTierError`；`importance='bogus'`→`UnknownImportanceError`；`horizon='2y'`→`HorizonOutOfRange`，`1q/2q/1y` 边界含；naive `first_seen_at` 归一 UTC 后**全序可比** |
| AC-07 无占位符 | **PASS** | `no_placeholder_guard.py system --fail-on warn` → `exit 0`（117 文件）；手工 grep `TODO/FIXME/HACK/待实现/占位/NotImplemented/pass$/except: pass/...` 于 `scripts/decision/**` → **0 命中**（含注释与 docstring） |
| AC-08 设计对齐 | **PARTIAL** | 锚点**逐条真实存在且内容对得上**：`Ch6 §B.2`(:140) 伪码与 `triage.py` **逐字同构**（含 `TIER_RANK`/`IMPORTANCE_RANK`/`BUDGET_MAP={40,15,4}`/`independent_evidence_count>=1`）、`§B.3`(:188)、`§E.1~§E.5`(:329/349/359/367/384)、`Ch7 §D.1~§D.7`(:310/320/353/364/372/395/404)、`Ch9 §3.4.3`(:668)/`§3.4.7`(:725)/`§3.5`(:772)、`rules/freeze.yaml::p04` `range:[1Q,1Y]`；`RecommendationInput` 无 `relations`（实测字段 `['company_id','baseline','stock_forecast','benchmark_forecast','own_evidence']`）—— **但** `§D.7` 第 418 行断言在生产**不可满足**（见 §5-11） |

→ **PASS 4 / PARTIAL 4 / FAIL 0 / UNKNOWN 0**（另有 5 项 UNKNOWN 见 §7，均**未**写成 PASS）

---

## §1 ★ 复原对照（证明新测试有判别力，非"顺手加恒真断言"）

> 我**被禁止**运行 pytest，故以**复刻被测用例的断言**在一次性副本上做对照：把修复**改回旧写法**，
> 用**同一段**探测代码跑，比较行为差异 = 「该用例会不会变红」。

### 对照 1 — `test_superseded_parse_failure_writes_nothing`（断言：零写入）
- **改动的那一行**：`transition.py:397` `prop(root, claim_ref, source=_EDGE_SOURCE, apply=False)` → 删除（恢复旧写序「先 `_append_claim` 后传播」）
- **同一场景**：真源 `c1→b1→r1`；注入 `propagate_fn=_boom`（干跑即抛）

```
  [修复版（当前 transition.py）]
    注入 propagate_fn=_boom（干跑时抛错）
    outcome        : RuntimeError: 解析阶段爆炸（模拟闭包/索引/ref 解析抛错）
    claims 新增行数: 0     tasks 行数: 0
    历史行逐字节未变: True
    → 用例断言（零写入）: 成立 → 绿

  [复原版（删干跑=旧写序）]
    outcome        : RuntimeError: 解析阶段爆炸（模拟闭包/索引/ref 解析抛错）
    claims 新增行数: 1     tasks 行数: 0
    → 用例断言（零写入）: 不成立 → 变红   ★ 判别力已证（本条会红）
```
→ **判别力成立**：该用例真能抓住"先写后传播"的半数据窗口。

### 对照 2 — `test_superseded_real_path_enqueues_graph_recheck`（断言：graph 口径 `recheck` 键）
- **改动的那一处**：把委托调用换回旧签名 `list(forward_closure(claim_ref, max_depth=3, detect_cycle=True))`

```
  [修复版（当前 transition.py）]
    outcome: recheck_tasks=['task_recheck::c1::b1', 'task_recheck::c1::r1']
    tasks 行数: 2
    → 用例断言: 成立 → 绿

  [复原版（旧调用形态 detect_cycle）]
    outcome: TypeError: forward_closure() got an unexpected keyword argument 'detect_cycle'
    tasks 行数: 0
    → 用例断言: 不成立 → 变红 ★ 判别力已证
```
→ **判别力成立**：该用例真能抓住 `N-2-a` 的签名错位（旧桩吞参数导致的漏网路径已封）。

---

## §2 `N-2-a/b/c/d` + `G-15`/`G-16`/`G-22` 原始证据

```
$ python probe_n2.py
真实签名 : (code_root: 'str | Path', start: 'str', *, max_depth: 'int' = 3,
            source: 'str' = 'dependency_edges', edges: ..., known_refs: ..., valid_asof: ...) -> 'ClosureResult'
ClosureResult 可迭代? False
返回类型       : ClosureResult
reached        : ('b1', 'r1')

复现旧代码路径 `forward_closure('c1', max_depth=3, detect_cycle=True)`：
  TypeError: forward_closure() got an unexpected keyword argument 'detect_cycle'

──────── 新 transition 真实路径（不注入任何桩）────────
  from->to        : pending_verification -> superseded  recorded_seq=2
  downstream      : ['b1', 'r1']   (类型 list)
  recheck_tasks   : ['task_recheck::c1::b1', 'task_recheck::c1::r1']
  rolled_back     : ['CO1']
  claims.jsonl 历史行逐字节未变?  True
  tasks.jsonl 行数: 2
    task_recheck::c1::b1   key=recheck::c1::b1   reason=dependency_stale  status=queued
    task_recheck::c1::r1   key=recheck::c1::r1   reason=dependency_stale  status=queued

──────── N-2-c 残留窗口：apply=True 落地失败 ────────
  调用序 apply 参数: [False, True]（先干跑后落地）
  after : claims=2  tasks=0  -> 残留=True（R-04 已登记，非「原子」）
  最后一行 status: superseded

──────── 干跑（apply=False）零写入独立验证 ────────
  干跑前: {'tasks': 0, 'companies': 1}
  干跑结果: downstream=('b1','r1') recheck_targets=('b1','r1') rolled_back=()
  干跑后: {'tasks': 0, 'companies': 1}  <- 与干跑前相同 = 干跑零写入 ✓
  落地后: {'tasks': 2, 'companies': 2}  created=('task_recheck::c1::b1','task_recheck::c1::r1') rolled=('CO1',)

──────── N-2-d / G-15：`transition.py` 旧载体出现次数 ────────
  'recheck::' : 1   'requires_recheck' : 1（docstring 叙述）   '_normalize_ref' : 0
  '_append_recheck_task' : 0   'resolve_forward_closure' : 0   '_RECHECK_OBJECT_TYPES' : 0
  '_GRAPH_CANDIDATE_MODULES' : 0   'detect_cycle' : 0   '_propagate' : 0   '_closure_fn' : 0
  'tarjan' : 0   'queue' : 0   'deque' : 0   'def _walk' : 0
  委托调用点: ['from scripts.graph.propagate import propagate_retraction as prop',
               'prop(root, claim_ref, source=_EDGE_SOURCE, apply=False)',
               'applied = prop(root, claim_ref, source=_EDGE_SOURCE, apply=True)']
```
**N-2-c 残留窗口的登记核查（是否被吹成"原子"）**：`transition.py:54-57` 明写「★ **诚实登记的残留窗口**（`R-04`，**不称为"原子"**）：第 3 步与第 2 步是**两次独立写盘**…本模块**无法**消除该窗口」；DoD `§B:126-128` 同口径；报告 `§7.4` 以 `wc -l` before/after 贴出 A（零写入）/B（有残留）两态；并有专门用例 `test_superseded_residual_io_window_is_honest` **钉住**该行为。→ **未吹成原子，登记如实**。

**`G-22` 残留过期表述逐行核查**：`ws_claim_dod.md` 全文 `active` 命中 4 处（:112 历史违约值一律拒绝 / :113 取代 v1 的 active 别名表 / :140 已为 pending_verification），`detect_cycle` 命中 2 处（:153 /:175，均标为**旧实现/过期**），`requires_recheck` 命中 3 处（:123 不自造该字段 /:170-172 契约文本过期登记）。→ **无残留过期表述**。

---

## §3 `ws/decision` 逐条 AC 证据要点

| AC | 关键原始证据 |
|---|---|
| AC-01 | `$ run_decide.py <rootB> --stock-prices …/demo_stock_prices.jsonl --benchmark-prices …/agix_prices.jsonl` → `{"action":"buy","degraded":false,"gaps":[],"recommendation_ids":["rec-usDEMO-2026-04-01"],"signals_emitted":1}` `EXIT=0`；落库行含 `evidence_version_ids=["dv-total_return-co-demo-compute-v1"]`、`change_reason="meets_buy_conditions"`。**扣分点**：`run_decide.py:186-197` 的 `ResearchBaseline(..., research_depth="tracking", baseline_complete=True)` 与 `JudgmentChange(fact_set_changed=True)` 为字面量 |
| AC-02 | 见 §4-P1 |
| AC-03 | `grep -rn` 全树：生产调用方**唯一链** `pipeline.py:142 → chain_steps.py:246/267 → decision.step::make_decision_handler`；无第二套实现。**扣分点**见 §0-B-AC-03 与 §4-P3 |
| AC-04 | 见 §0；四项子判据逐项有 exit 码 |
| AC-05 | `boundary_unresolved`→`('pending','boundary_unresolved')`；R8→`('pending','uncertain')`；R3→`('pending','uncertain')`；R4→`('maintain','active',is_new_signal=False)`；R1→`('buy','active',True)`；R2→`('sell','confident_underperform',True)` |
| AC-06 | 见 §0 |
| AC-07 | `no_placeholder_guard.py`（117 文件）`RESULT: PASS（0 violations）` `EXIT=0`；手工 grep 0 命中 |
| AC-08 | 见 §0 |

`Ch7 §D.4` 信号语义实测（`signals_emitted = 1 if is_new_signal else 0`）：
```
  R1 绝对正+相对跑赢  -> buy       active                 is_new_signal=True   signals_emitted=1
  R2 相对跑输         -> sell      confident_underperform is_new_signal=True   signals_emitted=1
  R3 相对不确定       -> pending   uncertain              is_new_signal=False  signals_emitted=0
  R4 判断未变         -> maintain  active                 is_new_signal=False  signals_emitted=0
  R8 负绝对+相对跑赢  -> pending   uncertain              is_new_signal=False  signals_emitted=0
```
→ `maintain`/`pending` **不产新信号**，与 `Ch7 §D.4` 一致。

---

## §4 三项探测原始证据

### P1 — write-read-reload（`facts/` 是真源、`index/` 可重建）：**PASS**
```
$ shasum -a 256 rootB/facts/recommendations.jsonl
379a67214c20a9ddca90b10ccfcf133812d9f052b96f9235ef3059afe7ae099e
$ sqlite3 → objects total: 1 / recommendations: 1
$ rm -rf rootB/index          → index/ 已删除
$ rebuild_index('rootB')      → rebuild_index -> …/rootB/index/facts.sqlite
    read_records(recommendations) 行数 = 1
    recommendation_id = rec-usDEMO-2026-04-01
    model_validate -> Recommendation rec-usDEMO-2026-04-01 RecommendationAction.buy RecommendationStatus.active
$ shasum -a 256 rootB/facts/recommendations.jsonl
379a67214c20a9ddca90b10ccfcf133812d9f052b96f9235ef3059afe7ae099e   ← 逐字节相同
```

### P2 — 让缺失层响亮失败：**PASS**（无静默空建议 / 无默认值）
```
$ run_decide.py … --stock-prices /tmp/nope.jsonl …
[INPUT-ERROR] run_decide: FileNotFoundError: 行情文件不存在: /tmp/nope.jsonl
EXIT=2

$ run_default(<空 root>)  → FileNotFoundError: …/rootA/facts/recommendations.jsonl  （响亮，非静默）
$ require_derived_worksheet(worksheet=0.1)
  → RawNumberRejected: 收益底稿必须是 DerivedValue（带 formula + operands + method_version），实得 float
$ research_complete(position_listed / baseline_complete=False) → False ; decide(...) → None
$ research_complete(research_depth='')  → UnknownResearchDepthError
```
**★ 但反向发现**：`run_decide` 不创建 `facts/` 目录 —— 传一个**尚不存在 `facts/` 的 root** 时 CLI `exit 2`（`FileNotFoundError`，非"亮丽拒绝"意义上的设计缺陷，但构成真实前置条件未登记）。

### P3 — 接线体检（`scripts/decision/**` 的生产调用方）：**接线真实，但口径错**
```
$ grep -rn "scripts.decision|make_decision_handler|decision.step" system --include=*.py --include=*.sh
system/scripts/orchestrate/chain_steps.py:246: from scripts.decision.step import make_decision_handler
system/scripts/orchestrate/chain_steps.py:267:     make_decision_handler(root, step_no=6),
system/scripts/orchestrate/pipeline.py:142:    register_chain_steps(self)
（其余命中为 report / tests / checks / rules 的**被检路径声明**，非调用方）

$ 真仓库态等价 rootE（18 个 JSONL 全 0 行 + rules/）全 8 步 run_daily：
blocked = True | degraded = True | signals_emitted = 1
  step 1 ingest_public_information                    status=ok       produced=[]
  step 2 trace_dedup_verify                           status=gap      produced=[]
  step 3 update_company_and_industry_relations        status=gap      produced=[]
  step 4 revise_growth_and_moat_judgment              status=gap      produced=[]
  step 5 update_financial_and_valuation_assumptions   status=gap      produced=[]
  step 6 compare_company_vs_benchmark_expected_return status=ok       produced=['rec-usDEMO-2026-04-01']
  step 7 publish_recommendations                      status=gap      produced=[]
  step 8 continuous_verification_and_history          status=gap      produced=[]

facts/recommendations.jsonl  1 行
   rec-usDEMO-2026-04-01 buy active | security= usDEMO | start= 2026-04-01 | ev= ['dv-total_return-co-demo-compute-v1']
facts/benchmarks.jsonl       0 行   ← step 6 声明 produces=[benchmarks, recommendations]，实际只产 1 项
```
**该处理器忽略 `run_date` 与 `scope`**（`step.py:46 def handler(_run_date, _scope)`），其输入来自 `run_decide.py:53-54` 的**仓库内测试夹具绝对路径** `DEFAULT_STOCK_PRICES/_BENCHMARK_PRICES`，与传入的 `root` **无关**。

---

## §5 对抗性缺陷清单（逐项）

| # | 检查项 | 结论 |
|---|---|---|
| 1 | 自报偏松（"工厂存在/CLI 存在"说成"已接线"） | **未见此向偏松**（自报 PARTIAL，实测反而**已真接线**）；但**新命中反向问题**：接线后 `produced`/`degraded` 语义在空输入下**被证伪**（§4-P3）→ 计入 §6 `P7-1` |
| 2 | `P-09`/纪律 1：决策域禁词 + 参数不得内置阈值 | **已查、无**。`conflict_scan --timing ci` → `PASS（0 violations）`；★反注入具判别力（`weight`/`score` 入决策域→`exit 1`；同件入 `scripts/compute/`→`exit 0`）。`BUDGET_MAP={40,15,4}`、`independent_evidence_count>=1` 经核对 `Ch6 §B.2:149/167` 为**设计逐字字典表**，**非**新增阈值。`rules/freeze.yaml::p04` 真实存在（`range:[1Q,1Y]`）；`freeze_guard.py` → `decision_scope_files_scanned:13` `exit 0` |
| 3 | `RecommendationInput` 不得含 `relations` | **已查、无**。实测字段 `['company_id','baseline','stock_forecast','benchmark_forecast','own_evidence']` |
| 4 | `DerivedValue` 强制 | **已查、真强制**。`require_derived_worksheet` 对裸数字抛 `RawNumberRejected`；`_forecast_is_explainable` 亦要求 `isinstance(worksheet, DerivedValue)` 且 `formula and operands` 非空 |
| 5 | `Ch7 §D.4`：`signals_emitted` 只计 `buy`/`sell` | **已查、符合**（§3 实测表） |
| 6 | 测试断言弱化（退出码/行为 vs "返回了列表"） | **命中（弱化）**：`tests/claim` 的断言基本是**行为/退出码**级（`recheck_tasks` 集合、`tasks.jsonl` 行数、`startswith(before)`、CLI `exit 1/2`）——尚可；**但** `ws/decision` 的 AC-02 自订断言「再次追加 → 2 行（**append-only**）」把**重跑重复落库**这一缺陷**写成了期望**（见 #11 与 §6 `P7-4`） |
| 7 | 空包假绿（`G-03`） | **命中**：`make_decision_handler` 在**零证据仓库**上产出 `produced=['rec-…']` + `degraded=False` + `incomplete_reason=None`（§4-P3）。`_declare_incomplete_when_empty` 的 `if not outcome.produced` 分支**永远不会**在夹具存在时触发 → 空包被当"有产出" |
| 8 | `R-06` 违例（关键词/名单式判据） | **命中（既有，非本批次引入）**：`chain_steps.py:43-53` 自记——`no_placeholder_guard.py` 的 `PLACEHOLDER-CN` 是**关键词式**规则且为**硬门禁**，导致"运行时缺口文案不许直白写明未交付"，自认为缺口 `G-27`。本批次未变，**与 `R-06 ①/④` 冲突未解** |
| 9 | 占位符（含注释/docstring） | **已查、无**。门禁 `exit 0` + 手工 grep `scripts/decision/**` 0 命中；`chain_steps.py` 用「属阶段②③/本批次未交付」措辞**规避**该关键词规则（信息量不减，但属 #8 的张力症状） |
| 10 | 纪律 9/10（改 `rules/**`、设计区、`conftest.py`、`CONVENTIONS.md`、`guard/**`） | **已查、无越界**。`69f485b`：仅 `reports/ws_claim_dod.md`+`ws_claim_report.md`+`scripts/claim/transition.py`+`tests/claim/test_transition.py`。`2f7f243`：仅 `reports/ws_decision_*`+`scripts/decision/**`+`tests/decision/**`。`530c3cd`（集成）：`chain_steps.py`+`pipeline.py`+`tests/injection/**`+`verify.py`（1 行，批次登记） |
| 11 | `Recommendation` 无 `trio_written_seq` → 断言条件化是否失去判别力 | **命中（失去判别力）**。设计 `Ch7 §D.7:418` 为**无条件** `assert rec.trio_written_seq <= rec.version_seq`；实现 `gate.py:252-257` 条件化为 `if trio_seq is not None and version_seq is not None`。实测 `Recommendation` **无** `trio_written_seq`（有 `version`、无 `version_seq`），且 `build_recommendation` 传入的是 `SimpleNamespace(assumptions, evidence_gaps, verification_conditions)`（`rules.py:332-337`）→ `trio_seq` **恒 `None`** → 该断言在生产路径**恒 no-op（死断言）**。DoD:97 已如实登记此条件化，但未标为"生产不可满足" |

---

## §6 缺口清单（建议并入 `phase1_gap_register.md`）

| ID | 缺口 | 严重度 | 证据 |
|---|---|---|---|
| `P7-1` | **step 6 在零证据仓库上产出"真建议 + `signals_emitted=1` + `degraded=False`"**，违反 `§一 底线 3`（不伪造产物）与 `chain_steps.py:27-28` 自订线 | **阻断** | §4-P3；`step.py:52-57`、`chain_steps.py:213-223` |
| `P7-2` | `run_decide.run_default` 把**仓库内测试夹具**（`tests/decision/fixtures/demo_stock_prices.jsonl`）硬编码为**生产输入**，且完全忽略传入 `root` | 高 | `run_decide.py:53-54,223-234` |
| `P7-3` | `make_decision_handler` 忽略 `run_date`/`scope`（签名接受但不用）→ 建议 `start_date` 恒为夹具窗口 `2026-04-01`，与 run_date 无关 | 高 | `step.py:46,51`；§4-P3 `start=2026-04-01` |
| `P7-4` | `Recommendation` 无幂等键：同窗口重跑**追加重复 `recommendation_id`**，`version` 恒 1、`recorded_seq` 恒 `None` → `as_of` 版本链对 `recommendations` 不可用 | 高 | 连跑 2 次 → 5 行全为同 id/`version=1`/`recorded_seq=None`；DoD AC-02 把该行为写成期望 |
| `P7-5` | `Ch7 §D.7:418` "同版本写入"断言在生产**恒 no-op**（`Recommendation` 无 `trio_written_seq`） | 中 | §5-11 |
| `P7-6` | `run_decide` 不创建 `facts/`；`root` 无 `facts/` → CLI `exit 2` `FileNotFoundError`（前置条件未登记） | 低 | §4-P2 |
| `P7-7` | step 6 声明 `produces: [benchmarks, recommendations]` 但跑 `ok` 时 `benchmarks.jsonl` 仍 0 行；`assert_steps_complete` 只校验 `produced` 非空，**不校验 `produces` 齐备** | 中 | `rules/pipeline.yaml:45`；§4-P3 |
| `P7-8` | `transition.py` 仍**零生产调用方**（`claim` AC-03 未闭合；`I-1` 只接 step 1–6，未接 claim 迁移） | 中 | §2 全树 grep 无命中 |
| `P7-9` | `pre-commit.sh` 仍未收录 `graph_integrity_guard` / `locator_check`（`run_all_gates.py:52-53` **已收录**）→ `G-07` 半闭合 | 低 | `grep -n` pre-commit.sh 无命中 |
| `P7-10` | `R-06 ①` 张力未解：`no_placeholder_guard` 关键词规则作硬门禁，逼出委婉语（`chain_steps.py:43-53` 自记 `G-27`） | 中 | §5-8 |

`N-1`（`read_records` 静默 `return []`）本单**未复测**（属 `fix/truth-source-loud`，我已见 `5c5d033` 新增 `truth_source_status` 三态与 `FileNotFoundError`，但**未**独立验收 —— 见 §7-U-6）。

---

## §7 未能证伪的项（UNKNOWN，**禁止**写成 PASS）

| ID | UNKNOWN | 原因 |
|---|---|---|
| `U-1` | `tests/claim`（24）、`tests/decision`（86）、`tests/injection` 的用例数与全绿 | **禁跑 pytest**（与另一审计员并发互删 `tests/.work/`）。已用**等价脚本**复刻关键断言（§1）作替代，但"用例计数/整体绿灯"本单**无法自证** → 需 pytest 通道，请主理人转派 |
| `U-2` | `test_superseded_residual_io_window_is_honest` 对"防误当原子"的**长期**效力 | 该用例依赖注入桩；我以同形态脚本复现了行为，但未走 pytest 夹具链 |
| `U-3` | `run_decide.py` 在 `<code_root>=system`（真仓库）上的实跑 | **故意不做**（会污染真源 `facts/recommendations.jsonl`）；以真仓库态等价副本 `rootE`（18 个 JSONL 全 0 行）替代 |
| `U-4` | `R5` 的"强制复查后**重新判断**"（设计 `Ch7 §D.1:318`） | 下游消费者（第八章/第十章）未交付；本层只置 `recheck_required`，**重判环节无法端到端复核** |
| `U-5` | 决策层→展示层口径（`views/**`） | `conflict_scan` 自报 `L5_SKIPPED_NO_VIEW_CONFIG（views/** 三入口于阶段④ 交付）` → L5 层无被检对象，**未验证** |
| `U-6` | `fix/truth-source-loud`（`G-17`）的实际闭合性 | **不在本单范围**（派给另一审计员/另一单）；我仅观测到 `5c5d033` 的存在与 step 2/3 因真源缺失 `failed`，未做独立验收 |

---

## §8 审计过程自述

**读了**：`reports/ws_independent_audit_graph_claim.md`（上轮报告）· `reports/ws_claim_dod.md` · `reports/ws_claim_report.md`（§七）· `reports/ws_decision_dod.md` · `reports/ws_decision_report.md` · `reports/batch6_fix_taskbook.md`（§1）· `scripts/claim/transition.py`（529 行）· `scripts/graph/propagate.py` · `scripts/graph/closure.py`（签名）· `tests/claim/test_transition.py`（585 行）· `scripts/decision/{triage,gate,rules,step,run_decide}.py` · `tests/decision/*`（目录与用例名）· `scripts/orchestrate/{pipeline,chain_steps}.py` · `scripts/checks/{assert_gate_input,conflict_scan}.py`（按需）· `scripts/ops/{run_all_gates,pre-commit.sh}` · `rules/{pipeline.yaml,freeze.yaml,banned_tokens.yaml}` · 设计区 `06_公开信息与证据筛选/02_实现方案.md §B.2~§B.4/§E.1~§E.5`、`07_产业链传导与股票建议/02_实现方案.md §D.1~§D.7`、`09_数据与实现约束/…_v1.md §3.3.3/§3.4.3/§3.4.6/§3.4.7/§3.5`。

**跑了**（全部 raw CLI，均 ≤60s）：`run_decide.py` 真跑（rootA/rootB/rootC）· `propagate_retraction` 干跑/落地 · `transition(...)` 真路径与注入路径 · `Pipeline.run_daily` 全 8 步（rootD 无真源 / rootE 真仓库态等价）· P1 删 `index/` 重建 + sha256 · `conflict_scan --timing ci`（含反注入）· `freeze_guard` · `no_placeholder_guard --fail-on warn` · `assert_gate_input`（含反注入）· `git log/show --stat`（**只读**）· 3 个自建探测脚本（`probe_n2.py` / `probe_restore.py` / 内联 `-c`）。

**未看 / 未做**：未运行 pytest（禁）· 未跑 `scripts/ops/verify.py` 全量 · 未审 `scripts/guard/**`（批次 4 已两轮审计，禁改）· 未审 `ws/compute`（另一审计员同批次）· 未做 git 写操作（无 add/commit/branch/checkout/stash/merge）· **未改动仓库任何文件**（复原对照只用 `system/tests/.audit/batch7_claim_decision/copies/` 下副本）。

**真源核验**：探测前 `system/facts/*.jsonl` 18 文件（15 个 0 行 + `industry_nodes.jsonl` 44 行）；全部写入型探测在副本 root 上完成；收尾已 `rm -rf system/tests/.audit/batch7_claim_decision`。

**判定汇总**：`fix/claim-propagation` **accepted**（FIXED 5 / PARTIAL 1）；`ws/decision` **merged-but-not-accepted**（PASS 4 / PARTIAL 4 / FAIL 0），最严重为 `P7-1` step 6 空仓库伪造产物。
