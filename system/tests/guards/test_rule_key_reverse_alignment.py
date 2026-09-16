"""方向 2「`rules/` 声明的记录列必须有消费者」的**可执行反例 + 反向对照 + 白名单机器绑定**。

被检对象：`scripts/checks/rule_key_alignment_guard.py` 的**反向**检查
（张力 `T-18` 家族：**「写在声明里」≠「在机器上有效力」**）。

## 为什么这些用例必须存在

方向 1 只做**单向**（代码读的键必须存在）。它的补集 —— **`rules/` 里声明了语义、代码区却从不读**
—— 是这条张力的暴露面，且**专挑两个盲区叠加处藏身**：
① 上游只枚举**叶键**（`_leaf_paths` 把 list 当叶子）⇒ `pipeline.yaml::steps[*]` 的列不在被检集；
② 它的名字**只出现在 docstring** ⇒ 文本口径的扫描器又会把它算成"已消费"。

⇒ 本文件用**真注入**证明方向 2 会红，并配**反向对照**（不改 ⇒ `exit 0`）：
两次运行之间唯一差别就是那次注入（`施工图 §5.1 AC-04`：注入违例 ⇒ **exit 1**，不是 warn）。
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from conftest import SYSTEM_ROOT, run_gate_inproc

GUARD = "scripts/checks/rule_key_alignment_guard.py"
PIPELINE_PY = Path("scripts") / "orchestrate" / "pipeline.py"
BENCHMARK_YAML = Path("rules") / "benchmark.yaml"

#: `T-18` 的**唯一代码消费者**所在行（`pipeline.py::_deferred_by_design`）——注入锚点。
_CONSUMER_ANCHOR = '    return cfg.get("implemented_in_first_version") is False\n'
#: `benchmark.yaml::benchmark_objects` 的第一条记录 —— 用来注入一个**全新**的记录列。
_BENCH_RECORD_ANCHOR = "    benchmark_role: primary"
_NEW_COLUMN = "reverse_probe_new_column"


def _inject(path: Path, *, old: str, new: str) -> None:
    """把 `old` 换成 `new` 并★**自证注入已生效**（否则用例测的是"什么都没发生"）。"""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"注入点未找到（上游文本已变？）：{old!r}"
    mutated = text.replace(old, new, 1)
    assert mutated != text, "注入是 no-op —— 替换前后文本相同，本用例将毫无判别力"
    path.write_text(mutated, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == mutated, "注入未落盘"


# ─────────────────── ① 反向对照 + 覆盖面（同一份副本，后续臂的基准） ───────────────────


def test_clean_copy_passes_and_reverse_direction_is_live(code_root: Path) -> None:
    """干净副本必须 `exit 0`，且方向 2 的**计数与说明**都在输出里。

    ★ 为什么"计数必须出现"要写进断言：一个**根本没跑**的反向段也能产出"PASS"。
      四个计数里任一消失 ⇒ 方向 2 静默退化，而输出看上去完全正常（`G-03`）。
    """
    code, out = run_gate_inproc(GUARD, code_root)

    assert code == 0, f"干净副本上应 exit 0，实得 {code}\n{out}"
    assert "RESULT: PASS" in out, f"未见 PASS 结论\n{out}"
    for needle in (
        "reverse_record_columns:",
        "reverse_unconsumed_columns:",
        "whitelisted_unconsumed_columns:",
        "方向 2",
    ):
        assert needle in out, f"输出里缺 {needle!r} —— 方向 2 的覆盖面不可见\n{out}"
    # ★ `T-18` 的死列在**合法态**下必须**不是**候选（它的消费点已接线）。
    assert "pipeline.yaml::steps::implemented_in_first_version" not in out, (
        f"合法态下 `implemented_in_first_version` 仍被当成无消费者 —— 消费点没接上\n{out}"
    )


# ─────────────────── ② 反例 A：删掉 `T-18` 的消费点（AC-03 的机器绑定） ───────────────────


def test_removing_the_first_version_consumer_is_blocked(code_root: Path) -> None:
    """★ 把 `implemented_in_first_version` 的读取点改名 ⇒ 方向 2 **exit 1**；恢复后 `exit 0`。

    ★ 这条正是 `T-18` 的机器绑定：**死列一旦复活就当场拦下**，避免它再退化成
      "声明在 `rules/` 里、代码零消费者"（本项目第三次同形态事故）。
    """
    path = code_root / PIPELINE_PY

    code, out = run_gate_inproc(GUARD, code_root)          # 反向对照（同副本、注入前）
    assert code == 0, f"未注入时应 exit 0，实得 {code}\n{out}"

    _inject(
        path,
        old=_CONSUMER_ANCHOR,
        new='    return cfg.get("implemented_in_first_version_moved") is False\n',
    )
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"删掉消费点后应 exit 1，实得 {code}\n{out}"
    assert "rules/pipeline.yaml::steps::implemented_in_first_version" in out, (
        f"应点名是哪条记录列变成死列\n{out}"
    )
    assert "零效力" in out, f"应说清后果是「声明在机器上零效力」\n{out}"

    # 恢复（把消费点改回来）⇒ 必须重新变绿。
    _inject(
        path,
        old='    return cfg.get("implemented_in_first_version_moved") is False\n',
        new=_CONSUMER_ANCHOR,
    )
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 0, f"恢复消费点后应 exit 0，实得 {code}\n{out}"


# ─────────────────── ③ 反例 B：新增一条**未登记**的记录列 ───────────────────


def test_new_unregistered_record_column_is_blocked(code_root: Path) -> None:
    """给 `benchmark_objects` 注入一个**全新**列 ⇒ `exit 1`；且提示应登记到哪里。

    ★ 这条证明方向 2 覆盖 **list-of-records**（而不是只覆盖 dict-of-dicts），
      并且**新出现的**无消费者列不会被既有白名单"顺带"盖住。
    """
    path = code_root / BENCHMARK_YAML

    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 0, f"未注入时应 exit 0，实得 {code}\n{out}"

    _inject(
        path,
        old=_BENCH_RECORD_ANCHOR,
        new=f"{_BENCH_RECORD_ANCHOR}\n    {_NEW_COLUMN}: 1",
    )
    code, out = run_gate_inproc(GUARD, code_root)
    assert code == 1, f"注入未登记的新列后应 exit 1，实得 {code}\n{out}"
    assert f"benchmark_objects::{_NEW_COLUMN}" in out, f"应点名新列\n{out}"
    assert "KNOWN_UNCONSUMED_RULE_COLUMNS" in out, (
        f"应告诉读者「已声明尚未接线」要登记到哪里（不然下一个人只能放宽判据）\n{out}"
    )


# ─────────────────── ④ 白名单本身的机器绑定（`口径 13`：方向 2 那张表） ───────────────────


def test_reverse_waiver_table_is_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    """★ `口径 13` 的四字段**逐条**校验必须覆盖**方向 2 那张表**。

    ★ 为什么单列一条：`_selfcheck_waivers` 早先只遍历两张表。若新表被漏掉，
      一条字段残缺的**方向 2** 豁免会**静默**生效 —— 那正是"把门禁关掉"。
    """
    from scripts.checks import rule_key_alignment_guard as G

    valid = {
        "reason": "r",
        "owner": "o",
        "expected_consumer_by": "e",
        "review_by": "2026-10-31",
    }
    monkeypatch.setattr(
        G, "KNOWN_UNCONSUMED_RULE_COLUMNS",
        {("a.yaml", "c::k"): G._Waiver(**valid)},  # type: ignore[arg-type]
    )
    G._selfcheck_waivers()  # 合法 ⇒ 不抛

    for field in ("reason", "owner", "expected_consumer_by", "review_by"):
        broken = dict(valid)
        broken[field] = "   "
        monkeypatch.setattr(
            G, "KNOWN_UNCONSUMED_RULE_COLUMNS",
            {("a.yaml", "c::k"): G._Waiver(**broken)},  # type: ignore[arg-type]
        )
        with pytest.raises(ValueError) as exc:
            G._selfcheck_waivers()
        assert field in str(exc.value), f"失败信息应点名缺哪个字段（实得 {exc.value}）"


# ─────────────────── ⑤ `P-05`（<0.5s）—— 如实限定在**新增的反向段** ───────────────────


def test_reverse_record_column_enumeration_is_cheap(code_root: Path) -> None:
    """★ `P-05`：**本次新增的反向判定段**必须很快（记录列枚举 + 集合差判定）。

    ★ **如实登记**（不是打折）：本守卫在**本次改动之前**就要整树 AST 解析 `scripts/**`
      （实测基线 > 0.5s），故 `P-05` 的 0.5s 预算**只能**加在**新增的反向段**上；
      整道门禁的总耗时如实写在报告里。这里断言的是"新增部分不会把门禁拖慢"这一事实。
    """
    from scripts.checks import rule_key_alignment_guard as G

    docs = G._load_rule_docs(code_root)
    t0 = time.perf_counter()
    columns = [col for name in docs for col in G._record_columns(docs[name])]
    elapsed = time.perf_counter() - t0
    assert columns, "记录列枚举为空 ⇒ 方向 2 **无被检对象**（`G-03`：无被检对象 ≠ 已验证）"
    assert elapsed < 0.5, f"记录列枚举 {elapsed:.3f}s ≥ 0.5s（`P-05`）"


# ─────────────────── ⑥ `G-07`：本守卫两处同时登记 ───────────────────


def test_reverse_direction_is_registered_in_both_gate_lists() -> None:
    """★ `G-07`：方向 2 与方向 1 **共用同一守卫脚本**，该脚本必须**同时**进两处清单。

    ★ 为什么这条要显式再断言一次：方向 2 是**新增的阻断面**，若只因它寄居在一个
      已登记的脚本里就假定"当然两处都有"，一旦有人把该脚本从某一处删掉，
      方向 2 会与方向 1 一起**静默消失**。
    """
    gates_src = (SYSTEM_ROOT / "scripts" / "ops" / "run_all_gates.py").read_text(encoding="utf-8")
    hook_src = (SYSTEM_ROOT / "scripts" / "ops" / "pre-commit.sh").read_text(encoding="utf-8")
    assert "rule_key_alignment_guard.py" in gates_src, "未登记进 run_all_gates.py::GATES"
    assert "rule_key_alignment_guard.py" in hook_src, "未登记进 pre-commit.sh"
