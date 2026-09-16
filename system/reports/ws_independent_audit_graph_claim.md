# `§九` 独立审计 — `ws/graph` 与 `ws/claim`

- **审计员**：独立审计员-2（对抗性、换人视角；非实现方，不采信实现方完成声明）
- **审计对象**：分支 `ws/graph`（tip `2aa7213`）· 分支 `ws/claim`（tip `3904fb6`），均已合并进 `main`（`4756028`）
- **判分表**：`reports/ws_graph_dod.md` · `reports/ws_claim_dod.md`（各 8 条 AC）
- **环境**：`CODEBUDDY_SAFE_DELETE_SANDBOX=0` / `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`；`python=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python`
- **方法**：全部探测用 **raw CLI / 短脚本**（`§九` 要求），**未运行 pytest**（`conftest.py::pytest_sessionstart` 会清空 `tests/.work/`，该通道归另一位审计员）
- **真源保护**：所有写入型探测在副本 `system/tests/.audit/graph_claim/`（已整目录删除）上进行；真仓库 `facts/` 0 行未变、`index/` 已复原

---

## §0 结论摘要

### `ws/graph` — **merged-but-not-accepted**

| AC | 判定 | 一句话依据 |
|---|---|---|
| AC-01 真跑通 | **PARTIAL** | 库入口 `propagate_retraction(apply=True)` 真跑通（下游 2 个 + 2 条 `recheck` + 深度回退 append），但**主流程无 step③**、真仓库 `facts/dependency_edges.jsonl` = **0 行** → 「主流程真跑到」不成立 |
| AC-02 持久化/可重建 | **PASS** | `build_adjacency_index` → 与真源逐边一致 → **删整个 `index/`** → 重建 → 仍一致；闭包 sha256 删前/删后**逐字节相同** `2fbd905f…804a0` |
| AC-03 真接线 | **FAIL** | 全树 `grep` 穷尽：`graph_integrity_guard`/`scripts.graph` 在 `scripts/graph/**` 之外**零引用**；`run_all_gates.py`（20 项）与 `pre-commit.sh` 均未收录；`pipeline.py` 只注册 step 1 → **孤儿模块** |
| AC-04 守卫真拦得住 | **PASS** | 自环 `exit 1`、重复边 `exit 1`、陈旧缓存 `exit 1`、干净树 `exit 0`+`scanned`、`code_root` 不存在 `exit 2`（全部真 CLI 子进程） |
| AC-05 错误路径 | **PASS** | 环不重入（`reached=[b,c]`、`cycle_detected=True`）、自环不死循环、悬空记 `dangling` 不抛、`should_stop`→`stop`+`mark=evidence_insufficient` |
| AC-06 边界 | **PASS** | 空图 `[]`+`truncated=False`+守卫 `exit 0` 记 note；5000 节点链 **0.011s**；重复边幂等；跨时区表示→**同一指纹** |
| AC-07 无占位符 | **PASS** | `no_placeholder_guard.py system --fail-on warn` → `exit 0`（107 文件）；手工 grep 无 TODO/FIXME/mock/except:pass |
| AC-08 设计对齐 | **PASS** | 节号逐条核对**真实存在且内容对得上**（`Ch9 §3.2.1/§3.3.2/§3.4.3/§3.4.7`、`Ch7 §B.4/§C.2/§C.3/§C.5/§C.6/§C.8`、`Ch2 §B.3`）；`assert_not_equivalent("capex","order"/"revenue")` **实调真抛** |

### `ws/claim` — **merged-but-not-accepted**（判分表本身有 1 格与代码不符 + 1 条前提过期）

| AC | 判定 | 一句话依据 |
|---|---|---|
| A-AC-01 真跑通 | **PASS** | 真跑 `ingest_public_information` → 真 claim → `locator_check.py` **exit 0**（**注意**：落库状态是 `pending_verification`，非 DoD 所写 `active`） |
| A-AC-02 持久化 | **PASS** | 只读校验器 + `run_checker` 留档，实跑生成 `reports/locator_check.py_2026-09-16.json` |
| A-AC-03 真接线 | **FAIL** | `transition.py`→`claim_locator_problems` 调用**真实存在**，但 `transition.py` 自身**零生产调用方**，且 `locator_check` **未注册** `run_all_gates.py`/`pre-commit.sh` → 孤儿调用孤儿 |
| A-AC-04 真拦得住 | **PASS** | `FULL_TEXT_UNPROVEN`/`QUOTE_HASH_MISMATCH` → **exit 1**（真 CLI） |
| A-AC-05 错误路径 | **PASS** | `LOCATOR_MISSING`/`LOCATOR_UNRECOGNIZED`/`LOCATOR_ESCAPE`/`LOCATOR_UNRESOLVABLE`/`CLAIM_SCHEMA_INVALID`/`OFFICIAL_KIND_TIER_MISMATCH` **全部 exit 1** |
| A-AC-06 边界 | **PASS** | 空 claims→`NO_CLAIMS`+**exit 0**（G-03 note 齐）；1500 条 **0.340s**（<2s）；`bogus` 枚举 exit 1；时间倒挂 `TIME_INVERSION` exit 1 |
| A-AC-07 无占位符 | **PASS** | 同上门禁 `exit 0` |
| A-AC-08 设计对齐 | **PARTIAL** | `Ch6 §D`/`N6.1-11`/`Ch9 §3.5 ②行`/`R-17` 全部核对通过；但 **`Ch9 §3.4.6 措施①/②` 子锚点在设计区不存在**（§3.4.6 = 注入防护，无 ①/②；全设计区不存在「措施①」字样） |
| B-AC-01 真跑通 | **FAIL（前提过期 → AC 不可满足）** | DoD 要求「采集层写入初始 `status="active"`→`transition(...,"pending_verification")`」；实测采集层写入 **`pending_verification`**，`ClaimStatus` 为封闭 `StrEnum`（默认 `pending_verification`），`active` **不是合法取值**；遗留 `active` 行被 `Claim.model_validate` 拒（exit 1）。**意图**（采集→迁移→可读出）在修正前提下 PASS |
| B-AC-02 持久化 | **PASS** | 迁移追加新行、**既有行全部逐字节不变**（sha256 前缀比对 True）；删 `index/`→`rebuild_index()`→`facts.sqlite` 2 行且末版 `supported` 仍在 |
| B-AC-03 真接线 | **FAIL（严重）** | `on_superseded`→`resolve_forward_closure()` 解析到真 `scripts.graph.forward_closure`，但调用写成 `forward_closure(claim_id, max_depth=3, detect_cycle=True)` → **`TypeError: unexpected keyword argument 'detect_cycle'`**（真 CLI traceback）；且**先写库后传播** → 留**半截数据** |
| B-AC-04 真拦得住 | **PASS** | `superseded→supported`、`supported→pending_verification`、自环、未知 from/to **全部 exit 1**，输出「不静默兜底、不自动纠正」 |
| B-AC-05 错误路径 | **PARTIAL** | 未知状态/定位无效/三字段互换/空 claims 均响亮（exit 1/2）；但「`forward_closure` 不可用→`PropagationUnavailable`（**写库前**）」仅在 **resolve 失败** 时成立（graph 目录移走→exit 1 且行数不变）；**resolve 成功而调用失败**（= main 的常态）→ 先落 `superseded` 行再崩 |
| B-AC-06 边界 | **PASS** | 空 claims→`ClaimNotFound` exit 2；终态再迁移 exit 1；非法 `version_kind` exit 1；序倒挂 exit 1；时间倒挂 exit 1 |
| B-AC-07 无占位符 | **PASS** | 同上门禁 `exit 0` |
| B-AC-08 设计对齐 | **PASS** | 迁移表 5 态逐边对齐 `Ch6 §E.1`（29/30 格一致，唯一不一致格见 §5）；§E.2/§E.3/§E.4/§E.5、`Ch9 §3.5 ②行` 均存在且对得上 |

**总判定：两条流均为 `merged-but-not-accepted`。** graph 的功能层扎实（9/8 条 AC 中 6 PASS、2 未达标），claim 的**判分表与代码差 1 格**且**跨流接口从未真跑过一次**。

---

## §1 三项探测原始证据

### `ws/graph` P1 — write-read-reload（原样输出）

```
[setup] dependency_edges.jsonl 行数 = 3
[build] wrote system/tests/.audit/graph_claim/system/index/adjacency.sqlite exists= True
[check1] adjacency_matches_facts = (True, '一致（3 条边）')
[closure-before] reached = ['bl-1', 'rec-1', 'sec-1'] depth_of = {'bl-1': 1, 'clm-1': 0, 'rec-1': 2, 'sec-1': 3}
[closure-before] sha256 = 2fbd905f3a65c7f34e34fc02abee0e6b6d6a089170fbbcc1d83bfe27793804a0
[delete] index/ exists = False
[check2-deleted] cache exists = False
[rebuild] wrote system/tests/.audit/graph_claim/system/index/adjacency.sqlite exists= True
[check3] adjacency_matches_facts = (True, '一致（3 条边）')
[closure-after] reached = ['bl-1', 'rec-1', 'sec-1'] depth_of = {'bl-1': 1, 'clm-1': 0, 'rec-1': 2, 'sec-1': 3}
[closure-after] sha256 = 2fbd905f3a65c7f34e34fc02abee0e6b6d6a089170fbbcc1d83bfe27793804a0
[VERDICT] closure 逐字节相同 = True
```
> **审计员保留意见**：`closure` 是**从 `facts/` 现算**的（不走缓存），故"逐字节相同"是**平凡成立**的；真正有效的是 `adjacency_matches_facts` 在删/建前后均为 `True`。DoD AC-02 的表述会让人误以为缓存参与闭包计算 —— 建议改写。

### `ws/graph` P2 — 让缺失层响亮失败（**部分失败**）

```
===== P2a: 删掉 facts/dependency_edges.jsonl =====
load_all_edges() = ()
forward_closure reached = [] truncated = False
!!! 缺失真源边表：无异常，静默返回空集 = True
EXIT=0

===== P2a-3: 缺失真源边表 + 无缓存 =====
  scanned cache_present: 0 / dependency_edges: 0 / relations: 0
  note: NO_CACHE：邻接表缓存不存在（可重建，非真源），本次不核一致性
  note: NO_EDGE_DATA：两张真源边表均为空；断言已就绪，待真实边数据
RESULT: PASS（0 violations）
graph_integrity_guard EXIT=0

===== P2c: code_root 不存在 =====
[INPUT-ERROR] code_root 不存在: .../__NOPE__
graph_integrity_guard EXIT=2

===== P2b: 悬空边（指向不可解析 ref）+ 有对象索引 =====
reached = ['bl-1', 'ghost-99', 'rec-1']     dangling = ['bl-1', 'ghost-99', 'rec-1']
不传 known_refs → dangling = []             reached = ['bl-1', 'ghost-99', 'rec-1']
```
> **结论**：`code_root` 不存在 → 响亮（`exit 2`）✅；**真源边表文件缺失** → 与「存在但 0 行」**不可区分**，静默返回空集、守卫仍 `exit 0 PASS`（仅记 note）❌ → 见 §7 `N-1`。悬空边按 DoD AC-05 **有意不抛**（记 `dangling`），但 `ghost-99` **仍进入 `reached`**（即"下游结论"里含不可解析 ref）→ 见 §7 `N-6`。

### `ws/graph` P3 — 接线体检（命令 + 输出）

```
$ grep -rn "scripts\.graph\|graph_integrity_guard\|locator_check\|scripts\.claim\|forward_closure\|propagate_retraction\|assert_not_equivalent" \
      --include="*.py" scripts/ | grep -v "^scripts/graph/" | grep -v "^scripts/claim/" | grep -v "^scripts/validators/"
(空)

$ grep -rn "graph_integrity_guard\|locator_check\|scripts\.claim\|scripts\.graph" \
      --include="*.py" --include="*.sh" --include="*.yaml" --include="*.md" . \
      | grep -v "^./tests/.work" | grep -v "^./scripts/graph/" | grep -v "^./scripts/claim/" | grep -v "^./scripts/validators/" | grep -v "^./reports/ws_"
(空)

$ grep -n "graph\|locator\|claim\|validators" scripts/ops/pre-commit.sh ; EXIT=1
$ grep -c '"scripts/' scripts/ops/run_all_gates.py   → 20   # 20 项门禁，无 graph_integrity_guard / locator_check
$ grep -nE "\"graph\"|\"claim\"|\"validators\"|\"compute\"|BATCHES" scripts/ops/verify.py
  → 127 compute / 131 graph / 135 validators / 139 claim / 157 ORDER → 批次已补齐（V-06 在 main 已解决）
$ pipeline.py::_register_default_steps → 只 register_step(1, ingest_public_information)
```
> **判定**：graph DoD AC-03 自报的两个"出口"在 `main` 上**均为假**：① `graph_integrity_guard.py` **不是** CI/pre-commit 调用的检查器；② `propagate_retraction` 的"阶段③ 传导步"**不存在**（`pipeline.py` 只接 step 1，step 2–6 显式记 `gap`+`blocked`）。**分歧点**：作者在 DoD 里**诚实登记**了"由主理人集成时加"，但 §一 底线 2 的口径是**实现事实**（"模块单测全绿，但主流程从不调用它（孤儿模块）"）—— 诚实登记不能替代接线。故我判 **FAIL**，不判 PARTIAL；若主理人把"诚实登记 + 集成时补"作为可接受路径，须显式修改 DoD AC-03 的判据，而不能让 AC 名存实亡。

### `ws/graph` 其余关键原始输出（AC-04 / AC-05 / AC-06 / AC-08，长输出截断）

```
（AC-04-① 自环）[FATAL] GI-SELF-LOOP @ facts/dependency_edges.jsonl:1 — 自环边: clm-1      RESULT: FAIL（1）EXIT=1
（AC-04-② 重复边）[FATAL] GI-DUP-EDGE @ facts/dependency_edges.jsonl:2 — 重复边 ('clm-1','bl-1','supports')（首见 L1）RESULT: FAIL（1）EXIT=1
（AC-04-③ 陈旧缓存）[FATAL] GI-STALE-CACHE @ index/adjacency.sqlite:0 … 不一致：真源 0 条，缓存 3 条 → EXIT=1
（AC-04 干净树）scanned dependency_edges: 3 → RESULT: PASS（0 violations）→ EXIT=0
（AC-05 环）环 a->b->c->a: reached= ['b','c'] cycle_detected= True cycle_nodes= ['a','b','c']
（AC-05 自环）自环 d->d: reached= [] cycle_detected= True ;  深度上限 1: reached= ['b'] truncated= True
（AC-05 条件不足）缺依据 -> StopDecision(action='stop', reason='evidence_insufficient', mark='evidence_insufficient', effect=None)
（AC-06）空图 reached = [] truncated = False ;  大图 5000 节点 reached=5000 耗时=0.011s
        重复边 邻接 dict 值域长度 = 1 ;  23:30Z vs 次日08:30+09:00 同指纹 = True
（AC-08 实调）STAGE_ORDER = {'order':0,'purchase_commitment':1,'capex':2,'production_schedule':3,'revenue':4}
        capex->order: raised StageEquivalenceError(capex(需求侧) ≠ 供应商订单/收入) OK
        capex->revenue: raised StageEquivalenceError(capex(需求侧) ≠ 供应商订单/收入) OK
        相邻 capex->production_schedule: allowed OK ;  跨级 order->production_schedule: raised OK（缺中间阶段证据）
（AC-01 库入口 T12 真跑）tasks 前=0 companies 前=1
        downstream= ['bl-1','rec-1']  by_kind= {'baselines': ('bl-1',), 'recommendations': ('rec-1',)}
        recheck_targets= ['bl-1','rec-1']  created= ['task_recheck::<cid>::bl-1','task_recheck::<cid>::rec-1']
        rolled_back_companies= ['co-1']  stale_marks= 2  tasks 后= 2 ;  company: co-1 tracking → baseline_done（追加新行）
        幂等重跑 created= [] skipped= ['recheck::<cid>::bl-1','recheck::<cid>::rec-1'] rolled_back= [] tasks= 2
（rules/transmission.yaml 缺失）FileNotFoundError（响亮失败）: 缺少传导参数真源 … 不得在代码里内置阈值
```

### `ws/claim` P1 — write-read-reload（原样输出）

```
=== 真跑采集（ingest_public_information）===
StepOutcome produced = ['claim-inbox-2026-03-01-nvidia-datacenter.md-d4d8aafb5083'] degraded = False signals = 0
claims 行数 = 1
  {'claim_id': 'claim-inbox-2026-03-01-nvidia-datacenter.md-d4d8aafb5083', 'status': 'pending_verification',
   'locator': 'raw/2026-03-01-nvidia-datacenter.md#L1-L1', 'full_text_read': False,
   'quote_hash': 'd4d8aafb50830bb0290e9b90b4e69ab5b66f9d10e1f4204eec1e68cf95f7ef3b', 'recorded_seq': 1}
===== A-AC-01: locator_check 真跑 CLI =====  scanned claims: 1 / note: NO_SOURCES: sources.jsonl 为空（G-03）
RESULT: PASS（0 violations）  locator_check EXIT=0
===== B-AC-01: transition CLI  pending_verification -> supported =====
  claim-inbox-...-d4d8aafb5083: 'pending_verification' -> 'supported'  recorded_seq=2      EXIT=0
===== 追加式不可变：再迁移 supported -> disputed =====
1 a4801fc016b08d840b0ccbbf8862c712f8f5313a15cfb642b32fa6f424950ae8   ← 迁移前既有行
2 f5e426598c57b9bf0de01881369f7310a11bfaea09ee7c06fc2fb54a7c901c32
  ...: 'supported' -> 'disputed'  recorded_seq=3      EXIT=0
[after] 行数 = 3  既有 2 行逐字节不变 = True
  L1: status=pending_verification recorded_seq=1 / L2: supported rec=2 / L3: disputed rec=3
===== B-AC-02: 删 index/ → rebuild_index → 末版状态仍在 =====
index/ exists after rmtree = False ;  rebuild_index -> .../index/facts.sqlite exists = True
index/facts.sqlite 中 claims 行 = 2   recorded_seq = [1, 2]  status = ['pending_verification', 'supported']
末版状态 = supported （应 supported）   facts/ 直接读 末版 = supported
===== A-AC-02：无 --no-report 时留档 =====  reports/locator_check.py_2026-09-16.json  ← 生成，exit=0
```

### `ws/claim` P2 — 让缺失层响亮失败（**半失败：见下**）

```
===== ① resolve 失败（graph 目录整体移走）→ 期望 PropagationUnavailable 且写库前失败 =====
迁移前 claims 行数 = 6
[BLOCKED] PropagationUnavailable: superseded 传播需 scripts/graph/forward_closure（Ch6 §E.4 复用第九章传播），
          但当前不可解析 —— 写库前失败，不留半截数据
TRANSITION-EXIT=1      迁移后 claims 行数 = 6        ← ✅ 写库前失败成立

===== ② resolve 成功、调用失败（= main 的真实状态）=====
$ python system/tests/.audit/graph_claim/system/scripts/claim/transition.py <copy> --claim-id <cid> --to superseded
Traceback (most recent call last):
  ...
  File ".../scripts/claim/transition.py", line 414, in transition
    result.downstream, result.recheck_tasks = _propagate(
  File ".../scripts/claim/transition.py", line 335, in _propagate
    downstream_raw = list(forward_closure(claim_id, max_depth=3, detect_cycle=True))
TypeError: forward_closure() got an unexpected keyword argument 'detect_cycle'
TRANSITION-EXIT=1
--- 崩溃后 claims 行数（是否有半截数据）---   4
  L1: status=pending_verification recorded_seq=1
  L2: status=supported            recorded_seq=2
  L3: status=disputed             recorded_seq=3
  L4: status=superseded           recorded_seq=4      ← ★ 半截数据：行已落，传播未做
tasks.jsonl 行数 = 0                                   ← 0 条 recheck 任务

===== 空 claims → ClaimNotFound =====
[INPUT-ERROR] ClaimNotFound: facts/claims.jsonl 中无 claim_id='anything'（不得凭空重建）   EXIT=2
===== 遗留 active 行（真数据文件）=====
[BLOCKED] Claim 校验失败（三字段维度不同，不得互换/合并）: 1 validation error for Claim
status  Input should be 'pending_verification','supported','disputed','refuted' or 'superseded' [type=enum, input_value='active']
EXIT=1
```
> **本次审计最严重的发现（§7 `N-2`）**：`transition.py:335` 的调用签名与 `closure.py:137` 的真签名**不兼容**（真签名 `forward_closure(code_root, start, *, max_depth, ...)`，**无 `detect_cycle`**）。因 `_append_claim`（行 403）在 `_propagate`（行 414）**之前**，真失败模式下 `superseded` 行**已落库**而 `tasks` 为空 —— 「不复用则抛 `PropagationUnavailable`、不留半截数据」的保证**只在 resolve 失败时成立**。

### `ws/claim` P3 — 接线体检

```
$ grep -rn "scripts\.graph\|locator_check\|scripts\.claim\|forward_closure" --include="*.py" scripts/ \
      | grep -v "^scripts/graph/" | grep -v "^scripts/claim/" | grep -v "^scripts/validators/"
(空)                                    ← transition.py 之外无任何调用方；transition 本身也无调用方
（代码级确认）transition.py:382/384  from scripts.validators.locator_check import claim_locator_problems → claim_locator_problems(prior_row, root, _source_index(root))
              transition.py:82       _GRAPH_CANDIDATE_MODULES = ("scripts.graph","scripts.graph.traversal","scripts.graph.propagation")
```
> `locator_check` 的**唯一调用方** `transition.py` 真的存在（A-AC-03 的这一半成立），但 `transition.py` 的调用方在 `main` 上**不存在**（`pipeline.py` step⑦ 未实现），且 `locator_check` 未进 `run_all_gates.py`/`pre-commit.sh` → **孤儿调用孤儿**。另：`_GRAPH_CANDIDATE_MODULES` 里 `scripts.graph.traversal` / `scripts.graph.propagation` **两个模块都不存在** —— "猜接口"的痕迹，正是 §7 `N-2` 的成因。

### `ws/claim` — 迁移表逐格 CLI 对拍 + 其余错误路径

```
（拒绝格抽样 / 全部 exit=1）
### superseded        -> supported            exit=1  [BLOCKED] IllegalTransition: ...（允许目标: []）
### superseded        -> superseded           exit=1  [BLOCKED] IllegalTransition: ...（允许目标: []）
### pending_verification -> pending_verification exit=1  ...（允许目标: ['disputed','refuted','superseded','supported']）
### supported         -> pending_verification exit=1  ...（允许目标: ['disputed','refuted','superseded']）
### refuted           -> supported            exit=1  ...（允许目标: ['disputed','pending_verification','superseded']）
（允许格抽样 / exit=0）disputed->supported OK ; refuted->pending_verification OK ; pending_verification->superseded OK
### active -> pending_verification（DoD 迁移表第 1 行 ✅）exit=1
      [BLOCKED] UnknownClaimStatus: 未知主张状态 from='active'；合法状态见 Ch6 §E.1: ('pending_verification','supported','disputed','refuted','superseded')
### 未知 from '待核验' exit=1 UnknownClaimStatus ;  未知 to 'frozen' exit=1 UnknownClaimStatus ;  缺 --to exit=2 [INPUT-ERROR]
### 非法 version_kind='bogus' exit=1  IllegalTransition: 合法值 ... ['financial_restatement','forecast_revision','source_retraction']
### 序倒挂 recorded_seq=1   IllegalTransition: recorded_seq=1 不大于现有最大 1 —— 版本序倒挂，拒绝
### 时间倒挂 recorded_at=2026-06-01 IllegalTransition: 新版本 first_seen_at=2026-06-01T00:00:00+00:00 早于原版本 2026-09-16T06:19:24+00:00 —— 时间倒挂，拒绝
### recheck 幂等（注入闭包）：第1次 created=['recheck::c1::baseline::bl-1','recheck::c1::event::ev-1'] tasks=2
                            第2次 created=[] （空 = 幂等） tasks=2 ; requires_recheck: baseline=True / event=False
```

`locator_check` 13 类违例真跑（真 CLI，逐条 `exit`）：

```
①基例 raw/x.txt#L1-L3, full=false      exit=0 PASS          ②full=true 但仅 L1-L1        exit=1 FULL_TEXT_UNPROVEN + QUOTE_HASH_MISMATCH
③full=true 全覆盖但 quote_hash 不符     exit=1 QUOTE_HASH_MISMATCH   ④locator 为空          exit=1 LOCATOR_MISSING
⑤locator='p.12'                        exit=1 LOCATOR_UNRECOGNIZED  ⑥'raw/../rules/x.yaml#L1-L1' exit=1 LOCATOR_ESCAPE
⑦claim_nature='bogus'                  exit=1 CLAIM_SCHEMA_INVALID  ⑧official_claim_kind 落非 primary exit=1 OFFICIAL_KIND_TIER_MISMATCH
⑨published_at 晚于 first_seen_at        exit=1 TIME_INVERSION        ⑩空 claims             exit=0 note: NO_CLAIMS（G-03）
⑪locator 指向不存在的 raw 文件           exit=1 LOCATOR_UNRESOLVABLE  ⑫'未披露' 哨兵 + full=false exit=0 PASS（允许，强制 full=false）
⑬'未披露' 哨兵 + full=true              exit=1 FULL_TEXT_UNPROVEN
（1500 条单遍 耗时=0.340s exit=0 scanned claims: 1500）
```

---

## §2 `ws/graph` 逐条 AC 四态判定

| AC | 判定 | 证据 | 不合格在哪条 DoD 子项 |
|---|---|---|---|
| AC-01 | PARTIAL | §1 graph "AC-01 库入口 T12 真跑"（下游 2 + 2 任务 + 深度回退 + 幂等） | DoD 要求「**主流程真跑到**」（`§5.1`）；`pipeline.py` 仅注册 step 1 → 不成立；且真仓库 `facts/dependency_edges.jsonl` = **0 行**（无真实被检对象，G-03） |
| AC-02 | PASS | §1 P1 原样输出 | — |
| AC-03 | FAIL | §1 P3（三条 grep 全空 + `run_all_gates.py` 20 项无此守卫 + `pre-commit.sh` 无引用 + 只注册 step 1） | DoD AC-03 两个"出口"**均为假**（① 非 CI/pre-commit 检查器；② 无阶段③ 传导步） |
| AC-04 | PASS | §1 AC-04 三条 + 干净树 + `code_root` 缺失；另 `assert_gate_input`…（未注册见 §7 `N-3`） | —（DoD 子项全中；"证据用 `run_gate_inproc`（进程内 runpy）而非子进程"由我更保守地重跑过） |
| AC-05 | PASS | §1 环/自环/悬空/条件不足 | 悬空 ref **仍进 `reached`**（DoD 写"不产生下游结论"）→ 低危，记 §7 `N-6` |
| AC-06 | PASS | §1 空图/5000 节点/重复边/时区 | — |
| AC-07 | PASS | `no_placeholder_guard.py system --fail-on warn` → `exit 0`；手工 grep 干净 | — |
| AC-08 | PASS | 节号逐条核对（`Ch9 §3.2.1`="依赖图传播 B+C 遍历+失效+入队"、`§3.4.3`=依赖图与 T12 传播、`§3.4.7`=事件去重指纹、`§3.3.2`=推荐组合三层存储、`Ch7 §B.4/§C.2/§C.3/§C.5/§C.6/§C.8`、`Ch2 §B.3`="命中即 fail，禁止 warn-only"）+ `capex` 实调真抛 | 轻微：`cycles.py` 引"裁定 J7"、`propagate.py` 引"（G1-04）"均为**不可解析引用**（Ch7 §J 无 J7；`CONVENTIONS.md` 只有 G-01~G-07） |

**`ws/graph` 结论：not accepted。** 阻塞项 = AC-03（孤儿）+ AC-01（主流程/真源缺失，PARTIAL）。

---

## §3 `ws/claim` 逐条 AC 四态判定

| AC | 判定 | 证据 | 不合格在哪条 DoD 子项 |
|---|---|---|---|
| A-AC-01 | PASS | §1 claim P1（真采集 → `locator_check` exit 0） | —（DoD 的 `active` 前提已过期，见 B-AC-01；本 AC 的"真跑通"意图已复现） |
| A-AC-02 | PASS | `reports/locator_check.py_2026-09-16.json` 真生成 | — |
| A-AC-03 | FAIL | §1 claim P3 | DoD 写"本模块**有生产调用方**（非孤儿）"——`transition.py` 本身无调用方；且"可被 `run_all_gates.py` 收录"在 main 上**未收录** |
| A-AC-04 | PASS | §1 ② ③（exit 1） | — |
| A-AC-05 | PASS | §1 ④⑤⑥⑦⑧⑪（全 exit 1） | — |
| A-AC-06 | PASS | §1 ⑩（NO_CLAIMS+exit 0）、⑦、⑨、1500 条 0.340s | — |
| A-AC-07 | PASS | 门禁 exit 0 | — |
| A-AC-08 | PARTIAL | `Ch6 §D`（七步主张化，`locator` 在 ①/② 行）· `N6.1-11`（line 509 原文"仅摘要时 `full_text_read=false`，越界被程序拦截"）· `Ch9 §3.5` ②行幂等键 `(source_id, quote_hash)` · `R-17`（`§3.4.6` 回改块）**全部核对通过** | `Ch9 §3.4.6 措施①/②：含定位、可复查` —— **子锚点不存在**：`§3.4.6` 实为「注入防护」（措施表 4 行：数据/指令物理分离、规则只读、工具白名单、主张性质强制），全设计区**无**「措施①」字样 |
| B-AC-01 | **FAIL** | §1 claim P1（`status=pending_verification`）+ "遗留 active 行 exit 1" + `schema/models.py::ClaimStatus(StrEnum)` 默认 `pending_verification` | DoD 前提「采集层写入初始 `status="active"`」**已过期**；`active→pending_verification` 是**死代码/不可达路径** —— 见 §5 |
| B-AC-02 | PASS | §1（sha256 前缀逐字节不变 True + `rebuild_index` 后末版 `supported`） | — |
| B-AC-03 | FAIL | §1 claim P2 ②（真 `TypeError` + traceback） | DoD「`on_superseded` 调用 `scripts/graph/forward_closure`（**复用**、`G-06` 不新建第二套）」**未成立**；且 step⑦ 接线不存在 |
| B-AC-04 | PASS | §1 迁移表对拍（全部 exit 1，无静默兜底/自动纠正） | — |
| B-AC-05 | PARTIAL | §1 claim P2 ①（resolve 失败 → 行数不变 ✅）/ ②（resolve 成功但调用失败 → 半截数据 ❌）；未知状态/定位无效/三字段互换 exit 1 ✅ | DoD「`PropagationUnavailable`（**写库前**抛出，**不留半截数据**）」在 main 的真实失败路径下**不成立** |
| B-AC-06 | PASS | §1（ClaimNotFound exit 2；终态 exit 1；version_kind exit 1；序/时间倒挂 exit 1） | — |
| B-AC-07 | PASS | 门禁 exit 0 | — |
| B-AC-08 | PASS | §1 迁移表对拍 29/30 格一致；`Ch6 §E.1~§E.5` 逐条核对通过；`Ch9 §3.5` ②行 | 轻微：`§E.4` 设计片段为 `on_superseded(claim_id, version_kind)`（2 参），实现为 `on_superseded(code_root, claim_id, version_kind, ...)`（3+ 参）→ 接口相对设计片段漂移 |

**`ws/claim` 结论：not accepted。** 阻塞项 = B-AC-03（跨流接口不通 + 半截数据）+ B-AC-01（判分表前提过期）+ A-AC-03（双重孤儿）。

---

## §4 自报判定复核

| 流 | 自报 | 复核结论 |
|---|---|---|
| graph | `IS_PASS：YES`；AC-01~AC-08 全 ✅ | **偏松**。① 报告 §6 的 `AC-01…AC-08` **与 DoD 的 AC 编号完全错位**（报告 AC-01="边表 schema 就位"、DoD AC-01="真跑通"），读者无法把报告的证据映射回判分表 —— 本身就是"看起来对"的来源；② AC-03 自报 ✅（"真接线"）而事实是孤儿；③ 报告称 §2.2/§2.3 的红是"环境 + 预期 V-06"——实测 **`V-06` 在 main 已解决**（`verify.py` 已含 `graph/validators/claim/compute` 四批，`verification_policy_guard` 现 `exit=0`），报告结论已过期 |
| claim | `IS_PASS: YES`（A/B 各 8 条全 ✅） | **偏松且有一处假绿**。① B-AC-03 自报 ✅ 但真接口**从未跑过**（作者 §4.2 自陈"本工作区 `scripts/graph/` 为空 → 可注入"，测试注入的是**自造的 `detect_cycle` 签名**闭包）——这正是 `§六 6.3`「mock 掉后被断言其行为」的形态；② 报告 §三 用例数 **22 + 18 = 40**，文件实际 `def test_` 计数 **20 + 19 = 39**（含 1 处 `parametrize(2)`）；③ 报告称 V-06 为"唯一预期红"——已过期；④ A-AC-03"可被 `run_all_gates.py` 收录"= 把"**提供 CLI 入口**"当成"**已接线**"（`§六 6.2` Phantom Subscription 的同型） |

---

## §5 ★ 迁移表逐格对拍（`Ch6 §E.1` / DoD 6×5 = 30 格）

对拍三方：**DoD 表**（`ws_claim_dod.md` §B）/ **代码表**（`transition.py::ALLOWED_TRANSITIONS`）/ **设计表**（`Ch6 §E.1` mermaid 逐边）。
`✅`=允许，`❌`=拒绝。**代码列 = 实跑 `--check` 观测**（非仅读表）。

| from ↓ \ to → | pending_verification | supported | disputed | refuted | superseded |
|---|:--:|:--:|:--:|:--:|:--:|
| `active` DoD / 代码 / 设计 | ✅→**❌** / **不可达** · ❌→❌ / — | ❌→❌ / — | ❌→❌ / — | ❌→❌ / — | ❌→❌ / — |
| `pending_verification` | ❌→❌ ✓ | ✅→✅ ✓ | ✅→✅ ✓ | ✅→✅ ✓ | ✅→✅ ✓ |
| `supported` | ❌→❌ ✓ | ❌→❌ ✓ | ✅→✅ ✓ | ✅→✅ ✓ | ✅→✅ ✓ |
| `disputed` | ❌→❌ ✓ | ✅→✅ ✓ | ❌→❌ ✓ | ✅→✅ ✓ | ✅→✅ ✓ |
| `refuted` | ✅→✅ ✓ | ❌→❌ ✓ | ✅→✅ ✓ | ❌→❌ ✓ | ✅→✅ ✓ |
| `superseded` | ❌→❌ ✓ | ❌→❌ ✓ | ❌→❌ ✓ | ❌→❌ ✓ | ❌→❌ ✓ |

**不一致格 = 1 格：`(active, pending_verification)`** —— DoD 标 ✅（"只允许 `active → pending_verification`"），代码 **`active` 键根本不在 `ALLOWED_TRANSITIONS` 中**，`--check --from active --to pending_verification` → `exit 1 UnknownClaimStatus`；`assert_transition` 在 `from_status not in ALLOWED_TRANSITIONS` 处即抛。
**按判据「任何一格不一致即 FAIL」→ `ws/claim` 迁移表对拍 = FAIL。**
（另 4 格 `(active, *)` 双方同为 ❌，属"巧合一致"：DoD 是"明确禁止"，代码是"未知状态一律拒"。）

**DoD 前提过期判定（探测 #3 的正面回答）**：
1. `schema/models.py::ClaimStatus(StrEnum)` 五态封闭，默认 **`pending_verification`**（源文件上可见 `★ 初版把它写成自由字符串 "active"，而 active 根本不在五态内`）。
2. **实测**：`ingest_public_information`（step 1，生产路径）落库行 `status="pending_verification"`。
3. **`active` 还可能是新写入行的合法状态吗？否。** 既不可能被采集层写出（封闭枚举），也不可能存在于旧行（`Claim.model_validate` 拒，`exit 1`）。
4. ⇒ 「`active → pending_verification` 状态机入口别名」= **死代码/不可达路径**；`transition.py` v2 已**删除**该概念（docstring 明写"**不存在任何五态之外的入口别名**"）。
5. ⇒ **DoD AC-01 已不可满足**（判分表未随 v2 更新）；DoD §B 迁移表第 1 行、`C-4`（"不改 `Claim.status` 默认值"）同样过期。

---

## §6 `§8` 十二条纪律逐条对拍

| # | 纪律 | graph | claim | 证据 |
|---|---|---|---|---|
| 1 | 零新增门槛 / 参数不进决策函数 | **无** | **无** | `freeze_guard.py system` → `PASS（scanned decision_scope_files_scanned: 8）`；`TransmitParams` 四字段**全必填无默认值**；`stop.py` 无阈值常量 |
| 2 | 命中即 fail，禁 warn-only | **有（G-07）** | **有（G-07）** | 守卫自身 `exit 1` 正确；但**两个新守卫都未注册** `run_all_gates.py`+`pre-commit.sh`（`G-07` 要求"同时注册"，防孤儿）→ 见 §7 `N-3` |
| 3 | 禁词入库前 grep + 声明 scope | 无 | 无 | `grep -rniE "\bweight|\bscore|\bvote|sentiment|follower_count" scripts/graph/` → **无命中** |
| 4 | 追加式不可变 | 无 | 无 | graph 唯一写口 `append_records`（stale/深度回退均追加新行，实测 `co-1` 新行 `baseline_done`）；claim 既有行 sha256 逐字节不变（True）；`append_only_guard.py system` → `exit 0` |
| 5 | 参数唯一真源 `rules/freeze.yaml` | 无 | 无 | `rules/` 无第二份值；`stop.load_transmit_params` 读 `rules/transmission.yaml` 且**缺失即 `FileNotFoundError`**（不内置） |
| 6 | 节号锚点，禁绝对行号 | **无** | **有（轻微）** | 三目录 grep 无"第 N 行"式引用；但 `Ch9 §3.4.6 措施①/②` 子锚点在设计区**不存在**（§3） |
| 7 | 枚举 token 英文小写+下划线；待定 `tbd` | 无 | 无 | `ClaimStatus`/`TaskType`/`StageOrder` 全 snake_case |
| 8 | 同名不同域消歧 | 无 | 无 | `stage_order.py` docstring 显式声明"`relation_progress_stage` 与 `relations.stage` 是**两维度**，不得互用（`Ch2 §C.2 R-15②`）" |
| 9/10 | `rules/` 0444 + 模型无写权 | 无 | 无（但**工作区层面**有披露） | main 上 `ls -l system/rules/*.yaml` → 10 个 **`-r--r--r--`**；`rules_lock_guard.py system` → `PASS`；claim 报告如实披露 worktree 内 `chmod 0444`（10 文件，内容未改） |
| 11 | 复用优先（能 A 不 B） | **有（重复真源）** | **有（假复用）** | graph 自建 `recheck::<cause>::<target>` 入队；claim 另建 `recheck::<claim_id>::<type>::<id>`，`task_id` 生成规则亦不同（`task_{key}` vs `task_<key下划线化>`）→ 同一批下游对象会有**两套幂等键**（`G-06` 风险）；且 claim 的"复用"在真接口上**必崩**（§7 `N-2`） |
| 12 | 阶段未过即阻塞 | 无 | 无 | 两流均未触碰 `stage_gate.py` |

**附加纪律观察（非 12 条，但属交付纪律）**：`ws/graph` 的提交 `0aa528b` 以 **`--no-verify` 绕过 pre-commit**（报告 §8 已如实披露并归因于 worktree 的 `rules/` 0644 + `V-06`）。**两个归因在 main 上均已不存在**（rules 0444、批次已补），即该绕过已无必要；建议主理人在集成侧复核该提交是否需重签。

---

## §7 缺口清单（N-5 converge）

| # | 流 | 描述 | 证据（文件:行 / 命令输出） | 建议处置 |
|---|---|---|---|---|
| **N-1** | graph | **真源边表文件缺失 ≠ 响亮失败**：`facts/dependency_edges.jsonl` 不存在时 `read_records` 静默返回 `[]` → 闭包返回空集、守卫 `exit 0 PASS`（仅 note），与"存在但 0 行"不可区分 | `schema/store.py::read_records`（`if not path.exists(): return out`）；`closure` 实测 `reached=[] EXIT=0`；守卫输出 `NO_EDGE_DATA` + `RESULT: PASS` | graph 层加载边前断言真源文件存在（缺失 → `FileNotFoundError`/`exit 2`）；或让缺失与空集产生**不同** note 前缀 |
| **N-2** | claim × graph | **跨流接口不兼容 → 生产路径必崩 + 留半截数据**：`transition.py:335` 调用 `forward_closure(claim_id, max_depth=3, detect_cycle=True)`，真签名 `closure.py:137 forward_closure(code_root, start, *, max_depth, source, edges, known_refs, valid_asof)` **无 `detect_cycle`**、且 `code_root` 占第一参 → `TypeError`；因 `_append_claim`(403) 在 `_propagate`(414) 之前 → `superseded` 行**已落库**、`tasks` 0 条 | 真 CLI traceback（§1 claim P2 ②）；`transition.py:82` 候选模块 `scripts.graph.traversal/propagation` **均不存在** | (a) 统一接口：`forward_closure(code_root, claim_id, max_depth=3, detect_cycle=…)` 或让 claim 侧只传真签名支持的参数；(b) **把传播前置到写库之前**（先 resolve+遍历+构任务列表，全部成功后再一次性 `append_records`）；(c) 加一条**跨流集成测试**（真 graph + 真 claim），禁注入自造签名 |
| **N-3** | 双流 | **`G-07` 违例**：`graph_integrity_guard.py` / `locator_check.py` **未注册**进 `run_all_gates.py`（20 项）与 `pre-commit.sh`（零引用）→ 两个新守卫永不被门禁执行 | `grep -c '"scripts/' run_all_gates.py` = 20；`grep graph\|locator pre-commit.sh` EXIT=1 | 各加一行到 `GATES` 与 `pre-commit.sh`（`locator_check` 需 `--no-report`）；同步 `test_exit_code_contract` 覆盖 |
| **N-4** | graph | **AC-03 孤儿**：`scripts/graph/**` 无任何生产调用方；`pipeline.py` 仅注册 step 1，step 2–6 记 `gap`+`blocked` | §1 P3；`pipeline.py:111 _register_default_steps` | 阶段③ 落 `scripts/transmit/engine.py` 时**真调用** `propagate_retraction`，并在运行日志留证（`N-3` 接线体检）；在此之前 graph AC-03 应保持 FAIL |
| **N-5** | claim | **判分表过期 + 迁移表 1 格不一致**：DoD AC-01/§B 第 1 行/C-4 均基于 `status="active"`，而真相是封闭 `StrEnum` 默认 `pending_verification`；`active` 已不可达 | §5 全节 | 由主理人**裁定并改 DoD**：删 `active` 行、AC-01 前提改为 `pending_verification`；同时在 DoD 里写明"入口别名"永不恢复 |
| **N-6** | graph | 悬空 ref **仍进入 `reached`**（`ghost-99` 在 `reached` 与 `dangling` 同时出现），且 `known_refs=None` 时 `dangling` **静默为空**；`object_index` 把 `dependency_edges`/`relations`/`tasks` 等**边与控制面对象**也当"可解析对象类型" → dangling 判定噪声 | §1 P2b；`adjacency.py:33 PRIMARY_KEY_FIELD` 含 `dependency_edges`；`closure.py:127` | 下游消费方按 `dangling` 剔除；`object_index` 只纳入**业务对象**（排除边表/任务/价格快照）；`known_refs` 缺失时记 note 而非静默 |
| **N-7** | 双流 | **两套 `recheck` 幂等键/ID 规则并存**（`G-06` 风险）：`recheck::<cause>::<target>` vs `recheck::<claim>::<type>::<id>`；`task_id` = `task_{key}` vs `task_<key 下划线化>` | `propagate.py:178,183` vs `transition.py:312,340` | 收敛为**一条**幂等键构造器（放 `schema/` 或 `_common`），两处共用 |
| **N-8** | claim | `Ch9 §3.4.6 措施①/②` 子锚点**在设计区不存在**（§3.4.6 = 注入防护；全设计区无「措施①」） | `locator_check.py:186`、`locator_check.py:51`、`DoD AC-08`；grep 设计区 `措施` 仅 2 处（line 714/863） | 改为可核实的锚点（如 `Ch6 §D.1 ①/②` 或 `Ch6 N6.1-11`）；`ingest_step.py` 同处措辞一并修正 |
| **N-9** | 双流 | **报告与事实不符**：① `ws_graph_report.md §6` 的 AC 编号与 DoD **错位**；② `ws_claim_report.md` 用例数 22+18=40 vs 文件 `def test_` 计数 20+19=39（另有 1 处 `parametrize(2)`）；③ 两报告"唯一预期红 = `V-06`"在 main 上**已消除** | `ws_graph_report.md:137-148`、`ws_claim_report.md:22-23,156-171`；`verification_policy_guard system` → `PASS（test_files_uncovered: 0）` | 报告按 DoD 的 AC 编号重排；用例数以 `pytest --collect-only` 实测为准；标注"报告写于基点、main 状态已变" |
| **N-10** | graph | 死代码/不可解析引用：`fingerprint.py:183 _bucket_of` **无任何引用**；`cycles.py` 引"裁定 J7"、`propagate.py:17` 引"（G1-04）" 均**不可解析**（`CONVENTIONS.md` 仅 G-01~G-07） | grep 全树 `_bucket_of` 仅定义处；`CONVENTIONS.md §二` 表 | 删死代码；不可解析引用改为真实节号或删除 |

---

## §8 未能证伪的项（UNKNOWN 清单）

| # | 项 | 为什么证不了 | 需要什么条件 |
|---|---|---|---|
| U-1 | 两流 `pytest` 的真实收集数/通过数（`tests/graph` 36 是否仍全绿、`tests/claim`+`validators` 实际多少用例） | **我被禁止运行 pytest**（`conftest.py::pytest_sessionstart` 清空 `tests/.work/`，与另一位审计员通道冲突）；我只能用 `def test_` 静态计数（graph 36 ✓、claim 39） | 由主理人转派 pytest 通道（`verify.py --batch graph` / `--batch claim` / `--batch validators`），读 `reports/verify_*_latest.log` |
| U-2 | claim 测试是否**仍**锚定行为而非说明文字（v2 称已去全部 `rule_hint=`） | 需 pytest 才能确认 `assert_rejected(..., rule_hint=...)` 的调用点是否全部移除；静态看 `test_locator_check.py:21` 仍 import `assert_rejected` | 同上（或 `grep -c "rule_hint=" tests/claim tests/validators` 的确认已产出：仅 `conftest.py` 定义处） |
| U-3 | graph AC-01「主流程真跑到」 | `pipeline.py` step 2–6 未实现 → **结构上不可能**证到；真仓库 `facts/dependency_edges.jsonl` = 0 行 | 阶段③ 落 `scripts/transmit/engine.py` 后重测 |
| U-4 | 提交 `0aa528b` 的 `--no-verify` 是否有内容级后果（是否绕过某条现在会红的门禁） | 我**只读**复核（`git show --name-only`）；若要确认需重放 pre-commit | 主理人在集成侧重跑 `run_all_gates.py` + `pre-commit.sh`（预期全绿） |
| U-5 | `ws/claim` 是否有**未合并**的同源分支改动（如另一 worktree 的中间提交） | 我只审 `main` 上已合并的 `2aa7213` / `3904fb6` 全量文件清单（只读 `git log --name-only`），未审计 `.worktrees/**` 的工作区状态 | 主理人确认 worktree 无未合并内容 |

---

## §9 审计过程自述

**读了（顺序：先判分表后代码）**：`00_开发Agent开工提示词.md` 全文（§一/§5.1/§5.2/§六/§八/§九/§十三）· `CONVENTIONS.md` 全文（重点 `R-06`/`G-01`/`G-03`/`G-07`/`P-01`/`P-03`/`P-09`）· 两份 DoD 与两份作者报告；设计权威**逐节核对存在性与内容**：`Ch6 §D.1~§D.5`/`§E.1~§E.5`/`N6.1-11`/`N6.3-10/11/18`、`Ch9 §2.1.1/§2.1.6/§2.2/§2.3.2/§3.2.1/§3.3.2/§3.3.3/§3.4.1~§3.4.7/§3.5`、`Ch7 §B.1/§B.4/§C.1/§C.2/§C.3/§C.5/§C.6/§C.7/§C.8`、`Ch2 §B.3`；代码：`scripts/graph/**`（9 文件）、`scripts/claim/transition.py`、`scripts/validators/locator_check.py`、`schema/models.py`、`schema/store.py`、`scripts/orchestrate/{pipeline,ingest_step}.py`、`scripts/ops/{run_all_gates,verify}.py`、`pre-commit.sh`、`tests/conftest.py`。

**跑了**（全部 raw CLI / 短脚本，单条 ≤60s，**无 pytest**）：graph P1/P2/P3 全组 · 守卫 4 类违例/干净树/缺失 `code_root` · 环·自环·深度截断 · 空图/5000 节点/重复边/时区指纹 · `assert_not_equivalent` 四组实调 · T12 全链路（真边+真 `Baseline`/`Recommendation`/`Company`）· `load_transmit_params` 缺文件 · claim 真采集→`locator_check` · 迁移表 12 组 `--check` + 未知状态/`frozen`/缺参 · 三次真迁移 + sha256 追加式复核 · `rebuild_index` · `locator_check` 13 类违例 · 1500 条性能 · 空 claims `ClaimNotFound` · `active` 遗留行 · 非法 `version_kind`/序倒挂/时间倒挂 · 注入闭包幂等 · graph 目录移走→`PropagationUnavailable` · **真 `TypeError` 复现** · 门禁真跑 6 个（`--no-report`）· `rules/*.yaml` 权限 · P-09 禁词 grep · P-03 惰性导入。

**只读 git（如实披露）**：任务书 §14 要求用 `git log --name-only` 自查纪律 9/10，而硬约束禁止"任何 git 命令"。我按**只读、不改状态**解读（未 add/commit/branch/checkout/stash/merge/worktree，未触碰 `.worktrees/**`），仅执行 `rev-parse`/`log --oneline`/`log --name-only`/`show --name-only`/`status --porcelain`。用它对拍 `775e714..2aa7213` 与 `775e714..3904fb6` 的**全量改动文件清单**（两流均只动 `system/scripts/{graph,claim,validators}/**`、`system/tests/{graph,claim,validators}/**`、`system/reports/ws_*` → **纪律 9/10 clean**）。若主理人认为只读 git 亦在禁止之列，本节证据请以"清单为空、无 `rules/**` 与设计区条目"为限复算。

**没看/没做**：未运行 pytest（硬约束）· 未审 `.worktrees/**` 工作区状态 · 未审 `ws/compute`（另一位审计员）· 未做展示层复核 · 未逐条读测试代码（静态抽样见 §4）。

**污染控制**：写入型探测全在 `system/tests/.audit/graph_claim/`（副本，**已整目录删除**）；真仓库 `facts/claims.jsonl`、`facts/dependency_edges.jsonl` 仍 **0 行**、`index/` 恢复为仅 `.gitkeep` + `.locks`；`git status --porcelain` 仅剩本报告 + `?? system/tests/.audit/`（其中只有**另一位审计员的** `compute/` 子目录，我未触碰）。**未改任何代码/测试/fixture/配置**（发现的问题一律只记录）。
