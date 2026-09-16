"""`tests/valuelayer/_fixtures.py` —— 本批次测试的**共享夹具构造器**（唯一真源）。

## 为什么有这份文件（`G-06`）

`Ch4 §G.2` 的形式完备性有五项、`§G.4` 又有分支必填；只在某一个用例里写一遍"合规 baseline"、
别处各抄一份的话，"合规"的定义会随改动漂移，而测试的观测对象正是它。
故把规则文件与合规/违例输入的构造**收在一处**。

## 规则文件：夹具自备一份，**结构照已安装的真文件**

`rules/**` 在真仓库是 `0444 + SHA256` 锁（纪律 9/10），任何工作流都**不得**写。
本文件在**夹具副本**（`code_root`，可写）里自备一份，供"阈值从 `rules/` 读"的用例使用。

★ 深度与键名**照 13-R 已安装的真文件逐字**（`R8-1` 裁定：`cfg` = `baseline["thresholds"]`）：

| 键（在 `thresholds:` 之下） | 夹具值 | 真文件值 | 设计出处 |
|---|---|---|---|
| `min_nonnull_rate` | `0.8` | `0.9` | `Ch4 §G.2` 伪码 `cfg.min_nonnull_rate`；值出处 `00_待拍板项清单.md B5` |
| `min_fields_per_section` | `tbd` | **`tbd`** | `§G.2` 表"六项 section 非空且达最小字段数"——**具体数设计未给**（`B5` 只定非空率 + 定位数） |
| `min_locator_count` | `1` | `1` | `§G.2` 伪码 `has_locator(baseline) >= 1` |
| `min_derivation_count` | `1` | `1` | `§G.2` 伪码 `has_derivation(baseline) >= 1` |
| `max_primary_drivers_per_business` | `5` | `5` | `§D.2` 逐字："默认 5，可配" |

★ 为什么夹具**照抄 `min_fields_per_section: tbd`** 而不是填一个数：填数就等于在测试里
  **替需求方拍板**，会让"该项不可核"这条分支**永远测不到** —— 而它正是真仓库当前的状态。
  夹具要能复现真实状态，故逐字保留 `tbd`。
★ `min_nonnull_rate` 夹具取 `0.8` 而非真文件的 `0.9`：这是**故意**保留的一个"夹具 ≠ 真文件"，
  用来证明"阈值确实是从**传入的** `cfg` 读的、不是代码里写死的" ——
  若代码内置了 `0.9`，本夹具的用例会立刻变红（见 `test_completeness.py` 的阈值来源用例）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

#: `Ch4 §C.1` 的三个指标集（硬件六段 / 云五段 / 软件五段）+ `§C.3` 的 `MS-GENERIC` 兜底。
METRIC_SETS: list[dict[str, Any]] = [
    {
        "metric_set_id": "MS-HW-6STAGE",
        "model_class": "hardware",
        "currency": "n/a",
        "stages": [
            "order", "production_schedule", "shipment", "acceptance", "revenue", "collection",
        ],
        "metrics": [
            {
                "name": "order_backlog",
                "unit": "usd",
                "source_class": "fact",
                "linked_account": "revenue",
                "owner_business_id": "BIZ-HW",
            }
        ],
        "linked_accounts": ["revenue", "cogs", "capex", "inventory", "receivables"],
    },
    {
        "metric_set_id": "MS-CLOUD-5STAGE",
        "model_class": "cloud",
        "currency": "usd",
        "stages": ["contract", "energized", "online", "utilization", "billing"],
        "metrics": [
            {
                "name": "energized_mw",
                "unit": "mw",
                "source_class": "fact",
                "linked_account": "revenue",
                "owner_business_id": "BIZ-CLOUD",
            }
        ],
        "linked_accounts": ["revenue", "cogs", "capex"],
    },
    {
        "metric_set_id": "MS-SW-5STAGE",
        "model_class": "software",
        "currency": "usd",
        "stages": ["usage", "paid", "renewal", "retention", "upsell"],
        "metrics": [],
        "linked_accounts": ["revenue", "opex"],
    },
    {
        # `Ch4 §C.3`：未注册类型归入它并显式标注 `unregistered_model_class=true`。
        "metric_set_id": "MS-GENERIC",
        "model_class": "generic",
        "currency": "n/a",
        "stages": [],
        "metrics": [],
        "linked_accounts": [],
    },
]

#: **纯逻辑用例**用的阈值映射（= `rules/baseline.yaml::thresholds` 的形状）。
#:
#: ★ 与 `BASELINE_CFG` 的唯一差别：`min_fields_per_section` 在这里是**已拍板的 1**，
#:   而 `BASELINE_CFG` 里逐字保留真文件的 `tbd`。两者都需要存在：
#:   - "最小字段数"那条分支的**逻辑**用例要有可比较的阈值（用本件）；
#:   - "阈值为 `tbd` ⇒ 该半项不可核"这条分支要用真状态（用 `BASELINE_CFG`）。
#:   ⇒ 不是两个真源，是**同一份键集合的两种取值**，且各自只服务一类用例。
THRESHOLDS: dict[str, Any] = {
    "max_primary_drivers_per_business": 5,
    "min_nonnull_rate": 0.8,
    "min_fields_per_section": 1,
    "min_locator_count": 1,
    "min_derivation_count": 1,
}

#: 夹具用的规则**文档**（结构照已安装的真文件：`thresholds:` 分组 + `form_completeness.sections`）。
BASELINE_CFG: dict[str, Any] = {
    "version": 1,
    "thresholds": {
        **THRESHOLDS,
        # ★ 逐字保留真文件的 `tbd`（理由见模块 docstring）：让"该项不可核"这条分支可测。
        "min_fields_per_section": "tbd",
    },
    "form_completeness": {
        "entry": "form_complete",
        "guard": "scripts/valuelayer/completeness.py",
        "sections": ["①业务与产业位置", "②增长驱动", "③增长确定性", "④护城河", "⑤财务与估值", "⑥价格与行动"],
        "require_cross_section_consistent": True,
        "failed_items_reported": True,
    },
}

#: `rules/metric-sets.yaml::routing`（`Ch4 §C.1`/`§C.3`）。★ 兜底 id 与代码常量**逐字一致**，
#: 否则 `route_guard.check()` 的漂移核对会报违例（那条核对本身另有专门用例）。
ROUTING: dict[str, Any] = {
    "key": "model_class",
    "binding_field": "business.metric_set_id",
    "metric_owner_field": "business_id",
    "fallback_metric_set_id": "MS-GENERIC",
    "fallback_marks_unregistered_model_class": True,
}


def write_rules(root: Path, *, cfg: dict[str, Any] | None = None, metric_sets: list[dict] | None = None) -> None:
    """在**夹具副本**里写 `rules/baseline.yaml` 与 `rules/metric-sets.yaml`（照真文件的形状）。"""
    rules = root / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    (rules / "baseline.yaml").write_text(
        yaml.safe_dump(cfg if cfg is not None else BASELINE_CFG, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (rules / "metric-sets.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "routing": ROUTING,
                "metric_sets": metric_sets if metric_sets is not None else METRIC_SETS,
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )



def write_thresholds(
    root: Path,
    thresholds: dict[str, Any],
    *,
    metric_sets: list[dict] | None = None,
) -> None:
    """按 **`thresholds` 映射**写规则文件（自动包进 `thresholds:` 分组）。

    ★ 为什么需要它：`form_complete(baseline, cfg)` 的 `cfg` 是 **thresholds 映射**
      （`R8-1`），而 `write_rules(cfg=...)` 收的是**整份文档**。用例里想改一个阈值时
      若直接把 `cfg` 当文档写出去，写出的文件就**缺整个 `thresholds:` 分组** ——
      于是被测到的是"分组缺失"而不是"那个键缺失"，用例会以**错误的理由**变红/变绿。
      本函数把"改一个阈值"这件事写直：改映射，包装由它负责。
    """
    doc = dict(BASELINE_CFG)
    doc["thresholds"] = dict(thresholds)
    write_rules(root, cfg=doc, metric_sets=metric_sets)


def write_jsonl(root: Path, stem: str, rows: list[dict]) -> None:
    path = root / "facts" / f"{stem}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def write_derived(root: Path, rows: list[dict]) -> None:
    path = root / "derived" / "derived_values.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


# ───────────────────────────── 单对象构造器 ─────────────────────────────


def driver(
    driver_id: str = "DRV-1",
    business_id: str = "BIZ-1",
    *,
    source_class: str = "demand_expansion",
    importance_class: str = "high",
    accounts: list[str] | None = None,
    formula_ref: str = "dv-1",
    **overrides: Any,
) -> dict[str, Any]:
    """`Ch4 §D.1` 的驱动对象（含 `§D.3` 五项代价齐备 + `§C.4` 三层映射）。"""
    row: dict[str, Any] = {
        "driver_id": driver_id,
        "business_id": business_id,
        "source_class": source_class,
        "duration": {"mode": "range", "value": "1-3Y"},
        "financial_link": {
            "accounts": ["revenue_segment"] if accounts is None else accounts,
            "per_share_metric": "eps",
            "formula_ref": formula_ref,
        },
        "cost_of_growth": {
            "price_discount": {"note": "均价年降 3%"},
            "capex_requirement": {"note": "capex/收入抬升"},
            "inventory_buildup": {"note": "备货天数上升"},
            "receivables_buildup": {"note": "账期延长"},
            "financing_need": {"note": "净负债上升"},
        },
        "realization_stage": "occurred",
        "timeline": "1-3Y",
        "confidence": "medium",
        "importance_class": importance_class,
        "dependencies": ["customer_budget"],
        "assumptions": ["数据中心 capex 增速维持"],
    }
    row.update(overrides)
    return row


def business(
    business_id: str = "BIZ-1",
    *,
    business_type: str = "hardware",
    metric_set_id: str = "MS-HW-6STAGE",
    chain: list[str] | None = None,
    unregistered: bool = False,
) -> dict[str, Any]:
    """`Ch4 §B.1` 的业务对象（含 `conversion_chain`，段名取自注册表 `stages`）。"""
    stages = chain if chain is not None else ["order", "production_schedule", "shipment"]
    return {
        "business_id": business_id,
        "company_id": "CO-1",
        "business_type": business_type,
        "metric_set_id": metric_set_id,
        "unregistered_model_class": unregistered,
        "mechanism": {
            "payer": {"party": "hyperscaler", "segment": "cloud", "geographies": ["US"]},
            "offering": ["GPU-X"],
            "revenue_model": "one_time",
            "conversion_chain": [
                {"stage": s, "input": "x", "output": "y", "evidence": ["CLM-1"]} for s in stages
            ],
            "cost_structure": {"main_cogs": ["hbm"]},
            "capital_requirements": {"capex": "usd"},
        },
    }


def claim(claim_id: str = "CLM-1", *, locator: str = "p.12 para.3", kinds: list[str] | None = None) -> dict[str, Any]:
    row = {"claim_id": claim_id, "locator": locator, "status": "verified"}
    if kinds is not None:
        row["moat_evidence_kinds"] = kinds
    return row


def baseline(**overrides: Any) -> dict[str, Any]:
    """**合规** baseline（六项齐全 + `§G.4` 盈利分支必填 + locator + 推导 + 跨节一致）。"""
    row: dict[str, Any] = {
        "baseline_id": "baseline-nvda-001",
        "company_id": "CO-1",
        "version": 1,
        "business_mechanism": "卖加速计算平台",
        "historical_numeric_claims": ["NC-1"],
        "driver_model": [{"driver_id": "DRV-1", "assumptions": ["数据中心 capex 增速维持"]}],
        "value_state_refs": {
            "growth_momentum_state": "strengthening",
            "certainty_state": "unchanged",
            "moat_level": "strong",
            "moat_state": "unchanged",
        },
        "business_refs": ["BIZ-1"],
        "driver_refs": ["DRV-1"],
        "moat": [
            {
                "moat_id": "MOAT-1",
                "mechanism": "CUDA 生态 + 装机量带来的迁移成本",
                "protected_objects": [{"object": "cost", "strength": "high", "evidence": ["CLM-2"]}],
                "origin_class": "durable_advantage",
                "cross_generation_survival": True,
                "evidence_claims": ["CLM-2"],
                "writer": "research_skill",
            }
        ],
        "valuation_inputs": {
            "growth_assumption": {"value": "0.25", "input_source": "model_estimate"},
            "margin_assumption": {"value": "0.60", "input_source": "fact"},
        },
        "valuation": {"method_class": "dcf", "formula_ref": "dv-1"},
        "evidence_claim_ids": ["CLM-1"],
        "is_profitable": True,
        "margin_persistence": "云厂商 capex 周期内维持",
        "fcf_persistence": "经营现金流覆盖 capex",
        "reinvestment_return": "ROIIC > WACC",
        "share_dilution_impact": "回购抵消 SBC",
    }
    row.update(overrides)
    return row


# ───────────────────────────── 成套种子 ─────────────────────────────


def seed_compliant(root: Path, *, baselines: list[dict] | None = None) -> None:
    """写出一整套**合规**的 `facts/` + `derived/` + 候选规则（供五项检查全部通过）。

    ★ 与阶段② 的 `six_step_chain_complete` 也兼容（`driver_model` / `value_state_refs` 齐备），
      使阶段级反例的判别力**可归因**："除了被注入的那一项，别的都没变"。
    """
    write_rules(root)
    write_jsonl(root, "claims", COMPLIANT_CLAIMS)
    write_jsonl(root, "drivers", [driver()])
    write_jsonl(root, "businesses", [business()])
    write_jsonl(root, "relations", COMPLIANT_RELATIONS)
    write_jsonl(root, "implied_requirements", COMPLIANT_IMPLIED)
    write_jsonl(root, "recommendations", COMPLIANT_RECOMMENDATIONS)
    write_derived(root, COMPLIANT_DERIVED)
    write_jsonl(root, "baselines", baselines if baselines is not None else [baseline()])


# ──────────────── 纯函数用例用的**内存**上下文（免去每例复制夹具） ────────────────
#
# ★ 为什么要有这一份（`P-05` 的成本账，实测）：`code_root` 夹具每例要复制并**删除**
#   一份 `system/`（≈273 项），而宿主对工作区内的删除逐项监察（实测 ≈16ms/项）
#   ⇒ **每例 ≈4.5s 纯删除开销**。若"五项检查逐项正反"这类**纯函数**用例也各建一次夹具，
#   38 例就是 216s（本单实测）—— 那是把门禁的可用性烧在了与判据无关的开销上。
#   ⇒ 需要真文件的用例（阈值从 `rules/` 读、缺键 `exit 2`、CLI 退出码、阶段判据绑定）
#     才用 `code_root`；纯逻辑用例一律用下面这份内存上下文（**同一份输入语义**）。

COMPLIANT_CLAIMS: list[dict] = [claim("CLM-1"), claim("CLM-2", kinds=["persistent_share"])]

COMPLIANT_RELATIONS: list[dict] = [
    {"relation_id": "R-1", "subject_id": "CO-1", "object_id": "CO-2", "relation_progress_stage": "tbd"}
]

COMPLIANT_IMPLIED: list[dict] = [
    {"requirement_id": "IR-1", "company_id": "CO-1", "solved_variable": "growth"}
]

COMPLIANT_RECOMMENDATIONS: list[dict] = [
    {"recommendation_id": "REC-1", "company_id": "CO-1", "version": 1}
]

COMPLIANT_DERIVED: list[dict] = [
    {"derived_id": "dv-1", "formula": "rev * margin", "operands": ["rev", "margin"]}
]


def compliant_context(**overrides: Any) -> dict[str, Any]:
    """`FormContext(...)` 的构造入参（与 `seed_compliant` 写入的内容**逐字对应**）。"""
    parts: dict[str, Any] = {
        "drivers": {"DRV-1": driver()},
        "businesses": {"BIZ-1": business()},
        "claims": {c["claim_id"]: c for c in COMPLIANT_CLAIMS},
        "derived": {d["derived_id"]: d for d in COMPLIANT_DERIVED},
        "relations": tuple(COMPLIANT_RELATIONS),
        "chapter_refs": {"CO-1": ("ch5:IR-1", "ch7:REC-1")},
    }
    parts.update(overrides)
    return parts
