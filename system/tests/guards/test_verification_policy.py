"""验证规范守卫的注入测试（`CONVENTIONS.md §一 V-01~V-06`）。

**本文件的用途是"防止规范被改回去"**：它断言的不是功能，而是
「这些绕过路径已不成立」。缺了它，下一次重构很容易把口子重新打开 ——
而本项目的铁律是**「声明与实现必须有机器绑定」**：只写在 `CONVENTIONS.md` 里的规范等于不存在。

覆盖 5 条绕过路径（全部是**真实可犯的错**，不是编出来的）：

| 反例 | 绕过方式 | 对应规范 |
|---|---|---|
| A | 让 `verify.py` 不带 `--batch` 也能跑（隐式全量） | V-01 |
| B | 加一个以裸 `tests` 为目标的"全量批次" | V-01 |
| C | 把某批超时设成 0 或不设上限 | V-02 |
| D | 把超时码 `124` 判成通过 | V-03 |
| E | 去掉 `run_pytest.sh` / `verify.py` 的 broker 关闭（测试又跑在沙箱里） | V-04 |
| F | 新增测试目录却不加批次（测试永远不被跑） | V-06 |
| G | 删掉 `verify.py` 的**第三道闸门** `CODEBUDDY_SAFE_DELETE_ENABLED` | V-04 |
| H | 删掉 `run_pytest.sh` 的**第三道闸门** | V-04 |
| I | ★ 文本里有第三道闸门、**运行时**派生环境里没有（声明↔实现脱节） | V-04 |
| J | ★ 删掉 `CONVENTIONS.md` 的 **V-02 批次表**里的一整行 / 把某行超时写成过期值 | V-02 |

★ G/H/I 是**第三道闸门**落地时补的：只关前两个 broker 变量时，每次删除仍会 spawn 一次
node CLI ⇒ 夹具批次照样打穿宿主**回合级**删除预算（`V-08`/`V-09`），症状是"后面所有建夹具的
用例集体报 `E`"，极易被读成"测试坏了"。三条闸门的**唯一真源** =
`scripts/checks/verification_policy_guard.py::BROKER_ENV_VARS`。
★ G/H 管**文本层**、I 管**运行时** —— **只测文本层会漏掉"写了却没进入子进程环境"**。
"""

from __future__ import annotations

import contextlib
import re

from pathlib import Path

import pytest

from conftest import assert_rejected, run_gate

GUARD = "scripts/checks/verification_policy_guard.py"
VERIFY_REL = "scripts/ops/verify.py"
RUN_PYTEST_REL = "scripts/ops/run_pytest.sh"


def _patch(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"注入失败：{rel} 中未找到锚点 {old[:60]!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


@contextlib.contextmanager
def _verify_module(root: Path, name: str = "_verify_under_binding_check"):
    """按**文件路径**加载夹具树里的 `verify.py`，`yield` 出模块对象。

    ★ 必须在 `exec_module` **之前**把模块登记进 `sys.modules`：`verify.py` 用了
      `@dataclass(frozen=True)`，而 `dataclasses` 会去 `sys.modules[cls.__module__]`
      取命名空间 ⇒ **不登记就 `AttributeError: 'NoneType' object has no attribute '__dict__'`**
      （本会话实测踩到）。
    ★ `finally` 复原 `sys.modules`：加载器带全局副作用，不还原会污染同会话的其它用例。
    """
    import importlib.util
    import sys as _sys

    path = root / VERIFY_REL
    assert path.exists(), f"缺少验证器: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"无法加载 {path}"
    module = importlib.util.module_from_spec(spec)
    _sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        _sys.modules.pop(name, None)


# ═══════════════ 反向对照（先证明守卫在干净树上不误报） ═══════════════

def test_policy_guard_passes_on_pristine_tree(code_root: Path) -> None:
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 0, f"干净树上验证规范守卫误报\n{proc.stdout}\n{proc.stderr}"
    # ★ **不要写死批次数**（初版断言 `"batches: 7"`，集成时统一加批次后即 11 →
    #   测试因"批次变多"而红。那是**脆断言**：把"实现细节的数量"当成契约。
    #   这里只断言与本测试目的相关的两件事：守卫跑通、覆盖检查无遗漏。
    assert re.search(r"batches: \d+", proc.stdout), "未上报批次数"
    assert "test_files_uncovered: 0" in proc.stdout


# ═══════════════ A · 隐式全量验证（V-01） ═══════════════

def test_implicit_full_run_is_rejected(code_root: Path) -> None:
    """让 `verify.py` 不带 `--batch` 也返回 0 → 必须 FAIL（那就是隐式全量验证）。"""
    _patch(code_root, VERIFY_REL, "return 0 if args.list else 2", "return 0")
    proc = run_gate(GUARD, code_root)
    assert_rejected(proc, rule_hint="V-01")
    assert "拒绝隐式全量验证" in proc.stdout


# ═══════════════ B · 全量批次（V-01） ═══════════════

def test_full_suite_batch_is_rejected(code_root: Path) -> None:
    """把某批目标改成裸 `tests`（全量）→ 必须 FAIL。"""
    _patch(
        code_root,
        VERIFY_REL,
        '_pytest("tests/test_ch11_invariants.py"), 30.0',
        '_pytest("tests"), 600.0',
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="全量批次")


def test_batch_target_outside_tests_is_rejected(code_root: Path) -> None:
    """批次目标指向 `tests/` 之外 → 必须 FAIL（防止把脚本/门禁混进 pytest 批次）。"""
    _patch(code_root, VERIFY_REL, '_pytest("tests/unit")', '_pytest("scripts")')
    assert_rejected(run_gate(GUARD, code_root), rule_hint="不在 tests/ 下")


# ═══════════════ C · 超时值不适合（V-02） ═══════════════

@pytest.mark.parametrize("bad_timeout", ["0.0", "9999.0"])
def test_unreasonable_timeout_is_rejected(bad_timeout: str, code_root: Path) -> None:
    """超时设为 0 或无上限（>300s）→ 必须 FAIL。"""
    _patch(
        code_root,
        VERIFY_REL,
        '_pytest("tests/conflict"), 30.0',
        f'_pytest("tests/conflict"), {bad_timeout}',
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="V-02")


# ═══════════════ D · 超时被判成通过（V-03） ═══════════════

def test_timeout_treated_as_pass_is_rejected(code_root: Path) -> None:
    """把超时码 124 的判定改成"通过" → 必须 FAIL。

    这是本规范里**最危险**的一种退化：卡死的批次若被当成通过，
    等于门禁整体失效（`V-03`：超时 = 该批有问题，绝不算通过）。
    """
    _patch(
        code_root,
        VERIFY_REL,
        '        return False, "**超时** —— 该批有问题（极大概率是测试本身）"',
        '        return True, "ok"',
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="V-03")


def test_timeout_verdict_without_keyword_is_rejected(code_root: Path) -> None:
    """超时判定返回不合格但**没说明是超时** → 仍必须 FAIL（要能被识别归因）。"""
    _patch(
        code_root,
        VERIFY_REL,
        '        return False, "**超时** —— 该批有问题（极大概率是测试本身）"',
        '        return False, "some failure"',
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="未说明")


# ═══════════════ E · 去掉沙箱外跑的修正（V-04） ═══════════════

def test_missing_broker_env_in_run_pytest_is_rejected(code_root: Path) -> None:
    """删掉 `run_pytest.sh` 里关闭 broker 的环境变量 → 必须 FAIL。"""
    _patch(code_root, RUN_PYTEST_REL, "export CODEBUDDY_SAFE_DELETE_SANDBOX=0", "# (removed)")
    assert_rejected(run_gate(GUARD, code_root), rule_hint="V-04")


def test_missing_broker_env_in_verify_is_rejected(code_root: Path) -> None:
    """删掉 `verify.py::_child_env` 里关闭 broker 的环境变量 → 必须 FAIL。"""
    _patch(
        code_root,
        VERIFY_REL,
        '"CODEBUDDY_BROKERED_FS_HOOK_ENABLED": "0",',
        "",
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="V-04")


# ═══════════════ G/H/I · 第三道闸门 `CODEBUDDY_SAFE_DELETE_ENABLED`（V-04） ═══════════════

def _load_child_env(root: Path) -> dict:
    """按**文件路径**加载夹具树里的 `verify.py`，返回 `_child_env()` 的结果。

    ★ 必须在 `exec_module` **之前**把模块登记进 `sys.modules`：`verify.py` 用了
      `@dataclass(frozen=True)`，而 `dataclasses` 会去 `sys.modules[cls.__module__]`
      取命名空间 ⇒ **不登记就 `AttributeError: 'NoneType' object has no attribute '__dict__'`**
      （本会话实测踩到）。`tests/injection/test_shard_coverage.py::_load_verify` 同法。
    ★ `try/finally` 复原 `sys.modules`：加载器带全局副作用，不还原会污染同会话的其它用例。
      （载入与复原已抽到 `_verify_module`，本节 J 的绑定复用同一份加载逻辑。）
    """
    with _verify_module(root) as module:
        return dict(module._child_env())


def test_missing_safe_delete_switch_in_verify_is_rejected(code_root: Path) -> None:
    """删掉 `verify.py::_child_env` 的**第三道闸门** → 必须 FAIL（文本层绑定）。"""
    _patch(code_root, VERIFY_REL, '"CODEBUDDY_SAFE_DELETE_ENABLED": "0",', "")
    assert_rejected(run_gate(GUARD, code_root), rule_hint="V-04")


def test_missing_safe_delete_switch_in_run_pytest_is_rejected(code_root: Path) -> None:
    """删掉 `run_pytest.sh` 的**第三道闸门** → 必须 FAIL（文本层绑定）。"""
    _patch(
        code_root,
        RUN_PYTEST_REL,
        "export CODEBUDDY_SAFE_DELETE_ENABLED=0",
        "# (removed)",
    )
    assert_rejected(run_gate(GUARD, code_root), rule_hint="V-04")


def test_child_env_actually_carries_all_three_switches(code_root: Path) -> None:
    """★ **运行时**断言：`_child_env()` 真的把**三道**闸门都置成了 `"0"`。

    上面 G/H 只证明守卫在**文本层面**要求它们；本用例补上另一半 ——
    **文本里有、运行时没有**同样是脱节（`G-02` 的立意：绑定要落在**函数体**上，
    而不是"某个文件里出现过这个字符串"）。
    """
    env = _load_child_env(code_root)
    for var in (
        "CODEBUDDY_SAFE_DELETE_SANDBOX",
        "CODEBUDDY_BROKERED_FS_HOOK_ENABLED",
        "CODEBUDDY_SAFE_DELETE_ENABLED",
    ):
        assert env.get(var) == "0", (
            f"派生环境里 {var} 不是 '0'，实际是 {env.get(var)!r} —— "
            "夹具会在沙箱里 copytree，即 V-04 被破"
        )


# ═══════════════ F · 新增测试却不入批（V-06） ═══════════════

def test_uncovered_new_test_file_is_rejected(code_root: Path) -> None:
    """新增一个**没有对应批次**的测试目录 → 必须 FAIL（否则它永远不被验证）。"""
    new_dir = code_root / "tests" / "brand_new_suite"
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "test_something.py").write_text(
        "def test_placeholder_free() -> None:\n    assert True\n", encoding="utf-8"
    )
    proc = run_gate(GUARD, code_root)
    assert_rejected(proc, rule_hint="V-06")
    assert "tests/brand_new_suite/test_something.py" in proc.stdout


def test_new_file_inside_existing_batch_is_allowed(code_root: Path) -> None:
    """**反向对照**：在**已被批次覆盖**的目录里新增测试文件 → 必须放行。"""
    (code_root / "tests" / "unit" / "test_brand_new_but_covered.py").write_text(
        "def test_ok() -> None:\n    assert True\n", encoding="utf-8"
    )
    proc = run_gate(GUARD, code_root)
    assert proc.returncode == 0, f"已被批次覆盖的新测试被误报\n{proc.stdout}\n{proc.stderr}"


# ═══════════════ J · V-02 批次表 ↔ 真源 `verify.py::BATCHES`（卡 #102） ═══════════════
#
# **为什么需要这条**：`CONVENTIONS.md::V-02` 那张表是"超时与批次的人的索引"，
# 而它的数字与 `verify.py::BATCHES` 是**同一事实的两个存放处**。实测已漂移过**两次**：
#   ① `#91`（2026-09-16）：表里写「6 片」而真源是 **7**、逐片例数四格全错、**`injection-g` 整行缺失**；
#      更糟的是**「超时」列 6 行过期**（`unit`/`guards` 写 60s 实为 300s、`compute` 60→180、
#      `validators` 30→90、`claim`/`decision` 30→120）。
#   ② 而 `V-02` 正是主理人裁 `unit`/`guards` 超时值时引的依据 ⇒ 规范文档里的数字**错了会直接误导裁定**。
# ⇒ 盯住三件"机器可判"的事：**行集**、**超时列**、**injection 行数**。
#
# ★ **明确不做**（防 `G-27` 关键词式门禁）：不检查「内容」列的措辞、不检查「实测」列
#   （那是读数，本来就会随时间变）。
# ★ 允许 markdown 重排导致判红，但**必须**指到"哪一行/哪个字段"+ 给一行修复提示（不宽松跳过）。
# ★ 本用例由 `verify.py --batch guards` 在**集成时**跑；**不**加进 `pre-commit`（`口径 16`：
#   把 pytest 塞进每次提交会把提交变慢 ⇒ 卡死的门禁就是被关掉的门禁）。

CONVENTIONS_REL = "CONVENTIONS.md"
_V02_HEADER_PREFIX = "| 批次 | 内容 | 超时 |"
_V02_NAME_RE = re.compile(r"`([A-Za-z][A-Za-z0-9._-]*)`")
_V02_TIMEOUT_RE = re.compile(r"(\d+)s")


def _v02_cells(line: str) -> list[str] | None:
    """把一行 markdown 表行切成单元格（`| a | b |` → `["a", "b"]`）。"""
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    if set(stripped) <= set("|-: "):
        return None  # 分隔行 |---|---|
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _v02_rows(root: Path) -> tuple[dict[str, tuple[int, int]], list[str]]:
    """解析 `CONVENTIONS.md` 的 V-02 批次表 → `({批次名: (超时秒, 行号)}, [问题])`。

    ★ 按**单元格位置**取数（第 1 格 = 批次名、第 3 格 = 超时），**不**正则整行 ——
      「实测」格是自由文本（如 `8.80s（**该批 exit=1**…）`），整行正则会误判。
    ★ 问题串里**必须带行号与原文**（授权边界要求"指到哪一行/哪个字段"）。
    """
    path = root / CONVENTIONS_REL
    if not path.exists():
        return {}, [f"缺少规范文件：{CONVENTIONS_REL}"]
    lines = path.read_text(encoding="utf-8").splitlines()

    start = next(
        (i for i, line in enumerate(lines) if line.strip().startswith(_V02_HEADER_PREFIX)),
        None,
    )
    if start is None:
        return {}, [
            f"在 {CONVENTIONS_REL} 里找不到 V-02 批次表：表头须以 {_V02_HEADER_PREFIX!r} 开头。"
            "（修复：恢复该表头；若表格被重排成别的写法，本绑定无法解析 ⇒ 请改回逐行 markdown 表）"
        ]

    rows: dict[str, tuple[int, int]] = {}
    problems: list[str] = []
    for i in range(start + 1, len(lines)):
        cells = _v02_cells(lines[i])
        if cells is None:
            if not lines[i].strip().startswith("|"):
                break  # 表格结束
            continue  # 分隔行
        lineno = i + 1
        if len(cells) < 4:
            problems.append(
                f"V-02 表第 {lineno} 行只有 {len(cells)} 个单元格（表头是 4 列：批次/内容/超时/实测）"
                f"：{lines[i]!r} ⇒ 修复：补齐为 4 列"
            )
            continue
        name_match = _V02_NAME_RE.fullmatch(cells[0])
        if name_match is None:
            problems.append(
                f"V-02 表第 {lineno} 行第 1 格不是 `批次名`（应为反引号包住的批次名）："
                f"{cells[0]!r} ⇒ 修复：写成 `\\`批次名\\``"
            )
            continue
        name = name_match.group(1)
        timeout_match = _V02_TIMEOUT_RE.fullmatch(cells[2])
        if timeout_match is None:
            problems.append(
                f"V-02 表第 {lineno} 行批次 `{name}` 的第 3 格超时不是「整数 + s」："
                f"{cells[2]!r} ⇒ 修复：写成如 `300s`"
            )
            continue
        if name in rows:
            problems.append(f"V-02 表第 {lineno} 行批次 `{name}` 重复（首见第 {rows[name][1]} 行）")
            continue
        rows[name] = (int(timeout_match.group(1)), lineno)
    if not rows:
        problems.append("V-02 批次表解析出 0 行 ⇒ 表格内容为空或格式不符合表头")
    return rows, problems


def _v02_binding_problems(root: Path) -> list[str]:
    """V-02 表 vs `verify.py::BATCHES` 的**三条**断言，返回问题清单（空 = 一致）。"""
    rows, problems = _v02_rows(root)
    with _verify_module(root, name="_verify_v02_table_binding") as module:
        batches = dict(module.BATCHES)
        shard_count = len(module.INJECTION_SHARDS)

    # ① 行集恰好等于真源全集（缺行/多行都红）
    for name in sorted(set(batches) - set(rows)):
        problems.append(
            f"V-02 表缺批次 `{name}`（真源有、表里没有；`#91` 漏的正是 `injection-g` 整行）"
            f" ⇒ 修复：在表中补一行，超时写 {batches[name].timeout:g}s"
        )
    for name in sorted(set(rows) - set(batches)):
        problems.append(
            f"V-02 表第 {rows[name][1]} 行的批次 `{name}` 不在 `verify.py::BATCHES` 里"
            "（表里多出来了）⇒ 修复：删掉该行，或把批次登记进 `BATCHES`"
        )

    # ② 每行超时 == 真源（`#91` 错的 6 行就是这个）
    for name in sorted(set(rows) & set(batches)):
        shown, lineno = rows[name]
        want = int(batches[name].timeout)
        if shown != want:
            problems.append(
                f"V-02 表第 {lineno} 行 `{name}` 的超时是 {shown}s，"
                f"真源 `BATCHES['{name}'].timeout` 是 {want}s ⇒ 修复：把该行超时改成 {want}s"
            )

    # ③ injection 行数 == 分片真源片数
    table_shards = sorted(n for n in rows if n.startswith("injection-"))
    if len(table_shards) != shard_count:
        problems.append(
            f"V-02 表里 `injection-*` 有 {len(table_shards)} 行（{table_shards}），"
            f"而 `verify.py::INJECTION_SHARDS` 是 {shard_count} 片 ⇒ 修复：让两者相等"
        )

    return [f"{CONVENTIONS_REL}: {p}" for p in problems]


def test_v02_table_matches_batch_truth_source(code_root: Path) -> None:
    """★ `CONVENTIONS.md::V-02` 批次表必须与真源 `verify.py::BATCHES` **逐行一致**。

    三条断言见 `_v02_binding_problems`；判红时逐条给出**行号 + 字段 + 一行修复提示**。
    """
    problems = _v02_binding_problems(code_root)
    assert not problems, (
        "V-02 批次表与真源 `verify.py::BATCHES` 不一致（同一事实的两个存放处漂移了）：\n"
        + "\n".join(f"  - {p}" for p in problems)
        + "\n★ 处置：改表、不要改真源 —— 真源是 `verify.py::BATCHES`；"
        "并检查是不是新增/改名批次时漏了同步本表。"
    )


def test_v02_table_missing_row_is_detected(code_root: Path) -> None:
    """★ **反例**（`G-05`：声称能守必须配反例）：删掉表里 `injection-g` **整行** ⇒ 必须判红。

    `injection-g` 正是 `#91` 实测里真实缺失的那一行 —— 用真实发生过的形态做反例。
    """
    _patch(
        code_root,
        CONVENTIONS_REL,
        "| `injection-g` | 分片 G（反编造 + 分片绑定） | 300s | 5.67s |\n",
        "",
    )
    problems = _v02_binding_problems(code_root)
    assert problems, "删掉 `injection-g` 整行后仍判通过 —— 这条绑定没有在守"
    assert any("injection-g" in p and "缺批次" in p for p in problems), problems


def test_v02_table_stale_timeout_is_detected(code_root: Path) -> None:
    """★ **反例**（`G-05`）：把 `unit` 的超时写回过期值 `60s` ⇒ 必须判红，且**指到那一行**。

    `unit` 的 300s 是主理人裁定的现行值；表里曾写 60s（`#91` 实测的 6 行之一）。
    """
    _patch(code_root, CONVENTIONS_REL, "| 300s | 3.40s |", "| 60s | 3.40s |")
    problems = _v02_binding_problems(code_root)
    assert problems, "把 `unit` 超时改回 60s 后仍判通过 —— 超时列没在守"
    assert any("`unit`" in p and "60s" in p and "300s" in p for p in problems), problems


def test_v02_table_reformat_is_reported_not_skipped(code_root: Path) -> None:
    """**重排/破坏表头 → 响亮判红并给出修复提示**（授权边界：不宽松跳过）。"""
    _patch(
        code_root,
        CONVENTIONS_REL,
        "| 批次 | 内容 | 超时 |",
        "| batch | content | timeout |",
    )
    problems = _v02_binding_problems(code_root)
    assert problems, "表头被改坏却判通过 —— 解析失败必须响亮"
    assert any("找不到 V-02 批次表" in p for p in problems), problems
    assert any("表头" in p for p in problems), problems
