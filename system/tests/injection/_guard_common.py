"""`tests/injection/` 的**共享工具**（唯一真源，`CONVENTIONS.md::G-06`）。

## 为什么会有这个模块

`test_guards_reject.py` 原有 **41 个用例**。夹具是**每用例复制一份 `system/`**
（`conftest.py::code_root`，完整夹具实测每份 **273 项**），而宿主对**单轮（turn）**的
删除操作有累积配额（`CONVENTIONS.md::V-08`，实测消息
`SAFE_DELETE_BULK_CONFIRM_REQUIRED {"count":…,"threshold":…,"scope":"turn"}`；
阈值**两次观测不同**：`9999` 与 `99999`，故此处不写死它）。
⇒ 按实测的**计数单位 ≈792/例**（≈2.9 × 273，见 `test_shard_coverage.py` 上方注释），
单个文件 41 例 ≈ **3.2 万计数**，**这一个文件本身就远超阈值**
（越过之后连单个用例目录都被拒删，之后所有夹具 setup 直接报 `E`）。

故按 `# ═══` **分节边界**把它**纯移动**拆成两个文件：

| 文件 | 分节 | 例数 |
|---|---|---|
| `test_guards_reject_a.py` | `L1` `L2` `L3` `G11` `launch` `benchmark` `anti_padding` `module_denylist` `neutrality` | 21 |
| `test_guards_reject_b.py` | `placeholder` + `injection_guard` | 20 |

拆完两文件**用例数之和仍为 41**，断言语义零改动（纯移动）。

两半都要用的工具（`_schema` / `_write_schema` / `_read_yaml` / `_write_yaml` / `_inject_py`）
与被测脚本路径常量**只能有一份** —— 故提到本模块。
★ **不许两处各抄一份**：同一事实两个存放处必然漂移（`G-06` 唯一真源）。

## 怎么被导入

pytest 的 `prepend` 导入模式会把握有测试文件的**最内层非包目录**放进 `sys.path`
（`tests/injection/` 无 `__init__.py`），故两半直接
`from _guard_common import ...` 即可。

★ 本模块名**不匹配** `test_*.py` ⇒ 既不会被 pytest 收集，也不会被
`verification_policy_guard.py` 的"测试文件必须被批次覆盖"（`V-06`）判成漏覆盖
—— 两处判据用的都是同一个定义（见该守卫 `_test_files()`）。
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

# ─────────────────────────── 被测脚本路径 ───────────────────────────
# 真源 = 各脚本在仓库里的相对路径；两半共用同一份，避免"改了一处漏了另一处"。

CONFLICT = "scripts/checks/conflict_scan.py"
FREEZE = "scripts/checks/freeze_guard.py"
LAUNCH = "scripts/checks/launch_guard.py"
RETURN = "scripts/benchmark/return_guard.py"
ANTI_PADDING = "scripts/scope/anti_padding.py"
MODULE_DENY = "scripts/checks/module_denylist.py"
NEUTRALITY = "scripts/views/neutrality_check.py"
PLACEHOLDER = "scripts/checks/no_placeholder_guard.py"
INJECTION_GUARD = "scripts/checks/injection_guard.py"


# ─────────────────────────── 工具 ───────────────────────────

def _schema(code_root: Path) -> dict:
    path = code_root / "schema" / "jsonschema" / "facts.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write_schema(code_root: Path, doc: dict) -> None:
    path = code_root / "schema" / "jsonschema" / "facts.schema.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_yaml(code_root: Path, rel: str) -> dict:
    return yaml.safe_load((code_root / rel).read_text(encoding="utf-8"))


def _write_yaml(code_root: Path, rel: str, doc: dict) -> None:
    (code_root / rel).write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _inject_py(code_root: Path, rel: str, source: str) -> None:
    path = code_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
