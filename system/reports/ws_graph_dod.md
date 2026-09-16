# DoD · 工作流 `ws/graph` —— 依赖图与传播层（`scripts/graph/**`）

> **分支**：`ws/graph` ｜ **基点**：`775e714` ｜ **工作区**：`.worktrees/ws-graph`
> **权威设计**：`00_交付施工图 §1.3 / §3.2 / §8` · `Ch7 §B.4 / §C` · `Ch9 §3.3.2 / §3.4.3 / §3.4.7`
> **本文件先于代码产出（`00_开发Agent开工提示词 §5.1`）**：未写出的标准 = 未满足的标准。

本批次交付 `Ch9 §3.2.1` 的裁定 **B 边表 schema + C 遍历 / 失效 / 入队**，外加 `Ch7 §G`
点名的 **环检测 SCC** 与 `Ch9 §3.4.7` 的 **事件指纹**，全部落在 `scripts/graph/**`。

---

## 交付范围（对应施工图 §3.2「图谱（C）」+ §2 阶段③ 传导前置）

| 能力 | 落位 | 设计锚点 |
|---|---|---|
| 依赖图遍历（正 / 反向闭包，深度上限 + 环安全） | `scripts/graph/closure.py` | `Ch9 §3.4.3` |
| 可重建邻接表缓存（`index/adjacency.sqlite`，**非真源**） | `scripts/graph/adjacency.py` | `Ch7 §C.8` · `Ch9 §3.3.2` |
| 环检测 SCC（Tarjan，迭代式） + 环折叠 | `scripts/graph/cycles.py` | `Ch7 §C.3` · `§C.2 ③` |
| 事件去重指纹（根来源，非标题） + `split`/`merge`/`event_alias` | `scripts/graph/fingerprint.py` | `Ch9 §3.4.7` · `N9.1-14` |
| T12 传播（下游失效 → `recheck` 入队 → 研究深度回退） | `scripts/graph/propagate.py` | `Ch9 §3.4.3` · `§3.4.2` |
| 禁跳级等同（`capex` ≠ 订单 / 收入） | `scripts/graph/stage_order.py` | `Ch7 §B.4` |
| 停止判定 7 条件 + 累计放大上限 | `scripts/graph/stop.py` | `Ch7 §C.2 / §C.5 / §C.6` |
| 图结构完整性守卫（命中即 `exit 1`） | `scripts/graph/graph_integrity_guard.py` | `Ch2 §B.3`（命中即 fail） |

---

## AC 清单（逐条可测）

### AC-01 真跑通（真实输入 → 真实结果）
- 触发：向 `facts/dependency_edges.jsonl` 写入真实边（`claim → baseline → recommendation` 链），
  调用 `propagate_retraction(root, <claim_id>)`。
- 观察：`forward_closure` 返回**可达下游集合**（逐层深度正确）；`propagate` 产出
  `recheck` 任务（`TaskType.recheck`）与研究深度回退记录；结果写入 `facts/*.jsonl` 真源。
- 证据：`tests/graph/test_propagate_t12.py::test_real_retraction_reaches_downstream_and_enqueues`。

### AC-02 持久化 / 可重建（write → 删 `index/` → 重建 → 可复现）
- 触发：`build_adjacency_index(root)` 写 `index/adjacency.sqlite`；
  断言缓存与 `facts/` 一致 → **删除整个 `index/`** → 重建 → 再次断言一致；
  且「从 facts 现算的闭包」与「删前 / 删后」结果**逐字节相同**。
- 证据：`tests/graph/test_adjacency_and_closure.py::test_adjacency_rebuild_is_reproducible`。

### AC-03 真接线
- 该层以两个出口接入主流程：① `graph_integrity_guard.py` 为**由 CI / pre-commit 调用的检查器**
  （`run_checker` 出口，`exit 0/1/2`）；② `propagate_retraction` 为阶段③ 传导步的**库入口**。
- **诚实登记**：`scripts/orchestrate/pipeline.py`（第 3 步传导）与 `run_all_gates.py` 的批次注册
  **不在本模块清单内**，**由主理人集成时统一加**（本报告「剩余不确定性」中显式列出）。
- 证据：`tests/graph/test_graph_integrity_guard.py` 真跑 CLI 出口；报告附 `python -m` 实跑输出。

### AC-04 守卫真拦得住（违例 → exit 1，**不是 warn**）
- 触发：注入三类违例之一 —— ① 自环边（`from_ref == to_ref`）② 重复边（同 `from,to,kind`）
  ③ 陈旧缓存（`index/adjacency.sqlite` 与 `facts/` 不一致）。
- 观察：`graph_integrity_guard.py` **`exit 1`**，且输出含对应规则标记；干净树 `exit 0` 且报
  `scanned` 计数；`code_root` 不存在 → `exit 2`。
- 证据：`tests/graph/test_graph_integrity_guard.py`。

### AC-05 错误路径（环 / 自环 / 悬空边 / 条件不足 → **事件保留、不下结论**）
- 环：`forward_closure` 遇环**不重入、不指数枚举**（`visited` 去重），并报 `cycle_detected`。
- 自环：`from_ref == to_ref` 的边被记为环，闭包**不因自环死循环**。
- 悬空边：边指向**无法解析到已知对象**的 ref → 记为 `dangling`，**不抛异常、不产生下游结论**。
- 条件不足：`stop.should_stop` 在依据门槛不满足时返回 `stop` + `mark=evidence_insufficient`，
  **事件 / 关系保留在真源中**（不删除），**不生成受益结论**。
- 证据：`tests/graph/test_adjacency_and_closure.py::test_cycle_and_self_loop_do_not_loop`、
  `::test_dangling_edge_is_recorded_not_raised`、`tests/graph/test_stage_and_stop.py`。

### AC-06 边界（空图 / 超大图 / 重复边 / 时区）
- 空图：`facts/` 无边 → 闭包返回空集，`truncated=False`，守卫 `exit 0` 且记 `note`。
- 超大图：构造长链（≥ 5000 节点）与高扇出，断言 **单遍遍历、线性耗时**上界（不做路径枚举）。
- 重复边：同 `(from,to,kind)` 多行 → 闭包结果**幂等**（并集不变），守卫报重复为违例。
- 时区：指纹对 `occurred_at` 一律归一到 **UTC 日桶**；同一时刻的不同时区表示 → **同一指纹**。
- 证据：`tests/graph/test_adjacency_and_closure.py::test_empty_graph`、
  `::test_large_graph_is_linear_no_path_enumeration`、`::test_duplicate_edges_are_idempotent`、
  `tests/graph/test_fingerprint_and_identity.py::test_timezone_normalized_to_utc_day_bucket`。

### AC-07 无占位符
- `no_placeholder_guard.py <code_root> --fail-on warn` → **exit 0**；
  代码与 docstring 不含被禁标记；无空函数体；无 `except: pass`。
- 证据：报告附 `verify.py --batch guards` 中 `no_placeholder_guard` 的真实输出。

### AC-08 设计对齐（节号）
- 每条能力在代码 docstring 中标注节号锚点（禁绝对行号，`施工图 §8 纪律 6`）：
  `Ch9 §3.4.3`（闭包 / 失效 / 入队）· `§3.4.7`（指纹）· `§3.3.2`（索引可重建）·
  `Ch7 §B.4`（五者语义层级）· `§C.2/§C.3/§C.5/§C.6`（停止 / SCC / 上限 / 门槛）· `Ch2 §B.3`（命中即 fail）。
- 特别覆盖 `Ch7 §C`：**`capex`（需求侧）≠ 供应商订单 / 收入** —— `assert_not_equivalent` 必抛。
- 证据：`tests/graph/test_stage_and_stop.py::test_capex_is_not_order_or_revenue`。

---

## 边界与不做（诚实登记）

- **不做** `scripts/transmit/`（`Ch7 §C.1` 的 `engine.py`/`demand.py` 编排）：本批次模块清单只含
  `scripts/graph/**`；本层提供**可复用原语**（闭包 / SCC / 停止判定 / 门槛），传导编排与终端需求
  归因留待阶段③ 的 `scripts/transmit/`，**由主理人统一集成**。
- **不新增 `facts/` JSONL**：`Ch9 §3.3.3` 的 18 个**不得增删改名**（`relation_flows` 仅在 `Ch7 §B.3`
  出现，与 `Ch9 §3.3.3` 存在跨章口径差异，非本批次可裁决 —— 已上报）。
- **不改** `verify.py` 批次、`run_all_gates.py`、`pipeline.py`、`conftest.py`、`CONVENTIONS.md`、
  `rules/**`、设计区 `00_*`/`01_`~`11_`。
- **参数不进决策函数**（`施工图 §8 纪律 1`）：`stop.py` 的 `TransmitParams` **不内置阈值**，
  由调用方显式传入或经 `rules/transmission.yaml`（值待冻结）读取；`scripts/graph/**` 属 P-09
  决策作用域，代码**不使用** `weight`/`score`/`vote` 等命中词。
