#!/usr/bin/env python3
"""`seed_industry_nodes.py` —— 把**附录一 44 个原型节点**迁入研究库（`Ch3 §B` / 承 `N9.2-04`）。

```
python system/scripts/ingest/seed_industry_nodes.py [code_root]
```

数据来源（**逐字取自 `02_可编辑源稿_v2.md` 附录一**，不新增、不猜测）：
> 本地文件 `ai-chain-product/lib/industry-map-data.json` 的**资料日期为 2026 年 9 月 8 日**，
> 本次**核对日期为 2026 年 9 月 14 日**。以下共 44 个公司或机构节点，
> **是原型覆盖范围，不是首批完整研究名单，也不是对其最新业务或证券资格的重新核验**。
> 节点标识**不一定等于可交易代码**；同一公司可出现在多个业务位置。

★ 五类时间语义（`Ch9 §N9.1-31/32`）：原型资料是**事后补入**的历史资料，故
  - `occurred_at` = 资料日期（2026-09-08，业务/有效时间）
  - `first_seen_at` = **补入日**（今天），**不得**回填为资料日期——否则事后信息会伪装成当时已知
  - `backfilled_at` = 补入日（显式标记为补入）
  - `analyzed_at` = 本次处理时间

★ 宪法级约束：**不填入猜测的事实数值**。节点标识≠代码 → **不在此处生成证券**；
  节点↔公司映射列为**待核验任务**（见 `registry/first_batch_relations_checklist.yaml`）。
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from schema.models import IndustryNode  # noqa: E402
from schema.store import append_records, read_records  # noqa: E402

SOURCE_ANCHOR = "源稿 §附录一"
DOCUMENT_DATE = "2026-09-08"       # 资料日期（原型 industry-map-data.json）
VERIFIED_DATE = "2026-09-14"       # 核对日期

# 源稿附录一表格逐字（产业位置 → 原型节点标识）
NODE_TABLE: dict[str, list[str]] = {
    "power_and_facilities": ["CEG", "VST", "GEV", "ETN", "PWR", "VRT"],
    "chip_architecture_and_design": ["ARM", "SNPS", "CDNS"],
    "manufacturing_and_memory": ["ASML", "AMAT", "LRCX", "KLAC", "TSM", "MU", "SK hynix", "SNDK"],
    "compute_chip_and_system": ["NVDA", "AMD", "AVGO", "MRVL", "DELL"],
    "cluster_network_and_interconnect": ["ANET", "LITE", "COHR", "CRDO"],
    "datacenter_and_cloud": ["DLR", "EQIX", "MSFT", "AMZN", "GOOGL", "ORCL", "CRWV", "NBIS"],
    "foundation_model": ["OpenAI", "Anthropic"],
    "software_platform_and_application": ["SNOW", "PLTR", "NET", "DDOG", "NOW", "CRM", "ADBE", "META"],
}

TAXONOMY_VERSION = "appendix1_v7"   # 承源稿：「已有研究版 v7 图谱 …… 重新验收」


def _node_id(position: str, label: str) -> str:
    """节点 id 由"产业位置 + 原型标识"派生（**稳定、可复现**，不等于可交易代码）。"""
    slug = label.strip().lower().replace(" ", "_")
    return f"node_{position}__{slug}"


def build_nodes(now: datetime) -> list[IndustryNode]:
    out: list[IndustryNode] = []
    for position, labels in NODE_TABLE.items():
        for label in labels:
            out.append(
                IndustryNode(
                    node_id=_node_id(position, label),
                    node_name=label,
                    taxonomy_version=TAXONOMY_VERSION,
                    # 五类时间（Ch9 §2.2 / §3.4.1）
                    occurred_at=datetime.fromisoformat(DOCUMENT_DATE + "T00:00:00+00:00"),
                    published_at=None,
                    effective_from=None,
                    first_seen_at=now,          # ★ 补入日，**不是**资料日期
                    analyzed_at=now,
                    recorded_seq=1,
                    backfilled_at=now,          # ★ 显式标记为"事后补入"
                )
            )
    return out


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else _ROOT
    now = datetime.now(timezone.utc)

    existing = {row["node_id"] for row in read_records(root, "industry_nodes")}
    nodes = [n for n in build_nodes(now) if n.node_id not in existing]

    total_expected = sum(len(v) for v in NODE_TABLE.values())
    if total_expected != 44:
        raise ValueError(f"附录一节点数应为 44，实为 {total_expected}（源稿改动？）")

    written = append_records(root, "industry_nodes", nodes)
    print(f"源锚点        : {SOURCE_ANCHOR}")
    print(f"资料日期      : {DOCUMENT_DATE} ｜ 核对日期: {VERIFIED_DATE}")
    print(f"附录一节点总数: {total_expected}")
    print(f"本次新增      : {written}")
    print(f"库内节点总数  : {len(existing) + written}")
    print(f"五类时间      : first_seen_at = 补入日 {now.date()}（**不是**资料日期 {DOCUMENT_DATE}）")
    print("未生成证券    : 节点标识≠可交易代码 → 节点↔公司映射列为待核验（不猜测）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
