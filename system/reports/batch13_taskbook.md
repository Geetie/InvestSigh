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

#### R8-3 · 13-B 的两个**死常量**：不是"留在代码"，而是"**进 `rules/`**"

`ws/ch2-rules` 报告：13-B 有 `DEFAULT_DISPLAY_CAP=3` / `MAX_DISPLAY_CAP=5`（`grep` 零引用 = 死常量），
以及 `DEFAULT_MIN_SOLUTIONS=2`；并引我的话"'不收进 rules' ≠ '写进代码'"。

★ **它引用得对，但推出的结论我推翻。** 我当时判"暂不收进 `rules/`"的**前提**是
**没有键名、没有指派文件**；现在前提没了 —— `05/02:460 §J3` 就是 `00_待拍板项清单.md` **B18 的来源**，
而 **B18 已拍板**：「估值解集展示上限 `N` = **默认展示 3 组，最多 5 组**〔新给〕」。
⇒ 条件变了，裁定随之改变：**必须进 `rules/`**（`rules/scenario.yaml`，§J3 指派的件）。

**先给一条可复用的统一判据**（免得每件重新吵）：

> **"影响产出取值/选择"的数 = 参数 ⇒ 必须住 `rules/`（`Ch11 §D.2` 单一真源 + `P-09`）；**
> **"仅为防组合爆炸/防卡死的上界" = 护栏 ⇒ 可住代码，但必须在 docstring 明标为护栏。**

按此判据逐条落：

| 常量 | 判定 | 处置 |
|---|---|---|
| `DEFAULT_DISPLAY_CAP=3` | **参数**（决定"展示哪几组解"，直接改变产出） | 进 `rules/scenario.yaml`，值 `3`，`basis` 记 B18 |
| `MAX_DISPLAY_CAP=5` | **参数**（同上） | 进 `rules/scenario.yaml`，值 `5`，`basis` 记 B18 |
| `DEFAULT_MIN_SOLUTIONS=2` | ★ **设计无字面 2，B18 也没给** | **不得自创**。有设计出处 → 按其转写；无 ⇒ **删掉该常量**（改为"展示解数 = 求解器实际解出组数，下界由 B18 的 `default_display_cap` 与真实解数共同决定"），若确需下界则登记 `tbd` 交需求方 |
| `max_grid_points=256` / `max_nodes=512` | **护栏**（防搜索爆炸，不改变解集语义） | 可留代码，docstring 须标"护栏" |

⇒ 处置：`ws/ch2-rules` 贴回 `§J3` 的**逐字原文**（键名 + 值 + 出处）+ 上述判定理由；
**由主理人**安装进 `rules/` + `chmod u+w` + `lock_rules.py` 重锁 + 核 `rules_lock_guard`。
**代码里不得留第二份**（`G-06`）。
