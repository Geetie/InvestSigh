"""`tests/unit/test_traceback_four_elements.py` —— `G1-03` 四要素反查的单元/夹具回归。

覆盖 WS-B 在 `scripts/trace/traceback.py` 上交付的两处修复，以及四条边界的**可执行**证据：

1. **版本解析**：同一 `recommendation_id` 有多条版本行（追加式不可变，`Ch9 §3.4.2`）时，
   取 `version` **最大**的那条作为"当前结论"（`latest_version_row`）。原实现取**第一条**
   ⇒ 永远读到 v1 种子行 ⇒ 即便 v2 已补齐 `evidence_version_ids`（含 `dv-…`），判据仍恒红。
   ★ 2026-09-17：该函数已由 `scripts.trace.traceback` **迁到 `scripts.decision.rules`**
   （`G-06` 唯一真源）—— 因为 `views/` 的构建也需要同类选择，两处各写一份正是漂移源。
   本文件仍覆盖它（行为不变），另见 `tests/decision/test_current_recommendation.py` 覆盖
   **另一个问题**（同一业务键下 `supersedes` 链的末节点，即 `B-7`）。
2. **`computation` 要素的两条解析路径**（`T-10` 裁决①的配套修复）：不仅能按 `derived_id`
   直接匹配，还能按建议声明的 `evidence_version_ids` 里的 `dv-…` 解析到 `derived/`。

`G-03`（空 ≠ 已验证）：缺 `derived/` / `dv-…` 解析不到 / 无被检对象时**不得**返回
`coverage = 1.0` 冒充通过 —— 由 `test_missing_derived_is_reported_not_silently_passed` 钉住。

★ 数据来源说明：`assumptions` 要素的唯一权威来源是 `baseline.driver_model[].assumptions`
（`01_产品目标与核心闭环/02_实现方案.md §E` 逐字："`baseline.driver_model / valuation_inputs(three-source)`"），
**本测试不改变该来源**，而是用夹具如实展示"有 / 无 `driver_model` 假设"两种结果 ——
从而把"该要素对基线深度的依赖"变成**可读的断言**，而不是靠口头声明。
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import run_gate_inproc
from scripts.decision.rules import latest_version_row
from scripts.trace.traceback import (
    ELEMENTS,
    traceback as tb_traceback,
    traceback_coverage,
)

TRACEBACK = "scripts/trace/traceback.py"

_DV_ID = "dv-nvda-dc-gross-margin-001"
_CLAIM_ID = "claim-nvidia-newsroom-q4-fy2025-4d13454fd859"


# ─────────────────────────── 夹具 ───────────────────────────


def _write_jsonl(root: Path, rel: str, rows: list[dict]) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def _derived_row(derived_id: str = _DV_ID) -> dict:
    """计算层产出的 `DerivedValue` 行（formula + operands + method_version 齐备）。"""
    return {
        "derived_id": derived_id,
        "value": "0.7497531723844067303395308716",
        "formula": "gross_profit / 96221",
        "operands": [
            "raw/2026-08-26-nvidia-q2-fy2027-results.txt#L212",
            "raw/2026-08-26-nvidia-q2-fy2027-results.txt#L225",
        ],
        "method_version": "compute-v1",
        "computed_at": "2026-09-16T18:51:20.578360Z",
        "version": "v2",
    }


def _baseline_row(*, driver_model: list[dict] | None = None) -> dict:
    return {
        "baseline_id": "baseline-nvda-001",
        "company_id": "company-nvidia",
        "version": 1,
        "business_mechanism": "NVIDIA 设计并销售数据中心加速计算平台。",
        "driver_model": driver_model or [],
    }


def _rec_row(
    *,
    version: int = 2,
    evidence_version_ids: list[str] | None = None,
    supersedes: str | None = "rec-nvda-001",
) -> dict:
    return {
        "recommendation_id": "rec-nvda-001",
        "security_id": "sec-nvda",
        "company_id": "company-nvidia",
        "action": "buy",
        "horizon": "1Y",
        "start_date": "2025-02-27",
        "status": "active",
        "rule_version": "v1",
        "evidence_version_ids": evidence_version_ids or [_CLAIM_ID, _DV_ID],
        "assumptions": [],
        "version": version,
        "supersedes": supersedes,
        "recorded_seq": version,
        "change_reason": "fixture",
    }


# ─────────────────────────── 1. 版本解析 ───────────────────────────


def test_latest_version_row_picks_max_version_then_recorded_seq() -> None:
    """`latest_version_row` 取 `(version, recorded_seq)` 最大者；同键取**靠后**那条。"""
    v1 = {"recommendation_id": "rec-x", "version": 1, "recorded_seq": 1}
    v2 = {"recommendation_id": "rec-x", "version": 2, "recorded_seq": 2}
    # 乱序输入：当前版本是 v2（不是"文件里第一条"）
    assert latest_version_row([v2, v1])["version"] == 2
    assert latest_version_row([v1, v2])["version"] == 2
    # 同 version：recorded_seq 大者胜
    a = {"recommendation_id": "rec-x", "version": 2, "recorded_seq": 1}
    b = {"recommendation_id": "rec-x", "version": 2, "recorded_seq": 9}
    assert latest_version_row([a, b])["recorded_seq"] == 9
    # 缺 version/recorded_seq：按 (1, 0) 归一，不抛
    assert latest_version_row([{}, {"version": 5}])["version"] == 5
    # ★ 反向对照（`G-05`）：**空集必须响亮** —— 不得凭空猜一个"当前版本"
    import pytest

    with pytest.raises(ValueError, match="非空"):
        latest_version_row([])


# ─────────────────────────── 2. computation 要素 ───────────────────────────


def test_traceback_resolves_computation_via_dv_ref_in_evidence(code_root: Path) -> None:
    """`evidence_version_ids` 里的 `dv-…` 能解析到 `derived/` 的真实 `DerivedValue`。"""
    _write_jsonl(code_root, "facts/recommendations.jsonl", [_rec_row()])
    _write_jsonl(code_root, "facts/baselines.jsonl", [_baseline_row()])
    _write_jsonl(code_root, "derived/derived_values.jsonl", [_derived_row()])

    result = tb_traceback(code_root, "rec-nvda-001")
    assert result.computation is not None, "computation 未解析（`dv-…` → `derived/` 链路断）"
    assert result.computation["derived_id"] == _DV_ID
    assert result.computation["formula"] and result.computation["operands"]
    # evidence 恒来自建议自身；prev_version_id 由 `supersedes` 提供
    assert result.evidence == [_CLAIM_ID, _DV_ID]
    assert result.prev_version_id == "rec-nvda-001"


def test_missing_derived_is_reported_not_silently_passed(code_root: Path) -> None:
    """`G-03`：`dv-…` 解析不到 → `computation` 计入缺失 → 门禁 **exit 1**（不得 1.0 冒充）。"""
    _write_jsonl(code_root, "facts/recommendations.jsonl",
                 [_rec_row(evidence_version_ids=[_CLAIM_ID, "dv-does-not-exist-999"])])
    _write_jsonl(code_root, "facts/baselines.jsonl", [_baseline_row()])
    _write_jsonl(code_root, "derived/derived_values.jsonl", [_derived_row()])

    result = tb_traceback(code_root, "rec-nvda-001")
    assert result.computation is None
    assert "computation" in result.missing()

    code, out = run_gate_inproc(TRACEBACK, code_root)
    assert code == 1, f"缺失 computation 未被拦下（exit={code}）:\n{out}"
    assert "computation" in out


# ─────────────────────────── 3. assumptions 要素的权威来源 ───────────────────────────


def test_assumptions_come_from_baseline_driver_model(code_root: Path) -> None:
    """`assumptions` 出自 `baseline.driver_model[].assumptions`（设计 §E 逐字）。

    两个方向都断言：**有** driver_model 假设 → 齐备；**无** → 计入缺失。
    这同时把"该要素依赖基线深度（WS-A 的 `drivers.jsonl` → `driver_model`）"写成可执行证据。
    """
    _write_jsonl(code_root, "facts/recommendations.jsonl", [_rec_row()])
    _write_jsonl(code_root, "derived/derived_values.jsonl", [_derived_row()])

    # (a) 无 driver_model ⇒ assumptions 缺失（当前 ws-b 工作树的真源形态）
    _write_jsonl(code_root, "facts/baselines.jsonl", [_baseline_row(driver_model=[])])
    assert "assumptions" in tb_traceback(code_root, "rec-nvda-001").missing()

    # (b) 有 driver_model ⇒ assumptions 齐备
    _write_jsonl(
        code_root,
        "facts/baselines.jsonl",
        [_baseline_row(driver_model=[{"driver_id": "DRV-NVDA-DC-CAPEX",
                                      "assumptions": ["数据中心 AI 资本开支增速维持"]}])],
    )
    result = tb_traceback(code_root, "rec-nvda-001")
    assert result.assumptions == ["数据中心 AI 资本开支增速维持"]
    assert result.complete, f"四要素应齐备，缺: {result.missing()}"


def test_four_elements_complete_and_coverage_is_one(code_root: Path) -> None:
    """完整夹具（baseline 有 driver_model + derived + rec v2）⇒ 齐备、覆盖率 1.0、exit 0。"""
    _write_jsonl(code_root, "facts/recommendations.jsonl", [_rec_row()])
    _write_jsonl(
        code_root,
        "facts/baselines.jsonl",
        [_baseline_row(driver_model=[{"driver_id": "DRV-1", "assumptions": ["假设 A"]}])],
    )
    _write_jsonl(code_root, "derived/derived_values.jsonl", [_derived_row()])

    assert traceback_coverage(code_root, ["rec-nvda-001"]) == 1.0
    code, out = run_gate_inproc(TRACEBACK, code_root)
    assert code == 0, f"完整夹具应 exit 0，实得 {code}:\n{out}"


def test_empty_sample_and_missing_truth_source_do_not_claim_pass(code_root: Path) -> None:
    """`G-03`：空样本 → 覆盖率抛错；真源为空 → 显式 note，**不得**判"覆盖率 1.0 已达成"。"""
    import pytest

    # 空样本：覆盖率无定义 → 抛错（不得返回 1.0）
    with pytest.raises(ValueError):
        traceback_coverage(code_root, [])

    # 真源为空：note 显式说明"不构成已达成"
    code, out = run_gate_inproc(TRACEBACK, code_root)
    assert code == 0
    assert "NO_RECOMMENDATION_DATA" in out


# ─────────────────────────── 4. 真实真源上的当前状态 ───────────────────────────


def test_real_root_computation_element_is_resolved() -> None:
    """真实 `system/` 上：**每个当前结论**的 `computation` 与 `evidence` 要素**都能解析**。

    ★ 只断言 WS-B **拥有**的部分（`computation` / `evidence`），不断言 `assumptions` ——
      后者由**基线深度**（WS-A）供给，随合并进度变化，不该被本测试钉死。

    ★★ 2026-09-17 重写（原实现**钉死了一个 id**：`rec-nvda-001`）：

      原实现把结论 id 写死成某个**历史种子数据**的 id。冷启动端到端重置真源后，
      该 id **在库里不存在** ⇒ `TraceabilityGap` ⇒ 本条**变红**。
      这与本仓反复栽的 `G-RC-02` 同族：**观测依赖"仓库里恰好有什么"**。

      ⇒ 改为**在真实数据上派生样本**：按业务键（`rules.recommendation_business_key`，
      与守卫同源）取每个结论的**当前版本**，逐条断言其 `computation` / `evidence` 可解析。
      并**显式断言样本非空** —— 否则"真源为空"会被读成"全部通过"（`G-03`）。

      ★ 判别力：本断言在**修复前**必然为红（`_find_derived` 对任何建议都返回 `None`，
      因 `dv-…` 与 `rec-…` 永不相等），也必然抓得住 `rec-sec-nvda-2026-08-03` 那类
      "声明的底稿从未存在"的行。
    """
    from conftest import SYSTEM_ROOT

    from scripts.decision.rules import recommendation_business_key

    rows = [
        json.loads(line)
        for line in (SYSTEM_ROOT / "facts" / "recommendations.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    # 每个**业务键**只取其**当前版本**（`version`, `recorded_seq` 最大者）——
    # 与 `traceback.check()` 的取样口径同源（`G-06` 唯一真源），不在此处另定一套。
    latest: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = recommendation_business_key(row)
        prev = latest.get(key)
        if prev is None or (int(row.get("version") or 1), int(row.get("recorded_seq") or 0)) >= (
            int(prev.get("version") or 1),
            int(prev.get("recorded_seq") or 0),
        ):
            latest[key] = row
    ids = [str(r.get("recommendation_id")) for r in latest.values()]
    assert ids, (
        "真实真源里没有任何建议 ⇒ 本判据无被检对象（G-03：不得把'无被检对象'当'已验证'）"
    )
    for cid in ids:
        result = tb_traceback(SYSTEM_ROOT, cid)
        assert result.computation is not None, f"{cid}: 真实真源上 computation 未解析"
        assert result.evidence, f"{cid}: evidence 应非空"
        assert set(result.applicable()) <= set(ELEMENTS)
        assert "computation" not in result.missing(), f"{cid}: {result.missing()}"
        assert "evidence" not in result.missing(), f"{cid}: {result.missing()}"
