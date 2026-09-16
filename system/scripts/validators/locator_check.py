#!/usr/bin/env python3
"""`locator_check.py` —— `full_text_read` 定位校验器（`Ch6 §D` · `Ch6 N6.1-11`）。

**程序拦截，非模型自觉**：本校验器**不采信**"模型自称读过全文"，而是把每条主张的定位信息
（`locator` / `quote_hash` / `full_text_read`）**机械复查回原文**，给出"定位有效 / 无效"的
**可判定**结论（`CONVENTIONS.md::R-06` ① ② —— 有明确算法、覆盖完整，不靠关键词枚举）。

## 判据（全部可判定；`raw/` 定位与"显式未披露"两种形式穷尽，其余默认拒绝）

| # | 判据 | 违例码 |
|---|---|---|
| 1 | `locator` 语法 = `raw/<relpath>#L<start>-L<end>` | `LOCATOR_UNRECOGNIZED` |
| 2 | `raw/<relpath>` 落在 `raw/` 内（拒路径穿越 / 绝对路径）且为常规文件 | `LOCATOR_ESCAPE` / `LOCATOR_UNRESOLVABLE` |
| 3 | `1 ≤ start ≤ end ≤ 行数` | `LOCATOR_RANGE_OUT_OF_BOUNDS` |
| 4 | `full_text_read=true` **仅当**定位覆盖**整份**原文 **且** `quote_hash == sha256(原文)` | `FULL_TEXT_UNPROVEN` / `QUOTE_HASH_MISMATCH` |
| 5 | `locator` 为显式"未披露"哨兵 → 允许，但**强制** `full_text_read=false` | `FULL_TEXT_UNPROVEN` |
| 6 | 三字段维度不同（`claim_nature` / `claim_form` / `official_claim_kind`），`official_claim_kind` **仅适用** `tier=primary` | `CLAIM_SCHEMA_INVALID` / `OFFICIAL_KIND_TIER_MISMATCH` |
| 7 | 来源 `obtainable_content_type` 非全文可获取时**不得**出"读过全文"主张 | `FULL_TEXT_UNSUPPORTED_BY_SOURCE` |
| 8 | `published_at` 不得晚于 `first_seen_at`（系统首见不早于公开） | `TIME_INVERSION` |

`quote_hash` 的机械含义 = `sha256(UTF-8 原文)`（与 `scripts/guard/executor.py::_derive_quote_hash`
同源；亦为 `Ch9 §3.5` 核验行幂等键组成项 `(source_id, quote_hash)`）。

## 退出码（`CONVENTIONS.md::G-01`）

`0` 放行 / `1` 命中违例（**命中即 fail，禁 warn-only**）/ `2` 输入异常（`code_root` 缺失 / JSONL 损坏）。
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any, Mapping, NamedTuple, Sequence

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import (  # noqa: E402
    CheckReport,
    Violation,
    run_checker,
)

RAW_DIRNAME = "raw"
"""原始物根目录名（`Ch9 §3.3.3` 目录地基：外部文本只进 `raw/`）。"""

UNDISCLOSED_PREFIX = "未披露"
"""来源确无可定位信息时的**显式**哨兵前缀（`Ch9 §3.4.6`：不得留空字符串）。"""

FULL_TEXT_CAPABLE_CONTENT_TYPES = frozenset({"full_text"})
"""**能力白名单**（`R-06` ⑤）：只有该取值才允许主张"读过全文"（`Ch6 N6.1-07`）。"""

LOCATOR_CODES = frozenset(
    {
        "LOCATOR_MISSING",
        "LOCATOR_UNRECOGNIZED",
        "LOCATOR_ESCAPE",
        "LOCATOR_UNRESOLVABLE",
        "LOCATOR_RANGE_OUT_OF_BOUNDS",
        "QUOTE_HASH_MISSING",
        "QUOTE_HASH_MISMATCH",
        "FULL_TEXT_UNPROVEN",
        "FULL_TEXT_UNSUPPORTED_BY_SOURCE",
    }
)
"""属"定位 / 全文证明"域的违例码；消费方（`scripts/claim/transition.py`）据此设定位前置门。"""

_RAW_LOCATOR_RE = re.compile(r"^raw/(?P<relpath>.+?)#L(?P<start>\d+)-L(?P<end>\d+)$")


class _Resolved(NamedTuple):
    """`raw/` 定位解析结果。`ok=True` 时 `code`/`detail` 为空、`text`/`line_count` 有效。"""

    ok: bool
    code: str
    text: str
    line_count: int
    detail: str


def _is_undisclosed(locator: str) -> bool:
    """`locator` 是否为显式"未披露"哨兵（前缀匹配，`Ch9 §3.4.6` 的显式降级取值）。"""
    return locator.startswith(UNDISCLOSED_PREFIX)


def parse_raw_locator(locator: str) -> tuple[str, int, int] | None:
    """解析 `raw/<relpath>#L<start>-L<end>`；不匹配该语法 → `None`（交由调用方判"非机械可复查"）。"""
    match = _RAW_LOCATOR_RE.match(locator)
    if match is None:
        return None
    return (match.group("relpath"), int(match.group("start")), int(match.group("end")))


def _resolve_raw_artifact(root: Path, relpath: str) -> _Resolved:
    """把 `raw/<relpath>` 解析为 `raw/` 内的常规文件并读出原文（越界 / 缺失 / 不可读 → 明确违例码）。"""
    normalized = relpath.replace("\\", "/")
    parts = [seg for seg in normalized.split("/") if seg not in ("", ".")]
    if not parts or any(seg == ".." for seg in parts):
        return _Resolved(False, "LOCATOR_ESCAPE", "", 0, f"定位含路径穿越或为空: {relpath!r}")
    if normalized.startswith("/") or Path(normalized).is_absolute():
        return _Resolved(False, "LOCATOR_ESCAPE", "", 0, f"定位不得为绝对路径: {relpath!r}")
    raw_dir = (Path(root) / RAW_DIRNAME).resolve()
    resolved = (raw_dir / "/".join(parts)).resolve()
    if resolved != raw_dir and raw_dir not in resolved.parents:
        return _Resolved(False, "LOCATOR_ESCAPE", "", 0, f"定位越出 raw/: {relpath!r}")
    if not resolved.is_file():
        return _Resolved(False, "LOCATOR_UNRESOLVABLE", "", 0, f"raw/ 下无此常规文件: {relpath!r}")
    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _Resolved(
            False,
            "LOCATOR_UNRESOLVABLE",
            "",
            0,
            f"原文不可读（非 UTF-8 或 IO 失败）: {type(exc).__name__}: {exc}",
        )
    return _Resolved(True, "", text, len(text.splitlines()), "")


def _validate_claim(claim: Mapping[str, Any]) -> tuple[Any, str]:
    """把原始行校验为 `schema.models.Claim`（三字段枚举域 / 必填项在此机械拦截）。

    非法 → 返回 `(None, 原因)`，**不抛**，由调用方折叠为一条违例（`CLAIM_SCHEMA_INVALID`）。
    ★ 惰性导入 pydantic（`P-03`：不在模块级急切导入）。
    """
    from pydantic import ValidationError
    from schema.models import Claim

    try:
        return (Claim.model_validate(claim), "")
    except ValidationError as exc:
        return (None, str(exc))


def _append_time_problems(obj: Any, problems: list[tuple[str, str]]) -> None:
    """时间倒挂：系统首见时间**不得**早于公开时间（`Ch9 §2.2` 双时间轴语义）。"""
    if (
        obj.published_at is not None
        and obj.first_seen_at is not None
        and obj.published_at > obj.first_seen_at
    ):
        problems.append(
            (
                "TIME_INVERSION",
                "published_at({0}) 晚于 first_seen_at({1}) —— 时间倒挂".format(
                    obj.published_at.isoformat(), obj.first_seen_at.isoformat()
                ),
            )
        )


def claim_locator_problems(
    claim: Mapping[str, Any],
    root: Path,
    sources: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[tuple[str, str]]:
    """校验**单条**主张的定位信息，返回 `[(违例码, 说明)]`（空列表 = 定位有效）。

    这是本模块的**进程内 API**：`scripts/claim/transition.py` 在迁移前调用它作定位前置门。
    """
    problems: list[tuple[str, str]] = []
    obj, schema_error = _validate_claim(claim)
    if obj is None:
        problems.append(("CLAIM_SCHEMA_INVALID", schema_error))
        return problems

    from schema.models import SourceTier

    if obj.official_claim_kind is not None and obj.tier != SourceTier.primary:
        problems.append(
            (
                "OFFICIAL_KIND_TIER_MISMATCH",
                "official_claim_kind 仅适用 tier=primary（Ch9 §3.4.6 R-17）："
                f"tier={obj.tier.value} official_claim_kind={obj.official_claim_kind.value}",
            )
        )

    locator = (obj.locator or "").strip()
    full = bool(obj.full_text_read)
    if not locator:
        problems.append(
            ("LOCATOR_MISSING", "locator 为空 —— 主张不可复查回原文（Ch9 §3.4.6 措施①/②）")
        )
        _append_time_problems(obj, problems)
        return problems

    parsed = parse_raw_locator(locator)
    if parsed is None:
        if not _is_undisclosed(locator):
            problems.append(
                (
                    "LOCATOR_UNRECOGNIZED",
                    "locator 非机械可复查形式（既非 raw/<relpath>#L<a>-L<b>，也非显式未披露）: "
                    f"{locator!r}",
                )
            )
        if full:
            problems.append(
                (
                    "FULL_TEXT_UNPROVEN",
                    "full_text_read=true 但定位非机械可复查的 raw/ 区间 —— 无法证明读到全文",
                )
            )
        _append_time_problems(obj, problems)
        return problems

    relpath, start, end = parsed
    resolved = _resolve_raw_artifact(root, relpath)
    if not resolved.ok:
        problems.append((resolved.code, resolved.detail))
        _append_time_problems(obj, problems)
        return problems

    if not (1 <= start <= end <= resolved.line_count):
        problems.append(
            (
                "LOCATOR_RANGE_OUT_OF_BOUNDS",
                f"定位区间 L{start}-L{end} 越界（原文共 {resolved.line_count} 行）",
            )
        )
        _append_time_problems(obj, problems)
        return problems

    if not obj.quote_hash:
        problems.append(
            ("QUOTE_HASH_MISSING", "quote_hash 为空 —— 幂等键组成项缺失（Ch9 §3.5 ②行）")
        )

    if full:
        if not (start == 1 and end == resolved.line_count):
            problems.append(
                (
                    "FULL_TEXT_UNPROVEN",
                    "full_text_read=true 但定位仅覆盖 L{0}-L{1}/{2} 行 —— 未证明读到全文".format(
                        start, end, resolved.line_count
                    ),
                )
            )
        expected = hashlib.sha256(resolved.text.encode("utf-8")).hexdigest()
        if obj.quote_hash and obj.quote_hash != expected:
            problems.append(
                (
                    "QUOTE_HASH_MISMATCH",
                    "quote_hash 与原文 sha256 不符 —— 定位所指原文与主张引文不同一条（Ch9 §3.5 ②行）",
                )
            )

    source = (sources or {}).get(obj.source_id)
    if full and source is not None:
        content_type = str(source.get("obtainable_content_type", ""))
        if content_type not in FULL_TEXT_CAPABLE_CONTENT_TYPES:
            problems.append(
                (
                    "FULL_TEXT_UNSUPPORTED_BY_SOURCE",
                    f"来源 obtainable_content_type={content_type!r} 非全文可获取 —— "
                    "不得出'读过全文'主张（Ch6 N6.1-07）",
                )
            )

    _append_time_problems(obj, problems)
    return problems


def _source_index(root: Path) -> dict[str, Mapping[str, Any]]:
    """读 `facts/sources.jsonl` 建 `source_id -> 行` 索引（供来源侧越界交叉核对）。"""
    from schema.store import read_records

    index: dict[str, Mapping[str, Any]] = {}
    for row in read_records(root, "sources"):
        index[str(row.get("source_id", ""))] = row
    return index


def check(root: Path) -> CheckReport:
    """校验器入口：**单遍**扫描 `facts/claims.jsonl`，逐条复查定位（`P-01`）。"""
    from schema.store import read_records

    report = CheckReport(checker="locator_check.py")
    claims = read_records(root, "claims")
    report.scanned["claims"] = len(claims)
    if not claims:
        report.notes.append(
            "NO_CLAIMS: facts/claims.jsonl 为空 —— 无被检对象（真空成立，非'已验证'，G-03）"
        )
        return report

    sources = _source_index(root)
    report.scanned["sources"] = len(sources)
    if not sources:
        report.notes.append(
            "NO_SOURCES: facts/sources.jsonl 为空 —— 来源侧越界交叉核对跳过（G-03）"
        )

    for lineno, claim in enumerate(claims, start=1):
        for code, detail in claim_locator_problems(claim, root, sources):
            report.violations.append(
                Violation(rule=code, reason=detail, file="facts/claims.jsonl", line=lineno)
            )
    return report


def summary_codes(report: CheckReport) -> Sequence[str]:
    """报告内出现的违例码（去重、字典序）——便于 CLI / 测试断言"命中了哪类违例"。"""
    return sorted({v.rule for v in report.violations})


if __name__ == "__main__":
    sys.exit(run_checker("locator_check.py", check))
