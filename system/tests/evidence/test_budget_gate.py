"""`budget_gate` 预算闸门测试（`ws/ch6-verify` · DoD AC-05~09）。

覆盖：
- **三类预算取先到者**：时间 / 计算 / 检索各造一个到限场景，断言 `first_binding`；
- **到限行为**：主张 → `pending_verification` **且** 真落**可重入** `VerificationTask`（幂等）；
- **`research_cap` 仅由 importance 决定**：同 importance、不同 tier/quality ⇒ cap 相同（`Ch6 §B.2`）；
- **参数不内置**：走 `freeze.get_param`；缺 `rules/budget.yaml` 且无显式缺省 ⇒ 响亮失败；
- **错误路径**：未知 claim ⇒ `BudgetStateError`（不凭空重建）。

★ 逻辑断言在**本进程内**直调模块（真读夹具副本的 `facts/`）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import SYSTEM_ROOT  # noqa: F401
from schema.models import Claim, ClaimForm, ClaimNature, ClaimStatus, SourceTier
from schema.store import append_records, read_records
from scripts.decision.triage import DecisionView, research_cap
from scripts.evidence.budget_gate import (
    COMPUTE_CLASS,
    RETRIEVAL_CLASS,
    TIME_CLASS,
    BudgetConfigMissing,
    BudgetLimits,
    BudgetStateError,
    BudgetUsage,
    apply_budget_gate,
    evaluate_budget,
    load_budget_limits,
    research_cap_for,
)

_SEED_AT = datetime(2020, 1, 1, tzinfo=timezone.utc)
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_DEADLINE = "2025-12-31T00:00:00+00:00"  # 早于 _NOW ⇒ 时间预算已触限


@pytest.fixture(autouse=True)
def _budget_file_hidden_by_default(code_root: Path) -> None:
    """**默认**把 `rules/budget.yaml` 移走 —— 让本文件回到它写作时的世界。

    ★ 为什么必须这么做（`G-RC-02` / `G-RC-07` 同族，2026-09-17 实测触发）：
      本文件绝大多数用例用 `defaults=` 构造输入，而 `budget_gate._configured_source()`
      的解析顺序是 **`rules/budget.yaml` ＞ `freeze p09` 数值映射 ＞ 显式 `defaults`**。
      该文件于 2026-09-17 落地后，`defaults` 被**整体旁路** ⇒ 13 处用例的**观测输入来源变了**
      （实测 6 条变红），尽管它们要测的性质（比值 / 零值语义 / 显式缺省链）**一点没变**。
      ⇒ 显式声明「本文件默认不需要那个文件」，把"仓库里此刻有没有它"从观测里剔出去。
    ★ 要测**文件在场**的路径，用 `budget_file_present`（见下）。
    """
    (code_root / "rules" / "budget.yaml").unlink(missing_ok=True)


@pytest.fixture()
def budget_file_present(code_root: Path) -> Path:
    """把 `rules/budget.yaml` 从**真仓库**拷回副本 —— 用于测「文件在场 ⇒ 它是第一顺位来源」。

    ★ 与 autouse 的 `_budget_file_hidden_by_default` 配对：一个钉"文件缺失"的路径，
      一个钉"文件在场"的路径。二者缺一，都会有半条分支无人验证（`T-18` 家族）。
    """
    import shutil

    shutil.copy(SYSTEM_ROOT / "rules" / "budget.yaml", code_root / "rules" / "budget.yaml")
    return code_root


def _seed_claim(root: Path, *, status: ClaimStatus = ClaimStatus.pending_verification) -> None:
    """经**唯一写入口**落一条合法 claim（默认 `pending_verification`）。"""
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
                locator="raw/doc.txt#L1-L2",
                status=status,
                occurred_at=_SEED_AT,
                first_seen_at=_SEED_AT,
                recorded_seq=1,
            )
        ],
    )
    raw = root / "raw" / "doc.txt"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("l1\nl2\n", encoding="utf-8")


def _tasks(root: Path) -> list[dict]:
    return read_records(root, "tasks")


def _claims(root: Path) -> list[dict]:
    return [r for r in read_records(root, "claims") if r.get("claim_id") == "c1"]


# ───────────────────────── 三类预算取先到者（AC-05） ─────────────────────────


def test_time_budget_first_reached(code_root: Path) -> None:
    """**AC-05 时间类**：`now >= deadline` ⇒ `exhausted` 且 `first_binding == time`。"""
    _seed_claim(code_root)
    usage = BudgetUsage(now=_NOW, started_at=datetime(2025, 12, 1, tzinfo=timezone.utc))
    out = apply_budget_gate(
        code_root, "c1", importance_class="medium", usage=usage, defaults={"deadline": _DEADLINE}
    )
    assert out.exhausted is True
    assert out.decision.first_binding == TIME_CLASS
    assert out.decision.binding == (TIME_CLASS,)


def test_compute_budget_first_reached(code_root: Path) -> None:
    """**AC-05 计算类**：`model_calls_used >= min(max_model_calls, research_cap)`。"""
    _seed_claim(code_root)
    usage = BudgetUsage(now=_NOW, model_calls_used=5)
    out = apply_budget_gate(
        code_root, "c1", importance_class="medium", usage=usage, defaults={"max_model_calls": 5}
    )
    assert out.exhausted is True
    assert out.decision.first_binding == COMPUTE_CLASS
    assert out.decision.binding == (COMPUTE_CLASS,)


def test_retrieval_budget_first_reached(code_root: Path) -> None:
    """**AC-05 检索类**：`searches_used >= max_searches`。"""
    _seed_claim(code_root)
    usage = BudgetUsage(now=_NOW, searches_used=3)
    out = apply_budget_gate(
        code_root, "c1", importance_class="medium", usage=usage, defaults={"max_searches": 3}
    )
    assert out.exhausted is True
    assert out.decision.first_binding == RETRIEVAL_CLASS
    assert out.decision.binding == (RETRIEVAL_CLASS,)


def test_first_binding_is_highest_utilization_among_reached(code_root: Path) -> None:
    """**取先到者**：多类同时触限 → `first_binding` 取**消耗比最高**者（确定性）。"""
    limits = load_budget_limits(
        code_root,
        importance_class="high",
        defaults={"max_model_calls": 10, "max_searches": 10},
    )
    usage = BudgetUsage(now=_NOW, model_calls_used=10, searches_used=10)
    decision = evaluate_budget(limits, usage)
    assert set(decision.binding) == {COMPUTE_CLASS, RETRIEVAL_CLASS}
    assert decision.first_binding in {COMPUTE_CLASS, RETRIEVAL_CLASS}


# ───────────────────────── 到限行为：pending + 可重入任务（AC-06） ─────────────────────────


def test_limit_keeps_pending_and_enqueues_reentrant_task(code_root: Path) -> None:
    """**AC-06**：到限 ⇒ 主张仍在 `pending_verification` **且** 真落**可重入**核验任务。"""
    _seed_claim(code_root)
    usage = BudgetUsage(now=_NOW, model_calls_used=99)
    out = apply_budget_gate(
        code_root,
        "c1",
        importance_class="low",
        usage=usage,
        defaults={"max_model_calls": 1},
        alt_explanation="替代解释线索：可能为框架采购而非直接订单",
        public_entry="https://example.com/ir",
    )
    assert out.exhausted is True
    assert out.claim_status_before == "pending_verification"
    assert out.status_written is False, "已是 pending_verification（状态机不允许自环）⇒ 不再写状态"
    assert out.task_id is not None

    # 任务真落库，且**可重入**（幂等键 + 输入引用 + 已用预算）
    tasks = _tasks(code_root)
    assert len(tasks) == 1
    task = tasks[0]
    assert task["task_type"] == "verify"
    assert task["status"] == "queued"
    assert task["idempotency_key"] == "verify_budget::c1::compute"
    assert task["input_refs"] == ["c1"]
    assert task["parent_context"]["gate"] == "budget"
    assert task["parent_context"]["budget_used"]["model_calls"] == 99
    assert task["parent_context"]["public_entry"] == "https://example.com/ir"

    # 主张最新版本仍是 pending_verification
    assert _claims(code_root)[-1]["status"] == "pending_verification"

    # **幂等**：重跑同场景 ⇒ 不重复建单
    apply_budget_gate(
        code_root, "c1", importance_class="low", usage=usage, defaults={"max_model_calls": 1}
    )
    assert len(_tasks(code_root)) == 1, "重跑不得重复入队"


def test_refuted_claim_is_transitioned_to_pending(code_root: Path) -> None:
    """到限且主张非 pending ⇒ **调用** `transition`（唯一状态写入者）真迁移；历史行不变。"""
    _seed_claim(code_root, status=ClaimStatus.refuted)
    usage = BudgetUsage(now=_NOW, model_calls_used=99)
    out = apply_budget_gate(
        code_root, "c1", importance_class="low", usage=usage, defaults={"max_model_calls": 1}
    )
    assert out.status_written is True
    assert out.claim_status_before == "refuted"
    rows = _claims(code_root)
    assert len(rows) == 2, "refuted→pending_verification 应追加一个新版本行"
    assert rows[0]["status"] == "refuted", "历史行不得被改（追加式不可变）"
    assert rows[-1]["status"] == "pending_verification"


def test_not_exhausted_has_no_side_effects(code_root: Path) -> None:
    """**反向对照（无误报阻断）**：未到限 ⇒ 不写状态、不建任务。"""
    _seed_claim(code_root)
    usage = BudgetUsage(now=_NOW, model_calls_used=1)
    out = apply_budget_gate(
        code_root, "c1", importance_class="high", usage=usage, defaults={"max_model_calls": 40}
    )
    assert out.exhausted is False
    assert out.task_id is None
    assert _tasks(code_root) == []
    assert len(_claims(code_root)) == 1


# ───────────────────────── research_cap 仅由 importance 决定（AC-07） ─────────────────────────


def test_research_cap_depends_only_on_importance() -> None:
    """**AC-07**：同 importance、不同 tier/quality ⇒ **cap 相同**（`Ch6 §B.2` 逐字禁令）。"""
    assert research_cap_for("high") == 40
    assert research_cap_for("medium") == 15
    assert research_cap_for("low") == 4

    strong = DecisionView(
        claim_id="a",
        tier="primary",
        importance_class="high",
        first_seen_at=_SEED_AT,
        direct_knowledge="direct",
        method_reproducible=True,
        caliber_match=True,
        independent_evidence_count=9,
    )
    weak = DecisionView(
        claim_id="b",
        tier="secondary_tertiary",
        importance_class="high",
        first_seen_at=_SEED_AT,
        direct_knowledge="unknown",
        method_reproducible=False,
        caliber_match=False,
        independent_evidence_count=0,
        strong_counter_evidence=("x",),
    )
    assert research_cap(strong) == research_cap(weak) == research_cap_for("high") == 40


def test_compute_limit_bounded_by_research_cap(code_root: Path) -> None:
    """有效计算上限 = `min(配置, research_cap)`：一手但低重要性也不深挖（`Ch6 §B.2`）。"""
    limits = load_budget_limits(
        code_root, importance_class="low", defaults={"max_model_calls": 9999}
    )
    assert limits.research_cap == 4
    assert limits.compute_limit == 4, "配置再大也被 research_cap 压到 4"


# ───────────────────────── 参数不内置 / 缺配置响亮失败（AC-08/09） ─────────────────────────


def test_missing_budget_config_fails_loud(code_root: Path) -> None:
    """**AC-09 错误路径**：缺 `rules/budget.yaml` 且无显式缺省 ⇒ `BudgetConfigMissing`（不静默兜底）。

    ★ 构成"文件缺失"这个输入的是 autouse 的 `_budget_file_hidden_by_default`（2026-09-17 起）
      —— 于是本用例测的是**缺失路径本身**，而**不是**"仓库里恰好没有它"。
    """
    assert not (code_root / "rules" / "budget.yaml").exists(), "夹具应已移走 budget.yaml"
    with pytest.raises(BudgetConfigMissing, match="budget.yaml"):
        load_budget_limits(code_root, importance_class="high")


def test_explicit_defaults_used_when_file_absent(code_root: Path) -> None:
    """缺文件但给**显式**缺省 ⇒ 走 `explicit_defaults`（另一条确定路径，非静默兜底）。

    ★ 同前：文件缺失由 autouse fixture 制造；`source` 的观测值不得由
      "仓库里此刻有没有这个文件"决定（`G-RC-02` 同族）。
    """
    limits = load_budget_limits(
        code_root, importance_class="high", defaults={"max_model_calls": 7, "max_searches": 2}
    )
    assert limits.source == "explicit_defaults"
    assert limits.compute_limit == 7
    assert limits.search_limit == 2
    assert any("显式" in note for note in limits.notes)


def test_installed_budget_file_is_the_source_of_truth(budget_file_present: Path) -> None:
    """★ **正向对照**（与上面两条配对）：`rules/budget.yaml` **在**时 ⇒ `source` = 该文件。

    ★ 为什么必须补这一条：上面两条都靠"移走文件"来测**缺失分支**；若只有它们，
      文件**真的**落地后就没有任何用例证明"它被优先读取" —— 那等于新文件无人验证
      （`T-18` 家族：写在声明里 ≠ 在机器上有效力）。本用例钉住解析顺序的第 1 顺位。
    """
    code_root = budget_file_present
    assert (code_root / "rules" / "budget.yaml").exists(), "夹具应把 budget.yaml 拷回副本"
    limits = load_budget_limits(code_root, importance_class="high")
    assert limits.source == "rules/budget.yaml", f"应优先取已安装的文件，实得 {limits.source!r}"
    # 三类上限在本文件里取显式降级（`null` ≠ `0`，`G5`）：
    assert limits.deadline is None, "deadline: null ⇒ 不设时间上限"
    assert limits.search_limit is None, "max_searches: null ⇒ 不设检索上限"
    # 计算类：未配置 `max_model_calls` ⇒ 有效上限 = `research_cap`（有确定上界，不是"无上限"）
    assert limits.compute_limit == limits.research_cap, (
        f"未配置 max_model_calls 时应走 research_cap，实得 compute={limits.compute_limit} "
        f"cap={limits.research_cap}"
    )
    assert any("research_cap" in n for n in limits.notes), (
        f"必须如实记 note 说明上限来自 research_cap（不静默）\n{limits.notes}"
    )


def test_unknown_claim_fails_loud(code_root: Path) -> None:
    """**错误路径**：到限但 claim 不存在 ⇒ `BudgetStateError`（不凭空重建）。"""
    usage = BudgetUsage(now=_NOW, model_calls_used=99)
    with pytest.raises(BudgetStateError, match="不凭空重建"):
        apply_budget_gate(
            code_root, "absent", importance_class="low", usage=usage, defaults={"max_model_calls": 1}
        )


# ───────────────────────── ④ G5：`0` = 上限为 0（不得静默当无上限）─────────────────────────


def test_zero_compute_limit_is_not_silently_unbounded(code_root: Path) -> None:
    """**G5 正向（正向对照）**：`max_model_calls: 0` = **上限为 0**（不允许任何调用）⇒ `used=999` 必到限。

    初版 `if limit is not None and limit > 0` 会把 `0` 静默当"无上限"（审计实测 `used=999`、`exhausted=False`）。
    """
    _seed_claim(code_root)
    usage = BudgetUsage(now=_NOW, model_calls_used=999)
    out = apply_budget_gate(
        code_root, "c1", importance_class="high", usage=usage, defaults={"max_model_calls": 0}
    )
    assert out.exhausted is True, "上限为 0 ⇒ 必到限，不得被静默当成无上限"
    assert COMPUTE_CLASS in out.decision.binding
    assert out.decision.first_binding == COMPUTE_CLASS


def test_zero_limit_binds_even_with_zero_usage(code_root: Path) -> None:
    """**G5 边界**：上限为 0 时，**即使 `used=0`** 也已到限（不允许任何调用）。"""
    limits = load_budget_limits(code_root, importance_class="high", defaults={"max_model_calls": 0})
    assert limits.compute_limit == 0
    decision = evaluate_budget(limits, BudgetUsage(now=_NOW, model_calls_used=0))
    assert decision.exhausted is True
    assert COMPUTE_CLASS in decision.binding
    assert decision.ratios[COMPUTE_CLASS] == 1.0, "0 预算 + 0 用量 ⇒ 已达限（比值可判定，不除零）"


def test_zero_search_limit_is_not_silently_unbounded(code_root: Path) -> None:
    """**G5 正向（检索类）**：`max_searches: 0` 同理不得静默。"""
    limits = load_budget_limits(code_root, importance_class="high", defaults={"max_searches": 0})
    assert limits.search_limit == 0
    decision = evaluate_budget(limits, BudgetUsage(now=_NOW, searches_used=3))
    assert decision.exhausted is True
    assert RETRIEVAL_CLASS in decision.binding


def test_none_limit_means_unbounded_not_zero() -> None:
    """**G5 反向对照**：`None` = **未设上限**（≠ 上限为 0）⇒ 不得因 `None` 误报到限。"""
    limits = BudgetLimits(
        deadline=None, compute_limit=None, search_limit=None, research_cap=40, source="test"
    )
    decision = evaluate_budget(
        limits, BudgetUsage(now=_NOW, model_calls_used=999, searches_used=999)
    )
    assert decision.exhausted is False, "None = 未设上限 ⇒ 该类不约束"
    assert decision.ratios[COMPUTE_CLASS] == 0.0
    assert decision.ratios[RETRIEVAL_CLASS] == 0.0


def test_unconfigured_search_limit_is_none(code_root: Path) -> None:
    """**G5 反向（真实取法）**：未配置 `max_searches` ⇒ `search_limit is None`（未设上限，不约束）。"""
    limits = load_budget_limits(
        code_root, importance_class="high", defaults={"max_model_calls": 40}
    )
    assert limits.search_limit is None
    decision = evaluate_budget(limits, BudgetUsage(now=_NOW, searches_used=999))
    assert decision.exhausted is False
    assert RETRIEVAL_CLASS not in decision.binding
