# ws/ch6-verify · 证据层 Definition of Done（先写后做）

> **工作树**：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-ch6-verify` ｜ **分支**：`ws/ch6-verify` ｜ **基点**：`main = d4f3aed`
> **只改**：`system/scripts/evidence/**` · `system/tests/evidence/**` · 本文件 + `ws_ch6_evidence_report.md`
> **写 DoD 依据**：`00_开发Agent开工提示词 §5.1`（**未写出的标准 = 未满足的标准**）

---

## T01 一句话

> **Ch6 证据层（阶段③ `core_chain` 的两条并行流之一：`Ch6 证据层 ∥ Ch7 传导层`）** —— 把
> ① "同一消息被多家转述" 机械判定为**一个原始证据来源 + 多条传播记录**（**不**升为多份独立佐证，`Ch6 §6.3` 第 3 步 / `§C`）；
> ② 第 6 步的**预算闸门**（时间 / 计算 / 检索三类预算取先到者 → 到限转 `pending_verification` + 保留可重入任务，`Ch6 §D.5`）。

**主责章依据**：`10_验收与持续复盘/01_需求拆解.md §2.1` 权威表 —— `T01` 最终主责章 = **Ch6**。

---

## 交付物清单

| # | 文件 | 性质 |
|---|---|---|
| 1 | `system/scripts/evidence/__init__.py` | 新增（惰性导入，`P-03`） |
| 2 | `system/scripts/evidence/independence.py` | 新增：追源去重与独立判定（`Ch6 §C.1~§C.4` / `§F.2~§F.3`） |
| 3 | `system/scripts/evidence/budget_gate.py` | 新增：预算闸门（`Ch6 §D.5`） |
| 4 | `system/tests/evidence/test_independence_t01.py` | 新增：T01 正反双向 + 错误路径 + 边界 |
| 5 | `system/tests/evidence/test_budget_gate.py` | 新增：三类预算取先到者 + pending + 可重入任务 + 参数缺省 |
| 6 | `system/reports/ws_ch6_evidence_dod.md` | 本文件（**先写**） |
| 7 | `system/reports/ws_ch6_evidence_report.md` | 收工四段式报告（`§5.2`） |

**复用声明（不重造，`G-06` 唯一真源）**：本工作流**新增 0 条**指纹 / 定位 / 状态机 / 写库路径，全部**调用**既有原语：

| 既有原语 | 用途 |
|---|---|
| `scripts/graph/fingerprint.py::event_fingerprint` | 消息去重身份（`Ch9 §3.4.7`：基于**根来源**而非标题） |
| `scripts/validators/locator_check.py::claim_locator_problems` | 迁移前的 `full_text_read` 定位机械复查 |
| `scripts/claim/transition.py::transition` | **唯一**的 claim 状态写入者（预算到限 → `pending_verification`） |
| `schema/store.py::append_records` | **唯一**写入口（传播记录 / 任务） |
| `schema/store.py::as_of` | 同一 `claim_id` 多版本取最新（`Ch9 §3.4.1`） |
| `scripts/decision/triage.py::research_cap` | 研究投入上限（**唯一** `BUDGET_MAP` 真源） |

---

## 逐条可测 AC（触发方式 + 可观察结果）

### A. 追源去重与独立判定（`Ch6 §6.3` / `§C`）

- **AC-01 真跑通（T01 正向，权威表逐字）**：`10_验收与持续复盘/01_需求拆解.md §2.1`
  场景 = **十篇文章转述同一匿名订单消息** → 预期 = **保留一个原始证据来源及传播记录，不提升为十份独立佐证**。
  触发：造 1 条根主张 + 10 条转述（指纹同、`origin_claim_id` 指向根）→ `classify_independence(...)`
  → 可观察：`independent_evidence_count[根] == 1` **且** 传播记录行数 **== 10**（**保留**，非丢弃）
  **且** 10 条转述均 `independent_evidence=False`。
- **AC-02 反向对照（T01 反向，证不欠报）**：3 条**真正独立**（无共同上游）的同一消息来源
  → `independent_evidence_count == 3`（`Ch6 §C.4` 判据的反向）。
- **AC-03 传播记录真落库 + 幂等**：`classify_and_record(root)` → `facts/claim_propagation.jsonl`
  真新增 10 行；**再跑一次** ⇒ 0 新增（append-only 下的幂等）。
- **AC-04 复用证据**：`grep` 显示本目录**只调用** `event_fingerprint` / `append_records` / `as_of`，
  **不新增**第二套指纹/写库（`G-06`）。

### B. 预算闸门（`Ch6 §D.5`）

- **AC-05 三类预算取先到者（实测各一个到限场景）**：分别命中
  **时间**（`deadline`）/ **计算**（`max_model_calls`，且受 `research_cap` 上界约束）/ **检索**（`max_searches`）
  → 每次 `exhausted=True` 且 `first_binding` == 该类别。
- **AC-06 到限行为**：到限 → 该主张 `pending_verification`（已是则记 note；否则经 `transition` 写入）
  **且** 生成**可重入** `VerificationTask`（`task_type=verify`、`status=queued`、含幂等键 + `budget_used`）
  → 真落 `facts/tasks.jsonl`；**绝不静默丢弃、绝不把未完成结论标为已验证**。
- **AC-07 `research_cap` 仅由 importance 决定**：同 `importance`、不同 `tier`/`quality` → **cap 相同**（`Ch6 §B.2` 逐字禁令）。
- **AC-08 参数不内置**：预算值一律走 `config/freeze.py::get_param('p09')`（`blocking_targets` 含 `Ch6 §D.5`）
  + `rules/budget.yaml`（缺则**显式缺省**或**响亮失败**，"待定"参数走 `tbd` 不阻塞开工）。

### C. 硬约束与纪律

- **AC-09 错误路径（≥1）**：`rules/budget.yaml` **缺失且未给显式缺省** → **响亮失败** `BudgetConfigMissing`（**不静默兜底**）。
- **AC-10 边界（≥1）**：`facts/claims.jsonl` 为空 → 无被检对象（`G-03` 显式 note、`independent_evidence_count == {}`、
  **不崩**）；`origin_claim_id` 成环 → **响亮拒绝**（不无限回溯）。
- **AC-11 无占位符**：`no_placeholder_guard.py` 通过（本目录 0 命中）。
- **AC-12 禁词**：决策作用域禁词（`weight`/`score`/`vote`/`sentiment`/`follower_count`）0 命中（`P-09`）。
- **AC-13 不污染真源**：所有写入型探测在**夹具副本**上；真仓库 `facts/` 保持 5 claims / 3 edges。
- **AC-14 设计对齐**：逐条对应 `06_公开信息与证据筛选/02_实现方案.md §C`（去重/独立）与 `§D.5`（预算闸门）。

---

## 关键设计决策（预先声明 + 依据节号）

| # | 决策 | 依据 |
|---|---|---|
| D1 | **不新建 `facts/` JSONL**：传播落既有 `claim_propagation`（18 个之一） | `Ch9 §3.3.3`（18 个不得增删改名） |
| D2 | 独立判定 = **内容分组（指纹）+ `origin_claim_id` 共同上游（union-find）**；`is_restatement ⟺ 有上游`，`is_independent ⟺ 无上游 且 direct_knowledge=direct` | `Ch6 §C.1`（共同上游求根）/`§C.2`（算法步骤）/`§F.3`（认定边界） |
| D3 | 分组键 = `fingerprint.event_fingerprint(root_source_id=根来源)`，**不按标题/措辞** | `Ch9 §3.4.7`（"基于根来源而非标题"）；`Ch6 §C.2` |
| D4 | `claim_alias` 人工 override（`Ch6 §C.3`）**不做**：它需要第 19 个 JSONL，违反 `Ch9 §3.3.3` | `Ch9 §3.3.3`（登记为已知缺口） |
| D5 | 预算三类 = 时间/计算/检索；`compute_limit = min(config.max_model_calls, research_cap)` | `Ch6 §D.5`（三类 + `research_cap` 给上限，取先到者） |
| D6 | `research_cap` **调用** `triage.research_cap`，本模块**不复制** `BUDGET_MAP` | `G-06`；`Ch6 §B.2` |
| D7 | 预算值来源优先级：`rules/budget.yaml` > `freeze p09`（数值映射）> 显式 `defaults`；**皆无 → 响亮失败** | `Ch6 §D.5`（谁设预算）；`§6.1`（缺值必须显式） |
| D8 | 模块放 `scripts/evidence/`（**不改** `scripts/graph/**`，设计 §C.2 伪码处此名但该目录禁改） | 主理人写入域约束；`R-04`（不擅自改设计数据契约，登记偏差） |

---

## 已知缺口 / 不做清单（如实登记）

1. **`claim_alias` 人工 override（`Ch6 §C.3`）不做** —— 需第 19 个 JSONL，违反 `Ch9 §3.3.3`（见 D4）。
   本模块对"根但非直接知情"的存疑项仅输出 `review_candidates`，不落 override 记录。
2. **`independent_evidence_count` 不落为 claim 字段** —— `schema.models.Claim` 无此字段且 `schema/**` 禁改
   （`extra="forbid"`）。本模块以**计算 API + 报告**暴露该基数（`Ch6 §B.4`：它是**基数**不是权重）。
3. **`rules/budget.yaml` 不存在**（`rules/` 0444，仅主理人经 `lock_rules.py` 可落）——
   本模块对"缺文件"实现**响亮失败 / 显式缺省**两条确定路径；是否落该文件**上报主理人**。
4. **`V-06` 预期红** —— `tests/evidence/` 是新目录，`verify.py::BATCHES` 无 `evidence` 批次；
   按 `V-06` 与主理人约定，**不自行改 `verify.py`**，只在报告登记"需新增批次 `evidence`"。
5. **预算闸门不强制非法状态回退**：设计状态机仅允许 `refuted → pending_verification`（`Ch6 §E.1`），
   `supported/disputed → pending_verification` **非法**。故本模块对非 pending 主张：已是 pending → no-op；
   否则**调用** `transition` 并如实暴露其合法性（**不静默造状态**）。
6. **`rules/budget.yaml` 的预算具体数值为 `tbd`**（`freeze.yaml p09.budget: tbd`）——值未冻结，代码路径完整。

---

> **说明**：AC 均含触发方式 + 可观察结果；**≥1 错误路径（AC-09）** + **≥1 边界（AC-10）** 已含。
