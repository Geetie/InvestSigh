# 交付报告 · 卡 13-E —— `Benchmark` 的 5 个字段正式并入

> 分支 `ws/ch13-e-benchmark-fields`（基点 `4006663`）｜写入面 = `system/schema/**` + `system/tests/unit/**` + 本报告
> **一手依据**：`Ch5 §E.1` / `§E.5`（`05_价格与市场预期研究/02_实现方案.md`）｜裁定来源 = 13-B 报告 §④-4 的待裁定项，主理人裁为"正式并入"

---

## ① 交付物

| 文件 | 改动 |
|---|---|
| `system/schema/models.py` | `Benchmark` 新增 **5** 个字段（含 1 个 `field_serializer`）+ 类 docstring 留痕；**顺带改正我自己写错的一处键路径**（见 §⑥） |
| `system/schema/jsonschema/facts.schema.json` | 重新生成（`python -m schema.build_jsonschema`），110 行新增 |
| `system/tests/unit/test_schema_expand.py` | **+9** 例（含精确字段集、默认值、"`None` vs `[]`"、字符串化、旧行兼容、反向 forbid）；文件头加第 6 条说明 |
| `system/reports/ws_ch13e_benchmark_fields_report.md` | 本报告 |

`Benchmark` 字段数 **20 → 25**（7 个时间基元 + 18 个业务字段）。

---

## ② 逐字出处（★ 5 个字段的**出处强度不一样**，故作两档列）

### 2.1 设计**逐字给出字段名**的 4 个

| 字段 | 设计逐字 | 位置 |
|---|---|---|
| `holdings_disclosure_lag` | 「公开持仓披露延迟 \| `holdings_disclosure_lag`」 | `05/02` **:222** |
| | 「新字段 \| `benchmarks` 上（`non_listed_assets`、`holdings_disclosure_lag`、`unverifiable_forecasts`、`sensitivity`）」 | `05/02` **:22** |
| | 需求侧 `N5.4-03`：「需 `holdings_disclosure_lag`/`non_listed_assets` 字段」 | `05_价格与市场预期研究/01_需求拆解.md` **:50** |
| `unverifiable_forecasts` | 「无法独立核验的预测 \| `unverifiable_forecasts[]`」 | `05/02` **:223** |
| `modeled_coverage` | 「`benchmarks.modeled_coverage` + `unmodeled_parts[]`：未建模部分**显式标注**；`modeled_coverage < 1` 时不得声称"完成整个基金预测"（N5.4-05）」 | `05/02` **:264** |
| `unmodeled_parts` | 同上（`§E.5`） | `05/02` **:264** |

阈值出处：`00_待拍板项清单.md` **:46** **B4 已确认**「未建模覆盖率阈值｜**已建模业务覆盖 ≥ 80%**，否则不得称"完整预测"〔新给〕」（来源 `05/02` J10）。

### 2.2 设计**只给禁令、未给字段名**的 1 个 —— ★ 这一档必须单独标出

`claims_complete_forecast`。三处出处给的都是**禁令**：

| 出处 | 逐字 |
|---|---|
| `05/02` **:264**（`§E.5`） | 「`modeled_coverage < 1` 时**不得声称**"完成整个基金预测"」 |
| `05/01` **:52**（`N5.4-05`） | 「不能忽略基金中没有建模的部分而**声称**完成了整个基金的预测」 |
| `00_待拍板项清单.md` **:46**（`B4`） | 「…**否则不得称**"完整预测"」 |

**没有一处给出承载"声称与否"的字段名**。而判据要成立就必须知道"有没有声称" ⇒ 需要载体。
本批次**沿用消费方（13-B `history_guard`）的既有命名**，并在 `models.py` 的字段 docstring 里
**逐字写明"设计未给字段名、本字段是载体命名"**，不把它混进 2.1 的"设计逐字"档。

★ 为什么这不算"臆造"、且**不产生第二真源**：该字段名**不进 `rules/`**（`rules/benchmark.yaml` 不声明它），
所以改名**不牵动任何锁**；若需求方另有命名口径，改名即可。
本报告把它**显式登记为待复核项**（见 §⑦），而不是静默按 5 个"都有出处"处理。

---

## ③ 裁定内容与**裁定前的状态**（如实留痕，不是"本来就该这样"）

13-B 先于本批次实现判据时，`Benchmark` **只有** `includes_non_listed_assets` / `non_listed_assets` /
`sensitivity` 三个，于是它按「**行内平铺键优先 → `coverage_profile` 内层回落**」**两边都认**，
并在 `system/reports/ws_ch5_pricelayer_report.md` **§④-4** 请裁定：

> 「**请裁定**：把 5 个键正式并入 `Benchmark`，还是明文指定用 `coverage_profile` 承载（裁定后本流删掉另一路即可）。」

**裁定 = 正式并入**（本卡执行）。

### ③-1 ⇒ 由此产生的**下游动作**（不在本卡，已通报）

`coverage_profile` 那一路从裁定落地起就是**同一事实的第二份载体**（`G-06`）。
消费方 `scripts/pricelayer/history_guard.py` 需删除回落分支：

- `_COVERAGE_PROFILE_KEYS`（该文件 :293-305）及其 docstring（其内已自述"裁定后只需删掉其中一路"）；
- `_coverage_value()`（:308-315）改为直接 `row.get(key)`；
- `_coverage_from_row()`（:319-340）随之简化。

★ 以上属 `scripts/pricelayer/**`，是 13-B 的写入面，**本卡未动**。已发消息给 13-B；
按主理人指示，本卡先落地以 unblock `ws-ch2-rules` 的 `#69`。

---

## ④ 字段形态的取舍（每条都有"为什么不那样"）

| 字段 | 定形 | 依据 / 反例 |
|---|---|---|
| `holdings_disclosure_lag` | `str \| None = None` | `None` = **字段缺席**（不是"延迟为 0"）⇒ 消费方判据④据此报违例。默认空串会把"缺席"与"写了空"压成一个 |
| `unverifiable_forecasts` | `list[str] \| None = None` | ★ **`None` 与 `[]` 语义不同，不得折叠**：`§E.1` 要求这类预测"单列"，缺席即没单列（违例）；`[]` 是**显式给出"没有"**（合规）。消费方判据⑤ 逐字写「未给出 `unverifiable_forecasts` 字段（`None`）」。默认若取 `[]`，判据**静默失去判别力** |
| `modeled_coverage` | `Decimal \| None = None` + `field_serializer` 转 `str` | ★ 默认**不得取 `1.0`**：`1.0` 读作"全部建模完毕"，恰是 `B4` / `N5.4-05` 要禁的"静默声称完整"。落库用字符串（`Ch9 §3.4.5` 避免浮点误差，同 `ValuationRange`） |
| `unmodeled_parts` | `list[str] = Field(default_factory=list)` | `§E.5`"未建模部分**显式标注**"。空列表 + `modeled_coverage=None` 的组合不会误判（判据在消费方） |
| `claims_complete_forecast` | `bool = False` | 见 §2.2 |

**未取的做法**（写下来，免得下一个人再试一遍）：
把 5 个字段落进 `coverage_profile: dict[str, Any]`（即 13-B 的"内层"路线）。
理由：设计 `§E.1` 的表头是「字段（`benchmarks` **新增**）」、`§E.5` 写 `benchmarks.modeled_coverage`
—— **`benchmarks.` 前缀指向行内平铺键**；落进开放 dict 会让这 5 个键**永远无法被 schema 强制**
（`extra="forbid"` 管不到 dict 内部），而本项目的铁律正是"只写在文档里没有检查器强制的规范等于不存在"。

---

## ⑤ 机器绑定与实测

### 5.1 新增的 9 条测试（`tests/unit/test_schema_expand.py`）

| # | 测试 | 钉住什么 |
|---|---|---|
| 1 | `test_benchmark_carries_the_four_ch5_e_anchor_fields` | §2.1 的 4 个**设计逐字**字段在位 |
| 2 | `test_benchmark_carries_the_b4_prohibition_carrier_field` | 第 5 个**单独断言**（出处强度不同，不混成一个"5 个都有出处"的印象） |
| 3 | `test_benchmark_field_set_is_exactly_the_designed_twentyfive` | **精确字段集**（7 时间 + 18 业务）—— 防多塞、也防悄悄删 |
| 4 | `test_benchmark_new_fields_do_not_silently_claim_full_coverage` | 默认值**不得**等于"静默声称覆盖完整" |
| 5 | `test_unverifiable_forecasts_absent_and_explicitly_empty_are_distinguishable` | ★ `None` ≠ `[]`（判据成立的前提） |
| 6 | `test_modeled_coverage_leaves_as_a_string_not_a_float` | `Decimal` 落库为字符串，可精确还原 |
| 7 | `test_benchmark_still_rejects_unknown_fields` | 加字段时**没有**顺手关掉 `extra="forbid"` |
| 8 | `test_benchmark_new_fields_survive_a_store_roundtrip` | 走**真实落库路径**（`append_records` + `read_models`） |
| 9 | `test_benchmark_old_rows_without_the_new_keys_still_validate` | **向后兼容**（只增不改） |

★ 之所以把"4 个"与"第 5 个"分成两条断言：**把两类出处混着测，等于把"载体命名"洗成"设计逐字"**。

### 5.2 实测（官方入口，全部在 `ws/ch13-e-benchmark-fields` 工作树内）

```bash
# 单文件（迭代用）
sh system/scripts/ops/run_pytest.sh tests/unit/test_schema_expand.py -q
# → 43 passed in 33.50s

# unit 批（官方入口 + 官方解释器）
$HOME/.workbuddy/binaries/python/envs/default/bin/python scripts/ops/verify.py --batch unit
# → ✓ [unit] exit=0  62.61s/270s  85 passed in 61.49s      （改动前 76 例 ⇒ +9 与上表一致）

# 回归相邻批（Benchmark 的消费方所在批）
… verify.py --batch pricelayer
# → ✓ [pricelayer] exit=0  27.17s/180s  127 passed in 26.32s

# schema 生成物同步
cd system && python -m schema.build_jsonschema        # → 写出 facts.schema.json
… run_all_gates.py . --timeout 60
# → 非零计数 1：仅 traceback.py exit=1（既存数据缺口，见 5.3）；
#   rules_lock_guard exit=0 ✓   schema_sync_guard exit=0 ✓
```

### 5.3 唯一的非零门禁 —— **既存数据缺口，与本卡无关**（已对拍证明）

`traceback.py` 报 2 条 FATAL，均在 `facts/recommendations.jsonl::rec-nvda-001`：

```
[FATAL] G1-03 @ facts/recommendations.jsonl:0 — rec-nvda-001 四要素（**适用项**）缺失:
        ['assumptions', 'computation']（适用=['evidence', 'assumptions', 'computation']，version=1）
```

★ **对拍**：在 `main` 工作树（`4006663`，不含本卡任何改动）跑同一条命令，
输出**逐字相同**（同 2 条、同 `rec-nvda-001`）⇒ 与本卡改动**无关**。

### 5.4 向后兼容的**实测口径**

`system/facts/benchmarks.jsonl` 当前 **0 行**（`wc -l` = 0）⇒ 本卡的兼容性风险在真源上是**真空**的。
故不靠"真源恰好没数据"取证，而是用 §5.1 第 9 条**构造旧形态行**（无这 5 个键）显式验证可读。

---

## ⑥ 顺带改正：我自己写错的一处**键路径**（主理人指出）

`Valuation.scenario_tag` 的 docstring 原写：

```
取值域由 `rules/scenario.yaml::scenario_tag.values`（`bear`/`neutral`/`bull`/`custom`）
```

**实测真文件**：

```
$ python3 -c "import yaml;print(list(yaml.safe_load(open('system/rules/scenario.yaml'))))"
['version','spec_anchor','scenario_tags','first_version_tag_policy','scenario_consistency',
 'scenario_method_status','scenario_method_status_domain','scenario_method_status_note',
 'scenario_method_blocking','scenario_method_promotion','probability','range_expression']
$ … d['scenario_tags'] → ['bear','neutral','bull','custom']      'scenario_tag' in d → False
```

⇒ **顶层键是复数 `scenario_tags`，且直接就是列表**；`scenario_tag.values` 是**假路径**。已改正。

★ 我把**全文件**的 `*.yaml::<键>` 形式引用都过了一遍（正则扫 + 逐条核真文件）：全文**只有这一处**这种写法，
其余 4 处 `rules/*.yaml` 提及（`models.py` :1041 / :1110 / :1118 / :1389）是**文件级**或**语义**表述：

| 行 | 表述 | 核实结果 |
|---|---|---|
| :1041 / :1110 / :1118 | `rules/metric-sets.yaml` 的 `stages:` | ✅ 真实存在（嵌套于 `metric_sets.<id>.stages`） |
| :1389 | `rules/valuation-methods.yaml` 的 `method_class → business.model_class` 路由 | ✅ 实装件 `method_routing` + `routing.key: model_class`；且"`business.model_class` vs 代码 `business_type`"的**命名张力已在两侧登记**（`rules/metric-sets.yaml` :15-17、`models.py` :1104-1107），不是新缺陷 |

★ 教训（第三次同类）：**"我记得键名"不等于"键名如此"**；尤其当同一语义两侧命名不一致时（正是 `G-55` 要绑定的对象），
引用**必须逐字对真文件核**。已在 docstring 内留痕。

---

## ⑦ 遗留 / 请裁定

### 7.1 ★ `claims_complete_forecast` 的命名（请复核，非阻塞）

设计三处只给禁令、未给字段名（§2.2）。本卡按消费方既有命名落为 `bool`，并已在代码里如实标注。
**若需求方另有口径，改名即可**（不进 `rules/`，无第二真源，成本 = 一行 + 一处测试）。

### 7.2 ★ 新发现：`sensitivity` **同一语义三种载体形态**（登记，未改）

| 载体 | 形态 | 出处 |
|---|---|---|
| 设计 | **行内平铺** `sensitivity[]`（**列表**） | `05/02` **:224**；`05/01` **:162** |
| `schema.models.Benchmark` | **行内平铺**，但类型是 `dict[str, Any]`（**不是列表**） | `models.py` |
| `rules/benchmark.yaml` | **嵌套**在 `non_listed_assets` 内层：`non_listed_assets: {disclosure_state: undisclosed, sensitivity: {disclosure_state: undisclosed}}` | 实装件 :23-26（**无顶层 `sensitivity`**） |

⇒ 三处**位置**与**类型**两两不同，且**无任何机器绑定**——与 `G-55`（`scenario_tags` ↔ `ScenarioTag`）**同族**。

**本卡未改**，理由：① `rules/**` 是 0444 锁件、安装面在主理人；② 改 `sensitivity` 的**类型**
（`dict` → `list`）是破坏性契约变更，且会动 `extra="forbid"` 之外的既有写入路径，需裁定。
③ 当下 `system/facts/benchmarks.jsonl` **0 行** ⇒ 任何"改对了"的断言在真源上都是**真空**的（`G-03`），
必须靠构造行取证，属独立一张卡的体量。**建议立卡或用 13-pre 的双向键对齐守卫一并覆盖。**

### 7.3 本卡**未做**的事（边界，如实）

- 未动 `scripts/pricelayer/**`（13-B 写入面）——`coverage_profile` 回落那一路的删除见 §③-1；
- 未动 `rules/**`（0444 锁件）；
- 未把"设计逐字字段名 ↔ 模型字段"做成**可执行**绑定：设计是只读散文，无机器可读清单 ⇒
  该绑定属 **13-pre**（双向守卫）的"方向 1"，本卡不做替代品（免得造成"已有守卫"的错觉）。

---

## ⑧ 纪律留痕（本卡踩到的坑与处置）

| # | 坑 | 处置 |
|---|---|---|
| 1 | ★ **BSD `grep` 的 BRE 不支持 `\|`** ⇒ `grep -n "A\|B"` 被当**字面量**，返回**假零命中**。本卡内**又踩了一次**（核 `field_serializer` 位置时零命中）。**这已是同一坑第三次** | 一律 `grep -E` / ripgrep；写入 §⑥ 教训 |
| 2 | `python scripts/ops/verify.py --batch unit` 报 `No module named pytest` | **不是测试坏了**：`python` 解析到的解释器无 pytest。官方入口 `run_pytest.sh` 用 `$HOME/.workbuddy/binaries/python/envs/default/bin/python` ⇒ 显式用该解释器 |
| 3 | `unit` 批耗时 **62.61s**（超时 270s，余量 4.3×） | `G-54` 已知高方差（48.73s ↔ 66.72s）。本卡**每轮只跑一次**批，迭代走**单文件**（`V-02` 纪律） |
| 4 | 未 `git add -A` | 本卡只 `git add` 4 个具名文件；提交后 `git status --short` 应为空（见提交说明） |
