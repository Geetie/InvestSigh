"""时间契约回归（批次 5b 缺陷的**直接护栏**）。

背景：批次 5 首次真实运行暴露 —— 落库 claim 的**五类时间全为 `None`、`locator` 为空**，
根因是「**从没在真实链路里跑过**，所以没人发现 claim 缺时间」。批次 5b 修法是给
`build_claim` / `process_external_text` / `process_raw_file` 新增**必填无默认**的
system_time 三元组（`first_seen_at` / `analyzed_at` / `recorded_seq`），并在 `build_claim`
加**运行期** `None` 断言（pydantic 不拦 `None`）。

本文件把该契约钉成回归：
  1. 签名**缺参** → `TypeError`（调用方无法省略）；
  2. 显式传 **`None`**（绕过签名）→ 运行期 `ValueError`；
  3. **端到端**：step 1 handler 真跑一次 → 每条 claim 的 system_time 齐备、`locator` 非空、
     `recorded_seq` 严格递增（「不恒为 1」）。

缺了这组，下次重构仍会把时间悄悄退回 `None`。
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest


def _valid_kwargs() -> dict:
    """`build_claim` 的**除 system_time 三元组外**的合法参数。"""
    from schema.models import ClaimForm, ClaimNature, SourceTier

    return dict(
        claim_id="claim-time-contract-1",
        source_id="src-time",
        quote_hash="0" * 64,
        claim_nature=ClaimNature.fact,
        claim_form=ClaimForm.citation,
        tier=SourceTier.secondary_tertiary,
    )


def test_build_claim_missing_system_time_is_typeerror() -> None:
    """缺 system_time 三元组 → 签名层 `TypeError`（必填无默认，调用方无法省略）。"""
    from scripts.guard.claims import build_claim

    with pytest.raises(TypeError):
        build_claim(**_valid_kwargs())


@pytest.mark.parametrize("missing", ["first_seen_at", "analyzed_at", "recorded_seq"])
def test_build_claim_explicit_none_system_time_is_valueerror(missing: str) -> None:
    """显式传 `None`（绕过签名）→ 运行期 `ValueError`（system_time 永不未知）。"""
    from scripts.guard.claims import build_claim

    kwargs = _valid_kwargs()
    kwargs["first_seen_at"] = datetime.now(timezone.utc)
    kwargs["analyzed_at"] = datetime.now(timezone.utc)
    kwargs["recorded_seq"] = 1
    kwargs[missing] = None
    with pytest.raises(ValueError):
        build_claim(**kwargs)


# ═════════════ 端到端：真实 handler（临时夹具副本，不污染真实仓库）═════════════

_E2E_INBOX_FILES = (
    "2026-09-15_server_backlog_note_sample.txt",
    "2026-09-16_cloud_capex_note_sample.txt",
)


def test_ingest_handler_end_to_end_fills_system_time(code_root: Path) -> None:
    """step 1 handler 真跑一次 → 每条 claim 的 system_time 齐备、`locator` 非空。

    ★ 在 `code_root`（`system/` 的**临时副本**，由 `conftest` 夹具提供）上跑**真子进程**：
      把副本插到 `sys.path[0]`，于是 `ingest_step._ROOT` 解析到**副本**，
      所有写入只发生在副本内，**不触碰真实仓库**的 `raw/` 与 `facts/`。
    ★ 两个投递文件 → 断言 `recorded_seq` **严格递增**（证明「不恒为 1」）。
    """
    inbox = code_root / "raw" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    for name in _E2E_INBOX_FILES:
        (inbox / name).write_text("第一行\n第二行\n第三行\n", encoding="utf-8")

    driver = code_root.parent / "drive_ingest_step.py"
    driver.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(code_root)!r})\n"
        "from datetime import date\n"
        "from scripts.orchestrate.ingest_step import ingest_public_information\n"
        "outcome = ingest_public_information(date(2026, 9, 16), 'sample')\n"
        "print('PRODUCED', len(outcome.produced))\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(driver)],
        cwd=str(code_root),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"handler 子进程失败：\n{proc.stdout}\n{proc.stderr}"

    claims = code_root / "facts" / "claims.jsonl"
    assert claims.exists(), "handler 应把 claim 落到 facts/claims.jsonl"
    rows = [
        json.loads(line)
        for line in claims.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == len(_E2E_INBOX_FILES), f"应产出 {len(_E2E_INBOX_FILES)} 条 claim，实得 {len(rows)}"

    seqs: list[int] = []
    for row in rows:
        assert row.get("first_seen_at") is not None, "system_time first_seen_at 不得为 None"
        assert row.get("analyzed_at") is not None, "system_time analyzed_at 不得为 None"
        recorded_seq = row.get("recorded_seq")
        assert isinstance(recorded_seq, int) and recorded_seq >= 1, (
            f"recorded_seq 必须是 int 且 >= 1，实得 {recorded_seq!r}"
        )
        assert row.get("locator"), "locator 不得为空（外部文本必须可复查）"
        seqs.append(recorded_seq)

    assert seqs == sorted(set(seqs)), f"recorded_seq 必须严格递增，实得 {seqs}"
