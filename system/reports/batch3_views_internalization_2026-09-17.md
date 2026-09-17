# 批次 III 收口报告 —— `views/`（三个阅读入口）构建与渲染的机制内化 + `B-7` 修复

> 承接 `implementation_plan_2026-09-17.md` 的**批次 II 剩余部分（`S-4`）**与 **`B-7`**（§7.3 已精确化）。
> 需求方 2026-09-17 指令：「把这些它运行时补的脚本的功能逻辑重写并内化到系统里固定下来。计划批准，开始执行。」
> 时效核对件：本报告读数取样于执行当时的 `main`；命令与判据见 §六（可复跑）。

---

## 一、一句话

**把"会话里临时写脚本拼三个阅读入口"这件事，变成了版本库里两条可复跑的命令**；
修掉了"公司页把**已被推翻的旧建议**当当前建议渲染"（`B-7`）；
并用一条**元断言**把"叙事重新写回代码"这条路封死 —— 该断言在本次执行中**当场抓出了它自己的一个漏洞**（§四）。

| 项 | 内容 |
|---|---|
| 新增 | `system/scripts/views/build.py`（构建）· `system/scripts/views/render.py`（渲染） |
| 承接自 | `.workbuddy/seed/build_views.py`（285 行）· `build_readable_views.py`（595 行）—— `gitignore` 内、**从不进版本库** |
| 唯一真源收敛 | `latest_version_row()` / `supersedes_map()` / `current_recommendation_row()` 新增于 `scripts/decision/rules.py`，**迁入**（原在 `trace/traceback.py` 私有）：消费方 3 处（`traceback` / `review_return` / `views.build`）共用 |
| 新增测试 | `tests/unit/test_views.py`（26 条）· `tests/decision/test_current_recommendation.py`（8 条） |
| 命令 | `python system/scripts/views/build.py system --run-date <日期> --check` → `python system/scripts/views/render.py system --run-date <日期>` |

---

## 二、等价比对：版本库机制 vs 会话脚本产物

**方法**（沿 `session-script-internalization` 技能）：**先统计"差异的字段种类"，再逐类归因** ——
不逐行看（差异点多、种类少）。脚本见 §六。

| 视图 | 差异字段种类 | 差异点 |
|---|---|---|
| `chain_map.json` | 1 | 1 |
| `company_pages.json` | 37 | 52 |
| `daily_page_2026-09-17.json` | 33 | 44 |
| **合计** | **71** | **97** |

**71 个种类全部可归因，无一类无法解释**：

| # | 差异类 | 条数 | 归因 |
|---|---|---|---|
| **A** | `current_recommendation.*`（`action`/`status`/`falsifiers`/`assumptions`/`evidence_gaps`/`verification_conditions`/`opportunity_types`/`supersedes`/`review_date`） | ~30 | **`B-7` 修复**：`buy(旧 v1)` → `pending`（`supersedes` 链末节点），并补齐该行自身的三要素 |
| **B** | `change_this_run.note` 删除 ×10 | 10 | **叙事外移**：原为写死句子（"本日新增 version=2…"），现由 `increment`/`version_kind` 派生、渲染层拼装 |
| **C** | `expanded.counter_evidence.source_row` / `history_versions[].baseline_id` 新增 | 12 | **新增出处标注**：修"同页不同源"（反证块属**基线**，与"建议反证"是两个对象，原先没标） |
| **D** | `superseded_recommendations` 新增（公司页） | 1 | **新增**：被取代的行**具名保留**（`Ch9 §3.4.2` / `N10.3-14`） |
| **E** | `data_gaps` | 3 处 | **派生替换写死**：`chain_map` 3→2 条（见下）；`company_pages`/`daily_page` 新增该键 |
| **F** | `run_summary.gaps` `8 → 10` | 1 | ★ **原写死的数与真源不符**（真源 `state.json` 实为 10） |
| **G** | `run_summary.signals_emitted` `1 → 0` | 1 | 真源最新回执是同日重跑后的 `check_2026-09-17_full_r1`（`signals_emitted=0`）；原写死 1 |
| **H** | `run_summary.note` | 1 | 派生文案（原为叙事）；现标出**读数来源**与"取不到"的字段 |
| **I** | `reviews_separated.*`（字符串 → 结构体） | 4 | **从 `eval_result` 真源派生**（原为三段写死文字） |
| **J** | `failed_research_tasks` → `failed_tasks`（改名 + 分类） | 1 | ★ **原标题与事实不符**：3 条失败行**全是**运行回执/降级标记，**一条研究任务都没有** |
| **K** | `important_information[*].discovery_note` → 区块级 `important_information_note` | 6 | **修渲染崩溃**：原实现从 `important_information[0]` 取 ⇒ **事件为空即 `IndexError`** |
| **L** | `stale_or_delayed_data` `True → False` | 2 | 派生自真源 `prices.delayed`（现全 `False`）；原写死"延迟 1 日" |
| **M** | `next_verification_nodes` 排序 + 新增 `recommendation_id` | 5 | 口径明确化（取**当前建议**的 `review_date`，而非基线 `expiry_review`）+ 排序稳定 |
| **N** | `recommendation_changes` 顺序（取代者在前）+ 新增 `first_seen_at` | 10 | **取代链两端都可见**的派生顺序；原为文件顺序 + 一条**写死 id** 的特殊捞取 |
| **O** | `unfinished_verification[].detail` 文字 | 1 | 机制统一反引号格式 |

### ★ `chain_map.data_gaps`：3 → 2 的**逐条**说明（不是"丢了内容"）

| 原会话脚本的 3 条 | 现机制 | 判定 |
|---|---|---|
| 「上游具名供应商未在本次取得的一手披露中点名」 | **不在**（属"披露是否充分"的**研究结论**） | ⇒ 该条已归**清单**（`research_ingest` 的 `tasks` 表，`research::` 行）；本树尚未声明 ⇒ 视图如实为空 |
| 「传导路径仅到 1 跳（库内 relations 仅 7 条且 NVDA 出边有限，2 跳及以上在库内不存在）」 | **不在**（派生值 = **2 跳**，故不成立） | ★ **原叙事已失真**：`nvidia→amd→anthropic` 就是 2 跳。写死的结论**没有跟着真源走** |
| 「价格隐含要求（反向估值）本轮 0 行」 | **不在**（`expectations` 本轮**非空**） | 同上，真源已变 |
| — | **新增**：空表扫描（`implied_requirements` / `dependency_edges` 0 行）× 2 | 机械可算，随真源自动更新；每条带 `source` |

⇒ 这一格最能说明内化的价值：**原来的 3 条里有 2 条已经与真源不符，而没有任何判据会因此变红。**

---

## 三、★ 核心判据：元断言 —— "叙事不得写回代码"

**这是本批次最重要的一条机器绑定**，也是"内化"这件事的**定义性判据**：

`tests/unit/test_views.py::test_no_narrative_literals_outside_docstrings`

```
AST 扫 `scripts/views/{build,render}.py` 的**非 docstring** 字符串字面量，
禁止出现：具体日期 / 具体财季 / 具体对象 id（sec-|company-|baseline-|rec-|dv-）/ 具体公司名
```

**为什么它必须有**（而不是"可有可无的洁癖"）：会话脚本把结论**写死在代码里** ——
`NOW = "2026-09-17T08:47:00Z"`、`blocked: True, gaps: 8`、三条 `data_gaps` 叙事、
`r["recommendation_id"] == "rec-sec-nvda-2026-08-03"`。换一天 / 换一家公司，
页面会**安静地显示旧事实**，而**没有任何判据会变红**。内化的目的就是让"会随真源变化的值"全部**算出来**。

### 该断言有牙齿（同一扫描器，跑在会话脚本 vs 新机制上）

| 文件 | 命中叙事字面量 |
|---|---|
| `.workbuddy/seed/build_views.py` | **7 处**（`2026-09-17` / `2026-09-17T08:47:00Z` / `2026-09-16` ×2 / `NVDA` ×2 …） |
| `.workbuddy/seed/build_readable_views.py` | **2 处**（`2026-09-17`，含 HTML 模板里那个） |
| `scripts/views/build.py` | **0** |
| `scripts/views/render.py` | **0** |

★ 只给 docstring 豁免（它解释**为什么**，必须能举例）—— 故按 AST **精确排除** docstring，
而不是"整文件 grep"（那会把解释性文字一起误杀，逼人写模糊的话，`G-27` 同族）。

---

## 四、★ 该元断言**当场抓出了它自己的一个漏洞**（本批次最值得记的一条）

我先写的是 `\b\d{4}-\d{2}-\d{2}\b`。反向对照 `test_meta_assertion_itself_discriminates`
往临时模块塞了会话脚本里**最典型的那一行**：

```python
NOW = "2026-09-17T08:47:00Z"
```

—— 结果**没命中**：日期后面紧跟 `T`（`17T`），两侧都是词字符 ⇒ `\b` **不成立** ⇒ 正则不匹配。
⇒ 若没有那条反向对照，**这条元断言会漏掉它最该抓的那一行**，而它自己一直是绿的。

**改正**：改用**前后否定环视**（`(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)`），并立即用同一扫描器
在新旧两批文件上复验（上表结果即改正后的读数）。

⇒ 印证本仓铁律：**"看起来在守"与"实际在守"必须用反向对照分开**（`G-05`）。

---

## 五、`B-7`：根因、修法与影响面

### 5.1 根因（实测精确化）

```python
# 原实现（.workbuddy/seed/build_views.py:41-45）
for r in recs:
    if cid not in cur_rec or (r.get("recorded_seq") or 0) > (cur_rec[cid].get("recorded_seq") or 0):
        cur_rec[cid] = r
```

真实数据里 NVIDIA 两行的 `recorded_seq` **都是 1** ⇒ `>` **从不成立** ⇒
取到**文件中第一条** = `rec-sec-nvda-2026-08-03`（v1、`buy`、依据是**已实现收益**）。

| | 旧（会话脚本） | 新（版本库机制） |
|---|---|---|
| `company_pages` → NVIDIA `current_recommendation` | `rec-sec-nvda-2026-08-03`　**buy / active**　`falsifiers=[]`　复查 `2026-09-16` | `rec-sec-nvda-***-session-review`　**pending / uncertain**　`falsifiers=3`　复查 `2026-11-25` |
| 同页 §八 的反证块 | 3 条（来自**取代它的那条**） | 3 条（同源，且标出 `source_row = baseline-nvda-001`，说明它属**基线**） |
| 读者看到 | **"买入 + 三条反证"** —— 已被评审推翻的建议被当"当前建议" | 一致：`pending` + 相应地反证 |

### 5.2 修法：**由关系决定，不由行的物理顺序决定**

新增 `rules.current_recommendation_row(rows)`：`supersedes_map()` → 取**没有被任何行取代**的那条
（链的末节点）；链分叉/成环时**回退**到版本水位并让调用方**具名报出**（`current_recommendation_multihead()`）。

★ **顺带收口一处同族缺陷**：`trace/traceback.py` 的 `_latest_version_row` 与 `review_return.py` 的
`_load_recommendation` 原先是**第二、第三份**"取当前版本"的实现；且 `traceback` 的
"按业务键分组 + 取水位最大"**靠 `>=` 恰好取到靠后那条**才对 —— 那是**物理顺序的巧合**，不是按语义选。
⇒ 三处收敛到 `decision/rules.py` 一份（`G-06`）。`traceback` 的同一处也改为
`current_recommendation_row` + 分叉具名报出。

### 5.3 影响面（**为什么这是老板会直接看到的错**）

公司研究页是三个阅读入口里**唯一给出"当前建议"的地方**；显示已被推翻的 `buy` ⇒ 读者据以行动。
本批次前，`daily_page`（5 条，含取代关系）与公司页 **NVIDIA 一家** 给出**互相矛盾**的读数。

---

## 六、复跑命令与验收读数

```bash
# 1) 构建（--check 就地跑展示层中立守卫，必须 0 违例）
python system/scripts/views/build.py system --run-date 2026-09-17 --check

# 2) 渲染（3 份人话 MD + 自包含 dashboard.html）
python system/scripts/views/render.py system --run-date 2026-09-17

# 3) 等价比对（差异种类 → 逐类归因）
python /tmp/roundtrip_views.py        # 见 §二；本次执行后已清理，重跑需按该思路重建
```

| 验证项 | 读数 |
|---|---|
| `run_all_gates` | 非零 **0** |
| `stage_gate --stage all` | **PASS（0 violations）** |
| `unit` | **268** passed（+26 本批次） |
| `decision` | **124** passed（+8 本批次） |
| `guards` | 155 · `daily` 70 · `injection` 7 片共 210 · `pricelayer` 202 · `valuelayer` 211 · `compute` 102 · `graph` 47 · `transmit` 29 · `evidence` 48 · `claim` 24 · `validators` 21 · `root` 8 · `conflict` 6 · `gates` 0 · `stage` PASS |
| `neutrality_check`（三份产物） | **0 violations**，且 5 条反向对照逐条判红 |

---

## 七、本批次**没做**的（如实登记，未自裁）

| 项 | 为什么没做 |
|---|---|
| **注册 `publish_hook`** | `rules/pipeline.yaml` 的 step 7 逐字 `implemented_in_first_version: false`（第八章交付）。且 `run_daily` **仅**在 `changed and not blocked` 时调它，实测 `blocked=True` ⇒ 注册了也不触发。**是否现在接线属裁定**（已登记 `gap-publish-hook-not-registered`） |
| `snapshots/` | 同属 step 7 的 `produces`，本次未涉及 |
| `B-2`（`dependency_edges` 写入方） | 原排期在批次 I 第 4 步，未做 |
| 批次 III（`B-9` 提问入口 / `B-10` 事件触发） | 未开始 |

**新登记缺口**（除上文两条）：

| id | 内容 |
|---|---|
| `gap-check-record-lacks-blocked-and-gaps` | `CheckRecord` **无** `blocked` / `gaps` 字段 ⇒ 这两个数只能来自运行态 `state.json`（**不在版本库**）。视图已在取不到时如实标 `null`，但"每天跑日报"的场景下若 `state.json` 丢失就看不到阻断状态。建议 `CheckRecord` 补两字段 |
| `gap-delayed-flag-all-false` | `facts/prices.jsonl` 160 行 `delayed` 全 `False`，而读数实为 09-16 收盘（读于 09-17）⇒ 二态字段表达力不足（与既有 `gap-delayed-bool-two-state` 同族，本次给出实测计数） |

---

## 八、给测试期的一句话速查（新增）

| 现象 | 归类 |
|---|---|
| 三个阅读入口由 `views/build.py` + `views/render.py` 产出，而 step 7 仍报 `deferred_by_design` | **设计如此**（机制在、编排钩子未注册，见 §七） |
| 公司页「当前建议」与 `daily_page` 的「建议变化」**不一致** | **真缺陷**（应为同一 `supersedes` 链末节点，本批次已修；再现即回归） |
| 公司页某区块的字段在真源某一行里**找不到** | **真缺陷**（"同页同源"约束，`current_recommendation` 全部字段取自同一 `recommendation_id`） |
| 视图里出现一个**真源里没有的数字/日期/公司名** | **真缺陷**（元断言覆盖构建/渲染的源码；但真源本身被污染时仍需人工核） |
| `daily_page.run_summary.blocked` / `.gaps` 显示"（取不到）" | **设计如此**（`CheckRecord` 无此二字段且 `state.json` 缺失，见 §七 `gap-check-record-lacks-blocked-and-gaps`） |
