"""`G-44` 的**机器绑定**：step 5 / step 6 在幂等重跑时必须如实上报 `skipped`。

## 缺陷背景（批次 11 独立审计发现，实测复现）

`scripts/compute/step.py`（step 5）与 `scripts/decision/step.py`（step 6）构造
`StepOutcome(...)` 时**都不设 `skipped`**，而适配器
`chain_steps._declare_incomplete_when_empty` **恰好只包装这两步**（两步 `blocking: true`），
其判据是 `if not outcome.produced and not outcome.skipped and outcome.incomplete_reason is None`。
⇒ 幂等重跑时 `produced=[]`（值已落库、无新增）+ `skipped=[]`
⇒ 适配器**补上** `incomplete_reason` ⇒ 编排器记 `STATUS_GAP` ⇒ **整轮 blocked**。

★ **这是 `4f95c3d` 自己承诺要防的事**：那次改动的 docstring 逐字写了
  "读了 N 个对象、判定均无需追加**不是**空执行"—— 但**机器上不生效**，
  因为承诺的那个字段**从没有人填**。本项目最怕的形态就是"**改了**但不生效"。

## 判据必须**有判别力**（`G-16`：不许有恒真断言）

故本文件成对给出正反两向：

- **(a)** 副本上连跑两次 `run_daily` → 首轮 step 5/6 `produced` 非空 / `skipped` 空；
  **重跑** `status == "ok"`、`produced == []`、`skipped` 非空、`derived_values.jsonl` 行数**不增**、
  且 step 5/6 **不产生任何新 gap**（这是"整轮不再被误判"的直接观测量）。
- **(b)** **反向对照**：清空副本 `facts/prices.jsonl` ⇒ 本步**真的一件都没得做**
  ⇒ `produced == []` **且** `skipped == []` ⇒ **仍然必须**判 `gap` + `status != "ok"`。
  —— 这一条是整单的关键：证明新增的 `skipped` 出口**没有**把"空执行"守卫削弱成恒真。

## 观测量为什么落在"步"上而不是 `result.blocked`

`blocked` 是**整轮**的布尔量。在本批次（张力 `T-08` 的 A 方案）下，step 2/3/4（模型侧未交付）
与 step 7/8（未实现 hook）**恒为 gap 且 `blocking: true`** ⇒ `blocked` **本来就是** `True`，
与 step 5/6 无关。若断言"重跑 `blocked is False`"，那它**在修复前后都是红的**——
一条永远红/永远绿的断言没有判别力（`G-16`）。故本节把成因**拆到步**：
断言的是"step 5/6 是否被误判"，并**同时**打印 `blocked` 的逐条成因（供人工核对）。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from conftest import SYSTEM_ROOT

RUN_DATE = date(2026, 9, 16)
_AGIX = SYSTEM_ROOT / "tests" / "compute" / "fixtures" / "agix_prices.jsonl"
_DEMO = SYSTEM_ROOT / "tests" / "decision" / "fixtures" / "demo_stock_prices.jsonl"

#: `blocking: true` 且在本批次**结构上恒为 gap** 的步（模型侧未交付 / 7/8 未实现）。
#: 它们决定 `result.blocked`，与 step 5/6 的修复无关 —— 故断言必须把它们排除在外。
_STRUCTURALLY_GAPPED = (2, 3, 4, 7, 8)


def _seed_prices(root: Path) -> None:
    """把两条**真实行情夹具**落进副本真源（`facts/prices.jsonl`）：usDEMO（个股）+ usAGIX（基准）。"""
    rows = [
        line
        for fixture in (_AGIX, _DEMO)
        for line in fixture.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    (root / "facts" / "prices.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _seed_benchmark_object(root: Path) -> None:
    """落一条基准**对象**到副本真源：取 `rules/benchmark.yaml` 的**原对象**并补 `security_id`。

    ★ 为什么要补：`rules/benchmark.yaml` 只给 `benchmark_id_param_ref: p01`、**不含** `security_id`；
      而副本行情有 2 个证券 ⇒ `_resolve_security` 无法解析基准证券 ⇒ step 6 无从比较
      （那属于"上游输入不全"，不是本单要测的路径）。
      **不自造任何口径字段**（`return_source` / `fee_deducted_again` … 一律沿用真源），
      只补一个证券指向，避免制造假的口径违例。
    """
    cfg = yaml.safe_load((root / "rules" / "benchmark.yaml").read_text(encoding="utf-8"))
    benchmark = dict((cfg.get("benchmark_objects") or [{}])[0])
    benchmark["security_id"] = "usAGIX"
    (root / "facts" / "benchmarks.jsonl").write_text(
        json.dumps(benchmark, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )


def _lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _step(result, no: int):
    return next(s for s in result.steps if s.step == no)


def _step56_gap_lines(result) -> list[str]:
    """`result.gaps` 里**属于 step 5/6** 的条目（含 `G1-05` 对该两步发射的违例）。

    `gaps` 是 `list[str]`：适配器写的条目形如 `step 5 (…)…`，`assert_steps_complete`
    写的形如 `G1-05 第 5 步（…）…`。两种都要算，否则"误判"会在这一维度上隐身。
    """
    return sorted(
        g for g in result.gaps if any(k in g for k in ("step 5", "step 6", "第 5 步", "第 6 步"))
    )


def _blocking_causes(root: Path, result) -> list[str]:
    """`blocked=True` 的**成因**逐条列出（把整轮布尔量拆到步，避免观测量不可区分）。"""
    cfg = yaml.safe_load((root / "rules" / "pipeline.yaml").read_text(encoding="utf-8"))
    blocking = {int(s["step"]): bool(s.get("blocking")) for s in (cfg.get("steps") or [])}
    return [
        f"step {s.step}（blocking={blocking.get(s.step)}）status={s.status}"
        for s in result.steps
        if blocking.get(s.step) and s.status != "ok"
    ]


def _run_twice(root: Path):
    from scripts.orchestrate.pipeline import Pipeline

    pipeline = Pipeline(root)
    return pipeline.run_daily(RUN_DATE), pipeline.run_daily(RUN_DATE)


# ═══════════════ (a) 正向：幂等重跑不再被误判成"未完成" ═══════════════


def test_rerun_does_not_falsely_declare_step5_and_step6_incomplete(code_root: Path) -> None:
    """★ `G-44` 主判据：连跑两次 `run_daily`，**重跑**的 step 5/6 必须是 `ok` 且带 `skipped`。"""
    _seed_prices(code_root)
    _seed_benchmark_object(code_root)
    derived = code_root / "derived" / "derived_values.jsonl"
    recs = code_root / "facts" / "recommendations.jsonl"

    r1, r2 = _run_twice(code_root)
    s1_5, s1_6 = _step(r1, 5), _step(r1, 6)
    s2_5, s2_6 = _step(r2, 5), _step(r2, 6)
    print(
        f"\n[G-44 round1] blocked={r1.blocked} step5=({s1_5.status},{len(s1_5.produced)},{len(s1_5.skipped)}) "
        f"step6=({s1_6.status},{len(s1_6.produced)},{len(s1_6.skipped)}) derived={_lines(derived)}"
        f"\n[G-44 round2] blocked={r2.blocked} step5=({s2_5.status},{len(s2_5.produced)},{len(s2_5.skipped)}) "
        f"step6=({s2_6.status},{len(s2_6.produced)},{len(s2_6.skipped)}) derived={_lines(derived)}"
        f"\n[G-44 blocked 成因 r1] {_blocking_causes(code_root, r1)}"
        f"\n[G-44 blocked 成因 r2] {_blocking_causes(code_root, r2)}"
        f"\n[G-44 step5/6 gap r1] {_step56_gap_lines(r1)}"
        f"\n[G-44 step5/6 gap r2] {_step56_gap_lines(r2)}"
    )
    derived_after_r1 = _lines(derived)
    recs_after_r1 = _lines(recs)

    # ── 首轮：两处都必须**真的产出**（否则"重跑为空"没有判别力：一个永不写的实现也能骗过） ──
    for no, s in ((5, s1_5), (6, s1_6)):
        assert s.status == "ok", f"首轮 step {no} 应为 ok，实得 {s.status!r}（gap={s.gap}）"
        assert s.produced, f"首轮 step {no} 应真正产出（判别力的前提）"
        assert s.skipped == [], f"首轮 step {no} 不该有幂等命中，实得 {s.skipped}"

    # ── 重跑：`ok` + `produced` 空 + `skipped` 非空 + 落库行数不增 ──
    for no, first, second in ((5, s1_5, s2_5), (6, s1_6, s2_6)):
        assert second.status == "ok", (
            f"★ step {no} 幂等重跑被误判为 {second.status!r}（gap={second.gap}）—— "
            "这正是 G-44：适配器把『已存在故未追加』读成了『空执行』"
        )
        assert second.produced == [], f"step {no} 重跑未新写入 → produced 必须为空"
        assert second.skipped, f"★ step {no} 重跑必须把幂等命中记进 skipped（否则 G1-05 判空执行）"
        assert set(second.skipped) == set(first.produced), (
            f"step {no} 重跑的 skipped 应恰为首轮那批对象："
            f"{sorted(second.skipped)} vs {sorted(first.produced)}"
        )
        assert set(second.produced) & set(second.skipped) == set(), "produced 与 skipped 必须互斥（G-42）"

    assert _lines(derived) == derived_after_r1, "幂等重跑不得新增 derived 行"
    assert _lines(recs) == recs_after_r1, "幂等重跑不得新增 recommendation 行"

    # ── 整轮：step 5/6 **不再贡献任何 gap**（旧缺陷下重跑会多出 4 条：2 条适配器 + 2 条 G1-05） ──
    assert _step56_gap_lines(r1) == [], f"首轮不该有 step 5/6 的 gap：{_step56_gap_lines(r1)}"
    assert _step56_gap_lines(r2) == [], (
        f"★ 重跑不该新增任何 step 5/6 的 gap（G-44 的直接观测量）：{_step56_gap_lines(r2)}"
    )
    # 同时把"blocked 的成因"钉住：它由 step 2/3/4/7/8 决定，**不含** step 5/6。
    for r in (r1, r2):
        causes = _blocking_causes(code_root, r)
        assert [c for c in causes if "step 5" in c or "step 6" in c] == [], f"blocked 成因不该含 step 5/6：{causes}"
        assert any(f"step {n}" in c for c in causes for n in _STRUCTURALLY_GAPPED), (
            "本批次 step 2/3/4/7/8 结构上恒为 gap ⇒ blocked 本就为 True；"
            "若这里不成立，说明用例的前提变了，需要重新评估判据"
        )


# ═══════════ (b) 反向对照：真·空执行仍必须被判"未完成" ═══════════


def test_empty_upstream_still_yields_gap_for_step5_and_step6(code_root: Path) -> None:
    """★ **关键反向对照**：清空副本 `facts/prices.jsonl` ⇒ 本步真的一件都没得做
    ⇒ `produced=[]` **且** `skipped=[]` ⇒ **仍然必须**判 `gap`（不得被 `skipped` 洗成 `ok`）。

    ★ 为什么必须在**编排器级**做这条（而不是只测 handler）：本单新增的出口正是
      `StepOutcome.skipped`，而消费它的判据在 `chain_steps` 的适配器与
      `pipeline.assert_steps_complete` 里。只测 handler 拿不到"判据是否被削弱"这个结论。
    ★ 两轮都要断言：首轮"从没写过"与重跑"写过但这次没输入"都必须判 gap。
    """
    # 刻意**不**写 prices：`facts/prices.jsonl` 由夹具保证存在且为空（`_reset_truth_source`）。
    _seed_benchmark_object(code_root)          # 基准对象在，但行情为空 → 仍然无输入可算
    assert _lines(code_root / "facts" / "prices.jsonl") == 0, "本用例的前提是行情真源为空"

    r1, r2 = _run_twice(code_root)
    for label, r in (("round1", r1), ("round2", r2)):
        for no in (5, 6):
            s = _step(r, no)
            print(f"[G-44 反向 {label}] step {no} status={s.status!r} produced={len(s.produced)} skipped={len(s.skipped)}")
            assert s.produced == [] and s.skipped == [], (
                f"★ 上游一件都没得做 ⇒ step {no} 的 produced/skipped **必须都为空**，"
                f"实得 produced={s.produced} skipped={s.skipped}（不可用 skipped 掩盖空执行）"
            )
            assert s.status == "gap", (
                f"★ 真·空执行必须**仍然**判 gap（{label} step {no}），实得 {s.status!r} —— "
                "若为 ok，说明『空执行』守卫被新增的 skipped 出口削弱成了恒真"
            )
            assert s.gap, f"判 gap 必须给出原因（不静默）：{s}"
        gaps56 = _step56_gap_lines(r)
        assert len(gaps56) >= 2, f"{label}: step 5/6 各应有一条 gap，实得 {gaps56}"


def test_reverse_control_is_exercised_by_the_fixture(code_root: Path) -> None:
    """机制层断言：上面的反向对照**真的**落在"行情为空"这条路径上（防夹具漂移使用例空转）。

    与 `test_fixture_does_not_inherit_runtime_state` 同思路（`G-03`：无被检对象 ≠ 已验证）：
    若哪天 `facts/prices.jsonl` 不再是空，反向对照会变成**空转**（它测的路径根本没走到）。
    """
    price_line = code_root / "facts" / "prices.jsonl"
    assert price_line.exists(), "夹具必须保留 18 个 JSONL（Ch9 §3.3.3 不得增删改名）"
    assert price_line.read_text(encoding="utf-8").strip() == "", "夹具契约：真源从**空**起步"

    from scripts.compute.driver import run_derived

    report = run_derived(code_root)
    assert (report.written_derived_ids, report.skipped_derived_ids) == ([], []), (
        f"空行情下不得有写入/命中：written={report.written_derived_ids} skipped={report.skipped_derived_ids}"
    )
