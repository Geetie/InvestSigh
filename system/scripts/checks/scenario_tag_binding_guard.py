#!/usr/bin/env python3
"""`scenario_tag_binding_guard.py` —— 情景取值域**两侧零绑定**守卫（缺口 `G-55`）。

```
python system/scripts/checks/scenario_tag_binding_guard.py [code_root]
```

## 它拦的是什么

**同一语义、两种载体形态、零机器绑定**（`G-55`，与 `G-50` / `T-18` 并列的第三种"声明≠有效力"）：

| 载体 | 形态 | 实例 |
|---|---|---|
| A · 声明面 | `rules/scenario.yaml` 的 **YAML 列表** | `scenario_tags: [bear, neutral, bull, custom]`（:25）/ `scenario_method_status_domain: [pending, neutral, probability_weighted]`（:41） |
| B · 实现面 | `scripts/pricelayer/scenario_guard.py` 的 **Python 取值域** | `class ScenarioTag(str, Enum)`（:82）/ `SCENARIO_METHOD_STATUSES`（:91） |

两边**值相同、各自自洽**，于是**没有任何东西会因为"只改一侧"而变红** ——
改 `rules/scenario.yaml` 的 `scenario_tags` 少一个 `custom`，`ScenarioTag` 照样能构造出 `custom`；
反过来源码里删掉 `bear`，规则文件照样声明着它。**漂移可以无限期存在而无人发现。**

★ **本缺陷是"合并的产物"，不是任何一条流的错**（`G-55` 的登记语）：13-B 自注册了 YAML 侧、
实现侧原本就有枚举，**两条流各自都自洽** —— 单流自检不可能发现它，只有集成才让它们变成两份可漂移的存储。
这正是本项目铁律要拦的形态：「**只写在文档里、没有检查器强制的规范等于不存在**」——
只不过这里"文档"是 `rules/` 里那份**已锁 0444 + SHA256** 的规则文件，看起来比散文权威得多。

## 三条断言（两侧都从**真源实读**，一律不手写清单）

1. **集合双向相等**：`set(YAML) == set(实现)`。**两侧的差集分别报出**（"YAML 多出 X" 与
   "实现多出 Y" 是两条不同的违例 —— 报告里必须能直接看出该改哪一侧）。
2. **两侧都非空**：任一侧为空即违例。★ 否则"两个空集合相等"会让断言**真空成立**（`G-03`）。
3. **形态正确**：YAML 侧必须是**字符串列表**。★ 若它退化成一个裸字符串（`scenario_tags: bear`），
   `set("bear")` = `{'b','e','a','r'}` —— 一个**字符集合**与枚举做比较，结果毫无意义却"看起来在比"。

## ★ 为什么必须加载**被检 `code_root`** 的那份实现

否则对夹具副本做注入测试时，本守卫会永远看着真仓库的枚举而"通过" ——
注入测试就**证伪不了**它（同 `schema_sync_guard` 的 `_load_builder` 注释所述；
`§5.1 AC-04` 要的正是"注入违例 ⇒ exit 1"这条可证伪性）。

## ★ 关于两个落点

`G-55` 登记时只点了「`scenario_tags` ↔ `ScenarioTag`」一处。
实现时按**同一判据**（"同一语义 / 两种载体 / 零绑定"）扫过这两份文件，
发现**同一形态还有第二处**：`scenario_method_status_domain`（YAML :41）↔ `SCENARIO_METHOD_STATUSES`
（`scenario_guard.py:91`）—— 值同为 `pending/neutral/probability_weighted`，同样零绑定。
**同一个缺陷形态、同一对文件、同一条判据** ⇒ 一并绑定（否则下一个人要把整卡重做一遍）。
两处都在下表里逐条列出，**不是**把两处折叠成一条含糊的"情景取值域检查"。

★ 命中即 fail，禁 warn-only（纪律 2）。
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    run_checker,
)

SCENARIO_YAML_RELPATH = Path("rules") / "scenario.yaml"
GUARD_MODULE_RELPATH = Path("scripts") / "pricelayer" / "scenario_guard.py"

# (YAML 键, 实现侧符号名, 出处)
# ★ 本表是「**哪两样东西是同一语义**」的绑定元数据，**不是**取值清单 ——
#   取值一律从两侧实读（这是 `G-55` 的要求，也是把清单写进代码就会重演 `G-28` 的原因）。
BINDINGS: tuple[tuple[str, str, str], ...] = (
    (
        "scenario_tags",
        "ScenarioTag",
        "Ch5 §J4（`05_价格与市场预期研究/02_实现方案.md:461`）："
        "「情景标签体系 | 枚举 | 定义 `{bear, neutral, bull, custom}`，首版仅用一致标签」",
    ),
    (
        "scenario_method_status_domain",
        "SCENARIO_METHOD_STATUSES",
        "Ch5 §E.4（同文件 `:256`）：`scenario_method_status: pending | neutral | probability_weighted`",
    ),
)

_MODULE_NAME = "scripts.pricelayer.scenario_guard"


def _load_checked_symbols(root: Path) -> dict[str, Any]:
    """从**被检 `code_root`** 加载实现侧的取值域符号，**用完不留副作用**。

    ★ 必须恢复 `sys.path` 与 `sys.modules`（同 `schema_sync_guard._load_builder` 的教训）：
      本守卫在测试里是**进程内执行**的（`tests/conftest.py::run_gate_inproc` 走 `runpy`），
      若把 `scripts*` 从 `sys.modules` 里删掉而不还原，会污染整个测试进程 ——
      后续检查器会从**已被删除的夹具目录**导入 `scripts`，引发一批与本守卫毫无关系的失败。
      **带全局副作用的加载器必须自己收尾。**

    ★ 取到的值在 `finally` 之前就**抽成纯数据**（字符串元组），
      这样还原 `sys.modules` 之后仍然可用（不依赖"模块对象还活着"这个偶然事实）。
    """
    if not (root / GUARD_MODULE_RELPATH).exists():
        raise FileNotFoundError(
            f"缺少实现侧取值域的载体 {GUARD_MODULE_RELPATH} —— 本守卫的 B 侧不存在，"
            "此时**不得**当作通过（`G-03`：没有可检对象 ≠ 已验证）"
        )

    root_str = str(root.resolve())
    saved_path = list(sys.path)
    saved_scripts_modules = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "scripts" or name.startswith("scripts.")
    }
    try:
        sys.path.insert(0, root_str)
        for name in list(saved_scripts_modules):
            del sys.modules[name]
        module = importlib.import_module(_MODULE_NAME)
        out: dict[str, Any] = {}
        for _, symbol, _ in BINDINGS:
            if not hasattr(module, symbol):
                raise FileNotFoundError(
                    f"实现侧符号 `{_MODULE_NAME}::{symbol}` 不存在 —— "
                    "声明面仍在，实现面已改/已删（`G-55` 要拦的正是这种单边漂移）"
                )
            obj = getattr(module, symbol)
            if isinstance(obj, type):  # Enum 类
                out[symbol] = tuple(str(member.value) for member in obj)
            else:
                out[symbol] = tuple(str(item) for item in obj)
        return out
    finally:
        sys.path[:] = saved_path
        for name in [
            n for n in sys.modules if n == "scripts" or n.startswith("scripts.")
        ]:
            del sys.modules[name]
        sys.modules.update(saved_scripts_modules)


def _read_declared_tokens(raw: Any, key: str, relpath: str) -> tuple[str, ...]:
    """把 YAML 侧的一个键读成 token 元组；**形态不对即响亮失败**。

    ★ 为什么必须查形态（而不是直接 `set(raw)`）：若 YAML 写成标量 `scenario_tags: bear`，
      `set("bear") == {'b','e','a','r'}` —— 拿一个**字符集合**去和枚举比，断言"在跑但没有意义"。
      这种"看着像在比"的假检查比没有检查更坏。
    """
    if raw is None:
        raise ValueError(
            f"{relpath}::{key} 不存在 —— 声明面缺键（实现侧仍在）⇒ 单边漂移，不得当作通过"
        )
    if isinstance(raw, str):
        raise ValueError(
            f"{relpath}::{key} 是**标量字符串** {raw!r}，应为**列表**（`set('bear')` 会得到字符集合，"
            "比较结果无意义却看起来在比）"
        )
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"{relpath}::{key} 形态应为列表，实为 {type(raw).__name__}")
    return tuple(str(item) for item in raw)


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="scenario_tag_binding_guard")

    yaml_path = root / SCENARIO_YAML_RELPATH
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"缺少声明面 {SCENARIO_YAML_RELPATH} —— 两侧绑定的 A 侧不存在，"
            "此时**不得**当作通过（`G-03`）"
        )
    doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{SCENARIO_YAML_RELPATH} 顶层不是 mapping，无法按键读取声明面")

    impl = _load_checked_symbols(root)

    report.scanned["bindings"] = len(BINDINGS)
    report.scanned["yaml_keys_present"] = sum(
        1 for key, _, _ in BINDINGS if key in doc
    )
    report.scanned["declared_tokens"] = 0
    report.scanned["implemented_tokens"] = 0

    rel = SCENARIO_YAML_RELPATH.as_posix()
    for key, symbol, anchor in BINDINGS:
        declared = _read_declared_tokens(doc.get(key), key, rel)
        implemented = impl[symbol]
        report.scanned["declared_tokens"] += len(declared)
        report.scanned["implemented_tokens"] += len(implemented)

        d_set = set(declared)
        i_set = set(implemented)

        # 断言 2：任一侧为空 ⇒ 违例。★ 否则"两个空集合相等"会让下面的相等断言**真空成立**。
        if not d_set or not i_set:
            report.violations.append(
                Violation(
                    "G-55",
                    f"`{rel}::{key}` 与 `{_MODULE_NAME}::{symbol}` 的绑定**不可判定**："
                    f"声明侧 {len(d_set)} 个 token、实现侧 {len(i_set)} 个 —— "
                    "任一侧为空时「相等」是真空成立，不得当作通过（`G-03`）。出处："
                    f"{anchor}",
                    rel,
                )
            )
            continue

        # 断言 1：**双向**相等，且两侧差集**分别**报出（报告要能直接看出改哪一侧）。
        only_declared = sorted(d_set - i_set)
        only_implemented = sorted(i_set - d_set)
        if only_declared:
            report.violations.append(
                Violation(
                    "G-55",
                    f"声明侧多出 {only_declared}：`{rel}::{key}` 声明了 "
                    f"{sorted(d_set)}，而 `{symbol}` 只实现 {sorted(i_set)} ⇒ "
                    f"实现侧 {_MODULE_NAME} 缺 {only_declared}（改一侧另一侧不会红）。出处：{anchor}",
                    rel,
                )
            )
        if only_implemented:
            report.violations.append(
                Violation(
                    "G-55",
                    f"实现侧多出 {only_implemented}：`{symbol}` 实现 {sorted(i_set)}，"
                    f"而 `{rel}::{key}` 只声明 {sorted(d_set)} ⇒ "
                    f"声明侧 {rel} 缺 {only_implemented}（改一侧另一侧不会红）。出处：{anchor}",
                    rel,
                )
            )
        if not only_declared and not only_implemented:
            report.notes.append(
                f"`{key}` ↔ `{symbol}` 双向相等（{len(d_set)} 个 token：{sorted(d_set)}），出处 {anchor}"
            )

    return report


if __name__ == "__main__":
    sys.exit(run_checker("scenario_tag_binding_guard.py", check))
