"""`Ch4 §F` —— **护城河反误判** + 六保护对象 + 四类来源 + **与价格的硬隔离**（逐条正反用例）。

设计锚点（逐字）：

```python
MOAT_EVIDENCE_KINDS = {"persistent_share","pricing_power","cost_advantage",
                       "switching_cost","scale_effect","network_effect"}

def is_durable_moat(moat, claims) -> bool:
    single_point = (moat.only_from({"product_leadership"})
                    or moat.only_from({"supply_scarcity"})
                    or moat.only_from({"high_gross_margin"}))
    if single_point:
        return False                                       # N4.3-06：单点证据不足以认定
    kinds = evidence_kinds(moat, claims) & MOAT_EVIDENCE_KINDS
    return (moat.mechanism_explained
            and len(kinds) >= 2                            # 需证据组合（≥2 类）
            and moat.cross_generation_survival is True
            and moat.origin_class != "supply_demand_cycle")  # 非周期性
```

★ `§F.3` 的三条硬隔离断言（设计明写"可直接写单测"）各配一条用例：

| 断言 | 用例 |
|---|---|
| A1 `MoatInput` **不含**任何 price/return 字段 | `test_a1_*`（含**判别力**对照组） |
| A2 拒绝 `evidence_claims` 引用价格快照的条目 | `test_a2_*` |
| A3 写路径 ∈ `{research_skill, human}`（不含 `price_ingest`） | `test_a3_*` |

★ `is_durable_moat` 的四条判据中三条是**硬否决**，故每条都配"只破坏这一条"的输入，
  使失败可归因到具体判据（而不是"某个输入没过"）。
"""

from __future__ import annotations

import dataclasses

import pytest

from conftest import run_gate_inproc
from scripts.valuelayer import moat_guard
from scripts.valuelayer.moat_guard import (
    FORBIDDEN_MOAT_INPUT_FIELDS,
    MOAT_EVIDENCE_KINDS,
    SINGLE_POINT_KINDS,
    MoatInput,
    assert_no_price_inputs,
    evidence_kinds,
    is_durable_moat,
    moat_level_hint,
    only_from,
    validate_moat,
)
from _fixtures import baseline, claim, write_jsonl, write_rules

CHECKER = "scripts/valuelayer/moat_guard.py"


def _moat(**overrides):
    """一条**够格**的护城河（机制 + 两类持久证据 + 跨代存活 + 非周期）⇒ `is_durable_moat` 为真。"""
    row = {
        "moat_id": "MOAT-1",
        "mechanism": "CUDA 生态 + 装机量带来的迁移成本",
        "protected_objects": [{"object": "cost", "strength": "high", "evidence": ["CLM-2"]}],
        "origin_class": "durable_advantage",
        "cross_generation_survival": True,
        "evidence_claims": ["CLM-2"],
        "writer": "research_skill",
    }
    row.update(overrides)
    return row


def _claims(*kinds: str, claim_id: str = "CLM-2") -> list[dict]:
    return [{"claim_id": claim_id, "moat_evidence_kinds": list(kinds)}]


# ══════════════════════ A1：与价格的**结构性**隔离 ══════════════════════


def test_a1_moat_input_has_no_price_or_return_field() -> None:
    """`§F.3/A1` 逐字：`MoatInput` dataclass **不含**任何 price/return 载体。

    ★ 这是**结构性**断言而非约定：字段集里没有这些载体 ⇒ "股价变化影响护城河判定"
      在**类型层不可表达**（`C45-5`：股价上涨不自动证明护城河增强）。
    """
    assert_no_price_inputs()  # 断言本身不抛
    names = {f.name for f in dataclasses.fields(MoatInput)}
    assert names == {
        "moat_id",
        "mechanism",
        "origin_class",
        "cross_generation_survival",
        "evidence_kinds",
        "writer",
    }
    assert names & FORBIDDEN_MOAT_INPUT_FIELDS == set()


def test_a1_assertion_is_load_bearing(monkeypatch) -> None:
    """★ **判别力对照**：把任一禁入字段塞进字段集 ⇒ A1 的断言必须当场抛。

    ★ 为什么需要这条：只看 `test_a1_moat_input_has_no_price_or_return_field` 的话，
      一个永远不抛的 `assert_no_price_inputs()`（例如 `return None`）也能骗过它 ——
      那正是"守卫看着在、其实不设防"的形态（`R-06 ③`）。
    """

    class _FakeField:
        name = "price"

    monkeypatch.setattr(moat_guard, "fields", lambda _cls: [_FakeField()])
    with pytest.raises(AssertionError, match="A1"):
        moat_guard.assert_no_price_inputs()


def test_forbidden_field_names_are_exactly_the_design_list() -> None:
    assert FORBIDDEN_MOAT_INPUT_FIELDS == {"price", "return", "snapshot", "quote", "past_performance"}


# ══════════════════════ A2：证据不得来自行情 ══════════════════════


def test_a2_rejects_evidence_claim_that_is_a_price_snapshot() -> None:
    """`§F.3/A2`：`evidence_claims` 里出现价格快照 id ⇒ `MoatPriceContamination`。"""
    problems = validate_moat(_moat(evidence_claims=["PRICE-SNAP-1"]), price_snapshot_ids=["PRICE-SNAP-1"])
    assert problems and "MoatPriceContamination" in problems[0]
    assert "PRICE-SNAP-1" in problems[0]


def test_a2_uses_set_membership_not_a_keyword_match() -> None:
    """★ 判据是**集合成员判定**，不是"id 里含 price 字样"（`R-06 ①` 禁关键词式判据）。

    一个**名字里带 price 但不是价格快照**的 claim ⇒ 不得被判污染；
      而一个名字里没有 price 字样、却在快照集合里的 id ⇒ 必须被判污染。
    """
    ok = validate_moat(_moat(evidence_claims=["CLM-pricey-story"]), price_snapshot_ids=["PRICE-SNAP-1"])
    assert ok == []

    bad = validate_moat(_moat(evidence_claims=["SNAP-42"]), price_snapshot_ids=["SNAP-42"])
    assert any("MoatPriceContamination" in p for p in bad)


# ══════════════════════ A3：写路径白名单 ══════════════════════


@pytest.mark.parametrize("writer", ["research_skill", "human"])
def test_a3_accepts_the_two_allowed_writers(writer) -> None:
    assert validate_moat(_moat(writer=writer)) == []


def test_a3_rejects_price_ingest_as_writer() -> None:
    """`§F.3/A3`：`price_ingest` 等写路径**不得**写入 moat。"""
    problems = validate_moat(_moat(writer="price_ingest"))
    assert any("research_skill" in p for p in problems)


def test_a3_rejects_a_missing_writer_too() -> None:
    """★ allowlist 默认拒绝（`R-06 ⑤`）：`§F.3` 的断言是 `writer ∈ {…}`，而 `None` **不在**集合内。

    ★ 为什么不能"没写就不查"：那会让"忘了填 writer"成为一种绕过 A3 的方式。
    """
    assert validate_moat(_moat(writer=None)) != []


def test_a3_allowlist_is_the_same_source_as_the_schema_enum() -> None:
    """`G-06`：白名单**与 `schema.models.MoatWriter` 同源**，不另抄一份。"""
    from schema.models import MoatWriter

    from scripts.valuelayer.moat_guard import _writer_allowlist

    assert _writer_allowlist() == frozenset(m.value for m in MoatWriter)


# ══════════════════════ 反误判：四条判据逐条硬否决 ══════════════════════


def test_durable_moat_requires_two_evidence_kinds() -> None:
    """判据③：落在 `MOAT_EVIDENCE_KINDS` 内的类别 **≥ 2**（"需证据组合"）。"""
    assert is_durable_moat(_moat(), _claims("persistent_share")) is False
    assert is_durable_moat(_moat(), _claims("persistent_share", "switching_cost")) is True


@pytest.mark.parametrize("label", SINGLE_POINT_KINDS)
def test_single_point_evidence_is_never_a_durable_moat(label) -> None:
    """★ 判据①（`N4.3-06`）：**单点证据**（产品领先 / 供给稀缺 / 高毛利）单独出现 ⇒ 一律不认定。

    这三个标签的共同点：它们都可以在**一个景气周期内**成立而**不构成**长期壁垒
      （紧缺时高毛利、供给恢复即消失）。
    """
    assert is_durable_moat(_moat(), _claims(label)) is False


def test_single_point_check_also_applies_when_it_is_the_only_kind_among_many() -> None:
    """**边界**：单点标签**混在**多个标签里时不再单独触发"单点否决"（伪码是 `only_from`）。

    ★ 注意 `product_leadership` 本身**不在** `MOAT_EVIDENCE_KINDS` 内 ⇒ 它不参与"≥2 类"计数；
      故本条要凑够两类持久证据，必须另加两个**在集合内**的类别。
    """
    assert is_durable_moat(
        _moat(), _claims("product_leadership", "switching_cost", "persistent_share")
    ) is True


def test_only_from_requires_non_empty_evidence() -> None:
    """★ `G-03`：空集 ⊆ 任何集合都成立 ⇒ 若允许空集，"一点证据都没有"会被判成"单点证据"。

    那会**歪打正着地**返回 False（结论对、理由错）。本实现让空证据明确返回 `False`。
    """
    assert only_from([], {"product_leadership"}) is False
    assert only_from(["product_leadership"], {"product_leadership"}) is True
    assert only_from(["a", "b"], {"a"}) is False


def test_unknown_evidence_kind_does_not_count_toward_the_two() -> None:
    """判据③是 **allowlist 式**：未列出的类别不计入（`R-06 ⑤`）⇒ 不可靠堆词凑够两类。"""
    assert is_durable_moat(_moat(), _claims("persistent_share", "某个还没人定义过的类别")) is False


def test_cross_generation_unknown_is_not_the_same_as_true() -> None:
    """判据④：`cross_generation_survival is True` —— `None`（unknown）**不算** `True`（三值语义）。

    ★ 输入刻意只破坏这一条（机制在、两类证据齐、非周期）⇒ 失败可**归因**到该判据。
    """
    evidence = _claims("persistent_share", "scale_effect")
    assert is_durable_moat(_moat(cross_generation_survival=None), evidence) is False
    assert is_durable_moat(_moat(cross_generation_survival=True), evidence) is True
    assert is_durable_moat(_moat(cross_generation_survival=False), evidence) is False


def test_supply_demand_cycle_is_not_a_durable_moat() -> None:
    """判据⑤：`origin_class != "supply_demand_cycle"`（`§F.2` 表：紧缺时高毛利、供给恢复即消失）。"""
    row = _moat(origin_class="supply_demand_cycle")
    assert is_durable_moat(row, _claims("persistent_share", "scale_effect")) is False


def test_mechanism_must_be_substantive() -> None:
    """`§F.1`：`mechanism` 必填（`N4.3-01`）；空白即"没给"（不判长度/关键词 —— 那是主观质量）。"""
    assert is_durable_moat(_moat(mechanism="   "), _claims("persistent_share", "scale_effect")) is False
    assert validate_moat(_moat(mechanism="")) != []


def test_origin_class_is_required_by_the_validator() -> None:
    """`§F.1/§F.2`：四类来源区分是**反误判的判据字段** ⇒ 缺它就没法判"是否周期性"。"""
    assert any("origin_class" in p for p in validate_moat(_moat(origin_class=None)))


def test_switching_cost_can_come_from_a_disclosed_real_substitute() -> None:
    """`evidence_kinds` 来源之二（`N4.3-03/04`）：`real_substitutes[].switching_cost` 已披露 ⇒ 计入。"""
    row = _moat(real_substitutes=[{"substitute": "自研 ASIC", "switching_cost": "高"}])
    assert "switching_cost" in evidence_kinds(row, [])


def test_tbd_switching_cost_does_not_count() -> None:
    """★ `tbd` 是"未披露"的占位 ⇒ 未披露的切换成本**不构成**类别证据（`G-03` 同族）。"""
    row = _moat(real_substitutes=[{"substitute": "自研 ASIC", "switching_cost": "tbd"}])
    assert "switching_cost" not in evidence_kinds(row, [])


def test_evidence_kinds_only_reads_claims_that_are_referenced() -> None:
    """只读 `evidence_claims` 引用到的主张 —— 未引用的主张**不得**替本条背书。"""
    rows = _claims("persistent_share", claim_id="CLM-OTHER")
    assert evidence_kinds(_moat(evidence_claims=["CLM-2"]), rows) == frozenset()


def test_evidence_kinds_are_a_closed_set() -> None:
    assert MOAT_EVIDENCE_KINDS == {
        "persistent_share",
        "pricing_power",
        "cost_advantage",
        "switching_cost",
        "scale_effect",
        "network_effect",
    }


def test_moat_level_hint_is_three_levels_and_not_a_score() -> None:
    """`§H.4①`：水平三档 `weak|moderate|strong`（**不是**打分，`纪律 7` / `P-09`）。"""
    assert moat_level_hint(_moat(), _claims("persistent_share", "switching_cost")) == "strong"
    assert moat_level_hint(_moat(cross_generation_survival=None), _claims("persistent_share")) == "moderate"
    assert moat_level_hint(_moat(), []) == "weak"


# ══════════════════════ 门禁入口 `check()`（需要真文件） ══════════════════════


def test_cli_exits_zero_on_a_durable_moat(code_root) -> None:
    write_rules(code_root)
    write_jsonl(code_root, "claims", [claim("CLM-2", kinds=["persistent_share", "switching_cost"])])
    write_jsonl(code_root, "baselines", [baseline()])
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out
    assert "durable_moat_entries" in out, out


def test_cli_flags_a_price_contaminated_moat(code_root) -> None:
    """★ A2 在 **CLI 出口**上必须是 `exit 1`：价格快照 id 的真源是 `facts/prices.jsonl`。"""
    write_rules(code_root)
    write_jsonl(code_root, "prices", [{"snapshot_id": "PRICE-SNAP-1", "close": "100"}])
    row = baseline()
    row["moat"][0]["evidence_claims"] = ["PRICE-SNAP-1"]
    write_jsonl(code_root, "baselines", [row])
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 1, out
    assert "MoatPriceContamination" in out, out


def test_cli_notes_when_no_price_snapshots_exist(code_root) -> None:
    """★ `G-03`：`facts/prices.jsonl` 为空 ⇒ A2 的判据集合为空 ⇒ **不可核**，必须显式记出。"""
    write_rules(code_root)
    write_jsonl(code_root, "baselines", [baseline()])
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out
    assert "NO_PRICE_SNAPSHOTS" in out, out


def test_cli_reports_no_moat_entries_as_vacuous(code_root) -> None:
    """有 baseline 但 `moat[]` 全空 ⇒ `NO_MOAT_ENTRIES` note（真空成立，**非**"护城河已验证"）。"""
    write_rules(code_root)
    write_jsonl(code_root, "baselines", [baseline(moat=[])])
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 0, out
    assert "NO_MOAT_ENTRIES" in out, out


def test_cli_treats_missing_baselines_source_as_input_error(code_root) -> None:
    write_rules(code_root)
    (code_root / "facts" / "baselines.jsonl").unlink(missing_ok=True)
    code, out = run_gate_inproc(CHECKER, code_root)
    assert code == 2, out
    assert "INPUT-ERROR" in out, out
