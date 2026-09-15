"""`rules/` 只读锁的注入测试（`Ch9 §3.10 J9` · 纪律 9/10）。

三条断言都必须**真跑**验证：
① 权限被放开 → exit 1
② 内容被改（哈希不符）→ exit 1
③ 新增/删除规则文件（未重锁）→ exit 1
④ 反向对照：原件（已锁）→ 放行

★ 这里显式调用 `_lock(root)` 把夹具副本恢复成"已锁"状态：
  夹具为了让其它注入测试能改写规则而放宽了权限（见 conftest），
  本测试必须把这份"放宽"收回来，否则测的是夹具而不是守卫。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from conftest import assert_rejected, run_gate

GUARD = "scripts/checks/rules_lock_guard.py"
LOCK = "registry/rules.lock.json"


def _lock(root: Path) -> None:
    """把夹具副本恢复成"已锁"状态：重算哈希写清单 + chmod 0444。"""
    from config.rules import sha256_of

    files = sorted(
        p
        for p in (root / "rules").rglob("*")
        if p.is_file() and p.suffix in (".yaml", ".yml", ".json")
    )
    entries = {p.relative_to(root).as_posix(): {"sha256": sha256_of(p)} for p in files}
    (root / LOCK).write_text(
        json.dumps(
            {
                "version": 1,
                "locked_at": "2026-09-16T00:00:00+00:00",
                "files": entries,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    for p in files:
        os.chmod(p, 0o444)


def _unlock(root: Path, rel: str) -> Path:
    path = root / rel
    os.chmod(path, 0o644)
    return path


def test_locked_rules_pass(code_root: Path) -> None:
    """**反向对照**：已锁且哈希一致 → 必须放行。"""
    _lock(code_root)
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 0, f"已锁的 rules/ 被误报\n{proc.stdout}\n{proc.stderr}"
    assert "registered_files" in proc.stdout


def test_writable_rule_file_is_rejected(code_root: Path) -> None:
    """① 权限被放开（0644）→ 必须 exit 1（纪律 9 未落地）。"""
    _lock(code_root)
    _unlock(code_root, "rules/freeze.yaml")
    assert_rejected(run_gate(GUARD, code_root), rule_hint="纪律 9")


def test_modified_rule_content_is_rejected(code_root: Path) -> None:
    """② 锁定后内容被改（哈希不符）→ 必须 exit 1。"""
    _lock(code_root)
    path = _unlock(code_root, "rules/scope.yaml")
    path.write_text(path.read_text(encoding="utf-8") + "\n# 偷偷改了一行\n", encoding="utf-8")
    os.chmod(path, 0o444)                       # 权限改回去，只留内容不符
    assert_rejected(run_gate(GUARD, code_root), rule_hint="哈希不符")


def test_unregistered_new_rule_file_is_rejected(code_root: Path) -> None:
    """③ 新增规则文件但未重锁 → 必须 exit 1（纪律 10：新增必须显式重锁）。"""
    _lock(code_root)
    extra = code_root / "rules" / "sneaky.yaml"
    extra.write_text("version: 1\n", encoding="utf-8")
    os.chmod(extra, 0o444)
    assert_rejected(run_gate(GUARD, code_root), rule_hint="未登记")


def test_deleted_registered_rule_file_is_rejected(code_root: Path) -> None:
    """③ 已登记的规则文件被删除 → 必须 exit 1（真源不得删除）。"""
    _lock(code_root)
    (code_root / "rules" / "schedule.yaml").unlink()
    assert_rejected(run_gate(GUARD, code_root), rule_hint="文件不存在")


def test_missing_lock_file_fails_loudly(code_root: Path) -> None:
    """**错误路径**：锁清单缺失 → exit 2（输入异常），不得静默放行。"""
    (code_root / LOCK).unlink(missing_ok=True)
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 2, (
        f"缺锁清单应报输入异常(2)，实得 {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    )
