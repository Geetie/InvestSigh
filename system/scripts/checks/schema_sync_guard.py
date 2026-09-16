#!/usr/bin/env python3
"""`schema_sync_guard.py` —— **schema 生成物漂移守卫**（`Ch9 §3.3.3` · `§一 底线 2`）。

```
python system/scripts/checks/schema_sync_guard.py [code_root]
```

**它拦的是什么**：`schema/jsonschema/facts.schema.json` 是 `schema/models.py` 的**生成物**，
生成器是 `schema/build_jsonschema.py`（该 JSON 自己的 `description` 也这么写）。但
生成器既不在门禁里、也不在 pre-commit 里 —— 于是**改了模型不改生成物，17 条门禁全绿、
105 个测试全过**（第二轮独立审计反例 E2 实测）。

而 L1 断言（`Ch2 §B.3` Checker-2：`P-03/P-04/P-05/P-07` 的字段存在性）
**是读生成物**的。生成物一旦漂移，L1 就在对一个**过期的 schema** 做断言 ——
"门禁通过了但断言的对象不是真源"，是典型的**假绿灯**。

三条断言：
① 生成物与"从当前 `models.py` 现算出来的"**逐字节等价**（规范化后）
② 每个对象都 `additionalProperties: false`（与 `ConfigDict(extra="forbid")` 对齐）
③ `objects` 映射与**事实表注册表**（`schema/models.py::JSONL_MODELS`）**集合逐一相等**

★ 第 ③ 条**不写字面表数**（原先写死 18）：
  表数由需求方 2026-09-16 裁定从 18 扩至 22（见 `schema/stems.py` 脚注 / `T-13` 备选②），
  而"写死一个数"意味着**每次表数变化都要来改这里** —— 那是手工台账，迟早漂移。
  改为从**被检 `code_root` 的注册表**现取 ⇒ 表数只有一处真源（`stems.py` → `JSONL_MODELS`），
  且"生成物多一张/少一张表"依然会被拦（集合不相等即违例）。

★ **必须加载「被检 `code_root`」的 schema 包**，不能加载本脚本自己那份 ——
  否则对副本做注入测试时，本守卫会永远看着真仓库的 models.py 而"通过"。
  这是"注入测试能不能证伪"的关键（`§5.1 AC-04`）。

★ 命中即 fail，禁 warn-only（纪律 2）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    run_checker,
)

SCHEMA_RELPATH = Path("schema") / "jsonschema" / "facts.schema.json"


def _normalized(doc: object) -> str:
    """规范化：排序键 + 稳定分隔符 —— 只比内容，不比排版。"""
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_builder(root: Path):
    """加载 **被检 code_root** 的生成器（不是本脚本自己那份），且**用完不留副作用**。

    ★ 必须恢复 `sys.path` 与 `sys.modules`。初版直接 `sys.path.insert` +
      删 `schema*` 缓存 —— 在"一次一个子进程"的语境下没问题，但测试改成
      **进程内执行**后，它会污染整个测试进程：后续检查器会从**已被删除的夹具
      目录**导入 `schema`，引发一批与本检查器毫无关系的失败（实测 16 条）。
      **带全局副作用的加载器必须自己收尾** —— 这是"结论：别让工具改变环境"的实例。

    返回的 `build` 仍可正常调用：它的 `__globals__` 持有夹具那份模块对象，
    模块级已绑定 `JSONL_MODELS` / `_inline_refs`，不需要再走 import 系统。
    """
    root_str = str(root.resolve())
    saved_path = list(sys.path)
    saved_schema_modules = {
        name: mod for name, mod in sys.modules.items() if name == "schema" or name.startswith("schema.")
    }
    try:
        sys.path.insert(0, root_str)
        for name in list(saved_schema_modules):
            del sys.modules[name]
        from schema.build_jsonschema import build  # noqa: PLC0415

        return build
    finally:
        sys.path[:] = saved_path
        for name in [n for n in sys.modules if n == "schema" or n.startswith("schema.")]:
            del sys.modules[name]
        sys.modules.update(saved_schema_modules)


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="schema_sync_guard")
    path = root / SCHEMA_RELPATH
    if not path.exists():
        raise FileNotFoundError(
            f"缺少聚合 schema 生成物 {SCHEMA_RELPATH} —— 先跑 python -m schema.build_jsonschema"
        )
    committed = json.loads(path.read_text(encoding="utf-8"))

    build = _load_builder(root)
    fresh = build()

    # ★ 注册表 = **被检 code_root** 的 `JSONL_MODELS`（`build()` 的 `__globals__` 里已绑定，
    #   见 `_load_builder` 的 docstring）。表数**不写字面量**，由此派生。
    registry: dict[str, object] = build.__globals__["JSONL_MODELS"]

    report.scanned["committed_defs"] = len(committed.get("defs") or {})
    report.scanned["fresh_defs"] = len(fresh.get("defs") or {})
    report.scanned["objects"] = len(committed.get("objects") or {})
    report.scanned["registry_stems"] = len(registry)

    if _normalized(committed) != _normalized(fresh):
        # 精确定位到哪个 def 漂了，便于直接修
        c_defs = committed.get("defs") or {}
        f_defs = fresh.get("defs") or {}
        drifted = sorted(
            name
            for name in set(c_defs) | set(f_defs)
            if _normalized(c_defs.get(name)) != _normalized(f_defs.get(name))
        )
        report.violations.append(
            Violation(
                "底线 2 / Ch9 §3.3.3",
                f"schema 生成物与 models.py 不一致（漂移对象: {drifted[:12]}"
                f"{' …' if len(drifted) > 12 else ''}）→ 重跑 "
                "`python -m schema.build_jsonschema`",
                SCHEMA_RELPATH.as_posix(),
            )
        )
    if _normalized(committed.get("objects")) != _normalized(fresh.get("objects")):
        report.violations.append(
            Violation(
                "Ch9 §3.3.3",
                "schema.objects（JSONL → 对象映射）与 models.JSONL_MODELS 不一致",
                SCHEMA_RELPATH.as_posix(),
            )
        )

    objects = committed.get("objects") or {}
    if set(objects) != set(registry):
        report.violations.append(
            Violation(
                "Ch9 §3.3.3",
                "schema.objects 与事实表注册表（JSONL_MODELS）不一致："
                f"多出 {sorted(set(objects) - set(registry))}；"
                f"缺少 {sorted(set(registry) - set(objects))}",
                SCHEMA_RELPATH.as_posix(),
            )
        )

    for name, definition in (committed.get("defs") or {}).items():
        if not isinstance(definition, dict) or "properties" not in definition:
            continue
        if definition.get("additionalProperties") is not False:
            report.violations.append(
                Violation(
                    "N9.2-01",
                    f"defs.{name} 的 additionalProperties 不为 false（与 extra='forbid' 不对齐）",
                    SCHEMA_RELPATH.as_posix(),
                )
            )
    return report


if __name__ == "__main__":
    sys.exit(run_checker("schema_sync_guard.py", check))
