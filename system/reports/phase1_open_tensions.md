# 阶段① 未决张力登记（`T-01` ~ `T-0N`）

> **用途**：把施工过程中遇到的「设计文档之间 / 文档内部」不一致**逐条登记**，
> 写清**双方节号 + 原文 + 本实现的取舍**，交需求方裁定。
>
> **依据**：`00_开发Agent开工提示词 §5.3`——
> 「设计文档之间冲突 → **停。写清冲突双方的确切节号 + 原文 → 上报**」；
> 以及 `§6.4` 第 8 条「跨模块字段/表名先对齐再实现」。
>
> **本实现的原则**（贯穿全部张力）：
> 1. **不擅自改动设计**（`施工图 §0` 第 4 条：本图不替设计做决定）；
> 2. **不悄悄放松纪律**（宁可把例外**钉死**在测试里，也不改窄规则）；
> 3. 两条都做不到时 → **保留最保守的形态 + 显式登记**。

| # | 张力 | 双方（节号 + 原文） | 本实现的取舍 | 状态 |
|---|---|---|---|---|
| **T-01** | `data-sources.allowlist.yaml` 落位 | ① `Ch9 §3.4.11` / `Ch11 §D.2`：写在 `rules/` ② `施工图 §3.1` 组件表：写在 `registry/` | 采 ①（`system/rules/data-sources.allowlist.yaml`）。依据 `施工图 §0` 第 4 条「组件细节以各章 `02` 为准」。文件头已注明分歧 | ✅ **已确认**（需求方 2026-09-16：「均按你的取舍点确认」） |
| **T-02** | 机会类型枚举的表面形式 | ① `Ch2 §C.1`：**"enum A/B"**（源稿："机会类型 A 类 / B 类"）② `施工图 §8` 纪律 7：**"枚举 token 英文小写 + 下划线"** | **wire 值保持设计逐字** `"A"` / `"B"`（数据契约以设计为准）；**成员名改小写** `type_a` / `type_b`（守纪律 7 的标识符要求）。例外集合被单测 `test_enum_value_exceptions_are_exactly_the_documented_ones` **钉死**，新增例外即 fail | ✅ **已确认**（需求方 2026-09-16：「均按你的取舍点确认」） |
| **T-03** | `freeze_status` 同名不同域 | ① `Ch11 §C`：`freeze_status ∈ {tbd, frozen}`（**参数域**）② `Ch3 §C.3`：`freeze_status ∈ {unfrozen, frozen}`（**基准对象域**） | 按**对象级作用域**实现为两个枚举：`ParamFreezeStatus` / `BenchmarkFreezeStatus`。**不擅自改名**（设计两处均逐字用 `freeze_status`） | ✅ **已确认**（需求方 2026-09-16：「均按你的取舍点确认」） |
| **T-04** | `skills/` 到底几个 `SKILL.md` | ① `施工图 §3.1` 末行 + `§4` 目录树："**六阶段**各一个 `SKILL.md`"② `施工图 §3.3` 第 2 行：给出**六个具名** skill | 采 ② 的**六个具名**（名字有逐字出处的才建，零发明）：`aichain-claim-extract` · `aichain-price-expectation` · `aichain-valuation-baseline` · `aichain-ask` · `aichain-daily` · `aichain-delivery`。①中"六阶段"疑为"六类流程"的措辞宽松；**不自行发明**第 7 个名字 | ✅ **已确认**（需求方 2026-09-16：「均按你的取舍点确认」） |
| **T-05** | `skills/` 契约的锚点指向 | `施工图 §3.1` 组件表把 `SKILL.md` 的出处标为 **`Ch9 §3.2.1`**；但 `Ch9 §3.2.1` 实为「**六项硬约束的归属裁定**」，不含任何 I/O 契约字段 | 按实际内容改用 **`Ch9 §3.5 模块输入输出契约（对齐 N9.2-09）`** 作为 SKILL.md 的 I/O 来源，并**同时标注** `施工图 §3.1` 的原始指向，便于需求方核对。同类于施工图 §7 已登记的 `N-01` | ✅ **已确认**（需求方 2026-09-16：「均按你的取舍点确认」） |
| **T-06** | `registry/rules.lock.json` 自身的防篡改 | 纪律 9「`rules/` 0444 + SHA256」未说明**锁清单自身**由谁保护 | 锁清单刻意放在 `rules/` **之外**，使"模型对 `rules/` 无写权"无例外路径；锁清单自身的完整性由 **Git 提交历史**承担（`Ch9 §3.2.1`：追加式不可变由 Git 承担）。已在 `rules_lock_guard.py` 报告里输出 `locked_at` 以便人工核对 | 已按设计意图落地 |
| **T-07** | `10/02 §I.2` 的 T 表指向错误 | `10/02 §I.2` 把 T 权威表指向"本章 §B.1"，实为「六结果链条表」 | 按施工图 §7 `N-01` 指示：查 T 表一律以 `10/01 §2.1` 为准；**不修改设计文档** | ✅ **已确认**（需求方 2026-09-16：「均按你的取舍点确认」）—— 即：**查 T 表一律以 `10/01 §2.1` 为准**，本实现**不修改设计文档**；`10/02 §I.2` 的那处错误指向由**需求方**在该文档侧修正 |
| **T-08** | **`rules/pipeline.yaml` 把 step 1–6 声明为"首版已实现"，但实现体（采集/核验/传导/估值/决策五层）分属阶段②③** | ① `rules/pipeline.yaml::steps`：`implemented_in_first_version: True`（step 1–6）、`blocking: True`、**无 `hook`、无 `gap_behavior`**；仅 step 7–8 为 `False` 且 `gap_behavior: explicit_gap_when_hook_absent`<br>② `施工图 §3.2` 组件归位：`scripts/orchestrate/pipeline.py` 属**阶段①**，而**采集/核验/传导/估值/决策各层组件属阶段②③** | ✅ **已裁定（需求方 2026-09-16 选 A）**：**注册 1–6**，算术 / 图 / 决策部分接真实实现；**模型侧缺口显式标 `degraded` + 记 gap，不静默**。已落地 `I-1`（`530c3cd`：`StepOutcome.incomplete_reason` + `scripts/orchestrate/chain_steps.py` + 11 用例）。实测 step 1/6 `ok`、step 2/3/4/5 `gap`（原因含设计锚点）、`blocked=True` —— **注册 ≠ 完成**，`rules/` 未改 | ✅ **已裁定** |
| **T-09** | ★ **"多因素综合比较"缺机制**：外部同题作业用**加权打分**排序，本项目**明令禁止**同类形态 | ① 本项目：`P-09` + `施工图 §8 纪律 1`（决策作用域内**参数不得内置阈值**、代码**不得**出现 `weight` / `score` 命中词）+ `R-06`（判据必须**可判定 + 穷尽**；加权分数是**不可判定的合成量**）<br>② 外部实测（`system/reports/nvda_task_lessons_for_investsigh.md §4`）：该作业用"需求可见度 25% / 瓶颈硬度 25% / 预期空间 15% / 估值安全边际 20% / 风险可测性 15%"加权，以及满分 100 的 8 维论点健康度评分，**把 6 个候选排成一列** | **两边都不错，但本项目因此缺一个等价物**：本项目 `DerivedValue` 可追到 operand、判据可判定，但**没有"把多个候选按多因素排成一列"的机制**。请需求方裁定采用何种**非加权**的可判定替代：<br>① **分层偏序**（先按单一判据筛，再按下一判据）；<br>② **逐维度支配关系**（Pareto 前沿，不做合成）；<br>③ **把权重外置**到 `rules/`（由需求方冻结，代码只读不算），从而不违反 `P-09`；<br>④ 确认本项目**不需要**排序表（那就不补） | ✅ **已裁定（需求方 2026-09-16 选 ②「逐维度支配关系 / Pareto 前沿」）**<br>**裁定内容**：本项目**不做加权合成、不出单一综合分**；候选之间的比较一律表达为**逐维度的支配关系**（A 在某维度不差于 B，且至少一维严格更好 ⇒ A 支配 B；互不支配 ⇒ **并列，不强行排序**）。未形成支配关系者**如实呈现为不可比**，不得用权重把它们压成一个数。<br>**实现落位**：属分析/展示层（`Ch5`/`Ch7` 的排序产物），**不在本批次**；届时：① 判据必须**可判定**（逐维度比较，而非"综合分比大小"）；② 支配关系必须可追溯（每个维度的取值都要能追到 `DerivedValue` / 证据对象）；③ **不得**出现 `weight`/`score` 命中词（`P-09` / `纪律 1`）。<br>**与之呼应**：`G-30`（传导矩阵的"强度"）**先不加数值** —— 若将来要加，必须做成**定性分档**（强/中/弱），否则会与 Pareto 的"可判定逐维比较"冲突 |

| **T-10** | ★ **首条建议的"四要素覆盖率 == 1.0"结构性不可达**（真实数据首次暴露） | ① `scripts/trace/traceback.py`（承担 `G1-03`）：对 `facts/recommendations.jsonl` 逐条要求"结论可追溯四要素"齐备，并断言**覆盖率 == 1.0**；四要素之一 = **`prev_version_id`（上一版本）**。<br>② 但**第一条**建议**结构上不存在**上一版本 —— `prev_version_id` 只能为 `None`。 | **实测**：真实数据入主线后 `traceback` 立刻 `exit=1`：<br>`[FATAL] G1-03 @ facts/recommendations.jsonl — rec-nvda-001 四要素缺失: ['assumptions','computation','prev_version_id']` + `四要素覆盖率 0.0000 < 1.0`。<br>→ **即使把 `assumptions`/`computation` 补齐**，`prev_version_id` 仍恒缺 ⇒ **覆盖率 1.0 对"首条建议"永远不可达**。<br>**主理人不自裁**（`R-04`）：本项涉及判据语义与"首版/首条"的边界，交需求方裁定。 | ✅ **已裁定（需求方 2026-09-16 选 ①）并已执行** —— 分母改为"该建议**适用的**要素数"：`TraceabilityResult.applicable()` 判定 `prev_version_id` 适用 ⟺ `version > 1` 或已给 `supersedes`（**`version` 未知时按适用处理**，不得靠"不知道版本"豁免）；`missing()` 只报**适用的**缺失项。实测真仓库：`适用=['evidence','assumptions','computation']`、`version=1` ⇒ 首版的结构性不可满足**已消除**。<br>★ 配套（审计员指出、主理人复核属实）：`_find_derived` 原先只按 `derived_id == conclusion_id` 匹配，而计算层 id 是 `dv-…`、建议 id 是 `rec-…` ⇒ **永不相等** ⇒ "计算"要素对**任何**建议都不可达、四要素之一形同虚设。已补第二条解析路径（按建议声明的 `evidence_version_ids` 里的 `dv-…` 解析，**不新增字段**）。 |

| **T-11** | ★ **`Ch6 §C.3` 的"人工去重覆盖（`claim_alias`）"无处承载** —— 它需要一张表，而 `Ch9 §3.3.3` 把 `facts/` 锁死在 **18 个 JSONL** | ① `Ch6 §C.3`：去重兜底要求**人工确认"这两条其实是同一事件"**（`claim_alias` 人工 override）<br>② `Ch9 §3.3.3`：`facts/` 下 **18 个 JSONL 不得增删改名** | 本实现**不新增第 19 个 JSONL**（守 `Ch9 §3.3.3`），改为**只输出 `review_candidates`**（待人工复核的候选对），**不落库人工覆盖结论** ⇒ **人工 override 这条链路目前无承载**（不是实现偷懒，是**没有合法的存放处**）。<br>→ 请需求方裁定：① 把该结论并入**既有**某张表（例如 `claims` 的某字段 / `claim_propagation` 的一种 `kind`）；② 还是允许 `facts/` 增至 19 个（**与 `Ch9 §3.3.3` 冲突，须改设计**）；③ 还是确认"首版不做人工 override" | ✅ **已按 ① 落地**（`66422a8`）：`ClaimPropagation` 增 `kind: PropagationKind`（默认 `restatement`，含 `manual_alias_override`）+ `alias_override: AliasOverride{is_independent, reason, operator, at}`，并加**一致性校验**（`kind` 与 `alias_override` 必须同时在场或缺席 —— 不允许"半截的人工覆盖"）。**不新增第 19 个 JSONL**；旧行取默认值即合法（`Ch9 §3.4.2`） |
| **T-12** | **`independent_evidence_count` 无法落为 `Claim` 字段** | ① `Ch6 §C.2/§C.4`：独立佐证基数是"去重与独立判定"的核心输出<br>② `schema/models.py::Claim` 为 `extra="forbid"`，且本批次**禁改 `schema/**`** | 本实现**以计算 API 暴露**该基数（不落库），故它是**每次现算**而不是**真源里的字段** ⇒ 消费方（如展示层 / 判据）拿不到持久化值。**这是"字段缺位"而不是"实现缺失"**，与 `T-11` 同源（都是"设计要求的量在 18 张表里没有位置"）。 | ✅ **已按"追加 `Claim` 可选字段"落地**（`66422a8`）：`Claim.independent_evidence_count: int \| None = None`（**基数非权重**，守 `Ch6 §B.4`）。真仓库 5 行真实 claim 仍合法；`origin_claim_id` 的产出方（`plan_origin_attribution` / `record_claim_updates` / `classify_and_record`）同期接入 |

| **T-13** | ★ **`facts/` 是否封闭为 18 个 JSONL？** —— 各章 02 声明的 **4 张新表**与全局件的"18 不得增删改名"正面冲突。**这是阶段② 进入条件的直接前置** | **甲方（封闭）**：`00_开发Agent开工提示词 §三`「`facts/` 的 18 个 JSONL → 8 类对象（照 `施工图 §4` 表建，**不得增删改名**）」；`00_交付施工图 §4`「18 个追加式 JSONL（8 类对象唯一真源）」；`Ch9 §3.3.3`「`facts/` **18 个追加式 JSONL**（见下）」+ 逐条列举 18。<br>**乙方（各章要求新表，节号 + 原文）**：<br>· `Ch4 §B.1`「**落位取舍：新建 `facts/businesses.jsonl`**（业务单元，mechanism 内嵌）」—— 其方案比选表**指名否决**了"挂 `baselines` 下"，理由逐字："baseline 是**版本化研究结论**（随研究更新换代），business 是**公司结构信息**（相对稳定，状态对象）；混在一起会让'业务定义'随研究版本爆炸"；<br>· `Ch4 §D.1`「驱动对象 schema（`facts/drivers.jsonl`）」；`Ch4 §19-20`「新表 … 挂 `facts/`」；<br>· `Ch5 §B.2 / §19 / §129`：`facts/implied_requirements.jsonl`；<br>· `Ch7 §B / §21`：`facts/businesses.jsonl`、`facts/relation_flows.jsonl`。<br>**且施工图自相矛盾**：`§2` 阶段②/③把 4 张新表**当既有文件列**（"数据 | `facts/businesses.jsonl` …"），`§4` 却只列 18。<br>**同源**：`T-11`/`T-12` 也是"设计要求的量在 18 张表里没有位置"，但**T-13 更重** —— 它不是"某个人工 override 无处放"，而是**阶段②的通过判据（`Ch4 §G` 六项底稿深度）所需字段整片缺位**。 | **实测证据（阶段② 结构性不可达）**：<br>① `Ch4 §G.1` 六项深度 → 字段映射要求 `business_refs[]` / `driver_refs[]`（含 `financial_link`、`duration`、`cost_of_growth`）/ `drivers[].timeline`+`confidence`+`dependencies[]` / `moat[]` / `valuation_inputs`；<br>② 而 `schema/models.py::Baseline`（:752-768）**这四组一个都没有**（只有 `business_mechanism: str`、`driver_model: list[DriverModel]`、`value_state_refs`）；<br>③ `DriverModel`（:741-749）只有 7 字段（`driver_id` / `driver_name` / `realization_stage` / `is_primary` / `linked_accounts` / `assumptions`），**缺 `Ch4 §D.1` 的 `business_id` / `source_class`（7 类）/ `duration{mode,value}` / `financial_link{accounts, per_share_metric, formula_ref}` / `cost_of_growth`（五项）/ `timeline` / `confidence` / `importance_class`**；<br>④ `Ch5 §50`「估值经营假设 = `baseline.driver_refs[].financial_link`」—— `driver_refs` 不存在 ⇒ **阶段② 的"推导可复查"链断在这里**。<br>⑤ **另**：`施工图 §2` 阶段② 点名的 **16 个组件全部未建**（`scripts/valuelayer/**` 与 `scripts/pricelayer/**` 两个包整体不存在；`rules/{metric-sets,baseline,valuation-methods,scenario}.yaml` 均不存在）。⇒ **T-13 不是离线理论问题，它就是近期目标的进入条件**。 | ★ **推荐：维持 18 封闭，逐项折叠**（与 `T-11`/`T-12` 的既有先例同构；代码注释逐字写着"**绝不新增第 19 个 JSONL**"）：<br>| 设计要点 | 既有载体 |<br>|---|---|<br>| `businesses`（`Ch4 §B`） | **`facts/business_positions.jsonl`** —— 它在 18 表内、`Ch9 §3.3.3` 的描述就是"公司与证券（**含多业务位置**）"，**正是为这个用的**；`Ch4 §B.1` 的方案比选**漏了这一项**（它只比了"挂 baselines"与"新建文件"两个选项，没有看到已存在的 `business_positions`） |<br>| `drivers`（`Ch4 §D`） | `baselines.driver_model[]`（嵌套，承载 `Ch4 §D.1` **全部**字段）+ `baselines.driver_refs[]`（引用）。driver 是**研究结论**（随研究版本更新），与 baseline 同版本化是自洽的 —— `Ch4 §B.1` 的否决理由只针对 **business**（公司结构信息） |<br>| `implied_requirements`（`Ch5 §B.2`） | **`derived/implied_requirements.jsonl`** —— ★ **`derived/` 不受 18 约束**（18 只约束 `facts/`，`Ch9 §3.3.3` 对 `derived/` 的定义是"确定性计算结果（带公式与操作数引用）"，反向求解正是计算结果），且顺带天然获得 `DerivedValue` 追溯链 |<br>| `relation_flows`（`Ch7 §B`） | `relations.jsonl` + `kind ∈ {product, capital, demand_signal}`（**与 `T-11` 给 `claim_propagation` 加 `kind` 完全同构**） |<br>**代价（如实）**：折叠会让 `Ch4 §B.1` 明写的"新建表"落空一次，需要在各章侧或在本文档侧留一条显式回改说明（**不得**让实现默默折叠而不留痕）；且 `DriverModel` 与 `business_positions` 要做一次**字段补齐**（`Ch4 §G.1` + `§D.1` 全部字段）。<br>**备选 ②**：允许 `facts/` 18 → 22，并显式回改 `提示词 §三` / `施工图 §4` / `Ch9 §3.3.3` 的"18"字样。**代价**：触及 `schema/models.py`、门禁的 `_TRUTH_STEMS`、`append_only_guard` 的 pathspec、`schema_sync_guard` 的对象计数与多处文档；但**与各章 02 逐字一致**。<br>**备选 ③**：维持 18 且**收窄 `Ch4 §G` 六项深度判据**（改判据不改数据）—— 这等于**改设计**（收窄已写死的验收标准），依 `施工图 §0` 第 4 条**不由实现方决定**，不推荐。<br>★ **不需要裁定就能做的一半**（已识别，将先行）：`Ch4 §22` 原文「新字段 | `baselines` 上（`business_refs`、`driver_refs`、`moat[]`、`value_state` 三字段、`valuation`）」—— 这些是 `baselines` 的**追加 schema**，**与表数无关** ⇒ `Ch4 §G.1` 的字段补齐**可以先做**，不必等 T-13 裁定 | ✅ **已裁定（需求方 2026-09-16）：`facts/` 扩表** —— 原话：「如果扩表能更方便后续的开发，不留技术债，达到更鲁棒、更科学稳定的效果，那扩表也没关系，改文档的事情而已。**哪个更好选哪个**」<br>★ 我(deliverable owner)据原文逐条复核后确认**扩表确实更好**，依据**不是偏好，而是设计自己的方案比选**：<br>① `Ch4 §B.1` 的方案比选**否决**折叠（"baseline 是版本化研究结论、business 是相对稳定的公司结构信息"）；<br>② `Ch7 §B.3` 的方案比选**否决**合并（"同一 `relations` 表三行 → ✗：关系身份被复制三份，去重与版本追踪困难"），并给出 **MSFT↔NVDA 的具体反例**：三方向压不成一个、存在性解耦（"有 capex 指引但尚无订单"）、误把需求信号当收入、去重需要分开、证据/阶段不同；<br>③ ★ 我原以为 `businesses` 可折进既有的 `business_positions` —— **实测证伪**：`BusinessPosition`（`schema/models.py:467`）是「公司 × 产业节点的**多业务位置**（覆盖维度）」（`research_depth` / `inclusion_reason` / `evidence_strength`，服务 Ch3 分级显示），与 `Ch4 §B` 的 `business`（业务单元 + `mechanism{payer,offering,conversion_chain}` + `metric_set_id`）**不是一回事**；<br>④ 折叠的**现存债**已可实测：`Baseline.business_mechanism` 是**自由文本串**（丢结构）、`DriverModel` 缺 `Ch4 §D.1` 的 7 类字段、`business_refs[]`/`driver_refs[]` **不存在** ⇒ `Ch4 §G.1` 六项深度**结构上不可达**。<br>**落位（18 → 22，四张全部按各章 02 逐字挂 `facts/`）**：`businesses`（`Ch4 §B`）· `drivers`（`Ch4 §D`）· `implied_requirements`（`Ch5 §B.2`）· `relation_flows`（`Ch7 §B.3`）。<br>**改动面（已核实有界）**：`schema/models.py` 4 新模型 + `Baseline` 字段补齐；`facts/` 4 个新 JSONL；`conftest._TRUTH_STEMS` 18→22；★ `append_only_guard` 的 pathspec 是 **glob** `system/facts/*.jsonl` ⇒ **自动覆盖新文件**，无需改；`schema_sync_guard` 的对象数从注册表派生 ⇒ 自动变 22。<br>⚠️ **文档侧不在我可改范围**：`00_开发Agent开工提示词 §三` / `00_交付施工图 §4` / `Ch9 §3.3.3` 的"18（不得增删改名）"字样属**设计区（只读）**，我**不得**修改（`提示词 §三` 明文：不修改/不删除/不移动/不重命名）。<br>→ 这构成一条**显式回改请求（待需求方在文档侧执行）**：把三处的"18"改为"22"并补 4 张表的说明。在文档回改前，**代码与文档会有一处已知且已批准的偏离**，以本裁定为准（`施工图 §0` 第 4 条：组件细节以各章 `02` 为准，而 4 张表**正是各章 02 逐字要求的**）。<br>★ 连带：`T-11`/`T-12` 的"折叠"解法**无需回退** —— `ClaimPropagation.kind` 与 `Claim.independent_evidence_count` 分别是**更贴切**的载体（人工别名覆盖本来就是一种传播 kind；基数是 claim 的属性），不是因为 18 锁才被迫折叠 |


> 记在这里是因为它们都属"**守卫看起来在跑，其实没在跑**"这一类 —— 比功能缺失更危险。

| # | 缺陷 | 症状（实测） | 根因 | 修复 |
|---|---|---|---|---|
| **D-1** | `is_decision_scope_module()` **恒返回 False** | 向 `scripts/decision/` 注入 `weight` 未被 P-09 拦下；门禁全绿 | `include_paths` 的 glob `**` 未被剥离，`key` 变成 `"scripts/decision/**"`，与裸路径永不相等 | 新增 `_common.strip_system_prefix()`；并**直测匹配器**（`tests/unit/test_scope_matchers.py`） |
| **D-2** | 反占位符扫描器**卡死** | `run_all_gates --timeout 25` → `TIMEOUT`；**卡死的门禁 = 被关掉的门禁** | `LOG_AND_RERAISE` 用了 `(?:\s*.+\n)*?` 嵌套量词 → 灾难性回溯 | 两行规则改无嵌套量词正则；结构规则改**缩进感知窗口**；加**硬超时**跑测器 |
| **D-3** | 空函数体**误报 13 条** | 所有**异常类**（只有 docstring）被判空体 | 抹白字符串后，docstring 只占的 body 变成"空" | `EMPTY_BODY` 改 **AST 判定**；docstring 不算实现但也不算"body 不存在" |
| **D-4** | 免扫机制**整体失效** | 检查器开始扫自己与 `tests/`（误报源头） | `_is_exempt(rel(root, p))` —— **参数顺序写反**，`rel` 静默返回绝对路径 | 修参数顺序；并让 `rel()` **响亮失败**（不再静默兜底） |
| **D-5** | L3 **自命中**致门禁恒红 | 首次真跑报 7 条「每条禁词命中自己」 | `rules/banned_tokens.yaml` **自己是禁词唯一真源**，却被 L3 扫 | 加 `L3_SELF_EXEMPT`；**降噪就是有效性** |
| **D-6** | L4 逐文件"找不到门即违规" | 决策目录下任何**辅助模块**都会把 L4 打红 | 把"目录级"判据误实现成"文件级" | 改**目录级聚合**；`--require-l4` 才是阶段③ 硬门 |
| **D-7** | `pre-commit.sh` 注释被判占位话术 | `# ③ N-2 反占位符（命中即 fail）` → FAIL | `DATA_PLACEHOLDER` 对 `.sh` **逐行全文**匹配 | 非 `.py` 文件先剥注释再匹配（`.json` 无注释语法除外） |
| **D-8** | `rules/` 0444 与注入测试冲突 | 夹具继承 0444 → 注入测试 `PermissionError` | `copytree` 保留源权限 | 夹具显式 `_make_writable`；锁的验证由 `test_rules_lock.py` **显式改回 0444** 后单独测 |

**共同教训**：这 8 条里有 6 条是「**守卫本身失效或误报**」。
按 `§八 N-2` 的话说——**降噪就是有效性：宁可漏报不可吵**。
一个天天误报的门禁，最终一定会被人关掉；那还不如一开始就没有它。

---

## 已裁定 / 待裁定的后续张力（批次 13 期间产生）

| # | 张力 | 双方（节号 + 原文） | 本实现的取舍 | 状态 |
|---|---|---|---|---|
| **`T-14`** | `Ch4 §G.1⑥` 与 `§G.2` 的"六项齐备" × `§A.1` 的方向，看起来像**环** | ① `Ch4 §G.1⑥`：「价格与行动 \| **引用第五章三份判断 + 第七章建议**（不落本表，§A.1）」<br>② `Ch4 §G.2`：形式完备性检查含 `sections_nonempty`（**六项** section 非空）<br>③ `Ch4 §A.1`：Ch4 是 Ch5 的**输入**（Ch5 只读 Ch4 的 `driver_model` 等接口） | ★ **判定：不是环，是"版本次序"** —— ⑥ 的载体是**引用**，而 `baseline` 是**版本化**的（`Ch9 §3.3.3`：键 = `(company_id, version)`，新版本追加）⇒ **首版不带 ⑥、待 Ch5/Ch7 产物到位后追加新版本补上**。<br>**实现口径**（`ws-ch4-valuelayer`）：⑥ 无上下文时记为 `not_evaluated` + **显式 note + 计数** + `passed=False`（**既不伪造 violation、也不当通过**，`G-03`）；并在 `stage_gate` 输出里让读者看出"⑥ 未评估"而非"⑥ 失败"。<br>★ **不**用"阶段② 只要求 ①–⑤"绕（那等于收窄一条写死的验收标准）。<br>★ 若实现中发现该路径**实际走不通**（取不到 `code_root` / 无新版本写入路径）⇒ 升级需求方 | **已裁定（主理人 2026-09-16）**：按版本次序处理；实现受阻则升级 |
| **`T-15`** | **`施工图:215/:234` 的退出物「三层复盘记录」是否应升格为阶段⑤ 的通过判据** | ① `施工图 §2 阶段⑤`：**退出物** = 三层复盘记录（`:215`）<br>② `10/02 §C.1/§C.4`：只约束 `eval_layer` 的**取值域**（`research_quality`/`forecast_quality`/`investment_result`；**不得新增、不得合并**）—— **没有**"三个都必须出现"<br>③ 而 `registry/delivery.yaml` 的 `expansion::review_append_only` 的**被绑检查**是"三层齐备"（缺层即违例） | **实现口径**（`ws-criterion-effectiveness`，主理人裁定）：<br>· 新 id **`eval_layer_domain`**（statement **逐字引** `Ch10 §C.4`「三层不得新增/合并」），检查 = **取值域** + **不合并** —— 属**纯对齐**，无新增门槛；<br>· "**三层齐备**" **不**升格为判据、**不计违例**（把**退出物**升格成通过判据属**新增门槛**，`施工图 §0` 第 1 条，不由实现方定）；<br>· 但**观测必须保留**：`stage_gate` 输出 `expansion.layers_seen: k/3` 显式 note + 计数（`G-03`：不允许静默消失）；<br>· `review_append_only` 重新绑定到**真正的 append-only 检查**（按 `Ch10 §D.5` **原文**，不按主理人转述） | **待裁定（需求方）**：是否把"三层齐备"升格为阶段⑤ 通过判据 |
| **`T-16`** | **字段名设计↔实现分歧**：`task_status` vs `status` | ① `08_产品入口与每日运行/02_实现方案.md §N8.2-04`：`task_status`<br>② 而 18 表的真源字段/`schema/models.py::Task` 用 `status` | 实现按**磁盘真名** `status`（真源已如此），**不擅自改名**（改真源字段名属设计级变更）；`ws-criterion-effectiveness` 实现 `G9-1` 的 `all_tasks_have_status` 时按 `status` 读，并在报告里**显式标注**这处分歧 | **待裁定（需求方）**：以 `task_status` 为准改名（需迁移已落库行），还是把设计侧改回 `status` |
| **`T-17`** | **`Ch10 §D.5` 第一条"三类记录齐全"`(success, failure, pending)` 无载体** | `Ch10 §D.5` 要求复盘记录"三类记录齐全"；而全仓 `grep` 只在 `registry/delivery.yaml:132` 的**声明**里出现这三个词，**代码区无任何承载**（无字段/表/enum） | 按 `G-03` **显式记账为缺口**（**不算通过、也不算违例**）；**不**为此新建表/字段/enum（载体属设计决定 —— `T-11`/`T-12` 的先例是**折叠进既有表**或**上报**，不是自造）；临时 `ineffective` 登记须写明"临时 + 载体待定" | **待裁定（需求方）**：载体落哪 |


---

## 批次 13 执行期的**后续复核补充**（主理人 2026-09-16）

### `T-15` 补充 —— 原计划「新 id `eval_layer_domain`」**机械上不可行**，且拿到一条更硬的证据

**（1）为什么它在本项目里做不到（不是判断问题，是绑定机制问题）**

原口径要求新增判据 id `eval_layer_domain`。但 `stage_gate` 的判据绑定是**双向机器绑定**：
`assert_criteria_implemented()` 把 `registry/delivery.yaml` 声明为 `automated` 的条目 与
函数体内的 `criterion()` 字面量**做双向比对**，且 `criterion_effectiveness_guard` 另加
"**登记 ⊆ 已绑定**、**已绑定 ⊆ 已声明**"两条义务。
⇒ 在函数体内绑一个 `delivery.yaml` **未声明**的 id ⇒ **当场红**（"绑定了未声明的判据"）。
⇒ 要新增 id，**必须同时改 `registry/delivery.yaml` 的 `pass_criteria_testable`**；
而该字段是 **`施工图 §2 阶段⑤` 通过判据列表的转写** ⇒ **给它加一条 = 改需求面**（`施工图 §0` 第 1 条）。

**（2）更硬的一手证据（取代原来"全设计区没有逐字出处"的穷举式否定）**

`ws-criterion-effectiveness` 原先的论据是"全设计区检索不到通过判据级的逐字出处"——
这属**穷举式否定**，容易被"你搜漏了"反驳。主理人实测出一条**可核的肯定事实**：

| 来源 | 实测内容 |
|---|---|
| `registry/delivery.yaml` → `delivery_stages` → `key: expansion` → `pass_criteria_testable` | **正好 3 条**：`research_standard_consistent` · `investment_result_verifiable` · `review_append_only` |
| 同条目 `exit_artifacts` | `['三层复盘记录']` |

⇒ **「三层齐备」确实只在退出物里、没有通过判据身份。** 这条是**实现区可核**的声明面事实，
比"设计区检索不到"强。★ 一般化口径：**用可核的肯定事实，代替不可穷举的否定。**

**（3）当前落点（主理人批准保持）**

· `review_append_only` **只**绑它的真语义（按 `Ch10 §D.5` 原文）：① `append_only_guard` 覆盖载体 ② **已声明过的 `eval_layer` 层不得从记录集里消失**（= "禁只留赢的"的可判定快照形态）。
· 「三层齐备」**检查保留、仍挂在该 id 名下**，并在 `registry/criterion_counterexamples.yaml` 里**显式标注「★ 待裁定」**（不静默、不新增 id、判别力不丢）。**这是本时点的正确中间态。**
· **待需求方**：① 是否把「三层齐备」升格为阶段⑤ 通过判据（需同时改 `delivery.yaml` 声明面）；② 若不升格，是否接受"退出物缺失只在 `expansion.layers_seen: k/3` 的 note 里可见、不阻断阶段"。

### `T-18` · ★ **`rules/pipeline.yaml` 把 step 7/8 声明为「既 blocking、又不首版实现」** ⇒ 首版**结构上不可能不 blocked**

| 双方（节号 + 原文） | 本实现的取舍 | 状态 |
|---|---|---|
| ① `rules/pipeline.yaml::steps` 实测（主理人逐条列出）：<br>　step **1–6**：`blocking: True` **+** `implemented_in_first_version: True`<br>　step **7** `publish_recommendations`：`blocking: True` **+** `implemented_in_first_version: **False**`<br>　step **8** `continuous_verification_and_history`：同上 `True` / `False`<br>② `T-08` 已裁：**注册 1–6**，模型侧缺口显式标 `degraded` + 记 gap | **实测后果**（`ws-degrade-contract` 本单钉出，主理人复核）：7/8 永不注册 ⇒ `run_daily()` 记 gap 并令 `blocked=True` ⇒ **`status` 恒 `failed`** ⇒ 阶段④ 在首版**没有任何"成功运行"**。<br>⇒ 直接后果：`degrade_keeps_last_valid` 的**「此前已有行持有有效结果、后失败却丢引用」这一半，在真仓库上永远不可自然发生**（只能在受控输入上验证）。<br>⇒ 更根本的：**`implemented_in_first_version` 这一列在首版没有任何作用**（写 `True` 还是 `False`，都照样 blocking）—— 与 **D1 同族：声明与现实矛盾**。<br>本单**只如实登记**，**不自行改 `rules/pipeline.yaml`**（0444 + 属设计裁定）。 | **待裁定（需求方）**。**主理人推荐**：首版**不把** `implemented_in_first_version: False` 的步计入 blocking 判定，**但必须**记 `gaps` 并显式标 `deferred_by_design`。<br>**理由**：① 否则 `implemented_in_first_version` 是**死列**；② `blocked` 恒真 ⇒ **失去判别力**，且让整条降级/幂等链**恒处于告警态**，正是本项目铁律「**卡死的信号 = 被关掉的信号**」最危险的形态（对比 `T-08` 的处置：那次是"注册 1–6 + 缺显式标 `degraded`"，同样以"恢复判别力"为目标）。<br>**备选**：维持现状 ⇒ 阶段④ 在 7/8 实现前**永久不可判 PASS**，且降级契约另一半**只能受控验证**（如实但代价大）。

#### ★ `T-18` 的**决定性证据**：`implemented_in_first_version` 的**代码消费者数 = 0**（主理人独立复核）

`ws-degrade-contract` 在异常性复核（④-1）中提出这条，**我逐条查证属实**，且它比上表的"blocking 表"更硬 ——
因为它把问题从"**语义上不该这样**"提升为"**机器上确实谁也没读它**"：

| 检索式 | 实测结果 |
|---|---|
| 全仓检索 `implemented_in_first_version` | **8 处**都在 `rules/pipeline.yaml`（**声明本身**）；其余全在 **注释 / docstring / 报告 / SKILL.md**（`scripts/orchestrate/ingest_step.py:4` · `pipeline.py:152` · `chain_steps.py:6` · `PROGRESS.md:258` · `tests/injection/test_chain_steps_wiring.py:5` · `skills/aichain-daily/SKILL.md:35`）；**没有任何 `cfg.get(...)` 读取点** |
| 对照检索同表的另一列 `blocking` | `scripts/orchestrate/pipeline.py` 里 `cfg.get("blocking")` **6 处**（:215 / :225 / :249 / :302 / :324 + :548）—— **有真实消费者** |

⇒ **同一张表的两列，一列有人读、一列零人读。** 后果必然是「`blocking` 说了算、`implemented_in_first_version` 说了不算」⇒ 7/8 恒 blocked。

★ **这是本项目第三次出现同一形态**，三条并列看：

| # | 形态 | 具体 |
|---|---|---|
| `G-50` | **有实现、有生产调用方，但判据没绑** | `evidence_locatable` —— 接线接在了**错的层** |
| `G-RC-12` | **机制存在，但在真源上不生效** | `append_only_guard` 的 pathspec 恒空 |
| `T-18` | **声明在 `rules/` 里，但代码零消费者** | `implemented_in_first_version` —— 死列 |

⇒ 共同形态一句话：**「写在声明里」≠「在机器上有效力」。** 三者的检查方向也是同一个：
**「声明」与「实现」必须有**可机的**消费者/绑定关系**（本项目铁律 5）。

★ **由此得出一条新的、可判定的机器检查（已派给 `ws-schema-expand` 的 13-pre，方向 2）**：
现有的"键对齐守卫"只顾**单向**（代码读的键 **必须存在** 于 `rules/`，否则静默 fallback）；
**必须再加反向**：**`rules/` 里声明了语义、但代码区从不读的键 ⇒ 报警**。
反向这一侧正是 `T-18`（`implemented_in_first_version`）、`scenario_method_status_domain` / `scenario_method_status_blocking`（`ws-ch5-pricelayer` 实测：真文件有这两个键，代码却把"`pending` ⇒ 阻塞"**硬编码**）的暴露面 —— **不查这一侧，就永远发现不了"死列"。**

★ **第三条并行发现（同族）**：`ws-ch5-pricelayer` 实测 `load_scenario_policy('.')` 在**真 `rules/scenario.yaml`** 上返回
`status='pending'` / `value_source='rules'` / **`method_version=''`** —— 因为真文件**没有 `method_version` 这个键**，
而它的**测试夹具**给了。⇒ **夹具造了一个真文件里不存在的形状**，与 `G-43`/`G-45`（夹具与真写路径不同源）**完全同族**。
⇒ 已派该流修（要么找到真实载体，要么改**响亮失败**，**不许静默取空串**）。
