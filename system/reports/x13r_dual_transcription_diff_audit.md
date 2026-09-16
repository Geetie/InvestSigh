# 卡 13-R 两份独立转写的逐键对照审计

**作者**：`ws-schema-expand`（卡 13-R 的执行者之一）
**日期**：2026-09-16
**分支**：`ws/x13r-dual-diff-audit`（基点 `bb32863`）
**性质**：**事后独立复核**。不改任何已安装投入物（`rules/**` 对模型只读：0444 + SHA256 锁）。

---

## §0 本报告的缘起（为什么值得写）

卡 13-R（把设计里写死的 4 份规则内容逐字转写为可安装 YAML）**被并行做了两遍**：

| 版本 | 作者 | 分支 | 提交 | 归宿 |
|---|---|---|---|---|
| A（本报告作者） | `ws-schema-expand` | `ws/ch13r-rule-candidates` | `b2e269c` / `ad33a6d` | **未进 main** |
| B | `ws-ch2-rules` | `ws/ch2-rules` | `3e5bc27` / `77df944` | 经 `2b13cbf` 合并，由 `bb32863` 安装进 `rules/` |

**main 采用了 B**。这一点我如实接受 —— 而且对照结论显示 **B 在多处比 A 更忠实**（§3、§4）。

既然已经存在两份**互相独立**的转写，且设计原文唯一，那么"逐键对照 + 回原文裁决"就是一次**零边际成本的独立复核**：任何一方漏掉的设计 token，只要另一方抓到，就会被暴露出来。这正是项目铁律"声明与实现必须有机器绑定"在**转写质量**上的对应物 —— 只是这一次，机器绑定是"两份独立产出互为对照"。

**本报告的两个产出**：① 我的错（§3、§4）；② 已安装投入物里的一处真实缺陷（§5）。

---

## §1 先把事实钉死

### 1.1 扩张交付已在 main 生效（先纠正一条过时指令）

team-lead 本轮给过我一条指令「你还没开始，请现在开始执行 `facts/` 扩表 18 → 22」。**该指令已过时**：

```
$ ls -1 system/facts/*.jsonl | wc -l
22
$ git merge-base --is-ancestor 19379c7 HEAD && echo 在 main 上
在 main 上     # 19379c7 / a3f68b1 / 3a1aa62 / 83b55e0 全部在 main
```
`ef16a81` = `merge ws/schema-expand`。任务 #53 ~ #56 均 `completed`。**不需要重做，我也没有重做。**

### 1.2 13-R 的归属

```
$ git merge-base --is-ancestor b2e269c HEAD || echo 不在 main
不在 main
$ git merge-base --is-ancestor ad33a6d HEAD || echo 不在 main
不在 main
```

### 1.3 ★ 两条必须先说的纪律性结论

1. **我的旧分支 `ws/ch13r-rule-candidates` 不得整体合并。** 它含 `system/registry/rule-candidates/`（4 份 YAML）。而 `bb32863` 已把该目录 `git mv` 进 `rules/` 并删除，其提交信息明写目的是「**候选目录转为安装件（去双真源）**」。整体合并旧分支会把 `registry/rule-candidates/` **重新引入** ⇒ **重建刚刚被消除的双真源**。本报告因此**另开分支** `ws/x13r-dual-diff-audit`（基点 `bb32863`），只承载这一份报告。

2. **两份转写不是"同一份的两个措辞"，而是两套几乎不相交的结构。**

| 文件 | 共有叶子键 | 其中值相同 | 值不同 | 仅 A 有 | 仅 B 有 |
|---|---|---|---|---|---|
| `baseline.yaml` | 2 | 1 | 1（`spec_anchor`） | 53 | 39 |
| `metric-sets.yaml` | 46 | 44 | 2 | 1 | 47 |
| `scenario.yaml` | 2 | 1 | 1（`spec_anchor`） | 30 | 40 |
| `valuation-methods.yaml` | 2 | 2 | 0 | 45 | 29 |

⇒ **只有 `metric-sets.yaml` 是"同一结构的两版"（46 共有键）**，其余 3 份是两套独立结构 ⇒ 逐键对照在 3/4 份上必须**以设计原文为唯一裁判**，不能靠"键名相同"对齐。这本身就是一条关于"转写自由度"的发现：设计给的是**散文 + 表格 + 代码块**，两份转写各自选择了不同的承载结构，**都自洽，但都偏离了"同一份可机械比对的东西"**。

---

## §2 ★ 我自己的错误（先讲自己的，再讲别人的）

### 2.1 错 1（实质）：`min_nonnull_rate` 我落了 `tbd`，正确值是 `0.9`

**我写的**（分支 A）：`form_completeness.min_nonnull_rate: tbd` + `min_nonnull_rate_basis: "…具体值设计未给，需需求方拍板"`

**裁决依据** —— `00_待拍板项清单.md:47` 逐字：

```
| B5 | 形式完备性最低阈值 | **必填字段非空率 ≥ 90%**；**每条关键主张 ≥ 1 处原文定位**〔新给〕 | `04/02` J3 |
```

`:114` `| **D-03** | **A 档 9 项 + B 档 22 项的推荐值全部确认** | 2026-09-15 |`

⇒ **B5 是已确认项，值 0.9 逐字在案**。B 版落 `thresholds.min_nonnull_rate: 0.9` 是**对的**；我落 `tbd` 是**错的**。

**根因**：我做 13-R 时读了清单的 **B11/B13**，**没有读 B5/B6**。而 `bb32863` 的提交信息明写「阈值取值 ← `00_待拍板项清单` **B5/B6/D-03（已确认）**」—— B 查到了我没查的那两条。

**这不是判断分歧，是查得不够。** 同类项我一并复核（双方对照后一致，故无错）：

| 键 | 值 | 依据 | A / B |
|---|---|---|---|
| `max_primary_drivers_per_business` | `5` | `B6`「**5**（可配，超限分级）」 | 双方均 5 ✅ |
| `min_locator_count` | `1` | `B5`「每条关键主张 ≥ 1 处原文定位」 | 双方均 1 ✅ |
| `min_derivation_count` | `1` | `§J.3` 占位 + 参数化 | 双方均 1 ✅ |

### 2.2 错 2（实质）：`valuation-methods` 的 `method_class` 我做了**中 → 英译写**

**我写的**（分支 A）：`method_class: [normalized_earnings, reinvestment_cash_flow, segment_valuation, peer_comparison]`

**裁决依据** —— `05_价格与市场预期研究/02_实现方案.md:153-158` 逐字：

```
| `model_class` | `method_class` |
|---|---|
| hardware | 正常化利润 / 含再投资现金流 / 分部估值 / 同行比较 |
| cloud | 含再投资现金流（订阅/用量） + 分部 |
| software | 正常化利润 / 现金流 + 留存指标 |
| ETF（基准） | 简化底稿（E） |
```

⇒ **设计原文该表的值是中文**。我把它译成英文 token，**违反任务卡约束 1「逐字转写不得自创」**。B 版 `method_routing.hardware: ["正常化利润", …]` 是**逐字**的 ✅，且还逐条附了原文片段注释。

**根因**：我在 `metric-sets.yaml` 里看到的原文是**英文 token**（`04/02:129` `stages: [order, production_schedule, …]`），于是**默认全仓同风格**，把中文表也译成了英文。**逐字转写必须按各节原文自身的形态,不能跨节外推风格。**

### 2.3 附带：我的**内部不一致**（同一概念两个处理）

| 概念 | 我在 `metric-sets.yaml` | 我在 `valuation-methods.yaml` | B 版 |
|---|---|---|---|
| 未注册类型的 fallback 取值 | `model_class: tbd`（MS-GENERIC 条目） | `fallback_method_class: generic` | 两处均 `generic` |

我一边承认 `generic` 是合法取值，一边在 metric-sets 落 `tbd` ⇒ 违反 `R-15 ③`（一个概念一个取值/字段名）。

**裁决**：`04/02:164`「未注册类型 \| 归入 `MS-GENERIC` 并显式标注 `unregistered_model_class=true`」**未给 `generic` 一词**；但 `05/02:160`「未注册类型归入 **generic** 并标注」**逐字给了**。⇒ B 的 `generic` 有**跨章旁证**，我的 `tbd` 是严格保守。**这是可辩护的分歧，不是错**；但我**同一份交付里两种处理**是真问题。

### 2.4 我漏掉的（设计逐字给了 token，我一处没写）

**我完全没有写任何 `validator_ref` / `guard` / `entry` / `rollup`**。而设计**逐字给了文件名与函数名**：

| 设计出处 | 逐字内容 |
|---|---|
| `04/02:148-149` | `# scripts/valuelayer/route_guard.py` / `def validate_binding(business, metric_set):` |
| `04/02:208` | `def validate_driver_count(business, drivers, cfg):` |
| `04/02:361` | `# scripts/valuelayer/completeness.py` |
| `04/02:157` | `scripts/valuelayer/rollup.py` 只做分部→公司层加总 |
| `00_交付施工图.md:125-131` | 同名 6 个脚本逐条登记 |

⇒ B 版写 `validator_ref: validate_driver_count`、`guard: scripts/valuelayer/completeness.py`、`binding_guard.entry: validate_binding` **是设计逐字转写，不是编造**（我一度怀疑是悬空指针，核实后**推翻了自己的怀疑**：`04/02:148-149/208/361` 逐字在案）。

**但**：`scripts/valuelayer/` 目录**当前整体不存在**（`ls scripts/valuelayer/` → 不存在；13-A 在 `in_progress`）。`batch13_taskbook.md:10` 本就登记了这个前提。⇒ 这些 ref 是**忠实的前向引用**，缺的是"声明 ↔ 实现"的机器绑定 —— **这是批次编排的已知状态，不是 B 的错**。我在 §7 把它作为**风险**而非缺陷登记。

### 2.5 一处**沟通期误报**（已自查并当面向队友更正，此处留痕）

我在给 13-A（`ws-ch4-valuelayer`）的通报消息里写过一句：「`00_交付施工图.md:125-131` 列的是 6 个脚本，而 taskbook 的 13-A 清单也是 6 个 —— **两处对不上**（施工图有 `stage_derive` 无 `growth_quality`？请你自己核一下）」。

**这句话是错的。核实后**：两处 6 个脚本**完全相同**（`route_guard` / `rollup` / `growth_quality` / `moat_guard` / `state_machine` / `completeness`），`growth_quality.py` 在施工图 `:127` **有**。`stage_derive.py` 只出现在 `04/02:276` 的**设计正文**里，**不在本批次交付清单**中。

**根因（我自己的工具用法，不是文件问题）**：我用 `grep` 按 `scripts/valuelayer/` 这个**路径前缀**去挑施工图条目，而 `:129` 那行是「护城河/价格**硬隔离** + 断言（A1/A2/A3）」（同表里的检查器条目，**不含该路径前缀**）⇒ 没进结果集；我看到行号 125/126/127/128/130/131 **跳过了 129**，就**误以为缺了一行**。

**为什么这条要留痕**：本报告 §2.4 刚写过"我一度怀疑 B 是悬空指针，核实后推翻了自己的怀疑"，紧接着我就对**另一位队友**做了一次**未核实先下判词**的误报（虽然带了"请你自己核一下"的余地，但**错误的暗示本身就会让对方去查一个不存在的问题**）。⇒ 教训：**用 `grep` 按前缀挑清单时，必须先确认筛选模式不会漏掉同表中不带该前缀的合法条目；"行号跳号"是与"条目缺失"完全不同的两件事，不能互推。** 已向 `ws-ch4-valuelayer` 发出更正并收回该暗示。

---

## §3 ★ 已安装投入物里的一处真实缺陷（D1）：候选期元数据残留

### 3.1 现象（精确到行）

`system/rules/` 下**新装的 4 份文件**里，每一份都还写着**"我是候选、尚未安装"**，且带着安装期的元数据字段。以 `rules/valuation-methods.yaml` 为例：

```
:1   # rules/valuation-methods.yaml —— 估值方法按 `model_class` 路由（**候选**，尚未安装进 `rules/`）
:10  # ★ 本文件是**候选**（`system/registry/rule-candidates/`）：`rules/**` 是 0444 + SHA256 锁
:26  install_target: "rules/valuation-methods.yaml"
:27  install_note: "由主理人安装到 rules/valuation-methods.yaml 并跑 system/scripts/ops/lock_rules.py 重锁"
```

**4 份文件全部命中**，位置一致：

| 文件 | 自称"候选" | 指向已删除的 `rule-candidates/` | `install_target:` | `install_note:` |
|---|---|---|---|---|
| `rules/baseline.yaml` | `:1` | `:10` | `:27` | `:28` |
| `rules/metric-sets.yaml` | `:1` | `:9` | `:28` | `:29` |
| `rules/scenario.yaml` | `:1` | `:11` | `:27` | `:28` |
| `rules/valuation-methods.yaml` | `:1` | `:10` | `:26` | `:27` |

### 3.2 判据：这是异类，不是风格

既有 10 份 `rules/*.yaml` 的头部风格（`scope.yaml:1-6` / `notification.yaml:1-5`）：

```
# rules/scope.yaml —— 推荐范围声明（Ch3 §B-17 / §E）
#
# 权威出处：`Ch3 §B-17`（推荐范围声明）/ `Ch3 §E`（推荐范围与覆盖解耦）
#
# ★ 单一真源纪律：推荐范围的**值** = `rules/freeze.yaml::p03`（`recommended_security_scope`）。
#   本文件只声明**结构与解耦不变量**，不复制该值（防双写漂移）。
```

—— **没有**"候选"、**没有** `install_target`/`install_note`，只讲"本文件声明什么 + 权威出处 + 单一真源"。

机器判据（**可复现**）：

```
$ grep -lE "^install_target:" system/rules/*.yaml
system/rules/baseline.yaml
system/rules/metric-sets.yaml
system/rules/scenario.yaml
system/rules/valuation-methods.yaml
```

⇒ 14 份里**恰好这 4 份**。边界与"新装 4 份"完全重合。

### 3.3 为什么这是**真缺陷**（不是注释美化问题）

1. **声明与实现直接矛盾**。文件在 `rules/` 里、0444、已登记进 `rules.lock.json`（14/14），却自称"尚未安装进 `rules/`"、自称位于一个**已被删除**的目录。项目铁律"声明与实现必须有机器绑定"在这里是**反向命中**：存在一条**可被机器检出**的假声明，而**没有任何检查器去看它**。
2. **`install_note` 把已完成的动作写成待办**。字面是「**由主理人安装到** … **并跑** `lock_rules.py` **重锁**」—— 而 `bb32863` 已经做完了。下一个读者可能据此**重复安装**（`chmod -R u+w` → 覆盖 → 重锁），而该目录是 0444 **目的就是防写**。
3. **读者正是本批次的下游**。`batch13_taskbook.md:17` 明写 13-A「**只读** `rules/{metric-sets,baseline}.yaml`」。13-A/13-B 正在 `in_progress`。它们读到"本文件是候选，权威在 `system/registry/rule-candidates/`"，而该目录**不存在** ⇒ 要么去别处找权威版（找不到），要么怀疑手上的 `rules/` 版不是权威 ⇒ **把"哪个是真源"重新变成问题**，而这正是本次安装要消灭的问题。
4. **`bb32863` 的"去双真源"只完成了一半**。它消除了**目录层**双真源（删 `rule-candidates/`，git 记为 rename，provenance 保留在历史与报告 §2），但**没消除文件自我描述层**的残留 —— 4 份文件的正文仍在指认自己属于那个已删除的目录。

### 3.4 ★ 为什么门禁拦不住（实测，非推断）

我在**基于 `bb32863` 的真 git 隔离树**（`git worktree add --detach`，跑过 `bootstrap_worktree.sh`）上实测三个最相关的门禁：

```
== rules_lock_guard.py ==
  scanned files_on_disk: 14
  scanned registered_files: 14
RESULT: PASS（0 violations）

== no_placeholder_guard.py ==
  scanned files: 127
RESULT: PASS（0 violations）

== conflict_scan.py ==
  scanned l4_gate_files: 5
RESULT: PASS（0 violations）
```

**三个全 PASS。** 原因不是门禁写得不好，而是**它们的检对象不同**：

- `rules_lock_guard` 校验的是**文件 SHA256 与登记值一致**。`bb32863` 在安装后跑了 `lock_rules.py` 重锁 ⇒ 锁与当前内容**自洽**。**锁保证的是"没被改过"，不是"内容与自称一致"。**
- `no_placeholder_guard` 的 `DATA_PLACEHOLDER = 待填写|待补充|占位符|PLACEHOLDER` —— "候选"不在禁词内。
- `conflict_scan` 的 L3 只查 7 个**决策禁词**（`P-01/P-02` 族）在 `rules/`+`registry/` 的键名/标量值中的出现。

⇒ 这是一条**结构性盲区**：**内容语义层的错误，SHA256 锁在原理上无法发现**。这把项目铁律推到它的边界：**"有机器绑定"不等于"绑定覆盖了该错"** —— 锁抓篡改，抓不住"文件说自己没装"。

### 3.5 建议修复（**我不执行** —— `rules/` 对模型只读）

4 份文件各自：

- 第 1 行：删掉「（**候选**，尚未安装进 `rules/`）」，改为（与既有 10 份同风格）只留 `# rules/<name>.yaml —— <一句话职责>（<出处>）`
- 第 9/10/11 行：删掉「★ 本文件是**候选**（`system/registry/rule-candidates/`）…」整段
- 删 `install_target:` / `install_note:` 两个字段（保留 `spec_anchor` —— 那是出处，不是安装元数据）
- **保留**其余出处注释与单一真源纪律段（那部分是对的，`valuation-methods.yaml:17-21` 对 p05 的论证尤其扎实）

执行须按纪律 9/10 由**主理人**：`chmod -R u+w system/rules` → 改 → `python system/scripts/ops/lock_rules.py` 重锁 → 复跑 `rules_lock_guard`（应仍 14/14 PASS）。

---

## §4 B 版两处建议复核点（**只报差异 + 原文，不下判词**）

### 4.1 `conversion_chain_per_model_class.hardware` 合并了段

B 版：`hardware: '订单→排产/出货→验收→收入/回款'`（5 段）

设计原文 `04/02:129`：`stages: [order, production_schedule, shipment, acceptance, revenue, collection]`（**6 段**）

⇒ B 版把 `production_schedule`+`shipment` 合为「排产/出货」、`revenue`+`collection` 合为「收入/回款」，并译为中文。`N4.1-07`「硬件六段呈现且**不跳级**」是 P0 条目 ⇒ **"六段"这个数可能是有契约的**，合并为 5 段值得复核。

同理 `conversion_chain_per_model_class.cloud`（B 版 4 段中文）vs `04/02:134`（5 段英文 `[contract, energized, online, utilization, billing]`）；`software`（B 版 4 段）vs `:138`（5 段）。

**B 版无争议的部分**：`conversion_chain_generic_stages: [获取, 交付, 使用, 变现]` —— `04/02:108` 逐字「**转化链路分段模型**（通用四段，按商业模式实例化）：**获取 → 交付 → 使用 → 变现**」✅ 出处确凿。

### 4.2 `assumption_grid.risk_assumption` 的键名

B 版：`growth_assumption: '±1 个百分点'` / `margin_assumption: '±0.5'` / `risk_assumption: '±0.5'`

`00_待拍板项清单.md:60` B13 逐字：「**增长率 ±1 个百分点 / 利润率 ±0.5 / 折现率 ±0.5**」

⇒ **值逐字 ✅**（B 版保留了 `±` 与原单位，比我拆成 `step: 0.5` 更忠实 —— 我丢了 `±` 与"个百分点"，这是我第三处偏差）。但第三项原文是**折现率**，键名 `risk_assumption`（风险）与原文**不同名**。建议复核键名。

**B 版正确处**：`grid_search_upper_bound: tbd` —— B13 只给粒度、未给上界；`§I.2` 逐字「网格搜索上界（`rules/valuation-methods.yaml`）」⇒ `tbd` 合理 ✅。

---

## §5 剩余不确定性（我**没有**验证的）

1. **B 版其余键的出处我没逐条核。** 本报告只核了差异点和被我怀疑的点（`p05`、`validate_*`、`generic`、`conversion_chain`、B5/B13）。`ws_ch2_rules_report.md`（39524 字节，116 行对照表）我**没有逐行复核**。
2. **`risk_assumption` 的语义我没有裁决**（可能 B 把折现率归入"风险假设"大类，这是合理建模选择）。需设计方或 13-B 定。
3. **D1 的影响面我只论证、未实测**：我没有去改 `rules/` 验证"修完锁还 PASS"。修复由主理人执行时应复跑 `rules_lock_guard`。
4. **`p05` 我核了存在性**（`system/rules/freeze.yaml:202  - param_id: p05` ✅），但**未核 B 版附在 `scenario.yaml` 里的那段张力论证**（`scenario.yaml:49-51`，关于"§E.4/§J.5 未把某物写成 p05 取值"）的正确性。

---

## §6 给主理人的摘要

| # | 事项 | 性质 | 归属 | 建议 |
|---|---|---|---|---|
| 1 | `min_nonnull_rate` 应为 `0.9`（B5 已确认） | **我的错** | A | 无需动作（A 未合入；B 已是 0.9） |
| 2 | `method_class` 应为中文（§D.1 原表格） | **我的错** | A | 同上（B 已逐字） |
| 3 | `MS-GENERIC.model_class` 我内部不一致 | 我的问题 | A | 同上 |
| 4 | 我漏写全部 `validator_ref`/`guard`（设计逐字给了） | 我的漏项 | A | 同上 |
| 4b | 我在沟通中**误报**了一处"施工图与 taskbook 脚本清单对不上"（实为完全一致） | **我的沟通错误** | 沟通 | 已更正队友 + §2.5 留痕；根因是 `grep -` 路径前缀漏读了同表内不带前缀的条目 |
| 5 | **D1：4 份已安装 `rules/` 文件仍自称"候选/尚未安装" + `install_target`/`install_note`** | **真缺陷** | **投入物** | **建议修**（§3.5），主理人执行 |
| 6 | `conversion_chain_per_model_class` 6 段 → 5 段 + 译中 | 待复核 | 投入物 | 复核 `N4.1-07`「六段不跳级」是否约束 |
| 7 | `risk_assumption` 键名 vs 原文「折现率」 | 待复核 | 投入物 | 复核键名 |
| 8 | 我的旧分支 `ws/ch13r-rule-candidates` 若整体合入会**重建双真源** | **风险** | A | **建议废弃**，勿整体合入 |
| 9 | `rules/` 候选→安装是纯人工、无机器绑定（与 `G-13R-5` 同族） | 缺口 | 流程 | D1 即该缺口的实证：安装后无人清候选期元数据 |
