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


def _sha256(text: str) -> str:
    """`quote_hash` 的来源：`sha256(UTF-8 原文)`（与 `scripts.guard.executor` 同源）。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _next_recorded_seq(root: Path) -> int:
    """`facts/claims.jsonl` 现有最大 `recorded_seq` + 1（追加式真源据此区分版本）。"""
    numeric = [
        row.get("recorded_seq")
        for row in read_records(root, "claims")
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
        description="阶段② 真实连接器：把 raw/ 一手材料按真实来源标注摄入 facts/claims.jsonl",
    )
    parser.add_argument("code_root", nargs="?", default=".", help="代码工程根（system/）")
    args = parser.parse_args(argv)

    try:
        created, failed = collect(Path(args.code_root))
    except (FileNotFoundError, OSError) as exc:
        print(f"[INPUT-ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("== real_collector.py ==")
    for claim_id in created:
        print(f"  created claim: {claim_id}")
    for source_id, why in failed:
        print(f"  FAILED: {source_id}: {why}")
    if not created and not failed:
        print("  NO_NEW_CLAIMS：MANIFEST 材料均已入库（幂等，无新增）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
