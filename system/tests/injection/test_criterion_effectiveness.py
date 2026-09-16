"""**判据有效性**注入测试（缺口 `G9`：绑定 ≠ 会拦）。

## 本文件存在的理由

`stage_gate.bound_criteria()` 用 AST 证明「判据声明」与「函数体」连上了线。
但独立审计证明：**把 `cv = coverage_check(root)` 换成空 `CheckReport`，
`criteria_bound` 仍是 4，而不达标数据下门禁变绿**（本文件
`test_daily_run_coverage_verifiable_counterexample_is_load_bearing` 复现了它）。

⇒ 本文件给**每条已绑定判据**配一条**可执行反例**，把义务从「接了」强化到「真的会拦」：

| 断言形态 | 含义 |
|---|---|
| **合规输入**下该判据的 `blocked_hint` **不出现** | 反例不是靠**别的**判据"顺带变红"（判别力归因） |
| **不合规输入**下门禁 `exit != 0` **且** `blocked_hint` 出现 | `H1`：该判据确实会拦 |
| 两个输入的**违例集合之差非空** | 量化"判别力"，不受阶段因未绑定判据而结构性变红的影响 |
| `ineffective` 条目：两个输入的违例集合**完全相同** | 如实证明"该判据无判别力"（`G-03`：不静默） |

义务本身的机器绑定在 `scripts/checks/criterion_effectiveness_guard.py`
（已绑定 ⊆ 已登记，缺登记 FATAL）——本文件是那份登记的**证据**。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from conftest import SYSTEM_ROOT, run_gate_inproc, write_check_records

GATE = "scripts/delivery/stage_gate.py"
GUARD = "scripts/checks/criterion_effectiveness_guard.py"
REGISTRY = "registry/criterion_counterexamples.yaml"
DELIVERY = "registry/delivery.yaml"

_DAY = "2026-09-16"
_FATAL = "[FATAL]"


# ────────────────────────────── 夹具工具 ──────────────────────────────


def _write_jsonl(root: Path, stem: str, rows: list[dict]) -> None:
    (root / "facts" / f"{stem}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def _drop_last_valid_ref(root: Path, task_id: str) -> None:
    """**违约注入**：把真实写入行的 `last_valid_result_ref` 抹成 `null`（`Ch8 §E.4` 禁止的置空）。

    ★ 违约只加在**被注入的那一行**上；其余行都是真实写路径的产物 ——
      这与"手工拼一个生产写不出来的形状"有本质区别（后者是**夹具造假**）。
    """
    path = root / "facts" / "tasks.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    hit = False
    for row in rows:
        if row.get("task_id") == task_id:
            row["last_valid_result_ref"] = None
            hit = True
    assert hit, f"注入点不存在: {task_id}"
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def _gate(root: Path, stage: str) -> tuple[int, str]:
    """跑**真仓库那份** `stage_gate.py`，`code_root` 指向夹具副本（进程内入口，不走缓存）。"""
    return run_gate_inproc(GATE, root, "--stage", stage)


def _fatal_lines(out: str) -> set[str]:
    """门禁输出里的违例行集合（量化"判别力"：不合规输入必须**改变**这个集合）。"""
    return {ln.strip() for ln in out.splitlines() if ln.strip().startswith(_FATAL)}


def _assert_hint_absent(out: str, hint: str) -> None:
    """**判别力归因**：合规输入下该判据的专属标记不得出现（否则"变红"可能来自别的判据）。"""
    assert hint not in out, f"合规输入下不该出现判据专属标记 {hint!r}：\n{out}"


# ───────────────────────── 合规基线（判据可分归因） ─────────────────────────

_BASELINE_OK = {
    "baseline_id": "baseline-nvda-001",
    "company_id": "co_1",
    "business_mechanism": "卖加速卡",
    "historical_numeric_claims": ["claim-1"],
    "driver_model": [{"assumptions": ["数据中心 capex 增速维持"], "d": 1}],
    "value_state_refs": ["vs-1"],
}

_RECOMMENDATION_OK = {
    "recommendation_id": "rec-1",
    "company_id": "co_1",
    "evidence_version_ids": ["dv-1"],
    "version": 1,
}

_DERIVED_OK = {"derived_id": "dv-1", "formula": "rev*margin", "operands": {}, "method_version": "v1"}


def _nvidia_compliant(root: Path) -> None:
    """阶段② 的**合规**输入：baselines 齐六项 + 建议四要素（适用项）可反查。"""
    _write_jsonl(root, "baselines", [_BASELINE_OK])
    _write_jsonl(root, "recommendations", [_RECOMMENDATION_OK])
    (root / "derived" / "trace.jsonl").write_text(
        json.dumps(_DERIVED_OK, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _daily_compliant(root: Path) -> None:
    """阶段④ 的**合规**输入：覆盖目标非空（CV3/CV4 可判）+ check_record 有时点。

    ★ 这份输入下阶段④ **`exit 0`** —— 故阶段④ 的反例具备完整判别力归因
      （红了就是该判据干的，不是别的判据顺带变红）。

    ★★ 运行记录行由**真实写路径**产出（`conftest.write_check_records`），**不手工拼字段形状** ——
      这是 `G-43` / `G-45` 的直接教训：审计实测的手工夹具（`status=done` +
      `output_refs=["rec-1"]`）**与生产写出形状不同源**（`_write_check_record()` 当时
      两个字段都不填），于是"判据空转"在夹具上完全看不出来。夹具与真形状必须同源（`G-06`）。
    """
    _write_jsonl(root, "companies", [{"company_id": "co_1", "research_depth": "position_listed"}])
    write_check_records(root, [{"produced": ["rec-1"]}])


def _task(task_id: str, status: str, **kw) -> dict:
    row = {
        "task_id": task_id,
        "task_type": "verify",
        "status": status,
        "idempotency_key": f"check::{task_id}",
        "parent_context": {"orchestrator": "pipeline.run_daily"},
        "last_valid_result_ref": None,
        "output_refs": [],
        "check_record": {
            "check_id": task_id,
            "run_date": _DAY,
            "changed": False,
            "judgment_change": {},
            "signals_emitted": 0,
            "degraded": False,
        },
    }
    row.update(kw)
    return row


def _expansion_compliant(root: Path) -> None:
    _write_jsonl(
        root,
        "tasks",
        [
            {"task_id": "t1", "eval_result": {"eval_layer": "research_quality"}},
            {"task_id": "t2", "eval_result": {"eval_layer": "forecast_quality"}},
            {"task_id": "t3", "eval_result": {"eval_layer": "investment_result"}},
        ],
    )


def _patch_yaml(path: Path, fn) -> None:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    path.write_text(
        yaml.safe_dump(fn(doc) or doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


# ═════════════════════════ 阶段① prep：4 条判据的反例 ═════════════════════════


def test_prep_compliant_baseline_is_green(code_root: Path) -> None:
    """**合规基线**：干净副本上阶段① `exit 0` —— 4 条反例因此都有完整归因力。"""
    code, out = _gate(code_root, "prep")
    assert code == 0, out


def test_prep_four_deliverables_blocks_on_missing_class(code_root: Path) -> None:
    """`four_deliverables` 反例：四类交付物削到三类 → 阶段① 必须红。"""
    base_out = _gate(code_root, "prep")[1]
    _assert_hint_absent(base_out, "交付物项数应为 4")

    path = code_root / "registry" / "prep_deliverables.yaml"
    _patch_yaml(path, lambda doc: doc.update({"deliverables": doc["deliverables"][:3]}))

    code, out = _gate(code_root, "prep")
    assert code == 1, out
    assert "交付物项数应为 4" in out, out


def test_prep_rule_vs_impl_split_blocks_on_collapsed_layers(code_root: Path) -> None:
    """`rule_vs_impl_split` 反例：清空「已确认规则」层 → 两层不再显式区分 → 必须红。"""
    base_out = _gate(code_root, "prep")[1]
    _assert_hint_absent(base_out, "confirmed_rules 为空")

    path = code_root / "registry" / "prep_deliverables.yaml"
    _patch_yaml(path, lambda doc: doc.update({"confirmed_rules": []}))

    code, out = _gate(code_root, "prep")
    assert code == 1, out
    assert "confirmed_rules 为空" in out, out


def test_prep_caliber_tbd_placeholder_blocks_on_frozen_without_fields(code_root: Path) -> None:
    """`caliber_tbd_placeholder` 反例：`tbd` 偷改成 `frozen` 却不给确认字段 → 必须红。"""
    base_out = _gate(code_root, "prep")[1]
    _assert_hint_absent(base_out, "frozen 但缺")

    path = code_root / "rules" / "freeze.yaml"
    _patch_yaml(path, lambda doc: doc["freeze_params"][0].update({"freeze_status": "frozen"}))

    code, out = _gate(code_root, "prep")
    assert code == 1, out
    assert "frozen 但缺" in out, out


def test_prep_no_paid_required_blocks_on_paid_in_required(code_root: Path) -> None:
    """`no_paid_required` 反例：`required` 里塞进付费订阅（红线二）→ 必须红。"""
    base_out = _gate(code_root, "prep")[1]
    _assert_hint_absent(base_out, "首版启动条件含付费订阅")

    path = code_root / "registry" / "launch_criteria.yaml"
    _patch_yaml(
        path, lambda doc: doc["required"][0].update({"requires_paid_subscription": True})
    )

    code, out = _gate(code_root, "prep")
    assert code == 1, out
    assert "首版启动条件含付费订阅" in out, out


# ═════════════════════ 阶段② nvidia_sample：2 条判据的反例 ═════════════════════


def test_nvidia_sample_six_step_chain_complete_blocks_on_missing_depth(code_root: Path) -> None:
    """`six_step_chain_complete` 反例：baseline 缺一项六步深度 → 必须红。

    ★ 先把**合规输入**跑一遍并断言两条判据的专属标记都不出现（判别力归因）；
      阶段② 因"未绑定判据台账"结构性 exit≠0，故归因靠标记与**违例集合之差**，不靠"红/绿"。
    """
    _nvidia_compliant(code_root)
    base_out = _gate(code_root, "nvidia_sample")[1]
    _assert_hint_absent(base_out, "六项深度缺")
    _assert_hint_absent(base_out, "四要素")

    row = dict(_BASELINE_OK)
    row.pop("driver_model")
    _write_jsonl(code_root, "baselines", [row])

    code, out = _gate(code_root, "nvidia_sample")
    assert code == 1, out
    assert "六项深度缺" in out, out
    assert _fatal_lines(out) - _fatal_lines(base_out), "不合规输入未改变违例集合（无判别力）"


def test_nvidia_sample_derivation_reviewable_blocks_on_missing_computation(code_root: Path) -> None:
    """`derivation_reviewable` 反例：建议的『计算』要素不可反查（`derived/` 无底稿）→ 必须红。"""
    _nvidia_compliant(code_root)
    base_out = _gate(code_root, "nvidia_sample")[1]
    _assert_hint_absent(base_out, "四要素")

    (code_root / "derived" / "trace.jsonl").write_text("", encoding="utf-8")

    code, out = _gate(code_root, "nvidia_sample")
    assert code == 1, out
    assert "四要素" in out, out
    assert _fatal_lines(out) - _fatal_lines(base_out), "不合规输入未改变违例集合（无判别力）"


# ── ★ 批次 13-A 新增：`chapter4_g_depth`（`Ch4 §G` 形式完备性）的反例 ─────────────
#
# 该判据此前**未绑定**（`Ch4 §G` 的校验器不存在），故本表原无条目；绑定后必须补反例
# （`criterion_effectiveness_guard` 的义务：已绑定 ⊆ 已登记）。
#
# ★ 为什么需要一个**自备规则文件**的合规输入（本文件其它反例都不需要）：
#   `rules/baseline.yaml` 在真仓库**尚不存在**（由 13-R + 主理人安装），
#   而 `Ch4 §G.2` 的四项阈值**只从它读**（`G-06`：不得内置默认阈值）⇒ 不写它的话，
#   本判据只会输出"规则文件缺失 ⇒ 无法判定"，**判别力无从证明**
#   （合规与不合规输入下都是同一句）。故这里在**夹具副本**内写一份候选规则
#   （`rules/**` 在真仓库是 0444 锁，副本可写 —— 与 `test_prep_*` 的 `_patch_yaml` 同一手法）。

# ★ 阈值**不再由本文件自备**：13-R 已把 `rules/baseline.yaml` + `rules/metric-sets.yaml`
#   安装进仓库并被 `code_root` 夹具原样复制 ⇒ 本用例直接吃**真文件**（比自备候选更强：
#   它同时验证"真文件的结构与代码的读口对得上"——初版曾因深度/键名不合而在这里暴露）。
#   ★ 真文件的 `thresholds.min_fields_per_section` 是 `tbd`（设计未给数值）⇒
#   §G.2 项①的『达最小字段数』半项不可核，只有『非空』半项在强制（`G-03`）；
#   故本用例的合规 baseline 必须让**六项 section 都非空**，而不是"凑够某个字段数"。

#: ★ 判据**专属**标记：只在 `scripts/valuelayer/completeness.py::g_depth_violations()` 的
#:   违例文案里出现（`registry/criterion_counterexamples.yaml` 登记的 `blocked_hint`）。
_CH4_HINT = "Ch4 §G 形式完备性未过"

_CH4_BASELINE_OK: dict = {
    "baseline_id": "baseline-nvda-001",
    "company_id": "co_1",
    "version": 1,
    "business_mechanism": "卖加速计算平台",
    "historical_numeric_claims": ["claim-1"],
    "driver_model": [{"driver_id": "drv-1", "assumptions": ["数据中心 capex 增速维持"]}],
    "value_state_refs": ["vs-1"],
    "business_refs": ["biz-1"],
    "driver_refs": ["drv-1"],
    "moat": [
        {
            "moat_id": "moat-1",
            "mechanism": "CUDA 生态带来的迁移成本",
            "protected_objects": [{"object": "cost", "strength": "high"}],
            "origin_class": "durable_advantage",
            "cross_generation_survival": True,
            "evidence_claims": ["claim-1"],
            "writer": "research_skill",
        }
    ],
    "valuation_inputs": {"growth_assumption": {"value": "0.25", "input_source": "model_estimate"}},
    "valuation": {"method_class": "dcf", "formula_ref": "dv-1"},
    "evidence_claim_ids": ["claim-1"],
    "is_profitable": True,
    "margin_persistence": "云厂商 capex 周期内维持",
    "fcf_persistence": "经营现金流覆盖 capex",
    "reinvestment_return": "ROIIC > WACC",
    "share_dilution_impact": "回购抵消 SBC",
}

_CH4_DRIVER_OK: dict = {
    "driver_id": "drv-1",
    "business_id": "biz-1",
    "source_class": "demand_expansion",
    "importance_class": "high",
    "financial_link": {"accounts": ["revenue_segment"], "per_share_metric": "eps", "formula_ref": "dv-1"},
    "realization_stage": "occurred",
    "timeline": "1-3Y",
    "confidence": "medium",
    "dependencies": ["customer_budget"],
    "assumptions": ["数据中心 capex 增速维持"],
}


def _nvidia_ch4_compliant(root: Path) -> None:
    """阶段② 的 `chapter4_g_depth` **合规**输入：`Ch4 §G.2` 五项 + `§G.4` 盈利分支全过。

    ★ 这一份与 `tests/valuelayer/_fixtures.py::seed_compliant()` **同义**（同一判据的两层证据：
      那里是单元层、这里是经 `stage_gate` 的端到端层）。此处不外引那份夹具，
      因为注入层刻意自备最小输入（本文件其它 `_*_compliant` 都如此），
      且跨目录导入会把两个批次的夹具绑在一起。
    """
    _write_jsonl(root, "baselines", [_CH4_BASELINE_OK])
    _write_jsonl(root, "recommendations", [_RECOMMENDATION_OK])
    _write_jsonl(
        root,
        "implied_requirements",
        [{"requirement_id": "ir-1", "company_id": "co_1", "solved_variable": "growth"}],
    )
    _write_jsonl(
        root,
        "claims",
        [
            {
                "claim_id": "claim-1",
                "locator": "p.12 para.3",
                "status": "verified",
                "moat_evidence_kinds": ["persistent_share"],
            }
        ],
    )
    _write_jsonl(
        root,
        "businesses",
        [{"business_id": "biz-1", "company_id": "co_1", "business_type": "hardware", "metric_set_id": "MS-HW-6STAGE"}],
    )
    _write_jsonl(root, "drivers", [_CH4_DRIVER_OK])
    _write_jsonl(
        root,
        "relations",
        [{"relation_id": "rel-1", "subject_id": "co_1", "object_id": "co_2", "relation_progress_stage": "tbd"}],
    )
    # ★ `operands` 必须是**非空数组**（`§G.2` 项④逐字："推导（**公式 + 操作数**）"）；
    #   本文件上面那份 `_DERIVED_OK` 的 `operands: {}` 会被判成"不合格推导"。
    #
    # ★ 路径必须是 `derived/derived_values.jsonl`：`Ch9 §3.3.3` 的 `DerivedValue` 真源
    #   由 `scripts.compute.store.values_path()` 定义，`iter_all_values()` 只读它。
    #   初版本条写成 `derived/trace.jsonl`（那是上面 ② 阶段那条 `_nvidia_compliant`
    #   顺手写的、**无任何消费者**的文件），结果是"引用了 `dv-1` 但上下文里 0 条推导" ⇒
    #   合规输入也报 `has_derivation` 不合格 —— 一个**假红**，被本测试自己的
    #   `_assert_hint_absent` 抓住（正是该断言存在的意义）。
    (root / "derived" / "derived_values.jsonl").write_text(
        json.dumps(
            {"derived_id": "dv-1", "formula": "rev*margin", "operands": ["rev", "margin"], "method_version": "v1"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def test_nvidia_sample_chapter4_g_depth_blocks_on_incomplete_form(code_root: Path) -> None:
    """`chapter4_g_depth` 反例：baseline 的六项深度**形式上**不全 → 阶段② 必须红。

    ★ 本反例把 `moat`（④）与 `valuation_inputs`（⑤）两个 section 的载体清空 ——
      这正是 `§G` 要拦的"**形式上齐了、实质是空标题**"的同族形态：
      文件里字段在、值也有（`moat: []` 是合法空数组），但**实质没有内容**。

    ★ 判别力归因：合规输入下 `_CH4_HINT` **不出现** —— 证明确实是本判据拦下的，
      不是别的判据顺带变红（阶段② 因未绑定判据台账本就结构性 `exit≠0`，故不靠"红/绿"归因）。
    """
    _nvidia_ch4_compliant(code_root)
    base_out = _gate(code_root, "nvidia_sample")[1]
    _assert_hint_absent(base_out, _CH4_HINT)

    row = dict(_CH4_BASELINE_OK)
    row["moat"] = []
    row["valuation_inputs"] = {}
    _write_jsonl(code_root, "baselines", [row])

    code, out = _gate(code_root, "nvidia_sample")
    assert code == 1, out
    assert _CH4_HINT in out, out
    assert _fatal_lines(out) - _fatal_lines(base_out), "不合规输入未改变违例集合（无判别力）"


# ═════════════════════ 阶段③ core_chain：1 条判据的反例 ═════════════════════

def test_core_chain_multi_company_transmission_blocks_on_single_company(code_root: Path) -> None:
    """`multi_company_transmission` 反例：关系图只涉及 1 家公司 → 必须红。"""
    _write_jsonl(
        code_root,
        "relations",
        [{"relation_id": "r1", "subject_id": "co_1", "object_id": "co_2", "kind": "supplier"}],
    )
    _write_jsonl(
        code_root,
        "impacts",
        [{"impact_id": "i1", "conditions": ["a"], "counter_forces": ["b"], "time_lag": "1Q"}],
    )
    _assert_hint_absent(_gate(code_root, "core_chain")[1], "关系图公司数")

    _write_jsonl(
        code_root,
        "relations",
        [{"relation_id": "r1", "subject_id": "co_1", "object_id": "co_1", "kind": "supplier"}],
    )
    code, out = _gate(code_root, "core_chain")
    assert code == 1, out
    assert "关系图公司数" in out, out


# ═════════════════════ 阶段④ daily_run：4 条判据的反例 ═════════════════════


def test_daily_run_compliant_baseline_is_green(code_root: Path) -> None:
    """★ **判别力归因的关键**：阶段④ 在合规输入下 `exit 0` —— 于是"红了"只能归因于被注入的那条判据。"""
    _daily_compliant(code_root)
    code, out = _gate(code_root, "daily_run")
    assert code == 0, out


def test_daily_run_timing_replayable_blocks_on_missing_run_date(code_root: Path) -> None:
    """`timing_replayable` 反例：`check_record.run_date` 缺失 → 时点不可核 → 必须红。"""
    _daily_compliant(code_root)
    assert _gate(code_root, "daily_run")[0] == 0

    rows = [_task("check_1", "done", output_refs=["rec-1"])]
    rows[0]["check_record"].pop("run_date")
    _write_jsonl(code_root, "tasks", rows)

    code, out = _gate(code_root, "daily_run")
    assert code == 1, out
    assert "缺 run_date" in out, out


def test_daily_run_degrade_keeps_last_valid_blocks_on_dropped_ref(code_root: Path) -> None:
    """`degrade_keeps_last_valid` 反例：先有有效产出、后失败却丢引用 → 必须红。

    ★★ **本反例的输入由真实写路径产出**（`G-43` / `G-45` 的教训）：
      原先手工拼 `[_task("check_1","done",output_refs=["rec-1"]), _task("check_1_r1","failed")]` ——
      那个"成功行"形状**生产代码从未写出过**，于是它对判据的判别力是**假的**
      （审计实测：真实形状 `[done + output_refs=[] + ref=null, failed]` ⇒ **一条真违规都不报**）。
      现在：成功行 / 失败行都由 `pipeline._write_check_record()` 写出，
      再对失败行做**定向违约注入**（把已填好的 `last_valid_result_ref` 抹成 null）。
    """
    _daily_compliant(code_root)
    assert _gate(code_root, "daily_run")[0] == 0

    rows = write_check_records(code_root, [{"blocked": True, "degraded": True}])
    bad_row = rows[-1]
    assert bad_row["last_valid_result_ref"] is not None, (
        "真实写路径**必须**在失败行上填出上一次成功运行的引用（`Ch8 §E.2`）——\n"
        f"若此处为 None，说明写路径没补契约，本反例就又变成'空转'的了：{bad_row}"
    )
    _drop_last_valid_ref(code_root, bad_row["task_id"])

    code, out = _gate(code_root, "daily_run")
    assert code == 1, out
    assert "失败但未保留 last_valid_result_ref" in out, out


def test_daily_run_coverage_verifiable_blocks_on_illegal_depth(code_root: Path) -> None:
    """`coverage_verifiable` 反例：`research_depth` 不在四态内 → 覆盖深度不可核 → 必须红。"""
    _daily_compliant(code_root)
    assert _gate(code_root, "daily_run")[0] == 0

    _write_jsonl(
        code_root, "companies", [{"company_id": "co_1", "research_depth": "bogus_depth"}]
    )
    code, out = _gate(code_root, "daily_run")
    assert code == 1, out
    assert "CV2" in out, out


def test_daily_run_task_state_auditable_blocks_on_illegal_status(code_root: Path) -> None:
    """`task_state_auditable` 反例：`status` 不可判定 → 任务状态不可核 → 必须红。

    ★ 本条**替换**了原先那条 `kind: ineffective` 的探针
      （`..._has_no_discriminating_check`，缺口 `G9-1` 的临时出口）。
      原探针断言的是「注入非法 status 后违例集合**完全相同**」——它随补实现**如期变红**，
      正是探针机制该有的行为；现按裁定把它改成**正向反例**，判别力不降反升
      （从"证明没在查"变成"证明真的会拦"）。

    ★ 判据（`施工图 §2 阶段④` 的 `all_tasks_have_status(run_window)` / `Ch8 §C.2`）=
      「每条任务都有**可判定的** status，**且**落在 `TaskStatus` 合法取值域内」。
      本用例覆盖该判据的**两种违反形态**（同一判据、同一夹具，故合并在一条用例里，
      避免为同一判据重复付夹具成本）：

      | 形态 | 输入 | 为什么也必须红 |
      |---|---|---|
      | **值非法** | `status="totally_bogus_status"` | 键在但值不在域内 ⇒ 状态不可判定 |
      | **字段缺失** | 整行无 `status` 键 | 连值都没有 ⇒ 同样不可判定 |

      ★ 只测"值非法"会漏掉"缺字段"，只测"缺字段"会漏掉"值为任意字符串"——
        两者都是 `not in legal` 判定覆盖的形态，故都要有可执行证据。

    ★ 判别力归因：本用例注入的都是**与其它三条判据无关**的轴
      （`status` 不参与 `run_date` / 覆盖深度 / 降级引用），且阶段④ 合规基线 `exit 0`
      （`test_daily_run_compliant_baseline_is_green`），故"红了"只能归因于本判据。
    """
    _daily_compliant(code_root)
    ok_code, ok_out = _gate(code_root, "daily_run")
    assert ok_code == 0, ok_out
    _assert_hint_absent(ok_out, "不在 TaskStatus 合法取值域内")

    # 形态一：值非法（键在、值不在域内）
    _write_jsonl(code_root, "tasks", [_task("check_1", "totally_bogus_status")])
    code, out = _gate(code_root, "daily_run")
    assert code == 1, f"非法 status 未被拦下（判据没接线）\n{out}"
    assert "不在 TaskStatus 合法取值域内" in out, out
    assert "totally_bogus_status" in out, f"违例必须带**实际值**（否则无法定位）\n{out}"
    assert "check_1" in out, f"违例必须带 task_id（否则无法定位）\n{out}"
    assert "queued" in out, f"违例必须带**合法取值域**（否则不知道该改成什么）\n{out}"
    assert _fatal_lines(out) - _fatal_lines(ok_out), "不合规输入未改变违例集合（无判别力）"

    # 形态二：字段整体缺失（连值都没有）
    row = _task("check_1", "done", output_refs=["rec-1"])
    row.pop("status")
    _write_jsonl(code_root, "tasks", [row])
    code2, out2 = _gate(code_root, "daily_run")
    assert code2 == 1, f"`status` 字段缺失未被拦下\n{out2}"
    assert "不在 TaskStatus 合法取值域内" in out2, out2
    assert "None" in out2, f"缺字段必须以 `None` 显形（区分于'值写错'）\n{out2}"


def test_daily_run_task_state_auditable_counterexample_is_load_bearing(code_root: Path) -> None:
    """★ **判别力绑定**：把 `task_state_auditable` 的新检查掏空 → 上面那条反例**必须失效**。

    与 `test_daily_run_coverage_verifiable_counterexample_is_load_bearing` 同源的理由：
    "已绑定"（AST 里有 `criterion(...)` 字面量）**只证明接了**，不证明**真的在查**。
    本条把"上面那条反例确实由这处检查驱动"钉成**可执行事实**：

    1. 掏空（只改**副本**的 `stage_gate.py`）后，同一条非法 `status` 输入**不再被拦**
       （`exit 1 → 0`）—— 若无此现象，说明那条反例是被别的检查顺带拦下的，归因不成立；
    2. 掏空后 `criteria_bound` **仍是 4** —— 再次证明"绑定数"这个指标**发现不了掏空**。

    ⇒ 两条合起来：**只有数据驱动的反例**能证明"真的在查"；绑定数不能。
    """
    _daily_compliant(code_root)
    _write_jsonl(code_root, "tasks", [_task("check_1", "totally_bogus_status")])
    code, out = _gate(code_root, "daily_run")
    assert code == 1 and "不在 TaskStatus 合法取值域内" in out, out

    # 掏空：把新检查的谓词置为恒假（只改副本的 stage_gate.py）
    gate_src = code_root / GATE
    text = gate_src.read_text(encoding="utf-8")
    anchor = "        if not isinstance(got, str) or got not in legal_status:\n"
    assert anchor in text, "找不到 task_state_auditable 的判定行（实现已变？请更新本用例）"
    gate_src.write_text(
        text.replace(anchor, "        if False:  # gutted-for-probe\n"), encoding="utf-8"
    )

    proc = subprocess.run(
        [sys.executable, str(code_root / GATE), str(code_root), "--no-report", "--stage", "daily_run"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    gutted = proc.stdout + proc.stderr
    assert proc.returncode == 0, (
        "掏空 task_state_auditable 的检查后门禁仍拦截 —— 说明那条反例不由此处驱动，"
        "判别力归因不成立：\n" + gutted
    )
    assert "daily_run.criteria_bound: 4" in gutted, (
        "掏空后 criteria_bound 未保持 4 —— 「绑定数发现不了掏空」这一结论需重新核实：\n" + gutted
    )


def test_daily_run_coverage_verifiable_counterexample_is_load_bearing(code_root: Path) -> None:
    """★ **复现并钉死**审计员报告的现象（`G9` 的核心）。

    独立审计：把 `cv = coverage_check(root)` 换成空 `CheckReport` 后
    `criteria_bound` 仍为 4，而不达标数据下门禁**变绿**。

    本用例在一个**副本**上复现该掏空（改的是副本的 `stage_gate.py`，真仓库零污染），
    并断言两件事同时成立：

    1. 掏空后，同一条反例输入 **不再被拦**（`exit 0`）—— 现象复现；
    2. 掏空后 `criteria_bound` **仍是 4** —— 证明「绑定数」这个指标**无法**发现掏空。

    ⇒ 结论：AST 绑定只能证明"接了"；**只有这条数据驱动的反例**才能证明"真的在查"。
      而它正是本文件 `test_daily_run_coverage_verifiable_blocks_on_illegal_depth`。

    第 3 件事：掏空后**由副本自己**跑 `stage_gate --stage daily_run`，确认这条反例
    在掏空版本上失效 —— 即本文件那条反例用例**会红**，掏空不可能静默通过。
    """
    _daily_compliant(code_root)
    assert _gate(code_root, "daily_run")[0] == 0

    _write_jsonl(
        code_root, "companies", [{"company_id": "co_1", "research_depth": "bogus_depth"}]
    )
    code, out = _gate(code_root, "daily_run")
    assert code == 1 and "CV2" in out, out

    # 掏空：把覆盖检查换成空 CheckReport（只改副本）
    gate_src = code_root / GATE
    text = gate_src.read_text(encoding="utf-8")
    old = "    cv = coverage_check(root)\n"
    assert old in text, "stage_gate 里找不到 coverage_check 调用点（实现已变？请更新本用例）"
    gate_src.write_text(
        text.replace(old, '    cv = CheckReport(checker="gutted-for-probe")\n'), encoding="utf-8"
    )

    proc = subprocess.run(
        [sys.executable, str(code_root / GATE), str(code_root), "--no-report", "--stage", "daily_run"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    gutted = proc.stdout + proc.stderr
    assert proc.returncode == 0, (
        "掏空 coverage_check 后门禁仍拦截 —— 说明另有检查在起作用（现象未能复现）：\n" + gutted
    )
    assert "daily_run.criteria_bound: 4" in gutted, (
        "掏空后 criteria_bound 未保持 4 —— 与审计报告不一致，请重新核实：\n" + gutted
    )


# ═════════════════════ 阶段⑤ expansion：1 条判据的反例 ═════════════════════


def test_expansion_review_append_only_blocks_on_missing_layer(code_root: Path) -> None:
    """「三层复盘齐备」的反例：缺一层 → 阶段⑤ 必须红。

    ★ **同一条 id 上有两件不同的事**（如实声明，勿混淆）：
      ① **本用例**证明的是「三层复盘齐备」这个检查**有判别力**；
      ② `test_expansion_review_append_only_blocks_on_layer_disappearing` 与
         `..._when_guard_pathspec_misses_carrier` 证明的是 `Ch10 §D.5` 的**真 append-only**
         语义已被守（本批次 `G9-2` 补实现）。
      两者都挂在 `review_append_only` 这一个 id 上 —— 因为 `registry/delivery.yaml` 里
      **没有**"三层齐备"自己的 id（见报告 §3 G9-2 的实测）。

    ★ **待裁定**：「三层齐备」在全设计区**没有"通过判据"级的逐字出处**
      （`Ch10 §C.1` 只定义 `eval_layer` 的**取值域**；`§C.4:250` 的 `assert layer in
      VALID_LAYERS, "三层不得新增/合并"` 也是取值域断言；`施工图:215/234` 只在**退出物**
      里写了"三层复盘记录"）。team-lead 裁定前，本条**留在 `review_append_only` 上**，
      不自行政措辞或新增 id（`R-04`）。
    """
    _expansion_compliant(code_root)
    base_out = _gate(code_root, "expansion")[1]
    _assert_hint_absent(base_out, "三层复盘缺层")

    _write_jsonl(
        code_root,
        "tasks",
        [
            {"task_id": "t1", "eval_result": {"eval_layer": "research_quality"}},
            {"task_id": "t2", "eval_result": {"eval_layer": "forecast_quality"}},
        ],
    )
    code, out = _gate(code_root, "expansion")
    assert code == 1, out
    assert "三层复盘缺层" in out, out
    assert _fatal_lines(out) - _fatal_lines(base_out), "不合规输入未改变违例集合（无判别力）"


def test_expansion_review_append_only_blocks_on_layer_disappearing(code_root: Path) -> None:
    """`review_append_only` 反例（**真判别力所在**）：已声明过的 `eval_layer` 从记录集里消失。

    ★ 本条**替换**了原先那条 `kind: ineffective` 的探针
      （`..._semantics_have_no_discriminating_check`）—— 它随补实现**如期变红**，
      现按裁定改成**正向反例**。

    ★ 逐字依据 `Ch10 §D.5` 第 3 行：「**禁"只留赢的"**：断言 **某标的的复盘记录集合
      ⊇ 其历史全部建议（含已验证失败者）**」；第 1 行「三类记录齐全……不可选择性删除」。

    ★ **为什么这条不是重造 append-only 比对**（`G-06` 的关键）：造的那个反例在 **diff 层面
      完全合法**（纯追加，没有任何既有行被改写）——`append_only_guard` 对它**必然放行**。
      它违反的是**语义**：用户看到的历史被悄悄收窄。两者被检面不重叠、互补。

    ★ 反例构造（同一任务在追加序上先声明三层、后只剩一层）：

    | 追加序 | 行 | 该行声明的层 |
    |---|---|---|
    | 1 | `t1`（`eval_result_history` 含三层） | {research_quality, forecast_quality, investment_result} |
    | 2 | `t1`（只剩 `research_quality`） | {research_quality} ← **丢了 FQ / IR** |

    ★ 同用例内**顺带**给出**合法**对照（同一任务层集合**单调不减**）→ 该 hint 必须不出现：
      否则"多层任务"会无差别报错，判据就成了误报源。
    """
    _expansion_compliant(code_root)
    base_out = _gate(code_root, "expansion")[1]
    _assert_hint_absent(base_out, "消失（此前已声明过）")

    # 合法对照：同一任务多层，且追加序上**只增不减** ⇒ 不报
    _write_jsonl(
        code_root,
        "tasks",
        [
            {"task_id": "t1", "eval_result": {"eval_layer": "research_quality"}},
            {
                "task_id": "t1",
                "eval_result": {"eval_layer": "forecast_quality"},
                "eval_result_history": [
                    {"eval_layer": "research_quality"},
                    {"eval_layer": "forecast_quality"},
                ],
            },
            {
                "task_id": "t1",
                "eval_result": {"eval_layer": "investment_result"},
                "eval_result_history": [
                    {"eval_layer": "research_quality"},
                    {"eval_layer": "forecast_quality"},
                    {"eval_layer": "investment_result"},
                ],
            },
            {"task_id": "t2", "eval_result": {"eval_layer": "research_quality"}},
            {"task_id": "t3", "eval_result": {"eval_layer": "forecast_quality"}},
        ],
    )
    ok_code, ok_out = _gate(code_root, "expansion")
    _assert_hint_absent(ok_out, "消失（此前已声明过）")

    # 反例：同一任务先声明三层、后只剩一层（纯追加，diff 层面对 append-only 完全合法）
    _write_jsonl(
        code_root,
        "tasks",
        [
            {
                "task_id": "t1",
                "eval_result_history": [
                    {"eval_layer": "research_quality"},
                    {"eval_layer": "forecast_quality"},
                    {"eval_layer": "investment_result"},
                ],
            },
            {"task_id": "t1", "eval_result": {"eval_layer": "research_quality"}},
            {"task_id": "t2", "eval_result": {"eval_layer": "forecast_quality"}},
            {"task_id": "t3", "eval_result": {"eval_layer": "investment_result"}},
        ],
    )
    code, out = _gate(code_root, "expansion")
    assert code == 1, out
    assert "消失（此前已声明过）" in out, out
    assert "t1" in out, f"违例必须带 task_id（否则无法定位是哪条记录被收窄）\n{out}"
    assert _fatal_lines(out) - _fatal_lines(base_out), "不合规输入未改变违例集合（无判别力）"
    assert ok_code == 1, (
        "★ 阶段⑤ 在合规输入下**结构上就是 exit 1**（两条未绑定判据的台账条目），"
        "故本条反例的归因不靠 red/green 而是靠「专属 hint + 违例集合差」。"
        "若此处 exit 变成 0，说明阶段⑤ 的绑定状态变了，请重新评估本用例的归因方式。\n" + ok_out
    )


def test_expansion_review_append_only_blocks_when_guard_pathspec_misses_carrier(
    code_root: Path,
) -> None:
    """`review_append_only` 反例（`Ch10 §D.5` 第 2 行）：append-only 守卫**没罩住**本真源。

    ★ **为什么"机制存在"不等于"机制生效"**：`append_only_guard` 曾有**既有假绿** ——
      linked worktree 里钩子导出的 `GIT_DIR` 让 `rev-parse --show-toplevel` 返回 cwd
      ⇒ pathspec 指错 ⇒ `git diff --cached` **恒空** ⇒ 守卫对任何输入都放行（`G-RC-12`）。
      这正是"复盘 append-only 没人守"的形态，故必须有一条**可执行反例**钉住它。

    ★ 判据的读法是「**读它的判据、不读它的输出文字**」（`G-06`，team-lead 裁定 2）：
      本用例把副本 `append_only_guard.py` 的 `facts_pathspec()` 改成指向**别的目录**，
      然后断言阶段⑤ **变红**并给出"未覆盖本函数所读的 facts/*.jsonl"。

    ★ 必须跑**副本那份** `stage_gate.py`（`subprocess`）：真仓库那份的 `_ROOT` 指向真文件，
      `from scripts.checks.append_only_guard import ...` 会解析到**真仓库**的守卫，
      于是看不到副本里的改动（与 `bound_criteria()` 同源的坑）。
    """
    _expansion_compliant(code_root)

    gate_src = code_root / GATE
    aog_src = code_root / "scripts" / "checks" / "append_only_guard.py"
    assert aog_src.exists(), f"副本里没有 append_only_guard（夹具跳过清单变了？）: {aog_src}"

    # 掏空：让守卫的 pathspec 指向一个**不覆盖本真源**的 glob（只改副本）
    aog_text = aog_src.read_text(encoding="utf-8")
    anchor = '    return f"{rel.as_posix()}/*.jsonl"\n'
    assert anchor in aog_text, "append_only_guard.facts_pathspec 的实现变了，请更新本用例"
    aog_src.write_text(
        aog_text.replace(anchor, '    return f"{rel.as_posix()}/*.bak"\n'), encoding="utf-8"
    )

    proc = subprocess.run(
        [sys.executable, str(gate_src), str(code_root), "--no-report", "--stage", "expansion"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, (
        "append-only 守卫的 pathspec 没罩住本真源，阶段⑤ 却放行了 —— "
        "『复盘 append-only 真的生效』这条无法被机器证伪：\n" + out
    )
    assert "未覆盖本函数所读的 facts/*.jsonl" in out, out
    assert "aog_covers_carrier: 0" in out, f"覆盖性必须计入 scanned（可观测）\n{out}"


def test_expansion_review_append_only_outcome_categories_have_no_check(code_root: Path) -> None:
    """★ **临时 `ineffective` 登记**：`Ch10 §D.5` 第 1 行「三类记录齐全」**无可检对象**。

    `Ch10 §D.5` 第 1 行逐字：「**三类记录齐全**：成功 / 失败 / `pending`（待判断）各有结构性记录，
    **不可选择性删除**（`N10.3-04`）」；`施工图:234` 亦写 `(success, failure, pending) ⊆ 记录集`。

    ★ **实测缺口**：`success`/`failure`/`pending` 这个三元组在**整个代码区只出现 1 次** ——
      `registry/delivery.yaml:132` 的那句声明本身。`schema/models.py` 里**没有**对应枚举，
      `facts/*.jsonl` 里**没有**对应字段 ⇒ 这条约束**没有可检查的载体**，按 `G-03`
      只能显式记账为"无被检对象"，**不得当成已验证**。

    ★ 探针断言（`kind: ineffective` 的定义）：把 `outcome` 由 `success`/`failure`/`pending`
      混搭改成**全 `success`**（即字面语义上的"只留赢的"）→ 阶段⑤ 的违例集合**完全相同**。

    ★ **临时性**：本条**不是**"这条路已经没问题"，而是"等 team-lead 指定 `(success, failure,
      pending)` 的载体（或确认它属后续阶段待交付）后补实现"。补实现的提交号见报告 §3 G9-2；
      实现后本探针**当场变红**，强制把登记改掉。
    """
    rows_mixed = [
        {"task_id": "t1", "eval_result": {"eval_layer": "research_quality", "outcome": "success"}},
        {"task_id": "t2", "eval_result": {"eval_layer": "forecast_quality", "outcome": "failure"}},
        {"task_id": "t3", "eval_result": {"eval_layer": "investment_result", "outcome": "pending"}},
    ]
    rows_only_winners = [
        {"task_id": "t1", "eval_result": {"eval_layer": "research_quality", "outcome": "success"}},
        {"task_id": "t2", "eval_result": {"eval_layer": "forecast_quality", "outcome": "success"}},
        {"task_id": "t3", "eval_result": {"eval_layer": "investment_result", "outcome": "success"}},
    ]

    _write_jsonl(code_root, "tasks", rows_mixed)
    mixed_out = _gate(code_root, "expansion")[1]
    _write_jsonl(code_root, "tasks", rows_only_winners)
    winners_out = _gate(code_root, "expansion")[1]

    assert _fatal_lines(winners_out) == _fatal_lines(mixed_out), (
        "「只留赢的」后违例集合发生了变化 —— 说明**三类记录**这条已被检查："
        "请把 registry/criterion_counterexamples.yaml 里 review_append_only 的该 ineffective 条目"
        "改为/补上 counterexample 条目，并更新报告 §3 G9-2。\n"
        f"混搭（success/failure/pending）:\n{mixed_out}\n只留赢的（全 success）:\n{winners_out}"
    )


# ═══════════ 义务本身的机器绑定（H2）：新绑判据却不登记 → 门禁必须红 ═══════════


def _guard(root: Path) -> tuple[int, str]:
    """跑判据有效性门禁（**进程内、不走 `run_gate` 的 session 级缓存**）。

    `run_gate` 对同一 `(脚本, code_root, 参数)` 只跑一次；本文件的用例普遍
    "改夹具 → 再跑同一命令"，用它会拿到**改动前**的结果（`conftest.run_gate` 已警告）。
    """
    return run_gate_inproc(GUARD, root)


# ═══════════════════ 计数派生（卡 13-J：写死计数 → 从真源派生）═══════════════════
#
# ★ 为什么**不能**把期望值改成"调用门禁内部那个函数"：那样两边**同源** ⇒ **自反断言**
#   （真源算错也照样绿），比写死**更糟** —— 写死至少会红。
# ⇒ 故本节刻意走**两条独立路径**，任一管道走歪都会红：
#     ① **期望值** = 测试**自己**数（自己 `yaml.safe_load` 解析登记表；自己按路径加载被检
#        副本那份 `stage_gate.py` 取绑定集合）——不 import 门禁的任何私有函数；
#     ② **实际值** = **门禁 CLI 打印文本**里的 `scanned <key>: N`（**文本解析**）。
# ★ 并额外留三条**关系式「锚」**（在下面的 `_assert_counts_match` 里）：即使有人把某个派生
#   写成了恒真，锚也会因"划分/穷尽/方向"不成立而红。
#
# ★ 诚实标注（防把这条判据说过头）：`criteria_bound` 的真源只有 `stage_gate.bound_criteria()`
#   一个（`G-06`：门禁不得另写解析），所以这一路两边的"数据源"必然相同 —— 它真正在核的是
#   **"门禁的统计/打印管道 == 直接聚合"**，**不是**"真源本身算对了"。真源本身的正确性由
#   `stage_gate` 自己的用例与门禁的断言 E（与 `criteria_not_implemented()` 逐阶段对拍）承担。

_COUNT_KEYS = (
    "criteria_bound",
    "criteria_registry_entries",
    "counterexample_entries",
    "ineffective_entries",
    "criteria_without_counterexample",
)


def _scanned(out: str, key: str) -> int:
    """取门禁 CLI 文本里的 `scanned <key>: N`（**文本路径**）。"""
    prefix = f"scanned {key}: "
    hits = [ln.strip() for ln in out.splitlines() if ln.strip().startswith(prefix)]
    assert len(hits) == 1, f"`{key}` 在门禁输出里出现 {len(hits)} 次（应为 1）：\n{out}"
    return int(hits[0][len(prefix) :])


def _registry_rows(code_root: Path) -> list[dict]:
    """**自己**解析登记表（不走门禁的 `_entries()`）。"""
    doc = yaml.safe_load((code_root / REGISTRY).read_text(encoding="utf-8"))
    assert isinstance(doc, dict), f"{REGISTRY} 顶层不是 mapping"
    rows = doc.get("counterexamples")
    assert isinstance(rows, list), f"{REGISTRY} 缺 counterexamples 列表"
    return [r for r in rows if isinstance(r, dict)]


def _bound_pairs(code_root: Path) -> set[tuple[str, str]]:
    """**自己**加载**被检副本**那份 `stage_gate.py` 取绑定集合（不复用门禁的加载器）。

    ★ 必须加载副本那一份：`bound_criteria()` 用 `Path(__file__)` 定位自身，
      加载副本才能让"往副本里加一行 `criterion(...)`"真的改变绑定集合。
    ★ `P-04`：`stage_gate.py` 模块级会 `sys.path.insert`，故全局副作用必须复原，
      否则同进程内后续检查器会加载到副本的 `scripts`。
    """
    path = code_root / "scripts" / "delivery" / "stage_gate.py"
    assert path.exists(), f"缺少判据绑定的唯一真源: {path}"
    name = "_stage_gate_for_count_derivation"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"无法加载 {path}"
    module = importlib.util.module_from_spec(spec)
    before_modules = set(sys.modules)
    before_path = list(sys.path)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        bound = module.bound_criteria()
    finally:
        sys.path[:] = before_path
        sys.modules.pop(name, None)
        for extra in set(sys.modules) - before_modules:
            if extra == "scripts" or extra.startswith("scripts."):
                sys.modules.pop(extra, None)
    return {(str(stage), str(cid)) for stage, ids in bound.items() for cid in ids}


def _derived_counts(code_root: Path) -> dict[str, int]:
    """**期望值**：测试自己从真源算出来的五个计数（**不读门禁的任何对象**）。"""
    rows = _registry_rows(code_root)
    counterexample_pairs = {
        (str(r.get("stage")), str(r.get("criterion_id")))
        for r in rows
        if str(r.get("kind")) == "counterexample"
    }
    bound = _bound_pairs(code_root)
    return {
        "criteria_bound": len(bound),
        "criteria_registry_entries": len(rows),
        "counterexample_entries": sum(1 for r in rows if str(r.get("kind")) == "counterexample"),
        "ineffective_entries": sum(1 for r in rows if str(r.get("kind")) == "ineffective"),
        # 语义同门禁 F 段：已绑定但**一条 counterexample 都没有**的判据数。
        "criteria_without_counterexample": len(bound - counterexample_pairs),
    }


def _assert_count_anchors(sc: dict[str, int]) -> None:
    """三条关系式「锚」（抽出来是为了能被反向对照**逐个**证明会红）。

    它们是**粗粒度恒等式**，用来兜住"某个派生被写成恒真"的情形：任一计数走歪、或出现
    第三套谓词，这三条里至少有一条不成立。
    """
    # 锚① 穷尽性：每条登记非 counterexample 即 ineffective，没有第三类 ⇒ 两数相加必等于总数。
    assert (
        sc["counterexample_entries"] + sc["ineffective_entries"] == sc["criteria_registry_entries"]
    ), f"登记条目未被 kind 二分穷尽（有第三类 kind，或某个计数走歪）：{sc}"
    # 锚② 划分恒等式：declared = bound + not_implemented（三者都取自门禁自己报的数）。
    assert (
        sc["criteria_bound"] + sc["criteria_not_implemented"] == sc["criteria_declared_automated"]
    ), f"「已绑定 + 未绑定 != 声明 automated」—— 两侧出现了第二套谓词或计数走歪：{sc}"
    # 锚③ 义务方向：已绑定 ⊆ 已登记 ⇒ 登记条数不得少于绑定判据数。
    assert (
        sc["criteria_registry_entries"] >= sc["criteria_bound"]
    ), f"登记条数少于绑定判据数 —— A 义务（已绑定必有登记）不成立：{sc}"


def _assert_counts_match(out: str, code_root: Path) -> None:
    """**派生断言本体**（抽成函数是为了能被反向对照直接调用）。

    ① 五键逐条：门禁**打印的数** == 测试**自己数**的数；
    ② 三条关系式「锚」——纯文本可核，防"派生把判据稀释成恒真"。
    """
    scanned = {key: _scanned(out, key) for key in _COUNT_KEYS}
    derived = _derived_counts(code_root)
    for key in _COUNT_KEYS:
        assert scanned[key] == derived[key], (
            f"`{key}`：门禁报 {scanned[key]}，测试自己数得 {derived[key]} —— "
            f"两条路径不一致（说明门禁的统计管道或本测试的派生逻辑有一处走歪）\n{out}"
        )
    _assert_count_anchors(
        {
            **scanned,
            "criteria_not_implemented": _scanned(out, "criteria_not_implemented"),
            "criteria_declared_automated": _scanned(out, "criteria_declared_automated"),
        }
    )


def test_derived_counts_follow_a_registry_change_without_editing_literals(
    code_root: Path,
) -> None:
    """**可执行反例（正向）**：真源里**去掉一条**登记 ⇒ 计数自动跟上，**不必**来改字面量。

    选 `expansion::review_append_only` 的**最后一条** counterexample（该判据共有 3 条
    counterexample + 1 条 ineffective）⇒ 删掉后它**仍有** counterexample ⇒ 门禁仍 `exit 0`，
    于是本条只考察"计数是否跟着真源走"，不掺"义务被违反"的旁支。
    """
    path = code_root / REGISTRY
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = list(doc["counterexamples"])
    before = _derived_counts(code_root)

    victims = [
        i
        for i, r in enumerate(rows)
        if str(r.get("stage")) == "expansion"
        and str(r.get("criterion_id")) == "review_append_only"
        and str(r.get("kind")) == "counterexample"
    ]
    assert len(victims) >= 2, f"该判据的 counterexample 少于 2 条，删一条会触发义务违例：{victims}"
    idx = victims[-1]
    doc["counterexamples"] = rows[:idx] + rows[idx + 1 :]
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    # 口径 1′（注入/篡改型实验的三条自证）：① 锚点在（victims 非空）② 前后不同 ③ 已读回确认落盘
    back = yaml.safe_load(path.read_text(encoding="utf-8"))["counterexamples"]
    assert len(back) == len(rows) - 1, "变更未落盘（读回条数没变）"

    code, out = _guard(code_root)
    assert code == 0, f"删掉一条**非最后一条**反例后门禁不应阻断\n{out}"
    _assert_counts_match(out, code_root)  # ← 全程没改任何字面量
    after = _derived_counts(code_root)
    assert after["counterexample_entries"] == before["counterexample_entries"] - 1, (
        "计数没跟着真源走 —— 说明它读的不是真源"
    )
    assert after["criteria_registry_entries"] == before["criteria_registry_entries"] - 1
    assert _scanned(out, "counterexample_entries") == after["counterexample_entries"]


def test_derived_count_assertion_is_load_bearing(code_root: Path) -> None:
    """**反向对照（防真空）**：证明"跟不上**会红**"。

    ★ 没有这一半，"能自动跟上"这句话是**真空的** —— 与 `G9`「绑定只证明接了、不证明真的在查」同型。
    四个方向各证一次，缺一个都会留下一个"改坏了也不响"的洞：
      ① **文本侧**篡改（门禁报数被改坏）⇒ 五键逐条必红；
      ② **真源侧**篡改但**不重跑**门禁（期望值变、文本没变）⇒ 必红；
      ③ 三条**关系式锚**逐个被喂入坏数字 ⇒ 每个都必须能红；
      ④ 干净输入 ⇒ 必须绿（否则上面的"红"可能只是断言恒假）。
    """
    code, out = _guard(code_root)
    assert code == 0, out
    _assert_counts_match(out, code_root)  # ④ 前提：干净输入是绿的

    # ① 文本侧：把 counterexample_entries 的报数 +1
    n = _scanned(out, "counterexample_entries")
    tampered_text = out.replace(
        f"scanned counterexample_entries: {n}", f"scanned counterexample_entries: {n + 1}", 1
    )
    assert tampered_text != out, "注入点不存在（文本侧）"
    with pytest.raises(AssertionError):
        _assert_counts_match(tampered_text, code_root)

    # ② 真源侧：删一条登记（**不重跑门禁**）⇒ 期望值变、文本没变 ⇒ 必红
    path = code_root / REGISTRY
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = list(doc["counterexamples"])
    doc["counterexamples"] = rows[:-1]
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    landed = yaml.safe_load(path.read_text(encoding="utf-8"))["counterexamples"]
    assert len(landed) == len(rows) - 1, "变更未落盘（真源侧）"
    with pytest.raises(AssertionError):
        _assert_counts_match(out, code_root)

    # ③ 三条锚逐个证明"能红"：基线**取自刚才那次干净运行**（不写死字面量，避免又开一处台账副本）
    good = {
        **{k: _scanned(out, k) for k in _COUNT_KEYS},
        "criteria_not_implemented": _scanned(out, "criteria_not_implemented"),
        "criteria_declared_automated": _scanned(out, "criteria_declared_automated"),
    }
    _assert_count_anchors(good)  # 基线必须绿，否则下面的"红"毫无意义（假通过同样是假的）
    # 锚①：kind 两数不再穷尽登记总数
    with pytest.raises(AssertionError):
        _assert_count_anchors({**good, "ineffective_entries": good["ineffective_entries"] + 1})
    # 锚②：划分恒等式被打破（declared != bound + not_implemented）
    with pytest.raises(AssertionError):
        _assert_count_anchors(
            {**good, "criteria_declared_automated": good["criteria_declared_automated"] + 1}
        )
    # 锚③（**隔离**）：登记数 < 绑定数，但 kind 两数相加仍等于登记数 ⇒ 只有锚③该红
    with pytest.raises(AssertionError):
        _assert_count_anchors(
            {
                **good,
                "criteria_registry_entries": good["criteria_bound"] - 1,
                "counterexample_entries": good["criteria_bound"] - 2,
                "ineffective_entries": 1,
            }
        )


def test_criterion_effectiveness_guard_passes_on_pristine_tree(code_root: Path) -> None:
    """**反向对照（H3-反例）**：登记完整 → 门禁 `exit 0` 且报出 `scanned`。

    ★ 卡 13-J：五个计数**不再写死字面量**，改由 `_assert_counts_match` 派生核对 ——
      期望值 = 本测试自己从真源数；实际值 = 门禁 CLI 文本。**新增判据时不必再来改数字**
      （"跟不上会红"由 `test_derived_count_assertion_is_load_bearing` 单独证明）。
    """
    code, out = _guard(code_root)
    assert code == 0, f"登记完整时门禁不应阻断\n{out}"
    assert "scanned " in out, f"未上报 scanned 计数（无法区分「没扫」与「扫了没问题」）\n{out}"
    _assert_counts_match(out, code_root)
    assert "review_append_only" in out, "语义错位的判据必须逐条可见（G-03）"
    # 缺口 `G9-1` 已闭合（`task_state_auditable` 补实现 + 反例由 ineffective 改 counterexample）。
    # ★ 这条断言是**反向**的：它钉住"该判据**不再**出现在缺口清单里" —— 若有人把登记退回
    #   `ineffective`（或删掉反例），本断言当场红。
    assert "判据有效性缺口[daily_run::task_state_auditable]" not in out, (
        f"`task_state_auditable` 又出现在缺口清单里 —— G9-1 的补实现或登记被退回？\n{out}"
    )


def test_removing_any_registry_entry_makes_guard_fail(code_root: Path) -> None:
    """**正向对照（H3-正例）**：删掉任意一条已绑定判据的登记 → 门禁必须 `exit 1`。

    逐条参数化：**每一条**登记都真的在被强制（不是只有第一条好使）。
    """
    path = code_root / REGISTRY
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = list(doc["counterexamples"])
    # ★ 卡 13-J：这里原来写死的 `len(entries) == 16` **不是在核对数字**，而是在**防真空** ——
    #   若登记为空，下面的参数化循环会执行 0 次、本用例**静默通过**（"没测"与"通过"观测上等价）。
    #   ⇒ 正确修法**不是**换成 `len(entries) == <派生数>`（那又变成自反、且与真源同源），
    #      而是：① 显式断言非空；② 数出**实际逐条检查了几条**并要求它等于总条数。
    assert entries, "登记为空 ⇒ 参数化循环执行 0 次、本用例真空（什么都没测）"
    monkey_checked = 0
    for idx, row in enumerate(entries):
        doc["counterexamples"] = entries[:idx] + entries[idx + 1 :]
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        code, out = _guard(code_root)
        # `review_append_only` 有**多条**条目（1 ineffective + 3 counterexample）：删掉其中一条时
        # 该判据仍有条目 ⇒ 门禁可以放行。允许多条目正是为了让"所绑定的检查有判别力"、
        # "字面语义的每个方面各自有证据"、"暂无载体的方面显式记账"三件事各自留证。
        remaining = {
            (str(r.get("stage")), str(r.get("criterion_id")))
            for r in doc["counterexamples"]
        }
        expected = 1 if (str(row["stage"]), str(row["criterion_id"])) not in remaining else 0
        assert code == expected, (
            f"删掉 {row['stage']}::{row['criterion_id']}（kind={row['kind']}）的登记后，"
            f"门禁退出码应为 {expected}，实得 {code}\n{out}"
        )
        if expected:
            assert row["criterion_id"] in out, out
        monkey_checked += 1
    assert monkey_checked == len(entries), (
        f"只逐条检查了 {monkey_checked}/{len(entries)} 条 —— 循环被提前中断，"
        "后面的条目**没有被验证**（静默漏测）"
    )
    doc["counterexamples"] = entries
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_newly_bound_criterion_without_registration_makes_guard_fail(code_root: Path) -> None:
    """★ **H2 的核心**：新绑一条 automated 判据但**不登记反例** → 门禁必须 `exit 1`。

    构造方式（全在副本上）：往 `registry/delivery.yaml` 的 prep 阶段加一条 automated 判据，
    **并**往副本 `stage_gate.py` 的 `stage_prep_passed()` 函数体里加一行 `criterion(...)`
    —— 于是它成为"已绑定"。门禁读的正是副本的 `stage_gate.py`（按路径加载），
    故这确实模拟了真实的"新绑一条判据"。
    """
    tag = "invented_bound_criterion_no_counterexample"

    dpath = code_root / DELIVERY
    doc = yaml.safe_load(dpath.read_text(encoding="utf-8"))
    for stage in doc["delivery_stages"]:
        if stage.get("key") == "prep":
            stage["pass_criteria_testable"].append(
                {"id": tag, "statement": "新绑但未登记反例的判据", "check_kind": "automated"}
            )
    dpath.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    gpath = code_root / GATE
    text = gpath.read_text(encoding="utf-8")
    anchor = '    v += assert_criteria_implemented(root, "prep")\n'
    assert anchor in text, "stage_prep_passed 的结构变了，请更新本用例"
    gpath.write_text(
        text.replace(anchor, f'    criterion("prep", "{tag}", v)\n' + anchor), encoding="utf-8"
    )

    # 前提确认：副本上它**确实已绑定**（否则本用例可能因为别的原因变红，属假阳性）。
    # ★ 必须跑**副本那份** stage_gate（真仓库那份的 `_SELF_PATH` 指向真文件，
    #   `bound_criteria()` 看不到副本的改动）—— 这与门禁 `_load_stage_gate()` 同源。
    proc = subprocess.run(
        [sys.executable, str(code_root / GATE), str(code_root), "--no-report", "--stage", "prep"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    bound_out = proc.stdout + proc.stderr
    assert "prep.criteria_bound: 5" in bound_out, (
        f"注入的判据未被绑定（bound 应为 5）—— 用例构造失败\n{bound_out}"
    )

    code, out = _guard(code_root)
    assert code == 1, (
        f"新绑定判据 {tag} 却没有反例登记，门禁却放行了 —— 义务没有机器绑定\n{out}"
    )
    assert tag in out, out
    assert "已在" in out and "函数体内绑定" in out, out


def test_registry_entry_pointing_to_missing_test_makes_guard_fail(code_root: Path) -> None:
    """登记指向一个**不存在**的测试 → 门禁必须 `exit 1`（义务不得靠字符串占位履行）。"""
    path = code_root / REGISTRY
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["counterexamples"][0]["test"] = (
        "tests/injection/test_criterion_effectiveness.py::test_four_deliverables_nonexistent_xyz"
    )
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    code, out = _guard(code_root)
    assert code == 1, out
    assert "不存在测试函数" in out or "未含判据 id" in out, out


def test_registry_entry_for_unbound_criterion_makes_guard_fail(code_root: Path) -> None:
    """**登记 ⊆ 已绑定**：给一条"声明为 automated 但未绑定"的判据登记 → 必须 `exit 1`。

    否则可以先把**将来要绑**的判据预登记，从而在真正绑定时免于义务。
    """
    path = code_root / REGISTRY
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["counterexamples"].append(
        {
            "stage": "nvidia_sample",
            "criterion_id": "evidence_locatable",
            "kind": "counterexample",
            "test": "tests/injection/test_criterion_effectiveness.py::test_prep_compliant_baseline_is_green",
            "blocked_hint": "x",
            "note": "预登记（未绑定）",
        }
    )
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    code, out = _guard(code_root)
    assert code == 1, out
    assert "未被绑定" in out, out


def test_guard_is_registered_in_runner_and_precommit() -> None:
    """`G-07`：新守卫必须同时进 `run_all_gates.py` 与 `pre-commit.sh`（防孤儿守卫）。"""
    runner = (SYSTEM_ROOT / "scripts" / "ops" / "run_all_gates.py").read_text(encoding="utf-8")
    hook = (SYSTEM_ROOT / "scripts" / "ops" / "pre-commit.sh").read_text(encoding="utf-8")
    assert "criterion_effectiveness_guard.py" in runner, "未注册进门禁跑测器"
    assert "criterion_effectiveness_guard.py" in hook, "未注册进 pre-commit"


def test_guard_reports_input_error_for_missing_code_root() -> None:
    """**退出码契约**（`§八 N-2`）：`code_root` 不存在 → 必须 `2`，不得折叠成 0（静默放行）。

    ★ 这里**没有**把本守卫加进 `tests/guards/test_exit_code_contract.py::GUARDS` 矩阵
      （那会把共享矩阵的 `len(GUARDS)` 断言一并改动，与 `ws-guards-catchup` 的范围重叠）；
      本用例与 `test_criterion_effectiveness_guard_passes_on_pristine_tree` 合起来
      覆盖与矩阵相同的三条契约：干净输入 → 0 + 报 `scanned`、`code_root` 缺失 → 2。
    """
    code, out = run_gate_inproc(GUARD, Path("/nonexistent/code_root_for_criterion_guard"))
    assert code == 2, f"缺少 code_root 应返回 2（输入异常），实得 {code}\n{out}"
