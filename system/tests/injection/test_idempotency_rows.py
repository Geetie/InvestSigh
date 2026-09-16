"""批次 10 补漏：claim **写路径的行幂等键**（`Ch9 §3.5` 阶段② = `(source_id, quote_hash)`）。

## 缺陷背景（批次 10 独立审计实测）

「同源 + 同 `quote_hash` ⇒ 同 `claim_id` ⇒ 跳过」这条幂等此前**只在
`scripts/ingest/real_collector.py` 内部成立**；真正的写库路径
（`scripts/guard/executor.py::process_external_text` → `schema.store.append_records`）
**没有行幂等**，于是**同一 claim 反复落库**（审计实测：同一 `claim_id`（AMD）累积到 6 行）。

## 判据必须**有判别力**（`G-16` 的教训：不许有恒真断言）

故本文件成对给出正反两向：

  - **(a)** 同源同 `quote_hash` 重跑 → **不新增行**（`wc -l` 前后对比）；
  - **(b)** 反向对照：**同源不同 `quote_hash`** 或 **同文本不同 `source_id`** →
    **必须新增行**（证明不是"一律不写"）。

断言的锚点是**真源行数**（`facts/claims.jsonl`）与执行器的**显式返回**（`status` / `note`），
不是"内部函数被调用"——后者能被改一行实现绕过（`G-02` 的思路）。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from scripts.guard.executor import (
    NOTE_DUPLICATE_CLAIM,
    STATUS_OK,
    STATUS_SKIPPED,
    process_external_text,
)

CLAIMS_STEM = "claims"


def _claims_path(root: Path) -> Path:
    return root / "facts" / f"{CLAIMS_STEM}.jsonl"


def _line_count(root: Path) -> int:
    """`facts/claims.jsonl` 的有效行数（空行不计）—— (a)/(b) 的 `wc -l` 判据。"""
    path = _claims_path(root)
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _ingest(
    root: Path,
    text: str,
    *,
    source_id: str,
    recorded_seq: int = 1,
    persist: bool = True,
):
    """走**真实入口** `process_external_text`（system_time 三元组显式传入，执行器必填）。"""
    from schema.models import ClaimForm, ClaimNature, SourceTier

    now = datetime.now(timezone.utc)
    return process_external_text(
        root,
        text,
        source_id=source_id,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        tier=SourceTier.primary,
        first_seen_at=now,
        analyzed_at=now,
        recorded_seq=recorded_seq,
        locator="raw/note.txt#L1-L1",
        persist=persist,
    )


# ───────────────────────── (a) 正向：同源同 quote_hash → 不新增行 ─────────────────────────


def test_same_source_same_quote_hash_does_not_append(code_root: Path) -> None:
    """(a) 同源同 `quote_hash` 重跑 → **不新增行**；且第二次**显式**返回 `skipped`（`G-03`）。"""
    text = "NVIDIA data center revenue grew sequentially.\n"

    first = _ingest(code_root, text, source_id="src-A", recorded_seq=1)
    assert first.status == STATUS_OK, f"首次应写入：{first.status!r} note={first.note!r}"
    after_first = _line_count(code_root)
    assert after_first == 1, f"首次应新增 1 行，实得 {after_first}"

    second = _ingest(code_root, text, source_id="src-A", recorded_seq=2)
    after_second = _line_count(code_root)
    assert after_second == after_first, (
        f"★ 同源同 quote_hash 重跑**不得**新增行（缺陷复现点）：{after_first} -> {after_second}"
    )
    assert second.status == STATUS_SKIPPED, (
        f"命中幂等必须**显式**返回 skipped（不得静默当 ok）：status={second.status!r}"
    )
    assert second.note == NOTE_DUPLICATE_CLAIM, f"命中必须带显式 note：{second.note!r}"
    assert second.claim_id == first.claim_id, (
        "同源同文本 ⇒ 同 claim_id；命中应返回同一 claim_id（可复查）"
    )


def test_rerun_many_times_stays_single_row(code_root: Path) -> None:
    """(a) 加固：连续重跑 5 次 → 始终 1 行（审计实测"累积到 6 行"的**直接反例**）。"""
    text = "AMD MI300 guidance reiterated.\n"
    counts: list[int] = []
    for seq in range(1, 6):
        _ingest(code_root, text, source_id="src-AMD", recorded_seq=seq)
        counts.append(_line_count(code_root))
    assert counts == [1, 1, 1, 1, 1], f"重跑 5 次应恒为 1 行，实得 {counts}"


# ───────────────────── (b) 反向对照：不同源 / 不同文本 → 必须新增行 ─────────────────────


def test_same_source_different_quote_hash_appends(code_root: Path) -> None:
    """(b) 反向对照：**同源、不同 `quote_hash`** → 必须新增行（不是"一律不写"）。"""
    a = _ingest(code_root, "文本甲：data center revenue grew.\n", source_id="src-B", recorded_seq=1)
    b = _ingest(code_root, "文本乙：gaming revenue declined.\n", source_id="src-B", recorded_seq=2)
    assert a.status == STATUS_OK and b.status == STATUS_OK, (a.status, b.status)
    assert _line_count(code_root) == 2, "同源不同文本必须各落一行"
    assert a.claim_id != b.claim_id


def test_different_source_id_same_text_appends(code_root: Path) -> None:
    """(b) 反向对照：**同文本、不同 `source_id`** → 必须新增行（键是二元组，不是只看文本）。"""
    text = "同一段原文，来自两个不同来源。\n"
    a = _ingest(code_root, text, source_id="src-C", recorded_seq=1)
    b = _ingest(code_root, text, source_id="src-D", recorded_seq=2)
    assert a.status == STATUS_OK and b.status == STATUS_OK, (a.status, b.status)
    assert _line_count(code_root) == 2, "不同源同文本必须各落一行"
    assert a.claim_id != b.claim_id


# ─────────────────── 既有语义不回归：`persist=False`（纯标注/预演）不做幂等判定 ───────────────────


def test_persist_false_writes_nothing_and_still_returns_ok(code_root: Path) -> None:
    """`persist=False` 的既有语义逐字不变：不写库、仍返回 `ok` + `claim_id`。"""
    before = _line_count(code_root)
    dry = _ingest(code_root, "预演文本（不落库）\n", source_id="src-E", persist=False)
    assert dry.status == STATUS_OK, f"persist=False 不得被幂等改判：{dry.status!r}"
    assert dry.claim_id is not None, "persist=False 仍应返回 claim_id（预演）"
    assert _line_count(code_root) == before, "persist=False 不得写库"


# ─────────────────── 端到端：step 1 处理器重跑 → 幂等且不误判为降级 ───────────────────


def test_ingest_handler_rerun_is_idempotent_not_degraded(code_root: Path) -> None:
    """step 1 处理器对**同一投递文件**重跑：claims 行数不变、`degraded=False`。

    ★ `produced` 只记**本轮真正新写入**（裁定 2 / `G-B10-07`）：
      首跑 `produced` 非空、`skipped == []`；重跑 `produced == []`、命中对象进 `skipped`。
    """
    from scripts.orchestrate.ingest_step import make_ingest_handler

    inbox = code_root / "raw" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "2026-09-15_note_sample.txt").write_text("第一行\n第二行\n", encoding="utf-8")

    handler = make_ingest_handler(code_root)
    first = handler(date(2026, 9, 16), "sample")
    n1 = _line_count(code_root)
    assert n1 == 1, f"首次应落 1 行，实得 {n1}"
    assert first.degraded is False, "首次正常摄入不应降级"
    assert first.produced and first.skipped == [], "首跑：produced 非空、skipped 为空"

    second = handler(date(2026, 9, 16), "sample")
    n2 = _line_count(code_root)
    assert n2 == n1, f"★ 重跑不得新增行：{n1} -> {n2}"
    assert second.degraded is False, "幂等重跑**不是**降级（重跑同日不重复落库是设计行为）"
    assert second.produced == [], "★ 重跑未新写入 → produced 必须为空（produced = 本轮真正新写入）"
    assert second.skipped == first.produced, "★ 命中对象走 skipped，且应与首跑 produced 同一批"


# ───────────── (a) 双跑端到端对照：`G-B10-07` 的正解观测（produced vs skipped）─────────────


def test_run_daily_twice_produced_then_skipped(code_root: Path) -> None:
    """★ (a) 副本上跑两次 `run_daily`：第 1 轮 `produced` 非空且 `skipped==[]`；
    第 2 轮 `produced==[]` 且 `skipped` = 第 1 轮那批 `claim_id` 的集合。

    ★ 打印两次的 `(produced, skipped)` 实测量 —— 这是"幂等 vs 非幂等"的**判别式本体**：
      幂等的正解是两轮观测**不同**（`produced` N→0、`skipped` 0→N）；把它们折进同一字段
      会让两轮观测**完全相同**，`G-B10-07` 要暴露的信号即被重新掩盖。
    """
    from scripts.orchestrate.pipeline import Pipeline

    inbox = code_root / "raw" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "2026-09-15_amd_q2.txt").write_text("AMD MI300 guidance.\n", encoding="utf-8")
    (inbox / "2026-09-16_nvda_q2.txt").write_text("NVIDIA data center revenue.\n", encoding="utf-8")

    pipeline = Pipeline(code_root)
    r1 = pipeline.run_daily(date(2026, 9, 16))
    s1 = next(s for s in r1.steps if s.step == 1)
    n1 = _line_count(code_root)
    print(f"[(a) round1] produced={s1.produced} skipped={s1.skipped} claims_lines={n1}")

    r2 = pipeline.run_daily(date(2026, 9, 16))
    s2 = next(s for s in r2.steps if s.step == 1)
    n2 = _line_count(code_root)
    print(f"[(a) round2] produced={s2.produced} skipped={s2.skipped} claims_lines={n2}")

    assert s1.produced and s1.skipped == [], "首跑：produced 非空、skipped 为空"
    assert n2 == n1, f"★ 重跑不得新增行：{n1} -> {n2}"
    assert s2.produced == [], "★ 重跑：produced 必须为空（本轮未新写入）"
    assert set(s2.skipped) == set(s1.produced), (
        "★ 重跑：skipped 应恰为首跑那批 claim_id（幂等命中的对象引用）"
    )


# ───────────── (b) `G1-05` 修正判据的**双向**对照（只证一边不算，批次 10 `C-03`）─────────────


def _g1_05_empty_execution_reasons(result) -> list[str]:
    """跑 `assert_steps_complete`，只取"空执行"类违例的 reason（隔离判据本体）。"""
    from scripts.orchestrate.pipeline import assert_steps_complete

    return [
        v.reason
        for v in assert_steps_complete(result, {"publish_hook": True, "verify_hook": True})
        if "空执行" in v.reason
    ]


def test_g1_05_still_flags_truly_empty_step() -> None:
    """(b) 反向：桩处理器 `produced=[] 且 skipped=[]` → **仍必须**判"空执行"违例（判据强度**未**削弱）。"""
    from scripts.orchestrate.pipeline import STATUS_OK, RunResult, StepResult

    result = RunResult(
        run_date="2026-09-16",
        scope="full",
        steps=[StepResult(2, "s2", STATUS_OK, produced=[], skipped=[])],
    )
    assert _g1_05_empty_execution_reasons(result), (
        "produced 与 skipped **双空**必须仍被判『空执行』违例（否则判据被削弱）"
    )


def test_g1_05_does_not_flag_idempotent_rerun() -> None:
    """(b) 正向：桩处理器 `produced=[] 但 skipped=["claim-x"]` → **必须不**判"空执行"违例。"""
    from scripts.orchestrate.pipeline import STATUS_OK, RunResult, StepResult

    result = RunResult(
        run_date="2026-09-16",
        scope="full",
        steps=[StepResult(2, "s2", STATUS_OK, produced=[], skipped=["claim-x"])],
    )
    assert _g1_05_empty_execution_reasons(result) == [], (
        "幂等重跑（produced 空但 skipped 非空）**不得**被判『空执行』"
    )

