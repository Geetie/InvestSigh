#!/usr/bin/env python3
"""`fetch_manifest.py` —— **公开网页抓取清单**（`public_fetcher.py` 的输入）。

## 清单的语义

每条 `FetchSpec` = 「一个公开入口 + 落点名 + 抓取健全性断言」。
`must_contain` 里的串**声明在先、比对在后**：抓到的正文若不逐字包含它们，
该来源判失败（`exit 1`）—— 拦的是错误页 / 验证页 / 页面改版，
**不是**对文本做词面分类（`CONVENTIONS.md::R-06` ①）。

## 分层（`tier` 在此处**不**声明）

本清单只负责"把公开文本抓回来"；来源分级（`Ch6 §C.1`）与三字段标注由
`real_collector.py::MANIFEST` 逐条给出（分工见 `public_fetcher.py` 的模块 docstring）。
**抓取侧不得据内容猜测分级**（`real_collector` 的 `DEFAULT_*` 口径同此）。

## 命名

`raw_name = YYYY-MM-DD-<slug>.txt`，日期 = **来源自述的发布日**。
来源确未披露发布日者，前缀取**抓取日**并在 slug 里显式标 `undated`
（`Semihub` 博客页无发布日）——**不**用抓取日冒充发布日。

## 本机直取被拒的来源（如实记录，不绕过）

`investor.tsmc.com` / `pr.tsmc.com` / `www.tsmc.com` 对本机 IP **一律 HTTP 403**
（WAF；已实测 `urllib` 与 `curl` 加完整浏览器请求头，均 403）。
该来源改走 allowlist 内的 `websearch_webfetch`（`builtin_capability`）取得，
其落盘物由 `WEBFETCH_SPECS` 声明、由采集动作显式投递（见 `system/reports/ws_real_collect_2_report.md`）。
**不**伪造 HTTP 直取的元数据。
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.ingest.public_fetcher import FetchSpec

__all__ = ["FETCH_SPECS", "WEBFETCH_ONLY"]

_NVIDIA_NEWSROOM = "https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-"


FETCH_SPECS: tuple[FetchSpec, ...] = (
    # ── NVIDIA 官方 IR / newsroom（一手：公司自己披露的经营结果） ─────────────────
    FetchSpec(
        url=_NVIDIA_NEWSROOM + "first-quarter-fiscal-2026",
        raw_name="2025-05-28-nvidia-q1-fy2026-results.txt",
        must_contain=(
            "NVIDIA Announces Financial Results for First Quarter Fiscal 2026",
            "Data Center revenue",
        ),
    ),
    FetchSpec(
        url=_NVIDIA_NEWSROOM + "second-quarter-fiscal-2026",
        raw_name="2025-08-27-nvidia-q2-fy2026-results.txt",
        must_contain=(
            "NVIDIA Announces Financial Results for Second Quarter Fiscal 2026",
            "Data Center revenue",
        ),
    ),
    FetchSpec(
        url=_NVIDIA_NEWSROOM + "third-quarter-fiscal-2026",
        raw_name="2025-11-19-nvidia-q3-fy2026-results.txt",
        must_contain=(
            "NVIDIA Announces Financial Results for Third Quarter Fiscal 2026",
            "Data Center revenue",
        ),
    ),
    FetchSpec(
        url=_NVIDIA_NEWSROOM + "fourth-quarter-and-fiscal-2026",
        raw_name="2026-02-25-nvidia-q4-fy2026-results.txt",
        must_contain=(
            "NVIDIA Announces Financial Results for Fourth Quarter and Fiscal 2026",
            "Record full-year revenue",
        ),
    ),
    FetchSpec(
        url=_NVIDIA_NEWSROOM + "first-quarter-fiscal-2027",
        raw_name="2026-05-20-nvidia-q1-fy2027-results.txt",
        must_contain=(
            "NVIDIA Announces Financial Results for First Quarter Fiscal 2027",
            "Data Center revenue",
        ),
    ),
    FetchSpec(
        url=_NVIDIA_NEWSROOM + "second-quarter-fiscal-2027",
        raw_name="2026-08-26-nvidia-q2-fy2027-results.txt",
        must_contain=(
            "NVIDIA Announces Financial Results for Second Quarter Fiscal 2027",
            "Data Center revenue",
        ),
    ),
    # ── 上游存储：SK hynix / Micron 官方 newsroom（一手） ───────────────────────
    FetchSpec(
        url="https://news.skhynix.com/en/sk-hynix-ships-samples-of-12-layer-next-gen-hbm4e-2/",
        raw_name="2026-06-18-sk-hynix-hbm4e-samples.txt",
        must_contain=("HBM4E", "MR-MUF"),
    ),
    FetchSpec(
        url=(
            "https://investors.micron.com/news/press-release/2026/"
            "Micron-in-High-Volume-Production-of-HBM4-Designed-for-NVIDIA-Vera-Rubin-"
            "PCIe-Gen6-SSD-and-SOCAMM2-03-16-2026/default.aspx"
        ),
        raw_name="2026-03-16-micron-hbm4-volume-production.txt",
        must_contain=("HBM4", "NVIDIA"),
    ),
    # ── 二手：主流媒体 / 行业媒体（**明确标二手**，不进决策逻辑） ────────────────
    FetchSpec(
        url="https://www.news.cn/world/20260226/8e2d572e6317402aa6b5be64c3a6cefd/c.html",
        raw_name="2026-02-26-xinhua-nvidia-fy2026-results.txt",
        must_contain=("英伟达", "数据中心"),
    ),
    FetchSpec(
        url="https://www.stcn.com/article/detail/3919308.html",
        raw_name="2026-05-20-stcn-nvidia-q1-fy2027.txt",
        must_contain=("英伟达", "营收"),
    ),
    FetchSpec(
        url=(
            "https://biz.heraldcorp.com/article/10849578"
        ),
        raw_name="2026-08-24-herald-sk-hynix-hbm4-hotchips.txt",
        must_contain=("HBM4", "hybrid bonding"),
    ),
    FetchSpec(
        url="https://m.ajupress.com/amp/20260105152112913",
        raw_name="2026-01-05-ajupress-cowos-bottleneck.txt",
        must_contain=("CoWoS", "TSMC"),
    ),
    FetchSpec(
        url="https://semihub.io/en/blog/cowos-guide-4.html",
        raw_name="2026-09-16-semihub-cowos-supply-war-undated.txt",
        must_contain=("CoWoS", "TSMC"),
    ),
)
"""HTTP 直取来源清单（13 条）。"""


@dataclass(frozen=True)
class WebfetchOnlySpec:
    """**本机直取被拒、改走 `websearch_webfetch` 能力**的来源声明（不参与 HTTP 抓取）。"""

    url: str
    raw_name: str
    transport: str
    note: str


WEBFETCH_ONLY: tuple[WebfetchOnlySpec, ...] = (
    WebfetchOnlySpec(
        url="https://investor.tsmc.com/english/monthly-revenue/2026",
        raw_name="2026-09-10-tsmc-monthly-revenue-2026.txt",
        transport="webfetch",
        note=(
            "investor.tsmc.com 对本机 IP 一律 HTTP 403（WAF，实测 urllib/curl 均 403），"
            "故经 allowlist 的 builtin_capability `websearch_webfetch` 取得页面文本"
        ),
    ),
)
"""经 `websearch_webfetch` 能力取得的来源（**非** HTTP 直取，落盘物头部如实标注 transport）。"""
