# `§九` 独立审计 — 批次 9（`ws/ch6-verify` + `ws/ch8-daily`）

> 审计员：`independent-auditor`（换眼审，非实现者）｜ 审计对象已并入 `main = f1c79a2`（ch6 `09ef2b4`→merge `c2f76e7`；ch8 `df31127`/`20f37bd`→merge `f1c79a2`）
> 本单为**第三单**：两条流此前只经"主理人集成复核"，**未经任何独立审计**（`G-16`：自证不构成验收）
> 审计时 `git status` 仅有两处**未提交**改动：`scripts/delivery/stage_gate.py`、`scripts/ops/verify.py`（主理人接线，本单按其工作树态审）
> 写型探测一律在副本：`system/tests/.audit/batch10/`、`/tmp/{p07root,ac03root}`（收工前已删）；真仓库 `facts/` 零改动

---

## §0 结论摘要

**总判定：两条流均「合并但未验收」（NOT ACCEPTED）。** 判定函数质量普遍较好，但**两条流的核心承诺都在系统层面不成立**：`T01` 无生产调用点、`coverage_verifiable` 虽已绑定但退化路径判据力为零、反 KPI 在真仓库已破。

### 表 1 · `ws/ch6-verify`（证据层：去重/独立判定 + 预算闸门）

| AC | 判定 | 一句话依据 |
|---|---|---|
| AC-01 T01 正向 | **PARTIAL** | 判定层按 AC 字面通过（`{'root':1}` / 传播 10）；但需输入**预置** `origin_claim_id`，未标上游的同源同指纹 10 篇 → **计 10**；且模块**无生产调用点** |
| AC-02 反向对照 | **PASS** | 独立复现 `{'ind0':3,'ind1':3,'ind2':3}`，**无误杀**（未见把真独立压成 1） |
| AC-03 传播真落库+幂等 | **PARTIAL** | 夹具路径 10 行→再跑 0 新增；真数据上 `propagation_rows=0` ⇒ 幂等断言在真数据上真空（0→0） |
| AC-04 复用证据 | **PASS** | grep 无原语重定义、无直写 `facts/`（§4-#6） |
| AC-05 三类取先到者 | **PASS** | 三场景实测 `first_binding=time/compute/retrieval`（§4-#1） |
| AC-06 到限行为 | **PASS** | 主张真转 `pending_verification`；`verify/queued`+幂等键+`budget_used` 真落库；重跑不重复建单 |
| AC-07 `research_cap` 仅由 importance | **PASS** | **真源**直测：同 importance 换 tier/知情/口径/佐证数 → 单值 40/15/4 |
| AC-08 参数不内置 | **PARTIAL** | 走 `get_param` 成立；但 `rules/budget.yaml` 不存在、数值 `tbd`，且 **0 值被静默当"无上限"** |
| AC-09 错误路径 | **PASS** | 缺配置且无显式缺省 → `BudgetConfigMissing`（响亮） |
| AC-10 边界 | **PASS** | 空 `claims` → `G-03` note + `{}`；成环/集合外上游/缺时间 → `IndependenceInputError` |
| AC-11 无占位符 | **PASS** | `no_placeholder_guard`：`violations=0`，扫 120 文件 |
| AC-12 禁词 | **PASS** | `conflict_scan(pre_commit)` `violations=0`；两目录直扫禁词为空 |
| AC-13 不污染真源 | **PASS** | 收工复核 `claims=5 edges=3 companies=2 tasks=3 rec=1 prop=0` |
| AC-14 设计对齐 | **PASS** | 节号锚点齐；字段名以 `schema` 优先（与设计 §C.2 样例名不同，未登记） |

**ch6 计：PASS 10 / PARTIAL 4 / FAIL 0 / UNKNOWN 0。**

### 表 2 · `ws/ch8-daily`（阶段④ `daily_run`）

| AC | 判定 | 一句话依据 |
|---|---|---|
| AC-1 `coverage_verifiable` | **PARTIAL** | CV1/CV2/CV3/CV4 实测可红可绿且**真绑定**门禁；但**退化路径 CV3 结构性不可命中**（真仓库当前即此态） |
| AC-2 降级 | **PARTIAL** | `mark_degraded` 四态实测通过（首日 `None` 如实、同日幂等）；但同一行在阶段④被另有内联规则判 FATAL（口径冲突） |
| AC-3 同日重跑幂等 | **PARTIAL** | `events`/`recommendations` 真零增；但 `append_deduped` **无生产调用点**（只事后检测）；集成断言在空真源上恒真 |
| AC-4 `p07` 配置化 | **PASS** | 改配置 → `BYHOUR=21→6` 跟随；缺文件/`tbd` 响亮失败；★附缺陷：YAML 六十进制陷阱（§4-#4） |
| AC-5 反 KPI | **FAIL** | 真仓库 `no_signal_day` **FATAL**：`changed=false signals_emitted=1`；本流测试在**空真源**上断言 = 恒真 |
| AC-6 复用证据 | **PASS** | `task_key == gap_to_task.idempotency_key`；深度四态取自 `schema` 侧定义 |
| AC-7 门禁与合规 | **PARTIAL** | `V-06` 集成后已绿（`test_files_uncovered=0`）；但 `daily` 批超时 60s vs 实测 ~43s（≈1.4×，违 `V-02` 的 8–30×） |

**ch8 计：PASS 2 / PARTIAL 4 / FAIL 1 / UNKNOWN 0。**

**最严重发现（一句）**：真仓库现有 `check_record`（由本流的 `run_daily` 写出）已违反反 KPI 铁律 `Ch1 §D.3`（无变化日产 1 个信号），而本流声称覆盖反 KPI 的用例建立在**空真源**上因而恒真 —— 即该铁律**当前无守卫**。

---

## §1 ★ `T01` 独立复现 + 反向对照（原样输出）

**权威表逐字**（`10_验收与持续复盘/01_需求拆解.md §2.1` L76）：

```
| **T01** | 十篇文章转述同一匿名订单消息 | 保留一个原始证据来源及传播记录，不提升为十份独立佐证 | Ch6 §C.2/§C.4；Ch8 §F.1/§5 | N6.3-03、N6.3-04、N9.1-13、N9.1-14、N8.4-03 | **Ch6** | Ch9 |
```

自建夹具（同 `root_source_id`/`metric`/`period_bucket`/`occurred_at` ⇒ 指纹同），原样输出：

```
--- ① 正向 1 根 + 10 转述（origin 链完整）
   root_count = 1
   independent_evidence_count = {'root': 1}
   propagation_count = 10
   断言 independent_evidence_count['root'] == 1 → True
   断言 propagation_count == 10 → True
--- ② 反向 3 条真独立
   root_count = 3
   independent_evidence_count = {'ind0': 3, 'ind1': 3, 'ind2': 3}
   propagation_count = 0
   断言 all(count == 3) → True
--- ③ 对抗 10 篇同源同指纹、无 origin 链、direct_knowledge=direct
   root_count = 10
   independent_evidence_count = {'c0': 10, ... 'c9': 10}   # 每篇都记 10
   propagation_count = 0    restatements = 0    review_candidates = ()
--- ④ 对抗 10 篇同源同指纹、无 origin 链、无 direct_knowledge
   independent_evidence_count = {'d0': 0, ... 'd9': 0}
   review_candidates = ('d0', ... 'd9')
```

**判读**：

1. **正向与反向都真通过，且方向正确** —— 没有"把真独立压成 1"的**误杀**（这是本单要求排除的方向）。
2. **但 ③ 是同一反例的现实形态**：系统拿到 10 篇**同根来源、同指纹**的报道时，`origin_claim_id` 尚不存在，模块把它们记成 **10 份独立佐证**（应为 1）。分组（指纹）算了，却**只用于分组、不用于限计数**；独立与否**只**由上游链 + `direct_knowledge` 决定。
3. 设计 §C.2 伪码同样无法覆盖该构造（`shares_root` 在"两两无共同根"时为假）—— 即**设计的隐含前提是"上游链由第③步产出"**（§D.1 第③步产出 = `origin_claim_id` + `claim_propagation` + `claim_fingerprint`）。实测该产出者**全仓不存在**：

```
$ Grep("origin_claim_id", system/scripts/**/*.py)
  independence.py:15  （docstring：沿 claim.origin_claim_id 回溯）
  independence.py:64  （docstring）/ :78（docstring）/ :184（docstring）/ :187（docstring）
  independence.py:197  parent = rec.get("origin_claim_id")     ← 读取
  independence.py:202  raise IndependenceInputError(f"origin_claim_id 成环…")  ← 报错
$ Grep("origin_claim_id", system/schema/models.py)
  models.py:587  origin_claim_id: str | None = None   ← 仅声明默认 None
  ⇒ 全仓**无任何赋值 / 写库方**
$ 真 claims（5 行）：全部 origin_claim_id = None、impact_capability = {}
```

**⇒ 结论：`T01` 判定层通过；`T01` 在系统层面尚未被守住**（(a) 上游链无人产出；(b) 同源同指纹无上游时计 10；(c) 模块零生产调用点，见 §4-#12 与 §5-G1）。

---

## §2 ★ `coverage_verifiable` 门禁绑定验证（含"删掉 `criterion` 那行会怎样"）

主理人接线（工作树，`stage_gate.py:528-534`）：`from scripts.daily.coverage import check as coverage_check` / `cv = coverage_check(root)` / `v += cv.violations` / `criterion("daily_run","coverage_verifiable", v)`。逐项独立复现（全部在副本，`code_root` = 副本 `system/`）：

```
--- 基线（副本原样，无 acceptance_input_set.yaml）
   passed = False  violations = 1
   [V] [FATAL] daily_run @ facts/tasks.jsonl:0 — task_check_2026-09-16_full 失败但未保留 last_valid_result_ref
   scanned = {'tasks': 3, 'check_records': 1, 'companies': 2, 'business_positions': 0,
              'industry_nodes': 44, 'coverage_target': 1, 'coverage_known': 1, 'nodes_without_coverage_record': 44}
   bound_criteria[daily_run] = ['coverage_verifiable', 'degrade_keeps_last_valid', 'task_state_auditable', 'timing_replayable']
   criteria_not_implemented   = []
--- (a) 覆盖不达标（target 含 company-ghost-uncovered）
   passed = False  violations = 2
   [V] [FATAL] coverage_verifiable @ facts/companies.jsonl:0 — CV3 覆盖目标 'company-ghost-uncovered' 无任何覆盖记录（静默遗漏；target=acceptance_input_set，10/01 §N10.1-06）
--- (b) 覆盖达标 + failed 任务已保留上次有效结果
   passed = True  violations = 0
--- (c) business_positions 缺 scan_frequency（CV1）
   passed = False  violations = 1
   [V] [FATAL] coverage_verifiable @ facts/business_positions.jsonl:0 — CV1 business_positions#1: 缺三份量 ['scan_frequency']（…，Ch3 §N3.2-03）
```

**(a)(b) ⇒ 门禁真的会因覆盖不达标而红、达标而绿**（不是只改计数）。**(c) ⇒ 反向对照（CV1）同样有判别力。**

**★ 删掉 `criterion("daily_run","coverage_verifiable", v)` 这一行**（副本上删，原样输出）：

```
删行后：passed = False  violations = 2
  [V] [FATAL] coverage_verifiable @ facts/companies.jsonl:0 — CV3 覆盖目标 'company-ghost-uncovered' …
  [V] [FATAL] G11-04 @ scripts/delivery/stage_gate.py::stage_daily_run_passed:0 — 阶段 daily_run 的判据 'coverage_verifiable' 已在 registry/delivery.yaml 声明为 automated，但 stage_daily_run_passed() 函数体内无对应 criterion() 声明 → **不得据此判 PASS**（静默漏判据）
  bound_criteria[daily_run] = ['degrade_keeps_last_valid', 'task_state_auditable', 'timing_replayable']
  criteria_not_implemented  = ['coverage_verifiable']
```

**⇒ 绑定是机器绑定的（4 → 3，且 G11-04 自曝），不是"删了仍报 4"的假绑定。**

**★ 但更强的反证：保留 `criterion` 行、只把检查掏空**（`cv = coverage_check(root); v += cv.violations` 换成 `cv = CheckReport(checker="coverage_verifiable")`）：

```
掏空检查后（覆盖仍不达标）：passed = True  violations = 0
  bound_criteria[daily_run] = ['coverage_verifiable', 'degrade_keeps_last_valid', 'task_state_auditable', 'timing_replayable']
  criteria_not_implemented  = []
  coverage_verifiable 的独立运行结果 = 1 violations
```

**⇒ 绑定是「在场绑定」而非「效果绑定」**：`criterion()` 只保证判据 id 出现在函数体（其 docstring 亦自承"本函数不做检查"）。删行会被 `G11-04` 抓住，但"掏空检查"**比删行更隐蔽**（绑定数仍 4、门禁对不达标数据变绿）。这是方法层局限，建议主理人知悉：**声明-实现绑定 ≠ 检查有效性绑定**。

---

## §3 逐条 AC 四态判定

见 §0 两张表（此处只补关键证据指向）：

- **ch6 AC-01**：原样输出见 §1；附加证据 `classify_and_record` 在真数据上：`propagation_rows(计算) = 0`、`independent_evidence_count = {…: 0}`（4 个根全 0）、`review_candidates = 4` ⇒ 真数据下该模块既不计 1 也不计 10，而是**全落存疑**（保守，但与 T01 期望的 1 不符）。
- **ch6 AC-05/AC-06**：原样输出见 §4-#1。
- **ch8 AC-1**：见 §2；退化路径证据 = §2 基线（`coverage_target=1`，`coverage_known=1`，CV3 违例 0）＋ `coverage.py:165-166, 226, 235`（`coverage_target` 退化取 `companies` 键集；`known_covered = set(company_latest) | position_company_ids` ⇒ **target ⊆ known_covered 恒真**）。
- **ch8 AC-3**：原样输出见 §4-#3。
- **ch8 AC-4**：见 §4-#4。
- **ch8 AC-5**：见 §4-#5（真仓库 FATAL 原文）。

---

## §4 对抗性清单逐项

1. **`Ch6 §D.5` 预算闸门** —— **命中（功能成立）+ 命中一处缺陷**。
   三类各造到限场景、到限行为、`research_cap` 真源直测（原样输出）：
   ```
   == B. 三类预算各造一个到限场景 ==
      [time] exhausted=True first_binding=time binding=('time',) task_id=task_verify_budget::c1::time 状态=pending_verification
      [compute] exhausted=True first_binding=compute binding=('compute',) task_id=task_verify_budget::c1::compute 状态=pending_verification
      [retrieval] exhausted=True first_binding=retrieval binding=('retrieval',) task_id=task_verify_budget::c1::retrieval 状态=pending_verification
   == C. 到限后落库的可重入任务（逐字段）==
      {'task_id': 'task_verify_budget::c1::compute', 'task_type': 'verify', 'status': 'queued',
       'idempotency_key': 'verify_budget::c1::compute', 'last_valid_result_ref': None}
      parent_context.budget_used = {'model_calls': 5, 'searches': 0}  limits = {'compute_limit': 5, 'research_cap': 15, 'search_limit': None}
   == D. 同 (claim, first_binding) 重跑 → 是否重复建单 ==
      tasks 行数 before/after = 3 / 3
   == E. research_cap 真源直测 ==
      importance=high → 取值集合 = {40}   importance=medium → {15}   importance=low → {4}
   == F. ★边界：max_model_calls = 0 ==
      compute_limit = 0
      used=999 calls / 0 searches → exhausted = False  first_binding = None  ratios = {'time': 0.0, 'compute': 0.0, 'retrieval': 0.0}
   == G. ★边界：非法状态（supported）到限 ==
      BudgetStateError: 预算到限要求置 pending_verification，但 supported -> pending_verification 非法（Ch6 §E.1 状态机）
   ```
   ⇒ 到限→`pending_verification`+可重入任务、`research_cap` **仅由 importance**（真源 `triage.py:152-158` 只读 `importance_class`）、非法状态响亮失败，**全部成立**。
   **缺陷（新）**：`evaluate_budget` 的 `if limit is not None and limit > 0`（`budget_gate.py:256`）使 `limit == 0` **静默等价于"无上限"** —— 配置 `max_model_calls: 0` / `max_searches: 0`（"不允许调用/检索"或占位 0）时用法 999 也不触限、`ratios` 归 0。这违反 `00_开发Agent开工提示词 §6.1`（缺值/边界必须显式兜底或显式降级，不得静默）。
2. **`Ch8 §E` 降级** —— **命中（成立）+ 命中一处口径冲突**。
   ```
   == #2 降级：保留上次有效结果 + 可见 + 首日如实为空 ==
      last_valid_result_ref(首日) = None
      applied= True  visible= True  last_valid_ref= None  task_id= task_degrade::2026-09-16::full  key= degrade::2026-09-16::full
      落库行 parent_context = {"degraded": true, "run_date": "2026-09-16", "reason": "degraded_run", "anchor": "Ch8 §E"}
      gaps 条数 = 2  last_valid_result_ref = None
      同日重跑 → applied= False  skipped_task_id= task_degrade::2026-09-16::full
      非降级日 → applied= False  visible= False
   ```
   ⇒ 保留上次有效结果、降级可见（`degraded`+`run_date`+`gaps` 真落库）、同日幂等、首日如实 `None`（`G-03`）**全部成立**。
   **冲突（新）**：同一批 `run_daily` 之后，阶段④门禁/降级模块对**同一批行**结论相反 ——
   ```
   degrade.check → 0 violations   notes = DEGRADE_NO_LAST_VALID：task_degrade::2026…（如实为空，note）
   阶段④ gate: passed = False  violations = 4
     [V] [FATAL] task_check_2026-09-16_full    失败但未保留 last_valid_result_ref
     [V] [FATAL] task_check_2026-09-16_full_r1 失败但未保留 last_valid_result_ref
     [V] [FATAL] task_check_2026-09-16_full_r2 失败但未保留 last_valid_result_ref
     [V] [FATAL] task_degrade::2026-09-16::full 失败但未保留 last_valid_result_ref
   ```
   ⇒ `stage_daily_run_passed`（`stage_gate.py:512-516`）把"降级红线"套在**所有** `status=failed` 行上（含首日合法降级行），而 `degrade.check` 把它当 note。**首日降级 ⇒ 阶段④必红**，且**每跑一次日更就多一条红**。
3. **幂等** —— **命中（生产路径成立，但守卫未接线）**。
   ```
   before = {'events': 0, 'recommendations': 1, 'tasks': 3, 'claim_propagation': 0, 'companies': 2}
   run#1 changed=False signals=0 blocked=True degraded=True gaps=12 dup_ev=() dup_rec=()
   after#1 = {… 'tasks': 5 …}  Δ = {'events': 0, 'recommendations': 0, 'tasks': 2, 'claim_propagation': 0, 'companies': 0}
   run#2 changed=False signals=0 dup_ev=() dup_rec=()
   after#2 = {… 'tasks': 6 …}  ★Δ#2 = {'events': 0, 'recommendations': 0, 'tasks': 1, …}
   ```
   ⇒ 同日重跑 `events`/`recommendations` **零增**（`Ch8 §N8.4-08` 成立）。但：(a) `append_deduped` 仅被 `tests/daily/test_idempotency.py` 调用，`run_daily` 只**事后检测**重复（`duplicates()`），**写入侧未接去重**；(b) `tasks` 每次 +1~+2（`check::…_r<n>` 修订号）——设计只约束 events/recommendations，故不算违例，但"行数不变"这条不变量的**唯一保障是"没有写入"**。
4. **`p07` 不得写死** —— **命中（配置化成立）+ 命中一处缺陷**。
   ```
   $ grep -nE "[0-9]{1,2}:[0-9]{2}|timezone *= *\"|Asia/|America/|\"DAILY\"|WEEKLY|MONTHLY" scripts/daily/*.py
     schedule.py:46:_CADENCE_FREQ: dict[str, str] = {"daily": "DAILY", "daily_and_event": "DAILY"}   ← 唯一命中（结构映射，本流 U-8 已披露）
     ⇒ 无写死的时刻 / 时区；频率侧仅 cadence→FREQ 的**结构翻译**
   设定 suggested_value.time_value=21:15 → time_value='21:15' timezone=America/New_York rrule=FREQ=DAILY;BYHOUR=21;BYMINUTE=15
   设定 suggested_value.time_value=06:05 → time_value='06:05' timezone=America/New_York rrule=FREQ=DAILY;BYHOUR=6;BYMINUTE=5
   ```
   ⇒ **改配置 → rrule 跟随**，未写死；缺 `rules/schedule.yaml` → `ScheduleFileMissingError`；`tbd` → `ScheduleUnresolvedError`（均实测）。
   **缺陷（新，高价值）**：YAML 把**未加引号**的 `time_value: 21:15` 解析为**六十进制整数 1275**：
   ```
   yaml.safe_load('21:15') = 1275 <class 'int'>      yaml.safe_load('"21:15"') = '21:15'
   YAML 原样写入 '"21:15"' → spec.time_value='21:15' rrule=FREQ=DAILY;BYHOUR=21;BYMINUTE=15
   YAML 原样写入 '21:15'   → 响亮失败: time_value='1275' 不是合法时刻（HH:MM）
   ```
   `freeze.yaml` 由**人工**在冻结时填写（0444，仅 `lock_rules.py` 可落），`time_value: 21:15` 是最自然的写法 → 一旦如此填写，调度**响亮失败但错误信息误报 `'1275'`**（操作员在文件里找不到 1275）。`AC-4a` 之所以通过，是因为测试用 `yaml.safe_dump` 序列化，落盘成**带引号**形态，**恰好掩盖了该陷阱**：
   ```
   测试 _patch_p07 写入后的 YAML 行 = ["    time_value: '21:15'"]
   ```
5. **反 KPI（`Ch1 §D.3`）** —— **★ 命中（真仓库已破，且本流守卫恒真）**。
   ```
   no_signal_day(真仓库): violations = 1 scanned = {'recommendations': 1, 'tasks': 3, 'check_records': 1}
      [V] [FATAL] G1-02① @ facts/tasks.jsonl:0 — 无变化日产了新信号: run_date=2026-09-16 signals_emitted=1
   ```
   该 `check_record` 的 `parent_context = {"orchestrator": "pipeline.run_daily"}`，即**本流的生产入口写出**。
   本流对应测试在**空真源**夹具上运行（`conftest.py:130` 契约："真源为空…测试必须自己声明自己的数据"）：
   ```
   def test_no_change_day_emits_zero_signals(code_root): assert report.signals_emitted == 0
   ```
   ⇒ 无主张 ⇒ 无第 6 步 ⇒ 恒 0：**空样本恒真，不构成守卫**（`G-03` 的精神同样适用于测试）。`run.py` 本身如实回传（我自己跑得 `changed=False signals=0`），**未做乐观改写**，此点清白。
6. **`G-06` 唯一真源** —— **无**。`grep -nE "^def (event_fingerprint|fingerprint_of_event|sha256|claim_locator_problems|append_records|as_of|transition|research_cap|idempotency_key)\b" scripts/evidence/*.py scripts/daily/*.py` 为空；`grep -nE "open\(.*facts|\.write_text\(" …` 为空（写一律走 `schema.store`）。
7. **`R-06`（鲁棒判据）** —— **命中**。`coverage.py` 的"覆盖目标集取法"用**名单** `_ACCEPT_LIST_KEYS = ("first_list","first_list_version","first_list_members")`（`coverage.py:72`）宽容匹配；更关键的是**退化路径使 CV3 失去判据力**：`coverage_target()` 退化返回 `sorted(companies)`（`coverage.py:165-166`），而 `known_covered = set(company_latest) | position_company_ids`（`:226`）⇒ **target ⊆ known_covered 由构造成立，CV3 永不命中**。CV3 恰是 `10/01 §N10.1-06`「无静默遗漏」的载体，**真仓库当前无 `registry/acceptance_input_set.yaml`** ⇒ 该义务未被任何有效检查守住（`R-06 ④`：不具防护力的检查不得承载防护语义）。
8. **静默兜底** —— **命中 1 处**（即 #1 的 `limit > 0`）。其余 `except` 均响亮或带原因元组：`budget_gate.py:295` 转抛 `BudgetStateError`；`schedule.py:185` 记 violation；`schedule.py:218` CLI 在 `tbd` 下打 note 并 `PASS/exit 0`（`Ch11 §F.1`：拍板前 `tbd` 为正常态 —— 可接受，但该检查**不得**被引作"时刻已解析"的证据）。
9. **占位符** —— **无**（`TODO|FIXME|XXX|NotImplementedError|^\s+pass$` 两目录 0 命中；`no_placeholder_guard` 0/120）。**另注**：`budget_gate.py` docstring 引设计"到限后 …**且 有日志** 且 可重跑"，实现只落 Task 行 + 返回内存 `notes`，**未持久化日志**（`R-02`：docstring 只写代码做到的事）。
10. **纪律 9/10** —— **无**。`git diff --name-only <commit>^..<commit>`：ch6 仅 `scripts/evidence/**` + `tests/evidence/**` + 其 2 份报告；ch8 仅 `scripts/daily/**` + `tests/daily/**` + DoD/报告。**未动** `rules/**`、设计区、`conftest.py`、`CONVENTIONS.md`、其他流目录。
11. **两条"范围外需主理人补"是否闭合** —— **已闭合，附一处规范偏差**。
    - 批次：`verify.py::BATCHES` 已加 `evidence`/`daily`（各 `60.0`，且登记进 `ORDER`）⇒ 实测 `verification_policy_guard: violations=0 scanned={… 'test_files_uncovered': 0}`，**`V-06` 已由红转绿**。
    - 接线：`stage_gate.py` 2 行已在工作树且实测生效（见 §2）。
    - **偏差**：`daily` 批超时 60s，而该批实测 ~43s（本流自报 `37 passed in 42.68s`；我合跑两批 `59 passed in 66.20s`）⇒ 约 **1.4×**，远低于 `V-02` 要求的 8~30×（`V-03`：超时=该批有问题且绝不算通过 —— 余量过薄会把"慢"误报成"卡死"）。`CONVENTIONS.md §V-02` 的"当前批次表"**未同步**这 4 个新批次（decision/transmit/evidence/daily），与文件自称的留档口径不符。
12. **`G-RC-05` 反向验证（根绑定）** —— **通过**。
    ```
    before = {'events': 0, 'recommendations': 1, 'tasks': 3, 'claim_propagation': 0, 'companies': 2}
    after  = {'events': 0, 'recommendations': 1, 'tasks': 3, 'claim_propagation': 0, 'companies': 2}
    ★ 真仓库 facts 零新增 = True
    ```
    在显式 `root`（副本）上跑 `run_daily` 两次 + `classify_and_record` 两次后，**真仓库零写入**（非"12 行"那次的复发）。

---

## §5 缺口清单（按严重度）

- **G1（严重，ch6+ch8 共同）**：两条流的核心产物**零生产调用点** —— `classify_and_record` / `apply_budget_gate` 在 `scripts/` 内无任何调用者（仅 `tests/evidence/` 调用）；`append_deduped` 同理（仅 `tests/daily/`）。即 `T01` 与"同日重跑写入侧幂等"在系统层面**未生效**。两流的写入域均不含接线方，属**需主理人补**。**披露情况不对称**：ch8 §三 已如实列出其两项范围外事项（`verify.py` 批次 + `stage_gate` 接线，本单核实均已闭合）；而 **ch6 §四 的 7 条缺口无一条提到"未接线"**，ch8 亦**未**披露 `append_deduped` 在生产路径上无人调用（`run_daily` 只事后检测）。
- **G2（严重，ch8）**：反 KPI 在真仓库已破（§4-#5），阶段④ 的 4 条判据中**没有任何一条**能发现它。
- **G3（中，ch8）**：退化的覆盖目标集使 **CV3 恒不可命中**（§4-#7），而 CV3 是 `N10.1-06` 的载体。
- **G4（中，ch6）**：`origin_claim_id` **全仓无产出方**（§1），`T01` 只在"答案已写进输入"时成立。
- **G5（中，ch6）**：`limit == 0` 被静默当"无上限"（§4-#1）。
- **G6（中，ch8）**：YAML 六十进制陷阱 + 错误信息误报配置值；测试以引号形态掩盖（§4-#4）。
- **G7（中，ch8）**：首日降级行被阶段④内联规则判 FATAL，与 `degrade.check` 口径冲突（§4-#2）。
- **G8（中，主理人侧）**：`daily` 批超时余量仅 ~1.4×（违 `V-02`）；`CONVENTIONS.md §V-02` 批次表未同步（§4-#11）。
- **G9（轻）**：`criterion()` 绑定是"在场绑定"非"效果绑定"（§2 掏空反证）。
- **G10（轻）**：`degrade.py:109` docstring 写"`0`"为空值，而 `_NULLISH`（`:55`）刻意不含 `0`/`False` —— 代码对、注释旧（`R-02`）。
- **G11（轻）**：`budget_gate` docstring 的"有日志"未持久化（§4-#9）；`independence` 字段名与设计 §C.2 样例不同（用 `schema` 名，正确但未登记）。

---

## §6 未能证伪的项（UNKNOWN + 原因；**禁止**把不确定写成 PASS）

1. **未跑全量验证**：只跑 `tests/evidence` + `tests/daily`（`V-08` 删除配额约束，本单**只跑一次**合批）。其余 13 批是否受影响**未验**。
2. **`conflict_scan` 只跑 `pre_commit` 层**：L4/L5（`require_l4/l5`）未启用，两流的 `L4/L5` 状态未知。
3. **`Pipeline.run_daily` 8 步内部语义**：属批次 8/`I-1` 与本单范围外；本单只按其输出（`changed/signals/degraded/blocked/gaps`）判 ch8 的薄封装，**未重审**步骤级实现。
4. **`registry/acceptance_input_set.yaml` 的最终 schema**：设计未定死，`_ACCEPT_LIST_KEYS` 的 3 个键名是否会在冻结时改变 → **无法判定** CV3 的键匹配覆盖面。
5. **`claim_alias` 人工 override（`Ch6 §C.3`）**：未实现，需求方尚未裁决落位（第 19 个 JSONL vs `Ch9 §3.3.3`）—— 无法判定"存疑项"是否终将有人复核。
6. **模型侧七步判定 / 关系抽取 / 增长护城河**：未实现（两流自报"未做清单"），故 `T01`–`T14` 的端到端串联**无法验证**。
7. **ch8 自报的 `p07.suggested_value` 不含 `timezone`**：我未核该偏差在冻结时的影响面。

---

## §7 审计过程自述

- **产出**：本文件唯一；未创建其他文件（`/tmp/audit10_*.py` 为一次性探针，已随会话结束）。
- **写入纪律**：只读 `git log/diff/status`，**无任何 git 写命令**；收工 `git status --short` 仅显示主理人自己的两处未提交改动（`stage_gate.py` / `verify.py`），**无我引入的改动**；真仓库 `facts/` 收工复核 `claims=5 / edges=3 / companies=2 / tasks=3 / recommendations=1 / claim_propagation=0`。
- **副本**：写型探测全部在 `system/tests/.audit/batch10/`（已 `rm -rf`）与 `/tmp/{p07root,ac03root}`（已删）。副本上对 `stage_gate.py` 做过两次临时改写（删行 / 掏空），**还原后 `diff -q` 与真仓库一致（rc=0）**。
- **pytest 通道**：`sh system/scripts/ops/run_pytest.sh tests/evidence tests/daily -q` → `59 passed in 66.20s`，`EXIT=0`；**本单只跑一次**（`V-08`），未反复迭代。
- **诚实记录三次自查**：① 首轮 `p07` 探针我的正则打偏，误改了副本 `freeze.yaml` 的错误位置，输出自相矛盾 → **重开全新副本**重跑，才得到 §4-#4 的干净结论（该缺陷是重跑后发现的真缺陷，非探针伪影）；② 一次探针因副本 `rules/` 保留 `0444` 抛 `PermissionError` → 改为**副本内** `chmod u+w`，**未触碰真仓库权限**；③ 早前 `grep -E "a\|b"` 在 zsh/BSD grep 下偶发空结果，关键结论均已改用 `Grep` 工具或 `python` 复核。
- **未触碰**：`system/tests/.audit/batch10_b`（**非我创建**，疑为 B 单审计员草稿）—— 我未读、未改、未删，请主理人收口时一并清理。
- **边界**：本单只判"两条流是否可验收"，不代改任何实现；所有缺陷均附可复现命令或原样输出。
