"""注入测试 —— **守卫真拦得住吗**（`00_开发Agent开工提示词 §5.1 AC-04` / `§十三 第 3 问`）**后半**。

## 本文件是**拆分后的后半**（`B` 半 · 20 例）

原 `test_guards_reject.py` 共 41 例，**单文件就超宿主的单轮删除配额**
（41 × 每例 271 项夹具 ≈ 11,111 > 9,999，见 `CONVENTIONS.md::V-08`），
故按 `# ═══` 分节边界**纯移动**拆成：

- `test_guards_reject_a.py`（`A`）：`L1` `L2` `L3` `G11` `launch` `benchmark`
  `anti_padding` `module_denylist` `neutrality` —— 21 例；
- **本文件**（`B`）：`placeholder`（13 例）+ `injection_guard`（7 例）—— 20 例。

两半**用例数之和仍为 41**，断言语义零改动。两半共用的工具（`_schema` / `_write_schema` /
`_read_yaml` / `_write_yaml` / `_inject_py`）与被测脚本路径常量在
`_guard_common.py`（**唯一真源**，`CONVENTIONS.md::G-06`）。
"""

from __future__ import annotations

from pathlib import Path

from conftest import assert_rejected, run_gate
from _guard_common import (
    INJECTION_GUARD,
    PLACEHOLDER,
    _inject_py,
    _read_yaml,
    _write_yaml,
)

# ═══════════════════════ 反占位符（含跨行规则） ═══════════════════════

def test_placeholder_pass_only_body_is_rejected(code_root: Path) -> None:
    """空函数体（只有 `pass`）→ 必须 exit 1。"""
    _inject_py(code_root, "scripts/build_report.py", "def build_report():\n    pass\n")
    assert_rejected(run_gate(PLACEHOLDER, code_root, "--fail-on", "warn"), rule_hint="EMPTY_BODY")


def test_placeholder_docstring_only_body_is_rejected(code_root: Path) -> None:
    """有 docstring 但无实现 → 必须 exit 1（docstring 不算实现）。"""
    _inject_py(
        code_root,
        "scripts/build_report.py",
        'def build_report():\n    """Build the report."""\n',
    )
    assert_rejected(run_gate(PLACEHOLDER, code_root, "--fail-on", "warn"), rule_hint="EMPTY_BODY")


def test_placeholder_exception_class_with_docstring_passes(code_root: Path) -> None:
    """**反向对照**：**异常类**只有 docstring 是常态 → 必须放行。

    这是实测发现的 13 条误报（抹白 docstring 后把异常类判成空体）。
    """
    _inject_py(
        code_root,
        "scripts/errors.py",
        'class MyError(RuntimeError):\n    """合法：异常类只有 docstring 是常态。"""\n',
    )
    proc = run_gate(PLACEHOLDER, code_root, "--fail-on", "warn")
    assert proc.returncode == 0, f"异常类误报为空体\n{proc.stdout}\n{proc.stderr}"


def test_placeholder_swallow_exception_pass_is_rejected(code_root: Path) -> None:
    """★ 跨行规则：`except ...:` 换行后 `pass`（`§八 N-2` 点名的形态）→ 必须 exit 1。"""
    _inject_py(
        code_root,
        "scripts/parse.py",
        "def parse(raw):\n"
        "    try:\n"
        "        return int(raw)\n"
        "    except ValueError:\n"
        "        pass\n",
    )
    assert_rejected(
        run_gate(PLACEHOLDER, code_root, "--fail-on", "warn"), rule_hint="SWALLOW_EXCEPTION_PASS"
    )


def test_placeholder_log_and_reraise_is_rejected(code_root: Path) -> None:
    """★ 跨行规则：log 后原样重抛（只加日志没处理）→ 必须 exit 1。"""
    _inject_py(
        code_root,
        "scripts/fetch.py",
        "import logging\n\n\n"
        "logger = logging.getLogger(__name__)\n\n\n"
        "def fetch(url):\n"
        "    try:\n"
        "        return url\n"
        "    except OSError as exc:\n"
        "        logger.error('failed: %s', exc)\n"
        "        raise\n",
    )
    assert_rejected(run_gate(PLACEHOLDER, code_root, "--fail-on", "warn"), rule_hint="LOG_AND_RERAISE")


def test_placeholder_not_implemented_error_is_rejected(code_root: Path) -> None:
    """`NotImplementedError` → 必须 exit 1（`§一 底线 1`）。"""
    _inject_py(
        code_root,
        "scripts/todo_mod.py",
        "def compute(x):\n    raise NotImplementedError\n",
    )
    assert_rejected(run_gate(PLACEHOLDER, code_root, "--fail-on", "warn"), rule_hint="NOT_IMPLEMENTED")


def test_placeholder_mention_in_docstring_passes(code_root: Path) -> None:
    """**反向对照**：docstring 里**讨论**占位符概念 → 必须放行（文档不是违例）。"""
    _inject_py(
        code_root,
        "scripts/documenting.py",
        'def explain():\n'
        '    """说明：本模块**不得**出现 TODO / 占位 / mock 数据这类东西。"""\n'
        "    return 1\n",
    )
    proc = run_gate(PLACEHOLDER, code_root, "--fail-on", "warn")
    assert proc.returncode == 0, f"docstring 说明被误报\n{proc.stdout}\n{proc.stderr}"


# ═══════════════ 反向对照 · 字符串型占位（独立审计 D-4 抓出的真实回归） ═══════════════
#
# 背景：早先为消除 docstring 误报，把**所有**字符串字面量都抹白了 ——
# 于是三条"检测对象本来就是字符串"的规则**永不命中**（抹白等于把探测器一起抹掉）：
#   HARDCODED_FALLBACK / DEMO_TALK / FAKE_DATA
# 而它们正是 `§一 底线 1`「真实现」要抓的第一类假交付。
# 修法：**只抹白注释与 docstring**，保留普通字符串字面量（`修正 5/6`）。
# 下列用例把这条修复钉死 —— 缺了它们，下一次"降噪"很容易再抹过头。

def test_placeholder_hardcoded_status_ok_is_rejected(code_root: Path) -> None:
    """`return {"status": "ok"}` 式**假成功** → 必须 exit 1（曾因正则写坏而永不命中）。"""
    _inject_py(
        code_root,
        "scripts/fake_ok.py",
        'def publish(row) -> dict:\n    return {"status": "ok"}\n',
    )
    assert_rejected(
        run_gate(PLACEHOLDER, code_root, "--fail-on", "warn"), rule_hint="HARDCODED_FALLBACK"
    )


def test_placeholder_demo_talk_string_is_rejected(code_root: Path) -> None:
    """字符串里的演示话术（`coming soon` / `演示用`）→ 必须 exit 1（曾被抹白而漏报）。"""
    _inject_py(
        code_root,
        "scripts/demo.py",
        'def label() -> str:\n    return "coming soon"\n\n\n'
        'def label_cn() -> str:\n    return "演示用数据"\n',
    )
    assert_rejected(run_gate(PLACEHOLDER, code_root, "--fail-on", "warn"), rule_hint="DEMO_TALK")


def test_placeholder_fake_data_string_is_rejected(code_root: Path) -> None:
    """字符串里的假数据标记（`mock`）→ 必须 exit 1（曾被抹白而漏报）。"""
    _inject_py(
        code_root,
        "scripts/stub.py",
        'def payload() -> str:\n    return "mock"\n',
    )
    assert_rejected(run_gate(PLACEHOLDER, code_root, "--fail-on", "warn"), rule_hint="FAKE_DATA")


def test_placeholder_words_in_ordinary_string_are_still_caught(code_root: Path) -> None:
    """★ 关键区分力：**普通字符串**里的 `TODO` 必须被抓（只有 docstring 才免罪）。"""
    _inject_py(
        code_root,
        "scripts/todo_string.py",
        'def marker() -> str:\n    return "TODO: finish this"\n',
    )
    assert_rejected(
        run_gate(PLACEHOLDER, code_root, "--fail-on", "warn"), rule_hint="PLACEHOLDER-TODO"
    )


def test_placeholder_in_config_value_is_rejected(code_root: Path) -> None:
    """配置里的**数据值**出现占位话术 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/scope.yaml")
    doc["coverage_note"] = "待填写"
    _write_yaml(code_root, "rules/scope.yaml", doc)
    assert_rejected(
        run_gate(PLACEHOLDER, code_root, "--fail-on", "warn"), rule_hint="DATA_PLACEHOLDER"
    )


def test_placeholder_mention_in_shell_comment_passes(code_root: Path) -> None:
    """**反向对照**：`.sh` 注释里**描述**规则（如 `# 反占位符门禁`）→ 必须放行。

    实测触发：`scripts/ops/pre-commit.sh` 的注释被判成"数据里的占位话术"。
    """
    (code_root / "scripts" / "ops").mkdir(parents=True, exist_ok=True)
    (code_root / "scripts" / "ops" / "demo.sh").write_text(
        "#!/bin/sh\n# 本脚本负责反占位符与追加式门禁\n"
        "echo 'placeholder check'\n",
        encoding="utf-8",
    )
    proc = run_gate(PLACEHOLDER, code_root, "--fail-on", "warn")
    assert proc.returncode == 0, f"注释里的规则描述被误报\n{proc.stdout}\n{proc.stderr}"


# ═══════════ 注入守卫 · B/C 静态绊线回归（独立审计 D-3 抓出的绕过面） ═══════════
#
# 背景：独立审计实测 `injection_guard` 的 B/C 静态断言**只匹配字面量直传形态**，
# 变量间接 / getattr / f-string / 路径拼接都能被**一次普通改写**绕过（D-3）。
# 工程师已把 B/C 加固为「结构化 + 对不可判定形式 fail-closed」。
#
# 下面的探针把这一加固钉死：① 4 条**必须被拦**（曾可绕过）；② 1 条**反向对照必须放行**
# （证明 fail-closed 没退化成"见 append_records 就杀"）；③ 2 条**运行期计算的写入目标必须放行**
# —— 能力白名单（`ALLOWED_IMPORTS` / `ALLOWED_DUNDERS`）**不覆盖**运行期计算的写入目标：
# 属 `R-06` 意义上的「**超出静止判据能力、且不以静止判据承担保证**」；完整保证由运行时效果断言承担。
# 它们**记录事实**而非把缺口说成不存在：将来若有人把静态判据做全了，这两条会红，逼其**显式**更新预期。
#
# ★ 断言一律取**退出码**，不取守卫输出里的说明文字（措辞可改，行为不可改）——
#   故**不传 `rule_hint`**：`injection_guard` 的说明文字可能被并发地做"仅措辞"改动。
# ★ 探针写在 `scripts/guard/` 下（守卫的扫描面），用完即删。


def _restore_rule_perms(root: Path) -> None:
    """把夹具副本 `rules/**` 权限改回 0444。

    ★ 只改权限：`injection_guard` 的断言 A 复用 `rules_lock_guard`，后者要求
      `rules/` **恰为 0444**；夹具默认放开为 0644（`_make_writable`，便于注入）。
      hash 校验仍**唯一**经该守卫 —— 本函数不重算、不比对 hash（`R-05` 唯一真源）。
    """
    import os

    for path in sorted((root / "rules").rglob("*")):
        if path.is_file() and path.suffix in (".yaml", ".yml", ".json"):
            os.chmod(path, 0o444)


def _probe_guard(code_root: Path, name: str, source: str):
    """在 `scripts/guard/` 放一个探针模块 → 跑注入守卫（`finally` 删除探针）。"""
    _restore_rule_perms(code_root)
    rel = f"scripts/guard/{name}.py"
    _inject_py(code_root, rel, source)
    try:
        return run_gate(INJECTION_GUARD, code_root)
    finally:
        (code_root / rel).unlink(missing_ok=True)


def test_injection_guard_rejects_subprocess_import_in_data_path(code_root: Path) -> None:
    """① 数据路径 `import subprocess` → 必须 exit 1（工具能力静态绊线）。"""
    proc = _probe_guard(
        code_root,
        "probe_d3_import_subprocess",
        "import subprocess\n\n\nPROBE = subprocess.PIPE\n",
    )
    assert_rejected(proc)


def test_injection_guard_rejects_getattr_os_system(code_root: Path) -> None:
    """② `getattr(os, 'system')(cmd)` → 必须 exit 1（动态调用的字面量落工具原语集合内）。"""
    proc = _probe_guard(
        code_root,
        "probe_d3_getattr_os_system",
        "import os\n\n\n"
        "def run_cmd(cmd):\n"
        "    return getattr(os, 'system')(cmd)\n",
    )
    assert_rejected(proc)


def test_injection_guard_rejects_variable_append_stem(code_root: Path) -> None:
    """③ `append_records(root, stem, rows)`（stem 是**变量**）→ 必须 exit 1（fail-closed）。"""
    proc = _probe_guard(
        code_root,
        "probe_d3_variable_stem",
        "from schema.store import append_records\n\n\n"
        "def persist(root, stem, rows):\n"
        "    return append_records(root, stem, rows)\n",
    )
    assert_rejected(proc)


def test_injection_guard_rejects_fstring_append_stem(code_root: Path) -> None:
    """④ `append_records(root, f'{x}', rows)`（f-string 目标）→ 必须 exit 1（fail-closed）。"""
    proc = _probe_guard(
        code_root,
        "probe_d3_fstring_stem",
        "from schema.store import append_records\n\n\n"
        "def persist(root, x, rows):\n"
        "    return append_records(root, f'{x}', rows)\n",
    )
    assert_rejected(proc)


def test_injection_guard_allows_literal_non_recommendation_stem(code_root: Path) -> None:
    """**反向对照**：`append_records(root, 'claims', rows)`（字面量且非 recommendations）→ 必须放行。

    证明 C 的「无法静态判定即 fail-closed」**没有**退化成"见 `append_records` 就杀"。
    """
    proc = _probe_guard(
        code_root,
        "probe_d3_literal_claims_stem",
        "from schema.store import append_records\n\n\n"
        "def persist(root, rows):\n"
        "    return append_records(root, 'claims', rows)\n",
    )
    assert proc.returncode == 0, (
        "字面量且非 recommendations 的 stem 被误拦 —— fail-closed 退化成见词就杀\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_injection_guard_known_static_limit_constant_in_receiver(code_root: Path) -> None:
    """★ **运行期计算的写入目标**：常量拼接落在**接收者**位置 → 当前 exit 0（放行）。

    `(root / 'facts' / ('recommend' + 'ations.jsonl')).write_text('x')`：
    目标名由**运行期** `str.__add__` 计算得到，静态上不可判定。

    **准确表述**：能力白名单（`ALLOWED_IMPORTS` / `ALLOWED_DUNDERS`）**不覆盖**运行期计算的
    写入目标 —— 属 `R-06` 意义上的「**超出静止判据能力、且不以静止判据承担保证**」。
    **完整保证由运行时效果断言承担**：处理外部文本前后 `facts/recommendations.jsonl`
    的**行数不变**（见 `tests/injection/test_prompt_injection.py` 的效果三元组 (b)）。

    本用例**记录事实**，而不是把缺口说成不存在：将来若有人把静态判据做全了，
    这条会红，逼其**显式**更新这里的预期。
    """
    proc = _probe_guard(
        code_root,
        "probe_d3_receiver_constant_concat",
        "from pathlib import Path\n\n\n"
        "def overwrite(root: Path) -> None:\n"
        "    (root / 'facts' / ('recommend' + 'ations.jsonl')).write_text('x')\n",
    )
    assert proc.returncode == 0, (
        "接收者位置的常量拼接**已**被静态判据覆盖 —— 请显式更新本用例的预期"
        "（此形态属运行期计算的写入目标，能力白名单不覆盖它）\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_injection_guard_known_static_limit_fstring_open_target(code_root: Path) -> None:
    """★ **运行期计算的写入目标**：写入目标名藏在**变量**里 → 当前 exit 0（放行）。

    `open(f'{root}/facts/{stem}.jsonl', 'a')`：目标名由 f-string + 变量拼出，
    静态不可判定。

    **准确表述**：能力白名单（`ALLOWED_IMPORTS` / `ALLOWED_DUNDERS`）**不覆盖**运行期计算的
    写入目标 —— 属 `R-06` 意义上的「**超出静止判据能力、且不以静止判据承担保证**」。
    **完整保证由运行时效果断言承担**（同上，效果三元组 (b) 的 `recommendations.jsonl`
    行数不变）。将来静态判据做全了，这条会红，逼其**显式**更新预期。
    """
    proc = _probe_guard(
        code_root,
        "probe_d3_fstring_open_target",
        "def append_line(root, stem):\n"
        "    with open(f'{root}/facts/{stem}.jsonl', 'a', encoding='utf-8') as fh:\n"
        "        fh.write('x')\n",
    )
    assert proc.returncode == 0, (
        "变量化的写入目标**已**被静态判据覆盖 —— 请显式更新本用例的预期"
        "（此形态属运行期计算的写入目标，能力白名单不覆盖它）\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
