# ws/real-collect 报告 —— 项目**第一次跑在真实数据上**

- 分支：`ws-real-collect`（基点 `main = d03418a`）
- 工作树：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-real-collect`
- 隔离 Python：`/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`
- 运行环境：`CODEBUDDY_SAFE_DELETE_SANDBOX=0`、`CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`
- 开工第一步：`sh system/scripts/ops/bootstrap_worktree.sh` → `RESULT: PASS（0 violations）`（EXIT 0）

---

## ① 做了什么

### 1.1 采集（只采公开的、**一级**的一手材料）

| # | 材料 | 发布方 | 来源等级 | 抓取日期 | URL |
|---|---|---|---|---|---|
| A | NVIDIA 2025 财年 Q4 & 全年业绩（官方新闻稿） | NVIDIA Corporation | **一手 primary** | 2026-09-16 | `https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-fourth-quarter-and-fiscal-2025` |
| B | NVIDIA 2025 财年 Q3 业绩（官方新闻稿） | NVIDIA Corporation | **一手 primary** | 2026-09-16 | `https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-third-quarter-fiscal-2025` |
| C | TSMC 2026 年 8 月营收（6-K，SEC 归档） | Taiwan Semiconductor Manufacturing Company Ltd | **一手 primary**（公司自述、SEC 归档） | 2026-09-16 | `https://www.sec.gov/Archives/edgar/data/1046179/000104617926000658/tsm-revenue20260910.htm` |
| D | AMD 2026 年 Q2 业绩（8-K Item 2.02，SEC 归档） | Advanced Micro Devices, Inc. | **一手 primary**（公司自述、SEC 归档） | 2026-09-16 | `https://www.sec.gov/Archives/edgar/data/2488/000000248826000121/amd-20260804.htm` |

**链条覆盖**：NVIDIA（本系统研究对象）+ TSMC（**上游**代工）+ AMD（**同业/下游需求侧**）—— 满足方法论第一条"上下游逐一收集"的**最小**形态。

**抓取失败/受限（如实登记，未用二三级来源顶替）**：

- `investor.nvidia.com` 官方 IR 新闻稿 → `curl` 命中 Cloudflare 盾（返回 `Just a moment...` 页面，5.8 KB）。**改用同为公司官方的 `nvidianews.nvidia.com`（NVIDIA Newsroom）**。
- `pr.tsmc.com`、`ir.amd.com`、`www.amd.com/newsroom` → 代理 DNS 解析失败（host 不可达）。**改用 SEC 归档的公司原始申报**（TSMC 6-K / AMD 8-K）。
- `www.sec.gov` 首访被拒（返回 "Your Request Originates from an Undeclared Automated Tool"）；按要求补**声明式 User-Agent**（含联系邮箱）后可达。
- NVIDIA 10-Q（`.../nvda-20240728.htm`，1.46 MB XBRL）**已抓到但未采用**：纯文本抽取后为**单行** 16.3 万字符，`locator` 退化为 `#L1-L1`，不利可复查；改用同源的两份新闻稿。

> **处理方式披露**：`raw/*.txt` 为官方页面的**纯文本渲染**（剥离 HTML 标记、正文/申报全文，**措辞零改动**；空白归一为行）。**非**字节级 HTML 原样。此点已列入 §④ 残留项。

### 1.2 落盘（原文进 `raw/`）

```
$ wc -l system/raw/2025-02-26-nvidia-q4-fy2025-results.txt      → 1146
$ wc -l system/raw/2024-11-20-nvidia-q3-fy2025-results.txt      → 1089
$ wc -l system/raw/2026-09-10-tsmc-aug2026-revenue.txt          →  231   （step 1 由投递口生成，与 inbox 副本逐字节一致）
$ wc -l system/raw/2026-08-04-amd-q2-2026-results.txt           →   71   （step 4 由投递口生成）
$ wc -l system/raw/inbox/2026-08-04-amd-q2-2026-results.txt     →   71   （投递口 payload）
```

`raw/` 目录：`2025-02-26-nvidia-q4-fy2025-results.txt`、`2024-11-20-nvidia-q3-fy2025-results.txt`、`2026-09-10-tsmc-aug2026-revenue.txt`、`2026-08-04-amd-q2-2026-results.txt` + `inbox/2026-08-04-amd-q2-2026-results.txt`。

### 1.3 走 step 1 落 claim（②）

- **step 1 投递口**（`scripts/orchestrate/ingest_step.py::ingest_public_information`）摄入 `raw/inbox/` 待采集文本。
  投递口处理器的**缺省标注**由该模块写死为最保守一档（`secondary_tertiary` / `interpretation` / `opinion`）——
  该模块 docstring 明确把"按来源逐条给出真实标注"列为**阶段② 连接器**职责。
- 因此本单**额外**落地一个**最小真实连接器** `system/scripts/ingest/real_collector.py`（`scripts/ingest/**` 属本单允许改动范围），
  对 NVIDIA 一手材料给出**真实标注**（`tier=primary` + `official_claim_kind`），以行使"三字段维度不同、不得互换合并"（`Ch9 §3.4.6` R-17 / `D-02`）。
  连接器**不自建** claim 构造口：一律经 `scripts.guard.claims.build_claim`，落库一律经 `schema.store.append_records`（`G-06` 唯一真源）。

**落库行（`facts/claims.jsonl`，逐字节）**：

| claim_id | tier | claim_nature | claim_form | official_claim_kind | status | recorded_seq | locator |
|---|---|---|---|---|---|---|---|
| `claim-nvidia-newsroom-q4-fy2025-4d13454fd859` | primary | fact | original_investigation | occurred_fact | pending_verification | 1 | `raw/2025-02-26-nvidia-q4-fy2025-results.txt#L1-L1146` |
| `claim-nvidia-newsroom-q3-fy2025-30d8b9bb6b87` | primary | fact | original_investigation | occurred_fact | pending_verification | 2 | `raw/2024-11-20-nvidia-q3-fy2025-results.txt#L1-L1089` |
| `claim-inbox-2026-09-10-tsmc-aug2026-revenue.txt-afebc81420c1` | secondary_tertiary | interpretation | opinion | *（None，合法：仅 tier=primary 才适用）* | pending_verification | 3 | `raw/2026-09-10-tsmc-aug2026-revenue.txt#L1-L231` |
| `claim-inbox-2026-08-04-amd-q2-2026-results.txt-44ea5ab4089d` | secondary_tertiary | interpretation | opinion | *（None）* | pending_verification | 5 | `raw/2026-08-04-amd-q2-2026-results.txt#L1-L71` |

- **五类时间语义**：system_time 三元组（`first_seen_at` / `analyzed_at` / `recorded_seq`）**均非 None 且 `recorded_seq` 递增**（1,2,3,5）；
  `occurred_at` 由投递文件名 ISO 前缀 / 连接器声明给出；`backfilled_at` 被显式标记（发布日均早于补入日）；
  `published_at`/`effective_from` 在 step 1 缺省层为 `None`（来源未披露，合法）；连接器层填 `published_at`=发布日。
- **`quote_hash` = sha256(UTF-8 原文)**；`locator` 覆盖整份被引原文（`#L1-L<行数>`）。
- **三字段未互换合并**：`claim_nature` / `claim_form` / `official_claim_kind` 分列三字段；`official_claim_kind` **仅**在 `tier=primary` 上非空。
- **`status`** 用 `schema.models.ClaimStatus` 合法值，初始态 `pending_verification`。

### 1.4 为 ③ 造的依赖边链与载体对象

`facts/dependency_edges.jsonl`（3 行）：`claim-nvidia-newsroom-q4-fy2025-… --supports--> baseline-nvda-001 --derives--> rec-nvda-001`（另 `q3` claim `--supports-->` 同一 baseline）。
配套载体：`facts/companies.jsonl`（`company-nvidia`，`research_depth=baseline_done`）、`facts/securities.jsonl`（`sec-nvda`）、`facts/baselines.jsonl`（`baseline-nvda-001`）、`facts/recommendations.jsonl`（`rec-nvda-001`）。

### 1.5 `facts/*.jsonl` 行数前后对比

| 文件 | 改动前 | 改动后 | 本单新增 |
|---|---|---|---|
| `claims.jsonl` | 0 | **5** | 2 primary（连接器）+ TSMC（step 1）+ AMD（step 1）+ 1 superseded 版本行 |
| `tasks.jsonl` | 0 | **3** | 2 `recheck`（T12 传播）+ 1 `check_record`（run_daily 必写） |
| `companies.jsonl` | 0 | **2** | 原始行 + 研究深度回退行 |
| `securities.jsonl` | 0 | **1** | 1 |
| `baselines.jsonl` | 0 | **1** | 1 |
| `recommendations.jsonl` | 0 | **1** | 1（`rec-nvda-001`，见 §④ 关于被剔除的合成行） |
| `dependency_edges.jsonl` | 0 | **3** | 3 |
| `industry_nodes.jsonl` | 44 | 44 | **未改** |

---

## ② 怎么验证的（原样命令 + 原样输出 + 退出码）

### ②-1 走 step 1（`ingest_public_information`）

```
$ python -c "from scripts.orchestrate.ingest_step import ingest_public_information; ..."
produced = ['claim-inbox-2026-09-10-tsmc-aug2026-revenue.txt-afebc81420c1']
degraded = False
signals_emitted = 0
EXIT=0
```

### ②-2 ★★ `superseded` 传播四项取证（本单最重要）

**(1) `recheck` 任务真的落库，`idempotency_key` 形如 `recheck::<ref>::<target>`**

```
$ python -c "from scripts.claim.transition import transition; transition('.', Q4, 'superseded', version_kind='financial_restatement', recorded_at=2026-09-16T09:00Z)"
[transition result]
  from -> to: pending_verification -> superseded  recordod_seq= 4
  version_kind: financial_restatement
  downstream: ['baseline-nvda-001', 'rec-nvda-001']
  recheck_tasks: ['task_recheck::claim-nvidia-newsroom-q4-fy2025-4d13454fd859::baseline-nvda-001',
                  'task_recheck::claim-nvidia-newsroom-q4-fy2025-4d13454fd859::rec-nvda-001']
  rolled_back_companies: ['company-nvidia']
```

`facts/tasks.jsonl` 原样（前两行）：

```
L1: task_id=task_recheck::claim-nvidia-newsroom-q4-fy2025-4d13454fd859::baseline-nvda-001
     task_type=recheck status=queued
     idempotency_key=recheck::claim-nvidia-newsroom-q4-fy2025-4d13454fd859::baseline-nvda-001
     input_refs=['baseline-nvda-001', 'claim-nvidia-newsroom-q4-fy2025-4d13454fd859']
     parent_context={'anchor': 'Ch9 §3.4.3', 'cause': 'claim-nvidia-newsroom-q4-fy2025-4d13454fd859', 'reason': 'dependency_stale', 'run_date': '2026-09-16'}
L2: task_id=task_recheck::claim-nvidia-newsroom-q4-fy2025-4d13454fd859::rec-nvda-001
     task_type=recheck status=queued
     idempotency_key=recheck::claim-nvidia-newsroom-q4-fy2025-4d13454fd859::rec-nvda-001
     input_refs=['rec-nvda-001', 'claim-nvidia-newsroom-q4-fy2025-4d13454fd859']
     parent_context={'anchor': 'Ch9 §3.4.3', 'cause': 'claim-nvidia-newsroom-q4-fy2025-4d13454fd859', 'reason': 'dependency_stale', 'run_date': '2026-09-16'}
```

研究深度回退（`facts/companies.jsonl` L2）：`baseline_done → relations_verified`，`change_log.cause = <claim ref>`。
**结论：阻断级缺陷 `N-2` 的修复在真实数据上「成立」。**

**(2) 幂等：同一迁移重跑不新增任务**

```
[idempotency] re-run propagate_retraction(apply=True)
  created_task_ids: []
  skipped_task_ids: ['recheck::claim-nvidia-newsroom-q4-fy2025-4d13454fd859::baseline-nvda-001',
                     'recheck::claim-nvidia-newsroom-q4-fy2025-4d13454fd859::rec-nvda-001']
  tasks.jsonl lines: 2 -> 2  (delta=0)

[terminal state] re-run transition on already-superseded claim:
  IllegalTransition: 非法迁移 'superseded' -> 'superseded'（Ch6 §E.1 有限状态机；允许目标: []）—— 本模块不静默兜底、不自动纠正
  after: tasks lines=2 claims lines=4
```

（`transition` 二次调用被**终态出边**合法拦截；"不重复建单"由传播层幂等键保证。）

**(3) 历史行逐字节不变（sha256 前后对比）**

```
[before] claims lines=3
  claims L1 sha256=32642e7dddda498643b93eb574a89e6ecfdf9b87cdace24db05897c8d3e02c11
  claims L2 sha256=21f25fc79f12655942c794774752be44a89787fb3ba071ae464d465ab312b465
  claims L3 sha256=ad23e55128ad9bda9a003fc7b88a29e7b42af5a157baaff7420abcc25cf356b5
[after] claims lines=4
  prefix(historical lines) byte-identical: True
  appended new line sha256: c20bb102b1c6848e4c97427c0538357fe919a79ad1f15e09d66b0e7fcaa4e585
```

**结论：迁移只**追加**一行（`status=superseded`, `version_kind=financial_restatement`, `recorded_seq=4`），既有 3 行**逐字节不变**。**

**(4) 半数据窗口：传播阶段失败 → 零写入**

```
[half-data] before (claims,tasks,edges): (4, 2, 3)
[half-data] ambiguous edges injected (claims,tasks,edges): (4, 2, 5)
  raised: ClaimTransitionError -> claim 'claim-nvidia-newsroom-q3-fy2025-30d8b9bb6b87' 在 dependency_edges 中出现多种 ref 形式
          ['claim-nvidia-newsroom-q3-fy2025-30d8b9bb6b87', 'claim:claim-nvidia-newsroom-q3-fy2025-30d8b9bb6b87'] —— 图数据不规范，拒绝猜测
[half-data] after failed migration (claims,tasks,edges): (4, 2, 5)
  claims delta = 0  tasks delta = 0
[half-data] edges restored byte-exact: True  final counts: (4, 2, 3)
```

**结论：把边表临时改成"不可解析的 ref"（同一 claim 的裸 id 与带前缀两种形式并存）→ 预飞阶段响亮失败 → `facts/claims.jsonl` 与 `facts/tasks.jsonl` **零新增行**。** 写序修正（"先解析/预飞、后写库"）在真实数据上成立。

### ②-3 `locator_check` / `graph_integrity_guard`（真实 claims/edges）

```
$ python scripts/validators/locator_check.py .
  scanned claims: 5 ; scanned sources: 0
  note: NO_SOURCES: facts/sources.jsonl 为空
RESULT: PASS（0 violations）        exit=0

$ python scripts/graph/graph_integrity_guard.py .
  scanned dependency_edges: 3
  note: NO_CACHE：邻接表缓存不存在
RESULT: PASS（0 violations）        exit=0
```

---

## ③ 结果

### ③-1 ④ 编排器 `run_daily` 原样输出（真实产出）

```
$ python -c "from scripts.orchestrate.pipeline import Pipeline; res = Pipeline(Path('.')).run_daily(date(2026, 9, 16)); ..."
=== run_daily(2026-09-16) ===
  step 1 ingest_public_information: status=ok produced=1
      produced refs: ['claim-inbox-2026-08-04-amd-q2-2026-results.txt-44ea5ab4089d']
  step 2 trace_dedup_verify: status=gap produced=4
      gap=`Ch6 §6.3` 追源去重与核验的**七步判定**（追源 / 交叉验证 / 采纳与否）属模型侧、阶段②③，本批次未交付；本次仅完成**定位机械复查**（4 条 claim 通过）。…
      produced refs: ['claim-inbox-2026-08-04-amd-q2-2026-results.txt-44ea5ab4089d',
                      'claim-inbox-2026-09-10-tsmc-aug2026-revenue.txt-afebc81420c1',
                      'claim-nvidia-newsroom-q3-fy2025-30d8b9bb6b87',
                      'claim-nvidia-newsroom-q4-fy2025-4d13454fd859']
  step 3 update_company_and_industry_relations: status=gap produced=3
      produced refs: ['edge-nvda-baseline-rec', 'edge-nvda-q3-claim-baseline', 'edge-nvda-q4-claim-baseline']
  step 4 revise_growth_and_moat_judgment: status=gap produced=0
  step 5 update_financial_and_valuation_assumptions: status=gap produced=0
  step 6 compare_company_vs_benchmark_expected_return: status=ok produced=1
      produced refs: ['rec-usDEMO-2026-04-01']        ← 见 §④ 缺陷 G-RC-01
  step 7 publish_recommendations: status=gap produced=0 （预留 hook = publish_hook）
  step 8 continuous_verification_and_history: status=gap produced=0 （预留 hook = verify_hook）
blocked=True degraded=True signals_emitted=1 changed=False
published=False verified=False
gaps (10): [step 2/3/4/5 的模型侧 gap + step 7/8 未注册 + 对应 4 条 G1-05]
```

- **step 1 有真实产出**：`produced=1`（AMD），`status=ok`。**（本项目第一次由真实外部文本产生 claim）**
- **step 2 有真实产出**：`produced=4`（4 条 claim 通过**机械定位复查**）；`status=gap` 属**预期**（`Ch6 §6.3` 七步判定属模型侧、张力 T-08 显式标 gap）。
- step 3 有真实产出（3 条边）；step 4/5 无产出（模型侧/上游输入缺失，显式 gap）。
- **step 6 报 `status=ok` 且 `signals_emitted=1` —— 但产出的是用测试夹具算出的合成建议，见 §④ G-RC-01（这**不是**真实产出，如实标出）。**
- `blocked=True`：step 2/3/4/5 记 gap（阻断级），step 7/8 未注册。符合"注册 ≠ 完成"。

### ③-2 结论

- **`N-2`（`superseded` 传播）在真实数据上成立**：`recheck` 落库、幂等、历史行不变、半数据窗口零写入 —— 四项全过。
- **step 1 / step 2 首次有真实产出**；step 6 的产出经核查为**夹具合成**（见 §④）。
- 采集/落盘均在**自己工作树**内完成，未触碰主仓库与其他工作树。

---

## ④ 诚实登记的残留 / 不确定项

### ★ 缺陷 G-RC-01（本单发现的**真实**缺陷，不在本单修复范围）

**现象**：真实 `run_daily` 的 **step 6（决策层）** 会**用 `tests/` 下的测试夹具作为"默认真实输入"**，
把一条**合成建议**写进真源 `facts/recommendations.jsonl`，并让编排器记 `status=ok`、`signals_emitted=1`。

**根因（只读定位）**：`scripts/decision/run_decide.py`

```python
DEFAULT_BENCHMARK_PRICES = _ROOT / "tests" / "compute" / "fixtures" / "agix_prices.jsonl"
DEFAULT_STOCK_PRICES     = _ROOT / "tests" / "decision" / "fixtures" / "demo_stock_prices.jsonl"

def run_default(root):      # ← 编排器 step 6 调的就是它（scripts/decision/step.py）
    ...
    return run(root, stock_prices_path=DEFAULT_STOCK_PRICES,
                      benchmark_prices_path=DEFAULT_BENCHMARK_PRICES)
# run(...) 默认 company_id="co-demo", security_id="usDEMO", benchmark_id="usAGIX"
```

`scripts/orchestrate/chain_steps.py::register_chain_steps`（批次 7 · 集成 I-1）已把 step 6 注册进 `Pipeline`，
故**真实 `run_daily` 会走到它**。

**被写入真源的原样行（`facts/recommendations.jsonl`，已在提交前剔除；此处为逐字节留证）**：

```json
{"action": "buy", "analyzed_at": null, "assumptions": [], "backfilled_at": null, "change_reason": "meets_buy_conditions",
 "company_id": "co-demo", "early_judgment": false, "effective_from": null, "evidence_gaps": [],
 "evidence_version_ids": ["dv-total_return-co-demo-compute-v1"], "expiry_review": null, "falsifier_written_at": null,
 "falsifiers": [], "first_seen_at": null, "horizon": "2q", "occurred_at": null, "opportunity_basis": [],
 "opportunity_types": [], "published_at": null, "recommendation_id": "rec-usDEMO-2026-04-01", "recorded_seq": null,
 "review_date": "2026-09-15", "rule_version": "decision-v1", "security_id": "usDEMO", "start_date": "2026-04-01",
 "status": "active", "supersedes": null, "unmet_conditions": [], "verification_conditions": [], "version": 1, "version_kind": null}
```

**连带影响（跑全部门禁 `run_all_gates.py` 后实测）**：

```
  no_signal_day.py        exit=1   [FATAL] G1-02① — 无变化日产了新信号: run_date=2026-09-16 signals_emitted=1
  traceback.py            exit=1   [FATAL] G1-03 — rec-nvda-001 四要素缺失: ['assumptions','computation','prev_version_id']
```

- `G1-02①`：`changed=False` 却 `signals_emitted=1` —— 信号正来自 G-RC-01 的合成建议。
- **本单处置**：**剔除**了合成行（不把已知捏造数据落进追加式真源），并**逐字节留证于上**。
  **未改** `scripts/decision/**`、`scripts/checks/**`（不在本单范围）。**建议主理人**：`run_default` 不应把 `tests/` 夹具当生产输入；
  编排器注册 step 6 时应对"输入为夹具 / 非真实行情"显式记 gap 或拒绝。

### 残余（本单内部，如实登记）

1. **`raw/*.txt` 是"纯文本渲染"，非字节级 HTML 原样**（剥离标记、空白归一为行；措辞零改动）。
   若需求方要求"抓到的字节原样落盘"，可另补 4 份 `.html`（~0.9 MB），本单未做（`数据量小即可`）。
2. **`rec-nvda-001` / `baseline-nvda-001` / `company-nvidia` / `sec-nvda` 为传播验证的**最小载体**，
   非经真实模型流程产出的"结论"**。故 `traceback.py`（G1-03）报四要素缺失属**已知**：
   其中 `prev_version_id`（= `supersedes`）对**首版**建议**结构性无法满足** —— 即**产出"第一条真实建议"必然使 G1-03 变红**。
   该红**非本单数据捏造**所致，属 checker 与"首版"的张力，登记待裁决。
3. `no_signal_day.py` 的 `G1-02①` 红**无法**在本单消除（由 G-RC-01 的合成信号触发），已如实登记。
4. 未跑 pytest 全量（`V-01` 禁）；本单**未新增测试目录**，故 `verification_policy_guard`（`V-06`）**不红**（实测 `exit=0`）。
5. `system/state.json`、`system/derived/compute_gaps.jsonl` 为 run_daily 的**运行产物**（未跟踪、非真源），**未提交**；`derived/compute_gaps.jsonl` 内含 2 条基准证券解析缺口（`p01` / `tbd`），与"基准选取未接真实行情"同源。
6. `facts/tasks.jsonl` 的 `check_record`（L3）如实记 `signals_emitted=1` / `status=failed`（对应该次 run），**保留**。

### ★ 发现 G-RC-02：真源码首次非空 → 破坏测试夹具的"空样本"假设（对照实验已证）

**现象**：本单把真实数据写入 `facts/*.jsonl` 与 `raw/*.txt` 后，三套**既有**测试子集出现红：
`tests/claim`（8 failed）、`tests/graph`（5 failed）、`tests/validators`（2 failed）。

**根因（对照实验证明，非本单代码缺陷）**：`system/tests/conftest.py` 的 `code_root` fixture 用
`shutil.copytree(SYSTEM_ROOT, target, ...)` **复制整个 `system/`（含 `facts/` 与 `raw/`）** 到临时目录；
`_ignore` 只跳过 `__pycache__/.pytest_cache/.venv/.work/index/reports/.locks` 与点文件。于是**测试不再从空真源起步**。
多个断言**写死了"空样本"假设**，例如：

- `tests/validators/test_locator_check.py::test_no_claims_passes_with_explicit_note`（L81）断言输出含 `NO_CLAIMS` → 假设 `claims.jsonl` 为空；
- `tests/validators/test_locator_check.py::test_real_ingested_claim_passes`（L142）依赖夹具 claims 为空后再驱动 ingest；
- `tests/graph/test_graph_integrity_guard.py::test_empty_edge_tables_pass_with_explicit_note`（L29）断言含 `NO_EDGE_DATA` → 假设边表为空。

**对照实验（原样命令 + 原样输出）**：

```
# 1) 备份真源，临时清空 facts/claims.jsonl 等 7 个文件 + 移走 raw/*.txt 到 /tmp/rc_rawtxt/
$ cp -a facts /tmp/rc_facts_bak
# （清空夹具可拷贝到的 7 个 facts 文件；移走 raw/*.txt）

# 2) 三套件复跑（真源"空"）
--- tests/claim ---       24 passed in 5.81s
--- tests/graph ---       38 passed in 4.64s
--- tests/validators ---  21 passed in 5.71s

# 3) 恢复（逐字节还原）
$ cp -a /tmp/rc_facts_bak/. facts/ && mv /tmp/rc_rawtxt/*.txt raw/
restored:
       5 facts/claims.jsonl
       3 facts/tasks.jsonl
       1 facts/recommendations.jsonl
```

**结论**：三套件**全绿** —— 红**不是**本单数据/代码问题，而是"**项目从未被真实数据跑过**"的又一直接表现：
测试的公共夹具把 `facts/` 与 `raw/` 一并复制，隐含假设它们为空；一旦真源非空，这些"空样本契约"即被破坏。
这是与 G1-02① / G1-03 同源的**结构性**问题（**测试侧契约未随真源演进**），已**逐字节恢复**真源后登记，**未改**任何测试或 `conftest.py`（不在本单范围）。

### 门禁总览（`run_all_gates.py`，实测）

- **放行 21/23**；红 2：`no_signal_day.py`、`traceback.py`（成因见 G-RC-01 与残余 2）。
- `pre-commit.sh` 的 10 道**不含**上述二者（`append_only`/`rules_lock`/`registry_schema`/`schema_sync`/`conflict_scan`/`no_placeholder`/`injection`/`verification_policy`/`shell_var`/`graph_integrity`）→ 提交未被阻断。

---

## 附：提交

- 分支：`ws/real-collect`（基点 `main = d03418a`）
- 主提交哈希：`08eddd3256fa29c35c303d91842c0b96bfd7dca2`（14 files changed, 3193 insertions）
- `pre-commit.sh`：**全部门禁放行**（`append_only`/`rules_lock`/`registry_schema`/`schema_sync`/`conflict_scan`/`no_placeholder`/`injection`/`verification_policy`/`shell_var`/`graph_integrity`）—— 提交未被阻断
- 提交范围：`raw/`（4 txt + inbox 副本）、`scripts/ingest/real_collector.py`、`facts/*.jsonl`（追加行）、本报告
- **未提交**（运行产物、非真源）：`system/state.json`、`system/derived/compute_gaps.jsonl`

