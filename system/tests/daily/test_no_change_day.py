"""`G1-04`「终态必须有输出」的**两个**合法例外（`G-64` 收口）：
① 无变化日（`C123-2` / `N7.3-04`）② **本轮降级**（`Ch8 §E`）。

锚点（设计正文逐字）：

| 出处 | 原文 |
|---|---|
| `02_已确认的投资规则/01_需求拆解.md:149`（`C123-2`） | 「**更新 ≠ 信号**：每日维护（采集/核验/复查），仅变化时产信号，**无变化写 `check_record`**」 |
| `07_产业链传导与股票建议/01_需求拆解.md:51`（`N7.3-04`） | 「**无变化日不产生新信号，仅生成核查记录**」 |
| `08_产品入口与每日运行/02_实现方案.md:78` | 「每日运行**必写** `check_record`（**无论有无变化**）」 |
| `08_产品入口与每日运行/02_实现方案.md:330`（`§E.2`，`Ch8 §E`） | 「`degraded` ｜ `check_record`（**复用** Ch1 §C.2）｜ **当日降级运行 = true**」 |

⇒ `done` + `output_refs=[]` 在**无变化日**及**降级轮**都是**设计规定的正确行为**
（前者的产出就是一份核查记录；后者本轮不产新有效结果，有效结果在 `last_valid_result_ref`）。
旧实现一刀切判 `G1-04` ⇒ **两类合法行为都被误报**。

★★ 修法是**换成可判定的正向标记**，**不是放松判据**（`R-06 ①`）：

> `done` 且 `output_refs` 为空 ⇒ **合法当且仅当** `check_record` **存在** 且
> （`check_record.changed is False`（无变化日）**或** `check_record.degraded is True`（本轮降级））；
> 否则仍按 `G1-04` 判空执行。

★★ **三类计数必须闭合**（`G-64` 的第二个产物，`G-43` 的教训在这里的形态）：

```
done_empty_output_rows == no_change_day_exempt + degraded_empty_output + empty_output_violations
```

—— 单一 `no_change_day_exempt` 计数器下 **B2（合法降级、此前无成功运行）与 C（真违规）都记 0**：
一个**合法态**与一个**违规态**在同一观测通道上**等价**（`G-62`）。
由 `test_counters_are_exhaustive_over_the_three_classes` 机器绑定。

★★ **夹具纪律**（`G-43` / `G-45` / `G-62` 的教训 —— 夹具本身曾是缺陷的一部分）：

- **正例与反例 A 走真实写路径**（`conftest.write_check_records` → `Pipeline._write_check_record`），
  即"无变化日"与"有变化却无产出"两种形状由**唯一写入方**产出，**不手工造第二套形状**（`G-06`）。
  降级两个正例（B/B2）**同样走真实写路径**。
- **反例 B/C/D/E 必须手工构造**（缺 `check_record` / 缺 `changed` / `changed=None` / 非对象）——
  真实写路径**写不出**这几种形状（它总会写出 `check_record` 且 `changed` 恒为 `bool`）。
  这三条是**结构性反例**，测的是"豁免条件的严格性"，手工构造**是唯一手段**，此处**明说**。
- `_rec()` **必须带 `degraded` 形参**（`G-62`）：它原先**硬写 `"degraded": False`**
  ⇒ 本文件**全部**用例把"降级"这一维钉死在 False 上 —— 判据在夹具上永远看不到降级支。
  这类"夹具把被检维度钉死"正是 `G-64` 能在 10 个用例全绿的情况下存活的直接原因。
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


def _rec(*, changed=True, degraded=False) -> dict:
    """手工构造的行内 `check_record`；**必须能表达 `degraded`**（见模块 docstring 的夹具纪律）。"""
    return {
        "check_id": "check_2026-09-16_full",
        "run_date": "2026-09-16",
        "scope": "full",
        "changed": changed,
        "judgment_change": {},
        "signals_emitted": 0,
        "degraded": degraded,
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
    assert "不满足两个合法空产出例外" in proc.stdout, proc.stdout


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
    assert "不满足两个合法空产出例外" in proc.stdout, proc.stdout


def test_changed_none_does_not_exempt(code_root: Path) -> None:
    """★ 反例 D：`changed=None` ⇒ **exit 1**（`None` 不是 `False`）。"""
    _append_raw(code_root, [_raw_row(
        task_id="task_changed_none", status="done", output_refs=[],
        check_record=_rec(changed=None))])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout
    assert "不满足两个合法空产出例外" in proc.stdout, proc.stdout


def test_check_record_not_a_mapping_does_not_exempt(code_root: Path) -> None:
    """★ 反例 E：`check_record` 是字符串（非对象）⇒ **exit 1**（不得被 `in`/真值性蒙混）。"""
    _append_raw(code_root, [_raw_row(
        task_id="task_cr_str", status="done", output_refs=[], check_record="changed=false")])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout


# ── 第二类合法空产出：**本轮降级**（`Ch8 §E` / `G-64`） ───────────────────────
#
# 四态实测表（**行全部由真实写路径 `Pipeline._write_check_record` 产出**，每态一个全新 root）：
#
# | 态 | changed | degraded | last_valid_result_ref | 实义            | 修前 → 修后 |
# |----|---------|----------|-----------------------|-----------------|-------------|
# | A  | False   | False    | None                  | 无变化日（合法）| 0 → 0       |
# | B  | True    | True     | check_…               | 降级+有上次成功 | **1 假红** → 0 |
# | B2 | True    | True     | **None**              | 降级+此前无成功 | **1 假红** → 0 |
# | C  | True    | False    | None                  | 真违规（空执行）| 1 → 1       |
#
# ★ 关键一格：**B2 与 C 在行上字段逐一相同，只有 `degraded` 不同** ⇒ 任何不看 `degraded`
#   的谓词都分不开它们；候选 `last_valid_result_ref is not None` 会**漏掉 B2**
#   （该字段为 `None`）⇒ 假红只是从 B 挪到 B2（换个字段复发，`G-43` 的形状）。


def test_degraded_day_without_prior_success_is_legal(code_root: Path) -> None:
    """★ 正例 B2：降级轮 + **此前无任何成功运行**（`last_valid_result_ref=None`）⇒ **exit 0**。

    ★ 该行由**真实写路径**产出（`degraded=True` + 该 root 内无成功运行），**不手工拼**。
    修前该行为 `exit 1`（假红），且与真违规 C **在读数上完全合并**。
    """
    from scripts.tasks.gap_to_task import check

    write_check_records(code_root, [{"produced": [], "judgment_change": {"x": True},
                                     "degraded": True}])
    row = json.loads((code_root / "facts" / "tasks.jsonl").read_text().splitlines()[0])
    # 先钉住"这确实是真实写路径产出的 B2 形状"
    assert row["status"] == "done", row
    assert row["output_refs"] == [], row
    assert row["last_valid_result_ref"] is None, row
    assert row["check_record"]["changed"] is True, row
    assert row["check_record"]["degraded"] is True, row

    report = check(code_root)
    assert report.passed, [v.reason for v in report.violations]
    assert report.scanned["done_empty_output_rows"] == 1, report.scanned
    assert report.scanned["degraded_empty_output"] == 1, report.scanned
    assert report.scanned["no_change_day_exempt"] == 0, report.scanned

    proc = run_gate(GATE, code_root)
    assert proc.returncode == 0, proc.stdout


def test_degraded_day_with_prior_success_is_legal(code_root: Path) -> None:
    """★ 正例 B：降级轮 + **有上次成功运行**（`last_valid_result_ref` 非空）⇒ **exit 0**。

    与 B2 只差"此前是否有过一次成功运行" ⇒ 两条一起把"用 `last_valid_result_ref` 做豁免"
    这个候选按在**两个方向**上都证伪（它漏 B2、且它不是降级的原因）。
    """
    from scripts.tasks.gap_to_task import check

    write_check_records(code_root, [
        {"produced": ["obj-a"], "judgment_change": {"a": True}},               # 先有一次成功
        {"produced": [], "judgment_change": {"x": True}, "degraded": True},    # 再降级
    ])
    rows = [json.loads(l) for l in
            (code_root / "facts" / "tasks.jsonl").read_text().splitlines()]
    row = rows[-1]
    assert row["status"] == "done" and row["output_refs"] == [], row
    assert row["last_valid_result_ref"] == "check_2026-09-16_full", row
    assert row["check_record"]["degraded"] is True, row

    report = check(code_root)
    assert report.passed, [v.reason for v in report.violations]
    assert report.scanned["done_empty_output_rows"] == 1, report.scanned
    assert report.scanned["degraded_empty_output"] == 1, report.scanned


# ── 降级豁免的**严格性**反例：不得从"缺字段 / 非规范取值"这一侧复发 ────────────

def test_degraded_field_missing_does_not_exempt(code_root: Path) -> None:
    """★ 反例（B2 形状 **减去 `degraded` 字段**）⇒ **exit 1**。

    去掉的正是那个唯一能区分 B2 与 C 的字段 ⇒ 必须退回真违规。
    （用 `record.get("degraded")` 的真值性写法会把它当 False 而**照样红**，
    所以本用例真正钉的是**另一头**：见下面 `degraded=1` 那条。）
    """
    rec = _rec(changed=True)
    del rec["degraded"]
    _append_raw(code_root, [_raw_row(
        task_id="task_degraded_missing", status="done", output_refs=[], check_record=rec)])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout
    assert "不满足两个合法空产出例外" in proc.stdout, proc.stdout


def test_degraded_none_does_not_exempt(code_root: Path) -> None:
    """★ 反例：`degraded=None` ⇒ **exit 1**（`None` 不是 `True`）。"""
    _append_raw(code_root, [_raw_row(
        task_id="task_degraded_none", status="done", output_refs=[],
        check_record=_rec(changed=True, degraded=None))])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout


def test_degraded_one_does_not_exempt(code_root: Path) -> None:
    """★ 反例：`degraded=1`（**非规范布尔**）⇒ **exit 1**。

    这条钉的是**严格同一性** `is True`（而不是 `== True` / 真值性）：`1 == True` 为真但
    `1 is True` 为假。豁免只认编排器写入的规范布尔（`schema.models.CheckRecord.degraded: bool`），
    否则同族缺陷会从"取值不规范"这一侧复发（`G-43` 的教训）。
    ★ 与 `is_valid_run_record()` 的对照：那边用真值性（非规范取值判**不是**有效结果，偏严），
    两侧都落在保守侧，且互斥性由 `test_degraded_predicate_is_derived_from_truth_source` 钉住。
    """
    _append_raw(code_root, [_raw_row(
        task_id="task_degraded_one", status="done", output_refs=[],
        check_record=_rec(changed=True, degraded=1))])
    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout


# ── 谓词同源 + 计数闭合（机器绑定） ────────────────────────────────────────

def test_degraded_predicate_is_derived_from_truth_source() -> None:
    """★ 机器绑定（`G-06`）：本仓库的降级豁免谓词**不含自己的判据**，整条派生自真源。

    三个断言：

    1. **逐格相等**：`is_degraded_empty_output(row) is is_degraded_run_record(row)`
       在 `degraded` 取值矩阵（`True/False/None/1/0/"true"/"false"` × `changed` × `status`
       + 无 `check_record` + `check_record` 非 Mapping）上**逐格**成立
       —— 防后人把"薄派生"改成**第二套局部判据**（那正是 `G-64` 的成因）。
    2. **互斥**：真源的两个行级谓词不可能同时为真（"同一行既是有效结果、又是降级运行"不存在）。
    3. ★★ **非真空**：`B2` 与 `C` 两行**除 `degraded` 外逐字段相同**，而谓词给出**相反**结论
       —— 把"B2 ≡ C 只差一格"这个实测事实变成**机器绑定**（`G-03`：不得靠空集过关）。
    """
    from scripts.daily.degrade import is_degraded_run_record, is_valid_run_record
    from scripts.tasks.gap_to_task import is_degraded_empty_output

    rows: list[dict] = []
    for degraded in (True, False, None, 1, 0, "true", "false"):
        for changed in (True, False):
            for status in ("done", "failed"):
                rows.append(_raw_row(
                    task_id=f"t_{degraded}_{changed}_{status}", status=status, output_refs=[],
                    check_record=_rec(changed=changed, degraded=degraded)))
    rows.append(_raw_row(task_id="t_no_rec", status="done", output_refs=[], check_record=None))
    rows.append(_raw_row(task_id="t_str_rec", status="done", output_refs=[], check_record="x"))

    for row in rows:
        assert is_degraded_empty_output(row) is is_degraded_run_record(row), row
        assert not (is_valid_run_record(row) and is_degraded_run_record(row)), row

    # ★ 非真空（`G-03`）：B2 与 C —— **同一个 task_id**，只差 `check_record.degraded` 一格
    b2 = _raw_row(task_id="t_same", status="done", output_refs=[],
                  check_record=_rec(changed=True, degraded=True))
    c = _raw_row(task_id="t_same", status="done", output_refs=[],
                 check_record=_rec(changed=True, degraded=False))
    assert {k for k in b2 if k != "check_record" and b2[k] != c[k]} == set(), \
        "B2/C 除 check_record 外必须逐字段相同"
    assert {k for k in b2["check_record"] if b2["check_record"][k] != c["check_record"][k]} == {"degraded"}, \
        "B2/C 的 check_record 必须只差 degraded 一格"
    assert is_degraded_empty_output(b2) is True, "B2 必须被豁免（合法降级）"
    assert is_degraded_empty_output(c) is False, "C 必须不被豁免（真违规）"


def test_counters_are_exhaustive_over_the_three_classes(code_root: Path) -> None:
    """★ 分列计数**闭合**（`G-64`）：`done_empty_output_rows == 三类之和`（无第三态、无静默丢弃）。

    同一份真源内放三类各一行：**无变化日**（14 日，成功运行且 `produced=[]`）/
    **降级轮**（15 日）/ **真违规**（16 日，有变化却无产出）。
    ★ 反例：修前单一 `no_change_day_exempt` 计数器下 **降级轮与真违规都记 0** ——
      一个**合法态**与一个**违规态**在同一读数上**等价**（`G-62`）。
    """
    from scripts.tasks.gap_to_task import check

    write_check_records(code_root, [
        {"produced": [], "judgment_change": {}, "run_date": "2026-09-14"},               # 无变化日
        {"produced": [], "judgment_change": {"x": True}, "degraded": True,
         "run_date": "2026-09-15"},                                                      # 降级轮
        {"produced": [], "judgment_change": {"moat": True}, "run_date": "2026-09-16"},    # 真违规
    ])
    report = check(code_root)
    scanned = report.scanned
    assert scanned["done_empty_output_rows"] == 3, scanned
    assert scanned["no_change_day_exempt"] == 1, scanned
    assert scanned["degraded_empty_output"] == 1, scanned
    assert scanned["empty_output_violations"] == 1, scanned
    # ★ 闭合恒等式（三类穷尽；任何"某一行没被任何一支接住"或"被两支重复计数"都会打破它）
    assert scanned["done_empty_output_rows"] == (
        scanned["no_change_day_exempt"]
        + scanned["degraded_empty_output"]
        + scanned["empty_output_violations"]
    ), scanned
    # 判别力未放松：**只有真违规那一条**红
    assert len(report.violations) == 1, [v.reason for v in report.violations]
    assert "task_check_2026-09-16_full" in report.violations[0].reason, report.violations[0].reason

    proc = run_gate(GATE, code_root)
    assert proc.returncode == 1, proc.stdout


def test_row_both_degraded_and_no_change_is_counted_as_degraded(code_root: Path) -> None:
    """★ 钉住**归类优先级**：`changed=False` **且** `degraded=True` ⇒ 归 `degraded_empty_output`。

    两态同时成立是**合法**的（无变化日又降级），豁免结论与归类无关；但**归类必须确定**
    （否则计数闭合性无法判定）。本仓库取**降级优先**：`Ch8 §E` 的降级是"本轮结果不完整"的
    **更强**理由（它强制本轮产出为空，与 `changed` 无关）。
    ★ 该优先级是**实现选择**，故必须有测试钉住 —— 否则后人翻转它不会红。
    """
    from scripts.tasks.gap_to_task import check

    write_check_records(code_root, [{"produced": [], "judgment_change": {},
                                     "degraded": True}])
    row = json.loads((code_root / "facts" / "tasks.jsonl").read_text().splitlines()[0])
    assert row["check_record"]["changed"] is False and row["check_record"]["degraded"] is True, row

    report = check(code_root)
    assert report.passed, [v.reason for v in report.violations]
    assert report.scanned["degraded_empty_output"] == 1, report.scanned
    assert report.scanned["no_change_day_exempt"] == 0, report.scanned
    assert report.scanned["done_empty_output_rows"] == 1, report.scanned


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
