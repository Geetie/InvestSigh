# 「设计上不做」清单 —— 预设不实现 / 只留接口 / 计划未落地

> **用途**：正式测试期间，见到失败/空缺时，先来这里比对 —— **分清"设计如此"与"真缺陷"**。
> 本清单只收**设计明确写了"本阶段不做 / 不提前实现 / 只留接口 / 不纳入首版"**的项；
> **不收**「等需求方拍板的 `tbd` 参数」（那是另一类，见 §六）。
>
> ★ **时效核对件**（`V-11` 规矩 5）：取样于 `main@a69cc14`（`git rev-parse HEAD`），2026-09-17。
> 每项都带**取证位置**，重读时回源码核对，不要直接引用本文件的结论。

---

## 0. 一句话

> 系统**故意**把三类东西留空：**① 编排的最后两步（发布/验证）**、**② 调度与通知/发布三个规则文件的"行为"**、
> **③ 五类宿主能力（Automation / SubAgent / 取数 / 展示 / 分享）** ——
> 前者由 Ch8/Ch10 承接，中者"值只在 `freeze.yaml`"、代码只落**可解析指针骨架**，
> 后者按施工图 §1.3 划为 **A 档（开箱即用零代码）= 直接用 WorkBuddy**。

---

## 一、编排层：第 7/8 步**只留 hook**（最核心的一条）

| 项 | 内容 |
|---|---|
| **声明位置** | `system/rules/pipeline.yaml` |
| **step 7** | `publish_recommendations` → `implemented_in_first_version: false` + `hook: publish_hook` + `gap_behavior: explicit_gap_when_hook_absent` |
| **step 8** | `continuous_verification_and_history` → `implemented_in_first_version: false` + `hook: verify_hook` |
| **逐字原文** | `pipeline.yaml:7-8`「第 7/8 步**预留接口**（`publish_hook` / `verify_hook`），第八章/第十章"已拆解"，接口即插即用；**不在第一章伪造第 7/8 步实现**」 |
| **跨章声明** | `01_产品目标与核心闭环/02_实现方案.md:106`（编排器只串 1–6 步）· `08_产品入口与每日运行/02_实现方案.md:79`「`verify_hook`（Ch1 §E 第 8 步预留）｜归第十章，本章**只留接口不实现**」 |
| **实现现状** | `pipeline.py:218/222` 有 `register_publish_hook()` / `register_verify_hook()`；`pipeline.py:315-321` 在**已注册**时才调用 |
| **★ 关键实测** | 这两个注册器**生产路径无调用方** —— 全仓只有 `tests/daily/test_daily_run.py:355-356` 调过（`system/skills/aichain-daily/SKILL.md:24` 亦注明"阶段① 尚未实现 → 落到 `gap`"） |
| **运行表现** | 不计入 `blocking`，但**记 `gaps` 并显式标 `deferred_by_design`**（`T-18` 裁定，`pipeline.py::_deferred_by_design()`） |

⇒ **测试时看到 `deferred_by_design` / 步骤 7/8 标 gap，是设计如此，不是缺陷。**

### ★ 2026-09-17 更新：step 7 的**产物机制已进版本库**（但 hook 仍未注册）

原先"第 7 步"这条只有声明；现在它的**产物机制**（`produces: [views, snapshots]` 里的 `views`）
已内化进版本库，**是否注册 `publish_hook` 仍属待裁定**：

| 项 | 现状 |
|---|---|
| 机制 | `scripts/views/build.py`（构建三份入口 JSON + `--check` 跑中立守卫）· `scripts/views/render.py`（三份人话 MD + 自包含 `dashboard.html`） |
| 来源 | 承接自**会话内脚本** `.workbuddy/seed/build_views.py` / `build_readable_views.py`（`gitignore` 内、从不进版本库） |
| 消费方 | ① 两个 CLI（可复跑，见 `test_prompt_cold_start_e2e.md`）② `tests/unit/test_views.py`（26 条） |
| **未做的接线** | `Pipeline.register_publish_hook()` **仍无生产调用方** —— 且当下**即使注册也不会触发**：`run_daily` 仅在 `changed and not blocked` 时调它，而实测 `blocked=True` |
| **待裁定** | 是否现在注册 `publish_hook`（= 把 step 7 从 `deferred_by_design` 里挪出来）。**未自裁**（`R-04`） |

⇒ 测试时看到 `views/` 里三份 JSON + `dashboard.html` 由这两个 CLI 产出、而步骤 7 仍标
`deferred_by_design`，**这不矛盾**：机制在、编排钩子未注册。

---

## 二、规则层：3 个 `pointer_skeleton`（只声明结构位，不实现行为）

| 文件 | 指向 | `delivery_stage` | 逐字声明 |
|---|---|---|---|
| `system/rules/schedule.yaml` | `p07` | 4 | `schedule.yaml:12-13`「本阶段只落**可解析的指针骨架**，使 `p07` 的 `schedule_pointer` 不悬空；**不提前实现**调度行为（**无 rrule、无触发器、无时区换算逻辑**）」 |
| `system/rules/publish.yaml` | `p08` / `p11` | 4 | `publish.yaml:10`「本阶段只落可解析指针骨架，**不提前实现**」 |
| `system/rules/notification.yaml` | `p11` | 4 | `notification.yaml:7` 同上 |

三者的 `implementation_status` 均为 **`pointer_skeleton`**（全仓共 3 处，`grep ^implementation_status system/rules`）。

**`rules/schedule.yaml` 的 `tbd` 字段**（这是"行为留空"，不是"参数待拍"）：
`cadence.daily` / `cadence.event_triggered` / `cadence.timezone` / `cadence.time_value` /
`cadence.non_trading_day_policy` —— 全部 `tbd`；仅 `anchor: us_market_close` 有值（源稿建议窗口）。

⇒ **调度行为的唯一供给方 = 宿主（WorkBuddy Automation）**，见 §五。

---

## 三、计划了但**未落地**（施工图 §3.1 对账）

拿 `00_交付施工图.md §3.1` 的 22 项计划配置与 `system/rules/` + `system/registry/` 实际内容逐项对账：

| 计划落位 | 计划阶段 | 出处 | 实况 | **有生产消费者？** |
|---|---|---|---|---|
| `rules/tiering.vN.yaml` | ③ | Ch6 §B 来源分级规则（版本化） | ✗ 缺 | 无（仅 `skills/aichain-claim-extract/SKILL.md:36` 提及） |
| `rules/budget.yaml` | ③ | Ch6 §D.5 三类预算闸门 | ✗ 缺 | **有** —— `scripts/evidence/budget_gate.py`（14 处引用） |
| `registry/publisher-entities.yaml` | ③ | Ch6 §B publisher-entity 名录 | ✗ 缺 | 无（0 处引用） |
| `rules/trigger.yaml` | ④ | Ch8 §D 五类触发契约 | ✗ 缺 | 无（仅 `conflict_scan.py:19` docstring 举例 + `skills/aichain-daily/SKILL.md:78`） |
| `rules/transmission.yaml` | **§3.1 未列**（出自 `07_产业链传导与股票建议/02_实现方案.md J4` / 待拍板 `B3`） | 传导阈值 | ✗ 缺 | **有** —— `scripts/transmit/engine.py`（15 处引用） |

**两处"落位漂移"（已装，只是不在计划写的目录）**：

- `registry/data-sources.allowlist.yaml`（计划，阶段①）→ 实装在 **`rules/data-sources.allowlist.yaml`**
  （且 `freeze.yaml` 的 `p09.allowlist_pointer` 正指向 `rules/...` ⇒ 实装自洽，计划表那一格是旧写法）
- `registry/acceptance_input_set`（计划，阶段⑤）→ 实装为 **`registry/acceptance_input_set.yaml`**（带后缀）

### ★★ 两个缺失项的**实测失败形态**（不是推测）

```
① rules/budget.yaml 缺失
   load_budget_limits(root, importance_class="high")            → BudgetConfigMissing（响亮失败）
     文案：缺 rules/budget.yaml，且 p09 的 budget 值非数值映射、亦未提供显式缺省 —— 拒绝静默兜底
   带 defaults={"time":30,"compute":10,"retrieval":20} 时        → 返回 BudgetLimits(source="explicit_defaults")
     并在 notes 里**如实标注**"rules/budget.yaml 缺失且 freeze 预算值为 tbd"

② rules/transmission.yaml 缺失
   load_transmit_params(root) → FileNotFoundError
     文案：缺少传导参数真源: rules/transmission.yaml（唯一真源，值待冻结；不得在代码里内置阈值）
```

⇒ **判据**：缺 `budget.yaml` 时，**有显式缺省**才通过（且留下"用的是显式缺省"的 note）；
缺 `transmission.yaml` 时**无条件响亮失败**（连缺省通道都没有）。
**这两种失败都是"响亮"的，不是静默** —— 见到它们属于**预期内的未落地**，不是回归缺陷。

---

## 四、能力边界（源稿逐字"不纳入首版"）

| 项 | 源稿/需求 | 状态 | 守卫 |
|---|---|---|---|
| 组合权重优化 · 个人账户管理 · 交易执行 | `03_覆盖范围与基准/01_需求拆解.md` `N3.3-04`（原文第 82 行） | **不纳入首版**，登记为"后续版本" | 建议无 `quantity`/`position`/下单字段（承 Ch2 `P-04`/`P-05`） |
| 黄金 / BTC / 跨资产配置模块 | `N3.3-02` / 张力 `C3-5` | **不建**（环境变化只作输入注入公司/基准研究） | 模块 denylist 守卫 |
| 环境层五类项独立成"择时/配置模块" | `N3.3-01` / 张力 `C3-5` | **只作输入**，不得独立成模块 | `03_覆盖范围与基准/02_实现方案.md §F.1` + denylist |
| 首版不做收益验收 | `01_产品目标与核心闭环/01_需求拆解.md:165` | 六步完成标准以 Ch10 为准，收益走**按周期前向复盘** | `N1.3-03/04` |

---

## 五、宿主侧：按施工图 §1.3 划为 **A 档**，代码里**故意不实现**

`00_交付施工图.md §1.3（阶段 × WorkBuddy 复用口径）` 阶段④ 的三档分工：

| 档 | 内容（逐字） |
|---|---|
| **A（零代码，直接复用）** | **`Automation（rrule）`** · SubAgent 任务队列 · `present_files` 三入口 |
| B（Skill / 配置 / 提示词） | `aichain-daily` / `aichain-ask` Skill · `rules/trigger\|schedule\|notification\|publish.yaml` · 视图 |
| C（需独立代码） | 降级写路径守卫 · 幂等与增量不变量 · 展示层中立守卫扩项 |

同表阶段① A 档 = MCP 连接器取数（westock / iFinD / pandadata）· 网页采集（WebSearch / WebFetch）· 文件系统持久化；
阶段⑤ A 档 = `present_files` 展示 · 腾讯文档分享。

⇒ **这正是 §二 那三个 `pointer_skeleton` 的对应关系**：
`schedule.yaml` 只留 `p07` 指针 ≙ 调度行为由 **WorkBuddy Automation（rrule）** 供给；
`publish.yaml` / `notification.yaml` 只留指针 ≙ 发布与通知渠道由**宿主展示/分享能力**承接。

**分层结论（回答"WorkBuddy 定时任务 vs `daily/run.py`"）**：

- **WorkBuddy Automation** = 供给"**什么时候跑**"（时刻 / 时区 / 非交易日策略）——代码里刻意留空
- **`scripts/daily/run.py`** = 供给"**跑的那一次到底是什么**"，且**不重造状态机**（`G-06`）：
  ① 8 步闭环 + 断点续跑一律由 `Pipeline.run_daily` 承载；
  ② 本模块只补三件事：**降级可见 + 保留上次有效结果**（`Ch8 §E`）· **覆盖可核**（阶段④硬判据）·
  **同日重跑幂等自检**（`Ch8 §N8.4-08`）；
  ③ **反 KPI**（`Ch1 §D.3`）：如实回传 `changed` / `signals_emitted` / `degraded` / `blocked` / `gaps`，
  **不做**任何乐观改写 ——「每天维护 ≠ 每天必须产生新买卖信号」。
- 两者**不是替代关系**：Automation 触发 → 会话里执行 `daily/run.py`（或按 `aichain-daily` skill 走契约）。

---

## 六、★ 与「待拍板的 `tbd` 参数」的区别（**不要混为一谈**）

| | 本清单（设计上不做） | `freeze.yaml` 的 11 项 `tbd` |
|---|---|---|
| 性质 | **实现边界**：本阶段就是不写 | **等拍板**：机制就绪，值待定 |
| 数量 | 见 §一~§五 | `p01`–`p11` 共 **11 项**，`frozen_at: tbd` |
| 现成答案 | 无（由 Ch8/Ch10 或宿主补） | **《`00_待拍板项清单.md`》A 档 9 + B 档 22 + C 档 20 已给值**（标注"值已确认"） |
| 后果 | 显式 `gap` / `deferred_by_design` / `pointer_skeleton` | `get_param()` 返 `tbd` ⇒ 消费者按 `blocked_by_*` 如实记账（**不伪造数字**） |
| 施工图的说法 | —— | `§7 N-03`「A 档 6 项未拍板 ⇒ **不阻塞开工；验收前须拍板**」 |
| 其他待外部口径 | —— | `§7 N-04`（J8 脱敏**待法务**）· `N-05`（J3 运行时刻 = `p07`，随阶段④前置冻结） |

★ 提示：**施工图 §7 把 `N-03` 写成"A 档 6 项"**，而 `freeze.yaml` 实为 **11 项**（A 档 6 项 + C 档 5 项，
对应 `11_交付顺序与实施参数` 的 A/C 分档）。两处**口径不同**，引用时须带限定词（`V-11` 规矩 9）。

---

## 七、测试期速查：看到 X，先归哪一类

| 现象 | 归类 | 依据 |
|---|---|---|
| 步骤 7/8 报 `gap` / `deferred_by_design` | **设计如此** | §一 |
| 步骤 2/3/4 报 `gap`（"模型侧、阶段②③ 未交付"） | **设计如此**（`T-08` A 方案） | §一 |
| `load_transmit_params` 抛 `FileNotFoundError: rules/transmission.yaml` | **设计如此**（未落地） | §三 |
| `BudgetConfigMissing`（缺 `budget.yaml` 且无显式缺省） | **设计如此**（未落地） | §三 |
| 复盘收益 `status=blocked_by_caliber` + 四个缺失键 | **设计如此**（`p10` 未冻结） | §六 |
| 每日运行报不出"下一班时刻" | **设计如此**（`schedule.yaml` `pointer_skeleton`） | §二 |
| `views/event_studies.jsonl` 为空 → `NOT_EVALUATED` | **设计如此**（六结果视图未落，`G-03` 显式记账） | `traceback_coverage.py` 输出 |
| 真源某些表 0 行 | **待判定**：可能是"还没采集"，不是"功能没做" | `G-03`：0 行 ≠ 已验证 |
| 门禁非 0 退出码 / 判据 FAIL | **真缺陷** | `run_all_gates.py` / `stage_gate.py` |
| ★ **`prices` / `benchmarks` 无生产写入方** | **★ 真缺陷候选**（**不是**设计留空） | 见 §八 |
| 三个阅读入口由 `views/build.py` + `views/render.py` 产出，而 step 7 仍报 `deferred_by_design` | **设计如此**（机制已进版本库、编排钩子未注册） | §一 的 2026-09-17 更新 |
| 公司页「当前建议」与每日页「建议变化」**不一致** | **真缺陷**（应为同一 `supersedes` 链末节点；`B-7` 已修，再现即回归） | `batch3_views_internalization_2026-09-17.md §五` |
| 视图里出现**真源里没有的**数字 / 日期 / 公司名 | **真缺陷**（元断言覆盖构建/渲染源码；真源自身被污染时另需人工核） | 同上 §三 |
| `daily_page.run_summary.blocked` / `.gaps` 显示"（取不到）" | **设计如此**（`CheckRecord` 无此二字段，且 `state.json` 缺失 ⇒ 如实为空，不臆造） | `gap-check-record-lacks-blocked-and-gaps` |

---

## 八、★ 真缺陷候选（**不是**"设计上不做"，测试时请区别对待）

### 8.1 `prices` / `benchmarks` 没有生产写入方

| 项 | 内容 |
|---|---|
| **实测方法** | 全仓扫 `append_records(..., "prices"/"benchmarks")` 写入点 + 扫 `rules/` 计划清单 |
| **实测结果** | **除 `tests/` 外零写入点**（唯一的正式写入出现在 `tests/unit/test_schema_expand.py:627`）。`scripts/ingest/` 四件（`seed_industry_nodes` / `real_collector` / `public_fetcher` / `fetch_manifest`）**只处理文本**（sources / claims），**不碰行情** |
| **为什么是缺陷而不是设计留空** | 施工图 §1.3 把"取数"划为 **A 档 = 用 WorkBuddy（MCP 连接器）** —— 那是说**取数动作**由宿主做；但**「取到的行情 → `facts/prices.jsonl`」这一段落库**在源稿里是**核心主线的必需环节**（`N10.3-04` 同区间绝对/相对收益、`Ch3 §N3.4-06/07` 基准收益），**设计没有把它列为"首版不做"**，而是**没有任何实现** |
| **后果（实测）** | `daily/run.py` 的 `blocked=True` 里，**步骤 5/6 各 2 条 gap 全部**指向「`facts/benchmarks.jsonl` 或 `prices` 为空」⇒ **收益比较主线整条走不通**；`review_return` 永远停在 `blocked_by_no_price` / `blocked_by_no_benchmark`（即便 `p10` 冻结也一样） |
| **测试期怎么办** | 见 `test_run_sheet_batched.md` **批次 0**：在会话里用 MCP 连接器（`westock-mcp` / `pandadata` / `tdx-connector`）取数，再经 `schema.store.append_records` 落库。**★ 落库这一动作目前只能由 Agent 手工做，没有脚本** —— 这本身就是要向需求方/实现方提的那条缺口 |
| **建议** | 要么补一个 `scripts/ingest/market_data.py`（把连接器返回值映射成 `PriceSnapshot` / `Benchmark` 行），要么明确裁为"首版由 Agent 在会话内落库"。**在裁定前，不要把它当"设计如此"放过** |

