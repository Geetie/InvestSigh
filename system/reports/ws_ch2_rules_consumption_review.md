# 规则消费面复核 —— 13-A（`ws/ch4-valuelayer`）/ 13-B（`ws/ch5-pricelayer`）

**复核人**：`ws-ch2-rules`（13-R 的产出方 = 被审契约的**作者**，故本报告含**自我指控**，见 §6）
**复核对象**：两流**未提交**的工作树快照（**会动**，SHA 见 §0.2）
**被审文件一律未改**：本报告只读两流；唯一写入物 = 本文件。
**结论档位**：好 / 不好 / 未做 / 不够 / 错（+ ✅/❌ 对照），每条附实测命令原样输出。

---

## §0 快照与对象

> ★ **本报告已随 `R8` 裁定更新**（`R8-1`/`R8-2`/`R8-3` 三项均已裁定，落账见 **§10** 与 §6.1b / §5.2 / §4.2）：
> ① `rules/baseline.yaml` 深度契约 = **分组为准**（团队长把「深度约定」写进该文件并重锁）；
> ② 13-A 的共享文件归属 = **已修表授权**（并行边界表回填 + 授权收窄）；
> ③ 13-B 的 B18 常量 = **改为迁进 `rules/`**，并立"参数 vs 护栏"统一判据。
> 本工作区已 `git merge main`（含 `17fac7d` R8 落账 + `0f618a9` 剥离候选期描述），HEAD = `9454311`。

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

### §0.3 提交后重跑：`#69` 的落点（**读 §11 / §12 请从这两节进，别用 §0.2 的旧快照**）

| 节 | 对应 commit | 内容 |
|---|---|---|
| **§11** | 13-B = **`4468da5`**（已合并）；13-A 仍 `d74a829` | ②③ 的 13-B 面复跑 + ★★ 一条**自我更正**（"`grep` 零引用 = 死常量"是**假阴性**，③ 定档上调为**错**） |
| **§12** | 13-B = `4468da5` 后的 **`main` = `c591082`**；13-A = `bb8991a`（**零领先提交**） | **`R8-3` 收口核**（`rules/` 侧 ✅ 已装 / **代码侧 ❌ 未做 ⇒ `G-06` 双份**）+ `R8-1`/`R8-2` 在 13-A 面 **⛔ 无被检对象**（`G-03`） |

⇒ 全文的 ②③ 结论按 **§11 + §12** 为准（§1 总览与 §7.1 已同步改档）；**§2–§10 的 SHA 仍是 13-A/13-B 未提交期的快照**，保留作过程证据。

---

## §1 结论总览

| # | 复核项 | 13-A（Ch4 价值层） | 13-B（Ch5 价格层） |
|---|---|---|---|
| ① | 键名对齐 | ❌ **未做**（仍是 `min_locators`/`min_derivations`）——且**改名也救不了**，见 §2.3 | n/a（无此清单） |
| ② | 偷偷新增键 | ✅ 键名 **11/11 全对齐**；❌ **夹具自造了不同形状的 `baseline.yaml`** ⇒ **不够** | ✅ **好**（无新增键；`method_version` 缺键**符合设计**） |
| ③ | 硬编码阈值 | ✅ **好**（阈值全部从 rules 读、缺键响亮失败） | ❌ **错**（B18 的 3/5 硬编码**且进决策函数**）+ ❌ **错**（`DEFAULT_MIN_SOLUTIONS=2` 无出处**且进决策**）+ ✅ **好**（`grid_step` 必填无默认）+ ✅ **不是违规**（`max_grid_points`/`max_nodes` = 护栏）<br>★ **2026-09-16 上调**：原判「不好/不够」基于"零引用=死常量"，该 `grep` 是**假阴性** ⇒ 见 **§11.2** |

**贯穿性结论（最重要的一条）**：
> 已安装的 `rules/baseline.yaml`（**我的 13-R 产出**）与 13-A 的读取路径**契约不一致**，且**不一致有两层**：① 键名后缀；② **YAML 嵌套深度**。
> 团队长先前的裁定「**已安装件为准**」只覆盖了第 ① 层。**只改键名的修法不会让任何一条阈值读通** —— 实测：改名后 `min_locator_count` **仍然失败**（§2.3）。第 ② 层需要一次新的、有依据的裁定，见 §7.1。
>
> ★ **已裁定（`R8-1`）**：第 ② 层**维持"分组（`thresholds.*`）为准"**，团队长把「深度约定」**写进 `rules/baseline.yaml` 并重锁**（§6.1b）⇒ **两条不一致都要改 13-A 一侧**，且**必须同时改**。故 §2.2 的"改名无效"实测仍是本轮最有价值的结论：**它阻止了一次白干**。

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

**判定：❌ 错**（原为「不好」，因我的"零引用"假阴性而**上调**，见下面第 3 条与 §11.2）。理由：
1. 这是**已拍板的设计参数值**（B18〔新给〕确认为 3/5；`§J3` 原为"待定"，由 B18 收口）⇒ 按单一真源纪律应住 `rules/`，**不应住代码**。
2. 方向与 `G-06` 正相反：我在 13-R 报告 §4.2 把 N-5/B18 登记为"设计给了值但**没给键名、未指派文件**"，团队长裁定**"保持不收"**（即暂不落 `rules/`）；13-B 于是把它**落进了代码** —— 结果它从"rules 侧待登记"变成了"**code 侧的既成事实**"。**"不收进 rules"≠"写进代码"。**
3. ~~★ **减轻情节**：这两个常量在 `pricelayer/` 里**零引用** ⇒ 死常量，未进决策路径，故定档「不好」不是「错」。~~
   ★★ **本条已被我自己推翻 —— 见 §11.2。** 那段 `grep` 是 **BSD `\|` 交替的假阴性**：三个常量**都在决策路径里**（`solver.py:318` 默认入参、`:336` 越界 raise、`:391` degraded 标记、`:403` 呈现前不变式 `SingleSolutionError`、`:503` 门禁 `Violation`）。
   ⇒ **定档上调为「错」**（`施工图 §8 纪律 1` 禁"参数进决策函数"，此处为**明确违反**）。
   ⇒ 且该错误已**进入团队长的裁定文本**（`batch13_taskbook.md:374` 引"（`grep` 零引用 = 死常量）"），**必须更正** —— 见 §11.2 与 §11.7。

★ **裁定结果（`R8-3`）：我的引用对，但结论被团队长推翻为"进 `rules/`"——依据更强，我接受。**
团队长指出：我判"暂不收"的**前提**是"**没有键名、没有指派文件**"，而**现在前提没了** —— `05/02:460 §J3` 就是 `00_待拍板项清单.md` **B18 的来源**，B18 已拍板 3/5 ⇒ **条件变了，裁定随之改变**。并给出一条**可复用的统一判据**（本报告 §10 采用）：
> **"影响产出取值/选择"的数 = 参数 ⇒ 必须住 `rules/`（`Ch11 §D.2` + `P-09`）；
> "仅为防组合爆炸/防卡死的上界" = 护栏 ⇒ 可住代码，但 docstring 必须明标为护栏。**
⇒ 故 `DEFAULT_DISPLAY_CAP=3` / `MAX_DISPLAY_CAP=5` = **参数** ⇒ 进 `rules/`（`basis` 记 B18）。**我"不好"的定档结论保留**（值错位判断成立），**处置方向由团队长改为"迁进 rules"**。收口内容见 **§10**。

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

**判定：❌ 错**（原为「不够」，同上**上调**；详见 §11.2 —— `2` 这个**设计无出处**的数在 `solver.py:391/403/503` **进入决策**：标 `degraded`、呈现前 raise `SingleSolutionError`、门禁产 `Violation`）。

★ **裁定结果（`R8-3`）：按统一判据处置为"不得自创"。** 团队长定：
> `DEFAULT_MIN_SOLUTIONS=2` = **设计无字面 2、B18 也没给** ⇒ **不得自创**，无出处就**删掉该常量**
> （改为"展示解数 = 求解器实际解出组数"）；确需下界则记 `tbd` 交需求方。
⇒ 我据此**补一层设计依据**（团队长未引，我核到）：`§B.1`（`05/02:69`）的"**必须展示多组解**"是**语义要求**（非数值），
   故"必须多解"这件事**应当保留为语义键**（而非数值键），数值下界落 `tbd`。收口内容见 **§10**。

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

★★ **归因更正（我的缺陷，团队长 `R8-2` 指出并已修表）**：我初稿在这里引了 `system/PROGRESS.md:228-229` 的"派单疏漏"。
**那条说的是另一件事**（批次只加在 `main`/`integration`、没进 WS 工作区），**不是本条**。本条的一手依据在**卡 13-A 自身**：
```
system/reports/batch13_taskbook.md:85 ← 卡 13-A「接线要求」第 2 条（V-06 必加批次）
                                  + DoD 第 3 条（必登记反例）
   ⟂ 与开头的「并行边界表」（原本只列 `scripts/valuelayer/**` · `tests/valuelayer/**` · 报告）
     ⇒ **相互矛盾**：按表读就是"越界"，按 DoD 读就是"必做"
```
团队长的裁定原文（修正后的任务卡 `batch13_taskbook.md:21-31`，**点名本复核**）：
```
> ★ **本表的原始版本漏了两处共享文件的"限量授权"，与下方 DoD 自相矛盾**（`ws-ch2-rules` 独立复核时指出，
> 主理人确认**是我的缺陷**，`R8` 已更正）：
> … 现值已补入，并把授权**收窄到"仅限本卡自己那一条"**：
> `verify.py` 只准加自己的批次条目（**不得动别家的，也不得改 `ORDER` 里别家的位置**），
> `criterion_counterexamples.yaml` 只准加自己的判据条目。跨卡冲突由主理人手工收（`R2` / `R3`）。
```
修正后的边界表（`batch13_taskbook.md:17`）已回填两个共享文件；`R2`（`batch13_taskbook.md:193-198`）另注：
```
> 13-A 需加 `valuelayer` 批次（`V-06`），13-B 已加 `pricelayer` 批次（`BATCHES` 条目 + `ORDER` 一行）。
> 两侧都改同一处必然冲突。**已明令 13-A 只加自己那条、不动 `pricelayer`**；合并冲突由主理人裁。
```
⇒ **本条已裁定并落账（`R8-2`）**：13-A 获得 `verify.py::BATCHES` 与 `registry/criterion_counterexamples.yaml` 的**限量授权**。**不要**让它变成 `--no-verify`（本项目明令禁）。一般化教训已写进任务卡："任务卡的「并行边界表」与「DoD」**必须同时更新**"，检查动作 = "新卡写完，**逐条把 DoD 里提到的每个文件回填进边界表**，少一个就是矛盾"。

### §5.3 ⚠️ 13-A 有一处**潜在越界**（尚未发生）

`stage_gate.py` 的注释声明：
```
+    #     配套的可执行反例登记在 `registry/criterion_counterexamples.yaml`
+    #     （`criterion_effectiveness_guard` 会 AST 校验那条测试真实存在且函数名含判据 id）。
```
但 `registry/` 当前**状态为空**（§5.1）⇒ **尚未写**。若 13-A 稍后写 `registry/criterion_counterexamples.yaml`，即**越出其（当时的）允许面**。
⇒ **提前提示团队长**：`criterion_effectiveness_guard` 要求"绑定判据必须有真实测试 + 反例登记"，而这条义务**跨了两个文件的允许面**。**建议在派单层面明确归属**（可由团队长自己登记，或授权给 13-A）。这是**结构性**的，不是 13-A 的失误。
★ **已裁定（`R8-2`，见 §5.2 的更正）**：团队长承认边界表漏回填是**他的缺陷**，已在 `batch13_taskbook.md:17` 把 `registry/criterion_counterexamples.yaml` 与 `verify.py::BATCHES` 补入 13-A 允许面并收窄授权 ⇒ **本条的"潜在越界"已消失**，13-A 现在**有权**写那条反例登记（仅限本卡自己那一条）。

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

### §6.1b 裁定结果（团队长 `R8-1`）—— **维持 `thresholds.*` 分组为准**，并把留白**显式写进安装件**

团队长逐条实测了我的证据（并**另加两条我没提的**：① 存量 10 件 **10/10** 均为"元数据 + 关注面分组"；② `baseline.yaml` 顶层有 **6 个互不相干的关注面**，摊平有键语义混淆风险），裁定**分组为准**，四条理由：
> ① 已安装件是**唯一被锁**的产物体（0444+SHA256+`rules_lock_guard`），为改深度重录 4 份设计 + 重锁 14 件，**语义收益为零**；
> ② "设计 `file:key` 记法**不锁深度**"已是项目既成契约（10/10 + 2 例同源先例）；
> ③ 设计 `cfg.X` 与分组**不矛盾** —— 把 `cfg` 读作 `baseline["thresholds"]` 即两立，所以这**不是"设计 vs 实现"冲突，是设计留白，留白由安装件填**；
> ④ 分组本身更优。

**落账实测**（`main::17fac7d`；我已 `git merge main`，本工作区 HEAD = `9454311`）：
```
$ sed -n '19,29p' system/rules/baseline.yaml
# ★★ 深度约定（主理人裁定 `R8-1`，2026-09-16）—— **本文件的分组深度为准。**
#   设计里 `cfg.max_primary_drivers_per_business` 这类 `cfg.<key>` 写法，一律读作
#   **本文件 `thresholds:` 分组下的键**（即 `cfg = baseline["thresholds"]`）；
#   设计里的 `rules/baseline.yaml: <key>` 是 **`file:key` 记法，不锁深度** ——
#   项目既成契约：存量 10 件规则文件 **10/10 分组包裹**，且有 2 例同源先例
#   （`schedule.yaml:trading_calendar` → 实装 `cadence.timezone`；
#    `freeze.yaml::freeze_param` → 实装 `freeze_params`）。
#   设计的这两种写法与分组**不矛盾**：设计没写深度，**深度由本件填**。
#   ⇒ 代码一律按**本文件实有结构**读；**不得**为迁就设计里扁平写法而摊平本文件。
```
⇒ **`R-1` 已闭合**。责任划分落为：**深度契约 = 分组（安装件）**，故**要改的是 13-A 的读路径**；`thresholds.*` 与 `*_count` **两处必须一起改**（§2.2 已证只改名字无效）。
★ 我**不需要**改回扁平，`thresholds:` 包裹层获得**明文追认**；我先前"准备承接改回 + 重锁"的预案**转为备用**（若将来再裁扁平，预案仍在 §6.1 末）。

### §6.2 「13-B 的 `method_version` 是潜在缺口」——**我错了，撤回**

我原先记为"13-B 读了 14 件都没有的键 ⇒ 潜在缺口"。核 `05/02:260` 后：`method_version` 是**转正时才写入** `rules/scenario.yaml` 的字段，首版 `pending` **本就不该有**。13-B 读它并容忍缺失，**正确**。⇒ 改为 **✅ 好**（已落 §3.3）。

### §6.3 「13-A 的 4 个键全缺」——**不完整，已补全**

我第一次的结论只打到"键名"层。补做后是**两层**（键名 + 深度），且**改名无效**（§2.2 的 `min_locator_count -> ❌`）。若只报第一层，团队长按"改名字"派活，**会白干一轮**。这是本报告最有价值的一次自我纠正。

---

## §7 待裁定与下一步

### §7.1 需团队长裁定的三件事（按紧急度）—— **★ 三项均已裁定，见 §10**

| # | 事项 | 为什么必须你来裁 | 建议 | 裁定 |
|---|---|---|---|---|
| **R-1** | **`rules/baseline.yaml` 的深度契约**：`thresholds.*`（现装）还是扁平（13-A 读法）？ | "已安装件为准"上次只覆盖了键名，**没覆盖深度**；而深度决定"改谁"（改 13-A 的读路径 **vs** 改我 13-R 的安装件 + 重锁） | 若维持"已安装件为准"⇒ 13-A 改为 `cfg["thresholds"][…]`；**同时**必须把 `min_locators→min_locator_count` 一起改（否则仍失败） | ✅ **`R8-1` 维持分组为准** + 已把「深度约定」写进 `rules/baseline.yaml` 并重锁（§6.1b） |
| **R-2** | **`tests/valuelayer/` 的 `V-06` 批次归属** | 13-A 的允许面**不含** `verify.py`（**修正后的一手依据**：卡 13-A「接线要求」第 2 条 + DoD 第 3 条 **⟂** 开头的并行边界表，**自相矛盾** —— 我初稿引的 `PROGRESS.md:228` 是**另一件事**，见 §5.2 的归因更正） | 授权 13-A 改 `verify.py::BATCHES`（对齐 13-B 的做法），或你自己补 —— **不要**落到 `--no-verify` | ✅ **`R8-2` 已修表**：边界表回填两个共享文件，授权**收窄到"仅限本卡自己那一条"** |
| **R-3** | **13-B 的两个死常量**（`DEFAULT_DISPLAY_CAP=3` / `MAX_DISPLAY_CAP=5`，B18 已拍板值） | ~~它们**零引用** ⇒ 现在无害~~ ★ **此话为假**（§11.2）：三常量**都在决策路径** ⇒ 是**明确违反** `施工图 §8 纪律 1`，**不是"现在无害"** | 二选一：**移进 `rules/`**（需给键名 + 指派文件，正是 13-R §4.2 登记的那批）／或**明确授权为"暂存于代码、接线前必须迁出"**并登记 | ✅ **`R8-3` 改为"进 `rules/`"**（前提变了：B18 的出处就是 §J3）；并立**参数/护栏统一判据**；`DEFAULT_MIN_SOLUTIONS=2` **不得自创、删常量**。收口见 §10 |

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

---

## §10 `R8-3` 收口：§J.3 逐字原文 + 逐键判定 + 候选内容（**待主理人安装**）

团队长要求"把 `05/02 §J3`（约 L460）的**逐字原文**贴回来 —— 键名 + 值 + 出处，并附按新判据的**逐键判定理由**"。
以下为我实测取回的一手原文（**`sed -n` 原样，未改写**）。

### §10.1 一手原文（逐字）

**（a）`05_价格与市场预期研究/02_实现方案.md` §J 技术待定项（**L454-462**，`grep -n '^## J\.'` 得 `454:## J. 技术待定项（仅第五章新引入）`）**
```
## J. 技术待定项（仅第五章新引入）

| # | 事项 | 选项 | 建议 |
|---|---|---|---|
| J1 | 反解数值方法 | 网格搜索 / 二分 / 优化器 | **网格 + 单调剪枝**（可单测、可控） |
| J2 | 每类假设离散粒度 | 待定 | 参数化 `rules/valuation-methods.yaml` |
| J3 | 解集展示上限 N | 待定 | 上限 + 区间包络折叠 |
| J4 | 情景标签体系 | 枚举 | 定义 `{bear, neutral, bull, custom}`，首版仅用一致标签 |
| J5 | `scenario_method_status` 转正条件 | 待样例 | 样例通过 + `rules/scenario.yaml` 版本化 |
```
★ **J3 本身只给"事项 + 建议"，值是「待定」** ⇒ **J3 不提供 3/5**。

**（b）值的来源：`00_待拍板项清单.md:75`（**B18〔新给〕**，出处栏直指 `05/02 J3`）**
```
| B18 | 估值解集展示上限 `N` | **默认展示 3 组，最多 5 组**〔新给〕 | `05/02` J3 |
```
★ 团队长的论证成立：**`05/02:460 §J3` 就是 B18 的来源**，B18 已把"待定"收口为 **3 / 5** ⇒ 键名/指派文件的前提已具备。

**（c）§I.2 风险表（L436-443 区域）—— 上限的语义（"超出折叠"）与护栏分界**
```
| **反解搜索空间** | 固定 4 类解第 5 类，每类含区间 → 组合数随离散粒度指数增长 | 限制每类假设的离散粒度 + 网格搜索上界（`rules/valuation-methods.yaml`） |
| **多解展示爆炸** | 可行解集可能很大 | 只保留**代表解 + 区间包络**（`solution_set` 上限 N，超出折叠） |
| **Worst-case** | `O(grid^k)`（k=假设离散点数） | 设网格上限告警；必要时用单调性剪枝/二分替代网格 |
```

**（d）"必须多组解"的语义来源：`05/02:69` §B.1**
```
价格 `P = f(g, m, r, k, T)`（增长 g、利润 m、再投资 r、风险 k、持续时间 T）是**欠定方程**——
一个 P 对应**无穷多组**解。故**必须展示多组解**，否则会把某一解误当"市场的唯一真相"。
```

### §10.2 逐键判定（按 `R8-3` 的统一判据）

> 判据：**"影响产出取值/选择"的数 = 参数 ⇒ 必须住 `rules/`**；**"仅为防组合爆炸/防卡死的上界" = 护栏 ⇒ 可住代码，但 docstring 必须明标为护栏**。

| 代码常量（现值） | 值 | 一手出处 | 判定 | 处置 |
|---|---|---|---|---|
| `solver.py:79 DEFAULT_DISPLAY_CAP` | `3` | `00_待拍板项清单.md:75` B18「**默认展示 3 组**」〔新给〕（出处栏 = `05/02 J3`） | **参数** —— 决定"**展示哪几组解**"，直接改变产出 | ⇒ 进 `rules/`（`basis` 记 B18）；代码**删除**该常量 |
| `solver.py:82 MAX_DISPLAY_CAP` | `5` | 同上 B18「**最多 5 组**」= `05/02:460 §J3`「解集展示**上限 N**」；语义另见 §I.2 `05/02:439`「只保留代表解 + 区间包络（`solution_set` 上限 N，**超出折叠**）」 | **参数** —— 决定解集**折叠边界**（改变产出） | ⇒ 进 `rules/`；代码**删除**该常量 |
| `solver.py:85 DEFAULT_MIN_SOLUTIONS` | `2` | **无出处**：`05/02:69 §B.1` 只写「**多**组解」（**无字面数**）；`§J3` 只给**上限**；B18 未给下界 | **无出处 ⇒ 不得自创**（`R8-3`） | ⇒ **删常量**，改"展示解数 = 求解器实际解出组数"；语义保留为**非数值键**，数值落 `tbd` + `basis` |
| `solver.py:317 max_grid_points` | `256` | `05/02:438` 指派给 rules 的是「限制每类假设的**离散粒度** + **网格搜索上界**」；`05/02:441`「设**网格上限告警**；必要时用单调性剪枝/二分替代网格」 | **护栏** —— 仅防组合爆炸，**不改变"展示哪组解"的取值/选择** | ⇒ **留代码**，但 docstring **必须明标为护栏** |
| `valuation.py:185 max_nodes` | `512` | 同上（计算护栏） | **护栏** | ⇒ **留代码** + 明标 |

★ **必须同框标注的混淆风险（我主动加的一条）**：`max_grid_points`（**点数**上限，护栏）与 `rules/valuation-methods.yaml::assumption_grid.grid_search_upper_bound`（**取值**上界，现 `tbd`，`§I.2` 明文指派进 rules）**名字太近**。混同即**双真源**。⇒ 建议接线时在这两处各写一行互指注释。

### §10.3 候选内容（键名 + 值 + 出处；**请主理人安装 + 重锁**）

**★ 我未写入任何位置** —— `rules/**` 是 0444 + SHA256、只准主理人安装；且 `registry/rule-candidates/` 已于 `bb32863` **转为安装件后清除**，任务卡 `batch13_taskbook.md:190-195` 明确该目录**不得复活**（否则成第二份真源，违 `G-06`）⇒ 故候选内容**只放在本报告里**。

```yaml
# ── 解集展示（§J.3 + 清单 B18；主理人 `R8-3` 裁定：属"参数" ⇒ 住本文件）──────────
#   键名为**转写选定**（设计 §J.3 只给"事项/选项/建议"，未给 YAML 键名）——
#   与 `13-R` 报告「逐字转写纪律」一致：值逐字、键名标注为转写。
solution_set_display:
  default_count: 3          # 清单 B18 逐字：「默认展示 3 组」〔新给〕；B18 出处栏 = `05/02` J3
  max_count: 5              # 清单 B18 逐字：「最多 5 组」= §J.3「解集展示上限 N」
  must_show_multiple: true  # §B.1 逐字：「故**必须展示多组解**」（**键名为转写**；此为语义、非数值）
  min_count: tbd            # §B.1 只写「多」、§J.3 只给上限、B18 未给下界 ⇒ **设计未给，不得自创**（`R8-3`）
  overflow_policy: "只保留代表解 + 区间包络（超出上限即折叠）"   # §I.2 风险行逐字
  basis:
    default_count: "00_待拍板项清单.md:75 B18〔新给〕「默认展示 3 组，最多 5 组」；B18 出处栏 = `05/02` J3"
    max_count: "同上 B18「最多 5 组」；= 05_价格与市场预期研究/02_实现方案.md §J.3「解集展示上限 N | 待定 | 上限 + 区间包络折叠」"
    min_count: "§B.1（05/02:69）只写「一个 P 对应无穷多组解。故必须展示多组解」，**无字面数值**；§J.3 只给上限 ⇒ 占位缺失，待需求方拍板"
    overflow_policy: "§I.2 风险表「多解展示爆炸 | 可行解集可能很大 | 只保留代表解 + 区间包络（`solution_set` 上限 N，超出折叠）」"
  solver_ref: scripts/pricelayer/solver.py   # §B.3 逐字：「求解 | **程序** | 固定 4 类解第 5 类；…（`scripts/pricelayer/solver.py`）」
```

**★ 落点需要你拍一下（我按你的话准备了内容，但发现一处证据分歧，按纪律须报）**：
你说落 `rules/scenario.yaml`；我核到 `§I.2`（`05/02:438`）**明文**把"离散粒度 + 网格搜索上界"指派给 **`rules/valuation-methods.yaml`**，且 `§J.2`（离散粒度）**我已经转写在 `valuation-methods.yaml::assumption_grid`**（该文件注释即引 `§I.2`/`§J.2`）。而 `§J.3`（解集展示上限）与其同属 §I.2 风险表的**同一族控制手段**（"多解展示爆炸"紧挨"反解搜索空间"），且 `solver_ref` 也已在该文件里。
⇒ **我建议落 `rules/valuation-methods.yaml`**（有 `§I.2` **同节同族**依据），`scenario.yaml` 只有"§J 表相邻"依据（该文件已含 §J.4/§J.5，但那是**情景**族）。
⇒ **这不是拒绝执行**：上面 YAML 块**可原样粘到任一文件**（键名/值/出处不变）。**你定，我照办**；若选 `scenario.yaml`，我只需换 `spec_anchor` 归属说明。
★ 另一条**低置信度观察**（不作为裁定请求，仅供你排期）：`method_version` 的**值**（13-B 现为 `pricelayer-solver-v1` / `pricelayer-valuation-v1`）按新判据也"影响产出"（`§D.2`/`N5.3-02` 要求写进输出），但目前无 rules 归属；且**设计自身给的示例值有两处不一致**（`05/02:81` `"method_version":"v1"` vs `05/02:166` `method_version="val-v1"`）⇒ 设计未钉规范串。我 `valuation-methods.yaml::valuation_compute.method_version_field` 只登记了**字段名**。**待你择期裁**，我这轮不擅动。

### §10.4 安装后 13-B 的待办（供你派活时引用）

1. **删** `solver.py:79/82/85` 三个常量；`default_count`/`max_count` 改从 rules 读（缺键 ⇒ 响亮失败，`R8-3` 判据同 `13-A::_rules.py` 的取向）；`min_count` 读到 `tbd` **不得当可用值**（`G-03`）。
2. `DEFAULT_MIN_SOLUTIONS` 语义改为"展示解数 = 求解器实际解出组数"，**不再拒绝**单解（除非 rules 的 `min_count` 被拍板）。
3. `max_grid_points` / `max_nodes` **留代码**，docstring **逐字标注"护栏"**，并与 `assumption_grid.grid_search_upper_bound`（**取值上界，非点数**）**互指**。


---

## §11 `#69` 重跑（**13-B 面已完成**）+ ★★ 一条自我更正

### §11.1 范围与快照

**13-B 已合并** ⇒ ②③ 的 **13-B 面有对象了**；**13-A 仍停在 `d74a829`**（未合并）⇒ **13-A 面仍无对象，本报告此节不覆盖**。
```
$ git -C .worktrees/ws-ch5-pricelayer log --oneline -3
4468da5 (HEAD -> ws/ch5-pricelayer, ws/daily-nochange-exit) merge ws/ch5-pricelayer: 批次13-B Ch5 价格层六模块（…）+ tests/pricelayer + verify.py 批次
b7103b6 docs: 登记 T-18（…）+ T-15 补充（…）+ G-51/G-52
9834f4f feat(pricelayer): 批次 13-B Ch5 价格层 —— 反解多解 / 估值路由 / 倒填守卫 / 情景 / 历史外推 / 每日解释

$ git -C .worktrees/ws-ch5-pricelayer status --short
 M system/scripts/pricelayer/scenario_guard.py          ← ★ 又有**未提交**改动（+322/−27），见 §11.3
$ git -C .worktrees/ws-ch5-pricelayer status --short system/rules system/registry
(空 —— 边界守住)

快照 SHA：
a4a1b95eebfd system/scripts/pricelayer/solver.py        （与 d74a829 快照**相同** ⇒ R8-3 未落地）
2c98f7edc448 system/scripts/pricelayer/scenario_guard.py （**未提交**工作区版）
b612de96b2b9 system/scripts/pricelayer/valuation.py
```

### §11.2 ★★ 自我更正：「零引用 = 死常量」是**假阴性**，③(a)(b) 定档上调

**我先前在 §4.2(a) 写了"这两个常量在 `pricelayer/` 里**零引用**"，并据以下结论"当前不影响任何决策输出 ⇒ 定'不好'不是'错'"。这句话是错的。** 原因是我**又踩了 BSD `grep` 不支持 `\|` 交替的坑**（本报告前面刚记过这个坑，随后自己再踩一次）：
```
$ grep -rn 'DEFAULT_DISPLAY_CAP\|MAX_DISPLAY_CAP\|DEFAULT_MIN_SOLUTIONS' system/
(exit=1)          ← 假阴性：BSD BRE 下 \| 被当字面量，整个模式匹配不到东西
```
**改用正确检索（`Grep` 工具 / `grep -E`）后的真相** —— 三个常量**全部在决策路径里**：
```
system/scripts/pricelayer/solver.py:79:DEFAULT_DISPLAY_CAP = 3
system/scripts/pricelayer/solver.py:82:MAX_DISPLAY_CAP = 5
system/scripts/pricelayer/solver.py:85:DEFAULT_MIN_SOLUTIONS = 2
system/scripts/pricelayer/solver.py:318:    display_cap: int = DEFAULT_DISPLAY_CAP,        ← ① 默认入参：直接决定"展示几组/折叠哪些"
system/scripts/pricelayer/solver.py:328:    - `display_cap` 必须 ∈ `[1, MAX_DISPLAY_CAP]`（B18 的"最多 5 组"是硬上限）。
system/scripts/pricelayer/solver.py:336:    if not 1 <= display_cap <= MAX_DISPLAY_CAP:    ← ② 越界 ⇒ raise SolverError（决策分支）
system/scripts/pricelayer/solver.py:391:    if solution_set.feasible_count < DEFAULT_MIN_SOLUTIONS:   ← ③ 标 degraded + 写 note
system/scripts/pricelayer/solver.py:403:    min_solutions: int = DEFAULT_MIN_SOLUTIONS,    ← ④ 呈现前不变式 assert_multi_solution 的默认
system/scripts/pricelayer/solver.py:503:        if count < DEFAULT_MIN_SOLUTIONS:          ← ⑤ check() 里产 Violation（门禁会红）
system/tests/pricelayer/test_solver.py:169:    assert DEFAULT_DISPLAY_CAP == 3, "B18 已确认：默认展示 3 组"   ← ⑥ 测试**钉住**这个硬编码值
```
`display_cap` 的实际效果（决定产出）：
```
system/scripts/pricelayer/solver.py:385:    solution_set.folded = feasible_solutions[display_cap:]
system/scripts/pricelayer/solver.py:403:def assert_multi_solution(… min_solutions: int = DEFAULT_MIN_SOLUTIONS) → 低于则 raise SingleSolutionError
```

**⇒ 定档更正**
| 项 | 原名 | 新名 | 依据 |
|---|---|---|---|
| `DEFAULT_DISPLAY_CAP=3` / `MAX_DISPLAY_CAP=5` | 不好 | **错** | `施工图 §8 纪律 1` 禁"**参数进决策函数**"；此处 ①②⑥ = 明确违反（且测试把硬编码值**钉死**，将来迁移必须同改测试） |
| `DEFAULT_MIN_SOLUTIONS=2` | 不够 | **错** | 一个**设计无出处**的数（§B.1 只写"多"）在 ③④⑤ **驱动 raise / Violation** —— 无出处 + 进决策，两项叠加 |

★ **这个错误不只影响本报告**：团队长的裁定文本**引用了我的错话** ——
```
system/reports/batch13_taskbook.md:374:`ws/ch2-rules` 报告：13-B 有 `DEFAULT_DISPLAY_CAP=3` / `MAX_DISPLAY_CAP=5`（`grep` 零引用 = 死常量），
```
⇒ **建议他删掉括号里的"（`grep` 零引用 = 死常量）"**，否则该错误会继续被下一个读任务卡的人继承。
★ **对裁定的实质结论无影响**（`R8-3` 已判"进 `rules/`"+"`DEFAULT_MIN_SOLUTIONS` 不得自创"，与更正后的定档**同向**），但**定档与"后果描述"必须改**：三常量**不是"现在无害的埋雷"，是"此刻就在用设计参数做决策"**；`DEFAULT_MIN_SOLUTIONS` 更是在**用无出处的数拒绝呈现**。
★ **根因与防范**：这是**同一类错误第二次**（第一次是 §3.1 的 67/65 个"不在键集合"假阳性）。⇒ 本项目应把"**macOS/BSD `grep` 的 `\|` 交替需用 `-E`**"写进检索纪律（我已在本报告的 `§6.3` 记过一次）。**我这次是自己违反了已知规则，责任在我。**

### §11.3 ② 13-B 复跑：**无自造规则键** ✅ 好（且新增了机器绑定，质量升级）

**(a) 键集合比对**（`python3 /tmp/keycmp.py`，合法键集合 = 682）
```
=== 13-B (…/pricelayer) ===
  .get()/下标 字符串键 共 73 处（去重 56 个名）
  不在已安装键集合里的 .get()/下标 键名 40 个：[…]
```
★ 这 40 个**仍以假阳性为主**（`facts/`/`derived/` 记录字段与 `report.scanned[...]` 诊断名），逐条收窄后：
- **真从 `rules/` 装载的对象**：`rules/valuation-methods.yaml`（`method_routing` / `registry_driven` / `unregistered_fallback`）与 `rules/scenario.yaml`（`scenario_method_status` / `scenario_tags` / `probability.*` / `scenario_method_blocking.*`）—— **全部在已安装件里**，**无一个自造键**。
- 新增的 `rule_keys_required` / `rule_binding_checks` / `blocking_status` / `downstream` / `required_field`：`report.scanned[...]` **诊断字段名**（非 rules 键）。
- `unregistered_fallback_method_class`：读 `valuation-methods.yaml::unregistered_fallback.method_class`（已安装件**有**）。

**(b) ★ 该流在未提交改动里**新增了"规则↔代码机器绑定"**（`scenario_guard.py`，+322/−27）**：
```
:86  RULE_KEY_TAGS = "scenario_tags"          （及 RULE_KEY_STATUS / _DOMAIN / _BLOCKING / _PROMOTION / _CONSISTENCY / _PROBABILITY …）
:96  REQUIRED_RULE_KEYS: tuple[str, ...] = (…7 个顶层键…)   """本模块**实际读取**的 rules/scenario.yaml 顶层键"""
:408 def assert_rule_tags_match(root)  — "scenario_tags 必须与 ScenarioTag 枚举**逐字一致**"
:428     expected = tuple(t.value for t in ScenarioTag)      ← 从**代码枚举**取，不写字面量
:489 def check(root) → _rule_binding_violations(root) → 违例 SCENARIO-RULE-BINDING
```
其 docstring 自列**四条判据**（键存在 / 标签逐字一致 / `probability.default` 恒 null / `must_be_null_50_50` 为 false）+ **"规则文件不存在 → 显式 note（`G-03`：**不**当'已核'）"**。

**(c) 我给这个绑定做了正反例实测**（`root` 指向 `/tmp` 副本，**未动其工作区**）：
```
=== 正向对照：原样（真实已安装件副本）===
  violations = []      notes = []
  assert_rule_tags_match -> ('bear','neutral','bull','custom')

=== 反例 A：scenario_tags 加一个 'PANIC' ===
  violations = ["rules/scenario.yaml:: scenario_tags=[…,'PANIC'] 与代码枚举 ['bear','neutral','bull','custom'] 不一致 —— 规则文件改了而代码没改（Ch11 §D.2 / Ch5 §J4）"]

=== 反例 B：删掉 scenario_method_status_domain ===
  violations = ["rules/scenario.yaml 缺本模块实际读取的键 ['scenario_method_status_domain'] —— 声明与实现脱节（Ch11 §D.2）"]

=== 反例 C：probability.default 由 null 改成 0.5 ===
  violations = ['rules/scenario.yaml:: probability.default=0.5 非 null —— Ch5 §D.6：情景概率默认 null（**不默认 50/50**）']
```
⇒ **正向干净、三个反例全部逐条命中**（且违例文本各自指回节号）。**这是本次复核里质量最高的一处实现** —— 且它恰好回应了 §3.3 那条"两流各自补了设计没给的键名、恰好对上（运气成分应被记录）"：**现在不再是运气，是机器绑定。**
**判定：② ✅ 好（较 `4468da5` 时点进一步升级）。**

### §11.4 ③ 13-B 复跑：`R8-3` **只落了一半**（`rules/` 侧 ✅ / 代码侧 ❌）；护栏判定成立；并避免一个假阳性

**(a) `R8-3` 必须**分开记两半**（★ 本条经 **§12.2** 重钉后更正 —— 我先写的是"尚未实施"，那只是**代码侧**的真相）**：
- **代码侧 ❌ 未改**：`solver.py` 在 `4468da5` 的 SHA 与该流任务卡快照**完全相同**（`a4a1b95eebfd`）⇒ 三个常量**仍在原位**，且**仍在决策路径上**（§11.2 已给逐处证据）。
- **`rules/` 侧 ✅ 已装**：主理人在 `182f8a1` 把 §10.3 候选装进 **`rules/valuation-methods.yaml::solution_set_display`**（**落点采纳我的建议、并更正了他先前的 `scenario.yaml` 指令**）。
- ⇒ 合并结果是 **`G-06` 意义上的"双份真源"**：rules 载 `default_count: 3 / max_count: 5`，代码载 `DEFAULT_DISPLAY_CAP = 3 / MAX_DISPLAY_CAP = 5`；**代码那份在决策路径上、rules 那份零消费者**。逐键对照 + 实测见 **§12.2**。

**(b) 护栏判定经复核** **成立**：
```
system/scripts/pricelayer/solver.py:277:    if len(values) > max_grid_points:
system/scripts/pricelayer/solver.py:280:            f"> 上限 {max_grid_points}，按已扫部分给区间（Ch5 §I.2 网格上界告警）"
system/scripts/pricelayer/solver.py:282:        values = values[:max_grid_points]
system/scripts/pricelayer/solver.py:30:- **网格上界告警**（`Ch5 §I.2`："设网格上限告警"）⇒ 超出 `max_grid_points` **不静默**：
system/scripts/pricelayer/valuation.py:225:        if len(seen) > max_nodes:
```
⇒ 只**截断搜索**且**非静默记 note**（`§I.2`"设网格上限告警"逐字），**不改变"展示哪组解"的取值/选择** ⇒ 属**护栏**，**`R8-3` 允许留代码**。★ 小建议：docstring 里把「护栏」二字**逐字写出**（现用"网格上界告警"，语义等价但不如"护栏"便于机器/人检索）。
★ 我之前提的**混淆风险仍在**：`max_grid_points`（点数上限）vs `rules/valuation-methods.yaml::assumption_grid.grid_search_upper_bound`（**取值**上界，现 `tbd`）—— 二者需互指。

**(c) ★ 避免一个假阳性：`weight` 不是 `P-09` 违规**
`history_guard.py:236` 有 `entry.get("weight")`，而 `weight` **确在** `rules/banned_tokens.yaml` 的 32 个 token 里（与 `score`/`vote`/`sentiment` 同族）。但逐层核后 **不是违规**：
```
# ① 它是**设计逐字给定的数据字段名**，不是决策权重：
05_价格与市场预期研究/02_实现方案.md:221:| 非上市资产无法独立建模 | `non_listed_assets{value, weight, gap_note}` |
05_价格与市场预期研究/01_需求拆解.md:161:| 非上市资产无法独立建模 | `non_listed_assets{value, weight, gap_note}` |
# ② 禁词表的**决策域**不含 pricelayer：
banned_tokens.yaml::decision_scope.include_paths = ['system/scripts/decision/**', 'system/scripts/graph/**']
```
⇒ 前者是"设计给字段、代码照读"，后者是"禁词只在其**声明的决策域**内生效" ⇒ **判"不是违规"**，并记下：**naive 扫描会把它当 P-09 命中**，下一个人别误报。

### §11.5 与 `ws-schema-expand` 的三条交叉核对（他给我的输入，我逐条独立复核）

| 他的命中 | 我的复核 | 结论 |
|---|---|---|
| **① `rules/scenario.yaml::scenario_tags` ↔ `ScenarioTag` 同值双存放、零绑定** | **在被审时点（`4468da5`）成立**：`git show 4468da5:…/scenario_guard.py \| grep -n 'scenario_tags\|assert_rule_tags_match'` → **两条皆 `exit=1`（无匹配）**。★★ **且经 §12.3 重钉：在 `main`（`c591082`）上仍成立** —— `git grep -nE 'RULE_KEY_TAGS\|REQUIRED_RULE_KEYS\|_rule_binding_violations' main -- system/scripts/pricelayer/scenario_guard.py` → **`exit=1`**。修复**存在**（§11.3(b)(c) 逐处 + 正反例），但**未提交、未进 main**（挂在 `ws/ch5-pricelayer` 工作区，`git status --short` = 5 个 `M`） | ✅ **他的命中成立，且不是"已闭合"而是"未提交的修复挂在分支工作区"** —— 我先前写的"已被未提交改动闭合"**会被误读成 main 已安全**，故在 §12.3 一并更正。⇒ 建议他：**在下一个 commit（不是工作区）上复跑**，别重复上报；**并提醒 13-B 把这份修复提交**（未提交的修复 = `G-50` 形态：一个"看着有、实际不在真源上"的绑定） |
| **② `Valuation.scenario_tag` 零生产消费** | **成立**：`check()` 只扫 `valuation.probability` + `formula_ref`（`scenario_guard.py:489+` 全文已读）；`assert_scenario_match(stock: ScenarioTag\|str, benchmark: ScenarioTag\|str)`（`:375`）**入参不是 `Valuation`**；`scenario_tag`（单数）在工作区版仅出现在**注释**（`:10,:11`） | ✅ **成立**。**但我不下"缺陷"判词**：设计 `§E.3` 的受检字段是 `checked_fields: [stock.scenario_tag, benchmark.scenario_tag]`（我 `rules/scenario.yaml:34` 逐字转写），即**设计把该字段放在 stock/benchmark 上**，放不放 `Valuation` 是他 (D) 那单的自选 ⇒ 若属自选，则"零消费"是**预期**（`G-50` 形态只在他**声称接线**时才成立）。**建议他自查**：有设计出处就补消费点，无出处就登记为待接线/删 |
| **③ `scenario_tags`（域）vs `scenario_tag`（值）** | 语义不同、确无冲突 | ✅ 同意，登记即可 |

★ 他的**边界声明我认可**：①③ 只覆盖 13-B 面，**13-A 面仍无对象** ⇒ **`#69` 现在只能做一半**，本报告 §11 **不是完整复核结账**。

### §11.6 13-B 工作区的一个**必然假红**（同我先前那次，提醒他）

```
$ ls -l .worktrees/ws-ch5-pricelayer/system/rules/baseline.yaml
-rw-r--r-- 1 gaza staff 7515 2026-09-16 21:36 …/rules/baseline.yaml     ← 644！应为 0444
```
⇒ `git merge main` 把只读位重置了（git 不跟踪权限位）。**`rules_lock_guard` 会报"应为 0o444"**。修法：
```
sh system/scripts/ops/bootstrap_worktree.sh     # 我这边实测：14 件置 0444 + rules_lock_guard PASS 14/14
```
（我已把这条单独发给 13-A 与他两流。）

### §11.7 本节的**未完成**与**需更正处**（如实登记）

**未完成（不冒充已核）**
1. **13-A 面 ②③ 仍无对象**（`ws/ch4-valuelayer` 停在 `d74a829`）。⇒ `#69` 保持 in_progress。
2. 13-B **工作区版**（`scenario_guard.py` 未提交，SHA `2c98f7edc448`）我的核对**仅覆盖**：键名、`assert_rule_tags_match`、`_rule_binding_violations`、`check()` 主体。**未读**其新增的 300 余行其余部分；**未跑其单测**（避 `V-05`/`V-08` 配额）。⇒ 结论"②✅好"对应**该 SHA 的这些函数**，不是全文件背书。
3. 我在 §11.3(c) 的反例是**我构造的**（`/tmp` 副本），**不是** 13-B 提交的测试。⇒ "绑定可拦"由我证明；"其测试覆盖了这些反例"**我没有核**。

**需更正**
4. **§4.2(a)(b) 的"零引用/死常量"已作废**（§11.2 给真相与逐处证据）；§1 总览与 §7.1 的 `R-3` 行已同步改档。
5. **团队长的裁定文本 `batch13_taskbook.md:374` 引了我的错话**（"`grep` 零引用 = 死常量"）⇒ **建议删除该括注**（裁定结论不受影响，但后果描述会误导）。

---

## §12 `#69` 第二轮：在 **`main` 上重钉**（`R8-3` 收口核验 + 13-A 面仍无对象）

> 触发：主理人 `182f8a1` 安装了 §10.3 候选（并更正落点）；`ws-schema-expand` 送来三条现成输入。
> **本节只读、只跑探针，未改任何被审文件**（被审面 = `scripts/pricelayer/**`、`scripts/valuelayer/**`、`rules/**`、`registry/**`）。

### §12.1 快照重钉（把 §11 的"分支工作区 SHA"换成 **commit hash**）

```
$ git -C .worktrees/ws-ch2-rules log --oneline main..HEAD          # 我领先 main 的提交
(空)      ⇒ 我的报告提交（8f3f476 / 89bdf00）已随 9cd3b6d 进 main

$ git -C .worktrees/ws-ch2-rules log --oneline HEAD..main           # main 领先我的提交
c591082 fix(verify)+docs: G-54 unit 批超时 60s→270s（…）+ G-53 把 bootstrap 触发面扩到 git merge（V-07）
bb8991a Merge branch 'ws/ch13-d-valuation-fields'
a4760db Merge branch 'ws/criterion-effectiveness'
9cd3b6d merge ws/ch2-rules: 13-R 报告收口（…）
182f8a1 feat(rules): 安装 §J.3 解集展示上限 → rules/valuation-methods.yaml::solution_set_display
        （落点采纳 ws-ch2-rules 建议，更正我先前的 scenario.yaml 指令）+ 重锁
```

| 对象 | 钉住的 commit | 说明 |
|---|---|---|
| **13-B 提交面** | `4468da5`（= `9834f4f` 合并） | §11 已核 |
| **13-B 工作区版** | 未提交（`ws/ch5-pricelayer` 工作区，5 个 `M`） | §12.3 |
| **`rules/valuation-methods.yaml` 安装** | `182f8a1` | §12.2 |
| **`rules.lock.json`** | `locked_at = 2026-09-16T13:38:46+00:00`，14 件，`owner_writable = False` | `rules/valuation-methods.yaml` → `bytes 8118` / `locked_mode 0o444` / `sha256 8e01a9bb91…4ae857` |
| **13-A 面** | `ws/ch4-valuelayer` = `bb8991a`（**main 的祖先，零领先提交**） | §12.4 ⇒ **仍无被检对象** |

★ 我先前 §11.6 提的"`git merge main` 把 `rules/*.yaml` 重置成 644 ⇒ `rules_lock_guard` 假红"**已被主理人以 `c591082` 的 `G-53` 收口**（把 `bootstrap` 触发面扩到 `git merge`，`V-07`）⇒ 该提醒**结案**，不必再逐流喊。

### §12.2 `R8-3` 逐项核（**结论：`rules/` 侧 ✅ 好 / 代码侧 ❌ 未做 ⇒ `G-06` 双份当场成立**）

#### (a) `rules/` 侧 ✅ **已装**（逐字）

```
$ git show main:system/rules/valuation-methods.yaml | sed -n '74,78p'
solution_set_display:
  default_count: 3                          # B18 逐字（「默认展示 3 组」）—— 设计 `§J.3` 原为"待定"
  max_count: 5                              # B18 逐字（「最多 5 组」）—— 同上
  selection: "代表解 + 区间包络"             # §I.2 行 2 控制手段逐字
  overflow: fold                            # §I.2 行 2 逐字（「…上限 N，**超出折叠**」）
```
★ 落点 = **`valuation-methods.yaml`**（我的 §10.3 建议被采纳，他先前的 `scenario.yaml` 指令已自更正）；头注 `:12-18` 把"为什么落本件"的三条依据逐字写了，`:69-73` 把 `§J.3` 与 B18 原文逐字贴了。**这一处我判 ✅ 好。**

#### (b) 代码侧 ❌ **未做**（不是"错"，是**没动**）—— 且现在**比装之前更糟**

```
$ git show main:system/scripts/pricelayer/solver.py | sed -n '79,85p'
DEFAULT_DISPLAY_CAP = 3
"""解集**默认展示组数**（`00_待拍板项清单` B18 已确认："默认展示 3 组，最多 5 组"）。"""

MAX_DISPLAY_CAP = 5
"""解集展示**硬上限**（同上 B18："最多 5 组"）。"""

DEFAULT_MIN_SOLUTIONS = 2

$ PYTHONPATH=. python3 -c "import inspect, scripts.pricelayer.solver as s; \
    print(s.DEFAULT_DISPLAY_CAP, s.MAX_DISPLAY_CAP, s.DEFAULT_MIN_SOLUTIONS); \
    print({k: v.default for k, v in inspect.signature(s.solve_implied_requirements).parameters.items() if v.default is not inspect._empty})"
3 5 2
{'max_grid_points': 256, 'display_cap': 3, 'computed_at': None, 'method_version': 'pricelayer-solver-v1'}

$ git grep -n 'solution_set_display' main -- system/scripts system/tests
(exit=1)                    ← ★★ **rules 那份装了，但零消费者**
```
⇒ **`G-06` 双份**：同一对值（3/5）**同时**住 `rules/valuation-methods.yaml` 与 `solver.py`；**代码那份在决策路径上**（`solver.py:318/336/338/384/385/391/395/403/503`），**rules 那份一行代码都不读**。
★ 定档为 **❌ 未做**（不是"错"）：处置方**尚未接到改动指令**（§10.4 那份待办是随 §10 一起给主理人的）。
★ 但**后果严重性上升了**：安装**之前**只是"值住错了地方"；**安装之后**多了一条 —— **规则文件自称唯一真源而实际零消费者**（"文件说谎"）。这正是 §11.3 那处 `scenario_tags` / 本处常量 的**同一形状**，**第三次出现**。⇒ 建议在 `§10.4` 待办里加一句**验收口径**：`git grep 'solution_set_display' -- system/scripts` **必须非空**，否则"装了没人读"会被下人当成"已消费"。

#### (c) §10.3 候选 ↔ 实装 **逐键对照**（他有权精简；我逐条给判词，不搞一刀切）

| §10.3 我的候选 | 实装（`182f8a1`） | 判词 | 为什么 |
|---|---|---|---|
| `default_count: 3` | `default_count: 3` | ✅ **好** | 值 = B18 逐字 |
| `max_count: 5` | `max_count: 5` | ✅ **好** | 值 = B18 逐字 / `§J.3`「上限 N」 |
| `must_show_multiple: true`（我标"键名为转写、语义非数值"） | **未落**，改落 `selection: "代表解 + 区间包络"` | ✅ **好** | 我这键**与 `overflow_policy` 语义重叠**，且我自己都标了"键名为转写"；他落的 `selection` 是 **`§I.2` 行 2 逐字**，**比我更像逐字转写** |
| `overflow_policy: "只保留代表解 + 区间包络（超出上限即折叠）"` | `overflow: fold` | ✅ **好** | `fold` = `§I.2` **逐字用词**（"超出**折叠**"）；我的长句反而是**复述** |
| `solver_ref: scripts/pricelayer/solver.py` | 未落（同文件 `:63 assumption_grid.solver_ref` 已有**同一指针**） | ✅ **好** | **不重复写**正合 `G-06` |
| `basis: {逐键出处}` | 未落，改在**头注 `:65-73` 逐字给** `§I.2`/`§J.3`/B18 原文 | ✅ **可接受** | 出处**逐字在**，只是载体是注释。★ 但与同目录惯例不一致（`baseline.yaml::thresholds.basis`、本件 `:58 assumption_grid.basis` 都是**映射**）⇒ **建议**（非缺陷）：补 `basis:` 映射，或在头注写明"本件此处出处由注释承载" |
| `min_count: tbd` | **未落** | ⚠ **不够** —— 见 (d) | 设计未给下界这个**事实**没被登记 |

#### (d) ★ 我这一轮**唯一要提的实质缺口**：`§B.1` 的「**必须展示多组解**」在 `rules/` 里**没有任何载体**

`rules` 现在载的是 `§J.3`/`§I.2` 的**上限面**（展示几组、超出怎么折叠）；而**下界面**（`05/02:69 §B.1` 逐字："一个 P 对应**无穷多组**解。故**必须展示多组解**，否则会把某一解误当『市场的唯一真相』"）在 rules 里**既无 `must_show_multiple` 也无 `min_count`**。
⇒ 后果不是抽象的：代码里那个 **`DEFAULT_MIN_SOLUTIONS = 2`（无出处）仍在决策路径**（`:391` 置 `degraded`、`:403` 呈现前不变式、`:503` `check()` 产 `IMPLIED-SINGLE-SOLUTION` Violation）⇒ **"2"长期没有归宿**，且**没有任何地方写着"下界 = tbd"**（`G-03`：未落 ≠ 无此要求）。
⇒ **请你拍一下**（三种都行，我不擅动 `rules/`）：① 补 `min_count: tbd` + `basis`（我 §10.3 的原案）；② 补 `must_show_multiple: true`（语义键，非数值）；③ 明确"§B.1 下界面首版不参数化、`2` 按护栏处理"——若选 ③，则 `2` 必须**改成护栏口径**（docstring 明标 + 与 rules 互指），否则它仍是"参数却住代码"（违 `R8-3`）。

#### (e) `max_grid_points = 256` —— 护栏判词**维持**，但记一条**前瞻风险**

```
$ PYTHONPATH=. python3 -c "…"        # 见 (b)：solve_implied_requirements 默认参数 max_grid_points = 256
$ git show main:system/scripts/pricelayer/solver.py | sed -n '277,282p'
    if len(values) > max_grid_points:
        …
            f"> 上限 {max_grid_points}，按已扫部分给区间（Ch5 §I.2 网格上界告警）"
        values = values[:max_grid_points]
```
判 **✅ 护栏**（`R8-3`：仅防搜索爆炸 + `:273` docstring 明写"**不静默**"）—— 与 §11.4(b) 一致。
★ **前瞻风险**：`rules/valuation-methods.yaml:61` 的 `grid_search_upper_bound: tbd` 一旦被拍板，代码里的 `256` 若不改读 **就重演同一 `G-06` 双份**（且这次是"真值 vs tbd"的更坏形态）。⇒ 护栏 docstring 里**除"护栏"二字外**，还应写明"本值非 rules 的 `grid_search_upper_bound`（那是**取值**上界，非**点数**上限）"。
★ 顺带：`:61` 现在 **`tbd` 但代码有 `256`** ⇒ `grid_search_upper_bound` 眼下是个**永远不会被读的空壳**（形状同 (b)，只是值为 `tbd`）。

#### (f) §12.2 判词汇总

| 项 | 判词 |
|---|---|
| §J.3 候选**进 `rules/valuation-methods.yaml`** + 落点依据逐字写在头注 | ✅ **好** |
| 实装键名/值相对我的候选的**精简**（`selection`/`overflow: fold`/不重复 `solver_ref`） | ✅ **好**（逐条理由见 (c)） |
| 实装**少了 `basis:` 映射**（出处改由注释承载） | ✅ 可接受 / ⚠ **与同目录惯例不一致**（建议项，非缺陷） |
| `§B.1` 下界面在 rules 里**无载体**、`DEFAULT_MIN_SOLUTIONS=2` 无出处仍在决策路径 | ⚠ **不够** ⇒ **待你拍**（(d) 三选一） |
| 代码侧**未改**（三常量仍在决策路径）+ rules 那份**零消费者** | ❌ **未做** ⇒ **`G-06` 双份当场成立**（(b)） |
| `max_grid_points` / `max_nodes` = 护栏 | ✅ **不是违规**（(e)，判词维持） |
| `batch13_taskbook.md:391-392` 的落点**仍写 `rules/scenario.yaml`** | ❌ **错**（文档与实装矛盾；同 `:374` 一起订正，见 §12.5） |

### §12.3 13-B 工作区：`scenario_tags` 绑定**仍未进 main**（并更正我 §11.5 的措辞）

```
$ git -C .worktrees/ws-ch5-pricelayer status --short
 M system/scripts/pricelayer/scenario_guard.py
 M system/scripts/pricelayer/valuation.py
 M system/tests/pricelayer/conftest.py
 M system/tests/pricelayer/test_scenario_guard.py
 M system/tests/pricelayer/test_valuation.py
$ git -C .worktrees/ws-ch5-pricelayer log --oneline -1
4468da5 …（HEAD 未前进）

$ git grep -nE 'RULE_KEY_TAGS|REQUIRED_RULE_KEYS|_rule_binding_violations|SCENARIO-RULE-BINDING' \
      main -- system/scripts/pricelayer/scenario_guard.py
(exit=1)                    ← ★★ main 上**零命中** ⇒ `scenario_tags` ↔ `ScenarioTag` 双存放**零绑定在 main 上仍活**
```
⇒ **更正我 §11.5 命中① 的措辞**：我写"已被 13-B 的未提交改动闭合"——**语义上会把"main 已安全"读进去**，实际是 **`main` 上仍无绑定**，修复**只存在于分支工作区**。
⇒ ⇒ 这本身是 **`G-50` 形态**的活标本：**"看着有绑定、实际不在真源上"**（工作区改动不进 commit ⇒ 下一个人 `git grep` 真源时看到的是**零绑定**；而门禁**是绿的**，因为**零绑定意味着没人查**——绿恰恰是风险而非安全）。
⇒ **建议**：提醒 13-B 尽快把这份修复提交；`#69` 的 ② 判词改为 **"13-B 面：设计上已补、真源上未达"**。

### §12.4 13-A 面：`R8-1` / `R8-2` 两项 **⛔ 无被检对象**（`G-03`：不计为已验证）

> ★★ **本节已被后续推翻，以 §13/§14 为准**：本节的时点是 `main = c591082`（13-A 零领先提交）。**此后** 13-A 进入 `git stash pop` 冲突期、工作面出现 ⇒ **§13 起 13-A 面已有被测对象**（工作区态）。保留本节作**时点证据**（说明"当时为什么不能算已核"），**不要**把这里的"无被检对象"当成当前状态。

```
$ git -C .worktrees/ws-ch2-rules log --oneline main..ws/ch4-valuelayer
(空)      ⇒ ws/ch4-valuelayer = bb8991a = **main 的祖先**，**零领先提交**（13-A 未提交任何东西）
$ git stash list
stash@{0}: On ws/ch4-valuelayer: wip-ch4          ← 线索：13-A 的活儿在 stash 里
$ git grep -n 'chapter4_g_depth' main -- system/scripts/delivery/stage_gate.py
(exit=1)          ⇒ stage_gate **未绑**（:451/:452 只有 six_step_chain_complete / derivation_reviewable）
$ git show main:system/registry/criterion_counterexamples.yaml | grep -c 'chapter4_g_depth'
0                 ⇒ 反例登记表**无** `nvidia_sample::chapter4_g_depth` 条目
$ cd system && python3 scripts/checks/criterion_effectiveness_guard.py
  note: 未绑定判据[nvidia_sample]：2 条（['chapter4_g_depth', 'evidence_locatable']）—— 属后续阶段待交付，**不计为已验证**（`G-03`：无被检对象不得当成已核）
RESULT: PASS（0 violations）
```
| `R8-*` 项 | 13-A 面现状 | 判词 |
|---|---|---|
| **R8-1**（`completeness.py` 键名 **且** `_rules.py::baseline_cfg` 深度） | 工作区零改动 ⇒ 真件上仍 `MissingRuleInput`（§6.3 已实测 6/6 键全红） | ⛔ **无被检对象**（`G-03`） |
| **R8-2**（`verify.py::BATCHES` 只加自己那一条 + 反例只加自己那一条） | 台账仍 `未绑定判据[nvidia_sample]：2 条`，反例条目 0 | ⛔ **无被检对象**（`G-03`） |
| **R8-3**（B18 常量） | 见 §12.2：rules 侧 ✅ / 代码侧 ❌ | 见 §12.2(f) |

★ 已有任务 **#73**（"把价值层读口适配到 13-R 已安装的 rules 结构"）、**#74**（"同步测试夹具与注入测试到真实 rules 结构并解冲突"）在跑，且描述里已含 `thresholds` 分组与 `min_locator_count` ⇒ **方向与我 §12.2 的结论一致**；但**它们尚未产出 commit** ⇒ 本轮**仍按"无对象"计**，不得当已核。

### §12.5 需主理人动作（截至本轮）

1. **`batch13_taskbook.md:374`** —— 删括注 "（`grep` 零引用 = 死常量）"（引了我已在本报告 §11.2 证伪的话；裁定结论不受影响）。
2. **`batch13_taskbook.md:391-392`** —— 落点仍写 `rules/scenario.yaml`，实际落在 `rules/valuation-methods.yaml`（`182f8a1`）⇒ **两行订正**（同一文件两处矛盾，别只改一处）。
3. **代码侧 `R8-3` 未做**（§12.2(b)）：`solver.py:79/82/85` + 5 处决策路径 + rules 零消费者。⇒ 派活时**给可验收口径**：`git grep 'solution_set_display' -- system/scripts` **必须非空**。
4. **`§B.1` 下界面载体缺失**（§12.2(d)）：三选一（`min_count: tbd` / `must_show_multiple: true` / 明确"下界按护栏口径"并把 `2` 的 docstring 改护栏）。
5. **13-B 的 `scenario_guard.py` 修复未提交**（§12.3）：真源上 `scenario_tags` 绑定**仍为零**。

### §12.6 本节一句话

**`rules/` 侧装得很好（落点、逐字、头注依据都对，我逐条给了"为什么好"）；但"装了"与"读了"之间隔着一次接线 —— 现在 `rules` 的那对值是当局的第二次"声明 ≠ 有效力"（`G-50` 家族），而 `13-A` 面连被检对象都还没有。⇒ `#69` 保持 `in_progress`，13-B 面收口、13-A 面挂账。**

---

## §13 13-A 面**首次有对象**（`git stash pop` 冲突期中途实测）—— `R8-1` / `R8-2` 实质已做，但**有一个阻塞项**

> ★ **快照不稳定声明（必须先读）**：13-A 此刻**正处于 `git stash pop` 的冲突期**（不是稳定提交态）：
> ```
> $ git -C .worktrees/ws-ch4-valuelayer status --short
> M  system/registry/criterion_counterexamples.yaml
> M  system/scripts/delivery/stage_gate.py
> UU system/scripts/ops/verify.py                       ← 冲突（现已解：0 个冲突标记）
> M  system/scripts/orchestrate/chain_steps.py
> UU system/tests/injection/test_criterion_effectiveness.py   ← ★ 冲突**未解**（6 个标记）
> ?? system/scripts/valuelayer/
> ?? system/tests/valuelayer/
> $ git -C /Users/gaza/Developer/InvestSigh log --oneline main..ws/ch4-valuelayer
> (空)      ⇒ **零领先提交**：以下全部是**工作区未提交**内容
> ```
> ⇒ 本节结论**对应工作区、不是 commit hash**；`#69` 的 A/B 仍须在**提交后**按 hash 重跑一次。**被审文件一律未改。**

### §13.1 ★★ 阻塞项：`test_criterion_effectiveness.py` **仍有冲突标记 ⇒ 文件语法非法 ⇒ 门禁当场 INPUT-ERROR**

```
$ grep -nE '^(<<<<<<<|=======|>>>>>>>)' system/tests/injection/test_criterion_effectiveness.py
895:<<<<<<< Updated upstream
901:=======
912:>>>>>>> Stashed changes
930:<<<<<<< Updated upstream
932:=======
934:>>>>>>> Stashed changes

$ python3 -c "import ast; ast.parse(open('system/tests/injection/test_criterion_effectiveness.py').read())"
  File "<unknown>", line 895
    <<<<<<< Updated upstream
    ^^
SyntaxError: invalid syntax

$ cd system && python3 scripts/checks/criterion_effectiveness_guard.py > /tmp/ceg_13a.txt 2>&1 ; echo $?
2
$ tail -1 /tmp/ceg_13a.txt
[INPUT-ERROR] criterion_effectiveness_guard.py: ValueError: tests/injection/test_criterion_effectiveness.py:
              语法错误，无法核对登记的反例测试: invalid syntax (test_criterion_effectiveness.py, line 895)
```
| 事实 | 证据 |
|---|---|
| 冲突标记在 **895/901/912 + 930/932/934**（**两组**） | 上面 `grep` |
| 冲突来源 = **`git stash pop`**（不是 merge） | 标记尾 `>>>>>>> Stashed changes` |
| 文件**语法非法** ⇒ 若照此提交，`injection` 分片批必红 | `ast.parse` → `SyntaxError` |
| ⇒ **`criterion_effectiveness_guard` 当前跑不起来**（`exit=2`，INPUT-ERROR） | 上面实测 |
| 同一冲突期里 **`verify.py` 已解干净**（0 标记），**只有测试文件没解** | `grep -c '^<<<<<<<' verify.py` → `0` |

★ 判词：**❌ 错 / 阻塞**（不是"不够"）—— 这是一份**照当前状态提交就必然红**的工作区；且**冲突只在两个文件里，一个已解一个未解**，最容易漏。→ 已直接告知 13-A。

### §13.2 `R8-1` 实质已做，且**我用真件实测通过**（这正是 §6.3 那两层不一致的收口）

**(a) 两层**都改了（**"只改键名会白干"的那个结论已被正确吸收**）：
```
system/scripts/valuelayer/_rules.py:44   THRESHOLDS_GROUP = "thresholds"
system/scripts/valuelayer/_rules.py:108  def baseline_cfg(root) -> …  """…即 rules/baseline.yaml 的 **`thresholds` 分组**…
                                         缺 `thresholds` 分组时**响亮失败**（不猜深度、不摊平规则文件）"""
system/scripts/valuelayer/completeness.py:84-87
  CFG_MIN_NONNULL_RATE     = "min_nonnull_rate"
  CFG_MIN_FIELDS_PER_SECTION = "min_fields_per_section"
  CFG_MIN_LOCATORS         = "min_locator_count"      ← 旧名 min_locators 已改
  CFG_MIN_DERIVATIONS      = "min_derivation_count"   ← 旧名 min_derivations 已改
```
**(b) 真件实测（`root='.'`）**—— 缺键/未拍板都**响亮**，且**真的读到了真值**：
```
$ PYTHONPATH=. python3 -c "import scripts.valuelayer._rules as R; …R.baseline_threshold('.', k)…"
  min_locator_count                 = 1
  min_derivation_count              = 1
  min_fields_per_section            -> UndecidedThreshold: rules/baseline.yaml::thresholds 的 'min_fields_per_section'
                                       'tbd' —— `tbd`/未拍板的值不得被当成一个可用阈值（G-03：空 ≠ 已验证）
  min_nonnull_rate                  = 0.9
  max_primary_drivers_per_business  = 5
```
⇒ 与 §6.3 的旧实测（**6/6 键全 `MissingRuleInput`**）对照：**6 个键现在 5 个读通、1 个按 `tbd` 响亮拒用**。`min_nonnull_rate = 0.9` / `max_primary_drivers_per_business = 5` = **真文件真值**，不是夹具值。
★ **我自己的一个假阳性（当场记下）**：我第一次跑这个探针时把 `root` 传给了 `baseline_threshold_from(cfg, key)`（它的首参是 **cfg**，不是路径），得到 5 条 "缺少键 … （现有键：`['.']`）"，差点写成"键名仍未对上"。**新签名是 `baseline_threshold(root, key)`**（`_rules.py:127`）；`baseline_threshold_from(cfg, key)` 存在的原因是 `§G.2` 的 `form_complete(baseline, cfg)` 里 `cfg` 是**入参**（`:130-136` docstring 明写）。⇒ **这是我的调用错，不是它的缺陷。**

**(c) `tbd` 的处理 = 既不恒红也不放行，且✅ **非静默****：
```
completeness.py:441   minimum = _rules.threshold_or_none(cfg, CFG_MIN_FIELDS_PER_SECTION)
completeness.py:463   scanned["min_fields_undecided"] = len(SECTIONS)     ← 计数，不写 0（与"没有不可核项"区分）
completeness.py:465-468  note: "MIN_FIELDS_UNDECIDED: …§G.2 项①的『达最小字段数』半项**不可核**（本次 6 个 section），
                          已按下界 1（=『非空』）强制；不可核 ≠ 已核（G-03）"
completeness.py:1049  # ★ 逐项把「半项不可核」等声明带到 CLI 输出（G-03：不可核必须**显式可见**）
```
⇒ 判 ✅ **好**（`G-01`/`G-03` 两侧都照顾到了）。

**(d) `g_depth_violations(真件)`：从"1 条读不到规则"→"9 条**可判定**的 FATAL"**
```
$ len(g_depth_violations('.')) = 9 ；9 条**全部 severity='FATAL'**
  理由样例（逐字）：
  "Ch4 §G 形式完备性未过 [baseline-nvda-001][sections_nonempty]：①业务与产业位置 为空（0 个字段非空，
   §G.2 项①'六项 section 非空'）；空字段 ['business_refs', 'relations']"        （②③④⑤ 同形）
  "Ch4 §G 形式完备性未过 [baseline-nvda-001][nonnull_rate]：必填字段非空率 0.1429 < 阈值 0.9（空字段 […]）"
```
⇒ ★ **判据性质变了，这才是 `R8-1` 的验收口径**：旧态是"**规则读不到 ⇒ 不可判定 ⇒ 恒红**"（`G-01`，不管数据好坏都红）；新态是"**读得到规则、按真阈值判数据**"（现在红是因为**真样例数据的六节确实为空 + 非空率 0.1429 < 0.9**）。
⇒ 我**如实报**：阶段②**仍然红**，但**红的理由是正确的**（真数据不完备）。这属 13-A 的样例数据面，**我不判为判据缺陷**；但它意味着"`chapter4_g_depth` 恒红"这句在**数据侧仍未解除**，别把"判据修好了"读成"阶段②能过了"。

**(e) ⚠ 一处残留（小）**：`completeness.py:542` / `:651` 的 docstring 仍写旧名（"阈值 = `cfg.min_locators`"、`cfg.min_derivations`），而同文件 `:86/:87` 的常量已是 `_count` 名 ⇒ **文档 ≠ 实现**（`G-06` 家族的小尾巴，建议顺手改；`:82` 已说明"初版曾用旧名"，所以是**漏改**不是故意）。

### §13.3 `R8-2` 两项**都做了，且边界守住了**

```
$ grep -nE 'valuelayer|pricelayer|ORDER' system/scripts/ops/verify.py
:348  "pricelayer": Batch( … )          ← 13-B 的条目，**未被改**（文本仍是"由**批次 13-B**…一并加入"）
:395  "valuelayer": Batch(
:408    "valuelayer", "tests/valuelayer/（Ch4 价值层：指标集/加总/增长质量/护城河/状态机/完备性）", …, 300.0, …
:437  "valuelayer",                       ← 已进 ORDER
```
```
$ sed -n '98,103p' system/registry/criterion_counterexamples.yaml
  - stage: nvidia_sample
    criterion_id: chapter4_g_depth
    kind: counterexample
    test: tests/injection/test_criterion_effectiveness.py::test_nvidia_sample_chapter4_g_depth_blocks_on_incomplete_form
    blocked_hint: "Ch4 §G 形式完备性未过"
```
| `R8-2` 要求 | 现状 | 判词 |
|---|---|---|
| 只加**自己那一条** `valuelayer` 批次（`V-06`） | `verify.py:395-409` + `:437`，共**一条** | ✅ **好** |
| **没动** 13-B 的 `pricelayer` 条目 | `:348-354` 逐字未变 | ✅ **好**（共享文件边界守住） |
| 只加**自己那一条** `nvidia_sample::chapter4_g_depth` 反例 | `criterion_counterexamples.yaml` 现**恰好一条** `chapter4_g_depth` | ✅ **好** |
| `stage_gate` 函数体内绑定 | `stage_gate.py:467` `criterion("nvidia_sample", "chapter4_g_depth", v)`，且**锚在** `six_step_chain_complete`（`:468`）**之前**（与任务卡 L294 的要求一致） | ✅ **好** |
| `criterion_effectiveness_guard` 的 `未绑定判据[nvidia_sample]` 应从 **2 → 1** | ⛔ **本轮无法核**（该门禁因 §13.1 的语法错误 `exit=2`） | **待提交后重跑** |

### §13.4 ⚠ `criterion_counterexamples.yaml` 的登记 `note` 里有一句**与事实矛盾**

逐字（`criterion_counterexamples.yaml:103` 末段）：
```
★ 该用例在**夹具副本**内自备 `rules/baseline.yaml`（§G.2 的阈值只从它读，G-06；**真仓库那份尚不存在**，
  故不写它就只能测到'规则缺失 ⇒ 无法判定'这一条）。
```
**"真仓库那份尚不存在"是错的** —— `rules/baseline.yaml` 自 `bb32863`（13-R 安装）起就在真仓库里，`rules.lock.json` 列了它，且我在 §13.2(b) **刚刚从它读出真值**（`0.9` / `5` / `tbd`）。
⇒ 判 ⚠ **不够**（属"声明与现实矛盾"家族；它是 `note` 而非绑定本身，绑定与反例都成立，故不改档为"错"）。
⇒ 建议 13-A 把该句改成**真实理由**（同目录 `tests/valuelayer/_fixtures.py:11-27` 其实**写对了**：夹具副本自备是为了可写/可控，且**故意**保留一处"夹具 ≠ 真文件"对照 —— `min_nonnull_rate` 夹具 `0.8` vs 真文件 `0.9`）。两处口径应统一到 `_fixtures.py` 那份。

### §13.5 §13 汇总

| 项 | 判词 |
|---|---|
| `R8-1` 深度（`thresholds` 分组）+ 键名（`*_count`）**两处同时改** | ✅ **好**（真件实测 5 个键读通真值、1 个按 `tbd` 响亮拒用） |
| `tbd` 处理（`UndecidedThreshold` + `scanned` 计数 + note + CLI 可见） | ✅ **好**（不静默、不恒红、不放行） |
| `g_depth_violations(真件)` 可变判定 | ✅ **好**（性质从"读不到规则"变为"按真阈值判数据"）；★ 但阶段②**仍红**，因真数据六节为空 |
| `R8-2` 三项（`valuelayer` 批次 / `chapter4_g_depth` 反例 / `stage_gate` 绑定） | ✅ **好**（含"没动 13-B 条目"的边界） |
| `test_criterion_effectiveness.py` **冲突标记未解 ⇒ 语法非法 ⇒ 门禁 `exit=2`** | ❌ **错 / 阻塞** |
| `completeness.py:542/:651` docstring 旧键名残留 | ⚠ **不够**（小尾巴，建议顺手改） |
| 反例登记 `note` 的"真仓库那份尚不存在" | ⚠ **不够**（与事实矛盾，改口径） |
| `verify.py` / `test_criterion_effectiveness.py` 冲突：**一个已解、一个未解** | 已上报 13-A |

⇒ **`#69` 保持 `in_progress`**：13-A 面**首次有被测对象**（工作区态），但**尚未提交**；本节所有结论**须在 commit 后按 hash 重跑一次**（`§13` 已给出全部可复跑命令）。

---

## §14 13-A 面 ②（新增键 / rules 消费面）与 ③（硬编码）—— **只读静态核，未跑其单测**（`V-05`/`V-08`）

> 快照同 §13：**工作区态**（`main..ws/ch4-valuelayer` 零领先提交），`R8-1`/`R8-2` 之外的部分。**未改任何被审文件。**

### §14.1 ② `rules/` 消费面：**唯一读口 + 只引用 2 件已安装件** ✅ 好

```
$ ls -1 system/scripts/valuelayer/
__init__.py  _rules.py  completeness.py  growth_quality.py  moat_guard.py  rollup.py  route_guard.py  state_machine.py

$ grep -rnE 'rules/|_cached_yaml|_rules\.' system/scripts/valuelayer/*.py | grep -v 注释
system/scripts/valuelayer/_rules.py:32   from scripts._common import _cached_yaml          ← 走 P-02 的缓存读口
system/scripts/valuelayer/_rules.py:34   BASELINE_RELPATH = "rules/baseline.yaml"
system/scripts/valuelayer/_rules.py:35   METRIC_SETS_RELPATH = "rules/metric-sets.yaml"
（其余模块**一律**经 `_rules.*`，无第二处 `_cached_yaml`、无第二处路径字面量）
```
| 事实 | 判词 |
|---|---|
| **只有 `_rules.py` 读 `rules/`**（其余 7 个模块全走它） | ✅ **好**（`G-06` 唯一读口，且 `P-02` 走 `_cached_yaml`） |
| 只引用 **2 件**：`rules/baseline.yaml` + `rules/metric-sets.yaml`，**都是已安装件** | ✅ **好**（无引用未安装件 / 无自造路径） |
| 无自造键：所有读取键都在已安装件里（`thresholds.*` / `metric_sets` / `routing.fallback_metric_set_id`） | ✅ **好** |

**★ `tbd` 的处理我判 ✅ 好（且它自己给了"为什么必须处理"，是本轮我看到的最锋利的一段推理）**：
```
route_guard.py:140-146
  """转成字符串元组；`None` / **`tbd`** / 空 ⇒ `()`（=「未声明」，不是"声明了一个叫 tbd 的值"）。
     ★ 为什么必须显式处理 `tbd`：13-R 转写 `rules/metric-sets.yaml` 时，设计**没给值**的字段如实写了 `tbd`
       （如 `MS-GENERIC` 的 `stages: tbd`、`MS-CLOUD-5STAGE` 的 `linked_accounts: tbd`）。
       若照字符串处理，`stages: tbd` 会变成**一个名为 `tbd` 的段名** ⇒ 真实转化链的段名全被判成
       "不在注册表里" ⇒ 假红；（`metrics: tbd` 更会逐**字符**迭代而直接抛异常）。
       故 `tbd` 一律读作「**未声明**」，由各检查按 `G-03` 记"不可核"。"""
```
⇒ 这是把"`tbd` 是占位符不是值"**落成了代码**，而不是靠注释自律。

### §14.2 ③ 硬编码：4 个新模块**没有硬编码阈值**；两道边界个案我都给了"为什么不是违规"

扫描口径：在 `rollup.py` / `moat_guard.py` / `state_machine.py` / `route_guard.py` 里找 `[2-9]` 及以上的数字字面量（去掉注释/docstring 后）⇒ **命中全部落在 docstring、异常消息与设计引文里**，**无一处是阈值**。

| 候选 | 情形 | 判词 + 为什么 |
|---|---|---|
| `moat_guard.py:19` `and len(kinds) >= 2` | **设计逐字**：`04_公司价值研究与深度标准/02_实现方案.md:311` 的 `§F.2` 代码块原文就是 `and len(kinds) >= 2   # 需证据组合（≥2 类）` | ✅ **不是违规**（`R8-3` 的判据是"**值住哪由谁定**"：此处**设计自己把值写在伪码里**，且**没有**要求"参数化到 rules" ⇒ 转写它就等于照设计落值。★ 注意反例：`baseline.yaml` 的阈值设计**明写**"占位 + 参数化 `rules/baseline.yaml`"，所以那一类才必须进 rules —— **同样一个"2"，两种判词，差别在设计的指派**） |
| `growth_quality.py:247-252` 上限 | `limit = cfg.get("max_primary_drivers_per_business")`；`None` ⇒ `MissingRuleInput("…代码不内置默认值")`；`cfg` = `_rules.baseline_cfg(root)` = **`thresholds` 分组** | ✅ **好**（上限只从 rules 读、缺键响亮失败、**深度正确** —— 这正是 `R8-1` 的第二层） |
| `route_guard.py:475-482` 兜底 id | `fallback_id = str(_rules.metric_set_routing(root).get("fallback_metric_set_id") or "")`，再与 `_rules.GENERIC_METRIC_SET_ID` 比对，不一致即报错 | ✅ **好**（真源在 rules，代码常量只作**一致性对照**，不一致就响） |

### §14.3 ★ 一条**同一族的新观察**（我判"待裁定"，不下缺陷判词）—— `metric-sets.yaml` 的多数分组**全仓零消费者**

`rules/metric-sets.yaml` 有 **11 个**顶层键。我逐键数了消费者（`scripts/valuelayer/` + **全仓**）：
```
分组（顶层键）                       13-A 内提及次数   全仓 scripts/tests 提及
metric_sets                                 有（route_guard:193）      有
routing.fallback_metric_set_id              有（route_guard:475）      有
financial_link                                   6                     ——
unregistered_model_class                         7                     ——
binding_guard                                    0          ★ (exit=1) 零
metric_item_fields                               0          ★ 零
segment_evidence                                 0          ★ 零
conversion_chain_per_model_class                 0          ★ 零
conversion_chain_generic_stages                  0          ★ 零
extension_policy                                 0          ★ 零
routing.key / binding_field / metric_owner_field 0          ★ 零
```
★ 我**不判"缺陷"**，理由有二（这就是我承诺的"不是一刀切"）：
1. `binding_guard` / `segment_evidence` / `conversion_chain_*` 的键名是**转写自设计节号**的（`metric-sets.yaml:79` 标 `§C.2`、`:103` 标 `§B.1`/`§B.2`、`:88` 标 `§C.3`、`:76` 标 `§C.1`），**不是**代码自造；设计给了这些**声明**，是否要求"运行时读"**设计没写**。
2. `binding_guard` 的两条 `rule_*` 恰好是 **13-A 的 `rollup.py` 真正实现的规则**（跨业务直接引用 / `model_class` 不符）⇒ 更可能是"**声明面 + 门禁核**"的用法，而不是"valuelayer 运行时读"。
⇒ 但它属于**我已报过的同一族**（`§12.2(b)`：`solution_set_display` "装了没人读"；`§12.3`：`scenario_tags` 零绑定）：**装了 ≠ 有人读**。
⇒ **待你裁定/立卡**（我不擅动 `rules/`）：这些分组要么 ① 明确"**由门禁核**（哪一道）"并给出该门禁，要么 ② 明确"**首版不消费**"并登记（`G-03`：未消费 ≠ 已交付）。★ 顺带自曝：**这 4 件 rules 是 13-R（我）转写的** —— 所以这条观察**也是对我自己产出物的复查**，不是只挑别人的。

### §14.4 §14 汇总

| 项 | 判词 |
|---|---|
| `rules/` 唯一读口（只有 `_rules.py`）+ 走 `_cached_yaml`（`P-02`） | ✅ **好** |
| 只引用 2 件**已安装**规则文件、**无自造键** | ✅ **好** |
| `tbd` 一律读作"未声明"并记 `G-03`（含段名不会变成 `"tbd"` 的假红论证） | ✅ **好** |
| 4 个新模块**无硬编码阈值** | ✅ **好** |
| `len(kinds) >= 2`（设计伪码逐字） | ✅ **不是违规**（判据是"设计有没有指派参数化"） |
| `metric-sets.yaml` 的 6–7 个分组**全仓零消费者** | ⚠ **待裁定**（不判缺陷；同族第三次） |
| 未核部分 | 4 个新模块**未跑其单测**（避 `V-05`/`V-08` 配额）；结论仅覆盖静态读取链和数字扫描 |

---

## §15 卡 **13-G**（`G-57`）：`rules/metric-sets.yaml` 9 个零消费者键**逐键三分类** + `R8-3` 收口复核

**复核人**：`ws-ch2-rules` —— ★ **我是这 4 件规则文件的转写人（13-R）** ⇒ 本节我是**枚举者**，**定性结论须换人复核**（并入批次 14 审计）。**不因"是我自己写的"而放宽 (c) 类登记要求。**
**被审对象**：`system/rules/metric-sets.yaml`（11 顶层键，**9 键零消费者**）+ 全仓消费者面（`system/scripts` · `system/tests` · `system/schema` · `system/registry`）。
**基准**：`main = 90e7c94`（含 `bef9628`）；13-A 面另查**其工作区**（因 `route_guard.py` 尚未提交，只查 `main` 会假阴性）——
快照 SHA：`route_guard.py f1c0c166ceb6` · `_rules.py 74c20c26e398` · `completeness.py 62e541cc95ad` · `rollup.py 087eb7640667` · `moat_guard.py 602050847758` · `growth_quality.py 55043b1f4c0c` · `state_machine.py 5b67f2680356` · `__init__.py 448cc755719e`。
**未改任何被审文件**（`rules/**` 0444，只准主理人安装）。

### §15.1 一、结论（四段式 · 第①段）

> **`(a) 有运行时消费者 = 0` / `(b) 由门禁·schema·测试核 = 0` / `(c) 三者皆无 = 9`。**
> **⇒ 9 个键**全部落到 **(c)**，需要**逐键处置**（补消费者，或显式登记"首版不消费 + note + 计数"）。

★★ **我必须先更正我自己 `§14.3` 的推测**：我当时写「`binding_guard` 的两条 `rule_*` 恰好是 `rollup.py` 实现的规则 ⇒ 更可能是『**声明面，由门禁核**』」。**"由门禁核"这半句被实测推翻**：全仓**没有任何门禁读 `metric-sets.yaml` 的语义**。真实情形是「**有实现**（代码真的实现了那两条规则）+ **有行为测试**（13-A 的 `tests/valuelayer/test_rollup.py` 等）」—— 但**检查的是行为，不是键**。这两件事差别很大：**键被删掉、或被改成矛盾值，那些测试照样全绿**。
⇒ 这正是本卡要防的形态：**"有人实现了同一件事" ≠ "这个键有人消费"**。

### §15.2 二、证据（四段式 · 第②段）

#### (a) 三分类的**判定口径**（我先把它写成可判定的，免得"算不算被核"各说各话）

| 类 | 我用的可判定判据 |
|---|---|
| **(a)** | 全仓（`scripts`+`tests`+`schema`+`registry`，**含 13-A 工作区**）搜该键名 ⇒ 有**代码**读它（指名 `文件:行`） |
| **(b)** | ★ **判别力口径**：把该键的值换成一个**"合法但错误"**的值（如 `binding_field: nonsense`）后，**存在某个机器检查会变红**。只"输出会随该键语义变化"的检查才算。按本项目自己的 `R-06 ①/④`：**关键词/禁词式的通用扫描不算**（它只覆盖**形状**，不覆盖**消费关系**） |
| **(c)** | 以上皆无 |

#### (b) 逐键结果（★ 9/9 落在 (c)）

| 键 | 类 | 证据（实测） | 处置 |
|---|---|---|---|
| `binding_guard` | **(c)** | 键名全仓 **0 命中**（含 13-A 工作区）。★ 但它的**声明内容恰好全部真实存在**：`guard: scripts/valuelayer/route_guard.py` ✅、`entry: validate_binding` ✅（`route_guard.py:21` 与 `:254`）、`rule_model_class_mismatch: raise MetricSetMismatch` ✅（`:65 class MetricSetMismatch`）、`rollup: scripts/valuelayer/rollup.py` ✅ ⇒ **声明与实现对得上，但无人校验"对得上"** ⇒ 两边可各自漂移 | **补绑定（最便宜、价值最高）**：一条"规则里声明的**路径/符号必须存在**"的检查（`guard`/`entry`/`rollup` 可解析；`rule_model_class_mismatch` 里的符号名存在）。这正是 `§C.2` 声明面唯一缺的机器绑定 |
| `metric_item_fields` | **(c)** | 0 命中。schema 里**没有"指标 item"对象**：`$defs` 中含 `source_class` 的**只有 `Driver`**（`models.py:1206` 的 `Literal[7 类 + mixed]`），`linked_account` 对应的是 `Driver.financial_link.accounts`（`models.py:1267` 逐字）⇒ **同名但不同物** | 显式登记"首版不消费"。★ **给门禁设计者的防误报提示**：**别按字段名绑** —— `source_class` 是 `Driver` 的字段，按名字绑会得出"已消费"的**假绿** |
| `segment_evidence` | **(c)** | 0 命中。其**字段名**在 schema 有对应（`facts.schema.json:1566` 的 `ChainSegment` 描述 + `:1585 pending_evidence` 属性 + "证据为空却不标注 ⇒ 拒绝"的校验器），但**没有检查读这个键** | **补绑定**：断言 `ChainSegment` 的字段集 ⊇ `{evidence, pending_evidence}`（`field`/`evidence_field` 两键各指一处） |
| `conversion_chain_generic_stages` | **(c)** | 0 命中。四段名只在 `models.py:1036` 的 **docstring** 与 schema 的 description 里被**文字引用** | 显式登记"首版不消费"。★ **不要**为它加枚举绑定：`facts.schema.json:1566` 逐字说明 `stage` **刻意是自由字符串**（"写成枚举会让 `§C.3` 的扩展机制失效"） |
| `conversion_chain_per_model_class` | **(c)** | 同上，0 命中 | 同上（同理不得绑成枚举） |
| `extension_policy` | **(c)** | 0 命中。**行为**已实现（`route_guard` 的 `MS-GENERIC` 兜底 + `unregistered_model_class` 标注，13-A 内 7 处），但**键本身无人读** | **补绑定（判别力最强的一条）**：用 13-A **已有的 scratch-root 夹具**写"给副本 rules 注册一个新 `metric_set` ⇒ `route_guard` 能路由它、**不改一行代码**" —— 这才真正守住 `new_model_class_requires_code_change: false` |
| `routing.key` | **(c)** | 0 命中（值 `model_class`）。★★ **且该值与 schema 不一致**：`Business` 的路由字段是 **`business_type`**（`models.py` 类 docstring：`business_type: str  # 路由键（model_class，见 §C）`）；`metric-sets.yaml:15-18` 自己已登记这处"命名张力" | 显式登记 + **绑定须做映射**：按 `business_type` 做**等价映射**，**别按字面 `model_class` 找字段**（必然找不到） |
| `routing.binding_field` | **(c)** | 0 命中（值 `business.metric_set_id`）。对应字段**存在**：`Business.metric_set_id`（`models.py:1118`） | **补绑定**：断言 `business.metric_set_id` 可在 schema 解析 |
| `routing.metric_owner_field` | **(c)** | 0 命中（值 `business_id`）。对应字段存在：`Business.business_id` | **补绑定**：同上 |

#### (c) 独立登记的「**有覆盖但只覆盖形状**」三处（**不**因此判 (b)，但**必须写出来**，否则会显得"这文件完全没人管"）

| 检查 | 覆盖什么 | 为什么**不足以**算 (b) |
|---|---|---|
| `rules_lock_guard`（`rules.lock.json` 含 `metric-sets.yaml`：`bytes`/`locked_mode 0o444`/`sha256`） | **文件级**：内容一变（未重锁）就红 | 它判的是"**文件变了**"，不是"**语义错了**"；重锁即绿 |
| `conflict_scan` **L3**（`CONFIG_SCAN_TARGETS = ("rules", "registry")`，`_flatten_mapping` **逐键**取 `(key, val, dotted)` 比 L3 禁词） | **键名与外层字符串值**命中禁词则红 | 把值改成 `nonsense`（合法但错）**不会红** ⇒ 对该键的**消费关系**零判别力（`R-06 ①/④`） |
| `no_placeholder_guard`（`scanned files: 136`；`.yaml` 在 `SCAN_EXTENSIONS` 内；`rules/` **不在** `EXEMPT_PATTERNS`/`_EXEMPT_PREFIXES`/豁免清单里） | **文件级**占位词扫描 | 同上：只判形状。★ 顺带一条**实测事实**：`tbd` **不在**该门禁的 token 表里（8 条 `LINE_RULES` 无 `tbd`）⇒ `metric-sets.yaml` 的 `tbd` 现在 **PASS**（`RESULT: PASS（0 violations）`） |

### §15.3 三、处置建议（四段式 · 第③段）

**原则**：**(c) 不等于"必须马上写代码"**，但**必须二选一**（`G-03`：不许静默留着）——
**① 补消费者**，或 **② 显式登记"首版不消费"（note + 计数，落在 `registry/` 侧）**。

| 优先级 | 键 | 建议 |
|---|---|---|
| **P0（补绑定，成本低、判别力强）** | `extension_policy` · `binding_guard` | 前者一条 scratch-root 用例；后者一条"声明路径/符号存在性"检查 |
| **P1（补绑定，成本低）** | `routing.binding_field` · `routing.metric_owner_field` · `segment_evidence` | 都是"断言 schema 里那个字段/字段集存在" |
| **P2（登记"首版不消费"+ 说明为什么不该绑）** | `metric_item_fields` · `conversion_chain_generic_stages` · `conversion_chain_per_model_class` | 前者的"同名不同物"、后两者的"自由字符串是有意设计" ⇒ **登记时把"为什么不绑"写清**，防后人误绑 |
| **P2** | `routing.key` | 登记 + 记录"值 `model_class` 与 schema 字段 `business_type` 的映射关系"（`metric-sets.yaml:15-18` 已有张力说明，登记时**指回去**即可） |

**★ 对 `ws-schema-expand` 的 13-pre（方向 2）门禁设计的硬约束（三条，来自本卡实测）**：
1. **必须三态输出**（`有消费者(运行时)` / `有消费者(门禁·测试)` / **`零消费者 ⇒ 红`**）且**三类各自计数**（主理人已裁，我补证据）。
2. ★★ **(b) 的判定必须用"判别力"口径**（改值 ⇒ 变红），**不能**把"这个行为已被测试覆盖"算成"这个键被消费" —— 否则本批 9 个键会**全绿**（因为 `rollup.py`/`route_guard.py` 的行为确实有实现也有测试），**门禁当场变成安慰剂**。
3. ★ **必须防"同名不同物"**：`segment_evidence` 的 `field`/`evidence_field`、`metric_item_fields` 的 `source_class` 都与 schema 里的**别的东西**同名 ⇒ **按字段名匹配会造成假绿**。绑定要么按**显式映射表**（规则键 → schema 符号），要么**只认"显式登记过的绑定"**，不做名字推断。

### §15.4 四、边界与待复核（四段式 · 第④段）

**责任边界（`§九`，我自己是转写人）**
1. 我是**枚举者**；**"哪一类"的最终定性须换人复核**（并入批次 14 审计）。我**没有**因"文件是我写的"而下调 (c) 的标准 —— **9 个键我一个都没往 (b) 里塞**，包括最像 (b) 的 `binding_guard`。
2. 本节结论对应 §15 开头的**快照 SHA**；13-A 工作区**正在被编辑**（我在核查中发现同一键的命中数在两分钟内从 1 变 0 —— 因为那是 `_fixtures.py` 里的**夹具副本**且该文件正被改动）⇒ 13-A 面**须在提交后复跑**。

**未做（如实登记，不冒充已核）**
3. ~~**未跑**任何探针去"真的把一个键改成错值再看门禁变不变"~~ ⇒ ★ **已做，见 §15.6**（我先把这条写成"未做"，随后补跑了差分实验；**此处保留原文并划掉**，不偷偷改写）。仍**未做**的是：**其余 8 道门禁**（`rules_lock_guard` 之外还有 `registry_schema_guard`/`freeze_guard`/`injection_guard`/`schema_sync_guard`/`criterion_effectiveness_guard`/`verification_policy_guard`/`shell_var_guard`/`graph_integrity_guard`）**未逐道跑差分** —— 理由是**静态已证**"无任何代码路径读这些键"（穷尽式搜索），**任何**检查都不可能有判别力；故剩余 8 道**由该结论覆盖**，不再逐个跑（并**如实标注这是推断而非实测**）。
4. `no_placeholder_guard` 覆盖 `rules/**` 这条，我是**代码审查 + `scanned files: 136`** 得出的，**不是**"逐文件列出被扫清单"的实测。

---

### §15.5 附：同轮的 `R8-3` 收口复核（`bef9628`）—— **rules 侧 ✅ 已补 / 代码侧 ❌ 仍未动，且新增一层"声明 ≠ 实现"**

**(a) `rules/` 侧 ✅ 已补，且采纳了我 §12.2(d) 的**方案 ②**：**
```diff
 system/rules/valuation-methods.yaml
 solution_set_display:
   default_count: 3
   max_count: 5
+  must_show_multiple: true       # ★ 语义键（`§B.1` 逐字）…这是**语义要求**、非数值参数。
+                                 #   ★ 数值下界（"多"的机械化 = ≥2）**不在此处**：它由本键**派生**
+                                 #   （`min_count = 2 if must_show_multiple else 1`），
+                                 #   以**避免**"语义键与数值键可互相矛盾"的同一事实两处（`G-06`）。
```
⇒ 我 §10.3 候选里的 `min_count: tbd` **没有被采纳**，改为"语义键 + 派生" —— **这个取舍比我的更好**：`tbd` 会把一条**已经把话说死的语义要求**降级成"待定"，且与语义键构成"同一事实两处"。**这一处我判 ✅ 好。**

**(b) 代码侧 ❌ 未动 —— 且形态**升级**了：**
```
$ git grep -nE 'DEFAULT_DISPLAY_CAP|MAX_DISPLAY_CAP|DEFAULT_MIN_SOLUTIONS' main -- system/scripts system/tests
solver.py:79 DEFAULT_DISPLAY_CAP = 3 / :82 MAX_DISPLAY_CAP = 5 / :85 DEFAULT_MIN_SOLUTIONS = 2
solver.py:318/:336/:391/:403/:503（决策路径，同 §11.2）
test_solver.py:19/:20/:168/:169
$ git grep -n 'solution_set_display' main -- system/scripts system/tests
(exit=1)                    ← ★★ rules 那份**仍然零消费者**（含新增的 `must_show_multiple`）
```
★ 定档 **❌ 错**（比 §12.2(b) 的"未做"更重）：规则文件现在**明文写着一个实现行为**——"它**由本键派生**（`min_count = 2 if must_show_multiple else 1`）"——而**该派生在代码里不存在**、常量 `2` 仍硬编码。**从"零消费者"升级为"声称已被消费/已派生"**。
★ **我把分歧点写出来，判词可由你定**：该注释也可读作**给你的实施指令**（`batch13_taskbook.md` 同批写了"代码删掉常量 `2`"）。若按"指令文本"读 ⇒ 应记为**未做**；我按**文件自身时态**（"它由本键**派生**"是陈述句、且 `rules/` 是**已安装真相源**而非草稿）判 **错**。**请裁**。

**(c) 我 §12.5 的两条已闭合 ✅**：`:374` 的假阴性括注**已删**并加了订正段（还留了一句很好的教训："裁定文本引用下级的 `grep` 结果前，要么自己复跑、要么注明未复核"）；`:391-392` 的落点**已更正为 `valuation-methods.yaml`**。

**(d) 仍未闭合**：13-B 的 `scenario_guard.py` 机器绑定**仍只在工作区**：
```
$ git grep -nE 'RULE_KEY_TAGS|_rule_binding_violations|SCENARIO-RULE-BINDING' main -- system/scripts/pricelayer/scenario_guard.py
(exit=1)     $ git grep -n 'scenario_tags' main -- system/scripts system/tests   → 0 命中
```
⇒ `G-55`（`scenario_tags` ↔ `ScenarioTag` 零绑定）在**真源上仍未闭合**；`bef9628` 没动它。

**`#69` 状态**：13-A 仍**未提交**（`main..ws/ch4-valuelayer` 空；`UU` 两个文件）⇒ A/B 的 13-A 面**仍差"提交后按 hash 重跑"**。

### §15.6 ★ 追加：**(b)=0 的差分实验（把 §15.4 第 3 条的"未做"补上）—— 可执行证据，不是推断**

**方法**（照项目自己的"反例是否 load-bearing"口径）：在 **scratch root**（`/tmp`，**不碰被审区**）里跑同一道门禁**两次**，只改 `rules/metric-sets.yaml` 的一个变量：

```
$ S=$(mktemp -d); mkdir -p "$S/rules" "$S/schema/jsonschema" "$S/registry"
$ cp rules/*.yaml "$S/rules/"; cp schema/jsonschema/facts.schema.json "$S/schema/jsonschema/"; cp registry/*.yaml registry/*.json "$S/registry/"

=== A) 真件副本（未改）===
$ python3 scripts/checks/conflict_scan.py "$S" --no-report ; echo $?
  scanned l3_config_files: 21          ← ★ 其中含 rules/metric-sets.yaml：门禁**确实读了这个文件**
RESULT: PASS（0 violations）
0
$ python3 scripts/checks/no_placeholder_guard.py "$S" --no-report ; echo $?
  scanned files: 22
RESULT: PASS（0 violations）
0

=== B) 把 9 个键全改成「**合法但错**」的值，其中 4 处**与代码/设计直接矛盾** ===
  binding_guard.entry                          : validate_binding          → definitely_not_a_function
  binding_guard.rule_model_class_mismatch      : raise MetricSetMismatch   → do_absolutely_nothing
  binding_guard.rule_metric_owner_must_be_own_business: true              → false      ← 与 rollup 实现矛盾
  binding_guard.cross_business_reference       : forbidden                 → allowed    ← 与 rollup 实现矛盾
  metric_item_fields                           : [name, unit, source_class, linked_account] → [zzz]
  segment_evidence.blocks_financial_link       : true                      → false      ← 与 §B.2 矛盾
  segment_evidence.field                       : segment.pending_evidence  → nope.nope
  conversion_chain_generic_stages              : [获取,交付,使用,变现]      → [A,B]
  conversion_chain_per_model_class.hardware    : 订单→排产/出货→…            → 乱写一串
  extension_policy.new_model_class_requires_code_change: false            → true       ← 与 §C.3 矛盾
  routing.key / binding_field / metric_owner_field: model_class / business.metric_set_id / business_id
                                                                          → not_a_field / not.a.field / not_a_field

$ # 变更已落盘校验（避免"其实没改成"的假实验）
★ 变更已落盘校验：binding_guard.entry = definitely_not_a_function | routing.key = not_a_field
  | extension_policy.new_model_class_requires_code_change = True | metric_item_fields = ['zzz']

$ python3 scripts/checks/conflict_scan.py "$S" --no-report ; echo $?
RESULT: PASS（0 violations）
0
$ python3 scripts/checks/no_placeholder_guard.py "$S" --no-report ; echo $?
RESULT: PASS（0 violations）
0

$ diff <A的输出> <B的输出>
★ 逐行完全相同（两份均 PASS / 0 violations）
```
⇒ **结论（可执行）**：把 9 个键改成**最恶毒**的错值（含 4 处直接与代码矛盾），这两道**确实读了该文件**的门禁**一行输出都不变** ⇒ 它们对这些键的**语义零判别力**，**(b) 的判词成立为实测结论**，不再只是"由静态搜索推出"。
★ 这也顺带证伪了一个可能的乐观猜测："虽然没人读，但至少 `conflict_scan` L3 会挡住乱改" —— **挡不住**（L3 只比禁词，`not_a_field` 不是禁词）。

**★★ 我在做这个实验时踩了两个坑，如实登记（否则后人照抄会得到假结论）**：
1. **第一次 B 跑出来"完全相同"是无效的** —— 我漏了 `rules/*.yaml` 是 **0444**，`cp` 把只读位一起复制过去，`write_text` 抛 `PermissionError`，**变更根本没落盘**，所以 A/B 当然一样。修法：`chmod u+w` 后再改。⇒ **教训：差分实验必须先"校验变更已落盘"**（我后来加了 `★ 变更已落盘校验` 那段打印，就是为此）。
2. **更早一次 scratch 只放了 `metric-sets.yaml`**，`conflict_scan` 直接 `[INPUT-ERROR] … 缺少禁词表 … rules/banned_tokens.yaml`（`exit=2`）。那次 A/B 也"diff 完全相同"，但**同样是假结论**（两次都 `exit=2`）⇒ **教训：`exit=2` 是输入错误，此时"结果一致"毫无意义，必须先把输入备齐**。
⇒ 两条都属"**看起来很干净的结论其实什么都没测**"，与本报告 §11.2 的 `grep` 假阴性同类 ⇒ **写进报告备查**。

★ **边界（仍未做）**：**其余 8 道门禁未逐道跑差分**；依据是"无任何代码路径读这些键"（穷尽式搜索）⇒ 任何检查都不可能对这些键有判别力。**这是推断**，我如实标注，并建议批次 14 若要更硬可补齐（成本低：同一 scratch 手法）。

---

## §16 提交后重跑（R11/R12 之后按 per-file SHA 结账）

**本节时点**：`2026-09-16` 夜。team-lead 的边界是「13-A 仍差 `git add`，一提交你就按 hash 结账」——
**实测：13-A 已完成 `git add`（索引不再 `UU`、5 个原冲突/改动文件全部 `M ` 已 staged、语法全部 OK），但仍未 `commit`**；
13-B（`ws/ch5-pricelayer`）**也已 `git add` 到 12 个文件，同样未提交**。
⇒ 本节**不是"按 commit hash 结账"**，而是**按 per-file blob SHA 结账**：我把每个被核文件的当前 blob SHA 钉在下面，
任何人可在提交后用 `git rev-parse <commit>:<path>` 比对"是不是同一份"。

### §16.1 对象与时点钉死（先说清"我在核哪一份"）

| 文件（13-A 树 `ws/ch4-valuelayer`） | 本次 blob SHA（`git hash-object`） | 我上一轮记的 | 是否变过 |
|---|---|---|---|
| `scripts/valuelayer/_rules.py` | `97e894c6b39f` | `74c20c26e398` | ★ **变过** |
| `scripts/valuelayer/completeness.py` | `359bd0c2a1dc` | `62e541cc95ad` | ★ **变过** |
| `scripts/valuelayer/growth_quality.py` | `9eef7391ac03` | `55043b1f4c0c` | ★ **变过** |
| `scripts/valuelayer/route_guard.py` | `992b9cc38f63` | `f1c0c166ceb6` | ★ **变过** |
| `scripts/valuelayer/moat_guard.py` | `6018fa60c5d7` | `602050847758` | ★ **变过** |
| `scripts/ops/verify.py` | `f73c6638b643` | — | — |
| `scripts/delivery/stage_gate.py` | `52698012a694` | — | — |
| `registry/criterion_counterexamples.yaml` | `d2dbafc7ab0a` | — | — |
| `tests/injection/test_criterion_effectiveness.py` | `58ac473880f1` | — | — |

| 文件（13-B 树 `ws/ch5-pricelayer`） | 本次 blob SHA（`git hash-object`） |
|---|---|
| `scripts/pricelayer/solver.py` | `452084eb3b28` |
| `scripts/pricelayer/valuation.py` | `9e4e1102e0fc` |

★ **两个工作树在我这一轮复核期间都仍在移动**：
13-B 的 `solver.py` 在我核的过程中 SHA 又变了一次（行号随之下移/上移 1~18 行，例：`class SolutionSetDisplay` 从 `:118` → `:117`，
`min_solutions` 派生从 `:523` 前移，`assert_multi_solution` 从 `:403` → `:505`）。
⇒ **本节所有 `文件:行号` 一律以 §16.1 这两个 SHA 为准**；对不上就是被改过，**须重跑本节**（不要"就地沿用行号"）。

★ **13-A 的树在我这一轮复核期间仍在移动**：`g_depth_violations` 已从 `moat_guard.py` **移到** `completeness.py:1082`，
`baseline_threshold` 从 `_rules.py:127` 挪到 `:128`。我第一次写的探针因此 `ImportError`。
⇒ **教训（再次）**：跨人工作树做"提交后复核"，**唯一稳的做法是先把 SHA 钉下来再断言**；
本节所有结论**只对上面的 SHA 成立**。团队里这条已咬过我两次（§11.2 的 `grep`、§13 的键数 1→0），这次是第三次。

### §16.2 team-lead 指定的四项 —— 逐项结账

| # | 结账项 | 判定 | 我的实测证据 |
|---|---|---|---|
| 1 | `未绑定判据[nvidia_sample]` **2 → 1** | ✅ | 我实跑 `python3 system/scripts/checks/criterion_effectiveness_guard.py system --no-report`：`note: 未绑定判据[nvidia_sample]：1 条（['evidence_locatable']）`，且 `RESULT: PASS（0 violations）`、`exit=0`（上一版是 2 条 + `exit=1` 结构性红） |
| 2 | `chapter4_g_depth` 在 `registry_entry_tests_resolved` 里查得到 | ✅ | 同一跑输出 `scanned registry_entry_tests_resolved: 16`（= `criteria_registry_entries: 16`）；登记条目**只有 1 条**（见下"2 处命中 ≠ 2 条"） |
| 3 | 13-B 的 `git grep 'solution_set_display'` 非空 | ⚠️ **只在工作树成立** | `git grep … main -- system/scripts system/tests` → **`exit=1`（空）**；`ws/ch5-pricelayer` 工作树 → **25 处命中**（`load_solution_set_display` 等）。⇒ **必须合并后才算真闭合** |
| 4 | `chapter4_g_depth` 绑定位置仍在 `six_step_chain_complete` 之前 | ✅ | `stage_gate.py` 内字符偏移 `chapter4_g_depth`=**17376** < `six_step_chain_complete`=**17430**（对应 `:467` / `:468`，`:469` 是 `derivation_reviewable`） |

★ **"2 处命中 ≠ 2 条登记"**（防误读）：`criterion_counterexamples.yaml` 里 `chapter4_g_depth` 字面出现 **2 次**，
但它们是**同一条**的 `criterion_id:` 与 `test: …::test_nvidia_sample_chapter4_g_depth_blocks_on_incomplete_form`。
⇒ **条目数 = 1**，`kind: counterexample`，`stage: nvidia_sample`，`blocked_hint: "Ch4 §G 形式完备性未过"`。
（`nvidia_sample` 出现 7 次 = 3 条 × 2 + 1 行节标题注释，同样自洽。）
**这条计数纪律要留着**：`grep -c` 对 YAML 是**下界**，不是条目数。

### §16.3 `R8-1` 复核（键名 + 深度）—— 独立探针，全程不走它们的 pytest

我写了一个只做直接调用的探针（`/tmp/probe13a.py`，不落库、不写报告），实测：

```
=== R8-1(a) 键名：真件读值 ===
  baseline_threshold('min_locator_count')            = 1
  baseline_threshold('min_derivation_count')         = 1
  baseline_threshold('min_nonnull_rate')             = 0.9
  baseline_threshold('max_primary_drivers_per_business') = 5
  baseline_threshold('min_fields_per_section') -> UndecidedThreshold
      "rules/baseline.yaml::thresholds 的 'min_fields_per_section' 为 'tbd' —— `tbd`/未拍板的值不得被当成一个可用…"
  baseline_threshold('__no_such_key__') -> MissingRuleInput
      "rules/baseline.yaml::thresholds 缺少键 '__no_such_key__' —— Ch4 §G.2/§D.2 要求该阈值参数化在…"

=== R8-1(b) 深度：真件必须可判定 ===
  len(g_depth_violations(真件)) = 9   FATAL = 9
    例：FATAL Violation(rule='nvidia_sample', reason="Ch4 §G 形式完备性未过 [baseline-nvda-001][sections_nonempty]：①业务与产业…")
```

⇒ **✅ R8-1 两件都落地，且是"真件可判定"而不是"夹具里可判定"**：
4 个阈值真读到值（**键名已真对上**）；`min_fields_per_section` = `tbd` ⇒ **响亮拒绝**（`UndecidedThreshold`，非静默取默认）；
**不存在的键 → `MissingRuleInput`**（≥2 处调用 ⇒ 缺键不兜底，这正是我在 §10 要的"缺键不许兜"）。
深度侧 `g_depth_violations(真件) = 9 条全 FATAL`（六节为空 + 非空率 0.1429 < 0.9）⇒ **不再是"无被检对象"**。

★ **残留（非阻塞，可核）1**：`completeness.py:543`、`:652` 两处 docstring **仍写旧键名** `cfg.min_locators` / `cfg.min_derivations`
（实装常量已是 `min_locator_count` / `min_derivation_count`，见 `:85-87`）。同一文件 `:82` 已留改名史说明 ⇒ **文档漂移，非行为缺陷**，
但我上一轮报过、**这一轮实测仍在**，故如实记载（不重复开单，只挂在此处备查）。

★ **残留（非阻塞，可核）2 —— `R8-3` 条款③ 的第二个条件没满足**：`moat_guard.py:19` 的 `len(kinds) >= 2` 仍是**唯一 1 处**、
代码未动（`90e7c94` 只把它写成条款③）。条款③ 说「照设计落值 = 转写，**可留代码**」——但**有第二个条件**：
「**代码必须在 docstring 标出该设计锚点**」。实测该行只有行末注释 `# 需证据组合（≥2 类）`，
**没有**指向设计逐字出处（我们上一轮引的是 `04_…/02_实现方案.md:311`）。
⇒ 判定：**留代码的资格成立，但"标设计锚点"这一子条件未做** —— 这是个一条注释即可闭合的小缺口，但它**不属于任何门禁能核的范围**（见 §16.5 末尾的名单类判据边界）。

### §16.4 `R8-2` 复核（归属：只登记自己的）

| 子项 | 判定 | 证据 |
|---|---|---|
| 只加自己的 `valuelayer` 批次条目 | ✅ | `verify.py:395` 新增 1 个 `valuelayer` 批次（`:396` 注释援引 `V-06`）；`pricelayer` 批次仍在 `:348`，其条目内容我逐行比对后**未变**；`ALL` 序 `:436/:437` 两者相邻 |
| 只登记自己的 `nvidia_sample::chapter4_g_depth` 反例 | ✅ | 见 §16.2 之"2 处命中 ≠ 2 条"：条目 1 条、`kind: counterexample`、note 明确自称"批次 13-A 绑定"；**未占用**他人条目（同节其余 2 条是既有的） |
| `未绑定判据[nvidia_sample]` 2→1 | ✅ | §16.2 第 1 项 |

★ **但该条 note 里有一句不实，我实测证伪**：note 写「…**真仓库那份尚不存在**，故不写它就只能测到'规则缺失 ⇒ 无法判定'这一条」。
实测：`system/rules/baseline.yaml` **存在**（7515 B，`thresholds` 段键齐全：
`max_primary_drivers_per_business: 5` / `min_nonnull_rate: 0.9` / `min_locator_count: 1` / `min_derivation_count: 1` / `min_fields_per_section: 'tbd'`）。
**夹具副本存在的真实理由不是"真件不存在"，而是"真件的 `min_fields_per_section` 是 `tbd`（未拍板）⇒ 该判据在真件上不可判定"** ——
反例要让 `sections_nonempty` / `nonnull_rate` **判成红**，需要一个**已拍板**的字段数阈值，这一点 13-A 自己在
`tests/valuelayer/_fixtures.py:97` 已经写清了（「★ 与 `BASELINE_CFG` 的唯一差别：`min_fields_per_section` 在这里是**已拍板的 1**」）。
⇒ **建议把 note 的理由改成后者**（现成措辞就在 `_fixtures.py:19-24` / `:97-116`）。这是**登记文本不实**，不是行为缺陷，但本项目的口径是"登记的每条理由都要能被证伪"。

### §16.5 `R8-3` 复核 —— 我上一轮的判词要**加对象限定**（自我更正）

**★ 更正点**：§15.5(b) 我判「代码侧 ❌ **错**：`rules/` 现在**断言**了一段代码里不存在的派生
（`min_count = 2 if must_show_multiple else 1`）」。
**这条判词对 `main` 成立，对 `ws/ch5-pricelayer` 工作树不成立** —— 同一句话在两个对象上真假相反。
（这正是本项目反复在教的那一课；我自己又犯了一次"判词不带对象"。）

**实测（13-B 工作树）**：该派生**已实现**，且不是"把值挪个地方"：

```
（行号 as of `solver.py` SHA `452084eb3b28`）
solver.py:102  RULE_KEY_SOLUTION_SET_DISPLAY = "solution_set_display"
solver.py:117  class SolutionSetDisplay  —— "带来源标注"
solver.py:127      @property
solver.py:128      def min_count(self) -> int:
solver.py:130          return 2 if self.must_show_multiple else 1
solver.py:133  def load_solution_set_display(root) —— "唯一读口"，走 `scripts._common._cached_yaml`（P-02）
solver.py:494  min_count = display.min_count          ← 呈现层真读（不再是常量）
solver.py:522  assert_multi_solution:  min_solutions = display.min_count if … else DEFAULT_MIN_SOLUTIONS
solver.py:582  check(): "下限**读** …solution_set_display.must_show_multiple 派生，**不硬编码**"
solver.py:597  report.scanned["min_solution_count"] = display.min_count   ← 计数也走真源
solver.py:600  for text in _rule_binding_violations(root_path):   ← 规则↔代码机器绑定
solver.py:672  if int(declared_default) != DEFAULT_DISPLAY_CAP:  → 违例
solver.py:679  if int(declared_max)     != MAX_DISPLAY_CAP:      → 违例
```

**我自己的独立探针（不走他们的 pytest；`/tmp/probe13b.py`）**：

| 探针 | 输入 | 输出 | 说明 |
|---|---|---|---|
| A 真件 | `root = ws/ch5-pricelayer/system` | `default_count=3  max_count=5  must_show_multiple=True  min_count=2  value_source='rules'` | 真读规则，不是走常量 |
| B 篡改（**合法但改行为**） | `must_show_multiple: true → false` | `min_count 2 → 1`，`value_source='rules'` | ★ **有判别力**：规则改则行为改 |
| C 篡改（非法） | `default_count: 3 → 9`（> `max_count=5`） | `PriceLayerError`（响亮失败，"不静默夹紧"） | 非法值不静默 |
| D 键整体缺失 | 删掉 `rules/valuation-methods.yaml` | 回落 `3/5/2` 且 `value_source='design_default'` | 回落**标了来源** |

⇒ **`R8-3` 在 13-B 这一面实质落地**（口径从"值在不在 rules 里"升级到"规则改则行为改"），
**且 `git grep` 只在工作树非空**（§16.2 第 3 项）。

**三个常量没消失，但角色变了**（要请示口径）：
`solver.py:79 DEFAULT_DISPLAY_CAP=3` / `:86 MAX_DISPLAY_CAP=5` / `:92 DEFAULT_MIN_SOLUTIONS=2` 仍在，但现在承担两件事：
① 规则文件/键缺失时的**回落**（docstring 明标"真值取自 `rules/…`"）；
② **漂移断言锚** —— `_rule_binding_violations` (`:643`) 在 `:672` / `:679` 比对规则声明的 `default_count` / `max_count`
与代码常量，**不一致即报违例**（`solver.py:672` / `:679`，实测读的是"与 `DEFAULT_DISPLAY_CAP` / `MAX_DISPLAY_CAP` 不一致"）。
⇒ 按 `G-06` 的通行解法（真源 + 机器绑定，同批次 11 的 `_TRUTH_STEMS↔注册表` 手法），我判**已收口**：两处**不静默**。
★ **但这里有一个必须说清的分层（否则会把它读成"已单一真源"）**：
`must_show_multiple` 是**真·单一真源**（代码**只**派生、不存副本，改规则即改行为 —— 探针 B 已证）；
而 `default_count` / `max_count` 是"**真源在 rules + 代码留副本 + 漂移断言绑死**"：
只改 rules 会让 `_rule_binding_violations` 报违例 ⇒ **使用者必须同时改两处**才能过门禁。
⇒ 也就是"**副本不可能悄悄漂移**"，但**仍是同一事实两处**。**请 team-lead 裁**：`G-06` 允不允许这一形态
（我倾向允许，理由是它不静默、且副本能覆盖"规则文件缺失仍需可运行"的场景；但这条只是我的倾向，不是我可以自己拍的口径）。

**★ 残留（新增，可核）—— `max_grid_points` 面两条**：

1. **`护栏` 标注未落地**。`batch13_taskbook.md:402` 明文要求「`max_grid_points=256` / `max_nodes=512` … 留代码，**docstring 须标"护栏"**」
   （这是我在 §10.3 提、主理人采纳的处置）。实测：`grep -c 护栏` → `solver.py` **0**、`valuation.py` **0**。
   ⇒ **要求未做**。**且它天然无法被门禁核**（没有任何检查能判断 docstring 里有没有"护栏"二字）⇒ 属**名单类判据**，
   按 `R-06` 只能当 lint，**不得**当成防护判据（这正是我 §15 对 13-G 那三条硬约束的同一逻辑）。
2. **模块头一句陈述与实装不符**。`solver.py:30-31` 写：「超出 `max_grid_points` **不静默**：记 note **+ 置 `degraded`**」。
   实测：网格超限路径（`:369-374`）**只**记 note（`GRID_CAP_EXCEEDED: …`，`:371`），note 经 `:466 solution_set.notes.extend(notes)`
   **确实非静默** ✅；但 **`degraded` 只在"未达解数下限"路径置位**（`:495-496`，`SINGLE_SOLUTION_RISK`），
   `GRID_CAP_EXCEEDED` 与 `degraded = True` 在全文件**无任何关联**（`grep` 各仅 1 处）。
   ⇒ **"记 note + 置 degraded" 里后半句是不实陈述**。修法二选一：改文档，或在超限路径也置 `degraded`（**请 13-B 定，我不改他人文件**）。
   ★ 附带说明**为什么我维持"`max_grid_points` 是护栏"这个分类**：它**会**改变产出（`:374 values = values[:max_grid_points]` 截断 ⇒ 可行集变了），
   但它**非静默**（note 落盘）⇒ 满足"护栏"分类成立的前提；反之前提一旦丢掉（note 被删），这个分类立刻不成立。

### §16.6 未闭合清单（按对象分，便于派活）

| 对象 | 未闭合项 | 严重度 | 我的建议 |
|---|---|---|---|
| **13-A**（工作树，已 `git add` 未提交） | 无阻塞项（四项结账 3 ✅ + 1 条件成立）；两条文档/登记残留：`completeness.py:543/:652` 旧键名、`criterion_counterexamples.yaml` note 的「真仓库那份尚不存在」 | 低（非行为） | **提交即可**；两条残留一并顺手改（各 1 行） |
| **13-B**（工作树，已 `git add` 12 文件未提交） | ① `max_grid_points`/`max_nodes` 的 `护栏` 标注（taskbook:402 要求）；② `solver.py:30-31` "置 `degraded`" 不实；③ 三个常量形态待 team-lead 裁 | 低（①②） | 提交后我按 hash 复跑 §16.3/§16.5 探针 |
| **13-B（`main` 面）** | `git grep 'solution_set_display' main` 仍 `exit=1` ⇒ `R8-3` 在真源上**尚未闭合** | — | **以合并为准**，合并后我重跑一次 |
| **我的树** | `git status --short system/rules system/registry` = **空** ✅（未污染真源）；本节只改 `reports/` | — | 无 |

★ **本节仍未做（如实标注，不掩盖）**：
1. **没有"按 commit hash 结账"** —— 因为**两个工作树都还没提交**。本节是**按 blob SHA 结账**，SHA 已钉在 §16.1；
   提交后请把 `git rev-parse <commit>:<path>` 与我表里的 SHA 对一下，**一致则本节结论直接继承**，不一致则**本节作废、须重跑**。
2. **我没有跑 13-A / 13-B 的 pytest**（`V-05`/`V-08` 的批耗时方差问题；此刻 13-A 树在动、13-B 树也在动）。
   本节所有"可执行"结论都来自**我自己的直接调用探针**（`/tmp/probe13a.py`、`/tmp/probe13b.py`），
   与它们的用例**互不覆盖**：我只能证明"这个键真被读了、改了会变行为"，**不能**代替"它们的用例全绿"。
3. 其余 10 个 rules 文件的引用面**本轮未重扫**（§12 已按 `main` 重钉过一次；13-A/13-B 未提交 ⇒ 不影响 `main`）。

### §16.7 对照组（我提交本节时**顺带白捡的**正/反控制 —— 比单点测量硬得多）

我提交 §16 时，**我自己的** worktree（`ws/ch2-rules`）的 `pre-commit` 也跑了同一道 `criterion_effectiveness_guard`。
我的树**不含** 13-A 的改动（`rules/`、`registry/` 与 `main` 一致，见 §16.6 末行）⇒ 于是同一道门禁、同一份门禁代码，在**两个树**上给出：

| `scanned` / `note` 项 | **13-A 树**（含其 staged 改动） | **我的树**（= `main` 面） | 差 |
|---|---|---|---|
| `未绑定判据[nvidia_sample]` | **1 条**（`['evidence_locatable']`） | **2 条**（`['chapter4_g_depth', 'evidence_locatable']`） | **−1（正好少了 `chapter4_g_depth`）** |
| `criteria_registry_entries` | 16 | 15 | +1 |
| `registry_entry_tests_resolved` | 16 | 15 | +1 |
| `criteria_bound` | 13 | 12 | +1 |

`criteria_registry_entries` → `15 → 16` 与 `criteria_bound` → `12 → 13`、`未绑定判据[nvidia_sample]` → `2 → 1`，
三处**同时**只动 **1** ⇒ 在这次改动里，`chapter4_g_depth` 这一条判据**恰好**从"声明 automated 但未绑定 + 无登记"变成"已绑定 + 有 1 条反例登记"。
⇒ 这是**正/反控制对**，它同时证明两件事：
1. **§16.2 第 1、2 项的 `2→1` 是 13-A 的改动造成的**，不是我这边环境/缓存造成的（我把同一跑在**不含**该改动的树上做了反向对照）；
2. 这道门禁**对对象敏感**（不是常数输出）—— 否则两个树会给出同一组数。
★ 反过来也提醒一句：**任何"门禁显示 PASS/N 条"的读数，必须连"在哪个树上跑的"一起报**；只报数字，读者无法区分"没做"和"做了但没生效"。

---

## §17 卡 13-J（`#79`）实现 + `§16` 重钉 + `G-60` 现场

### §17.1 `§16` 重钉：**9 个 blob SHA 与 `a8f763f` 逐一相同 ⇒ 本节结论整体继承**

13-A 已提交并合并（`a8f763f` / merge `3a7acc9`，我在本树 `git merge main` ⇒ `9c775ca`，并重跑了 `bootstrap_worktree.sh`：
`rules_lock_guard` PASS、14 个 `rules/*.yaml` 全 `-r--r--r--`，符合 `G-53`/`V-07`）。

| 文件 | `git rev-parse a8f763f:<path>` | §16.1 我记的 | |
|---|---|---|---|
| `_rules.py` | `97e894c6b39f` | `97e894c6b39f` | ✅ 一致 |
| `completeness.py` | `359bd0c2a1dc` | `359bd0c2a1dc` | ✅ |
| `growth_quality.py` | `9eef7391ac03` | `9eef7391ac03` | ✅ |
| `route_guard.py` | `992b9cc38f63` | `992b9cc38f63` | ✅ |
| `moat_guard.py` | `6018fa60c5d7` | `6018fa60c5d7` | ✅ |
| `verify.py` | `f73c6638b643` | `f73c6638b643` | ✅ |
| `stage_gate.py` | `52698012a694` | `52698012a694` | ✅ |
| `criterion_counterexamples.yaml` | `d2dbafc7ab0a` | `d2dbafc7ab0a` | ✅ |
| `test_criterion_effectiveness.py` | `58ac473880f1` | `58ac473880f1` | ✅ |

⇒ **§16 的 13-A 面结论（四项结账、R8-1、R8-2）按此继承，无需重跑**。`#69` 只剩 **13-B 面**（`git grep 'solution_set_display' main` 仍 `exit=1`）。

### §17.2 卡 13-J 实现（`+252 / −12`，单文件）

**对象**：`system/tests/injection/test_criterion_effectiveness.py`（`58ac473880f1` → **`d7977a94f7c9`**）。

**设计（按卡的三条硬要求 + 我补的第四条）**：

| 要求 | 落法 |
|---|---|
| **两边必须不同源** | **期望值** = 测试**自己**数（`yaml.safe_load` 直接解析登记表；按路径加载**被检副本**那份 `stage_gate.py` 取绑定集合）；**实际值** = **门禁 CLI 打印文本**解析（`_scanned()`）。不 import 门禁的任何私有函数 |
| **关系式「锚」** | 三条，全部**纯文本可核**：①**穷尽性** `ce + ineffective == registry_entries`；②**划分恒等式** `bound + not_implemented == declared_automated`；③**义务方向** `registry_entries >= criteria_bound` |
| **反向对照（防真空）** | 新增用例 `test_derived_count_assertion_is_load_bearing`：①文本侧篡改 ②真源侧篡改但**不重跑** ③三条锚逐个喂坏值 ④干净输入必须绿 |
| ★ **我补的第四点** | `len(entries) == 16` **不能**派生成 `len(entries) == <派生数>` —— 它**不是**在核对数字，而是在**防真空**（空登记 ⇒ 参数化循环 0 次 ⇒ 静默通过）⇒ 改为 `assert entries, "登记为空 ⇒ 本用例真空"` + `assert monkey_checked == len(entries)`（"逐条都真被删过一次"） |

**★ 诚实标注（这条判据的**能力边界**，别读过头）**：
`criteria_bound` 的真源只有 `stage_gate.bound_criteria()` 一个（`G-06` 不许门禁另写解析）⇒ 这一路两边**数据源必然相同**，
它真正在核的是「**门禁的统计/打印管道 == 直接聚合**」，**不是**「真源本身算对了」（后者由 `stage_gate` 自己的用例与门禁断言 E 承担）。
且**"台账一变就逼人复核"这条绊线按设计消失了**：新增一条判据时，旧写法会红（逼你来看），新写法直接绿。
⇒ 这是**有意取舍**（卡就是这么要求的），替代物是上面三条锚 + 两条反向对照 ⇒ **请 team-lead 知情**。

### §17.3 派生**前 / 后**各跑一次（据实）

**前（写死版，`3c7b34d` 的 `58ac473880f1`）**：把它的 5 个字面量与**同一次干净运行**的门禁真值对拍 ⇒ **逐条相符**，即旧断言在该树上是绿的：
```
旧断言字面量:  criteria_bound: 13 / criteria_registry_entries: 16 / counterexample_entries: 15
              ineffective_entries: 1 / criteria_without_counterexample: 0
门禁实际报数:  criteria_bound: 13 / criteria_registry_entries: 16 / counterexample_entries: 15
              ineffective_entries: 1 / criteria_without_counterexample: 0        exit = 0
```
**后（派生版，`d7977a94f7c9`）**：同一条件，`_assert_counts_match` 绿；五键"门禁文本 vs 测试自数"逐条相等（见 §17.5 之 A）。

**本回合的 pytest 实测（在删除配额耗尽**之前**完成）**：
```
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_criterion_effectiveness.py \
    -q -p no:cacheprovider \
    -k "pristine_tree or removing_any_registry_entry or derived_counts_follow or derived_count_assertion"
....                                                                     [100%]
4 passed, 25 deselected in 17.72s
```
⇒ 改动的两条 + 新增的两条**全绿**。

### §17.4 ★★ `G-60` **现场**：本回合删除配额耗尽 ⇒ 完整单文件回归**跑不了**

紧接着的整文件回归失败，且**不是缺陷**：
```
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_criterion_effectiveness.py -q -p no:cacheprovider
EEEEEEEEEEEEEEEEEEEEEEEEEEE..                                            [100%]
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
  {"count":100267,"threshold":99999,"scope":"turn","targets":["…/tests/.work/test_prep_compliant_baseline_is_green-…"],"targetCount":1}
⇒ 27 E / 2 passed（过的那 2 条是**不建 `code_root` 夹具**的用例）
```
**归因（我自己的算术，防误栽给某一条流）**：`system/` = **629 文件 + 123 目录**（夹具还 skip `__pycache__/.work/reports/derived/index/state.json` 等）⇒
一次 `code_root` 用例的 teardown 最多删 ~600 项；我那 4 条**最多贡献 ~2.4k** ⇒ **距 100267 三个数量级**。
⇒ 与 `V-09` 的定性一致：**删除预算是「宿主回合级 + 全流共享」** ⇒ 是全体并发流一起推到了天花板。**已广播全流**（"任何 `E`/`INTERNALERROR` 先看有没有 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`，别报成本单缺陷；不许绕过"）。

★ **`G-60` 的新实测数据点（比原登记更硬）**：不是"残留清不掉"那么轻 ——
**正常开发（跑一个文件的用例）在单回合内就会撞天花板**，且判据是 `count = 累计 + 本次 > 99999` 的**累计式**，
**一旦越过，连"删 1 项"都被永久拒绝**（我实测 `targetCount: 1`）。
⇒ 卡 13-F 把 `_clear_work_dir()` 改**逐文件删除**（单次体量 ~600 → 1）是**唯一**能救的方向；"分批/分片跑"按此机理**救不了**（与 `G-60` 登记一致）。

> ★★ **本段已被 §17.11 更正（`ws-degrade-contract` 的实测 + 我重算三份报文）**：
> 「**逐文件删除是唯一能救的方向**」这句**站不住** —— 按实测模型，`base` 本身已 = `99,998`，
> **单次删除只要体量 ≥ 1 就 `99,998 + 1 = 99,999 ≥ 99,999` 被拒** ⇒ 逐文件**既不增加可删总量**，
> 还会把「一次原子拒绝」变成「**删到一半开始拒绝**」= 静默半清空。详见 §17.11。

★ **因此本节"整文件 29 条全绿"这句话我**没有**拿到**。我**不会**拿 `E` 冒充结论 —— 替代证据见 §17.5（**不删文件**的直连探针，覆盖同样四条用例的全部逻辑）。

### §17.5 端到端直连探针（**不删任何文件**；`cp -R` 到 `/tmp` 后直接调门禁与派生函数）

> ★ **事后补记（§17.11 之后）**：本节探针之所以能跑，此前我只敢说"因为它在 `/tmp`、不动仓库"——
> 现在有了**实测机制**：`/tmp` 是一个**独立的低基数桶**（`ws-degrade-contract` 实测 `4334`，
> 对照仓库内桶 `99,998`，同一时刻同一解释器）⇒ **`/tmp` 下的删除不受该守卫拦**。
> ⇒ 这条同时意味着：**本节的成功读数从来就不是关于删除配额的证据**（我当时也是这么写的），
> 而且它给出了一条**建设性出路**：**夹具工作目录若落在系统临时目录，本会话就能全程跑完**（详见 §17.11）。

```
A. 干净件：门禁 exit = 0；`_assert_counts_match` 绿；五键"门禁文本 vs 测试自数"逐条相等
   criteria_bound 13/13 · criteria_registry_entries 16/16 · counterexample_entries 15/15
   ineffective_entries 1/1 · criteria_without_counterexample 0/0

B. 反向对照①（**文本侧**篡改门禁报数 +1）⇒ ★ AssertionError：
   "`counterexample_entries`：门禁报 16，测试自己数得 15 —— 两条路径不一致"

C. 反向对照②（**真源侧**删一条但**不重跑**门禁）⇒ ★ AssertionError：
   "`criteria_registry_entries`：门禁报 16，测试自己数得 15"
   （变更已落盘校验：15 == 16 − 1）

D. 正向（真源侧删 `expansion::review_append_only` 最后一条 counterexample → **重跑**门禁）：
   门禁 exit = 0；`_assert_counts_match` **绿（全程未改任何字面量）**；
   counterexample_entries 15 → 14、registry_entries 16 → 15；门禁文本与派生一致

E. 三条锚：基线绿；坏值逐个**必红** —— 锚①改 ineffective+1 红、锚②改 declared+1 红、锚③（隔离）registry<bound 红

F. 防真空：空登记下 `assert entries` 必触发（否则参数化循环 0 次 ⇒ 静默通过）
⇒ 全部通过 ✅
```
★ 口径 1′（注入/篡改型实验三条自证）**逐条打印**：锚点在（受害条目下标 `[12,13,14]`）/ 前后不同 / **读回文件确认已落盘** —— 任一条不成立就停。

### §17.6 两条给 team-lead 的更正请求

1. **`76a2d5b` 不是仓库里的对象**。`3c7b34d` 的 `batch13_taskbook.md` 写「卡 13-J 归属改派给 `ws-ch2-rules`（它已提交 `76a2d5b` 交付"逐条方案与证据"）」，但我实测：
   ```
   $ git log --oneline --all | grep 76a2d5b      → 空
   $ git cat-file -t 76a2d5b                     → fatal: Not a valid object name 76a2d5b
   ```
   ⇒ **请更正该 hash**（可能是 `76ec851` 的笔误？那条是"§11 + §12"）。我**没有**用任何 `76a2d5b` 提交过东西；
   13-J 的"逐条方案与证据"实际在**我发给你的两条消息**里，落盘的对应物是 `0b834e0`/`ba17f28`（§16/§16.7）。
   ★ 这与本项目"每条登记都要可核"的口径同类 —— 一个**指不到任何对象的 hash** 会让后人无法复核，故按纪律报出（我自己的 `grep` 假阴性也是这么被纠的）。
2. **`G-60` 已收入我的复核视野**，并给出同族定位：它是我 §15 立的"**静默变空**"家族的**第三种形态** ——
   `G-03`（无被检对象 ⇒ 不得当已验证）是第一种，`len(entries)==16` 防的"空集 ⇒ 循环 0 次"是第二种，
   `G-60`（清理机制在累计超限后**永久失效** ⇒ 会话启动即被拒）是第三种：**"空"与"通过/成功"观测上无法区分**。
   ⇒ 建议 `G-60` 的修法在登记里也照这个措辞写一句，将来好一起查。

### §17.7 未做 / 未验证（如实）

1. **整文件 29 条的全绿**：本回合**无法取得**（`G-60`，见 §17.4）。我拿到的是"4 条相关用例 pytest 全绿" + "覆盖同四条逻辑的直连探针全绿"。
2. **其余 25 条未逐条重跑**：我对它们的改动面为零（只新增了 7 个模块级名字、改了 2 条用例、加 1 个 `import importlib.util`），
   且已核**无重名**（`_COUNT_KEYS`/`_scanned`/`_registry_rows`/`_bound_pairs`/`_derived_counts`/`_assert_counts_match`/`_assert_count_anchors` 各只 1 处定义，`:903`–`:997`）⇒ **推断**它们不受影响，**这是推断、不是实测**，本回合无法补。
3. **13-B 面仍未闭合**：等它提交后按 hash 复跑。

### §17.8 ★★ 实现过程中撞上 `G-61` 的**最恶性形态**：幽灵门禁卡死**全流**提交（本节是现场记录，非本单缺陷）

**现象**：本单的第一次提交被拒：
```
pre-commit → scenario_tag_binding_guard
  python: can't open file '…/ws-ch2-rules/system/scripts/checks/scenario_tag_binding_guard.py': [Errno 2]
pre-commit ✗ scenario_tag_binding_guard 阻断（exit=2）
pre-commit: 有门禁阻断，提交被拒。
```

**我先按上一轮 `G-61`（`quote_provenance_guard` 那次）的办法处理 —— 合并 `main`** ⇒ **`Already up to date`**（我已在 `681f696`），脚本**仍然不存在** ⇒ 说明这次**不是"滞后"**。

**根因（实测命令与输出，不是推断）**：
```
$ git -C /Users/gaza/Developer/InvestSigh status --short        # 主仓工作区（@ main）
A  system/scripts/checks/scenario_tag_binding_guard.py
AM system/scripts/checks/scenario_tag_binding_guard.py          # ← 暂存后又改过（磁盘≠索引）
M  system/scripts/ops/pre-commit.sh                             # ← 暂存里加了第 ⑬ 条门禁
M  system/scripts/ops/run_all_gates.py
A  system/tests/guards/test_scenario_tag_binding.py
A  system/reports/ws_g55_binding_guard_report.md

$ git merge-base --is-ancestor 7835c0b main   → 不是祖先（**未合并**）
$ git branch --contains 7835c0b               → 只在 ws/ch13-e-benchmark-fields
```
机制：**共享钩子（`.git/hooks/pre-commit`，全 worktree 共用）执行的是主仓那份
`/Users/gaza/Developer/InvestSigh/system/scripts/ops/pre-commit.sh`** —— 那份**含第 ⑬ 条、但只处于暂存状态**；
而 `CODE_ROOT` 从 cwd 反解 = **被检的那个工作树** ⇒ 任何**不含 `7835c0b`** 的树里都没有该脚本 ⇒ `[Errno 2]` ⇒ `exit=2`。

| | 上一轮 `quote_provenance_guard` | **本轮 `scenario_tag_binding_guard`** |
|---|---|---|
| 判据脚本在哪 | **已在 `main`** | ★ 只在 `ws/ch13-e-benchmark-fields`，**未合并**，且**暂存在主仓索引** |
| `git merge main` 能救吗 | ✅ 能（脚本随合并进来） | ❌ **不能**（`Already up to date`——那个状态**不在任何可合并的分支上**） |
| 谁受影响 | 所有**滞后**的树 | ★ **所有树**（含 `main` 自己：它也合并不到"那个"状态） |

⇒ **升级前的判断**：在 `7835c0b` 被提交并合进 `main` 之前，**全体流的 `git commit` 都会失败**，且**报成"违规"**。
⇒ 已**直接报 team-lead**（二选一：提交合并 `7835c0b`，或把主仓索引恢复到一致状态 —— **都由那个工作区的属主做，我不碰主仓**），并**广播全流**（"先看有没有 `Errno 2` / `SAFE_DELETE_BULK_CONFIRM_REQUIRED`，别把基础设施错配读成本单缺陷；**不许 `--no-verify`**"）。

★ **同处还有一个独立的小缺陷（可核、易修）**：`exit=2` 是**输入错误**（本项目自己的约定：`2`=输入异常、`1`=违规），
但 `pre-commit.sh` 把两者**同款报成"阻断"** ⇒ 把**判据与对象不同源**伪装成**"你改坏了"**。
**建议**：脚本不存在时报 `[INPUT-ERROR] 门禁脚本不在被检树里：判据与对象不同源（G-61）`，**保持 `exit=2` 阻断**
（**不跳过** —— 跳过会掩盖"真缺一道门禁"），但**不写"阻断"**。
★ 我**没有**去改 `pre-commit.sh` / `run_all_gates.py`：它们此刻**在别人的暂存区里**，一动就制造冲突 —— 这也正是"不进他人工作区"这条纪律的自然后果。

★ **本单的处置（留痕）**：
1. **没有 `--no-verify`**，也不会用 —— 绕过门禁得到的绿不算证据；
2. 中间为绕开"树不干净 ⇒ 不能合并"做过一次 `git stash` / `git stash pop`，**用 blob SHA 逐字校验复原**：
   测试文件 `d7977a94f7c9…`、报告 `e98546e88aa9…`，pop 后**两个 SHA 与 stash 前完全一致**（另有 `/tmp/probe13j/` 下的备份）；
3. **`git merge main` 两次**把 `quote_provenance_guard` 等已合并的新门禁脚本取回本树（第一次解决了它，第二次 `Already up to date` 说明第二轮起就卡在幽灵门禁上）。

### §17.9 幽灵门禁**闭合**（`main` 前移到 `53de9a3`）+ 一个可复用的手法「合并前先干跑」

**对象**：worktree `/Users/gaza/Developer/InvestSigh/.worktrees/ws-ch2-rules`（分支 `ws/ch2-rules`）；时点：本单提交之前。
（口径 10：本节所有读数都出自这棵树 + 下面写出的那些 SHA。）

**① §17.8 的两形态在 `53de9a3` 上同时闭合（实测，不是转述）**

```
$ git log --oneline f5dbc6f..53de9a3      # f5dbc6f = 我上一轮合进来的那个 main 头（= 当时的 main）
53de9a3 merge ws/step56-skipped（口径 11 补合）
f2d1371 merge ws/fixture-cost（口径 11 补合）—— 冲突取分支侧：guards 维持 300s…
8aa7862 merge ws/ch13-e-benchmark-fields: G-55 跨载体绑定守卫（门禁清单冲突取并集 ⑫/⑬…）
7e608c0 docs(ws/step56-skipped): `G-60` 归因更正 —— 那只日间歇 ERROR 是删除预算的**未越顶阶段**
e18aedd Merge branch 'main' into ws/fixture-cost
5f80ea5 docs(g55): 报告按口径 9/10 订正 —— 所有读数带树+SHA
664252f Merge branch 'main' into ws/ch13-e-benchmark-fields
7835c0b feat(guards): G-55 —— 跨载体取值域绑定守卫（rules/scenario.yaml ↔ 实现侧枚举）+ 双落点登记

$ git merge-base --is-ancestor 8aa7862 main        → YES（8aa7862 已是 main 祖先）
$ git ls-files --error-unmatch system/scripts/checks/scenario_tag_binding_guard.py   → 命中
$ grep -n scenario_tag_binding_guard system/scripts/ops/pre-commit.sh
119:run_gate "scenario_tag_binding_guard" "$CODE_ROOT/scripts/checks/scenario_tag_binding_guard.py" "$CODE_ROOT"
```

⇒ 两形态各自的出路都到位了：**判据脚本 `7835c0b` 已可达**（治"滞后可 merge 修"那半），
**主仓索引里那份"悬空判据"也已随 `8aa7862` 合进 `main`**（治"判据只在未合并分支"那半）。
★ 值得记一笔：**闭合方式正是我 §17.8 提的第一选项（把它提交并合并）**，而不是动主仓索引 —— 也就是说
`G-61` 这一族当时**唯一的正解**就是"把悬空判据落成 commit 再说"，我判断"不碰主仓、只升级报主理人"这条路是对的。
★ 附带一条**别人已经追上的**：`f2d1371` 把 `ws/fixture-cost` 的合并（含 `verify.py` 冲突解）也带进了 `main`
（`e18aedd` 那条）⇒ `auditor-batch11` 警告的"你 `git merge main` 可能在 `verify.py` 上冲突"**本轮没有发生**，
因为冲突解已经先一步进 `main` 了（教训同 `口径 11`：**警告的对象会过期**）。

**② 手法（可复用）：合并前先 `merge-tree` 干跑，别急着 stash**

上一轮我为了"树不干净 ⇒ 不能合并"付了两次 `git stash` 的代价，其中一次还因为 `&&` 链断掉把活儿留在了 stash 里（§17.8）。这次换了顺序：

```
$ git merge-tree --write-tree --name-only HEAD main
db8e4c6662b2423f46ad88afe41372c19e114c65        ← 只回一个树 OID、**无任何冲突行** ⇒ 干净合并
$ git merge-base HEAD main
f5dbc6f02fb4aa3cde99b6cb0c2ef9405ed68062
$ git diff --name-only $(git merge-base HEAD main) HEAD
system/reports/ws_ch2_rules_consumption_review.md      ← 我这边相对祖先只改了这一个文件（已提交的那部分）
```
⇒ **`merge-tree --write-tree` 是"不落地、不改索引、不改工作区"的冲突探测**（`git 2.50.1`）。
**这一步应在任何 stash 之前做** —— 它把"要不要 stash、会不会冲突"从**试探**变成**判读**。
我这次据此判定"我的两个文件都不在合并面上"，于是**只 stash 了我自己的两处改动**（避免被折进 merge commit），而不是盲目 stash 整个工作区。

**③ 落地与逐字复验**

| 步骤 | 命令 | 结果 |
|---|---|---|
| stash 前 | `git hash-object` 两个文件 | `d7977a94f7c9d5d8…` / `6c37ac21284224954b…` |
| stash | `git stash push -m ws-ch2-rules-13J -- <两文件>` | `RC=0`，`git status` **干净**，报告回到 HEAD 的 1788 行 |
| 合并 | `git merge main --no-edit` | **`RC=0`，零冲突**（`ort` 策略，11 files changed, +1234/−107）⇒ 新 HEAD `da8254e`，无 `MERGE_HEAD` 残留 |
| pop 后 | `git hash-object` 两个文件 | **`d7977a94f7c9d5d8a8564b8fe1539be4c181ba45` / `6c37ac21284224954b5d73e85f0ea7e57d2db171` ⇒ 与 stash 前逐字节一致** |
| 行数 | `wc -l` | 报告 **1969** 行、测试 **1285** 行 |
| `rules/` 权限 | `ls -l system/rules/{freeze,metric-sets}.yaml` | 均 **`-r--r--r--`（0444）** ⇒ 本次合并**未**重置（与 `V-07` 一致：只有**会 stage `rules/` 的** git 操作才重置；本次合并面不含 `system/rules/**`） |

★ 顺带更正我 §17.8 的一条**路径口误**：我当时写的 `rules/freeze.yaml` 是**错的**，
真路径在 `system/rules/`（`git ls-files | grep -E 'rules/(freeze|metric-sets)\.yaml$'`
⇒ `system/rules/freeze.yaml` / `system/rules/metric-sets.yaml`）。这正是我 §17.6 抱怨别人"指不到对象"的同族毛病，故自我登记。

**④ ★ 我第二次犯同一个操作失误（根因不是粗心，是**把校验和变更串在 `&&` 里**）**

```
$ ls -l rules/freeze.yaml rules/metric-sets.yaml && git stash pop
ls: rules/: No such file or directory
--- pop RC=1 ---            ← pop 从未执行，但看起来"pop 了却没效果"
```
上一次（§17.8 第 2 条）也是同一形状：`ls`/`grep` 之类**校验命令**失败 ⇒ `&&` 短路 ⇒ **紧随其后的状态变更命令根本没跑**，
而输出里"有报错、有 RC"很容易被读成"执行了但失败了"。**改法（纳入纪律）**：
**状态变更命令（`stash pop` / `merge` / `add` / `commit`）永远单独一条命令执行，不许和校验命令串在 `&&` 里。**
我是这么补救的：单跑一次 `git stash pop` ⇒ `RC=0`、`Dropped refs/stash@{0} (b6d52264…)`，再单跑 `hash-object` 复验（即上表）。
★ 另外注意 `stash@{1}: On ws/ch4-valuelayer: wip-ch4` **不是我的** —— 共享 stash 栈里还有别人的条目，**不许 `stash clear`**（同 `G-59`/共享资源的性质）。

**⑤ 未做 / 未验证**
1. 本节**不含本提交自身的 hash**（报告无法自含自身 commit 的 hash）—— 13-J 主提交是 **`cf57ca4`**
   （`test(criterion-effectiveness): 卡 13-J —— 写死计数改「判据真源派生」+ 可执行反例（逐个看清原数字在挡什么）`，
   「2 files changed, 515 insertions(+), 12 deletions(-)」，`HEAD~1` = 合并 `da8254e`；提交时**全部门禁 PASS**）；
   复核命令：`git log --oneline ws/ch2-rules` / `git rev-parse cf57ca4:system/tests/injection/test_criterion_effectiveness.py`
   ⇒ `d7977a94f7c9d5d8a8564b8fe1539be4c181ba45`（与上图逐字一致）。
   ★ 本 §17.9/§17.10 自身是在 `cf57ca4` **之后**追加的 ⇒ 本文件在 `cf57ca4` 里的 blob 是 `5742915147c8…`，
   `cf57ca4` 之后的那次提交会给出新的 blob SHA。**这不是"文件变了"，是"报告在持续记账"** —— 读者对不上时请按上句逐级取。
2. `G-60` 的**整文件 29 条全绿**仍然**没拿到**（§17.4/§17.7 不变：本回合删除配额仍受限）。
3. 13-B 面仍未闭合（§17.7 第 3 条不变）——

### §17.10 `#69` 四项结账（对象 = 本树 `cf57ca4` / `main` = `53de9a3`）—— ★ **四项全过，13-A 面与 13-B 面同时闭合**

**先钉对象（口径 10）**

| 项 | 值 |
|---|---|
| 工作树 | `/Users/gaza/Developer/InvestSigh/.worktrees/ws-ch2-rules`（分支 `ws/ch2-rules`） |
| 内容对象 | **`cf57ca4`** = `main`（`53de9a3`）+ 本单两个文件；其 `stage_gate.py` blob = `52698012a694` |
| 该 blob 是否被 `a8f763f..main` 动过 | **没有**（`git log a8f763f..main -- system/scripts/delivery/stage_gate.py` 空、`git diff --stat` 空；`main` / `a8f763f` / 我的树 / 工作区**四者同 blob**） |
| 门禁读数来源 | `python system/scripts/checks/criterion_effectiveness_guard.py system --no-report` ⇒ **`exit=0` / `RESULT: PASS（0 violations）`**；另有一次**同树**读数来自 `pre-commit`（同一门禁，输出一致）；两次跑完 `git status` **仍干净**（`--no-report` 不落报告文件） |

**① `未绑定判据[nvidia_sample]` `2 → 1`** ✅

```
note: 未绑定判据[nvidia_sample]：1 条（['evidence_locatable']）
```
对照侧（`2 条`）在 §16.7 的那张控制表里，**两侧各自的树都写在表上** ——
13-A 绑定前是 `['chapter4_g_depth', 'evidence_locatable']`，绑定后 `chapter4_g_depth` 转入 `bound` ⇒ 只剩 1 条。
★ 这正是本项能"按 hash 结账"的原因：**同一条门禁、同一份登记表、只差 13-A 那一个改动**（`口径 12`：单变量）。

**② `chapter4_g_depth` 在 `registry_entry_tests_resolved` 里查得到** ✅ —— **逐条枚举，不是靠总数推断**

只读探针 `/tmp/probe13_q_resolved.py`（用**门禁自己的谓词** `_check_entry_tests` 对**单条** row 判定）：
```
entries 条数 = 16 ；_test_index 覆盖测试文件数 = 76
逐条 resolved = 16 / 16 ；未 resolved 的条目 = []
其中 chapter4_g_depth 是否在 resolved 名单里：✅ 在
逐条求和 = 16   （与门禁打印 scanned registry_entry_tests_resolved: 16 一致）
```
外加**四组对照**（证明这个谓词是"活的"，不是我念了一遍注释）：
| 对照 | 改法 | 结果 |
|---|---|---|
| ③ 原样 | —— | `violations=0 resolved=1` |
| ① | 函数名去掉 `_chapter4_g_depth` 段 | `violations=1 resolved=0` ⇒ 命中「函数不存在」那条（★**不是**"名字不含判据 id"那条，如实标注） |
| ② | 指向不存在的测试文件 | `violations=1 resolved=0` ⇒ 「反例测试文件不存在或不可收集」 |
| ④ | 指向**真实存在但不含判据 id** 的函数 `test_removing_any_registry_entry_makes_guard_fail` | `violations=1 resolved=0`，理由 =「测试函数名 `'test_removing_…'` 未含判据 id `'chapter4_g_depth'` —— 无法阻止把登记改指向一个与本案无关的用例（`G-02` 函数级绑定）」⇒ **把 G-02 那条单独隔离出来了** |

★ **一处卡面措辞的歧义（不是错，但会误导复现者）**：登记表里**没有 `tests_resolved` 字段**
（`git grep -c 'tests_resolved'` 对 `registry/criterion_counterexamples.yaml` **零命中**）；
它是一个**门禁运行时算出来的计数**：`report.scanned["registry_entry_tests_resolved"] = resolved`
（`system/scripts/checks/criterion_effectiveness_guard.py:359`，计数规则 `:238–288`：
「`test` 非空」→「是 `tests/...py::test_xxx` 形态」→「文件可收集」→「函数存在」→「**函数名含判据 id**」五关全过才 +1）。
⇒ "查得到"的正确含义是**该条目逐关通过、被计入那 16**，我按这个含义核的。

**③ 13-B 面 `git grep 'solution_set_display'` 非空** ✅ ⇒ **13-B 面闭合**
```
$ git grep -n 'solution_set_display' main -- 'system/**'        → 命中 16 行，RC=0
$ git branch --contains 8aa7862                                  → 含 ws/ch5-pricelayer ⇒ 13-B 已并入 main
```
（实现仍在 `system/scripts/pricelayer/solver.py`：`RULE_KEY_SOLUTION_SET_DISPLAY = "solution_set_display"`、`load_solution_set_display`、`min_count` 派生。）

**④ `chapter4_g_depth` 绑定位置仍在 `six_step_chain_complete` 之前** ✅ —— 但**偏移数值须更正我 §16.1 的记法**

哈希钉住的读取（`blob 52698012a694`，文件 **47314** 字节）：
```
字节偏移 21895  行 467  criterion("nvidia_sample", "chapter4_g_depth", v)
字节偏移 21949  行 468  criterion("nvidia_sample", "six_step_chain_complete", v)
字节偏移 22010  行 469  criterion("nvidia_sample", "derivation_reviewable", v)
间距 = 54 字节 ； 关系式 21895 < 21949 ⇒ 成立
```
★ **自我更正 §16.1**：我在 §16.1 记的是 `17376 < 17430`，与本次实测**恰好同差 4515**
⇒ 当时用的是**另一个偏移基准**（不是文件字节 0，很可能是从某个切片/函数体起算），
**结论（谁在前 + 间距 54）完全一致**，但**数值必须以本次为准**。
★ 这条正好演示 `口径 10` 的用处：**一个不带基准说明的偏移量，换个人在原文件上复现就对不上**；
而我当时没写"基准是什么"，所以这次只能靠"同差 4515 + 间距 54 相同"来**反推**它是同两行 —— 能做，但本不该需要。

**★★ 本轮我又犯了两个「自己刚写进纪律」的错（如实登记，不藏）**

1. **BSD `grep` BRE 的 `\|` 假阴性（队内第 5 次 / 我自己第 2 次）**：
   `grep -n 'registry_entry_tests_resolved\|def _check_entry_tests\|tests_resolved' <guard>` **回空** ⇒
   我一度据此以为"脚本里根本没有这个字符串"（差点写成一条**假发现**）。改用 Grep（ripgrep）即有命中。
   ⇒ **卡 13-L 的 `grep_usage_guard` 有据可依，且应把 `\|` 在 BRE 里立成硬禁**（提示语直接给 `grep -E` 的写法）。
2. **`&&` 串了"我要读结果"的命令（第 3 次）**：
   `git grep -c 'tests_resolved' … && git show main:… | grep -b …` —— 前者**无匹配 ⇒ `exit 1` ⇒ 短路**，
   **④ 根本没跑**；而屏幕上只剩"一个没有输出的段"，看起来像"没命中"而不是"没执行"。
   我在 §17.9 第 ④ 条刚写下"状态变更命令不许和校验命令串 `&&`"，**几分钟后就又犯了**（这次受害的是**校验**命令）。
   ⇒ **纪律升级**：**凡"我要读它的结果"的命令，一律单独一条执行**；`&&` 只用于"前一条失败则后一条无意义"的场景。**这条比我原来那条宽** —— 原来只禁了状态变更，现在把校验也纳入。

**小结（可核）**：`#69` 的四项在 `cf57ca4` 上**全过**，且 ③ 使 13-B 面闭合 ⇒
`#69` 的 13-A 面（§16/§17.1 继承）与 13-B 面（本 §17.10③）**都已能按 hash 结账**。

### §17.11 ★★ `G-60` 机制更正（`ws-degrade-contract` 实测 + 三份报文重算）⇒ **「逐文件删除」不是解药**

**一、他作废了哪条读数、我引用了什么**
他先前给我的「体量 1 / 2 / 100 都成功」被他自己推翻：那三次的**目标全在 `/tmp/wsnc/**`**。他实跑仓库内 = `exit=3`、0s、`INTERNALERROR`，并在**同一时刻、同一解释器**做了两步对照：

| 目标 | 结果 |
|---|---|
| `/tmp/wsnc/pathprobe/a.txt`（1 项） | **成功** |
| 仓库内 `system/tests/.work/zz_pathprobe.txt`（1 项） | 拒 `{"count":99999,"threshold":99999,"scope":"turn","targetCount":1}` |

⇒ **`/tmp` 与仓库是两个桶**：`/tmp` 走低桶（实测 `4334`），仓库桶基数 `99,998`。
★ 我**没有**引用过他那三条作废读数（我只引用了这条更正本身）。

**二、三份报文放一起算 —— 自洽性与一处判据缺陷**

| 来源 | 目标 | 报文 `count` | 报文 `targetCount` | 反解 `base = count − 体积(目标)` |
|---|---|---|---|---|
| 他（路径探针） | 仓库内**单文件** | `99,999` | `1` | `99,998` |
| 他（ARM1/ARM2） | 仓库内**目录**（他注："那目录恰 3 项"） | `100,001` | `1` | `99,998` |
| 我（§17.4） | `system/tests/.work/test_prep_compliant_baseline_is_green-…` | `100,267` | `1` | `?`（见第三段） |

★ `base = 99,998` 在**他两条上完全一致** ⇒ 他的判据成立。
★ **但报文里只有 `targetCount`，没有"体积"** —— 他解释 `100,001` 用的是"那目录恰 3 项"，而报文写的是 `targetCount: 1`。
⇒ 唯一自洽的读法：**`targetCount` = 目标个数（1 个目录）**，"被删条数（3 / …）"是**另一个量、报文里没有**。
⇒ ★★ **这是判据本身的一处可核缺陷**：判据写成 `count = 基数 + 本次目标体量`，
可 **`体量` 不在报文里** ⇒ **光看日志无法判读**，归属只能靠猜。
（这正是 `口径 9`/`口径 10` 的作用：**读数必须自带基准与对象**。）
**建议**：`G-60` 登记里补一句「**报文字段语义须先验明**：`targetCount` = 目标个数、非条目数」，
并请宿主在报文里**同时打印 base 与体量** —— 否则"谁把我的额度吃掉了"这类争议**永远无法收敛**。

**三、我 §17.4 的归因要改（自我更正）**
我原文写「`count=100267` ⇒ **全体并发流一起推到了天花板**」。按上面模型，正确读法是
`count = base + 本次目标体积` ⇒ **我这一次请求本身就把 `count` 抬到了 `100,267`**，
不是"我只是被别人的读数连累"。
★ 但我**不能**据此宣布"我那次的 `base` 也是 `99,998`、体积 = `269`" ——
若 `base` 是**累积量**，则我那次（较早）与他那次（较晚）的 `base` **不同**，`269` 这个反解就不成立。
⇒ 要钉住体积，必须有**同刻配对读数**（同一时刻、同一桶、两个体积不同的目标）。**这是本次拿不到的数据**，如实登记。

**四、★★ 结论：`逐文件删除` 既不抬高预算，**还引入"静默半清空"**

设阈值 `T = 99,999`，判据 `base + 体积 ≥ T ⇒ 拒`：

1. **可删总量与粒度无关**：从 `base` 出发，无论一次删 1 项还是 269 项，都只能删到 `base + 体积 < T` 为止 ⇒
   **`逐文件` 不抬高这条线**。
2. **在 `base = 99,998` 的当下，单次删 1 项即 `99,998 + 1 = 99,999 ≥ T` ⇒ 立刻被拒** ⇒
   逐文件**连"删第一项"都过不去**，与"批量删"**同样失败**（他实测 `targetCount: 1` 即此类）。
3. ★ **更糟的是它改变了失败形态**：当 `base < T` 但 `base + 269 ≥ T` 时 ——
   批量删除是**一次原子拒绝**（夹具**原封不动**，下回合可原样重试）；
   而**逐文件会先删掉前 `T − base − 1` 项、然后开始被拒** ⇒
   **夹具留在"半清空"状态**，而 `pytest` 只看见一个 `E`。
   ⇒ 这**正是我在 §15 命名的「静默变空」家族的第四种形态**：
   **"清了一半"与"清干净了"观测上无法区分**，且下一条用例会拿到一个**脏且残缺**的夹具
   （比"完全没清"**更容易**造出假绿/假红）。
   ⇒ **`ws-degrade-contract` 的判词成立，而且比他说的更强**：不只是"救不了本回合"，
   而是**按实测机制它救不了任何回合，还会带来新风险**。
4. ⇒ **13-F / 13-M 的验收判据必须改**（我完全同意他那句「"逐子项"这个词不能当验收判据」）：
   至少写成 **「单次删除目标体量 ≤ 1」+「`base < T` 时一次会话可全程跑完」**；
   我再补一条**防形态退化**的：**「部分删除之后必须响亮失败、且夹具状态可判定」** ——
   否则上面第 3 条的**静默半清空**会**通过验收却不被发现问题**。

**五、一条建设性出路（有实测支撑，且不是"逐文件"）**
`/tmp` 走**独立低基数桶**（`4334`）且**不受该守卫拦**（他实测；我 §17.5 的探针也是这个桶）⇒
**把夹具的工作目录放到系统临时目录（`tempfile.mkdtemp()` / pytest `tmp_path`）**，则：
1. 删除落在低桶 ⇒ **本会话可全程跑完**（不必等下一回合、不必求授权）；
2. 顺带缓解"残留清不掉"（低桶离阈值远）；
3. **反例证据就是我自己**：§17.5 的直连探针在 `/tmp` 下**完整跑完 A–F**，
   而**同一回合**仓库内的整文件回归是 `27 E`。
★ 这**不是**我越界去改 `conftest`（那是 13-F 的面）—— 我只给一条**有实测支撑的备选方向**，供 team-lead 在 13-F/13-M 裁决时取舍。
★ 同时说清**代价**：夹具若落到 `/tmp`，会失去"仓库内可追溯、被 `.gitignore` 管理"的性质 ⇒
**这是设计取舍，不是纯收益**，必须由主理人裁。

**六、边界（如实）**
1. 本节**没有做任何新实验**（本回合仓库内连删 1 项都被拒 ⇒ 实验**做不了**），全部是**对已发布报文的重算**，无新读数。
2. `base` 究竟是「恒定的桶体量」还是「本回合累计成功删除量」—— **本次数据不足以判定**；
   但**两种模型对"逐文件能否抬高总量"都答「否」**（第四段第 1 条与模型无关）⇒ **结论不受影响**，机制描述仍待钉。
3. 我**没有**引用他作废的那三条"成功"读数；**未使用任何绕过手段**。

### §17.12 ★ 更正 §17.9 的**合并对象**（我把它写成了早 40 秒的那个 commit）+ 「`main..branch` 不能判合并」的方法论

**一、我的错：§17.9 写的"`main` = `53de9a3`"不是那次合并的对象**

硬证（命令 + 输出，不是推断）：
```
$ git rev-list --parents -n1 da8254e
da8254e… 681f696… ea0ceae0dbef33b85596deaebbb0e419574b2234
                          ↑ 第二父 = 我那次 merge 真正并进来的 main tip
$ git show -s --format='%h %ci %s' 53de9a3 ea0ceae
53de9a3  2026-09-16 22:40:09  merge ws/step56-skipped（口径 11 补合）
ea0ceae  2026-09-16 22:40:49  merge ws/verify-shard（口径 11 补合）—— …
$ git merge-base --is-ancestor 53de9a3 ea0ceae  → YES（53de9a3 更早）
```
⇒ **`53de9a3`(22:40:09) → `ea0ceae`(22:40:49)**，而我那次合并的对象是**后者**。

**根因（口径 10 的典型违反，且是"同类第 N 例"）**：`53de9a3` 是我在**本会话开头**读到的
主仓 `HEAD -> main`；我在写 §17.9 时把它当成了"**合并时的** main"，而**合并发生时 main 已前进到 `ea0ceae`**。
⇒ **"较早时刻的读数" ≠ "操作发生时的对象"** —— 这与 team-lead 在 `28e1eff` 里自我更正的
「广播写的时刻未核」**同族**（他也在册）。
★ 另一个可乘之机：本仓同时存在 `refs/remotes/tmp/main = 53de9a3` ⇒
**报"`main` 在哪"必须写 ref 全名 + 取值时刻**，否则同名 ref 会互相冒充（这条我加进自己的检查清单）。

**影响面（说清哪些结论会变、哪些不变）**：
- **变**：§17.9 里"我合进来的 main 头"这个**标签**，应为 **`ea0ceae`**；
- **不变**（这些都以 `da8254e` 这个提交本身为准，与标签无关）：幽灵门禁闭合、
  `f5dbc6f..53de9a3` 那 8 个提交的区间、`git stash`/`pop` 后的逐字 blob 比对、
  合并零冲突（`ort`，**11 files changed, +1234/−107**）、`system/rules/*.yaml` 仍 `0444`。

**二、本轮又一次合并（把我这棵树推到最新）**：`1e1a197`，两父 = `fc76c23`（我）+ `261f8c9`（`main`）
```
 system/reports/batch13_taskbook.md                | 140 +++++
 system/reports/phase1_gap_register.md             | 121 +++++
 system/reports/ws_audit_quota11_recheck_report.md | 246 ++++++（新文件）
 system/reports/ws_independent_audit_batch11.md    |  10 +
 system/scripts/ops/verify.py                      |  21 +
 5 files changed, 538 insertions(+)
```
复验：我的两个 blob **逐字不变**（报告 `b719c585e7b4…`（2225 行）、测试 `d7977a94f7c9…`）、
工作区与提交一致、`system/rules/*.yaml` 仍 `-r--r--r--`、`git status` 干净。

**三、★ 方法论更正：`git diff main..branch` 判不出"合并会不会回退 main"**

`ws-step56-skipped` 在卡 `#82` 里用 `git diff --numstat main..ws/ch2-rules` 判我的分支是"陈旧形态"，
并据此说我的分支"**要删掉 `main` 已有的内容**"（`taskbook 0/77`、`gap_register 0/55`、`audit_batch11 0/4`）。
**这条对我的分支是假阳性**，原因在基准：

| 命令 | 含义 | 能不能判"合并会做什么" |
|---|---|---|
| `git diff main..branch` | **tip-to-tip**：两个末端快照的差 | ❌ **不能** —— 它**不携带 merge-base 语义** |
| `git diff $(git merge-base main branch)..branch` | 我方**相对共同祖先**改了什么 | ✅ 能（这才决定合并的"我方改动面"） |
| `git merge-tree --write-tree branch main` | 干跑，给出结果树/冲突 | ✅ 能（最直接） |

**实测反证（同一件事的两种读法，符号相反）**：
- 他的读法：`main..ws/ch2-rules` ⇒ `taskbook` **`0 +, 77 −`**（像"我要删 77 行"）；
- 真实的合并（上面 `1e1a197` 的 diffstat）⇒ `taskbook` **`+140`**（**纯加**，一行不删）。
⇒ 我的分支相对 merge-base 只改了**两个文件**（`git diff --name-status $(git merge-base HEAD main) HEAD`
⇒ `M` 报告、`M` 测试文件，**仅此两项**）⇒ **合并只会带上我的改动，不会回退 `main` 的任何内容**。
★ 这与 team-lead 已入册的「`口径 11` 扩展之二：**禁用三点 `main...branch`**」**同源** ——
两点号 `main..branch` 与三点号 `main...branch` **都不**表达 merge-base 语义；
**只有显式写出 merge-base（或 `merge-tree` 干跑）才算证据**。

**四、边界（如实）**
1. 我**没有**去核 `ws/fixture-cost` 那条"口径 11 第 2 形态"是否也是假阳性 —— 那要用正确命令重算、
   且**不属我单内**。我只报"**方法要换**"，**不下**它成立与否的判词。
2. `ws-step56-skipped` 引用的时点是 `main@28e1eff`，而 `main` 现已到 `261f8c9` ⇒ 他那些数字**按 `口径 10` 也已过期**
   （我这次实测的 tip-to-tip 是 `taskbook 0/140`、`gap_register 0/55`、`audit_batch11 0/10`）。
3. 他提醒的两条**我采纳**：`git merge main` 现在能过门禁（实测第二次合并同样零冲突）；
   若合并把 `rules/*.yaml` 带回 `0644` 就 `chmod 444`（本次**未**发生：合并面不含 `system/rules/**`）。
   ★ 他附的 zsh 提醒（`*.yml` 混进 glob ⇒ `no matches found` ⇒ **整条 chmod 静默不执行**）与 team-lead 的 `723321d` 同源，我已在 §17.9 第 ④ 条踩过同类（`&&` 短路）。

**五、本单内容已被主干采纳（收获，非我功）**：`main` 上
`f819bab`（采纳 merge-tree 干跑手法 + 更正 `76a2d5b`→`76ec851` + 精确化逐文件删除的作用域）、
`261f8c9`（★ 撤回「逐文件删除」方向 + 三条验收判据 + `targetCount` 语义）、
`28e1eff`（`口径 11` 扩展之三 + `口径 16`）、`3e644a2`（`G-61` 第二种形态）—— 即 §17.9/§17.10/§17.11 的结论已落主干。

---

### §17.13 卡 13-O（钩子同源化）收口 + ★ **一处对我自己的事实更正（`grep \|` 的根因我归错了）**

**对象（`口径 10`）**：本树 `ws/ch2-rules`；`HEAD = ab2629b`（`54a7885` + `ab2629b`），树干净，
`system/rules/*.yaml` 仍 `-r--r--r--`；**`refs/heads/main = 5b9bdc3`（2026-09-16 23:09:19）**，
且 `git merge-base --is-ancestor main HEAD` **为假** ⇒ 本树**尚未**含 `5b9bdc3`。

**一、交付（本卡的报告-of-record 是专门的设计短文，不在本节重复）**

`system/reports/ws_hook_same_source_design.md`：§1 现象三份现场/两条流 · §2 根因两行代码 ·
§3 为什么"每次 merge"不是解 · §4 目标 T1–T4 · §5 候选 A/B/C/D + **否决 B 的原理性理由**
（"一棵树只能被它自己的规则判"）· §6 方向②处置 · §7 风险/共享影响/回滚 · §8 反例 + E0–E5 实测 ·
§9 状态与待批 · §10 边界。

代码：`install_hooks.sh`（薄壳单一真源 + `--print`/`--check` + 自动备份 + `--git-common-dir`）、
`pre-commit.sh`（输入预检 + `rc=2`/`rc=1` 分流 + 收尾 `exit 2`）、
`tests/guards/test_hook_same_source.py`（4 例，`--noconftest` 零夹具，`4 passed in 2.77s`）。

**★ 本卡最关键的一步是 §8.4**：前面所有验证都**没有**回答"薄壳在**真钩子**里（`GIT_DIR` 已被 git 导出）
解析出的根，是否就是发起提交的那棵树"。实测两条路径（**只读 `rev-parse`，未跑门禁、未改文件、未装钩子**）：

| 场景 | 注入环境 | 解析出的 `root` | 结论 |
|---|---|---|---|
| linked worktree | `GIT_DIR=.git/worktrees/ws-ch2-rules` | `…/.worktrees/ws-ch2-rules` | ✅ 同源成立（**不是**主仓根） |
| 主仓 | `GIT_DIR=.git` | `/Users/gaza/Developer/InvestSigh` | ✅ 行为不变（== 旧钩子写死的那个根） |

⇒ **旧钩子为什么必错**：它把第一行的 `root` **硬写成**第二行 —— **两棵树被同一个常量抹平**。

**二、★★ 事实更正：`grep 'a\|b'` 返回空，根因**不是** BSD grep（我此前归错了，且我已在别处引用过）**

我在本批次里两次把 `grep -n 'x\|y' <file>` 返回空归因为「**BSD/macOS `grep` 不支持 BRE 交替**」，
并按此形成纪律。`main` 的 `5b9bdc3` 标题更正为「**broker 包装器，非 BSD BRE**」。**我现场复测，结论站在 `5b9bdc3` 一边，我错了**：

```
$ command -v grep
/Applications/WorkBuddy.app/…/cli/vendor/shim/brokered-bin/grep
$ ls -l "$(command -v grep)"
…/brokered-bin/grep -> codebuddy-toybox-dispatch          ← ★ PATH 上的 grep 是**broker 的 toybox 派发器**
$ grep --version | head -1
toybox 0.8.13 (is not GNU grep 9.0)                       ← ★ 括号里那句就是包装器加的

$ grep -n 'alpha\|beta' /tmp/greptest.txt   → 空 · exit=1   ← 走 PATH ⇒ toybox ⇒ 不支持 \|
$ /usr/bin/grep --version | head -1
grep (BSD grep, GNU compatible) 2.6.0-FreeBSD
$ /usr/bin/grep -n 'alpha\|beta' /tmp/greptest.txt
1:alpha
2:beta                                                     ← ★ 真 BSD grep **支持** \| · exit=0
$ grep -nE 'alpha|beta' /tmp/greptest.txt   → 两行都中 · exit=0  ← -E 在两边都可用
```

**更正后的正确表述**：不是"BSD grep 不支持 `\|`"，而是
「**本环境的 `grep` 是动态派发：PATH 上是被 broker 影子化的 toybox 派发器（不支持 `\|`），
而 `/usr/bin/grep` 是真 BSD grep（支持 `\|`）**」。
⇒ 纪律**不变但理由要改**：**一律 `grep -E`（两边都可用）或用 Grep 工具**；
★ 新增一条更狠的推论：**凡在脚本里写裸 `grep`，其行为取决于"谁的 PATH"** ——
门禁脚本、钩子、pytest 子进程可能各自解析到**不同的 `grep`**。这是一个**环境依赖的静默分支**，
与 `G-61`/`G-62` 同族（**用"不携带我们要问的那个语义"的载体去回答那个语义问题**）。
**我未去全仓搜裸 `grep '…\|…'` 的调用点**（不属本卡），如实登记，只报"理由改了"。
★ 这条同时是 `口径 10` 的一次自救：我原先把**当时的读数**（空）配上了一个**未验证的归因**（BSD）——
**"现象为真"不等于"归因为真"**，与 §17.12 的"较早时刻的标签 ≠ 操作时的对象"是同一类毛病。

**三、本树与 `main` 的门禁面差异（自查答案：**暂时无差**）**

```
本树门禁数 = 14 · main 门禁数 = 14 · 逐条门禁名 diff **为空**
```
⇒ `5b9bdc3` 未新增门禁 ⇒ **本树此刻不会撞幽灵门禁**。
★ 但这只是**此刻**的读数（`口径 10`/`口径 9`）：**一旦 `main` 再加一道门禁，本树立刻会撞** ——
这正是 13-O 要治的病，也是它必须被安装（而非"每次 merge 一下"）的理由。

**四、边界（如实）**
1. **共享钩子未安装**：`.git/hooks/pre-commit` 仍是旧版（138 字节、mtime `00:13`）——
   全 34 人共享，改坏则全体无法提交 ⇒ 我**一个字都没动**，已请 team-lead 的 go。**未用 `--no-verify`。**
2. 方向②（判据旧于对象）**仍未实测** ⇒ 按 `G-03` 不计为已验证。
3. 本节所有读数：**无耗时、无配额**（`口径 21`：本卡不含任何跑批测量）。

---

### §17.14 ★★ 四套 `grep` 方言的**静默零**矩阵（复核 `ws-criterion-effectiveness` 的地面真值矩阵 + 我补的三格）

`ws-criterion-effectiveness` 广播了"更正自己的规则：`\.`／`\{` 没失效，只有 GNU 扩展运算符失效"并附真值矩阵。
他**主动收窄**是对的（他先前把 `\.`/`\{` 也归为失效）。我**独立复核**了他的矩阵，**确认他的每一格**，
并补齐**他没测的三格**。受控输入 `/tmp/ge-probe2/m.txt` = `aab / ab / a.b / aa / zz`，
地板真值 = **Python `re`**（每格都有真值列，不靠推断），取样 2026-09-16 23:2x。

| 写法 | 真值 | 裸 `grep`（toybox 派发器） | `grep -E`（toybox） | **Grep 工具**（ripgrep） | `/usr/bin/grep`（BSD 2.6.0, GNU compatible） |
|---|---|---|---|---|---|
| `a\|b` 交替 | 4 | **0 ★静默** | 4 ✓（**须去掉反斜杠**） | **0 ★静默** | 4 ✓ |
| `a\+b` | 2 | **0 ★静默** | 2 ✓ | — | 2 ✓ |
| `a\?b` | 3 | **0 ★静默** | 3 ✓ | — | 3 ✓ |
| `\<ab\>` 词边界 | 1 | **0 ★静默** | **0 ★静默**（他没测这格） | — | 1 ✓ |
| `a\.b` 字面点 | 1 | 1 ✓ | 1 ✓ | — | 1 ✓ |
| `a\{2\}b` | 1 | 1 ✓ | **0 ★静默**（他没测这格） | — | 1 ✓ |
| `a\{1,2\}b` | 2 | 2 ✓ | **0 ★静默**（他没测这格） | — | 2 ✓ |
| `\(a\)\1` 反向引用 | 2 | 2 ✓ | **0 ★静默** | **0 ★静默** | 2 ✓ |
| `\-w ab` / `[[:<:]]ab[[:>:]]` | 1 | 1 ✓ | 1 ✓ | — | 1 ✓ |

**★ 结论一：他"仅 GNU 扩展运算符失效"的收窄成立** —— 裸 `grep`（toybox）缺的是 `\|` `\+` `\?` `\<` `\>`；
POSIX BRE 自身的 `\.` `\{n\}` `\{n,m\}` `\(\)` `\1` **全部正常**（我 8 格逐格复现）。
**★ 结论二（我补的，且是一条真陷阱）：`-E` 不是可机械套用的替换。** 我测到两格**他没测的静默零**：
`grep -E '\<ab\>'` → **0**；`grep -E 'a\{2\}b'` → **0**、`grep -E 'a\{1,2\}b'` → **0**
（ERE 的区间语法**没有反斜杠** ⇒ 原样搬过去变成字面 `{2}`）。
⇒ **正确规则：改 `-E` 必须把该 pattern 里"全部" GNU-BRE 转义一次性翻完；只翻一半 = 静默 0。**
**★ 结论三（我补的，推翻他的一句）：他推荐的"默认首选 Grep 工具（内置 ripgrep，上述扩展全支持，**无方言问题**）"不成立。**
实测（Grep 工具、同一文件、同一行可被普通模式正常命中）：`(a)\1` → **No matches found**（真值 2）；
`a\|b` → **No matches found**（真值 4）。⇒ **ripgrep 是另一套方言，有它自己的静默零**
（把 `\|` 当字面竖线、不支持 `\1`）。**"无方言问题"是错的。**
**★ 结论四（他说对了、我实测更硬）：唯一 8/8 全对的是 `/usr/bin/grep`**（BSD grep 2.6.0-FreeBSD, GNU compatible）。
⇒ 修正后的操作口径：要"绝对不出静默零"，首选 **`/usr/bin/grep`**；其次 `-E`（前提是把反斜杠**全**翻完）；
裸 `grep` 只在**严格 POSIX BRE** 范围内可信；**Grep 工具不是超集**。

#### 17.14.1 ★ 他的推荐写法**本身带着它要防的那个陷阱**（同一封里复现）

他把 `\|` 的替代写成 **`grep -E 'a\|z'`（保留了反斜杠）**。我实测：`grep -E 'a\|b'` → **0 / rc=1**（toybox 与 BSD **都是 0**）；
只有 `grep -E 'a|b'`（**去掉反斜杠**）→ 4 = 真值。而他那一格记的读数 **5** 恰好等于**无反斜杠**版本
（`a|z` 匹配 5 行）⇒ 可判定为**转写笔误**（`\|` 应为 `|`），**但后果是"照抄必踩"**：
**这封以"零命中不许进结论"为教训的更正信里，替换写法那一行本身就是一条静默零。**

#### 17.14.2 ★ 我自己的仪器错（如实，且是同一族的第 4 例）

我的第一版探针用 `grep -c` 拿结果，却**去数 `stdout` 的行数** —— 而 `-c` 输出的是**一个数字**，
⇒ **每一格都变成 `1`**，屏幕上看起来像"**所有写法都匹配**"。这正是 `G-62`：
**用"不携带该语义的载体（行数）"去回答"匹配了几行"**。修法是**解析整数**（`int(stdout)`）。
★ 与 §17.13 同源：**现象为真 ≠ 归因为真**；本次是**现象本身就是仪器造的**。

#### 17.14.3 最上位的那条纪律（双方结论一致，我并入自己的检查清单）

**任何"零命中"在下结论前必须先做三候选区分实验**：①真没有 ②语法/方言不支持 ③路径或参数错。
⇒ 并且 **广播/报告里每一格都必须带"地板真值列"，没有真值的格子不许进结论**。

---

### §17.15 ★★ 独立复核 `auditor-batch11` 的 `G-64`：**确认，并把它推进了两层**（`gap_to_task` 的豁免谓词）

对象（`口径 10`）：本树 `ws/ch2-rules`；本节**期间 `main` 移动了三次**，逐次留痕：
`98d0c32`（23:17:44，落 `V-10`/`V-11`）→ `3653c7c`（23:21:44，E 第三道闸门）→ `439e8d0`（23:23:24）；
我已 merge 到 **`4fed1ac`**（含 `98d0c32` 与 `3653c7c` 两次合并，零冲突）。
★ 取样 **2026-09-16 23:4x**。★ **`main` 的取值时刻必须随读数一起报**（`V-11`）——
本节正是"`main` 在一条 5 分钟的工作窗口里前进 3 次"的现场，**这也正是卡 13-O 要治的病**。
仪器：`/tmp/g64_probe2.py`（**每态一个全新 root**；`/tmp` 为独立低桶 ⇒ **零仓库写入、零删除配额**）。
全部行由**唯一写入方** `Pipeline._write_check_record` 产出，**不手工拼行**（`G-06`）。

#### 17.15.1 四态实测（`gap_to_task.py` 的 exit）

| 态 | `check_record.changed` | `check_record.degraded` | `last_valid_result_ref` | `output_refs` | **exit** | 应然 |
|---|---|---|---|---|---|---|
| **A** 无变化日 | `False` | `False` | `None` | `[]` | **0** ✅ | 0（设计合法） |
| **B** 降级（此前有成功） | `True` | `True` | `check_2026-09-16_full` | `[]` | **1** ❌ | 0 |
| **B2** 降级（此前**无**成功） | `True` | `True` | **`None`** | `[]` | **1** ❌ | 0 |
| **C** 真违规（有变化、未降级） | `True` | `False` | `None` | `[]` | **1** ✅ | 1 |

★★ 这**确认**了他的两条核心断言：① 降级行被误判空执行（`B`/`B2` 都是**假红**）；
② `A` 与 `C` 的对照正常 ⇒ **不是判据整体坏了，是"降级"这一态在豁免谓词里没有表达**。

#### 17.15.2 ★ 我补的第一条（**决定修法该 predicate 谁**）：`B2` 与 `C` **在行上字段逐一相同**

```
B2-降级(此前无成功)   degraded=True   last_valid_result_ref=None   changed=True   output_refs=[]   exit=1
C -真违规(未降级)     degraded=False  last_valid_result_ref=None   changed=True   output_refs=[]   exit=1
                      ↑ 唯一差异    ↑ 相同        ↑ 相同            ↑ 相同          ↑ 相同
```

⇒ **`check_record.degraded` 是唯一能把"降级"与"真违规"分开的字段。**
⇒ ★ 由此**排除一个看似合理、实际不可用的候选修法**：
把谓词写成 `last_valid_result_ref is not None` **不行** —— `B2`（降级且此前无成功运行）该字段为 **`None`**，
用它做豁免**会漏掉 `B2`**，把假红从 `B` 挪到 `B2`（**换个字段复发**，正是本仓 `G-43` 的形状）。
⇒ **他的修法（`changed is False` **或** `degraded is True`）经此检查是正确的那一支。**

#### 17.15.3 ★ 我补的第二条（层判断）：**状态映射不是缺陷，别改错了层**

`pipeline.py:412`：`status=TaskStatus.failed if result.blocked else TaskStatus.done`
—— **`degraded` 不参与状态判定**（只有 `blocked` 才 `failed`）。
而 `TaskStatus`（`schema/models.py:240`）是 **`Ch1 §C.3` 的五态**（`queued/researching/pending_evidence/done/failed`），
**没有 degraded 槽位**。

⇒ **"降级行却标 `done`"不是本缺陷的根因**：在五态机里 `degraded → done` 是**唯一可选映射**，
   降级只能由 `check_record.degraded`（+ `last_valid_result_ref`）表达。
⇒ 因此**改状态映射 = 改设计**（要加第六态），**不属本卡**；本缺陷在**谓词层**。他定位的层是对的。

#### 17.15.4 ★★ 我补的第三条（**根因再上一层**）：这是 **`G-06` 单一真源违反**

```
$ /usr/bin/grep -nE 'degrade|holds_valid_result|is_valid_run_record' system/scripts/tasks/gap_to_task.py
（零命中）
```
⇒ `gap_to_task.py` **完全不引用** `scripts/daily/degrade.py`。两个模块**各自**回答"这一行算不算一次合法运行"：

| 模块 | 谓词 | **看哪个字段** |
|---|---|---|
| `tasks/gap_to_task.py:54` | `is_no_change_day()` | **`check_record.changed is False`** |
| `daily/degrade.py:98` | `is_valid_run_record()` | **`status != "failed"` 且 `not check_record.degraded`** ← ★ **它看 `degraded`！** |

⇒ ★★ **正确的那半已经存在**（`degrade.py:98`），只是**豁免谓词没有复用它**。
`degrade.py:95` 的 docstring 还自称是首日豁免判定的「**唯一真源**」——
于是"唯一真源"与"另一个同题谓词"**对同一行给出相反结论**：
`B2` 在 `is_valid_run_record()` 下 `degraded=True` ⇒ 判为"不是一次成功运行"（对），
在 `is_no_change_day()` 下却因为只读 `changed` ⇒ 判为"空执行"（错）。

⇒ **修法建议（比"加一个 `or`"更根本）**：`is_no_change_day()` 应**从 `degrade` 的真源派生**
（复用同一份"降级/失败"语义），而**不是**再加第 4 个同族局部谓词；并按他的建议**分列计数**。
★ 我给"分列计数"补一条**硬证据**：当前单一计数器下，**`B2` 与 `C` 都记 `no_change_day_exempt=0`**
（实测）⇒ 一个**合法态**与一个**违规态**在读数上**完全合并**。

#### 17.15.5 ★ 我补的第四条（顺带，属他的 `G-63`）：**同一个引用完整性缺口有第二个落点**

他报 `stage_gate.py:600` 只判 `last_valid_result_ref` 的**真值性**。我实测（1 行、零夹具）同一个缺口
**也落在 `daily/degrade.py:130`（`holds_valid_result()` 的载体 ①）**：

```
failed 行 + last_valid_result_ref = …        holds_valid_result
None                                          False
''                                            False
'garbage'                                     True   ← ★
'self'                                        True   ← ★
'check_不存在'                                 True   ← ★
```

⇒ **`G-63` 至少两个落点，不是一个**；且第二个落点更重 —— 它所在的函数自称「**唯一真源**」。
   （★ 口径：本格是**实测**，但**只证明谓词可被垃圾字符串穿过**；我**未**验证"生产数据里会出现这种行"
   —— 唯一写入方填的是真 `check_id`。按 `G-03`，**可达性未证**，如实标注。）

#### 17.15.6 ★ 我自己在本节的两次失误（如实）

1. **探针污染**：`v1` 让四态**共用同一个 root** ⇒ `B` 的 `last_valid_result_ref` 指向了 `A` 那一行，
   看起来像"降级行的引用被正确填了" ⇒ **假证据**。改成**每态一个全新 root** 后 `B2` 才暴露
   （此前无成功 ⇒ `None`），**而这一格恰恰是决定修法的那一格**。
   ⇒ 又一次 `G-62`：**用被前一态污染过的现场，去回答"这一态是什么"**。
2. **`\|` 再犯**：本轮我在主仓 `CONVENTIONS.md` 里查 `V-10`/`V-11` 时写了
   `grep -n 'V-10\|V-11'` ⇒ **toybox 静默零** ⇒ 我一度得出"我的树里没有 V-10"的**错误结论**，
   直到 `git grep` 把它找出来。**`V-10` 落地不到 10 分钟，我就是第 1 个中招者**
   （它自己那段"5 处报告写错根因 / 多人多次中招"的代价表，现在应当 +1）。
3. ★ **我差点误读一次"合并方向"**：我用 `git diff --name-status HEAD main` 看到
   `M system/scripts/ops/pre-commit.sh`、`M install_hooks.sh`，第一反应是"**main 也改了这两个文件**"。
   实际上 `3653c7c` 只动了 6 个文件、**不含**这两个 ⇒ 那个 `M` **完全是"我方有改动"造成的**，
   **不是"对方改了"**。
   ⇒ **tip-to-tip 差分的每一行都不携带"谁改的"方向信息** —— 这正是 `口径 11 扩展之四`
   （`main..b` 判不出合并会做什么）的**孪生形态**：连"**差异归属谁**"它也答不了。
   我在落纸前用 `git show main --stat` 复核了，**未把误读写进本节**（如实登记这次自查）。
4. ★★ **第四次，而且这次污染了产物本身**：我用 `git commit -m "…"` 提交本节，
   消息里含反引号（`` `degraded is True` `` 等 **4 处**）⇒ **shell 把它们当命令替换执行**：
   ```
   (eval):1: command not found: degraded
   (eval):1: command not found: last_valid_result_ref
   (eval):1: command not found: failed
   (eval):1: command not found: or
   ```
   ⇒ 于是提交信息里出现 4 处**语义空缺**：`⇒ 修法**必须** predicate ；`、
   `⇒ **排除**候选 ：`、`pipeline.py:412  ⇒ …`、`⇒ 修法不能只加一个 （…）`
   —— 而**屏幕上看不出**（行仍然"读得通"）。
   ★ 与我早前在 `pre-commit.sh` 里踩过的**完全同型**（当时是 `echo` 里的反引号，
   `line 161: G-61: command not found` 且那个词被静默吞掉），**我今天在 `git commit -m` 上再犯**。
   ⇒ **纪律：提交信息一律 `git -F <file>`（或 `-m` 里零反引号/零 `$()`）**；
     我当天给 13-O 那条长信息用的就是 `-F`（**同一手法，一处做对一处做错**）。
   ★ 处置：该提交**未被任何其他 ref 引用**（`git show-ref` 只列本分支）⇒ 用 `-F` 重写其信息，
     **未用 `--no-verify`、未改任何文件内容以求脱身**。

---

### §17.16 卡 `#95` 实现：`G-64` 收口（谓词**从真源派生** + 分列计数 + 8 条可判红反例）

#### 17.16.1 对象与取样钉死（`口径 10` / `口径 9`）

| 项 | 值 |
|---|---|
| 实施树（对象） | `/Users/gaza/Developer/InvestSigh/.worktrees/ws-ch2-rules` @ 分支 `ws/ch2-rules`，改动前 HEAD = `3a43098` |
| 取样时刻 | 2026-09-16 深夜 CST |
| 被测脚本 | `system/scripts/tasks/gap_to_task.py`、`system/scripts/daily/degrade.py` |
| 被检真源 | `facts/tasks.jsonl`（**行全部由唯一写入方 `Pipeline._write_check_record` 产出**，不手工拼） |
| 门禁读数所属树 | 上述工作树（**不是**主仓）；主仓读数另标 |

★ 本轮**未**用 `git diff main..` 之类 tip-to-tip 判"main 改了什么"（`口径 11 扩展之四`）：
  凡涉及"谁改的"一律回落到 `git log HEAD..main -- <path>` 与 `git diff HEAD main -- <path>`
  的**逐文件**读法（见 §17.16.7 第 3 条，我本轮又差点误读一次）。

#### 17.16.2 改了什么（**三处**，且刻意**不是**"只加一个 `or`"）

| # | 文件 | 改动 | 为什么这样改 |
|---|---|---|---|
| ① | `scripts/daily/degrade.py` | **新增**行级原语 `is_degraded_run_record(row)`（`check_record` 存在 且 `degraded is True`，**严格同一性**）；并抽出共用的 `_check_record(row)`（取 `check_record` 且必须是 `Mapping`），`is_valid_run_record()` 改为经它取记录（**行为逐字不变**） | 卡的第 2 条不许"只加一个 `or degraded`"：`G-64` 的根因是 `gap_to_task.py` 对 `degrade.py` **零引用**，"降级"这件事两个模块各有一套局部口径。新原语放在**真源模块**，供全局复用 |
| ② | `scripts/tasks/gap_to_task.py` | **import** 上述真源；新增薄派生 `is_degraded_empty_output(row)`（**函数体内零字段读取**，整条 `return is_degraded_run_record(row)`）；`check()` 改为 **`degraded` 优先的 if/elif/else**，并新增 `degraded_empty_output` / `empty_output_violations` 两列 | 把"合法空产出"从**一支**改成**两支**；分列计数治 `G-62`（合法态与违规态读数等价） |
| ③ | `tests/daily/test_no_change_day.py` | 原 **12** 例 → **20** 例（+8）；`_rec()` 增 `degraded` 形参 | 补正例 B/B2、严格性反例 3 条、同源绑定 1 条、计数闭合 1 条、归类优先级 1 条 |

★ **为什么 `is_degraded_empty_output()` 不算"第 4 个同族局部谓词"**（这是本节最容易被质疑的一点，
  故先答）：它**不读任何字段** —— 判据整条在真源里，本函数只做"降级轮 ⇒ 空产出合法"这一步语义命名。
  可判定的证据不是我的措辞，而是测试
  `test_degraded_predicate_is_derived_from_truth_source`：在 `degraded ∈ {True, False, None, 1, 0,
  "true", "false"}` × `changed` × `status` 的**全矩阵**上断言
  `is_degraded_empty_output(row) is is_degraded_run_record(row)` —— 后人把它改成第二套判据就会当场红。

#### 17.16.3 五态实测（**修前 → 修后**）—— `B2 ≡ C` 是决定修法的那一格

每态**一个全新 root**（不复用 —— 上一轮我正是在这里踩过"探针污染"）。行字段取自真源文本。

| 态 | `changed` | `degraded` | `last_valid_result_ref` | 实义 | 修前 `exit` | 修后 `exit` |
|---|---|---|---|---|---|---|
| A | False | False | `None` | 无变化日（合法） | `0` | `0` |
| B | True | True | `check_2026-09-16_full` | 降级 + 有上次成功（合法） | **`1` 假红** | `0` |
| **B2** | True | **True** | **`None`** | 降级 + 此前**无**成功运行（合法） | **`1` 假红** | `0` |
| **C** | True | **False** | **`None`** | **真违规**（空执行） | `1` | `1` |
| D | False | True | `None` | 两态重叠（合法） | `0` | `0` |

★★ **`B2` 与 `C` 的差异只有 `degraded` 一格**（`status='done'` / `output_refs=[]` /
`last_valid_result_ref=None` / `changed=True` 全同）⇒ 这把卡上"必须 predicate `degraded is True`、
**排除** `last_valid_result_ref is not None`"的论证从**推断**变成**实测**：后者会漏掉 B2，
假红只是从 B 挪到 B2（**换个字段复发**，`G-43` 的形状）。E4 反例把这条钉住了（见 17.16.4）。

★ `D` 那一行不是装饰：它证明"降级优先"的归类是**可判定的**（否则 `changed=False` 与
`degraded=True` 同时成立时归类悬空 ⇒ 计数闭合性无法判定）。

#### 17.16.4 可判红反例：`E0`–`E5`（每个实验都"一行打回"，用完**无条件还原**）

探针 `/tmp/g64_killtest.py`：备份 → 改一行 → 跑用例 → **`finally` 还原并逐字断言还原成功** → 打印。
判据是"**期望 exit≠0**"：若某个反例在"打回"后仍绿，它就没有判别力（`G-03`）。

| 实验 | 打回成什么 | 结果 | 判定 |
|---|---|---|---|
| `E0` | 不改 | `20 passed` | 基线 |
| `E1` | `is_degraded_empty_output` 恒 `False`（= **修前行为**：只认无变化日一支） | `exit=1`，**4 failed** / 16 deselected | ✅ |
| `E2` | `degrade.is_degraded_run_record` 恒 `False`（真源被掏空） | `exit=1`，**2 failed** | ✅ |
| `E3` | 真源换成**真值性**写法（`bool(record.get("degraded"))`） | `exit=1`，**1 failed**（`test_degraded_one_does_not_exempt`） | ✅ |
| `E4` | 豁免**换字段**：改用 `last_valid_result_ref is not None` | `exit=1`，**1 failed**（B2 正例） | ✅ |
| `E5` | 去掉 `degraded_empty_output` 这一列（计数不闭合） | `exit=1`，**1 failed** | ✅ |
| `E9` | 全部还原后复跑 | `20 passed` | 现场未留补丁 |

★ `E3` 与 `E4` 是**两个方向的"换字段复发"**：前者是"同一字段的宽松读法"，后者是"换一个字段"。
  这正是卡里"必须严格同一性 + 必须 predicate `degraded`"两条要求的**可执行依据**。

#### 17.16.5 分列计数与**闭合恒等式**

`check()` 现在报四列，并满足（测试 `test_counters_are_exhaustive_over_the_three_classes` 断言）：

```
done_empty_output_rows == no_change_day_exempt + degraded_empty_output + empty_output_violations
```

| 态 | 修前读数 | 修后读数 |
|---|---|---|
| B | `{rows:1, exempt:0}` | `{rows:1, exempt:0, degraded:1, violations:0}` |
| B2 | `{rows:1, exempt:0}` ← **与 C 完全相同** | `{rows:1, exempt:0, degraded:1, violations:0}` |
| C | `{rows:1, exempt:0}` | `{rows:1, exempt:0, degraded:0, violations:1}` |

⇒ 修前 **B2 与 C 在读数上一字不差**（`G-62`：两个不同事实在同一观测通道上等价）；
修后两者由 `degraded` / `violations` 两列分开。★ 三列之和恒等于"形状行数"这一条，
把"某一行被两支重复计数"或"某一行没被任何一支接住"都变成**可判**（不是靠读代码相信）。

#### 17.16.6 ★ **举证半径更正**：卡里对 `Ch8 §E.4` 的引用**过宽**（`V-11`，我自己也照抄过一次）

卡的产物段写：「`Ch8 §E.4` 明令降级时 `output_refs` 必须如实为空」。我逐字核对设计正文后，
**这条不成立**，如实更正如下（`08_产品入口与每日运行/02_实现方案.md`）：

| 行 | 逐字原文 | 它实际规定的是 |
|---|---|---|
| `:312 §E.1` | 「**共同红线**：故障时**保留上次有效结果并清楚显示日期 + 失效状态**；**不覆盖为无意义空值**；**不把旧数据标为最新**」 | 降级三红线（**没有**"output_refs 必须为空"） |
| `:330 §E.2` | 「`degraded` ｜ `check_record`（复用 Ch1 §C.2）｜ **当日降级运行 = true**」 | 字段归属与写入语义 |
| `:346 §E.4` | 标题 = 「"不置 null" / "不标最新" 的**写路径断言设计**」，正文代码为 `assert_no_null_overwrite` / `assert_not_labeled_latest` | **禁止**把字段**覆盖为**空值（是"不得置空"，方向**相反**） |
| `:76 N8.4-06` | 「禁止在降级时把字段**覆盖**为无意义空值」 | 同上 |

⇒ **"降级轮 `output_refs` 必须为空"是本仓写路径的语义取舍，不是设计逐字规定** ——
  这一点的**最早出处不是我的推断**：`reports/ws_degrade_contract_report.md §④-3`
  已经**自己明说**「`output_refs` 在"失败运行"上的语义是**本单的取舍**（非设计逐字规定）」，
  并由 `pipeline.py:391/415`（`valid_run = not (blocked or degraded)`）落地。
  ★ 故本卡的判据与它**同源**：**不新增任何要求**，只是**承认已经落地的写路径契约**，
  从而不再把合法行判成空执行。措辞已按此写进 `gap_to_task.py` 的 docstring（带 ⚠️ 标注）。
  ⇒ 教训与 `V-11` 一致：**引用条款前必须读到那一行**，否则"我引了设计"会给出**比实际更宽**的权威半径。

★ 附带登记一条**未改**的张力（不属本卡、**未验证**，只记账，不静默）：
  `§E.4` 的 `assert_no_null_overwrite(old_row, new_row)` 是**跨行**比较（旧行非空 → 新行空即抛），
  若有人把它施加到 **task 行**的 `output_refs` 上，就会与 `_write_check_record` 的
  "降级轮写空 `output_refs`"**直接冲突**。设计正文的代码样例比较的是**数据对象**的
  `old_row.data_fields`（`stale` 那一族），故当前无实现冲突；但两者**同时存在**这件事本身
  没有机器绑定 ⇒ 如实登记，**未改任何文件**。

#### 17.16.7 边界与未证（如实）

1. **B2 的生产可达性仍未证**（`G-03`）。本轮 B2 由**真实写路径**（`Pipeline._write_check_record`
   ← `RunResult(degraded=True)`）在"该 root 内此前无成功运行"时产出 —— 但"实际调度里会不会出现
   '降级且此前从未成功过'的那一天"**未核**。★ 与 `auditor-batch11` 的差别仅在于证据路径：
   他直接注入 `RunResult`，我经 `conftest.write_check_records`（**同一个唯一写入方**）。
2. **未改状态映射**（按卡的边界）：`pipeline.py:412` 仍把 `degraded → done`（只有 `blocked → failed`），
   而 `TaskStatus` 是 `Ch1 §C.3` 五态、**没有 degraded 槽位** ⇒ 改它 = 改设计，另开卡。
3. ★ **`traceback.py` 这道门禁在本树上"本来就红"**（不是我造成的）：`run_all_gates.py` 27 道里
   26 道 `exit=0`，唯 `traceback.py exit=1`（`G1-03` `rec-nvda-001` 四要素缺 `assumptions`/`computation`）。
   我按 `口径 11 扩展之四` 的教训做了**逐文件**归因，而不是拿 tip-to-tip 差分猜：
   `git log HEAD..main -- scripts/trace/traceback.py`（空）+ `git stash` 后**在原树上复跑**得到
   **完全相同的 2 条违例** ⇒ **继承自 `main`、与本卡无关**。
   （★ 复跑时我先用 `| tail -5` 读它的退出码，那是 `tail` 的 `rc` —— 违反 `口径 17`；
   已改为单独执行取 `rc=1`，见本节末的自查。）
4. **本卡未跑"整仓 29 条回归"**：`G-60` 的删除配额约束下，本轮只跑了**同源面**
   （`tests/daily` 全目录 + `tests/injection/test_wiring_guards.py` = **81 passed**）与
   **14 道 pre-commit 门禁**（全绿）+ **27 道全量门禁**（26 绿 / 1 项继承自 main）。
   跨面全量回归按纪律留给新的回合（不静默：这是**未跑**，不是**跑过**）。
5. 我**未**改动 `stage_gate.py`（`G-63` 的两个落点仍在）—— 那是另一张卡的范围。

#### 17.16.8 我本轮的自查（又一次把"读数"读成"结论"的前一刻停住）

- ★ 我在复跑 `traceback.py` 时写了 `python3 … | tail -5; echo rc=$?` ⇒ 打印的是 **`tail` 的 `rc`**，
  而 `traceback` 的真实 `rc=1` 是**单独执行**才拿到的。这正是 `口径 17`（凡我要读它的结果的命令一律单独执行）
  与 `V-10` 家族的同型错误：**仪器的读数被我当成被检对象的读数**。已在 17.16.7 第 3 条按
  "单独执行得到的 `rc=1`"重述，未把管道读数写进结论。
- ★ 本节的过程里我**第三次**撞上"tip-to-tip 差分不携带归属"：`git diff --name-status HEAD main`
  对 `pre-commit.sh` / `install_hooks.sh` 显示 `M`，而 `git log HEAD..main -- <这两个路径>` **为空**
  ⇒ 差异 100% 来自**我方**（13-O 的改动），**不是** main 改了它们。
  我没有据此得出"main 也动了"的结论，而是先查 `git log` 再落纸。

