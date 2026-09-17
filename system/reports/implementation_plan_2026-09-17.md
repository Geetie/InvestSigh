# 未实现项汇总与实现 / 补强计划（v2 · 2026-09-17 冷启动端到端实测后）

> **v2 修订说明**：v1 **只读了**运行记录 + `views/` 的 JSON 结构，**漏读了 4 份人读产物**
> （人话版报告 + 三个阅读入口 MD）。补读后：**新增 7 项 v1 漏掉的未实现项**（§2.4）、
> **更正 1 项错误结论**（§7.3），并把 T01–T14 的实测状态纳入（§4）。
> **本版依据**：`cold_start_e2e_2026-09-17.md`（运行记录）· `AI产业链研究报告_人话版_2026-09-17.md`
> · `阅读入口_1_产业图谱.md` · `阅读入口_2_公司研究页.md` · `阅读入口_3_每日研究页_2026-09-17.md`
> + 本文件作者的**独立复核**（读数与命令见 §9）。

> **配套文档**：`batch2_internalization_2026-09-17.md`（批次 II 收口报告）

---

## 0.0 ★ 执行进度（2026-09-17 当日更新）

| 批次 | 状态 | 证据 |
|---|---|---|
| **I**（P0：P-08 运行时门 + 假红） | **已执行（3/4 步）** | `run_all_gates` 非零 **2 → 0**；`no_signal_day`/`traceback` 双双转绿，**两条历史失败记录都还在库**（一条成 superseded 修订、一条被具名报出） |
| — §2.1 `B-1` | ✅ | `rules.decide()` 新增 **P-08 门**（R4 后 / R2 前）+ `build_recommendation` 的 `FalsifiersMissing`。★ 连带发现：测试夹具 `make_forecast` 的缺省驱动**就是**被禁形态 ⇒ 17 条用例同时变红，**那恰是"该缺陷从未被任何判据覆盖过"的证据** |
| — §2.1 `B-2`（`dependency_edges`） | ⏳ **未做** | 原排期在批次 I 第 4 步 |
| — §5 批次 I 附带 | ✅ 额外修掉 | ① `step.py` 恒回传 `judgment_change={}`（回执撒谎 ⇒ `G1-02①` 对合法买入日**假红**）② `traceback` 按 `recommendation_id` 去重 → 改按**业务键**（与 `rules.recommendation_business_key` 唯一真源） |
| **II**（P1：落库路径进版本库） | **已执行（机制全部内化）** | ① `scripts/ingest/research_ingest.py` + `raw/inbox/research_manifest_2026-09-17.json`（**往返等价实测通过**：17 表 / 188 行逐一重建）；② `scripts/views/build.py` + `render.py`（**三份入口的构建与渲染**，见 `batch3_views_internalization_2026-09-17.md`）；`unit` 268 passed |
| — §2.2 `B-3`（落库脚本） | ✅ 机制部分 | 见上。★ 内化过程中抓到 **3 个真缺陷**（`quote_hash` 契约写错 / `period_bucket` 年份季度互换 / 幂等键丢版本），逐条见 §0.0 下方与收口报告 |
| — §2.2 `B-4` / `S-5`（会话产出受控通路） | ✅ | 投递口第三类投递物 `research_manifest_*` + STEP 1 **按文件名分派** |
| — §7.3 `B-7`（入口与 `supersedes` 链） | ✅ **已修** | 根因精确化：原按 `recorded_seq` 比大小，而真实数据 **5 行该值全为 1** ⇒ `>` 从不成立 ⇒ 取到文件第一条（NVIDIA = 被推翻的 v1 `buy`）。改为 `rules.current_recommendation_row()`（`supersedes` 链末节点）；**同一实现也迁到 `decision/rules.py` 供 `traceback`/`review_return` 复用**（原先三处各一份） |
| — §6 `S-4`（`views` 构建/渲染内化） | ✅ **已做** | `build_views.py` / `build_readable_views.py`（3063 行会话脚本的 views 部分）→ `scripts/views/build.py` + `render.py`；★ 元断言钉死"叙事不得写回代码"（见收口报告 §三） |
| **III**（`B-9` 提问入口 / `B-10` 事件触发） | ⏳ 未开始 | 源稿点名的两条 ❌ |
| **IV / V** | ⏳ 未开始 | 需先拍板（§8 的 7 件） |

**新登记缺口（本次实测新增，均未自裁修改）**：

| id | 内容 | 性质 |
|---|---|---|
| `gap-claim-period-bucket-swapped` | `facts/claims.jsonl` **5 行**的 `impact_capability.period_bucket` = `CY2Q2026`（应 `CY2026Q2`）。**被独立佐证指纹消费**（`Ch9 §3.4.7`）；当前组内一致故**未致错**，但潜伏 | 数据（需裁定更正版与计数口径） |
| `gap-claim-metric-session-override` | 10 行主张的 `metric` 来自会话**显式覆盖值**（`anthropic-2gw`），不由 `key` 派生 ⇒ 与机制派生约定**不统一** | 口径 |
| `gap-step6-fact-set-change-not-derived` | `run_decide._run_core` 的 `JudgmentChange(fact_set_changed=True)` **恒真、尚未由数据判定** ⇒ 每日回执恒记"判断已变" | 设计（"判断是否改变"的判定归属） |
| `gap-check-record-lacks-blocked-and-gaps` | `CheckRecord` **无** `blocked` / `gaps` 字段 ⇒ 这两个数**只能**来自运行态 `state.json`（不在版本库）。视图如实标 `null`，但"每天跑日报"若 `state.json` 丢失就看不到阻断状态 | 契约缺口（建议 `CheckRecord` 补两字段） |
| `gap-delayed-flag-all-false` | `facts/prices.jsonl` **160 行**的 `delayed` 全为 `False`，而读数实为 09-16 收盘（读于 09-17）⇒ 该二态字段表达力不足（与既有 `gap-delayed-bool-two-state` 同族，本次给出实测计数） | 契约缺口 |
| `gap-publish-hook-not-registered` | `scripts/views/` 机制已进版本库，但 `Pipeline.register_publish_hook()` **仍无生产调用方**（step 7 仍 `deferred_by_design`）；且当下**即使注册也不触发**（`run_daily` 仅在 `changed and not blocked` 时调用）⇒ **是否现在接线属裁定** | 设计边界（`R-04` 未自裁） |

---

## 0.0.1 原计划正文（以下为 2026-09-17 制定时的原文）

## 0. 运行实况（一句话）

**真源从全空推到 395 行 / 20 张表，三个阅读入口 + 人话版报告全部产出，原 4 条阶段阻塞全部消失；
同时把系统里两处真正的缺陷暴露成 2 条红门禁。**

| 项 | 起点 | 终点 |
|---|---|---|
| `facts/*.jsonl` | 22 张表 **全 0 行** | **395 行 / 20 张表**（空表仅剩 `dependency_edges`、`implied_requirements`） |
| `system/raw/` | 空 | **15 份原文 + 1 份行情清单** |
| `system/views/` | 空 | **3 份入口 JSON + `dashboard.html`** |
| `system/reports/` | — | 运行记录 · **人话版报告** · **3 份入口 MD** |
| `run_all_gates` | 非零 0 | **非零 2**（两条均为**真缺陷**） |
| `stage_gate --stage all` | **FAIL(4)** | **FAIL(2)**；★ 原 4 条 `G11-04` **逐条消失** |

阶段门：`prep`/`core_chain`/`daily_run`/`expansion` **PASS** · `nvidia_sample` **BLOCKED**。
生产代码改动 4 处（+70/−7），**零新增测试**（见 B-8）。

---

## 1. ★ 先分清三类"没做"（否则计划会写歪）

| 类 | 定义 | 判定依据 | 归属 |
|---|---|---|---|
| **A 设计上不做** | 文档**逐字**写"首版不实现 / 只留接口" | `unimplemented_by_design_inventory.md` | §3.3（**不排期**） |
| **B 未实现但必需** | 设计要求，但**代码里没有生产实现** | 全仓扫消费方 | **§2（排期）** |
| **C 数据 / 口径缺口** | 机制在位，但输入缺或参数 `tbd`/`pending` | 真源 0 行 · 字段 `tbd` | **§3（拍板或补数）** |

★ 本次 2 条红**全部落在 B**；`nvidia_sample BLOCKED` **落在 C**（一条规则 `pending`）。

---

## 2. ★ 未实现项全清单（B 类）

### 2.1 P0 —— 当前 2 条红门禁的**同一根因**

**B-1 决策路径把"已实现收益"当"预期收益"用**

| 项 | 内容 |
|---|---|
| 现象 | `G1-02①`：无变化日产了新信号 `run_date=2026-09-17 signals_emitted=1`；`G1-03`：该建议四要素缺 `computation`，反查成功率 **0.8000 < 1.0** |
| 精确位置 | `scripts/decision/run_decide.py::_run_core` |
| 根因 | ① 把 `_total_return(窗口内已实现收益)` 包成 `ExplainableForecast` 送前置门 ⇒ 门通过 ⇒ 出 `buy`（违反 `P-08`），且 `falsifiers` 为空；② `subject` 用 `company_id`（无窗口）⇒ `derived_id` 与计算层**不是同一个 id**，且**从不落 `derived/`** ⇒ 建议声明的 `evidence_version_ids` 指向**从未存在**的底稿 |
| 已做 | 会话内补足 `subject` 口径 + 落底稿（对**新**产出生效） |
| **仍缺** | ★ **该函数本身仍能在"无预测输入"时产出 `buy`** —— 现靠"会话事后 `supersedes` 覆盖"兜住。**那是补丁，不是修复** |
| 补法 | 加前置门：`forecast.basis` 含 `past_return`/`trailing_return` ⇒ **不得出 `buy`**（输出 `pending` + 缺口）；并校验"`falsifiers` 为空的建议不得为 `buy`" |
| 验收 | ① 注入测试：喂已实现收益 ⇒ 必得 `pending` ② `falsifiers=[]` + `buy` ⇒ 拒 ③ 旧行 `rec-sec-nvda-2026-08-03` **不删**（保留失败记录） |

**B-2 `dependency_edges` 零生产写入方**

`facts/dependency_edges.jsonl` **0 行** ⇒ `T12`（撤回追踪）在真实数据上无对象可追；
`graph/closure.py` 只能靠测试夹具。补法：写建议/基线/主张时**同时写边**。
验收：端到端后 `dependency_edges` 非 0，且 `reverse_closure(rec)` 可达其依赖 claim。

### 2.2 P1 —— 让"研究链路"可复现

**B-3 ★★ 落库靠会话内临时脚本（最该修的一条）**

| 项 | 内容 |
|---|---|
| 现象 | 本次 395 行靠 `.workbuddy/seed/` 下 **7 个脚本约 200 KB**（`seed_sources_claims` / `seed_research_structure` / `seed_entities` / `seed_fundamentals` / `seed_repair_and_finish` / `build_views` / `build_readable_views`） |
| 问题 | `.workbuddy/` 在 `.gitignore` 内 ⇒ **不在版本库、不可重跑、不可审、不可测**。与 `gap-mcp-fetch-not-reproducible` 同族且规模更大（这次是**全链路的模型侧产出**） |
| 补法 | ① 可确定部分（字段映射 / 五类时间 / `recorded_seq` 分配 / 幂等 / `views` 构建）固化成 `scripts/ingest/research_ingest.py` + `scripts/views/build.py`，配测试；② 不可确定部分（研究结论）改为"**清单 + 编译**"（与 `market_data.py` 同构） |
| 验收 | 清空真源后，**只用版本库里的命令**能重跑出"空 → 非 0"，且 `views` 可重建 |

**B-4 模型侧四环节无生产实现**（`orchestrate/chain_steps.py` 已声明归属）：
step 2 七步判定 · step 3 关系抽取 · step 4 增长/护城河判断 · step 6 基准选取与价格抓取。
⇒ 这是 `T-08` A 方案**已裁定**的设计行为（编排器如实记 `gap` + `blocked`），
但**缺一条"把会话产出登记进受控通路"的机制** —— 与 B-3 一并做。

### 2.3 P2 —— 判据口径分歧（需裁定，非实现问题）

- **B-5** `quote_provenance_guard` / `ASKTRACE` 扫**全部行**，其余守卫按 `recorded_seq` 取最新 ⇒ 追加版本后旧行恒红。
- **B-6** `no_signal_day` 按 `run_date` 去重，`stage_gate::degrade_keeps_last_valid` **不去重** ⇒ 每多跑一次多一条。
  （2026-09-17 已把 `stage_gate` 的**前提谓词**改为与写路径同口径，缓解假红；但"同日重跑算几次"仍未统一。）

### 2.4 ★ v1 漏掉的未实现项（**补读 4 份人读产物后新增**）

| # | 未实现项 | 出处（逐字） | 卡住什么 |
|---|---|---|---|
| **B-9** | **提问入口未建（T14 ❌）** | 人话版 §一「提问必须成为真研究任务 ❌ 未实现（`ASKTRACE-WRITEBACK` 守卫已在，但**提问入口未建**）」；§九 G8 | 源稿 §八「从公司/产品/关系提问 → 真研究任务 + 可追溯回写」**整条体验缺失** |
| **B-10** | **事件触发规则未实现** | 人话版 §一「事件触发规则未实现（属阶段④）」；§九 G6 | 只有日度更新，**没有事件驱动**（源稿 §八 明确要求"重大事件触发额外研究"） |
| **B-11** | **事件四时间戳只落了 2 个** | 人话版 §一「发现时间与完成时间在库；**入队/发布时间未实现**」 | 源稿 §八「事件发现时间、入队时间、研究完成时间和发布结果时间**分别记录**」不完整 |
| **B-12** | **主张七步处理的第 4–6 步无实现** | 人话版 §一「前 3 步 + 状态机 ✅；**第 4–6 步（判质量 / 判增量 / 优先核验排序）属模型侧未实现**」 | 源稿 §六 的"判证据质量 / 判研究增量 / 优先核验"没有生产实现 |
| **B-13** | **`rules/valuation-methods.yaml` 未对 hardware 给出已冻结方法** | 公司研究页 §五 逐字「估值方法：**tbd**（`rules/valuation-methods.yaml` 路由未对 hardware 给出已冻结方法）」 | 除折现参数外，**估值方法的选取本身也 pending** ⇒ 六项底稿的第 ⑤ 项不可完成 |
| **B-14** | **强制复查阈值未参数化（T08 部分）** | 人话版 §八 T08「记录与归因分离（结论=无法解释）；**强制复查阈值未参数化**」 | 源稿 §二「价格下跌先触发强制复查」的**触发条件**没有可配置参数 |
| **B-15** | **公司行动表未落（T11 部分）** | 人话版 §八 T11「延迟标注✅；**公司行动表本轮 0 行**（窗口内无事件），靠后复权口径承担」 | 分红/拆股事件表为空 ⇒ 收益计算的"公司行动"环节**未被真数据验证过** |

★ **B-9 / B-10 是源稿点名、本次实测唯一两条 ❌**，优先级应高于其编号所示（见 §5 批次 III）。

---

## 3. ★ 数据 / 口径缺口（C 类）

| # | 缺口 | 现值 | 卡住什么 | 处置 |
|---|---|---|---|---|
| C-1 | `freeze.yaml::p05.algorithm` | `tbd` | 反向估值 / 价格隐含**整条做不了**（`implied_requirements` 0 行） | **需求方拍板** |
| C-2 | `freeze.yaml::p10.caliber_terms` 四键 | `tbd` | 复盘收益停在 `blocked_by_caliber`，**不出数字** | **拍板** |
| C-3 | `scenario.yaml::scenario_method_status` | `pending` | ★ **`nvidia_sample BLOCKED` 的直接原因**；人话版称之为「当前**唯一的总闸门**」 | **拍板** |
| C-4 | `freeze.yaml::p07`（时刻/时区/非交易日） | `tbd` | 每日运行靠 WorkBuddy 定时 | 拍板（施工图 §1.3 已划给宿主） |
| C-5 | `expectations` | 4 条**全是** `company_guidance`；**券商样本 0 份** | 无法与外部预期对照 | 接券商公开预测源（见 §5 批次 IV） |
| C-6 | 上游具名供应商 | 10-Q 取得副本在 **Item 1A 前被截断** | 供应商关系无法成立 | 重取完整 10-Q（`fetch_manifest` 加规格） |
| C-7 | X / YouTube / Substack | 未取到可抓正文 | 二三手来源缺 | 保留任务（设计允许"显示尚未完成解析"） |
| C-8 | 44 节点中 38 个 | 仅"位置收录" | 传导 / 覆盖面 | ★ **研究进度，不是缺陷**；入口已显式渲染"尚未研究" |
| C-9 | 行情窗口 | 仅 **32 个交易日** | 已实现相对收益的说服力 | 延长窗口（人话版 §十.3） |

---

## 4. T01–T14 实测状态（本次纳入计划；源：人话版 §八 逐条）

| 状态 | 编号 | 说明 |
|---|---|---|
| ✅ **通过（7）** | T01 T02 T03 T04 T05 T09 T10 T13 | 其中 T01 的证据最强：缺陷修复前同源 18 条不同指标被算成 18 份独立佐证，修后各 = 1 |
| ⚠️ **部分 / 未触发（4）** | T06 T07 T08 T11 | T06/T07「不是没做，是本轮**确实没有触发条件**」（无一家完成模型到能出买入）；T08 见 B-14；T11 见 B-15 |
| ❌ **未实现（3）** | **T14**（B-9）· T12（依赖边 0 行，B-2）· T08 的"强制"部分 | |

★ 计划里应把 **T14 与 T12** 当成"必须有可验收产出"的项（不是"未触发所以不用做"）。

---

## 5. 实现计划（五批）

### 批次 I —— 把"不得用已实现收益出 buy"钉死（P0）

| 步 | 动作 | 验收 |
|---|---|---|
| 1 | 前置门：`forecast.basis` 含 `past_return`/`trailing_return` ⇒ 不出 `buy` | 注入测试：喂已实现收益 ⇒ 必得 `pending` |
| 2 | `falsifiers` 为空 ⇒ 不得为 `buy` | 注入：`[]` + `buy` ⇒ 拒 |
| 3 | 补底稿落库测试（`subject` 口径 + `evidence_version_ids` 可解析） | `traceback._find_derived` 对**新**产出非 `None` |
| 4 | 修 B-2：写建议/基线/主张时同时写 `dependency_edges` | 端到端后非 0；`reverse_closure` 可达 |

**标志**：`run_all_gates` 非零 **→ 0**，而旧失败记录仍在库。

### 批次 II —— 把落库路径搬进版本库（P1）

同 §2.2 的 B-3/B-4：定义"研究清单"JSON 契约 → 写 `scripts/ingest/research_ingest.py` +
`scripts/views/build_views.py`（含 B-7 修法）→ 把 `.workbuddy/seed/*.py` 可确定部分并入。
**验收**：清空后**只用版本库命令**重跑出非 0。

### 批次 III —— 补源稿两条 ❌（B-9 / B-10）

| 步 | 动作 | 验收 |
|---|---|---|
| 1 | **提问入口**：从公司/产品/关系提问 ⇒ 跑与自动监测**相同**的研究流程 ⇒ 产出任务 + 答案 + 证据 + 更新；状态机（排队/研究中/待补证/已完成/失败）可见 | 提一个真问题 ⇒ `tasks` 多一行 + `ASKTRACE-WRITEBACK` 有产出（不再空转） |
| 2 | **事件触发规则**：财报/指引、重要订单与产能、产品与竞争变化、关键证据撤回、异常价格变化 ⇒ 触发额外研究；触发标准 = 研究优先级规则（**不是**止损、**不是**最低超额门槛） | 注入一个"财报"事件 ⇒ 产生研究任务而非直接改判断 |
| 3 | 补 **B-11** 的入队/发布两个时间戳 | 事件行四时间戳齐全 |

### 批次 IV —— 能力补齐（需拍板后启动，顺序照人话版 §十的性价比）

1. **先冻折现参数**（C-1 + **B-13 估值方法**）—— 人话版称之为「**唯一的总闸门**」
2. **把 10-Q 风险因素章节完整取回**（C-6）⇒ 上游供应商从 0 变可核验，且证据是**一手**
3. **延长行情窗口**（C-9，现 32 交易日）
4. **补券商公开预测样本**（C-5）
5. **B-14 参数化强制复查阈值** + **B-15 落公司行动表**
6. C-8 按可核实关系逐节点推进（**不按数量凑**）

### 批次 V —— 判据口径收敛（需裁定）

见 B-5 / B-6，统一后再动守卫。

---

## 6. 补强计划（防再踩坑）

| # | 补强 | 为什么 | 落点 |
|---|---|---|---|
| S-1 | **把"不得用已实现收益做预测"从文档变机器守卫** | `P-08` 现在只是文档；本次靠人发现 | 新守卫或并入 `scenario_tag_binding_guard` 同族 |
| S-2 | **`append_only_guard` 补"测试环境重置"通路** | 本次清空真源只能 `--no-verify` 豁免（已登记 `gap-no-test-env-reset-channel`） | `checks/append_only_guard.py` |
| S-3 | **落库脚本必须进版本库** | B-3 | 批次 II |
| S-4 | **入口产物与 `supersedes` 链绑定** | B-7（§7.3 已精确化） | `views` 构建器 + 守卫 |
| S-5 | **给"会话内产出"一条受控通路** | `gap-session-revision-no-channel` + B-4 同根因 | 批次 II 的清单模式 |
| S-6 | **失败记录保留的机器绑定** | 现在靠"人不去删" | `append_only_guard` 扩项：禁 `recommendations` 行被删或 `status` 被就地改写 |
| S-7 | **[新] 补 T06/T07 的触发条件** | 人话版逐字「不是我们没做，而是**这一轮确实没有触发条件**」—— 但没有触发条件的规则**永远无法验收** | 构造一个"仅略高于基准"的样例（T06）与一个"正收益但跑不赢"的样例（T07）进 `acceptance_checks` |

---

## 7. 我的复核结论与**更正**

### 7.1 完全复现（与运行记录一致）

两条 FATAL 逐字 · 三条专项守卫 PASS · facts 395 行/20 表 · 空表两张
· 两行建议的 `supersedes` 关系确在库里 · 阶段门五项读数。

### 7.2 ★ 运行记录的质量评价

- **最值得肯定**：**没有**为刷绿而改写失败记录或手写 `check_record`（`R-04` 守住）；
  6 条"靠 Agent 补足"逐条登记（含精确位置与修法）；人话版**逐条对照源稿**并给出 ✅/⚠️/❌，
  还**主动承认**了自己的三条数据缺口。
- **最该警惕**：那 6 条补足**全部发生在生产代码里，且零测试** —— 它们与既有代码现已无法区分。

### 7.3 ★ **更正 v1 的错误结论（B-7 精确化）**

**v1 说**：「三个入口渲染的是已被 `supersedes` 的旧建议」——**这个说法不准确**。

**复核实际**（`daily_page` 的 5 条 + `company_pages` 的 10 家逐条查）：

| 入口 | 实际情况 | 判 |
|---|---|---|
| `daily_page_*.json` | **5 条**（NVIDIA 两行：`buy` + `pending`，且 `pending` 明确标 `supersedes`） | ✅ **对的** |
| `company_pages.json` → TSMC / MSFT / AMD | 各自的 `-session-review`（`pending`） | ✅ 对的 |
| **`company_pages.json` → NVIDIA** | `rec-sec-nvda-2026-08-03`（**`buy`**）⇒ **取到了已被取代的那条** | ❌ **错的** |

而且**同一页内自相矛盾**（公司研究页 §六 vs §八）：
- §六「当前建议」= **买入**、`复查 2026-09-16`、`rule_version=decision-v1`、
  **提前判断三要素全为 `—`、反证 `—`**（= 缺陷建议的形态）
- §八「反证与未兑现条件」= **3 条**（来自 `pending` 那条）
- 而 `daily_page` 给 NVIDIA 的复查日是 **2026-11-25**，与 §六 的 `2026-09-16` **又不一致**

⇒ **精确结论**：`company_pages` 的 `current_recommendation` **未沿 `supersedes` 链取末节点**；
当同一公司有多条建议且存在取代关系时，会取到**已被取代的旧建议**，并与同页其它区块**取自不同行**。
**修法**：构建 `views` 时按 `supersedes` 链取末节点，且**同一页的所有区块必须取自同一行**（加断言）。

### 7.4 更正我上一轮的"待复核"

2026-09-17 早些时候，我按 `V-11` 把「裸词 `AGIX` 被解析成一家加拿大公司（CAD）」记为**待复核**
（当时换 3 入口 4 措辞复现不出）。人话版 §七 载明本次运行**复现了同一形态**
（「搜 `AGIX` 会返回**两只**同名近似标的（另一只是加拿大的公司、计价 CAD）」）。
⇒ **两次独立观测** ⇒ 该形态**成立**，**关闭"待复核"**。已落地的防线（`market_data.py` 的
"代码 + 名称 + 币种"三项比对）正是为它准备的。

---

## 8. 需要裁定的 7 件事（按阻塞强度）

| # | 事项 | 阻塞什么 | 选项 |
|---|---|---|---|
| 1 | `scenario_method_status`（C-3） | ★ **`nvidia_sample` 阶段 PASS** —— 人话版称"唯一的总闸门" | ① 定方法并冻结 ② 接受长期 BLOCKED ③ 移出通过条件（`T-15` 已裁定不得把退出物升格为判据） |
| 2 | `p05.algorithm`（C-1）+ **估值方法**（B-13） | 反向估值 / 价格区间 / 六项底稿第 ⑤ 项 | 给方法 + 给 `valuation-methods.yaml` 的 hardware 路由 |
| 3 | `p10.caliber_terms` 四键（C-2） | 复盘出数字 | 给信号生效价/交易成本/税前口径/观察窗口 |
| 4 | B-5 守卫扫全行 vs 取最新 | 两守卫长期稳定 | 二选一并统一 |
| 5 | B-6 同日重跑口径 | `stage_gate` 与 `no_signal_day` 一致性 | 统一到"每个 run_date 只看最新" |
| 6 | `supersedes` 的版本链写法 | 版本链语义 | 现状：新 id + `supersedes` + `recorded_seq=1`（**未递增**）与 `Ch9 §3.4.2`"同业务键追加版本"**不一致** ⇒ 裁定"新建议 vs 新版本" |
| 7 | B-9/B-10 的归属阶段 | 源稿两条 ❌ 何时做 | 是否提前到"阶段④之前"（它们是**老板体验最直接**的两块） |

---

## 9. 复核命令

```bash
V=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python
export CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0

$V system/scripts/ops/run_all_gates.py --timeout 30        # 非零 2
$V system/scripts/delivery/stage_gate.py system --stage all # FAIL(2)
$V system/scripts/validators/locator_check.py system        # PASS(0)
$V system/scripts/checks/quote_provenance_guard.py system    # PASS(0)
$V system/scripts/views/neutrality_check.py system          # PASS(0)

# §7.3 的两处读数
$V -c "import json;d=json.load(open('system/views/daily_page_2026-09-17.json',encoding='utf-8'));[print(r['company_id'],r['action'],r.get('supersedes')) for r in d['recommendation_changes']]"
$V -c "import json;c=json.load(open('system/views/company_pages.json',encoding='utf-8'));[print(x['company_id'],(x.get('current_recommendation') or {}).get('recommendation_id'),(x.get('current_recommendation') or {}).get('action')) for x in c['companies']]"
```
