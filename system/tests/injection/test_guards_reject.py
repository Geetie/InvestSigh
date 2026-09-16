"""注入测试 —— **守卫真拦得住吗**（`00_开发Agent开工提示词 §5.1 AC-04` / `§十三 第 3 问`）。

> AC-04 守卫真拦得住：注入一个违例 → 检查器 **exit 1**（**不是 warn**）

每个用例的构造方式一致：在 `code_root` 副本里**注入一处真实违例**，
跑**真实检查器脚本**（子进程），断言 `exit == 1`。
另配**反向对照**（同型输入但应放行）——只有"该拦的拦、该放的放"才叫守卫真的在工作，
单纯"全都 exit 1"说明不了任何事。
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from conftest import assert_rejected, run_gate

CONFLICT = "scripts/checks/conflict_scan.py"
FREEZE = "scripts/checks/freeze_guard.py"
LAUNCH = "scripts/checks/launch_guard.py"
RETURN = "scripts/benchmark/return_guard.py"
ANTI_PADDING = "scripts/scope/anti_padding.py"
MODULE_DENY = "scripts/checks/module_denylist.py"
NEUTRALITY = "scripts/views/neutrality_check.py"
PLACEHOLDER = "scripts/checks/no_placeholder_guard.py"


# ─────────────────────────── 工具 ───────────────────────────

def _schema(code_root: Path) -> dict:
    path = code_root / "schema" / "jsonschema" / "facts.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write_schema(code_root: Path, doc: dict) -> None:
    path = code_root / "schema" / "jsonschema" / "facts.schema.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_yaml(code_root: Path, rel: str) -> dict:
    return yaml.safe_load((code_root / rel).read_text(encoding="utf-8"))


def _write_yaml(code_root: Path, rel: str, doc: dict) -> None:
    (code_root / rel).write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _inject_py(code_root: Path, rel: str, source: str) -> None:
    path = code_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


# ═══════════════════════ L1：schema 字段存在性断言 ═══════════════════════

def test_L1_inject_stop_loss_field_is_rejected(code_root: Path) -> None:
    """P-03（禁止损）：`Recommendation` 上出现 `stop_loss` → 必须 exit 1。"""
    doc = _schema(code_root)
    doc["defs"]["Recommendation"]["properties"]["stop_loss"] = {"type": "number"}
    _write_schema(code_root, doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-03")


def test_L1_inject_position_field_is_rejected(code_root: Path) -> None:
    """P-04（建议对象不得有仓位字段）：`position` → 必须 exit 1。"""
    doc = _schema(code_root)
    doc["defs"]["Recommendation"]["properties"]["position"] = {"type": "number"}
    _write_schema(code_root, doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-04")


def test_L1_inject_short_action_enum_is_rejected(code_root: Path) -> None:
    """P-05（禁止做空）：`action` 枚举混入 `short` → 必须 exit 1。"""
    doc = _schema(code_root)
    enum = doc["defs"]["RecommendationAction"]["enum"]
    doc["defs"]["RecommendationAction"]["enum"] = sorted(set(enum) | {"short"})
    _write_schema(code_root, doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-05")


def test_L1_inject_consensus_field_is_rejected(code_root: Path) -> None:
    """P-07（无 source_id 的聚合预测）：`consensus` → 必须 exit 1。"""
    doc = _schema(code_root)
    doc["defs"]["Recommendation"]["properties"]["consensus"] = {"type": "number"}
    _write_schema(code_root, doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-07")


def test_L1_removed_business_positions_is_rejected(code_root: Path) -> None:
    """回归断言：删掉 `business_positions` 对象 → 合法同义词豁免失去落点，必须 exit 1。"""
    doc = _schema(code_root)
    doc["objects"].pop("business_positions", None)
    doc["defs"].pop("BusinessPosition", None)
    _write_schema(code_root, doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="回归断言失败")


# ═══════════════════════ L2：决策作用域禁词 ═══════════════════════

def test_L2_inject_weight_inside_decision_scope_is_rejected(code_root: Path) -> None:
    """P-09：决策作用域内出现 `weight` → 必须 exit 1。"""
    _inject_py(
        code_root,
        "scripts/decision/rank_candidates.py",
        "def rank_candidates(rows):\n    weight = 1.0\n    return sorted(rows, key=lambda r: r) + [weight]\n",
    )
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-09")


def test_L2_same_weight_outside_decision_scope_passes(code_root: Path) -> None:
    """**反向对照**：同样的 `weight` 放在 `scripts/compute/`（非决策域）→ 必须放行。

    证明 P-09 的 `decision_scope_only` 作用域**真的在生效**，不是"见词就杀"。
    """
    _inject_py(
        code_root,
        "scripts/compute/aggregate.py",
        "def aggregate(rows):\n    weight = 1.0\n    return sum(rows) * weight\n",
    )
    proc = run_gate(CONFLICT, code_root, "--timing", "ci")
    assert proc.returncode == 0, (
        "非决策域的 weight 被误报 —— P-09 作用域失效（会逼人关掉门禁）\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_L2_freeze_param_reader_in_decision_module_passes(code_root: Path) -> None:
    """**反向对照**：决策目录下的**纯参数读口**函数不属决策作用域（`Ch11 §E.1` 排除项）。

    参数只做基准/范围/口径/披露，不进决策函数；但"读参数"这件事本身在决策目录里
    也必须被允许，否则 `get_param` 无处安放。
    """
    _inject_py(
        code_root,
        "scripts/decision/caliber.py",
        "from config.freeze import get_param\n\n\n"
        "def scope_value():\n    return get_param('p03').effective_value\n",
    )
    proc = run_gate(CONFLICT, code_root, "--timing", "ci")
    assert proc.returncode == 0, (
        "决策目录下的 freeze_param 纯读口被误报 —— 与 Ch11 §E.1 排除项冲突\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


# ═══════════════════════ L3：配置扫描 ═══════════════════════

def test_L3_inject_banned_config_key_is_rejected(code_root: Path) -> None:
    """P-01/P-02：配置里出现禁词**键名** → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/scope.yaml")
    doc["min_excess_return"] = 0.05
    _write_yaml(code_root, "rules/scope.yaml", doc)
    assert_rejected(run_gate(CONFLICT, code_root, "--timing", "ci"), rule_hint="P-01")


def test_L3_banned_token_in_prose_passes(code_root: Path) -> None:
    """**反向对照**：散文中提到禁词（解释"为什么禁止它"）→ 必须放行。

    否则无法在配置里写明"不得设置 min_excess_return 这类门槛"。
    """
    doc = _read_yaml(code_root, "rules/scope.yaml")
    doc["ban_note"] = "不得设置最低超额收益门槛（如 min_excess_return 之类），理由见 Ch11 §E.1"
    _write_yaml(code_root, "rules/scope.yaml", doc)
    proc = run_gate(CONFLICT, code_root, "--timing", "ci")
    assert proc.returncode == 0, f"散文说明被误报为禁词键\n{proc.stdout}\n{proc.stderr}"


# ═══════════════════════ G11：参数与红线一 ═══════════════════════

def test_G11_param_becomes_new_gate_is_rejected(code_root: Path) -> None:
    """红线一：把参数改名成 `min_excess_return`（借参数补门槛）→ 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/freeze.yaml")
    doc["freeze_params"][0]["param"] = "min_excess_return"
    _write_yaml(code_root, "rules/freeze.yaml", doc)
    assert_rejected(run_gate(FREEZE, code_root), rule_hint="G11-02")


def test_G11_absolute_line_number_in_blocking_targets_is_rejected(code_root: Path) -> None:
    """纪律 6：`blocking_targets` 写绝对行号 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/freeze.yaml")
    doc["freeze_params"][0]["blocking_targets"] = ["第 570 行"]
    _write_yaml(code_root, "rules/freeze.yaml", doc)
    assert_rejected(run_gate(FREEZE, code_root), rule_hint="G11-05")


def test_G11_frozen_without_trio_is_rejected(code_root: Path) -> None:
    """G11-01：`frozen` 但缺 `confirmed_by/confirmed_at/version` → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/freeze.yaml")
    doc["freeze_params"][0]["freeze_status"] = "frozen"
    doc["freeze_params"][0]["value"] = "AGIX"
    _write_yaml(code_root, "rules/freeze.yaml", doc)
    assert_rejected(run_gate(FREEZE, code_root), rule_hint="G11-01")


def test_G11_decision_scope_reads_freeze_param_is_rejected(code_root: Path) -> None:
    """G11-02 ②：决策函数读入 `freeze_param` → 必须 exit 1（参数不进决策函数）。"""
    _inject_py(
        code_root,
        "scripts/decision/gate.py",
        "from config.freeze import get_param\n\n\n"
        "def decide(company):\n    return get_param('p03').effective_value\n",
    )
    assert_rejected(run_gate(FREEZE, code_root), rule_hint="G11-02")


# ═══════════════════════ 红线二 / 基准口径 / 反凑数 ═══════════════════════

def test_launch_paid_required_source_is_rejected(code_root: Path) -> None:
    """红线二：`required` 里出现付费订阅 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "registry/launch_criteria.yaml")
    doc["required"][0]["requires_paid_subscription"] = True
    _write_yaml(code_root, "registry/launch_criteria.yaml", doc)
    assert_rejected(run_gate(LAUNCH, code_root), rule_hint="required")


def test_benchmark_proxy_index_is_rejected(code_root: Path) -> None:
    """N3.4-05：基准收益来源被换成公开指数 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/benchmark.yaml")
    doc["benchmark_objects"][0]["return_source"] = "public_index_proxy"
    _write_yaml(code_root, "rules/benchmark.yaml", doc)
    assert_rejected(run_gate(RETURN, code_root), rule_hint="N3.4-05")


def test_benchmark_double_fee_is_rejected(code_root: Path) -> None:
    """N3.4-07：二次扣费 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/benchmark.yaml")
    doc["benchmark_objects"][0]["return_basis"]["fee_deducted_again"] = True
    _write_yaml(code_root, "rules/benchmark.yaml", doc)
    assert_rejected(run_gate(RETURN, code_root), rule_hint="N3.4-05/07")


def test_anti_padding_target_company_count_is_rejected(code_root: Path) -> None:
    """反凑数：出现目标名单规模配置 → 必须 exit 1。"""
    doc = _read_yaml(code_root, "rules/scope.yaml")
    doc["target_company_count"] = 25
    _write_yaml(code_root, "rules/scope.yaml", doc)
    assert_rejected(run_gate(ANTI_PADDING, code_root), rule_hint="N3.1")


def test_module_denylist_portfolio_optimizer_is_rejected(code_root: Path) -> None:
    """交付止于研究+建议：出现组合权重优化模块 → 必须 exit 1。"""
    _inject_py(code_root, "scripts/portfolio_weight_optimizer.py", "X = 1\n")
    assert_rejected(run_gate(MODULE_DENY, code_root), rule_hint="N3.3")


def test_neutrality_urgency_color_is_rejected(code_root: Path) -> None:
    """P-10：展示层用紧迫色隐性引导 → 必须 exit 1。"""
    (code_root / "views").mkdir(parents=True, exist_ok=True)
    (code_root / "views" / "daily.yaml").write_text(
        yaml.safe_dump(
            {"default_sort": [], "urgency_color": True, "evidence_panel": {"collapsed_default": False}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    assert_rejected(run_gate(NEUTRALITY, code_root), rule_hint="P-10")


def test_neutrality_unresearched_rendered_neutral_is_rejected(code_root: Path) -> None:
    """N3.2-05：未完成研究被渲染成"中性" → 必须 exit 1（待判断 ≠ 未完成研究）。"""
    (code_root / "views").mkdir(parents=True, exist_ok=True)
    (code_root / "views" / "daily.yaml").write_text(
        yaml.safe_dump(
            {
                "render_mappings": [
                    {"from": "unresearched", "to": "中性"},
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    assert_rejected(run_gate(NEUTRALITY, code_root), rule_hint="N3.2-05")


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
# （证明 fail-closed 没退化成"见 append_records 就杀"）；③ 2 条**已知静态局限必须放行**
# —— 它们**记录事实**而非把缺口说成不存在：将来若有人把静态判据做全了，这两条会红，
# 逼其**显式**更新预期。
#
# ★ 断言一律取**退出码**，不取守卫输出里的说明文字（措辞可改，行为不可改）——
#   故**不传 `rule_hint`**：`injection_guard` 的说明文字可能被并发地做"仅措辞"改动。
# ★ 探针写在 `scripts/guard/` 下（守卫的扫描面），用完即删。

INJECTION_GUARD = "scripts/checks/injection_guard.py"


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
    """★ **已知静态局限**：常量拼接落在**接收者**位置 → 当前 exit 0（放行）。

    `(root / 'facts' / ('recommend' + 'ations.jsonl')).write_text('x')`：
    目标名由**运行期** `str.__add__` 计算得到，静态上不可判定 —— 属**原理上**的局限，
    不是缺陷。

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
        "接收者位置的常量拼接**已**被静态判据覆盖 —— 请显式更新本『已知静态局限』用例"
        "（并同步 injection_guard.py 的 KNOWN_STATIC_LIMIT note）\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_injection_guard_known_static_limit_fstring_open_target(code_root: Path) -> None:
    """★ **已知静态局限**：写入目标名藏在**变量**里 → 当前 exit 0（放行）。

    `open(f'{root}/facts/{stem}.jsonl', 'a')`：目标名由 f-string + 变量拼出，
    静态不可判定 —— 属**原理上**的局限，不是缺陷。

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
        "变量化的写入目标**已**被静态判据覆盖 —— 请显式更新本『已知静态局限』用例\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
