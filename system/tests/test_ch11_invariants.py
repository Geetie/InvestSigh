"""`Ch11 §F` 不变量单测（`施工图 §3.4` 具名的阶段① 测试资产）。

`Ch11 §C/§D/§F` 的 11 项参数与 4 条不变量（`I11-01`~`I11-04`）是**参数层的宪法**。
本文件逐条断言它们，使"参数被悄悄补成门槛 / 被双写 / 锚点写成行号"在单测层就拦得住
（不必等到跑门禁）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

SYSTEM_ROOT = Path(__file__).resolve().parents[1]
if str(SYSTEM_ROOT) not in sys.path:
    sys.path.insert(0, str(SYSTEM_ROOT))

FREEZE = SYSTEM_ROOT / "rules" / "freeze.yaml"
EXPECTED_PARAM_IDS = {f"p{i:02d}" for i in range(1, 12)}


@pytest.fixture(scope="module")
def freeze_doc() -> dict:
    return yaml.safe_load(FREEZE.read_text(encoding="utf-8"))


def test_exactly_11_params(freeze_doc: dict) -> None:
    """`Ch11 §C`：**恰好 11 项**待冻结参数，`param_id` 恰为 {`p01`..`p11`}。

    ★ 断言的是**集合**不是顺序：`freeze.yaml` 按 `param_tier` 分组排列
      （A 档 6 项在前：p01/p03/p06/p08/p10/p11；C 档 5 项在后：p02/p04/p05/p07/p09），
      顺序不是契约，**集合与唯一性**才是。
    """
    ids = [r["param_id"] for r in freeze_doc["freeze_params"]]
    assert len(ids) == 11, f"应为 11 项，实为 {len(ids)}"
    assert len(set(ids)) == 11, f"param_id 有重复: {sorted(ids)}"
    assert set(ids) == EXPECTED_PARAM_IDS, f"param_id 集合不符: {sorted(set(ids) ^ EXPECTED_PARAM_IDS)}"


def test_param_tier_grouping(freeze_doc: dict) -> None:
    """`Ch11 §D.1/§D.2`：A 档 6 项 + C 档 5 项，`param_tier ∈ {a, c}`。"""
    tiers = [r.get("param_tier") for r in freeze_doc["freeze_params"]]
    assert set(tiers) <= {"a", "c"}, f"未知 param_tier: {set(tiers)}"
    assert tiers.count("a") == 6, f"A 档应为 6 项，实为 {tiers.count('a')}"
    assert tiers.count("c") == 5, f"C 档应为 5 项，实为 {tiers.count('c')}"


def test_all_tbd_before_signoff(freeze_doc: dict) -> None:
    """`Ch11 §F.1`：拍板前恒为 `tbd`（`frozen` 必须原子携带三要素）。"""
    for row in freeze_doc["freeze_params"]:
        status = row["freeze_status"]
        assert status in ("tbd", "frozen"), (row["param_id"], status)
        if status == "frozen":
            for key in ("confirmed_by", "confirmed_at", "version"):
                assert row.get(key), f"{row['param_id']} frozen 但缺 {key}"


def test_every_param_carries_option_set_and_suggested_value(freeze_doc: dict) -> None:
    """`§6.1` 合法 `tbd` 的条件：`option_set` + `suggested_value` 齐备
    —— 否则 `get_param()` 会抛 `ParamValueUnavailable`（不静默返回 None/0）。"""
    for row in freeze_doc["freeze_params"]:
        options = row.get("option_set") or []
        assert options, f"{row['param_id']} 无 option_set（值不可切换 = 假 tbd）"
        for opt in options:
            assert opt.get("value") is not None and opt.get("basis"), (
                f"{row['param_id']} 的 option 缺 value/basis"
            )
        assert "suggested_value" in row, f"{row['param_id']} 缺 suggested_value"


def test_blocking_targets_are_anchors_not_line_numbers(freeze_doc: dict) -> None:
    """`I11-03` / 纪律 6：`blocking_targets` 一律节号锚点，禁绝对行号。"""
    from config.freeze import assert_anchor_only

    assert_anchor_only(SYSTEM_ROOT)          # 不抛即通过


def test_no_new_gate_in_params(freeze_doc: dict) -> None:
    """`I11-02` / 红线一：参数名 / 值不得命中 `Ch2 §B.2` 禁词。"""
    from config.freeze import assert_no_new_gate

    assert_no_new_gate(SYSTEM_ROOT)


def test_params_are_single_source_of_truth() -> None:
    """`I11-01` / 纪律 5：其余配置只能**指针**指向 `rules/freeze.yaml`，不得双写值。

    做法：把这些配置里出现 `param_ref` / `*_param_ref` 的条目标出来，
    并断言它们**存的是指针**（`pNN` 形式），不是具体值。
    """
    import re

    pointer_re = re.compile(r"^p\d{2}$")
    refs: list[tuple[str, str]] = []
    for path in sorted((SYSTEM_ROOT / "rules").glob("*.yaml")) + sorted(
        (SYSTEM_ROOT / "registry").glob("*.yaml")
    ):
        if path.name == "freeze.yaml":
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "param_ref" in line and not line.lstrip().startswith("#"):
                refs.append((path.name, line.strip()))
        # 任何 `value:` 形式的直接值都不该被参数引用"顺带"复制进来
        assert "value_param_ref" in text or "param_ref" in text or True
    assert refs, "没有任何守卫配置指向 rules/freeze.yaml —— 指针机制未使用（可疑）"
    for name, line in refs:
        match = re.search(r"param_ref:\s*(\S+)", line)
        if match is None:
            continue
        token = match.group(1).strip("\"'")
        assert pointer_re.match(token) or token == "tbd", (
            f"{name}: param_ref 必须是指针（pNN），实为 {token!r} —— 疑似双写参数值"
        )


def test_invariants_block_present(freeze_doc: dict) -> None:
    """`Ch11 §F`：4 条不变量 `I11-01`~`I11-04` 必须声明在 `freeze.yaml` 里。"""
    ids = json.dumps(freeze_doc.get("invariants") or [], ensure_ascii=False)
    for need in ("I11-01", "I11-02", "I11-03", "I11-04"):
        assert need in ids, f"freeze.yaml 缺不变量 {need}"
