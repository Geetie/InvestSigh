# 未实现项汇总与实现 / 补强计划（2026-09-17 冷启动端到端实测后）

> **依据**：`system/reports/cold_start_e2e_2026-09-17.md`（运行记录）+ 本文件作者**独立复核**的读数。
> 复核方式与实测命令见 §8。★ 标 **[独立发现]** 的是运行记录**未指出**、由本次复核新发现的项。

---

## 0. 本次运行的实况（一句话）

**真源从全空推到 395 行 / 20 张表，三个阅读入口全部产出，原 4 条阶段阻塞全部消失；
同时把系统里两处真正的缺陷暴露成 2 条红门禁。**

| 项 | 起点 | 终点 |
|---|---|---|
| `facts/*.jsonl` | 22 张表 **全 0 行** | **395 行 / 20 张表**（`dependency_edges`、`implied_requirements` 仍 0） |
| `system/raw/` | 空 | **15 份原文 + 1 份行情清单** |
| `system/views/` | 空 | **3 份入口 JSON + 1 份 dashboard.html** |
| `system/derived/` | 空 | `derived_values` **6 行** · `compute_gaps` **0 行** |
| `run_all_gates` | 非零 0 | **非零 2**（两条都是**真缺陷**，见 §2.1） |
| `stage_gate --stage all` | **FAIL(4)** | **FAIL(2)**；原 4 条 `G11-04` **逐条消失** |
| 生产代码改动 | — | 4 个文件 **+70 / −7**（`compute/driver.py` · `decision/run_decide.py` · `evidence/independence.py` · `ingest/market_data.py`） |

阶段门：`prep PASS` · **`nvidia_sample BLOCKED`** · `core_chain PASS` · `daily_run PASS` · `expansion PASS`。
专项守卫：`locator_check` **PASS(0)** · `quote_provenance_guard` **PASS(0)** · `neutrality_check` **PASS(0)**。

---

## 1. ★ 先分清三类"没做"（否则计划会写歪）

| 类 | 定义 | 判定依据 | 本文归属 |
|---|---|---|---|
| **A 设计上不做** | 文档**逐字**写"首版不实现 / 只留接口" | `unimplemented_by_design_inventory.md` | §5（**不是缺陷，不该排期**） |
| **B 未实现但必需** | 设计要求，但**代码里没有生产实现**（无写入方 / 无调用方） | 全仓扫消费方 | **§2（要排期）** |
| **C 数据 / 口径缺口** | 机制在位，但**输入缺**或**参数 pending** | 真源 0 行 / 字段 `tbd` | **§3（要拍板或补数）** |

★ 本次运行把 B 与 C **暴露得很清楚**：那 2 条红门禁全部落在 B；而 `nvidia_sample BLOCKED` 落在 C。

---

## 2. ★ 未实现项全清单（B 类，按"卡住什么"排序）

### 2.1 P0 —— 当前 2 条红门禁的直接原因（都是**同一个缺陷**的两个面）

**B-1 决策路径把"已实现收益"当"预期收益"用**

| 项 | 内容 |
|---|---|
| 现象 | 无变化日产了新信号：`run_date=2026-09-17 signals_emitted=1`（`G1-02①`）；该建议的四要素缺 `computation`（`G1-03`） |
| 精确位置 | `scripts/decision/run_decide.py::_run_core` |
| 根因 | ① 把 `_total_return(窗口内已实现收益)` 包成 `ExplainableForecast` 送进前置门 ⇒ 门通过 ⇒ 出 `buy`（违反 `P-08`"不得用 `past_return` 做收益预测"），且 `falsifiers` 为空；② `subject` 用 `company_id`（无窗口）⇒ `derived_id` 与计算层命名口径**不是同一个 id**，且**从不落 `derived/`** ⇒ 建议声明的 `evidence_version_ids` 指向**从未存在**的底稿 |
| 本次已做 | 会话内补足：`subject` 与计算层同口径 + 落建议前经唯一写入口落两份 `DerivedValue`（对**新**产出生效） |
| **仍缺** | ★ **该函数本身仍能在"无预测输入"时产出 `buy`** —— 现在靠"会话事后 `supersedes` 覆盖"兜住。**这是补丁，不是修复** |
| 补法 | 在 `_run_core` 里加**前置门**：`forecast` 的来源必须不是已实现收益（`basis` 不得含 `past_return`/`trailing_return`），否则**输出 `pending` + 缺口**，不出 `buy`；并补 `falsifiers` 必填校验（空即不许 `buy`） |
| 验收 | ① 该路径在缺预测输入时**不可能**产出 `buy`（注入测试：喂已实现收益 ⇒ 必须得 `pending`）② `falsifiers` 为空的 `buy` 被拒 ③ `rec-sec-nvda-2026-08-03` 那条旧行**不删**（保留失败记录），但**新**产出不得再犯 |

**B-2 `dependency_edges` 零生产写入方**

| 项 | 内容 |
|---|---|
| 现象 | `facts/dependency_edges.jsonl` **0 行**（本次仍是） |
| 影响 | `T12`（原文被撤回 → 追依赖触发复查）在真实数据上**无对象可追**；`graph/closure.py` 的依赖闭包只能靠测试夹具 |
| 补法 | 在写建议 / 写基线 / 写主张时**同时写边**（`claim → baseline`、`baseline → recommendation`、`recommendation → supersedes`）。★ 边界已由测试证明可用（`test_core_chain_acceptance` 的 47 例），缺的是**生产写入点** |
| 验收 | 跑一次端到端后 `dependency_edges` **非 0**，且 `reverse_closure(rec)` 能回到其依赖的 claim |

### 2.2 P1 —— 让"研究链路"可复现

**B-3 ★★ 落库靠会话内临时脚本（最该修的一条）** **[独立发现：报告 §7 提到但未登记为缺口]**

| 项 | 内容 |
|---|---|
| 现象 | 本次 395 行的落库，靠 `.workbuddy/seed/` 下 **7 个脚本约 200 KB**（`seed_sources_claims.py` / `seed_research_structure.py` / `seed_entities.py` / `seed_fundamentals.py` / `seed_repair_and_finish.py` / `build_views.py` / `build_readable_views.py`） |
| 问题 | `.workbuddy/` 在 `.gitignore` 里 ⇒ **这些脚本不在版本库** ⇒ 整条落库路径**不可重跑、不可审、不可测**。这与 `gap-mcp-fetch-not-reproducible` **同族**，且规模更大（这次是**全链路的模型侧产出**） |
| 补法 | 分两步：① **把可确定的部分**（字段映射、五类时间、`recorded_seq` 分配、幂等、`views` 构建）固化成 `scripts/ingest/research_ingest.py` + `scripts/views/build.py`，配测试；② **不可确定的部分**（研究结论本身）改为"**清单 + 编译**"模式（与 `market_data.py` 同构：会话产出 JSON 清单 → 版本库代码校验并落库） |
| 验收 | 清空真源后，**只用版本库里的命令**能重跑出"空 → 非 0"，且 `views` 三份可重建 |

**B-4 模型侧四个环节无生产实现（设计如此，但现在是"靠人"）**

| 环节 | 位置（模块 docstring 已声明归属） | 现状 |
|---|---|---|
| step 2 七步判定 | `orchestrate/chain_steps.py` | 记 `gap` + `blocked` ⇒ **设计行为**，但本轮由会话 Agent 代做 |
| step 3 关系抽取 | 同上 | 同上 |
| step 4 增长 / 护城河判断 | 同上 | 同上 |
| step 6 基准选取与价格抓取 | 同上 | 同上 |

★ 这不是缺陷（`T-08` A 方案已裁定），但**缺一条"把会话产出登记进受控通路"的机制** —— 这正是 B-3 的修法要解决的事。两者应**一并做**。

### 2.3 P2 —— 判据口径分歧（需裁定，不是实现问题）

**B-5 `quote_provenance_guard` / `ASKTRACE` 扫全行 vs 其余守卫取最新版本**

- 现象：这两个守卫扫**全部** `claims.jsonl` / `tasks.jsonl` 行，而其余守卫按 `recorded_seq` 取最新版本
  ⇒ 追加版本后，**旧行带着已被修正的值** ⇒ 恒红
- 本次处置：把本会话产出的两个文件**收敛为每业务键最新版本**（这些行是本会话内产生、`HEAD` 为 0 行）
- **需裁定**：守卫应当"扫全行"还是"只看最新版本"？（`Ch9 §3.4.2` 追加式真源的语义倾向于后者，
  但"扫全行"对历史审计更严格）★ 两个守卫之间也必须**同口径**

**B-6 同日重跑口径不一致**（本轮复现确认）

- `no_signal_day.py` 按 `run_date` **去重**（`effective` 判 FATAL、`superseded` 只打具名 note）
- `stage_gate::degrade_keeps_last_valid` **不去重** ⇒ 每多跑一次多一条
- 已在 2026-09-17 的补强中把 `stage_gate` 的**前提谓词**改为与写路径同口径，缓解了假红，
  但"同日重跑是否算多次运行"这一层**仍未统一**
- **需裁定**：统一到 `_latest_per_run_date` 语义

**B-7 [独立发现] 三个入口渲染的是已被 `supersedes` 的旧建议**

| 项 | 内容 |
|---|---|
| 现象 | `recommendations.jsonl` 里 `rec-sec-nvda-2026-08-03-session-review`（`action=pending`）**已 `supersedes`** 旧的那条；但 `views/company_pages.json` 与 `views/daily_page_*.json` 的 `current_recommendation` / `recommendation_changes` 渲染的**仍是旧的 `buy`** |
| 后果 | 阅读入口会把**已被评审推翻的建议**当作"当前建议"展示 —— 与 `§八`"结论简洁、变化可见"的要求相悖 |
| 根因 | `views` 构建器取"该公司的建议行"时**没有沿 `supersedes` 链取末节点** |
| 补法 | 构建 `views` 时按 `supersedes` 链**取末节点**（无人再 supersede 的那条）作为 `current_recommendation` |
| 验收 | 注入：造 A→B supersede 链 ⇒ 入口必须渲染 B；且 A 仍在"历史版本"区可见 |

**B-8 [独立发现] 本次 4 处代码改动零新增测试**

- `compute/driver.py` · `decision/run_decide.py` · `evidence/independence.py` · `ingest/market_data.py` 四处共 +70 行，**新增测试 0 条**
- 其中 `evidence/independence.py::claim_group_fingerprint` 连**既有测试引用都没有**（全仓 grep 为空）
- 更关键：`independence.py` 的 `_carried()` 回落改变了**独立证据计数**（修前同源 18 条被算成 18 份独立佐证），
  这是**影响结论强度**的核心口径 —— **必须有测试钉住**
- 补法：四处各配区分性测试（尤其 `_carried` 的"顶层优先、回落 `impact_capability`"两臂）

---

## 3. ★ 数据 / 口径缺口（C 类：机制在、输入缺）

| # | 缺口 | 现值 | 卡住什么 | 处置 |
|---|---|---|---|---|
| C-1 | `rules/freeze.yaml::p05.algorithm` | `tbd` | 反向估值 / 价格隐含要求**整条做不了**（`implied_requirements` 0 行） | **需求方拍板** |
| C-2 | `rules/freeze.yaml::p10.caliber_terms` 四键 | `tbd` | 复盘收益停在 `blocked_by_caliber`，**不出数字** | **需求方拍板** |
| C-3 | `rules/scenario.yaml::scenario_method_status` | `pending` | ★ **`nvidia_sample BLOCKED` 的直接原因**：相对判断被**设计性阻塞** | **需求方拍板**（这是"跑通"的最后一道设计门） |
| C-4 | `rules/freeze.yaml::p07`（时刻 / 时区 / 非交易日） | `tbd` | 每日运行靠 WorkBuddy 定时 | 拍板（`00_交付施工图 §1.3` 已把它划给宿主） |
| C-5 | `facts/expectations.jsonl` | 4 条**全是** `company_guidance`；**券商样本 0 份** | 无法与外部预期对照；只能叫"公开预测样本" | 接券商公开预测源（或接受现状并如实标注） |
| C-6 | 上游具名供应商 | 10-Q 取得副本在 Item 1A 前**被截断** | 供应商关系无法成立 | 重取完整 10-Q（`fetch_manifest` 加一条） |
| C-7 | X / YouTube / Substack | 本次**未取到**可抓正文 | 二三手来源缺 | 保留任务（设计允许"显示尚未完成解析"） |
| C-8 | 44 节点中 38 个 | 仅"位置收录" | 传导 / 覆盖面 | ★ **研究进度，不是缺陷**；入口已显式渲染为"尚未研究" |

---

## 4. 实现计划（四批，每批独立可验收）

### 批次 I —— 把"决策路径不得用已实现收益出 buy"钉死（P0）

| 步 | 动作 | 文件 | 验收 |
|---|---|---|---|
| 1 | 加前置门：`forecast.basis` 含 `past_return`/`trailing_return` ⇒ **不出 `buy`**，输出 `pending` + 缺口 | `decision/run_decide.py` | 注入测试：喂已实现收益 ⇒ 必得 `pending` |
| 2 | `falsifiers` 为空的建议**不得**为 `buy` | 同上（或 `schema` 层校验） | 注入：`falsifiers=[]` + `buy` ⇒ 拒 |
| 3 | 补 `B-3` 的底稿落库测试（`subject` 口径 + `evidence_version_ids` 可解析） | `tests/decision/` | `traceback._find_derived` 对新产出**非 None** |
| 4 | 修 `B-2`：写建议 / 基线 / 主张时同时写 `dependency_edges` | `decision/` · `compute/` | 端到端后 `dependency_edges` 非 0，`reverse_closure` 可达 |

**批次 I 完成的标志**：`run_all_gates` **非零降至 0**（那两条红消失），而**旧失败记录仍在库**。

### 批次 II —— 把落库路径搬进版本库（P1，可复现性）

| 步 | 动作 | 验收 |
|---|---|---|
| 1 | 定义"研究清单"JSON 契约（sources / claims / entities / fundamentals / views 五段），与 `market_data.py` 同构 | 契约进 `market_data.py` 同族模块 + docstring |
| 2 | 写 `scripts/ingest/research_ingest.py`（校验 → 五类时间 → 幂等 → `append_records`），含 4 处取数/落库校验 | 清空后**只用版本库命令**重跑出非 0 |
| 3 | 写 `scripts/views/build_views.py`（含 B-7 的 `supersedes` 链取末节点） | 三份入口可重建；A→B 链渲染 B |
| 4 | 把 `.workbuddy/seed/*.py` 的**可确定部分**并入上述两模块，其余归档到 `system/reports/` 作历史记录 | 版本库里能重跑 |

### 批次 III —— 判据口径收敛（P2，需先裁定）

| 步 | 动作 | 前置 |
|---|---|---|
| 1 | 裁定 B-5（扫全行 vs 取最新）并统一 `quote_provenance_guard` / `ASKTRACE` | **需求方 / 设计侧裁定** |
| 2 | 裁定 B-6（同日重跑口径）并把 `stage_gate` 与 `no_signal_day` 统一到 `_latest_per_run_date` | 同上 |
| 3 | 补 `B-8`：四处会话内代码改动的测试 | 无 |

### 批次 IV —— 能力补齐（C 类，需拍板后启动）

- C-1 / C-2 / C-3 / C-4 拍板 ⇒ 解锁反向估值、复盘数字、**`nvidia_sample` 阶段**、定时调度
- C-5 接券商公开预测源（或用 WebSearch/WebFetch 人工补样本）
- C-6 重取完整 10-Q（`fetch_manifest.py` 加规格）
- C-8 按"可核实的关系"逐节点推进（**不按数量凑**）

---

## 5. 补强计划（防再踩坑 —— 与实现计划分开）

| # | 补强 | 为什么 | 落点 |
|---|---|---|---|
| S-1 | **"不得用已实现收益做预测"从文档变成机器守卫** | `P-08` 现在只是文档；本次就是靠人发现的 | 新守卫或并入 `scenario_tag_binding_guard` 同族 |
| S-2 | **`append_only_guard` 补"测试环境重置"通路** | 本次清空真源只能靠 `--no-verify` 豁免（已登记 `gap-no-test-env-reset-channel`）。建议要求提交信息含标记 + 附恢复点 SHA | `checks/append_only_guard.py` |
| S-3 | **落库脚本必须进版本库** | 见 B-3；`gap-mcp-fetch-not-reproducible` 的**扩大版** | 批次 II |
| S-4 | **入口产物与 `supersedes` 链绑定** | 见 B-7：现在会把被推翻的建议当"当前建议" | `views` 构建器 + 守卫 |
| S-5 | **给"会话内产出"一条受控通路** | `gap-session-revision-no-channel` + 本次"会话内代做模型侧" ⇒ 同一根因 | 批次 II 的清单模式 |
| S-6 | **失败记录保留的机器绑定** | 现在靠"人不去删"。建议：守卫禁止 `recommendations` 行被删除或 `status` 被就地改写 | `checks/append_only_guard.py` 扩项 |

---

## 6. 需要裁定的 6 件事（按阻塞强度）

| # | 事项 | 阻塞什么 | 选项 |
|---|---|---|---|
| 1 | `scenario_method_status`（C-3） | ★ **`nvidia_sample` 阶段 PASS**（= "跑通"的最后一道设计门） | ① 定方法并冻结 ② 明确接受该阶段长期 BLOCKED ③ 移出通过条件（`T-15` 已裁定"不得把退出物升格为判据"） |
| 2 | `p05.algorithm`（C-1） | 反向估值 / 价格区间 | 给方法（WACC 口径 + 高增长年数 + ROIIC 来源） |
| 3 | `p10.caliber_terms` 四键（C-2） | 复盘出数字 | 给信号生效价 / 交易成本 / 税前口径 / 观察窗口 |
| 4 | B-5 守卫扫全行 vs 取最新 | 两个守卫的长期稳定性 | 二选一并统一 |
| 5 | B-6 同日重跑口径 | `stage_gate` 与 `no_signal_day` 的一致性 | 统一到"每个 run_date 只看最新" |
| 6 | `supersedes` 的版本链写法（**[独立发现]**） | 版本链语义 | 现状：新 id + `supersedes` + `recorded_seq=1`（**未递增**、`prev_version_id=None`）。与 `Ch9 §3.4.2`"同业务键追加版本 + `recorded_seq` 递增"**不一致** ⇒ 裁定是"新建议 vs 版本"还是"同键新版本" |

---

## 7. 我的独立复核结论（与运行记录的差异）

| # | 运行记录说 | 复核实际 | 性质 |
|---|---|---|---|
| 1 | `views/` 产出 3 份 JSON | **确实是 3 份 + 1 份 dashboard.html** | ✓ 一致（我首轮 `head` 截断，已更正） |
| 2 | "已以 `supersedes` 覆盖为 `pending`" | 库里**确有**该 `pending` 行 ✓ | ✓ 一致 |
| 3 | — | **[独立发现]** 但三个入口渲染的 `current_recommendation` **仍是旧的 `buy`** | ★ **新缺陷 B-7** |
| 4 | — | **[独立发现]** 本次 4 处代码改动**零新增测试**，其中 `claim_group_fingerprint` 连既有引用都没有 | ★ **新缺口 B-8** |
| 5 | §7 提到落库脚本在 `.workbuddy/seed/` | 确实存在（7 个约 200 KB），但**未登记为缺口** | ★ **补登为 B-3** |
| 6 | `run_all_gates` 非零 2 / `stage_gate` FAIL(2) | **完全复现**（含两条 FATAL 逐字） | ✓ |
| 7 | 三条专项守卫 PASS | **完全复现** | ✓ |
| 8 | facts 395 行 / 20 张表、2 张空表 | **完全复现**（空表 = `dependency_edges` + `implied_requirements`） | ✓ |

★ 运行记录**最值得肯定**的一点：它**没有**为了刷绿而改写失败记录或手写 `check_record`
（`R-04` 守住了），并把 6 条"靠 Agent 补足"的部分**逐条登记**（含精确位置与修法）。
★ **最该警惕**的一点：那 6 条补足**全部发生在生产代码里，且零测试** —— 它们现在和既有代码**无法区分**，
下次改同一处时没人知道为什么那样写。

---

## 8. 复核命令

```bash
V=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python
export CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0

$V system/scripts/ops/run_all_gates.py --timeout 30            # 非零 2
$V system/scripts/delivery/stage_gate.py system --stage all     # FAIL(2)
$V system/scripts/validators/locator_check.py system            # PASS(0)
$V system/scripts/checks/quote_provenance_guard.py system        # PASS(0)
$V system/scripts/views/neutrality_check.py system              # PASS(0)

# 真源与入口
$V -c "import json,pathlib;[print(p.name, sum(1 for l in p.read_text(encoding='utf-8').splitlines() if l.strip())) for p in sorted(pathlib.Path('system/facts').glob('*.jsonl'))]"
$V -c "import json;d=json.load(open('system/views/company_pages.json',encoding='utf-8'));print(d['companies'][0]['current_recommendation'])"
```
