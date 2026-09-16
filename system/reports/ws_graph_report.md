# ws/graph 交付报告 —— 依赖图与传播层（`Ch9 §3.2.1` B 边表 schema + C 遍历/失效/入队）

- 工作区：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-graph`（分支 `ws/graph`，基线 `775e714`）
- 角色：寇豆码（Kou）· 工程师 · 并行工作流 `ws/graph`
- 目标：为阶段③ `core_chain` 提供**可遍历 / 可失效 / 可入队**的图能力前置
- DoD（写入优先）：`system/reports/ws_graph_dod.md`（与本节 AC 逐条对应）

---

## §1 交付物清单（8 能力 → 8 模块，全部实装，无占位）

| # | 模块（新增/填充） | 承载能力 | 设计锚点 |
|---|---|---|---|
| 1 | `system/scripts/graph/adjacency.py` | 边加载（`dependency_edges` + `relations`）+ **可重建**邻接表缓存 `index/adjacency.sqlite`、缓存↔真源逐边一致性核对 | `Ch7 §C.8` · `Ch9 §3.3.2` |
| 2 | `system/scripts/graph/closure.py` | 正/反向闭包（`forward_closure` / `reverse_closure`），**单遍 BFS `O(V+E)`**、深度上限、悬空端点 | `Ch9 §3.4.3` |
| 3 | `system/scripts/graph/cycles.py` | 环检测 SCC（**迭代式 Tarjan**，无递归）+ 环折叠（代表值取 max，非求和） | `Ch7 §C.3` / 裁定 J7 |
| 4 | `system/scripts/graph/fingerprint.py` | 事件去重指纹（**根来源而非标题**）+ `event_alias` / `split` / `merge` 人工纠正入口 | `Ch9 §3.4.7` / `N9.1-14` |
| 5 | `system/scripts/graph/stage_order.py` | 五者语义层级程序约束：**禁跳级等同**、`capex`（需求侧）≠ `order`/`revenue`（供给） | `Ch7 §B.4` |
| 6 | `system/scripts/graph/stop.py` | 停止判定 **7 条件**逐字 + 累计放大上限（**零内置阈值**） | `Ch7 §C.2 / §C.5 / §C.6` |
| 7 | `system/scripts/graph/propagate.py` | T12 传播：下游失效 → `recheck` 入队（幂等）→ 研究深度回退（追加式） | `Ch9 §3.4.3` / `§2.3.3` |
| 8 | `system/scripts/graph/graph_integrity_guard.py` | 图结构完整性守卫（空端点/自环/重复边/重复 edge_id/陈旧缓存，命中 `exit 1`） | `Ch2 §B.3` |
| — | `system/scripts/graph/__init__.py` | PEP 562 **惰性导出**枢纽（导入期不拉起子模块/pydantic） | `CONVENTIONS.md §三 P-03` |

测试（新增）：`system/tests/graph/` —— 5 文件 **36 用例**：

| 测试文件 | 用例数 | 覆盖 |
|---|---|---|
| `test_adjacency_and_closure.py` | 9 | AC-02 缓存可重建复现、正/反向闭包、深度截断、环/自环、悬空、空图、重复边幂等、**大图 5000 节点线性** |
| `test_fingerprint_and_identity.py` | 5 | 根来源去重、时区归一（AC-06）、别名解析、split/merge 纠正任务 |
| `test_stage_and_stop.py` | 13 | 层级排序逐字、`capex≠order/revenue`、相邻 vs 跨级、**7 条件逐条**、累计放大上限 |
| `test_propagate_t12.py` | 4 | 撤回真实到达下游 + 入队、幂等、干跑不落库、有环仍收敛 |
| `test_graph_integrity_guard.py` | 5 | 干净树 `exit 0` + `scanned`、自环/重复边/陈旧缓存阻断、缺 `code_root` `exit 2` |

---

## §2 验证证据（真实输出 + 退出码）

> 环境：沙箱外（`CODEBUDDY_SAFE_DELETE_SANDBOX=0` / `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0`），批次化、每批独立超时，**无并行 pytest、无单命令全量**。

### 2.1 本模块测试批次 `tests/graph`（未登记于 `verify.py::BATCHES`，见 §3）

```
$ sh system/scripts/ops/run_pytest.sh tests/graph
collected 36 items
tests/graph/test_adjacency_and_closure.py .........                      [ 25%]
tests/graph/test_fingerprint_and_identity.py .....                       [ 38%]
tests/graph/test_graph_integrity_guard.py .....                          [ 52%]
tests/graph/test_propagate_t12.py ....                                   [ 63%]
tests/graph/test_stage_and_stop.py .............                         [100%]
============================== 36 passed in 2.86s ==============================
EXIT=0
```

### 2.2 `verify.py --batch guards`（`exit=1`，用时 3.68s / 60s，**无超时**）

```
5 failed, 51 passed in 3.68s
FAILED test_exit_code_contract.py::...[rules_lock_guard]
FAILED test_exit_code_contract.py::...[injection_guard]
FAILED test_exit_code_contract.py::...[verification_policy_guard]
FAILED test_verification_policy.py::test_policy_guard_passes_on_pristine_tree
FAILED test_verification_policy.py::test_new_file_inside_existing_batch_is_allowed
EXIT=1
```

逐条归因（**5 条全部非本模块代码缺陷**）：

| 失败项 | 归因 | 是否我引入 |
|---|---|---|
| `rules_lock_guard` | `system/rules/*.yaml` 在本 worktree 为 `0o644`，守卫要求 `0o444`。**git 只存可执行位、不存 0444** —— 任何新建 worktree 检出都是 `0644`（主检出由 `lock_rules.py` chmod 至 0444）。 | 否（环境，集成回主仓即绿） |
| `injection_guard` | 同上（同一条规则 9 权限判据，10 条 FATAL 全为 `0o644→0o444`）。 | 否（环境） |
| `verification_policy_guard` | **V-06：`tests/graph/` 未被任何批次覆盖** | 预期（主理人集成时加批次） |
| `test_policy_guard_passes_on_pristine_tree` | 同上 V-06 | 预期 |
| `test_new_file_inside_existing_batch_is_allowed` | 同上 V-06 | 预期 |

> ✅ **`freeze_guard` 已从失败列表移除**：本模块已消除全部裸 `import X`（改用 `from X import Y`），不再触发下述潜伏缺陷。

### 2.3 `verify.py --batch gates`（`exit=1`，用时 2.56s / 60s，**无超时**）

20 项门禁中 **17 项 exit=0**，非零 3 项（均已在 §2.2 归因）：

```
conflict_scan 0 · append_only_guard 0 · registry_schema_guard 0 · schema_sync_guard 0
assert_gate_input 0 · freeze_guard 0 · launch_guard 0 · module_denylist 0 · no_signal_day 0
no_placeholder_guard 0 · neutrality_check 0 · return_guard 0 · anti_padding 0 · gap_to_task 0
traceback 0 · pipeline 0 · stage_gate --stage prep 0
rules_lock_guard 1(rules 权限·环境) · injection_guard 1(rules 权限·环境) · verification_policy_guard 1(V-06·预期)
非零计数 3
EXIT=1
```

关键项确认：`freeze_guard.py exit=0`、`no_placeholder_guard.py exit=0`、`append_only_guard.py exit=0`（本模块全为新增，不触碰 `facts/*.jsonl`）。

---

## §3 需主理人集成项（**请勿由我改动，遵铁律**）

1. **新增验证批次**：在 `system/scripts/ops/verify.py::BATCHES` 增加/扩展批次覆盖 `tests/graph/`（如 `("graph", ["run_pytest.sh tests/graph"], ...)`），以消除 `V-06`（当前 `verification_policy_guard` 报红为**预期**）。
2. **提供传导参数真源**：`system/rules/transmission.yaml` **当前不存在**。`stop.load_transmit_params()` 按设计**响亮失败**（`FileNotFoundError`），**代码内不内置任何阈值**。请主理人在集成时提供该文件（字段：`importance_threshold` / `amplification_cap` / `gain_map`（须含保守键 `undisclosed`）/ `max_depth`），值随第十一章 `p04` 参数一并冻结。单测不依赖该文件（直接构造 `TransmitParams`）。

---

## §4 未改动的共享文件清单（遵守 0444/禁改约定）

以下共享文件**均未改动内容**（`git status` 无相关条目）：

- `rules/**`（`system/rules/*.yaml` 0444 锁定）—— 未改内容、未 chmod
- 设计区 `00_*` 与 `01_`~`11_` —— 未读改
- `system/tests/conftest.py` —— 未改（复用其 `code_root` / `run_gate_*` 夹具）
- `system/CONVENTIONS.md` —— 未改
- `system/scripts/ops/verify.py` —— **未改**（V-06 由主理人集成时统一处理）
- 其余一切不在本模块清单内的文件（`facts/**`、`schema/**`、`scripts/checks/**`、`registry/**`、`config/**` 等）—— 未改

本模块内的**新增**文件仅：`system/scripts/graph/**`（含填充的 `__init__.py`）、`system/tests/graph/**`；另写 `system/reports/ws_graph_report.md` 与本 `DoD`。

---

## §5 关键设计决策、偏差与风险登记

- **口径**：边表**就是**真源（`facts/dependency_edges.jsonl` + `facts/relations.jsonl`），**不引入图数据库**；`index/adjacency.sqlite` 仅作**可重建缓存**（`删 index/` 可从 `facts/` 全量重建，正确性以现算为准）。
- **指纹基于根来源而非标题**（`root_source_id` 必填非空），十篇转述 = 1 event + N propagation；`occurred_at` 一律归一到 **UTC 日桶**（跨时区书面表示 → 同一指纹）。
- **误并/漏并人工可纠正**：`split`/`merge` → `TaskType.dedup_override` 任务 + `Event.event_alias` 别名解析。
- **环检测用 SCC（迭代式 Tarjan，`O(V+E)`）**，**绝不枚举路径**；环折叠取 **max（非求和）**，回边只计一次。
- **纪律 1（零新增门槛、参数不进决策函数）**：`stop.py` **无任何内置阈值**，`TransmitParams` 全字段必填，阈值唯一真源 = `rules/transmission.yaml`（经 `_cached_yaml` 读）。
- **追加式不可变**：`propagate` 唯一写路径 = `schema.store.append_records`；stale 标记/深度回退均**追加新行**，不 UPDATE/DELETE。
- **退出码契约**：守卫 `0` 放行 / `1` 阻断 / `2` 输入异常，**禁 warn-only**（G-01）。
- **R-06 稳健性**：守卫判据基于**可穷尽的结构缺陷**（空端点/自环/重复/陈旧），非关键词/名单。
- **偏差登记 ①**（不自行裁决设计冲突，`R-04`）：`closure.DEFAULT_MAX_DEPTH=3` 取 `Ch7 §C.3` 逐字默认；`Ch7 §J3` 建议「硬上限 5」构成张力 —— 已作为**显式参数**暴露（调用方可覆盖），未把阈值固化进逻辑。
- **偏差登记 ②**：`stage_order.skip_evidence(evidence)` 的具体化（`evidence["skip_justification"]` 非空即真）为对 `Ch7 §B.4` 程序片段的**保守实现**，缺省为**假**（无中间证据不放行跳级）。
- **潜伏缺陷上报（非本模块清单，未改）**：`system/scripts/checks/freeze_guard.py:119-123` 对 `ast.Import` 节点访问 `node.module`（该属性仅 `ast.ImportFrom` 有）→ 决策作用域内**任何裸 `import X` 都会让该守卫抛 `AttributeError`**。当前 `scripts/decision/` 为空，故此前未暴露；本模块（`scripts/graph/` 在 `DECISION_SCOPE_DIRS` 内）为**首个触发点**。**规避**：本模块已全部改用具名 `from X import Y`（含 `from sqlite3 import connect` / `from hashlib import sha256` / `from sys import path as _sys_path, exit as _sys_exit`），故 `freeze_guard` 现 `exit=0`。**建议**：由主理人（或该文件属主）将第 121-123 行改为 `getattr(node, "module", None)` 以根治。
- **性能**：AST 单遍；配置经 `_common._cached_yaml()`（mtime/size 缓存）；`graph/__init__` PEP 562 惰性导入；大图线性（5000 节点闭包 < 5s 已在测试中断言）。

---

## §6 AC 判定（AC-01 ~ AC-08）

| AC | 判据 | 判定 | 证据 |
|---|---|---|---|
| AC-01 | 边表 schema 就位（B：`from/to/kind`，两真源边表），边加载忠实、可复现 | ✅ 通过 | `adjacency.load_edges` / `load_all_edges`；`test_adjacency_and_closure.py` |
| AC-02 | `index/` 是**可重建缓存**：删 `index/` 后能从 `facts/` 全量重建且与原一致 | ✅ 通过 | `build_adjacency_index` + `adjacency_matches_facts`；`test_adjacency_rebuild_is_reproducible` |
| AC-03 | 正/反向闭包可用（C：遍历），`O(V+E)` 单遍、有深度上限、含环/悬空不崩 | ✅ 通过 | `forward_closure` / `reverse_closure`；`test_*_closure*`、`test_large_graph_*` |
| AC-04 | 环用 SCC 检测 + 折叠（max，非求和），**无路径枚举**、大图有界 | ✅ 通过 | `cycles.sccs`（迭代 Tarjan）/`collapse_cycles`；`test_cycle_*`、`test_*large*` |
| AC-05 | T12 传播：下游失效 → `recheck` 入队（幂等）→ 研究深度回退（追加式） | ✅ 通过 | `propagate.propagate_retraction`；`test_propagate_t12.py`（4 用例） |
| AC-06 | 事件指纹基于**根来源**、UTC 日桶归一、跨时区同指纹；误并/漏并可人工纠正 | ✅ 通过 | `fingerprint.event_fingerprint` / `event_alias_map` / `plan_split|merge`；`test_fingerprint_and_identity.py`（含时区归一） |
| AC-07 | 停止判定 7 条件逐字 + 累计放大上限；**零内置阈值**（阈值走真源） | ✅ 通过 | `stop.should_stop`（7 分支）；`test_stage_and_stop.py`（7 条件逐条 + 上限） |
| AC-08 | 五者语义层级约束：**`capex`（需求侧）≠ `order`/`revenue`**，禁跳级等同 | ✅ 通过 | `stage_order.assert_not_equivalent`（`capex→order/revenue` 直接抛错）；`test_*capex*` |

**IS_PASS：YES**（全局跨文件一致性核对通过：`closure`→`adjacency`/`cycles`、`propagate`→`adjacency`/`closure` 的导入契约一致；`__init__` 惰性导出表与各模块定义符号逐一吻合；无重复实装、无循环导入）。

---

## §7 复现命令

```bash
export CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0
WT=/Users/gaza/Developer/InvestSigh/.worktrees/ws-graph
PY=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python
cd "$WT"
sh system/scripts/ops/run_pytest.sh tests/graph          # 36 passed, EXIT=0
$PY system/scripts/ops/verify.py --batch guards          # 51 passed / 5 failed（2 环境 + 3 预期 V-06）
$PY system/scripts/ops/verify.py --batch gates           # 17/20 exit=0（非零 3 = 2 环境 + 1 预期 V-06）
```
