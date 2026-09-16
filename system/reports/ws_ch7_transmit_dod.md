# DoD · 工作流 `ws/ch7-transmit` —— 传导编排 + 终端需求归因（`scripts/transmit/**`）

> **分支**：`ws/ch7-transmit` ｜ **基点**：`main = d03418a` ｜ **工作区**：`.worktrees/ws-ch7-transmit`
> **权威设计**：`Ch7 §C.1 / §C.2 / §C.4 / §C.5 / §C.6 / §B.4 / §A.6` · `Ch9 §3.4.3`
> **本文件先于代码产出**（`00_开发Agent开工提示词 §5.1`）：**未写出的标准 = 未满足的标准**。

---

## 0. 任务一句话

把「依赖图原语（`scripts/graph/**`，已由 `ws/graph` 交付）」**编排**成 `Ch7 §C.1` 的
**传导引擎**（`scripts/transmit/engine.py`）与 **终端需求归因**（`scripts/transmit/demand.py`）：
给定一次上游撤回 / 一次事件冲击，产出**逐层可达的下游集合**与**逐跳影响**，并**复用**既有入队出口
（`propagate_retraction`）落 `recheck` 任务 —— **不重造任何图算法，只调用**。

> 为什么是本模块（依据来自设计区，非自造）：`Ch7 §C.1` 逐字点名 `scripts/transmit/engine.py` 与 `demand.py`；
> `system/reports/ws_graph_dod.md` 的「不做清单」逐字写着 **不做 `scripts/transmit/`**，
> graph 只提供**可复用原语**（闭包 / SCC / 停止判定 / 门槛），「传导编排与终端需求归因留待阶段③ 的
> `scripts/transmit/`」。**这就是留给本流的活**。

---

## 1. 交付物清单

| # | 交付物 | 落位 | 设计锚点 |
|---|---|---|---|
| D1 | 传导编排（撤回传导：逐层可达下游 + `recheck` 入队） | `scripts/transmit/engine.py` | `Ch7 §C.1` · `Ch9 §3.4.3` |
| D2 | 传导编排（事件/主张 → 逐跳影响：六要素 + 路径记录 + 待核验线索） | `scripts/transmit/engine.py` | `Ch7 §C.1 / §C.2 / §C.6` |
| D3 | 终端需求归因（union-find 同根归并 + 分摊，只计一次） | `scripts/transmit/demand.py` | `Ch7 §C.4` · `§A.6` · `J6` |
| D4 | 包出口（惰性导入，PEP 562） | `scripts/transmit/__init__.py` | `CONVENTIONS §三 P-03` |
| D5 | 自动化测试（传导 / 归因 / 错误路径 / 边界） | `system/tests/transmit/**` | `§5.1` |
| D6 | 本 DoD + 交付报告 | `system/reports/ws_ch7_transmit_dod.md` · `ws_ch7_transmit_report.md` | `§5.1 / §5.2` |

---

## 2. 逐条可测的 AC（每条给**触发方式** + **可观察结果**）

### AC-01 传导编排真跑通（真实输入 → 真实结果 → 真入队）
- **触发**：在**副本** `facts/` 写入真实形态链路 `claim:c1 → baseline:b1 → recommendation:r1`
  （`DependencyEdge` 边 + `Claim`/`Baseline`/`Recommendation`/`Company` 对象），
  调 `engine.retraction_downstream(root, "c1", apply=True)`。
- **观察**：
  ① `reached_by_depth == {1: ("b1",), 2: ("r1",)}`（**方向 / 深度正确**）；
  ② 产出 `recheck` 任务（`TaskType.recheck`，`status=queued`，`parent_context.reason=dependency_stale`）
     **经 `propagate_retraction`**（复用，不新建第二套键），追加进 `facts/tasks.jsonl` 真源；
  ③ 研究深度回退（`tracking → baseline_done`）追加进 `facts/companies.jsonl`；主张**保留不删除**。
- **证据**：`tests/transmit/test_engine_transmit.py::test_retraction_layered_downstream_and_recheck`。

### AC-02 终端需求归因（`demand.py`，`Ch7 §C.4` 口径）
- **触发**：构造 3 条路径共享同一 `root_demand_entity`（如「AI 训练需求」经三条中间链路），
  调 `demand.attribute_terminal_demand(...)`。
- **观察**：三条路径**归并到同一 root** → **只计一次**（`Σ allocated_share == 1.0`，非 3 份）；
  分摊规则按 `J6`（**已知经济暴露份额**按比例；**未披露则均分**）；口径锚点（`Ch7 §C.4`）写进 docstring。
- **证据**：`tests/transmit/test_demand_attribution.py`。

### AC-03 禁跳级等同（`Ch7 §B.4`，`capex ≠ 订单/收入`）
- **触发**：给一次传导的某跳注入 `from_progress_stage="capex"`、`to_progress_stage="revenue"`。
- **观察**：`engine` 在落库前调用 `scripts.graph.stage_order.assert_not_equivalent`，
  **实测真抛 `StageEquivalenceError`**（贴原样输出）。
- **证据**：`tests/transmit/test_engine_transmit.py::test_capex_is_not_revenue_actually_raises`。

### AC-04 停止判定与放大上限（门槛**由调用方传入**）
- **触发**：`engine.transmit(..., params=<调用方显式构造的 TransmitParams>)`；
  构造一条路径使其累计放大超过 `params.amplification_cap`。
- **观察**：命中 `should_stop` 第 ⑦ 条 → `action="stop"`、`effect="decay"`；
  **本模块代码内不存在任何数值门槛常量**（`grep` 无 `importance_threshold=./amplification_cap=.` 之类字面量）。
- **证据**：`tests/transmit/test_engine_transmit.py::test_amplification_cap_from_caller`。

### AC-05 环安全（不重入、不指数枚举）
- **触发**：构造含环的关系边（`a→b→a`）与自环（`x→x`）。
- **观察**：`transmit` **不重入**、不指数枚举；复用 `forward_closure` 的 `visited` 与
  `cycles` 的 SCC；`cycle_detected=True`、`cycle_nodes` 正确；结果对重复运行**幂等**。
- **证据**：`tests/transmit/test_errors_and_edges.py::test_cycle_does_not_reenter_or_enumerate`。

### AC-06 错误路径（**响亮失败**，不得静默返回空集 / 默认值）
- **触发 / 观察**（各一条）：
  ① **边表缺失**（`facts/` 里**无**该 JSONL 文件）→ `FileNotFoundError`；
  ② **ref 不可解析**（`start` 不在对象索引中，且索引非空）→ `ValueError`；
  ③ **阈值未传**（`params=None` 且无 `rules/transmission.yaml`）→ `FileNotFoundError`（经 `load_transmit_params`）；
  ④ **出现跳级等同** → `StageEquivalenceError`（见 AC-03）。
- **证据**：`tests/transmit/test_errors_and_edges.py::test_loud_failures`。

### AC-07 边界（4 条）
- **空边表**：`facts/relations.jsonl` 存在但 0 行 → 返回空 `impacts`，
  **显式 `note` 前缀 `EMPTY_EDGE_TABLE:`**（`CONVENTIONS §二 G-03`：**不得**当「已验证」）。
- **单点链**：单跳 → 1 条 impact，`depth == 1`。
- **高扇出**（单遍、线性）：1 起点 + N 条出边 → **N 条 impact**（不做路径枚举 → 不指数爆炸）。
- **重复边幂等**：同 `(from,to,kind)` 多行 → 结果与单行**逐项相同**。
- **证据**：`tests/transmit/test_errors_and_edges.py`。

### AC-08 复用而非重造（`G-06` 唯一真源 / 纪律 11）
- **观察**：`scripts/transmit/**` **只调用** `scripts.graph.**` 的
  `forward_closure` / `should_stop` / `evidence_gate` / `assert_not_equivalent` /
  `load_edges` / `object_index` / `propagate_retraction`；
  **不存在**任何重造的闭包 / SCC / 停止判定定义（`grep 'def forward_closure|def sccs|def strongly_connected|def should_stop|def evidence_gate' scripts/transmit` → 空）。
- **证据**：报告附 `grep -n` 原样输出。

### AC-09 设计对齐（节号锚点）
- 每条能力在 docstring 标注节号锚点（`Ch7 §C.1/§C.2/§C.4/§C.5/§C.6/§B.4/§A.6`、`Ch9 §3.4.3`），
  **禁绝对行号**（`施工图 §8 纪律 6`）。

### AC-10 无占位符
- `no_placeholder_guard.py system --fail-on warn` → **exit 0**；
  代码、注释与 docstring 均不含被禁标记；无空函数体；无 `except: pass`。

---

## 3. 关键设计决策（预先声明 + 依据节号）

1. **只编排、不重造**（`纪律 11` / `G-06`）：传导遍历的**可达性 / 环 / 深度**一律取
   `scripts.graph.closure.forward_closure` 的结果；**停止判定**一律调 `scripts.graph.stop.should_stop`；
   **跳级等同**一律调 `stage_order.assert_not_equivalent`；**入队**一律调 `propagate.propagate_retraction`。
   transmit 层新增的只是**编排**（把上述原语串成 `Ch7 §C.1` 的引擎契约）与**终端需求归因**（`§C.4`）。
2. **参数不进决策函数**（`施工图 §8 纪律 1` / `P-09`）：`transmit` 的一切阈值经
   **调用方显式传入的 `TransmitParams`** 或 `rules/transmission.yaml`（唯一真源，值待冻结）；
   本模块**不内置任何数值门槛**。缺文件 / 缺参数 → **响亮失败**（不静默兜底）。
3. **决策作用域禁词**：`scripts/transmit/**` 代码、docstring、字符串**不出现**
   `P-09` 命中词（无加权 / 打分 / 投票 / 情绪 / 粉丝数）；分摊一律用「份额（share）」语义。
4. **终端需求口径**（`Ch7 §C.4`）：同 `root_demand_entity` → **只计一次**；分摊按
   `J6`（已知经济暴露份额按比例、未披露均分），**不各自全额计入**。
5. **六要素输出**（`Ch7 §C.1`）：每跳产出 `variable / direction / magnitude / conditions /
   counter_forces / time_lag`；**缺条件则不成立**（`§C.6` 依据门槛已在 `stop.evidence_gate` 内）。
6. **未披露幅度用保守值**（`Ch7 §J5`）：`magnitude` 默认 `"undisclosed"`，
   **不点估计**（与 `stop.GAIN_KEY_UNDISCLOSED` 同口径）。

---

## 4. 已知缺口 / 不做（如实登记）

- **不创建 / 修改 `rules/**`**：若需 `rules/transmission.yaml`，本流**只报所需键 + 建议值 + 依据**，
  由主理人按 `lock_rules.py` 流程落。（见报告「需新增配置键」。）
- **不改** `scripts/orchestrate/**`（`pipeline.py` / `chain_steps.py`，正在被审计）、
  `scripts/checks/**`、`scripts/ops/**`、`scripts/graph/**`、`scripts/decision/**`、`scripts/validators/**`、
  `scripts/compute/**`、`scripts/claim/**`、`schema/**`、`tests/conftest.py`、`CONVENTIONS.md`、设计区。
- **不改** `verify.py` 批次：`tests/transmit/` 是新目录 → `verification_policy_guard`（`V-06`）**预期红**
  （批次由主理人统一加）；本流只报「需新增批次 `transmit`」。
- **`relation_flows` 表**：`Ch9 §3.3.3` 的 18 个 JSONL 不含 `relation_flows`（跨章口径差异，已由 `ws/graph` 上报）。
  本流**不新增 `facts/` JSONL**；需求信号（`demand_signal`）作为**归因输入**（调用方经 `Hop.terminal_demand_id` /
  `HopFields` 传入），不落新表。
- **真实 `relations` / `relation_flows` 数据**：真仓库 `facts/` 目前为空（除 `industry_nodes` 44 行），
  故 AC-01/02/04/05/07 均在**副本**上以**真实对象形态**注入验证；**写入型探测只在副本上做**。
- **不做** Skill 编排（`aichain-transmission`）、建议生成（`scripts/decision/**`）、展示视图（`views/**`）——
  不属本流模块清单。

---

## 5. 验证计划（逐条怎么验）

| AC | 命令 | 期望 |
|---|---|---|
| AC-01~07 | `sh system/scripts/ops/run_pytest.sh tests/transmit -q` | 全 passed，exit 0 |
| AC-03 | 见报告「`assert_not_equivalent` 实测真抛」 | `StageEquivalenceError` 输出原样贴出 |
| AC-08 | `grep -n 'def forward_closure\|def sccs\|...' system/scripts/transmit/*.py` | 无输出 |
| AC-10 | `no_placeholder_guard.py system --fail-on warn` | exit 0 |
| 门禁 | `sh system/scripts/ops/pre-commit.sh` | 全绿（唯一预期红：`verification_policy_guard` `V-06`） |

> 单命令超时 ≤ 60s；超时 = 该批有问题（`V-03`），如实上报。
