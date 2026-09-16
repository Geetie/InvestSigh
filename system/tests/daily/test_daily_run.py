"""AC-5：**每日运行薄封装**的端到端 + 反 KPI 守卫（`Ch1 §D.3` / `Ch1 §F G1-02` / `Ch8 §D/§E/§F`）。

锚点：`Ch1 §D.3`（反 KPI：**每天维护判断 ≠ 每天必须产生新买卖信号**）/
`Ch1 §F G1-02`（三条断言：无变化日零信号 / 新建议有 `change_reason` / 建议数 ≤ 变化数）/
`Ch1 §D.1`（8 步闭环）/ `Ch8 §E`（降级可见）/ `Ch8 §N8.4-08`（同日重跑不重复产事件/建议）。

## ★ 本文件修的是"反 KPI 测试在空真源上恒真"这一缺陷（批次 10 审计 `ch8 AC-5 = FAIL`）

**原缺陷**：`test_no_change_day_emits_zero_signals` 跑在 `code_root` 夹具的**空真源**上
（`tests/conftest.py` 的契约"真源为空"）。空真源 ⇒ 无行情 / 无基准 ⇒ step 6（建议生成）
**根本走不到** ⇒ `signals_emitted == 0` **恒真** ⇒ 该断言**不构成守卫**
（`CONVENTIONS.md §二 G-03` 的"空样本不得当已核"同样适用于测试自身）。

**修法**（`G-RC-02`：测试自己声明自己的数据）：见 `_seed_step6_inputs()` ——
在夹具副本里播种**能走到 step 6 的最小真源**，然后**正反两向**：

- **(a) 无交易信号的运行日** → `signals_emitted == 0`，且**确实产出了建议**
  （非真空：零信号是"决策结论"，不是"路径缺失"）；
- **(b) 有交易信号的运行日** → `signals_emitted` **正常计数**（反向对照，证明它不是"永远 0"）。

★ **只有 (a) 通过不算通过** —— 没有 (b) 就无法区分"守卫在工作"与"路径根本没走到"
（这正是原测试的毛病）。判别力另由 `test_no_signal_assertion_has_discrimination` 用
**故意注入违规**钉死（`G-05` / `G-16`：不许有恒真断言）。

## ★ 与"真仓库反 KPI 已破"的关系（缺口 `G-RC-04`，**本流写入域之外**，如实登记）

真仓库 `facts/tasks.jsonl` 现有 `check_record = {changed: false, …, signals_emitted: 1}`
（由 `pipeline.run_daily` 写出，同日产出 `rec-nvda-001`），`no_signal_day` 对它 FATAL。
根因**不在本文件、也不在本流写入域**：`pipeline` 的 step 6 处理器**恒回传 `judgment_change={}`**
（`scripts/decision/step.py`），故任何"买 / 卖"日写出的记录都是 `changed=False + signals=1`。
本文件**不修**该缺口（属共享编排层，归主理人），但**测试能发现该形态**：见
`test_anti_kpi_guard_discriminates`（`(changed=False, signals=1)` → 守卫命中）
与 `test_no_signal_assertion_has_discrimination`（注入 → 真红）。
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from pathlib import Path

import pytest

from schema.models import Company
from schema.store import append_records, read_records
from scripts.checks import no_signal_day
from scripts.daily import run as daily_run

_RUN_DAY = date(2026, 9, 16)
_START = date(2026, 9, 1)
_END = date(2026, 9, 10)
_COMPANY_SEC = "usNVDA"
_BENCH_SEC = "usAGIX"


# ── 播种：造出**能走到 step 6**的最小真源（`G-RC-02`） ─────────────────────────


def _append_raw(root: Path, stem: str, rows: list[dict]) -> None:
    """绕过 pydantic 直接写真源行（`facts/<stem>.jsonl`）。

    ★ 为什么这两张表**不能**走 `append_records`（对象模型）：

    - `facts/prices.jsonl` 的行由 `scripts.compute.driver.load_price_points` 按**原始 dict** 解析
      （字段 `security_id` + `day` + `price`），与 `schema.models.PriceSnapshot` 的字段名不同；
    - `facts/benchmarks.jsonl` 需要基准对象带**显式 `security_id`**（step 6 靠它解析基准证券），
      而冻结的 `schema.models.Benchmark` **无 `security_id` 字段**。

    这与 `tests/conftest.py::_reset_truth_source`（同样直接写 JSONL）同一形态，
    且写入后经 `driver` 的**真实读取路径**消费（并非绕过被测逻辑）。
    """
    path = root / "facts" / f"{stem}.jsonl"
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _seed_step6_inputs(root: Path, *, company_end_price: str, benchmark_end_price: str) -> None:
    """播种**能走到 step 6（建议生成）的最小真源**（`G-RC-02`）。

    最小集 = **2 张真源表**（均落在 `Ch9 §3.3.3` 的 18 个 JSONL 内，**不新增文件**）：

    | 表 | 行 | 为什么这些够 |
    |---|---|---|
    | `facts/prices.jsonl` | 2 证券 × 2 行情点（同起止日 `2026-09-01` .. `2026-09-10`） | `run_default` 取"个股 / 基准各 ≥2 点"才能算区间收益（`<2` → `inputs_unavailable`） |
    | `facts/benchmarks.jsonl` | 1 行**主基准对象**（显式 `security_id`） | step 6 靠它解析基准证券；缺 → `securities_unresolved` |

    真实步序走查（`scripts/decision/run_decide.py::run_default`）：
    `_load_truth_series`(读 prices) → `_load_primary_benchmark`(读 benchmarks) →
    `_resolve_benchmark_security`(用显式 `security_id`) →
    `_select_company_security`(行情里除基准外的**唯一**证券) →
    `_run_core`: `compute_total_return` × 2 → 前置门 → 5 规则 → **落 `recommendations`**。

    **收益率只由终点价决定**（起点价恒 `100`）：

    - `company_end_price == benchmark_end_price` ⇒ 相对方向 `uncertain` ⇒ R3 `pending`（**不产信号**）；
    - `company_end_price > benchmark_end_price` 且绝对为正 ⇒ R1 `buy`（**产 1 个信号**）。
    """
    _append_raw(
        root,
        "prices",
        [
            {"security_id": _COMPANY_SEC, "day": _START.isoformat(), "price": "100"},
            {"security_id": _COMPANY_SEC, "day": _END.isoformat(), "price": company_end_price},
            {"security_id": _BENCH_SEC, "day": _START.isoformat(), "price": "100"},
            {"security_id": _BENCH_SEC, "day": _END.isoformat(), "price": benchmark_end_price},
        ],
    )
    _append_raw(
        root,
        "benchmarks",
        [
            {
                "benchmark_id": _BENCH_SEC,
                "benchmark_role": "primary",
                "security_id": _BENCH_SEC,
                "return_source": "fund_market_price",
                "proxy_index_used": False,
                "return_basis": {
                    "currency": "USD",
                    "dividends_reinvested": True,
                    "fee_deducted_again": False,
                },
            }
        ],
    )


def _check_records(root: Path) -> list[dict]:
    """取 `facts/tasks.jsonl` 里所有 `check_record` 子记录（`Ch1 §C.2`；控制面子记录）。"""
    return [
        t["check_record"]
        for t in read_records(root, "tasks")
        if isinstance(t.get("check_record"), dict)
    ]


def _degraded_marks(root: Path) -> list[dict]:
    return [
        r
        for r in read_records(root, "tasks")
        if isinstance(r.get("parent_context"), dict) and r["parent_context"].get("degraded") is True
    ]


# ── AC-5 (a)：无交易信号的运行日 → 零信号；且**路径确实走到了 step 6** ──────────────


def test_no_change_day_emits_zero_signals(code_root: Path) -> None:
    """(a) 无交易信号的运行日 → `signals_emitted == 0` 且 `changed is False`。

    ★ **非真空断言**（本用例判别力所在）：同一次运行**必须真产出一条建议**
      （`action=pending`）。这正是原测试缺的那一环 —— 空真源谈"零信号"没有分辨力；
      "走到了 step 6 却按规则**不产**信号"才落进反 KPI 的口径（`Ch1 §D.3`）。
    """
    _seed_step6_inputs(code_root, company_end_price="110", benchmark_end_price="110")
    report = daily_run.run_daily(code_root, _RUN_DAY)

    assert report.signals_emitted == 0
    assert report.changed is False

    # ★ 非真空：step 6 **确实执行并产出建议**（否则 `== 0` 是"没走到"而非"不产信号"）
    actions = [r.get("action") for r in read_records(code_root, "recommendations")]
    assert actions == ["pending"], actions
    # 真源行情 / 基准被**真实消费**（无"输入缺失"缺口 → 排除退化路径冒充）
    assert not any("inputs_unavailable" in g for g in report.gaps), report.gaps

    # 该运行写出的 check_record 如实：无变化 + 零信号 → 反 KPI 守卫放行
    checks = _check_records(code_root)
    assert checks and checks[0]["changed"] is False and checks[0]["signals_emitted"] == 0
    guard = no_signal_day.check(code_root)
    assert guard.passed, [v.render() for v in guard.violations]


# ── AC-5 (b)：有交易信号的运行日 → 信号**正常计数**（反向对照） ──────────────────────


def test_change_day_signal_is_counted(code_root: Path) -> None:
    """(b) 有交易信号的运行日 → `signals_emitted` **正常计数**（证明它不是"永远 0"）。

    没有本用例，就无法区分"守卫在工作"与"路径根本没走到"（这正是原测试的毛病）。
    """
    _seed_step6_inputs(code_root, company_end_price="130", benchmark_end_price="110")
    report = daily_run.run_daily(code_root, _RUN_DAY)

    assert report.signals_emitted == 1
    actions = [r.get("action") for r in read_records(code_root, "recommendations")]
    assert actions == ["buy"], actions


# ── 反 KPI 守卫（`scripts/checks/no_signal_day.py`）**两向判别力** ────────────────


@pytest.mark.parametrize(
    ("changed", "signals", "expect_hit"),
    [
        (False, 0, False),  # 无变化日、无信号 —— 反 KPI 期望态，不得误报
        (True, 1, False),   # 有变化日、有信号 —— 反向对照：守卫**不得**误杀
        (False, 1, True),   # ★ 无变化却产信号 —— 真违规（G1-02①），**必须**命中（= 真仓库形态）
        (True, 0, False),   # 有变化却零信号 —— 反 KPI **不**覆盖该类（见报告"本层无法覆盖"）
    ],
)
def test_anti_kpi_guard_discriminates(changed: bool, signals: int, expect_hit: bool) -> None:
    """`check_no_signal_day` 对 `(changed, signals_emitted)` 四组合的判定力。

    第三行 `(False, 1)` 即真仓库当前 `check_record` 的**同一形态**（`G-RC-04`）——
    证明守卫**能发现**"无变化却产信号"。
    """
    rec = {"run_date": _RUN_DAY.isoformat(), "changed": changed, "signals_emitted": signals}
    violations = no_signal_day.check_no_signal_day([rec])
    hit = [v for v in violations if v.rule == "G1-02①"]
    assert bool(hit) is expect_hit, (changed, signals, [v.render() for v in violations])


# ── ★ 判别力反证（`G-05` / `G-16`）：故意制造违规 → (a) 的断言必须变红 ──────────────


def test_no_signal_assertion_has_discrimination(
    code_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**故意制造违规**：在"无变化"的播种数据上强制 step 6 报告 `signals_emitted=1`。

    期望（三者缺一不可）：

    1. 违规注入**生效**（`signals_emitted == 1`）；
    2. 于是 (a) 的目标准确性 `signals_emitted == 0` **不成立** —— 若 (a) 是恒真断言，
       这一步就不可能发生（本用例把"注入违规 → 必红"钉进测试，`G-16`）；
    3. 反 KPI 守卫对本次运行写出的 `check_record`（`changed=False, signals=1`）**如实命中**。
    """
    _seed_step6_inputs(code_root, company_end_price="110", benchmark_end_price="110")
    from scripts.decision import run_decide

    real_run_default = run_decide.run_default

    def _forced(root, **kwargs):  # type: ignore[no-untyped-def]
        # 强制"多报一个信号"，模拟"无变化却产信号"的真违规形态（其余如实转回）。
        return dataclasses.replace(real_run_default(root, **kwargs), signals_emitted=1)

    monkeypatch.setattr(run_decide, "run_default", _forced)

    report = daily_run.run_daily(code_root, _RUN_DAY)

    assert report.signals_emitted == 1  # ① 违规注入生效
    assert not (report.signals_emitted == 0)  # ② (a) 的目标在此不成立 → (a) 有判别力
    guard = no_signal_day.check(code_root)  # ③ 守卫必须发现它
    assert any(v.rule == "G1-02①" for v in guard.violations), [
        v.render() for v in guard.violations
    ]


# ── 降级：空真源 → 降级可见 + 保留上次有效结果（如实为空） ───────────────────


def test_report_is_faithful_not_optimistic(code_root: Path) -> None:
    """缺口（模型侧未实现）**如实**报出并置 blocked，不得被乐观改写为成功。"""
    report = daily_run.run_daily(code_root, _RUN_DAY)
    assert report.blocked is True
    assert len(report.gaps) > 0


def test_degradation_is_visible_on_empty_truth(code_root: Path) -> None:
    report = daily_run.run_daily(code_root, _RUN_DAY)
    assert report.degraded is True
    assert report.degradation_visible is True
    assert report.degradation_task_id is not None
    assert report.last_valid_result_ref is None  # 首日降级：如实为空

    marks = _degraded_marks(code_root)
    assert len(marks) == 1
    assert marks[0]["parent_context"]["run_date"] == _RUN_DAY.isoformat()


# ── 幂等：同日重跑 N 次不重复产事件/建议，且运行记录幂等键唯一 ───────────────


def test_same_day_rerun_no_duplicate_events_or_recommendations(code_root: Path) -> None:
    for _ in range(3):
        report = daily_run.run_daily(code_root, _RUN_DAY)

    assert report.duplicate_events == ()
    assert report.duplicate_recommendations == ()
    assert len(read_records(code_root, "events")) == 0
    assert len(read_records(code_root, "recommendations")) == 0

    # 运行记录（check_record）追加式写入，但幂等键唯一（同日重跑用 `_r<n>` 修订号）
    keys = [
        r.get("idempotency_key")
        for r in read_records(code_root, "tasks")
        if str(r.get("idempotency_key", "")).startswith("check::")
    ]
    assert len(keys) == len(set(keys)), keys
    # 降级标记同日幂等：只落一条
    assert len(_degraded_marks(code_root)) == 1


# ── 覆盖可核（阶段④ 硬判据）在真实运行路径上生效 ────────────────────────────


def test_coverage_criterion_fires_on_run_path(code_root: Path) -> None:
    """空真源 → 覆盖目标集为空 → CV4（真空不得判过）命中 → `coverage_ok is False`。"""
    report = daily_run.run_daily(code_root, _RUN_DAY)
    assert report.coverage_ok is False
    assert any("CV4" in v for v in report.coverage_violations), report.coverage_violations


def test_coverage_ok_when_acceptance_input_is_covered(code_root: Path) -> None:
    append_records(
        code_root, "companies", [Company(company_id="c1", legal_name="C1")]
    )
    registry = code_root / "registry"
    registry.mkdir(parents=True, exist_ok=True)
    (registry / "acceptance_input_set.yaml").write_text(
        "first_list_version:\n  - c1\n", encoding="utf-8"
    )

    report = daily_run.run_daily(code_root, _RUN_DAY)
    assert report.coverage_ok is True, report.coverage_violations


# ── ★ `G-43` / `G-45`：写路径**真的**填了「保留上次有效结果」的两个字段 ─────────────
#
# 缺陷回顾（独立审计批次 11，逐条实测）：
#   `pipeline._write_check_record()` 写 `facts/tasks.jsonl` 时**既不设** `last_valid_result_ref`
#   **也不设** `output_refs` ⇒ 真行恒为 `None` / `[]` ⇒ 阶段④ 的判据
#   `degrade_keeps_last_valid` 的首日豁免谓词**恒 False** ⇒ 每个失败行都被当"首日"豁免
#   ⇒ **判据空转，从不报任何真违规**；且全仓库 `output_refs=` **零个生产赋值点**。
#
# ★ 本用例为什么必须走**完整 `run_daily`**（而不是直接调写入函数）：
#   "改了谓词"与"真源里字段真的被填了"是两件事 —— 前者在函数级测试里就能过，
#   后者只有**真跑一遍端到端再读真源**才看得见（本项目反复出现的形态："改了"但机器上不生效）。


def _stub_eight_steps(monkeypatch: pytest.MonkeyPatch, fail_step: dict) -> None:
    """把 8 步换成**确定性桩**（只为造出"第一次成功"这一前提），写入方仍是真代码。

    ★ 为什么必须换桩：step 2/3/4/7/8 的模型侧在本批次**未交付**，`rules/pipeline.yaml` 里
      `blocking: true` ⇒ 不换桩则每轮都 `blocked`，"成功运行"这个前提**根本造不出来**，
      于是"失败行应保留引用"这条契约永远无法被端到端验证。
      桩只提供 `StepOutcome`，**被验证的写入方 `_write_check_record()` 是真代码**。
    """
    from scripts.orchestrate import pipeline as P

    real = P.Pipeline._register_default_steps

    def patched(self):  # type: ignore[no-untyped-def]
        real(self)
        for no in range(1, 9):
            def handler(_d, _s, _no=no):  # type: ignore[no-untyped-def]
                if fail_step.get("on") and _no == 3:
                    raise RuntimeError("注入故障：step 3 模型侧超时")
                return P.StepOutcome(produced=[f"obj-step{_no}"])
            self.register_step(no, handler)
        # 7/8 步的 hook 也注册（否则 `assert_steps_complete` 记 G1-05 gap → 恒 blocked）
        self.register_publish_hook(lambda _r: None)
        self.register_verify_hook(lambda _r: None)

    monkeypatch.setattr(P.Pipeline, "_register_default_steps", patched)


def test_writepath_really_fills_degrade_contract_fields(
    code_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """先成功、后失败：读 `facts/tasks.jsonl` 的**真实行**，证明两个字段真的被填了。

    断言四件事（缺一不可）：
    ① 成功行：`status=done`、`output_refs` **非空**（本轮真正新写入的对象引用）、
       `last_valid_result_ref=None`（本次结果就是有效结果）；
    ② 失败行：`status=failed`、`output_refs` 如实为空、
       `last_valid_result_ref` = **第一次成功运行的 `check_id`**（`Ch8 §E.2`："失败时指向旧结果"）；
    ③ 降级标记行（`degrade.mark_degraded()` 写的，**另一个模块**）指向**同一个** `check_id`
       —— 消掉 `G-45` 的"两个模块口径相反"；
    ④ 首日（第一次运行）失败时 `last_valid_result_ref` **如实为空**，不得臆造（`G-03`）。
    """
    fail_step: dict = {}
    _stub_eight_steps(monkeypatch, fail_step)

    # ── 第 1 天：**首日**失败运行 → 引用如实为空（不得编一个，`G-03`） ──
    fail_step["on"] = True
    first = daily_run.run_daily(code_root, date(2026, 9, 15))
    assert first.blocked is True and first.degraded is True
    first_check = [r for r in read_records(code_root, "tasks") if r.get("check_record")][0]
    assert first_check["status"] == "failed"
    assert first_check["last_valid_result_ref"] is None, first_check
    assert first_check["output_refs"] == [], first_check

    # ── 第 2 天：成功运行 ──
    fail_step["on"] = False
    ok = daily_run.run_daily(code_root, _RUN_DAY)
    assert ok.blocked is False and ok.degraded is False
    ok_row = [r for r in read_records(code_root, "tasks") if r.get("check_record")][-1]
    ok_id = ok_row["check_record"]["check_id"]
    assert ok_row["status"] == "done", ok_row
    assert ok_row["last_valid_result_ref"] is None, ok_row
    assert ok_row["output_refs"] == [f"obj-step{n}" for n in range(1, 9)], ok_row

    # ── 第 3 天：再一次失败运行 → **必须**保留上一次成功运行的引用 ──
    #    ★ 用**不同运行日**：降级标记的幂等键是 `degrade::<date>::<scope>`，
    #      同日复用会命中幂等、不落新标记（那会掩盖本用例要看的字段）。
    fail_step["on"] = True
    bad = daily_run.run_daily(code_root, date(2026, 9, 17))
    assert bad.blocked is True and bad.degraded is True
    bad_row = [r for r in read_records(code_root, "tasks") if r.get("check_record")][-1]
    assert bad_row["status"] == "failed", bad_row
    assert bad_row["last_valid_result_ref"] == ok_id, (
        "失败运行**必须**保留上一次成功运行的 check_id（Ch8 §E.2）——\n"
        f"实得 {bad_row['last_valid_result_ref']!r}，期望 {ok_id!r}"
    )
    assert bad_row["output_refs"] == [], bad_row

    # ── ③ 跨模块口径一致：`degrade.mark_degraded()` 写的标记行指向**同一个** check_id ──
    marks = _degraded_marks(code_root)
    assert marks[-1]["last_valid_result_ref"] == ok_id, marks
    assert bad.last_valid_result_ref == ok_id, bad.last_valid_result_ref
