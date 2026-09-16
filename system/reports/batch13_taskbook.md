# 批次 13 任务卡 · **阶段② `nvidia_sample` 主体并行开工**

> **为什么是现在**：阶段② 的**入口契约**刚刚就绪 —— `facts/` 18→22 已落地（`merge ws/schema-expand`）、
> `Baseline` 已补齐 `Ch4 §G.1` 六项深度所需字段（`business_refs[]` / `driver_refs[]` / `moat[]` /
> `valuation_inputs` / `valuation`），`baseline.driver_model` 已收窄为**由 `driver_refs[]` + `drivers.jsonl`
> 派生的假设投影**（带 `model_validator`：投影 ⊆ 引用）。此前 `Ch4 §G` 六项深度是**结构上不可达**的，
> 现在可达。
>
> **盘点**：`施工图 §2 阶段②` 点名 **16 个组件**，目前 **0 个已建**
> （`scripts/valuelayer/**`、`scripts/pricelayer/**` 两个包整体不存在；`rules/{metric-sets,baseline,valuation-methods,scenario}.yaml` 均不存在）。
> 本批次把它全部铺开，**三张卡并行**。

## 并行边界（**文件集互不相交**，这是能并行的前提）

| 卡 | 文件集 | 依赖 |
|---|---|---|
| **13-A Ch4 价值层** | `scripts/valuelayer/**` · `tests/valuelayer/**` · `verify.py::BATCHES` 加**一条** `valuelayer`（`V-06`）· `registry/criterion_counterexamples.yaml` 加**本卡自己那一条** `nvidia_sample::chapter4_g_depth` · 报告 | 只读 `rules/{metric-sets,baseline}.yaml` + `facts/{baselines,businesses,drivers}.jsonl` |
| **13-B Ch5 价格层** | `scripts/pricelayer/**` · `tests/pricelayer/**` · `verify.py::BATCHES` 加**一条** `pricelayer`（`V-06`）· 报告 | 只读 `rules/{valuation-methods,scenario}.yaml` + `facts/{prices,expectations,benchmarks}.jsonl` + `derived/`（Ch9 compute 已建） |
| **13-R 规则文件转写** | `system/registry/rule-candidates/*.yaml` · 报告 | 只读**设计区**（各章 `02_实现方案.md`） |

> ★ **本表的原始版本漏了两处共享文件的"限量授权"，与下方 DoD 自相矛盾**（`ws-ch2-rules` 独立复核时指出，
> 主理人确认**是我的缺陷**，`R8` 已更正）：
> 卡 13-A 的「接线要求」第 2 条与 DoD 第 3 条明文要求它登记反例，`V-06` 明文要求新测试目录同步加批次，
> 但上表只列了 `scripts/valuelayer/**` · `tests/valuelayer/**` · 报告 ⇒ **按表读就是"越界"，
> 按 DoD 读就是"必做"**。现值已补入，并把授权**收窄到"仅限本卡自己那一条"**：
> `verify.py` 只准加自己的批次条目（**不得动别家的，也不得改 `ORDER` 里别家的位置**），
> `criterion_counterexamples.yaml` 只准加自己的判据条目。跨卡冲突由主理人手工收（`R2` / `R3`）。
>
> ★ **一般化教训**：任务卡的「并行边界表」与「DoD」**必须同时更新**，否则边界表会被当作唯一的越界判据
> —— 而 DoD 里那些"必须改共享文件"的条目会**静默失效**（执行方按边界表自我审查，反而更守规矩）。
> 检查动作：新卡写完，**逐条把 DoD 里提到的每个文件回填进边界表**，少一个就是矛盾。

★ **`rules/**` 是 0444 + SHA256 锁（纪律 9/10），任何流都不得写。**
13-R 只产出**候选内容**到 `system/registry/rule-candidates/`；**由主理人**安装进 `rules/` 并跑
`lock_rules.py` 重锁。13-A/13-B 的**测试**一律在夹具副本里自备候选文件（夹具副本可写），
代码路径按 `rules/<name>.yaml` 读取 —— 安装由主理人在合并前完成。

## 三张卡的共同约束（**违反即返工**）

1. **设计是权威**：每条实现写清**节号锚点**（`Ch4 §C.2`），禁绝对行号。设计未写的**不得新增**；
   若认为设计有问题 → **停下、写清冲突双方节号 + 原文、报主理人**，不要自己改。
2. **判据鲁棒性**（`CONVENTIONS.md::R-06`）：可判定 + 穷尽；**禁关键词/名单式判据**；
   优先 **runtime-effect 断言**；allowlist > denylist；**每个守卫必须配可执行反例（会红）**。
3. **不许把"无被检对象"当"已验证"**（`G-03`）：空样本必须**显式记 note 并计数**。
4. **性能不退化**（`CONVENTIONS.md::P-*`）：AST 扫描单遍（禁对每个节点再 `ast.walk`）；
   配置读取走 `scripts/_common._cached_yaml()`，禁循环内读盘。
5. **向量/命名**：枚举 token **英文小写+下划线**；"待定"统一 `tbd`；
   **不许出现 `weight` / `score` / `vote`**（`P-09` / 纪律 1：参数与排序不得进决策函数）。
6. ★ **新增注入测试文件必须同时登记进 `verify.py` 的一片**（`injection-a..f`，每片 ≤32 例现算），
   否则 `test_shard_coverage.py` 的穷尽性断言会如实变红。**普通测试目录**新增则须同步 `verify.py::BATCHES`（`V-06`）。
7. ★ **在 worktree 里提交前先 `git merge main`**（拿排他会话锁 + 最新的 `facts/` 22 表 + `append_only_guard` 修复）。
8. **不要跑 `verify.py --batch <整目录>`**（单轮删除量可达 4.4 万项 ≫ 宿主阈值 9999）；
   要验证就**单文件**、分次。夹具已有排他会话锁（见到 `[V-05]` 即该工作树已有会话在跑）。
9. **提交**：只 add 自己改的文件（**禁 `git add -A`**）；`pre-commit` 必须全绿（**禁 `--no-verify`**）；
   报告给**实际命令输出 + 退出码** + commit hash + `git status --short`。
10. **产物语言/风格**照既有模块（docstring 写清"为什么这么做"与设计锚点）。

---

## 卡 13-A · Ch4 价值层（`scripts/valuelayer/**`）

**目标**：让 `Ch4 §G` 的**六项底稿深度**从"结构上可达"变成"**机器可校验**"。

**交付物**（逐个按 `施工图 §2 阶段②` 清单）：

| 文件 | 职责 | 设计锚点 |
|---|---|---|
| `scripts/valuelayer/route_guard.py` | 指标集绑定**防串味**（`MetricSetMismatch`） | `Ch4 §C` |
| `scripts/valuelayer/rollup.py` | 分部 → 公司层加总（**不跨业务混用语义**） | `Ch4 §C` |
| `scripts/valuelayer/growth_quality.py` | 增长质量 / ROIIC / **代价五类** + 收入增速 denylist | `Ch4 §D` |
| `scripts/valuelayer/moat_guard.py` | **护城河反误判** + 六保护对象 + 四类区分 | `Ch4 §F` |
| `scripts/valuelayer/state_machine.py` | 3×4 状态机 + 增量更新 + 无变化分支 | `Ch4 §E` |
| `scripts/valuelayer/completeness.py` | **形式完备性校验器**（`form_complete` 五项）+ gap 衔接 | `Ch4 §G.2/§G.3` |

★ **`completeness.py` 是本卡的核心**：`Ch4 §G.2` 逐字给了伪码
（`sections_nonempty` / `nonnull_rate >= cfg.min_nonnull_rate` / `has_locator >= 1` /
`has_derivation >= 1` / `cross_section_consistent`），**照它实现**，并**必须**：
- 五项**逐项**可判定、可定位（哪一项不过就报哪一项）；
- **`cfg` 的阈值只从 `rules/baseline.yaml` 读**（`Ch11 §D.2` 单一真源；**不得**在代码里内置阈值）；
- ★ 配**可执行反例**：构造"六项 section 齐备但内容空洞 / 无 locator / 无推导 / 跨节不一致"的 baseline
  ⇒ **必须逐条 exit 非零**；反向对照：真材实料的 baseline ⇒ 放行。
- ★ 且**必须挂进 `stage_gate` 的 `nvidia_sample::chapter4_g_depth` 判据**
  （见"接线要求"）。

**接线要求（本卡最容易被漏掉、也最容易被判 PARTIAL）**：
- 阶段② 现在有 **2 条判据未绑定**：`chapter4_g_depth`、`evidence_locatable`。
  → 本卡负责把 **`chapter4_g_depth` 真正绑进 `scripts/delivery/stage_gate.py::stage_nvidia_sample_passed()`**
  （函数体内写 `criterion("nvidia_sample","chapter4_g_depth", v)` + 真的调 `completeness.form_complete`）。
  ★ **`stage_gate.py` 是共享文件**：只准改**这一个函数体内**的这一处绑定；
  需要别处改动就**报主理人**。
- ★ **被判据有效性门禁约束**：`registry/criterion_counterexamples.yaml` 里必须有
  `nvidia_sample::chapter4_g_depth` 的 `counterexample` 条目，且**指向一个真实存在的测试**（`criterion_effectiveness_guard` 会 AST 校验）。
- 新模块**必须有生产调用方**（`§一 底线 2` 真接线）：至少 `chain_steps` 的 step 4（`revise_growth_and_moat`）
  或 step 3/5 能调到 `growth_quality` / `moat_guard` / `state_machine` 的确定性部分；
  **做不到就如实说清"接缝在哪、为什么现在接不上"**，不要留孤儿模块。

**测试**：`tests/valuelayer/`（**新目录 ⇒ 必须同步在 `verify.py::BATCHES` 加一批**，`V-06`）。
含正/反向、边界（空 baselines、缺 driver_refs、未盈利公司走 `Ch4 §G.4` 分支）。

**判定标准（DoD）**：
- [ ] 6 个模块建成，`import` 可跑，无 `pass`/`NotImplementedError`/假数据
- [ ] `completeness` 五项**逐项**有正反用例；阈值**只**来自 `rules/baseline.yaml`
- [ ] `chapter4_g_depth` **已在 `stage_gate` 函数体内绑定**且**有反例登记**，门禁实测能被击穿
- [ ] 每个守卫**注入违例 → exit 非零**（贴真实输出）
- [ ] `tests/valuelayer` 全绿；`run_all_gates` 无新增非零项
- [ ] 报告：改了什么 / 真实输出+退出码 / 每条 DoD 的证据 / 剩余不确定性与缺口

---

## 卡 13-B · Ch5 价格层（`scripts/pricelayer/**`）

**目标**：把"价格隐含的要求"做成**可复查的多解集**，并守住**顺序**与**非上市/历史外推**两类误判。

| 文件 | 职责 | 设计锚点 |
|---|---|---|
| `scripts/pricelayer/solver.py` | **反向求解**：固定 4 类解第 5 类，产出**解集 + 区间 + 替代解释** | `Ch5 §B` |
| `scripts/pricelayer/valuation.py` | 估值计算 + 方法按 `model_class` 路由 + `DerivedValue` 追溯链 | `Ch5 §D` |
| `scripts/pricelayer/order_guard.py` | 顺序约束 + **倒填检测四规则** | `Ch5 §D` |
| `scripts/pricelayer/scenario_guard.py` | 情景一致性 + **`probability` 默认 `null`** | `Ch5 §E` |
| `scripts/pricelayer/history_guard.py` | AGIX 底稿 + 非上市资产 + **历史外推检测** | `Ch5 §E` |
| `scripts/pricelayer/daily_explain.py` | 每日解释：行情口径校验 + 三分类 + 因果链 | `Ch5 §F` |

★ **`solver.py` 的核心约束（`Ch5 §B.1` 逐字）**：`P = f(g,m,r,k,T)` 是**欠定方程** ⇒
**必须展示多组解**，否则会把某一解误当"市场的唯一真相"。产出落 `facts/implied_requirements.jsonl`
（**已建，22 表之一**，字段照 `Ch5 §B.2` 的 JSON 结构逐字）。
- **模型不做算术、程序不做假设**（`Ch5 §B.3` 的责任分工）：假设由**模型**给（本卡不做），
  求解由**程序**做 ⇒ 本卡的入参是"候选假设组合"，出参是"解集 + 区间 + 替代解释"。
- ★ **`probability` 默认 `null`**（`Ch5 §E`）：**不得**给个默认概率糊过去。

★ **`order_guard.py` 的"倒填检测四规则"**：`Ch5 §D` 有逐字四规则，且 `Ch5 §118` 明确
"构造一个 `source=implied_solution` 的假设写入 `baselines.driver_model` → 断言被 `OrderViolation` 拒绝；
反解输出**只允许**写 `implied_requirements` 或 `gap`" ⇒ **照它写反例**。

**测试**：`tests/pricelayer/`（**新目录 ⇒ 同步 `verify.py::BATCHES` 加一批**）。

**判定标准（DoD）**：
- [ ] 6 个模块建成；`solver` 产出**多组解**（不是单解）、含**区间**与**替代解释**
- [ ] `order_guard` 四规则逐条有正反用例；倒填被拒（贴真实输出）
- [ ] `scenario_guard`：`probability` 缺省 = `null`（有断言）；情景不一致被拒
- [ ] `valuation` 的方法路由**只**读 `rules/valuation-methods.yaml`；`DerivedValue` 追溯链可追（`operand` 可达）
- [ ] 每个守卫**注入违例 → exit 非零**
- [ ] `tests/pricelayer` 全绿；`run_all_gates` 无新增非零项
- [ ] 报告四段式同上

---

## 卡 13-R · 4 个规则文件的内容转写（`system/registry/rule-candidates/**`）

**目标**：把设计里已经写死的 4 份规则内容**逐字转写**成可安装的 YAML 候选，交主理人安装 + 重锁。

| 候选 | 出处（**逐字读**） | 要点 |
|---|---|---|
| `rule-candidates/metric-sets.yaml` | `04_公司价值研究与深度标准/02_实现方案.md` **§C** | 指标集注册表：**硬件六段 / 云五段 / 软件五段** + `model_class` 路由 + `MS-GENERIC` 兜底 + `unregistered_model_class` 标注 |
| `rule-candidates/baseline.yaml` | 同文件 **§B/§G** | `max_primary_drivers_per_business`、`min_nonnull_rate` 等**阈值参数化**；未定的值写 `tbd` 并给 `basis` |
| `rule-candidates/valuation-methods.yaml` | `05_价格与市场预期研究/02_实现方案.md` **§D** | 方法按 `model_class` 路由表 |
| `rule-candidates/scenario.yaml` | 同文件 **§E** | 情景定义 + `scenario_method_status` |

**硬约束**：
- ★ **只写 `system/registry/rule-candidates/`，绝不写 `system/rules/`**（0444 + SHA256 锁，纪律 9/10）。
- ★ **逐字转写，不得自创**：每个键都要能指出设计出处（节号 + 原文片段）；
  设计没给的值 ⇒ 写 `tbd` + `basis`（建议来源），**不得编数**。
- ★ 每个文件头注明：`spec_anchor`（节号）、`install_target`（`rules/<name>.yaml`）、
  `install_note`（"由主理人安装并跑 `lock_rules.py` 重锁"）。
- ★ 交付一张**逐键对照表**：`键 → 取值 → 设计出处（节号+原文片段）`，让主理人能逐条核。
- ★ 若某处**设计根本没写**（例如阈值具体值）⇒ 如实标注"设计未给，需需求方拍板"，
  **不要**从别处抄一个数来填空。

**判定标准（DoD）**：
- [ ] 4 个候选文件齐备，YAML 可解析（贴 `yaml.safe_load` 实测）
- [ ] 逐键对照表齐备；`tbd` 项与"设计未给"项**分开列**
- [ ] 与现有 `rules/*.yaml` 的**风格一致**（照抄它们的头部注释格式与字段命名）
- [ ] 报告四段式 + `rules/` **零改动**（贴 `git status --short system/rules`）

---

## 合并顺序（主理人）

1. 13-R 报告到达 → **主理人**安装 4 份候选进 `rules/` + `chmod u+w rules && python scripts/ops/lock_rules.py` → 核 `rules_lock_guard` 绿。
2. 13-A / 13-B 报告到达 → 核 diff（三点 diff + 试合并）→ 合并 → **实测**：新增测试目录已入批次、`stage_gate --stage nvidia_sample` 的判据数变化、无新增非零门禁项。
3. 合并后开**批次 14 独立审计**（换人复核，含"判据真的会拦"的反例复核）。

---

## ★ 主理人裁定（批次 13 执行期，逐条留痕）

> 裁定时间：13-R 已安装并重锁（`bb32863` → `0f618a9`）、13-A/13-B 仍在各自工作树内。

### R1 · `ws/ch13r-rule-candidates` **废弃 · 禁止合并**（副产物为 `ws/x13r-dual-diff-audit`）

`b2e269c` / `ad33a6d` 两个 commit 把 4 份规则候选写进 `system/registry/rule-candidates/`。该目录在
`bb32863` 里已**转为安装件并清除**（`rules/` 成为唯一真源）。若合并该分支，`registry/rule-candidates/`
会**复活成第二份真源** ⇒ 违反 `G-06`。
**处置**：分支**保留不删**（留痕），**永不合并**。审计产物已走 `ws/x13r-dual-diff-audit`（`9540e5f`）。

### R2 · `verify.py` 双侧改动 ⇒ 冲突由**主理人**手工收

13-A 需加 `valuelayer` 批次（`V-06`），13-B 已加 `pricelayer` 批次（`BATCHES` 条目 + `ORDER` 一行）。
两侧都改同一处必然冲突。**已明令 13-A 只加自己那条、不动 `pricelayer`**；合并冲突由主理人裁。
★ 之所以允许多方改 `verify.py` 而不是收归主理人独写：`V-06` 要求"新增测试目录**同时**加批次"，
若主理人代劳，测试目录与批次的登记就会**跨人手脱节**（这正是 `G-28` 的成因）。冲突面小、收益大。

### R3 · `stage_gate.py` 三方改动面 ⇒ 合并后**必须**重跑判据有效性门禁

同一文件三条流各改一处，落在**不同函数**：

| 流 | 改动点 | 函数 |
|---|---|---|
| 13-A | 新增 `criterion("nvidia_sample","chapter4_g_depth", v)` + 调 `valuelayer.completeness.g_depth_violations` | `stage_nvidia_sample_passed` |
| `ws-criterion-effectiveness` | `G9-1` 补 `task_state_auditable` 真检查 | `stage_daily_run_passed` |
| `ws-degrade-contract` | `G-43`/`G-45` 降级契约 | `stage_daily_run_passed` |

⇒ 13-A 与 criterion-effectiveness 改动点相隔约 60 行、**函数不相交**（可自动合并）；
但 criterion-effectiveness 与 degrade-contract **同改 `stage_daily_run_passed`** ⇒ **必然要人工核对**。
★ 且 13-A **新增了一条绑定判据** ⇒ 合并后 `criterion_effectiveness_guard` 会要求它有登记。
**合并后必跑**：`python scripts/checks/criterion_effectiveness_guard.py`，不绿不许进批次 14 审计。

### R4 · 13-A 的两项 DoD 缺口（巡检发现，已回单）

1. `registry/criterion_counterexamples.yaml` **无** `nvidia_sample::chapter4_g_depth` 条目（实测 `git status` 无该文件、grep 零命中）；
2. `verify.py::BATCHES` **无** `valuelayer` 批次。
⇒ 已在巡检中明令补齐，且**不得**碰 `pricelayer`（见 R2）。

### R5 · `ws-schema-expand` 的 13-pre / 13-post **顺序修订**

原计划「13-pre 键对齐守卫」在本时点**结构性不可执行**：被检对象（`scripts/valuelayer/**`、
`scripts/pricelayer/**`）都在**未合并分支**上，`main` 里不存在 ⇒ AST 抽不出读键。
按 `G-03`「无被检对象 ≠ 已验证」，**拒绝执行是正确的**（该流自己的判断，保留）。
**修订后顺序**：`(D) Valuation 3 字段` → 13-A/13-B 合并 → **13-pre**（键对齐守卫：AST 抽代码实际读取键
↔ `rules/*.yaml` 实有键，**单向缺失即红**）→ **13-post**（全消费面复核 + 硬编码阈值扫描）。

### R6 · `ws-degrade-contract` 改动面复核结论：**全部在界内**（主理人先前的越界疑虑撤回）

5 个 commit 涉 8 文件，逐项核对：
- 界内本体：`scripts/daily/degrade.py` · `delivery/stage_gate.py` · `orchestrate/pipeline.py` · `tests/conftest.py` · `tests/daily/test_daily_run.py`
- `tests/injection/test_criterion_effectiveness.py`：**在界内** —— 把 `degrade_keeps_last_valid` 的反例由手工拼行
  改为 `write_check_records()` 真实写路径 + 对真实行定向违约注入。这正是「夹具与真形状同源（`G-06`）」的修复**本身**。
- `tests/injection/test_wiring_guards.py`：**在界内** —— 同理，`_check_task()` 那个"生产代码从未写出过的形状"
  （`status=done` + `output_refs=["rec-nvda-001"]`）换成唯一写入方。
★ 教训留痕：**我一度把"改了相邻测试文件"当成越界**，实际是"修复必须改到那个测试"。判越界前先看
**改动内容的因果方向**（是"顺手改"还是"不改就修不干净"），不要只看文件名。

### R7 · 阶段② 第 4 条判据 `evidence_locatable` **此前无人认领** ⇒ 立卡 13-C

任务卡原只把 `chapter4_g_depth` 派给 13-A（卡 13-A「接线要求」只写了那一条），
`evidence_locatable` **没有 owner**。实测门禁把它如实暴露成 FATAL：

```
note: 判据台账[nvidia_sample]：函数体内已绑定 2 条，声明为 automated 但未绑定 2 条 → ['chapter4_g_depth', 'evidence_locatable']
[FATAL] G11-04[nvidia_sample] @ scripts/delivery/stage_gate.py::stage_nvidia_sample_passed:0
        — 阶段 nvidia_sample 的判据 'evidence_locatable' 已在 registry/delivery.yaml 声明为 automated，
          但 stage_nvidia_sample_passed() 函数体内无对应 criterion() 声明 → 不得据此判 PASS（静默漏判据）
```

★ **为什么这条必须单独立卡**：`scripts/validators/locator_check.py`（`Ch6 §D`）**早就建好、测过、且已注册进
`run_all_gates` + `pre-commit`**，甚至已被 `chain_steps.py:92` 调用 —— 但**阶段②门禁的 `criterion()` 绑定**
这一行从未写。这正是铁律 1「只建模块、不接线 = 未完成」的教科书形态：**实现齐备而判据空绑**，
前置产物齐备时该阶段会直接 FATAL。

（`ws-schema-expand` 的 13-pre「键对齐守卫」只覆盖"代码读的键 ↔ `rules/` 有的键"，
**不覆盖"判据是否绑定"** —— 两条检查口径不同，不能互相顶替。）

---

## 卡 13-C · 阶段② `evidence_locatable` 接线（**新立**）

**工作树**：`.worktrees/ws-evidence-locatable` · 分支 `ws/evidence-locatable`（主理人已建 + 已 `bootstrap_worktree.sh`）

**目标**：把阶段② 第 4 条判据 `evidence_locatable`（`registry/delivery.yaml:56-58` · statement「证据可定位（Ch6 §D）」·
`check_kind: automated`）**真正绑进** `stage_nvidia_sample_passed()`，消灭 `G11-04` FATAL。

**现状（实测，不是推测）**：

| 事实 | 证据 |
|---|---|
| 阶段② 现绑 2 条，缺 2 条 | `criteria_bound` 台账：`['chapter4_g_depth', 'evidence_locatable']` 未绑 |
| `chapter4_g_depth` 归 **13-A**（另一分支） | 卡 13-A「接线要求」第 1 条 ⇒ **本卡不碰** |
| `evidence_locatable` 的实现**已存在** | `scripts/validators/locator_check.py`（8 条可判定判据 · `run_checker` CLI `0/1/2`） |
| 已被门禁注册 | `run_all_gates.py` + `ops/pre-commit.sh` 均有 |
| 已有生产调用方 | `scripts/orchestrate/chain_steps.py:92` `from scripts.validators.locator_check import check as locator_check` |
| 已有 18 例测试 | `tests/validators/test_locator_check.py` |

★ **`G-06` 唯一真源：一律复用，禁重建第二套定位校验。** 本卡**不新增任何校验逻辑**，
只做「接线 + 反例登记 + 拆一颗测试雷」。

**交付物**：

1. `scripts/delivery/stage_gate.py::stage_nvidia_sample_passed()` 函数体内，加
   `from scripts.validators.locator_check import check as locator_check`（**就地导入**，与既有
   `from scripts.trace.traceback import check as trace_check` 同款）+ `report = locator_check(root)`
   + `v += report.violations` + `criterion("nvidia_sample", "evidence_locatable", v)`。
   - ★ **只准改这一个函数体**。别处要改 → **先报主理人**。
   - ★ **插入位置**：放在 `criterion("nvidia_sample", "derivation_reviewable", v)` **之后**、
     `v += assert_criteria_implemented(root, "nvidia_sample")` **之前**。
     理由：13-A 在同一函数体加 `chapter4_g_depth`，锚点在 `six_step_chain_complete` **之前**；
     两侧错开放置可让 git 的 hunk 尽量不重叠。**若仍冲突，由主理人手工收，不用你处理**。
2. `registry/criterion_counterexamples.yaml` 加 `stage: nvidia_sample` / `criterion_id: evidence_locatable`
   的 `kind: counterexample` 条目：`blocked_hint` 取 `locator_check` 里该判据的**专属**字样
   （如 `LOCATOR_MISSING`），`test` 指向一个**真实存在**且函数名**含 `evidence_locatable`** 的测试。
3. 该测试（建议落 `tests/injection/test_criterion_effectiveness.py`）：
   - **违约输入** ⇒ 阶段② `exit != 0` **且** 输出含 `blocked_hint`（`§5.1 AC-04`）；
   - **反向对照** ⇒ 合规输入下该阶段 `exit 0` **且该字样不出现**（证明红是这条判据干的，
     不是别的判据顺带变红）。
4. ★★ **顺手拆一颗雷（本卡独有，最容易漏）**：
   `tests/injection/test_criterion_effectiveness.py::test_registry_entry_for_unbound_criterion_makes_guard_fail`
   （约 L602-623）**把 `evidence_locatable` 硬编码成"未绑定判据"的样本**（它 append 一条该 id 的登记，
   断言守卫报 `未被绑定`）。**你一绑上它，这个前提就消失了** ⇒ 该用例会红（或退化成空转）。
   **必须一并改**：把探针改成**不依赖任何具体判据名**的形式 ——
   要么从守卫**自己的诊断输出**里取一个当前确实未绑定的 id，要么用一个只存在于夹具
   `delivery.yaml` 里的**假 id**。
   ★ 这正是 `R-06`「禁关键词/名单式判据」在**测试**上的同款毛病：**硬编码一个会变化的名单成员**。
   改完请在该用例 docstring 写清"为什么不写死判据名"。
5. 提交前 `git merge main`（拿排他会话锁 + `facts/` 22 表 + `append_only_guard` 修复）。

**DoD**：

- [ ] `evidence_locatable` 已在 `stage_nvidia_sample_passed()` 函数体内绑定，且**真的调用** `locator_check`
- [ ] `criterion_counterexamples.yaml` 有对应条目，指向真实测试、函数名含判据 id
- [ ] 违约输入 ⇒ 阶段② 非零 + 专属 `blocked_hint`；合规输入 ⇒ 阶段② 零 + 无该字样（**两次真实输出**）
- [ ] `criterion_effectiveness_guard`：`criteria_without_counterexample` 由 **1 → 0**
- [ ] `stage_gate` 台账：`nvidia_sample` 未绑定判据由 **2 → 1**（只剩 13-A 的 `chapter4_g_depth`）
- [ ] `test_registry_entry_for_unbound_criterion_makes_guard_fail` 已去硬编码，且仍**真能拦**（贴改后实测）
- [ ] 报告四段式：改了什么 / 真实命令输出 + 退出码 / 每条 DoD 证据 / 剩余不确定性
- [ ] 提交只 `add` 自己改的文件（**禁 `git add -A`**），`pre-commit` 全绿（**禁 `--no-verify`**）

★ **不要跑 `verify.py --batch <整目录>`**（`V-08` 删除配额）；单文件、分次。注入测试在 `injection-a..f` 分片里，
跑单文件即可。

---

### R8 · 规则消费面复核（`ws/ch2-rules`，卡 13 延伸）—— 三条裁定

`ws/ch2-rules` 在 13-R 安装后做了**独立复核**，指出三处。**三处的性质各不相同，逐条裁**：

#### R8-1 · `rules/baseline.yaml` 的**深度契约**：`thresholds.*` 分组 **维持为准**

**事实（我逐条实测，非采信）**：

| 事实 | 证据 |
|---|---|
| 设计写 `rules/baseline.yaml: max_primary_drivers_per_business` | `04/02:203`（`file:key` 记法） |
| 同一设计写 `cfg.max_…` / `cfg.min_nonnull_rate`（**扁平属性访问**） | `04/02:210` / `04/02:364` |
| 设计**全文无** `thresholds` 一词 | 全文检索零命中 |
| 存量 10 件规则文件**全部**分组包裹 | 我实跑 `yaml.safe_load` 列顶层键：`banned_tokens` / `benchmark` / `data-sources.allowlist` / `freeze` / `notification` / `pipeline` / `publish` / `review` / `schedule` / `scope` —— 10/10 均为"元数据 + 关注面分组" |
| **同源先例 2 例** | ① 设计 `08/02:239` 写 `schedule.yaml:trading_calendar`，实装在 `cadence.timezone` 下，按 `schedule.yaml::cadence.timezone` 读；② 设计写 `freeze.yaml::freeze_param`（单数），实装顶层键是 `freeze_params`（复数） |

**裁定：维持已安装件的 `thresholds.*` 分组为准。** 四条理由：

1. **`G-06` 唯一真源 + 已安装件是唯一被锁的产物体**（0444 + SHA256 + `rules_lock_guard`）。
   为改深度而重录 4 份设计文档 + 重锁 14 件，**语义收益为零**（两种读法能表达的完全一样）。
2. **"设计 `file:key` 记法不锁深度"已是项目既成契约**：10/10 存量件分组 + 2 例同源先例。
   这不是"我们跟设计不一致"，而是**设计本就没写深度，深度由安装件填**。
3. **设计 `cfg.X` 与 `thresholds` 分组不矛盾**：把 `cfg` 读作 `baseline["thresholds"]` 即两立。
   ⇒ 这**不是**"设计 vs 实现"的冲突，而是**设计留白**，留白归安装件。
4. **分组本身更优**：`baseline.yaml` 顶层有 6 个互不相干的关注面
   （`thresholds` / `driver_overflow_policy` / `driver_duration` / `form_completeness` /
   `required_extra_fields_by_profitability` / `segment_evidence`），摊平会有键语义混淆风险。

⇒ **13-A / 13-B 一律按 `rules/*.yaml` 实有结构读**；`cfg` = `baseline["thresholds"]`。
⇒ ★ **并且必须把这个留白显式写下来**（否则下一个人还会再问一遍）：已在 `rules/baseline.yaml`
头部加"深度约定"段（主理人改 + 重锁），并在本卡留痕（本条）。

#### R8-2 · 13-A 的**共享文件授权**：任务卡「并行边界表」与 DoD 自相矛盾 —— **我的缺陷，已更正**

`ws/ch2-rules` 指出"13-A 允许面不含 `verify.py` / `registry/`"⇒ 无权自修。
**结论对，归因要引对一手证据**：`PROGRESS.md:228` 那条"派单疏漏"说的是**另一件事**
（批次只加在 `main`/`integration`、没进 WS 工作区），**不是**本条。
本条的一手依据是**卡 13-A 自身**：line 85（`V-06` 必加批次）+ DoD 第 3 条（必登记反例）
与「并行边界表」（只列 `scripts/valuelayer/**` · `tests/valuelayer/**` · 报告）**互相矛盾**。
⇒ **我已按 `R8-2` 修表**（见本文开头边界表下的更正说明），并把授权**收窄到"仅限本卡自己那一条"**。
⇒ 13-A 已获明令：`verify.py` 只加 `valuelayer` 条目、**不得动 `pricelayer`**（`R2`）。

#### R8-3 · 13-B 的三个常量：不是"留在代码"，而是"**参数进 `rules/`、护栏留代码**"

`ws/ch2-rules` 报告：13-B 有 `DEFAULT_DISPLAY_CAP=3` / `MAX_DISPLAY_CAP=5` / `DEFAULT_MIN_SOLUTIONS=2`；
并引我的话"'不收进 rules' ≠ '写进代码'"。

> ★★ **订正（`ws-ch2-rules` 自曝，主理人采纳）**：本段原写「两个常量…（`grep` 零引用 = 死常量）」——
> **该判定是假阴性**：`ws-ch2-rules` 第二次踩了 BSD `grep` **不支持 `\|` 交替**的坑，`grep -rn 'A\|B\|C'` 返回 `exit=1`。
> 实测三个常量**全在决策路径**（`solver.py:318` 默认参数 / `:336` 越界 `raise` / `:391` 置 `degraded` /
> `:403` 呈现前不变式 / `:503` `check()` 产 `Violation`）⇒ 它们在**装 `rules/` 之前就已经在影响产出**，
> 所以**不是**"死常量"，而是**"活参数住错了地方"**。档位由「不好/不够」**上调为「错」**。
> ★ 主理人留痕：**本段先前照抄了该流的假阴性**，且该假阴性是在**我自己的裁定文本里**被引用的 ——
> 教训：**裁定文本引用下级的 `grep` 结果前，要么自己复跑、要么注明"未复核"**。

★ **它引用得对，但推出的结论我推翻。** 我当时判"暂不收进 `rules/`"的**前提**是
**没有键名、没有指派文件**；现在前提没了 —— `05/02:460` 是 `§J.3` 本体，`00_待拍板项清单.md` **B18**（出处栏 = `05/02` J3）已拍板：
「估值解集展示上限 `N` = **默认展示 3 组，最多 5 组**〔新给〕」。
⇒ 条件变了，裁定随之改变：**必须进 `rules/`**。

**先给一条可复用的统一判据**（免得每件重新吵）：

> **"影响产出取值/选择"的数 = 参数 ⇒ 必须住 `rules/`（`Ch11 §D.2` 单一真源 + `P-09`）；**
> **"仅为防组合爆炸/防卡死的上界" = 护栏 ⇒ 可住代码，但必须在 docstring 明标为护栏。**

★ **补充条款 ③（`R11`，`ws-ch2-rules` 提出，主理人采纳）—— 防"把设计逐字值误判成自创参数"**：

> **若"设计把该值逐字写在实现伪码里"且"设计未指派参数化"，则照设计落值 = 转写，不是自创参数，可留代码。**
> **两个条件必须同时成立**，且**代码必须在 docstring 标出该设计锚点**；只要缺一条（值不在伪码里 / 设计明说"参数化 `rules/…`"）⇒ 仍按统一判据办。

**实例（`ws-ch2-rules` 判、主理人确认）：`scripts/valuelayer/moat_guard.py:19` 的 `len(kinds) >= 2`**
- 出处：`04_公司价值研究与深度标准/02_实现方案.md:311`（`§F.2` 代码块**逐字**）`and len(kinds) >= 2   # 需证据组合（≥2 类）`
- 设计**没有**要求"参数化到 `rules/`"（对照 `§J.2` 明写「参数化 `rules/valuation-methods.yaml`」）
⇒ **判"不是违规"**：这是**照设计落值**。★ 同样一个 `2`，两种判词，**差别只在"设计有没有指派参数化"** —— 这正是本条判据要守住的分界。
★ **反例护栏（防漏洞）**：若某值**不在设计伪码里**、设计也没说参数化 ⇒ 那是**自创**，必须报错而不是"留代码"。

按此判据逐条落（★ 落点已更正为 **`rules/valuation-methods.yaml`**，见下）：

| 常量 | 判定 | 处置 |
|---|---|---|
| `DEFAULT_DISPLAY_CAP=3` | **参数**（决定"展示哪几组解"，直接改变产出） | **已落** `rules/valuation-methods.yaml::solution_set_display.default_count = 3`（`182f8a1`），`basis` 记 B18 |
| `MAX_DISPLAY_CAP=5` | **参数**（同上） | **已落** 同件 `max_count = 5` |
| `DEFAULT_MIN_SOLUTIONS=2` | ★ **设计无字面 2** —— 但 `§B.1` 有**语义**出处（逐字「一个 P 对应**无穷多组**解。故**必须展示多组解**」） | **取方案 ②（语义键 + 代码派生）**：`rules/` 增 `must_show_multiple: true`（语义键，非数值）；**代码删掉常量 `2`**，改为**从该键派生** `min_count = 2 if must_show_multiple else 1`。**不补 `min_count: tbd`** —— `tbd` 会把一条**已经说死的语义要求**降级成"待定"，且与语义键构成"同一事实两处"（可互相矛盾） |
| `max_grid_points=256` / `max_nodes=512` | **护栏**（仅截断搜索 + `:273` 明写"不静默"，不改变解集语义） | 留代码，docstring 须标"护栏" |

★ **落点更正（`e`）**：本节原写 `rules/scenario.yaml`，**与实装矛盾**。改判依据三条（见 `182f8a1` 提交信息）：
① `§I.2` 风险表行 1 把「反解搜索空间」的控制手段**明文指派**给 `rules/valuation-methods.yaml`，
「多解展示爆炸」是**紧邻的同一族**控制手段；② `§J.2` 离散粒度**已在该件**；
③ **生产者同源**（`assumption_grid.solver_ref` 指的就是 `scripts/pricelayer/solver.py`）。
⇒ **实装为准**：`rules/valuation-methods.yaml::solution_set_display`。

★ **前瞻风险（`d`，`ws-ch2-rules` 提出，主理人采纳）**：`rules/valuation-methods.yaml:61`
`grid_search_upper_bound: tbd` 一旦被拍板，代码里的 `max_grid_points=256` **若不改读就会重演同一双份** ⇒
该键拍板时必须**同时**把 `256` 改为从 `rules/` 读。

⇒ 处置：`ws/ch2-rules` 贴回 `§J3` 的**逐字原文**（键名 + 值 + 出处）+ 上述判定理由；
**由主理人**安装进 `rules/` + `chmod u+w` + `lock_rules.py` 重锁 + 核 `rules_lock_guard`。
**代码里不得留第二份**（`G-06`）。

---

## `R12` · ★★ 「零消费者键」同族**第三次**，且这次是**分组级**（`G-57`）—— 立卡 **13-G**

### 事实（`ws-ch2-rules` 逐键数消费者，主理人采纳其枚举）

`rules/metric-sets.yaml` 共 **11 个顶层键**，对 `scripts/valuelayer/**` + **全仓**分别数消费者：

| 分类 | 键 |
|---|---|
| **有消费者** | `metric_sets` · `routing.fallback_metric_set_id` |
| **全仓零消费者**（`grep` exit=1） | `binding_guard` · `metric_item_fields` · `segment_evidence` · `conversion_chain_per_model_class` · `conversion_chain_generic_stages` · `extension_policy` · `routing.key` · `routing.binding_field` · `routing.metric_owner_field` |

⇒ **11 键里 9 键零消费者。** 这是 `G-50`（判据没绑）→ `T-18`（列零消费者）→ `G-55`（两侧零绑定）之后
**同族第四次**，也是**规模最大的一次**（前三次是单点，这次是一个文件的分组面）。

### ★ 为什么**不**直接判成缺陷（`ws-ch2-rules` 的处置，主理人确认）
1. **这些键名转写自设计节号**（`:79` ← `§C.2`、`:103` ← `§B.1/§B.2`、`:76` ← `§C.1`），**不是代码自造**；
2. 设计**没写**它们是否要求"运行时读"；
3. ★ **`binding_guard` 的两条 `rule_*` 恰好就是 `rollup.py` 真正实现的规则** ⇒ 更像是「**声明面，由门禁核**」而不是"valuelayer 运行时读"。
⇒ 故**不判缺陷**，但**必须定性**（`G-03`：不许静默留着）。

### ⇒ 立卡 **13-G**：把 9 个零消费者键**逐键定性**（三分类，可判定、穷尽）

★ **三分类（本卡的核心，必须逐键落到恰一类）**：

| 类 | 含义 | 要求 |
|---|---|---|
| **(a) 有运行时消费者** | 代码区真在读 | 指名**文件:行** |
| **(b) 无运行时消费者，但由「门禁 / schema / 测试」核** | **合法**，且这是**最重要的一类** | **必须指名是哪一道门禁/哪个测试**（写不出名字 ⇒ 归 (c)） |
| **(c) 三者皆无** | 无人消费 | 要么**补消费者**，要么**明确"首版不消费"并显式登记**（`G-03`：显式 note + 计数，不静默） |

**交付**：一张逐键表（键 → 类别 → 证据（文件:行 或 门禁名）→ 处置）+ 报告四段式。

**★ 责任与边界（`§九`）**：`ws-ch2-rules` 是这 4 件规则文件的**转写人** ⇒ 它是**枚举者**，
**必须明写"这是对我自己产出物的复查"**（它已主动这么做了）；**定性结论仍需后续换人复核**（并入批次 14 审计）。
⇒ **不许**因为"是我自己写的"而放宽 (c) 类的登记要求。

### ★ 对 `ws-schema-expand` 的 13-pre（方向 2）的**硬约束**（否则这门禁会被关掉）
方向 2「`rules/` 声明了语义却零消费者的键 ⇒ 报警」**必须把 (b) 类的消费者算进"消费者"** ——
即**门禁 / schema / 测试**也算。否则会把上面 (b) 那一批**合法**的声明面全判红 ⇒
**噪音 → 门禁被关掉**（本项目铁律：天天误报的门禁一定会被关掉）。
⇒ 方向 2 的正确形态是**三态输出**：`有消费者(运行时)` / `有消费者(门禁/测试)` / **`零消费者 ⇒ 红`**，
且**必须能算出三类各自计数**。

---

## 卡 13-H · `sensitivity` 三载体形态收口（`G-58` / `T-20`）—— **阻塞于 13-B 提交**

**为什么单列**：`G-58` 是「声明 ≠ 有效力」的**第五次**（`G-50` → `T-18` → `G-55` → `G-57` → 本条），
但它是**唯一一条"位置与类型都不同"**的形态，且**可能是同名不同义**（`T-20`）。`G-55` 的绑定断言**解不了它** ——
`G-55` 是"两处值应相等"，本条是"三处**形态**不兼容"，断言形式完全不同。

**前置（必须先解决，否则做了白做）**：
1. **`T-20` 需求方裁定**：设计的 `sensitivity[]` 与 `rules/benchmark.yaml` 的 `sensitivity.{disclosure_state}` **是否同一物**？
   - **同一物** ⇒ 定唯一形态（主理人推荐**按设计取列表**）+ 定位置；
   - **不同物** ⇒ **`rules/` 侧改名**（避免与设计撞名）。
   ★ **不裁定就动手 = 猜**；而本卡动的是**契约形态**，猜错比不动更贵。
2. **13-B 提交**（它正在改 `scripts/pricelayer/history_guard.py`，该文件是本卡的下游之一）⇒ 避免撞同一片文件。

**★ 窗口期**：`system/facts/benchmarks.jsonl` **当前 0 行** ⇒ **此刻**是改契约成本最低的时点（无迁移成本）。
⇒ 若 `T-20` 判"同一物"，**应尽快做**。

**DoD（裁定落地后）**：
- [ ] 三处形态**统一**（或改名后各自唯一），且**有机器绑定**（断言三处一致 —— 参照 `G-55` 的做法：**两侧/三侧均从真源实读，不许手写清单**）
- [ ] **可执行反例**：注入一处漂移 ⇒ 红；**反向对照**：不动 ⇒ 绿
- [ ] `facts/benchmarks.jsonl` **0 行**这一事实必须**显式登记**（`G-03`：任何"改对了"的断言在真源上真空成立 ⇒ **必须构造行取证**，并贴真实输出）
- [ ] 下游清理：`scripts/pricelayer/history_guard.py` 的 `_COVERAGE_PROFILE_KEYS` / `_coverage_value()` 回落分支（13-B 写入面，**由 13-B 做**）
- [ ] `rules/` 侧若需改：**候选交主理人**，主理人 `chmod u+w` + 编辑 + `lock_rules.py` 重锁 + 核 `rules_lock_guard`

---

## 主理人追加口径（批次 13 集成期，逐条来自实测）

### 口径 1 · 差分/对拍实验**必须先断言"变更已落盘"**
`ws/ch2-rules` 在 13-G 的差分实验里**第一次得到"完全相同"的结论是无效的**：`rules/*.yaml` 是 **0444**，
`cp` 把只读位带走 ⇒ `write_text` 抛 `PermissionError` ⇒ **变更根本没落盘**，于是"两次结果相同"是**假阳性**。
⇒ **规矩**：任何"改前/改后对拍"实验，**必须先读回被改文件、断言新值已在盘上**，否则实验无效。

### 口径 2 · `exit=2`（输入错误）下"结果一致"**不算证据**
同一次实验里，另一次 scratch 缺 `rules/banned_tokens.yaml` ⇒ 两次都 `exit=2`（**输入错误**），
此时"违例集合相同"**毫无意义**（两次都没真正检查）。
⇒ **规矩**：对拍实验**必须先确认两次都跑到了判定逻辑**（`exit != 2`），否则结论作废。

### 口径 3 · 判"某单改了哪些代码"的**正确命令**
`git diff <本单commit>..HEAD` **会把别人合并进来的改动算进来**（本单已 merge 过 main）⇒ 结论失真。
⇒ **正确**：`git show <本单commit> --numstat`，或 `git diff main..HEAD --numstat`。

### 口径 4 · 两个环境闸门**不可混为一谈**
`run_pytest.sh` 治的是 **broker 在解释器层卡死**（`CODEBUDDY_*` 两个 env）；
**治不了宿主删除预算**（`G-59`）。⇒ 报告里说"已按 `run_pytest.sh` 跑"时，**不得**暗示删除预算问题也被解决了。

### 口径 5 · 「有人实现了同一件事」≠「这个键有人消费」
`ws/ch2-rules` 的 13-G 实测：`metric-sets.yaml` 的 9 个键**行为**确有实现、也**有测试覆盖**，
但**把键删掉或改成矛盾值，那些测试照样全绿** ⇒ 判 **零消费者**（`(c)`）。
⇒ **规矩**：判"某声明是否被消费"，**必须用"判别力"口径**（改值 ⇒ 是否变红），
**不能**把"这个行为已被测试覆盖"当成"键被消费" —— 否则本批 9 键**全绿**，门禁当场变**安慰剂**。

---

## 批次 13 收尾口径（主理人 2026-09-16，`ws-ch4-valuelayer` 八项裁定 + 两项一般化）

### 口径 6 · ★ 设计未给值时**不得"兜一个数"，也不得"恒红"** —— 正确形态是**三段式**
面对 `min_fields_per_section: tbd`（设计写"达最小字段数"但**未给数值**）的两难：
缺键 ⇒ **恒红**（`G-01` 禁：恒红的门禁一定会被关掉）；代码兜一个数 ⇒ 设计未拍板的事实**不可观测**（`G-03` 禁）。
⇒ **裁定（批准 `ws-ch4-valuelayer` 的处置，并升格为通用口径）**：
1. **可核的部分照常强制**（`§G.2` 的「六项 section **非空**」是可判定的 ⇒ `moat: []` 照样被拦）；
2. **不可核的部分显式记「不可核」+ 机读计数 + note**（`scanned["min_fields_undecided_sections"]` + `MIN_FIELDS_UNDECIDED`）；
3. **需求方给出该键的值后，无需改代码即自动生效**（参数化的正确收益）。
★ 这与 `T-10`（"四要素覆盖率 1.0"对首条建议结构性不可达）的处置是**同一手法**：
**把"结构性不可达"从判据里显式剥离并记账，而不是伪造分母或放行。**

### 口径 7 · ★ **验收判据是「有生产调用方」，不是「有 CLI」**
`ws-ch4-valuelayer` 问：「空壳 CLI」与「孤儿模块」哪一边更不可接受？
⇒ **孤儿模块更不可接受**（铁律 1：只建模块、不接线 = 未完成）。
但**不得**因此要求每个模块都有 CLI：`rollup` / `state_machine` **有生产调用方**（`chain_steps.py` step 4 真调），
违例契约是**抛异常**且有真实异常类作证 ⇒ **它们不是孤儿**。
- **`G-07`（新守卫必须进 `run_all_gates`）只适用于「独立门禁」**，不适用于**被调用方的纯函数模块**；
- 给纯函数硬造 CLI ⇒ 造出「**假接口**」（`G-03`：无被检对象却造一个入口）。

### 口径 8 · 两条设计规则互相排斥时：取「能同时满足两者意图」且**判别力不降**的那条
`§C.2` 字面比 `model_class` vs `§C.3` 未注册类型归 `generic` ⇒ **字面比较使 `§C.3` 的正常路径恒红**。
⇒ 改判为 **「routing 等价」**（"你绑的必须正是你路由到的那一个"）→ 比字面**更强**：
"注册类却绑 `MS-GENERIC`" 会被拦下，**字面比较会放它过去**。
**规矩**：两规则互斥时 **不选"更弱"**，选"更严且不误伤"的那条（与 `T-09` 的处置口径一致）。

### 新张力
- **`T-22`**：`owner_business_id` **由谁写**？`§C.1` 模板式注册表（`metric_item_fields` **不含** `owner_business_id`，
  各 `metric_set` 的 `metrics` 全是 `tbd`）× `§C.2` `binding_guard.rule_metric_owner_must_be_own_business: true`
  要 `m.owner_business_id == business.business_id`。⇒ **待需求方裁定**。
  **当前处置（批准）**：注册表**声明了归属就严格判等**；**一条都没声明 ⇒ 该检查"不可核"**（note + 计数 + 放行，不恒红）。
- **`T-23`**：`§G.1⑥` 的 Ch5↔Ch7 循环接缝（"建议又要 baseline ⇒ 互为输入"）是否**设计口径**？
  **当前处置（批准）**：以 `implied_requirements`(ch5:) + `recommendations`(ch7:) 按 `company_id` 归并。
- **`T-24`**：`CLAIM_KINDS_KEY`（护城河证据类别取自 claim 的哪个键）**真文件未定义**，夹具用 `moat_evidence_kinds`。
  ⇒ **接受夹具方案 + 显式登记**（`G-03`），并写明"**真文件未定义 = 设计缺口**"。

### ★ 卡 13-J · 把 `test_criterion_effectiveness.py` 的 **5 个写死计数**改为**派生**
`ws-ch4-valuelayer` 本次**不得不手工同步 5 个数字**：`criteria_bound 13` / `registry_entries 16` /
`counterexample_entries 15` / `ineffective 1` / `without_counterexample 0`、`len(entries) == 16`。
★ **这与 `PROGRESS.md §7.5` 第 1 条是同一个反面模式**（`test_verification_policy.py` 写死 `"batches: 7"`）——
**把实现细节的数量当契约**。⇒ **那条教训没有被一般化**，这是第二次犯。
**危害**：每次新增判据都要人工同步 5 个数字；**漏同步要么让门禁红（响的），要么让断言失效（静默）** —— 后者更危险。
**修法**：像 `tests/guards/test_exit_code_contract.py::GUARDS` 已从 `run_all_gates.GATES` 派生那样，
让这些计数**从判据真源派生**、**不写死**。

★★ **但"改派生"本身有一个陷阱，必须先钉死（`ws/ch2-rules` 提出，主理人采纳并修正本卡）**：
若把期望值改成"**调用门禁内部的同一个函数**算出来"，就成了**自反断言**（两边同源 ⇒ **无论真源对错都绿**）
⇒ **比写死更糟**（写死至少会红）。⇒ **本卡追加三条硬要求**：
1. **两边必须不同源**：
   - **期望值** = **测试自己数**（`stage_gate.bound_criteria()` 逐阶段求和 / 自己解析 registry 条目）；
   - **实际值** = **门禁 CLI 打印的 `scanned … : N`**（**文本解析**）。
2. ★ **必须留一个「锚」关系式断言**，防止"派生"把整条判据稀释成**恒真**（例如
   `criteria_bound >= 声明 automated 的判据数 - 未绑定数`）。
3. ★★ **反向对照（防真空，本卡原稿漏了）**：「注入一条判据 ⇒ 计数自动跟上、无需人工改字面量」**只证明了一半**；
   **必须同时证明"跟不上时会红"** —— 即**把派生逻辑改坏**（例如少算一个阶段）⇒ 测试**立即红**。
   ★ 没有这一半，"能自动跟上"这句话是**真空的**（与 `G9` 的"绑定只证明接了、不证明真的在查"同型）。
⇒ 主理人**未**把 13-J 派给 `ws/ch2-rules`（它只是恰好核过这些计数）；13-J **仍在 `ws-ch4-valuelayer`**（它 staged 了该文件）。

### 口径 9 · ★ 报门禁读数**必须连"在哪个树上跑的"一起报**
`ws/ch2-rules` 做了本轮最硬的一组对照（§16.7）：**同一道 `criterion_effectiveness_guard`、同一份门禁代码**，在**两个树**上：

| 项 | 13-A 树 | `main` 面 |
|---|---|---|
| `未绑定判据[nvidia_sample]` | **1 条** | **2 条** |
| `registry_entry_tests_resolved` / `criteria_registry_entries` / `criteria_bound` | 16 / 16 / 13 | 15 / 15 / 12 |

三处**同时只动 1** ⇒ ① `2→1` 是 **13-A 的改动**造成的（不是环境/缓存）；② 门禁**对对象敏感**。
⇒ **规矩**：只报数字，读者分不清"**没做**"和"**做了没生效**"。**必须写"在哪个工作树 / 哪个 commit 上跑的"**。

### 口径 10 · ★★ 判词**必须带「对象 + SHA」** —— 否则同一句话在对象变时真假相反
本批次**同一病灶出现三次**：
1. `ws/ch2-rules` 报"13-A 冲突没解完" —— 对**更早快照**成立，对现状**不成立**（内容是解好的、只差 `git add`）；
2. `ws/ch2-rules` §15.5(b) 判"**错**"（`rules/` 断言了代码里不存在的派生）—— 对 **`main`** 成立，对 **`ws/ch5-pricelayer` 工作树不成立**（该派生**已实现**：`min_count = 2 if must_show_multiple else 1`，且它的探针 B 实测**有判别力**：篡改语义键 ⇒ `min_count 2→1`）；
3. ★ **主理人自己也犯了同一次**：我裁定该条注释"假声明（`错`）成立"时，**也没写对象** ——
   我当时是拿 `main` 判的，而 13-B 的工作树里已经实现。**我的裁定对 `main` 成立，对 13-B 树已过期。**
⇒ **规矩**：**任何"当前态"结论（判词、计数、门禁读数、测试结果）都必须写清【对象 = 工作树/分支/commit SHA + 取样时刻】。**
被判词影响的人（如 13-B）有权要求"按我的 SHA 重判"。

### 裁定 · `G-06` 是否允许「**真源在 `rules/` + 代码留副本 + 漂移断言绑死**」这一镜像形态
`ws/ch2-rules` 提请注意：`must_show_multiple` 是**真·单一真源**（代码只派生、零副本）；
而 `default_count` / `max_count` 是**副本 + 断言**（`solver.py:672/:679`：只改 `rules/` 会报违例 ⇒ **必须同时改两处**）。

**裁定：有条件允许，三条约束缺一不可；但本案例的"必要性"未被证明 ⇒ 默认应删副本。**
1. **副本必须被断言绑死**（漂移即违例，**不许静默**）—— 已满足；
2. **副本必须显式标注为「副本（镜像）」并在 docstring 指明真源路径** —— 否则后人会误以为它是真源；
3. ★ **必须存在一个「真实场景」**（规则文件不可读时仍需可运行）。**只为"少读一次盘"而留副本 → 必须删**（性能用 `_cached_yaml` 解决）。
⇒ **对 `default_count`/`max_count` 具体裁定**：`rules/` 是 **0444 锁件 + `rules_lock_guard` 守着、必须存在**，
"**缺失仍需可运行**"**不是**一个真实场景；且 13-B 自己实测 `default_count=9 ⇒ PriceLayerError` ⇒ **缺/错值已经响亮失败**。
⇒ 请 13-B **先回答"真实场景是什么"**；**答不出即删副本**（一律从 `rules/` 读、缺键响亮失败）。
★ **不由我替它认定场景** —— 这是"**不裁定假设，要求给具体场景**"。

### 口径 1′ · ★★ 扩展：**任何「注入 / 篡改 / 对拍」型实验，必须自证"变更真的生效了"**
原口径 1 只说"差分实验必须先断言变更已落盘"。`ws-schema-expand` 本轮又踩到**同一族的另一半**，故合并升格：

> **原口径 1（落盘）**：`ws/ch2-rules` 的 `cp` 带走 0444 只读位 ⇒ `write_text` 抛 `PermissionError`
> ⇒ **变更根本没落盘** ⇒ "两次相同"是**假阳性**。
> **新增（匹配）**：`ws-schema-expand` 的 `no-op` 陷阱 —— 注入串**没匹配上**（`rules/scenario.yaml` 那一行带行尾注释，
> 它按带 `\n` 的串替换）⇒ `write_text` 把原文写回 ⇒ **"注入"什么都没做、守卫照样绿**，
> 而失败信息把**归因指向守卫**（**假缺陷**）。
⇒ **规矩（注入/篡改型实验的三条自证）**：
1. **锚点在**（替换目标串确实出现在原文里）；
2. **替换前后文本不同**（`assert new != old`）；
3. **已落盘**（读回文件确认新值在盘上）。
★ 并且：**该纪律必须写进反例登记规范** —— 反例的价值取决于"注入真的生效了"。
★ 一般化一句话：**工具/实验会安静地把证据变成空，而"空"与"通过"观测上无法区分**（与 `G-03` 同源）。

### 卡 13-J **修正**（归属与做法都变了，`ws-ch2-rules` 复核后提出）

**（1）归属：改派给 `ws-ch2-rules`**（它已提交 `76a2d5b` 交付"逐条方案与证据"）。
★ 撤销先前派给 `ws-ch4-valuelayer` 的安排（13-A 单已合并收工）。**13-A 请勿再动此卡。**

**（2）做法：不能一刀切"改成派生"** —— `ws/ch2-rules` 的核心发现：
> **"把写死计数改成派生"这个动作必须逐个看清那个数字原来在挡什么。**

| 数字 | 原来在挡什么（它实测的原文） | 正确修法 |
|---|---|---|
| `criteria_bound 13` / `registry_entries 16` / `counterexample_entries 15` / `ineffective 1` / `without_counterexample 0` | **故意留的绊线**（`test_criterion_effectiveness.py:894` **逐字写着**）⇒ 加判据时**必须被绊一次**，否则算漏改 | **保留数量断言**，但**期望值改为测试自己数、实际值取门禁 CLI 的 `scanned …: N`**（两边不同源）；**必须留一个「锚」关系式**防"派生把判据稀释成恒真" |
| `len(entries) == 16` | ★★ **真空防护**：`entries` 被参数化进循环，**若登记为空则循环执行 0 次 ⇒ 用例静默通过** | **不要**改成 `len(entries) == <派生数>`；正确修法是 **`assert entries, "登记为空 ⇒ 本用例真空"` + `assert checked == len(entries)`**（`checked` 是循环实际检查数） |

★ **两个数字守的是两件事** ⇒ **两套修法**。一刀切"改派生"会把真空防护一起拆掉。

### 新裁项 / 新卡
- **`T-25`**：`G-07`（新守卫必须同时进 `run_all_gates` 与 `pre-commit`）**是否升格为通用规则**？
  实测：`pre-commit` 跑 **12** 道、`run_all_gates.GATES` **25** 条 ⇒ **包含关系存在**，但**是否为缺陷需一次裁定**。
  ★ `ws-schema-expand` **拒绝自行发明更严的通用规则**（"会当场造出一条假红门禁"）—— **这个判断正确，主理人确认**。⇒ 登记交需求方。
- **卡 13-L**：新增一道 **`grep_usage_guard`** —— 检出 `grep` 调用中 pattern 含 `\|` 且**未加** `-E`/`-F` 的用法
  （BSD `grep` 的 BRE **不支持** `\|` 交替 ⇒ **静默返回 exit=1**）。
  ★ 依据：**该坑本会话被踩了 4 次**（`ws-ch2-rules` 2 次、主理人 1 次、`ws-schema-expand` 1 次）；
  且 `ws-schema-expand` 的判断正确 —— **"记下教训不足以改变习惯，必须做成机器绑定"**（照 `shell_var_guard` 的做法）。

### 口径 11 · ★★ 「merged ≠ closed」—— **合并后必须复核 `main..branch` 是否归零**

**本批次实际发生（主理人的流程缺口，`ws-degrade-contract` 主动报告）**：
我合并了 `ws/degrade-contract`（`6ee7121`）与 `ws/daily-nochange-exit`（`60d5348`），
但**合并之后**对方**继续提交**了两个**只改报告**的 commit（`576c390` / `d594a6b`）⇒
**这两个提交都不在 main 上**（主理人实测：`git merge-base --is-ancestor <commit> main` ⇒ `exit=1`）。
⇒ 后果：**代码进了主干、报告留在分支** ⇒ 主干上的报告**落后于**它自称描述的状态 ——
正是 D1 / 口径 10 那一类「**声明与现实不符**」。（两处均已补合：`4da29a1` / `70fd2af`，现两分支 `main..branch = 0`。）

**规矩**：
1. **每次合并后，必须再把该分支核一次 `git rev-list --count main..<branch>`**；
2. **若不为 0** ⇒ ① 再合一次，**或** ② **显式冻结该分支**（写进任务卡/留言："**已冻结，不再接受提交**"）；
3. ★ **不允许靠"我合过了"的记忆判断** —— 必须**带对象与时刻**（口径 10 同族）；
4. ★ **判据**（一句话）：**"合并那一刻的 tip 进了主干" ≠ "这个分支的内容全进了主干"**。

### 口径 12 · ★★ 两个变量同时变 ⇒ **不得归因**（受控变量原则）
`ws-schema-expand` 自曝：它的高方差表里两次读数 —— **101.96s @`64aed64`** ↔ **30.73s @`7835c0b`** ——
**既换了 SHA、又换了宿主负载** ⇒ **两个因子未被分离**。
⇒ 它**只声明"跨度 3.3×"，明确不声称**其中多少归因于"我加的 5 例"、多少归因于负载。
★ **这个处置完全正确，升格为口径**：**要归因就必须做受控实验**（**同一 SHA 下只变负载**，或**同一负载下只变 SHA**）。
⇒ 已把"**同一 SHA 下变负载**"写进 13-F 的取证要求（分离"负载"与"夹具/用例数"两个因子）。
★ 同族：口径 9（读数必须带树/SHA）解决的是"**这是哪个对象**"；口径 12 解决的是"**变化归因于哪个因子**"。

### 口径 13 · ★★ 白名单必须自带**三条**，否则它等于"把门禁关掉"
方向 2「零消费者 ⇒ 红」**必然**会命中一批**首版按设计不消费**的键（例 `rules/pipeline.yaml::implemented_in_first_version`
= `T-18` 待裁定项）。⇒ **裁定：走白名单 + 计数（不一律红）**，理由与 `G-27`（`placeholder_exemptions.yaml`）**同形态**：
白名单 **+ `reason` + `approved_by` + `scope_note`，放行但计 `exempted_hits` 并打 `EXEMPTED` note，不静默**。
★ **为什么"一律红"不行**：会把 `T-18` 这类**待需求方裁定**的项变成硬红 ⇒ 门禁沦为"待裁定项的镜子" ⇒ 噪音 ⇒ **被关掉**（铁律）。
★ **但白名单必须自带三条**（缺一即退化成"永久豁免池"）：
1. **逐条** `reason` + `owner` + ★ **`预期何时有消费者`**（写不出 ⇒ 不得入白名单）；
2. ★★ **过期机制**：每条带 `review_by`（或 `expected_consumer_by`）⇒ **到期未消 ⇒ 报警**；
   ★ 依据：本项目已有先例 —— `placeholder_exemptions.yaml` 的豁免条数**在增长**，而**没有任何机制让它们过期**。
3. ★★ **输出白名单与被检集合的比值**（`whitelisted: n / total: m`）⇒ 让"白名单把整道门禁稀释掉"这件事**可见**。

### 口径 15 · ★★ 试合并**不得在 `main` 工作树里停留**（否则全体成员提交不安全）
**依据 `G-61`**：共享钩子跑 **main 工作树那份 `pre-commit.sh`**，而它从 **cwd** 反解 `CODE_ROOT` ⇒
**判据来自 main、被检对象来自提交者** ⇒ main 工作树处于 merge 中间态时，**任何人提交都可能被"自己树里永远满足不了"的门禁挡住**。
⇒ **规矩**：
1. **试合并 / 冲突探查** 一律在**临时工作树**里做（例如复用 `.worktrees/integration`，或 `git worktree add --detach` 一个临时树）；
2. 只有**确认无冲突**后，才在 main 工作树里**一次性**完成 `git merge --no-ff`（**不加 `--no-commit`**，与提交在**同一次工具调用**内完成）；
3. ★ **不允许**把 main 工作树留在 `--no-commit` 的中间态**跨工具调用**（这正是 `G-61` 的成因）；
4. 确有需要留窗口 ⇒ **显式声明**"main 正在合并，请勿提交"。

### 口径 11 扩展 · ★★ 「缺口判定」的**三步联合**（`auditor-batch11` 提出，主理人采纳）
`rev-list --count main..b > 0` **只作线索，不作结论**：它会**把一个"合并方向是 main→b"的 merge-only 提交也算进去** ⇒ 假阳性。
⇒ **结论一律由内容差分决定**：
1. `git diff --numstat main..b -- system/` —— **有输出** ⇒ 该分支有内容未入主干 ⇒ **真缺口**；
2. 无输出且 `main..b` 只有 merge 提交 ⇒ **不算缺口，但记一条"待清理的 merge-only 提交"**；
3. ★ **三者必须都做**：`main..b` 计数（线索）+ `git diff --numstat main..b -- system/`（**结论**）+ **`main:path` 是否存在**（存在性）。
   ★ **`main:path` 的存在性判别必须用** `git cat-file -e main:<path>`：**`git rev-parse main:<path>` 在路径不存在时会把参数原样回显到 stdout**（非空）⇒ **"不存在"被判成"存在"**（`ws-degrade-contract` 实测）。
   ⇒ 两条工具陷阱（`rev-parse` 回显 / `rev-list` 计 merge）**都表现为"整齐的假结论"**，与 `grep \|` 同族。

### `G-61` 条文（`ws-step56-skipped` 拟稿，主理人采纳并入缺口登记）
> **`G-61` 的强制意义：`main` 工作树在合并过程中处于"逐文件中间态"，此时共享钩子会让它树上的判据去检各工作树，
> 造成"合法者被误判"** —— 这是真实假缺陷来源，必须修（改钩子为 `"$(dirname -- "$0")/../.."` 或去 `cd`），
> **不能**依赖"主理人合并要快"这条流程纪律。

### 环境口径 · zsh `nomatch` 会**中止整条命令**（`ws-criterion-effectiveness` 实测）
```
$ chmod -R u+w rules/*.yaml rules/*.yml    # zsh: no matches found: rules/*.yml
```
⇒ **zsh 默认 `nomatch`**：**任一 glob 无匹配 ⇒ 整条命令在展开阶段中止** ⇒ **`rules/*.yaml` 的 chmod 也没执行**
（后续 `lock_rules.py` 可能因此报不明原因失败）。
⇒ **规矩**：这类命令用 `chmod -R u+w rules/`（**目录**，无 glob）或 `setopt +o nomatch` 显式关闭。
★ 与 `G-53`/`V-07` 同族：**`rules/` 的权限操作极易被"工具行为"静默降级**，且**症状指向别处**。

---

## 卡 13-M · ★ 夹具降本（13-F 续）—— **方向更正 + 先做证伪实验**

**方向更正（主理人，依据两条实测）**：
- **不是**「`_clear_work_dir()` 改逐文件删除」—— `ws-criterion-effectiveness` 的正确质疑：宿主判据是
  `count = 本回合已累计 + 本次目标树条目数` ⇒ **拆成逐文件，条目总数不变** ⇒ **对配额无效**，
  且**审批调用数暴涨**（600 次 vs 1 次）⇒ **更慢**。
- **正确目标 = 减少「每例副本的条目总数」**（13-F 实测：每例 **275 项**，其中 `scripts/` 113 + `tests/` 86 = **72%**）
  ⇒ 单价 × 用例数 = 配额消耗；**只有减少条目数才能同时降配额与降时间**。
- ★ `ws-real-collect-2` 已**主动把"`_COPY_SKIP` 加 `raw`"降级为"可选清理，非修复"**（`raw` 仅 18 项 ≈3%）
  ⇒ **主理人采纳，不据此立项**。

**必须先做的证伪实验（成本极低，决定后续方向）**：
> 在同一回合内，做 **N 次「单文件删除」**，观察宿主报文的 `count` **是否按条目累加**。
> - **累加** ⇒ 逐文件无效（预期结果，与 13-F 的模型一致）；
> - **不累加**（即按"调用次数"计）⇒ 逐文件有效。
⇒ **不先做这个，任何"改删除粒度"的改动都是在猜。**

**可选方向（待证伪实验后择一，需先给出可变现场景）**：
① `_COPY_SKIP` 扩展到 `scripts/`/`tests/` 的**非必需子集**；② 用**符号链接 / 只读挂载**替代整树拷贝；
③ 会话级基线拷贝 + 每例廉价 overlay（13-F 原案 A）。

## 卡 13-N · 清理 `verify.py` 内**手写数量/枚举**与真源的漂移（**第 4 次同族**，归 `ws-ch4-valuelayer`）
`INJECTION_SHARDS` 已是 **7 项**（我加 `injection-g` 所致），但**同文件 8 处散文仍写"6 片"**，且表里枚举上界只到 `f`：
```
29:  | `injection-a`…`injection-f` | …**6 个分片**      ← 枚举上界与计数都过期
43/94/226/237/238/297/313/516: 「6 片 / 六片」             ← 8 处
362/383: 「a27 b28 c27 d29 e32 f29，合计 172」「最大余量只有 5 例」  ← 实测为 a30 b32 c31 d29 e32 f31 g18，最大余量 3
```
★ **这是「把实现细节的数量写进描述」的第 4 次**（`PROGRESS.md §7.5 #1` → 卡 13-J → `CONVENTIONS` 批次表 → **本处**）。
⇒ **规矩（13-F 已示范）**：**能在描述里删掉的数量就删掉**（它把批次表的"超时"列整列删除，理由逐字："同一事实两处写必然漂移"）；
删不掉的就**从真源派生**。**不许**在散文里再抄一份计数。
