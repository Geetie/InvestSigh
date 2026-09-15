#!/usr/bin/env python3
"""`rules_lock_guard.py` —— **`rules/` 只读锁校验**（`Ch9 §3.10 J9` · 纪律 9/10）。

```
python system/scripts/checks/rules_lock_guard.py [code_root]
```

三条断言（逐条可执行）：

| # | 断言 | 依据 |
|---|---|---|
| ① | `rules/**` 每个文件权限**恰为 0444** | 纪律 9「`rules/` 0444 + SHA256」 |
| ② | 每个文件的 SHA256 **与 `registry/rules.lock.json` 一致** | 纪律 9 |
| ③ | **没有未登记文件**、也**没有登记后消失的文件** | 纪律 10（模型无写权） |

★ 为什么锁**必须**有校验方：只 chmod 不上锁 = 没人知道规则被人改过；
  只写清单不校验 = 清单是死文件（**假交付第 2 类：接线失败**）。
  两者齐备、且由本检查器在门禁里真跑，纪律 9/10 才算落地。

★ 命中即 fail，禁 warn-only（纪律 2）。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.rules import is_read_only, sha256_of  # noqa: E402
from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    run_checker,
)

LOCK_RELPATH = "registry/rules.lock.json"
RULE_SUFFIXES = (".yaml", ".yml", ".json")
READ_ONLY_MODE = 0o444


def _load_lock(root: Path) -> dict:
    path = root / LOCK_RELPATH
    if not path.exists():
        raise FileNotFoundError(
            f"缺少 rules 锁清单 {LOCK_RELPATH} —— 纪律 9/10 未落地（先跑 "
            f"system/scripts/ops/lock_rules.py）"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def check(root: Path) -> CheckReport:
    report = CheckReport(checker="rules_lock_guard")
    lock = _load_lock(root)
    registered: dict[str, dict] = lock.get("files") or {}
    if not registered:
        raise ValueError(f"{LOCK_RELPATH} 的 files 为空 —— 锁清单无效（不静默放行）")

    rules_dir = root / "rules"
    on_disk = {
        p.relative_to(root).as_posix(): p
        for p in sorted(rules_dir.rglob("*"))
        if p.is_file() and p.suffix in RULE_SUFFIXES
    }
    report.scanned["registered_files"] = len(registered)
    report.scanned["files_on_disk"] = len(on_disk)

    for rel, path in sorted(on_disk.items()):
        # ★ 用 `config.rules.is_read_only()` 而不是就地 `stat`：
        #   一是"只读语义"只应有一个定义处；二是初版该函数**零调用**
        #   （docstring 声称"试图写 rules/ → ReadOnlyRuleViolation，不留静默路径"，
        #   却没有调用方 —— 属"文档声称 vs 代码事实"脱节）。
        if not is_read_only(path):
            mode = os.stat(path).st_mode & 0o777
            report.violations.append(
                Violation(
                    "纪律 9",
                    f"{rel} 权限为 {oct(mode)}，应为 {oct(READ_ONLY_MODE)}"
                    "（rules/ 必须 0444 —— 锁定后仍可写说明锁没落上）",
                    rel,
                )
            )
        if rel not in registered:
            report.violations.append(
                Violation("纪律 10", f"{rel} 未登记在 {LOCK_RELPATH}（新增规则必须显式重锁）", rel)
            )
            continue
        actual = sha256_of(path)
        expected = registered[rel].get("sha256")
        if actual != expected:
            report.violations.append(
                Violation(
                    "纪律 9",
                    f"{rel} 内容哈希不符（期望 {str(expected)[:12]}… 实得 {actual[:12]}…）"
                    "—— 规则被改动过且未重锁",
                    rel,
                )
            )

    for rel in sorted(registered):
        if rel not in on_disk:
            report.violations.append(
                Violation("纪律 10", f"{rel} 已登记但文件不存在（真源不得删除）", rel)
            )

    report.notes.append(f"锁清单 locked_at = {lock.get('locked_at')}")
    return report


if __name__ == "__main__":
    sys.exit(run_checker("rules_lock_guard.py", check))
