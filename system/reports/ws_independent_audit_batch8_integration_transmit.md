# `§九` 独立审计 — 批次 8（集成面 + `ws/ch7-transmit` + 真实数据）

- 审计员：`independent-auditor-2`（对抗性、换眼）
- 审计基线：`main = f1c79a2`（工作区另有**未提交**改动，见 `§2-B6`）
- 审计对象：**A** `ws/ch7-transmit`（`66694a3`/合并 `97af071`）· **B** 主理人自写的批次 8 集成改动 · **C** 真实数据（`ws-real-collect`，合并 `bb42184`）
- 硬约束遵守：**未执行任何 git 写命令**；**未修改任何仓库文件**（唯一写入 = 本报告）；**未运行 pytest**；所有写型探针只跑在 `system/tests/.audit/batch10_b/` 的副本上（`raw/`、`facts/`、`rules/` 的真源指纹在本单首尾**逐字节相同**）。
- 行数说明：本报告 ≤320 行；`§1`+`§2`+`§5#1/#3` 为最高优先级且均**实测**，`§4`/`§7` 如实标 UNKNOWN。

---

## §0 结论摘要

| 块 | 判定 | 一句话 |
|---|---|---|
| **A** `ws/ch7-transmit` | **PASS（建议接受）+ 1 PARTIAL** | 真复用、参数真外置、无写路径、无占位符；唯一瑕疵：`gain_map` 的保守键 `undisclosed` **不在装载期校验**（延迟到运行时才炸）。 |
| **B** 主理人集成改动 | **PASS（4 项）· PARTIAL（2 项）· UNKNOWN（1 项）** | `G-RC-05` root 绑定**反向验证通过**；`resume`/`run_daily` 聚合语义**已一致**（但违例枚举仍不等）；空真源契约**机制成立**（"仍绿"需 pytest 通道）；`reports/` 免扫是**未登记的静默宽免**；`stage_gate` 接线**未提交**。 |
| **C** 真实数据 | **PASS + 2 note** | 4/4 `quote_hash` 我自算 sha256 **全中**，`locator` 行数**精确**，渲染取舍**如实登记**；note：`raw/inbox` 与 `raw/` 有**同一份源的字节级双份**；`full_text_read=false` 与"全篇覆盖"自相矛盾地保守。 |

**FAIL 0 · PARTIAL 3 · UNKNOWN 3 · 新增缺口 6**（`§6`）。
最重要发现（按危害排序）：
1. **`stage_gate.py::coverage_verifiable` 接线与 `verify.py` 新增两批都在工作区、不在提交树**（`§2-B6`，可被 `git checkout .` 静默抹掉）。
2. **`no_placeholder_guard` 的 `EXEMPT_PATTERNS` 内嵌 `"reports/"` 子串免扫**：`code_root` 下**任何**名为 `reports` 的目录整目录、全规则、**静默**免扫 —— 与清单自称的"唯一豁免入口"矛盾（`§2-B5`）。
3. `run_daily` 重跑**每次追加重复 claim**（副本实测同一 `claim_id` ×6）—— 幂等键面（`§5-#1`）。
4. `T-10` 比登记的**更严重**：四要素里**两条**（`prev_version_id`、`computation`）对"首条定性建议"结构性不可达（`§4`）。

---

## §1 ★ `transmit` 复用与参数外置

### 1.1 `G-06`：**无第二实现**（grep 为证）

对 `system/scripts/transmit/**` 检索 `def forward_closure|def should_stop|def assert_not_equivalent|def tarjan|def adjacency_from_edges|def load_edges|recheck::|def propagate_retraction|DEFAULT_MAX_DEPTH\s*=`：
**只返回 import 语句**（`from scripts.graph.{adjacency,closure,propagate,stage_order,stop}` + `schema.store`），唯一 `recheck::` 命中在 `engine.py:362` 的 **docstring** 里。→ **没有重造闭包/SCC/停判/邻接**。

`engine.py` 的设计是"**复用既有出口 + 加逐层视图**"：`retraction_downstream()` 同时调 `forward_closure` 与 `propagate_retraction`，`LayeredPropagation` 只是**只读派生视图**。**无写路径**实证（grep `append_records|write_text|open(.*w|apply=True|mkdir` 于 `transmit/**` = **空**）→ 单一写入者纪律（纪律 5）未被绕过。

### 1.2 ★ `assert_not_equivalent` **真会抛**（我跑的，原文粘贴）

```
--- ★ assert_not_equivalent 实测 ---
  capex -> revenue: RAISED StageEquivalenceError: capex(需求侧) ≠ 供应商订单/收入
  order -> revenue: RAISED StageEquivalenceError: order 不能直接等同 revenue（缺中间阶段证据）
  revenue -> order: PASS(未等价，放行)
  capex -> purchase_commitment: PASS(未等价，放行)
```

→ 不是"声明在文档里"，**方向敏感**（`revenue→order` 放行、`order→revenue` 拦）也成立。

### 1.3 ★ 参数真外置：**缺文件 = 响亮失败，不是静默兜底**

```
--- ★ 参数外置：缺 rules/transmission.yaml ---
  FileNotFoundError: 缺少传导参数真源: /tmp/.../rules/transmission.yaml（唯一真源，值待冻结；不得在代码里内置阈值）
  TransmitParams 字段是否必须有默认值: [('importance_threshold', MISSING), ('amplification_cap', MISSING), ('gain_map', MISSING), ('max_depth', MISSING)]
```

`rules/transmission.yaml` 确实**不存在**，而缺它**不是**静默降级到内置阈值 —— 4 个字段**全部无默认值**（`MISSING`）。**此判据成立**。

### 1.4 PARTIAL：`gain_map` 的保守键 `undisclosed` **装载期未校验**

DoD/`stop.py` docstring 要求 `gain_map` "必须含 `undisclosed`"，但：

```
装载期：未报错 → {'high': 0.8}          ← 缺保守键，照样装成功
对照组 gain_map 含 undisclosed： {'undisclosed': 0.5}
```

**判定**：**不是静默兜底**（真缺键时运行时必炸，属"响亮但迟到"），**但** DoD 承诺的"4 键必须含 `undisclosed`"在**装载期**没有被强制 → 若所有 hop 的 `gain_key` 恰好都不是 `undisclosed`，这份**不合规配置会一路静默通过**（`Ch7 §J5` 的安全网只在第一次遇到未披露 hop 时才展开）。修法：`load_transmit_params` 里加一行守卫。**PARTIAL（低-中）**。

---

## §2 ★★ 我的集成改动逐项验证

### B1 `G-RC-05` root 绑定 —— **PASS（反向验证通过）**

副本根跑 `run_daily`，真源指纹首尾对比：

```
=== BEFORE: 真仓库 facts 行数 + sha256 ===
87cfafe931f563c81a562b850c4f29c356ff2480d3e1817c6f7ba88426f57464  -
     60 total
副本 facts 行数: {'baselines': 1, 'claims': 9, ..., 'tasks': 9}
run_daily: blocked=True degraded=True signals=0
steps: [(1, 'ok', 1), (2, 'gap', 4), (3, 'gap', 0), ... (8, 'gap', 0)]
副本 facts 行数(跑后): {..., 'claims': 10, ..., 'tasks': 10}
=== AFTER: 真仓库 facts 指纹 ===
87cfafe931f563c81a562b850c4f29c356ff2480d3e1817c6f7ba88426f57464  -
     60 total
=== git status ===
 M system/scripts/delivery/stage_gate.py
 M system/scripts/ops/verify.py
```

**正反两向都有信号**：副本 `claims 9→10 / tasks 9→10`（step 1 **真写了**，不是空跑），而真 `facts/*.jsonl` **逐字节相同**、行数不变、`git status` 不变。→ **缺陷 `G-RC-05` 的修法（`make_ingest_handler(self.root)`）确实成立**。

### B2 `run_daily` vs `resume` —— **PARTIAL**（聚合语义一致，违例枚举不一致）

同一副本上独立复跑（team-lead 曾量出过相反结论，本次独立复现）：

```
run_daily : blocked=True degraded=True signals=0 gaps=12 steps=[(1,'ok',1),(2,'gap',4),(3..6,'gap',0)]
resume    : blocked=True degraded=True signals=0 gaps=14 steps=[(1,'skipped',0),(2,'gap',4),(3..8,'gap',0)]
run_daily gaps(12): ... step 2..6 缺口 ×5, step 7/8 未注册处理器 ×2, G1-05 ×5(仅 step 2..6)
resume    gaps(14): ... 同上 7 条 + G1-05 ×7(step 2..6 + publish_hook + verify_hook)
```

- **一致**：`blocked` / `degraded` / `signals_emitted` / 每步 `status` 归类 **全部相同**；`resume` 对已 `ok` 的 step 1 判 `skipped`、**不**误报 G1-05（`assert_steps_complete` 的 `STATUS_SKIPPED: continue` 分支生效）→ **此前"两边结论相反"的问题已闭合**。
- **不一致**：`resume` 比 `run_daily` **多报 2 条 G1-05**（`publish_hook` / `verify_hook`）。同一事实（hook 未注册）在 `resume` 里被**既记 gap 又记 G1-05**（双重计数），`run_daily` 只记 gap。→ "同语义"**只在聚合层成立**；违例枚举层 `resume` 更严（偏严的一侧，不产生假通过）。**PARTIAL（低）**，建议两条路径共用同一次 `assert_steps_complete` 的入参口径。

### B3 `conftest` 空真源契约 —— **PASS（机制）· UNKNOWN（"仍绿"的实测）**

- `_reset_truth_source` 把 `facts/` 下 **18 个** JSONL 清零、`raw/` 清到只剩 `.gitkeep`，**只动数据不动结构**（18 个文件仍存在 → `Ch9 §3.3.3` 的"不得增删改名"断言仍可测）；`code_root`（每例）与 `pristine_code_root`（session）**都**调用它，且顺序正确（`_make_writable` 之后）。
- ★ **对抗性对照：清空清单是否真的覆盖全部真源？**（若漏一个 stem，夹具就会残留真数据）

```
stems: 18 real: 18
★ 真源有而清空清单未覆盖（夹具会残留真数据）: []
★ 清空清单有而真源没有（夹具会凭空造文件）: []
```

→ 清单与真源**互为全集**，**无残余泄漏面**。**"往副本真源塞行 → 受影批仍绿"这一步只有 pytest 能证伪，我禁跑 → UNKNOWN**（`§7-U2`）。

### B4 `pristine_code_root` —— **PASS（结构性）· UNKNOWN（实测）**

`git show 68c0152` 证实契约矩阵从 `SYSTEM_ROOT`（真仓库）改为 `pristine_code_root`（空真源副本）：

```diff
-    code, out = run_gate_inproc(script, SYSTEM_ROOT, *extra)
+    code, out = run_gate_inproc(script, pristine_code_root, *extra)
```

★ **"这不是掩盖"我独立复核成立**：`verify.py::BATCHES["gates"]` 跑 `scripts/ops/run_all_gates.py {root}`，而 `run_all_gates.py:67` 用 `code_root = Path(args.code_root)…else ROOT`、并在 `:84` 把 `str(code_root)` **传给它跑的每一个门禁** → `gates` 批跑的是**真仓库**，`T-10`/`G-RC-04` 两条真实违例**照样可见**。`_lock_rules_perms` 的存在也必要（副本 `rules/` 复原 0444，否则 `rules_lock_guard` 会在副本上假红）。**guards 批"由红转绿"我无法验（pytest 禁跑）→ UNKNOWN**。

### B5 `no_placeholder_guard` 豁免 —— **PASS（登记的豁免）· 发现未登记宽免面**

我搭了探针根（完全在 scratch 内），把**同款措辞**分别放进"已登记文件"与"未登记文件"：

```
===== RUN 2: 同款措辞 · 已登记文件 vs 未登记文件 =====
  scanned exempted_hits: 1
  scanned exemptions: 1
  scanned files: 2
  note: EXEMPTED(not a violation): scripts/orchestrate/chain_steps.py:2 rule=PLACEHOLDER-CN —— 命中已在 config/placeholder_exemptions.yaml 逐条登记
  [FATAL] PLACEHOLDER-TODO @ scripts/orchestrate/chain_steps.py:6 — 占位标记 TODO
  [FATAL] PLACEHOLDER-CN @ scripts/orchestrate/other.py:2 — 中文占位标记（待实现/待补/占位/未实现）
RESULT: FAIL（2 violations）
```

真仓库上：

```
  scanned exempted_hits: 1
  scanned exemptions: 1
  scanned files: 120
  note: EXEMPTED(not a violation): scripts/orchestrate/chain_steps.py:103 rule=PLACEHOLDER-CN —— 命中已在 config/placeholder_exemptions.yaml 逐条登记
RESULT: PASS（0 violations）
```

**结论（登记清单本身是对的）**：① 豁免按 `(path, rule)` **精确匹配**，同款措辞换个文件**照样 `[FATAL]`**（不是按措辞放行）；② 同文件内**其它规则**（`PLACEHOLDER-TODO`）**照样 `[FATAL]`**（不是整文件放行）；③ 豁免命中**不静默**（逐条 `note` + `exempted_hits` 计数，`scope_note` 写明"不放行什么"）；④ 清单缺文件 → 返回**空集**（fail-safe，默认不豁免）。

★ **但发现第二套、更宽、且静默的免扫机制**：`EXEMPT_PATTERNS` 内嵌 `"reports/"`，而 `_is_exempt()` 是 **子串匹配**（`pat in normalized`）→ `code_root` 下**任何**名为 `reports` 的目录（不只根下的 `reports/`）**整目录免扫、对全部规则、且不产生任何 note**：

```
探针：scripts/reports/evil.py 内含 "待实现"
  scanned files: 2          ← 该文件根本未被扫描
  scanned exempted_hits: 0  ← 也不计入豁免命中
（无任何 note）
```

这与 `config/placeholder_exemptions.yaml` 自称的"本文件是**唯一**的豁免入口"**直接矛盾**：真实的免扫面 = 清单（可见）**+** 代码内嵌 5 条模式（其中 `reports/`/`tests/` 是**整目录级、静默**）。**PARTIAL（中）**：修法——把 `reports/` 收成**锚定**模式（如 `^reports/`）或移入清单并逐条登记 + 对"目录级免扫"也输出 note。

### B6 `stage_gate.py` `coverage_verifiable` 接线 —— **PARTIAL（未提交）**

接线**代码本身正确**（复用 `scripts/daily/coverage.py::check`，`criterion("daily_run","coverage_verifiable", v)` 与 AST 抽取字面量一致，`v += cv.violations` + `**cv.scanned` 上报）——但它**不在提交树里**：

```
=== git status --short ===
 M system/scripts/delivery/stage_gate.py
 M system/scripts/ops/verify.py
```

即：以 `main = f1c79a2`（或 `git archive`）审计，`daily_run` 的 `criteria_not_implemented` **仍是 1**，接线只存在于**工作区**。同一未提交改动里还有 `verify.py` 新增的 `evidence` / `daily` 两个批次（即 `V-06` 对新测试目录的登记也只在工作区）。**风险**：`git checkout .` / `git stash` / 换工作树 → 接线与批次登记**静默消失**，而报告/DoD 里已经写了"已绑定"。**PARTIAL（中，属流程而非逻辑）**。

### B7 其它集成改动（抽验）

- `ingest_step.py`：`make_ingest_handler(root)` → `ingest_public_information(..., root=root_path)`，默认值路径 `_code_root()` 只在**未显式绑定**时回退 —— 与 `G-RC-05` 的修法一致；`B1` 已实证其生效。
- 批次 8 各提交**未碰** `system/rules/**`、**未碰**设计区（见 `§5-#6`）。
- **环境异常（非代码缺陷，但影响可复现性）**：本单开始时该解释器**连 `pyyaml`、`pydantic` 都没有**（`pip list` 只有 `pip`），项目亦**无依赖清单**（无 `requirements.txt`/`pyproject.toml`/`uv.lock`）→ 任何走 `_cached_yaml` 的门禁都会 `ModuleNotFoundError` 崩（且 `run_checker` 的 `except` 不捕 `ImportError`，直接抛栈、exit 1）。我为跑探针**装了 `pyyaml` + `pydantic`**（只动解释器 site-packages，**未动仓库任何文件**）。建议补一份依赖清单（`§6-G-B10-06`）。

---

## §3 真实数据可信度抽查（我自己算的 sha256）

```
claim-nvidia-newsroom-q4-fy2025-4d13454fd859
  locator      : raw/2025-02-26-nvidia-q4-fy2025-results.txt#L1-L1146   (文件实际行数=1146)
  quote_hash   : 4d13454fd8593e20490db2a23a086795280a826fa13630e6935a762d35a1e449
  sha256(原文) : 4d13454fd8593e20490db2a23a086795280a826fa13630e6935a762d35a1e449   → 匹配=True
  自称覆盖全篇 : True    bytes=19530
claim-inbox-2026-09-10-tsmc-aug2026-revenue.txt-afebc81420c1
  locator      : raw/2026-09-10-tsmc-aug2026-revenue.txt#L1-L231   (文件实际行数=231)
  quote_hash   : afebc81420c13b374786d228f22afde162e4f4c2da1085a72969153dcb36bd20
  sha256(原文) : afebc81420c13b374786d228f22afde162e4f4c2da1085a72969153dcb36bd20   → 匹配=True
（另两条 AMD / NVDA-Q3 亦 → 匹配=True）
```

**4/4 全中**（`quote_hash == sha256(UTF-8 原文)`，与 `locator_check` 的机械含义同源），`locator` 的 `L1-L<n>` 与文件**实际行数逐条相等**，原始文本首行确实是官方披露正文（`NVIDIA Announces Financial Results…` / `6-K` / SEC 表单头）。

- **渲染取舍如实登记**：`ws_real_collect_report.md:31` 明写"`raw/*.txt` 为官方页面的**纯文本渲染**（剥离 HTML 标记、空白归一为行，**措辞零改动**），**非**字节级 HTML 原样"，并在 `:286-287` 的 §④ 残留项重申 + 给出补 `.html` 的路径 → **不是偷偷换口径**。
- **note 1**：`system/raw/inbox/2026-08-04-amd-q2-2026-results.txt` 与 `system/raw/2026-08-04-amd-q2-2026-results.txt` **逐字节相同**（`cmp` 无输出、各 4419 B / 71 行）—— 同一份源在 `raw/` 下**双份**存在，而只有 4 条 claim 指向 4 份正文；该"inbox 副本是否保留"未在报告里登记。
- **note 2**：4 条 claim 全部 `full_text_read: false`，**但** `locator` 覆盖全篇（`L1-L<末行>`）且 `quote_hash == sha256(整个文件)` —— 即 `locator_check` 的第 4 条规则（"覆盖全篇 **且** hash 相等"⇒ 可判 `full_text_read=true`）**两个条件都满足**，记录却填 `false`。**保守方向**，故不误红；但 `full_text_read` 作为**可核字段**此时"低估自己"，且 `locator_check` 只约束 `true ⇒ 条件成立`，反向不告警 → 一个**单向判据的静默面**。建议：规则补一条"覆盖全篇 + hash 相等却标 `false`"的 note（不必 fail）。
- **note 3（与 `§5-#1` 同源）**：真源 `claims.jsonl` 有 5 行 / **4 个** `claim_id`，其中 `…q4-fy2025-4d13454fd859` 出现 2 次（`recorded_seq` 1 与 4，后者 `version_kind=financial_restatement`、`status=superseded`）→ 这是**有意的版本重录**（append-only + `recorded_seq` 排序），**不是**污染残留；但它意味着"`claim_id` 唯一"**不是**真源不变量，读者必须按 `recorded_seq` 取最新。

---

## §4 `T-10` / `G-RC-04` 的独立第二意见

两条我都**亲手复现**（真仓库、`--no-report`）：

```
===== G-RC-04 实测：no_signal_day 在真仓库 =====
  scanned check_records: 1   scanned recommendations: 1   scanned tasks: 3
  [FATAL] G1-02① @ facts/tasks.jsonl:0 — 无变化日产了新信号: run_date=2026-09-16 signals_emitted=1
RESULT: FAIL（1 violations）      EXIT=1

===== T-10 实测：traceback 在真仓库 =====
  scanned coverage_x100: 0   scanned recommendations: 1   scanned sample: 1
  [FATAL] G1-03 @ facts/recommendations.jsonl:0 — rec-nvda-001 四要素缺失: ['assumptions', 'computation', 'prev_version_id']
  [FATAL] G1-03 @ facts/recommendations.jsonl:0 — 四要素覆盖率 0.0000 < 1.0
```

### `T-10`：**成立，而且被"说轻了"**（严重度 中 → **建议提到 高**）

`traceback.py:40` `ELEMENTS = ("evidence","assumptions","computation","prev_version_id")`，`missing()` 要求四者**全部非空**；`prev_version_id = target.get("supersedes")` → 首条建议恒 `None`。登记项说"即使把 `assumptions`/`computation` 补齐，`prev_version_id` 仍恒缺"——**这句不成立**：`computation` 对"**定性**首条建议"同样**结构性不可达**：

```python
def _find_derived(root, conclusion_id):     # traceback.py:119
    for row in _load_jsonl(path):           # 在 derived/ 里找
        if row.get("conclusion_id") == conclusion_id or row.get("derived_id") == conclusion_id:
            if row.get("formula") and row.get("operands") is not None and row.get("method_version"): return row
```

它要求 `derived/` 里存在**以该 `recommendation_id` 为键**的 `DerivedValue`；而本项目的 `derived/` 存的是**被算出来的量**（各自 `derived_id`），一条**非数值**的 `buy` 建议根本不会产生这样的行（实测 `system/derived/` **只有 `.gitkeep`**）。→ **四要素里至少两条对"首条定性建议"不可达**，`G1-03` 的 `覆盖率==1.0` 是**不可满足判据**（不是"还差一点数据"）。
**我的裁定建议**：`G1-03` 应改为"四要素**可解析率**（按建议类型定义必需项：数值型需 `computation`、`version>1` 才需 `prev_version_id`）"，或改成"缺失项必须**显式声明为不适用**"；仍保留"删掉某结论的 `prev_version_id` → 拦截"这条反向用例（`traceback.py:22-23` 的本意仍在）。

### `G-RC-04`：**成立，登记严重度（中）合适**

`no_signal_day.py:122-124` 把 `tasks.jsonl` 中**所有**含 `check_record` 的行都纳入，`check_no_signal_day` 对每条判 `not changed and emitted != 0`。真源里 `P7-1` 修复**之前**那次运行的记录（`changed:false, signals_emitted:1, check_id=check_2026-09-16_full`）**不可删**（追加式不可变）→ 门禁**恒红**，且**修好 bug 也清不掉**。**同意该缺口成立、严重度中**。
**我补充的两点**：① 判据本身**没有错**（那条历史记录**确实是**违例），所以**不该放宽**它，而应做"**当前 vs 历史**"的**可见拆分**（该模块已有 `_r<n>` 修订机制，同一 `run_date` 取最新修订即可）＋ 把历史违例登记为**具名豁免**（与本项目的"门禁被关掉"禁忌一致：**恒红的门禁 = 被学会忽略的门禁**）；② 它是**唯一**让"真源追加式不可变"与"门禁可修复"两条纪律正面对撞的样本，建议连同 `§4-T-10` 一并作为"判据语义"议题上报需求方，**由主理人以外的人裁定**（避免自裁）。

---

## §5 对抗性清单逐项

**#1 第二实现 / 第二写入路径** —— **PARTIAL**。`transmit/**`：**无**第二实现（`§1.1`）、**无**写路径、**无**第二个幂等键（`recheck::<ref>::<target>` 只有一处、在 docstring）。但**集成层的写入路径不幂等**：副本上连续跑 `run_daily`，同一条 `claim_id`（AMD 那条）累积到 **6 行**（`analyzed_at` 各不相同、`recorded_seq` 连续递增）——即"同一源 + 同一 `quote_hash` ⇒ 同一 `claim_id` ⇒ 应跳过"这条**只在 `real_collector` 内部成立**，一旦编排层重跑/多入口调用，真源就会长出重复行（这正是 `G-RC-05` 那 12 行的成因，`root` 绑定只**限制了污染范围**，没有消除重复落库）。另注：`tasks.jsonl` 的 `idempotency_key` 在副本上**无重复**（10 行 10 键）——两表的幂等强度**不一致**。

**#2 静默兜底 / `G-03`** —— **PASS（含 2 例外）**。`transmit._resolve_edges`：`TRUTH_MISSING → FileNotFoundError`（响亮）、`TRUTH_EMPTY → ((), True) + note`（**不**冒充"已验证"，符合 `G-03`）；`load_transmit_params` 缺文件**响亮**；`attribute_terminal_demand` 对重复 `path_id` / `share<=0` 抛 `ValueError`，空路径 → `NO_DEMAND_PATHS` note。**例外**：`§1.4` 的 `undisclosed` 延迟校验；`§2-B5` 的 `reports/` **静默**目录免扫。

**#3 `R-06` 关键词判据 + 豁免是不是后门** —— **PARTIAL / 有条件的 PASS**。清单形态**正确**：白名单、逐条 `(path, rule)`、`reason`+`approved_by`+`scope_note`、命中**可见**（note + `exempted_hits`）、缺文件**fail-safe**（空集）、精确匹配（换文件/换规则仍 `[FATAL]`，`§2-B5` 实证）。**两点保留**：① `PLACEHOLDER-CN` 本身仍是**关键词式判据**（`R-06①` 禁止关键词判据作防护判据），清单只是"把误报收口"，**没有**把它降级为 lint —— 该判据仍在 `pre-commit.sh`/`run_all_gates` 里**硬阻断**，属"已知的二阶代价"；② **真正的后门形状在代码里**：`EXEMPT_PATTERNS` 的 `"reports/"` 子串 → 整目录、全规则、**静默**、**未登记**（`§2-B5`）。修掉 ② 才谈得上"唯一豁免入口"。

**#4 真实数据可信度** —— **PASS + 2 note**（见 `§3`：4/4 sha256 自算命中；渲染取舍已登记；note：`raw/` 与 `raw/inbox/` 同源双份、`full_text_read=false` 与全篇覆盖矛盾）。

**#5 `T-10` / `G-RC-04`** —— 见 `§4`：**两条都成立**；`T-10` **被说轻了**（两条要素不可达，非一条），`G-RC-04` 严重度合适；两者都属"判据语义"议题，**不宜由主理人自裁**。

**#6 纪律 9/10：`rules/**` / 设计区 / `conftest.py` / `CONVENTIONS.md`** —— **PASS（无越界）**。

```
=== bb42184..f1c79a2 里非 system/ 的改动（设计区越界检查）===
(空=未碰设计区)
=== 该区间是否碰 rules/ 与 CONVENTIONS.md / tests/conftest.py ===
system/CONVENTIONS.md
system/tests/conftest.py
=== rules/ 权限 ===
-r--r--r-- banned_tokens.yaml / benchmark.yaml / data-sources.allowlist.yaml / freeze.yaml / ...
```

`rules/**` **未被任何批次 8 提交触碰**，权限仍 **0444**（纪律 9/10 不变量在）；`system/CONVENTIONS.md` 的改动（`35e4ae5`）**只新增 V-08 + 批次 9 任务书**，而 `CONVENTIONS.md` 头部自我定位是"**代码区**开发规范（补充任务书与施工纪律 12 条）"，且明确"**设计区只读，本文件不改设计**" → 由集成者追加一条**验证规范**（V-08 宿主删除配额）**不构成越界**；`tests/conftest.py` 属测试基建（非 `rules/`、非设计区），是本批 `G-RC-02/03/05` 的**修复面**，改动范围与任务书一致。**唯一保留**：V-08 把一个**宿主（WorkBuddy）特定行为**（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`、阈值 9999、`scope:"turn"`）写成项目**通用**规范 → 可移植性隐患，建议标注"宿主相关"。

**#7 占位符 / 空实现 / 吞异常** —— **PASS**。守卫在**真仓库**上 `RESULT: PASS（0 violations）`（`scanned files: 120`，1 条已登记豁免）；因守卫会抹白注释与 docstring，我**另做手工 grep**：`TODO|FIXME|HACK|NotImplementedError` 在 `scripts/{orchestrate,transmit,daily,delivery,evidence}` = **0 命中**；`transmit/**` 无 `except …: pass`。`§1.1` 全文读过 `engine.py`/`demand.py`/`stop.py`，无空函数体、无假数据返回。

---

## §6 缺口清单（本单新增）

| # | 缺口 | 严重度 | 位置 / 证据 |
|---|---|---|---|
| `G-B10-01` | **`coverage_verifiable` 接线 + `verify.py` 两个新批次未提交**（只在工作区）→ 以提交树审计则判据仍未实现；可被 `git checkout .` 静默抹掉 | **中** | `git status --short` 的两条 ` M`；`§2-B6` |
| `G-B10-02` | **`EXEMPT_PATTERNS` 内嵌 `"reports/"` 子串 = 未登记、静默、整目录全规则免扫**；与清单自称"唯一豁免入口"矛盾 | **中** | `no_placeholder_guard.py:100,449-451`；`§2-B5` 探针 |
| `G-B10-03` | **编排层重复落库**：重跑 `run_daily` 每次追加同一 `claim_id`（副本实测 ×6）；幂等只在 `real_collector` 内部成立，`tasks`/`claims` 两表幂等强度不一致 | **中** | 副本 `claims.jsonl` 6 行同 id；`§5-#1` |
| `G-B10-04` | **`load_transmit_params` 不校验 `gain_map` 的保守键 `undisclosed`**（DoD 承诺装载期强制）→ 不合规配置可静默通过（直到第一个未披露 hop） | 低-中 | `§1.4` 实测 |
| `G-B10-05` | `raw/` 与 `raw/inbox/` **同源字节级双份**（AMD 文本），未登记；`full_text_read=false` 与"locator 覆盖全篇 + hash 相等"矛盾（判据单向） | 低 | `cmp` 一致；4 条 claim 全 `false` |
| `G-B10-06` | **项目无依赖清单**（无 `requirements.txt`/`pyproject.toml`）；本单开始时解释器连 `pyyaml`/`pydantic` 都没有 → 走 `_cached_yaml` 的门禁直接抛栈（`run_checker` 不捕 `ImportError`） | 低-中 | `pip list` 只有 `pip`；`_common.py:190-197` |

---

## §7 未能证伪的项（UNKNOWN，**不得**当 PASS）

| # | 项 | 为什么 UNKNOWN |
|---|---|---|
| `U1` | `tests/guards` 契约矩阵在 `pristine_code_root` 上**真绿** | 需 pytest 通道（**我禁跑**）。我只证了**机制**：空真源副本 + `rules/` 0444 复原 + 契约用例已改指副本 + `gates` 批仍跑真仓库。 |
| `U2` | "**往副本真源塞行 → 受影响批仍绿**"（`G-RC-02` 的收口证据） | 同上。我证了它的**前提**（清空清单与真源**互为全集**、`_reset_truth_source` 被两个夹具都调用），但"批仍绿"只有 pytest 能判。 |
| `U3` | `resume` 的 2 条额外 G1-05 是"过报"还是 `run_daily` "少报" | 需读两处 `registered_hooks` 的实际传参并跑对应单测（`tests/orchestrate`）→ pytest 通道。我只证了**现象**（12 vs 14）与聚合一致。 |
| `U4` | `coverage_verifiable` 判据在**真数据**上的正反向 | 属另一审计员的 A 单对象（`ws/ch8-daily`）；我仅核其**接线**（`§2-B6`）。 |
| `U5` | `rules/transmission.yaml` 一旦落地后 `transmit` 的 `max_depth`/`amplification_cap` 取值是否合理 | 该文件**不存在**（参数值待需求方冻结）→ 无可审对象；本单只能审"是否外置、是否响亮失败"。 |

---

## §8 审计过程自述

**做了什么**：全文读 `transmit/{engine,demand}.py`、`graph/{stop,stage_order}.py`、`checks/no_placeholder_guard.py`、`checks/no_signal_day.py`、`tests/conftest.py`、`trace/traceback.py`、`config/placeholder_exemptions.yaml`、`orchestrate/{pipeline,ingest_step}.py` 相关段；`git log/show/diff` **只读**看批次 8 各提交与工作区改动；在 `system/tests/.audit/batch10_b/` 下搭了 4 个副本根（`copyroot`/`cr2`/`cr3`/`guardroot`）跑实测：`run_daily`×3、`resume`×1、守卫反向对照×3、sha256 自算×4、`assert_not_equivalent`、`load_transmit_params`；真仓库上只跑**只读**门禁（`no_placeholder_guard --no-report`、`no_signal_day --no-report`、`traceback --no-report`）。

**遵守的边界**：未执行任何 git 写命令；未改任何仓库文件（真源 `facts/*.jsonl` 指纹首尾同一 `87cfafe9…`，`raw/` 亦同）；**未运行 pytest**（`U1/U2/U3` 如实标 UNKNOWN，未偷跑）；写型探针全在 scratch 副本；scratch 目录收尾**分片删除**（`V-08`：避免单次批量删除触发 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`）。

**环境异常（如实上报）**：审计开始时解释器**缺 `pyyaml`、`pydantic`**（`pip list` 仅 `pip`），项目亦**无依赖清单** → 我先 `pip install pyyaml`（成功），`pydantic` 首次失败后用 `pip download` + 离线 `--no-index` 装成（2.13.5）。**只动了解释器 site-packages，未动仓库任何文件**。若宿主环境在其它会话里缺失同一批依赖，`gates`/`stage` 批会以 `ModuleNotFoundError` 抛栈（`G-B10-06`）。

**证据强度声明**：`§1`、`§2-B1/B2/B3(机制)/B4(结构性)/B5/B6`、`§3`、`§4`、`§5-#6/#7` 均为**本单亲手实测/只读复核**；`§2-B4` 的"guards 批转绿"、`§7-U1/U2/U3` 属 pytest 通道，**如实标 UNKNOWN**。
