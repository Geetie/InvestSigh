"""`tests/unit/test_views.py` —— 三个阅读入口的**构建机制**与**渲染**的机器绑定。

覆盖 `scripts/views/build.py` + `scripts/views/render.py`。这两支原本是**会话内脚本**
（`.workbuddy/seed/`，`gitignore` 内、从不进版本库）—— 本文件是它们"内化"的验收面。

七组断言，每组都对应一个"会话脚本会犯、而机制必须不犯"的错：

| # | 断言 | 对应缺陷 |
|---|---|---|
| 1 | `current_recommendation` 取 `supersedes` 链**末节点**（顺序无关） | `B-7`：原实现按 `recorded_seq` 比大小，而真实数据该值全为 1 ⇒ 取到**已被推翻的 v1** |
| 2 | 被取代的行**具名列出**，不静默丢弃 | `Ch9 §3.4.2` / `N10.3-14`（删掉 = 洗掉失败记录） |
| 3 | `run_summary` 从真源派生；取不到 ⇒ `None` | 原实现**写死** `blocked: True, gaps: 8`，真源实为 `10` |
| 4 | `data_gaps` 由空表 + `research::` 行**算出** | 原实现写死 3 条叙事 |
| 5 | 产物过 `neutrality_check` 四条，且该守卫**确实会拦**（反向对照） | `P-10` / `N3.2-05` |
| 6 | ★ **源码里不得再出现日期/公司名字面量**（AST 扫非 docstring 字符串） | 防"叙事被重新写回代码"（本次内化的**目的**） |
| 7 | 渲染器**不读真源**、缺 views 时**响亮失败** | 渲染与取数分离（否则两边会各算一遍） |
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from scripts.views.build import (
    CHAIN_MAP_FILE,
    COMPANY_PAGES_FILE,
    DAILY_PAGE_TEMPLATE,
    build_chain_map,
    build_company_pages,
    build_daily_page,
    build_views,
    write_views,
)
from scripts.views.neutrality_check import check_view_config
from scripts.views.render import md_daily, render_readable, write_readable

from conftest import SYSTEM_ROOT

RUN_DATE = "2026-01-02"
STAMP = "2026-01-02T00:00:00+00:00"
DAILY = DAILY_PAGE_TEMPLATE.format(run_date=RUN_DATE)


# ─────────────────────────── 夹具 ───────────────────────────


def _write_jsonl(root: Path, stem: str, rows: list[dict]) -> None:
    """直接写 JSONL（`read_records` 不校验模型，故夹具只保证**字段名与真源一致**）。"""
    path = root / "facts" / f"{stem}.jsonl"
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def _rec(rid: str, *, action: str, status: str, supersedes: str | None = None, **over: object) -> dict:
    """一条建议行；默认与另一条**数值水位完全相同**（`(1, 1)`）—— 这正是 `B-7` 的现场。"""
    row = {
        "recommendation_id": rid, "company_id": "co-a", "security_id": "sec-a",
        "start_date": "2026-01-01", "horizon": "2q", "action": action, "status": status,
        "version": 1, "recorded_seq": 1, "supersedes": supersedes,
        "review_date": "2026-03-01", "rule_version": "v1", "change_reason": "test",
        "falsifiers": [], "evidence_gaps": [], "verification_conditions": [],
        "assumptions": [], "first_seen_at": f"{RUN_DATE}T00:00:00Z",
    }
    row.update(over)
    return row


def _seed_minimal(root: Path, recs: list[dict]) -> None:
    _write_jsonl(root, "companies", [
        {"company_id": "co-a", "legal_name": "Co A", "research_depth": "baseline_done"}
    ])
    _write_jsonl(root, "recommendations", recs)


# ─────────────────── 1. `supersedes` 链：B-7 回归 ───────────────────


@pytest.mark.parametrize("order", [("old", "new"), ("new", "old")])
def test_current_recommendation_follows_supersedes_chain(code_root: Path, order: tuple) -> None:
    """★ `B-7` 回归：**文件顺序无关** —— 当前建议是取代链的末节点。

    两条行的 `(version, recorded_seq)` **完全相同**（`(1, 1)`），故"按数值取最大"这一族实现
    只能退化为"取文件里第一条或最后一条"。本用例**两种物理顺序都跑**，
    从而证明选中的是**语义**（`supersedes`），不是位置。
    """
    old = _rec("rec-old", action="buy", status="active", falsifiers=[])
    new = _rec("rec-new", action="pending", status="uncertain", supersedes="rec-old",
               falsifiers=["证伪条件 1", "证伪条件 2"])
    by_name = {"old": old, "new": new}
    recs = [by_name[n] for n in order]
    # 前提（防夹具漂移）：两条水位必须相同，否则本用例失去区分力
    assert (old["version"], old["recorded_seq"]) == (new["version"], new["recorded_seq"])
    _seed_minimal(code_root, recs)

    page = build_company_pages(code_root, RUN_DATE, STAMP)
    cur = page["companies"][0]["current_recommendation"]
    assert cur["recommendation_id"] == "rec-new", (
        f"物理顺序 {order} 下取到了 {cur['recommendation_id']!r} —— "
        "说明选择仍然取决于行的位置而不是 `supersedes` 关系"
    )
    assert cur["action"] == "pending" and cur["status"] == "uncertain"
    # ★ 同一页的反证必须来自**同一条建议行**（原缺陷：action 取自旧行、反证取自新行）
    assert cur["falsifiers"] == ["证伪条件 1", "证伪条件 2"]


def test_superseded_row_is_named_not_dropped(code_root: Path) -> None:
    """被取代的行**具名保留**（不删、不静默）。"""
    _seed_minimal(code_root, [
        _rec("rec-old", action="buy", status="active"),
        _rec("rec-new", action="pending", status="uncertain", supersedes="rec-old"),
    ])
    page = build_company_pages(code_root, RUN_DATE, STAMP)
    sup = page["superseded_recommendations"]
    assert [s["recommendation_id"] for s in sup] == ["rec-old"]
    assert sup[0]["replaced_by"] == "rec-new"
    assert sup[0]["business_key"] == "sec-a@2026-01-01"


def test_company_without_recommendation_is_explicit(code_root: Path) -> None:
    """没有任何建议的公司 ⇒ `current_recommendation is None`（**不编一条**）。"""
    _write_jsonl(code_root, "companies", [
        {"company_id": "co-z", "legal_name": "Co Z", "research_depth": "position_listed"}
    ])
    page = build_company_pages(code_root, RUN_DATE, STAMP)
    assert page["companies"][0]["current_recommendation"] is None
    assert page["unfinished_research_companies"] == ["co-z"]


# ─────────────────── 2. `run_summary` 派生，不臆造 ───────────────────


def test_run_summary_derives_from_state_and_check_record(code_root: Path) -> None:
    """`blocked`/`gaps` 取自 `state.json`（**唯一**出处）；`changed`/`signals` 取自 `check_record`。

    ★ 判别力：原脚本把这两个值写成 `True` / `8` 的字面量。本用例注入 **3** 条缺口，
      并要求读数**等于 3** —— 任何写死实现都会在此变红。
    """
    # ★ 夹具**故意**只给 state.json 那两项 `check_record` 拿不到的键（`blocked` / `gaps`），
    #   其余（`changed` / `signals_emitted` / `degraded`）留给 `check_record` —— 这样一次跑
    #   同时验证"优先 state"与"缺键回退 check_record"两条路径。
    (code_root / "state.json").write_text(json.dumps({
        "runs": {f"run_{RUN_DATE}_full": {
            "run_date": RUN_DATE, "scope": "full", "blocked": True,
            "gaps": ["g1", "g2", "g3"],
        }}
    }), encoding="utf-8")
    _write_jsonl(code_root, "tasks", [{
        "task_id": "task_check", "idempotency_key": "check::c1", "status": "failed",
        "output_refs": [],
        "check_record": {"check_id": "check_x", "run_date": RUN_DATE, "scope": "full",
                         "changed": False, "signals_emitted": 0, "degraded": True},
    }])
    rs = build_daily_page(code_root, RUN_DATE, "full", STAMP)["run_summary"]
    assert rs["gaps"] == 3, rs          # ← 写死 8 的实现必红
    assert rs["blocked"] is True
    # 回退路径：这三个键 `state.json` 没给 ⇒ 取自 `check_record`（证明两个来源真的都在用）
    assert rs["changed"] is False and rs["signals_emitted"] == 0
    assert rs["degraded"] is True
    assert "state.json" in rs["note"] and "check_record" in rs["note"]


def test_run_summary_does_not_fabricate_when_state_missing(code_root: Path) -> None:
    """`state.json` 不在 ⇒ `blocked`/`gaps` **如实为 None**，note 明说取不到。

    ★ `check_record` **没有** `blocked` / `gaps` 字段（`CheckRecord` 模型如此），
      故"没有 state.json"时这两个数**不存在**。此处断言不得退化成 `False` / `0`
      （把"不知道"渲染成"没有"是同一类撒谎）。
    """
    _write_jsonl(code_root, "tasks", [{
        "task_id": "task_check", "idempotency_key": "check::c1", "status": "done",
        "output_refs": ["x"],
        "check_record": {"check_id": "check_x", "run_date": RUN_DATE, "scope": "full",
                         "changed": True, "signals_emitted": 1, "degraded": False},
    }])
    rs = build_daily_page(code_root, RUN_DATE, "full", STAMP)["run_summary"]
    assert rs["blocked"] is None and rs["gaps"] is None, rs
    assert rs["changed"] is True and rs["signals_emitted"] == 1
    assert "取不到" in rs["note"]


def test_run_summary_flags_signal_on_unchanged_day(code_root: Path) -> None:
    """反向对照（`G-05`）：无变化日却产信号 ⇒ note 必须点出命中 `G1-02①`。

    若不加这一臂，上面的"无变化 0 信号 = 正确状态"那句就无法区分
    "判据在工作"与"这句话恒被打印"。
    """
    _write_jsonl(code_root, "tasks", [{
        "task_id": "task_check", "idempotency_key": "check::c1", "status": "failed",
        "output_refs": [],
        "check_record": {"check_id": "check_x", "run_date": RUN_DATE, "scope": "full",
                         "changed": False, "signals_emitted": 2, "degraded": False},
    }])
    rs = build_daily_page(code_root, RUN_DATE, "full", STAMP)["run_summary"]
    assert "G1-02" in rs["note"], rs


def test_reviews_separated_reads_three_eval_rows(code_root: Path) -> None:
    """三层复盘从 `eval_result` 行**派生**（不再写死三段文字）。"""
    _write_jsonl(code_root, "tasks", [
        {"task_id": f"task_eval_{layer}", "idempotency_key": f"eval::{layer}",
         "status": "done", "output_refs": ["b1"], "recorded_seq": i,
         "eval_result": {"eval_layer": layer, "error_axis": [f"axis-{i}"],
                         "error_axis_note": f"note-{layer}"}}
        for i, layer in enumerate(("research_quality", "forecast_quality", "investment_result"), 1)
    ])
    rv = build_daily_page(code_root, RUN_DATE, "full", STAMP)["reviews_separated"]
    for layer in ("research_quality", "forecast_quality", "investment_result"):
        assert rv[layer]["note"] == f"note-{layer}"
        assert rv[layer]["error_axis"]
    assert "不合并为单一评分" in rv["note"]


def test_missing_review_layer_is_declared_not_padded(code_root: Path) -> None:
    """缺某层复盘 ⇒ 如实为 `None` + 具名进 `missing_layers`（不拿文字凑）。"""
    rv = build_daily_page(code_root, RUN_DATE, "full", STAMP)["reviews_separated"]
    assert rv["research_quality"] is None
    assert set(rv["missing_layers"]) == {
        "research_quality", "forecast_quality", "investment_result"
    }


# ─────────────────── 3. `data_gaps` 派生 ───────────────────


def test_empty_facts_tables_produce_gaps(code_root: Path) -> None:
    """空表 ⇒ 派生出缺口（原实现写死 3 条固定叙事，与真源无关）。"""
    gaps = build_chain_map(code_root, RUN_DATE, STAMP)["data_gaps"]
    assert gaps, "空真源下必须报出空表 —— 否则'没数据'会渲染成'没问题'"
    joined = " ".join(g["detail"] for g in gaps)
    assert "0 行" in joined
    # 每条缺口都必须给出处（否则读者无法回查）
    assert all(g.get("source") for g in gaps), gaps


def test_declared_research_gap_is_read_from_tasks(code_root: Path) -> None:
    """清单声明的缺口（`tasks` 里 `research::` 行）被读出并带 `blocked_steps`。"""
    _write_jsonl(code_root, "tasks", [{
        "task_id": "task_gap_x", "idempotency_key": "research::gap-x", "status": "queued",
        "output_refs": [],
        "parent_context": {"title": "上游供应商未点名", "detail": "披露被截断",
                           "blocked_steps": ["第 3 步"]},
    }])
    gaps = build_chain_map(code_root, RUN_DATE, STAMP)["data_gaps"]
    hit = [g for g in gaps if g["gap"] == "上游供应商未点名"]
    assert len(hit) == 1, gaps
    assert hit[0]["blocked_steps"] == ["第 3 步"]
    assert "research::gap-x" in hit[0]["source"]


def test_transmission_depth_gap_is_directed(code_root: Path) -> None:
    """可达性按**有向**边算：`a→b` 不得被读成 `b→a`（否则会算出不存在的传导路径）。"""
    _write_jsonl(code_root, "companies", [
        {"company_id": "a", "legal_name": "A", "research_depth": "baseline_done"},
        {"company_id": "b", "legal_name": "B", "research_depth": "baseline_done"},
    ])
    # 只有 b→a 一条边。从 a 出发**无法**到达任何地方 ⇒ 最长可达 = 0 ⇒ 报"不足 2 跳"
    _write_jsonl(code_root, "relations", [{
        "relation_id": "r1", "relation_type": "supply", "subject_id": "b", "object_id": "a",
        "subject_kind": "company", "object_kind": "company", "relation_progress_stage": "s",
        "valid_from": "2026-01-01", "economic_exposure": "x",
        "economic_exposure_disclosure": "undisclosed", "commitment_kind": "k",
        "evidence_claim_ids": [],
    }])
    gaps = build_chain_map(code_root, RUN_DATE, STAMP)["data_gaps"]
    assert any("不足 2 跳" in g["gap"] for g in gaps), gaps


# ─────────────────── 4. 中立性（含反向对照） ───────────────────


def test_all_three_views_pass_neutrality_check(code_root: Path) -> None:
    """三份产物**逐份**过 `neutrality_check` 的四条判据（`P-10` / `N3.2-05`）。"""
    _seed_minimal(code_root, [_rec("rec-a", action="buy", status="active")])
    for name, payload in build_views(code_root, RUN_DATE, generated_at=STAMP).items():
        vio = check_view_config(payload)
        assert not vio, f"{name}: {[v.render() for v in vio]}"


@pytest.mark.parametrize("mutate,expect_rule", [
    (lambda p: p["default_sort"].__setitem__(0, {"field": "action", "order": "desc"}), "P-10"),
    (lambda p: p.__setitem__("urgency_color", True), "P-10"),
    (lambda p: p.__setitem__("red_green_bias", True), "P-10"),
    (lambda p: p["evidence_panel"].__setitem__("collapsed_default", True), "P-10"),
    (lambda p: p.__setitem__("render_mappings", [
        {"from": "未完成研究", "to": "中性"}]),
     "N3.2-05"),
])
def test_neutrality_check_actually_rejects(code_root: Path, mutate, expect_rule: str) -> None:
    """★ 反向对照（`G-05`）：上面那条"全过"必须**可被推翻**。

    否则"三份都过"可能只是守卫没在看 —— 本组逐条注入五种隐性引导形态，逐条要求判红。
    """
    payload = build_chain_map(code_root, RUN_DATE, STAMP)
    mutate(payload)
    vio = check_view_config(payload)
    assert any(v.rule == expect_rule for v in vio), [v.render() for v in vio]


# ─────────────────── 5. 渲染：不读真源、响亮失败 ───────────────────


def test_render_reads_only_views_not_truth_source(code_root: Path) -> None:
    """渲染器**只读 `views/*.json`**：真源为空也必须渲染成功（证明它没去取数）。"""
    write_views(code_root, RUN_DATE, generated_at=STAMP)
    out = render_readable(code_root, RUN_DATE)
    assert set(out) >= {"阅读入口_1_产业图谱.md", "阅读入口_2_公司研究页.md", "dashboard.html"}
    assert "阅读入口_3_每日研究页_" + RUN_DATE + ".md" in out
    assert "dashboard" not in out["阅读入口_1_产业图谱.md"]


def test_render_empty_events_does_not_crash(code_root: Path) -> None:
    """★ 空事件**不得**让渲染崩（原实现从 `important_information[0]` 取说明 ⇒ 空列表即 IndexError）。"""
    write_views(code_root, RUN_DATE, generated_at=STAMP)
    daily = json.loads((code_root / "views" / DAILY).read_text(encoding="utf-8"))
    assert daily["important_information"] == []        # 前提：确实是空的
    text = md_daily(daily)                             # 不得抛
    assert "本轮真源里没有事件" in text


def test_render_without_views_is_loud(code_root: Path) -> None:
    """缺 views 产物 ⇒ **响亮失败并指路**（不自行取数兜底 —— 那会与构建器各算一遍）。"""
    with pytest.raises(FileNotFoundError, match="build.py"):
        render_readable(code_root, RUN_DATE)


def test_write_readable_writes_three_md_plus_dashboard(code_root: Path) -> None:
    """写盘落位正确：3 份 MD 进 `reports/`、dashboard 进 `views/`。"""
    write_views(code_root, RUN_DATE, generated_at=STAMP)
    written = write_readable(code_root, RUN_DATE)
    names = {p.name for p in written}
    assert names == {"阅读入口_1_产业图谱.md", "阅读入口_2_公司研究页.md",
                     f"阅读入口_3_每日研究页_{RUN_DATE}.md", "dashboard.html"}
    for p in written:
        assert p.parent.name == ("views" if p.name == "dashboard.html" else "reports")
        assert p.stat().st_size > 0


def test_write_views_writes_three_json(code_root: Path) -> None:
    """构建产物落位：三份 JSON 在 `views/`，且是合法 JSON。"""
    written = write_views(code_root, RUN_DATE, generated_at=STAMP)
    assert [p.name for p in written] == [CHAIN_MAP_FILE, COMPANY_PAGES_FILE, DAILY]
    for p in written:
        assert isinstance(json.loads(p.read_text(encoding="utf-8")), dict)


# ─────────────────── 6. ★ 元断言：叙事不得被写回代码 ───────────────────


def _non_docstring_strings(path: Path) -> list[tuple[int, str]]:
    """模块里**非 docstring** 的字符串字面量（含 f-string 的静态片段）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    doc_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_nodes.add(id(body[0].value))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in doc_nodes:
            out.append((node.lineno, node.value))
    return out


#: ★ 用**前后否定环视**而不是 `\b`：`2026-09-17T08:47:00Z` 里日期后紧跟 `T`（都是词字符），
#:   `\d{4}-\d{2}-\d{2}\b` **不匹配** ⇒ 恰好漏掉会话脚本里最典型的那一行
#:   （`NOW = "2026-09-17T08:47:00Z"`）。本处由 `test_meta_assertion_itself_discriminates`
#:   当场抓出并改正 —— 那条反向对照的价值就在于此。
_NARRATIVE_PATTERNS = (
    (r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", "具体日期"),
    (r"(?<![0-9A-Za-z])\d{4}Q[1-4](?![0-9])", "具体财季"),
    (r"\b(?:sec|company|baseline|rec|dv)-[a-z0-9]", "具体对象 id"),
    (r"\b(?:NVDA|AGIX|TSMC|MSFT|AMD|nvidia|agix)\b", "具体公司名"),
)


@pytest.mark.parametrize("target", ["build.py", "render.py"])
def test_no_narrative_literals_outside_docstrings(target: str) -> None:
    """★★ **元断言**：`views/` 两支的**非 docstring 字符串**里不得出现具体日期 / 对象 id / 公司名。

    ★ 为什么这是本次内化的**核心判据**（而不是可有可无的洁癖）：
      会话脚本把它们**写死在代码里**（`blocked: True, gaps: 8`、`data_gaps` 三条叙事、
      `recommendation_id == "rec-sec-nvda-2026-08-03"`、`NOW = "2026-09-17T08:47:00Z"`），
      于是换一天/换一家公司，页面会**安静地显示旧事实**——没有任何判据会变红。
      内化的目的就是让"会随真源变化的值"全部**算出来**。本断言把这件事变成**机器可查**的：
      谁再把一个日期或公司名写回代码，这条立刻红。

    ★ 例外只给 docstring（它解释**为什么**，必须能举例）—— 故本断言按 AST 精确排除 docstring，
      而不是靠"整文件 grep"（那会把解释性文字一起误杀，逼人写模糊的话，`G-27` 同族）。
    """
    import re

    path = SYSTEM_ROOT / "scripts" / "views" / target
    bad: list[str] = []
    for lineno, text in _non_docstring_strings(path):
        for pattern, what in _NARRATIVE_PATTERNS:
            m = re.search(pattern, text)
            if m:
                bad.append(f"{target}:{lineno} 含{what} {m.group(0)!r} —— {text[:60]!r}")
    assert not bad, (
        "`views/` 的构建/渲染里出现了**叙事字面量**（会随真源变化的值必须算出来）：\n  "
        + "\n  ".join(bad)
    )


def test_meta_assertion_itself_discriminates() -> None:
    """反向对照：把一条 `NOW = "2026-09-17T..."` 塞进临时模块 ⇒ 上面那条扫描必须抓到。

    没有这一臂，`test_no_narrative_literals_outside_docstrings` 可能因为**正则写错**
    而永远通过（那正是本仓最忌的"看起来在守、实际空转"）。
    """
    import re
    import tempfile

    src = '"""docstring 里可以有 2026-09-17 与 NVDA（本断言只看非 docstring）"""\n' \
          'NOW = "2026-09-17T08:47:00Z"\n'
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "fake.py"
        p.write_text(src, encoding="utf-8")
        hits = [
            (n, t) for n, t in _non_docstring_strings(p)
            if any(re.search(pat, t) for pat, _ in _NARRATIVE_PATTERNS)
        ]
    assert hits, "docstring 被排除、模块级字面量必须命中"
    assert all("docstring 里可以有" not in t for _, t in hits)
