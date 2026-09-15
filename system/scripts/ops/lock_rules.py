#!/usr/bin/env python3
"""`lock_rules.py` —— **给 `rules/` 上 0444 + SHA256 锁**（`Ch9 §3.10 J9` · 纪律 9/10）。

```
python system/scripts/ops/lock_rules.py [code_root]
```

这是**唯一**被授权改动 `rules/` 权限的工具。它做三件事：

1. 计算 `rules/**/*.{yaml,yml,json}` 的 SHA256
2. 把清单写进 **`registry/rules.lock.json`**
3. 把 `rules/` 下每个文件 `chmod 0444`

★ **锁文件刻意放在 `rules/` 之外**：这样"模型对 `rules/` 无写权（纪律 10）"是
  **绝对**的、没有例外路径 —— 不会出现"唯一允许写的是锁文件自己"这种破口。
  校验方见 `scripts/checks/rules_lock_guard.py`。

★ 合法改规则的流程（**可审计**）：`chmod -R u+w system/rules` → 改 → 重跑本脚本。
  权限变更是**显式动作**，天然留痕；不会有人"顺手改了规则而没人发现"。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.rules import sha256_of  # noqa: E402

LOCK_RELPATH = Path("registry") / "rules.lock.json"
RULE_SUFFIXES = (".yaml", ".yml", ".json")
READ_ONLY_MODE = 0o444


def rule_files(root: Path) -> list[Path]:
    base = root / "rules"
    if not base.exists():
        raise FileNotFoundError(f"缺少 rules/ 目录: {base}")
    return sorted(
        p for p in base.rglob("*") if p.is_file() and p.suffix in RULE_SUFFIXES
    )


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]).resolve() if argv else _ROOT
    files = rule_files(root)

    entries: dict[str, dict[str, object]] = {}
    for path in files:
        rel = path.relative_to(root).as_posix()
        entries[rel] = {
            "sha256": sha256_of(path),
            "bytes": path.stat().st_size,
            "locked_mode": oct(READ_ONLY_MODE),
        }

    lock_path = root / LOCK_RELPATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "version": 1,
                "spec_anchor": "Ch9 §3.10 J9 / 施工图 §8 纪律 9-10",
                "locked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "locked_by": "system/scripts/ops/lock_rules.py",
                "owner_writable": False,
                "note": (
                    "本清单是 rules/ 的 SHA256 快照。校验方 "
                    "scripts/checks/rules_lock_guard.py；改动流程见 lock_rules.py 文档头。"
                ),
                "files": entries,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"锁清单: {lock_path.relative_to(root)}（{len(entries)} 个文件）")

    for path in files:
        os.chmod(path, READ_ONLY_MODE)
    print(f"已 chmod {READ_ONLY_MODE:o}: rules/ 下 {len(files)} 个文件")

    # 读回验证：锁完必须真的读不动写
    bad = [p.relative_to(root).as_posix() for p in files if (os.stat(p).st_mode & 0o777) != READ_ONLY_MODE]
    if bad:
        print(f"错误：以下文件未被锁为 0444: {bad}", file=sys.stderr)
        return 2
    print("读回验证：全部 0444 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
