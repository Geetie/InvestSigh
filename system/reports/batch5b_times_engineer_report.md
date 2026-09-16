# 批次 5b · 工程师报告 —— 修 claim 时间契约缺陷（`build_claim` / `executor` / `ingest_step`）+ 清理合成数据 + 合规复跑

- **工程师**：`software-engineer-4`（寇豆码 / Kou）
- **主理人**：齐活林（交付总监）
- **目标**：修批次 5 首次真实运行暴露的**数据契约缺陷** —— 落库 claim 的
  `occurred_at / published_at / effective_from / first_seen_at / analyzed_at / recorded_seq / backfilled_at`
  **全为 None**、`locator=''`；并清理为验证而造的**未提交**合成数据，用**合规样例**复跑证明五类时间齐备。
- **环境**：broker 关（`CODEBUDDY_SAFE_DELETE_SANDBOX=0` / `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`）；
  `python=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`；**逐批串行**，未并行。
- **引用规范**：一律节号锚点（`Ch9 §2.2` / `§3.4.1` / `§3.4.6` / `rules/pipeline.yaml::steps[1]` / `CONVENTIONS.md::R-06`），**无绝对行号**。
- **临时探针**：`/tmp/run_daily_accept6.py`、`/tmp/probe_required.py`（**仓库外**，不入库）。

---

## 一、改了什么（文件 + 节号锚点）

| 文件 | 改动 | 节号锚点 |
|---|---|---|
| `scripts/guard/claims.py` | `build_claim` 新增**必填无默认**形参 `first_seen_at` / `analyzed_at` / `recorded_seq`（system_time 三元组）与**可选**形参 `occurred_at` / `published_at` / `effective_from` / `backfilled_at`（valid_time + backfill）；填进 `TimeMixin` **既有**字段，**不新增设计外字段**；另加**运行期效果断言**：三元组任一为 `None` → `ValueError`（`system_time` 永不未知） | `Ch9 §3.4.6` 措施④ · `§2.2` · `§3.4.1` · `CONVENTIONS.md::R-06`⑥ |
| `scripts/guard/executor.py` | `process_external_text` / `process_raw_file` 新增同款必填三元组 + 可选 valid_time 形参，**原样转发**给 `build_claim`；`handle_external_request` 的 `kind="data"` 路径把三元组并入**必需键**（缺 → `blocked/MISSING_PAYLOAD_FIELDS`，fail-closed）。**本层不产生 `now()`**（数据路径不得 import `datetime`，见 §四）。docstring 补"system_time 由调用方传入" | `Ch9 §3.4.6` 措施① · `R-07` · `AC-05` · `G-06` |
| `scripts/orchestrate/ingest_step.py` | 在**采集层**显式赋五类时间并传入：`first_seen_at`=`analyzed_at`=本次处理时刻（UTC）；`recorded_seq`=`facts/claims.jsonl` 现有最大 `recorded_seq`**+1**（逐文件递增，**不得**恒为 1）；`locator`=`raw/<file>#L1-L<n>`（无内容可定位 → **显式**"未披露"，不留空串）；`occurred_at` 仅当文件名带 ISO 日期前缀时取其日期，否则 None；`backfilled_at`=资料日期早于补入日时置补入日 | `Ch9 §2.2` · `§3.4.1` · `§N9.1-31/32` · `§3.4.6` 措施①/②（`seed_industry_nodes.py` 为正确范例） |

**清理的合成数据**（批次 5 为验证而造，**主理人授权的演示输入，非真实研究数据**；**均未提交**）：

| 路径 | 清理动作 |
|---|---|
| `system/raw/inbox/2026-09-16_cloud_capex_note.txt` | 删除（合成样例） |
| `system/raw/2026-09-16_cloud_capex_note.txt` | 删除（执行器落盘副本） |
| `system/facts/claims.jsonl` | 由该样例产生的 1 行 → **还原为已提交状态（0 字节）** |
| `system/facts/tasks.jsonl` | 由该样例产生的 1 行（`check_record`）→ **还原为已提交状态（0 字节）** |
| `system/state.json` | 删除（未被 git 追踪的运行游标） |
| `system/raw/inbox/.gitkeep` | **新增**（保留采集接缝目录，使 `raw/inbox/` 在 git 中留存） |

★ **删的是"未提交的合成行"**：`append_only_guard` 只看 `git diff --cached`，而这些行**从未 `git add`**；
  且目标文件在 `HEAD` 中即为 **0 字节**（`git show HEAD:system/facts/claims.jsonl | wc -c` = 0），
  故"还原为空"后**工作树与 `HEAD` 完全一致**（`git status` 不再列 `facts/*.jsonl` 为 modified），**不违反追加式不可变纪律**。

**未触碰**：`rules/**`（仍 `0444`）、`tests/**`、`conftest.py`、`scripts/checks/` 下**其他**守卫、`00_*`~`11_*` 设计区。

---

## 二、测了什么（真实输出：命令 + 原始 stdout + 退出码）

### 1) `injection_guard` 在真实仓库上（数据路径能力白名单未被破坏）

```
$ python system/scripts/checks/injection_guard.py system --no-report
== injection_guard.py ==
  scanned builtin_codeexec_hits: 0
  scanned chokepoints_wired: 2
  scanned data_path_modules: 7
  scanned dunder_outside_allowlist: 0
  scanned import_outside_allowlist: 0
  scanned recommendation_writes: 0
  scanned rules_files: 10
  scanned rules_files_on_disk: 10
  scanned unverifiable_stem_calls: 0
  note: CAPABILITY_ALLOWLIST: ...
  note: AUX_LINT: ...
  note: NO_RAW_EXTERNAL_TEXT：raw/ 无外部文本（数据路径不变式**真空成立**，须标注）
  note: data_path_globs=scripts/guard/** rules_suffixes=('.yaml', '.yml', '.json')
RESULT: PASS（0 violations）
EXIT=0
```

**要点**：`import_outside_allowlist: 0` —— `claims.py` / `executor.py` 新增的 `datetime`
**仅出现在（PEP 563 延迟求值的）类型注解里**，**未新增 `import`**，故未触白名单（见 §四.1）。

### 2) 必填契约真的生效（临时探针 `/tmp/probe_required.py`，真子进程）

```
$ python /tmp/probe_required.py
=== 1) build_claim 缺 system_time 三元组 → TypeError（调用方无法省略）===
  build_claim 缺 first_seen_at/analyzed_at/recorded_seq: TypeError → build_claim() missing 3 required keyword-only arguments: 'first_seen_at', 'analyzed_at', and 'recorded_seq'
=== 2) build_claim 传 None 的 system_time（绕过签名）→ 运行期 ValueError ===
  build_claim first_seen_at=None: ValueError → system_time 永不未知，不得为 None：['first_seen_at', 'analyzed_at', 'recorded_seq']（Ch9 §2.2 / §3.4.1；为 None 会使版本选取退化）
=== 3) process_external_text 缺 system_time 三元组 → TypeError（旧调用方报错）===
  process_external_text 缺三元组: TypeError → process_external_text() missing 3 required keyword-only arguments: 'first_seen_at', 'analyzed_at', and 'recorded_seq'
PROBE_DONE
EXIT=0
```

**要点**：① 签名层 `TypeError`（调用方**无法省略**，与 `claim_nature` 同一手法）；
② 若**绕过签名**显式传 `None`，pydantic（`TimeMixin` 字段默认 `None`）**不会拦**，故由
`build_claim` 的**运行期效果断言**拦下 → `ValueError`（这是本批次的鲁棒性关键，`R-06`⑥）。

### 3) 任务 4 验收：真实 `system/` 跑 `run_daily`（**合规样例**，两文件）

```
$ python /tmp/run_daily_accept6.py
=== BEFORE ===
  raw/: ['raw/.gitkeep', 'raw/inbox', 'raw/inbox/.gitkeep', 'raw/inbox/2026-09-08_cloud_capex_note_sample.txt', 'raw/inbox/2026-09-15_server_backlog_note_sample.txt']
  facts/claims.jsonl lines: 0
  facts/tasks.jsonl  lines: 0
  state.json exists: False
=== RUN RESULT ===
  step 1 ingest_public_information                          status=ok      produced=2
  step 2 trace_dedup_verify                                 status=gap     produced=0  gap=step 2 (trace_dedup_verify) 未注册处理器
  step 3 update_company_and_industry_relations              status=gap     produced=0  gap=step 3 (...) 未注册处理器
  step 4 revise_growth_and_moat_judgment                    status=gap     produced=0  gap=step 4 (...) 未注册处理器
  step 5 update_financial_and_valuation_assumptions         status=gap     produced=0  gap=step 5 (...) 未注册处理器
  step 6 compare_company_vs_benchmark_expected_return       status=gap     produced=0  gap=step 6 (...) 未注册处理器
  step 7 publish_recommendations                            status=gap     produced=0  gap=step 7 (...)；预留 hook = publish_hook
  step 8 continuous_verification_and_history                status=gap     produced=0  gap=step 8 (...)；预留 hook = verify_hook
  blocked=True degraded=False signals_emitted=0 gaps=12
=== AFTER ===
  raw/: ['raw/.gitkeep', 'raw/2026-09-08_cloud_capex_note_sample.txt', 'raw/2026-09-15_server_backlog_note_sample.txt', 'raw/inbox', 'raw/inbox/.gitkeep', 'raw/inbox/2026-09-08_cloud_capex_note_sample.txt', 'raw/inbox/2026-09-15_server_backlog_note_sample.txt']
  facts/claims.jsonl lines: 2
  facts/tasks.jsonl  lines: 1
  state.json exists: True
=== recorded_seq 递增证据（全部行）===
  row1: claim_id=claim-inbox-2026-09-08_cloud_capex_note_sample.txt-cc8fa4a3f8be  recorded_seq=1  locator='raw/2026-09-08_cloud_capex_note_sample.txt#L1-L4'
  row2: claim_id=claim-inbox-2026-09-15_server_backlog_note_sample.txt-82ae102314c0  recorded_seq=2  locator='raw/2026-09-15_server_backlog_note_sample.txt#L1-L3'
=== 五类时间齐备性判定（逐行）===
  row1: first_seen_at 非 None=True  analyzed_at 非 None=True  recorded_seq 是 int 且 >=1=True  locator 非空=True  occurred_at 非 None（文件名带日期前缀）=True
  row2: first_seen_at 非 None=True  analyzed_at 非 None=True  recorded_seq 是 int 且 >=1=True  locator 非空=True  occurred_at 非 None（文件名带日期前缀）=True
  recorded_seq 序列: [1, 2] → 严格递增: True
=== VERDICT ===
  ALL_FIVE_OK: True
EXIT=0
```

**结论**：step 1 = `ok`（`produced=2`）；`raw/` 落盘；`claims.jsonl` ≥1 行；**每行五类时间齐备**；
`recorded_seq` = `[1, 2]` **严格递增**（证明"**不恒为 1**"）。
（step 2–8 仍 `gap` 属张力 `T-08`，本批次范围外；`blocked=True` 属**预期**，同批次 5。）

### 4) 分批验证（逐批串行，各自独立超时）

| 批次 | 命令 | 结果 | 退出码 | 耗时/上限 |
|---|---|---|---|---|
| `gates` | `verify.py --batch gates` | ✓ **20 项门禁，非零计数 = 0** | `0` | ~4s / 60s |
| `guards` | `verify.py --batch guards` | ✓ **56 passed** | `0` | 3.35s / 60s |
| `injection` | `verify.py --batch injection` | ✗ **21 failed / 88 passed**（**全部同一 `TypeError`，见 §四.2**） | `1` | 21.98s / 120s |

`skipped` / `xfail` / `error`：各批均为 **0**（无静默跳过）。
★ **`injection` 的 21 条失败是"暴露没传时间"的预期行为**（任务明示）；**未改** `tests/**`，
  只在 §四.2 列出"哪些测试需 QA 随之更新"。

### 5) 最终仓库状态（`git status` 证据）

```
$ git status --porcelain
 M system/CONVENTIONS.md
 M system/reports/phase1_gap_register.md
 M system/scripts/checks/injection_guard.py
 M system/scripts/guard/claims.py            ← 本次
 M system/scripts/guard/executor.py          ← 本次
 M system/scripts/guard/rawsink.py
 M system/scripts/orchestrate/pipeline.py
?? system/raw/inbox/                          ← 采集接缝目录（仅含 .gitkeep）
?? system/reports/batch4_independent_audit_round2.md
?? system/reports/batch5_engineer_report.md
?? system/scripts/orchestrate/ingest_step.py
$ wc -c system/facts/claims.jsonl system/facts/tasks.jsonl
       0 system/facts/claims.jsonl
       0 system/facts/tasks.jsonl
$ find system/raw -type f
system/raw/.gitkeep
system/raw/inbox/.gitkeep
$ ls -d system/state.json 2>/dev/null || echo "state.json: ABSENT"
state.json: ABSENT
```

**要点**：`facts/claims.jsonl` / `facts/tasks.jsonl` **不再出现在 `git status`**（已还原为 `HEAD` 的 0 字节）；
`raw/` 下**无样例文件**（仅 `.gitkeep`）；`state.json` **不存在**；`rules/` 仍 `0444`。

---

## 三、缺陷处理证据 —— 复跑那行 claim 的**完整 JSON**（五类时间齐备）

> 取自 §二.3 复跑后 `facts/claims.jsonl` 第 2 行（`indent=2` 便于逐字段核对）。
> 该行**随后已随合成数据一并清理**（见 §四.3），此处为**清理前**的原始落库证据。

```json
{
  "analyzed_at": "2026-09-16T04:45:35.614585Z",
  "backfilled_at": "2026-09-16T04:45:35.614585Z",
  "carrier_platform": "",
  "claim_form": "opinion",
  "claim_id": "claim-inbox-2026-09-15_server_backlog_note_sample.txt-82ae102314c0",
  "claim_nature": "interpretation",
  "effective_from": null,
  "first_seen_at": "2026-09-16T04:45:35.614585Z",
  "full_text_read": false,
  "impact_capability": {},
  "locator": "raw/2026-09-15_server_backlog_note_sample.txt#L1-L3",
  "occurred_at": "2026-09-15T00:00:00Z",
  "official_claim_kind": null,
  "origin_claim_id": null,
  "published_at": null,
  "publisher_entity": "",
  "quote_hash": "82ae102314c0050e1b49be3f6e0931c134a43806c6df330e82016b31484d9014",
  "recorded_seq": 2,
  "source_id": "inbox-2026-09-15_server_backlog_note_sample.txt",
  "status": "active",
  "supersedes": null,
  "tier": "secondary_tertiary",
  "tier_basis": "",
  "version_kind": null
}
```

**逐条对应设计原文的修复**：

| 缺陷（批次 5 首跑） | 本次取值 | 依据 |
|---|---|---|
| `recorded_seq = None`（版本选取退化） | `recorded_seq = 2`（int） | `Ch9 §3.4.1`：按业务键取 `recorded_seq` 最大 |
| `first_seen_at = None`（时点不可区分） | `first_seen_at = "2026-09-16T…Z"` | `Ch9 §2.2` 行 915：系统时间缺字段组 → 时点不可区分 |
| `analyzed_at = None` | `analyzed_at = "2026-09-16T…Z"` | `Ch9 §2.2` system_time 三元组 |
| `locator = ''`（不可复查） | `locator = "raw/…_sample.txt#L1-L3"` | `Ch9 §3.4.6` 措施①/②：含定位、主张性质 |
| `occurred_at = None`（valid_time 缺失） | `occurred_at = "2026-09-15T00:00:00Z"` | `Ch9 §2.2` valid_time（`§N9.1-31/32`） |
| `backfilled_at = None`（事后信息伪装风险） | `backfilled_at = "2026-09-16T…Z"`（资料 09-15 < 补入 09-16） | `Ch9 §N9.1-31/32`：显式标记事后补入 |
| `published_at` / `effective_from = None` | 仍为 `null` | **来源未披露 → 保持 None 合法**（valid_time 未知合法；system_time 未知才非法） |

---

## 四、剩余不确定性与缺口

### 4.1 `datetime` 为何"注解而不导入"（结构性约束，非疏漏）

`scripts/guard/**` 属 `injection_guard` 的**数据路径**，受 `ALLOWED_IMPORTS` **能力白名单**约束
（`import datetime` 会命中 `import_outside_allowlist` → FATAL）。故本批次：

- `claims.py` / `executor.py` **不 import `datetime`**；类型注解写 `datetime`，
  由模块级 `from __future__ import annotations`（PEP 563）**延迟求值**，运行期**不求值**该名字。
- 直接后果：**`now()` 不在数据路径产生**。system_time 三元组**必须由调用方传入**
  （采集层 `ingest_step.py`，或外部请求 payload）—— 这与"本模块不解析文本、不合成事实"的
  结构性约束**一致**，且使"没传时间"在**类型/运行期**双重暴露（§二.2）。
- **实证**：`import_outside_allowlist: 0`（§二.1）。若后续需在数据路径内产生时间，
  须先由需求方裁定是否扩白名单（**本批次不擅自扩**，`R-04`）。

### 4.2 ★ 需 QA 随之更新的测试（**唯一**受影响面）

`injection` 批次 **21 failed / 88 passed**，失败**全部同因**：
`TypeError: process_external_text() missing 3 required keyword-only arguments: 'first_seen_at', 'analyzed_at', and 'recorded_seq'`。
**全部位于** `tests/injection/test_prompt_injection.py`：

- **helper** `_ingest(...)`（文件内约第 84 行的定义处）—— 它是 20 条用例的公共入口；
  需在 `process_external_text(...)` 调用处补三个必填实参（建议用 `datetime.now(timezone.utc)`
  与逐调用递增的 `recorded_seq`，或抽一个夹具级 `now`）。
- **直接调用** `test_ac34_empty_external_text_is_degraded_with_note`（约第 625 行）——
  同样补三个实参（注意：空文本走 `degraded` 早返回，**不落** claim，但仍需满足签名）。
- 受影响用例清单（20 条经 `_ingest`）：
  `test_ac13` `test_ac14` `test_ac15` `test_ac16` `test_ac17` `test_ac18` `test_ac19` `test_ac20`
  `test_ac21` `test_ac22` `test_ac23` `test_ac24` `test_ac25` `test_ac26` `test_ac27` `test_ac28`
  `test_ac29` `test_ac30` `test_ac31` `test_ac32`，外加 `test_ac34`。

★ **断言语义无需改**（这些用例断言的是"注入被中立化 / 放行"的**效果三元组**，与时间无关）；
  只需**补实参**使旧调用点满足新契约。**未改** `tests/**`（纪律）。
★ 其它批次**不受影响**：`guards` 56 passed、`gates` 0 非零（§二.4）；`unit` / `conflict` / `root`
  经检索**无**对 `build_claim` / `process_external_text` / `process_raw_file` 的调用点。

### 4.3 `facts/` 最终是否保留样例行 —— **本批次不留（回到 0 行）**

- 本批次**已将复跑产生的 2 条样例行一并清理**（同 §一 理由）：`facts/claims.jsonl` = **0 字节**，
  `facts/tasks.jsonl` = **0 字节**，`state.json` 删除。
- **理由**：`facts/` 是**追加式不可变真源**，其内容会被后人当作**真实研究数据**读取；
  验证样例**不是**真实研究结论（样例文件名虽含 `sample`，但真源内不应混入任何非研究数据）。
  故选择"**证据留报告、真源保干净**"（原始 JSON 见 §三）。
- **未决**：若主理人认为"保留一条**明确标注为验证样例**的行"更利于交接，可**一键复跑** §二.3 的
  `/tmp/run_daily_accept6.py` 重现；但那将使 `facts/claims.jsonl` **非空**且其 `source_id` 指向样例文件。
  **请主理人裁定**；在裁定前保持 **0 行**。

### 4.4 其它（沿用批次 5 结论，未扩大范围）

1. **重复运行产生重复 claim**：`ingest_step` 未消费/未去重投递口；幂等键去重（`Ch9 §3.5` 的
   `(source_id, quote_hash)`）按设计属**阶段②**，本批次**不实现**（`R-04`）。本次为演示 `recorded_seq`
   递增而**刻意**保留了投递口文件未消费的行为（两文件 → 两条不同 `claim_id`，各 `recorded_seq` 递增）。
2. **step 2–8 仍 `gap`**：属张力 `T-08`（`rules/` 0444 锁定，须需求方裁定），本批次**未触碰**。
3. **`published_at` / `effective_from` 保持 None**：当前投递口样例**未披露**该二 valid_time；
   阶段② 连接器按来源提供真实标注后应填入（`Ch9 §2.2`）。

---

## 五、全局一致性审查

- **跨文件 import**：`ingest_step` → `executor.process_raw_file` → `process_external_text` → `build_claim`：
  逐层转发 system_time 三元组，签名一致；`ingest_step` 另用 `schema.store.read_records` 计算
  `recorded_seq`（`scripts/orchestrate/**` 不受数据路径白名单约束）；**无循环导入**。
- **接口契约**：`build_claim` / `process_external_text` / `process_raw_file` 的三元组均为
  **必填无默认**；`handle_external_request(kind="data")` 把三元组并入必需键（fail-closed）。
- **数据流**：`recorded_seq` 逐文件递增（`[1,2]` 实证）；`locator` 指向落盘 `raw/<file>` 行区间；
  `occurred_at`/`backfilled_at` 由文件名日期与补入日比对派生；valid_time 未知保持 None（合法）。
- **无重复实现**：`build_claim` 仍是 claim 的**唯一**构造口；`raw/` 越界判定仍唯真源（`G-06` 未动）。
- **无越界**：`rules/**`（0444）、`tests/**`、`conftest.py`、其它守卫语义、设计区**均未改**（`git status` 证实）。
- **性能**：`injection_guard` 单次 **0.09s**（< 0.5s，`P-05`）；各门禁均 < 0.25s。

---

**IS_PASS: YES**

**理由**：

1. **缺陷已修且可自证**：复跑后 claim 的 **system_time（`first_seen_at`/`analyzed_at`/`recorded_seq`）齐备**、
   `recorded_seq` **严格递增**、`locator` **非空**、valid_time/backfill 按语义填/留（§二.3、§三）。
2. **契约真的生效**：签名 `TypeError` + 绕过签名的运行期 `ValueError` 双重拦截（§二.2）；
   未新增设计外字段（填的是 `TimeMixin` **既有**字段）。
3. **未破坏既有门禁**：`gates` **0 非零**、`guards` **56 passed**、`injection_guard` **PASS**（§二.1/4）。
4. **合成数据已清理、纪律未破**：`facts/*.jsonl` 还原为 `HEAD` 的 0 字节、`raw/` 与 `state.json` 干净、
   `rules/` 仍 0444（§二.5）；删除的是**未提交**行，`append_only_guard` 不受影响。
5. **唯一"未绿"项是预期且已界定**：`injection` 的 21 条失败**全部同一原因**（旧调用点未传必填三元组），
   **不涉断言语义**、清单与修法已交 QA（§四.2）——即任务要求的"暴露没传时间"。

**唯一需下游动作**：QA 按 §四.2 为 `tests/injection/test_prompt_injection.py` 的 `_ingest`（及 `test_ac34`）
补三个必填实参；主理人裁定 §四.3（样例行是否保留，默认 0 行）。
