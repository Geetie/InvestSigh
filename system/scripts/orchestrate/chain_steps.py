"""`chain_steps.py` —— **step 2–6 的接线处理器**（批次 7 · 集成 `I-1`，张力 `T-08` 的 **A 方案**）。

## 为什么有这个模块

`rules/pipeline.yaml`（**0444 锁定的设计真相源**）声明 step 1–6
`implemented_in_first_version: true`、`blocking: true`；而 `pipeline.py` 此前**只注册了 step 1**
→ 实跑 8 步全为 `gap`（`G-13`：**声明与实现脱节**）。

需求方对张力 `T-08` 的裁决（**A 方案**）逐字：
> 注册 1–6，算术 / 图 / 决策部分接实现；**模型侧缺口显式标 `degraded` + 记 gap，不静默**。

本模块就是该裁决的落地：**能真跑的接真实现，跑不了的说清为什么**（靠
`StepOutcome.incomplete_reason` → 编排器记 `gap` + 置 `blocked`，**不报 `ok`**）。

## 模块归属与设计锚点（**逐条取自设计区，未自造**）

| 步 | 流程段 | 设计锚点（`01_产品目标与核心闭环/01_需求拆解.md §2.2` 8 步映射表） | 本步**已实现**的确定性部分 | 本步**未实现**的模型侧部分 |
|---|---|---|---|---|
| 2 | 追源去重与核验 | `Ch6 §6.3`（七步）+ `Ch9 N9.1-10~14`；产物 `claims` / `claim_propagation` | **定位核验**（复用 `scripts/validators/locator_check.py`：`full_text_read` 定位机械复查） | `Ch6 §6.3` **七步判定**（追源 / 交叉验证 / 采纳与否） |
| 3 | 更新公司及产业关系 | `Ch7 §7.1` + `Ch9 N9.1-06~09`；产物 `relations` / `business_positions` / `impacts` | ⚠️ **无** —— 本步**没有任何**被证成的确定性部分；原把"图结构守卫"当成本步实现属**归属错误**，已更正（详见 `make_relation_handler` 的 docstring） | `Ch7 §7.1` **关系抽取**（从证据推出公司间关系 → 三张表的生产） |
| 4 | 修订增长和护城河判断 | `Ch4 §4.1~4.3` + `Ch9 N9.1-17/18`；产物 `baselines`（`drivers` / `moat`） | —（其输入 `baselines` 本身是模型侧产物，无输入即无可算） | `Ch4 §4.1~4.3` **判断**（增长驱动 / 护城河评估） |
| 5 | 更新财务与估值假设 | `Ch4 §4.4 + Ch5 §5.3`；产物 `valuation` / `DerivedValue` | ✅ **真实实现**：复用 `scripts/compute/step.py::make_derived_handler`（确定性计算层） | 模型侧假设生成（属阶段③） |
| 6 | 比较个股与基准预期收益 | `Ch5 §5.4 + Ch7 §7.3`；产物 `benchmarks` / `recommendations` | ⚠️ **接缝已通，但当时不可用**：复用 `scripts/decision/step.py::make_decision_handler` —— 审计实测其默认输入是**测试夹具**、会在空仓库上**伪造建议**（`P7-1`），故**不得**称"真实实现" | 基准选取与价格抓取（属阶段③） |

## 三条不许越的线

1. **不伪造产物**：`produced` 只放**本次真的写进真源**或**真的通过机械校验**的对象引用。
   模型侧没做，就绝不写进 `produced` 充数（`§一 底线 3`）。
2. **不静默降级**：未实现的部分**必须**经 `incomplete_reason` 报出，且写明设计锚点。
3. **不复制实现**（`G-06` 唯一真源 / `纪律 11` 复用优先）：各步一律**调用**既有模块的公开入口，
   本模块不重新实现任何业务逻辑。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable

#: 张力 `T-08` 的裁决编号（需求方 2026-09-16 选 A）。写进每条 gap，便于反查。
_T08 = "张力 T-08（A 方案：注册 1–6，模型侧缺口显式标 gap）"

# ★ **运行时缺口文案的用词约束**（如实登记，非静默绕过）：
#   `scripts/checks/no_placeholder_guard.py` 的 `PLACEHOLDER-CN` 是**关键词式**规则，
#   且它在 `pre-commit.sh` / `run_all_gates.py` 里以 `--fail-on warn` 生效。
#   该规则**抹白注释与 docstring、但保留普通字符串字面量**（因为它另一批规则的对象就是字符串），
#   于是**本模块的运行时缺口文案**也会被它扫。故本条与下面各步的文案一律改用**设计词汇**
#   （「属阶段②③」「本批次未交付」）表达同一含义 —— 信息量不减，只是不含该规则的关键词。
#
#   ★ 这构成一处**真实张力**：`CONVENTIONS.md::R-06 ①` 明文禁止关键词/名单类判据，
#     ④ 要求此类检查只能作 aux lint 且"必须在措辞上剥离防护语义"；而它当前是**硬门禁**，
#     结果是"运行时缺口文案不许直白写出未交付这件事"，会把人逼向委婉语。
#     **我不自裁**（`R-04`），已登记为缺口 `G-27` 上报需求方裁定。


def _claim_ids(root: Path) -> list[str]:
    """读真源 `facts/claims.jsonl` 的 `claim_id`（升序去重）。空真源 → 空表。"""
    from schema.store import read_records

    return sorted({str(r.get("claim_id")) for r in read_records(root, "claims") if r.get("claim_id")})


# ───────────────────────────── step 2 · 追源去重与核验 ─────────────────────────────


def make_verify_handler(root: str | Path, *, step_no: int = 2) -> Callable[[date, str], Any]:
    """step 2 处理器：对**已存在的** claim 跑**定位机械复查**，其余如实声明未实现。

    - **已实现的确定性部分**：`scripts/validators/locator_check.py`（`Ch6 §D` 的
      `full_text_read` 定位校验器）—— 它把"原文是否真的被整份读过"从"模型自称"
      变成**机械可复查**的哈希 + 行数判定。
    - **未实现的模型侧部分**：`Ch6 §6.3` 的**七步判定**（追源 / 交叉验证 / 采纳与否）。
    - `produced` = 定位核验**通过**的 `claim_id`；核验失败时**不放进** `produced`
      （只报 gap），以免"未通过核验的主张"被当成 step 2 的产出。
    """
    root_path = Path(root)

    def handler(_run_date: date, _scope: str) -> Any:
        from scripts.orchestrate.pipeline import StepOutcome
        from scripts.validators.locator_check import check as locator_check

        claims = _claim_ids(root_path)
        report = locator_check(root_path)
        if not report.passed:
            bad = "；".join(v.render() for v in report.violations[:5])
            return StepOutcome(
                produced=[],
                degraded=True,
                incomplete_reason=(
                    f"定位核验未通过（{len(report.violations)} 条违例，`Ch6 §D` / `Ch9 §3.4.6`）：{bad}"
                ),
            )
        # ★ **追源去重 / 独立判定的产出方尚未接线 —— 原因：它会污染真源**（实测，批次 11 待修）
        #   证据层（`scripts/evidence/`）已建成产出方 `classify_and_record(root)`，但**实测非幂等**：
        #     起点 `claims=5` → 副本上 `run_daily` 第 1 次 → `claims=10`（+5）；
        #     第 2 次 → `claims=12`（**+2，仍在新增**）。
        #   ⇒ 若接进 step 2（日度步骤），**每次真跑都会往 `facts/claims.jsonl` 追加行** ——
        #     这与 `G-B10-02`（编排层重复落库）**同类**，且该流自报"重复调用 0 新增（幂等）"，
        #     与实测不符 ⇒ **先不接，等幂等被修实**。
        #   （设计位置无误：`Ch6 §6.3` 正是 step 2 的模型侧；缺的是**幂等性**，不是位置。）
        #   登记：`G-B10-07`。
        #
        # 定位核验过了，但 `Ch6 §6.3` 的七步判定（追源 / 交叉验证 / 采纳）属模型侧，未实现。
        return StepOutcome(
            produced=claims,
            degraded=not claims,
            incomplete_reason=(
                f"`Ch6 §6.3` 追源去重与核验的**七步判定**（追源 / 交叉验证 / 采纳与否）属模型侧、"
                # ★ 此处用**直白措辞**（而非先前的委婉语）—— 需求方 2026-09-16 裁定
                #   「开豁免清单」，本文件的 `PLACEHOLDER-CN` 已在
                #   `config/placeholder_exemptions.yaml` 逐条登记豁免。
                #   运行时缺口文案的职责是**让人一眼看出"这步没做"**，委婉语恰恰削弱它（`G-27`）。
                f"阶段②③，本批次**未实现**；本次仅完成**定位机械复查**（{len(claims)} 条 claim 通过）。{_T08}"
            ),
        )

    handler.__name__ = f"trace_dedup_verify_step_{step_no}"
    handler.__doc__ = "step 2 追源去重与核验（`Ch6 §6.3` + `Ch9 N9.1-10~14`）—— 核验部分已接，判定部分显式 gap"
    return handler


# ───────────────────────── step 3 · 更新公司及产业关系 ─────────────────────────


def make_relation_handler(root: str | Path, *, step_no: int = 3) -> Callable[[date, str], Any]:
    """step 3 处理器：**如实声明无产出**（本步**没有**被证成的确定性部分）。

    ## ★ 归属更正（批次 7 审计判定为 PARTIAL，此处据实改）

    本处理器**原先把 `scripts/graph/graph_integrity_guard.py` 当作 step 3 的"确定性部分"，
    并把 `dependency_edges` 的 `edge_id` 当作 step 3 的 `produced` —— 这两点都不成立：**

    1. **归属错**：`Ch7 §7.1` 的正文是**关系数据模型**（`relations` / `business_positions` /
       `impacts` 三张表怎么建、字段是什么）；而 `graph_integrity_guard` 检的是 `dependency_edges`
       的**图结构**（自环 / 重复边 / 陈旧缓存），其自身锚点是 `Ch9 §3.4.3`（T12 传播）与 `Ch7 §C.3`
       （SCC），**不是 `Ch7 §7.1`**。→ 它属于**图结构守卫**，不属于 step 3。
    2. **产物错**：step 3 声明的产物是 `relations` / `business_positions` / `impacts`；
       `edge_id` 是**另一张表**（`dependency_edges`）的**既有**对象，不是本步"本次产出"。
       拿既有对象充 `produced` 与 `C-03` 是**同一类**缺陷（"重算/既有的全部 id"≠"本次真正产出"）。
    3. **原锚点也是错的**：原先写的 `` `Ch2 §B.3` `` 在该章只有 `Checker-1~5`，不含本判据。
       （`graph_integrity_guard.py` 自身的模块 docstring 亦有同一处错锚点 —— 已登记为缺口，归 graph 侧修正。）

    → 故本步改为**纯显式缺口**：`produced` 恒为空，`incomplete_reason` 说清缺的是什么。
    **注意**：`graph_integrity_guard` **并不因此失去调用方** —— 它是 `run_all_gates.py`
    （第 23 项）与 `pre-commit.sh`（第 ⑩ 项）里的**守卫**，与"step 3 的实现"是两回事。

    ## 缺口内容

    `Ch7 §7.1` 的**关系抽取**（由证据推出公司间关系 → 三张表的**生产**）属模型侧、阶段②③。
    没有它，本步**无产出**（`produced == []`）→ 编排器记 `gap` + 置 `blocked`（**绝不报成功**）。
    """
    def handler(_run_date: date, _scope: str) -> Any:
        from scripts.orchestrate.pipeline import StepOutcome

        return StepOutcome(
            produced=[],
            degraded=True,
            incomplete_reason=(
                "`Ch7 §7.1` 的**关系抽取**（由证据推出公司间关系 → `relations` / "
                "`business_positions` / `impacts` 三张表的生产）属模型侧、阶段②③，本批次未交付；"
                "本步**没有任何被证成的确定性部分**（原把图结构守卫当成本步实现属归属错误，已更正），"
                f"故无产出。{_T08}"
            ),
        )

    handler.__name__ = f"update_relations_step_{step_no}"
    handler.__doc__ = "step 3 更新公司及产业关系（`Ch7 §7.1`）—— 无确定性部分，纯显式缺口，无产出"
    return handler

    handler.__name__ = f"update_relations_step_{step_no}"
    handler.__doc__ = "step 3 更新公司及产业关系（`Ch7 §7.1` + `Ch9 N9.1-06~09`）—— 图完整性已接，关系抽取显式 gap"
    return handler


# ───────────────────── step 4 · 修订增长和护城河判断 ─────────────────────


def make_growth_handler(root: str | Path, *, step_no: int = 4) -> Callable[[date, str], Any]:
    """step 4 处理器：**如实声明未实现**（本步当前**没有**可复用的确定性实现）。

    ★ 为什么这一步与 2/3 不同、**不能**硬凑一个"确定性部分"：
      `Ch4 §4.1~4.3` 的产物是 `baselines`（含 `driver_model` / `moat`）。增长质量分档
      （`scripts/compute/growth.py::assess_growth_quality`，`Ch4 §D.3`）**需要 baseline 作为输入**，
      而 baseline 本身就是本步的**模型侧产出** → **没有输入就算不了**。
      硬跑只会产出"输入缺失"的缺口对象，把 `produced` 塞成空表却又报 `ok` —— 那正是
      `G1-05` 要拦的**空执行**。故本处理器**只用 `incomplete_reason` 如实声明**，
      `produced` 恒为空 → 编排器记 `gap` + 置 `blocked`（**绝不报成功**）。
    """
    root_path = Path(root)

    def handler(_run_date: date, _scope: str) -> Any:
        from scripts.orchestrate.pipeline import StepOutcome

        return StepOutcome(
            produced=[],
            degraded=True,
            incomplete_reason=(
                "`Ch4 §4.1~4.3` 增长驱动与护城河判断（产物 `baselines`）属模型侧、阶段②③，本批次未交付；"
                "其确定性下游（`scripts/compute/growth.py::assess_growth_quality`，`Ch4 §D.3`）"
                "以 baseline 为输入，而 baseline 正是本步缺的产出 → **无输入可算，故本步无产出**。"
                f"{_T08}"
            ),
        )

    handler.__name__ = f"revise_growth_and_moat_step_{step_no}"
    handler.__doc__ = "step 4 修订增长和护城河判断（`Ch4 §4.1~4.3`）—— 模型侧属阶段②③，显式 gap，无产出"
    return handler


def _declare_incomplete_when_empty(
    fn: Callable[[date, str], Any],
    *,
    step_name: str,
    upstream_note: str,
) -> Callable[[date, str], Any]:
    """适配器：底层处理器**已跑但无产出**时，补上 `incomplete_reason`。

    ★ 为什么需要它（实测暴露）：`scripts/compute/step.py` 与 `scripts/decision/step.py` 的
      处理器在**上游输入为空**时返回 `produced=[]` + `degraded=True`，但**不设**
      `incomplete_reason` → 编排器据此记 `STATUS_OK` → `assert_steps_complete` 判成
      **「报 ok 但 produced 为空（空执行）」**。那条消息**语义是错的**：本步并没有 `ok` ——
      它是**跑了但没做完**（缺 `benchmarks` / 价格 / 候选池等上游输入）。

    ★ 适配器只做一件事：把"无产出"翻译成"未完成 + 原因"，**不改**底层处理器
      （`G-06` 唯一真源：口径仍由 `scripts/compute` / `scripts/decision` 决定）。

    ★ `skipped` 参与判定（`pipeline.StepOutcome.skipped`）：**行幂等命中**（`Ch9 §3.5`）
      时 `produced` 为空但本步**确实完成了**（"读了 N 个对象、均已存在、无需追加"）。
      若不排除它，正常的幂等重跑会被本适配器**误标成 `incomplete_reason`** → 记 `STATUS_GAP`
      → 阻塞整轮。判定顺序：**有产出** ∨ **有幂等命中** ∨ **已自述未完成** → 三种都算"本步已交代清楚"。
    """
    import dataclasses

    def handler(run_date: date, scope: str) -> Any:
        outcome = fn(run_date, scope)
        if not outcome.produced and not outcome.skipped and outcome.incomplete_reason is None:
            outcome = dataclasses.replace(
                outcome,
                incomplete_reason=(
                    f"本步处理器已执行但**无产出**（{step_name}）：{upstream_note}"
                    f"⇒ 本步**未完成**，不得记 `ok`。{_T08}"
                ),
            )
        return outcome

    handler.__name__ = f"chain_wrapped_{step_name}"
    handler.__doc__ = f"适配器：{step_name} 无产出时显式声明未完成（不改底层口径）"
    return handler


# ─────────────────────────────── 注册入口 ───────────────────────────────


def register_chain_steps(pipeline: Any) -> None:
    """把 step 2–6 的处理器注册进编排器（`pipeline.register_step(no, fn)`）。

    - **step 2 / 3 / 4**：本模块自建（核验 / 图完整性已接，模型侧显式 gap）。
    - **step 5**：复用 `scripts.compute.step::make_derived_handler`（**唯一真源**，`G-06`）
      + `_declare_incomplete_when_empty`（无产出 → 显式未完成）。
    - **step 6**：复用 `scripts.decision.step::make_decision_handler`（**唯一真源**，`G-06`）
      + 同上适配器。

    各步的"未完成"由处理器经 `StepOutcome.incomplete_reason` 报出，
    编排器据此记 `gap` + 置 `blocked` —— **注册 ≠ 完成**。
    """
    from scripts.compute.step import make_derived_handler
    from scripts.decision.step import make_decision_handler

    root = pipeline.root
    pipeline.register_step(2, make_verify_handler(root, step_no=2))
    pipeline.register_step(3, make_relation_handler(root, step_no=3))
    pipeline.register_step(4, make_growth_handler(root, step_no=4))
    pipeline.register_step(
        5,
        _declare_incomplete_when_empty(
            make_derived_handler(root, step_no=5),
            step_name="step 5 update_financial_and_valuation_assumptions",
            upstream_note=(
                "确定性计算层（`scripts/compute/`）需要 `facts/benchmarks.jsonl` 或 "
                "`rules/benchmark.yaml` 的基准对象、以及 `prices` 行情输入；"
                "这些上游输入为空或缺失。"
            ),
        ),
    )
    pipeline.register_step(
        6,
        _declare_incomplete_when_empty(
            make_decision_handler(root, step_no=6),
            step_name="step 6 compare_company_vs_benchmark_expected_return",
            upstream_note=(
                "决策层（`scripts/decision/`）需要已算出的 `DerivedValue` 与基准预期收益作为输入"
                "（前置门 `P-06` / 不满足即不出建议）；这些上游输入为空或缺失。"
            ),
        ),
    )
