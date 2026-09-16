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


def test_daily_run_task_state_auditable_has_no_discriminating_check(code_root: Path) -> None:
    """★ **如实登记的缺口**（`registry/criterion_counterexamples.yaml::kind: ineffective`）。

    `task_state_auditable` 除 `delivery.yaml` 的声明与 `stage_gate.criterion()` 的声明之外，
    **全仓库无任何检查**。故本用例断言的是**反面事实**：
    把 `status` 置为非法值 → 阶段④ 的违例集合与合规输入**完全相同**。

    ★ 这不是"放行"：它是**可执行的缺口证据** —— 一旦有人真的实现了"任务状态可核"，
      本用例**当场变红**，从而强制把登记从 `ineffective` 改成 `counterexample`。
      这比"改一行数据把自己标成 ineffective"强得多（项目铁律 5）。
    """
    _daily_compliant(code_root)
    ok_code, ok_out = _gate(code_root, "daily_run")

    _write_jsonl(code_root, "tasks", [_task("check_1", "totally_bogus_status")])
    bad_code, bad_out = _gate(code_root, "daily_run")

    assert _fatal_lines(bad_out) == _fatal_lines(ok_out), (
        "注入非法 status 后违例集合发生了变化 —— 说明 `task_state_auditable` **已有判别力**："
        "请把它在 registry/criterion_counterexamples.yaml 里由 ineffective 改为 counterexample，"
        "并给出 blocked_hint 与反例断言。\n"
        f"合规: exit={ok_code}\n{ok_out}\n注入: exit={bad_code}\n{bad_out}"
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
    """`review_append_only` 反例：三层复盘缺一层 → 阶段⑤ 必须红。

    ★ **语义错位（如实声明）**：该 id 当前绑定的检查是「三层复盘齐备」，
      **不是** `delivery.yaml` 声明的 append-only（`(success, failure, pending) ⊆ 记录集`）。
      本用例证明的是「这个绑定有判别力」，**不能**证明「append-only 被守住」。
      详见 `reports/ws_criterion_effectiveness_report.md §3 G9-2`。
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


def test_expansion_review_append_only_semantics_have_no_discriminating_check(
    code_root: Path,
) -> None:
    """★ **缺口 G9-2 的可执行证据**：`review_append_only` 的**字面语义**没有被守。

    `registry/delivery.yaml` 的声明是：
    「复盘 **append-only**（`(success, failure, pending) ⊆ 记录集`，禁选择性删除）」。

    但门禁里与复盘相关的**唯一**判别轴是 `eval_layer` 的**取值集合**。故下列两份输入
    给出**完全相同**的违例集合：

    | 输入 | 语义 |
    |---|---|
    | A | 三层齐备，且**保留了**失败 / 待定记录 |
    | B | 三层齐备，但失败 / 待定记录被**选择性删除**（只剩成功） |

    ⇒ append-only 语义**零判别力**：门禁分不出"保留了失败"与"删掉了失败"。
      AST 实测该 id 在代码区只出现 1 次（`stage_gate.py:606` 的 `criterion()` 声明本身）。

    ★ 这不是"放行"而是**可执行的缺口证据**：一旦实现 append-only 检查，本用例当场变红，
      强制把登记从 `ineffective` 改掉。
    """
    rows_a = [
        {"task_id": "t1", "eval_result": {"eval_layer": "research_quality", "outcome": "success"}},
        {"task_id": "t2", "eval_result": {"eval_layer": "forecast_quality", "outcome": "failure"}},
        {"task_id": "t3", "eval_result": {"eval_layer": "investment_result", "outcome": "pending"}},
    ]
    rows_b = [
        {"task_id": "t1", "eval_result": {"eval_layer": "research_quality", "outcome": "success"}},
        {"task_id": "t2", "eval_result": {"eval_layer": "forecast_quality", "outcome": "success"}},
        {"task_id": "t3", "eval_result": {"eval_layer": "investment_result", "outcome": "success"}},
    ]

    _write_jsonl(code_root, "tasks", rows_a)
    a_out = _gate(code_root, "expansion")[1]
    _write_jsonl(code_root, "tasks", rows_b)
    b_out = _gate(code_root, "expansion")[1]

    assert _fatal_lines(b_out) == _fatal_lines(a_out), (
        "「选择性删除失败记录」后违例集合发生了变化 —— 说明 append-only 语义**已被检查**："
        "请把 registry/criterion_counterexamples.yaml 里 review_append_only 的 ineffective 条目"
        "改为/补上 counterexample 条目，并更新报告 §3 G9-2。\n"
        f"A（保留失败）:\n{a_out}\nB（删除失败）:\n{b_out}"
    )


# ═══════════ 义务本身的机器绑定（H2）：新绑判据却不登记 → 门禁必须红 ═══════════


def _guard(root: Path) -> tuple[int, str]:
    """跑判据有效性门禁（**进程内、不走 `run_gate` 的 session 级缓存**）。

    `run_gate` 对同一 `(脚本, code_root, 参数)` 只跑一次；本文件的用例普遍
    "改夹具 → 再跑同一命令"，用它会拿到**改动前**的结果（`conftest.run_gate` 已警告）。
    """
    return run_gate_inproc(GUARD, root)


def test_criterion_effectiveness_guard_passes_on_pristine_tree(code_root: Path) -> None:
    """**反向对照（H3-反例）**：登记完整 → 门禁 `exit 0` 且报出 `scanned`。"""
    code, out = _guard(code_root)
    assert code == 0, f"登记完整时门禁不应阻断\n{out}"
    assert "scanned " in out, f"未上报 scanned 计数（无法区分「没扫」与「扫了没问题」）\n{out}"
    assert "criteria_bound: 12" in out, out
    assert "criteria_registry_entries: 13" in out, out
    assert "counterexample_entries: 11" in out, out
    assert "ineffective_entries: 2" in out, out
    assert "criteria_without_counterexample: 1" in out, out
    assert "task_state_auditable" in out, "无判别力的判据必须逐条可见（G-03）"
    assert "review_append_only" in out, "语义错位的判据必须逐条可见（G-03）"


def test_removing_any_registry_entry_makes_guard_fail(code_root: Path) -> None:
    """**正向对照（H3-正例）**：删掉任意一条已绑定判据的登记 → 门禁必须 `exit 1`。

    逐条参数化：**每一条**登记都真的在被强制（不是只有第一条好使）。
    """
    path = code_root / REGISTRY
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = list(doc["counterexamples"])
    assert len(entries) == 13, "登记条数变了 —— 请同步本用例的期望值"
    for idx, row in enumerate(entries):
        doc["counterexamples"] = entries[:idx] + entries[idx + 1 :]
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        code, out = _guard(code_root)
        # `review_append_only` 有两条条目：删掉其中一条时该判据仍有条目 ⇒ 门禁可以放行
        # （允许多条目正是为了让"所绑定的检查有判别力"与"字面语义未被守"两件事各自留证）。
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
