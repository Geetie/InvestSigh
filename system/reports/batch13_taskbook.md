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
| **13-A Ch4 价值层** | `scripts/valuelayer/**` · `tests/valuelayer/**` · 报告 | 只读 `rules/{metric-sets,baseline}.yaml` + `facts/{baselines,businesses,drivers}.jsonl` |
| **13-B Ch5 价格层** | `scripts/pricelayer/**` · `tests/pricelayer/**` · 报告 | 只读 `rules/{valuation-methods,scenario}.yaml` + `facts/{prices,expectations,benchmarks}.jsonl` + `derived/`（Ch9 compute 已建） |
| **13-R 规则文件转写** | `system/registry/rule-candidates/*.yaml` · 报告 | 只读**设计区**（各章 `02_实现方案.md`） |

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
