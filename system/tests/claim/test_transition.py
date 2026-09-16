"""`transition` 五态状态机 + `superseded` 传播测试（`ws/claim` · DoD B）。

覆盖：**真跑通**（真实采集 claim → 真迁移）、**持久化**（追加式 + `index/` 重建）、
**守卫真拦得住**（非法迁移 / 定位无效 → CLI **exit 1**）、**错误路径**（悬空传播 / 三字段互换 /
未知状态）、**边界**（空 claims / 终态 / 非法 `version_kind` / 序或时间倒挂）。

★ 逻辑断言在**本进程内**直调模块（真读夹具副本的 `facts/`）；**退出码**断言走**真子进程 CLI**。
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import SYSTEM_ROOT
from scripts.claim import transition as transition_mod

TRANSITION_CLI = SYSTEM_ROOT / "scripts" / "claim" / "transition.py"

_CHILD_ENV = {
    **os.environ,
    "CODEBUDDY_SAFE_DELETE_SANDBOX": "0",
    "CODEBUDDY_BROKERED_FS_HOOK_ENABLED": "0",
}

DEFAULT_FIRST_SEEN = "2026-09-16T00:00:00+00:00"
LATER = datetime(2026, 9, 16, 5, 0, tzinfo=timezone.utc)


def _claim(**over: object) -> dict:
    base: dict = {
        "claim_id": "clm-1",
        "source_id": "src-1",
        "quote_hash": "a" * 64,
        "claim_nature": "fact",
        "claim_form": "citation",
        "tier": "secondary_tertiary",
        "locator": "raw/doc.txt#L1-L2",
        "status": "active",
        "first_seen_at": DEFAULT_FIRST_SEEN,
        "analyzed_at": DEFAULT_FIRST_SEEN,
        "recorded_seq": 1,
        "full_text_read": False,
    }
    base.update(over)
    return base


def _seed(root: Path, rows: list[dict], *, raw: bool = True) -> None:
    """把 raw 原文与 claim 行写入夹具副本。"""
    if raw:
        target = root / "raw" / "doc.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("l1\nl2\n", encoding="utf-8")
    path = root / "facts" / "claims.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _read_claims(root: Path) -> list[dict]:
    path = root / "facts" / "claims.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_tasks(root: Path) -> list[dict]:
    path = root / "facts" / "tasks.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TRANSITION_CLI), str(root), *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=60,
        env=_CHILD_ENV,
    )


def _closure_fn(*_args: object, **_kwargs: object) -> list[dict]:
    """注入用遍历实现（模拟 `scripts/graph/forward_closure` 的下游集合）。"""
    return [{"type": "baseline", "id": "bl-1"}, {"type": "event", "id": "ev-1"}]


# ───────────────────────── 迁移表（Ch6 §E.1） ─────────────────────────


def test_allowed_transition_table_matches_design_ch6_e1() -> None:
    """允许迁移表逐边对齐 `Ch6 §E.1` 状态图；终态无出边；四态均可 → superseded。"""
    t = transition_mod.ALLOWED_TRANSITIONS
    assert t["pending_verification"] == {"supported", "disputed", "refuted", "superseded"}
    assert t["supported"] == {"disputed", "refuted", "superseded"}
    assert t["disputed"] == {"supported", "refuted", "superseded"}
    assert t["refuted"] == {"pending_verification", "disputed", "superseded"}
    assert t["superseded"] == set()
    # refuted 可重开（Ch6 §E.5）；superseded 不可重开
    assert transition_mod.can_transition("refuted", "pending_verification") is True
    assert transition_mod.can_transition("superseded", "pending_verification") is False


def test_illegal_self_transition_rejected() -> None:
    """自环（状态不变）非法 → `IllegalTransition`。"""
    with pytest.raises(transition_mod.IllegalTransition):
        transition_mod.assert_transition("pending_verification", "pending_verification")
    with pytest.raises(transition_mod.IllegalTransition):
        transition_mod.assert_transition("supported", "supported")


def test_terminal_superseded_has_no_outgoing() -> None:
    """`superseded` 为终态（`Ch6 §E.5`）：任何出边都非法。"""
    for target in transition_mod.CLAIM_STATES:
        if target == "superseded":
            continue
        with pytest.raises(transition_mod.IllegalTransition):
            transition_mod.assert_transition("superseded", target)


def test_entry_alias_active_only_enters_pending() -> None:
    """入口别名 `active` **只允许**进入 `pending_verification`（强制显式进入，不得直跳证据集）。"""
    assert transition_mod.can_transition("active", "pending_verification") is True
    assert transition_mod.can_transition("active", "supported") is False
    assert transition_mod.can_transition("active", "superseded") is False
    with pytest.raises(transition_mod.IllegalTransition):
        transition_mod.assert_transition("active", "supported")


def test_unknown_status_rejected() -> None:
    """`Ch6 §E.1` 五态之外的取值 → `UnknownClaimStatus`（响亮拒绝）。"""
    with pytest.raises(transition_mod.UnknownClaimStatus):
        transition_mod.assert_transition("frozen", "supported")
    with pytest.raises(transition_mod.UnknownClaimStatus):
        transition_mod.assert_transition("pending_verification", "待核验")


# ───────────────────────── 真跑通 + 持久化 ─────────────────────────


def _drive_ingest(code_root: Path) -> dict:
    inbox = code_root / "raw" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "2026-09-15_note_sample.txt").write_text("第一行\n第二行\n", encoding="utf-8")
    driver = code_root.parent / "drive_ingest_step.py"
    driver.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(code_root)!r})\n"
        "from datetime import date\n"
        "from scripts.orchestrate.ingest_step import ingest_public_information\n"
        "outcome = ingest_public_information(date(2026, 9, 16), 'sample')\n"
        "print('PRODUCED', len(outcome.produced))\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(driver)], cwd=str(code_root), capture_output=True, text=True, timeout=60,
        env=_CHILD_ENV,
    )
    assert proc.returncode == 0, f"ingest 子进程失败:\n{proc.stdout}\n{proc.stderr}"
    rows = _read_claims(code_root)
    assert len(rows) == 1
    return rows[0]


def test_real_ingest_then_enter_then_support(code_root: Path) -> None:
    """**AC-01 真跑通**：真实采集 claim（`status="active"`）→ `active→pending_verification→supported`。"""
    row = _drive_ingest(code_root)
    cid = row["claim_id"]
    assert row["status"] == "active"

    at = datetime.now(timezone.utc) + timedelta(seconds=1)
    r1 = transition_mod.transition(code_root, cid, "pending_verification", recorded_at=at)
    assert (r1.from_status, r1.to_status) == ("active", "pending_verification")

    r2 = transition_mod.transition(
        code_root, cid, "supported", recorded_at=at + timedelta(seconds=1)
    )
    assert (r2.from_status, r2.to_status) == ("pending_verification", "supported")

    rows = [r for r in _read_claims(code_root) if r["claim_id"] == cid]
    assert len(rows) == 3, f"应有 3 个版本行（追加），实得 {len(rows)}"
    seqs = [r["recorded_seq"] for r in rows]
    assert seqs == sorted(set(seqs)), f"recorded_seq 必须严格递增：{seqs}"
    assert rows[-1]["status"] == "supported"


def test_transition_appends_new_version_not_modifies(code_root: Path) -> None:
    """**AC-02 持久化**：追加式不可变（原行逐字不变）+ 删 `index/` 重建后数据仍在。"""
    _seed(code_root, [_claim()])
    original = (code_root / "facts" / "claims.jsonl").read_text(encoding="utf-8")

    result = transition_mod.transition(
        code_root, "clm-1", "pending_verification", recorded_at=LATER
    )
    assert result.recorded_seq == 2

    after = (code_root / "facts" / "claims.jsonl").read_text(encoding="utf-8")
    assert after.startswith(original), "既有行未被修改（新版本为**追加**）"
    assert after.count("\n") == original.count("\n") + 1

    from schema.store import rebuild_index

    index_path = rebuild_index(code_root)
    conn = sqlite3.connect(index_path)
    try:
        count = conn.execute(
            "SELECT count(*) FROM objects WHERE jsonl = 'claims'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 2


# ───────────────────────── 守卫真拦得住（CLI 退出码） ─────────────────────────


def test_cli_legal_check_exit0(code_root: Path) -> None:
    proc = _cli(code_root, "--check", "--from", "pending_verification", "--to", "supported")
    assert proc.returncode == 0, proc.stderr
    assert "合法" in proc.stdout


def test_cli_illegal_transition_exit1(code_root: Path) -> None:
    """**AC-04**：非法迁移 → CLI **exit 1**（不是 warn）。"""
    proc = _cli(code_root, "--check", "--from", "superseded", "--to", "supported")
    assert proc.returncode == 1, f"应 exit 1，实得 {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    assert "IllegalTransition" in proc.stderr


def test_cli_unknown_status_exit1(code_root: Path) -> None:
    proc = _cli(code_root, "--check", "--from", "frozen", "--to", "supported")
    assert proc.returncode == 1, proc.stderr
    assert "UnknownClaimStatus" in proc.stderr


def test_cli_missing_claim_exit2(code_root: Path) -> None:
    """**AC-06 空 claims**：请求不存在的 claim → `ClaimNotFound` → CLI **exit 2**（输入异常）。"""
    _seed(code_root, [], raw=False)
    proc = _cli(code_root, "--claim-id", "clm-absent", "--to", "supported")
    assert proc.returncode == 2, proc.stderr
    assert "ClaimNotFound" in proc.stderr


# ───────────────────────── 错误路径：定位无效 / 三字段互换 / 悬空传播 ─────────────────────────


def test_locator_invalid_blocks_transition(code_root: Path) -> None:
    """**AC-05**：主张定位无效（空 locator）→ 迁移被拒 `ClaimLocatorInvalid`；CLI exit 1。"""
    _seed(code_root, [_claim(locator="")], raw=False)
    with pytest.raises(transition_mod.ClaimLocatorInvalid):
        transition_mod.transition(code_root, "clm-1", "pending_verification", recorded_at=LATER)

    proc = _cli(code_root, "--claim-id", "clm-1", "--to", "pending_verification")
    assert proc.returncode == 1, proc.stderr
    assert "ClaimLocatorInvalid" in proc.stderr
    # 被拒后不落任何新行
    assert len(_read_claims(code_root)) == 1


def test_swapped_three_fields_rejected(code_root: Path) -> None:
    """**AC-05 三字段互换**：`claim_form` 取值塞进 `claim_nature` → 迁移前 `Claim` 校验响亮失败。"""
    _seed(code_root, [_claim(claim_nature="opinion")])
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        transition_mod.transition(code_root, "clm-1", "pending_verification", recorded_at=LATER)


def test_forward_closure_unavailable_blocks_superseded(
    code_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**AC-05 悬空传播**：`forward_closure` 不可用 → `PropagationUnavailable`，**写库前**失败、无半截数据。"""
    _seed(code_root, [_claim(status="pending_verification")])
    monkeypatch.setattr(transition_mod, "resolve_forward_closure", lambda: None)
    with pytest.raises(transition_mod.PropagationUnavailable):
        transition_mod.transition(
            code_root, "clm-1", "superseded", version_kind="source_retraction", recorded_at=LATER
        )
    assert len(_read_claims(code_root)) == 1, "失败必须发生在写库前（无半截数据）"


# ───────────────────────── superseded 传播（复用 forward_closure） ─────────────────────────


def test_superseded_propagation_enqueues_recheck(code_root: Path) -> None:
    """**AC-01 传播**：`superseded` → 下游逐个入 `recheck` 任务；结论类 `requires_recheck=True`。"""
    _seed(code_root, [_claim(status="pending_verification")])
    result = transition_mod.on_superseded(
        code_root, "clm-1", "source_retraction", recorded_at=LATER, forward_closure_fn=_closure_fn
    )
    assert result.to_status == "superseded"
    assert set(result.downstream) == {("baseline", "bl-1"), ("event", "ev-1")}

    claims = _read_claims(code_root)
    assert claims[-1]["status"] == "superseded"
    assert claims[-1]["version_kind"] == "source_retraction"

    tasks = _read_tasks(code_root)
    assert len(tasks) == 2, f"应有 2 条 recheck 任务，实得 {len(tasks)}"
    by_id = {t["parent_context"]["stale_object_id"]: t for t in tasks}
    assert by_id["bl-1"]["task_type"] == "recheck"
    assert by_id["bl-1"]["parent_context"]["requires_recheck"] is True
    assert by_id["bl-1"]["parent_context"]["invalidated_by"] == "clm-1"
    assert by_id["ev-1"]["parent_context"]["requires_recheck"] is False
    assert by_id["bl-1"]["idempotency_key"] == "recheck::clm-1::baseline::bl-1"


def test_propagation_is_idempotent(code_root: Path) -> None:
    """重跑传播不重复建单（幂等键 `recheck::<claim>::<type>::<id>`，`Ch9 §N9.1-26`）。"""
    _seed(code_root, [_claim(status="pending_verification")])
    first = transition_mod._propagate(code_root, "clm-1", "source_retraction", _closure_fn)
    second = transition_mod._propagate(code_root, "clm-1", "source_retraction", _closure_fn)
    assert len(first[1]) == 2
    assert second[1] == [], "重复传播不得新建任务"
    assert len(_read_tasks(code_root)) == 2


def test_illegal_version_kind_rejected(code_root: Path) -> None:
    """**AC-06**：`version_kind` 不在三类版本事件内 → `IllegalTransition`。"""
    _seed(code_root, [_claim(status="pending_verification")])
    with pytest.raises(transition_mod.IllegalTransition):
        transition_mod.on_superseded(
            code_root, "clm-1", "bogus_kind", recorded_at=LATER, forward_closure_fn=_closure_fn
        )


def test_superseded_is_terminal_via_cli(code_root: Path) -> None:
    """**AC-06**：`superseded` 终态 → 再迁移 CLI **exit 1**。"""
    _seed(code_root, [_claim(status="superseded")])
    proc = _cli(code_root, "--claim-id", "clm-1", "--to", "supported")
    assert proc.returncode == 1, proc.stderr
    assert "IllegalTransition" in proc.stderr


# ───────────────────────── 边界：序倒挂 / 时间倒挂 ─────────────────────────


def test_non_advancing_recorded_seq_rejected(code_root: Path) -> None:
    """**AC-06 序倒挂**：显式 `recorded_seq` 不大于现有最大 → `IllegalTransition`。"""
    _seed(code_root, [_claim()])
    with pytest.raises(transition_mod.IllegalTransition):
        transition_mod.transition(
            code_root, "clm-1", "pending_verification", recorded_at=LATER, recorded_seq=1
        )


def test_time_inversion_rejected(code_root: Path) -> None:
    """**AC-06 时间倒挂**：`recorded_at` 早于原版本 `first_seen_at` → `IllegalTransition`。"""
    _seed(code_root, [_claim()])
    earlier = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(transition_mod.IllegalTransition):
        transition_mod.transition(
            code_root, "clm-1", "pending_verification", recorded_at=earlier
        )
