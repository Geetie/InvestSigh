"""`research_ingest.py` —— 「研究清单」编译器（把会话内模型侧产出**经唯一写入口**落真源）。

★ 本文件测的是**机制**（不是研究内容）：引文定位 / 引文指纹 / 期间桶 / 指标 / 事件类型 /
  行幂等 / 唯一写入口 / 未知键拒绝 / 导出-导入往返。

★★ 为什么这些机制值得单测（`gap-mcp-fetch-not-reproducible` 的扩大版）：

  2026-09-17 冷启动端到端那 395 行真源，原本靠 `.workbuddy/seed/` 下 7 个**不入版本库**的
  会话脚本落库；脚本之间 `locator` / `period_bucket` / `metric_of` / `event_type_of`
  **各写了 2~4 份且已漂移**（`_EARNINGS_METRICS` 少 6 个词元、`_PERIOD_RE` 少一种形态）。
  漂移的后果不是报错，而是**同一次运行里不同来源的主张拿到不同的 `event_type`** ——
  而它是独立佐证指纹（`Ch9 §3.4.7`）的组成项 ⇒ **影响结论强度且无人会发觉**。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from scripts.ingest.research_ingest import (
    MANIFEST_VERSION,
    ResearchIngestError,
    TABLES,
    claim_id_of,
    compile_manifest,
    event_type_of,
    export_manifest,
    ingest_research_file,
    locate_quote,
    metric_of,
    period_bucket,
    quote_hash_of_located,
)

RAW_NAME = "2026-08-26-demo-raw.txt"
"""夹具原文的相对名（落在 `code_root/raw/` 下）。"""

RAW_TEXT = (
    "NVIDIA today reported revenue for the second quarter of fiscal 2027.\n"
    "Data Center revenue of $89.0\n"
    "billion, up 117% from a year ago.\n"
    "\n"
    "第二季度收入达 962 亿美元,较去年同期增长 106%,\n"
    "环比增长约 20%。\n"
    "GAAP and non-GAAP gross margins were both 75.0%.\n"
)
"""★ 行布局是**刻意**的：英文引文跨行处原文**有**空格（L2→L3 折行）、
中文引文跨行处原文**没有**空格（L5→L6 折行）⇒ 两种归一化各有用武之地。"""

EN_QUOTE = "Data Center revenue of $89.0 billion, up 117%"
"""跨 L2–L3 的英文引文：需要"行间插空格"的归一化。"""

CJK_QUOTE = "第二季度收入达 962 亿美元,较去年同期增长 106%,环比增长约 20%。"
"""跨 L5–L6 的中文引文：需要"行间不插空格"的归一化。"""


def _seed_raw(code_root: Path) -> None:
    (code_root / "raw" / RAW_NAME).write_text(RAW_TEXT, encoding="utf-8")


def _claim(source_key: str = "src-demo", key: str = "dc-rev-q2fy27", quote: str = EN_QUOTE) -> dict:
    """主张的**最小形式**（只给派生输入 —— `claim_id` / `quote_hash` / `locator` 都由机制算）。"""
    return {
        "source_key": source_key,
        "key": key,
        "quote": quote,
        "raw_relpath": RAW_NAME,
        "source_id": source_key,
        "claim_nature": "fact",
        "claim_form": "original_investigation",
        "tier": "primary",
    }


def _manifest(tables: dict, *, run_date: str = "2026-09-17") -> dict:
    return {
        "manifest_version": MANIFEST_VERSION,
        "run_date": run_date,
        "system_time": "2026-09-17T08:47:00+00:00",
        "tables": tables,
    }


# ═══════════════════════ 一、引文定位（两种归一化） ═══════════════════════


def test_locate_quote_spans_lines_with_space_join(code_root: Path) -> None:
    """英文引文跨行（原文该处**有**空格）→ 定位到 L2-L3。"""
    _seed_raw(code_root)
    assert locate_quote(code_root, RAW_NAME, EN_QUOTE) == f"raw/{RAW_NAME}#L2-L3"


def test_locate_quote_spans_lines_without_space_join(code_root: Path) -> None:
    """中文引文跨行（原文该处**无**空格）→ 定位到 L5-L6（只有"去空白"归一化能对上）。"""
    _seed_raw(code_root)
    assert locate_quote(code_root, RAW_NAME, CJK_QUOTE) == f"raw/{RAW_NAME}#L5-L6"


def test_locate_quote_single_line(code_root: Path) -> None:
    _seed_raw(code_root)
    got = locate_quote(code_root, RAW_NAME, "GAAP and non-GAAP gross margins were both 75.0%.")
    assert got == f"raw/{RAW_NAME}#L7-L7"


def test_locate_quote_fails_loudly_on_miss(code_root: Path) -> None:
    """**响亮失败**（不静默返回一个坏 locator）：两种归一化都试过仍无命中 ⇒ 抛。"""
    _seed_raw(code_root)
    with pytest.raises(ResearchIngestError, match="LOCATOR-MISS"):
        locate_quote(code_root, RAW_NAME, "这句话根本不在原文里")


def test_locate_quote_fails_loudly_when_raw_missing(code_root: Path) -> None:
    with pytest.raises(ResearchIngestError, match="不是常规文件"):
        locate_quote(code_root, "no-such-file.txt", EN_QUOTE)


# ═══════════════════════ 二、★ 引文指纹的契约（本次最实质的修复） ═══════════════════════


def test_quote_hash_is_sha256_of_located_segment_not_of_quote_string(code_root: Path) -> None:
    """★★ `quote_hash` = `sha256(locator 区间**逐字切片**)` —— **不是**归一化引文串的哈希。

    ★ 这是原会话脚本**算错**的那一处：它们算 `sha256(" ".join(quote.split()))`，
      于是数据从一开始就不满足 `quote_provenance_guard` 的契约，
      要靠 `seed_repair_and_finish.py` 里一整段"引文指纹修复"事后重算。

    本用例把两个**不同**的值都算出来并断言机制取的是**切片**那个 ——
    没有这一条，"产出即正确"就退化成"事后修好就算了"。
    """
    import hashlib

    _seed_raw(code_root)
    locator = locate_quote(code_root, RAW_NAME, EN_QUOTE)
    derived = quote_hash_of_located(code_root, locator)

    segment = "Data Center revenue of $89.0\nbillion, up 117% from a year ago.\n"   # L2-L3 逐字（含换行）
    assert derived == hashlib.sha256(segment.encode("utf-8")).hexdigest()

    wrong = hashlib.sha256(" ".join(EN_QUOTE.split()).encode("utf-8")).hexdigest()
    assert derived != wrong, "指纹必须是切片哈希，不是归一化引文哈希（原会话脚本的错法）"


def test_declared_quote_hash_mismatch_is_rejected(code_root: Path) -> None:
    """清单若自带一个**错**的 `quote_hash` ⇒ 拒（让"事后修复"变成"产出即正确"）。"""
    _seed_raw(code_root)
    row = _claim()
    row["quote_hash"] = "0" * 64
    with pytest.raises(ResearchIngestError, match="quote_hash"):
        compile_manifest(code_root, _manifest({"claims": [row]}))


def test_declared_locator_inconsistent_with_quote_is_rejected(code_root: Path) -> None:
    """清单给的 `locator` 与按 `quote` 重新定位的结果不同 ⇒ 拒（两者必须指向同一条内容）。"""
    _seed_raw(code_root)
    row = _claim()
    row["locator"] = f"raw/{RAW_NAME}#L7-L7"
    with pytest.raises(ResearchIngestError, match="不一致"):
        compile_manifest(code_root, _manifest({"claims": [row]}))


def test_segment_matches_guard_implementation() -> None:
    """★ **元断言**（本仓"三份同公式并存"的漂移由机器兜住）。

    `_segment` 的公式在**三处**并存且**有意**独立（判据不得复用被验证方的实现）：
      - `scripts/ingest/research_ingest.py::_segment`（本模块，产出侧）
      - `scripts/checks/quote_provenance_guard.py::_segment`（守卫侧，**刻意**独立）
      - `scripts/guard/executor.py::_quote_segment`（采集侧）

    "公式相同"这件事**必须被机器检查** —— 任何一处改了公式而另两处没跟上，
    都会表现为"守卫与产出方各说各话"，且**症状是假红**。本用例是那个检查点。
    """
    from scripts.checks.quote_provenance_guard import _segment as guard_segment
    from scripts.ingest.research_ingest import _segment as ingest_segment

    text = RAW_TEXT
    line_count = len(text.splitlines(keepends=True))
    cases = [(1, 1), (2, 3), (5, 6), (7, 7), (1, line_count), (4, 4)]
    for first, last in cases:
        assert ingest_segment(text, first, last) == guard_segment(text, first, last), (
            f"L{first}-L{last}：产出侧与守卫侧的切片公式已不一致"
        )


# ═══════════════════════ 三、期间 / 指标 / 事件类型（两份会话实现的**并集**） ═══════════


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("rev-q2fy27", "FY2027Q2"),          # 两份实现都认
        ("rev-q2fy27", "FY2027Q2"),
        ("rev-q2-2026", "CY2026Q2"),         # ★ 只有 `seed_research_structure` 认（并集后都认）
        ("rev-q2 fy27", "FY2027Q2"),         # ★ 带空格的形态
        ("rev-fy27", "FY2027"),
        ("dc-rev-q1fy27", "FY2027Q1"),
        ("no-period-token", "undated"),
    ],
)
def test_period_bucket_is_the_union_of_both_seed_implementations(key: str, expected: str) -> None:
    assert period_bucket(key) == expected


@pytest.mark.parametrize("key", ["rev-q2fy27", "rev-q2-2026", "rev-q2 fy27"])
def test_metric_strips_period_and_restate_prefix(key: str) -> None:
    """`metric_of` 去掉期间词元与 `restate-` ⇒ **转述与其根落在同一指标上**。"""
    assert metric_of(key) == "rev"
    assert metric_of(f"restate-{key}") == "rev", "转述必须与根同指标（否则独立佐证计数被污染）"


def test_metric_override_wins() -> None:
    assert metric_of("dc-rev-q2fy27", "dc-rev") == "dc-rev"


@pytest.mark.parametrize(
    ("metric", "expected"),
    [
        ("rev", "earnings"),
        ("gm", "earnings"),
        ("dc-rev", "earnings"),
        # ★ 以下 6 个只有 `seed_research_structure` 的元组里有 —— 并集之前，
        #   同样的 metric 在两个脚本下会拿到**不同**的 event_type。
        ("azure", "earnings"),
        ("azure-growth", "earnings"),
        ("rpo", "earnings"),
        ("mcloud", "earnings"),
        ("hpc", "earnings"),
        ("node-mix", "earnings"),
        ("capex", "earnings"),
        ("guide-rev", "guidance"),
        ("anthropic-2gw", "guidance"),
        ("msft-azure-helios", "guidance"),
        ("supply-commitments", "supply"),
        ("total-commitments", "supply"),
        ("vr-full-production", "product"),
        ("reporting-framework", "product"),
        ("something-else", "other"),
    ],
)
def test_event_type_covers_both_seed_tuples(metric: str, expected: str) -> None:
    assert event_type_of(metric) == expected


def test_claim_id_construction_is_single_sourced() -> None:
    """`claim_id_of` 是唯一构造式 —— 引用与定义不可能拼出不同的串。"""
    assert claim_id_of("src-demo", "rev-q2fy27") == "claim-src-demo-rev-q2fy27"


# ═══════════════════════ 四、编译：派生 / 幂等 / 拒错 ═══════════════════════


def _compiled_claim(code_root: Path) -> dict:
    report = compile_manifest(code_root, _manifest({"claims": [_claim()]}))
    assert report.rows_written == 1, report.render()
    rows = [
        json.loads(line)
        for line in (code_root / "facts" / "claims.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    return rows[0]


def test_compile_derives_id_locator_hash_and_capability(code_root: Path) -> None:
    """最小输入 ⇒ 机制补齐 `claim_id` / `locator` / `quote_hash` / `impact_capability` 三键。"""
    _seed_raw(code_root)
    row = _compiled_claim(code_root)
    assert row["claim_id"] == "claim-src-demo-dc-rev-q2fy27"
    assert row["locator"] == f"raw/{RAW_NAME}#L2-L3"
    assert row["quote_hash"] == quote_hash_of_located(code_root, row["locator"])
    cap = row["impact_capability"]
    assert cap["metric"] == "dc-rev"
    assert cap["period_bucket"] == "FY2027Q2"
    assert cap["event_type"] == "earnings"
    assert row["recorded_seq"] == 1
    assert row["first_seen_at"] == "2026-09-17T08:47:00Z"


def test_reimport_is_idempotent(code_root: Path) -> None:
    """重跑同一份清单 ⇒ 一行不写、全部计入 `skipped`（两集合**分开**，`Ch9 §3.5`）。

    ★ id 里的 `#1` 是**出现序**（该业务键的第 1 行）—— 追加式真源里同一主键可以有**多行**
      （它们就是版本序列），故幂等键必须是"主键 + 出现序"，否则**首跑就会把第 2 个版本
      当重复丢掉**（实测形态：`facts/drivers.jsonl` 18 行 / 9 个不同 `driver_id`）。
    """
    _seed_raw(code_root)
    first = compile_manifest(code_root, _manifest({"claims": [_claim()]}))
    assert first.rows_written == 1 and first.rows_skipped == 0
    second = compile_manifest(code_root, _manifest({"claims": [_claim()]}))
    assert second.rows_written == 0 and second.rows_skipped == 1
    assert second.written == {}
    assert second.skipped == {"claims": ["claim-src-demo-dc-rev-q2fy27#1"]}


def test_dry_run_writes_nothing(code_root: Path) -> None:
    """`dry_run` **必须真的不写盘**（只算"将写入/将跳过"）。"""
    _seed_raw(code_root)
    report = compile_manifest(code_root, _manifest({"claims": [_claim()]}), dry_run=True)
    assert report.rows_written == 1, "应报出'将写入 1 行'"
    assert (code_root / "facts" / "claims.jsonl").read_text(encoding="utf-8").strip() == "", (
        "dry_run 却写了盘"
    )


def test_unknown_key_is_rejected_and_all_extras_listed(code_root: Path) -> None:
    """★ 未知键 ⇒ 拒，且**一次性列出全部**多余键（`extra="forbid"` 只报第一个）。

    实测价值：`Baseline.version_kind` 那类"契约缺位"缺陷在此处一眼可见，
    不必靠"改一个再跑一次"逐个试。
    """
    _seed_raw(code_root)
    row = _claim()
    row["version_kind"] = "forecast_revision"
    row["totally_made_up"] = 1
    with pytest.raises(ResearchIngestError) as exc:
        compile_manifest(code_root, _manifest({"claims": [row]}))
    message = str(exc.value)
    assert "extra=forbid" in message
    assert "totally_made_up" in message


def test_manifest_version_mismatch_is_rejected(code_root: Path) -> None:
    """版本不符 ⇒ 拒（**不静默按旧版解析** —— 结构性差异会被读成"清单写错"）。"""
    _seed_raw(code_root)
    path = code_root / "raw" / "inbox" / "research_manifest_x.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"manifest_version": 999, "tables": {}}), encoding="utf-8")
    with pytest.raises(ResearchIngestError, match="版本"):
        ingest_research_file(code_root, path)


def test_ungoverned_table_is_rejected(code_root: Path) -> None:
    """清单含**本模块不管辖**的表（如 `prices`）⇒ 拒（各自有唯一写入方，不得代写）。"""
    _seed_raw(code_root)
    path = code_root / "raw" / "inbox" / "research_manifest_y.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_manifest({"prices": [{"snapshot_id": "x"}]})), encoding="utf-8"
    )
    with pytest.raises(ResearchIngestError, match="不管辖"):
        ingest_research_file(code_root, path)


def test_all_governed_tables_are_declared_once() -> None:
    """元断言：`TABLES` 里不得有重复 stem（清单是唯一真源，重复即"一处改另一处不改"）。"""
    stems = [spec.stem for spec in TABLES]
    assert len(stems) == len(set(stems)), stems


def test_manifest_roundtrip_preserves_business_content(code_root: Path) -> None:
    """★★ **往返等价**：导出 → 清空 → 只用本模块重跑 → 业务内容逐字相同。

    这是"内化后的机制真的能重建会话产出"的**唯一机器证明**（`B-3` 的验收判据）。

    ★ 两类**预期内**的差异（各自有理由，不是缺陷）：
      1. `recorded_seq` —— **机制分配的版本水位**（导出时剥离、导入时重算）。
         保证的不是"逐字相等"，而是"**按业务键取 recorded_seq 最大者**取到同一行"
         （这正是 `Ch9 §3.4.1` 的用法）。故比对时排除该键。
      2. 清单里为空的 `first_seen_at` 会被**补全**（`Ch9 §2.2`：system_time 永不未知）。
         本夹具显式给出 `system_time`，故两轮取值相同、不构成差异。
    """
    _seed_raw(code_root)
    tables = {
        "companies": [{"company_id": "company-demo", "legal_name": "Demo Corp"}],
        "sources": [
            {
                "source_id": "src-demo",
                "public_entry": "https://example.invalid/demo",
                "obtainable_content_type": "full_text",
                "crawl_method": "crawl",
                "tier": "primary",
                "observed_stats": {"raw_path": f"raw/{RAW_NAME}"},
            }
        ],
        "claims": [_claim(), _claim(key="gm-q2fy27", quote="GAAP and non-GAAP gross margins were both 75.0%."),
                   _claim(key="restate-rev-q2fy27", quote=CJK_QUOTE)],
    }
    compile_manifest(code_root, _manifest(tables))

    exported = export_manifest(code_root, run_date="2026-09-17", system_time="2026-09-17T08:47:00+00:00")
    before = {
        stem: [
            {k: v for k, v in row.items() if k != "recorded_seq"}
            for row in exported["tables"].get(stem, [])
        ]
        for stem in tables
    }

    # 清空真源（只动**数据**，不动结构：22 个 JSONL 仍全部存在）
    for path in (code_root / "facts").glob("*.jsonl"):
        path.write_text("", encoding="utf-8")

    report = compile_manifest(code_root, exported)
    assert report.rows_written == sum(len(v) for v in tables.values()), report.render()

    after = {
        stem: [
            {k: v for k, v in json.loads(line).items() if k != "recorded_seq"}
            for line in (code_root / "facts" / f"{stem}.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for stem in tables
    }
    assert after == before, "导出-导入往返改变了业务内容"

    # ★ 幂等：再导入一次 ⇒ 一行不写
    again = compile_manifest(code_root, exported)
    assert again.rows_written == 0
