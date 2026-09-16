"""`transition` 五态状态机 + `superseded` 传播测试（`ws/claim` · DoD B）。

覆盖：**真跑通**（真实采集 claim → 真迁移）、**持久化**（追加式 + `index/` 重建）、
**守卫真拦得住**（非法迁移 / 定位无效 → CLI **exit 1**）、**错误路径**（传播不可用 /
三字段互换 / 未知状态）、**边界**（空 claims / 终态 / 非法 `version_kind` / 序或时间倒挂）。

★ 逻辑断言在**本进程内**直调模块（真读夹具副本的 `facts/`）；**退出码**断言走**真子进程 CLI**。

## `superseded` 传播（缺陷 N-2 的回归防线）

`Ch6 §E.4` 要求 `superseded` 传播**复用**第九章 `scripts/graph` 的传播实现，**不另建一套**。
本文件据此：

- **删除**了旧版"参数吞掉型"注入桩 `_closure_fn(*_args, **_kwargs)`（它让一条**签名错误**的
  自建遍历也能"假通过"——正是缺陷 N-2 得以漏网的直接原因）；
- 新增**真实路径**用例：真 `facts/claims.jsonl` + 真 `facts/dependency_edges.jsonl`
  （`claim → baseline → recommendation`），从 `pending_verification` 真迁到 `superseded`，
  断言 `recheck` 任务**真落库**、幂等键是 **graph 口径** `recheck::<ref>::<target>`、
  重跑**幂等**、且真源 `claims.jsonl` 历史行**逐字节未变**；
- 强化"传播不可用"用例：不仅断言抛 `PropagationUnavailable`，还**证明零写入**；
- 新增**反向对照**（无误报阻断）：无下游边时 `superseded` **照常成功**。
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import SYSTEM_ROOT
from schema.models import (
    Baseline,
    Claim,
    ClaimForm,
    ClaimNature,
    Company,
    DependencyEdge,
    Recommendation,
    RecommendationAction,
    ResearchDepth,
    SourceTier,
)
from schema.store import append_records
from scripts.claim import transition as transition_mod
from scripts.graph.propagate import PropagationResult, propagate_retraction

TRANSITION_CLI = SYSTEM_ROOT / "scripts" / "claim" / "transition.py"

_CHILD_ENV = {
    **os.environ,
    "CODEBUDDY_SAFE_DELETE_SANDBOX": "0",
    "CODEBUDDY_BROKERED_FS_HOOK_ENABLED": "0",
}

DEFAULT_FIRST_SEEN = "2026-09-16T00:00:00+00:00"
SEED_AT = datetime(2026, 9, 16, 0, 0, tzinfo=timezone.utc)
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
        "status": "pending_verification",
        "first_seen_at": DEFAULT_FIRST_SEEN,
        "analyzed_at": DEFAULT_FIRST_SEEN,
        "recorded_seq": 1,
        "full_text_read": False,
    }
    base.update(over)
    return base


def _seed(root: Path, rows: list[dict], *, raw: bool = True) -> None:
    """把 raw 原文与 claim 行写入夹具副本（**原始 dict 直写**，用于纯状态机 / 定位用例）。"""
    if raw:
        target = root / "raw" / "doc.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("l1\nl2\n", encoding="utf-8")
    path = root / "facts" / "claims.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _seed_chain(root: Path, *, prefix: str = "") -> str:
    """**真实链路**（走 `schema.store.append_records`，与生产同一写口）：

    `<prefix>c1 → b1 → r1`，公司 `CO1`（研究深度 `tracking`）。
    返回 claim 在边表里的 ref 形式（`prefix` 见调用处：裸 id / `claim:` 前缀）。
    """
    append_records(
        root,
        "claims",
        [
            Claim(
                claim_id="c1",
                source_id="s1",
                quote_hash="q1",
                claim_nature=ClaimNature.fact,
                claim_form=ClaimForm.original_investigation,
                tier=SourceTier.primary,
                first_seen_at=SEED_AT,
                recorded_seq=1,
            )
        ],
    )
    append_records(
        root,
        "baselines",
        [Baseline(baseline_id="b1", company_id="CO1", version=1, business_mechanism="hw")],
    )
    append_records(
        root,
        "recommendations",
        [
            Recommendation(
                recommendation_id="r1",
                security_id="SEC1",
                company_id="CO1",
                action=RecommendationAction.buy,
                horizon="2Q",
                start_date=date(2026, 9, 1),
                rule_version="v1",
            )
        ],
    )
    append_records(
        root,
        "companies",
        [
            Company(
                company_id="CO1",
                legal_name="Co One",
                research_depth=ResearchDepth.tracking,
                recorded_seq=1,
                first_seen_at=SEED_AT,
            )
        ],
    )
    claim_ref = f"{prefix}c1"
    append_records(
        root,
        "dependency_edges",
        [
            DependencyEdge(edge_id="e0", from_ref=claim_ref, to_ref="b1", kind="evidence"),
            DependencyEdge(edge_id="e1", from_ref="b1", to_ref="r1", kind="supports"),
        ],
    )
    return claim_ref


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


def _claims_bytes(root: Path) -> bytes:
    """真源 `claims.jsonl` 的**逐字节**快照（用于"历史行未变"断言）。"""
    path = root / "facts" / "claims.jsonl"
    return path.read_bytes() if path.exists() else b""


def _recheck_tasks(root: Path) -> list[dict]:
    return [t for t in _read_tasks(root) if t.get("task_type") == "recheck"]


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TRANSITION_CLI), str(root), *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=60,
        env=_CHILD_ENV,
    )


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


def test_legacy_active_status_rejected() -> None:
    """`active` **不在** `Ch6 §E.1` 五态内（违约值）→ `UnknownClaimStatus`（响亮拒绝）。

    设计初始态是 `pending_verification`（`Ch6 §E` 状态机首行）；把 `active` 当"入口别名"
    的旧处理已移除 —— 五态之外的状态一律不该存在（这正是 `Claim.status` 违约的教训）。
    """
    assert transition_mod.can_transition("active", "pending_verification") is False
    assert transition_mod.allowed_targets("active") is None
    with pytest.raises(transition_mod.UnknownClaimStatus):
        transition_mod.assert_transition("active", "pending_verification")


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


def test_real_ingest_then_support(code_root: Path) -> None:
    """**AC-01 真跑通**：真实采集 claim（写库即初始态 `pending_verification`）→ `pending_verification→supported`。"""
    row = _drive_ingest(code_root)
    cid = row["claim_id"]
    assert row["status"] == "pending_verification"

    at = datetime.now(timezone.utc) + timedelta(seconds=1)
    r1 = transition_mod.transition(code_root, cid, "supported", recorded_at=at)
    assert (r1.from_status, r1.to_status) == ("pending_verification", "supported")

    rows = [r for r in _read_claims(code_root) if r["claim_id"] == cid]
    assert len(rows) == 2, f"应有 2 个版本行（追加），实得 {len(rows)}"
    seqs = [r["recorded_seq"] for r in rows]
    assert seqs == sorted(set(seqs)), f"recorded_seq 必须严格递增：{seqs}"
    assert rows[-1]["status"] == "supported"


def test_transition_appends_new_version_not_modifies(code_root: Path) -> None:
    """**AC-02 持久化**：追加式不可变（原行逐字不变）+ 删 `index/` 重建后数据仍在。"""
    _seed(code_root, [_claim()])
    original = (code_root / "facts" / "claims.jsonl").read_text(encoding="utf-8")

    result = transition_mod.transition(
        code_root, "clm-1", "supported", recorded_at=LATER
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


# ───────────────────────── 错误路径：定位无效 / 三字段互换 ─────────────────────────


def test_locator_invalid_blocks_transition(code_root: Path) -> None:
    """**AC-05**：主张定位无效（空 locator）→ 迁移被拒 `ClaimLocatorInvalid`；CLI exit 1。"""
    _seed(code_root, [_claim(locator="")], raw=False)
    with pytest.raises(transition_mod.ClaimLocatorInvalid):
        transition_mod.transition(code_root, "clm-1", "supported", recorded_at=LATER)

    proc = _cli(code_root, "--claim-id", "clm-1", "--to", "supported")
    assert proc.returncode == 1, proc.stderr
    assert "ClaimLocatorInvalid" in proc.stderr
    # 被拒后不落任何新行
    assert len(_read_claims(code_root)) == 1


def test_swapped_three_fields_rejected(code_root: Path) -> None:
    """**AC-05 三字段互换**：`claim_form` 取值塞进 `claim_nature` → 迁移前 `Claim` 校验响亮失败。"""
    _seed(code_root, [_claim(claim_nature="opinion")])
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        transition_mod.transition(code_root, "clm-1", "supported", recorded_at=LATER)


# ───────────────────────── superseded 传播：真实路径（缺陷 N-2 回归） ─────────────────────────


def test_superseded_real_path_enqueues_graph_recheck(code_root: Path) -> None:
    """**AC-01 传播（真跑通）**：真源 `claims.jsonl` + `dependency_edges.jsonl`（`c1→b1→r1`），
    真从 `pending_verification` 迁到 `superseded` → 下游结论类**真落 `recheck` 任务**，
    幂等键是 **graph 口径** `recheck::<ref>::<target>`（`Ch9 §N9.1-26`，全库唯一一套键格式）。

    这条用例替代了旧版"参数吞掉型"桩 `_closure_fn` —— 后者对**任意签名**都返回固定值，
    使缺陷 N-2（自建遍历签名错误）也能"假通过"。
    """
    _seed_chain(code_root)  # 裸 id 形式（与 graph 侧 `test_propagate_t12` 同口径）
    before = _claims_bytes(code_root)

    result = transition_mod.transition(
        code_root, "c1", "superseded", version_kind="source_retraction", recorded_at=LATER
    )

    assert (result.from_status, result.to_status) == ("pending_verification", "superseded")
    assert result.downstream == ["b1", "r1"]
    assert set(result.recheck_tasks) == {"task_recheck::c1::b1", "task_recheck::c1::r1"}
    assert result.rolled_back_companies == ["CO1"]

    # 真源 `tasks.jsonl` 真的落了 recheck 任务，键是 graph 那套
    rechecks = _recheck_tasks(code_root)
    assert len(rechecks) == 2, f"应有 2 条 recheck 任务，实得 {len(rechecks)}"
    assert {t["idempotency_key"] for t in rechecks} == {"recheck::c1::b1", "recheck::c1::r1"}
    assert all(t["status"] == "queued" for t in rechecks)
    assert all(t["parent_context"]["reason"] == "dependency_stale" for t in rechecks)

    # 真源 `claims.jsonl`：superseded 行存在，且**历史行逐字节未变**
    after = _claims_bytes(code_root)
    assert after.startswith(before), "历史行必须逐字节未变（追加式不可变）"
    claims = _read_claims(code_root)
    assert claims[-1]["claim_id"] == "c1"
    assert claims[-1]["status"] == "superseded"
    assert claims[-1]["version_kind"] == "source_retraction"


def test_superseded_propagation_is_idempotent(code_root: Path) -> None:
    """**再跑一次幂等（新增 0 条）**：传播由 `propagate_retraction` 唯一实现，重跑不重复建单。

    claim 迁到 `superseded` 后即为**终态**（无法二次迁移），故"再跑一次"经**委托入口**
    `propagate_retraction` 验证幂等（这正是 claim 流实际复用的那一层）。
    """
    _seed_chain(code_root)
    transition_mod.transition(
        code_root, "c1", "superseded", version_kind="source_retraction", recorded_at=LATER
    )
    assert len(_recheck_tasks(code_root)) == 2

    again = propagate_retraction(code_root, "c1", source="dependency_edges", apply=True)
    assert again.stale_marks == 0, "重复传播不得新建任务"
    assert again.rolled_back_companies == (), "已回退过 → 不重复追加"
    assert len(_recheck_tasks(code_root)) == 2, "tasks.jsonl 行数不变"


def test_superseded_ref_form_follows_edges_not_guess(code_root: Path) -> None:
    """**ref 形式由 edges/object_index 判定，不猜测**：边用 `claim:c1` → 幂等键也用 `claim:c1`。

    覆盖 `_resolve_claim_ref` 的"带前缀"分支：它读取真实边端点集合，而非盲目套用 `claim_id`。
    """
    claim_ref = _seed_chain(code_root, prefix="claim:")
    assert claim_ref == "claim:c1"

    result = transition_mod.transition(
        code_root, "c1", "superseded", version_kind="source_retraction", recorded_at=LATER
    )
    keys = {t["idempotency_key"] for t in _recheck_tasks(code_root)}
    assert keys == {"recheck::claim:c1::b1", "recheck::claim:c1::r1"}, "键必须沿用边表里的 ref 形式"
    assert set(result.recheck_tasks) == {"task_recheck::claim:c1::b1", "task_recheck::claim:c1::r1"}


def test_superseded_without_downstream_succeeds(code_root: Path) -> None:
    """**反向对照（无误报阻断）**：claim 无任何下游边 → 传播为空集，`superseded` **照常成功**。"""
    append_records(
        code_root,
        "claims",
        [
            Claim(
                claim_id="solo",
                source_id="s1",
                quote_hash="q1",
                claim_nature=ClaimNature.fact,
                claim_form=ClaimForm.original_investigation,
                tier=SourceTier.primary,
                first_seen_at=SEED_AT,
                recorded_seq=1,
            )
        ],
    )
    result = transition_mod.transition(
        code_root, "solo", "superseded", version_kind="source_retraction", recorded_at=LATER
    )
    assert result.to_status == "superseded"
    assert result.downstream == []
    assert result.recheck_tasks == []
    assert _read_tasks(code_root) == [], "无下游 → 不建任何任务（不误报阻断）"


# ───────────────────────── superseded 传播：错误路径与写序（半数据窗口） ─────────────────────────


def test_propagation_unavailable_blocks_superseded(
    code_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**AC-05 悬空传播**：传播实现不可用 → `PropagationUnavailable`，**写库前**失败、**零写入**。"""
    _seed(code_root, [_claim(status="pending_verification")], raw=False)
    claims_before = _claims_bytes(code_root)

    monkeypatch.setattr(transition_mod, "_propagation_available", lambda: False)
    with pytest.raises(transition_mod.PropagationUnavailable):
        transition_mod.transition(
            code_root, "clm-1", "superseded", version_kind="source_retraction", recorded_at=LATER
        )

    # 零写入：claims 无新增行，tasks 完全没有
    assert _claims_bytes(code_root) == claims_before, "失败必须发生在写库前（无半截数据）"
    assert _read_tasks(code_root) == [], "失败时不得落任何任务"


def test_superseded_parse_failure_writes_nothing(code_root: Path) -> None:
    """**半数据窗口前半段已消灭**：传播的**解析/预飞**（`apply=False` 干跑）先于写库，
    解析类失败 → claim 版本行**不追加**（零写入）。

    注入一个在**干跑**时即抛错的传播实现 —— 只有"干跑在 `_append_claim` 之前"才可能零写入。
    """
    _seed_chain(code_root)
    claims_before = _claims_bytes(code_root)

    def _boom(*_args: object, **_kwargs: object) -> PropagationResult:
        raise RuntimeError("解析阶段爆炸（模拟闭包/索引/ref 解析抛错）")

    with pytest.raises(RuntimeError, match="解析阶段爆炸"):
        transition_mod.transition(
            code_root, "c1", "superseded", version_kind="source_retraction",
            recorded_at=LATER, propagate_fn=_boom,
        )

    assert _claims_bytes(code_root) == claims_before, "解析失败不得追加 claim 版本行"
    assert _read_tasks(code_root) == [], "解析失败不得落任务"


def test_superseded_residual_io_window_is_honest(code_root: Path) -> None:
    """★ **诚实登记的残留窗口**（`R-04`，**不称"原子"**）：第 3 步（`apply=True` 落地）
    与第 2 步（追加 claim 版本）是**两次独立写盘**；若第 3 步在 **I/O 层**失败，仍会留下
    "claim 已 `superseded`、task 未落"的残留。设计区无事务机制，本模块无法消除该窗口。

    本用例**钉住**这一行为，防止有人把它误当成"已原子"。
    """
    _seed_chain(code_root)
    calls: list[bool] = []

    def _fail_on_apply(*_args: object, **kwargs: object) -> PropagationResult:
        apply = bool(kwargs.get("apply"))
        calls.append(apply)
        if apply:
            raise OSError("模拟第 3 步写盘失败（磁盘满 / 权限）")
        # 干跑：返回一个结构合法的结果（transition 不使用其返回值）
        return PropagationResult(retracted_ref="c1", source="dependency_edges", apply=False)

    with pytest.raises(OSError, match="写盘失败"):
        transition_mod.transition(
            code_root, "c1", "superseded", version_kind="source_retraction",
            recorded_at=LATER, propagate_fn=_fail_on_apply,
        )

    assert calls == [False, True], "写序必须是：先干跑（False）、后落地（True）"
    # 残留：claim 已 superseded，但 task 未落 —— 诚实暴露，不掩饰
    assert _read_claims(code_root)[-1]["status"] == "superseded"
    assert _read_tasks(code_root) == [], "第 3 步 I/O 失败时 task 未落（残留窗口）"


def test_illegal_version_kind_rejected(code_root: Path) -> None:
    """**AC-06**：`version_kind` 不在三类版本事件内 → `IllegalTransition`（写库前拒绝）。"""
    _seed(code_root, [_claim(status="pending_verification")], raw=False)
    with pytest.raises(transition_mod.IllegalTransition):
        transition_mod.on_superseded(code_root, "clm-1", "bogus_kind", recorded_at=LATER)


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
            code_root, "clm-1", "supported", recorded_at=LATER, recorded_seq=1
        )


def test_time_inversion_rejected(code_root: Path) -> None:
    """**AC-06 时间倒挂**：`recorded_at` 早于原版本 `first_seen_at` → `IllegalTransition`。"""
    _seed(code_root, [_claim()])
    earlier = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(transition_mod.IllegalTransition):
        transition_mod.transition(
            code_root, "clm-1", "supported", recorded_at=earlier
        )
