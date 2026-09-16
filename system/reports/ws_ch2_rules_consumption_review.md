# 规则消费面复核 —— 13-A（`ws/ch4-valuelayer`）/ 13-B（`ws/ch5-pricelayer`）

**复核人**：`ws-ch2-rules`（13-R 的产出方 = 被审契约的**作者**，故本报告含**自我指控**，见 §6）
**复核对象**：两流**未提交**的工作树快照（**会动**，SHA 见 §0.2）
**被审文件一律未改**：本报告只读两流；唯一写入物 = 本文件。
**结论档位**：好 / 不好 / 未做 / 不够 / 错（+ ✅/❌ 对照），每条附实测命令原样输出。

---

## §0 快照与对象

### §0.1 我方工作区

```
$ git -C .worktrees/ws-ch2-rules log --oneline -3
5823ff1 (HEAD -> ws/ch2-rules) docs(report): 13-R 报告收口 —— 安装后状态 + §4.2 归属建议 + 三条裁定落地
bb32863 (ws/x13r-dual-diff-audit, main) feat(rules): 安装阶段② 的 4 个规则文件（rules/ 10 → 14）+ 重锁；候选目录转为安装件（去双真源）
2b13cbf merge ws/ch2-rules: 阶段② 4 个规则文件的设计转写候选 + 116 行逐键对照表

$ git status --short            # 空
$ ls system/rules/*.yaml | wc -l
14
```

### §0.2 被审快照（★ 两流**均未提交**，仍在写入；本报告结论对应下列 SHA）

```
$ git -C .worktrees/ws-ch4-valuelayer log --oneline -1
d74a829 (HEAD -> ws/ch4-valuelayer, ...) docs(batch13): 阶段② 主体并行开工任务卡（13-A Ch4 价值层 / 13-B Ch5 价格层 / 13-R 规则文件转写）
$ git -C .worktrees/ws-ch4-valuelayer status --short
 M system/scripts/delivery/stage_gate.py
?? system/scripts/valuelayer/
?? system/tests/valuelayer/

$ git -C .worktrees/ws-ch5-pricelayer log --oneline -1
d74a829 (HEAD -> ws/ch5-pricelayer, ...) docs(batch13): ...
$ git -C .worktrees/ws-ch5-pricelayer status --short     # ★ 已**暂存**，说明正在提交中
M  system/PROGRESS.md
M  system/scripts/ops/verify.py
A  system/scripts/pricelayer/__init__.py
A  system/scripts/pricelayer/daily_explain.py
A  system/scripts/pricelayer/history_guard.py
A  system/scripts/pricelayer/order_guard.py
A  system/scripts/pricelayer/scenario_guard.py
A  system/scripts/pricelayer/solver.py
A  system/scripts/pricelayer/step.py
A  system/scripts/pricelayer/valuation.py
A  system/tests/pricelayer/conftest.py
A  system/tests/pricelayer/test_daily_explain.py
A  system/tests/pricelayer/test_history_guard.py
A  system/tests/pricelayer/test_order_guard.py
A  system/tests/pricelayer/test_package_laziness.py
A  system/tests/pricelayer/test_scenario_guard.py
A  system/tests/pricelayer/test_solver.py
A  system/tests/pricelayer/test_step_wiring.py
A  system/tests/pricelayer/test_valuation.py
?? reports/
```

**快照 SHA（我钉的，供复查）**

```
$ shasum -a 256 … | cut -c1-12,66-     # 只列有结论的文件
41e42ac79bce system/scripts/valuelayer/_rules.py          (13-A)
16e12970e376 system/scripts/valuelayer/completeness.py    (13-A)   ★ 我上次钉的是 3b0441891349，已变
240cc7c190a3 system/scripts/valuelayer/growth_quality.py  (13-A)
68c488ffd756 system/scripts/valuelayer/route_guard.py     (13-A)
f54118dffe3d system/tests/valuelayer/_fixtures.py         (13-A)
a4a1b95eebfd system/scripts/pricelayer/solver.py          (13-B)
b612de96b2b9 system/scripts/pricelayer/valuation.py       (13-B)
9f715e12f976 system/scripts/pricelayer/scenario_guard.py  (13-B)
cc8671740de3 system/tests/pricelayer/conftest.py          (13-B)

$ shasum -a 256 system/rules/*.yaml | cut -c1-12,66-      # 已安装件
bb07b9bfdcce system/rules/baseline.yaml
b420c67a77ad system/rules/metric-sets.yaml
af49b71385c9 system/rules/valuation-methods.yaml
e5039163c2d5 system/rules/scenario.yaml
```

★ **时序声明**：两流仍在写入（13-A 的 `completeness.py` 在我上次钉 SHA 后已变；13-B 已进入 `git add` 暂存态）。故 ②③ 的结论**对应上列 SHA**；**提交后须以 commit hash 重跑一遍**（§7 给了可复跑的命令）。

---

## §1 结论总览

| # | 复核项 | 13-A（Ch4 价值层） | 13-B（Ch5 价格层） |
|---|---|---|---|
| ① | 键名对齐 | ❌ **未做**（仍是 `min_locators`/`min_derivations`）——且**改名也救不了**，见 §2.3 | n/a（无此清单） |
| ② | 偷偷新增键 | ✅ 键名 **11/11 全对齐**；❌ **夹具自造了不同形状的 `baseline.yaml`** ⇒ **不够** | ✅ **好**（无新增键；`method_version` 缺键**符合设计**） |
| ③ | 硬编码阈值 | ✅ **好**（阈值全部从 rules 读、缺键响亮失败） | ❌ **不好**（B18 的 3/5 硬编码）+ **不够**（`DEFAULT_MIN_SOLUTIONS=2` 自定）+ ✅ **好**（`grid_step` 必填无默认） |

**贯穿性结论（最重要的一条）**：
> 已安装的 `rules/baseline.yaml`（**我的 13-R 产出**）与 13-A 的读取路径**契约不一致**，且**不一致有两层**：① 键名后缀；② **YAML 嵌套深度**。
> 团队长先前的裁定「**已安装件为准**」只覆盖了第 ① 层。**只改键名的修法不会让任何一条阈值读通** —— 实测：改名后 `min_locator_count` **仍然失败**（§2.3）。第 ② 层需要一次新的、有依据的裁定，见 §7.1。

---

## §2 ① 13-A 键名对齐 —— **未做**

### §2.1 逐处证据（文件:行 + 实际键名）

```
$ cd .worktrees/ws-ch4-valuelayer && grep -n 'CFG_' system/scripts/valuelayer/completeness.py
82:CFG_MIN_NONNULL_RATE = "min_nonnull_rate"
83:CFG_MIN_FIELDS_PER_SECTION = "min_fields_per_section"
84:CFG_MIN_LOCATORS = "min_locators"              ← ❌ 团队长已裁定应为 min_locator_count
85:CFG_MIN_DERIVATIONS = "min_derivations"        ← ❌ 团队长已裁定应为 min_derivation_count
422:    minimum = int(_rules.baseline_threshold_from(cfg, CFG_MIN_FIELDS_PER_SECTION))
449:    minimum = float(_rules.baseline_threshold_from(cfg, CFG_MIN_NONNULL_RATE))
523:    minimum = int(_rules.baseline_threshold_from(cfg, CFG_MIN_LOCATORS))
621:    minimum = int(_rules.baseline_threshold_from(cfg, CFG_MIN_DERIVATIONS))
1058:            CFG_MIN_NONNULL_RATE,
1059:            CFG_MIN_FIELDS_PER_SECTION,
1060:            CFG_MIN_LOCATORS,
1061:            CFG_MIN_DERIVATIONS,
```

**判定：❌ 未做。** `completeness.py:84-85` 仍是 `min_locators` / `min_derivations`；`min_nonnull_rate` / `min_fields_per_section` 两个**名字对**。

13-A 在代码里**如实登记了**这三个键名是自选的（`completeness.py:78-81`）：

```
#: `Ch4 §G.2` / `§J.4 J3` 要求参数化在 `rules/baseline.yaml` 的阈值键。
#: ★ `min_nonnull_rate` 是**设计逐字**给出的名字（§G.2 伪码 `cfg.min_nonnull_rate`）；
#:   另外三个键的设计只给了**语义**（"最小字段数" / "定位数" / "推导数"），
#:   键名由本实现选定并**已在报告「剩余不确定性与缺口」里登记为待裁定**。
```

★ 这条**自陈是诚实的**（`G-03` 意义上的"不假装有依据"）——问题是团队长已经裁定过了，13-A 未合并 `main` 故**看不到**安装件（§2.4），裁定没落地。

### §2.2 装上真件后的实测（**决定性**）

把**真实已安装** `rules/baseline.yaml`（SHA `bb07b9bfdcce`）喂给 13-A **自己的**函数：

```
$ cd .worktrees/ws-ch4-valuelayer && python3 -   # sys.path=13-A 的 system；REAL=ws-ch2-rules/system
1) baseline_cfg(REAL) 顶层键 = ['driver_duration', 'driver_overflow_policy', 'form_completeness',
   'install_note', 'install_target', 'required_extra_fields_by_profitability', 'segment_evidence',
   'spec_anchor', 'thresholds', 'version']
   thresholds 子键         = ['basis', 'max_primary_drivers_per_business', 'min_derivation_count',
   'min_fields_per_section', 'min_locator_count', 'min_nonnull_rate']

2) 逐键喂真实已安装件：
   min_nonnull_rate           -> ❌ MissingRuleInput: rules/baseline.yaml 缺少键 'min_nonnull_rate' …
   min_fields_per_section     -> ❌ MissingRuleInput: … 缺少键 'min_fields_per_section' …
   min_locators               -> ❌ MissingRuleInput: … 缺少键 'min_locators' …
   min_derivations            -> ❌ MissingRuleInput: … 缺少键 'min_derivations' …
   min_locator_count          -> ❌ MissingRuleInput: … 缺少键 'min_locator_count' …   ★★ 改名也失败
   min_derivation_count       -> ❌ MissingRuleInput: … 缺少键 'min_derivation_count' … ★★ 改名也失败
EXIT=0
```

**★★ 这是本报告最关键的一行**：`min_locator_count` / `min_derivation_count`（**团队长裁定的正确键名**）在真实件上**同样失败**。
⇒ **不一致有两层**：键名后缀 **和** 嵌套深度。**只改键名 = 白改**。

### §2.3 根因：深度冲突（13-A 读**扁平**，已安装件是**分组**）

```
$ sed -n '61,63p' .worktrees/ws-ch4-valuelayer/system/scripts/valuelayer/_rules.py
    doc = _cached_yaml(path)
    if not isinstance(doc, dict):
        raise MissingRuleInput(f"{relpath} 顶层不是 mapping，实为 {type(doc).__name__}")
    return doc

$ sed -n '68,76p' …/_rules.py
def baseline_cfg(root: str | Path) -> dict[str, Any]:
    """`rules/baseline.yaml` 的完整文档（`Ch4 §D.2` / `§G.2` 的 `cfg` 就是它）。

    ★ 为什么直接返回整份文档而不是挑几个键：`Ch4 §D.2` 逐字写
      `rules/baseline.yaml: max_primary_drivers_per_business`（**顶层键**），
      `§G.2` 伪码逐字写 `cfg.min_nonnull_rate` —— 两处都把 `cfg` 当作
      **baseline.yaml 的顶层映射**。本函数照此，**不另造一层嵌套**。
    """
```

即 13-A 的模型是 **`cfg` = 整份 `baseline.yaml` 的顶层映射**，故：
- `completeness.py:*` 用 `cfg[key]` 读 `min_*` ⇒ 要求**顶层**
- `growth_quality.py:239` 用 `cfg.get("max_primary_drivers_per_business")` ⇒ 要求**顶层**

```
$ sed -n '239,244p' …/growth_quality.py
    limit = cfg.get("max_primary_drivers_per_business")
    if limit is None:
        raise _rules.MissingRuleInput(
            f"{_rules.BASELINE_RELPATH} 缺 max_primary_drivers_per_business —— "
            "Ch4 §D.2 把该上限定义为规则文件里的可配项；代码不内置默认值"
        )
```

实测（真实件该值确实是 5）：

```
3) growth_quality.validate_driver_count(真实 cfg)：
   ❌ MissingRuleInput: rules/baseline.yaml 缺 max_primary_drivers_per_business —— …
   真实已安装件里的值 = cfg['thresholds']['max_primary_drivers_per_business'] = 5
```

### §2.4 端到端：Ch4 阶段门禁在真仓库上**永远过不去**

13-A 唯一改的共享文件是 `stage_gate.py` 里**一个函数体**（在其允许面内）：

```
$ git -C .worktrees/ws-ch4-valuelayer diff system/scripts/delivery/stage_gate.py
@@ -448,6 +448,23 @@ def stage_nvidia_sample_passed(root: Path) -> tuple[bool, list[Violation], dict[
+    from scripts.valuelayer.completeness import g_depth_violations
+
+    v += g_depth_violations(root)
+    criterion("nvidia_sample", "chapter4_g_depth", v)
     criterion("nvidia_sample", "six_step_chain_complete", v)
```

该函数喂真件的实测结果：

```
$ python3 -    # completeness.g_depth_violations(REAL)
=== 端到端：g_depth_violations(真实已安装规则) ===
   Violation(rule='nvidia_sample', reason="Ch4 §G 深度**无法判定**：rules/baseline.yaml 缺少键
   'min_nonnull_rate' —— Ch4 §G.2/§D.2 要求该阈值参数化在规则文件里，代码不内置默认值（现有键：[…]）",
   file='rules/baseline.yaml', line=0, severity='FATAL')
   违例条数 = 1
EXIT=0
```

⇒ **`chapter4_g_depth` 在真仓库上是恒 FATAL**，阶段②**不可能通过**。
**失败方式是响亮的**（`FATAL` + 逐字原因 + 指到文件），**不是静默用错阈值** —— 这点 13-A 做对了（`_rules.py` docstring 第 2 条把"缺键响亮失败"写成核心行为，实测兑现）。
但它同时意味着：**这不是"文档不一致"，是功能断裂**。裁定必须尽快，且必须**同时**解决深度与命名。

---

## §3 ② 有没有"偷偷新增键"

### §3.1 判法（可复跑）

```
# 1) 从真·已安装 14 件抽取"合法键集合"（含各级路径 + 裸名）
$ cd .worktrees/ws-ch2-rules && python3 /tmp/keycmp.py
已安装 rules/*.yaml 件数 = 14
合法键集合（含各级路径与裸名）size = 684

# 2) 用 AST 抽两流**所有** .get()/下标 的字符串键，与合法键集合逐一比对
=== 13-A (…/valuelayer) ===
  .get()/下标 字符串键 共 67 处（去重 46 个名）
  不在已安装键集合里的 .get()/下标 键名 37 个：[…]
=== 13-B (…/pricelayer) ===
  .get()/下标 字符串键 共 65 处（去重 50 个名）
  不在已安装键集合里的 .get()/下标 键名 40 个：[…]
```

**★ 这 37/40 个里绝大多数是"假阳性"**：它们是 `facts/*.jsonl` / `derived/*.jsonl` 的**记录字段**（`business_id` / `driver_id` / `snapshot_id` / `solution_set_id` / `baseline_id` …），来源是 `schema/`，**不是 `rules/`**。
⇒ 单靠"名字不在 rules 键集合里"**不能判违规**。必须**逐处确认该 `.get()` 的宿主对象是否由 `rules/` 装载**。我按此收窄，结论如下。

### §3.2 13-A —— 键名 ✅ **好**；夹具 ❌ **不够**

**(a) 从 `rules/` 装载的对象，其键名全部对齐**（11/11 ✅）：

```
$ cd .worktrees/ws-ch2-rules && python3 -   # keyset(已安装件)
=== 13-A 读的 metric-set 项字段（修正后） ===
  metric_set_id                -> ✅在        metrics                      -> ✅在
  model_class                  -> ✅在        currency                     -> ✅在
  stages                       -> ✅在        linked_accounts              -> ✅在
  basis                        -> ✅在        metric_item_fields           -> ✅在
  segment_evidence             -> ✅在        financial_link               -> ✅在
  extension_policy             -> ✅在
```

**正向对照（13-A 的读口能吃真件）**：

```
4) _rules.metric_sets(REAL)：
   ✅ 返回 4 个指标集: ['MS-HW-6STAGE', 'MS-CLOUD-5STAGE', 'MS-SW-5STAGE', 'MS-GENERIC']
```
`_rules.py:127-130` 对 `metric_sets:` 包裹层做了**兼容分支**（顶层 list **或** `{"metric_sets":[…]}`，且**非法形态响亮失败、不静默返回空表**），故我 13-R 在 `metric-sets.yaml` 用的包裹层**不构成问题**。**这是 13-A 主动做的兼容，应记功。**

**(b) ❌ 但夹具自造了一份"形状不同"的 `rules/baseline.yaml`**：

```
$ sed -n '90,109p' .worktrees/ws-ch4-valuelayer/system/tests/valuelayer/_fixtures.py
BASELINE_CFG: dict[str, Any] = {
    "min_nonnull_rate": 0.8,
    "min_fields_per_section": 1,
    "min_locators": 1,                       ← 扁平 + 旧键名
    "min_derivations": 1,                    ← 扁平 + 旧键名
    "max_primary_drivers_per_business": 5,
}

def write_rules(root: Path, *, cfg: dict[str, Any] | None = None, metric_sets: list[dict] | None = None) -> None:
    """在**夹具副本**里写候选 `rules/baseline.yaml` 与 `rules/metric-sets.yaml`。"""
    rules = root / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / "baseline.yaml").write_text(
        yaml.safe_dump(cfg if cfg is not None else BASELINE_CFG, allow_unicode=True, sort_keys=False),
```

`system/tests/conftest.py` 的 `code_root` 夹具**复制整个 `SYSTEM_ROOT` 但不清空 `rules/`** ⇒ 真件在副本里**本来就在**；而 `write_rules()` **另写一份覆盖它**。结果：
- 夹具把它**自己的形状**（扁平 + 旧键名）**顶替了已安装件**；
- 测试在夹具上**全绿**，在真件上**全红**（§2.2）。

**判定：❌ 不够。** 用团队长的原话校准：这不是"在 `rules/` 里偷偷新增键"（13-A **确实没写 `rules/`**，见 §5.1），而是**在夹具副本里自造键名/结构，并把代码契约建立在其上** —— **净效果等价于改了契约**。且因为夹具"看起来像真件"（同样的相对路径 `rules/baseline.yaml`），**绿灯具有误导性**。

★ 13-A 的夹具 docstring **是诚实的**（未把夹具值冒充设计值）：
```
23:★ 这些**值**是夹具的输入，不是对设计的声明 —— 真仓库的 `rules/baseline.yaml` 由 13-R + 主理人安装。
```
⇒ 问题不在"撒谎"，在"**夹具与真件形状不同却共用同一路径约定**，缺少一条'夹具形状必须等于已安装件形状'的断言"。

### §3.3 13-B —— ✅ **好**（含一条对我先前判断的更正）

```
=== 13-B 读的 rules 键 是否在对应已安装件里 ===
  valuation-methods.yaml   method_routing             -> ✅在
  valuation-methods.yaml   registry_driven            -> ✅在
  scenario.yaml            scenario_method_status     -> ✅在
  scenario.yaml            method_version             -> ❌不在

=== 全 14 件里是否有任何一件含键名 method_version ===
   无（14 件皆无 method_version）
```

**运行时实测（13-B 能吃真件，且中国话逐字一致）**：

```
$ cd .worktrees/ws-ch5-pricelayer && python3 -    # REAL = ws-ch2-rules/system
1) valuation.load_method_routing(REAL) -> ✅ 类: ['cloud', 'etf', 'hardware', 'software']
     hardware   -> ('正常化利润', '含再投资现金流', '分部估值', '同行比较')
     cloud      -> ('含再投资现金流（订阅/用量）', '分部')
     software   -> ('正常化利润', '现金流', '留存指标')
     etf        -> ('简化底稿',)
2) scenario_guard.load_scenario_policy(REAL) -> ScenarioPolicy(status='pending', value_source='rules',
   method_version='', notes=())
     status='pending' value_source='rules' method_version=''
EXIT=0
```

- **`method_routing` / `registry_driven`** ✅ 在：13-B 自选的 YAML 键名（设计 §D.1 **未给键名**，`valuation.py:38` 自陈"设计**没有给**"），与我 13-R 报告的 §4.2（"设计给了映射内容但没给键名"）**一致** ⇒ **自选键名合法**，不算新增。★ 这是"两流各自补了设计没给的键名、且**恰好对上**"——运气成分应被记录。
- **`method_version`** ❌ 不在 14 件里 —— **但这不是缺陷，我先前判断错了**（更正见 §6.2）。设计 `05/02:260` 逐字：
  > **待定转正流程**：样例确定后 → 写 `rules/scenario.yaml`（版本化）→ `status` 转 `neutral`/`probability_weighted` + 记 `method_version`。

  即 `method_version` 是**转正时才写入** `rules/scenario.yaml` 的字段。当前首版 `status=pending`，**故它现在就不该存在**。13-B 读它并容忍缺失（`str(doc.get("method_version") or "")`）**是设计所许**。⇒ **✅ 好。**
- **无新增键**：13-B 对 `rules/` 的全部引用只有 `rules/valuation-methods.yaml` 与 `rules/scenario.yaml`（`grep -rn 'rules/'` 全文见 §5.1），键引用仅上列 4 个。**没有在 `rules/` 或夹具里自造任何键。** ✅

---

## §4 ③ 有没有硬编码阈值（逐项"是/否 + 为什么"，**不一刀切**）

**判据**（团队长给定）：`施工图 §8 纪律 1` 禁的是"**参数进决策函数**"；`P-09` 禁 `weight`/`score`/`vote`。**纯算术常量、格式宽度、计算护栏不算违规。**

### §4.1 13-A —— ✅ **好**

```
$ cd .worktrees/ws-ch4-valuelayer && grep -nE '^[A-Z_]+ *[:=].*[0-9]|Decimal\("[0-9]|>= *[0-9]|<= *[0-9]|> *[0-9]|< *[0-9]' system/scripts/valuelayer/growth_quality.py
59:_ROOT = pathlib.Path(__file__).resolve().parents[2]      ← 路径解析，非阈值
```

- `growth_quality.py`（增长质量分档，重点点名文件）：**零数值阈值常量**。上限唯一来源 = `rules/baseline.yaml`，读不到 ⇒ `MissingRuleInput`。
- `completeness.py`：四个阈值**全部**经 `_rules.baseline_threshold_from(cfg, …)`（422/449/523/621），无字面兜底。
- `_rules.py` docstring 第 2 条把"**不内置任何兜底默认值**"写成硬约束，并给出理由（`G-03`：代码里放默认数会让"规则文件其实没写"变成**不可观测**）。★ **这是本项目里少见的把纪律写成机制而非口号的实现。**
- `_rules.py` 还刻意把 `MissingRuleInput(ValueError)` 与"命中违例"分开（`exit 2` vs `exit 1`），并**记录了初版继承 `RuntimeError` 导致异常穿透、把输入异常伪装成违例的实测教训**。

**判定：✅ 好。** 13-A 的问题在**读什么名字/什么深度**（§2），**不在**"把阈值写死在代码里"。这两件事必须分开裁 —— 否则会开错药方。

### §4.2 13-B —— 三项 ✅/❌ 分开判

```
$ cd .worktrees/ws-ch5-pricelayer && grep -nE '^[A-Z_]+ *[:=].*[0-9]|: *(int|Decimal|float) *= *[0-9]' system/scripts/pricelayer/solver.py
73:METHOD_VERSION = "pricelayer-solver-v1"
79:DEFAULT_DISPLAY_CAP = 3
82:MAX_DISPLAY_CAP = 5
85:DEFAULT_MIN_SOLUTIONS = 2
317:    max_grid_points: int = 256,

$ grep -nE '^[A-Z_]+ *[:=].*[0-9]|: *(int|Decimal|float) *= *[0-9]' system/scripts/pricelayer/{order_guard,valuation,scenario_guard}.py
order_guard.py:67:_ROOT = …                     ← 路径解析
valuation.py:61:_ROOT = …
valuation.py:77:METHOD_VERSION = "pricelayer-valuation-v1"
valuation.py:185:    max_nodes: int = 512,
scenario_guard.py:65:_ROOT = …
```

#### (a) `DEFAULT_DISPLAY_CAP = 3` / `MAX_DISPLAY_CAP = 5` —— ❌ **不好**

13-B 自己标注了出处（诚实的）：
```
79:DEFAULT_DISPLAY_CAP = 3
"""解集**默认展示组数**（`00_待拍板项清单` B18 已确认："默认展示 3 组，最多 5 组"）。"""
82:MAX_DISPLAY_CAP = 5
"""解集展示**硬上限**（同上 B18："最多 5 组"）。"""
```

设计核对：
```
$ cd .worktrees/ws-ch2-rules && grep -n 'B18' 00_待拍板项清单.md
75:| B18 | 估值解集展示上限 `N` | **默认展示 3 组，最多 5 组**〔新给〕 | `05/02` J3 |
$ grep -n '解集展示上限' '05_价格与市场预期研究/02_实现方案.md'
460:| J3 | 解集展示上限 N | 待定 | 上限 + 区间包络折叠 |
```

**判定：❌ 不好。** 理由：
1. 这是**已拍板的设计参数值**（B18〔新给〕确认为 3/5；`§J3` 原为"待定"，由 B18 收口）⇒ 按单一真源纪律应住 `rules/`，**不应住代码**。
2. 方向与 `G-06` 正相反：我在 13-R 报告 §4.2 把 N-5/B18 登记为"设计给了值但**没给键名、未指派文件**"，团队长裁定**"保持不收"**（即暂不落 `rules/`）；13-B 于是把它**落进了代码** —— 结果它从"rules 侧待登记"变成了"**code 侧的既成事实**"。**"不收进 rules"≠"写进代码"。**
3. ★ **减轻情节（必须写清，否则是过度指控）**：这两个常量在 `pricelayer/` 里**零引用**：
```
$ grep -rn 'DEFAULT_DISPLAY_CAP\|MAX_DISPLAY_CAP\|DEFAULT_MIN_SOLUTIONS' system/
(exit=1)
```
   ⇒ 它们是**死常量**，**当前不影响任何决策输出**。按判据（禁"参数进决策函数"）严格讲它们**尚未进入决策路径**。
   ⇒ 故定档 **不好**（值错位真存在、且埋了雷），**不是"错"**（未产生错误行为）。**风险项**：一旦接线（解集折叠/展示），就立即变成真实违规。

#### (b) `DEFAULT_MIN_SOLUTIONS = 2` —— **不够**

```
85:DEFAULT_MIN_SOLUTIONS = 2
"""`Ch5 §B.1` 的**多解下限**："欠定方程 ⇒ 必须展示多组解"。低于此值 ⇒ `SingleSolutionError`。"""
```

设计核对：
```
$ grep -n '欠定\|多组解\|必须展示' '05_价格与市场预期研究/02_实现方案.md'
69:价格 `P = f(g, m, r, k, T)`（增长 g、利润 m、再投资 r、风险 k、持续时间 T）是**欠定方程**——
   一个 P 对应**无穷多组**解。故**必须展示多组解**，否则会把某一解误当"市场的唯一真相"。
```
设计只写"**多**组解"，**没有任何字面 2**；`§J3` 的"上限 N"是**上限**不是**下限**。

**判定：不够。** "多"⇒ ≥2 的推演**合理但属代码自定**；既未参数化，也未登记为"待裁定"。它**不在 11 项冻结参数内**，故不触发 `param_ref` 指针纪律。修法二选一：登记为待裁定，或参数化进 `rules/`。（与 (a) 不同：(a) 有 B18 明文，是无争议的"值错位"。）

#### (c) `max_grid_points = 256` / `max_nodes = 512` —— ✅ **不是违规**

```
317:    max_grid_points: int = 256,
185:    max_nodes: int = 512,
```
设计 `05/02:438` 确实把**网格参数**指派给了 rules：
```
438:| **反解搜索空间** | 固定 4 类解第 5 类，每类含区间 → 组合数随离散粒度指数增长 |
     限制每类假设的离散粒度 + 网格搜索上界（`rules/valuation-methods.yaml`） |
```
★ **但这是两个不同的量**：
- 被指派给 `rules/` 的是「**网格搜索上界**」= **取值上界**（value upper bound，我 13-R 转写为 `assumption_grid.grid_search_upper_bound: tbd`）；
- `max_grid_points` / `max_nodes` 是「**网格点数上限**」= **组合爆炸护栏**（compute guard），属实现细节。

**判定：✅ 不是违规。** 是**实现护栏**，非设计参数。**但留一条警示**：这两者名字相近，**极易被将来的人混成同一个东西**（那就会变成双真源）。建议（不改文件）在报告/注释里把二者显式区分 —— 13-B 的 docstring 已部分做到，值得再点明一次。

#### (d) `grid_step: Decimal` **必填无默认** —— ✅ **好**

```
$ grep -n '离散粒度\|参数化' system/scripts/pricelayer/solver.py
"""… 离散粒度由**调用方显式传入**（本层不内置数值，`Ch5 §J2` 要求参数化）"""
```
⇒ 与 13-A 的 `_rules.py` 取向一致（**缺输入就响亮失败，不给默认值**）。✅

#### (e) `scenario_guard` 的 `design_default` 兜底 —— ✅ **好**（附一条 `G-03` 观察）

```
$ sed -n '140,166p' system/scripts/pricelayer/scenario_guard.py
    if root is None:
        return ScenarioPolicy(status=DEFAULT_SCENARIO_METHOD_STATUS, value_source="design_default")
    path = Path(root) / SCENARIO_YAML
    if not path.exists():
        return ScenarioPolicy(
            status=DEFAULT_SCENARIO_METHOD_STATUS, value_source="design_default",
            notes=(f"NO_SCENARIO_YAML: {SCENARIO_YAML} 不存在，按 Ch5 §E.4 的逐字默认 pending",),
        )
    doc = _cached_yaml(path) or {}
    status = doc.get("scenario_method_status")
    if status is None:
        return ScenarioPolicy(
            status=DEFAULT_SCENARIO_METHOD_STATUS, value_source="design_default",
            notes=(f"NO_SCENARIO_METHOD_STATUS: {SCENARIO_YAML} 缺该键，按 Ch5 §E.4 默认 pending",),
        )
    if status not in SCENARIO_METHOD_STATUSES:
        raise ScenarioGuardError(…)
```

**这是"设计明文许可的默认"，不是自造兜底** —— 设计 `05/02:256-258`：
```
256:scenario_method_status: pending | neutral | probability_weighted    # 默认 pending
258:- 首版方法（中性情景 vs 概率加权）未定 → **显式 `pending`，不静默默认**（N5.4-07 / C45-2）。
```
⇒ ① "默认 pending"**是逐字设计给的**；② 设计强调"**不静默**"，13-B 用 `value_source` + `notes`（含 `NO_SCENARIO_YAML` / `NO_SCENARIO_METHOD_STATUS` 两个具名 token）**显式标注了来源**；③ 非法取值 ⇒ `ScenarioGuardError` 响亮失败，**不许"未知状态当 pending 用"**。

**判定：✅ 好。** 三点都守住了。
★ **一条观察（不是缺陷，交团队长裁）**：13-A 的取向是"**规则文件缺失 ⇒ exit 2**"（不可判定就必须响），13-B 的取向是"**规则文件缺失 ⇒ 取设计默认 pending + 显式标注来源**"。两者都**有设计依据**，但**取向相反**。叠加我在 13-R 装的 `rules/scenario.yaml: scenario_method_status: pending` 之后，"文件没装"这件事在**状态值**上不可观测，只能靠 `value_source`/`notes` 发现 —— 正是 `G-03` 的形态（**不可观测 ≠ 已验证**）。是否要求两条流统一取向，需团队长定。

---

## §5 附带发现（越出三问，但影响交付）

### §5.1 ✅ 两流都**没碰** `rules/` 与 `registry/`（边界守住了）

```
$ git -C .worktrees/ws-ch4-valuelayer status --short system/rules system/registry
(rules/registry status 行数 = 0)
$ git -C .worktrees/ws-ch5-pricelayer status --short system/rules system/registry
(行数 = 0)
```
⇒ 团队长最担心的"**两流擅自改 `rules/` 契约**"**没有发生**。✅ 这一条是**好消息**，且是可核的（`rules/` 0444 + SHA256 锁未被触碰）。

### §5.2 ❌ 13-A 的新测试目录**未注册批次** ⇒ 会撞 `V-06`（**且 13-A 无权自己修**）

```
$ grep -rn 'valuelayer' .worktrees/ws-ch4-valuelayer/system/scripts/ops/verify.py \
    .worktrees/ws-ch4-valuelayer/system/registry/*.yaml
(无输出)
$ grep -rn 'pricelayer' .worktrees/ws-ch5-pricelayer/system/scripts/ops/verify.py   # 对照：13-B 已注册
（13-B 的 verify.py diff 见下）
```

`V-06`（`system/CONVENTIONS.md:225`）：
> **规范**：在 `tests/` 下新增**子目录**时，必须同时在 `verify.py::BATCHES` 里加一个批次。
> **为什么**：否则新测试**永远不被验证到** —— 而"没被跑"与"跑过且没问题"在报告里长得一样。
> **强制手段**：守卫断言 `tests/` 下每个含测试文件的子目录都有对应批次。

13-B **做了**（且其允许面含 `verify.py::BATCHES`）：
```
$ git -C .worktrees/ws-ch5-pricelayer diff HEAD -- system/scripts/ops/verify.py
+    "pricelayer": Batch(
+        # 新增测试目录必须同时加批次，否则 `V-06` 会把新目录判成"未覆盖"（`CONVENTIONS.md::V-06`）。
+        # 超时：工作树内实测 42.21s（124 例）→ **180s（≈4.3×）**：
+        "pricelayer", "tests/pricelayer/（Ch5 价格层：…）",
+        _pytest("tests/pricelayer"), 180.0, _exit_zero,
+    ),
@@ -409,6 +417,7 @@ ORDER = (
+    "pricelayer",
```
13-A **没做**，且其**允许面不含 `verify.py`**（任务卡 13-A：`scripts/valuelayer/**` + `tests/valuelayer/**` + `stage_gate.py` 一个函数体）。

`system/PROGRESS.md:228-229` 已把这类事件记为**派单疏漏**并给了教训：
```
228:3. **派单疏漏**：批次只加在 `main`/`integration`，**没进 WS 工作区** → WS 的 V-06 必红（已据 §1.5 授权 `--no-verify`）。
229:   **教训：若 WS 需遵守 V-06，应在派单时就预置批次**。
```

⇒ **需要一次裁定**：要么现在给 13-A 补 `verify.py::BATCHES` 的 `valuelayer` 批次（谁做？13-A 允许面外），要么像 13-B 那样**显式授权 13-A 改 `BATCHES`**。**不要**让它变成第二次 `--no-verify`（本项目明令禁）。

### §5.3 ⚠️ 13-A 有一处**潜在越界**（尚未发生）

`stage_gate.py` 的注释声明：
```
+    #     配套的可执行反例登记在 `registry/criterion_counterexamples.yaml`
+    #     （`criterion_effectiveness_guard` 会 AST 校验那条测试真实存在且函数名含判据 id）。
```
但 `registry/` 当前**状态为空**（§5.1）⇒ **尚未写**。若 13-A 稍后写 `registry/criterion_counterexamples.yaml`，即**越出其允许面**（该文件不在 13-A 的 `scripts/valuelayer/**` + `tests/valuelayer/**` + `stage_gate.py` 之内）。
⇒ **提前提示团队长**：`criterion_effectiveness_guard` 要求"绑定判据必须有真实测试 + 反例登记"，而这条义务**跨了两个文件的允许面**。**建议在派单层面明确归属**（可由团队长自己登记，或授权给 13-A）。这是**结构性**的，不是 13-A 的失误。

### §5.4 ✅ `reports/*.json` **不是**卫生问题（避免假阳性 —— 我一度想报）

```
$ git check-ignore -v reports/pricelayer_solver_2026-09-16.json ; (exit=1)   # 未被忽略
$ git ls-files reports | wc -l ; 0                                            # main 上从不跟踪
$ grep -n 'reports' system/scripts/_common.py
73:    """把报告落 `reports/<checker>_<date>.json`（`Ch2 §B.4`：命中 → 写报告）。"""
74:    out_dir = code_root / "reports"
```
⇒ `<root>/reports/<checker>_<date>.json` **正是** `P-02`/`Ch2 §B.4` 规定的落盘位置，且从不入库（`git ls-files reports` = 0）。13-B 工作树根的 6 个 JSON **是本该在那里的产物**。**不是问题**（记下来是为了说明"我核过、不是漏看"）。

---

## §6 对我自己先前判断的更正（诚实纠错）

### §6.1 「`thresholds:` 包裹层」——我原本准备指控 13-A，核完设计后**指向我自己**

我在备稿时把 `_rules.py` 的"顶层映射"说法当作 13-A 的**自选解释**。核设计后，它**有逐字依据**：
```
04/02:203:| 上限 | `rules/baseline.yaml: max_primary_drivers_per_business`（默认 5，可配） |
04/02:210:    if len(primary) > cfg.max_primary_drivers_per_business:
04/02:211:        raise TooManyDrivers(len(primary), cfg.max_primary_drivers_per_business)
04/02:364:              nonnull_rate(baseline) >= cfg.min_nonnull_rate,
04/02:483:| N4.1-05 | P0 | `rules/baseline.yaml:max_primary_drivers_per_business` + `validate_driver_count` | …
```
⇒ 设计确实用 `file: key` 与 `cfg.key`（**扁平**）两处写法。**13-A 不是凭空解释的。**

**BUT —— 我又做了第二个判别性检验，结论反过来了：**

**检验 A：设计是否用点号表达深度？**
```
$ cd .worktrees/ws-ch2-rules && grep -n 'thresholds' '04_公司价值研究与深度标准/02_实现方案.md'
(exit=1)    ← 设计**全文没有 thresholds 一词**
```
⇒ 支持"扁平"。

**检验 B：存量 10 件的读法惯例？**（这才是项目内的**既成契约**）
```
$ python3 -c "…打印 14 件顶层键…"
banned_tokens.yaml          顶层=['decision_scope', 'exempt_namespaces', 'reference_only', 'tokens', …]
benchmark.yaml              顶层=['benchmark_objects', 'change_governance', 'return_guard', …]
data-sources.allowlist.yaml 顶层=['budget_policy', 'decision_anchor', 'launch_criteria_ref', 'param_ref', 'sources', …]
freeze.yaml                 顶层=['ban_new_gate_anchor', 'freeze_params', 'frozen_at', 'invariants', …]
notification.yaml           顶层=['delivery_stage', 'implementation_status', 'interface', 'param_ref', 'red_lines', …]
pipeline.yaml               顶层=['anti_kpi', 'completeness', 'steps', …]
publish.yaml                顶层=['three_layer_permission', 'red_lines', 'interface', …]
review.yaml                 顶层=['anti_delay', 'anti_fake_signal', 'forced_recheck', 'tier', …]
schedule.yaml               顶层=['cadence', 'four_timestamps_ordering_required', 'latency_target', 'param_ref', …]
scope.yaml                  顶层=['coverage_scope', 'fake_coverage_guard', 'first_version_boundary', …]
```
⇒ **存量 10 件 100% 是"分组包裹"**，没有一件是"把参数平铺在顶层"。

**检验 C（关键先例）：设计写 `schedule.yaml:trading_calendar`，实际装在 `cadence` 下并被按 `::cadence.timezone` 读。**
```
08_产品入口与每日运行/02_实现方案.md:239:  `schedule.yaml:trading_calendar`
system/reports/ws_ch8_daily_report.md:216:  `schedule.yaml::cadence.timezone`（`tbd` …
```
⇒ 项目已确立的读法是：**设计的 `file:key` 记法命名的是"项"，不锁定深度**；消费者用 `::group.key` 形式读。
**同源先例 2**：设计写 `freeze.yaml::freeze_param`（单数），实际顶层键是 **`freeze_params`**（复数）——**安装件的拼写也可与设计字面不同，且世界照常运转。**

**结论（诚实版）：**
> 设计对 `baseline.yaml` 的**深度是欠定的**，而"是否扁平"**两种读法都能从文本里找出依据**。但项目**既成契约**（存量 10 件全分组 + `schedule` 先例）**偏向分组**；真正的判据应是"**安装件为准**"这条已有裁定。
> ⇒ 因此，**我把 `thresholds:` 包裹层写进安装件，与"扁平"派的 13-A 产生冲突，责任是共同的**；且既然采用"已安装件为准"，那么**要改的是 13-A 的读路径**（改成读 `thresholds.*`）——**但这必须由团队长明文重申，因为"已安装件为准"上次只被用来裁命名。**
> ⇒ 我**撤回**"13-A 读错"的单方面指控；改为"**两流契约不一致，需一次覆盖'深度'的裁定**"。
> ⇒ 若团队长改判"扁平为准"，则 **我 13-R 的产出需要改**（代价：`rules/` 0444 锁 + 重锁 + 14 件的 `rules_lock_guard` 重跑），**这次改动会落在我头上**，我准备好承接。

### §6.2 「13-B 的 `method_version` 是潜在缺口」——**我错了，撤回**

我原先记为"13-B 读了 14 件都没有的键 ⇒ 潜在缺口"。核 `05/02:260` 后：`method_version` 是**转正时才写入** `rules/scenario.yaml` 的字段，首版 `pending` **本就不该有**。13-B 读它并容忍缺失，**正确**。⇒ 改为 **✅ 好**（已落 §3.3）。

### §6.3 「13-A 的 4 个键全缺」——**不完整，已补全**

我第一次的结论只打到"键名"层。补做后是**两层**（键名 + 深度），且**改名无效**（§2.2 的 `min_locator_count -> ❌`）。若只报第一层，团队长按"改名字"派活，**会白干一轮**。这是本报告最有价值的一次自我纠正。

---

## §7 待裁定与下一步

### §7.1 需团队长裁定的三件事（按紧急度）

| # | 事项 | 为什么必须你来裁 | 建议 |
|---|---|---|---|
| **R-1** | **`rules/baseline.yaml` 的深度契约**：`thresholds.*`（现装）还是扁平（13-A 读法）？ | "已安装件为准"上次只覆盖了键名，**没覆盖深度**；而深度决定"改谁"（改 13-A 的读路径 **vs** 改我 13-R 的安装件 + 重锁） | 若维持"已安装件为准"⇒ 13-A 改为 `cfg["thresholds"][…]`；**同时**必须把 `min_locators→min_locator_count` 一起改（否则仍失败） |
| **R-2** | **`tests/valuelayer/` 的 `V-06` 批次归属** | 13-A 的允许面**不含** `verify.py`；`PROGRESS.md:228` 已定性为"派单疏漏" | 授权 13-A 改 `verify.py::BATCHES`（对齐 13-B 的做法），或你自己补 —— **不要**落到 `--no-verify` |
| **R-3** | **13-B 的两个死常量**（`DEFAULT_DISPLAY_CAP=3` / `MAX_DISPLAY_CAP=5`，B18 已拍板值） | 它们**零引用** ⇒ 现在无害；但"值住代码"与 `G-06` 反向，且接线即违规 | 二选一：**移进 `rules/`**（需给键名 + 指派文件，正是 13-R §4.2 登记的那批）／或**明确授权为"暂存于代码、接线前必须迁出"**并登记 |

### §7.2 提交后必须重跑的（本报告结论对应未提交快照）

13-A/13-B **提交后**，请按其 commit hash 重跑下列三条（我可复跑）：

```bash
# ② 键集合比对（本条覆盖两流全部 .get()/下标 键）
python3 /tmp/keycmp.py                    # 脚本原文见 §3.1；我已落盘在 /tmp

# ① / ③ 真实已安装件下的运行时断言（最有力的一类证据）
cd .worktrees/ws-ch4-valuelayer && python3 -   # §2.2 / §2.4 的探针（改 root 指向已装件）
cd .worktrees/ws-ch5-pricelayer && python3 -   # §3.3 的探针
```

**未完成的覆盖（如实登记，不冒充已核）**：
- 我的键集合比对只覆盖了**从 `rules/` 装载的 4 个文档**（`baseline` / `metric-sets` / `valuation-methods` / `scenario`）。两流对**其余 10 件**（`freeze.yaml` / `pipeline.yaml` / `schedule.yaml` / `data-sources.allowlist.yaml` …）的引用：13-A 无、13-B 仅在 `step.py:6` 的**注释**里提到 `rules/pipeline.yaml`（非读取）—— 已用 `grep -rn 'rules/' system/scripts/{valuelayer,pricelayer}/ system/tests/{valuelayer,pricelayer}/` 全文核过（命中行即 §3.3 与 §5.2 引用的那些；13-A 全部命中集中在 `_rules.py` 的路径常量与注释），**但这两流的文件仍在增长**，提交后需再核一遍增量。
- `pricelayer` 的**决策路径**我只做了静态阅读 + 常量抽取，**未跑其单测**（避免与它们的 pytest 会话抢配额，`V-05`/`V-08`）。故 ③ 的"是否进入决策函数"是基于**调用点 grep**（`DEFAULT_DISPLAY_CAP` 零引用为实测），**不是**运行时追踪。
- 13-A 的 `rollup.py` / `moat_guard.py` / `state_machine.py` 是**我上次快照之后新增**的文件，我只做了键引用扫描，**未逐行读**。

---

## §8 命令与退出码清单（全部实测原样）

| 命令 | 结果 | 退出码 |
|---|---|---|
| `git -C .worktrees/ws-ch2-rules status --short` | 空 | 0 |
| `ls system/rules/*.yaml \| wc -l` | `14` | 0 |
| `git -C ws-ch4-valuelayer status --short system/rules system/registry` | 0 行 | 0 |
| `git -C ws-ch5-pricelayer status --short system/rules system/registry` | 0 行 | 0 |
| `grep -n 'CFG_' ws-ch4-valuelayer/…/completeness.py` | 84/85 仍是 `min_locators`/`min_derivations` | 0 |
| `python3` §2.2 探针（5 键 × 真件） | 6/6 全部 `MissingRuleInput`（含 `*_count`） | 0 |
| `python3` §2.4 探针（`g_depth_violations(REAL)`） | 1 条 `FATAL` | 0 |
| `python3` §3.2 探针（`_rules.metric_sets(REAL)`） | 4 个指标集 | 0 |
| `python3` §3.3 探针（13-B 读真件） | 4 类方法 + `status=pending value_source=rules` | 0 |
| `grep -rn 'DEFAULT_DISPLAY_CAP\|MAX_DISPLAY_CAP\|DEFAULT_MIN_SOLUTIONS' ws-ch5-pricelayer/system/` | 无输出（零引用） | **1** |
| `grep -n 'thresholds' 04_…/02_实现方案.md` | 无输出（设计无此词） | **1** |
| `git check-ignore -v reports/pricelayer_solver_*.json` | 无输出（未忽略） | **1** |
| `git ls-files reports \| wc -l` | `0` | 0 |

> `exit=1` 出现在**"grep 没匹配到"**的行上，是**预期结果本身**（"设计里没有这个词"/"零引用"就是结论），非命令失败。

---

## §9 一句话给团队长

**好消息**：两流**都没碰 `rules/`**（契约未被擅自改）；13-B 的读口**能吃真件且逐字正确**；13-A 的"缺阈值即响亮失败、绝不内置默认值"是**本项目里少见的把纪律做成机制**的实现，且它**成功地把一次契约冲突从"静默用错阈值"变成了"响亮报不可判定"** —— **这正是 fail-loud 该有的样子**。

**坏消息**：`tests/` 级别的绿**掩盖了集成级的红** —— 13-A 在真仓库上 `chapter4_g_depth` **恒 FATAL**，而根因**两层**（键名 + 深度），**只改键名会白改一轮**；责任**一半在我**（`thresholds:` 包裹层是我写进安装件的，我已在 §6.1 撤回单方面指控并准备承接改回扁平的代价）。

**请裁 R-1 / R-2 / R-3**（§7.1）。
