# 并行工作流任务书（`ws/compute` · `ws/graph` · `ws/claim`）

> **依据**：需求方指令——
> 「现在单开一个阶段还是太慢了。其他阶段应该有可以解耦并行开发的模块功能。
> **写任务书**，规定各自在哪个 **worktree** 干活、**git 操作规范**（此前项目多次出现多 Agent git 事故）、
> 怎么测试、当前任务状态、任务目标。**派完工程师干活去后就立即写任务书**。」
>
> **本文件 = 三份任务书的合集 + 共用规范 + 集成计划。**
> 锚点一律**节号**（`Ch9 §3.5`），禁绝对行号。

---

## 0. 为什么可以并行（解耦依据）

**关键前提：真源与契约都已冻结** —— 所以"只依赖冻结契约"的模块可以立即并行，不必等前一阶段"整体过门"。

| 已冻结的东西 | 锚点 | 为什么它使并行安全 |
|---|---|---|
| `facts/` 18 个 JSONL 的 schema | `Ch9 §3.3.3` · `system/schema/models.py` | 有 `schema_sync_guard` 守住"生成物与模型一致"，下游只要按 schema 读写就不会互相踩 |
| 六阶段模块 I/O 契约（输入/输出/幂等键/失败处理） | **`Ch9 §3.5`** | 模块之间是**契约**关系而非实现依赖 → 可各写各的 |
| 20 项门禁 + 开发规范 | `system/CONVENTIONS.md` | 每个 worktree 都能**独立自检**，不必等集成才发现违规 |
| 分批验证器（7 批 / 独立超时） | `verify.py` · `CONVENTIONS.md §一` | 并行 worktree 各自验证互不干扰 |

**为什么"单开一个阶段"慢**：阶段门（`stage_gate`）是**串行闸门**，但它闸的是"阶段交付物是否齐备"，
**不是"每个模块必须等前一模块写完"**。`施工图 §5.2` 本身就允许阶段内并行（"接口先冻结即可并行"）；
本次把这条纪律**跨阶段**用起来：凡是**只依赖冻结契约**的 C 档模块（`施工图 §1.3`：C 档只保留**可单测的确定性薄层**），
都不该排队。

### 0.1 可并行 / 需先冻接口 / 不可并行

| 分类 | 模块 | 依据 |
|---|---|---|
| ✅ **可立即并行**（本次派出） | `scripts/compute/**` · `scripts/graph/**` · `scripts/validators/**` + `scripts/claim/**` | 只依赖 `facts/` schema 与自身 I/O 契约 |
| ⏭️ **下一轮可并行** | `scripts/ingest/guard.py`（`Ch6 §N6.1-01` 来源白名单）· `views/**` 三入口（`Ch8 §B`）· `scripts/transmit/**`（`Ch7 §C`） | 依赖各自 registry / facts 视图，与本次三流文件集互斥 |
| ⚠️ **必须先冻结接口** | `scripts/decision/**`（gate + triage） | 依赖 `compute` 与 `graph` 的**函数签名** → 等本次两流落地后冻结签名再并行 |
| ❌ **本质上不可并行** | 阶段② `nvidia_sample` 六步链 · 阶段③ `T01–T14` | 前者需**真实数据** + `p01`/`p03` 冻结；后者是**跨模块集成判据**，只能在全链就绪后评 |

---

## 1. 共用规范：worktree 与 git 铁律 ⛔

> **背景（为什么要写这么细）**：本项目**此前多次出现多 Agent 并发 git 事故**——
> worktree 混乱、并发读写 git、抢当前分支、**不在自己 worktree 里操作**。
> 以下每条都是**硬约束**，违反即视为事故：**立即停止并上报主理人**。

### 1.1 工作区规则

| # | 规则 |
|---|---|
| **W-1** | **你的唯一工作目录 = 你的 worktree 绝对路径**（见各任务书）。所有文件读写与命令**一律用绝对路径**在其下执行。 |
| **W-2** | **永远不要 `cd` 到主仓库 `/Users/gaza/Developer/InvestSigh`，也不要进其他 WS 的 worktree** —— 它们正在被其他 Agent 并行使用。 |
| **W-3** | 主仓库 = **设计真相源**（`00_*` + `01_`~`11_`）**只读** + `system/` 的集成分支。**你不写主仓库。** |

### 1.2 Git 铁律

| # | 禁止 | 为什么 |
|---|---|---|
| **G-1** | `git checkout` / `switch` / `branch` / `reset` / `rebase` / `merge` / `cherry-pick` / `stash` / `push` / `fetch` / `tag` | **任何分支操作**。你的分支在 worktree 创建时已固定，**不需要也不允许**切换。抢当前分支正是历史事故的主因 |
| **G-2** | `git gc` / `prune` / `repack` / `worktree <子命令>` | 多 worktree **共享 object store**，这些命令会互相破坏 |
| **G-3** | `git add -A` / `git add .` | **只准白名单式 add**（`git add <你的模块路径>`）。`-A` 会把别人的东西或设计区一起提交 |
| **G-4** | 向 `main` 提交 | **只准在你的 `ws/<name>` 分支上 commit** |
| **G-5** | 任何集成动作 | **merge 回 main 由主理人单独执行** |
| **G-6** | 跨模块改动 | **禁止修改**：`rules/**`（0444 锁定）· 设计区 `00_*`/`01_`~`11_` · `system/tests/conftest.py` · `system/CONVENTIONS.md` · `system/scripts/ops/verify.py` · `system/scripts/guard/**`（批次 4 已交付并经两轮独立审计） · 以及**任何不在你模块清单内的文件** |
| **G-7** | 用 git 传递信息 | 沟通**只用 SendMessage + 报告文件**。**不要**用 commit / branch / tag 当"消息" |

**允许的 git 操作（只有这三个）**：
```bash
git status                                  # 看你自己 worktree 的状态
git add <你的模块路径>                        # 白名单式
git commit -m "ws(<name>): <摘要>"           # 在你自己的分支上
```
**提交信息格式**：`ws(<name>): <摘要>`；body 写任务编号与对应 AC 编号。

### 1.3 一个必须知道的约束：`V-06`

`CONVENTIONS.md §一 V-06` 要求「**新增测试目录必须同时在 `verify.py::BATCHES` 加批次**」，
并由 `verification_policy_guard.py` **机器强制**。

→ **你的 worktree 里 `--batch gates` 会因新测试目录而报 `V-06`** —— 这是**预期的**。
**不要改 `verify.py` 去消红**（那是共享文件，三方同时改必冲突）。
**你只需在报告里写明"需主理人集成时新增批次：`tests/<你的目录>/`"**，由主理人统一加。

### 1.4 worktree 里**两处预期报红**（都不是你的 bug，别去"修"）

| 现象 | 根因 | 你要怎么做 |
|---|---|---|
| `verification_policy_guard` 报 `V-06` | 你的新测试目录未入 `verify.py::BATCHES`（见 §1.3） | **不改 `verify.py`**；报告里列出需新增的批次名 |
| `rules_lock_guard` 报"权限不为 0444" / "哈希不符" | ★ **git 不记录只读位**：`rules/` 的 `0444` 是**本地文件系统属性**，任何**全新 checkout / worktree / clone 都拿到 `0644`** | 在自己的 worktree 里跑一次本仓库既有的 `python system/scripts/ops/lock_rules.py`（它按已锁内容重算并 chmod），**之后即可**；或在报告里声明"本工作区 rules 权限为 0644，属环境预期" |

★ **第二条是本次三流共同踩到的真实基础设施约束**（`ws/graph` 与 `ws/compute` 各自独立发现）：
**纪律 9 的 `0444` 无法随版本库传播** —— 它只能靠"每个新工作区做一次 bootstrap"来落地。
主理人在集成时会统一执行；此条同时登记进 `CONVENTIONS.md`，作为**新环境 bootstrap 步骤**。

### 1.5 `--no-verify` 的**唯一**允许条件（本次两流都用到，故显式立规）

**默认仍然禁止跳过钩子。** 仅当**同时满足**下列 3 条时允许 `git commit --no-verify`：

1. **唯一红的门是 §1.4 表中的两项之一**（`V-06` 或 `rules` 权限），
   且你**已手动逐个跑过 `run_all_gates.py`**、在报告里**逐项贴出退出码**证明"没有其它红项"；
2. 你**无法**通过非禁改途径让它变绿（如 §1.4 所述，`verify.py` 是禁改文件）；
3. **在报告里显式披露**（哪一条命令、为何必须、跑了哪些替代验证）。

→ 不满足任一条件而用 `--no-verify` = **事故**：主理人会在集成复核时逐项重跑全部门禁，
并且**凡有未披露的跳过一律退回**。

---

## 2. 任务书 `ws/compute` —— 确定性计算层

| 项 | 值 |
|---|---|
| **worktree** | `/Users/gaza/Developer/InvestSigh/.worktrees/ws-compute` |
| **分支** | `ws/compute` |
| **基点提交** | `775e714` |
| **模块清单（只能改这些）** | `system/scripts/compute/**` · `system/tests/compute/**` · `system/reports/ws_compute_{dod,report}.md` |

**当前状态**：`scripts/compute/` **是空包**（只有 `__init__.py`）。它是 `施工图 §3.2` 点名的 **C 档最重自建块**，
也是阶段②④⑤ 估值/回测的**算术底座**。

**任务目标**：建成确定性计算层，落实 **`Ch9 §N9.2-03`（算术由程序层承担，模型不口算）**。

**必读锚点**：`施工图 §1.3`·`§3.2`·`§8` ｜ `开工提示词 §一`·`§5.1`·`§5.2`·`§六` ｜ **`CONVENTIONS.md`（逐字）**
｜ `Ch9 §2.3`（数值保真：`NumericClaim` / `DerivedValue` = `formula`+`operands[]`+`method_version`）·`§3.4.1`（双时间轴）·`§3.5`（④估值行）
｜ `Ch3 §D.2`（基准收益三条硬口径）｜ `Ch4` / `Ch5`（价值层与价格层算术要求）

**硬要求（摘）**：
- `DerivedValue` **复用既有定义**；**`method_version` 变更必须产生新对象，不得就地覆盖**（追加式不可变）
- **输入缺失 → 输出缺口对象，不出数值**；**不得** `None`/`0`/估算值冒充实值（`AC-05`）
- 基准三条口径**只调用** `scripts/benchmark/return_guard.py`，**不写第二套校验**（`G-06` 唯一真源）
- 禁第二条 `rules/` hash 校验路径；AST 单遍；配置走 `_common._cached_yaml()`；docstring 只写做到的事

**DoD**：`ws_compute_dod.md`，覆盖 `AC-01`~`AC-08`（模板见 `§5.1`，**≥1 错误路径 + ≥1 边界**）

**测试命令**：
```bash
export CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0
WT=/Users/gaza/Developer/InvestSigh/.worktrees/ws-compute
sh $WT/system/scripts/ops/run_pytest.sh tests/compute
/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python $WT/system/scripts/ops/verify.py --batch gates
```

---

## 3. 任务书 `ws/graph` —— 依赖图与 T12 传播

| 项 | 值 |
|---|---|
| **worktree** | `/Users/gaza/Developer/InvestSigh/.worktrees/ws-graph` |
| **分支** | `ws/graph` |
| **基点提交** | `775e714` |
| **模块清单** | `system/scripts/graph/**` · `system/tests/graph/**` · `system/reports/ws_graph_{dod,report}.md` |

**当前状态**：`scripts/graph/` **是空包**。`Ch9 §3.2.1` 已裁定其归属：**B（边表 schema）+ C（遍历/失效/入队）**。

**任务目标**：依赖图遍历 + **T12 传播** + 环检测 + 事件去重指纹 + 可重建邻接表缓存。

**必读锚点**：`施工图 §3.2` · `§8` ｜ `开工提示词 §一`/`§5.1`/`§5.2`/`§六` ｜ `CONVENTIONS.md`（逐字）
｜ **`Ch7 §C`（传导引擎 / 环检测 SCC / 累积上限 / 停止判定 7 条件）·`§C.7`（多公司传导）** ｜
**`Ch9 §3.4.7`（事件指纹：`sha256(event_type ‖ sorted(company_ids) ‖ metric ‖ period_bucket ‖ bucket(occurred_at,1d) ‖ root_source_id)`；`split`/`merge`/`event_alias` 人工纠正）** ｜ `§3.5`（③传导行）

**硬要求（摘）**：
- **`index/` 下产物皆可重建缓存、非真源**：删掉必须能从 `facts/*.jsonl` 完整重建
- **指纹基于根来源而非标题**（十篇转述 = 1 event + N 条 propagation）
- 停止判定 7 条件**逐条落地**，**不得自创阈值**；需要阈值走 `get_param()`（`纪律 1`：**参数不进决策函数**）
- 环检测用 **SCC**，**不得**指数级路径枚举；大图必须有可测上界
- **不引入图数据库**（`Ch9 §3.3.1` 明确「不用 Neo4j」）
- ★ 必须覆盖 `Ch7 §C` 的「**`capex` ≠ 订单/收入**」这类**禁跳级等同**断言

**DoD / 测试命令**：同 §2 结构（测试目录 `tests/graph/`）

---

## 4. 任务书 `ws/claim` —— 定位校验器 + 五态状态机

| 项 | 值 |
|---|---|
| **worktree** | `/Users/gaza/Developer/InvestSigh/.worktrees/ws-claim` |
| **分支** | `ws/claim` |
| **基点提交** | `775e714` |
| **模块清单** | `system/scripts/validators/**` · `system/scripts/claim/**` · `system/tests/validators/**` · `system/tests/claim/**` · `system/reports/ws_claim_{dod,report}.md` |

**当前状态**：`scripts/validators/` 与 `scripts/claim/` **都是空包**。
另注：批次 5b 刚修好 claim 的**五类时间与 `locator`**（此前真实运行写出的 claim 时间全为 `None`）——
所以**定位校验器现在有真实、合规的输入可测**。

**任务目标**（两个互相独立的小模块）：
- **A. `scripts/validators/locator_check.py`** —— `full_text_read` 定位校验器。`Ch6 §D` 的关键：**「程序拦截，非模型自觉」**：
  校验器要能**机械证明**"这条主张真的被读到过全文"，而不是"模型说它读了"
- **B. `scripts/claim/transition.py`** —— **五态状态机 + `superseded` 传播**（`Ch6 §E`）

**必读锚点**：`施工图 §3.2` · `§8` ｜ `开工提示词 §一`/`§5.1`/`§5.2`/`§六` ｜ `CONVENTIONS.md`（逐字）
｜ **`Ch6 §D`（`full_text_read` 校验器 / 采集编排 / 降级）·`§E`（五态状态机 + `superseded` 传播）**
｜ `Ch9 §3.4.6`（**R-17：`claim_nature`/`claim_form`/`official_claim_kind` 三字段维度不同，不得互换、不得合并**）·`§2.2`（五类时间）·`§3.5`（②核验行；幂等键 = (`source_id`, `quote_hash`)）
｜ `Ch2`（`claim_nature` 取值与强制）

**硬要求（摘）**：
- **非法迁移必须响亮拒绝**（`exit 1` / 抛错），**不得**静默兜底或自动纠正
- **`full_text_read` 不得被"模型自称"代替** —— 必须给**机械判据**（`R-06` 可判定）
- 三字段**不得互换、不得合并**（R-17）
- **不得改 `scripts/guard/**`**（批次 4 已审计通过）；不得引入第二条 hash 校验路径

**DoD / 测试命令**：同 §2 结构（测试目录 `tests/validators/` + `tests/claim/`，各模块各 ≥1 错误路径 + ≥1 边界）

---

## 5. 集成计划（**只有主理人做**）

| 步 | 动作 | 备注 |
|---|---|---|
| **I-1** | 等三流各自回传**报告 + 真实测试输出 + AC 判定** | 报告不到齐不集成 |
| **I-2** | **主理人逐条独立复核**（不采信声明）：在**一个临时集成 worktree** 上 `git merge --no-ff ws/<name>`，跑该流测试 + `gates` | 冲突**不硬解**：若发生冲突，说明**接口/文件集划分有问题**，先查根因 |
| **I-3** | 统一加批次：`verify.py::BATCHES` + `ORDER` 增 `tests/compute` / `tests/graph` / `tests/validators` / `tests/claim`（并同步 `gates` 的计数文案） | 这是**共享文件唯一改动点**，由主理人一次做完 |
| **I-4** | 跑**全部分批**（7→11 批）确认无回归 | 禁止一条命令全量验证 |
| **I-5** | 提交到 `main`；更新 `PROGRESS.md` 与缺口登记 | — |

**冲突预案**：三流文件集**互斥**（`scripts/{compute,graph,validators,claim}/**` + 各自 `tests/`），
唯二共享点是 `verify.py`（I-3 统一处理，三流都**不许**动）与 `CONVENTIONS.md`（只读）。
**因此理论上不应出现冲突** —— 一旦出现，就是**划分被破坏**的信号，需查根因而不是解冲突。

---

## 6. 本任务书下发时的状态快照

| 项 | 值 |
|---|---|
| 已入库提交 | `775e714`（批次 5/5b/5c 全部收口） |
| 阶段 | ① `prep` 判据 PASS·不宣告完成（`G-13` 已由 step 1 接线**实质闭合**，待正式复核）；②–⑤ 仍 BLOCKED |
| 测试 | `injection` 119 passed · `guards` 56 passed · `unit` 42 · `conflict` 6 · `root` 8 = **231 passed** |
| 门禁 | **20 项**全绿（分批验证，各自独立超时） |
| 已闭合的审计发现 | 两轮共 `D-2`~`D-7` / `A-1` / `A-2` / `A-5` / `A-6` / `A-13`（`A-3` 经主理人探针裁决：**能力白名单已拦下 4 种绕过**） |
| 仍开放 | `A-4`（已由 QA 补测）· `A-8`（`G-07` 需机器断言）· `A-9`/`A-10`/`A-11`/`A-12`（文档与裁定）· **`T-08` 待需求方裁定** · `p01`/`p03` 未冻结 |
