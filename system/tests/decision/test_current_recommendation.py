"""`tests/decision/test_current_recommendation.py` —— 「**哪条建议是当前**」的机器绑定。

覆盖 `scripts.decision.rules` 的三个函数（`B-7` 的修复面）：

| 函数 | 回答 |
|---|---|
| `supersedes_map` | 谁**取代**了谁（`supersedes` 字段的解析） |
| `current_recommendation_row` | 同一业务键下，**当前**建议（`supersedes` 链的末节点） |
| `current_recommendation_multihead` | 末节点**不唯一**时如实报出（不静默择一） |

★★ 为什么这个文件必须存在（2026-09-17 冷启动实测缺陷 `B-7`）：

  `views/company_pages.json` 的 `current_recommendation` 原先按 `recorded_seq` 取最大。
  真实数据里 NVIDIA 的**两行 `recorded_seq` 都是 1** ⇒ 比较用 `>` **从不成立** ⇒
  取到**文件中第一条** = `rec-sec-nvda-2026-08-03`（v1、`buy`、依据是**已实现收益**）——
  即**已被评审明确推翻**的旧建议被当作"当前建议"渲染；而同页"反证"却取自取代它的那条
  （`pending`）⇒ **同页不同源、自相矛盾**（读者看到"买入 + 三条反证"）。

  ⇒ 本文件用**真实数据形态**（两行 `(version, recorded_seq)` 完全相同、靠 `supersedes` 区分）
    钉住：**"哪条是当前"必须由图关系决定，不能由行的物理顺序决定。**

★ 与 `tests/unit/test_traceback_four_elements.py::test_latest_version_row_*` 的**分工**：
  那条测的是"**同一条**建议的多版本行取哪版"（按 `recommendation_id` 分组）；
  本文件测的是"**同一业务键**下哪条建议是当前"（可能**换了 id**，按 `supersedes` 链走）。
  两个问题不同、实现不同、判据也不同 —— 混为一个会让其中一种形态失去覆盖。
"""

from __future__ import annotations

import pytest
from scripts.decision.rules import (
    current_recommendation_multihead,
    current_recommendation_row,
    latest_version_row,
    supersedes_map,
)


# ─────────────────────── 夹具：真实数据形态（B-7 原样） ───────────────────────


def _v1_buy() -> dict:
    """旧建议：`buy` + 依据是已实现收益（`falsifiers` 空）—— 已被评审推翻。"""
    return {
        "recommendation_id": "rec-sec-nvda-2026-08-03",
        "company_id": "company-nvidia", "security_id": "sec-nvda",
        "start_date": "2026-08-03", "action": "buy", "status": "active",
        "version": 1, "recorded_seq": 1, "supersedes": None,
        "review_date": "2026-09-16", "falsifiers": [],
    }


def _v1_pending_superseding() -> dict:
    """新建议：`pending`，明确 `supersedes` 旧的那条。★ 数值水位与旧行**完全相同**。"""
    return {
        "recommendation_id": "rec-sec-nvda-2026-08-03-session-review",
        "company_id": "company-nvidia", "security_id": "sec-nvda",
        "start_date": "2026-08-03", "action": "pending", "status": "uncertain",
        "version": 1, "recorded_seq": 1,
        "supersedes": "rec-sec-nvda-2026-08-03",
        "review_date": "2026-11-25",
        "falsifiers": ["Q3 FY2027 实际收入 < 105.84B", "GAAP 毛利率连续两季 < 74%"],
    }


# ─────────────────────── 1. `supersedes_map` ───────────────────────


def test_supersedes_map_parses_the_field() -> None:
    """只认显式 `supersedes`；空串/缺失一律**不**入表（不把""当成一个 id）。"""
    assert supersedes_map([_v1_buy(), _v1_pending_superseding()]) == {
        "rec-sec-nvda-2026-08-03": "rec-sec-nvda-2026-08-03-session-review"
    }
    assert supersedes_map([{"recommendation_id": "a", "supersedes": ""}]) == {}
    assert supersedes_map([{"recommendation_id": "a"}, {"recommendation_id": "b", "supersedes": None}]) == {}
    # 分叉：两条都声称取代同一条 ⇒ 保留**首个声明者**（不静默择后一个）
    fork = [
        {"recommendation_id": "n1", "supersedes": "old"},
        {"recommendation_id": "n2", "supersedes": "old"},
    ]
    assert supersedes_map(fork) == {"old": "n1"}


# ─────────────────────── 2. 末节点选择（B-7 回归） ───────────────────────


def test_current_row_follows_supersedes_chain_not_file_order() -> None:
    """★ **B-7 回归**：`(version, recorded_seq)` 完全相同时，**只有 `supersedes` 能区分**。

    这一条是本文件的核心 —— 用**真实数据形态**（两行水位都是 `(1, 1)`）证明：
      · 按物理顺序选 ⇒ 取到**第一个**（`buy`，已被推翻）
      · 按 `supersedes` 链选 ⇒ 取到**取代者**（`pending`）
    """
    old, new = _v1_buy(), _v1_pending_superseding()
    # 前提（防夹具漂移）：两行的数值水位必须**相同**，否则本用例失去区分力
    assert (old["version"], old["recorded_seq"]) == (new["version"], new["recorded_seq"])

    # ★ 顺序无关：两种物理顺序都必须选到 `new`
    assert current_recommendation_row([old, new])["recommendation_id"] == new["recommendation_id"]
    assert current_recommendation_row([new, old])["recommendation_id"] == new["recommendation_id"]

    # 反向对照：拿掉 `supersedes` ⇒ 退化为"取靠后那条"（`latest_version_row` 的语义）
    #   —— 证明上面那条**不是**恒真，而是真由 `supersedes` 决定的
    new_no_marker = dict(new, supersedes=None)
    assert current_recommendation_row([old, new_no_marker])["recommendation_id"] == new["recommendation_id"]
    assert current_recommendation_row([new_no_marker, old])["recommendation_id"] == old["recommendation_id"], (
        "无 supersedes 标记时应退化为按物理顺序（靠后者胜）—— 否则本用例的区分力不成立"
    )


def test_current_row_walks_a_multi_hop_chain_to_the_end() -> None:
    """`supersedes` 可以成链（a←b←c）：末节点是 **c**，不是中间节点。"""
    a = dict(_v1_buy(), recommendation_id="rec-a", supersedes=None)
    b = dict(_v1_buy(), recommendation_id="rec-b", supersedes="rec-a")
    c = dict(_v1_buy(), recommendation_id="rec-c", supersedes="rec-b")
    assert current_recommendation_row([a, b, c])["recommendation_id"] == "rec-c"
    assert current_recommendation_row([c, a, b])["recommendation_id"] == "rec-c"


def test_current_row_handles_independent_rows() -> None:
    """组内只有一条、或几条互不取代 ⇒ 各自都是自己那条链的末节点（不误判、不抛）。"""
    one = _v1_pending_superseding()
    assert current_recommendation_row([one]) is one
    x = dict(one, recommendation_id="rec-x", supersedes=None)
    y = dict(one, recommendation_id="rec-y", supersedes=None)
    assert current_recommendation_row([x, y])["recommendation_id"] in ("rec-x", "rec-y")


# ─────────────────────── 3. 分叉/成环：如实报出，不静默 ───────────────────────


def test_multihead_is_reported_not_silently_picked() -> None:
    """★ 末节点**不唯一**（分叉）⇒ 如实报出两个 id（`R-03`：降级要显式可见）。

    分叉意味着**该结论的"当前版本"本身不唯一**——机器不得替人择一，
    只能取一条（保证不崩）并把事实**具名报出**。
    """
    a = dict(_v1_buy(), recommendation_id="rec-a", supersedes=None)
    b = dict(_v1_buy(), recommendation_id="rec-b", supersedes="tail")
    c = dict(_v1_buy(), recommendation_id="rec-c", supersedes="tail")
    heads = current_recommendation_multihead([a, b, c])
    assert set(heads) == {"rec-a", "rec-b", "rec-c"}, heads
    # 仍能取到一条（不抛），但**不宣称**它独一无二
    assert current_recommendation_row([a, b, c])["recommendation_id"] in heads


def test_multihead_is_empty_when_chain_has_one_end() -> None:
    """唯一末节点 ⇒ 空元组（调用方据此**不**报分叉；不得恒非空把正常当异常）。"""
    assert current_recommendation_multihead([_v1_buy(), _v1_pending_superseding()]) == ()
    assert current_recommendation_multihead([]) == ()


def test_cycle_falls_back_loudly_by_note_not_by_silent_choice() -> None:
    """链成环（a 取代 b、b 取代 a）⇒ 末节点为空 ⇒ **回退到版本水位**取一条，且报出全部相关 id。

    ★ 这里不抛异常：真源里的成环是**数据缺陷**，但视图构建**不能因此崩掉**
      （它只是展示层；崩掉等于整页看不到）。处置 = 取一条 + **具名报出**，
      让判据（而非崩溃）去承载"数据有问题"这件事。
    """
    a = dict(_v1_buy(), recommendation_id="rec-a", supersedes="rec-b")
    b = dict(_v1_buy(), recommendation_id="rec-b", supersedes="rec-a")
    assert current_recommendation_multihead([a, b]) == ()      # 环里没有"没被取代"的行
    picked = current_recommendation_row([a, b])
    assert picked["recommendation_id"] in ("rec-a", "rec-b")
    # 与纯水位法一致（回退路径就是它）—— 证明回退是**确定的**，不是随机的
    assert picked is latest_version_row([a, b])


def test_empty_group_is_loud() -> None:
    """空组必须响亮（`G-03`：不得把"无被检对象"当"已验证"）。"""
    with pytest.raises(ValueError, match="非空"):
        current_recommendation_row([])
