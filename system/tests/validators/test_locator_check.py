"""`locator_check` 定位校验器测试（`ws/claim` · DoD A）。

覆盖：**真跑通**（真实采集链路落库的 claim → 真实校验）、**守卫真拦得住**（定位无效 → exit 1）、
**错误路径**（缺失/非机械/穿越/三字段互换）、**边界**（空 / 超大 / 非法枚举 / 时间倒挂）。

★ 一律跑**仓库里的真实脚本**（`conftest.run_gate` = 进程内走 `__main__` 入口，不 mock），
  `code_root` 指向夹具副本（`system/` 的临时拷贝），不污染真仓库。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import assert_rejected, run_gate

GUARD = "scripts/validators/locator_check.py"

_CHILD_ENV = {
    **__import__("os").environ,
    "CODEBUDDY_SAFE_DELETE_SANDBOX": "0",
    "CODEBUDDY_BROKERED_FS_HOOK_ENABLED": "0",
}


def _base_claim(**over: object) -> dict:
    """一条合法 claim 的基线（其余字段用模型默认值）。"""
    base: dict = {
        "claim_id": "clm-base",
        "source_id": "src-1",
        "quote_hash": "a" * 64,
        "claim_nature": "fact",
        "claim_form": "citation",
        "tier": "secondary_tertiary",
        "locator": "*",
        "status": "pending_verification",
        "first_seen_at": "2026-09-16T00:00:00+00:00",
        "analyzed_at": "2026-09-16T00:00:00+00:00",
        "recorded_seq": 1,
        "full_text_read": False,
    }
    base.update(over)
    return base


def _write_claims(root: Path, rows: list[dict]) -> None:
    path = root / "facts" / "claims.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def _write_sources(root: Path, rows: list[dict]) -> None:
    path = root / "facts" / "sources.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def _write_raw(root: Path, name: str, text: str) -> None:
    target = root / "raw" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ───────────────────────── 边界：空样本 ─────────────────────────


def test_no_claims_passes_with_explicit_note(code_root: Path) -> None:
    """空 `claims.jsonl` → 显式 note + **exit 0**（无被检对象不得当'已验证'，G-03）。"""
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 0, proc.stdout
    assert "== locator_check.py ==" in proc.stdout
    assert "NO_CLAIMS" in proc.stdout


# ───────────────────────── 真跑通：真实采集链路落库的 claim ─────────────────────────


def _drive_ingest(code_root: Path) -> dict:
    """真跑 step 1 handler（子进程，sys.path 指向夹具副本）→ 返回落库的 claim 行。"""
    inbox = code_root / "raw" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "2026-09-15_note_sample.txt").write_text("第一行\n第二行\n第三行\n", encoding="utf-8")
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
        env=_CHILD_ENV,
    )
    assert proc.returncode == 0, f"ingest 子进程失败:\n{proc.stdout}\n{proc.stderr}"
    rows = [
        json.loads(line)
        for line in (code_root / "facts" / "claims.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1, f"应产出 1 条 claim，实得 {len(rows)}"
    return rows[0]


def test_real_ingested_claim_passes(code_root: Path) -> None:
    """**AC-01 真跑通**：真跑采集 → 真实 claim → 真实校验 → **exit 0**。"""
    row = _drive_ingest(code_root)
    assert row["status"] == "pending_verification"
    assert row["full_text_read"] is False
    assert row["locator"].startswith("raw/")
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 0, proc.stdout
    assert "RESULT: PASS" in proc.stdout


# ───────────────────────── 守卫真拦得住：full_text_read 越界 ─────────────────────────


def test_partial_locator_with_full_text_true_rejected(code_root: Path) -> None:
    """**AC-04**：`full_text_read=true` 但定位仅覆盖部分行 → `FULL_TEXT_UNPROVEN` → **exit 1**。"""
    _write_raw(code_root, "doc.txt", "l1\nl2\nl3\n")
    _write_claims(
        code_root,
        [_base_claim(locator="raw/doc.txt#L1-L2", full_text_read=True, quote_hash=_sha("l1\nl2\nl3\n"))],
    )
    assert_rejected(run_gate(GUARD, code_root))


def test_quote_hash_mismatch_rejected(code_root: Path) -> None:
    """全文主张但 `quote_hash` 与原文不符 → `QUOTE_HASH_MISMATCH` → exit 1。"""
    text = "l1\nl2\nl3\n"
    _write_raw(code_root, "doc.txt", text)
    _write_claims(
        code_root,
        [_base_claim(locator="raw/doc.txt#L1-L3", full_text_read=True, quote_hash="0" * 64)],
    )
    assert_rejected(run_gate(GUARD, code_root))


def test_full_text_true_with_whole_locator_and_matching_hash_passes(code_root: Path) -> None:
    """正向对照：定位覆盖整份原文 **且** `quote_hash == sha256(原文)` → 证明成立 → exit 0。"""
    text = "l1\nl2\nl3\n"
    _write_raw(code_root, "doc.txt", text)
    _write_claims(
        code_root,
        [_base_claim(locator="raw/doc.txt#L1-L3", full_text_read=True, quote_hash=_sha(text))],
    )
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 0, proc.stdout
    assert "RESULT: PASS" in proc.stdout


def test_full_text_unsupported_by_source_rejected(code_root: Path) -> None:
    """来源 `obtainable_content_type` 非全文可获取 → 不得出'读过全文'主张（`Ch6 N6.1-07`）→ exit 1。"""
    text = "l1\nl2\n"
    _write_raw(code_root, "doc.txt", text)
    _write_sources(code_root, [{"source_id": "src-1", "obtainable_content_type": "summary"}])
    _write_claims(
        code_root,
        [_base_claim(locator="raw/doc.txt#L1-L2", full_text_read=True, quote_hash=_sha(text))],
    )
    assert_rejected(run_gate(GUARD, code_root))


# ───────────────────────── 错误路径：定位缺失 / 非机械 / 越界 ─────────────────────────


def test_missing_locator_rejected(code_root: Path) -> None:
    """**AC-05**：`locator` 为空 → `LOCATOR_MISSING` → exit 1。"""
    _write_claims(code_root, [_base_claim(locator="")])
    assert_rejected(run_gate(GUARD, code_root))


def test_unrecognized_locator_rejected(code_root: Path) -> None:
    """**AC-05**：非机械可复查的自由文本定位（`"p.12"`）→ `LOCATOR_UNRECOGNIZED` → exit 1。"""
    _write_claims(code_root, [_base_claim(locator="p.12")])
    assert_rejected(run_gate(GUARD, code_root))


def test_locator_path_escape_rejected(code_root: Path) -> None:
    """**AC-05**：定位路径穿越（`raw/../rules/...`）→ `LOCATOR_ESCAPE` → exit 1。"""
    _write_claims(code_root, [_base_claim(locator="raw/../rules/banned_tokens.yaml#L1-L2")])
    assert_rejected(run_gate(GUARD, code_root))


def test_locator_unresolvable_rejected(code_root: Path) -> None:
    """定位指向不存在的原文 → `LOCATOR_UNRESOLVABLE` → exit 1。"""
    _write_claims(code_root, [_base_claim(locator="raw/absent.txt#L1-L2")])
    assert_rejected(run_gate(GUARD, code_root))


def test_range_out_of_bounds_rejected(code_root: Path) -> None:
    """定位区间超出原文行数 → `LOCATOR_RANGE_OUT_OF_BOUNDS` → exit 1。"""
    _write_raw(code_root, "doc.txt", "l1\nl2\n")
    _write_claims(code_root, [_base_claim(locator="raw/doc.txt#L1-L5")])
    assert_rejected(run_gate(GUARD, code_root))


def test_undisclosed_locator_allowed_when_not_full(code_root: Path) -> None:
    """显式"未披露"哨兵 + `full_text_read=false` → 合法降级 → exit 0。"""
    _write_claims(
        code_root,
        [_base_claim(locator="未披露（来源未提供可定位信息）", full_text_read=False)],
    )
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 0, proc.stdout


def test_undisclosed_locator_with_full_text_rejected(code_root: Path) -> None:
    """显式"未披露"哨兵**不得**配 `full_text_read=true` → `FULL_TEXT_UNPROVEN` → exit 1。"""
    _write_claims(
        code_root,
        [_base_claim(locator="未披露（来源未提供可定位信息）", full_text_read=True)],
    )
    assert_rejected(run_gate(GUARD, code_root))


# ───────────────────────── 错误路径：三字段维度不同（R-17） ─────────────────────────


def test_three_fields_swapped_rejected(code_root: Path) -> None:
    """**AC-05 三字段互换**：`claim_form` 取值塞进 `claim_nature` → `CLAIM_SCHEMA_INVALID` → exit 1。"""
    _write_claims(code_root, [_base_claim(claim_nature="estimate")])
    assert_rejected(run_gate(GUARD, code_root))


def test_official_claim_kind_on_non_primary_rejected(code_root: Path) -> None:
    """`official_claim_kind` **仅适用** `tier=primary` → 非 primary 出现即 `OFFICIAL_KIND_TIER_MISMATCH` → exit 1。"""
    _write_raw(code_root, "doc.txt", "l1\nl2\n")
    _write_claims(
        code_root,
        [
            _base_claim(
                locator="raw/doc.txt#L1-L2",
                official_claim_kind="occurred_fact",
                tier="secondary_tertiary",
            )
        ],
    )
    assert_rejected(run_gate(GUARD, code_root))


# ───────────────────────── 边界：非法枚举 / 时间倒挂 / 超大 ─────────────────────────


def test_illegal_enum_value_rejected(code_root: Path) -> None:
    """**AC-06**：`claim_nature="bogus"` → `CLAIM_SCHEMA_INVALID` → exit 1。"""
    _write_claims(code_root, [_base_claim(claim_nature="bogus")])
    assert_rejected(run_gate(GUARD, code_root))


def test_time_inversion_rejected(code_root: Path) -> None:
    """**AC-06**：`published_at` 晚于 `first_seen_at`（时间倒挂）→ `TIME_INVERSION` → exit 1。"""
    _write_claims(
        code_root,
        [
            _base_claim(
                locator="未披露（无）",
                published_at="2026-09-16T02:00:00+00:00",
                first_seen_at="2026-09-16T00:00:00+00:00",
            )
        ],
    )
    assert_rejected(run_gate(GUARD, code_root))


def test_large_claims_file_single_pass_is_fast(code_root: Path) -> None:
    """**AC-06 超大**：1500 条合法主张 → 单遍扫描、exit 0、耗时 < 5s（`P-01`）。"""
    _write_raw(code_root, "doc.txt", "l1\nl2\nl3\n")
    rows = [
        _base_claim(
            claim_id=f"clm-{i}",
            source_id=f"src-{i}",
            quote_hash=f"{i:064d}",
            locator="raw/doc.txt#L1-L3",
        )
        for i in range(1500)
    ]
    _write_claims(code_root, rows)
    started = time.monotonic()
    proc = run_gate(GUARD, code_root)
    elapsed = time.monotonic() - started
    assert proc.returncode == 0, proc.stdout
    assert elapsed < 5.0, f"单遍扫描耗时过长：{elapsed:.2f}s"


@pytest.mark.parametrize("code", ["CLAIM_SCHEMA_INVALID", "LOCATOR_MISSING"])
def test_problem_codes_are_reported(code_root: Path, code: str) -> None:
    """违例码出现在进程输出（可机读，便于 CI / 审计定位）。"""
    if code == "CLAIM_SCHEMA_INVALID":
        _write_claims(code_root, [_base_claim(claim_form="bogus_form")])
    else:
        _write_claims(code_root, [_base_claim(locator="")])
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 1, proc.stdout
    assert code in proc.stdout
