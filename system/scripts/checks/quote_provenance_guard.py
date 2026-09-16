#!/usr/bin/env python3
"""`quote_provenance_guard.py` —— **引文溯源守卫**（反编造；`CONVENTIONS.md §一 V-*` / `§二 G-*`）。

## 它守什么（一句话）

**每一条 claim 的 `quote_hash` 必须等于其 `locator` 所指 `raw/` 行区间的 sha256。**
引文与原始物之间因此是**内容等价**的机械绑定，而不是"模型说它引了"。

## 为什么需要它（既有盲区，缺口 `G-B10-05`）

`scripts/validators/locator_check.py` 判据 4 只在 `full_text_read == true` 时校验
`quote_hash == sha256(整份原文)`；而真实入真源的主张**全部**是 `full_text_read == false`
（引文级定位只覆盖片段）。于是出现一个**空档**：

    locator 覆盖全篇 + quote_hash 与原文相符 + full_text_read=false
        → 既有校验器**不发声**（它把该行归类为"未主张读过全文"，于是不比 hash）

而真实风险恰恰在这里：`full_text_read=false` 的 claim 数量最多、来源最杂，
却是**唯一**没有任何"引文↔原文"机械校验的一类。

→ 本守卫**只管辖 `full_text_read == false` 的 claim**（互补而非重复）：
  该类逐条断言区间绑定；`full_text_read == true` 的 claim 仍由 `locator_check.py`
  判据 4/5 覆盖（本守卫只**计数**并记 note，声明管辖边界 —— `G-03`：不把"不归我管"
  伪装成"我验过了"）。

## 判据（可判定 + 穷尽 + 二值；`R-06` ①②）

管辖范围 = `full_text_read == false` 的全部 claim；其中**每一步都是确定的算法**，
不存在"可疑/可能/待定"第三态：

| # | 判据 | 违例码 |
|---|---|---|
| 1 | `locator` 非空 | `QUOTE_LOCATOR_MISSING` |
| 2 | `locator` 形如 `raw/<relpath>#L<a>-L<b>`，**或**为显式"未披露"哨兵 | `QUOTE_LOCATOR_UNRECOGNIZED` |
| 3 | `raw/<relpath>` 落在 `raw/` 内且为常规可读文件 | `QUOTE_LOCATOR_ESCAPE` / `QUOTE_LOCATOR_UNRESOLVABLE` |
| 4 | `1 ≤ a ≤ b ≤ 原文行数` | `QUOTE_LOCATOR_RANGE_OUT_OF_BOUNDS` |
| 5 | `quote_hash` 非空 | `QUOTE_HASH_MISSING` |
| 6 | ★ `sha256(locator 区间文本) == quote_hash` | `QUOTE_PROVENANCE_MISMATCH` |

判据 2 的两支（机械可解析的 `raw/` 定位 / 显式"未披露"哨兵）**穷尽且互斥**，
其余一律 `QUOTE_LOCATOR_UNRECOGNIZED`（默认拒绝，`R-06` ⑤ allowlist 语义）。

判据 3 复用 `locator_check._resolve_raw_artifact` 做解析，但它的裸码
（`LOCATOR_ESCAPE` / `LOCATOR_UNRESOLVABLE`）**必须收编进本守卫声明的码域**
（→ `QUOTE_LOCATOR_ESCAPE` / `QUOTE_LOCATOR_UNRESOLVABLE`，见 `_namespaced`）：
否则"每条 claim 的判定只落在 `QUOTE_CODES` 里"这句声明就是假的 ——
调用方据此断言码域时会被外部码打穿。

判据 6 的区间文本取法（**逐字**，含行尾换行）：

    "".join(text.splitlines(keepends=True)[a-1 : b])

`a==1 and b==原文行数` 时它**恒等于**原文本身 —— 故"覆盖全篇"的 claim 走同一公式，
退化为 `sha256(整份原文)`（与 `scripts.guard.executor._derive_quote_hash` 同值）。
**同一公式、无第二套语义**。

## ★ 本守卫的计算**刻意不**复用被验证方的实现

区间切片在此**独立实现**（不复用 `scripts/ingest/real_collector.py::_quote_segment`）：
若守卫调用被验证方来计算判据，则"改一行采集代码"即可让证据与判据**同时**改变 ——
那是自证同义、不是防护。**独立实现是判据有效性的前提**，不是重复代码。
（`locator` 的**语法解析**则复用 `locator_check.parse_raw_locator`：
那是两个校验器之间的共享契约，不构成"被验证方可以改判据"。）

## 退出码（`G-01`）

`0` 放行 / `1` 命中违例（命中即 fail，禁 warn-only）/ `2` 输入异常
（`code_root` 缺失 / **真源 JSONL 缺失** / JSONL 损坏）。

「真源 `facts/claims.jsonl` **缺失**」与「存在但 0 行」是**两件事**（`G-03`）：
前者是结构性违例（`Ch9 §3.3.3`：18 个 JSONL 不得增删改名）→ `exit 2`；
后者真空成立 → 显式 `NO_CLAIMS` note + `exit 0`。

## 空样本与降级（`R-03`）

- 0 条 claim → `NO_CLAIMS` note + `exit 0`（真空成立，**不**等于已验证）；
- 有 claim 走"未披露"支 → **显式计数** `scanned claims_without_locator: N`，
  并在 note 里声明"这些主张**未**经本守卫核验"。
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402
from scripts.validators.locator_check import (  # noqa: E402
    UNDISCLOSED_PREFIX,
    _resolve_raw_artifact,
    parse_raw_locator,
)

QUOTE_CODES = frozenset(
    {
        "QUOTE_LOCATOR_MISSING",
        "QUOTE_LOCATOR_UNRECOGNIZED",
        "QUOTE_LOCATOR_ESCAPE",
        "QUOTE_LOCATOR_UNRESOLVABLE",
        "QUOTE_LOCATOR_RANGE_OUT_OF_BOUNDS",
        "QUOTE_HASH_MISSING",
        "QUOTE_PROVENANCE_MISMATCH",
    }
)
"""本守卫的违例码域（穷尽：每条 claim 的判定只会落在这里面）。"""


def _segment(text: str, first_line: int, last_line: int) -> str:
    """取原文第 `first_line`..`last_line` 行的**逐字切片**（1-based 闭区间，含行尾换行）。

    ★ 独立实现（见模块 docstring「刻意不复用被验证方的实现」）。公式与采集侧
      `real_collector._quote_segment` 逐字相同 —— 但**不是**同一份代码。
    """
    return "".join(text.splitlines(keepends=True)[first_line - 1 : last_line])


def _is_undisclosed(locator: str) -> bool:
    """`locator` 是否为显式"未披露"哨兵（复用 `locator_check` 的同一前缀常量）。"""
    return locator.startswith(UNDISCLOSED_PREFIX)


_RAW_ARTIFACT_CODE_PREFIX = "LOCATOR_"
"""`_resolve_raw_artifact` 的码前缀（`locator_check` 域）。"""

_OUR_CODE_PREFIX = "QUOTE_LOCATOR_"
"""本守卫对应的码前缀（`QUOTE_CODES` 域）。"""

_RAW_ARTIFACT_CODES = ("LOCATOR_ESCAPE", "LOCATOR_UNRESOLVABLE")
"""`_resolve_raw_artifact` **实际会产出**的全部码（读源码逐一核对；见 `locator_check.py:107-121`）。

上游若新增码，`_assert_code_domain_covered()` 在导入期即失败 ——
`R-06` 要求判据穷尽，穷尽性必须是**被机器检查的**，不能只是注释里的一句承诺。
"""


def _namespaced(code: str, detail: str) -> tuple[str, str]:
    """把 `locator_check` 传来的裸码**收编进本守卫声明的 `QUOTE_CODES` 域**。

    本守卫声明"每条 claim 的判定只落在 `QUOTE_CODES` 里"（穷尽性承诺），
    因此不得把 `LOCATOR_ESCAPE` 之类的**外部码**原样透传出去 ——
    那会让"输出码在声明域内"这条性质变成假的。

    映射是**机械的**（`LOCATOR_X` → `QUOTE_LOCATOR_X`），不是人工清单；
    若上游将来新增一个本守卫尚未声明的码，则**降级为 `QUOTE_LOCATOR_UNRESOLVABLE`
    并把原始码写进 detail**（不静默、不丢信息）。
    """
    if code.startswith(_RAW_ARTIFACT_CODE_PREFIX):
        mapped = f"{_OUR_CODE_PREFIX}{code[len(_RAW_ARTIFACT_CODE_PREFIX):]}"
        if mapped in QUOTE_CODES:
            return (mapped, detail)
    return (
        "QUOTE_LOCATOR_UNRESOLVABLE",
        f"[上游码 {code!r} 不在本守卫声明域内，已降级] {detail}",
    )


def _assert_code_domain_covered() -> None:
    """导入期自检：`_resolve_raw_artifact` 的每个可能码都能收编进 `QUOTE_CODES`。"""
    for code in _RAW_ARTIFACT_CODES:
        mapped = f"{_OUR_CODE_PREFIX}{code[len(_RAW_ARTIFACT_CODE_PREFIX):]}"
        assert mapped in QUOTE_CODES, (
            f"{code} 无法收编进 QUOTE_CODES（映射为 {mapped}）—— "
            "判据声明的穷尽性与实现不一致（R-06）"
        )


_assert_code_domain_covered()


def claim_quote_problems(claim: Mapping[str, Any], root: Path) -> list[tuple[str, str]]:
    """校验**单条** claim 的引文溯源，返回 `[(违例码, 说明)]`（空列表 = 该条通过）。

    ★ 只处理 `full_text_read == false` 的 claim；`true` 的由 `locator_check.py` 管辖，
      此处返回空列表并**不**意味着"已核验"（调用方按 `scanned` 计数区分）。
    """
    locator = str(claim.get("locator") or "").strip()
    if not locator:
        return [
            (
                "QUOTE_LOCATOR_MISSING",
                "locator 为空 —— 引文无法回溯到 raw/ 落点（Ch9 §3.4.6 措施①/②）",
            )
        ]

    parsed = parse_raw_locator(locator)
    if parsed is None:
        if _is_undisclosed(locator):
            return []  # 显式"未披露"分支：允许，由调用方计数（不得当"已核验"）
        return [
            (
                "QUOTE_LOCATOR_UNRECOGNIZED",
                "locator 既非 raw/<relpath>#L<a>-L<b>，也非显式未披露 —— "
                f"引文不可机械复查: {locator!r}",
            )
        ]

    relpath, start, end = parsed
    resolved = _resolve_raw_artifact(root, relpath)
    if not resolved.ok:
        # ★ 收编进本守卫的码域（见 `_namespaced`）：不得把 locator_check 的裸码透传出去。
        return [_namespaced(resolved.code, resolved.detail)]
    if not (1 <= start <= end <= resolved.line_count):
        return [
            (
                "QUOTE_LOCATOR_RANGE_OUT_OF_BOUNDS",
                f"定位区间 L{start}-L{end} 越界（原文共 {resolved.line_count} 行）",
            )
        ]

    quote_hash = str(claim.get("quote_hash") or "")
    if not quote_hash:
        return [("QUOTE_HASH_MISSING", "quote_hash 为空 —— 引文指纹缺失（Ch9 §3.5 ②行）")]

    expected = hashlib.sha256(
        _segment(resolved.text, start, end).encode("utf-8")
    ).hexdigest()
    if quote_hash != expected:
        return [
            (
                "QUOTE_PROVENANCE_MISMATCH",
                f"quote_hash 与 locator 所指原文区间（{relpath} L{start}-L{end}, "
                f"共 {end - start + 1} 行）的 sha256 不符 —— "
                "引文与 raw/ 落点不是同一条内容（反编造：该主张不能回溯到已落盘的抓取物）",
            )
        ]
    return []


def check(root: Path) -> CheckReport:
    """单遍扫描 `facts/claims.jsonl`，逐条复查引文溯源（`P-01`）。"""
    from schema.store import TRUTH_MISSING, read_records, truth_source_status

    report = CheckReport(checker="quote_provenance_guard.py")
    if truth_source_status(root, "claims") == TRUTH_MISSING:
        raise FileNotFoundError(
            "facts/claims.jsonl 缺失 —— Ch9 §3.3.3 规定 facts/ 下 18 个 JSONL 不得增删改名，"
            "文件缺失即结构性违例（与'存在但 0 行'不同；G-03：不得把'无被检对象'当'已验证'）"
        )

    claims = read_records(root, "claims")
    report.scanned["claims"] = len(claims)
    if not claims:
        report.notes.append(
            "NO_CLAIMS: facts/claims.jsonl 为空 —— 无被检对象（真空成立，非'已验证'，G-03）"
        )
        return report

    checked = 0
    without_locator = 0
    delegated = 0

    for lineno, claim in enumerate(claims, start=1):
        # ── 管辖边界：full_text_read=true 的 claim 由 locator_check.py 判据 4/5 覆盖 ──
        if bool(claim.get("full_text_read")):
            delegated += 1
            continue
        if _is_undisclosed(str(claim.get("locator") or "").strip()):
            without_locator += 1
        checked += 1
        for code, detail in claim_quote_problems(claim, root):
            report.violations.append(
                Violation(rule=code, reason=detail, file="facts/claims.jsonl", line=lineno)
            )

    report.scanned["claims_checked"] = checked
    report.scanned["claims_without_locator"] = without_locator
    report.scanned["claims_delegated_full_text"] = delegated
    report.notes.append(
        f"GOVERNED_SCOPE: 本守卫管辖 full_text_read=false 的 claim（{checked} 条）；"
        f"full_text_read=true 的 {delegated} 条由 locator_check.py 判据 4/5 管辖 —— "
        "不计入本守卫的通过结论（G-03）"
    )
    if without_locator:
        report.notes.append(
            f"CLAIMS_WITHOUT_LOCATOR: {without_locator} 条 claim 的 locator 为显式'未披露' —— "
            "**未**经本守卫核验（显式计数，不得当'已验证'）"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    return run_checker("quote_provenance_guard.py", check, argv)


if __name__ == "__main__":
    sys.exit(main())
