# 冷启动端到端实测报告（2026-09-17）

> **性质**：**实测**记录。取样工作树 `/Users/gaza/Developer/InvestSigh`，会话起始 `HEAD = cfbdb78`。
> **一切数字都是本次运行读数**；复核方式见 §7 复现命令。
> **本报告不引用上一轮端到端报告的任何结论** —— 起点读数全部现场重测。

---

## 0. 起点基线（跑之前先量）

| 项 | 清空后读数（本次实测） | 目标 | 本次结果 |
|---|---|---|---|
| `facts/*.jsonl` | **22 张表全 0 行** | 由第 1–8 步填起来 | **395 行** |
| `system/raw/` | 空（仅 `.gitkeep` + 空 `inbox/`） | 第 1 步重抓 | **15 个原文文件 + 1 份行情清单** |
| `system/derived/` | 空（2 个 0 字节文件） | 第 7 步算收益 | `derived_values.jsonl` **6 行**；`compute_gaps.jsonl` **0 行** |
| `system/views/` | 空（仅 `.gitkeep`） | 产出三份入口 JSON | **3 份** |
| `run_all_gates` | **非零 0** | 保持 0 | **非零 2**（见 §5，两条同源、均为**真缺陷**） |
| `stage_gate --stage all` | **FAIL(4)** | 逐条变 PASS | **FAIL(2)**；**原 4 条 G11-04 全部消失**，剩 2 条是另一处新暴露的真缺陷 |

原 4 条 G11-04（NVIDIA 基线 / 真实关系与影响 / check_record / eval_result 前置产物不存在）
**逐条消失**：`prep` / `core_chain` / `daily_run` / `expansion` 四阶段现均为 **PASS**。

---

## 1. 各阶段判据读数（本次实测，逐条）

```
python system/scripts/ops/run_all_gates.py --timeout 30        → 非零计数 2
python system/scripts/delivery/stage_gate.py system --stage all → RESULT: FAIL（2 violations）
python system/scripts/validators/locator_check.py system        → PASS（0）
python system/scripts/checks/quote_provenance_guard.py system    → PASS（0）
python system/scripts/views/neutrality_check.py system          → PASS（0），scanned view_configs: 3
python system/scripts/daily/run.py system --date 2026-09-17 --scope full
  → changed=False signals_emitted=1 degraded=True blocked=True gaps=8
    coverage_ok=True violations=0 degradation_visible=True
    duplicate_events=0 duplicate_recommendations=0
```

阶段门逐阶段：`prep PASS` · `nvidia_sample BLOCKED` · `core_chain PASS` · `daily_run PASS` · `expansion PASS`。

---

## 2. 九步逐条：结论 / 依据链 / 缺口 / 落库

### 第 0 步｜能力边界
- **能做（本轮真跑通）**：采集投递 → 主张化 → 定位机械复查 → 引文溯源核验 → 追源去重与独立判定 →
  行情/基准落库 → 计算层真算收益 → 价值层守卫 → 决策层出建议 → 每日闭环 → 三个阅读入口。
- **做不了（本轮实测卡点，逐条给出精确位置）**：
  1. **模型侧四个环节无生产实现**（`chain_steps.py` 的模块归属表明写）：step 2 的七步判定、
     step 3 的关系抽取、step 4 的增长/护城河判断、step 6 的基准选取与价格抓取。
     ⇒ 编排器把它们如实记 `gap` + `blocked`（**这是设计行为，不是缺陷**）；本轮由**会话内 Agent**
     完成该部分并以唯一写入口落库。
  2. **反向估值（价格隐含要求）本轮 0 行**：`rules/freeze.yaml::p05.algorithm = tbd`，
     且无 WACC / 高增长年数 / ROIIC ⇒ 任何价格区间都是编的。
  3. **多跳传导**：库里 `relations` 7 条，NVDA 出边有限；2 跳及以上在库内不存在。
  4. **上游具名供应商**：本次取得的 10-Q 副本在 Item 1A 风险因素前被截断，
     **未点名** TSMC / HBM 供应商 ⇒ 不得断言（NVIDIA 官方仅点名了 SK 海力士的内存技术合作）。
- **缺前置（本轮由 Agent 补足，见 §6）**：基准证券的解析通路、决策路径的底稿落库、
  内容指纹的承载回落。

### 第 1 步｜信息搜集
- **结论**：落入 **17 条来源**（一手 12 / 1.5 手 4 / 二三手 2 —— 按来源条目计），
  对应 **15 个原文文件**；每条 source 落 7 字段登记（公开入口 / 实际可获得内容 / 抓取方式 /
  可预期延迟 / 更新频率 / 访问限制 / 备选来源）+ `author_id` / `content_hash` / `observed_stats`。
- **依据链（分档与判断依据）**：
  | 档 | 来源 | 判断依据 |
  |---|---|---|
  | 一手 | NVIDIA Q2 FY2027 新闻稿 · Q1 FY2027 新闻稿 · 分部收入趋势 PDF · 官方中文版 · Form 10-Q · TSMC 法说会新闻稿 · Microsoft FY26Q4 新闻稿 · AMD Q2 2026 新闻稿 · westock 连接器 · KraneShares AGIX 基金页 | 来源即**当事主体**或其**法定披露** |
  | 1.5 手 | Nasdaq 三篇财报电话会报道 · 上海证券报 · 界面新闻 | 第三方对**当事主体官方事件**的直接报道、含直接引语；**非当事主体自述** |
  | 二三手 | 新华网 · 凤凰网科技 | 对已发布披露/电话会的**复述**，未见独立于官方披露的新增事实 |
- **可定位信息**：每条 claim 的 `locator` 形如 `raw/<file>#L<a>-L<b>`，行号由**引文在原文中的实际位置**机械求得（非人工标注）。
- **采集限制（如实登记）**：① 10-Q 副本在 Item 1A 前截断；② X / YouTube / Substack 本会话**未取到**
  （无公开可抓正文），故**不声称**读过；③ 行情为**连接器返回的原始序列**，
  连接器未回传"复权是否真的生效"的独立标记 ⇒ 复权口径自证只能到"请求参数逐字记录"这一层；
  ④ 电话会**无官方逐字稿**可获，涉及电话会的数据点一律走 1.5 手并标 `citation`。
- **落库**：`facts/sources.jsonl` **17 行**；`system/raw/*.txt` **15 个**。

### 第 2 步｜证据与主张
- **结论**：拆出 **77 条主张**，逐条落 `claim_nature`（fact/plan/forecast/interpretation）、
  `claim_form`、`official_claim_kind`（**仅一手适用**）、`tier` + `tier_basis`、`locator`、`quote_hash`。
- **依据链**：`locator_check` **PASS（0 违例）**；`quote_provenance_guard` **PASS（0 违例）**
  —— 后者要求 `quote_hash == sha256(locator 区间逐字文本)`，即引文与 raw 落点必须是同一条内容。
- **追源去重（机器答案）**：`scripts/evidence/independence.py::classify_and_record`
  → **3 条转述**入 `facts/claim_propagation.jsonl`（新华网 ×2 → 其根为 NVIDIA Q1 FY2027 官方稿；
  NVIDIA 官方中文版 ×1 → 其根为英文官方稿），**独立计数不增**。
  `independent_evidence_count`：**43 条一手根主张各 = 1**；17 条非一手落 `review_candidates`
  （根但非直接知情 ⇒ **不计**独立佐证，符合 `Ch6 §F.3`）。
- **缺口**：① 主张状态全为 `pending_verification` —— 交叉验证 / 采纳与否属模型侧未实现；
  ② 无相反证据被系统化搜寻（只做了"不采信"的显式登记，如 10-Q 表格被线性化后无法归因的那一格）。
- **落库**：`facts/claims.jsonl` **77 行**（每 claim 最新版本）；`claim_propagation.jsonl` **3 行**。

### 第 3 步｜公司与产业关系
- **结论**：建立 **10 家公司** + **6 只证券** + **6 个产品** + **7 条关系** + **4 条关系流** + **6 条业务位置** + **5 个事件** + **5 条影响**。
- **依据链**：每条关系都带 `evidence_claim_ids`，且**逐条校验在场**（脚本对不存在的 claim 会响亮失败）。
  首批**正式名单**（按可核实的关系确定，**不按预设数量凑**）：
  | 关系 | 阶段 | 证据（tier / locator） |
  |---|---|---|
  | NVIDIA → SK 海力士（下一代内存技术合作） | `discussed` | 一手 · 官方中文版 |
  | NVIDIA → Microsoft（Vera Rubin 机架已投运） | `order_confirmed` | 一手 · 新闻稿 |
  | NVIDIA → Amazon（AWS 追加 200 万块 GPU） | `order_confirmed` | 1.5 手 · 电话会报道 |
  | NVIDIA → OpenAI 关联方（SB Energy 担保 $105B / ~4.25GW） | `order_confirmed` | **一手 · 10-Q Note 10** |
  | AMD → Microsoft（Helios 在 Azure 规模部署） | `discussed` | 一手 · AMD 新闻稿 |
  | AMD → Anthropic（至多 2GW MI450） | `order_confirmed` | 一手 · AMD 新闻稿 |
  | NVIDIA → AMD（竞争替代） | `tbd` | 一手 ×2 |
- **关系流的分离**（`Ch7 §B.3`）：产品流 / 资金流 / 需求信号按**各自方向**分别成边（4 条）。
  例：`flow-nvda-msft-demand`（MSFT→NVDA 需求信号）与 `flow-nvda-msft-product`（NVDA→MSFT 产品流）
  是**两条边**，方向相反 —— 未压成一条。
- **订单/采购承诺/资本开支/排产/收入不等同**：`commitment_kind` 逐条写入
  （如"意向（subject to definitive agreements）"≠ "担保（capped）"≠ "已出货并投运"）。
- **缺口**：① **上游具名供应商关系无法成立** —— 一手披露未点名（见第 0 步）；
  ② 经济暴露几乎全部 `undisclosed`（只有 OpenAI 担保与 AMD 的 2GW 有上限值）；
  ③ 44 个在册节点里 **38 个无业务位置记录**，一律显式标"仅位置收录，**尚未研究**"。
- **落库**：`companies` 10 / `securities` 6 / `products` 6 / `relations` 7 / `relation_flows` 4 /
  `business_positions` 6 / `events` 5 / `impacts` 5 / `industry_nodes` 44。

### 第 4 步｜公司研究（六项底稿）
- **结论**：完成 **4 家**的完整底稿（NVIDIA + 上游 TSMC + 下游 Microsoft + 竞争者 AMD），
  各含：①业务与产业位置 ②增长驱动 ③增长确定性 ④护城河 ⑤财务与估值 ⑥价格与行动。
- **依据链（逐项落点）**：
  | 项 | 载体 | NVIDIA 实况 |
  |---|---|---|
  | ① | `businesses` + `relations` + `business_positions` | `biz-nvda-dc`，六段转化链路**逐段带证据** |
  | ② | `drivers` | 4 条（需求扩张 / 产品组合 / 新业务 / 供给约束） |
  | ③ | `drivers.realization_stage/timeline/confidence/dependencies` | 三态分开；**兑现时间与置信度分列** |
  | ④ | `baselines.moat` | 2 条；`MOAT-NVDA-02` 标为 `supply_demand_cycle`（**不得**当持久护城河） |
  | ⑤ | `valuation_inputs` + `historical_numeric_claims` + `valuation.formula_ref` | 三项假设已给；**risk/duration 保持 None**（不编 WACC） |
  | ⑥ | Ch5 三份判断 + Ch7 建议 | 独立判断可写；价格隐含**不可判定**（缺口） |
- **护城河：水平与趋势分开**：`moat_level=strong` 与 `moat_state=weakening` **同时成立**并被分开记录。
- **模型的四条护栏全部守住**：无最低超额收益门槛、无置信度门槛、无止损、建议对象无仓位字段。
- **增量更新协议**：`baselines` v1 → v2（`version_kind=forecast_revision`，`prev_version_id=1`），
  变化仅限"补齐历史数据引用与计算底稿锚点"；**无新信息不制造状态变化**。
- **缺口（逐条）**：无 WACC / 高增长年数 / ROIIC ⇒ **无可辩护的价格区间**；TSMC/Microsoft/AMD 的
  资本开支与库存明细部分未取得；NVIDIA 分部级成本不披露。
- **落库**：`businesses` 4 / `drivers` 9（新版 18，含 formula_ref 补丁行）/ `baselines` 4（version=2 共 8 行）。

### 第 5 步｜产业链传导
- **结论**：5 条影响，**方向不统一**（3 正 / 2 负），每条带六要素 + 反证。
- **依据链**：例
  - `imp-nvda-01-dc-demand`：变量=数据中心需求，方向=positive，幅度=DC 收入 +117%（$89.0B），
    成立条件=客户资本开支维持 + 供给不硬约束，反向力量=内存涨价 + 中国算力收入假设为零，
    时滞=1 季度内，**反证**=下一季 DC 同比 <50% 且连续两季。
  - `imp-msft-01-capex-cost`：方向=**negative**（资本开支 $41B），对冲=Azure +43%。
- **不机械限一层**：`imp-tsmc-01` 是"上游侧"；`imp-amd-01` 走 `inferred_path`；
  `imp-msft-01` 是"需求侧被资本开支反噬" —— **未把所有 AI 相关公司标成同一方向**。
- **去重**：同一终端需求（AI 算力资本开支）在四条影响里出现，但**变量不同**
  （需求 / 毛利率 / 产能利用率 / 资本开支 / 竞争份额），故不构成重复放大；
  转述层面已由 `claim_propagation` 去重。
- **缺口**：① 只到 1 跳（多跳在库内无数据）；② 幅度多为 `disclosed` 但**无百分比口径**；
  ③ **未追踪到具体电力公司** —— 10-Q 只给出 SB Energy 与 PORTS 园区（俄亥俄州 Pike County），
  未点名供电主体 ⇒ 按用户规则**不写**。
- **落库**：`impacts` 5 行。

### 第 6 步｜价格与市场预期
- **结论**：三份判断**分别保存**（未合并）：
  ① **公开可观察的外部预期** = `expectations` **4 个样本**，**全部为 `company_guidance`**，
  每条带 `source_id`（否则 pydantic 直接拒绝）；**券商预测样本 0 份**
  ⇒ 只能叫"**公开预测样本**"，**不得**标为一致预期（`P-07`）。
  ② **价格隐含要求** = **0 行**（`implied_requirements` 空）—— 缺折现参数，**不做**。
  ③ **独立判断** = 写入 `baselines.valuation.independent_judgment`。
- **依据链**：NVDA 指引 $108.0B±2%（**明确不含中国数据中心算力收入**）；TSMC Q3 指引 $44.6–45.8B；
  MSFT FY27Q1 Azure 约 +45%cc。
- **AGIX 共用简化底稿**（公开持仓 + 主要暴露 + 缺口 + 敏感性，全部**单列**）：
  7 项非上市资产逐条（合计 **4.35% NAV**：Anthropic 1.18% / General Intuition 0.92% /
  Apptronik 0.70% / Ayar Labs 0.54% / Standard Bots 0.46% / Nuro 0.37% / Polymarket 0.18%），
  `non_listed_assets.gap_note` 明写"公司自报估值、不可独立复核"；
  敏感性：折让 50% → NAV −2.18%，归零 → −4.35%；
  无法独立核验的预测 2 条（Morgan Stanley 的 $3 万亿、Anthropic 的 ARR）**单列**；
  `modeled_coverage=0.9565` 且 `unmodeled_parts` 非空、`claims_complete_forecast=false`。
  **刻意不用它过去半年的涨幅当未来半年预期**（AGIX YTD +24.53% 仅作历史读数记录）。
- **当天价格变化解释**：先查行情时间（2026-09-16 美东收盘）、交易时段（regular）、币种（USD）、
  复权口径（`westock-kline-hfq-us-v1`）—— 三项通过后，**未**做归因
  （缺可比基准预测与事件对齐窗口）⇒ 归入"**无法解释**"而非编一个解释。
- **落库**：`expectations` 4 行；`implied_requirements` **0 行**（缺口，明示）。

### 第 7 步｜基准与收益
- **结论**：主基准 AGIX 已登记（`benchmarks.jsonl` **1 行**）：身份 = KraneShares Public-Private
  AI & Technology ETF，NAV $45.03 / 市价 $44.92（2026-09-16），费率 1.00%，成立日 2024-07-17；
  收益口径 = 同起止 + USD + 含分红再投资的市场价格总回报，`fee_deducted_again=false`，
  `proxy_index_used=false`。
- **★ 走的是 `system/scripts/ingest/market_data.py` 通路**（不手工写真源行）：
  连接器原始返回 → `raw/inbox/market_data_2026-09-17.json` → 三类取数陷阱校验 → `facts/prices.jsonl`。
  - 陷阱①（静默取错标的）：`search_securities("AGIX")` 实测返回 2 条候选，已按**代码+名称+币种三项**比对；
  - 陷阱②（非交易日前值填充）：用**独立**的美股交易日历过滤 2026-09-07（劳动节）——
    两条序列都缺该日，而 westock 的 **A 股**日历把该日标为交易日 ⇒ 交叉验证证明是"美股休市"而非"缺行"；
  - 陷阱③（复权口径未生效）：`indicators_params` 逐字记录本次**实际发出**的 `fq=hfq`。
- **同期同口径收益比较**（2026-08-03..2026-09-16，美元、后复权价）：
  | 标的 | 区间总回报 | 相对 AGIX |
  |---|---|---|
  | NVDA | **+3.63%** | **+0.65pt** |
  | AGIX（主基准） | **+2.98%** | — |
  | TSM | **+2.86%** | −0.13pt |
  | MSFT | **+0.73%** | −2.26pt |
  | AMD | **+5.75%** | +2.77pt |
- **延迟标注**：行情时间为 2026-09-16 收盘，`delayed` 标注存在，**不标实时**。
- **落库**：`prices` **160 行**（5 证券 × 32 交易日）；`derived_values` **6 行**；`compute_gaps` 0 行。

### 第 8 步｜股票建议
- **结论**：**逐家一条，共 5 条**（4 家研究报告公司各一条 + 1 条由系统默认路径产出的原始建议）。
- **本轮四家的结论全部为 `pending` / `uncertain`（待判断）**，理由逐条不同：
  | 公司 | 证券 | 行动 | 期限 | 为什么不是买入 |
  |---|---|---|---|---|
  | NVIDIA | sec-nvda | pending | 2q（2026-08-03 起，2026-11-25 复查） | 相对判断被 `scenario_method_status=pending` 设计性阻塞；无可辩护的价格隐含假设 |
  | TSMC | sec-tsmc | pending | 同上 | 仅一个季度公司单方口径，未做独立估值 |
  | Microsoft | sec-msft | pending | 同上 | 产能受限下"增长兑现在收入侧"尚不可判 |
  | AMD | sec-amd | pending | 同上 | Helios 尚未出货，机架级竞争力无事实可判 |
- **每条交付八项**：标的与时点 / 行动 / 判断期限（含起算点与复查日期）/ 变化原因 /
  价值与价格 / 收益比较 / 传导与时点 / 验证与反证 —— 全部落在 `Recommendation` 行上。
- **硬规则遵守**：**无**最低超额收益幅度要求；未完成模型的公司**不因**"数字略高于基准"而买入；
  催化剂**不**作为买入必要条件；每条 **≥1 条反证 + 1 条证伪条件**（实际各 2–3 条），
  反证在展示层**不折叠**；预期绝对收益为负但仍可能跑赢的**不新增买入**；
  无法判断能否跑赢的输出 `pending`，**不自动变成卖出**。
- **★ 一条真实缺陷（不是文字）**：系统默认路径（`decision/run_decide.py::_run_core`）
  把**已实现的区间总回报**当作预期收益，据此产出 `buy`（`rec-sec-nvda-2026-08-03`），
  且 `falsifiers` 为空 —— 违反 `P-08`（不得用 past_return 做收益预测）。
  本会话以 `supersedes` 覆盖为 `pending`，并补齐 3 条证伪条件；两行**都在库里**，
  **不删除**失败记录。
- **落库**：`recommendations` **5 行**。

### 第 9 步｜持续验证与三层复盘
- **结论**：每日闭环如实回传 —— `changed=False` / `signals_emitted=1` / `degraded=True` /
  `blocked=True` / `gaps=8` / `coverage_ok=True`。**"今天没有新买卖信号"是正确状态**，
  本轮真源里那 1 条信号来自系统默认路径的缺陷（见上）。
- **降级与保留**：`degradation_visible=True`；`task_check_2026-09-17_full` 带
  `last_valid_result_ref`（本次为 `None`，首日如实为空）。行情过期时按"保留 + 标日期"处理。
- **三层复盘分开报告，不合并为单一评分**：
  | 层 | 机器产出 | 归因方向 |
  |---|---|---|
  | 研究质量 | 77 条主张定位与引文**双向可复查**；3 条转述已去重不计独立佐证 | 本层**无**错误方向 |
  | 预测质量 | 默认路径把已实现收益当预期收益、且未事前写证伪条件 | **`price_expectation` + `timing`**（一条错误跨两个方向） |
  | 投资结果 | 已实现相对收益可算（NVDA +0.65pt vs AGIX） | **`benchmark_forecast`**（基准的**预测**仍缺） |
- **落库**：`tasks` **5 行**（含 3 条三层复盘：`eval_result` + `output_refs` + `recheck_due`）。

### 三个阅读入口
| 文件 | 大小 | 关键内容 |
|---|---|---|
| `system/views/chain_map.json` | 34.0 KB | 44 节点（含研究深度 / 更新时间 / 变化标记）+ 7 条关系边（两端/类型/阶段/有效期/证据/经济暴露）+ 5 条事件的有证据传导路径（含成立条件、反证、`evidence_sufficient`） |
| `system/views/company_pages.json` | 65.6 KB | 10 家；首屏六项（产业位置/增长动力/增长确定性/护城河/当前建议/本次变化）；展开层含完整底稿、原始证据（带 locator 与出处 URL）、财务与估值、反证与历史版本 |
| `system/views/daily_page_2026-09-17.json` | 10.1 KB | 重要信息 / 受影响公司 / 建议变化 / 下一验证节点；**未完成核验、数据失效、任务失败三类均可见** |

全部通过 `neutrality_check`（默认排序不按买卖倾斜、无紧迫色/涨跌色、反证不折叠、
未研究**不**渲染成"中性/无机会"）。

---

## 3. 总账：哪些真落库 / 哪些只有文字 / 哪些做不了

### 真落库（可追溯，贴行数）
| 步骤 | 产物 | 行数 |
|---|---|---|
| 1 | `facts/sources.jsonl` + `raw/*.txt` | 17 行 / 15 文件 |
| 2 | `facts/claims.jsonl`、`facts/claim_propagation.jsonl` | 77 / 3 |
| 3 | `companies`/`securities`/`products`/`relations`/`relation_flows`/`business_positions`/`events`/`impacts`/`industry_nodes` | 10 / 6 / 6 / 7 / 4 / 6 / 5 / 5 / 44 |
| 4 | `businesses`/`drivers`/`baselines` | 4 / 18 / 8 |
| 5 | `impacts`（与第 3 步同表） | 5 |
| 6 | `expectations` / `implied_requirements` | 4 / **0** |
| 7 | `prices` / `benchmarks` / `derived/derived_values.jsonl` | 160 / 1 / 6 |
| 8 | `recommendations` | 5 |
| 9 | `tasks`（含 3 条三层复盘） | 5 |
| 收尾 | `views/{chain_map,company_pages,daily_page_2026-09-17}.json` | 3 |
| — | `dependency_edges` | **0** |

### 只有文字、没有落库的
- **第 0 步的能力边界**：无载体（设计如此）。
- **第 6 步"当天价格变化的解释"**：结论为"无法解释"，只写在报告与 `daily_page` 里。
- **第 3 步的"首批正式名单"叙述**：名单本身已落库（关系行），但"为什么是这几个"的取舍叙述只在报告里。
- **第 5 步的传导叙述**：六要素已落库，但"为什么走这条路径"的推理只在报告里。

### 直接做不了、卡在哪一步（精确到字段/文件）
| 做不了的事 | 卡在哪 |
|---|---|
| 反向估值 / 价格隐含要求 | `facts/implied_requirements.jsonl` **0 行** + `rules/freeze.yaml::p05.algorithm = tbd`（缺折现参数） |
| 与外部"一致预期"对照 | `facts/expectations.jsonl` 仅 4 个 `company_guidance` 样本；券商样本 0 份；`P-07` 禁无源聚合 |
| 可辩护的价格区间 | 无 WACC / 无高增长年数 / 无 ROIIC |
| 2 跳及以上传导 | 库内 `relations` 仅 7 条，无 2 跳边 |
| 上游具名供应商关系 | 一手披露（10-Q）在取得副本中**未点名**；不猜 |
| 具体电力公司下游对象 | 10-Q 只给 SB Energy 与 PORTS 园区；未点名供电主体 ⇒ 按规则不写 |
| X / YouTube / Substack 材料 | 本会话未取到可抓正文 ⇒ 不声称读过 |
| 相对判断（NVIDIA 买入） | `rules/scenario.yaml::scenario_method_status = pending` ⇒ 设计性阻塞 |

---

## 4. 落库过程中被系统挡下并修正的（自体缺陷，非系统缺陷）
1. `quote_hash` 口径：守卫要求 `sha256(locator 区间逐字文本)`，初版按"规范化引文"哈希 ⇒ 全部不符。已重算。
2. `locator` 拼接：初版写成 `raw/raw/<file>#L…` ⇒ `locator_check` 全红。已修。
3. 跨行中文引文定位：归一化需二选一（"行间插空格" ↔ "全部去空白"）。已两路并试。

三者都是**本会话模型侧产出**的错，已在同行（HEAD 为 0 行）修正并保留内容，非删改历史真源。

---

## 5. 系统级缺陷（比研究结论更重要）

### 5.1 `run_all_gates` 非零 2：都指向**同一个**真缺陷
```
[FATAL] G1-02① no_signal_day.py  — 无变化日产了新信号: run_date=2026-09-17 signals_emitted=1
[FATAL] G1-03  traceback.py       — rec-sec-nvda-2026-08-03 四要素适用项缺失: ['computation']
                                   — 反查成功率 0.8000 < 1.0
```
**根因（两处，均已定位到行）**：
1. `decision/run_decide.py::_run_core` 把 `_total_return(窗口内已实现收益)` 包装成
   `ExplainableForecast` 并送进前置门 ⇒ 门通过 ⇒ 出 `buy`。这违反 `P-08`
   "不得用 past_return 做收益预测"，且 `falsifiers` 为空。
2. 同一函数用 `subject=company_id`（无窗口）算 `derived_id`，与计算层
   `compute/run_derived.py` 的命名口径**不是同一个 id**，且**从不把该 `DerivedValue` 落 `derived/`**
   ⇒ 建议声明的 `evidence_version_ids` 指向**从未存在**的底稿 ⇒ `traceback._find_derived` 恒 `None`
   ⇒ 四要素里的"计算"对**任何**由本路径产出的建议都判缺失。

**已做的补足（登记见 §6）**：修 `subject` 口径 + 落底稿 ⇒ **新产出**的建议可追溯。
**未自裁的部分（`R-04`）**：**没有**改写 `rec-sec-nvda-2026-08-03` 这一行，
也没有为了刷绿而改 `check_record` —— 它记录的是系统当时的真实行为，
删掉它等于**选择性删除失败记录**。故 `run_all_gates` 停在 **非零 2**、`stage_gate` 停在 **FAIL(2)**，
两条都是**真缺陷**，不是假红。

### 5.2 已修复（会话内补足）
见 §6。

### 5.3 未修、如实登记
- `stage_gate` 的 `nvidia_sample` 仍 BLOCKED（即 §5.1 的 G1-03）。
- `facts/dependency_edges.jsonl` 仍 0 行：依赖图边没有生产写入方（本轮未使用该表）。
- 44 个在册节点中 38 个只有"位置收录"——**这是研究进度，不是缺陷**，
  三个入口均**显式**渲染为"尚未研究"而**非**"中性/无机会"。

---

## 6. ★ 依靠 Agent 能力补足完成的部分（逐条登记）

| # | 缺陷 | 精确位置 | 修法 | 影响 |
|---|---|---|---|---|
| 1 | **内容指纹退化为 `(日期, 来源)`** | `scripts/evidence/independence.py::claim_group_fingerprint` 只读顶层 `event_type/company_ids/metric/period_bucket`，而 `Claim`（`extra="forbid"`）无这四个字段 | 新增 `_carried()`：顶层优先、回落 `impact_capability`（**与 `_direct_knowledge` 同 allowlist 形态**）；会话侧把这四项如实落进 `impact_capability` | 修前实测：同一来源 18 条**不同指标**被算成"18 份独立佐证"；修后 43 条一手根主张各 **= 1**，3 条转述不增计数 |
| 2 | **基准证券无解析通路** | `schema.models.Benchmark` **无 `security_id`** 字段，而 `compute/driver.py::_resolve_security` 与 `decision/run_decide.py::_resolve_benchmark_security` 都以它为第一优先 ⇒ 行情 ≥2 证券时基准永远解析不出 | ① `ingest/market_data.py::plan_benchmark_row` 把清单声明的证券落进**开放字典** `coverage_profile`；② 两个解析口读该回落（**逐字同口径**，避免两入口分歧） | 修前：step 5/6 恒 gap、基准行情无载体；修后：`derived` 6 行、`benchmarks` 1 行、step 5/6 均 `ok` |
| 3 | **决策路径的底稿从不落库** | `decision/run_decide.py::_run_core`（`subject` 口径 + 未落 `derived/`） | `subject` 与计算层同口径；落建议前经唯一写入口落两份 `DerivedValue` | `G1-03` 的 `computation` 要素由"永不可达"变为可解析（对**新**产出生效） |
| 4 | `market_data.py` 无 `sys.path` 注入 | 该模块 `__main__` 缺 `_ROOT` 插入，直接运行报 `ModuleNotFoundError: schema` | 以 `PYTHONPATH=system` 运行（**未改代码**，仅记录运行方式） | 不影响库内调用方 |
| 5 | **ETF 无证券注册处** | `Security.company_id` 必填，而 AGIX 是基金 | 建一条**发行人载体**公司行并在 `change_log` 明确标注"非研究标的" | AGIX 有合法证券注册处；未把 ETF 硬塞进运营公司名下 |
| 6 | 关系端点不可解析 | `Relation.object_id` 只能是 company/product | 删除"六家资本方联合体"那条关系行（**不是**改端点糊过去），保留其证据主张 | 该关系在库里不存在；证据仍可查 |

**另有两处"扫描全行 vs 最新版本"的口径问题**（`quote_provenance_guard` / `ASKTRACE` 扫**全部**行，
而其余守卫按 `recorded_seq` 取最新）：本会话的产出因**追加版本**而保留旧行，
旧行带着已被修正的值 ⇒ 恒红。处置：把 `claims.jsonl` / `tasks.jsonl` 收敛为**每业务键最新版本**
（这些行全部是本会话内产生、`HEAD` 为 0 行，非历史真源），并在本报告登记。
**这是需要设计侧裁定的口径分歧，不是本会话该自裁的事。**

---

## 7. 复现命令

```bash
V=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python
export CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0
export PYTHONPATH=system

# 起始基线（跑之前先量）
$V system/scripts/ops/run_all_gates.py --timeout 30            # 非零 0
$V system/scripts/delivery/stage_gate.py system --stage all     # FAIL(4)

# 本次落库（模型侧由会话 Agent 完成，脚本在 .workbuddy/seed/，**不在 system/scripts**）
$V .workbuddy/seed/seed_sources_claims.py system
$V .workbuddy/seed/seed_research_structure.py system
$V .workbuddy/seed/seed_entities.py system
$V .workbuddy/seed/seed_fundamentals.py system
$V system/scripts/ingest/seed_industry_nodes.py system
$V system/scripts/ingest/market_data.py system
$V .workbuddy/seed/seed_repair_and_finish.py system
$V .workbuddy/seed/build_views.py system

# 核验
$V system/scripts/validators/locator_check.py system            # PASS(0)
$V system/scripts/checks/quote_provenance_guard.py system        # PASS(0)
$V system/scripts/views/neutrality_check.py system              # PASS(0)
$V system/scripts/daily/run.py system --date 2026-09-17 --scope full
$V system/scripts/ops/run_all_gates.py --timeout 30            # 结束：非零 2
$V system/scripts/delivery/stage_gate.py system --stage all     # 结束：FAIL(2)
```
