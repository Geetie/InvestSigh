#!/usr/bin/env python3
"""`build.py` —— 第 7 步产物 `views/`（**三个阅读入口**）的构建机制。

```
python system/scripts/views/build.py <code_root> [--run-date YYYY-MM-DD]
                                    [--scope full] [--generated-at ISO] [--check]
```

输入：`facts/*.jsonl`（真源）+ `derived/*.jsonl` + `state.json`（编排器的运行游标）
输出：`views/{chain_map,company_pages,daily_page_<日期>}.json`

★ 本模块承接自**会话内脚本**（`.workbuddy/seed/build_views.py`，`gitignore` 内、从不进版本库）。
  内化时做了三件事，每件都是"把会话里的一次性动作变成机器可判定的规则"：

**① 叙事内容移出代码（内容 → 真源/清单，机制 → 版本库）**
  原脚本把三类**结论性文字**写死在代码里，其中一部分**根本不是真源里的数**：

  | 字段 | 原脚本 | 现机制 |
  |---|---|---|
  | `run_summary.blocked` / `.gaps` | 写死 `True` / `8` | 读 `state.json` 的运行游标（**真实**取值）；取不到则**如实为 `null`**，不臆造 |
  | `run_summary.changed` / `.signals_emitted` | 写死 | 读最新 `check_record`（真源） |
  | `reviews_separated.*` | 写死三段文字 | 读三层 `eval_result` 的 `error_axis` / `error_axis_note` |
  | `data_gaps` | 写死 3 条 | **派生**：计算层缺口（`derived/compute_gaps.jsonl`）+ 传导可达性 + 空表归因 + **清单声明的**研究缺口 |
  | `stale_or_delayed_data` | 写死 | 由 `prices` 的 `occurred_at` / `delayed` 派生 |
  | `next_verification_nodes` | 取基线 `expiry_review` | 取**当前建议**的 `review_date`（"该建议的复查日"才是这个字段的语义） |

  ⇒ 判据：**本模块不出现任何具体日期、公司名、数字字面量**（除了枚举/图例的中文名）。
    凡会随真源变化的值，一律算出来。

**② 修 `B-7`：`current_recommendation` 沿 `supersedes` 链取末节点**
  原实现 `if (r.get("recorded_seq") or 0) > cur.get(...)` —— 真实数据里 NVIDIA 两行的
  `recorded_seq` **都是 1**，`>` 从不成立 ⇒ 取到**文件里第一条** = `rec-sec-nvda-2026-08-03`
  （v1、`buy`、依据是**已实现收益**）⇒ **已被评审推翻的旧建议被当"当前建议"渲染**，
  而同页"反证"却取自取代它的那条（`pending`）⇒ **同页不同源、读者看到"买入 + 三条反证"**。
  ⇒ 改为 `rules.current_recommendation_row()`（`supersedes` 链的**末节点**），
    并把被取代的行**具名列出**（`superseded_recommendations`）—— 不删、不静默丢弃
    （追加式不可变真源，`Ch9 §3.4.2`；`N10.3-14`：删掉等于把失败记录洗掉）。

**③ 复用唯一真源**：版本选择 / 业务键 / 取代关系都取自 `scripts.decision.rules`（`G-06`），
  本模块**不重写**第二份 —— 三处各写一份正是本仓最高频的漂移源（症状恒为**假红**）。

★ 硬约束：产物必须过 `scripts/views/neutrality_check.py` 的四条
  （`P-10` 展示层中立 / `N3.2-05` 未研究 ≠ 中性）。`--check` 在写盘后**就地**跑一遍。

★ 接线边界（如实登记，**不是**"忘了接"）：本机制对应 `rules/pipeline.yaml` 的**第 7 步**
  `publish_recommendations`（`produces: [views, snapshots]`），而该步 `implemented_in_first_version:
  false`（第八章交付，首版**只注册 hook**）。⇒ 本模块**只提供机制 + 可复跑 CLI**，
  **不**自行注册 `publish_hook`（那是 Ch8 的裁定，且 `run_daily` 仅在 `changed and not blocked`
  时调用该 hook，当下条件不成立）。**是否现在注册 hook 属需求方裁定**，已登记在
  `reports/unimplemented_by_design_inventory.md`。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from schema.store import read_records  # noqa: E402
from scripts.decision.rules import (  # noqa: E402
    current_recommendation_multihead,
    current_recommendation_row,
    latest_version_row,
    recommendation_business_key,
)

VIEWS_DIRNAME = "views"
"""产物目录（相对 `code_root`）。"""

CHAIN_MAP_FILE = "chain_map.json"
COMPANY_PAGES_FILE = "company_pages.json"
DAILY_PAGE_TEMPLATE = "daily_page_{run_date}.json"

STUDY_DEPTH_LEGEND: dict[str, str] = {
    "position_listed": "位置收录（尚未研究）",
    "relations_verified": "关系已核验",
    "baseline_done": "研究基线完成",
    "tracking": "持续跟踪",
}
"""四种研究深度（`Ch3 §D.1`）—— 图例文案，非数据。"""

_UNRESEARCHED = "position_listed"

#: 未研究节点的说明。★ 逐字守住 `N3.2-05`：**未研究 ≠ 中性评级 ≠ 没有投资机会**。
_STUDY_STATE_NOTES: dict[str, str] = {
    "baseline_done": "已建立研究基线",
    "tracking": "已建立研究基线，持续跟踪",
    "relations_verified": "关系已核验",
    _UNRESEARCHED: "**仅位置收录，尚未研究** —— 不是'中性评级'，也不是'没有投资机会'",
}

#: 三层复盘（`Ch10 §C.1`）与它们的展示名 —— **分开报告，不合并为单一评分**。
REVIEW_LAYERS: tuple[tuple[str, str], ...] = (
    ("research_quality", "研究质量"),
    ("forecast_quality", "预测质量"),
    ("investment_result", "投资结果"),
)
REVIEWS_NOTE = "三层**分别报告，不合并为单一评分**（`Ch10 §C.1`）。"
"""★ 这是**口径声明**（`Ch10 §C.1` 的硬要求），不是对本次运行的描述 —— 故为常量。"""

FAILED_TASK_KINDS: tuple[tuple[str, str], ...] = (
    ("check::", "运行回执"),
    ("degrade::", "降级标记"),
    ("eval::", "复盘任务"),
    ("research::", "研究任务"),
)
"""失败行的 `idempotency_key` 前缀 → 人话类别。

★ 为什么比"研究任务失败"更细（原脚本只列 `status == failed` 的行并称之为"研究任务失败"）：
  真实数据里的 3 条失败行**全部是**运行回执 / 降级标记，**一条研究任务都没有**。
  沿用原标题会让读者以为"有研究任务失败了"—— 那是**标题在撒谎**。
  ⇒ 按前缀分类列出（`kind`），标题由实际内容决定。
"""


class ViewBuildError(ValueError):
    """视图构建的输入不成立（缺真源结构 / 缺规则参数）—— **响亮失败**，不静默兜底。"""


# ───────────────────────────── 读真源 ─────────────────────────────


def _rows(root: Path, stem: str) -> list[dict[str, Any]]:
    return [dict(r) for r in read_records(root, stem)]


def _empty_stems(root: Path) -> list[str]:
    """`facts/` 下**本轮 0 行**的表（`G-03`：0 行 ≠ 已验证，故要显式可见）。"""
    from schema.stems import JSONL_STEMS

    out: list[str] = []
    for stem in JSONL_STEMS:
        path = root / "facts" / f"{stem}.jsonl"
        if not path.exists():
            continue
        if not path.read_text(encoding="utf-8").strip():
            out.append(str(stem))
    return out


def _state_run(root: Path, run_date: str, scope: str) -> Mapping[str, Any] | None:
    """`state.json` 里该次运行的游标（编排器自报的 `blocked` / `gaps` 等）。

    ★ 这是 `blocked` / `gaps` 的**唯一真源**：它们**不在** `check_record` 里
      （`CheckRecord` 无此二字段）。原脚本把 `blocked: True, gaps: 8` 写死在代码里，
      而真源当时的实际值是 `gaps: 10` ⇒ **页面上的数字既无出处、也不对**。
    """
    path = root / "state.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ViewBuildError(f"state.json 解析失败：{exc}") from exc
    run = (data.get("runs") or {}).get(f"run_{run_date}_{scope}")
    return run if isinstance(run, Mapping) else None


def _latest_check_record(root: Path, run_date: str | None) -> Mapping[str, Any] | None:
    """最新一条 `check_record`（真源）—— `changed` / `signals_emitted` / `degraded` 的出处。"""
    best: Mapping[str, Any] | None = None
    for row in _rows(root, "tasks"):
        rec = row.get("check_record")
        if not isinstance(rec, Mapping):
            continue
        if run_date and str(rec.get("run_date") or "") != run_date:
            continue
        best = rec if best is None else max(
            (best, rec), key=lambda r: str(r.get("check_id") or "")
        )
    return best


# ─────────────────────── data_gaps：**派生**，不写死 ───────────────────────


def _compute_layer_gaps(root: Path) -> list[dict[str, Any]]:
    """计算层缺口（`derived/compute_gaps.jsonl`）—— 原样转述，不加工。"""
    path = root / "derived" / "compute_gaps.jsonl"
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)          # 坏行**响亮**（这是真源，不得静默跳过）
        out.append({
            "gap": f"计算层缺口：{row.get('derived_id') or row.get('gap_id') or '(未命名)'}",
            "detail": str(row.get("reason") or row.get("note") or "") or "（未给原因）",
            "blocked_steps": list(row.get("blocked_steps") or []),
            "source": "derived/compute_gaps.jsonl",
        })
    return out


def _declared_research_gaps(root: Path) -> list[dict[str, Any]]:
    """**清单声明**的研究缺口 —— `tasks` 表里 `idempotency_key` 以 `research::` 开头的行。

    ★ 为什么走这一条而不是写死在构建器里：缺口是**研究结论**（"我们因为 X 所以没能断言 Y"），
      属**内容** ⇒ 归清单（`scripts/ingest/research_ingest.py` 的 `tasks` 表已能加载/导出它）。
      构建器只负责**读出来渲染**。这样缺口也跟着真源一起被清空/重放，不会变成"删不掉的旧叙事"。
    """
    out: list[dict[str, Any]] = []
    for row in _rows(root, "tasks"):
        key = str(row.get("idempotency_key") or "")
        if not key.startswith("research::"):
            continue
        ctx = row.get("parent_context") or {}
        out.append({
            "gap": str(ctx.get("title") or key[len("research::"):]),
            "detail": str(ctx.get("detail") or "") or "（未给说明）",
            "blocked_steps": list(ctx.get("blocked_steps") or []),
            "source": f"facts/tasks.jsonl#{key}",
        })
    return out


def _transmission_depth(root: Path, relations: Sequence[Mapping[str, Any]]) -> int:
    """从**已建基线的公司**出发，沿 `relations` 的**有向**最长可达跳数（防环）。

    ★ **必须有向**：传导的语义是"上游变动 → 下游影响"（`Ch7 §C`），边是
      `subject_id → object_id`。若按无向图算，`A 依赖 B` 会同时被读成"B 依赖 A"，
      可达面被系统性放大 ⇒ 判据把**不存在的传导路径**算成存在。
    """
    adj: dict[str, set[str]] = {}
    for r in relations:
        a, b = str(r.get("subject_id") or ""), str(r.get("object_id") or "")
        if a and b:
            adj.setdefault(a, set()).add(b)          # 有向：只从 subject 走向 object
    starts = [c["company_id"] for c in _rows(root, "companies")
              if c.get("research_depth") in ("baseline_done", "tracking")]
    best = 0
    for s in starts:
        seen, frontier, depth = {s}, {s}, 0
        while frontier:
            nxt: set[str] = set()
            for node in frontier:
                nxt |= adj.get(str(node), set()) - seen
            if not nxt:
                break
            seen |= nxt
            frontier = nxt
            depth += 1
        best = max(best, depth)
    return best


def _derived_coverage_gaps(
    root: Path, relations: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """**能算出来的**缺口：传导可达性 + 空表归因（含冻结参数状态）。

    ★ 为什么这两条可以做而"上游供应商未点名"不能：前者是**图的可达性**与**表是否有行**，
      纯机械；后者是对**披露文本是否充分**的判断，属研究结论 ⇒ 归清单（见 `_declared_research_gaps`）。
    """
    out: list[dict[str, Any]] = []

    depth = _transmission_depth(root, relations)
    if depth < 2:
        out.append({
            "gap": "传导路径在库内不足 2 跳",
            "detail": f"从已建基线的公司出发，`relations` 上最长的**有向**可达为 **{depth}** 跳"
                      f"（共 {len(relations)} 条边）—— 2 跳及以上在库内不存在，"
                      "故'某供应商的需求如何经二级环节传导'这类问题无法回答。",
            "blocked_steps": ["第 5 步（多跳传导）"],
            "source": "facts/relations.jsonl（有向可达性派生）",
        })

    for stem in _empty_stems(root):
        blocked = _EMPTY_STEM_BLOCKED_STEPS.get(stem)
        out.append({
            "gap": f"`facts/{stem}.jsonl` 本轮 0 行",
            "detail": "该表 0 行 ⇒ 依赖它的判断只能如实答'缺口'（`G-03`：0 行 ≠ 已验证）。"
                      + _freeze_note_for(root, _EMPTY_STEM_FREEZE_PARAM.get(stem)),
            "blocked_steps": [blocked] if blocked else [],
            "source": f"facts/{stem}.jsonl（空表扫描）",
        })
    return out


#: 空表 → 它主要卡在哪一步（**只列能给出确切步骤的**；无把握就不写，`G-03`）。
_EMPTY_STEM_BLOCKED_STEPS: dict[str, str] = {
    "expectations": "第 6 步（价格隐含要求 / 反向估值）",
    "events": "第 2 步（事件触发）",
    "dependency_edges": "第 5 步（撤回追踪 `T12`）",
    "implied_requirements": "第 6 步（价格隐含要求）",
}

#: 空表 → 它缺的是哪个冻结参数（**只在确有关联时写**，否则不猜）。
_EMPTY_STEM_FREEZE_PARAM: dict[str, str] = {
    "expectations": "p05",   # 收益预测方法（含折现算法）
    "benchmarks": "p01",     # 基准身份
}


def _freeze_note_for(root: Path, param_id: str | None) -> str:
    """给空表补一句**有出处**的归因：该表缺的冻结参数当前取值来源是什么。

    ★ 只经 `config.freeze.get_param()` 这个公开入口读（`G-06` 唯一真源），
      **不在本模块**解释冻结语义。参数 id 写错 ⇒ `UnknownParamError` **向上抛**
      （那是代码错误，不得被吞成"没有关联参数"）。
    """
    if not param_id:
        return ""
    from config.freeze import get_param

    res = get_param(param_id, root)
    return (f" 关联的冻结参数 `rules/freeze.yaml::{res.param_id}`（`{res.param}`）"
            f"当前 `freeze_status={res.freeze_status}`、取值来源 `{res.value_source}`。")


def derive_data_gaps(root: Path, relations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """合并三类缺口：计算层（原样转述）+ 派生（可达性 / 空表）+ 清单声明。"""
    return (
        _compute_layer_gaps(root)
        + _derived_coverage_gaps(root, relations)
        + _declared_research_gaps(root)
    )


# ─────────────────────── run_summary / reviews：**派生** ───────────────────────


def derive_run_summary(root: Path, run_date: str, scope: str) -> dict[str, Any]:
    """本轮运行读数 —— 优先 `state.json`（编排器自报），回退 `check_record`（真源）。

    ★ 两个来源**覆盖面不同**，必须如实标出用了哪个（`source` 字段）：
      · `state.json`：有 `blocked` / `gaps`（**唯一**出处），但它是**运行态**、不在版本库；
      · `check_record`：在真源、进版本库，但**没有** `blocked` / `gaps`。
      ⇒ 取不到就**如实 `null`**，绝不臆造（原脚本写死 `gaps: 8`，真源实为 10）。
    """
    state = _state_run(root, run_date, scope)
    check = _latest_check_record(root, run_date)

    def pick(key: str) -> Any:
        if state is not None and key in state:
            return state[key]
        if check is not None and key in check:
            return check[key]
        return None

    blocked, gaps = pick("blocked"), None
    if state is not None and state.get("gaps") is not None:
        gaps = len(state["gaps"])
    signals, changed, degraded = pick("signals_emitted"), pick("changed"), pick("degraded")
    sources = []
    if state is not None:
        sources.append(f"state.json::run_{run_date}_{scope}")
    if check is not None:
        sources.append(f"check_record::{check.get('check_id')}")

    note = (
        f"读数来源：{'、'.join(sources) if sources else '**无**（本轮既无 state.json 也无 check_record）'}。"
    )
    if blocked is None or gaps is None:
        note += " ★ `blocked` / `gaps` 本行**取不到**（`check_record` 无此二字段，"
        note += "而 `state.json` 不在版本库）⇒ 如实为空，**不臆造**。"
    if changed is False and signals == 0:
        note += " ★ 无变化日产出 0 条新信号 = **正确状态**（`Ch1 §D.3` 反 KPI）。"
    elif changed is False and isinstance(signals, int) and signals > 0:
        note += " ★★ 无变化日却产出信号 ⇒ 命中 `G1-02①`（`Ch1 §D.3`）。"
    return {
        "changed": changed, "signals_emitted": signals, "degraded": degraded,
        "blocked": blocked, "gaps": gaps, "note": note,
    }


def derive_reviews_separated(root: Path) -> dict[str, Any]:
    """三层复盘 —— 从 `facts/tasks.jsonl` 的三条 `eval_result` 行**派生**（`Ch10 §C.1`）。

    每层取该层**最新一条**（同层可能因修订有多行，`_latest_version_row` 的同一纪律：
    按 `recorded_seq` 取水位最大者 —— 这里用 `task_id` 的字典序不成立，故显式比 `recorded_seq`）。
    """
    rows = [r for r in _rows(root, "tasks") if isinstance(r.get("eval_result"), Mapping)]
    out: dict[str, Any] = {}
    missing: list[str] = []
    for layer, _cn in REVIEW_LAYERS:
        same = [r for r in rows if str((r["eval_result"] or {}).get("eval_layer")) == layer]
        if not same:
            missing.append(layer)
            out[layer] = None
            continue
        latest = max(same, key=lambda r: int(r.get("recorded_seq") or 0))
        ev = latest["eval_result"]
        axes = list(ev.get("error_axis") or [])
        text = str(ev.get("error_axis_note") or "").strip()
        out[layer] = {"error_axis": axes, "note": text or f"错误方向：{axes or '—'}"}
    out["note"] = REVIEWS_NOTE
    if missing:
        out["missing_layers"] = missing
        out["note"] += f" ★ 本轮缺 {missing} 层的复盘记录（如实为空，不得用文字凑）。"
    return out


# ─────────────────────── 时效 / 未完成 / 失败：派生 ───────────────────────


def derive_stale_or_delayed(root: Path) -> list[dict[str, Any]]:
    """行情时效 —— 由 `prices` 的 `occurred_at` / `delayed` 派生（原脚本写死"延迟 1 日"）。"""
    prices = _rows(root, "prices")
    if not prices:
        return [{"kind": "行情时效", "detail": "`facts/prices.jsonl` 本轮 0 行 ⇒ 无行情可谈时效",
                 "as_of": None, "delayed": None}]
    days = sorted(str(p.get("occurred_at") or "")[:10] for p in prices if p.get("occurred_at"))
    delayed_flags = {bool(p.get("delayed")) for p in prices}
    return [{
        "kind": "行情时效",
        "detail": f"{len(prices)} 条价格快照（{len({p.get('security_id') for p in prices})} 只证券），"
                  f"区间 {days[0]}..{days[-1]}；"
                  f"真源 `delayed` 标记：{'**全部为真**' if delayed_flags == {True} else '全部为假' if delayed_flags == {False} else '真伪混合'}",
        "as_of": days[-1],
        "delayed": True if delayed_flags == {True} else False if delayed_flags == {False} else None,
    }]


def derive_unfinished_verification(root: Path, limit: int = 5) -> list[dict[str, Any]]:
    """未完成核验 —— 按主张的 `status` 计数（不写死数字）。"""
    claims = _rows(root, "claims")
    pending = [c for c in claims if str(c.get("status")) == "pending_verification"]
    if not pending:
        return []
    return [{
        "kind": "未完成核验",
        "detail": "`claim.status=pending_verification`（尚未做交叉验证 / 采纳判定）",
        "refs": [str(c.get("claim_id")) for c in pending[:limit]],
        "count": len(pending),
    }]


def derive_failed_tasks(root: Path) -> list[dict[str, Any]]:
    """失败任务 —— 按 `idempotency_key` 前缀分类（原脚本一律称"研究任务失败"，与事实不符）。"""
    out: list[dict[str, Any]] = []
    for row in _rows(root, "tasks"):
        if str(row.get("status")) != "failed":
            continue
        key = str(row.get("idempotency_key") or "")
        kind = next((cn for pre, cn in FAILED_TASK_KINDS if key.startswith(pre)), "其他")
        out.append({
            "task_id": str(row.get("task_id")), "kind": kind,
            "status": "failed",
            "last_valid_result_ref": row.get("last_valid_result_ref"),
        })
    return out


# ─────────────────────── 1) chain_map ───────────────────────


def build_chain_map(
    root: Path, run_date: str, generated_at: str
) -> dict[str, Any]:
    nodes = _rows(root, "industry_nodes")
    bpos = _rows(root, "business_positions")
    rels = _rows(root, "relations")
    flows = _rows(root, "relation_flows")
    impacts = _rows(root, "impacts")
    events = _rows(root, "events")
    claims = {str(c.get("claim_id")): c for c in _rows(root, "claims")}

    node_payload: list[dict[str, Any]] = []
    for n in nodes:
        owners = [b for b in bpos if b.get("node_id") == n.get("node_id")]
        depth = str(owners[0].get("research_depth")) if owners else _UNRESEARCHED
        node_payload.append({
            "node_id": n["node_id"], "node_name": n["node_name"],
            "taxonomy_version": n.get("taxonomy_version"),
            "position_bucket": str(n["node_id"]).split("__")[0].replace("node_", ""),
            "research_depth": depth,
            "updated_at": generated_at,
            # ★ 派生：该节点上有没有"已建基线的公司"。无 owners ⇒ 无变化（未研究谈不上变化）。
            "changed_since_last_run": depth in ("baseline_done", "tracking"),
            "company_refs": [b["company_id"] for b in owners],
            "study_state_note": _STUDY_STATE_NOTES.get(depth, _STUDY_STATE_NOTES[_UNRESEARCHED]),
        })

    edges = [{
        "relation_id": r["relation_id"], "type": r["relation_type"],
        "from": r["subject_id"], "to": r["object_id"],
        "from_kind": r["subject_kind"], "to_kind": r["object_kind"],
        "stage": r["relation_progress_stage"],
        "valid_from": r["valid_from"], "valid_to": r.get("valid_to"),
        "economic_exposure": r["economic_exposure"],
        "exposure_disclosure": r["economic_exposure_disclosure"],
        "commitment_kind": r["commitment_kind"],
        "evidence_claim_ids": r["evidence_claim_ids"],
        "evidence_sources": [
            {"claim_id": c, "source_id": claims[c]["source_id"],
             "locator": claims[c]["locator"], "tier": claims[c]["tier"]}
            for c in r["evidence_claim_ids"] if c in claims
        ],
        "flows": [{"flow_kind": f["flow_kind"], "from": f["from_ref"], "to": f["to_ref"]}
                  for f in flows if f.get("relation_id") == r.get("relation_id")],
    } for r in rels]

    event_paths = [{
        "event_id": e["event_id"], "event_type": e["event_type"],
        "company_ids": e["company_ids"], "occurred_at": e["occurred_at"],
        "root_source_id": e["root_source_id"],
        "paths": [{
            "impact_id": i["impact_id"], "affected_company_id": i["affected_company_id"],
            "variable": i["impact_variable"], "direction": i["direction"],
            "magnitude": i["magnitude"], "magnitude_disclosure": i["magnitude_disclosure"],
            "conditions": i["conditions"], "counter_forces": i["counter_forces"],
            "time_lag": i["time_lag"], "falsifiers": i["falsifiers"],
            "path_kind": i["path_kind"], "evidence_claim_ids": i["evidence_claim_ids"],
            # ★ 派生：**有成立条件且引用了证据**才算"依据充足"（缺一即不足，`Ch7 §J`）。
            "evidence_sufficient": bool(i["conditions"]) and bool(i["evidence_claim_ids"]),
        } for i in impacts if i.get("event_id") == e.get("event_id")],
    } for e in events]

    return {
        "view": "chain_map", "generated_at": generated_at, "run_date": run_date,
        "scope": "能源 → 应用的位置全景（位置收录 / 关系已核验 / 研究基线完成 / 持续跟踪）",
        "study_depth_legend": dict(STUDY_DEPTH_LEGEND),
        # ★ `neutrality_check` ①：默认排序**不得**按买卖/紧迫倾斜（故用位置而不是建议）。
        "default_sort": [{"field": "position_bucket", "order": "asc"},
                         {"field": "node_id", "order": "asc"}],
        # ★ `neutrality_check` ③：反证与缺口与支持证据**同等可见**，不默认折叠。
        "evidence_panel": {"collapsed_default": False,
                           "note": "反证、缺口与支持证据同等可见，不默认折叠"},
        "nodes": node_payload,
        "relations": edges,
        "event_paths": event_paths,
        "unfinished_visible": [n["node_id"] for n in node_payload
                               if n["research_depth"] == _UNRESEARCHED],
        "data_gaps": derive_data_gaps(root, rels),
    }


# ─────────────────────── 2) company_pages ───────────────────────


def _current_recommendations(
    recs: Sequence[Mapping[str, Any]]
) -> tuple[dict[tuple[str, str], Mapping[str, Any]], list[dict[str, Any]]]:
    """按业务键分组 → 取当前建议；同时返回**被取代的行**（具名，不静默丢弃）。"""
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    order: list[tuple[str, str]] = []
    for row in recs:
        key = recommendation_business_key(row)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(row)

    current: dict[tuple[str, str], Mapping[str, Any]] = {}
    superseded: list[dict[str, Any]] = []
    for key in order:
        rows = grouped[key]
        pick = current_recommendation_row(rows)
        current[key] = pick
        heads = current_recommendation_multihead(rows)
        if heads:
            superseded.append({
                "kind": "supersedes_chain_multihead",
                "business_key": f"{key[0]}@{key[1]}",
                "heads": list(heads),
                "note": "该结论的 `supersedes` 链有多个末节点 ⇒ '当前版本'本身不唯一，须人工理清",
            })
        for row in rows:
            if row is pick:
                continue
            superseded.append({
                "recommendation_id": str(row.get("recommendation_id")),
                "business_key": f"{key[0]}@{key[1]}",
                "replaced_by": str(pick.get("recommendation_id")),
                "action": str(row.get("action")), "status": str(row.get("status")),
            })
    return current, superseded


def _recommendation_view(rec: Mapping[str, Any]) -> dict[str, Any]:
    """一条建议 → 视图块。★ 只放**该行自己**的字段（同页同源，不跨行拼）。"""
    return {
        "recommendation_id": rec["recommendation_id"],
        "action": rec["action"], "status": rec["status"],
        "horizon": rec["horizon"], "start_date": rec["start_date"],
        "review_date": rec.get("review_date"),
        "rule_version": rec["rule_version"], "change_reason": rec["change_reason"],
        "falsifiers": rec["falsifiers"], "evidence_gaps": rec["evidence_gaps"],
        "verification_conditions": rec["verification_conditions"],
        "assumptions": rec["assumptions"], "supersedes": rec.get("supersedes"),
        "opportunity_types": rec.get("opportunity_types", []),
    }


def build_company_pages(root: Path, run_date: str, generated_at: str) -> dict[str, Any]:
    companies = _rows(root, "companies")
    baselines = _rows(root, "baselines")
    bpos = _rows(root, "business_positions")
    recs = _rows(root, "recommendations")
    drivers = {str(d.get("driver_id")): d for d in _rows(root, "drivers")}
    claims = {str(c.get("claim_id")): c for c in _rows(root, "claims")}
    sources = {str(s.get("source_id")): s for s in _rows(root, "sources")}

    # 基线：同公司多版本取**水位最大**者（与 `latest_version_row` 同一纪律）
    cur_base: dict[str, Mapping[str, Any]] = {}
    for b in baselines:
        cid = str(b.get("company_id"))
        cur_base[cid] = b if cid not in cur_base else max(
            (cur_base[cid], b), key=lambda r: int(r.get("version") or 0)
        )

    current_recs, superseded = _current_recommendations(recs)
    by_company: dict[str, Mapping[str, Any]] = {}
    for (_sec, _sd), row in current_recs.items():
        cid = str(row.get("company_id") or "")
        by_company[cid] = row          # 每家公司一条当前建议（业务键含 security+start_date）

    pages: list[dict[str, Any]] = []
    for co in companies:
        cid = str(co["company_id"])
        b = cur_base.get(cid)
        rec = by_company.get(cid)
        ev: list[dict[str, Any]] = []
        for c_ in (b or {}).get("evidence_claim_ids") or []:
            cl = claims.get(str(c_))
            if cl:
                ev.append({
                    "claim_id": c_, "quote": (cl.get("impact_capability") or {}).get("quote"),
                    "locator": cl["locator"], "tier": cl["tier"], "source_id": cl["source_id"],
                    "source_entry": (sources.get(str(cl["source_id"])) or {}).get("public_entry"),
                })
        pages.append({
            "company_id": cid, "legal_name": co["legal_name"],
            "research_depth": co["research_depth"],
            "industry_position": [
                {"node_id": p["node_id"], "role": p["inclusion_reason"],
                 "evidence_strength": p["evidence_strength"], "raw_source": p["raw_source"]}
                for p in bpos if p.get("company_id") == cid
            ],
            "growth_drivers": [
                {"driver_id": d, "source_class": drivers[str(d)]["source_class"],
                 "realization_stage": drivers[str(d)]["realization_stage"],
                 "timeline": drivers[str(d)]["timeline"], "confidence": drivers[str(d)]["confidence"],
                 "dependencies": drivers[str(d)]["dependencies"],
                 "assumptions": drivers[str(d)]["assumptions"]}
                for d in ((b or {}).get("driver_refs") or []) if str(d) in drivers
            ],
            "growth_certainty": (b or {}).get("value_state_refs", {}),
            "moat": (b or {}).get("moat", []),
            # ★★ `B-7` 修复点：取 `supersedes` 链的**末节点**，不是文件里第一条。
            "current_recommendation": _recommendation_view(rec) if rec else None,
            "change_this_run": {
                "baseline_version": (b or {}).get("version"),
                "version_kind": (b or {}).get("version_kind"),
                "increment": (b or {}).get("increment"),
            },
            "expanded": {
                "full_baseline": b,
                "business_mechanism": (b or {}).get("business_mechanism"),
                "financial_and_valuation": {
                    "valuation_inputs": (b or {}).get("valuation_inputs"),
                    "valuation": (b or {}).get("valuation"),
                    "historical_numeric_claims": (b or {}).get("historical_numeric_claims"),
                },
                "raw_evidence": ev,
                "counter_evidence": {
                    # ★ 这里放的是**基线**的反证（另一个对象），故显式标出来源，
                    #   避免读者把"基线反证"当成"当前建议的反证"（原实现没标 ⇒ 同页混淆）。
                    "source_row": str((b or {}).get("baseline_id") or ""),
                    "falsifiers": (b or {}).get("falsifiers", []),
                    "unmet_conditions": (b or {}).get("unmet_conditions", []),
                    "note": "反证与支持证据同等可见（不默认折叠）；本块取自**研究基线**，"
                            "与 `current_recommendation.falsifiers`（建议自身）是两个对象",
                },
                "history_versions": [
                    {"baseline_id": x.get("baseline_id"),
                     "version": x["version"], "conclusion_version": x.get("conclusion_version"),
                     "version_kind": x.get("version_kind"), "prev_version_id": x.get("prev_version_id")}
                    for x in baselines if x.get("company_id") == cid
                ],
                "study_state": ("研究基线完成" if b else
                                "**尚未完成研究** —— 本页只显示产业位置与研究缺口，"
                                "不代表'中性'或'没有投资机会'"),
            },
        })

    payload: dict[str, Any] = {
        "view": "company_pages", "generated_at": generated_at, "run_date": run_date,
        "default_sort": [{"field": "research_depth", "order": "asc"},
                         {"field": "company_id", "order": "asc"}],
        "evidence_panel": {"collapsed_default": False},
        "companies": pages,
        # ★ 被取代的建议**具名保留**（`Ch9 §3.4.2` / `N10.3-14`：删掉等于把失败记录洗掉）。
        "superseded_recommendations": superseded,
        "data_gaps": derive_data_gaps(root, _rows(root, "relations")),
    }
    unfinished = [c["company_id"] for c in pages if not cur_base.get(str(c["company_id"]))]
    if unfinished:
        payload["unfinished_research_companies"] = unfinished
    return payload


# ─────────────────────── 3) daily_page ───────────────────────


def _recommendation_change_rows(
    recs: Sequence[Mapping[str, Any]], run_date: str
) -> list[dict[str, Any]]:
    """本期建议变化：**本轮首次出现**的建议 + 它取代的那条（取代链两端都可见）。

    ★ 原实现用 `r["recommendation_id"] == "rec-sec-nvda-2026-08-03"` 这个**写死的 id**
      把一条特定记录捞进来 —— 换个日期/公司就失效且没人会察觉。现改为**纯派生**。
    """
    index = {str(r.get("recommendation_id")): r for r in recs}
    out: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for r in recs:
        if not str(r.get("first_seen_at") or "").startswith(run_date):
            continue

        def _add(row: Mapping[str, Any]) -> None:
            rid = str(row.get("recommendation_id"))
            if rid not in seen:
                seen.add(rid)
                out.append(row)

        _add(r)
        target = str(r.get("supersedes") or "")
        if target and target in index:
            _add(index[target])
    return [{
        "company_id": r.get("company_id"), "recommendation_id": r["recommendation_id"],
        "action": r["action"], "status": r["status"],
        "change_reason": r["change_reason"], "supersedes": r.get("supersedes"),
        "falsifiers": r["falsifiers"],
        "first_seen_at": r.get("first_seen_at"),
    } for r in out]


def build_daily_page(root: Path, run_date: str, scope: str, generated_at: str) -> dict[str, Any]:
    events = _rows(root, "events")
    impacts = _rows(root, "impacts")
    recs = _rows(root, "recommendations")
    sources = {str(s.get("source_id")): s for s in _rows(root, "sources")}
    current_recs, _superseded = _current_recommendations(recs)

    return {
        "view": "daily_page", "date": run_date, "generated_at": generated_at,
        # ★ `neutrality_check` ①：默认按**事件时间**排（不按建议倾向）。
        "default_sort": [{"field": "event_time", "order": "desc"},
                         {"field": "company_id", "order": "asc"}],
        "evidence_panel": {"collapsed_default": False},
        "important_information": [{
            "event_id": e["event_id"], "event_time": e["occurred_at"],
            "type": e["event_type"], "companies": e["company_ids"],
            "source": (sources.get(str(e["root_source_id"])) or {}).get("public_entry"),
            "source_tier": (sources.get(str(e["root_source_id"])) or {}).get("tier"),
        } for e in events],
        # ★ 说明放在**区块级**（原实现从 `important_information[0]` 取 ⇒ 事件为空时渲染器崩）。
        "important_information_note": (
            "事件发现时间 = 系统首次获得（`first_seen_at`）；**先显示发现，完成分析后才更新判断**。"
        ),
        "affected_companies": [{
            "impact_id": i["impact_id"], "company_id": i["affected_company_id"],
            "variable": i["impact_variable"], "direction": i["direction"],
            "magnitude": i["magnitude"], "conditions": i["conditions"],
            "counter_forces": i["counter_forces"], "time_lag": i["time_lag"],
            "falsifiers": i["falsifiers"],
        } for i in impacts],
        "recommendation_changes": _recommendation_change_rows(recs, run_date),
        "next_verification_nodes": [
            {"company_id": r.get("company_id"), "recommendation_id": r["recommendation_id"],
             "review_date": r.get("review_date")}
            for _k, r in sorted(current_recs.items())
        ],
        "unfinished_verification": derive_unfinished_verification(root),
        "stale_or_delayed_data": derive_stale_or_delayed(root),
        "failed_tasks": derive_failed_tasks(root),
        "run_summary": derive_run_summary(root, run_date, scope),
        "reviews_separated": derive_reviews_separated(root),
        "data_gaps": derive_data_gaps(root, _rows(root, "relations")),
    }


# ─────────────────────── 入口 ───────────────────────


def build_views(
    root: str | Path, run_date: str, *, scope: str = "full",
    generated_at: str | None = None,
) -> dict[str, dict[str, Any]]:
    """构建三份视图负载（**不写盘**）。键 = 文件名，值 = 负载。"""
    root_path = Path(root)
    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    return {
        CHAIN_MAP_FILE: build_chain_map(root_path, run_date, stamp),
        COMPANY_PAGES_FILE: build_company_pages(root_path, run_date, stamp),
        DAILY_PAGE_TEMPLATE.format(run_date=run_date): build_daily_page(
            root_path, run_date, scope, stamp
        ),
    }


def write_views(
    root: str | Path, run_date: str, *, scope: str = "full",
    generated_at: str | None = None,
) -> list[Path]:
    """构建并写盘；返回写出的文件路径（按传入顺序：图谱 / 公司页 / 每日页）。"""
    out_dir = Path(root) / VIEWS_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, payload in build_views(
        root, run_date, scope=scope, generated_at=generated_at
    ).items():
        path = out_dir / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


def check_neutrality(root: str | Path) -> list[str]:
    """就地跑展示层中立守卫，返回违例文本（空 = 通过）。"""
    from scripts._common import CheckReport, run_checker  # noqa: F401  (文档性导入)

    from scripts.views.neutrality_check import check as neutrality_check

    report = neutrality_check(Path(root))
    return [v.render() for v in report.violations]


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    positional = [a for a in args if not a.startswith("--")]
    root = Path(positional[0]).resolve() if positional else _ROOT

    def _opt(name: str, default: str | None = None) -> str | None:
        if name in args:
            idx = args.index(name)
            if idx + 1 < len(args):
                return args[idx + 1]
        return default

    run_date = _opt("--run-date")
    if not run_date:
        # ★ 不猜日期：取真源里最新一条 check_record 的 run_date（**有出处**），
        #   无 check_record 则响亮失败（`G-03`：不得拿系统当天日期冒充"运行日"）。
        latest = _latest_check_record(root, None)
        run_date = str((latest or {}).get("run_date") or "")
        if not run_date:
            print("[views] 无法确定运行日：无 --run-date 且真源里没有 check_record。"
                  "请显式给出 --run-date。", file=sys.stderr)
            return 2
        print(f"[views] 未给 --run-date，取最新 check_record 的 run_date = {run_date}")

    scope = _opt("--scope", "full") or "full"
    paths = write_views(root, run_date, scope=scope, generated_at=_opt("--generated-at"))
    for p in paths:
        print(f"[views] {p.relative_to(root)}  {p.stat().st_size} bytes")

    if "--check" in args:
        problems = check_neutrality(root)
        if problems:
            print("[views] neutrality_check 违例：", file=sys.stderr)
            for p in problems:
                print("  -", p, file=sys.stderr)
            return 1
        print("[views] neutrality_check 通过（0 violations）")
    return 0


if __name__ == "__main__":  # pragma: no cover - 手工入口
    raise SystemExit(main())
