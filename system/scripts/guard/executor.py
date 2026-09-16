"""`executor.py` —— **真实入口**：编排注入防护四措施（`Ch9 §3.4.6`）。

把"外部文本"编排成一条受控链路：

    raw 落盘（措施①载体） → 角色标注（措施①prompt） → 主张化（措施④，claim_nature 必填）
        → 全过程**不调用**工具（措施③）→ 组装 prompt 数据段

★ 本模块**不解析**文本内容，故"外部文本无法改变规则内核 / 无法触发工具"是**结构性**的。

`handle_external_request`（`R-07`）：外部来源的**请求**入口，按**调用方声明的 `kind`** 路由，
为两个收口点（`rulewrite.write_rule` / `toolwatch.request_tool`）提供**可被生产调用的**路由入口。
★ 生产接线（把本入口接进真实采集链路）属阶段② 采集层，见 `G-13`。

★ `kind` 由调用方**声明**，不是对文本做词面分类 —— 因此**不违反** `AC-33`（禁关键词黑名单）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from schema.store import append_records

from .annotate import AnnotatedData, annotate_as_data, assemble_prompt_context
from .claims import build_claim
from .rawsink import ExternalTextDecodeError, read_external_text, store_raw
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
    locator: str = "",
    raw_name: str | None = None,
    persist: bool = True,
) -> IngestResult:
    """**真实入口**：raw 落盘 → 主张化（`claim_nature` 必填）→ prompt 组装（角色标注）。

    有序步骤：
      1) `store_raw(root, raw_name, text)` → 文本**只**进 `raw/`（不进 `rules/`）；
      2) `annotate_as_data(text, source_ref=raw_ref, locator)` → 角色标注；
      3) `build_claim(...)` → `append_records(root, "claims", [claim])`（pydantic 校验兜底）；
      4) 全过程**不调用** `request_tool`；`tool_calls` 取自本次 `tool_call_ledger`。

    ★ 空文本 → `status="degraded"` + `note="EMPTY_EXTERNAL_TEXT"`（**不得**当 PASS=已验证）。
    ★ 越界名（`ValueError`）→ `status="blocked"` + note（不崩溃）。
    ★ `persist=False` → 不落 `claims.jsonl`，`claim_id` 仍返回（用于纯标注/预演）。
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
            locator=locator,
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
    locator: str = "",
    persist: bool = True,
) -> IngestResult:
    """从 `raw/` 读一个文件走同一流程。

    - 非 UTF-8 → `status="blocked"` + note（`DECODE_DEGRADED`，不崩）。
    - 输入源缺失（`raw/<relpath>` 不存在）→ `status="blocked"` + note（`SOURCE_MISSING`），
      **不把 `FileNotFoundError` 抛给调用方**（`AC-05`：明确降级，不 500）。
    """
    root_path = Path(root)
    path = root_path / relpath
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
    return process_external_text(
        root_path,
        text,
        source_id=source_id,
        claim_nature=claim_nature,
        claim_form=claim_form,
        tier=tier,
        locator=locator,
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
                            必需字段 `("claim_nature","claim_form","tier")` 缺任一 →
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
        required = ("claim_nature", "claim_form", "tier")
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
            locator=str(payload.get("locator", "")),
            raw_name=payload.get("raw_name"),
            persist=bool(payload.get("persist", True)),
        )

    return _blocked(
        ledger, kind=kind or "unknown", note=f"{NOTE_UNKNOWN_KIND}: {kind!r}"
    )
