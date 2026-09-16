"""接线与登记层的注入测试（`§一 底线 2` 真接线 / `Ch9 §3.4.9`）。

本文件存在的理由：**独立审计抓到两类"能通过 100% 覆盖率测试的假交付"** ——
1. `schema/registry_models.py` 是**孤儿模块**（无人导入），
   而 `registry/prep_deliverables.yaml` 却声明它是 `QualityLabel` 的载体；
2. `stage_gate.py` 的 docstring 声称检查了 `T01–T14`，**代码里根本没有**。

两类都是 `§一 底线 2`「真接线」点名的形态。断言方式一律是**注入→必须 exit 非零**，
不是"函数被调用了"。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from conftest import SYSTEM_ROOT, assert_rejected, run_gate, write_check_records

REGISTRY_GUARD = "scripts/checks/registry_schema_guard.py"
GATE = "scripts/delivery/stage_gate.py"


# ═══════════ 登记层真源：`registry_models` 的读取方必须真的在跑 ═══════════

def test_registry_models_is_actually_imported() -> None:
    """`schema/registry_models.py` 必须有**真实调用方**（防孤儿模块）。

    这条测试不查"文件存在"，而是查**谁导入它** —— 孤儿模块的判据就是"无人导入"。
    """
    guard = SYSTEM_ROOT / "scripts" / "checks" / "registry_schema_guard.py"
    text = guard.read_text(encoding="utf-8")
    assert "from schema.registry_models import" in text, (
        "registry_schema_guard.py 未导入 registry_models —— registry_models 仍是孤儿模块"
    )
    # 而且必须真的用到 REGISTRY_MODELS / registry_model_for，不是只 import 不调用
    assert "REGISTRY_MODELS" in text and "registry_model_for(" in text


def test_registry_guard_registered_in_gate_runner() -> None:
    """守卫必须出现在门禁跑测器里（否则写了没人跑 = 假接线）。"""
    runner = (SYSTEM_ROOT / "scripts" / "ops" / "run_all_gates.py").read_text(encoding="utf-8")
    assert "registry_schema_guard.py" in runner


def test_valid_registry_record_passes(code_root: Path) -> None:
    """**反向对照**：合法登记记录 → 放行。"""
    path = code_root / "registry" / "quality-labels.jsonl"
    path.write_text(
        json.dumps(
            {
                "label_id": "ql_1",
                "subject_kind": "source",
                "subject_id": "westock",
                "human_verified": True,
                "label_value": "high",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    proc = run_gate(REGISTRY_GUARD, code_root)
    assert proc.returncode == 0, f"合法登记记录被误报\n{proc.stdout}\n{proc.stderr}"
    assert "lines_validated: 1" in proc.stdout


def test_invalid_registry_record_is_rejected(code_root: Path) -> None:
    """非法登记记录（缺必填字段）→ 必须 exit 1。"""
    path = code_root / "registry" / "corporate-actions.jsonl"
    path.write_text(json.dumps({"action_id": "ca_1"}) + "\n", encoding="utf-8")
    assert_rejected(run_gate(REGISTRY_GUARD, code_root), rule_hint="CorporateAction")


def test_extra_field_on_registry_record_is_rejected(code_root: Path) -> None:
    """`extra="forbid"` 必须真的生效（多一个字段也拦）。"""
    path = code_root / "registry" / "idempotency.jsonl"
    path.write_text(
        json.dumps(
            {
                "idempotency_key": "k1",
                "first_seen_at": "2026-09-16T00:00:00+00:00",
                "task_ref": "task_1",
                "unexpected_field": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert_rejected(run_gate(REGISTRY_GUARD, code_root), rule_hint="IdempotencyRecord")


def test_unregistered_registry_jsonl_is_rejected(code_root: Path) -> None:
    """`registry/` 出现未登记模型的 JSONL → 必须 exit 1（没人读的数据）。"""
    (code_root / "registry" / "sneaky.jsonl").write_text("{}\n", encoding="utf-8")
    assert_rejected(run_gate(REGISTRY_GUARD, code_root), rule_hint="未在 REGISTRY_MODELS 登记")


def test_missing_declared_registry_file_is_rejected(code_root: Path) -> None:
    """已登记模型的文件被删 → 必须 exit 1（真源缺失）。"""
    (code_root / "registry" / "quality-labels.jsonl").unlink()
    assert_rejected(run_gate(REGISTRY_GUARD, code_root), rule_hint="登记层真源缺失")


def test_empty_registry_source_is_not_reported_as_verified(code_root: Path) -> None:
    """**关键**：真源为空时**不得**当作"已验证结构合规" —— 必须显式记 note。"""
    proc = run_gate(REGISTRY_GUARD, code_root)
    assert proc.returncode == 0
    assert "EMPTY_REGISTRY_SOURCE" in proc.stdout, "空真源必须显式说明，不得静默通过"
    assert "lines_validated: 0" in proc.stdout


# ═══════════ 判据台账：不得"声明了 automated 却没实现" ═══════════

def test_prep_has_zero_unimplemented_criteria(code_root: Path) -> None:
    """阶段① 声明的 4 条 automated 判据必须**全部实现**（PASS 的前提）。"""
    proc = run_gate(GATE, code_root, "--stage", "prep")
    assert proc.returncode == 0
    assert "prep.criteria_not_implemented: 0" in proc.stdout
    assert "prep.criteria_bound: 4" in proc.stdout


def test_newly_declared_criterion_without_implementation_blocks_stage(code_root: Path) -> None:
    """★ 注入一条**新声明**的 automated 判据（代码里没实现）→ 阶段① 必须 FAIL。

    这正是独立审计抓到的那类缺陷（`t01_t14_all_pass` 只写在 docstring 里）。
    有了这条机制，"声明"与"实现"不可能再悄悄脱节。
    """
    path = code_root / "registry" / "delivery.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for st in doc["delivery_stages"]:
        if st.get("key") == "prep":
            st["pass_criteria_testable"].append(
                {
                    "id": "invented_automated_criterion",
                    "statement": "一条被声明为 automated 但代码里没有的判据",
                    "check_kind": "automated",
                }
            )
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    assert_rejected(
        run_gate(GATE, code_root, "--stage", "prep"), rule_hint="invented_automated_criterion"
    )


# ═══════════ 夹具不得继承**运行态**（`G-RC-07` 的文件版） ═══════════
#
# `state.json` 是运行态游标（含真仓库的 run 历史），`.gitignore` 明确它是"每次运行重写、可重建"。
# `copytree` 复制的是**磁盘上的一切**（不只是 git 跟踪的东西）—— 原先 `_COPY_SKIP` 只列**目录**，
# 于是 `state.json` 被带进每个夹具副本，`resume()` 会去续跑**真仓库**那一次运行。
# 与 `G-RC-02` / `G-RC-07` 同一形态：**测试观测量取决于真仓库当前恰好有什么**。


def test_fixture_does_not_inherit_runtime_state(code_root: Path) -> None:
    """夹具副本**不得**含 `state.json`（否则 `resume()` 会续跑真仓库的运行）。"""
    assert not (code_root / "state.json").exists(), (
        "夹具继承了真仓库的 state.json —— `resume()` 会去续跑真仓库的那一次运行，"
        "测试观测量因此与真仓库的运行历史耦合（G-RC-07 的文件版）"
    )
    # 机制层断言：防本用例因"真仓库恰好没有该文件"而变成**空转**
    # （`G-03`：无被检对象 ≠ 已验证，故不能只靠运行时那一条）。
    from conftest import _COPY_SKIP  # noqa: PLC0415

    assert "state.json" in _COPY_SKIP, "夹具的复制跳过清单必须包含 state.json"


def test_unimplemented_criteria_are_listed_as_notes(code_root: Path) -> None:
    """阶段②–⑤ 的未实现判据必须**逐条列出**（不得因"反正阻塞了"而藏起来）。

    ★ 注意断言的**对象**：本用例要求的是"五阶段的判据台账**都出现**"，
      而不是"每个阶段都有缺口"。当某阶段判据全部绑定后，台账行仍须存在
      （`stage_gate.check()` 已改为**无条件发射**）—— 否则"该阶段判据已全部绑定"
      与"台账代码路径根本没跑"在输出上不可区分（前者是好事、后者是守卫静默失效，
      观测量却完全相同）。这是本条要求的**加强版**，不是放松。
    """
    proc = run_gate(GATE, code_root, "--stage", "all")
    assert proc.returncode == 1
    assert "t01_t14_all_pass" in proc.stdout, "T01–T14 缺口必须显式可见"
    assert "判据台账[core_chain]" in proc.stdout
    for stage in ("nvidia_sample", "daily_run", "expansion"):
        assert f"判据台账[{stage}]" in proc.stdout


# ═══════════ 阶段④「降级保留上次有效结果」· 首日豁免的**实际有效性** ═══════════
#
# 为什么单开一节：这条豁免判据的第一版**是死代码**（批次 11 自查抓到，实测真仓库
# `degrade_first_day_exempt: 0` 而 2 条违例一条没少）。根因：
#   它取 `parent_context.run_date`，而 `_write_check_record()` 写的 `parent_context`
#   只有 `{"orchestrator": "pipeline.run_daily"}` —— **不含 run_date**
#   （run_date 真正落在 `check_record.run_date`）。于是每个任务都取到 `""` →
#   `min(...)` = `""` → `_earliest` 为**空串**（假值）→ 豁免分支**永不进入**。
# 形态与本文档开头点名的那两类同族：**"改了"但机器上不生效**。
#
# ★ 故本节的断言**必须落在"豁免计数"上**，只断言"没有违例"是不够的 ——
#   豁免生效 与 判据根本没跑 都表现为"没有违例"，两者观测量相同（与 `G-03` 同源：
#   没有可观测的证据，就不等于已验证）。
#
# ★★ **本节的夹具在批次 11 独立审计中被判为"跟真数据不同源"**（`G-43` / `G-45`）：
#   旧夹具手工拼行 —— `_done_task_with_output()` 给 `output_refs=["rec-nvda-001"]`，
#   而**生产代码从未写出过那个形状**：`_write_check_record()` 当时**两个字段都不填**，
#   真行恒为 `output_refs=[]` / `last_valid_result_ref=None`。
#   ⇒ 谓词在**夹具上**为 True、在**真数据上**恒 False：
#     夹具全绿，判据在真数据上**空转、从不报任何真违规**。
#   现一律改走**唯一写入方** `conftest.write_check_records()`
#   （= `Pipeline._write_check_record`，真实字段形状，`G-06` 不造第二套）。
#   需要"契约被破坏"的形态时，对**真实写入的行**做**定向篡改**（删掉引用）——
#   篡改是**违约注入**，不是夹具造假（`§5.1 AC-04`：注入即必须 exit 非零）。

_DAY = "2026-09-16"


def _tasks_path(code_root: Path) -> Path:
    return code_root / "facts" / "tasks.jsonl"


def _drop_last_valid_ref(code_root: Path, task_id: str) -> None:
    """**注入违约**：把真实写入的某行 `last_valid_result_ref` 抹成 `null`（`Ch8 §E.4` 禁止的置空）。"""
    rows = [json.loads(l) for l in _tasks_path(code_root).read_text(encoding="utf-8").splitlines() if l.strip()]
    hit = False
    for row in rows:
        if row.get("task_id") == task_id:
            row["last_valid_result_ref"] = None
            hit = True
    assert hit, f"注入点不存在: {task_id}（行未被真实写路径写出？）"
    _tasks_path(code_root).write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def test_write_path_fills_last_valid_ref_and_output_refs(code_root: Path) -> None:
    """★ **写路径补齐契约**（`G-43` 的根因那一半）：成功 / 失败两种运行写出的**真行**长什么样。

    这条断言不跑门禁，直接看**真源里被写出的字段** —— 因为缺陷的本质是
    "谓词改了、真数据里字段仍是空的"（"改完就信"）。
    """
    rows = write_check_records(
        code_root,
        [
            {"produced": ["obj-1", "obj-2"]},                       # 成功运行
            {"blocked": True, "degraded": True},                    # 失败 / 降级运行
            {"produced": []},                                       # 有效但**无新增产出**的运行
        ],
    )
    ok, bad, noop = rows[0], rows[1], rows[2]
    cid = ok["check_record"]["check_id"]

    # ① 成功运行：`last_valid_result_ref` 为空（本次结果**就是**有效结果，无需保留旧引用）；
    #    `output_refs` = 本轮真正新写入的对象引用（**不再恒为空**）
    assert (ok["status"], ok["last_valid_result_ref"], ok["output_refs"]) == ("done", None, ["obj-1", "obj-2"]), ok
    # ② 失败运行：**必须保留上一次成功运行的引用**（`Ch8 §E.2`："失败时指向旧结果"）；
    #    本次**不产有效结果** ⇒ `output_refs` 如实为空（不得把部分写入冒充有效产出）
    assert (bad["status"], bad["last_valid_result_ref"], bad["output_refs"]) == ("failed", cid, []), bad
    # ③ 无新增产出的**成功**运行：`output_refs` 合法为空，但它**仍是一次有效结果**
    #    （`Ch1 §D.3`：无变化日不产信号）—— 故 `last_valid_result_ref=None` 不等于"没有有效结果"
    assert (noop["status"], noop["last_valid_result_ref"], noop["output_refs"]) == ("done", None, []), noop

    # ④ 谓词的**两载体之一**（"一次成功的运行"）在上述真实形状上必须为真 ——
    #    旧谓词（`last_valid_result_ref` ∪ `done∧output_refs`）对 ①②③ **全是 False**。
    from scripts.daily.degrade import holds_valid_result, last_valid_result_ref

    assert holds_valid_result(ok) is True, "成功运行行必须被认成'持有有效结果'（真实形状）"
    assert holds_valid_result(noop) is True, (
        "**无新增产出**的成功运行行也必须被认成'持有有效结果' —— "
        "否则'成功但无新增'的日子一过，下一次失败就会被误判首日（G-43 换字段复发）"
    )
    assert holds_valid_result(bad) is True, "失败行已保留引用 ⇒ 它自身也持有有效结果"
    # ⑤ 而"该指向谁"由**追加序 + 只认成功运行**决定：第 2 次失败时指向**当时**最后一次成功运行
    #    （= row1），此后又成功一次 ⇒ 现在指向 row3。链式保留不"记住旧值"，也不跳过错行。
    assert bad["last_valid_result_ref"] == cid, bad
    assert last_valid_result_ref(code_root, scope="full") == noop["check_record"]["check_id"]


def test_audit_counterexample_real_shape_is_now_caught(code_root: Path) -> None:
    """★★ **审计反例（`G-43`）必须从"拦不住"变成"拦得住"** —— 用**真实字段形状**构造。

    审计实测的反例形状 = `[done + output_refs=[] + last_valid_result_ref=null, failed]`
    （**这正是 `_write_check_record()` 写出的真形状**）。
    修复前：`degrade_first_day_exempt=1`、预期的那条真违规 FATAL **一条不报**（判据空转）。
    修复后：必须 `exit=1` 且命中"失败但未保留 last_valid_result_ref"，豁免计数为 0。

    ★ 成功行**不做任何手工拼装**：`produced=[]` 的"成功运行"由真实写路径写出
      （`output_refs=[]` 是它的**合法**真形状）。违约只加在失败行上（删引用）。
    """
    rows = write_check_records(code_root, [{"produced": []}, {"blocked": True, "degraded": True}])
    ok_row = rows[0]
    assert ok_row["status"] == "done" and ok_row["output_refs"] == [], ok_row
    assert ok_row["last_valid_result_ref"] is None, ok_row
    _drop_last_valid_ref(code_root, rows[1]["task_id"])

    proc = run_gate(GATE, code_root, "--stage", "daily_run")
    assert proc.returncode == 1, (
        "真实字段形状下 '此前有成功运行、失败却未保留引用' 必须 FATAL\n" + proc.stdout
    )
    assert "失败但未保留 last_valid_result_ref" in proc.stdout, proc.stdout
    assert "degrade_first_day_exempt: 0" in proc.stdout, proc.stdout


def test_first_day_degrade_exemption_is_effective_and_counted(code_root: Path) -> None:
    """★ 首日降级（此前**无**任何行持有有效结果）→ 豁免，且**计数必须可见且 > 0**。

    ★ 反向对照的另一半：`rows_holding_valid_result: 0` 与 `degrade_first_day_exempt: 1`
      **同时**出现才说明"豁免是因为结构上不可能保留"，
      而不是"谓词恒 False ⇒ 人人豁免"（后者两个计数会是 `1` / `0`，此处可区分）。
    """
    write_check_records(code_root, [{"blocked": True, "degraded": True}])
    proc = run_gate(GATE, code_root, "--stage", "daily_run")
    assert "degrade_first_day_exempt: 1" in proc.stdout, (
        "首日豁免必须**实际生效**且计数可见 —— 计数恒 0 意味着豁免分支根本没进（死代码）。\n"
        f"{proc.stdout}"
    )
    assert "rows_holding_valid_result: 0" in proc.stdout, (
        "首日必须**没有任何行**持有有效结果（否则'豁免'就不是结构性的，而是漏判）\n" + proc.stdout
    )
    assert "失败但未保留 last_valid_result_ref" not in proc.stdout, proc.stdout


def test_degrade_violation_fires_when_a_prior_result_exists(code_root: Path) -> None:
    """**反向对照**：此前已有行持有有效结果 → 仍必须 FATAL（不放松）。

    ★ 本条同时是"取 run_date 最早"那版判据的**反例**：两行的 `run_date` 同为 `_DAY`，
      按日期判定会把失败行当成"首日"而豁免 —— 那是**漏报真违规**。
      按**追加序**判定则不受同日重跑影响。
    """
    rows = write_check_records(
        code_root,
        [{"produced": ["rec-nvda-001"]}, {"blocked": True, "degraded": True}],
    )
    _drop_last_valid_ref(code_root, rows[1]["task_id"])
    proc = run_gate(GATE, code_root, "--stage", "daily_run")
    assert "失败但未保留 last_valid_result_ref" in proc.stdout, (
        "此前已完成并持有产出 ⇒ 引用本该在却被丢掉，必须 FATAL\n" + proc.stdout
    )
    assert "degrade_first_day_exempt: 0" in proc.stdout, proc.stdout


def test_failed_row_that_kept_ref_does_not_exempt_the_next_one(code_root: Path) -> None:
    """前序**失败但保留了引用**的行同样算"持有有效结果" → 紧随其后的失败行**不得**豁免。

    这是 `holds_valid_result()` 的载体①（`last_valid_result_ref`）的判别力来源：
    前序行**已经证明"引用是能保留的"**，故后续失败行丢引用不可归因于"当时无引用可保留"。
    """
    rows = write_check_records(
        code_root,
        [{"produced": ["rec-nvda-001"]}, {"blocked": True, "degraded": True},
         {"blocked": True, "degraded": True}],
    )
    # 第 2 行（真实写路径）**保留了引用** —— 先断言它确实保留了，再注入第 3 行违约
    assert rows[1]["last_valid_result_ref"] == rows[0]["check_record"]["check_id"], rows[1]
    _drop_last_valid_ref(code_root, rows[2]["task_id"])
    proc = run_gate(GATE, code_root, "--stage", "daily_run")
    assert f"{rows[2]['task_id']} 失败但未保留 last_valid_result_ref" in proc.stdout, proc.stdout
    assert "degrade_first_day_exempt: 0" in proc.stdout, proc.stdout
