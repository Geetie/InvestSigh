# 工作流 `ws/claim` · Definition of Done（**先写 DoD，再写代码**，`00_开发Agent开工提示词 §5.1`）

- **工程师**：寇豆码（Kou）· `ws-claim-engineer`
- **主理人**：齐活林（交付总监）
- **工作区**：`/Users/gaza/Developer/InvestSigh/.worktrees/ws-claim`（分支 `ws/claim`，基点 `775e714`）
- **本批次两个模块**（`00_交付施工图 §3.2` 的"主张（C）"行）：
  - **A** `scripts/validators/locator_check.py` —— `full_text_read` 定位校验器（`Ch6 §D` · `Ch6 N6.1-11`）
  - **B** `scripts/claim/transition.py` —— 五态状态机 + `superseded` 传播（`Ch6 §E` · `Ch6 N6.3-10/11/18`）

> 本文件**先于代码**产出。每条 AC **可测**，且两模块**各含 ≥1 条错误路径 + ≥1 条边界**（`§5.1`）。

---

## A. `scripts/validators/locator_check.py` —— `full_text_read` 定位校验器

### T-A  `full_text_read` 不得由"模型自称"代替；程序须能**机械复查**每条主张的定位

- [ ] **AC-01 真跑通**：投递一个真实外部文本 → 真跑 `scripts/orchestrate/ingest_step.py` 落库 claim
      → 对**真实** `facts/claims.jsonl` 跑 `python scripts/validators/locator_check.py <root>`
      → **exit 0**（定位有效）。**不是**只跑单测里的构造体。
- [ ] **AC-02 持久化**：本模块是**只读校验器**（不写 `facts/*.jsonl`）；其"留档"= `run_checker` 落
      `reports/locator_check.py_<date>.json`。**不涉及**写库 → 以"只读 + 报告留档"作为持久化证据（如实标注）。
- [ ] **AC-03 真接线**：`scripts/claim/transition.py` 在**迁移前**调用本模块的 `claim_locator_problems(...)`
      作**定位前置门**（`Ch6 §D` "程序拦截"）→ 本模块**有生产调用方**（非孤儿）。
      另：本模块经 `run_checker` 具 `__main__` CLI 入口，可被 `run_all_gates.py` 收录（**收录由主理人集成时加**）。
- [ ] **AC-04 守卫真拦得住**：制造 `full_text_read=true` 但 `locator` 仅覆盖部分行（或 `quote_hash` 与原文不符）
      → 校验器 **exit 1**（**不是 warn**）。
- [ ] **AC-05 错误路径**：
      - 缺失定位（空 `locator`）→ `LOCATOR_MISSING` → **exit 1**；
      - 非机械可复查的自由文本定位（如 `"p.12"`）→ `LOCATOR_UNRECOGNIZED` → **exit 1**；
      - `locator` 路径穿越（`raw/../rules/...`）→ `LOCATOR_ESCAPE` → **exit 1**；
      - **三字段互换/合并**（把 `claim_form` 取值塞进 `claim_nature`、或 `official_claim_kind` 落在非 `primary`）
        → `CLAIM_SCHEMA_INVALID` / `OFFICIAL_KIND_TIER_MISMATCH` → **exit 1**（`Ch9 §3.4.6` R-17）。
- [ ] **AC-06 边界**：
      - **空 claims** → 显式 `note=NO_CLAIMS` + **exit 0**（无被检对象**不得**当"已验证"，`G-03`）；
      - **超大**（数千行）→ **单遍**扫描、< 2s（`P-01`）；
      - **非法枚举值**（`claim_nature="bogus"`）→ `CLAIM_SCHEMA_INVALID` → **exit 1**；
      - **时间倒挂**（`published_at` 晚于 `first_seen_at`）→ `TIME_INVERSION` → **exit 1**。
- [ ] **AC-07 无占位符**：`no_placeholder_guard.py` 对本模块 **exit 0**（无 TODO/占位/假数据返回）。
- [ ] **AC-08 设计对齐**：判据逐条对应 `Ch6 §D`（采集编排/`full_text_read` 校验器）+ `Ch6 N6.1-11`
      + `Ch9 §3.4.6`（措施①/②：含定位、可复查）+ `Ch9 §3.5`（核验行幂等键 `(source_id, quote_hash)`）+ R-17。

### A 的关键点（"程序拦截，非模型自觉"的可判定判据）

| # | 判据 | 可判定性（`R-06`） |
|---|---|---|
| 1 | `locator` 语法 = `raw/<relpath>#L<start>-L<end>`（能力白名单，未列出的形式**默认拒绝**） | 正则 + 路径解析，唯一判定 |
| 2 | 定位**可复查原文**：`raw/<relpath>` 存在、在 `raw/` 内、`1 ≤ start ≤ end ≤ 行数` | 文件系统 + 行数，唯一判定 |
| 3 | `full_text_read=true` **仅当**定位覆盖**整份**原文（`start=1 ∧ end=行数`）**且** `quote_hash == sha256(原文)` | 哈希相等，运行时效果断言 |
| 4 | `locator` 显式"未披露"哨兵 → 允许，**但强制** `full_text_read=false` | 哨兵前缀 + 逻辑蕴含 |

> 判据 1–4 全部**可判定**（有明确算法）且**覆盖完整**（`raw/` 定位与显式未披露两种形式穷尽；其余默认拒绝）。
> **不**采用"文本里出现哪些词"的关键词判据（`R-06` ①）。

---

## B. `scripts/claim/transition.py` —— 五态状态机 + `superseded` 传播

### T-B  主张状态迁移是**有限状态机**；非法迁移**响亮拒绝**；`superseded` 能**传播**

- [ ] **AC-01 真跑通**：真实 `facts/claims.jsonl` 里的 claim（采集层写入，初始 `status="active"`）
      → `transition(..., "pending_verification")` → 落**新版本行**（追加式），`status` 变更、`recorded_seq` 递增
      → 再 `→ "supported"` → 结果可读出。**主流程真跑到**（非仅函数单测）。
- [ ] **AC-02 持久化**：新状态**追加**为新行（**不改历史行**，`Ch9 §3.4.2` 追加式不可变）；
      删 `index/` 重建 → 末版状态仍在（write-read-reload）。
- [ ] **AC-03 真接线**：`on_superseded` 调用 `scripts/graph/forward_closure`（复用第九章传播，**不新建第二套**，
      `G-06`）；本模块 CLI 可被编排器 step ⑦ 调用（**接线由主理人集成时加**，见报告"需集成项"）。
- [ ] **AC-04 守卫真拦得住**：非法迁移（如 `superseded → supported`、`pending_verification → pending_verification`）
      **抛错 + CLI exit 1**（**不是 warn，不静默兜底、不自动纠正**）。
- [ ] **AC-05 错误路径**：
      - 未知状态（`status="待核验"` 或 `to="frozen"`）→ **响亮拒绝**（`IllegalTransition`/`UnknownClaimStatus`）；
      - 悬空 `superseded` 传播：`forward_closure` 不可用 → `PropagationUnavailable`（**写库前**抛出，不留半截数据）；
      - claim 定位无效 → `ClaimLocatorInvalid`（**exit 1**，接 `locator_check`）；
      - 三字段互换 → 迁移前 `Claim.model_validate` 项**响亮失败**。
- [ ] **AC-06 边界**：
      - 空 `facts/claims.jsonl` → `ClaimNotFound`（明确报错，**不静默**）；
      - `to_status="superseded"` 终态 → **无可再迁移**（再次迁移即 exit 1）；
      - 非法 `version_kind`（不在 `VersionKind` 三值）→ **拒绝**；
      - **时间/序倒挂**：新版本 `recorded_seq` 不大于既有最大、或 `recorded_at` 早于原版 `first_seen_at` → **拒绝**。
- [ ] **AC-07 无占位符**：`no_placeholder_guard.py` 对本模块 **exit 0**。
- [ ] **AC-08 设计对齐**：迁移表逐条对应 `Ch6 §E.1`（状态图）/ `§E.2`（触发器/副作用）/ `§E.3`（`version_kind` 衔接）
      / `§E.4`（`superseded` 复用 `forward_closure`）/ `§E.5`（`refuted` 可重开 vs `superseded` 终态）
      + `Ch9 §3.5`（②行幂等键 `(source_id, quote_hash)`）。

### B 的状态机（允许迁移表，逐条对齐 `Ch6 §E.1` 状态图）

```
        [入口] active（采集层默认 status，schema/models.py::Claim.status）
                │  仅此一条入边（强制显式进入状态机）
                ▼
        pending_verification ──► supported ──► disputed ──► refuted ──► superseded(终态)
             │  ▲                    │            │            │
             │  └── refuted ─────────┼────────────┘            │
             │  （反证被撤回，重开）  │            │            │
             └──► disputed / refuted │            │            │
                                    └────────────┴────────────┘
                                    任意非终态 ──► superseded（上游版本事件）
```

允许迁移表（**严格**，其余一律非法）：

| from ↓ \ to → | pending_verification | supported | disputed | refuted | superseded |
|---|:--:|:--:|:--:|:--:|:--:|
| `active`（采集默认，状态机之外） | ✅ | ❌ | ❌ | ❌ | ❌ |
| `pending_verification` | ❌ | ✅ | ✅ | ✅ | ✅ |
| `supported` | ❌ | ❌ | ✅ | ✅ | ✅ |
| `disputed` | ❌ | ✅ | ❌ | ✅ | ✅ |
| `refuted` | ✅ | ❌ | ✅ | ❌ | ✅ |
| `superseded`（终态） | ❌ | ❌ | ❌ | ❌ | ❌ |

> `active` 是采集层默认值（真库实测行 `"status": "active"`，见批次 5b 报告 §三），**不是** `Ch6 §E.1` 五态之一：
> 本模块把它当**状态机入口别名**，**只允许** `active → pending_verification`（强制显式进入），
> **不允许**它直跳 `supported`（未核验不得进证据集）。此取舍见报告 §四（设计张力，须主理人确认）。

### B 的 `superseded` 传播（复用，不重造）

- 迁移到 `superseded` 时调用 `scripts/graph/forward_closure(claim_id, max_depth=3, detect_cycle=True)`（`Ch6 §E.4`）。
- 对每个下游对象：入 **`recheck` 任务**（`TaskType.recheck`，`Ch9 §2.1.6` 控制面对象）承载"标记 stale"，
  幂等键 `recheck::<claim_id>::<type>::<id>`（重跑不重复建单，`Ch9 §N9.1-26`）；
  `parent_context.requires_recheck = (type ∈ {baseline, recommendation})`（`Ch6 §E.4` 只对结论入复查）。
- `forward_closure` 不可解析 → **写库前**抛 `PropagationUnavailable`（**不静默兜底、不留半截数据**）。

---

## C. 本批次**不**做的事（如实登记，`R-04`）

| # | 不做 | 原因 |
|---|---|---|
| C-1 | 不改 `scripts/ops/verify.py`（新增 `tests/validators/`、`tests/claim/` 批次） | 主理人集成时统一加；改则触 `V-06` |
| C-2 | 不把 `locator_check` 注册进 `run_all_gates.py` / `pre-commit.sh` | 非本模块清单（`G-07` 由主理人集成时补） |
| C-3 | 不实现 `scripts/graph/forward_closure` | 属 `ws/graph` 工作流；本模块只**接线** |
| C-4 | 不改 `schema/models.py` 的 `Claim.status` 默认值 | 非本模块清单；默认 `"active"` 的处置见报告 §四 |
| C-5 | 不改 `scripts/guard/**` | 批次 4 已两轮独立审计（禁改） |
