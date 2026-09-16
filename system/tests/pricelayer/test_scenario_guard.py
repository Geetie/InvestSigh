"""`scenario_guard` 单测（`Ch5 §D.6` 概率默认空 / `§E.3` 情景一致 / `§E.4` 状态 pending）。

覆盖 DoD：「`scenario_guard`：`probability` 缺省 = `null`（**有断言**）；情景不一致被拒」
+ 「注入违例 → exit 非零」+ 反向对照。

★ **夹具纪律（修 `G-43`/`G-45` 同族病）**：凡涉及规则解析的用例，一律用 `real_rules` 夹具把
  **真** `rules/scenario.yaml` 原样复制进副本 —— 手写夹具会造出"真文件里不存在的形状"，
  让"代码读一个不存在的键"这类缺陷在夹具上永远绿。
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from scripts.pricelayer import ProbabilityWithoutBasis, ScenarioMethodPending, ScenarioMismatch
from scripts.pricelayer.scenario_guard import (
    DEFAULT_SCENARIO_METHOD_STATUS,
    DESIGN_SCENARIO_METHOD_STATUSES,
    PROBABILITY_DEFAULT,
    REQUIRED_RULE_KEYS,
    RULE_KEY_BLOCKING,
    RULE_KEY_CONSISTENCY,
    RULE_KEY_DOMAIN,
    RULE_KEY_PARAM_REF,
    RULE_KEY_STATUS,
    RULE_KEY_TAGS,
    ScenarioEstimate,
    ScenarioGuardError,
    ScenarioPolicy,
    ScenarioTag,
    assert_probability_has_basis,
    assert_relative_judgment_allowed,
    assert_rule_tags_match,
    assert_scenario_match,
    load_scenario_policy,
)


# ───────────────────── §D.6：probability 默认 null ─────────────────────


def test_probability_default_is_none_not_fifty_fifty() -> None:
    """★ `Ch5 §D.6` 逐字断言：`probability` 默认 `null`（**不是 50/50**）。"""
    assert PROBABILITY_DEFAULT is None
    assert ScenarioEstimate(tag=ScenarioTag.neutral).probability is None


def test_probability_stays_none_when_not_provided_explicitly() -> None:
    """上/下行情景（`N5.3-05`："不含概率"）默认构造 → 概率仍为空。"""
    lower = ScenarioEstimate(tag=ScenarioTag.bear, range_low=Decimal("80"), range_high=Decimal("100"))
    upper = ScenarioEstimate(tag=ScenarioTag.bull, range_low=Decimal("120"), range_high=Decimal("150"))
    assert lower.probability is None and upper.probability is None


def test_probability_without_basis_is_rejected() -> None:
    """`Ch5 §J9` / B11：填概率但**无来源** → 拒绝（不得凭空给概率）。"""
    with pytest.raises(ProbabilityWithoutBasis):
        assert_probability_has_basis(Decimal("0.6"))


def test_probability_with_unresolvable_basis_is_rejected() -> None:
    """依据必须能解析到**真** `DerivedValue`（追不到 operand 的不算依据）。"""
    with pytest.raises(ProbabilityWithoutBasis):
        assert_probability_has_basis(Decimal("0.6"), basis_ref="dv-missing", resolve=lambda _ref: None)


def test_reverse_control_probability_with_real_derived_basis_passes() -> None:
    """反向对照：给了依据且解析到带 formula/operands 的 `DerivedValue` → **放行**。"""

    class _Fake:
        formula = "a / b"
        operands = ["a", "b"]

    assert_probability_has_basis(Decimal("0.6"), basis_ref="dv-1", resolve=lambda _ref: _Fake())


def test_reverse_control_none_probability_needs_no_basis() -> None:
    """反向对照：概率为空是**合法默认**（不需要依据）。"""
    assert_probability_has_basis(None)


# ───────────────────── §E.3：情景口径一致性 ─────────────────────


def test_scenario_mismatch_bull_vs_bear_is_rejected() -> None:
    """★ `Ch5 §E.3` 逐字单测：个股乐观 + 基准悲观 → `ScenarioMismatch`（`N5.4-08`）。"""
    with pytest.raises(ScenarioMismatch):
        assert_scenario_match(ScenarioTag.bull, ScenarioTag.bear)


def test_reverse_control_same_scenario_passes() -> None:
    """反向对照：两者同为中性 → 放行（`§E.3` 伪码 `return True`）。"""
    assert assert_scenario_match(ScenarioTag.neutral, ScenarioTag.neutral) is True
    assert assert_scenario_match("bull", "bull") is True


def test_unknown_scenario_tag_is_rejected() -> None:
    """`Ch5 §J4` 的标签集合是闭集（enum 全等判定，不是文本相似）。"""
    with pytest.raises(ScenarioGuardError):
        assert_scenario_match("optimistic", "bull")


# ───────────────────── §E.4：scenario_method_status ─────────────────────


def test_default_status_is_pending() -> None:
    """`Ch5 §E.4` 逐字：默认 `pending`（**不静默默认**成 neutral）。"""
    assert DEFAULT_SCENARIO_METHOD_STATUS == "pending"
    assert DESIGN_SCENARIO_METHOD_STATUSES == ("pending", "neutral", "probability_weighted")
    policy = load_scenario_policy(None)
    assert policy.status == "pending"
    assert policy.value_source == "design_default"


def test_pending_blocks_relative_judgment() -> None:
    """`Ch5 §E.4`：`pending` ⇒ **阻塞**相对判断生成（输出"待判断"而非建议）。"""
    with pytest.raises(ScenarioMethodPending):
        assert_relative_judgment_allowed(ScenarioPolicy(status="pending", value_source="rules"))


def test_reverse_control_neutral_allows_relative_judgment() -> None:
    """反向对照：`blocking=False` → 放行。"""
    assert_relative_judgment_allowed(
        ScenarioPolicy(status="neutral", value_source="rules", blocking=False)
    )


# ───────── 规则↔代码绑定：**在真 rules/scenario.yaml 上**（防 G-43/G-45 同族病）─────────


def test_real_rules_file_contains_every_key_the_guard_reads(scratch: Path, real_rules) -> None:
    """★ 机器绑定：本模块读取的每个键在**真** `rules/scenario.yaml` 里**真实存在**。

    这是"夹具与真文件不同源"病的正面封堵：若代码读了一个真文件没有的键
    （如曾经的 `method_version`），本用例当场红，而不是靠人手看夹具。
    """
    real_rules(scratch, "scenario.yaml")
    import yaml

    doc = yaml.safe_load((scratch / "rules" / "scenario.yaml").read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED_RULE_KEYS if key not in doc]
    assert not missing, f"真 rules/scenario.yaml 缺本模块读取的键: {missing}"
    # 指针与阻塞条件必须真的在文件里（此前这两处是硬编码的）
    assert doc[RULE_KEY_CONSISTENCY][RULE_KEY_PARAM_REF] == "p05"
    assert doc[RULE_KEY_BLOCKING]["when"] == f"{RULE_KEY_STATUS} == pending"


def test_real_rules_policy_reads_blocking_and_domain_from_file(
    scratch: Path, real_rules
) -> None:
    """在**真文件**上：`domain` / `blocking` / `param_ref` 全部**读**出来的，非硬编码。"""
    real_rules(scratch, "scenario.yaml")
    policy = load_scenario_policy(scratch)
    assert policy.value_source == "rules"
    assert policy.status == "pending"
    assert policy.domain == ("pending", "neutral", "probability_weighted")
    assert policy.blocking is True
    assert policy.required_field_at_downstream == "benchmark_forecast"
    assert policy.param_ref == "p05"
    assert policy.record_method_version is True
    # pending ⇒ 转正尚未发生 ⇒ §E.4 的"记 method_version"尚未适用，空串是**正确值**
    assert policy.method_version == ""
    assert policy.method_version_source == "not_applicable_pending"
    assert policy.notes == ()


def test_real_rules_tags_match_code_enum(scratch: Path, real_rules) -> None:
    """真 `scenario_tags` 与代码枚举**逐字一致**（`Ch5 §J4` + `Ch11 §D.2`）。"""
    real_rules(scratch, "scenario.yaml")
    assert assert_rule_tags_match(scratch) == tuple(t.value for t in ScenarioTag)
    assert assert_rule_tags_match(scratch) == ("bear", "neutral", "bull", "custom")


def test_rule_tags_divergence_from_code_is_rejected(scratch: Path, real_rules) -> None:
    """★ 反例：规则文件标签集改了、代码没改 → **响亮失败**（防声明与实现脱节）。"""
    real_rules(scratch, "scenario.yaml")
    path = scratch / "rules" / "scenario.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "scenario_tags: [bear, neutral, bull, custom]",
            "scenario_tags: [bear, neutral, bull, custom, sideways]",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ScenarioGuardError, match="scenario_tags"):
        assert_rule_tags_match(scratch)


def test_rule_domain_read_from_file_governs_validation(scratch: Path, real_rules) -> None:
    """★ 取值域**读**文件：把域缩到 `pending` 后，`neutral` 立即被判非法（`Ch11 §D.2`）。"""
    real_rules(scratch, "scenario.yaml")
    assert load_scenario_policy(scratch).domain == DESIGN_SCENARIO_METHOD_STATUSES
    path = scratch / "rules" / "scenario.yaml"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "scenario_method_status_domain: [pending, neutral, probability_weighted]",
        "scenario_method_status_domain: [pending]",
    ).replace("scenario_method_status: pending", "scenario_method_status: neutral")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ScenarioGuardError, match="非法"):
        load_scenario_policy(scratch)


def test_rule_domain_key_absent_falls_back_with_note(scratch: Path, real_rules) -> None:
    """缺 `scenario_method_status_domain` → 回落设计逐字域 + **显式 note**（非"已核"）。"""
    real_rules(scratch, "scenario.yaml")
    path = scratch / "rules" / "scenario.yaml"
    kept = [
        line
        for line in path.read_text(encoding="utf-8").splitlines(keepends=True)
        if not line.startswith(f"{RULE_KEY_DOMAIN}:")
    ]
    path.write_text("".join(kept), encoding="utf-8")
    assert RULE_KEY_DOMAIN not in path.read_text(encoding="utf-8")
    policy = load_scenario_policy(scratch)
    assert policy.domain == DESIGN_SCENARIO_METHOD_STATUSES
    assert any("NO_DOMAIN_KEY" in note for note in policy.notes)


def test_rule_blocking_when_is_read_not_hardcoded(scratch: Path, real_rules) -> None:
    """★ 阻塞条件**读** `scenario_method_blocking.when`：改成 `== neutral` 后行为随之改变。"""
    real_rules(scratch, "scenario.yaml")
    assert load_scenario_policy(scratch).blocking is True
    path = scratch / "rules" / "scenario.yaml"
    text = path.read_text(encoding="utf-8").replace(
        f'when: "{RULE_KEY_STATUS} == pending"', f'when: "{RULE_KEY_STATUS} == neutral"'
    )
    path.write_text(text, encoding="utf-8")
    policy = load_scenario_policy(scratch)
    assert policy.status == "pending"
    assert policy.blocking is False, "阻塞条件改了，代码行为必须跟着改（不得硬编码）"
    assert_relative_judgment_allowed(policy)  # 不再阻塞


def test_rule_blocking_when_unknown_shape_fails_loudly(scratch: Path, real_rules) -> None:
    """★ 反例：`when` 形态不认识 → **响亮失败**（不发明表达式求值器、不当"不阻塞"）。"""
    real_rules(scratch, "scenario.yaml")
    path = scratch / "rules" / "scenario.yaml"
    text = path.read_text(encoding="utf-8").replace(
        f'when: "{RULE_KEY_STATUS} == pending"', 'when: "A and B or C"'
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ScenarioGuardError, match="形态不认识"):
        load_scenario_policy(scratch)


def test_rule_blocking_key_absent_falls_back_with_note(scratch: Path, real_rules) -> None:
    """缺 `scenario_method_blocking` → 回落 `§E.4` 逐字条件 + **显式 note**。"""
    real_rules(scratch, "scenario.yaml")
    path = scratch / "rules" / "scenario.yaml"
    text = path.read_text(encoding="utf-8").replace(f"{RULE_KEY_BLOCKING}:", "renamed_blocking:")
    path.write_text(text, encoding="utf-8")
    policy = load_scenario_policy(scratch)
    assert policy.blocking is True
    assert any("NO_BLOCKING_RULE" in note for note in policy.notes)


# ──────── `method_version` 的真实载体：**不再从 scenario.yaml 读**（修静默空串）────────


def test_promoted_status_without_available_method_version_fails_loudly(
    scratch: Path, real_rules
) -> None:
    """★ 修 1 的核心反例：`status != pending` 而 `method_version` **不可用** → **响亮失败**。

    真文件把 `method_version` 的值面指向 `rules/freeze.yaml::p05`（`return_forecast_method`），
    而 `p05` 现为 `freeze_status: tbd` / `suggested_value.algorithm: tbd`
    ⇒ 未冻结参数就转正状态 ⇒ 必须报错，**不得静默取空串**（旧实现 `doc.get("method_version") or ""`）。
    """
    real_rules(scratch, "scenario.yaml", "freeze.yaml")
    path = scratch / "rules" / "scenario.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "scenario_method_status: pending", "scenario_method_status: neutral"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ScenarioGuardError, match="method_version 不可用"):
        load_scenario_policy(scratch)


def test_promoted_status_with_frozen_method_version_resolves(
    scratch: Path, real_rules
) -> None:
    """反向对照：把 `p05` 冻结成真算法后，转正即能解析出 `method_version`。"""
    import yaml

    real_rules(scratch, "scenario.yaml", "freeze.yaml")
    scenario = scratch / "rules" / "scenario.yaml"
    scenario.write_text(
        scenario.read_text(encoding="utf-8").replace(
            "scenario_method_status: pending", "scenario_method_status: probability_weighted"
        ),
        encoding="utf-8",
    )
    freeze = scratch / "rules" / "freeze.yaml"
    doc = yaml.safe_load(freeze.read_text(encoding="utf-8"))
    for row in doc["freeze_params"]:
        if row.get("param_id") == "p05":
            row["value"] = {"same_period_same_scenario_as_benchmark": True, "algorithm": "scenario-v2"}
            row["freeze_status"] = "frozen"
    freeze.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")

    policy = load_scenario_policy(scratch)
    assert policy.status == "probability_weighted"
    assert policy.method_version == "scenario-v2"
    assert policy.method_version_source == "freeze:p05"
    assert policy.blocking is False


def test_promoted_status_with_dangling_param_ref_fails_loudly(
    scratch: Path, real_rules
) -> None:
    """★ 反例：指针悬空（`param_ref` 指向不存在的参数）→ 响亮失败，不静默取空串。"""
    real_rules(scratch, "scenario.yaml", "freeze.yaml")
    path = scratch / "rules" / "scenario.yaml"
    text = path.read_text(encoding="utf-8")
    text = text.replace("scenario_method_status: pending", "scenario_method_status: neutral")
    text = text.replace("param_ref: p05", "param_ref: p99")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ScenarioGuardError, match="指针悬空"):
        load_scenario_policy(scratch)


def test_pending_status_never_touches_freeze(scratch: Path, real_rules) -> None:
    """`pending` 时**不读** `freeze.yaml`（转正尚未发生）—— 删掉 freeze 仍可解析。"""
    real_rules(scratch, "scenario.yaml")
    assert not (scratch / "rules" / "freeze.yaml").exists()
    policy = load_scenario_policy(scratch)
    assert policy.status == "pending" and policy.method_version == ""


def test_illegal_status_value_is_rejected(scratch: Path, real_rules) -> None:
    """取值不在取值域内 → 响亮失败（不许"未知状态当 pending 用"）。"""
    real_rules(scratch, "scenario.yaml")
    path = scratch / "rules" / "scenario.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "scenario_method_status: pending", "scenario_method_status: maybe"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ScenarioGuardError, match="非法"):
        load_scenario_policy(scratch)


def test_missing_scenario_yaml_falls_back_to_design_default_with_note(scratch: Path) -> None:
    """文件缺失 ⇒ 按 `§E.4` 逐字默认 `pending`，但**显式标注来源**（不静默）。"""
    policy = load_scenario_policy(scratch)
    assert policy.status == "pending"
    assert policy.value_source == "design_default"
    assert any("NO_SCENARIO_YAML" in note for note in policy.notes)


def test_tests_never_write_real_rules_files(scratch: Path, real_rules) -> None:
    """★ 纪律：测试只**读**真 `rules/**` —— 全流程 SHA256 必须不变（副本内随便改）。

    ★ 另注：真 `rules/` 的 **0444 锁纪律**（`Ch9 §3.10 J9` / 纪律 10）由 `rules_lock_guard.py`
      承担；本卡实测**该门禁当前是红的**（`baseline/metric-sets/scenario/valuation-methods`
      四个新装文件为 0644）—— 属 `rules/` 安装方，已在报告 §④ 上报，本卡不写 `rules/**`。
    """
    import hashlib

    real_dir = Path(__file__).resolve().parents[2] / "rules"
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    before = {p.name: digest(p) for p in sorted(real_dir.glob("*.yaml"))}
    real_rules(scratch, "scenario.yaml", "freeze.yaml", "valuation-methods.yaml")
    for name in ("scenario.yaml", "freeze.yaml", "valuation-methods.yaml"):
        (scratch / "rules" / name).write_text("mutated: true\n", encoding="utf-8")
    after = {p.name: digest(p) for p in sorted(real_dir.glob("*.yaml"))}
    assert before == after, "测试改动了真 rules/** —— 违反只读纪律"


# ───────────────────── CLI：注入违例 → exit 非零 + 反向对照 ─────────────────────


def _baseline_with_probability(baseline_id: str, *, probability: str | None, formula_ref: str) -> dict[str, object]:
    return {
        "baseline_id": baseline_id,
        "version": 1,
        "business_mechanism": "x",
        "valuation": {
            "probability": probability,
            "formula_ref": formula_ref,
            "range": {"low": "80", "high": "120"},
        },
    }


def test_cli_rejects_probability_without_formula_ref(
    scratch: Path, write_jsonl, run_script
) -> None:
    """★ 注入违例：填了概率却无依据 → CLI **exit 1**（`Ch5 §D.6` / `§J9` / B11）。"""
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability="0.6", formula_ref="tbd")])
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "PROBABILITY-WITHOUT-BASIS" in proc.stdout


def test_cli_rejects_probability_basis_that_does_not_resolve(
    scratch: Path, write_jsonl, write_derived_jsonl, run_script
) -> None:
    """注入违例：依据 id 在 `derived/` 里**不存在** → exit 1（追溯链断）。"""
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability="0.6", formula_ref="dv-nope")])
    write_derived_jsonl(
        scratch,
        [
            {
                "derived_id": "dv-other",
                "value": "1",
                "formula": "1",
                "operands": ["x"],
                "method_version": "v1",
                "computed_at": "2026-09-15T12:00:00+00:00",
            }
        ],
    )
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "PROBABILITY-BASIS-UNRESOLVED" in proc.stdout


def test_reverse_control_cli_passes_with_null_probability(
    scratch: Path, write_jsonl, run_script
) -> None:
    """反向对照：概率为空（设计常态）→ **exit 0**。"""
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability=None, formula_ref="tbd")])
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "NO_PROBABILITY_FILLED" in proc.stdout


def test_reverse_control_cli_passes_on_real_rules_file(
    scratch: Path, write_jsonl, real_rules, run_script
) -> None:
    """反向对照：**真** `rules/scenario.yaml` + 概率为空的 baseline → exit 0（无绑定违例）。"""
    real_rules(scratch, "scenario.yaml", "freeze.yaml")
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability=None, formula_ref="tbd")])
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SCENARIO-RULE-BINDING" not in proc.stdout


def test_cli_flags_rule_key_missing_from_scenario_yaml(
    scratch: Path, write_jsonl, write_rules, run_script
) -> None:
    """★ 注入违例：规则文件缺本模块读取的键 → CLI **exit 1**（`Ch11 §D.2` 声明与实现脱节）。"""
    write_rules(scratch, "scenario.yaml", {RULE_KEY_STATUS: "pending"})
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability=None, formula_ref="tbd")])
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SCENARIO-RULE-BINDING" in proc.stdout


def test_cli_flags_non_null_probability_default_in_rule(
    scratch: Path, write_jsonl, real_rules, run_script
) -> None:
    """★ 注入违例：规则文件把概率默认值改成数值 → exit 1（`Ch5 §D.6` 不默认 50/50）。"""
    import yaml

    real_rules(scratch, "scenario.yaml")
    path = scratch / "rules" / "scenario.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["probability"]["default"] = 0.5
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability=None, formula_ref="tbd")])
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SCENARIO-RULE-BINDING" in proc.stdout


def test_cli_reports_rule_binding_indeterminate_when_file_absent(
    scratch: Path, write_jsonl, run_script
) -> None:
    """`G-03`：规则文件缺失 → 绑定判据**不可判定**（显式 note），不当"已核"。"""
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability=None, formula_ref="tbd")])
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "NO_SCENARIO_YAML_FOR_BINDING" in proc.stdout


def test_reverse_control_cli_passes_with_resolvable_basis(
    scratch: Path, write_jsonl, write_derived_jsonl, run_script
) -> None:
    """反向对照：概率有依据且依据可解析 → exit 0。"""
    write_jsonl(scratch, "baselines", [_baseline_with_probability("b1", probability="0.6", formula_ref="dv-1")])
    write_derived_jsonl(
        scratch,
        [
            {
                "derived_id": "dv-1",
                "value": "0.6",
                "formula": "a / b",
                "operands": ["a", "b"],
                "method_version": "v1",
                "computed_at": "2026-09-15T12:00:00+00:00",
            }
        ],
    )
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── 主理人裁定 ③-3：**回落值 == 真文件里的值**（防"规则改了、回落没改"）──


def test_rule_domain_drift_from_code_fallback_is_flagged(scratch: Path, real_rules, run_script) -> None:
    """★ 判据⑥：`scenario_method_status_domain` 改了而代码回落值未改 → CLI **exit 1**。"""
    import yaml

    real_rules(scratch, "scenario.yaml")
    path = scratch / "rules" / "scenario.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["scenario_method_status_domain"] = ["pending", "neutral"]
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SCENARIO-RULE-BINDING" in proc.stdout
    assert "scenario_method_status_domain" in proc.stdout


def test_rule_blocking_when_drift_from_code_fallback_is_flagged(
    scratch: Path, real_rules, run_script
) -> None:
    """★ 判据⑦：`scenario_method_blocking.when` 改了而 `DESIGN_BLOCKING_WHEN` 未改 → exit 1。"""
    import yaml

    real_rules(scratch, "scenario.yaml")
    path = scratch / "rules" / "scenario.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["scenario_method_blocking"]["when"] = "scenario_method_status == neutral"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SCENARIO-RULE-BINDING" in proc.stdout
    assert "scenario_method_blocking" in proc.stdout


def test_rule_record_method_version_drift_is_flagged(
    scratch: Path, real_rules, run_script
) -> None:
    """★ 判据⑦：`record_method_version` 改假而 `DESIGN_RECORD_METHOD_VERSION` 为真 → exit 1（`§E.4`）。"""
    import yaml

    real_rules(scratch, "scenario.yaml")
    path = scratch / "rules" / "scenario.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["scenario_method_promotion"]["record_method_version"] = False
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SCENARIO-RULE-BINDING" in proc.stdout
    assert "record_method_version" in proc.stdout


def test_design_status_default_is_deliberately_not_bound() -> None:
    """★ 反向自证：`DEFAULT_SCENARIO_METHOD_STATUS` **不得**被绑到文件的 `scenario_method_status`。

    二者**不是同一事实** —— 前者是"尚未转正时的默认值"，后者是**当前状态**
    （转正后合法地变成 `neutral`）。若把它也纳入绑定，正常转正后就会**假红**。
    本用例把这条"刻意不绑"的选择固化成可执行的说明。
    """
    from scripts.pricelayer.scenario_guard import DEFAULT_SCENARIO_METHOD_STATUS

    assert DEFAULT_SCENARIO_METHOD_STATUS == "pending"
    assert "pending" in DESIGN_SCENARIO_METHOD_STATUSES, "默认值必须落在设计取值域内"


# ── 第四轮：**缺子键 ≠ 值合规**（合法值恰是 `null`/`false` 的那两个键最危险）──


def _scenario_doc(scratch: Path, real_rules) -> tuple[Path, dict]:
    """把**真** `scenario.yaml`（+ `freeze.yaml`）复制进副本并解析 —— 第四轮用例的最小夹具。"""
    import yaml

    real_rules(scratch, "scenario.yaml", "freeze.yaml")
    path = scratch / "rules" / "scenario.yaml"
    return path, yaml.safe_load(path.read_text(encoding="utf-8"))


def _put_doc(path: Path, doc: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")


def test_missing_probability_default_is_flagged_not_read_as_compliant(
    scratch: Path, real_rules, run_script
) -> None:
    """★ 第四轮主反例：**删** `probability.default` ⇒ 必须 `exit 1`（不得读成"合规 null"）。

    该键的**合法值就是 `null`** ⇒ 旧写法 `probability.get("default") is not None`
    在键不存在时 `.get` 回 `None`，判据**通过** —— 即"文件里根本没写"被读成"已确认不默认 50/50"
    （**假通过**）。故必须先判"键在不在"，再判"值对不对"（`Ch11 §D.2`；`G-03`：跳过不是通过）。
    """
    path, doc = _scenario_doc(scratch, real_rules)
    doc["probability"].pop("default")
    _put_doc(path, doc)
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "SCENARIO-RULE-BINDING" in proc.stdout
    assert "probability.default 缺失" in proc.stdout


def test_missing_must_be_null_50_50_is_flagged(
    scratch: Path, real_rules, run_script
) -> None:
    """★ 同族：删 `probability.must_be_null_50_50`（**合法值就是 `false`**）⇒ 必须 `exit 1`。

    旧写法 `bool(probability.get("must_be_null_50_50"))` 在缺键时得 `False` ⇒ 判据通过
    ⇒ "缺键"被静默读成"已确认不默认 50/50"。
    """
    path, doc = _scenario_doc(scratch, real_rules)
    doc["probability"].pop("must_be_null_50_50")
    _put_doc(path, doc)
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "must_be_null_50_50 缺失" in proc.stdout


def test_missing_blocking_when_and_record_method_version_are_flagged(
    scratch: Path, real_rules, run_script
) -> None:
    """★ 判据⑥⑦：删 `blocking.when` 与 `promotion.record_method_version` ⇒ **两条**违例都要出现。

    旧写法用 `doc.get(k)` 取值后再比 ⇒ 缺键时**静默跳过**（"无可比对象"），
    于是"阻塞条件/是否须记版本"这两个事实从规则面消失而门禁全绿。
    """
    path, doc = _scenario_doc(scratch, real_rules)
    doc["scenario_method_blocking"].pop("when")
    doc["scenario_method_promotion"].pop("record_method_version")
    _put_doc(path, doc)
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "scenario_method_blocking.when 缺失" in proc.stdout
    assert "record_method_version 缺失" in proc.stdout


def test_empty_blocking_when_is_flagged(
    scratch: Path, real_rules, run_script
) -> None:
    """★ `when: ""`（键在但值为空）：旧写法 `if declared_when and …` 让**空串静默通过** ⇒ 必须红。"""
    path, doc = _scenario_doc(scratch, real_rules)
    doc["scenario_method_blocking"]["when"] = ""
    _put_doc(path, doc)
    proc = run_script("scripts/pricelayer/scenario_guard.py", scratch, "--no-report")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "scenario_method_blocking.when='' 与代码回落值" in proc.stdout
