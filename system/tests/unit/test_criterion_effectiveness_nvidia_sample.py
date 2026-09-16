"""**判据有效性** —— 阶段② 判据 `evidence_locatable` 的**可执行反例**（缺口 `G-50`）。

## 为什么在这里（`tests/unit/`）而不是 `tests/injection/`

`criterion_effectiveness_guard._test_index()` 用 AST 扫 **`tests/**`** 收集 `def test_*`
—— 判据反例落在 `tests/unit/**` 或 `tests/injection/**` 对它**等价**（只要求文件真实存在、
且测试函数名含判据 id）。本卡（WS-B）**禁改** `scripts/ops/verify.py`，而
`tests/injection/**` 的"每片必须显式登记文件路径、且片内 ≤32 例"由 `verify.py::BATCHES`
承载 ⇒ **新增注入测试文件无法在不改 `verify.py` 的前提下入片**
（`test_shard_coverage.test_every_injection_test_file_is_covered_by_shards` 会如实变红）。
`tests/unit/` 的批次目标是一个**目录**（`_pytest("tests/unit")`），新文件自动被覆盖
（`verification_policy_guard` V-06 满足）。故本反例落此新文件。

## 判据绑定的形态（`G-50`：接线接在了错的层）

`evidence_locatable`（`registry/delivery.yaml` 阶段② 第 2 条 · `Ch6 §D` · `check_kind: automated`）
的**检查器早已实现**（`scripts/validators/locator_check.py`，8 条可判定判据），且**已有生产调用方**
（`scripts/orchestrate/chain_steps.py`）—— 唯独 `stage_gate.stage_nvidia_sample_passed()`
函数体内**没有** `criterion(...)` 声明 ⇒ `assert_criteria_implemented()` 报 `G11-04` FATAL。
本卡把它**绑进**函数体，并由本文件证明它**真的会拦**（`G9`：绑定 ≠ 会拦）。

## 反例的两个方向（`registry/criterion_counterexamples.yaml` 的义务）

| 输入 | 断言 |
|---|---|
| **合规**（claim 定位可机械复查回 `raw/` 区间） | 阶段② 输出里 **不出现** `LOCATOR_UNRECOGNIZED` |
| **违约**（同一条 claim，只把 `locator` 改成非机械可复查形式） | 阶段② `exit != 0` **且** 输出含 `LOCATOR_UNRECOGNIZED` |

`LOCATOR_UNRECOGNIZED` 是 `locator_check` 的**专属**违例码（判据级归因：
"门禁红了"必须可归因到**这一条**判据，而不是别的判据顺带变红）。
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import run_gate_inproc

GATE = "scripts/delivery/stage_gate.py"
_HINT = "LOCATOR_UNRECOGNIZED"

#: 反例专属标记（`locator_check` 的违例码；见其模块 docstring 的判据表第 1 行）。


def _gate(root: Path) -> tuple[int, str]:
    """跑**真仓库那份** `stage_gate.py`，`code_root` 指向夹具副本（进程内入口）。"""
    return run_gate_inproc(GATE, root, "--stage", "nvidia_sample")


def _write_jsonl(root: Path, stem: str, rows: list[dict]) -> None:
    (root / "facts" / f"{stem}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def _baseline_row() -> dict:
    """阶段② 的合规基线行（六项深度齐备，使函数体走到 `evidence_locatable` 的检查点）。"""
    return {
        "baseline_id": "baseline-nvda-001",
        "company_id": "co_1",
        "business_mechanism": "卖加速卡（数据中心 GPU + 网络 + 系统 + 软件）",
        "historical_numeric_claims": ["claim-1"],
        "driver_model": [{"driver_id": "drv-1", "assumptions": ["数据中心 capex 增速维持"]}],
        "value_state_refs": {"certainty_state": "tbd"},
    }


def _recommendation_row() -> dict:
    """合规建议：四要素（适用项）可反查（`evidence` + `computation`，`assumptions` 由 baseline 投影）。"""
    return {
        "recommendation_id": "rec-1",
        "company_id": "co_1",
        "evidence_version_ids": ["dv-1"],
        "version": 1,
    }


def _derived_row() -> dict:
    return {
        "derived_id": "dv-1",
        "formula": "rev * margin",
        "operands": {"rev": "1", "margin": "0.5"},
        "method_version": "v1",
    }


def _claim_row(claim_id: str, locator: str) -> dict:
    """一条**schema 合法**的 claim，`locator` 由调用方给（合规 / 违约两态共用其余字段）。

    ★ 只翻转 `locator` 一个字段 —— 这是"单变量对照"：红/绿之差**只能**来自定位信息，
    不可能来自别的字段（`口径 12`）。
    """
    return {
        "claim_id": claim_id,
        "source_id": "src-1",
        "quote_hash": "a" * 64,
        "claim_nature": "fact",
        "claim_form": "original_investigation",
        "tier": "primary",
        "locator": locator,
        "full_text_read": False,
    }


def _write_nvidia_env(root: Path, *, locator: str) -> None:
    """写一份"阶段② 前置齐备"的夹具：baseline + recommendation + derived + 一条 claim。"""
    _write_jsonl(root, "baselines", [_baseline_row()])
    _write_jsonl(root, "recommendations", [_recommendation_row()])
    (root / "derived" / "trace.jsonl").write_text(
        json.dumps(_derived_row(), ensure_ascii=False) + "\n", encoding="utf-8"
    )
    # `raw/` 原文（供合规定位 `raw/notes.txt#L1-L2` 机械复查）。
    (root / "raw" / "notes.txt").write_text("第一行\n第二行\n第三行\n", encoding="utf-8")
    _write_jsonl(root, "claims", [_claim_row("claim-loc-1", locator)])


def test_nvidia_sample_evidence_locatable_blocks_on_unlocatable_claim(code_root: Path) -> None:
    """★ `evidence_locatable` 的**可执行反例**：定位非机械可复查 ⇒ 阶段② 必须红。

    对应 `registry/criterion_counterexamples.yaml` 里
    `stage: nvidia_sample` / `criterion_id: evidence_locatable` 的 `counterexample` 条目
    （`blocked_hint: LOCATOR_UNRECOGNIZED`）。

    三件事同时钉住（`G9` / `R-02` / `G-05`）：

    1. **合规侧**：claim 的定位可机械复查回 `raw/notes.txt#L1-L2` ⇒ `LOCATOR_UNRECOGNIZED` **不出现**；
    2. **违约侧**：只把 `locator` 改成非机械可复查串 ⇒ 阶段② `exit != 0` **且** 该码出现；
    3. **归因**：由于只翻转一个字段，红绿之差只能来自**定位检查**这一处（判别力归因成立）。
    """
    # ① 合规侧：定位有效 → 该判据的专属码不得出现（否则"红"可能来自别的判据）。
    _write_nvidia_env(code_root, locator="raw/notes.txt#L1-L2")
    ok_code, ok_out = _gate(code_root)
    assert _HINT not in ok_out, f"合规定位下不该出现 {_HINT!r}：\n{ok_out}"

    # ② 违约侧：同一条 claim，只把 locator 换成一个非机械可复查形式。
    _write_nvidia_env(code_root, locator="第十二章第三段（无机械定位形态）")
    code, out = _gate(code_root)
    assert code != 0, f"定位无效时阶段② 竟 exit=0（判据未拦）：\n{out}"
    assert _HINT in out, f"违约输入未命中 {_HINT!r}（判别力归因不成立）：\n{out}"
