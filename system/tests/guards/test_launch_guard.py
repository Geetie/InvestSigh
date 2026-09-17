"""`launch_guard.py`（付费非首版条件守卫）的**可执行反例 + 反向对照**。

被检对象：`scripts/checks/launch_guard.py`  ← 读 `registry/launch_criteria.yaml`
权威出处：`Ch11 §E.2` 红线二 / `N11.1-07`（源稿第 368 行）/ `N6.1-13` / `D-01`。

## 为什么这些用例必须存在（不是"顺手补测"）

2026-09-17 补 `tdx` 入白名单时发现：本守卫**此前零测试覆盖**，
且 `available_sources` 的校验被写死成 `if s.get("id") not in D01_SOURCE_IDS: continue`
—— 即**只认 `iFinD` / `pandadata` 两项**。后果：新补进来的 `tdx` 填的
`license_tier` / `cost` / `requires_paid_subscription` **一个都不会被校验**
（本仓反复出现的「**有声明、无消费者**」，`G-13` / `G-50` / `G-RC-12` 同族）。

⇒ 本文件的核心不是"守卫能拦付费源"（那是老功能），而是**证伪旧的窄口径写法**：

| 用例 | 注入点 | 若守卫仍是旧写法 | 意图 |
|---|---|---|---|
| `test_non_d01_source_without_license_tier_is_rejected` | **`tdx`**（非 D-01 项）删掉 `license_tier` | **exit 0（漏检）** | ★ **本文件最重要的那条**：证明新判据对**每一项**生效 |
| `test_non_d01_source_with_nonzero_cost_is_rejected` | **`tdx`** 的 `cost` 改 1 | **exit 0（漏检）** | 同上，另一条子判据 |
| `test_paid_source_in_available_is_rejected` | `available_sources` 加 `requires_paid_subscription: true` | exit 0（漏检） | 付费源不得出现在"可用来源" |
| `test_d01_license_tier_regression_is_rejected` | `iFinD` 的 tier 改成 `paid` | exit 1 | D-01 原有判据**不得因改动而失效** |
| `test_paid_required_is_rejected` | `required` 加付费项 | exit 1 | 红线二 |
| `test_optional_paid_without_deferred_is_rejected` | `optional` 付费项去掉 `deferred` | exit 1 | 红线二（可后置） |

★ 每条注入都**与反向对照跑在同一份副本上**，两次运行之间唯一的差别就是那次注入。
★ `施工图 §5.1 AC-04` 的口径：**注入违例 ⇒ 守卫 `exit 1`**（不是 warn）。
★ 本守卫**不探活**（只做静态清单校验）—— 故本文件**不**测"数据源实际可达"，
  那属另一个维度（见 `system/reports/mcp_setup_brief.md` §八-1）。
"""

from __future__ import annotations

from pathlib import Path

from conftest import run_gate_inproc

GUARD = "scripts/checks/launch_guard.py"
CRITERIA_REL = Path("registry") / "launch_criteria.yaml"

#: `tdx` 那一行（2026-09-17 补入）—— ★ **非 D-01 项**，正是旧写法会漏检的那类。
_TDX_LINE = "  - {id: tdx,       license_tier: free_quota, cost: 0, requires_paid_subscription: false}\n"
#: `iFinD` 那一行 —— D-01 项（老判据覆盖）。
_IFIND_LINE = "  - {id: iFinD,     license_tier: free_quota, cost: 0, requires_paid_subscription: false}\n"
#: `available_sources:` 段头 —— 用来在段首插入一个"新源"。
_AVAIL_ANCHOR = "available_sources:\n"

#: 真实登记在册的四个源（元断言用；★ 含 `tdx`，漏登会让本文件退化）。
_EXPECTED_IDS = {"westock", "iFinD", "pandadata", "tdx"}


def _patch(root: Path, old: str, new: str) -> None:
    """在副本里做**一次**精确替换（唯一差别 = 这次注入）。"""
    path = root / CRITERIA_REL
    text = path.read_text(encoding="utf-8")
    assert old in text, f"注入锚点不存在（夹具漂移，需同步本测试）：{old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _run(root: Path) -> tuple[int, str]:
    return run_gate_inproc(GUARD, root)


def test_clean_copy_passes(code_root: Path) -> None:
    """**反向对照（基准）**：不改任何东西 ⇒ `exit 0`。

    ★ 没有这一条，后面所有"注入即红"都无法区分"守卫在守"与"守卫恒红"。
    """
    code, out = _run(code_root)
    assert code == 0, f"干净副本应放行，实得 exit={code}\n{out}"


def test_scanned_covers_every_registered_source(code_root: Path) -> None:
    """元断言：守卫报出的 `available_sources` 计数 = 文件里真实登记项数（含 `tdx`）。

    ★ 为什么`: `scanned` 是**唯一**能证明"这些项被看过了"的信号。
      若哪天有人在 `available_sources` 下加了第 5 项而 `scanned` 没变，
      说明解析漏项 —— 那与新判据失效是同一个后果。
    """
    import yaml

    data = yaml.safe_load((code_root / CRITERIA_REL).read_text(encoding="utf-8"))
    ids = {s["id"] for s in data["available_sources"]}
    assert ids >= _EXPECTED_IDS, f"在册源少了：{_EXPECTED_IDS - ids}（元断言失败）"

    code, out = _run(code_root)
    assert code == 0, out
    assert f"scanned available_sources: {len(ids)}" in out, (
        f"`scanned` 计数应等于真实项数 {len(ids)} —— 不等即为解析漏项\n{out}"
    )


def test_every_registered_source_is_licensable(code_root: Path) -> None:
    """元断言：`available_sources` **每一项**都写明 `license_tier` / `cost` / `requires_paid_subscription`。

    ★ 这是对**新判据**的机器绑定：只要文件里出现"缺字段即拒"的情况，
      守卫会红；而本用例保证**当前**文件是完整的（否则守卫本身的红灯会被误读成代码 bug）。
    """
    import yaml

    data = yaml.safe_load((code_root / CRITERIA_REL).read_text(encoding="utf-8"))
    for s in data["available_sources"]:
        for field in ("license_tier", "cost", "requires_paid_subscription"):
            assert field in s, f"{s.get('id')}: 缺 {field} —— 无法判定许可（`N6.1-13`）"


# ══════════════ ★ 新判据（非 D-01 项也要被校验）══════════════
# 这两条是**本次改动的可证伪判据**：旧写法（`id not in D01_SOURCE_IDS → continue`）下必 exit 0。


def test_non_d01_source_without_license_tier_is_rejected(code_root: Path) -> None:
    """★ **反例（核心）**：把**非 D-01 项** `tdx` 的 `license_tier` 删掉 ⇒ 必须红。

    旧写法只认 `iFinD`/`pandadata` ⇒ `tdx` 被 `continue` 跳过 ⇒ **exit 0（漏检）**。
    "没写字段"不等于"免费"，故按 allowlist 语义（`R-06` ⑤）**缺字段即拒**。
    """
    _patch(code_root, _TDX_LINE, "  - {id: tdx, cost: 0, requires_paid_subscription: false}\n")
    code, out = _run(code_root)
    assert code == 1, (
        "非 D-01 项缺 `license_tier` 却放行 —— 说明校验仍被写死在 D01_SOURCE_IDS 上（漏检）\n" + out
    )
    assert "license_tier" in out and "N6.1-13" in out, out


def test_non_d01_source_with_nonzero_cost_is_rejected(code_root: Path) -> None:
    """★ **反例（核心）**：`tdx` 标 `free_quota` 但 `cost: 1` ⇒ 必须红（自相矛盾）。"""
    _patch(code_root, _TDX_LINE, _TDX_LINE.replace("cost: 0", "cost: 1"))
    code, out = _run(code_root)
    assert code == 1, f"非 D-01 项 `free_quota` 却有 cost 却放行（漏检）\n{out}"
    assert "cost" in out, out


def test_paid_source_in_available_is_rejected(code_root: Path) -> None:
    """★ **反例**：`available_sources` 里出现 `requires_paid_subscription: true` ⇒ 必须红。

    付费源只能出现在 `optional` 且 `deferred: true`（`Ch11 §E.2` 红线二）。
    """
    _patch(
        code_root,
        _AVAIL_ANCHOR,
        _AVAIL_ANCHOR + "  - {id: some_paid, license_tier: paid, cost: 999, requires_paid_subscription: true}\n",
    )
    code, out = _run(code_root)
    assert code == 1, f"付费源进了 available_sources 却放行\n{out}"
    assert "N11.1-07" in out, out


# ══════════════ 老判据不得因本次改动而失效 ══════════════


def test_d01_license_tier_regression_is_rejected(code_root: Path) -> None:
    """**反例**：`iFinD`（D-01 项）的 `license_tier` 改成 `paid` ⇒ 必须红（`D-01` 那条老判据仍在守）。

    ★ 与上面两条配对：证明"新判据是**加**上去的，不是把老判据换掉了"。
    """
    _patch(code_root, _IFIND_LINE, "  - {id: iFinD,     license_tier: paid, cost: 0, requires_paid_subscription: false}\n")
    code, out = _run(code_root)
    assert code == 1, f"D-01 项的 tier 被改坏却放行\n{out}"
    assert "D-01" in out, out


def test_paid_required_is_rejected(code_root: Path) -> None:
    """**反例**：`required`（首版启动条件）里塞一个付费项 ⇒ 必须红（红色二）。"""
    _patch(
        code_root,
        "required:",
        "required:\n  - {id: sneaky_paid, requires_paid_subscription: true, statement: '混进来的付费项'}",
    )
    code, out = _run(code_root)
    assert code == 1, f"`required` 含付费项却放行\n{out}"
    assert "N11.1-07" in out, out


def test_optional_paid_without_deferred_is_rejected(code_root: Path) -> None:
    """**反例**：`optional` 的付费项去掉 `deferred: true` ⇒ 必须红（必须可后置、不阻塞首版）。"""
    _patch(
        code_root,
        "  - id: paid_research_library\n    requires_paid_subscription: true\n    statement: \"新增付费研报库\"\n    deferred: true\n",
        "  - id: paid_research_library\n    requires_paid_subscription: true\n    statement: \"新增付费研报库\"\n",
    )
    code, out = _run(code_root)
    assert code == 1, f"optional 付费项未标 deferred 却放行\n{out}"
    assert "N11.1-07" in out, out


def test_missing_criteria_file_fails_loudly(code_root: Path) -> None:
    """**响亮失败**（`G-03`：不许把"无被检对象"当"已验证"）：清单缺失 ⇒ **exit 2** + `[INPUT-ERROR]`。

    ★ 断言的是 `_common.run_checker` 的统一约定：**输入异常 = 2**（`0` 放行 / `1` 阻断 / `2` 输入异常）。
      故这里**不能**用 `pytest.raises(FileNotFoundError)` —— `check()` 抛出的异常会被
      `run_checker` 捕获并**转成退出码 2**，不会传播到测试进程（实测 `DID NOT RAISE`）。
    ★ 反面：若它退化成 `exit 0`，就是"没有被检对象"被当成"验证通过"。
    """
    (code_root / CRITERIA_REL).unlink()
    code, out = _run(code_root)
    assert code == 2, f"清单缺失应 exit 2（输入异常），实得 {code} —— 若为 0 即『无对象当已验证』\n{out}"
    assert "[INPUT-ERROR]" in out and "launch_guard" in out, out
