#!/usr/bin/env python3
"""`render.py` —— 把三个阅读入口的 **JSON** 翻成**人话 MD** + 自包含 **HTML**。

```
python system/scripts/views/render.py <code_root> [--run-date YYYY-MM-DD]
```

输入：`views/{chain_map,company_pages,daily_page_<日期>}.json`（由 `views/build.py` 产出）
输出：
  `reports/阅读入口_1_产业图谱.md`
  `reports/阅读入口_2_公司研究页.md`
  `reports/阅读入口_3_每日研究页_<日期>.md`
  `views/dashboard.html`（自包含，双击可看，无外部依赖）

★ 本模块承接自**会话内脚本**（`.workbuddy/seed/build_readable_views.py`）。内化时保持"渲染"与"取数"
  **严格分离**：本模块**不读真源**、**不做任何判断**，只把 `build.py` 的产物换个呈现形式。
  ⇒ 结构上不可能出现"MD 里的数与 JSON 里的数不一致"（改数只需改一处）。

★ 两条内容纪律：

**① 不确定的东西不美化。** 未研究 ⇒ 逐字写"尚未研究，不等于中性、不等于没有机会"
  （`N3.2-05`）；缺字段 ⇒ 写"（未给）"而不是留空或补默认值。

**② 被取代的建议要看得见。** `superseded_recommendations` 单独一节列出
  （`Ch9 §3.4.2` / `N10.3-14`：删掉等于把失败记录洗掉）——
  原会话脚本把这段**整个丢了**（渲染时只取 `current_recommendation`）。
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

from scripts.views.build import (  # noqa: E402
    CHAIN_MAP_FILE,
    COMPANY_PAGES_FILE,
    DAILY_PAGE_TEMPLATE,
    REVIEW_LAYERS,
    STUDY_DEPTH_LEGEND,
    VIEWS_DIRNAME,
    write_views,
)

REPORTS_DIRNAME = "reports"
CHAIN_MD = "阅读入口_1_产业图谱.md"
PAGES_MD = "阅读入口_2_公司研究页.md"
DAILY_MD_TEMPLATE = "阅读入口_3_每日研究页_{run_date}.md"
DASHBOARD = "dashboard.html"

# ── 展示名（**纯文案映射**；值域由 schema 枚举决定，改枚举须同步此表） ──
DEPTH_CN: dict[str, str] = dict(STUDY_DEPTH_LEGEND)
ACTION_CN = {"buy": "买入", "sell": "卖出", "pending": "待判断", "maintain": "维持原判断"}
STATUS_CN = {
    "active": "有效", "uncertain": "不确定（已研究但不足以定论）",
    "confident_underperform": "确定跑不赢", "boundary_unresolved": "未决边界",
}
BUCKET_CN = {
    "power_and_facilities": "电力与配套设施",
    "chip_architecture_and_design": "芯片架构与设计",
    "manufacturing_and_memory": "制造与存储",
    "compute_chip_and_system": "算力芯片与系统",
    "cluster_network_and_interconnect": "集群网络与互连",
    "datacenter_and_cloud": "数据中心与云",
    "foundation_model": "基础模型",
    "software_platform_and_application": "软件平台与应用",
}
BUCKET_ORDER = list(BUCKET_CN)
DEPTH_ORDER = ["position_listed", "relations_verified", "baseline_done", "tracking"]

_EMPTY_DASH = "—"
_MISSING = "**（未给）**"


def _join(items: Sequence[Any] | None, sep: str = "；") -> str:
    """把列表拼成一行；空 ⇒ `—`（**不留白**，留白会被读成"没有反证"）。"""
    vals = [str(x) for x in (items or []) if str(x).strip()]
    return sep.join(vals) if vals else _EMPTY_DASH


def _cn(table: Mapping[str, str], key: Any) -> str:
    """查展示名；未登记 ⇒ 原样返回**并加标记**（不得静默显示裸英文码）。"""
    k = str(key)
    return table.get(k, f"{k}（未登记展示名）")


def _markdown_escape(text: Any) -> str:
    """表格单元格里的换行会断表 ⇒ 折成空格（不改其他字符）。"""
    return " ".join(str(text if text is not None else "").split())


# ═════════════════════════ ① 产业图谱 ═════════════════════════


def md_chain(chain: Mapping[str, Any]) -> str:
    L: list[str] = []
    A = L.append
    A("# 阅读入口 ①　产业图谱（人话版）\n")
    A(f"> 生成时间 {chain['generated_at']}　运行日 {chain['run_date']}\n")
    A("> 数据来源：`system/views/chain_map.json`（本文件是它的中文转述，**不改任何结论**）\n")
    A("---\n")
    A("## 这张图回答什么\n")
    A("从**能源**一路到**应用**，每个位置上有谁、我们**研究到了哪一步**、**今天有没有变化**。"
      "点一家公司能看它周边的局部关系；选一个事件能看**有证据的传导路径和成立条件**。\n")
    A("**四种研究深度**（这是本图最重要的信息）：\n")
    A("| 深度 | 含义 | 本轮节点数 |")
    A("|---|---|---|")
    nodes = chain.get("nodes") or []
    for k, v in DEPTH_CN.items():
        A(f"| {v} | {chain.get('study_depth_legend', {}).get(k, '')} "
          f"| {sum(1 for x in nodes if x.get('research_depth') == k)} |")
    A("")
    A("★ **没研究 ≠ 中性评级，更不是「没有投资机会」**。本图对未完成的节点一律直说"
      "「仅位置收录，尚未研究」。\n")
    A("---\n")
    A("## 全景：按产业位置分组\n")
    for b in BUCKET_ORDER:
        ns = [n for n in nodes if n.get("position_bucket") == b]
        if not ns:
            continue
        done = sum(1 for n in ns if n.get("research_depth") == "baseline_done")
        A(f"### {BUCKET_CN[b]}　（{len(ns)} 个节点，其中 {done} 个已完成研究基线）\n")
        A("| 节点 | 研究深度 | 今天有没有变化 | 我们做了什么 |")
        A("|---|---|---|---|")
        for n in ns:
            chg = "有" if n.get("changed_since_last_run") else "无"
            A(f"| **{n['node_name']}**<br>`{n['node_id']}` "
              f"| {_cn(DEPTH_CN, n.get('research_depth'))} | {chg} | {n.get('study_state_note', '')} |")
        A("")
    # ★ 未在册的 bucket（真源出现新 bucket 而文案表没跟上）⇒ 如实报出，不静默丢节点
    unknown = sorted({n.get("position_bucket") for n in nodes} - set(BUCKET_ORDER))
    if unknown:
        A(f"> ★ 有 {len(unknown)} 个产业位置桶**未在本文件的展示名表里登记**："
          f"{'、'.join('`' + str(u) + '`' for u in unknown)} ⇒ 上面未列出，"
          "须补 `render.py::BUCKET_CN`（不静默丢节点）。\n")
    A("---\n")
    A("## 关系边：我们**核验过**的关系（每条都有出处）\n")
    A("| 关系 | 阶段 | 经济暴露 | 承诺性质 | 证据出处 |")
    A("|---|---|---|---|---|")
    for r in chain.get("relations") or []:
        ev = "；".join(
            f"{str(e['claim_id']).split('-', 2)[-1]}（{e['tier']}，{e['locator']}）"
            for e in r.get("evidence_sources") or []
        ) or _EMPTY_DASH
        A(f"| {r['from']} → {r['to']}<br>_{r['type']}_ | `{r['stage']}` "
          f"| {r['economic_exposure']}<br>（{r['exposure_disclosure']}） "
          f"| {r['commitment_kind']} | {ev} |")
    A("")
    A("**同一对公司的两条边是分开的**（方向可能相反）——产品流、资金流、需求信号各自成边：\n")
    for r in chain.get("relations") or []:
        if r.get("flows"):
            A(f"- **{r['from']} ⇄ {r['to']}**：" + "；".join(
                f"{f['flow_kind']}（{f['from']} → {f['to']}）" for f in r["flows"]))
    A("")
    A("---\n")
    A("## 选一个事件，看有证据的传导路径\n")
    if not chain.get("event_paths"):
        A("_本轮真源里没有事件 ⇒ 本图无传导路径可看（**不是**\"传导未发生\"）。_\n")
    for e in chain.get("event_paths") or []:
        A(f"### {e['event_id']}　（{e['event_type']}，{'、'.join(e.get('company_ids') or [])}）\n")
        A(f"- 事件发生时间：`{e['occurred_at']}`　根来源：`{e['root_source_id']}`")
        A("")
        for p in e.get("paths") or []:
            ok = "**证据充足**" if p.get("evidence_sufficient") else "**依据不足**"
            A(f"**→ {p['affected_company_id']}　（{p['path_kind']}，{ok}）**\n")
            A(f"- 影响变量：{p['variable']}　方向：**{p['direction']}**")
            A(f"- 幅度/范围：{p['magnitude']}（{p['magnitude_disclosure']}）")
            A(f"- 成立条件：{_join(p.get('conditions')) or '—（缺条件即不成立）'}")
            A(f"- 反向力量：{_join(p.get('counter_forces'))}")
            A(f"- 体现时间：{p['time_lag']}")
            A(f"- **反证**：{_join(p.get('falsifiers'))}")
            A("")
    A("---\n")
    A("## 本图**自己承认**的数据缺口\n")
    gaps = chain.get("data_gaps") or []
    if not gaps:
        A("- _本轮未登记缺口（`data_gaps` 为空 ≠ 没有缺口，只表示没有**登记**）。_\n")
    for g in gaps:
        blocked = "、".join(g.get("blocked_steps") or []) or "（未标步骤）"
        A(f"- **{g['gap']}**　卡在：{blocked}\n  {g['detail']}\n  <sub>出处：{g.get('source', '')}</sub>")
    A("")
    A(f"\n**未研究节点清单**（{len(chain.get('unfinished_visible') or [])} 个）："
      + ("、".join(f"`{str(x).split('__')[-1]}`" for x in chain.get("unfinished_visible") or [])
         or _EMPTY_DASH))
    return "\n".join(L)


# ═════════════════════════ ② 公司研究页 ═════════════════════════


def md_pages(pages: Mapping[str, Any]) -> str:
    L: list[str] = []
    A = L.append
    A("# 阅读入口 ②　公司研究页（人话版）\n")
    A(f"> 生成时间 {pages['generated_at']}　运行日 {pages['run_date']}\n")
    A("> 数据来源：`system/views/company_pages.json`\n")
    A("---\n")
    A("## 怎么读这页\n")
    A("**首屏六项**（结论简洁）：产业位置 → 增长动力 → 增长确定性 → 护城河 → 当前建议 → 本次变化。\n")
    A("**展开层**（研究保持深度）：完整底稿、原始证据（带出处与定位）、财务与估值、**反证**、历史版本。\n")
    A("★ 反证与支持证据**同等可见**，不默认折叠。\n")
    A("★ **「当前建议」取的是 `supersedes` 链的末节点** —— 若某条建议被后续评审取代，"
      "此处显示的是**取代它的那条**，被取代的行列在本页末尾「已取代的建议」一节。\n")
    A("---\n")
    companies = pages.get("companies") or []
    done = [c for c in companies if c.get("growth_drivers") or c.get("moat")]
    todo = [c for c in companies if c not in done]

    for c in done:
        e = c.get("expanded") or {}
        fin = e.get("financial_and_valuation") or {}
        A(f"\n# {c['legal_name']}　`{c['company_id']}`\n")
        A(f"**研究深度**：{_cn(DEPTH_CN, c.get('research_depth'))}\n")
        A("## 一、产业位置\n")
        if c.get("industry_position"):
            A("| 产业节点 | 为什么收录 | 出处 | 证据强度 |")
            A("|---|---|---|---|")
            for p in c["industry_position"]:
                A(f"| `{p['node_id']}` | {p['role']} | {p['raw_source']} | {p['evidence_strength']} |")
        else:
            A("_尚未建立产业位置记录。_")
        A("")
        A("## 二、增长动力（每条都标了「已经发生」还是「还靠条件」）\n")
        A("| 驱动 | 来源类别 | 兑现阶段 | 期限 | 置信 | 依赖条件 |")
        A("|---|---|---|---|---|---|")
        for d in c.get("growth_drivers") or []:
            A(f"| `{d['driver_id']}` | {d['source_class']} | **{d['realization_stage']}** "
              f"| {d['timeline']} | {d['confidence']} | {_join(d.get('dependencies'))} |")
        A("")
        for d in c.get("growth_drivers") or []:
            if d.get("assumptions"):
                A(f"- `{d['driver_id']}` 支撑的经营假设：{_join(d['assumptions'])}")
        A("")
        A("## 三、增长确定性（**状态与趋势分开记**）\n")
        vs = c.get("growth_certainty") or {}
        A(f"- 增长动力状态：**{vs.get('growth_momentum_state', 'tbd')}**")
        A(f"- 兑现确定性状态：**{vs.get('certainty_state', 'tbd')}**")
        A(f"- 护城河**水平**：**{vs.get('moat_level', 'tbd')}**　／　"
          f"护城河**趋势**：**{vs.get('moat_state', 'tbd')}**")
        A("\n> 四种状态可以同时并存且方向不同（例如「增长动力增强、确定性减弱、护城河不变」）。\n")
        A("## 四、护城河\n")
        if not c.get("moat"):
            A("_尚无护城河条目。_")
        for m in c.get("moat") or []:
            A(f"### `{m['moat_id']}`\n")
            A(f"- 优势机制：{m['mechanism']}")
            A("- 保护对象：" + "；".join(
                f"{o['object']}（强度 {o['strength']}）" for o in m.get("protected_objects") or []))
            A(f"- 来源分类：**{m['origin_class']}**"
              + ("　★ **供需周期类，不得当持久护城河**"
                 if m.get("origin_class") == "supply_demand_cycle" else ""))
            A(f"- 跨代际是否存活：{m['cross_generation_survival']}　"
              f"跨代际竞争力：{m['cross_generation_competitiveness']}")
            for s in m.get("real_substitutes") or []:
                A(f"- 真实替代方案：触发条件={s['switch_trigger']}；切换成本={s['switching_cost']}；"
                  f"**实际切换证据**={_join(s.get('actual_switch_evidence'), sep='、')}"
                  f"{'（无）' if not s.get('actual_switch_evidence') else ''}")
            A("")
        A("## 五、财务与估值\n")
        A("**估值输入（事实 / 模型估计 / 人工设定三类分开存）**\n")
        A("| 因素 | 取值 | 来源类型 |")
        A("|---|---|---|")
        inputs = fin.get("valuation_inputs") or {}
        if not inputs:
            A(f"| {_MISSING} | — | — |")
        for k, v in inputs.items():
            A(f"| {k} | {_MISSING} | — |" if not v
              else f"| {k} | {v['value']} | `{v['input_source']}` |")
        A("")
        vv = fin.get("valuation") or {}
        A(f"- 估值方法：{vv.get('method_class', _EMPTY_DASH)}")
        A(f"- 计算底稿引用：`{vv.get('formula_ref', _EMPTY_DASH)}`")
        A(f"- 情景标签：{vv.get('scenario_tag', _EMPTY_DASH)}")
        A(f"- 价格隐含引用：{vv.get('implied_ref', _EMPTY_DASH)}")
        A(f"\n**独立判断（Agent 根据业务证据形成）**："
          f"{vv.get('independent_judgment') or '_尚未给出_ '}\n")
        A("## 六、当前建议\n")
        rec = c.get("current_recommendation")
        if rec:
            A(f"- 行动：**{_cn(ACTION_CN, rec['action'])}**　状态：{_cn(STATUS_CN, rec['status'])}")
            A(f"- 建议 ID：`{rec['recommendation_id']}`"
              f"（★ 本区块**全部**字段取自这一行）")
            A(f"- 期限：`{rec['horizon']}`　起算 {rec['start_date']}　复查 {rec.get('review_date') or _EMPTY_DASH}")
            A(f"- 规则版本：`{rec['rule_version']}`"
              + (f"　**取代** `{rec['supersedes']}`" if rec.get("supersedes") else ""))
            A(f"- 变化原因：{rec['change_reason']}")
            A("- 提前判断三要素：")
            A(f"  - 假设：{_join(rec.get('assumptions'))}")
            A(f"  - 证据缺口：{_join(rec.get('evidence_gaps'))}")
            A(f"  - 验证条件：{_join(rec.get('verification_conditions'))}")
            A(f"- **反证/证伪条件**：{_join(rec.get('falsifiers'))}")
        else:
            A("_本轮尚未形成建议——这属于「研究未完成先记缺口」，不是中性评级。_")
        A("")
        A("## 七、原始证据（带出处与定位）\n")
        A("| 主张 | 引文 | 定位 | 层级 | 来源入口 |")
        A("|---|---|---|---|---|")
        raw = e.get("raw_evidence") or []
        if not raw:
            A(f"| {_MISSING} | — | — | — | — |")
        for x in raw:
            A(f"| `{x['claim_id']}` | {_markdown_escape(x.get('quote'))} | `{x['locator']}` "
              f"| {x['tier']} | {x.get('source_entry') or _EMPTY_DASH} |")
        ce = e.get("counter_evidence") or {}
        A("\n## 八、反证与未兑现条件\n")
        A(f"> 本块取自**研究基线** `{ce.get('source_row') or _EMPTY_DASH}`"
          "（与第六节的「建议反证」是两个对象，**不要混读**）。\n")
        A(f"- 反证/证伪：{_join(ce.get('falsifiers'))}")
        A(f"- 未兑现条件：{_join(ce.get('unmet_conditions'))}")
        A("\n## 九、历史版本\n")
        A("| 基线 | 版本 | 结论版本 | 版本类型 | 上一版 |")
        A("|---|---|---|---|---|")
        for h in e.get("history_versions") or []:
            A(f"| `{h.get('baseline_id', _EMPTY_DASH)}` | v{h['version']} | {h.get('conclusion_version')} "
              f"| {h.get('version_kind')} | {h.get('prev_version_id')} |")
        A("\n---\n")

    if todo:
        A("\n# 仅在册、尚未研究的公司\n")
        A("下列公司**没有研究底稿** —— 直说「尚未研究」，不等于中性，也不等于没有机会：\n")
        A("| 公司 | 研究深度 | 收录说明 |")
        A("|---|---|---|")
        for c in todo:
            roles = [p.get("role") for p in (c.get("industry_position") or []) if p.get("role")]
            note = _join(roles) if roles else (
                "仅位置收录（无产业位置记录，也未见已核验关系）")
            A(f"| {c['legal_name']} | {_cn(DEPTH_CN, c.get('research_depth'))} | {note} |")
        A("")

    superseded = pages.get("superseded_recommendations") or []
    if superseded:
        A("\n---\n")
        A("# 已取代的建议（**保留在真源、不删除**）\n")
        A("> 追加式不可变真源（`Ch9 §3.4.2`）：一次修正**追加新行**、不原地改写；"
          "删掉旧行等于把失败记录洗掉（`N10.3-14`）。本表把被取代的行**具名列出**。\n")
        A("| 被取代的建议 | 业务键 | 取代者 | 行动 | 状态 |")
        A("|---|---|---|---|---|")
        for s in superseded:
            if s.get("kind") == "supersedes_chain_multihead":
                A(f"| **链条分叉** | `{s.get('business_key')}` | "
                  f"{'、'.join('`' + str(h) + '`' for h in s.get('heads') or [])} | — | — |")
                continue
            A(f"| `{s.get('recommendation_id')}` | `{s.get('business_key')}` "
              f"| `{s.get('replaced_by')}` | {_cn(ACTION_CN, s.get('action'))} "
              f"| {_cn(STATUS_CN, s.get('status'))} |")
        A("")
    return "\n".join(L)


# ═════════════════════════ ③ 每日研究页 ═════════════════════════


def _review_text(block: Any) -> str:
    """三层复盘的一层 → 一行文字（`None` ⇒ 如实说缺，不编）。"""
    if not isinstance(block, Mapping):
        return "**本轮该层无复盘记录**（如实为空，不得用文字凑）"
    axes = block.get("error_axis") or []
    return f"{block.get('note') or _EMPTY_DASH}　<sub>错误方向：{_join(axes) if axes else '—（本轮无）'}</sub>"


def md_daily(daily: Mapping[str, Any]) -> str:
    L: list[str] = []
    A = L.append
    A(f"# 阅读入口 ③　每日研究页　{daily['date']}\n")
    A(f"> 生成时间 {daily['generated_at']}\n"
      f"> 数据来源：`system/views/daily_page_{daily['date']}.json`\n")
    A("---\n")
    rs = daily.get("run_summary") or {}

    def tri(v: Any) -> str:
        return "**（取不到）**" if v is None else ("是" if v else "否")

    def num(v: Any) -> str:
        return "**（取不到）**" if v is None else str(v)

    A("## 今天这一轮跑成什么样\n")
    A(f"- 有变化吗：{tri(rs.get('changed'))}　新买卖信号：**{num(rs.get('signals_emitted'))}** 条")
    A(f"- 是否降级：{tri(rs.get('degraded'))}　是否阻断：{tri(rs.get('blocked'))}　"
      f"缺口：{num(rs.get('gaps'))} 条")
    A(f"- {rs.get('note', '')}\n")
    A("> ★ **每天维护判断 ≠ 每天必须产生新买卖信号**。「今天没有新信号」是正确状态。\n")
    A("---\n")
    A("## 一、重要信息（按事件发生时间）\n")
    info = daily.get("important_information") or []
    if info:
        A("| 事件 | 发生时间 | 类型 | 涉及公司 | 根来源 | 层级 |")
        A("|---|---|---|---|---|---|")
        for i in info:
            A(f"| `{i['event_id']}` | {i['event_time']} | {i['type']} "
              f"| {'、'.join(i.get('companies') or [])} | {i.get('source') or _EMPTY_DASH} "
              f"| {i.get('source_tier')} |")
    else:
        A("_本轮真源里没有事件。_")
    A(f"\n> {daily.get('important_information_note', '')}\n")
    A("## 二、受影响公司（含条件、反向力量与反证）\n")
    aff = daily.get("affected_companies") or []
    if not aff:
        A("_本轮真源里没有影响路径记录。_\n")
    for a in aff:
        A(f"**{a['company_id']}　方向：{a['direction']}**\n")
        A(f"- 影响变量：{a['variable']}　幅度：{a['magnitude']}")
        A(f"- 成立条件：{_join(a.get('conditions')) or '—（缺条件即不成立）'}")
        A(f"- 反向力量：{_join(a.get('counter_forces'))}")
        A(f"- 体现时间：{a['time_lag']}　**反证**：{_join(a.get('falsifiers'))}\n")
    A("## 三、建议变化\n")
    changes = daily.get("recommendation_changes") or []
    if not changes:
        A("_本运行日没有新增或被取代的建议。_\n")
    else:
        A("> 下表含**取代链的两端**：本轮新出现的建议 + 它明确取代的那条。\n")
        A("| 公司 | 建议 | 状态 | 变化原因 | 取代了谁 | 反证 |")
        A("|---|---|---|---|---|---|")
        for r in changes:
            A(f"| {r.get('company_id')} | **{_cn(ACTION_CN, r['action'])}** "
              f"| {_cn(STATUS_CN, r['status'])} | {r['change_reason']} "
              f"| {r.get('supersedes') or _EMPTY_DASH} | {_join(r.get('falsifiers'))} |")
    A("")
    A("## 四、下一验证节点\n")
    nxt = daily.get("next_verification_nodes") or []
    if not nxt:
        A("_尚无当前建议 ⇒ 无复查节点。_\n")
    else:
        A("| 公司 | 建议 | 复查日期 |")
        A("|---|---|---|")
        for n in nxt:
            A(f"| {n.get('company_id')} | `{n.get('recommendation_id')}` "
              f"| {n.get('review_date') or _EMPTY_DASH} |")
    A("")
    A("---\n")
    A("## 五、三类异常态（**都必须在页面上看得见**）\n")
    A("### 5.1 未完成核验\n")
    un = daily.get("unfinished_verification") or []
    if not un:
        A("- 无")
    for u in un:
        A(f"- {u['detail']}：**共 {u['count']} 条**（示例：{'、'.join(u.get('refs') or [])}）")
    A("\n### 5.2 数据失效 / 延迟\n")
    for s in daily.get("stale_or_delayed_data") or []:
        A(f"- {s['detail']}（as-of {s.get('as_of')}，延迟标记 {s.get('delayed')}）")
    A("\n### 5.3 失败的运行 / 研究任务\n")
    failed = daily.get("failed_tasks") or []
    if not failed:
        A("- 无")
    else:
        A("| 任务 | 类别 | 状态 | 保留的上次有效结果 |")
        A("|---|---|---|---|")
        for f in failed:
            A(f"| `{f['task_id']}` | {f.get('kind')} | {f['status']} "
              f"| {f.get('last_valid_result_ref') or '—（无）'} |")
    A("")
    A("---\n")
    A("## 六、三层复盘（**分开报告，不合并为单一评分**）\n")
    rv = daily.get("reviews_separated") or {}
    for layer, cn in REVIEW_LAYERS:
        A(f"- **{cn}**：{_review_text(rv.get(layer))}")
    A(f"\n> {rv.get('note', '')}\n")
    A("---\n")
    A("## 七、本页明确不做的事\n")
    A("- 不把「尚未研究的事件」包装成「已验证结论」（先显示发现，分析完成才更新判断）")
    A("- 故障时**保留上次有效结果**并显示日期与失效状态，**不覆盖为无意义空值**，"
      "**不把旧数据标成最新**")
    A("- 重复执行**不重复生成**事件或建议")
    A("- **不把被取代的建议当成「当前建议」**（本页 `current_recommendation` 一律取 "
      "`supersedes` 链的末节点）")
    return "\n".join(L)


# ═════════════════════════ ④ 可视化 HTML ═════════════════════════

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 产业链研究 · 三个阅读入口</title>
<style>
:root{--bg:#F8F7F4;--card:#fff;--ink:#1f2328;--muted:#6b7280;--line:#e6e2da;
--rust:#b4502a;--blue:#2f5d8a;--green:#1a7f4b;--red:#c0392b;--amber:#a8761c;--purple:#6b4a8f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
header{background:var(--card);border-bottom:1px solid var(--line);padding:18px 26px;position:sticky;top:0;z-index:20}
h1{margin:0 0 4px;font-size:19px;letter-spacing:.2px}
.sub{color:var(--muted);font-size:12.5px}
.tabs{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
.tab{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 15px;cursor:pointer;font-size:13px;color:var(--muted)}
.tab.on{background:var(--ink);color:#fff;border-color:var(--ink)}
main{padding:22px 26px 70px;max-width:1500px;margin:0 auto}
section{display:none}section.on{display:block}
h2{font-size:16px;margin:26px 0 10px;padding-left:9px;border-left:3px solid var(--rust)}
h3{font-size:14px;margin:18px 0 8px;color:var(--blue)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:10px}
.col-wrap{display:flex;gap:12px;overflow-x:auto;padding-bottom:8px}
.col{min-width:210px;flex:1 0 210px}
.col h4{margin:0 0 8px;font-size:12.5px;color:var(--muted);font-weight:600;letter-spacing:.4px}
.node{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:9px 11px;margin-bottom:8px;cursor:pointer;transition:.12s}
.node:hover{border-color:var(--rust);transform:translateY(-1px)}
.node .nm{font-weight:600;font-size:13px;display:flex;justify-content:space-between;align-items:center;gap:6px}
.badge{font-size:10.5px;padding:1.5px 7px;border-radius:999px;white-space:nowrap;font-weight:600}
.b0{background:#efece6;color:#7a7268}.b1{background:#e3ecf6;color:var(--blue)}
.b2{background:#e2f1e8;color:var(--green)}.b3{background:#f3ebf9;color:var(--purple)}
.dot{width:6px;height:6px;border-radius:50%;background:var(--rust);display:inline-block;margin-left:5px}
.card{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:15px 17px;margin-bottom:12px}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:#f4f1ec;font-weight:600;color:#4a453e}
code{background:#f1eee8;padding:1px 5px;border-radius:4px;font-size:11.5px;
font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.kv{display:grid;grid-template-columns:118px 1fr;gap:4px 10px;font-size:12.5px}
.kv b{color:var(--muted);font-weight:600}
.muted{color:var(--muted)}.up{color:var(--red);font-weight:600}.down{color:var(--green);font-weight:600}
.pos{color:var(--red)}.neg{color:var(--green)}.neu{color:var(--amber)}
.pill{display:inline-block;background:#f1eee8;border-radius:999px;padding:1px 8px;font-size:11px;margin:0 4px 4px 0}
.warn{background:#fdf6ec;border:1px solid #f0dfc0;border-left:3px solid var(--amber);border-radius:8px;padding:11px 14px;margin:10px 0;font-size:12.5px}
.gap{background:#fdeeec;border:1px solid #f2ccc6;border-left:3px solid var(--red);border-radius:8px;padding:11px 14px;margin:10px 0;font-size:12.5px}
details{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:8px 0;background:#fdfcfb}
summary{cursor:pointer;font-weight:600;font-size:13px}
.sel{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:14px 16px;min-height:90px}
.ev{font-size:11.5px;color:var(--muted);border-top:1px dashed var(--line);padding-top:7px;margin-top:7px}
.bar{height:7px;border-radius:4px;background:#eee;overflow:hidden;margin-top:3px}
.bar>i{display:block;height:100%;background:var(--green)}
</style></head><body>
<header>
  <h1>AI 产业链研究 · 三个阅读入口</h1>
  <div class="sub">运行日 <b>__RUN_DATE__</b>　·　数据来自 <code>system/facts/*.jsonl</code> 与 <code>system/views/*.json</code>　·　全部数字为当时读数</div>
  <div class="tabs">
    <div class="tab on" data-t="t1">① 产业图谱</div>
    <div class="tab" data-t="t2">② 公司研究页</div>
    <div class="tab" data-t="t3">③ 每日研究页</div>
  </div>
</header>
<main>
<section id="t1" class="on">
  <div class="warn"><b>怎么读：</b>四种深度 = 位置收录（尚未研究）／关系已核验／研究基线完成／持续跟踪。
  <b>没研究 ≠ 中性评级</b>，也不是"没有投资机会"。点节点看局部关系，点事件看传导路径。</div>
  <h2>研究深度总览</h2><div id="depthStats" class="grid"></div>
  <h2>全景：能源 → 应用</h2><div id="chainCols" class="col-wrap"></div>
  <h2>选中详情</h2><div id="chainSel" class="sel muted">点上面任一个节点或事件。</div>
  <h2>选事件看有证据的传导路径</h2><div id="evtList"></div>
  <h2>我们核验过的关系（每条都有出处）</h2><div id="relTable"></div>
  <h2>本图自己承认的数据缺口</h2><div id="gaps"></div>
</section>

<section id="t2">
  <div class="warn"><b>首屏六项</b>（结论简洁）：产业位置 → 增长动力 → 增长确定性 → 护城河 → 当前建议 → 本次变化。<br>
  <b>展开层</b>（研究深度）：完整底稿、原始证据、财务与估值、反证、历史版本。<b>反证不折叠。</b><br>
  <b>「当前建议」取 <code>supersedes</code> 链的末节点</b> —— 被取代的建议列在本节末尾，不删除、不静默丢弃。</div>
  <h2>公司列表</h2><div id="coList" class="grid"></div>
  <div id="coDetail" class="sel muted">点一家公司看首屏六项与展开层。</div>
  <h2>仅在册、尚未研究的公司</h2><div id="coTodo"></div>
  <h2>已取代的建议（保留在真源、不删除）</h2><div id="coSuperseded"></div>
</section>

<section id="t3">
  <div class="warn" id="dailyRun"></div>
  <h2>一、重要信息</h2><div id="dInfo"></div>
  <h2>二、受影响公司</h2><div id="dAff"></div>
  <h2>三、建议变化</h2><div id="dRec"></div>
  <h2>四、下一验证节点</h2><div id="dNext"></div>
  <h2>五、三类异常态（都必须看得见）</h2><div id="dBad"></div>
  <h2>六、三层复盘（分开报告，不合并为单一评分）</h2><div id="dRev"></div>
</section>
</main>
<script>
const D = __DATA__;
const DEPTH=__DEPTH__;
const BK=__BUCKET__;
const ACT=__ACTION__;
const ST=__STATUS__;
const REVIEWS=__REVIEWS__;
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const dirCls=d=>d==='positive'?'pos':d==='negative'?'neg':'neu';
const dash=v=>v==null?'<span class="muted">—</span>':esc(v);
const dashBool=v=>v==null?'<b>（取不到）</b>':(v?'是':'否');
const dashNum=v=>v==null?'<b>（取不到）</b>':v;
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('on'));
  t.classList.add('on');document.getElementById(t.dataset.t).classList.add('on');});

/* ---- ① 图谱 ---- */
const ORDER=['position_listed','relations_verified','baseline_done','tracking'];
function depthStats(){
  document.getElementById('depthStats').innerHTML=ORDER.map(k=>{
    const n=D.chain.nodes.filter(x=>x.research_depth===k).length;
    const pc=D.chain.nodes.length?(n/D.chain.nodes.length*100).toFixed(0):'0';
    return `<div class="card"><div class="kv"><b>${DEPTH[k]||k}</b><span style="font-size:20px;font-weight:700">${n}</span></div>
    <div class="bar"><i style="width:${pc}%"></i></div>
    <div class="muted" style="font-size:11.5px;margin-top:5px">占 ${pc}% 的在册节点</div></div>`;}).join('');
}
function chainCols(){
  const bk={};D.chain.nodes.forEach(n=>{(bk[n.position_bucket]=bk[n.position_bucket]||[]).push(n)});
  document.getElementById('chainCols').innerHTML=Object.keys(BK).filter(b=>bk[b]).map(b=>
    `<div class="col"><h4>${BK[b]}（${bk[b].length}）</h4>`+bk[b].map(n=>{
      const i=ORDER.indexOf(n.research_depth);
      return `<div class="node" data-node="${esc(n.node_id)}">
        <div class="nm"><span>${esc(n.node_name)}</span><span class="badge b${i<0?0:i}">${esc((DEPTH[n.research_depth]||n.research_depth).replace(/（.*/,''))}</span></div>
        <div class="muted" style="font-size:11.5px;margin-top:3px">${n.changed_since_last_run?'<span class="dot"></span> 今日有变化':'今日无变化'}</div>
      </div>`;}).join('')+'</div>').join('');
  document.querySelectorAll('[data-node]').forEach(el=>el.onclick=()=>showNode(el.dataset.node));
}
function showNode(id){
  const n=D.chain.nodes.find(x=>x.node_id===id);
  const rs=D.chain.relations.filter(r=>r.from===id||r.to===id);
  const ps=D.pages.companies.filter(c=>c.industry_position.some(p=>p.node_id===id));
  document.getElementById('chainSel').classList.remove('muted');
  document.getElementById('chainSel').innerHTML=`<h3 style="margin-top:0">${esc(n.node_name)} <code>${esc(n.node_id)}</code></h3>
  <div class="kv"><b>研究深度</b><span>${esc(DEPTH[n.research_depth]||n.research_depth)}</span><b>更新时间</b><span>${esc(n.updated_at)}</span>
  <b>今日变化</b><span>${n.changed_since_last_run?'有':'无'}</span><b>收录公司</b><span>${n.company_refs.map(esc).join('、')||'—'}</span></div>
  <div class="warn" style="margin-top:9px">${esc(n.study_state_note)}</div>
  <h3>局部关系（${rs.length} 条）</h3>${rs.length?rs.map(r=>`<div class="card"><b>${esc(r.from)} → ${esc(r.to)}</b>　<code>${esc(r.stage)}</code>
    <div class="muted" style="font-size:12px">${esc(r.type)}｜经济暴露：${esc(r.economic_exposure)}（${esc(r.exposure_disclosure)}）｜承诺性质：${esc(r.commitment_kind)}</div>
    <div class="ev">证据：${r.evidence_sources.map(e=>esc(e.claim_id)+'（'+esc(e.locator)+'）').join('；')||'—'}</div>
    ${r.flows.length?'<div class="muted" style="font-size:12px;margin-top:4px">流向：'+r.flows.map(f=>esc(f.flow_kind)+'（'+esc(f.from)+'→'+esc(f.to)+'）').join('；')+'</div>':''}</div>`).join(''):'<div class="muted">该节点暂无已核验关系。</div>'}
  <h3>收录该节点的公司</h3><div>${ps.map(c=>`<span class="pill">${esc(c.legal_name)}（${esc(DEPTH[c.research_depth]||c.research_depth)}）</span>`).join('')||'<span class="muted">—</span>'}</div>`;
}
function evtList(){
  const E=D.chain.event_paths;
  document.getElementById('evtList').innerHTML=E.length?E.map(e=>`<div class="card">
    <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px">
      <b>${esc(e.event_id)}</b><span class="muted" style="font-size:12px">${esc(e.event_type)}｜${esc(e.occurred_at)}｜${e.company_ids.map(esc).join('、')}</span></div>
    ${e.paths.length?e.paths.map(p=>`<div style="margin-top:9px;padding-top:8px;border-top:1px dashed #e6e2da">
      <b>${esc(p.affected_company_id)}</b>　<span class="${dirCls(p.direction)}">${esc(p.direction)}</span>　<code>${esc(p.path_kind)}</code>　
      <span class="badge ${p.evidence_sufficient?'b2':'b0'}">${p.evidence_sufficient?'依据充足':'依据不足'}</span>
      <div class="kv" style="margin-top:6px">
        <b>影响变量</b><span>${esc(p.variable)}</span>
        <b>幅度/范围</b><span>${esc(p.magnitude)}（${esc(p.magnitude_disclosure)}）</span>
        <b>成立条件</b><span>${p.conditions.map(esc).join('；')||'—（缺条件即不成立）'}</span>
        <b>反向力量</b><span>${p.counter_forces.map(esc).join('；')||'—'}</span>
        <b>体现时间</b><span>${esc(p.time_lag)}</span>
        <b>反证</b><span>${p.falsifiers.map(esc).join('；')||'—'}</span></div></div>`).join(''):'<div class="muted">该事件暂无影响路径记录。</div>'}
  </div>`).join(''):'<div class="muted">本轮真源里没有事件 ⇒ 无传导路径可看（不是"传导未发生"）。</div>';
}
function relTable(){
  document.getElementById('relTable').innerHTML='<table><tr><th>关系</th><th>阶段</th><th>经济暴露</th><th>承诺性质</th><th>证据</th></tr>'+
  D.chain.relations.map(r=>`<tr><td><b>${esc(r.from)} → ${esc(r.to)}</b><br><span class="muted">${esc(r.type)}</span></td>
  <td><code>${esc(r.stage)}</code></td><td>${esc(r.economic_exposure)}<br><span class="muted">${esc(r.exposure_disclosure)}</span></td>
  <td>${esc(r.commitment_kind)}</td><td>${r.evidence_sources.map(e=>esc(e.claim_id)+'<br><span class="muted">'+esc(e.locator)+'</span>').join('<br>')||'—'}</td></tr>`).join('')+'</table>';
}
function gaps(){
  const G=D.chain.data_gaps;
  document.getElementById('gaps').innerHTML=G.length?G.map(g=>
   `<div class="gap"><b>${esc(g.gap)}</b>　<span class="muted">卡在：${(g.blocked_steps||[]).map(esc).join('、')||'（未标步骤）'}</span><br>${esc(g.detail)}<br><span class="muted" style="font-size:11px">出处：${esc(g.source||'')}</span></div>`).join('')
   :'<div class="muted">本轮未登记缺口（为空 ≠ 没有缺口，只表示没有登记）。</div>';
}

/* ---- ② 公司研究页 ---- */
function coList(){
  document.getElementById('coList').innerHTML=D.pages.companies.map((c,i)=>`<div class="node" data-co="${i}">
    <div class="nm"><span>${esc(c.legal_name)}</span><span class="badge b${Math.max(0,ORDER.indexOf(c.research_depth))}">${esc((DEPTH[c.research_depth]||c.research_depth).replace(/（.*/,''))}</span></div>
    <div class="muted" style="font-size:11.5px;margin-top:3px">${c.current_recommendation?('建议：'+esc(ACT[c.current_recommendation.action]||c.current_recommendation.action)):'尚无建议'}</div></div>`).join('');
  document.querySelectorAll('[data-co]').forEach(el=>el.onclick=()=>showCo(+el.dataset.co));
}
function showCo(i){
  const c=D.pages.companies[i],e=c.expanded,rec=c.current_recommendation;
  const vs=c.growth_certainty||{};
  const fin=e.financial_and_valuation||{}, vv=fin.valuation||{};
  document.getElementById('coDetail').classList.remove('muted');
  document.getElementById('coDetail').innerHTML=`
  <h3 style="margin-top:0">${esc(c.legal_name)} <code>${esc(c.company_id)}</code>　<span class="badge b2">${esc(DEPTH[c.research_depth]||c.research_depth)}</span></h3>
  <h3>首屏六项</h3>
  <div class="kv">
    <b>①产业位置</b><span>${c.industry_position.map(p=>esc(p.node_id)+'（'+esc(p.evidence_strength)+'）').join('；')||'<span class="muted">尚未建立</span>'}</span>
    <b>②增长动力</b><span>${c.growth_drivers.map(d=>esc(d.driver_id)+'·'+esc(d.realization_stage)).join('；')||'<span class="muted">—</span>'}</span>
    <b>③增长确定性</b><span>动力 <b>${esc(vs.growth_momentum_state||'tbd')}</b>／确定性 <b>${esc(vs.certainty_state||'tbd')}</b>（状态与趋势分开记）</span>
    <b>④护城河</b><span>水平 <b>${esc(vs.moat_level||'tbd')}</b>／趋势 <b>${esc(vs.moat_state||'tbd')}</b>　${c.moat.map(m=>esc(m.moat_id)).join('、')||''}</span>
    <b>⑤当前建议</b><span>${rec?`<b>${esc(ACT[rec.action]||rec.action)}</b>（${esc(ST[rec.status]||rec.status)}）${esc(rec.horizon)}｜起算 ${esc(rec.start_date)}｜复查 ${dash(rec.review_date)}<br><span class="muted"><code>${esc(rec.recommendation_id)}</code>（本区块全部字段取自这一行）</span>`: '<span class="muted">尚无建议（研究未完成先记缺口）</span>'}</span>
    <b>⑥本次变化</b><span>基线 v${dash(c.change_this_run.baseline_version)}｜${esc(c.change_this_run.version_kind||'无版本类型标记')}</span>
  </div>
  ${rec?`<div class="warn"><b>建议八项要点</b><br>变化原因：${esc(rec.change_reason)}<br>
    假设：${rec.assumptions.map(esc).join('；')||'—'}<br>
    证据缺口：${rec.evidence_gaps.map(esc).join('；')||'—'}<br>
    验证条件：${rec.verification_conditions.map(esc).join('；')||'—'}<br>
    <b>反证/证伪条件：${rec.falsifiers.map(esc).join('；')||'—'}</b>${rec.supersedes?`<br>取代：<code>${esc(rec.supersedes)}</code>`:''}</div>`:''}
  <details open><summary>展开层 · 完整底稿（经营机制）</summary><div class="muted">${esc(e.business_mechanism)}</div></details>
  <details><summary>展开层 · 增长动力明细</summary><table><tr><th>驱动</th><th>来源类别</th><th>兑现阶段</th><th>期限</th><th>置信</th><th>依赖</th></tr>
   ${c.growth_drivers.map(d=>`<tr><td><code>${esc(d.driver_id)}</code></td><td>${esc(d.source_class)}</td><td>${esc(d.realization_stage)}</td><td>${esc(d.timeline)}</td><td>${esc(d.confidence)}</td><td>${d.dependencies.map(esc).join('；')||'—'}</td></tr>`).join('')}</table></details>
  <details><summary>展开层 · 护城河</summary>${c.moat.map(m=>`<div class="card"><b>${esc(m.moat_id)}</b><br>${esc(m.mechanism)}<br>
   <span class="muted">来源：${esc(m.origin_class)}｜保护对象：${(m.protected_objects||[]).map(o=>esc(o.object)+'('+esc(o.strength)+')').join('、')}｜跨代际存活：${esc(m.cross_generation_survival)}｜跨代际竞争力：${esc(m.cross_generation_competitiveness)}</span>
   ${(m.real_substitutes||[]).map(s=>`<div class="ev">替代方案：触发=${esc(s.switch_trigger)}｜切换成本=${esc(s.switching_cost)}｜实际切换证据=${(s.actual_switch_evidence||[]).length?(s.actual_switch_evidence||[]).map(esc).join('、'):'[]（无）'}</div>`).join('')}</div>`).join('')||'—'}</details>
  <details><summary>展开层 · 财务与估值</summary>
   <table><tr><th>估值输入</th><th>取值</th><th>来源类型</th></tr>${Object.entries(fin.valuation_inputs||{}).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${v?esc(v.value):'<b>（未给）</b>'}</td><td>${v?esc(v.input_source):'—'}</td></tr>`).join('')}</table>
   <div class="kv"><b>估值方法</b><span>${dash(vv.method_class)}</span>
   <b>底稿引用</b><span><code>${dash(vv.formula_ref)}</code></span>
   <b>情景标签</b><span>${dash(vv.scenario_tag)}</span>
   <b>价格隐含</b><span>${dash(vv.implied_ref)}</span></div>
   <div class="warn"><b>独立判断：</b>${dash(vv.independent_judgment)}</div></details>
  <details><summary>展开层 · 原始证据（${e.raw_evidence.length} 条，带定位）</summary>
   <table><tr><th>主张</th><th>引文</th><th>定位</th><th>层级</th><th>来源</th></tr>
   ${e.raw_evidence.map(x=>`<tr><td><code>${esc(x.claim_id)}</code></td><td>${esc(x.quote)}</td><td><code>${esc(x.locator)}</code></td><td>${esc(x.tier)}</td><td>${x.source_entry?`<a href="${esc(x.source_entry)}" target="_blank" rel="noopener">${esc(x.source_entry).slice(0,52)}…</a>`:'—'}</td></tr>`).join('')||'<tr><td colspan="5" class="muted">（未给）</td></tr>'}</table></details>
  <details><summary>展开层 · 反证与未兑现条件</summary>
   <div class="gap"><span class="muted">取自研究基线 <code>${esc(e.counter_evidence.source_row||'')}</code>（与"建议反证"是两个对象，勿混读）</span><br>
   <b>证伪条件：</b>${e.counter_evidence.falsifiers.map(esc).join('；')||'—'}<br>
   <b>未兑现条件：</b>${e.counter_evidence.unmet_conditions.map(esc).join('；')||'—'}</div></details>
  <details><summary>展开层 · 历史版本</summary><table><tr><th>基线</th><th>版本</th><th>结论版本</th><th>版本类型</th><th>上一版</th></tr>
   ${e.history_versions.map(h=>`<tr><td><code>${esc(h.baseline_id)}</code></td><td>v${esc(h.version)}</td><td>${esc(h.conclusion_version)}</td><td>${esc(h.version_kind)}</td><td>${esc(h.prev_version_id)}</td></tr>`).join('')}</table></details>`;
}
function coTodo(){
  const d=D.pages.companies.filter(c=>!(c.growth_drivers.length||c.moat.length));
  document.getElementById('coTodo').innerHTML=d.length?('<table><tr><th>公司</th><th>研究深度</th></tr>'+
   d.map(c=>`<tr><td>${esc(c.legal_name)}</td><td>${esc(DEPTH[c.research_depth]||c.research_depth)}</td></tr>`).join('')+
   '</table><div class="warn">以上公司<b>没有研究底稿</b> —— 直说「尚未研究」，不等于中性，也不等于没有机会。</div>'):'<div class="muted">全部公司均已有底稿。</div>';
}
function coSuperseded(){
  const s=D.pages.superseded_recommendations||[];
  document.getElementById('coSuperseded').innerHTML=s.length?
   ('<table><tr><th>被取代的建议</th><th>业务键</th><th>取代者</th><th>行动</th><th>状态</th></tr>'+
    s.map(x=>x.kind==='supersedes_chain_multihead'
      ? `<tr><td><b>链条分叉</b></td><td><code>${esc(x.business_key)}</code></td><td>${(x.heads||[]).map(h=>'<code>'+esc(h)+'</code>').join('、')}</td><td>—</td><td>—</td></tr>`
      : `<tr><td><code>${esc(x.recommendation_id)}</code></td><td><code>${esc(x.business_key)}</code></td><td><code>${esc(x.replaced_by)}</code></td><td>${esc(ACT[x.action]||x.action||'')}</td><td>${esc(ST[x.status]||x.status||'')}</td></tr>`).join('')+
    '</table><div class="warn">追加式不可变真源（<code>Ch9 §3.4.2</code>）：一次修正<b>追加新行</b>、不原地改写；删掉旧行等于把失败记录洗掉（<code>N10.3-14</code>）。</div>')
   :'<div class="muted">本轮没有被取代的建议。</div>';
}

/* ---- ③ 每日研究页 ---- */
function reviewBlock(v){
  if(!v) return '<div class="muted">本轮该层无复盘记录（如实为空，不得用文字凑）</div>';
  const ax=(v.error_axis||[]);
  return `<div>${esc(v.note||'—')}<br><span class="muted" style="font-size:11.5px">错误方向：${ax.length?ax.map(esc).join('、'):'—（本轮无）'}</span></div>`;
}
function dailyPage(){
  const r=D.daily.run_summary;
  document.getElementById('dailyRun').innerHTML=`<b>今天这一轮：</b>有变化=<b>${dashBool(r.changed)}</b>　新买卖信号=<b>${dashNum(r.signals_emitted)}</b> 条　
   降级=${dashBool(r.degraded)}　阻断=${dashBool(r.blocked)}　缺口=${dashNum(r.gaps)} 条<br>${esc(r.note)}<br>
   <span class="muted">★ 每天维护判断 ≠ 每天必须产生新买卖信号。"今天没有新信号"是正确状态。</span>`;
  const I=D.daily.important_information;
  document.getElementById('dInfo').innerHTML=(I.length?'<table><tr><th>事件</th><th>发生时间</th><th>类型</th><th>涉及公司</th><th>根来源</th><th>层级</th></tr>'+
   I.map(i=>`<tr><td><code>${esc(i.event_id)}</code></td><td>${esc(i.event_time)}</td><td>${esc(i.type)}</td>
   <td>${i.companies.map(esc).join('、')}</td><td>${i.source?`<a href="${esc(i.source)}" target="_blank" rel="noopener">${esc(i.source).slice(0,48)}…</a>`:'—'}</td><td>${esc(i.source_tier)}</td></tr>`).join('')+'</table>':'<div class="muted">本轮真源里没有事件。</div>')
   +`<div class="warn" style="margin-top:8px">${esc(D.daily.important_information_note||'')}</div>`;
  const AF=D.daily.affected_companies;
  document.getElementById('dAff').innerHTML=AF.length?AF.map(a=>`<div class="card">
   <b>${esc(a.company_id)}</b>　方向 <span class="${dirCls(a.direction)}">${esc(a.direction)}</span>
   <div class="kv" style="margin-top:6px"><b>影响变量</b><span>${esc(a.variable)}</span><b>幅度</b><span>${esc(a.magnitude)}</span>
   <b>成立条件</b><span>${a.conditions.map(esc).join('；')||'—'}</span><b>反向力量</b><span>${a.counter_forces.map(esc).join('；')||'—'}</span>
   <b>体现时间</b><span>${esc(a.time_lag)}</span><b>反证</b><span>${a.falsifiers.map(esc).join('；')||'—'}</span></div></div>`).join(''):'<div class="muted">本轮真源里没有影响路径记录。</div>';
  const RC=D.daily.recommendation_changes;
  document.getElementById('dRec').innerHTML=RC.length?('<table><tr><th>公司</th><th>建议</th><th>状态</th><th>变化原因</th><th>取代</th><th>反证</th></tr>'+
   RC.map(r=>`<tr><td>${esc(r.company_id)}</td><td><b>${esc(ACT[r.action]||r.action)}</b></td>
   <td>${esc(ST[r.status]||r.status)}</td><td>${esc(r.change_reason)}</td><td>${esc(r.supersedes||'—')}</td><td>${r.falsifiers.map(esc).join('；')||'—'}</td></tr>`).join('')+'</table>'):'<div class="muted">本运行日没有新增或被取代的建议。</div>';
  const N=D.daily.next_verification_nodes;
  document.getElementById('dNext').innerHTML=N.length?('<table><tr><th>公司</th><th>建议</th><th>复查日期</th></tr>'+
   N.map(n=>`<tr><td>${esc(n.company_id)}</td><td><code>${esc(n.recommendation_id)}</code></td><td>${dash(n.review_date)}</td></tr>`).join('')+'</table>'):'<div class="muted">尚无当前建议 ⇒ 无复查节点。</div>';
  const u=D.daily.unfinished_verification,s=D.daily.stale_or_delayed_data,f=D.daily.failed_tasks;
  document.getElementById('dBad').innerHTML=`
   <h3>5.1 未完成核验</h3>${u.length?u.map(x=>`<div class="warn">${esc(x.detail)}：<b>共 ${x.count} 条</b><br><span class="muted">示例：${x.refs.map(esc).join('、')}</span></div>`).join(''):'<div class="muted">无</div>'}
   <h3>5.2 数据失效 / 延迟</h3>${s.map(x=>`<div class="warn">${esc(x.detail)}（as-of ${dash(x.as_of)}，延迟标记 ${esc(x.delayed)}）</div>`).join('')}
   <h3>5.3 失败的运行 / 研究任务</h3>${f.length?('<table><tr><th>任务</th><th>类别</th><th>状态</th><th>保留的上次有效结果</th></tr>'+
     f.map(x=>`<tr><td><code>${esc(x.task_id)}</code></td><td>${esc(x.kind)}</td><td>${esc(x.status)}</td><td>${x.last_valid_result_ref?esc(x.last_valid_result_ref):'—（无）'}</td></tr>`).join('')+'</table>'):'<div class="muted">无</div>'}`;
  const rv=D.daily.reviews_separated;
  document.getElementById('dRev').innerHTML=REVIEWS.map(([k,cn])=>`<div class="card"><b>${cn}</b><br>${reviewBlock(rv[k])}</div>`).join('')
   +`<div class="warn">${esc(rv.note)}</div>`;
}
depthStats();chainCols();evtList();relTable();gaps();coList();coTodo();coSuperseded();dailyPage();
</script></body></html>"""


def build_html(
    chain: Mapping[str, Any], pages: Mapping[str, Any], daily: Mapping[str, Any],
    run_date: str,
) -> str:
    """自包含 dashboard（数据整块内联，无外部请求）。"""
    data = json.dumps({"chain": chain, "pages": pages, "daily": daily}, ensure_ascii=False)
    out = _HTML_TEMPLATE.replace("__RUN_DATE__", run_date).replace("__DATA__", data)
    out = out.replace("__DEPTH__", json.dumps(DEPTH_CN, ensure_ascii=False))
    out = out.replace("__BUCKET__", json.dumps(BUCKET_CN, ensure_ascii=False))
    out = out.replace("__ACTION__", json.dumps(ACTION_CN, ensure_ascii=False))
    out = out.replace("__STATUS__", json.dumps(STATUS_CN, ensure_ascii=False))
    out = out.replace("__REVIEWS__", json.dumps(list(REVIEW_LAYERS), ensure_ascii=False))
    return out


# ═════════════════════════ 入口 ═════════════════════════


def _load_views(root: Path, run_date: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """读三份 JSON；缺任何一份都**响亮失败**（不重算、不兜底）。"""
    vs = root / VIEWS_DIRNAME
    out: list[dict[str, Any]] = []
    for name in (CHAIN_MAP_FILE, COMPANY_PAGES_FILE, DAILY_PAGE_TEMPLATE.format(run_date=run_date)):
        path = vs / name
        if not path.exists():
            raise FileNotFoundError(
                f"缺 {path} —— 请先跑 `python system/scripts/views/build.py {root} "
                f"--run-date {run_date}`（本渲染器**不**自行取数，避免与构建器各算一遍）"
            )
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out[0], out[1], out[2]


def render_readable(root: str | Path, run_date: str) -> dict[str, str]:
    """返回 `{文件名: 内容}`（**不写盘**）—— 三份人话 MD + dashboard.html。"""
    root_path = Path(root)
    chain, pages, daily = _load_views(root_path, run_date)
    return {
        CHAIN_MD: md_chain(chain),
        PAGES_MD: md_pages(pages),
        DAILY_MD_TEMPLATE.format(run_date=run_date): md_daily(daily),
        DASHBOARD: build_html(chain, pages, daily, run_date),
    }


def write_readable(root: str | Path, run_date: str) -> list[Path]:
    """写 3 份 MD 到 `reports/`、dashboard 到 `views/`；返回写出的路径。"""
    root_path = Path(root)
    reports = root_path / REPORTS_DIRNAME
    reports.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, text in render_readable(root_path, run_date).items():
        path = (root_path / VIEWS_DIRNAME / name) if name == DASHBOARD else (reports / name)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def _latest_run_date(root: Path) -> str:
    """从 `views/` 里**已有**的每日页文件名反推运行日（有出处，不猜）。"""
    names = sorted(p.name for p in (root / VIEWS_DIRNAME).glob("daily_page_*.json"))
    if not names:
        raise FileNotFoundError(
            f"{root / VIEWS_DIRNAME} 下没有 daily_page_*.json ⇒ 无法确定运行日，请显式给 --run-date"
        )
    return names[-1][len("daily_page_"):-len(".json")]


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    positional = [a for a in args if not a.startswith("--")]
    root = Path(positional[0]).resolve() if positional else _ROOT
    run_date = None
    if "--run-date" in args:
        idx = args.index("--run-date")
        run_date = args[idx + 1] if idx + 1 < len(args) else None
    if "--build" in args:      # 便捷：先构建再渲染（等价于串联两个 CLI）
        write_views(root, run_date or _latest_run_date(root))
    run_date = run_date or _latest_run_date(root)
    for p in write_readable(root, run_date):
        print(f"[readable] {p.relative_to(root)}  {p.stat().st_size} bytes")
    return 0


if __name__ == "__main__":  # pragma: no cover - 手工入口
    raise SystemExit(main())
