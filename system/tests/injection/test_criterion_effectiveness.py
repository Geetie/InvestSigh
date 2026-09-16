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

from conftest import SYSTEM_ROOT, run_gate_inproc

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
    """
    _write_jsonl(root, "companies", [{"company_id": "co_1", "research_depth": "position_listed"}])
    _write_jsonl(root, "tasks", [_task("check_1", "done", output_refs=["rec-1"])])


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
    """`degrade_keeps_last_valid` 反例：先有有效产出、后失败却丢引用 → 必须红。"""
    _daily_compliant(code_root)
    assert _gate(code_root, "daily_run")[0] == 0

    _write_jsonl(
        code_root,
        "tasks",
        [
            _task("check_1", "done", output_refs=["rec-1"]),
            _task("check_1_r1", "failed"),
        ],
    )
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


def test_criterion_effectiveness_guard_passes_on_pristine_tree(code_root: Path) -> None:
    """**反向对照（H3-反例）**：登记完整 → 门禁 `exit 0` 且报出 `scanned`。"""
    code, out = _guard(code_root)
    assert code == 0, f"登记完整时门禁不应阻断\n{out}"
    assert "scanned " in out, f"未上报 scanned 计数（无法区分「没扫」与「扫了没问题」）\n{out}"
    assert "criteria_bound: 12" in out, out
    assert "criteria_registry_entries: 15" in out, out
    assert "counterexample_entries: 14" in out, out
    assert "ineffective_entries: 1" in out, out
    assert "criteria_without_counterexample: 0" in out, out
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
    assert len(entries) == 15, "登记条数变了 —— 请同步本用例的期望值"
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
