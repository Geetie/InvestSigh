"""`quote_provenance_guard.py` 的注入 / 反向对照测试。

反编造守卫的**唯一**有效性证据链是这两条同时成立：

| 方向 | 输入 | 期望 |
|---|---|---|
| **必拦** | 引文与该 claim 的 `locator` 所指 `raw/` 区间**不是同一条内容** | `exit 1` |
| **不误伤** | 引文与区间**逐字同源** | `exit 0` |

只证"能拦"不够（把所有输入都拒掉也能"能拦"）；只证"不误伤"也不够
（什么都不查自然不误伤）。故本文件每条"必拦"用例都配一条同型的"不误伤"对照，
并另有一条把**同一份数据改一个字节**的对照 —— 那是判据灵敏度的直接度量。

## 管辖边界也是一条判据

`full_text_read == true` 的 claim **不归本守卫管**（由 `locator_check.py` 判据 4/5 管）。
本文件显式守住这一点：即便把这种 claim 的 `quote_hash` 改成明显的假值，
本守卫也**应当**放行 —— 但它必须**如实计数**（`claims_delegated_full_text`），
**不得**把"不归我管"说成"我验过了"（`CONVENTIONS.md::G-03`）。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import SYSTEM_ROOT, run_gate_inproc

GUARD = "scripts/checks/quote_provenance_guard.py"
RAW_NAME = "2026-01-02-demo-source.txt"

# 三个物理行的原文（含行尾换行）。`_segment` 的语义：1-based 闭区间、逐字、含行尾换行。
TEXT = "# source_url: https://example.invalid/demo\n\nAlpha revenue was $1.0 billion\nBeta revenue was $2.0 billion\n"


def _segment(first: int, last: int, text: str = TEXT) -> str:
    return "".join(text.splitlines(keepends=True)[first - 1 : last])


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_raw(code_root: Path, text: str = TEXT, name: str = RAW_NAME) -> None:
    raw_dir = code_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / name).write_text(text, encoding="utf-8")


def _append_claim(code_root: Path, **overrides: object) -> dict:
    """向副本的 `facts/claims.jsonl` 追加一行（**只**写本测试自己的数据）。"""
    row: dict[str, object] = {
        "claim_id": "claim-demo-000000000000",
        "source_id": "demo-source",
        "quote_hash": _sha(_segment(3, 3)),
        "claim_nature": "fact",
        "claim_form": "citation",
        "tier": "secondary_tertiary",
        "locator": f"raw/{RAW_NAME}#L3-L3",
        "full_text_read": False,
        "recorded_seq": 1,
    }
    row.update(overrides)
    path = code_root / "facts" / "claims.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def _run(code_root: Path) -> tuple[int, str]:
    return run_gate_inproc(GUARD, code_root)


# ═══════════════ 反向对照（不误伤）：真引文必须放行 ═══════════════


def test_quote_hash_of_exact_segment_passes(code_root: Path) -> None:
    """引文 = locator 所指区间 → **exit 0**（该放的必须放）。"""
    _write_raw(code_root)
    _append_claim(code_root, locator=f"raw/{RAW_NAME}#L3-L3", quote_hash=_sha(_segment(3, 3)))
    code, out = _run(code_root)
    assert code == 0, f"同源引文被误拦\n{out}"
    assert "scanned claims: 1" in out, out


def test_full_span_quote_hash_equals_whole_file_hash(code_root: Path) -> None:
    """区间覆盖全篇时，判据退化为 `sha256(整份原文)`（与既有 executor 路径同值）。"""
    _write_raw(code_root)
    total = len(TEXT.splitlines())
    _append_claim(
        code_root,
        locator=f"raw/{RAW_NAME}#L1-L{total}",
        quote_hash=_sha(TEXT),
    )
    code, out = _run(code_root)
    assert code == 0, f"全篇覆盖的同源引文被误拦\n{out}"


def test_multi_line_segment_passes(code_root: Path) -> None:
    """多行区间（含行尾换行的逐字切片）→ exit 0。"""
    _write_raw(code_root)
    _append_claim(code_root, locator=f"raw/{RAW_NAME}#L3-L4", quote_hash=_sha(_segment(3, 4)))
    code, out = _run(code_root)
    assert code == 0, f"多行区间同源引文被误拦\n{out}"


def test_undisclosed_locator_is_allowed_but_counted(code_root: Path) -> None:
    """显式"未披露"哨兵 → 放行，但**必须显式计数**（不得当"已核验"）。"""
    _write_raw(code_root)
    _append_claim(code_root, locator="未披露（来源未提供可定位信息）", quote_hash=_sha("任意"))
    code, out = _run(code_root)
    assert code == 0, f"'未披露'是合法显式取值，不应被拦\n{out}"
    assert "claims_without_locator: 1" in out, f"未显式计数（不得当'已验证'）\n{out}"


def test_full_text_read_true_is_delegated_not_silently_passed(code_root: Path) -> None:
    """**管辖边界**：`full_text_read=true` 由 `locator_check.py` 管 —— 本守卫放行但**如实计数**。

    这里故意给一个与区间不符的 `quote_hash`：本守卫**不应**报它
    （否则与 `locator_check` 判据 4 形成两条同类校验路径），
    但**必须**在 `scanned` 里声明它不归本守卫管 —— 否则"没查"会被读成"查过了没问题"。
    """
    _write_raw(code_root)
    _append_claim(
        code_root,
        locator=f"raw/{RAW_NAME}#L3-L3",
        quote_hash=_sha("显然不是这一行"),
        full_text_read=True,
    )
    code, out = _run(code_root)
    assert code == 0, f"full_text_read=true 属 locator_check 管辖，本守卫不应报\n{out}"
    assert "claims_delegated_full_text: 1" in out, f"未声明管辖边界（G-03）\n{out}"
    assert "claims_checked: 0" in out, out


# ═══════════════ 必拦：编造 / 失配 / 不可定位 ═══════════════


def test_fabricated_quote_hash_is_rejected(code_root: Path) -> None:
    """★ 核心：`quote_hash` 与区间内容不符（编造引文）→ **exit 1**。"""
    _write_raw(code_root)
    _append_claim(
        code_root,
        locator=f"raw/{RAW_NAME}#L3-L3",
        quote_hash=_sha("Alpha revenue was $9.9 billion\n"),  # 凭空写出的数字
    )
    code, out = _run(code_root)
    assert code == 1, f"编造引文未拦下（门禁失效）\n{out}"
    assert "QUOTE_PROVENANCE_MISMATCH" in out, out


def test_one_byte_change_in_raw_makes_existing_hash_stale(code_root: Path) -> None:
    """★ 灵敏度对照：**改动原文一个字节**，原本正确的 claim 立刻失配 → exit 1。

    这条与上一条配对，证明判据真的在读 `raw/` 内容，而不是在比对两个常量。
    """
    _write_raw(code_root)
    _append_claim(code_root, locator=f"raw/{RAW_NAME}#L3-L3", quote_hash=_sha(_segment(3, 3)))
    code_before, _ = _run(code_root)
    assert code_before == 0

    # 只把 $1.0 改成 $1.1 —— 行数不变、locator 不变、quote_hash 不变
    _write_raw(code_root, TEXT.replace("$1.0 billion", "$1.1 billion"))
    code_after, out = _run(code_root)
    assert code_after == 1, f"原文改了却仍放行 —— 判据没在读原文\n{out}"
    assert "QUOTE_PROVENANCE_MISMATCH" in out, out


def test_missing_raw_artifact_is_rejected(code_root: Path) -> None:
    """`locator` 指向不存在的 `raw/` 文件 → **exit 1**（不得静默放过）。"""
    _append_claim(code_root, locator="raw/2026-01-02-never-fetched.txt#L1-L1")
    code, out = _run(code_root)
    assert code == 1, f"不可定位的 claim 未拦下\n{out}"
    assert "QUOTE_LOCATOR_UNRESOLVABLE" in out, out


def test_range_out_of_bounds_is_rejected(code_root: Path) -> None:
    """行区间越界 → **exit 1**。"""
    _write_raw(code_root)
    total = len(TEXT.splitlines())
    _append_claim(
        code_root,
        locator=f"raw/{RAW_NAME}#L1-L{total + 5}",
        quote_hash=_sha(TEXT),
    )
    code, out = _run(code_root)
    assert code == 1, f"越界区间未拦下\n{out}"
    assert "QUOTE_LOCATOR_RANGE_OUT_OF_BOUNDS" in out, out


def test_unrecognized_locator_is_rejected(code_root: Path) -> None:
    """`locator` 非规定形式（既非 `raw/…` 区间，也非显式"未披露"）→ **exit 1**。"""
    _write_raw(code_root)
    _append_claim(code_root, locator="https://example.invalid/demo")
    code, out = _run(code_root)
    assert code == 1, f"非机械可复查的 locator 未拦下\n{out}"
    assert "QUOTE_LOCATOR_UNRECOGNIZED" in out, out


def test_empty_locator_is_rejected(code_root: Path) -> None:
    """`locator` 为空 → **exit 1**（空串不得被当成合法取值）。"""
    _write_raw(code_root)
    _append_claim(code_root, locator="")
    code, out = _run(code_root)
    assert code == 1, f"空 locator 未拦下\n{out}"
    assert "QUOTE_LOCATOR_MISSING" in out, out


def test_path_traversal_locator_is_rejected(code_root: Path) -> None:
    """`locator` 借 `..` 逃出 `raw/`（去读 `rules/`）→ **exit 1**。"""
    _write_raw(code_root)
    _append_claim(code_root, locator="raw/../rules/freeze.yaml#L1-L1")
    code, out = _run(code_root)
    assert code == 1, f"路径穿越未拦下\n{out}"
    assert "QUOTE_LOCATOR_ESCAPE" in out, out


def test_empty_quote_hash_is_rejected(code_root: Path) -> None:
    """`quote_hash` 为空 → **exit 1**（没有指纹就无法绑定）。"""
    _write_raw(code_root)
    _append_claim(code_root, locator=f"raw/{RAW_NAME}#L3-L3", quote_hash="")
    code, out = _run(code_root)
    assert code == 1, f"空 quote_hash 未拦下\n{out}"
    assert "QUOTE_HASH_MISSING" in out, out


def test_every_emitted_code_lies_in_declared_domain(code_root: Path) -> None:
    """★ **穷尽性**：守卫**实际产出**的每个码都必须落在它**声明的** `QUOTE_CODES` 里（`R-06`）。

    守卫在 docstring 里承诺"每条 claim 的判定只会落在 `QUOTE_CODES` 里"。
    本用例把承诺变成断言：跑遍全部必拦场景，从输出里抠出所有 `[FATAL] <CODE>`，
    逐一核对 ∈ `QUOTE_CODES`。

    ★ 为什么必须单独测（实测踩过）：判据 3 借用了 `locator_check._resolve_raw_artifact`，
      初版把它的**裸码** `LOCATOR_ESCAPE` / `LOCATOR_UNRESOLVABLE` 原样透传出去 ——
      门禁行为完全正确（照拦不误），但**声明域是假的**。
      没有这条用例，"声明穷尽"就只是一句注释。
    """
    from scripts.checks.quote_provenance_guard import QUOTE_CODES

    cases: tuple[tuple[str, dict[str, object]], ...] = (
        ("空 locator", {"locator": ""}),
        ("非规定形式", {"locator": "https://example.invalid/demo"}),
        ("指向不存在的 raw/ 文件", {"locator": "raw/2026-01-02-never-fetched.txt#L1-L1"}),
        ("路径穿越", {"locator": "raw/../rules/freeze.yaml#L1-L1"}),
        ("区间越界", {"locator": f"raw/{RAW_NAME}#L1-L{len(TEXT.splitlines()) + 5}"}),
        ("空 quote_hash", {"locator": f"raw/{RAW_NAME}#L3-L3", "quote_hash": ""}),
        ("编造引文", {"locator": f"raw/{RAW_NAME}#L3-L3", "quote_hash": _sha("编出来的\n")}),
    )
    _write_raw(code_root)
    emitted: set[str] = set()
    for label, override in cases:
        _append_claim(code_root, **override)
        code, out = _run(code_root)
        assert code == 1, f"{label} 应被拦下，实得 exit {code}\n{out}"
        for line in out.splitlines():
            if "[FATAL]" in line:
                emitted.add(line.split("[FATAL]", 1)[1].strip().split()[0])

    assert emitted, "一条码都没抠出来 —— 解析逻辑失效，本用例等于没跑"
    stray = emitted - set(QUOTE_CODES)
    assert not stray, (
        f"守卫输出了声明域之外的码 {sorted(stray)} —— "
        f"QUOTE_CODES 的'穷尽性'是假的（声明域 {sorted(QUOTE_CODES)}）"
    )


# ═══════════════ 空样本与输入异常（G-03 / G-01） ═══════════════


def test_empty_truth_source_passes_with_explicit_note(code_root: Path) -> None:
    """0 条 claim → `exit 0` + `scanned claims: 0` + `NO_CLAIMS` note（真空成立，非"已验证"）。"""
    code, out = _run(code_root)
    assert code == 0, out
    assert "scanned claims: 0" in out, out
    assert "NO_CLAIMS" in out, f"空样本必须显式记 note（G-03）\n{out}"


def test_missing_truth_source_is_input_error(code_root: Path) -> None:
    """真源 `facts/claims.jsonl` **缺失** → `exit 2`（结构性违例，不得与"0 行"混同）。"""
    (code_root / "facts" / "claims.jsonl").unlink()
    code, out = _run(code_root)
    assert code == 2, f"真源缺失应判输入异常（exit 2），实得 {code}\n{out}"


# ═══════════════ CLI 接线：真子进程拿到的退出码 ═══════════════


@pytest.mark.parametrize(
    ("label", "expect_code"),
    (("同源引文", 0), ("编造引文", 1)),
)
def test_cli_exit_code_reaches_shell(code_root: Path, label: str, expect_code: int) -> None:
    """★ 真子进程跑 CLI：证明 `sys.exit(main())` 把判据结论**真的**交给了 shell。

    进程内调用便宜，但"进程内 exit 1、命令行其实 exit 0"这种断法只有起真进程才看得见。
    """
    _write_raw(code_root)
    quote_hash = (
        _sha(_segment(3, 3)) if label == "同源引文" else _sha("编造的内容\n")
    )
    _append_claim(code_root, locator=f"raw/{RAW_NAME}#L3-L3", quote_hash=quote_hash)

    proc = subprocess.run(
        [sys.executable, str(SYSTEM_ROOT / GUARD), str(code_root), "--no-report"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == expect_code, (
        f"{label}：期望 exit {expect_code}，实得 {proc.returncode}\n{combined}"
    )
    assert "scanned claims: 1" in combined, combined
