#!/usr/bin/env python3
"""`real_collector.py` —— 阶段② **真实连接器**：把 `raw/` 已落盘的一手材料按**真实来源标注**摄入 claims。

## 与 step 1 的分工（接缝在**投递侧**，不在**处理侧**）

`scripts/orchestrate/ingest_step.py::ingest_public_information` 是 step 1 的**投递口处理器**：
它从 `raw/inbox/` 读取待采集文本，并以**最保守的缺省标注**摄入
（`secondary_tertiary` / `interpretation` / `opinion`）。该模块 docstring 明确把
"按来源逐条给出真实标注"列为**阶段② 连接器**的职责。本模块即该连接器的最小实现：

- **载荷**：`raw/<name>` 的原文（采集侧已落盘；本模块**不抓取、不合成**文本）；
- **标注**：`MANIFEST` 逐条声明的真实来源元数据（`source_id` / 发布方 / `tier` /
  `claim_nature` / `claim_form` / `official_claim_kind`）—— 即"三字段维度不同、不得互换"（`Ch9 §3.4.6` R-17 / D-02）。

## 唯一真源（`CONVENTIONS.md::G-06`）

- claim 构造**一律**经 `scripts.guard.claims.build_claim`（**唯一构造口**），本模块不自建第二条；
- 落库**一律**经 `schema.store.append_records`（**唯一写入口**）；
- `locator` / `quote_hash` 语义与 `scripts.guard.executor` **同源**：
  `locator = raw/<name>#L1-L<行数>`、`quote_hash = sha256(UTF-8 原文)`。

## 五类时间语义（`Ch9 §2.2` / `§3.4.1`）

- **system_time**（永不未知）：`first_seen_at` = `analyzed_at` = 本次处理时刻（UTC）；
  `recorded_seq` = `facts/claims.jsonl` 现有最大者 + 1（**不得**恒为 1）。
- **valid_time**：`occurred_at` = `published_at` = 原文发布日；`effective_from` 保持 `None`（来源未披露生效口径）。
- **backfill**：发布日早于补入日 → `backfilled_at` = 补入日（防"事后信息伪装成当时已知"）。

## 幂等

同一 `claim_id`（= `claim-<source_id>-<quote_hash[:12]>`）已存在 → **跳过**，不重复落库。

## 用法

    python system/scripts/ingest/real_collector.py [code_root]

退出码（`CONVENTIONS.md::G-01`）：`0` 全部摄入或均已入库 · `1` 有材料缺失/未落库 · `2` 输入异常。
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from schema.models import ClaimForm, ClaimNature, OfficialClaimKind, SourceTier  # noqa: E402
from schema.store import append_records, read_records  # noqa: E402

RAW_DIRNAME = "raw"
"""原始物根目录名（`Ch9 §3.3.3`：外部文本只进 `raw/`）。"""


@dataclass(frozen=True)
class SourceSpec:
    """一条**已落盘**一手材料的真实来源标注（采集侧按来源逐条声明，非对文本做词面分类）。"""

    raw_name: str
    """`raw/` 下的文件名（`locator` 的目标，也是载荷所在）。"""

    source_id: str
    publisher_entity: str
    tier: SourceTier
    claim_nature: ClaimNature
    claim_form: ClaimForm
    official_claim_kind: OfficialClaimKind | None
    tier_basis: str
    occurred_at: datetime


def _utc(year: int, month: int, day: int) -> datetime:
    """构造 UTC 时点（发布时间一律按 UTC 零点记，避免本地时区偏移）。"""
    return datetime(year, month, day, tzinfo=timezone.utc)


MANIFEST: tuple[SourceSpec, ...] = (
    SourceSpec(
        raw_name="2025-02-26-nvidia-q4-fy2025-results.txt",
        source_id="nvidia-newsroom-q4-fy2025",
        publisher_entity="NVIDIA Corporation",
        tier=SourceTier.primary,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier_basis=(
            "发布方 = NVIDIA 公司官方新闻稿（investor.nvidia.com / nvidianews.nvidia.com），"
            "属公司一手披露（Ch6 §C.1）；内容为其自述的季度/年度经营结果。"
        ),
        occurred_at=_utc(2025, 2, 26),
    ),
    SourceSpec(
        raw_name="2024-11-20-nvidia-q3-fy2025-results.txt",
        source_id="nvidia-newsroom-q3-fy2025",
        publisher_entity="NVIDIA Corporation",
        tier=SourceTier.primary,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier_basis=(
            "发布方 = NVIDIA 公司官方新闻稿（nvidianews.nvidia.com），属公司一手披露（Ch6 §C.1）；"
            "内容为其自述的季度经营结果。"
        ),
        occurred_at=_utc(2024, 11, 20),
    ),
)
"""**来源连接描述**：逐条给出真实标注（`source_id` / 发布方 / `tier` / 三字段 / 发布日）。

★ 载荷（原文）由采集侧落到 `raw/<raw_name>`；本清单只声明"这条载荷来自哪个来源、按什么档标注"。
"""


@dataclass(frozen=True)
class SourceRecordSpec:
    """一条来源在 `facts/sources.jsonl` 的**登记**（`Ch9 §N9.3` 七字段 + `tier`）。

    `Ch9 §N9.3` 要求登记 7 项：公开入口 / 实际可获得内容 / 抓取方式 / 可预期延迟 /
    更新频率 / 访问限制 / 备选来源。本类逐项承载，**七个字段无一空缺**。
    """

    source_id: str
    public_entry: str
    """公开入口（URL）—— 抓取物的**唯一**可回溯入口。"""

    obtainable_content_type: str
    """实际可获得内容边界（`full_text` / `summary` / `snippet`）—— **如实**填，不乐观估计。"""

    crawl_method: str
    """抓取方式：`http_get`（本机 HTTP 直取）/ `webfetch`（allowlist 的 builtin 能力）。"""

    access_restriction: str
    expected_latency: str
    update_frequency: str
    fallback_source_ids: tuple[str, ...]
    tier: SourceTier
    publisher_entity: str
    occurred_at: datetime | None
    """来源自述的发布日；**确未披露**者保持 `None`（`Ch9 §2.2`：不猜测）。"""

    raw_name: str
    """抓取物在 `raw/` 的落点 —— `content_hash` 与 `observed_stats` 运行期由它现算。"""


@dataclass(frozen=True)
class QuoteSpec:
    """一条**引文级** claim：把主张绑定到 `raw/` 原文的**具体行区间**（不是整份文件）。

    与 `SourceSpec` 的差别只有一处、但关键：`locator` 指到**行区间**，
    `quote_hash = sha256(该区间文本)`（见 `_quote_segment`）——
    于是"这条主张引的是原文的哪一段"是**机械可复查**的，
    而不是"反正这一整份文件里有这个数"。

    `full_text_read` **不由本类声明**：它是 `locator_check.py` 判据 4/5 的**机械结论**
    （覆盖全篇 **且** `quote_hash == sha256(原文)` 才为 `true`）。引文级定位只覆盖片段，
    ⇒ 机械上取 `false`。这不表示"没读过原文"，而表示"**未证明**读过全文"（`G-03` 口径）。
    """

    source_id: str
    raw_name: str
    first_line: int
    last_line: int
    claim_nature: ClaimNature
    claim_form: ClaimForm
    official_claim_kind: OfficialClaimKind | None
    tier: SourceTier
    tier_basis: str
    publisher_entity: str
    occurred_at: datetime


_NV_TIER_BASIS = (
    "发布方 = NVIDIA Corporation 官方新闻稿（nvidianews.nvidia.com，公司自家 IR/newsroom）"
    "—— 属公司一手披露（Ch6 §C.1）；内容为其自述的季度经营结果。"
)
"""NVIDIA 官方新闻稿的**统一**分级依据（六季逐条复用同一依据，非逐次另立说法）。"""

_EXTERNAL_TIER_BASIS = (
    "发布方为**第三方媒体**，内容系对公司披露/第三方研究机构数据的转述与整理 —— "
    "非一手（Ch6 §C.1）；按其转述性质归 secondary_tertiary，**不得**据其内容反推升级 tier。"
)


SOURCE_RECORDS: tuple[SourceRecordSpec, ...] = (
    # ── 一手：NVIDIA 官方 newsroom ×6 ─────────────────────────────────────────
    SourceRecordSpec(
        source_id="nvidia-newsroom-q1-fy2026",
        public_entry="https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-first-quarter-fiscal-2026",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面，无登录/付费/地域限制）",
        expected_latency="季度披露后即时可得",
        update_frequency="每季度一次（公司财报发布时）",
        fallback_source_ids=("stcn-nvidia-q1-fy2027", "nvidia-newsroom-q2-fy2026"),
        tier=SourceTier.primary,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2025, 5, 28),
        raw_name="2025-05-28-nvidia-q1-fy2026-results.txt",
    ),
    SourceRecordSpec(
        source_id="nvidia-newsroom-q2-fy2026",
        public_entry="https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2026",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面，无登录/付费/地域限制）",
        expected_latency="季度披露后即时可得",
        update_frequency="每季度一次（公司财报发布时）",
        fallback_source_ids=("xinhua-nvidia-fy2026", "nvidia-newsroom-q1-fy2026"),
        tier=SourceTier.primary,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2025, 8, 27),
        raw_name="2025-08-27-nvidia-q2-fy2026-results.txt",
    ),
    SourceRecordSpec(
        source_id="nvidia-newsroom-q3-fy2026",
        public_entry="https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-third-quarter-fiscal-2026",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面，无登录/付费/地域限制）",
        expected_latency="季度披露后即时可得",
        update_frequency="每季度一次（公司财报发布时）",
        fallback_source_ids=("nvidia-newsroom-q2-fy2026", "nvidia-newsroom-q4-fy2026"),
        tier=SourceTier.primary,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2025, 11, 19),
        raw_name="2025-11-19-nvidia-q3-fy2026-results.txt",
    ),
    SourceRecordSpec(
        source_id="nvidia-newsroom-q4-fy2026",
        public_entry="https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-fourth-quarter-and-fiscal-2026",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面，无登录/付费/地域限制）",
        expected_latency="季度披露后即时可得",
        update_frequency="每季度一次（公司财报发布时）",
        fallback_source_ids=("xinhua-nvidia-fy2026", "nvidia-newsroom-q3-fy2026"),
        tier=SourceTier.primary,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2026, 2, 25),
        raw_name="2026-02-25-nvidia-q4-fy2026-results.txt",
    ),
    SourceRecordSpec(
        source_id="nvidia-newsroom-q1-fy2027",
        public_entry="https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-first-quarter-fiscal-2027",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面，无登录/付费/地域限制）",
        expected_latency="季度披露后即时可得",
        update_frequency="每季度一次（公司财报发布时）",
        fallback_source_ids=("stcn-nvidia-q1-fy2027", "nvidia-newsroom-q4-fy2026"),
        tier=SourceTier.primary,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2026, 5, 20),
        raw_name="2026-05-20-nvidia-q1-fy2027-results.txt",
    ),
    SourceRecordSpec(
        source_id="nvidia-newsroom-q2-fy2027",
        public_entry="https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-second-quarter-fiscal-2027",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面，无登录/付费/地域限制）",
        expected_latency="季度披露后即时可得",
        update_frequency="每季度一次（公司财报发布时）",
        fallback_source_ids=("nvidia-newsroom-q1-fy2027", "stcn-nvidia-q1-fy2027"),
        tier=SourceTier.primary,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2026, 8, 26),
        raw_name="2026-08-26-nvidia-q2-fy2027-results.txt",
    ),
    # ── 一手：上游存储厂商官方 newsroom ×2 ────────────────────────────────────
    SourceRecordSpec(
        source_id="sk-hynix-newsroom-hbm4e",
        public_entry="https://news.skhynix.com/en/sk-hynix-ships-samples-of-12-layer-next-gen-hbm4e-2/",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面，无登录/付费/地域限制）",
        expected_latency="产品里程碑发布后即时可得",
        update_frequency="不定期（产品里程碑）",
        fallback_source_ids=("herald-sk-hynix-hbm4-hotchips", "micron-newsroom-hbm4"),
        tier=SourceTier.primary,
        publisher_entity="SK hynix Inc.",
        occurred_at=_utc(2026, 6, 18),
        raw_name="2026-06-18-sk-hynix-hbm4e-samples.txt",
    ),
    SourceRecordSpec(
        source_id="micron-newsroom-hbm4",
        public_entry=(
            "https://investors.micron.com/news/press-release/2026/"
            "Micron-in-High-Volume-Production-of-HBM4-Designed-for-NVIDIA-Vera-Rubin-"
            "PCIe-Gen6-SSD-and-SOCAMM2-03-16-2026/default.aspx"
        ),
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面，无登录/付费/地域限制）",
        expected_latency="产品里程碑发布后即时可得",
        update_frequency="不定期（产品里程碑 / 季度财报）",
        fallback_source_ids=("sk-hynix-newsroom-hbm4e", "herald-sk-hynix-hbm4-hotchips"),
        tier=SourceTier.primary,
        publisher_entity="Micron Technology, Inc.",
        occurred_at=_utc(2026, 3, 16),
        raw_name="2026-03-16-micron-hbm4-volume-production.txt",
    ),
    # ── 一手：TSMC 官方 IR（经 webfetch 能力取得，本机 HTTP 直取被 WAF 拒绝） ────
    SourceRecordSpec(
        source_id="tsmc-ir-monthly-revenue-2026",
        public_entry="https://investor.tsmc.com/english/monthly-revenue/2026",
        obtainable_content_type="summary",
        crawl_method="webfetch",
        access_restriction=(
            "本机直取被拒：investor.tsmc.com / pr.tsmc.com / www.tsmc.com 对本机 IP 一律 HTTP 403"
            "（WAF；urllib 与 curl 加完整浏览器请求头均 403，已实测）→ 改经 allowlist 的 "
            "builtin_capability `websearch_webfetch` 取得"
        ),
        expected_latency="每月 10 日前后披露上月营收",
        update_frequency="每月一次",
        fallback_source_ids=("nvidia-newsroom-q2-fy2027",),
        tier=SourceTier.primary,
        publisher_entity="Taiwan Semiconductor Manufacturing Company Limited",
        occurred_at=None,
        raw_name="2026-09-10-tsmc-monthly-revenue-2026.txt",
    ),
    # ── 二手：媒体转述（**明确标二手**；不进决策逻辑） ─────────────────────────
    SourceRecordSpec(
        source_id="xinhua-nvidia-fy2026",
        public_entry="https://www.news.cn/world/20260226/8e2d572e6317402aa6b5be64c3a6cefd/c.html",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面）",
        expected_latency="公司披露后 1 日内",
        update_frequency="不定期（新闻）",
        fallback_source_ids=("nvidia-newsroom-q4-fy2026",),
        tier=SourceTier.secondary_tertiary,
        publisher_entity="新华网（新华社）",
        occurred_at=_utc(2026, 2, 26),
        raw_name="2026-02-26-xinhua-nvidia-fy2026-results.txt",
    ),
    SourceRecordSpec(
        source_id="stcn-nvidia-q1-fy2027",
        public_entry="https://www.stcn.com/article/detail/3919308.html",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面）",
        expected_latency="公司披露后 1 日内",
        update_frequency="不定期（新闻）",
        fallback_source_ids=("nvidia-newsroom-q1-fy2027",),
        tier=SourceTier.secondary_tertiary,
        publisher_entity="证券时报（stcn.com）",
        occurred_at=_utc(2026, 5, 20),
        raw_name="2026-05-20-stcn-nvidia-q1-fy2027.txt",
    ),
    SourceRecordSpec(
        source_id="herald-sk-hynix-hbm4-hotchips",
        public_entry="https://biz.heraldcorp.com/article/10849578",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面；页面自述为 AI 机器翻译，准确性由发布方声明不作保证）",
        expected_latency="会后 1 日内",
        update_frequency="不定期（新闻）",
        fallback_source_ids=("sk-hynix-newsroom-hbm4e",),
        tier=SourceTier.secondary_tertiary,
        publisher_entity="The Herald Business (biz.heraldcorp.com)",
        occurred_at=_utc(2026, 8, 24),
        raw_name="2026-08-24-herald-sk-hynix-hbm4-hotchips.txt",
    ),
    SourceRecordSpec(
        source_id="ajupress-cowos-capacity",
        public_entry="https://m.ajupress.com/amp/20260105152112913",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面）",
        expected_latency="不定期",
        update_frequency="不定期（新闻）",
        fallback_source_ids=("semihub-cowos-capacity",),
        tier=SourceTier.secondary_tertiary,
        publisher_entity="Aju Press (ajupress.com)",
        occurred_at=_utc(2026, 1, 5),
        raw_name="2026-01-05-ajupress-cowos-bottleneck.txt",
    ),
    SourceRecordSpec(
        source_id="semihub-cowos-capacity",
        public_entry="https://semihub.io/en/blog/cowos-guide-4.html",
        obtainable_content_type="full_text",
        crawl_method="http_get",
        access_restriction="none（公开页面；页面**未披露发布日期**，故 occurred_at 保持 None）",
        expected_latency="不定期",
        update_frequency="不定期（博客）",
        fallback_source_ids=("ajupress-cowos-capacity",),
        tier=SourceTier.secondary_tertiary,
        publisher_entity="SemiHub (semihub.io)",
        occurred_at=None,
        raw_name="2026-09-16-semihub-cowos-supply-war-undated.txt",
    ),
)
"""来源登记清单（15 字段逐条给出，`Ch9 §N9.3` 七字段无一空缺）。"""


QUOTE_MANIFEST: tuple[QuoteSpec, ...] = (
    # ── NVIDIA 官方：季度营收 / 数据中心收入 / 分部构成 ──────────────────────
    QuoteSpec(
        source_id="nvidia-newsroom-q1-fy2026",
        raw_name="2025-05-28-nvidia-q1-fy2026-results.txt",
        first_line=59,
        last_line=59,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=_NV_TIER_BASIS,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2025, 5, 28),
    ),
    QuoteSpec(
        source_id="nvidia-newsroom-q2-fy2026",
        raw_name="2025-08-27-nvidia-q2-fy2026-results.txt",
        first_line=59,
        last_line=59,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=_NV_TIER_BASIS,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2025, 8, 27),
    ),
    QuoteSpec(
        source_id="nvidia-newsroom-q3-fy2026",
        raw_name="2025-11-19-nvidia-q3-fy2026-results.txt",
        first_line=60,
        last_line=60,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=_NV_TIER_BASIS,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2025, 11, 19),
    ),
    QuoteSpec(
        source_id="nvidia-newsroom-q4-fy2026",
        raw_name="2026-02-25-nvidia-q4-fy2026-results.txt",
        first_line=60,
        last_line=60,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=_NV_TIER_BASIS,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2026, 2, 25),
    ),
    QuoteSpec(
        source_id="nvidia-newsroom-q1-fy2027",
        raw_name="2026-05-20-nvidia-q1-fy2027-results.txt",
        first_line=59,
        last_line=59,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=_NV_TIER_BASIS,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2026, 5, 20),
    ),
    QuoteSpec(
        source_id="nvidia-newsroom-q1-fy2027",
        raw_name="2026-05-20-nvidia-q1-fy2027-results.txt",
        first_line=68,
        last_line=68,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=_NV_TIER_BASIS,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2026, 5, 20),
    ),
    QuoteSpec(
        source_id="nvidia-newsroom-q2-fy2027",
        raw_name="2026-08-26-nvidia-q2-fy2027-results.txt",
        first_line=59,
        last_line=59,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=_NV_TIER_BASIS,
        publisher_entity="NVIDIA Corporation",
        occurred_at=_utc(2026, 8, 26),
    ),
    # ── 上游存储：SK hynix / Micron 官方 ────────────────────────────────────
    QuoteSpec(
        source_id="sk-hynix-newsroom-hbm4e",
        raw_name="2026-06-18-sk-hynix-hbm4e-samples.txt",
        first_line=60,
        last_line=60,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=(
            "发布方 = SK hynix Inc. 官方 newsroom（news.skhynix.com）—— 公司一手产品披露"
            "（Ch6 §C.1）；内容为其自述的产品规格与送样进度。"
        ),
        publisher_entity="SK hynix Inc.",
        occurred_at=_utc(2026, 6, 18),
    ),
    QuoteSpec(
        source_id="micron-newsroom-hbm4",
        raw_name="2026-03-16-micron-hbm4-volume-production.txt",
        first_line=23,
        last_line=23,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=(
            "发布方 = Micron Technology, Inc. 官方投资者关系新闻稿（investors.micron.com）"
            "—— 公司一手产品披露（Ch6 §C.1）。"
        ),
        publisher_entity="Micron Technology, Inc.",
        occurred_at=_utc(2026, 3, 16),
    ),
    # ── 一手：TSMC 月度营收（webfetch 取得；页未披露发布日 → occurred_at 保持 None） ─
    QuoteSpec(
        source_id="tsmc-ir-monthly-revenue-2026",
        raw_name="2026-09-10-tsmc-monthly-revenue-2026.txt",
        first_line=52,
        last_line=52,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=(
            "发布方 = TSMC 官方投资者关系网站（investor.tsmc.com）的月度营收页 —— 公司一手披露"
            "（Ch6 §C.1）。★ `occurred_at` 保持 None：该页**未披露**发布日期，`Ch9 §2.2` 规定"
            "来源未披露时保持 None 合法，**不**用抓取日或惯例推断冒充发布日期。"
        ),
        publisher_entity="Taiwan Semiconductor Manufacturing Company Limited",
        occurred_at=None,
    ),
    QuoteSpec(
        source_id="tsmc-ir-monthly-revenue-2026",
        raw_name="2026-09-10-tsmc-monthly-revenue-2026.txt",
        first_line=50,
        last_line=52,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.original_investigation,
        official_claim_kind=OfficialClaimKind.occurred_fact,
        tier=SourceTier.primary,
        tier_basis=(
            "发布方 = TSMC 官方投资者关系网站（investor.tsmc.com）的月度营收页 —— 公司一手披露"
            "（Ch6 §C.1）。★ 本条与上一条引同一页，但区间含**月份标签行 `Aug.`**："
            "上一条（L52 单行）只有两个裸数字，读者无法从引文本身判断它指哪个月 —— "
            "该引文作为证据是**不自洽**的（信息量不足），故补此更完整区间。"
            "两条都已入真源（追加式真源不可回删），此处如实说明二者关系，不掩盖。"
            "★ `occurred_at` 保持 None，理由同上（该页未披露发布日期）。"
        ),
        publisher_entity="Taiwan Semiconductor Manufacturing Company Limited",
        occurred_at=None,
    ),
    # ── 二手：媒体转述 ──────────────────────────────────────────────────────
    QuoteSpec(
        source_id="xinhua-nvidia-fy2026",
        raw_name="2026-02-26-xinhua-nvidia-fy2026-results.txt",
        first_line=20,
        last_line=20,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.citation,
        official_claim_kind=None,
        tier=SourceTier.secondary_tertiary,
        tier_basis=_EXTERNAL_TIER_BASIS,
        publisher_entity="新华网（新华社）",
        occurred_at=_utc(2026, 2, 26),
    ),
    QuoteSpec(
        source_id="stcn-nvidia-q1-fy2027",
        raw_name="2026-05-20-stcn-nvidia-q1-fy2027.txt",
        first_line=104,
        last_line=104,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.citation,
        official_claim_kind=None,
        tier=SourceTier.secondary_tertiary,
        tier_basis=_EXTERNAL_TIER_BASIS,
        publisher_entity="证券时报（stcn.com）",
        occurred_at=_utc(2026, 5, 20),
    ),
    QuoteSpec(
        source_id="herald-sk-hynix-hbm4-hotchips",
        raw_name="2026-08-24-herald-sk-hynix-hbm4-hotchips.txt",
        first_line=46,
        last_line=46,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.citation,
        official_claim_kind=None,
        tier=SourceTier.secondary_tertiary,
        tier_basis=_EXTERNAL_TIER_BASIS,
        publisher_entity="The Herald Business (biz.heraldcorp.com)",
        occurred_at=_utc(2026, 8, 24),
    ),
    QuoteSpec(
        source_id="ajupress-cowos-capacity",
        raw_name="2026-01-05-ajupress-cowos-bottleneck.txt",
        first_line=23,
        last_line=23,
        claim_nature=ClaimNature.interpretation,
        claim_form=ClaimForm.citation,
        official_claim_kind=None,
        tier=SourceTier.secondary_tertiary,
        tier_basis=(
            _EXTERNAL_TIER_BASIS
            + " ★ 该行内容是媒体**转述 TrendForce 的产能估算**（非任何公司自述的已发生事实），"
            "故 claim_nature 取 interpretation 而非 fact。"
        ),
        publisher_entity="Aju Press (ajupress.com)",
        occurred_at=_utc(2026, 1, 5),
    ),
    QuoteSpec(
        source_id="semihub-cowos-capacity",
        raw_name="2026-09-16-semihub-cowos-supply-war-undated.txt",
        first_line=255,
        last_line=255,
        claim_nature=ClaimNature.interpretation,
        claim_form=ClaimForm.citation,
        official_claim_kind=None,
        tier=SourceTier.secondary_tertiary,
        tier_basis=(
            _EXTERNAL_TIER_BASIS
            + " ★ 该行是行业博客**汇总产能估算**（页面未披露发布日期），故 claim_nature 取"
            " interpretation；`occurred_at` 保持 None。"
        ),
        publisher_entity="SemiHub (semihub.io)",
        occurred_at=None,
    ),
)
"""引文级主张清单：每条绑定 `raw/<file>` 的**具体行区间**（`quote_hash` 由该区间现算）。"""



def _sha256(text: str) -> str:
    """`quote_hash` 的来源：`sha256(UTF-8 原文)`（与 `scripts.guard.executor` 同源）。

    ★ **机械含义（唯一）**：`quote_hash = sha256(locator 所指的 raw/ 行区间文本)`。
      `locator` 覆盖**整份**原文时退化为 `sha256(整份原文)` —— 即 `executor._derive_quote_hash`
      的取值。故两处**同一公式**，非两条校验路径（`G-06`）。
      区间文本的取法见 `_quote_segment`（含行尾换行，逐字切片）。
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _quote_segment(text: str, first_line: int, last_line: int) -> str:
    """取 `raw/` 文本的**行区间逐字切片**（1-based 闭区间，**保留行尾换行**）。

    这是 `quote_hash` 的**唯一**区间取法（`quote_provenance_guard` 与之逐字同源）：
    `"".join(text.splitlines(keepends=True)[first-1:last])`。
    `first==1 and last==总行数` 时结果**恒等于** `text` 本身 —— 故既有"全篇覆盖"的 claim
    仍按同一公式得出其 `quote_hash`（实测：真源现有 5 行的 `quote_hash` 均等于 `sha256(整份原文)`）。
    """
    return "".join(text.splitlines(keepends=True)[first_line - 1 : last_line])


def _next_recorded_seq(root: Path, stem: str = "claims") -> int:
    """`facts/<stem>.jsonl` 现有最大 `recorded_seq` + 1（追加式真源据此区分版本）。"""
    numeric = [
        row.get("recorded_seq")
        for row in read_records(root, stem)
        if isinstance(row.get("recorded_seq"), int)
    ]
    return (max(numeric) if numeric else 0) + 1


def _existing_claim_ids(root: Path) -> set[str]:
    """已入库的 `claim_id` 集合（供幂等跳过）。"""
    return {
        str(row.get("claim_id"))
        for row in read_records(root, "claims")
        if row.get("claim_id")
    }


def _read_raw(root: Path, raw_name: str) -> str:
    """读 `raw/<raw_name>`；缺失即抛 `FileNotFoundError`（**不返回空串兜底**）。"""
    path = root / RAW_DIRNAME / raw_name
    if not path.is_file():
        raise FileNotFoundError(f"raw 原文缺失: {raw_name}")
    return path.read_text(encoding="utf-8")


def register_sources(
    root: str | Path, *, now: datetime | None = None
) -> tuple[list[str], list[tuple[str, str]]]:
    """把 `SOURCE_RECORDS` 登记进 `facts/sources.jsonl`（按 `source_id` 幂等）。

    `content_hash` / `observed_stats` **运行期由 `raw/` 落盘物现算**（不从清单手填）——
    这样"登记的内容哈希"与"实际落盘物"不可能对不上（手填正是漂移的来源）。
    """
    from schema.models import Source

    root_path = Path(root)
    processed_at = now or datetime.now(timezone.utc)
    existing = {str(row.get("source_id", "")) for row in read_records(root_path, "sources")}
    created: list[str] = []
    failed: list[tuple[str, str]] = []
    for spec in SOURCE_RECORDS:
        if spec.source_id in existing:
            continue
        try:
            text = _read_raw(root_path, spec.raw_name)
        except FileNotFoundError as exc:
            failed.append((spec.source_id, str(exc)))
            continue
        record = Source(
            source_id=spec.source_id,
            public_entry=spec.public_entry,
            obtainable_content_type=spec.obtainable_content_type,
            crawl_method=spec.crawl_method,
            expected_latency=spec.expected_latency,
            update_frequency=spec.update_frequency,
            access_restriction=spec.access_restriction,
            fallback_source_ids=list(spec.fallback_source_ids),
            tier=spec.tier,
            content_hash=_sha256(text),
            observed_stats={
                "raw_name": spec.raw_name,
                "line_count": len(text.splitlines()),
                "bytes": len(text.encode("utf-8")),
            },
            first_seen_at=processed_at,
            analyzed_at=processed_at,
            recorded_seq=_next_recorded_seq(root_path, "sources"),
            occurred_at=spec.occurred_at,
            published_at=spec.occurred_at,
            effective_from=None,
            backfilled_at=(
                processed_at
                if spec.occurred_at is not None and spec.occurred_at.date() < processed_at.date()
                else None
            ),
        )
        append_records(root_path, "sources", [record])
        existing.add(spec.source_id)
        created.append(spec.source_id)
    return created, failed


def collect_quotes(
    root: str | Path, *, now: datetime | None = None
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]]]:
    """把 `QUOTE_MANIFEST` 的**引文级**主张摄入 `facts/claims.jsonl`。

    返回 `([(claim_id, locator, 引文原文)], [(source_id, 原因)])`。

    - `raw/` 原文缺失 / 行区间越界 / 区间为空 → 归入失败（**不**凭空生成 claim）；
    - 同一 `claim_id` 已存在 → 跳过（幂等）；
    - `quote_hash = sha256(locator 所指区间文本)`（`_quote_segment`，**唯一**区间取法）；
    - `full_text_read` **不在此声明**：由 `locator_check.py` 的机械判据给出（引文级定位
      只覆盖片段 ⇒ 其结论为 `false`，即"未证明读过全文"，`G-03`）。
    """
    from scripts.guard.claims import build_claim

    root_path = Path(root)
    processed_at = now or datetime.now(timezone.utc)
    existing = _existing_claim_ids(root_path)
    created: list[tuple[str, str, str]] = []
    failed: list[tuple[str, str]] = []
    for spec in QUOTE_MANIFEST:
        try:
            text = _read_raw(root_path, spec.raw_name)
        except FileNotFoundError as exc:
            failed.append((spec.source_id, str(exc)))
            continue
        total = len(text.splitlines())
        if not (1 <= spec.first_line <= spec.last_line <= total):
            failed.append(
                (
                    spec.source_id,
                    f"行区间越界: L{spec.first_line}-L{spec.last_line}（{spec.raw_name} 共 {total} 行）",
                )
            )
            continue
        segment = _quote_segment(text, spec.first_line, spec.last_line)
        if not segment.strip():
            failed.append(
                (spec.source_id, f"行区间为空行: L{spec.first_line}-L{spec.last_line}（{spec.raw_name}）")
            )
            continue
        quote_hash = _sha256(segment)
        claim_id = f"claim-{spec.source_id}-{quote_hash[:12]}"
        if claim_id in existing:
            continue
        locator = f"{RAW_DIRNAME}/{spec.raw_name}#L{spec.first_line}-L{spec.last_line}"
        claim = build_claim(
            claim_id=claim_id,
            source_id=spec.source_id,
            quote_hash=quote_hash,
            claim_nature=spec.claim_nature,
            claim_form=spec.claim_form,
            tier=spec.tier,
            first_seen_at=processed_at,
            analyzed_at=processed_at,
            recorded_seq=_next_recorded_seq(root_path, "claims"),
            locator=locator,
            occurred_at=spec.occurred_at,
            published_at=spec.occurred_at,
            effective_from=None,
            backfilled_at=(
                processed_at
                if spec.occurred_at is not None and spec.occurred_at.date() < processed_at.date()
                else None
            ),
            official_claim_kind=spec.official_claim_kind,
            tier_basis=spec.tier_basis,
            publisher_entity=spec.publisher_entity,
        )
        append_records(root_path, "claims", [claim])
        existing.add(claim_id)
        created.append((claim_id, locator, segment))
    return created, failed


def collect(
    root: str | Path, *, now: datetime | None = None
) -> tuple[list[str], list[tuple[str, str]]]:
    """把 `MANIFEST` 里的**已落盘一手材料**按真实标注摄入 claims。

    返回 `(新建的 claim_id 列表, 失败列表[(source_id, 原因)])`。

    - 原文缺失 → 归入失败（**不**凭空生成 claim、**不**静默略过）；
    - 同一 `claim_id` 已存在 → 跳过（幂等）；
    - 每条 claim 的 system_time 三元组在**采集层显式赋值**（本层产生 `now()`）。
    """
    from scripts.guard.claims import build_claim

    root_path = Path(root)
    processed_at = now or datetime.now(timezone.utc)
    existing = _existing_claim_ids(root_path)
    created: list[str] = []
    failed: list[tuple[str, str]] = []
    for spec in MANIFEST:
        path = root_path / RAW_DIRNAME / spec.raw_name
        if not path.is_file():
            failed.append((spec.source_id, f"raw 原文缺失: {spec.raw_name}"))
            continue
        text = path.read_text(encoding="utf-8")
        quote_hash = _sha256(text)
        claim_id = f"claim-{spec.source_id}-{quote_hash[:12]}"
        if claim_id in existing:
            continue
        locator = f"{RAW_DIRNAME}/{spec.raw_name}#L1-L{len(text.splitlines())}"
        backfilled_at = (
            processed_at if spec.occurred_at.date() < processed_at.date() else None
        )
        claim = build_claim(
            claim_id=claim_id,
            source_id=spec.source_id,
            quote_hash=quote_hash,
            claim_nature=spec.claim_nature,
            claim_form=spec.claim_form,
            tier=spec.tier,
            first_seen_at=processed_at,
            analyzed_at=processed_at,
            recorded_seq=_next_recorded_seq(root_path),
            locator=locator,
            occurred_at=spec.occurred_at,
            published_at=spec.occurred_at,
            effective_from=None,
            backfilled_at=backfilled_at,
            official_claim_kind=spec.official_claim_kind,
            tier_basis=spec.tier_basis,
            publisher_entity=spec.publisher_entity,
        )
        append_records(root_path, "claims", [claim])
        existing.add(claim_id)
        created.append(claim_id)
    return created, failed


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。退出码：`0` 成功/均已入库 · `1` 有材料缺失 · `2` 输入异常。"""
    parser = argparse.ArgumentParser(
        prog="real_collector.py",
        description="阶段② 真实连接器：把 raw/ 一手材料按真实来源标注摄入 facts/",
    )
    parser.add_argument("code_root", nargs="?", default=".", help="代码工程根（system/）")
    args = parser.parse_args(argv)

    try:
        created, failed = collect(Path(args.code_root))
        registered, src_failed = register_sources(Path(args.code_root))
        quotes, quote_failed = collect_quotes(Path(args.code_root))
    except (FileNotFoundError, OSError) as exc:
        print(f"[INPUT-ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("== real_collector.py ==")
    for claim_id in created:
        print(f"  created claim(全篇级): {claim_id}")
    for source_id in registered:
        print(f"  registered source: {source_id}")
    for claim_id, locator, segment in quotes:
        preview = segment.strip().splitlines()[0] if segment.strip() else ""
        print(f"  created claim(引文级): {claim_id}  [{locator}]  {preview[:80]}")
    failures = failed + src_failed + quote_failed
    for source_id, why in failures:
        print(f"  FAILED: {source_id}: {why}")
    if not failures and not created and not registered and not quotes:
        print("  NO_NEW_RECORDS：清单材料均已入库（幂等，无新增）")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
