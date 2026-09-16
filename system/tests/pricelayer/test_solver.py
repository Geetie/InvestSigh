"""`solver` 单测（`Ch5 §B.1` 多解 / `§B.2` 输出结构 / `§B.3` 分工 / `§B.5` 写目标）。

覆盖 DoD：「`solver` 产出**多组解**（不是单解）、含**区间**与**替代解释**」
+ 「每个守卫**注入违例 → exit 非零**」+ 反向对照。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from schema.models import SolvedVariable

from scripts.pricelayer import SingleSolutionError
from scripts.pricelayer.solver import (
    DEFAULT_DISPLAY_CAP,
    MAX_DISPLAY_CAP,
    CandidateCombination,
    SearchBound,
    SolverError,
    assert_multi_solution,
    load_solution_set_display,
    solve_implied_requirements,
    write_solution_set,
)

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
#: 测试用的正算函数（`Ch5 §B.3`：具体形式设计未给 ⇒ 由调用方注入；此处只求**单调**可测）。
FORWARD = lambda point: point["growth"] * Decimal(100) + point["margin"] * Decimal(10)  # noqa: E731


def _combination(
    combination_id: str,
    solved: SolvedVariable,
    *,
    fixed_growth: str,
    fixed_margin: str,
    bound: tuple[str, str],
    alternatives: list[str] | None = None,
    monotonic_increasing: bool = True,
) -> CandidateCombination:
    fixed = {
        "growth": Decimal(fixed_growth),
        "margin": Decimal(fixed_margin),
        "reinvestment": Decimal("0.25"),
        "risk": Decimal("0.09"),
        "duration": Decimal("5"),
    }
    fixed.pop(solved.value)
    return CandidateCombination(
        combination_id=combination_id,
        solved_variable=solved,
        fixed=fixed,
        solved_bound=SearchBound(Decimal(bound[0]), Decimal(bound[1])),
        alternative_explanations=(
            alternatives if alternatives is not None else ["替代解释甲", "替代解释乙"]
        ),
        monotonic_increasing=monotonic_increasing,
    )


def _candidates() -> list[CandidateCombination]:
    return [
        _combination("C-growth", SolvedVariable.growth, fixed_growth="0", fixed_margin="0.30", bound=("0.10", "0.30")),
        _combination("C-margin", SolvedVariable.margin, fixed_growth="0.20", fixed_margin="0", bound=("0.25", "0.35")),
    ]


def _solve(candidates: list[CandidateCombination] | None = None, **overrides: object):
    kwargs: dict[str, object] = {
        "security_id": "sec_nvda",
        "price_snapshot_id": "SNP-1",
        "current_price": Decimal("23"),
        "candidates": candidates if candidates is not None else _candidates(),
        "forward_price": FORWARD,
        "grid_step": Decimal("0.01"),
        "tolerance": Decimal("1.5"),
        "solution_set_id": "SET-nvda-2026-09-15",
        "computed_at": NOW,
    }
    kwargs.update(overrides)
    return solve_implied_requirements(**kwargs)  # type: ignore[arg-type]


def test_underdetermined_equation_yields_multiple_solutions() -> None:
    """`Ch5 §B.1`：欠定方程 ⇒ **多组解**（本用例断言 `>= 2`，不是"有一组即可"）。"""
    result = _solve()
    assert result.feasible_count == 2, f"应有 2 组可行解，实得 {result.feasible_count}"
    assert len(result.solutions) == 2
    solved_vars = {s.combination.solved_variable for s in result.solutions}
    assert solved_vars == {SolvedVariable.growth, SolvedVariable.margin}, "两组解解的是不同的第 5 类"
    assert_multi_solution(result)  # 不抛即通过
    for solution in result.solutions:
        assert solution.solved_low is not None and solution.solved_high is not None, "每组解都必须带区间"
        assert solution.combination.alternative_explanations, "每组解都必须带替代解释"
    assert result.notes == [] or all("GRID_CAP" not in n for n in result.notes)


def test_range_reflects_tolerance_band_not_a_fake_point() -> None:
    """`Ch5 §B.2` 的 `range{low,high}`：区间**来自容差带**（不是把点值包装成区间）。

    容差 ±1.5（价格单位）在增长率上 = ±0.015 ⇒ 网格 `0.19/0.20/0.21` 三个点可行 ⇒ `[0.19, 0.21]`。
    """
    result = _solve()
    growth_solution = next(s for s in result.solutions if s.combination.solved_variable is SolvedVariable.growth)
    assert growth_solution.solved_low == Decimal("0.19")
    assert growth_solution.solved_high == Decimal("0.21")
    assert growth_solution.solved_low < growth_solution.solved_high, "区间必须是**真区间**，不是点值"

    margin_solution = next(s for s in result.solutions if s.combination.solved_variable is SolvedVariable.margin)
    assert margin_solution.solved_low == Decimal("0.25")
    assert margin_solution.solved_high == Decimal("0.35")


def test_alternative_explanations_are_required_at_construction() -> None:
    """`Ch5 §B.2` 的 `alternative_explanations` 是**必填**：候选组合缺它 → 响亮失败。"""
    with pytest.raises(SolverError):
        _combination(
            "C-bad", SolvedVariable.growth, fixed_growth="0", fixed_margin="0.30",
            bound=("0.10", "0.30"), alternatives=[],
        )


def test_fixed_classes_must_be_exactly_the_other_four() -> None:
    """`Ch5 §B.4`："固定其余 4 类，解第 5 类" —— 固定类不合法即拒绝。"""
    with pytest.raises(SolverError):
        CandidateCombination(
            combination_id="C-bad",
            solved_variable=SolvedVariable.growth,
            fixed={"margin": Decimal("0.3")},          # 只有 1 类，缺 3 类
            solved_bound=SearchBound(Decimal("0"), Decimal("1")),
            alternative_explanations=["x"],
        )


def test_single_solution_is_rejected_at_presentation() -> None:
    """★ `Ch5 §B.1` 的核心：只有 1 组可行解 → **拒绝呈现**（`SingleSolutionError`）。"""
    only_one = [
        _combination("C-growth", SolvedVariable.growth, fixed_growth="0", fixed_margin="0.30", bound=("0.10", "0.30")),
        _combination("C-margin", SolvedVariable.margin, fixed_growth="0.20", fixed_margin="0", bound=("0.90", "1.00")),
    ]
    result = _solve(only_one)
    assert result.feasible_count == 1
    assert result.degraded is True, "可行解不足下限 ⇒ degraded（不静默）"
    assert any("SINGLE_SOLUTION_RISK" in n for n in result.notes)
    with pytest.raises(SingleSolutionError):
        assert_multi_solution(result)


def test_reverse_control_two_solutions_pass_presentation_gate() -> None:
    """反向对照：两组解时 `assert_multi_solution` **放行**（守卫不是恒红）。"""
    assert_multi_solution(_solve())


def test_display_cap_folds_extra_solutions_and_records_note() -> None:
    """`Ch5 §I.2` / B18：超出展示上限 → 折叠 + 显式 note（不静默丢弃）。"""
    result = _solve(display_cap=1)
    assert len(result.solutions) == 1
    assert len(result.folded) == 1
    assert any("SOLUTION_SET_FOLDED" in n for n in result.notes)


def test_display_cap_upper_bound_is_enforced() -> None:
    """B18："最多 5 组" —— 越界即拒绝（不把上限当建议）。"""
    with pytest.raises(SolverError):
        _solve(display_cap=MAX_DISPLAY_CAP + 1)
    assert DEFAULT_DISPLAY_CAP == 3, "B18 已确认：默认展示 3 组"


def test_grid_cap_exceeded_is_noted_not_silent() -> None:
    """`Ch5 §I.2`："设网格上限告警" —— 网格超限必须留痕（不得静默截断）。"""
    result = _solve(max_grid_points=3)
    assert any("GRID_CAP_EXCEEDED" in n for n in result.notes)


def test_non_positive_price_is_rejected() -> None:
    with pytest.raises(SolverError):
        _solve(current_price=Decimal("0"))


def test_to_implied_requirements_matches_ch5_b2_structure() -> None:
    """`Ch5 §B.2` 输出结构逐字：字段齐备 + `solved_variable` + `range` + `feasible`。"""
    result = _solve()
    rows = result.to_implied_requirements()
    assert len(rows) == 2
    dumped = [json.loads(row.model_dump_json()) for row in rows]
    for row in dumped:
        assert row["solution_set_id"] == "SET-nvda-2026-09-15"
        assert row["security_id"] == "sec_nvda"
        assert row["price_snapshot_id"] == "SNP-1"
        assert row["solved_variable"] in {v.value for v in SolvedVariable}
        assert row["feasible"] is True
        assert row["method_version"]
        assert row["computed_at"]
        assert set(row["range"]) == {"low", "high"}
        assert row["assumptions"], "五类假设载荷不得为空"
        assert any(v.get("solved") for v in row["assumptions"].values())


def test_write_solution_set_appends_to_implied_requirements(scratch: Path) -> None:
    """落地：`facts/implied_requirements.jsonl` 追加写入（唯一写入口 = `schema.store`）。"""
    written = write_solution_set(scratch, _solve())
    assert written == 2
    rows = [
        json.loads(line)
        for line in (scratch / "facts" / "implied_requirements.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    assert {row["solution_set_id"] for row in rows} == {"SET-nvda-2026-09-15"}


# ───────────────────── CLI：注入违例 → exit 非零 + 反向对照 ─────────────────────


def _row(solution_set_id: str, implied_id: str, *, feasible: bool = True) -> dict[str, object]:
    return {
        "implied_id": implied_id,
        "solution_set_id": solution_set_id,
        "security_id": "sec_nvda",
        "price_snapshot_id": "SNP-1",
        "current_price": "23",
        "assumptions": {"growth": {"value": "0.2"}},
        "solved_variable": "growth",
        "range": {"low": "0.19", "high": "0.21"},
        "alternative_explanations": ["替代解释甲"],
        "feasible": feasible,
        "method_version": "v1",
        "computed_at": "2026-09-15T12:00:00+00:00",
    }


def test_cli_rejects_single_solution_set(
    scratch: Path, write_jsonl, run_script
) -> None:
    """★ 注入违例：解集只有 1 组 → CLI **exit 1**（不是 warn）。"""
    write_jsonl(scratch, "implied_requirements", [_row("SET-one", "IMP-1")])
    proc = run_script("scripts/pricelayer/solver.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "IMPLIED-SINGLE-SOLUTION" in proc.stdout


def test_cli_passes_with_multi_solution_and_no_violation(
    scratch: Path, write_jsonl, run_script
) -> None:
    """反向对照：两组解 + 字段齐备 → CLI **exit 0**（守卫不是恒红）。"""
    write_jsonl(
        scratch,
        "implied_requirements",
        [_row("SET-two", "IMP-1"), _row("SET-two", "IMP-2")],
    )
    proc = run_script("scripts/pricelayer/solver.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESULT: PASS" in proc.stdout


def test_cli_rejects_missing_alternative_explanations(
    scratch: Path, write_jsonl, run_script
) -> None:
    """注入违例：某行无替代解释 → exit 1（`Ch5 §B.2`）。"""
    bad = _row("SET-two", "IMP-1")
    bad["alternative_explanations"] = []
    write_jsonl(scratch, "implied_requirements", [bad, _row("SET-two", "IMP-2")])
    proc = run_script("scripts/pricelayer/solver.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "IMPLIED-NO-ALTERNATIVE" in proc.stdout


# ───────── 规则↔代码绑定：**在真 rules/valuation-methods.yaml 上**（防硬编码）─────────


def test_real_rules_solution_set_display_values(scratch: Path, real_rules) -> None:
    """★ 展示上限**读**真文件（B18：默认 3 / 最多 5）；多解下限由 `must_show_multiple` 派生。"""
    real_rules(scratch, "valuation-methods.yaml")
    display = load_solution_set_display(scratch)
    assert display.value_source == "rules"
    assert (display.default_count, display.max_count) == (3, 5)
    assert display.must_show_multiple is True
    assert display.min_count == 2, "「多」的机械化 = ≥2，由语义键派生（G-06 单一真源）"
    assert display.selection and display.overflow


def test_rule_change_to_must_show_multiple_changes_min_count(scratch: Path, real_rules) -> None:
    """★ 反例/行为绑定：把 `must_show_multiple` 改成 `false` ⇒ 下限降为 1（代码随之改变）。"""
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["solution_set_display"]["must_show_multiple"] = False
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    assert load_solution_set_display(scratch).min_count == 1


def test_rule_change_to_default_count_drives_folding(scratch: Path, real_rules) -> None:
    """★ 行为绑定：`default_count` 由 3 改成 2 ⇒ 求解结果只展示 2 组、其余折叠（**不硬编码 3**）。"""
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"

    # 三组可行解（解不同的第 5 类 + 一个不同固定值的同类解 ⇒ 排序后依次落在 0.19 / 0.20 / 0.25）
    candidates = [
        _combination("C-growth", SolvedVariable.growth, fixed_growth="0", fixed_margin="0.30", bound=("0.10", "0.30")),
        _combination("C-margin", SolvedVariable.margin, fixed_growth="0.20", fixed_margin="0", bound=("0.25", "0.35")),
        _combination("C-growth-2", SolvedVariable.growth, fixed_growth="0", fixed_margin="0.20", bound=("0.10", "0.30")),
    ]

    # 真值（`default_count: 3`）⇒ 三组全展示、零折叠
    on_real_value = _solve(candidates, display=load_solution_set_display(scratch))
    assert (len(on_real_value.solutions), len(on_real_value.folded)) == (3, 0)

    # 规则改成 2 ⇒ 展示 2 组、折叠 1 组（代码跟随规则；折叠而非丢弃）
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["solution_set_display"]["default_count"] = 2
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    display = load_solution_set_display(scratch)
    assert display.default_count == 2

    result = _solve(candidates, display=display)
    assert len(result.solutions) == 2, "展示组数必须跟随 default_count"
    assert len(result.folded) == 1, "超出 default_count 的可行解应折叠，不得丢弃"
    assert any("SOLUTION_SET_FOLDED" in n for n in result.notes)


def test_illegal_display_values_fail_loudly(scratch: Path, real_rules) -> None:
    """★ 反例：`default_count > max_count` → **响亮失败**（不静默夹紧）。"""
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["solution_set_display"]["default_count"] = 9
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    with pytest.raises(Exception, match="取值非法"):
        load_solution_set_display(scratch)


def test_real_rules_solver_ref_points_to_this_module(scratch: Path, real_rules) -> None:
    """真文件的 `assumption_grid.solver_ref` 指向本模块 ⇒ 无绑定违例。"""
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    doc = yaml.safe_load((scratch / "rules" / "valuation-methods.yaml").read_text(encoding="utf-8"))
    assert doc["assumption_grid"]["solver_ref"] == "scripts/pricelayer/solver.py"


def test_cli_clean_on_real_rules_file(scratch: Path, real_rules, run_script) -> None:
    """反向对照：真规则文件 → CLI **exit 0**（无绑定违例），即便 `facts/` 为空。"""
    real_rules(scratch, "valuation-methods.yaml")
    proc = run_script("scripts/pricelayer/solver.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "NO_IMPLIED_ROWS" in proc.stdout
    assert "SOLVER-RULE-BINDING" not in proc.stdout


def test_cli_flags_solver_ref_drift(scratch: Path, real_rules, run_script) -> None:
    """★ 注入违例：规则文件的 `solver_ref` 不再指向本模块 → CLI **exit 1**。"""
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["assumption_grid"]["solver_ref"] = "scripts/pricelayer/solver_v2.py"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/solver.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SOLVER-RULE-BINDING" in proc.stdout


def test_cli_flags_display_count_drift(scratch: Path, real_rules, run_script) -> None:
    """★ 注入违例：规则文件的 `default_count` 与代码回落值不一致 → CLI **exit 1**。"""
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["solution_set_display"]["default_count"] = 4
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/solver.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SOLVER-RULE-BINDING" in proc.stdout


# ── 主理人裁定 ③：`design_default` 必须带 note + 回落值必须绑定（防"规则改了、回落没改"）──


def test_display_fallback_records_source_and_note(scratch: Path) -> None:
    """★ 裁定 ③-1/③-2：缺文件 ⇒ `design_default`，且 note 必须写明**缺的是哪个文件**。"""
    display = load_solution_set_display(scratch)          # scratch 里没有 rules/
    assert display.value_source == "design_default"
    assert display.notes, "design_default 必须打 note（否则单独特调看不出'缺键'）"
    assert "valuation-methods.yaml" in display.notes[0]
    assert (display.default_count, display.max_count) == (DEFAULT_DISPLAY_CAP, MAX_DISPLAY_CAP)
    assert display.must_show_multiple is True


def test_display_real_rules_records_rules_source_without_note(scratch: Path, real_rules) -> None:
    """★ **反向对照（`G-05`）**：真文件**五个字段齐备** ⇒ `rules` 且 **零 note**。

    ★ 这条是第五轮裁定（甲）的**反向对照**：甲把标志收紧为"**全部字段都来自文件**才叫
      `rules`"，其风险是标志**退化成"永远 `design_default`"**（那与"永远 `rules`"一样
      没有信息量）。故必须同时证明"字段齐备时**仍报 `rules`**"。
    """
    real_rules(scratch, "valuation-methods.yaml")
    display = load_solution_set_display(scratch)
    assert display.value_source == "rules"
    assert display.notes == ()


@pytest.mark.parametrize(
    "missing_key",
    ["default_count", "max_count", "must_show_multiple", "selection", "overflow"],
)
def test_display_partial_fallback_downgrades_value_source(
    scratch: Path, real_rules, missing_key: str
) -> None:
    """★ 裁定（第五轮·甲）：删**任一**子键 ⇒ `value_source == "design_default"` **且**点名该子键。

    判据 = "标志的单位必须等于它声称覆盖的单位"：结构内**有**字段不是从文件读到的，
    就不再声称"整块已核"（`V-11` 类别轴 / `G-62` 不可区分）。
    ★ 同时断言**构造不变量**：`notes` 非空 ⟺ `value_source == "design_default"`
      —— 否则"标志为真但无 note"或"有 note 但标志仍称已核"两种不一致都可能出现。
    """
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["solution_set_display"].pop(missing_key)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")

    display = load_solution_set_display(scratch)
    assert display.value_source == "design_default", (
        f"删掉 {missing_key} 后仍有字段不是从文件读到的 ⇒ 不得报 rules（裁定甲）"
    )
    assert display.notes, "design_default 必须打 note（裁定 ③-2）"
    assert any(missing_key in n for n in display.notes), display.notes
    assert (display.notes == ()) is (display.value_source == "rules"), (
        "构造不变量：notes 非空 ⟺ value_source == design_default"
    )


def test_display_fallback_note_distinguishes_the_two_kinds(
    scratch: Path, real_rules
) -> None:
    """★★ 裁定 (甲) 的**附加条件**（主理人第五轮）：两种缺件**在读数上必须可区分**。

    ① **有设计逐字依据**的字段（`default_count`/`max_count`/`must_show_multiple`）
       ⇒ 回落值**真的用了**设计原文里的某个值 ⇒ token = `NOTE_NO_DISPLAY_KEY`，
       note 里要能读出**用的是哪个值**。
    ② **设计里本无逐字值**的标签（`selection`/`overflow`）⇒ 只能给空串，
       **不存在**"被设计认可的默认值" ⇒ token = `NOTE_NO_DISPLAY_LABEL`，
       note 里必须写明**本无**回落值。

    ⇒ 若两者共用一个 token，下游会误以为"有一个**被设计认可过的**默认值被应用了"（`G-62` 不可区分）。
    ⇒ 本用例是**机器绑定**：token 改名 / 两种情形混用 ⇒ **当场红**。

    ★ 反向对照（同文件 `test_display_real_rules_records_rules_source_without_note`）：
      字段齐备 ⇒ 两种 token **一个都不出现**（不得无差别打 note）。
    """
    import yaml

    from scripts.pricelayer.solver import NOTE_NO_DISPLAY_KEY, NOTE_NO_DISPLAY_LABEL

    assert NOTE_NO_DISPLAY_KEY != NOTE_NO_DISPLAY_LABEL, "两种缺件必须用不同 token"

    def _notes_after_dropping(key: str) -> tuple[str, ...]:
        real_rules(scratch, "valuation-methods.yaml")
        path = scratch / "rules" / "valuation-methods.yaml"
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["solution_set_display"].pop(key)
        path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
        return load_solution_set_display(scratch).notes

    # ① 有设计逐字依据 ⇒ 用 NOTE_NO_DISPLAY_KEY，且必须写出"用了哪个回落值"
    for key, code_value in (("default_count", DEFAULT_DISPLAY_CAP), ("max_count", MAX_DISPLAY_CAP)):
        notes = _notes_after_dropping(key)
        hit = [n for n in notes if key in n]
        assert len(hit) == 1, notes
        assert hit[0].startswith(NOTE_NO_DISPLAY_KEY), hit[0]
        assert NOTE_NO_DISPLAY_LABEL not in hit[0], (
            f"{key} 有设计逐字依据，不得标成'本无回落值'：{hit[0]}"
        )
        assert str(code_value) in hit[0], f"note 必须写明用了哪个回落值：{hit[0]}"

    # ② 设计里本无逐字值 ⇒ 用 NOTE_NO_DISPLAY_LABEL，且**不得**声称用了某个回落值
    for key in ("selection", "overflow"):
        notes = _notes_after_dropping(key)
        hit = [n for n in notes if key in n]
        assert len(hit) == 1, notes
        assert hit[0].startswith(NOTE_NO_DISPLAY_LABEL), hit[0]
        assert NOTE_NO_DISPLAY_KEY not in hit[0], (
            f"{key} 在设计里本无逐字值，不得标成'用了设计回落值'：{hit[0]}"
        )
        assert "本无" in hit[0], f"note 必须写明本无回落值：{hit[0]}"

    # ③ 反向对照：字段齐备 ⇒ 两种 token 一个都不出现
    real_rules(scratch, "valuation-methods.yaml")
    clean = load_solution_set_display(scratch)
    assert clean.notes == (), clean.notes
    assert not any(NOTE_NO_DISPLAY_KEY in n or NOTE_NO_DISPLAY_LABEL in n for n in clean.notes)


def test_cli_flags_must_show_multiple_drift(scratch: Path, real_rules, run_script) -> None:
    """★ 裁定 ③-3：`must_show_multiple` 被改而代码回落值未改 → CLI **exit 1**。

    这条是此前**漏掉**的一项绑定（只绑了 `default_count`/`max_count`）——
    `must_show_multiple` 决定多解下限（`min_count` 的派生源），漏绑就等于
    "把'必须多组解'这条设计不变量交给规则文件单方面决定"。
    """
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["solution_set_display"]["must_show_multiple"] = False
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/solver.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SOLVER-RULE-BINDING" in proc.stdout
    assert "must_show_multiple" in proc.stdout


def test_cli_reports_display_source_when_rules_absent(scratch: Path, run_script) -> None:
    """★ 裁定 ③-2 的**出口面**：规则文件缺 ⇒ note 必须**出现在 report 里**（不只活在对象上）。"""
    proc = run_script("scripts/pricelayer/solver.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "NO_SOLUTION_SET_DISPLAY" in proc.stdout
    assert "design_default" in proc.stdout or "display_value_source: 0" in proc.stdout


# ── 第四轮：**缺子键 ≠ 无可比对象**（删 `default_count` / `solver_ref` 也必须是红）──


def test_missing_default_count_is_flagged(scratch: Path, real_rules, run_script) -> None:
    """★ 第四轮反例：**删** `solution_set_display.default_count` ⇒ 必须 `exit 1`。

    旧写法 `if declared_default is not None and int(declared_default) != DEFAULT_DISPLAY_CAP`
    在缺键时 `declared_default is None` ⇒ **静默跳过** ⇒ "展示几组"这一事实从规则面消失、
    而代码仍按回落值 `DEFAULT_DISPLAY_CAP` 展示，门禁却全绿（`G-03`：跳过不是通过）。
    """
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["solution_set_display"].pop("default_count")
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/solver.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SOLVER-RULE-BINDING" in proc.stdout
    assert "default_count 缺失" in proc.stdout


def test_missing_solver_ref_is_flagged(scratch: Path, real_rules, run_script) -> None:
    """★ 同族：删 `assumption_grid.solver_ref` ⇒ 必须 `exit 1`（旧写法 `if ref and …` 静默跳过）。"""
    import yaml

    real_rules(scratch, "valuation-methods.yaml")
    path = scratch / "rules" / "valuation-methods.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["assumption_grid"].pop("solver_ref")
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/solver.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SOLVER-RULE-BINDING" in proc.stdout
    assert "solver_ref 缺失" in proc.stdout
