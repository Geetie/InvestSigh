"""`G1-04`「终态必须有输出」的**唯一合法例外**：无变化日（`C123-2` / `N7.3-04`）。

锚点（设计正文逐字）：

| 出处 | 原文 |
|---|---|
| `02_已确认的投资规则/01_需求拆解.md:149`（`C123-2`） | 「**更新 ≠ 信号**：每日维护（采集/核验/复查），仅变化时产信号，**无变化写 `check_record`**」 |
| `07_产业链传导与股票建议/01_需求拆解.md:51`（`N7.3-04`） | 「**无变化日不产生新信号，仅生成核查记录**」 |
| `08_产品入口与每日运行/02_实现方案.md:78` | 「每日运行**必写** `check_record`（**无论有无变化**）」 |

⇒ `done` + `output_refs=[]` 在**无变化日**是**设计规定的正确行为**（那一轮的产出就是一份核查记录），
不是空执行。旧实现一刀切判 `G1-04` ⇒ **合法行为被误报**。

★★ 修法是**换成可判定的正向标记**，**不是放松判据**（`R-06 ①`）：

> `done` 且 `output_refs` 为空 ⇒ **合法当且仅当** `check_record` **存在**
> 且 `check_record.changed is False`；否则仍按 `G1-04` 判空执行。

★★ **夹具纪律**（`G-43` / `G-45` 的教训 —— 夹具本身曾是缺陷的一部分）：

- **正例与反例 A 走真实写路径**（`conftest.write_check_records` → `Pipeline._write_check_record`），
  即"无变化日"与"有变化却无产出"两种形状由**唯一写入方**产出，**不手工造第二套形状**（`G-06`）。
- **反例 B/C/D 必须手工构造**（缺 `check_record` / 缺 `changed` / `changed=None`）——
  真实写路径**写不出**这三种形状（它总会写出 `check_record` 且 `changed` 恒为 `bool`）。
  这三条是**结构性反例**，测的是"豁免条件的严格性"，手工构造**是唯一手段**，此处**明说**。
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import run_gate, write_check_records

GATE = "scripts/tasks/gap_to_task.py"


def _append_raw(root: Path, rows: list[dict]) -> None:
    """手工构造**结构性反例**行（真实写路径写不出这些形状，见模块 docstring）。"""
    path = root / "facts" / "tasks.jsonl"
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _raw_row(*, task_id: str, status: str, output_refs: list, check_record) -> dict:
    """与真实 check 行**同字段集**（逐字取自 `facts/tasks.jsonl`），只改被测的三处。"""
    return {
        "task_id": task_id,
        "task_type": "verify",
        "status": status,
        "idempotency_key": f"check::{task_id}",
        "input_refs": [],
        "output_refs": output_refs,
        "parent_context": {"orchestrator": "pipeline.run_daily"},
        "last_valid_result_ref": None,
        "check_record": check_record,
    }


def _rec(*, changed=True) -> dict:
    return {
        "check_id": "check_2026-09-16_full",
        "run_date": "2026-09-16",
        "scope": "full",
        "changed": changed,
        "judgment_change": {},
        "signals_emitted": 0,
        "degraded": False,
    }


# ── 正例：无变化日（走真实写路径） ──────────────────────────────────────────

def test_no_change_day_done_with_empty_output_is_legal(code_root: Path) -> None:
    """★ 正例：无变化日 → `done` + 空产出 + `changed=False` ⇒ **exit 0**（此前误报 exit 1）。"""
    write_check_records(code_root, [{"produced": [], "judgment_change": {}}])
    row = json.loads((code_root / "facts" / "tasks.jsonl").read_text().splitlines()[0])
    # 先钉住"这确实是真实写路径产出的无变化日形状"
    assert row["status"] == "done", row
    assert row["output_refs"] == [], row
    assert row["check_record"]["changed"] is False, row

    proc = run_gate(GATE, code_root)
    assert proc.returncode == 0, proc.stdout
    assert "RESULT: PASS" in proc.stdout, proc.stdout


def test_no_change_day_is_counted_so_the_exemption_is_not_vacuous(code_root: Path) -> None:
    """★ 豁免**可见**（`G-43` 的教训）：只看"0 违例"无法区分"没有这类行"与"判据恒假"。

    故必须把"落进该形状的行数"与"其中被豁免的行数"**成对**报出。
    """
    from scripts.tasks.gap_to_task import check

    write_check_records(code_root, [{"produced": [], "judgment_change": {}}])
    report = check(code_root)
    assert report.passed, [v.reason for v in report.violations]
    assert report.scanned["done_empty_output_rows"] == 1, report.scanned
    assert report.scanned["no_change_day_exempt"] == 1, report.scanned


def test_no_rows_of_that_shape_means_both_counters_are_zero(code_root: Path) -> None:
    """反向：没有该形状的行时，**两个计数同时为 0** ⇒ 不是"判据恒假"的假绿。"""
    from scripts.tasks.gap_to_task import check

    write_check_records(code_root, [{"produced": ["obj-a"], "judgment_change": {"a": True}}])
    report = check(code_root)
    assert report.passed, [v.reason for v in report.violations]
    assert report.scanned["done_empty_output_rows"] == 0, report.scanned
    assert report.scanned["no_change_day_exempt"] == 0, report.scanned


# ── 反例 A：有变化却无产出（走真实写路径） ───────────────────────────────────

def test_change_day_with_empty_output_is_still_a_violation(code_root: Path) -> None:
    """★ 反例 A：`judgment_change` 非空（= `changed=True`）却没产出 ⇒ **exit 1**（判别力未放松）。"""
    write_check_records(code_root, [{"produced": [], "judgment_change": {"moat": True}}])
    row = json.loads((code_root / "facts" / "tasks.jsonl").read_text().splitlines()[0])
    assert row["status"] == "done" and row["output_refs"] == [], row
    assert row["check_record"]["changed"] is True, row

    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout
    assert "G1-04" in proc.stdout and "空执行" in proc.stdout, proc.stdout


# ── 反例 B/C/D：结构性反例（手工构造，见模块 docstring 的"明说"） ─────────────

def test_done_with_empty_output_and_no_check_record_is_a_violation(code_root: Path) -> None:
    """★ 反例 B：`done` + 空产出 + **无 `check_record`** ⇒ **exit 1**（缺字段不得当豁免）。"""
    _append_raw(code_root, [_raw_row(
        task_id="task_no_check_record", status="done", output_refs=[], check_record=None)])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout
    assert "不满足无变化日豁免" in proc.stdout, proc.stdout


def test_changed_field_missing_does_not_exempt(code_root: Path) -> None:
    """★ 反例 C：`check_record` 在、但**缺 `changed` 字段** ⇒ **exit 1**。

    这测的是豁免条件的**严格性**：用 `record.get("changed") is False`（严格同一性），
    而不是 `not record.get("changed")` —— 后者会把"**缺字段**"当成"无变化"，
    于是**同族缺陷会从缺字段这一侧复发**（`G-43` 的教训：判据被一个恒真的谓词空转）。
    """
    rec = _rec()
    del rec["changed"]
    _append_raw(code_root, [_raw_row(
        task_id="task_changed_missing", status="done", output_refs=[], check_record=rec)])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout
    assert "不满足无变化日豁免" in proc.stdout, proc.stdout


def test_changed_none_does_not_exempt(code_root: Path) -> None:
    """★ 反例 D：`changed=None` ⇒ **exit 1**（`None` 不是 `False`）。"""
    _append_raw(code_root, [_raw_row(
        task_id="task_changed_none", status="done", output_refs=[],
        check_record=_rec(changed=None))])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout
    assert "不满足无变化日豁免" in proc.stdout, proc.stdout


def test_check_record_not_a_mapping_does_not_exempt(code_root: Path) -> None:
    """★ 反例 E：`check_record` 是字符串（非对象）⇒ **exit 1**（不得被 `in`/真值性蒙混）。"""
    _append_raw(code_root, [_raw_row(
        task_id="task_cr_str", status="done", output_refs=[], check_record="changed=false")])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout


# ── 对照：不得误伤 / 不得误判 ────────────────────────────────────────────────

def test_done_with_output_is_not_affected(code_root: Path) -> None:
    """对照：正常 `done` + 非空产出 ⇒ exit 0（改动没有波及正常行）。"""
    write_check_records(code_root, [{"produced": ["obj-a"], "judgment_change": {"moat": True}}])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 0, proc.stdout


def test_failed_row_with_empty_output_is_not_flagged(code_root: Path) -> None:
    """对照：`failed` + 空产出 ⇒ exit 0。

    `TERMINAL_STATES = ("done",)` **只含 `done`、不含 `failed`** ⇒
    **不存在"失败行被误判空执行"的假阳性**（这一条是给后人看的：别把它当问题）。
    """
    _append_raw(code_root, [_raw_row(
        task_id="task_failed", status="failed", output_refs=[],
        check_record=_rec(changed=False))])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 0, proc.stdout


# ── 混合：只有真违例那一条红（配对计数的判别力） ─────────────────────────────

def test_mixed_rows_flag_only_the_real_violation(code_root: Path) -> None:
    """正例 + 反例 A 同处一份真源 ⇒ **只红 1 条**（且豁免计数 = 1）。

    改前：两条都红（2 违例 —— 合法无变化日被误报），这正是本单要修的。
    """
    write_check_records(code_root, [
        {"produced": [], "judgment_change": {}, "run_date": "2026-09-15"},
        {"produced": [], "judgment_change": {"moat": True}, "run_date": "2026-09-16"},
    ])
    from scripts.tasks.gap_to_task import check

    report = check(code_root)
    assert not report.passed
    assert len(report.violations) == 1, [v.reason for v in report.violations]
    assert "task_check_2026-09-16_full" in report.violations[0].reason, report.violations[0].reason
    assert report.scanned["done_empty_output_rows"] == 2, report.scanned
    assert report.scanned["no_change_day_exempt"] == 1, report.scanned

    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout


def test_exemption_is_not_id_based(code_root: Path) -> None:
    """豁免**不靠任何 id 名单**（`R-06 ①`：穷尽两态、无第三态）。

    把正例的 `task_id` 换成一个**从未出现过的**名字，仍然照样豁免 ⇒ 判据看的是**字段**，不是名单。
    """
    _append_raw(code_root, [_raw_row(
        task_id="task_totally_unknown_xyz", status="done", output_refs=[],
        check_record=_rec(changed=False))])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 0, proc.stdout
