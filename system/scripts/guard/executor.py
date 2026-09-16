"""`executor.py` —— **真实入口**：编排注入防护四措施（`Ch9 §3.4.6`）。

把"外部文本"编排成一条受控链路：

    raw 落盘（措施①载体） → 角色标注（措施①prompt） → 主张化（措施④，claim_nature 必填）
        → 全过程**不调用**工具（措施③）→ 组装 prompt 数据段

★ 本模块**不解析**文本内容，故"外部文本无法改变规则内核 / 无法触发工具"是**结构性**的。

`handle_external_request`（`R-07`）：外部来源的**请求**入口，按**调用方声明的 `kind`** 路由，
为两个收口点（`rulewrite.write_rule` / `toolwatch.request_tool`）提供**可被生产调用的**路由入口。

★ 生产接线（把本入口接进真实采集链路）属**阶段①**（`G-13`：原判"属阶段② 采集层" **是错的，已纠正**）：
  `rules/pipeline.yaml::steps[1]`（0444 锁定）声明 step 1 = `ingest_public_information`
  首版已实现、`blocking: true`、**无 hook**，故本入口经编排器 step 1 接线 ——
  `scripts/orchestrate/ingest_step.py::ingest_public_information` 调 `process_raw_file`，
  由 `Pipeline` **默认注册**（见 `scripts/orchestrate/pipeline.py::_register_default_steps`）。

★ `kind` 由调用方**声明**，不是对文本做词面分类 —— 因此**不违反** `AC-33`（禁关键词黑名单）。

★ 五类时间语义（`Ch9 §2.2` / `§3.4.1`）：本模块处于 `scripts/guard/**` **数据路径**，受
  `injection_guard.ALLOWED_IMPORTS` 能力白名单约束，**不得** import `datetime`（故 `now()`
  不在本层产生）。因此 system_time 三元组（`first_seen_at` / `analyzed_at` / `recorded_seq`）
  由**调用方**（采集层 `scripts/orchestrate/ingest_step.py` 或外部请求 payload）**传入**，
  本层只**转发**给 `build_claim` —— 与本模块"不解析文本、不合成事实"的结构性约束一致。
  类型注解写 `datetime`，由模块级 `from __future__ import annotations`（PEP 563）**延迟求值**，
  运行期不求值该名字，故无需（也不得）import。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from schema.store import append_records

from .annotate import AnnotatedData, annotate_as_data, assemble_prompt_context
from .claims import build_claim
from .rawsink import (
    RAW_DIRNAME,
    ExternalTextDecodeError,
    _validate_name,
    assert_within_raw,
    read_external_text,
    store_raw,
)
from .rulewrite import write_rule
from .toolwatch import (
    ORIGIN_EXTERNAL,
    ToolCallLedger,
    ToolInvocationBlocked,
    tool_call_ledger,
    request_tool,
)

from config.rules import ReadOnlyRuleViolation
from schema.models import ClaimForm, ClaimNature, SourceTier

__all__ = [
    "STATUS_OK",
    "STATUS_DEGRADED",
    "STATUS_BLOCKED",
    "NOTE_EMPTY_EXTERNAL_TEXT",
    "NOTE_DECODE_DEGRADED",
    "NOTE_UNKNOWN_KIND",
    "NOTE_RULE_WRITE_BLOCKED",
    "NOTE_TOOL_CALL_BLOCKED",
    "NOTE_SOURCE_MISSING",
    "NOTE_SOURCE_UNREADABLE",
    "NOTE_RAW_PATH_REJECTED",
    "NOTE_MISSING_PAYLOAD_FIELDS",
    "IngestResult",
    "process_external_text",
    "process_raw_file",
    "handle_external_request",
]

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_BLOCKED = "blocked"

NOTE_EMPTY_EXTERNAL_TEXT = "EMPTY_EXTERNAL_TEXT"
NOTE_DECODE_DEGRADED = "DECODE_DEGRADED"
NOTE_UNKNOWN_KIND = "UNKNOWN_KIND"
NOTE_RULE_WRITE_BLOCKED = "RULE_WRITE_BLOCKED"
NOTE_TOOL_CALL_BLOCKED = "TOOL_CALL_BLOCKED"
NOTE_SOURCE_MISSING = "SOURCE_MISSING"
NOTE_SOURCE_UNREADABLE = "SOURCE_UNREADABLE"
NOTE_RAW_PATH_REJECTED = "RAW_PATH_REJECTED"
NOTE_MISSING_PAYLOAD_FIELDS = "MISSING_PAYLOAD_FIELDS"


@dataclass
class IngestResult:
    """一次外部文本处理的结果（**不置 null 冒充成功**）。"""

    raw_ref: str                        # 落 `raw/` 的相对路径（未落盘 → ""）
    claim_id: str | None                # 落库成功 → claim_id；未落库 → None
    annotated: AnnotatedData | None     # 角色标注结果
    prompt_context: str                 # 组装出的数据段（含角色标注）
    tool_calls: int                     # 本过程记录到的工具调用尝试数（期望 0）
    status: str                         # ok / degraded / blocked
    note: str = ""                      # 降级/空样本/阻断的显式说明
    blocked_kind: str = ""              # 阻断类别（仅 blocked 时非空）


def _derive_quote_hash(text: str) -> str:
    """由文本内容派生的幂等键组成项（`Ch9 §3.5` 阶段②：幂等键 = (source_id, quote_hash)）。

    ★ 这里**不是** `rules/` hash 校验路径（那是 `checks/rules_lock_guard.py` 的唯一职责）；
      它只标识"这条外部文本"，使同一文本重复处理时 claim 幂等。
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _derive_raw_name(source_id: str, raw_name: str | None, text: str) -> str:
    safe = raw_name if raw_name else f"{source_id}-{_derive_quote_hash(text)[:12]}.txt"
    return safe


def process_external_text(
    root: str | Path,
    text: str,
    *,
    source_id: str,
    claim_nature: ClaimNature,
    claim_form: ClaimForm,
    tier: SourceTier,
    first_seen_at: datetime,
    analyzed_at: datetime,
    recorded_seq: int,
    locator: str = "",
    occurred_at: datetime | None = None,
    published_at: datetime | None = None,
    effective_from: datetime | None = None,
    backfilled_at: datetime | None = None,
    raw_name: str | None = None,
    persist: bool = True,
) -> IngestResult:
    """**真实入口**：raw 落盘 → 主张化（`claim_nature` + system_time 必填）→ prompt 组装（角色标注）。

    有序步骤：
      1) `store_raw(root, raw_name, text)` → 文本**只**进 `raw/`（不进 `rules/`）；
      2) `annotate_as_data(text, source_ref=raw_ref, locator)` → 角色标注；
      3) `build_claim(...)` → `append_records(root, "claims", [claim])`（pydantic 校验兜底）；
      4) 全过程**不调用** `request_tool`；`tool_calls` 取自本次 `tool_call_ledger`。

    ★ 空文本 → `status="degraded"` + `note="EMPTY_EXTERNAL_TEXT"`（**不得**当 PASS=已验证）。
    ★ 越界名（`ValueError`）→ `status="blocked"` + note（不崩溃）。
    ★ `persist=False` → 不落 `claims.jsonl`，`claim_id` 仍返回（用于纯标注/预演）。
    ★ system_time 三元组（`first_seen_at` / `analyzed_at` / `recorded_seq`）为**必填无默认**
      —— 本层不产生 `now()`（数据路径不得 import `datetime`），须由调用方传入（`Ch9 §2.2`）；
      缺省 / None → `build_claim` 运行期断言**响亮失败**（不静默落库）。
    """
    root_path = Path(root)
    with tool_call_ledger() as ledger:
        raw_ref = ""
        try:
            name = _derive_raw_name(source_id, raw_name, text)
            raw_path = store_raw(root_path, name, text)
            raw_ref = str(raw_path.relative_to(root_path).as_posix())
        except ValueError as exc:
            return IngestResult(
                raw_ref="",
                claim_id=None,
                annotated=None,
                prompt_context="",
                tool_calls=ledger.tool_calls,
                status=STATUS_BLOCKED,
                note=f"RAW_NAME_REJECTED: {exc}",
                blocked_kind="raw_name",
            )

        annotated = annotate_as_data(text, source_ref=raw_ref, locator=locator)
        prompt_context = assemble_prompt_context([annotated])

        if text == "":
            # 空样本：文本已落 raw/、标注已生成，但**显式降级**（不当 PASS=已验证）。
            return IngestResult(
                raw_ref=raw_ref,
                claim_id=None,
                annotated=annotated,
                prompt_context=prompt_context,
                tool_calls=ledger.tool_calls,
                status=STATUS_DEGRADED,
                note=NOTE_EMPTY_EXTERNAL_TEXT,
            )

        quote_hash = _derive_quote_hash(text)
        claim_id = f"claim-{source_id}-{quote_hash[:12]}"
        claim = build_claim(
            claim_id=claim_id,
            source_id=source_id,
            quote_hash=quote_hash,
            claim_nature=claim_nature,
            claim_form=claim_form,
            tier=tier,
            first_seen_at=first_seen_at,
            analyzed_at=analyzed_at,
            recorded_seq=recorded_seq,
            locator=locator,
            occurred_at=occurred_at,
            published_at=published_at,
            effective_from=effective_from,
            backfilled_at=backfilled_at,
        )
        if persist:
            append_records(root_path, "claims", [claim])

        return IngestResult(
            raw_ref=raw_ref,
            claim_id=claim_id,
            annotated=annotated,
            prompt_context=prompt_context,
            tool_calls=ledger.tool_calls,
            status=STATUS_OK,
            note="",
        )


def process_raw_file(
    root: str | Path,
    relpath: str,
    *,
    source_id: str,
    claim_nature: ClaimNature,
    claim_form: ClaimForm,
    tier: SourceTier,
    first_seen_at: datetime,
    analyzed_at: datetime,
    recorded_seq: int,
    locator: str = "",
    occurred_at: datetime | None = None,
    published_at: datetime | None = None,
    effective_from: datetime | None = None,
    backfilled_at: datetime | None = None,
    persist: bool = True,
) -> IngestResult:
    """从 `raw/` 读一个文件走同一流程。

    ★ **读侧与写侧共用同一越界判定**（`rawsink._validate_name` + `rawsink.assert_within_raw`，
      `G-06` 唯一真源）：`relpath`（相对 `root`）必须落在 `raw/` 内 —— 含 `..` / 绝对路径 /
      落出 `raw/` → `status="blocked"` + note（`RAW_PATH_REJECTED`）。**外部文本只从 `raw/` 来**，
      不得把 `rules/` 等内部文件当外部文本摄入并主张化（`A-2`：读侧此前裸读、与写侧不对称）。
    - 非 UTF-8 → `status="blocked"` + note（`DECODE_DEGRADED`，不崩）。
    - 输入源缺失（`raw/<relpath>` 不存在）→ `status="blocked"` + note（`SOURCE_MISSING`）。
    - 其余读取类 `OSError`（目录 / 权限 / …）→ `status="blocked"` + note（`SOURCE_UNREADABLE`）。
      **不把 `OSError` 抛给调用方**（`AC-05`：明确降级，不 500）。
    ★ system_time 三元组（`first_seen_at` / `analyzed_at` / `recorded_seq`）为**必填无默认**，
      原样转发给 `process_external_text`（`Ch9 §2.2`；本层不产生 `now()`）。
    """
    root_path = Path(root)
    try:
        safe_rel = _validate_name(relpath)
        path = root_path / safe_rel
        assert_within_raw(root_path / RAW_DIRNAME, path)
    except ValueError as exc:
        return IngestResult(
            raw_ref="",
            claim_id=None,
            annotated=None,
            prompt_context="",
            tool_calls=0,
            status=STATUS_BLOCKED,
            note=f"{NOTE_RAW_PATH_REJECTED}: {exc}",
            blocked_kind="raw_path",
        )
    try:
        text = read_external_text(path)
    except ExternalTextDecodeError as exc:
        return IngestResult(
            raw_ref=relpath,
            claim_id=None,
            annotated=None,
            prompt_context="",
            tool_calls=0,
            status=STATUS_BLOCKED,
            note=f"{NOTE_DECODE_DEGRADED}: {exc}",
            blocked_kind="decode",
        )
    except FileNotFoundError as exc:
        # 输入源缺失 → 明确降级（raw_ref 留空：未产出任何 raw 物）
        return IngestResult(
            raw_ref="",
            claim_id=None,
            annotated=None,
            prompt_context="",
            tool_calls=0,
            status=STATUS_BLOCKED,
            note=f"{NOTE_SOURCE_MISSING}: {relpath}",
            blocked_kind="missing_source",
        )
    except OSError as exc:
        # 目录 / 权限 / 其它读取类错误 → 一律明确降级（不把 OSError 抛给调用方）
        return IngestResult(
            raw_ref="",
            claim_id=None,
            annotated=None,
            prompt_context="",
            tool_calls=0,
            status=STATUS_BLOCKED,
            note=f"{NOTE_SOURCE_UNREADABLE}: {type(exc).__name__}: {exc}",
            blocked_kind="source_unreadable",
        )
    return process_external_text(
        root_path,
        text,
        source_id=source_id,
        claim_nature=claim_nature,
        claim_form=claim_form,
        tier=tier,
        first_seen_at=first_seen_at,
        analyzed_at=analyzed_at,
        recorded_seq=recorded_seq,
        locator=locator,
        occurred_at=occurred_at,
        published_at=published_at,
        effective_from=effective_from,
        backfilled_at=backfilled_at,
        raw_name=Path(relpath).name,
        persist=persist,
    )


def _blocked(
    ledger: ToolCallLedger,
    *,
    kind: str,
    note: str,
) -> IngestResult:
    """构造一个 `status="blocked"` 的结果（阻断时 `claim_id=None`，不冒充成功）。"""
    return IngestResult(
        raw_ref="",
        claim_id=None,
        annotated=None,
        prompt_context="",
        tool_calls=ledger.tool_calls,
        status=STATUS_BLOCKED,
        note=note,
        blocked_kind=kind,
    )


def handle_external_request(
    root: str | Path,
    *,
    kind: str,
    payload: Mapping[str, Any],
    ledger: ToolCallLedger,
) -> IngestResult:
    """外部来源的**请求**入口：按调用方声明的 `kind` 路由。

    - `kind="rule_write"` → `rulewrite.write_rule(...)`（→ 恒抛 `ReadOnlyRuleViolation`）
                          → 捕获后返回 `status="blocked"` + note（不吞异常语义：blocked 即明确降级）
    - `kind="tool_call"`  → `toolwatch.request_tool(origin=ORIGIN_EXTERNAL, ...)`（→ 恒抛）
                          → 捕获后返回 `status="blocked"` + note
    - `kind="data"`       → 走 `process_external_text` 的**数据**路径（正常吸收）；
                            必需字段 `("claim_nature","claim_form","tier")` 与 system_time 三元组
                            `("first_seen_at","analyzed_at","recorded_seq")` 缺任一 →
                            `status="blocked"` + note（`MISSING_PAYLOAD_FIELDS`，不抛 `KeyError`）
    - 未知 kind           → `status="blocked"` + note（**明确拒绝，不静默当数据**）

    ★ `kind` 由**调用方声明**，不是对文本做词面分类（因此不违反 `AC-33` 禁关键词黑名单）。
    ★ 本函数是 `rulewrite.write_rule` 与 `toolwatch.request_tool` 的**生产调用方**（`R-07`）。
    """
    if kind == "rule_write":
        path = payload.get("path", "")
        content = payload.get("content", "")
        try:
            write_rule(path, content)
        except ReadOnlyRuleViolation as exc:
            return _blocked(
                ledger, kind="rule_write", note=f"{NOTE_RULE_WRITE_BLOCKED}: {exc}"
            )
        # write_rule 声明 NoReturn，理论不可达；若未来语义变化导致可达 → 明确报错而非静默成功。
        return _blocked(
            ledger, kind="rule_write", note=f"{NOTE_RULE_WRITE_BLOCKED}: write_rule 未抛（异常）"
        )

    if kind == "tool_call":
        name = str(payload.get("name", "unknown_tool"))
        try:
            request_tool(name, origin=ORIGIN_EXTERNAL, ledger=ledger)
        except ToolInvocationBlocked as exc:
            return _blocked(
                ledger, kind="tool_call", note=f"{NOTE_TOOL_CALL_BLOCKED}: {exc}"
            )
        return _blocked(
            ledger, kind="tool_call", note=f"{NOTE_TOOL_CALL_BLOCKED}: request_tool 未抛（异常）"
        )

    if kind == "data":
        # 先校验必需键：缺字段 → 明确降级为 blocked（不把 KeyError 抛给调用方）
        # system_time 三元组亦为必需（本层不产生 now()，须由声明方给出，Ch9 §2.2）
        required = (
            "claim_nature",
            "claim_form",
            "tier",
            "first_seen_at",
            "analyzed_at",
            "recorded_seq",
        )
        missing = [key for key in required if key not in payload]
        if missing:
            return _blocked(
                ledger,
                kind="payload",
                note=f"{NOTE_MISSING_PAYLOAD_FIELDS}: {missing}",
            )
        return process_external_text(
            root,
            str(payload.get("text", "")),
            source_id=str(payload.get("source_id", "")),
            claim_nature=payload["claim_nature"],
            claim_form=payload["claim_form"],
            tier=payload["tier"],
            first_seen_at=payload["first_seen_at"],
            analyzed_at=payload["analyzed_at"],
            recorded_seq=payload["recorded_seq"],
            locator=str(payload.get("locator", "")),
            occurred_at=payload.get("occurred_at"),
            published_at=payload.get("published_at"),
            effective_from=payload.get("effective_from"),
            backfilled_at=payload.get("backfilled_at"),
            raw_name=payload.get("raw_name"),
            persist=bool(payload.get("persist", True)),
        )

    return _blocked(
        ledger, kind=kind or "unknown", note=f"{NOTE_UNKNOWN_KIND}: {kind!r}"
    )
