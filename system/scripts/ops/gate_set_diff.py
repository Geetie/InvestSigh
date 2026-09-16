#!/usr/bin/env python3
"""把「两组门禁集合之差」派生成**一行可读文本**（缺口 `G-65`，卡 `#96` §③）。

```
python system/scripts/ops/gate_set_diff.py <run_all_gates.py> <pre-commit.sh> <shell 扫得的本树门禁数>
```

标准输出**恰好一行**（无换行以外内容），由 `pre-commit.sh` 直接接在
`pre-commit: 判据树 HEAD=<sha> · 本树门禁 N 道 · ` 之后。

## 为什么需要它（`G-65`：流程级缺口）

`run_all_gates.py::GATES` **27 道** vs `pre-commit.sh` **14 道**不是同一集合
⇒ **有 13 道只在集成时跑，红着也不挡提交**。此前这个差**在任何输出里都不可见**。

★ **明确不做**：把 27 道塞进 `pre-commit`。那会让每次提交变慢，而"**卡死的门禁 = 被关掉的门禁**"；
  且 `口径 16` 已定 pre-commit 不跑 pytest（13 道里的多数）。
⇒ 只做**可见性**：多打一行，让差**机器可读**。

## 为什么用"装载模块"而不是"文本扫 `GATES`"（`G-06`）

`GATES` 是**真源**。文本扫行只在"格式恰好是这样"时成立 ——
格式一变，计数会**静默漂移**（本卡上一轮实测过同族形态：`_gate_count` 静默变成 `0`，
而 14 道照跑、脚本照常 `exit 0`）。故此处 `spec_from_file_location` **按路径装载真源模块**
取 `len(GATES)`；`__main__` 守卫保证不执行 `main()`。

## 与 `pre-commit.sh` 的关系

两边都在数"本树门禁"，但**手段独立**：本文件用正则扫 `run_gate "<label>" "$CODE_ROOT/<rel>"`，
`pre-commit.sh` 用 `case` 扫行首。**两处派生必须一致** —— 不一致时报 `⚠`（不阻断提交）。
"同一事实的两条派生路径必须对得上"是 `G-06` 在**派生层**的形态；只写一条就没人能发现它漂了。

## 退出码

`0` 一律（**本文件永不阻断提交**：它是可见性工具，不是门禁）；`2` 仅用于用法错误。

★ 但**取不到数时不许默默当 0**：`run_all_gates.py` 不在本树 / 装载失败 / `GATES` 不是序列
⇒ 输出里显式写"**取不到**（⚠ 不得当作 0）"。假数比不报更坏（`G-03`：0 道 ≠ 没门禁）。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

# ★ 与 `pre-commit.sh` 的调用点**同源**：`run_gate "<label>" "$CODE_ROOT/<rel>" [args…]`
#   （`tests/guards/test_precommit_exit_contract.py::_GATE_RE` 是同一形状的第三份副本，
#     那边用于"真违例仍 exit 1"的夹具构造。）
_GATE_RE = re.compile(r'run_gate\s+"[^"]*"\s+"\$CODE_ROOT/(?P<rel>[^"]+)"')


def gates_of_run_all_gates(path: Path) -> list[str] | str:
    """按路径装载真源模块，取 `GATES` 的脚本相对路径列表。

    ★★ **失败时返回「原因字符串」，返回类型里就写着"可能失败"** ——
      `no_placeholder_guard::SWALLOW_EXCEPTION_CONTINUE` 判据的初版实现（`except … return None`）
      **当场被它抓下**，而且**抓得对**：静默吞掉失败会让"**文件不在本树**"与"**装载失败**"
      在调用方**看起来一模一样**（`G-62`）。
      ⇒ 照本项目已两次记录的修法（`scripts/ops/sample_batch_times.py::_read_log_header`、
        `scripts/daily/coverage.py:145`）：**失败也携带原因**并进入输出，而不是 `None`。
      ★ 这也与本节的目的自洽：这个文件**就是**为"不许静默"而写的。
    """
    if not path.is_file():
        return f"文件不在本树：{path.name}"
    try:
        spec = importlib.util.spec_from_file_location("_gate_set_diff_rag", path)
        if spec is None or spec.loader is None:
            return f"无法按路径装载（spec/loader 为空）：{path.name}"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as exc:                             # noqa: BLE001 —— 但**携带原因**，不吞
        return f"装载失败（{type(exc).__name__}: {exc}）"
    gates = getattr(mod, "GATES", None)
    if not isinstance(gates, (list, tuple)):
        return f"`GATES` 不是序列（实为 {type(gates).__name__}）"
    rels: list[str] = []
    for entry in gates:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            rels.append(str(entry[1]))
    if not rels:
        return "`GATES` 是空序列（⚠ 空 ≠ 没有门禁 —— 不得当作 0）"
    return rels


def gates_of_pre_commit(text: str) -> list[str]:
    return [m.group("rel") for m in _GATE_RE.finditer(text)]


def clause(rag_path: Path, pc_path: Path, shell_n: int) -> str:
    rels = gates_of_run_all_gates(rag_path)
    if isinstance(rels, str):
        # ★ 把**原因**原样带出去（"取不到"必须带得清是哪一种取不到）
        return f"run_all_gates 道数**取不到**（{rels}；⚠ 不得当作 0）"
    try:
        pc_text = pc_path.read_text(encoding="utf-8")
    except OSError:
        return (
            f"run_all_gates 共 {len(rels)} 道（本文件自身读不到，两集合之比**不可得**）"
        )
    pc_rels = gates_of_pre_commit(pc_text)
    g, p = set(rels), set(pc_rels)
    extra = sorted(g - p)
    only_here = sorted(p - g)

    parts = [f"run_all_gates 另有 {len(extra)} 道（集成时跑）"]
    if only_here:
        # ★ 危险方向：提交时跑、但**没登记**进 run_all_gates ⇒ 两处口径不一致（`G-07`）。
        parts.append(
            f"⚠ 本树另有 {len(only_here)} 道**未登记**进 run_all_gates："
            f"{'、'.join(only_here)}（`G-07`：两处口径不一致）"
        )
    # ★ `shell_n <= 0` 表示 `pre-commit.sh` 自己也没数出来（它有自己的 `取不到` 说法）
    #   ⇒ 此时**不做**这条交叉核对，免得报一个**假的**不一致。
    if 0 < shell_n != len(p):
        parts.append(
            f"⚠ 两处派生不一致：`pre-commit.sh` 的 case 扫得 {shell_n} / 本文件的正则扫得 {len(p)}"
        )
    return " · ".join(parts)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 3:
        print(
            "用法：gate_set_diff.py <run_all_gates.py> <pre-commit.sh> <本树门禁数>",
            file=sys.stderr,
        )
        return 2
    rag_path, pc_path = Path(argv[0]), Path(argv[1])
    try:
        shell_n = int(argv[2])
    except ValueError:
        print(f"[INPUT-ERROR] 本树门禁数不是整数：{argv[2]!r}", file=sys.stderr)
        return 2
    # ★ `%s` 而非 f-string 嵌套：`clause()` 自己已经拼好了，这里只补断行
    print(clause(rag_path, pc_path, shell_n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
