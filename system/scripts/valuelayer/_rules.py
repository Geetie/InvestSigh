"""`_rules.py` —— `rules/{baseline,metric-sets}.yaml` 的**唯一读口**（`G-06` 唯一真源）。

## 为什么必须集中成一个模块

`route_guard` / `growth_quality` / `completeness` 三个模块都要读这两份规则文件。
若各自 `yaml.safe_load(root / "rules" / ...)`，就出现了**第二条解析路径** ——
"阈值到底从哪里来的"这个问题会有多个答案，而本项目最忌的正是这种双真源
（`CONVENTIONS.md §二 G-06`；实测教训 `D-20`：每函数重解析 YAML 数千次）。

本模块**只读不判**：任何判定（阈值比较、枚举校验）都留在调用方。

## 两条硬约束（都是刻意的）

1. **走 `scripts/_common._cached_yaml()`**（`CONVENTIONS.md §三 P-02`）——缓存键含
   `mtime_ns` + `size`，故"夹具里改配置再跑检查器"的注入测试**不会**被缓存骗过。
2. **缺文件 / 缺键 / 值非法 ⇒ 响亮失败**（`_common.EXIT_INPUT_ERROR` = 2），
   **不内置任何兜底默认值**。理由（`Ch4 §G.2` / `§J.4 J3` / `Ch11 §D.2`）：
   阈值必须**参数化在 `rules/baseline.yaml` 这唯一真源里**；代码里放一个默认数，
   会让"规则文件里其实没写这个阈值"这件事**变成不可观测** —— 而那正是 `G-03`
   要拦的形态（"没有被检对象 / 没有配置"被当成"已验证"）。

   ★ 与 `Ch4 §D.2` 的"默认 5"不冲突：那个"默认"是**设计给规则文件的值**，
     由 13-R 逐字写进 `rules/baseline.yaml`，**不是**代码里的兜底。
     代码只读键，不猜值。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from scripts._common import _cached_yaml

BASELINE_RELPATH = "rules/baseline.yaml"
METRIC_SETS_RELPATH = "rules/metric-sets.yaml"

#: `rules/baseline.yaml` 里阈值所在的分组名。
#:
#: ★ **为什么有这一层**（`R8-1`，主理人 2026-09-16 裁定，逐字登记在 `rules/baseline.yaml` 头部）：
#:   设计里 `cfg.max_primary_drivers_per_business` 这类写法一律读作
#:   **`baseline["thresholds"]` 分组下的键**；设计里 `rules/baseline.yaml: <key>` 是
#:   `file:key` 记法、**不锁深度**，深度由**已安装的规则文件**填（存量 10 件规则文件 10/10 分组包裹）。
#:   故「代码按本文件实有结构读」—— 本模块就是那唯一的读口。
THRESHOLDS_GROUP = "thresholds"

#: 规则文件里表示「**已声明但未拍板**」的字面量。
#:
#: ★ 与「缺键」**刻意分开**（`G-03`）：
#:   - **缺键** ⇒ 说明这份规则文件**根本没管这件事** ⇒ `MissingRuleInput`（`exit 2`）；
#:   - **`tbd`** ⇒ 说明**管了、但值待需求方拍板**（13-R 的转写纪律：设计未给值 ⇒ `tbd` + `basis`）
#:     ⇒ 该阈值为**不可核**，由调用方按 `G-03` 记「不可核 + 计数 + note」，
#:     既**不得**按一个代码里的默认数放行，也**不得**因此让判据恒红（`G-01`）。
UNDECIDED = "tbd"


def is_undecided(value: Any) -> bool:
    """`null` / `tbd` / 全空白字符串都算「已声明但未拍板」（与 `completeness._is_blank` 同一语义）。"""
    if value is None:
        return True
    return isinstance(value, str) and value.strip().lower() == UNDECIDED


class MissingRuleInput(ValueError):
    """规则文件缺失 / 结构非法 / 阈值键缺失 —— **输入异常**（CLI 折叠为 `exit 2`）。

    ★ 与"命中违例"（`exit 1`）**刻意分开**：前者是"我不知道该按什么标准判"，
      后者是"我知道标准、而对象不达标"。把两者混成一个退出码，会让
      "规则没装好"看起来像"数据不合格"——本项目反复栽在这类假信号上。

    ★ 为什么继承 **`ValueError`**（而不是 `RuntimeError`）：`scripts/_common.run_checker`
      已把 `(FileNotFoundError, ValueError, KeyError, OSError)` 折叠为 `exit 2`。
      继承它即**复用**该唯一出口（`G-06`），不需要在本层再写一条 CLI 异常翻译路径 ——
      实测教训：初版继承 `RuntimeError` 时异常**穿透** `run_checker`，
      进程以 traceback `exit 1` 结束，把"输入异常"伪装成"命中违例"。
    """


class UndecidedThreshold(MissingRuleInput):
    """键**在**、但值为 `tbd`/`null` —— 阈值**已声明未拍板**（`G-03` 的"不可核"）。

    ★ 继承 `MissingRuleInput` 是**刻意的**：对"必须要有值"的调用方（如 `>=` 比较）
      它与"缺键"是**同一件事**——没有可用的阈值，必须响亮失败；
      而对能处理"不可核"的调用方（如 `sections_nonempty` 的"最小字段数"一项），
      另有 `threshold_or_none()` 这条**显式**通路，不靠捕获异常来分流。
      这样两种语义都**可判定**，且没有把 `tbd` 悄悄变成一个数。
    """


def _load_mapping(root: str | Path, relpath: str) -> dict[str, Any]:
    """读一份必须**存在且为 mapping** 的规则 YAML（缺则 `MissingRuleInput`）。"""
    path = Path(root) / relpath
    if not path.exists():
        raise MissingRuleInput(
            f"缺少规则文件 {relpath}（规则真源在 rules/，由主理人安装并重锁；"
            "本层不提供内置默认值）"
        )
    doc = _cached_yaml(path)
    if not isinstance(doc, dict):
        raise MissingRuleInput(f"{relpath} 顶层不是 mapping，实为 {type(doc).__name__}")
    return doc


def baseline_doc(root: str | Path) -> dict[str, Any]:
    """`rules/baseline.yaml` 的**完整文档**（含 `spec_anchor` / `form_completeness` 等非阈值节）。"""
    return _load_mapping(root, BASELINE_RELPATH)


def baseline_cfg(root: str | Path) -> dict[str, Any]:
    """`Ch4 §D.2` / `§G.2` 伪码里的 `cfg` —— 即 `rules/baseline.yaml` 的 **`thresholds` 分组**。

    ★ 深度由 `R8-1` 裁定（见 `THRESHOLDS_GROUP` 的注释）：设计里的 `cfg.<key>` 一律读作
      本分组下的键。初版曾按设计里"扁平写法"直接取顶层键，13-R 安装真文件后**实测**：
      `min_nonnull_rate` 等键在 `thresholds:` 之下 ⇒ 顶层取键会全部报"缺键"，
      把 `chapter4_g_depth` 变成**恒红**（`G-01`）。故此处按**实有结构**读，
      且缺 `thresholds` 分组时**响亮失败**（不猜深度、不摊平规则文件）。
    """
    doc = _load_mapping(root, BASELINE_RELPATH)
    group = doc.get(THRESHOLDS_GROUP)
    if not isinstance(group, dict):
        raise MissingRuleInput(
            f"{BASELINE_RELPATH} 缺 `{THRESHOLDS_GROUP}:` 分组（或它不是 mapping，实为 "
            f"{type(group).__name__}）—— `R8-1` 裁定阈值一律读该分组；"
            "本层不猜深度、也不为迁就扁平写法而改读顶层"
        )
    return dict(group)


def baseline_threshold(root: str | Path, key: str) -> Any:
    """取 `rules/baseline.yaml::thresholds` 的**单个阈值键**；缺键 / 值未拍板 ⇒ 响亮失败。

    ★ 缺键不兜底是本模块的**核心行为**（见模块 docstring 第 2 条）：
      `Ch4 §J.4 J3` 明写形式完备性阈值是"**占位 + 参数化** `rules/baseline.yaml`"，
      所以"键不在"是可发生状态；此时**必须**报输入异常，让"阈值从未被拍板"
      这件事在门禁输出里逐字可见，而不是悄悄按一个代码里的数放行。
    """
    return baseline_threshold_from(baseline_cfg(root), key)


def baseline_threshold_from(cfg: Mapping[str, Any], key: str) -> Any:
    """从**已装载的** `cfg` 取阈值键；缺键 / 值未拍板 ⇒ 响亮失败。

    ★ 为什么既要有 `baseline_threshold(root, key)` 又要有本函数：
      `Ch4 §G.2` 伪码的签名是 `form_complete(baseline, cfg)` —— `cfg` 是**入参**，
      不是路径。若 `form_complete` 为了取阈值自己读盘，它就不再是纯函数，
      "阈值来自哪个文件"也会在调用链里变得不可见。
      故：装载走 `baseline_cfg(root)`，判定走本函数（对 `cfg` 的**同一个**检查）。
      两者的缺键行为**逐字相同**（同一个异常、同一段理由），不构成第二套谓词。
    """
    if key not in cfg:
        raise MissingRuleInput(
            f"{BASELINE_RELPATH}::{THRESHOLDS_GROUP} 缺少键 {key!r} —— "
            f"Ch4 §G.2/§D.2 要求该阈值参数化在规则文件里，代码不内置默认值（现有键：{sorted(cfg)}）"
        )
    value = cfg[key]
    if is_undecided(value):
        raise UndecidedThreshold(
            f"{BASELINE_RELPATH}::{THRESHOLDS_GROUP} 的 {key!r} 为 {value!r} —— "
            "`tbd`/未拍板的值不得被当成一个可用阈值（G-03：空 ≠ 已验证）"
        )
    return value


def threshold_or_none(cfg: Mapping[str, Any], key: str) -> Any | None:
    """取阈值；**值未拍板**时返回 `None`（缺键仍响亮失败）。

    ★ 这条通路是给「**该子项本身可分解成"可核部分 + 待拍板部分"**」的检查用的，
      目前唯一的使用者是 `Ch4 §G.2` 的 `sections_nonempty`：
      "六项 section 非空"**可核**，而"达**最小字段数**"的数值在
      `rules/baseline.yaml` 里是 `min_fields_per_section: tbd`（13-R 如实转写：设计未给值）
      ⇒ 子项降级为「非空 enforced + 最小字段数记 `不可核`」，
      既不放行也不恒红（`G-01`/`G-03`）。
    """
    if key not in cfg:
        raise MissingRuleInput(
            f"{BASELINE_RELPATH}::{THRESHOLDS_GROUP} 缺少键 {key!r}（现有键：{sorted(cfg)}）"
        )
    return None if is_undecided(cfg[key]) else cfg[key]


def metric_sets(root: str | Path) -> list[dict[str, Any]]:
    """`rules/metric-sets.yaml` 的指标集注册表（`Ch4 §C.1` / `§C.3`）。

    设计给的顶层结构是**列表**（§C.1 的 yaml 块以 `- metric_set_id: ...` 开头）：
    每一项含 `metric_set_id` / `model_class` / `currency` / `stages` / `metrics` /
    `linked_accounts`。

    ★ 兼容两种写法（顶层 list，或 `{"metric_sets": [...]}`）而**不改变语义**：
      13-R 逐字转写时两种都可能出现，而"顶层是 list"是本模块的**主契约**；
      若非这两种形态 ⇒ 响亮失败（不静默返回空表 —— 那会让路由守卫扫到 0 个指标集而"通过"）。
    """
    doc = _cached_yaml(Path(root) / METRIC_SETS_RELPATH) if (Path(root) / METRIC_SETS_RELPATH).exists() else None
    if doc is None:
        raise MissingRuleInput(f"缺少规则文件 {METRIC_SETS_RELPATH}")
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict) and isinstance(doc.get("metric_sets"), list):
        rows = doc["metric_sets"]
    else:
        raise MissingRuleInput(
            f"{METRIC_SETS_RELPATH} 结构非法：应为 metric_set 列表（Ch4 §C.1 的 yaml 块），"
            f"实为 {type(doc).__name__}"
        )
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise MissingRuleInput(f"{METRIC_SETS_RELPATH} 第 {idx} 项不是 mapping")
        out.append(row)
    return out


def metric_set_routing(root: str | Path) -> dict[str, Any]:
    """`rules/metric-sets.yaml::routing` 分组（`Ch4 §C.1`/`§C.3` 的路由与兜底声明）。

    ★ 用途：`route_guard` 里的 `MS-GENERIC` 是个**代码常量**，而兜底 id 的**真源**
      是本文件的 `routing.fallback_metric_set_id`。两条并存就有漂移风险（`G-06`）。
      故 `route_guard.check()` 用本函数**在运行时核对**常量与文件一致 ——
      把"同一个事实的两个存放处"降级成"一个真源 + 一处被核对的引用"。
    """
    doc = _load_mapping(root, METRIC_SETS_RELPATH)
    group = doc.get("routing")
    if not isinstance(group, dict):
        raise MissingRuleInput(
            f"{METRIC_SETS_RELPATH} 缺 `routing:` 分组（或它不是 mapping，实为 {type(group).__name__}）"
            "—— 路由键与兜底指标集的真源在该分组（Ch4 §C.1/§C.3）"
        )
    return dict(group)


#: `Ch4 §C.3` 逐字：未注册的 `model_class` 归入 `MS-GENERIC` 并**显式标注**
#: `unregistered_model_class=true`（"只改 rules/metric-sets.yaml、不改代码"的扩展机制）。
#:
#: ★ 这是**被核对的引用**，不是第二真源：`route_guard.check()` 会读
#:   `metric-sets.yaml::routing.fallback_metric_set_id` 与它比对，不一致即报违例。
GENERIC_METRIC_SET_ID = "MS-GENERIC"

