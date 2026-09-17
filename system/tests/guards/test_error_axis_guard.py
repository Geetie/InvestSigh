"""`error_axis_guard`（`S-07`）的**可执行反例 + 反向对照 + 双注册绑定**（`G-05` / `G-07`）。

被检对象：`scripts/checks/error_axis_guard.py`

缺陷（`10_验收与持续复盘/02_实现方案.md §G.1` / `Ch10 §C.1`）：`eval_result` 的三个**标记字段**
（`eval_layer` / `error_axis` / `error_axis_note`）是**复盘/定位**用的标记枚举，**不进决策函数** ——
但这条若只写在文档里，把它们接进 `scripts/decision/**`（例如"按错误方向加权"）**没有任何门禁会响**。
本守卫把 `Ch2 §B.3` Checker-1 的 `is_decision_scope` **排除项**变成可执行断言。

## 为什么这些用例必须存在（不是"顺手补测"）

本守卫的形态是「**没读却毫无症状**」：一个只会打印"扫了 N 个函数"、从不真去比对的守卫，
也能产出**完全相同**的 stdout。⇒ 判据必须**可证伪**，故用**两个方向**的真注入证明它会红：

| 方向 | 注入点 | 意图 |
|---|---|---|
| A（路径作用域） | 把一个读标记字段的函数放进 `scripts/decision/**` | `include_paths` 纳入的模块必须红 |
| B（调用链作用域） | 在**非**路径作用域文件里加一个 `classify_*` 读标记字段 | `include_call_chain` 纳入的函数必须红 |
| C（结构断言②） | 给 `RecommendationInput` 加一个标记字段 | 决策输入结构不得含标记字段 |

★ **只测一个方向不够**：守卫完全可能只实现路径作用域（那样 B 不红）、或只做结构与运行期断言（那样 A 不红）。
★ 反向对照（不改 ⇒ `exit 0`）与注入放在**同一份副本**上，两次运行之间唯一的差别就是那次注入。
"""

from __future__ import annotations

from pathlib import Path

from conftest import SYSTEM_ROOT, run_gate_inproc

GUARD = "scripts/checks/error_axis_guard.py"

#: 路径作用域文件（`decision_scope.include_paths` = `scripts/decision/**`）。
PATH_SCOPE_FILE = Path("scripts") / "decision" / "gate.py"
#: **非**路径作用域文件（只能靠 `include_call_chain` 的 `classify_*` / `assert_*` 纳入）。
OUT_OF_SCOPE_FILE = Path("scripts") / "valuelayer" / "completeness.py"
#: 标记字段的**唯一真源**（`decision_scope.exclude_fields`）。
BANNED_TOKENS = Path("rules") / "banned_tokens.yaml"

#: 三份稳定锚点（均实测**全文件唯一**）。
_FUTURE_ANCHOR = "from __future__ import annotations\n"
_OWN_EVIDENCE_ANCHOR = (
    "    own_evidence: tuple[str, ...] = field(default_factory=tuple)  # 该标的**自身** claim_id[]\n"
)
_EXCLUDE_FIELDS_ANCHOR = (
    "  exclude_fields:\n"
    "    - eval_layer\n"
    "    - error_axis\n"
    "    - error_axis_note\n"
)


def _inject(path: Path, *, old: str, new: str) -> None:
    """在 `path` 里把 `old` 换成 `new`，并★**自证注入已生效**。

    ★ 注入型测试必须**先证明注入真的改动了输入**（锚点写错 ⇒ `write_text` 写回原文 ⇒
      注入是 no-op、守卫照样绿，而用例以一句含糊的失败收场、**归因指向守卫** = 假缺陷）。
    """
    text = path.read_text(encoding="utf-8")
    assert old in text, f"注入点未找到（上游文本已变？）：{old!r}"
    mutated = text.replace(old, new)
    assert mutated != text, "注入是 no-op —— 替换前后文本相同，本用例将毫无判别力"
    path.write_text(mutated, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == mutated, "注入未落盘"


# ─────────────────────── ① 反向对照 + 被检域可见（`G-03` / `G-05`） ───────────────────────


def test_clean_copy_passes_and_reports_scanned_domain(code_root: Path) -> None:
    """干净副本必须 `exit 0` 且**报出被检域**（否则"没扫"与"扫了没问题"不可区分）。

    ★ 断言的是**结构性**事实（标记数 = 3、有作用域计数、有 allowlist note），
      **不写死**"作用域模块 == 18"这类写死计数（它随 `scripts/**` 的正常改动而变）。
    """
    code, out = run_gate_inproc(GUARD, code_root)

    assert code == 0, f"干净副本上应 exit 0，实得 {code}\n{out}"
    assert "RESULT: PASS" in out, f"未见 PASS 结论\n{out}"
    # 被检域必须可见：标记集合来自配置（唯一真源），且作用域计数逐项打出。
    assert "scanned markers: 3" in out, f"标记集合应来自 decision_scope.exclude_fields（3 条）\n{out}"
    assert "scanned decision_scope_modules:" in out, f"未报作用域模块数（跳过不是通过）\n{out}"
    assert "scanned scanned_functions:" in out, f"未报被检函数数\n{out}"
    assert "scanned call_chain_functions:" in out, f"未报调用链纳入数\n{out}"
    assert "include_call_chain" in out, f"应说明被检域口径（allowlist，R-06）\n{out}"


# ─────────────────────── ② 路径作用域注入（`include_paths`） ───────────────────────


def test_marker_use_in_path_scope_is_blocked(code_root: Path) -> None:
    """★ 方向 A：在 `scripts/decision/**` 里读标记字段 ⇒ `exit 1`。"""
    path = code_root / PATH_SCOPE_FILE

    code, out = run_gate_inproc(GUARD, code_root)          # 反向对照（同副本、注入前）
    assert code == 0, f"未注入时应 exit 0，实得 {code}\n{out}"

    _inject(
        path,
        old=_FUTURE_ANCHOR,
        new=_FUTURE_ANCHOR + '\n\ndef _wsg_probe(row):\n    return row.get("eval_layer")\n',
    )
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"决策作用域里读标记字段时应 exit 1，实得 {code}\n{out}"
    assert "eval_layer" in out, f"应点名被读的标记字段\n{out}"
    assert "S-07" in out, f"应给出规则号 S-07\n{out}"
    assert "决策函数 _wsg_probe()" in out, f"应点出**哪个函数**越界（G-02 函数级归因）\n{out}"


# ─────────────────────── ③ 调用链作用域注入（`include_call_chain`） ───────────────────────


def test_marker_use_in_call_chain_scope_is_blocked(code_root: Path) -> None:
    """★ 方向 B：在**非**路径作用域文件里加一个 `classify_*` 读标记字段 ⇒ `exit 1`。

    ★ 这条同时证伪"守卫只实现了路径作用域"：`scripts/valuelayer/**` **不在** `include_paths` 内，
      只有 `include_call_chain`（`classify_*` / `assert_*`）能把它纳入 ⇒ B 红 = 调用链作用域真的生效。
    """
    path = code_root / OUT_OF_SCOPE_FILE

    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 0, f"未注入时应 exit 0，实得 {code}\n{out}"

    _inject(
        path,
        old=_FUTURE_ANCHOR,
        new=_FUTURE_ANCHOR + '\n\ndef classify_wsg_probe(row):\n    return row.get("error_axis")\n',
    )
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"classify_* 读标记字段时应 exit 1，实得 {code}\n{out}"
    assert "error_axis" in out, f"应点名被读的标记字段\n{out}"
    assert "classify_wsg_probe" in out, f"应点出越界的 classify_* 函数\n{out}"


# ─────────────────────── ④ 结构断言②（决策输入结构不得含标记字段） ───────────────────────


def test_decision_input_structure_rejects_marker_field(code_root: Path) -> None:
    """★ 方向 C：给 `RecommendationInput`（`Ch7 §D.5`）加一个标记字段 ⇒ `exit 1`。

    ★ 结构断言独立于函数体断言：`from_mapping` 是 **allowlist**，标记字段一旦成为**结构字段**，
      就会被顺理成章地接进决策 —— 故必须单独钉住"字段集不含标记字段"（`Ch10 §G.1` ②）。
    """
    path = code_root / PATH_SCOPE_FILE

    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 0, f"未注入时应 exit 0，实得 {code}\n{out}"

    _inject(path, old=_OWN_EVIDENCE_ANCHOR, new=_OWN_EVIDENCE_ANCHOR + '\n    eval_layer: str = ""\n')
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"决策输入结构含标记字段时应 exit 1，实得 {code}\n{out}"
    assert "决策输入结构" in out, f"应命中**结构断言②**（而非仅函数体断言）\n{out}"
    assert "RecommendationInput" in out, f"应点名决策输入结构\n{out}"


# ─────────────────────── ⑤ 输入异常 ⇒ exit 2（`Ch2 §B.3` 的 0/1/2 三分） ───────────────────────


def test_input_errors_are_exit_2_and_never_a_pass(code_root: Path) -> None:
    """★ 两种**输入异常**都必须 `exit 2`（"我没法判"），**不得**报成"通过"（`G-03`）。

    | 臂 | 输入 | 为什么不能算通过 |
    |---|---|---|
    | A | `decision_scope.exclude_fields` 被清空 | 标记集合**无来源** ⇒ 守卫**没有可检对象**；报 PASS 等于把"没检查"说成"检查过" |
    | B | `scripts/**` 里有**无法解析的 `.py`** | 该文件**根本没被扫**，而输出里一切看起来正常 |
    """
    # ── 臂 A：标记集合无来源 ⇒ exit 2 ──
    _inject(
        code_root / BANNED_TOKENS,
        old=_EXCLUDE_FIELDS_ANCHOR,
        new="  exclude_fields: []\n",
    )
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 2, f"标记集合为空时应 exit 2（输入异常），实得 {code}\n{out}"
    assert "exclude_fields" in out, f"应点名缺的是哪个配置键\n{out}"

    # ── 臂 B：扫到无法解析的源码 ⇒ exit 2（★ 与臂 A 同一个 `code_root`，省一份夹具）──
    #    先在**未注入**的另一份副本上做，避免与臂 A 的 no-op 语义混淆 —— 直接改回配置再注入语法错误。
    _inject(code_root / BANNED_TOKENS, old="  exclude_fields: []\n", new=_EXCLUDE_FIELDS_ANCHOR)
    _inject(
        code_root / OUT_OF_SCOPE_FILE,
        old=_FUTURE_ANCHOR,
        new=_FUTURE_ANCHOR + "\ndef broken(:\n",
    )
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 2, f"源码无法解析时应 exit 2（输入异常），实得 {code}\n{out}"
    assert "语法错误" in out, f"应说清原因不是「违例」而是「我没法判」\n{out}"


# ─────────────────────── ⑥ `G-07` 双注册（防孤儿守卫） ───────────────────────


def test_gate_is_registered_in_both_places() -> None:
    """★ `G-07`：本守卫必须**同时**进 `run_all_gates.py::GATES` 与 `scripts/ops/pre-commit.sh`。

    ★ 为什么需要这条断言：只进一处 = "提交时放行、CI 时拦"（或反之），
      两处口径不一致本身就是同一族的缺陷。本断言把**本守卫**的这条义务变成可执行的。
    """
    gates_src = (SYSTEM_ROOT / "scripts" / "ops" / "run_all_gates.py").read_text(encoding="utf-8")
    hook_src = (SYSTEM_ROOT / "scripts" / "ops" / "pre-commit.sh").read_text(encoding="utf-8")
    assert "error_axis_guard.py" in gates_src, "未登记进 run_all_gates.py::GATES"
    assert "error_axis_guard.py" in hook_src, "未登记进 pre-commit.sh"
