"""注入测试 —— **守卫真拦得住吗**（`00_开发Agent开工提示词 §5.1 AC-04` / `§十三 第 3 问`）。

> AC-04 守卫真拦得住：注入一个违例 → 检查器 **exit 1**（**不是 warn**）

每个用例的构造方式一致：在 `code_root` 副本里**注入一处真实违例**，
跑**真实检查器脚本**（子进程），断言 `exit == 1`。
另配**反向对照**（同型输入但应放行）——只有"该拦的拦、该放的放"才叫守卫真的在工作，
单纯"全都 exit 1"说明不了任何事。

## 本文件是**拆分后的前半**（`A` 半 · 21 例）

原 `test_guards_reject.py` 共 41 例，**单文件就超宿主的单轮删除配额**
（41 × 每例 271 项夹具 ≈ 11,111 > 9,999，见 `CONVENTIONS.md::V-08`），
故按 `# ═══` 分节边界**纯移动**拆成：

- **本文件**（`A`）：`L1` `L2` `L3` `G11` `launch` `benchmark` `anti_padding`
  `module_denylist` `neutrality` —— 21 例；
- `test_guards_reject_b.py`（`B`）：`placeholder` + `injection_guard` —— 20 例。

两半**用例数之和仍为 41**，断言语义零改动。两半共用的工具（`_schema` / `_write_schema` /
`_read_yaml` / `_write_yaml` / `_inject_py`）与被测脚本路径常量在
`_guard_common.py`（**唯一真源**，`CONVENTIONS.md::G-06`）。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from conftest import assert_rejected, run_gate
from _guard_common import (
    ANTI_PADDING,
    CONFLICT,
    FREEZE,
    LAUNCH,
    MODULE_DENY,
    NEUTRALITY,
    PLACEHOLDER,
    RETURN,
    _inject_py,
    _read_yaml,
    _schema,
    _write_schema,
    _write_yaml,
)

# ═══════════════════════ L1：schema 字段存在性断言 ═══════════════════════

def test_L1_inject_stop_loss_field_is_rejected(code_root: Path) -> None:
    """P-03（禁止损）：`Recommendation` 上出现 `stop_loss` → 必须 exit 1。"""
    doc = _schema(code_root)
    doc["defs"]["Recommendation"]["properties"]["stop_loss"] = {"type": "number"}
    _write_schema(code_root, doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-03")


def test_L1_inject_position_field_is_rejected(code_root: Path) -> None:
    """P-04（建议对象不得有仓位字段）：`position` → 必须 exit 1。"""
    doc = _schema(code_root)
    doc["defs"]["Recommendation"]["properties"]["position"] = {"type": "number"}
    _write_schema(code_root, doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-04")


def test_L1_inject_short_action_enum_is_rejected(code_root: Path) -> None:
    """P-05（禁止做空）：`action` 枚举混入 `short` → 必须 exit 1。"""
    doc = _schema(code_root)
    enum = doc["defs"]["RecommendationAction"]["enum"]
    doc["defs"]["RecommendationAction"]["enum"] = sorted(set(enum) | {"short"})
    _write_schema(code_root, doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-05")


def test_L1_inject_consensus_field_is_rejected(code_root: Path) -> None:
    """P-07（无 source_id 的聚合预测）：`consensus` → 必须 exit 1。"""
    doc = _schema(code_root)
    doc["defs"]["Recommendation"]["properties"]["consensus"] = {"type": "number"}
    _write_schema(code_root, doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-07")


def test_L1_removed_business_positions_is_rejected(code_root: Path) -> None:
    """回归断言：删掉 `business_positions` 对象 → 合法同义词豁免失去落点，必须 exit 1。"""
    doc = _schema(code_root)
    doc["objects"].pop("business_positions", None)
    doc["defs"].pop("BusinessPosition", None)
    _write_schema(code_root, doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="回归断言失败")


# ═══════════════════════ L2：决策作用域禁词 ═══════════════════════

def test_L2_inject_weight_inside_decision_scope_is_rejected(code_root: Path) -> None:
    """P-09：决策作用域内出现 `weight` → 必须 exit 1。"""
    _inject_py(
        code_root,
        "scripts/decision/rank_candidates.py",
        "def rank_candidates(rows):\n    weight = 1.0\n    return sorted(rows, key=lambda r: r) + [weight]\n",
    )
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-09")


def test_L2_same_weight_outside_decision_scope_passes(code_root: Path) -> None:
    """**反向对照**：同样的 `weight` 放在 `scripts/compute/`（非决策域）→ 必须放行。

    证明 P-09 的 `decision_scope_only` 作用域**真的在生效**，不是"见词就杀"。
    """
    _inject_py(
        code_root,
        "scripts/compute/aggregate.py",
        "def aggregate(rows):\n    weight = 1.0\n    return sum(rows) * weight\n",
    )
    proc = run_gate(CONFLICT, code_root, "--timing", "ci")
    assert proc.returncode == 0, (
        "非决策域的 weight 被误报 —— P-09 作用域失效（会逼人关掉门禁）\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_L2_freeze_param_reader_in_decision_module_passes(code_root: Path) -> None:
    """**反向对照**：决策目录下的**纯参数读口**函数不属决策作用域（`Ch11 §E.1` 排除项）。

    参数只做基准/范围/口径/披露，不进决策函数；但"读参数"这件事本身在决策目录里
    也必须被允许，否则 `get_param` 无处安放。
    """
    _inject_py(
        code_root,
        "scripts/decision/caliber.py",
        "from config.freeze import get_param\n\n\n"
        "def scope_value():\n    return get_param('p03').effective_value\n",
    )
    proc = run_gate(CONFLICT, code_root, "--timing", "ci")
    assert proc.returncode == 0, (
        "决策目录下的 freeze_param 纯读口被误报 —— 与 Ch11 §E.1 排除项冲突\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


# ═══════════════════════ L3：配置扫描 ═══════════════════════

def test_L3_inject_banned_config_key_is_rejected(code_root: Path) -> None:
    """P-01/P-02：配置里出现禁词**键名** → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/scope.yaml")
    doc["min_excess_return"] = 0.05
    _write_yaml(code_root, "rules/scope.yaml", doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-01")


def test_L3_banned_token_in_prose_passes(code_root: Path) -> None:
    """**反向对照**：散文中提到禁词（解释"为什么禁止它"）→ 必须放行。

    否则无法在配置里写明"不得设置 min_excess_return 这类门槛"。
    """
    doc = _read_yaml(code_root, "rules/scope.yaml")
    doc["ban_note"] = "不得设置最低超额收益门槛（如 min_excess_return 之类），理由见 Ch11 §E.1"
    _write_yaml(code_root, "rules/scope.yaml", doc)
    proc = run_gate(CONFLICT, code_root, "--timing", "ci")
    assert proc.returncode == 0, f"散文说明被误报为禁词键\n{proc.stdout}\n{proc.stderr}"


# ═══════════════════════ G11：参数与红线一 ═══════════════════════

def test_G11_param_becomes_new_gate_is_rejected(code_root: Path) -> None:
    """红线一：把参数改名成 `min_excess_return`（借参数补门槛）→ 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/freeze.yaml")
    doc["freeze_params"][0]["param"] = "min_excess_return"
    _write_yaml(code_root, "rules/freeze.yaml", doc)
    assert_rejected(run_gate(FREEZE, code_root), rule_hint="G11-02")


def test_G11_absolute_line_number_in_blocking_targets_is_rejected(code_root: Path) -> None:
    """纪律 6：`blocking_targets` 写绝对行号 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/freeze.yaml")
    doc["freeze_params"][0]["blocking_targets"] = ["第 570 行"]
    _write_yaml(code_root, "rules/freeze.yaml", doc)
    assert_rejected(run_gate(FREEZE, code_root), rule_hint="G11-05")


def test_G11_frozen_without_trio_is_rejected(code_root: Path) -> None:
    """G11-01：`frozen` 但缺 `confirmed_by/confirmed_at/version` → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/freeze.yaml")
    doc["freeze_params"][0]["freeze_status"] = "frozen"
    doc["freeze_params"][0]["value"] = "AGIX"
    _write_yaml(code_root, "rules/freeze.yaml", doc)
    assert_rejected(run_gate(FREEZE, code_root), rule_hint="G11-01")


def test_G11_decision_scope_reads_freeze_param_is_rejected(code_root: Path) -> None:
    """G11-02 ②：决策函数读入 `freeze_param` → 必须 exit 1（参数不进决策函数）。"""
    _inject_py(
        code_root,
        "scripts/decision/gate.py",
        "from config.freeze import get_param\n\n\n"
        "def decide(company):\n    return get_param('p03').effective_value\n",
    )
    assert_rejected(run_gate(FREEZE, code_root), rule_hint="G11-02")


# ═══════════════════════ 红线二 / 基准口径 / 反凑数 ═══════════════════════

def test_launch_paid_required_source_is_rejected(code_root: Path) -> None:
    """红线二：`required` 里出现付费订阅 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "registry/launch_criteria.yaml")
    doc["required"][0]["requires_paid_subscription"] = True
    _write_yaml(code_root, "registry/launch_criteria.yaml", doc)
    assert_rejected(run_gate(LAUNCH, code_root), rule_hint="required")


def test_benchmark_proxy_index_is_rejected(code_root: Path) -> None:
    """N3.4-05：基准收益来源被换成公开指数 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/benchmark.yaml")
    doc["benchmark_objects"][0]["return_source"] = "public_index_proxy"
    _write_yaml(code_root, "rules/benchmark.yaml", doc)
    assert_rejected(run_gate(RETURN, code_root), rule_hint="N3.4-05")


def test_benchmark_double_fee_is_rejected(code_root: Path) -> None:
    """N3.4-07：二次扣费 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/benchmark.yaml")
    doc["benchmark_objects"][0]["return_basis"]["fee_deducted_again"] = True
    _write_yaml(code_root, "rules/benchmark.yaml", doc)
    assert_rejected(run_gate(RETURN, code_root), rule_hint="N3.4-05/07")


def test_anti_padding_target_company_count_is_rejected(code_root: Path) -> None:
    """反凑数：出现目标名单规模配置 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/scope.yaml")
    doc["target_company_count"] = 25
    _write_yaml(code_root, "rules/scope.yaml", doc)
    assert_rejected(run_gate(ANTI_PADDING, code_root), rule_hint="N3.1")


def test_module_denylist_portfolio_optimizer_is_rejected(code_root: Path) -> None:
    """交付止于研究+建议：出现组合权重优化模块 → 必须 exit 1。"""
    _inject_py(code_root, "scripts/portfolio_weight_optimizer.py", "X = 1\n")
    assert_rejected(run_gate(MODULE_DENY, code_root), rule_hint="N3.3")


def test_neutrality_urgency_color_is_rejected(code_root: Path) -> None:
    """P-10：展示层用紧迫色隐性引导 → 必须 exit 1。"""
    (code_root / "views").mkdir(parents=True, exist_ok=True)
    (code_root / "views" / "daily.yaml").write_text(
        yaml.safe_dump(
            {"default_sort": [], "urgency_color": True, "evidence_panel": {"collapsed_default": False}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    assert_rejected(run_gate(NEUTRALITY, code_root), rule_hint="P-10")


def test_neutrality_unresearched_rendered_neutral_is_rejected(code_root: Path) -> None:
    """N3.2-05：未完成研究被渲染成"中性" → 必须 exit 1（待判断 ≠ 未完成研究）。"""
    (code_root / "views").mkdir(parents=True, exist_ok=True)
    (code_root / "views" / "daily.yaml").write_text(
        yaml.safe_dump(
            {
                "render_mappings": [
                    {"from": "unresearched", "to": "中性"},
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    assert_rejected(run_gate(NEUTRALITY, code_root), rule_hint="N3.2-05")
