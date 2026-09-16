#!/usr/bin/env python3
"""`acceptance_checks.py` —— **T01–T14 反例的可执行判定器**（`10/01 §2.1` 权威表的落位）。

```
python system/scripts/graph/acceptance_checks.py        # 自检：打印每条 T 的判定结果
```

## 本模块的角色

`registry/acceptance_input_set.yaml` 是 T01–T14 的**台账**（逐字场景 / 预期行为 /
权威锚点 / 责任章）。判据 `t01_t14_all_pass`（`registry/delivery.yaml`）**逐条执行**
本模块里对应的判定器 —— 每个判定器对一个 T 的**预期行为**构造 canonical 场景，
打到**真实模块**上，返回违例（空 = ✅）。

★ 为什么是"canonical 场景打真实模块"而不是"读真仓库数据"：
  T01–T14 是**规则/流程正确性**的反例（`10/01 §N10.2-03`），其判据是**不变量**，
  与"仓库里恰好有多少数据"无关。故判定器**自带输入**，在**任意 root**（含空真源）上
  结果确定 —— 这正是让判据可复现、不依赖运行态的做法。

★ **不臆造通过**（`G-03`）：判定器里任何非预期异常都折成**违例**（携 T 号），
  绝不静默吞成"通过"。

## 责任边界（如实登记）

T02（单源预测 ≠ 完整市场一致预期）的判定载体**并非**本层私有逻辑 ——
`registry/prep_deliverables.yaml::cr13_no_aggregate_consensus` 逐字指名其载体为
**共享 schema 模型** `schema/models.py::ExpectationSample`（样本语义 + 必填 `source_id`；
禁 `consensus` / `market_view` / `average_forecast`，`Ch2 §B.2 P-07`）。
故 T02 **可程序化判定**：本模块**复用**该模型断言 —— ① 单份公开预测能以**样本**形态
落库（携 `sample_size` 与来源）；② 无源外部预测被拒（P-07 聚合入口关闭）；
③ 样本对象**不接受**一致预期升级字段（`extra="forbid"`）。全部为对真实模型的真断言，
不是"自造一个恒过的用例"。
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

_THIS = Path(__file__).resolve()
_ROOT = _THIS.parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import Violation  # noqa: E402

_MODULE = "scripts/graph/acceptance_checks.py"
_FIXED_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _v(t_id: str, reason: str) -> list[Violation]:
    """把一次判定失败落成一条违例（规则号带 T 号，便于逐条定位）。"""
    return [Violation(f"ACC-{t_id}", f"{t_id}：{reason}", _MODULE)]


def _num(text: str) -> Decimal:
    return Decimal(text)


# ─────────────────────────── 判定器 ───────────────────────────


def t01_single_root_not_ten_independent(_root: Path) -> list[Violation]:
    """T01：十篇文章转述同一匿名订单 → 保留一个原始证据来源，不升为十份独立佐证。"""
    from scripts.evidence.independence import classify_independence

    base = {
        "source_id": "s-official",
        "claim_nature": "fact",
        "occurred_at": "2026-09-16T00:00:00Z",
        "company_ids": ["company-nvidia"],
    }
    root_claim = {
        "claim_id": "c-root",
        "publisher_entity": "官方",
        "direct_knowledge": "direct",
        **base,
    }
    restatements = [
        {
            "claim_id": f"c-{i}",
            "publisher_entity": f"转述媒体{i}",
            "origin_claim_id": "c-root",
            **base,
        }
        for i in range(1, 11)
    ]
    summary = classify_independence([root_claim, *restatements])
    if summary.root_count != 1:
        return _v("T01", f"十篇转述应归并到 **1** 个根，实得 {summary.root_count} 个")
    if len(summary.restatements) != 10:
        return _v("T01", f"应记 10 条转述，实得 {len(summary.restatements)} 条")
    if summary.independent_evidence_count.get("c-root") != 1:
        return _v(
            "T01",
            "根主张的独立佐证基数应为 1（十份转述不升为十份独立佐证），实得 "
            f"{summary.independent_evidence_count.get('c-root')!r}",
        )
    return []


def t02_single_sample_not_consensus(_root: Path) -> list[Violation]:
    """T02：只有一份公开盈利预测发生变化 → 更新公开样本；不声称完整市场一致预期已改变。

    载体（`registry/prep_deliverables.yaml::cr13_no_aggregate_consensus` 逐字指名）=
    `schema.models.ExpectationSample` + P-07 禁词（`consensus`/`market_view`/`average_forecast`）：
    ① 单份公开预测须能以**样本**形态落库（携 `sample_size` 与来源，`N5.2-02`）；
    ② 无 `source_id` 的外部预测须被拒（不得聚合无源预测冒充一致预期，`N5.2-03` / P-07）；
    ③ 样本对象**不得**承载一致预期升级字段（`extra="forbid"`，`N5.2-03`）。
    """
    from pydantic import ValidationError
    from schema.models import ExpectationSample

    base: dict[str, Any] = {
        "sample_id": "exp-t02-broker-alpha-fy2027-eps",
        "security_id": "node_nvda",
        "provider_id": "broker-alpha",
        "provider_kind": "broker",
        "metric": "eps",
        "period": "FY2027",
        "sample_value": "4.10",
        "sample_size": 1,
        "source_id": "src-broker-alpha",
        "occurred_at": _FIXED_TS,
    }

    # ①「按样本存」：单份公开盈利预测变化必须能以**样本**形态落库（携样本数与来源）。
    try:
        sample = ExpectationSample(**base)
    except ValidationError as exc:      # ← 只捕**校验失败**（具体异常），不吞一切
        return _v("T02", f"单份公开盈利预测无法以样本形态落库：{exc}")
    if sample.sample_size != 1 or not sample.source_id:
        return _v("T02", "样本未显式承载样本数 / 来源 → 无法据实标『公开预测样本(n=x)』")

    # ②「不聚合无源预测」：缺 source_id 的外部预测样本必须被拒（P-07）。
    rejected = False
    try:
        ExpectationSample(**{**base, "source_id": ""})
    except ValidationError:
        rejected = True
    if not rejected:
        return _v("T02", "无 source_id 的外部预测样本未被拒绝（P-07 聚合预测入口未关）")

    # ③「不升级为完整一致预期」：一致预期 / 共识字段不得塞进样本对象（`extra="forbid"`）。
    for upgraded in ("consensus", "market_view", "average_forecast"):
        rejected = False
        try:
            ExpectationSample(**{**base, upgraded: "完整一致预期"})
        except ValidationError:
            rejected = True
        if not rejected:
            return _v(
                "T02", f"样本对象接受 {upgraded!r} 字段 → 单源预测可被升级为完整一致预期"
            )
    return []


def _stage_equivalence_rejected(stage_from: str, stage_to: str) -> bool:
    """`assert_not_equivalent` 是否**拒绝**了这次跨级等同（拒绝 ⇒ 返回 True）。"""
    from scripts.graph.stage_order import StageEquivalenceError, assert_not_equivalent

    try:
        assert_not_equivalent(stage_from, stage_to)
    except StageEquivalenceError:
        return True
    return False


def t03_stage_not_auto_upgraded(_root: Path) -> list[Violation]:
    """T03：官方仅披露验证完成 → 不自动升级为量产供应 / 确认订单 / 收入。"""
    if not _stage_equivalence_rejected("order", "revenue"):
        return _v("T03", "order→revenue 的跨级等同未被拒绝（缺中间阶段证据）")
    if not _stage_equivalence_rejected("capex", "revenue"):
        return _v("T03", "capex(需求侧)→revenue 未被拒绝（不得把客户预算当供应商收入）")
    if _stage_equivalence_rejected("order", "purchase_commitment"):  # 相邻跨级：允许
        return _v("T03", "相邻阶段（order→purchase_commitment）被误拒绝")
    return []


def t04_third_party_evidence_admitted(_root: Path) -> list[Violation]:
    """T04：第三方证据可信且可复核、官方尚未确认 → 可纳入独立判断，不因缺官方确认一票否决。"""
    from scripts.evidence.independence import classify_independence

    third = {
        "claim_id": "c-third",
        "source_id": "s-thirdparty",
        "publisher_entity": "第三方研究方",
        "claim_nature": "fact",
        "direct_knowledge": "direct",
        "occurred_at": "2026-09-16T00:00:00Z",
        "company_ids": ["company-nvidia"],
    }
    summary = classify_independence([third])
    if summary.independent_evidence_count.get("c-third") != 1:
        return _v(
            "T04",
            "第三方直接知情主张未被计为独立佐证（不得因缺官方确认而一票否决）",
        )
    if summary.review_candidates:
        return _v("T04", f"第三方主张被误列入存疑：{summary.review_candidates}")
    return []


def _rec_input(stock: tuple[str, str], bench: tuple[str, str]) -> Any:
    """构造一个通过前置门的 `RecommendationInput`（自身基线 + 可解释预测 + DerivedValue 底稿）。"""
    from schema.models import DerivedValue
    from scripts.decision.gate import (
        ExplainableForecast,
        RecommendationInput,
        ResearchBaseline,
        ReturnValue,
    )

    def _dv() -> Any:
        return DerivedValue(
            derived_id="dv-acc",
            value=Decimal("0.1"),
            formula="a+b",
            operands=["a", "b"],
            method_version="v1",
            computed_at=_FIXED_TS,
        )

    def _fc(drivers: tuple[str, ...], rng: tuple[str, str]) -> Any:
        return ExplainableForecast(
            drivers=drivers,
            horizon="1q",
            return_range=ReturnValue(low=_num(rng[0]), high=_num(rng[1])),
            worksheet=_dv(),
            method_version="v1",
        )

    return RecommendationInput(
        company_id="company-acc",
        baseline=ResearchBaseline(
            company_id="company-acc", research_depth="baseline_done", baseline_complete=True
        ),
        stock_forecast=_fc(("d1",), stock),
        benchmark_forecast=_fc(("b1",), bench),
        own_evidence=("claim-acc",),
    )


def _decide(stock: tuple[str, str], bench: tuple[str, str], **kw: Any) -> Any:
    from scripts.decision.gate import JudgmentChange
    from scripts.decision.rules import decide

    judgment = kw.pop("judgment", JudgmentChange(fact_set_changed=True))
    return decide(_rec_input(stock, bench), judgment, **kw)


def t05_value_price_separated_no_mechanical_buy(_root: Path) -> list[Violation]:
    """T05：基本面改善但价格已更充分反映 → 分开更新价值状态与投资判断，不机械产生买入。"""
    from scripts.decision.rules import classify_opportunity

    improving_but_fully_reflected = classify_opportunity(
        {"growth_momentum_state": "strengthening"}, "fully_reflected"
    )
    if improving_but_fully_reflected:
        return _v(
            "T05",
            "价格已充分反映时仍标注机会类型 → 会机械产生买入倾向，实得 "
            f"{improving_but_fully_reflected}",
        )
    return []


def t06_no_min_excess_threshold(_root: Path) -> list[Violation]:
    """T06：预期绝对收益为正、仅略高于基准 → 不因最低超额幅度门槛拒绝建议。"""
    decision = _decide(("0.110", "0.120"), ("0.100", "0.105"))
    if decision is None or decision.action != "buy":
        got = None if decision is None else decision.action
        return _v("T06", f"仅略高基准不应被额外门槛拒绝，期望 buy，实得 {got!r}")
    return []


def t07_relative_underperform_sells(_root: Path) -> list[Violation]:
    """T07：预期仍有正收益但跑不赢基准 → 形成卖出建议并解释相对判断。"""
    decision = _decide(("0.050", "0.060"), ("0.100", "0.120"))
    if decision is None or decision.action != "sell":
        got = None if decision is None else decision.action
        return _v("T07", f"正收益但确定跑不赢应卖出，期望 sell，实得 {got!r}")
    return []


def t08_price_drop_recheck_not_autostop(_root: Path) -> list[Violation]:
    """T08：股价大跌且原因未明 → 触发强制复查；不自动止损、不自动买入、不改护城河。"""
    from scripts.decision.gate import JudgmentChange

    decision = _decide(
        ("0.050", "0.200"),
        ("0.050", "0.200"),
        judgment=JudgmentChange(),  # 判断未变 → 维持
        price_drop_triggered=True,
    )
    if decision is None:
        return _v("T08", "价格大跌触发的强制复查路径被前置门误拒")
    if decision.action == "sell":
        return _v("T08", "价格大跌被自动止损（转卖出）—— 应强制复查而非自动止损")
    if not decision.recheck_required:
        return _v("T08", "价格明显下跌未置 recheck_required（未触发强制复查）")
    return []


def t09_catalyst_moat_not_hard_gate(_root: Path) -> list[Violation]:
    """T09：低估但缺明确催化剂 / 护城河不强 → 不把两项设为硬性买入门槛。"""
    from scripts.decision.gate import RecommendationInput

    fields = set(RecommendationInput.__dataclass_fields__)
    for banned in ("catalyst", "catalyst_required", "moat", "moat_required"):
        if banned in fields:
            return _v("T09", f"买入门输入结构里出现了 {banned!r} → 催化剂/护城河被当硬门槛")
    decision = _decide(("0.110", "0.120"), ("0.100", "0.105"))
    if decision is None or decision.action != "buy":
        got = None if decision is None else decision.action
        return _v("T09", f"缺催化剂/护城河不应阻挡买入，期望 buy，实得 {got!r}")
    return []


def t10_pending_not_sell(_root: Path) -> list[Violation]:
    """T10：模型暂时不能判断相对收益 → 输出待判断和缺口；不混同为跑不赢。"""
    decision = _decide(("0.050", "0.200"), ("0.100", "0.120"))
    if decision is None:
        return _v("T10", "相对收益不确定被前置门误拒（应输出待判断）")
    if decision.action == "sell":
        return _v("T10", "相对收益不确定被误判为卖出 —— 待判断必须与卖出分离")
    if decision.action != "pending":
        return _v("T10", f"相对收益不确定应输出待判断，实得 {decision.action!r}")
    if not decision.gaps:
        return _v("T10", "待判断未附缺口（gap）")
    return []


def t11_effective_price_and_corporate_action(_root: Path) -> list[Violation]:
    """T11：盘后消息 / 拆股分红 → 不使用消息前报价假设可成交；正确处理时间与公司行动。"""
    from scripts.pricelayer.daily_explain import QuoteCaliber, validate_quote
    from scripts.pricelayer import QuoteCaliberViolation

    good = QuoteCaliber(
        quote_time=_FIXED_TS,
        trading_session="regular",
        currency="usd",
        adjusted_flag=True,
        corporate_actions_ref="caliber-v1",
    )
    try:
        validate_quote(good)
    except QuoteCaliberViolation as exc:
        return _v("T11", f"合规行情口径被误拒：{exc}")

    adjusted_without_ref = QuoteCaliber(
        quote_time=_FIXED_TS,
        trading_session="regular",
        currency="usd",
        adjusted_flag=True,
        corporate_actions_ref="",
    )
    try:
        validate_quote(adjusted_without_ref)
    except QuoteCaliberViolation:
        return []
    return _v("T11", "已调整口径但缺公司行动引用（corporate_actions_ref）未被拒绝")


def t12_retraction_traces_dependents(_root: Path) -> list[Violation]:
    """T12：原证据被撤回 / 财务数值重述 → 追踪依赖关系、触发复查，保留前后版本。"""
    from scripts.graph.adjacency import Edge
    from scripts.graph.closure import forward_closure, reverse_closure

    edges = (
        Edge("claim-x", "baseline-y", "supports", "dependency_edges", "e1"),
        Edge("baseline-y", "rec-z", "derives", "dependency_edges", "e2"),
    )
    known = {"claim-x", "baseline-y", "rec-z"}

    forward = forward_closure(
        _root, "claim-x", max_depth=5, source="dependency_edges", edges=edges, known_refs=known
    )
    if not {"baseline-y", "rec-z"}.issubset(set(forward.reached)):
        return _v(
            "T12",
            f"撤回主张未正向追踪到全部下游依赖，实得 {forward.reached}",
        )
    reverse = reverse_closure(
        _root, "rec-z", max_depth=5, source="dependency_edges", edges=edges, known_refs=known
    )
    if "claim-x" not in set(reverse.reached):
        return _v("T12", f"建议未反查回其依赖的主张，实得 {reverse.reached}")
    return []


def t13_missing_source_not_fabricated(_root: Path) -> list[Violation]:
    """T13：关键行情或来源不可访问 → 显示延迟和缺口，不伪造实时价格 / 全文 / 预测。"""
    from scripts.daily.degrade import holds_valid_result

    if holds_valid_result({}):
        return _v("T13", "空记录被当成持有有效结果 —— 存在伪造有效结果的风险")
    if not holds_valid_result({"status": "done", "output_refs": ["rec-1"]}):
        return _v("T13", "正常完成且产出的记录未被认作有效结果")
    if holds_valid_result({"status": "failed", "output_refs": []}):
        return _v("T13", "失败且无产出的记录被当成有效结果（伪造）")
    return []


def t14_ask_task_traceable(root: Path) -> list[Violation]:
    """T14：用户在公司或关系上提问 → 产生研究任务 + 来源回答 + 可追溯回写；失败状态可见。"""
    from scripts.graph.traceability import task_traceability_violations

    canonical = {
        "task_id": "task_ask_acceptance",
        "task_type": "ask",
        "status": "done",
        "input_refs": [],
        "output_refs": ["claim-acc"],
        "failure_reason": "tbd",
        "failure_stage": "tbd",
    }
    good, _ = task_traceability_violations(root, tasks=[canonical])
    if good:
        return _v("T14", f"可追溯的提问任务被误判为违例：{[x.reason for x in good]}")

    broken = {
        "task_id": "task_ask_broken",
        "task_type": "ask",
        "status": "done",
        "input_refs": [],
        "output_refs": [],
    }
    bad, _ = task_traceability_violations(root, tasks=[broken])
    if not bad:
        return _v("T14", "done 但无回写的提问任务未被判违例（可追溯回写未强制）")
    return []


#: `t_id -> 判定器`（**逐条对应** `registry/acceptance_input_set.yaml` 的 `t_cases`）。
ADJUDICATORS: dict[str, Callable[[Path], list[Violation]]] = {
    "T01": t01_single_root_not_ten_independent,
    "T02": t02_single_sample_not_consensus,
    "T03": t03_stage_not_auto_upgraded,
    "T04": t04_third_party_evidence_admitted,
    "T05": t05_value_price_separated_no_mechanical_buy,
    "T06": t06_no_min_excess_threshold,
    "T07": t07_relative_underperform_sells,
    "T08": t08_price_drop_recheck_not_autostop,
    "T09": t09_catalyst_moat_not_hard_gate,
    "T10": t10_pending_not_sell,
    "T11": t11_effective_price_and_corporate_action,
    "T12": t12_retraction_traces_dependents,
    "T13": t13_missing_source_not_fabricated,
    "T14": t14_ask_task_traceable,
}
# T01–T14 **全部** programmatic（14/14）。T02 的载体是共享 schema 模型
# `ExpectationSample`（`registry/prep_deliverables.yaml::cr13` 逐字指名），
# 不再标 `delegated` —— 由 `t02_single_sample_not_consensus` 真跑断言。


def adjudicate(t_id: str, root: Path) -> list[Violation]:
    """执行一条 T 的判定器（未知 t_id / 缺判定器 → 违例，**不静默通过**）。"""
    fn = ADJUDICATORS.get(t_id)
    if fn is None:
        return _v(t_id, "本层无对应判定器（责任章未提供可执行载体）")
    try:
        return list(fn(root))
    except Exception as exc:  # noqa: BLE001 - 非预期异常**必须**显形，不得吞成"通过"（G-03）
        return _v(t_id, f"判定器执行异常：{type(exc).__name__}: {exc}")


def main() -> int:
    root = _ROOT
    failed = 0
    for t_id in sorted(ADJUDICATORS):
        violations = adjudicate(t_id, root)
        if violations:
            failed += 1
            for item in violations:
                print(f"  [FAIL] {item.render()}")
        else:
            print(f"  [PASS] {t_id}")
    print(f"RESULT: {'PASS' if failed == 0 else 'FAIL'}（{failed} 条 T 不通过）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
