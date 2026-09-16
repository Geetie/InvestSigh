# 批次 6 任务书 —— §九 独立审计后的修复与集成收口

> **签发人**：齐活林（交付总监 / 主理人）· **签发时间**：2026-09-16
> **触发**：`§九 独立验收`（换人、新会话、对抗性）对 `ws/compute` · `ws/graph` · `ws/claim` 三流审计完毕。
> **审计实体**：`reports/ws_independent_audit_compute.md` · `reports/ws_independent_audit_graph_claim.md`
> **对拍基准**：`00_开发Agent开工提示词 §5.1/§六/§八/§九` · `system/CONVENTIONS.md`（V/G/P/R）· 各流 `ws_*_dod.md`
> **纪律**：本任务书先于修复代码产出（`§5.1`）。未写出的标准 = 未满足的标准。

---

## §0 为什么要开这一批：审计推翻了"已验收"的假设

自审（`reports/parallel_workstreams_self_audit.md`）只证明了"**已合并**"。独立审计的结论是：

| 流 | 判定 | FAIL | PARTIAL | UNKNOWN |
|---|---|:--:|:--:|:--:|
| `ws/compute` | **not accepted** | 1 | 2 | 2 |
| `ws/graph` | **not accepted** | 1 | 1 | 2 |
| `ws/claim` | **not accepted** | 3 | 2 | 2 |
| `ws/decision` | 已合并（**独立审计未做**，批次 7 排期） | — | — | — |

**四条流的 FAIL 高度同构** —— 各自的 `AC-03 真接线` 全部不合格：

- `ws/compute`：`make_derived_handler` 工厂存在，但 `pipeline.py` 未注册；
- `ws/graph`：全树 `scripts.graph` / `graph_integrity_guard` 在 `scripts/graph/**` 之外**零引用**；
- `ws/claim`：`transition.py` 自身零生产调用方，而它调的 `locator_check` 也未注册 → **孤儿调用孤儿**；
- `ws/decision`：同形（`AC-03 PARTIAL`）。

→ **共同根因**：`scripts/orchestrate/pipeline.py::_register_default_steps()` **只注册了 step 1**，
而 `rules/pipeline.yaml`（**0444 锁定 = 设计真相源**）声明 **step 1–6 `implemented_in_first_version: true`、`blocking: true`**。
即 **`G-13`** 的同一件事：**声明与实现脱节**。

**关键推论**：四条流的组件**现在都建好了**。因此"接线"不再是跨阶段（②③）的事，
而是**兑现 `rules/pipeline.yaml` 既有声明的阶段①义务**。接线是批次 6 的主线。

---

## §1 修复流 A：`fix/claim-propagation`（接入时进行中）

| 项 | 内容 |
|---|---|
| 工作树 | `.worktrees/fix-claim-propagation` |
| 分支 | `fix/claim-propagation`（基点 `main` = `4756028`） |
| 负责模块 | `system/scripts/claim/transition.py` · `system/tests/claim/**`（+ 授权扩范围：`scripts/graph/propagate.py` 的 `parent_context`） |
| 目标 | 消除**阻断级跨流缺陷 `N-2`** 与**半数据窗口** |

### 缺陷事实（主理人已复核并实测）

1. **签名三层不匹配**：`transition.py:335` 调 `forward_closure(claim_id, max_depth=3, detect_cycle=True)`；真实签名为
   `forward_closure(code_root, start, *, max_depth=3, source=..., edges=None, known_refs=None, valid_asof=None)`
   —— `code_root` 是第 1 位置参数、`start` 必填、**无 `detect_cycle`**。实测 `TypeError`。
2. **返回类型不匹配**：真实返回 `ClosureResult`（`closure.py:37`，`@dataclass`，**不可迭代**），
   其 `reached` 是**裸 ref 字符串**；而 `_normalize_ref`（`transition.py:269`）要求 `.object_type`/`.object_id` → **永不成立**。
3. **测试为何没抓到**：`tests/claim/test_transition.py:92` 的桩是 `_closure_fn(*_args, **_kwargs)`
   —— **吞掉一切参数**，错位参数永远测不出来 → **真实传播路径零覆盖**。
4. **半数据**：`_append_claim`（`:403`）在 `_propagate`（`:414`）**之前** → 传播抛错时真源已留 `status=superseded` 行、
   而 `recheck` 任务 0 条 → 违反追加式一致性，且与模块自身 docstring「写库前失败，不留半截数据」矛盾。
5. **重复实现（主理人复核时新发现，比审计报告更深一层）**：`scripts/graph/propagate.py::propagate_retraction`
   **已完整实现同一件事**（`object_index` → ref→stem；`RECHECK_STEM_TYPES` 过滤；幂等键 `recheck::<ref>::<target>`；`apply` 落库 + 深度回退）。
   `transition.py` 自带的第三套幂等键 `recheck::<claim_id>::<type>::<id>` 与它在**同一 `facts/tasks.jsonl`** 争用同段前缀 → **重复建单**。
   违反 `G-06 唯一真源` 与 `纪律 11 复用优先`。

### 验收判据（必须先失败、再变绿）

- [ ] `_propagate` / `_normalize_ref` / `_append_recheck_task` 的"自带一套"部分被删除，改为**委托** `propagate_retraction`；
- [ ] **解析阶段前移**：制造一次解析失败 → `facts/claims.jsonl` 与 `facts/tasks.jsonl` **零新增行**（贴 `wc -l` 前后对比）；
- [ ] 吞参数桩被删除或改为**显式形参签名**；
- [ ] 新增**不注入、走真实路径**的用例：真落 `recheck` 任务（键为 graph 那套）+ 重跑幂等（新增 0）；
- [ ] `tests/claim` 与 `tests/graph` 双绿（证明不误伤 graph）；
- [ ] 诚实登记**残留 I/O 窗口**（无事务机制，不得吹成原子）。

---

## §2 修复流 B：`fix/compute-silent-defects`（接入时进行中）

| 项 | 内容 |
|---|---|
| 工作树 | `.worktrees/fix-compute-silent-defects` |
| 分支 | `fix/compute-silent-defects`（基点 `main` = `4756028`） |
| 负责模块 | `system/scripts/compute/**` · `system/tests/compute/**` |
| 目标 | 修四条**"该响的时候没响"**的静默缺陷（全部经主理人复核定位） |

| # | 位置 | 静默行为 | 应有行为 |
|---|---|---|---|
| **C-01** | `contract.py:167-173` `require_nonzero` | `value is None` 时 `None == 0` 为假 → **静默放过**，随后抛**裸 `TypeError`** | 折叠为**缺口对象**（DoD AC-05 明文：缺汇率 → 缺口，不得返回 `None`/`0`/估算值） |
| **C-02** | `contract.py:150-153` `derived_id_for` | 幂等键实际是 `(kind, subject, method_version)`，**缺 `version`**（设计 `Ch9 §3.5` 要求 `(company_id, version, method_version)`）→ 上游重述后**静默保留陈旧值并报 OK** | 键纳入 `version`；重述必须**追加新 `DerivedValue`**，旧行逐字节不变 |
| **C-03** | `step.py:49` `produced=list(report.derived_ids)` | `derived_ids` 是**每次重算的全部 id**（`driver.py:328`），与是否落库无关 → 幂等重跑时 `produced` 仍非空 → **击穿编排器 `G1-05` 空执行守卫** | `produced` = **本次真正新增落库**的 id 集合 |
| **C-05** | `valuation.py:114-123` | 两个时间都 `None` 时**整个跳过** `Ch5 §D.3` 顺序校验，并静默注入 `now()` —— 与其自身 docstring「不得用当前时间兜底」**自相矛盾** | 双 `None` **响亮拒绝** |

**P2（修或如实登记，不许静默）**：`growth.py:104` `cash_threshold=0.8` 硬编码阈值（`纪律 1` 禁参数内置）·
`Ch4 §D.3` 分档与实现的 `medium`+标志位不一致 · `NumericClaim` 零命中 · `share_count`/`compute_date` 未落库。

**每条必须附**：改动位置 + **原样测试输出** + 退出码 + **反向对照**（证明不误伤）+ `AC-01` 真实运行重跑（证明没破坏）。

---

## §3 集成主线（**主理人亲自做**，不外派）

四条流都按纪律**不改共享文件**，所以"注册/接线"必须由主理人统一执行。批次 6 的集成清单：

| # | 动作 | 依据 | 预期效果 |
|---|---|---|---|
| **I-1** | `pipeline.py` 注册 step 1–6 处理器（消费 `scripts/{ingest,claim,graph,compute,decision}` 现有出口） | `rules/pipeline.yaml` 的 `implemented_in_first_version: true` · `G-13` | `AC-03 真接线` 由 FAIL → PASS；`Pipeline.run_daily` 不再 8 步全 `gap` |
| **I-2** | `run_all_gates.py` + `pre-commit.sh` 注册 `graph_integrity_guard` 与 `locator_check` | `ws_graph_dod AC-03` · `ws_claim_dod A-AC-03` · `G-07` | 两个孤儿检查器获得生产调用方 |
| **I-3** | `schema/store.py::read_records` 缺失真源由 `return []` 改为**响亮失败**（区分"缺失"与"0 行"） | 审计 `N-1`：当前守卫据此 `exit 0` PASS | 消除"空真源被当已验证"（`G-03` 同类） |
| **I-4** | `verify.py` 批次 11 → **12 批**（新增 `decision`） | `reports/parallel_workstreams.md §5 I-3` | ✅ **已完成**（`a90ee91`；12 批 475 用例全绿） |
| **I-5** | 修正过期契约文本：`ws_claim_dod.md` 的 `active` 行/迁移表格；`Ch9 §3.4.6 措施①/②` 不存在的子锚点 | 审计：`B-AC-01` 前提过期 · `A-AC-08` `纪律 6` | DoD 与代码一致；不再"DoD 写了代码不认" |

> **`--no-verify` 一律禁用**（除 §1.5 三条件外）。集成 worktree 的 pre-commit 必须**正常通过**。

---

## §4 ★ 待需求方裁定：张力 `T-08`

`rules/pipeline.yaml`（**0444 锁定，主理人无权修改**）声明 step 1–6 首版已实现且 `blocking: true`；
但 step 4/5/6 的**完整**产物（`baselines` / `expectations` / `benchmarks` / `recommendations`）
含**模型侧假设生成**，其组件按施工图属阶段②③。已在建的是其中的**算术/图/状态机部分**。

**三个选项**（须需求方择一）：

| 选项 | 内容 | 后果 |
|---|---|---|
| **A（推荐）** | 注册 1–6，算术/图/决策部分接实现；模型侧缺口**显式标 `degraded` + 记 gap**，不静默 | 项目**当天可端到端跑**；`blocking: true` 与"step 报 ok"之间的落差被**如实登记**而非掩盖 |
| B | 仅注册已有完整实现的步，其余保持 `gap` | 保守；但 `assert_steps_complete` 仍会挡，端到端跑不通 |
| C | 保持现状，等阶段②③ | 四条流继续是孤儿；`G-13` 长期挂账 |

**主理人建议选 A**：需求方明确要求「**尽快看到一个能真实开始干活的项目**」，
而 A 是唯一能在**不改 `rules/`、不伪造模型输出**的前提下让主流程真实跑起来的路径。

---

## §5 状态快照（截至本任务书签发）

| 项 | 值 |
|---|---|
| `main` | `a90ee91`（§九 审计结论登记 + decision 批次集成） |
| 批次 | **12 批 / 475 用例全绿**（`42+6+56+119+8+82+36+20+20+86`） |
| 工作树 | 主 + `integration` + `ws-{compute,graph,claim,decision}` + `fix-{claim-propagation,compute-silent-defects}` = **9** |
| 进行中 | `fix/claim-propagation` · `fix/compute-silent-defects`（各自分支，互不干扰） |
| 未做 | `ws/decision` 独立审计（批次 7 排期）· `T-08` 裁定 · `p01`/`p03` 参数冻结 |
| 门禁 | 20 项绿 · pre-commit 8 项绿 · `batches: 12` `test_files: 39` `uncovered: 0` |

### 铁律（对所有参与方，逐条硬约束）

- **W-1** 只在自己的工作树里工作（绝对路径）；**W-2** 绝不 `cd` 到主仓库或他人工作树；
  **W-3** 绝不切分支（`checkout`/`switch`/`reset`/`rebase`/`stash`/`merge`/`worktree` 全禁）。
- **G-2** 只 `git add <具体文件>`，**永不** `-A` / `.`；**G-3** 只在自己分支提交，**不做集成**；
  **G-4** 绝不 `gc`/`prune`/`repack`/`clean`；**G-5** 提交信息用 `-F <文件>`，防引号破坏；
  **G-7** 不与其他成员直连，只回主理人。
- **V-01** 禁全量验证；**V-02** 每批独立超时；**V-03** 超时 = 不合格，绝不当通过；
  **V-04** 一律沙箱外跑；**V-06** 新增测试目录必须同时加批次。
- **R-06** 禁关键词/名单式判据；判据须**可判定 + 穷尽**；**允许清单优于禁止清单**。
