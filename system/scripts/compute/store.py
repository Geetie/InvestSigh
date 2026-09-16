"""`store.py` —— `derived/` 追加式持久化（`Ch9 §3.3.3` `derived/` / `§3.5` 阶段④）。

`Ch9 §3.3.3` 把 `derived/` 定义为"**确定性计算结果（带公式与操作数引用）**"，
与 `facts/` 的 18 个 JSONL **分开** —— 故本层把 `DerivedValue` 落 `derived/`，
**不**往 `facts/` 写（`facts/` 恰为 18 个 JSONL，**不得增删改名**，见
`tests/unit/test_contracts.py::test_facts_dir_holds_exactly_the_18_files`）。

追加式不可变（`Ch9 §3.4.2` / 纪律 4）：

| 机制 | 实现 |
|---|---|
| 只追加 | 只 `open(path, "a")`，**无** UPDATE/DELETE |
| 防并发 | **复用** `schema.store._file_lock`（同一 `index/.locks/`，**不新增**第二条锁路径，纪律 11） |
| 幂等 | `(derived_id, version, method_version)` 已存在 → **跳过追加**（`Ch9 §3.5` 阶段④幂等键 `(company_id, version, method_version)`；`N9.2-11`） |
| `method_version` 变更 | `(derived_id, version, method_version)` 是新键 → **新增行**，旧行保留（`Ch9 §2.3`） |
| `version` 变更（上游重述） | 同 `derived_id`/`method_version`、新 `version` → **新键 → 新增行**（防"上游重述被静默沿用旧值"；`Ch9 §3.5` 阶段④） |

消费方：`scripts/trace/traceback.py::_find_derived()` 真读 `derived/*.jsonl`。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from schema.models import DerivedValue
from schema.store import _file_lock  # 复用唯一文件锁实现（纪律 11 / Ch9 §3.10 J6）

from .contract import DEFAULT_VERSION, ComputeGap


@dataclass(frozen=True)
class AppendOutcome:
    """一次 `DerivedValue` 追加的**如实结果**（`Ch9 §3.5` 阶段④）。

    | 字段 | 语义 |
    |---|---|
    | `written` | **本轮真正新写入**的 `derived_id`（首次某幂等键） |
    | `skipped` | 本轮**考察过、但键已存在故未写入**的 `derived_id`（幂等命中） |

    ★ **两者互斥**（`pipeline.assert_steps_complete` 的 G-42 互斥校验）：
      同一个 `derived_id` 不可能**既**是"本轮新写入"**又**是"已存在故未写入"。
      本类在 `__post_init__` 里**自己断言**这条不变量 —— 违反即**响亮失败**，
      不把自相矛盾的结果交给上层（否则上层只能靠"相信"）。
    """

    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        overlap = sorted(set(self.written) & set(self.skipped))
        if overlap:
            raise ValueError(
                f"AppendOutcome 自相矛盾：{overlap} 同时出现在 written 与 skipped —— "
                "同一 derived_id 不可能既'本轮新写入'又'已存在故未写入'"
            )


DERIVED_DIRNAME = "derived"
DERIVED_VALUES_STEM = "derived_values"
DERIVED_GAPS_STEM = "compute_gaps"


def derived_dir(root: str | Path) -> Path:
    return Path(root) / DERIVED_DIRNAME


def values_path(root: str | Path) -> Path:
    """`derived/derived_values.jsonl` —— `DerivedValue` 的追加式真源。"""
    return derived_dir(root) / f"{DERIVED_VALUES_STEM}.jsonl"


def gaps_path(root: str | Path) -> Path:
    """`derived/compute_gaps.jsonl` —— 缺口对象的追加式真源（缺口也留痕）。"""
    return derived_dir(root) / f"{DERIVED_GAPS_STEM}.jsonl"


def _append_lines(root: str | Path, stem: str, lines: Sequence[str]) -> int:
    """**追加**若干 JSON 行（唯一写入口）；空 `lines` 不建文件、不写。"""
    if not lines:
        return 0
    path = derived_dir(root) / f"{stem}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(lines) + "\n"
    with _file_lock(Path(root), f"derived_{stem}"):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(payload)
    return len(lines)


def read_rows(root: str | Path, stem: str) -> list[dict[str, Any]]:
    """读某 stem 的全部行（原始 dict）。文件不存在 → 空列表。损坏行 → **响亮失败**。"""
    path = derived_dir(root) / f"{stem}.jsonl"
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} 不是合法 JSON: {exc}") from exc
    return out


def existing_keys(root: str | Path) -> set[tuple[str, str, str]]:
    """已存在的 `(derived_id, version, method_version)` 键集合（幂等判据）。

    ★ `version` 是 `Ch9 §3.5` 阶段④ 幂等键的分量（上游基线版本）；旧行若未写 `version`
      列，按 `DEFAULT_VERSION` 归一（兼容历史行），不改变其字节。
    """
    return {
        (
            str(row.get("derived_id", "")),
            str(row.get("version", DEFAULT_VERSION)),
            str(row.get("method_version", "")),
        )
        for row in read_rows(root, DERIVED_VALUES_STEM)
    }


def append_derived_value_ids_detailed(
    root: str | Path,
    values: Sequence[DerivedValue],
    *,
    version: str = DEFAULT_VERSION,
    skip_existing: bool = True,
) -> AppendOutcome:
    """追加 `DerivedValue`，返回 `(written, skipped)` **两个**互斥集合（`AppendOutcome`）。

    ★ **这是"哪些算已存在"的唯一定义处**（`G-06` 唯一真源）：幂等判据 = 键
      `(derived_id, version, method_version)` 是否已在 `derived/derived_values.jsonl`
      （`Ch9 §3.5` 阶段④）。**任何**调用方（CLI / step 处理器 / 测试）都只能由此得到
      "已存在"这件事，**不得**在别处重算 —— 否则同一个问题会有两个答案，
      而它们总有一天会不一致。

    语义（`Ch9 §3.4.2` 追加式不可变）：

    - 首次某 `(derived_id, version, method_version)` → **写入**，进 `written`；
    - 同键重跑 → **跳过追加**，进 `skipped`（**不是**"什么都没干"：这是**已完成的判定**）；
    - 上游重述（同 `derived_id`/`method_version`、**新 `version`**）→ **新键** → **新增行**，
      旧行保留。

    ★ **互斥归一**：同一 `derived_id` 若在本批次内既有**新键**写入、又有**旧键**命中
      （例如同名派生值的方法版本升级），则**以写入为准**、`skipped` 里剔除它 ——
      保证 `written ∩ skipped = ∅`（G-42）。这是**归一**而非丢弃信息：
      "本轮确实写了这个对象"是更强的事实。
    """
    seen = existing_keys(root) if skip_existing else set()
    written: list[str] = []
    hits: list[str] = []
    lines: list[str] = []
    for value in values:
        key = (value.derived_id, version, value.method_version)
        if skip_existing and key in seen:
            hits.append(value.derived_id)
            continue
        seen.add(key)
        written.append(value.derived_id)
        lines.append(_dump_row(value, version))
    _append_lines(root, DERIVED_VALUES_STEM, lines)
    written_set = set(written)
    skipped = sorted({i for i in hits if i not in written_set})
    return AppendOutcome(written=written, skipped=skipped)


def append_derived_value_ids(
    root: str | Path,
    values: Sequence[DerivedValue],
    *,
    version: str = DEFAULT_VERSION,
    skip_existing: bool = True,
) -> list[str]:
    """追加 `DerivedValue`（返回**实际写入**的 `derived_id` 列表）。

    本函数是 `append_derived_value_ids_detailed` 的**只取写入侧的视图**（既有契约不变：
    调用方只关心"写进去了什么"）。幂等判定**不在这里重复实现**，见后者的 docstring。
    """
    return append_derived_value_ids_detailed(
        root, values, version=version, skip_existing=skip_existing
    ).written


def append_derived_values(
    root: str | Path,
    values: Sequence[DerivedValue],
    *,
    version: str = DEFAULT_VERSION,
    skip_existing: bool = True,
) -> int:
    """追加 `DerivedValue`（返回**实际写入**行数）。

    幂等键 = `(derived_id, version, method_version)`；语义与 `append_derived_value_ids` 一致，
    本函数只是其"写了几行"的计数视图（兼容既有调用方）。
    """
    return len(append_derived_value_ids(root, values, version=version, skip_existing=skip_existing))


def append_gaps(
    root: str | Path,
    gaps: Sequence[ComputeGap],
    *,
    skip_existing: bool = True,
) -> int:
    """追加缺口对象（返回实际写入行数）。幂等键 = `(gap_id, missing)`。"""
    seen = {
        (str(row.get("gap_id", "")), tuple(row.get("missing", [])))
        for row in read_rows(root, DERIVED_GAPS_STEM)
    } if skip_existing else set()
    lines: list[str] = []
    for gap in gaps:
        key = (gap.gap_id, tuple(gap.missing))
        if skip_existing and key in seen:
            continue
        seen.add(key)
        lines.append(json.dumps(gap.to_dict(), ensure_ascii=False, sort_keys=True))
    return _append_lines(root, DERIVED_GAPS_STEM, lines)


def _dump_row(value: DerivedValue, version: str = DEFAULT_VERSION) -> str:
    """`DerivedValue` → 单行 JSON（`Decimal`/`datetime` 走 pydantic 的 json 模式）。

    `version` 作为 `derived/` 真源的**行级列**并入（`Ch9 §3.5` 阶段④ 幂等键的 `version`
    分量）；冻结的 `schema/models.py::DerivedValue` 不含该字段，故在序列化处补列，**不改模型**。
    """
    row = value.model_dump(mode="json")
    row["version"] = version
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def history_for(root: str | Path, derived_id: str) -> list[dict[str, Any]]:
    """某 `derived_id` 的**全部历史行**（追加式不可变的证据：方法版本变更留全量）。"""
    return [row for row in read_rows(root, DERIVED_VALUES_STEM) if row.get("derived_id") == derived_id]


def current_value(
    root: str | Path,
    derived_id: str,
    *,
    method_version: str | None = None,
) -> dict[str, Any] | None:
    """取某 `derived_id` 的**当前**结果（append-only → 取最后一行）。

    给定 `method_version` 时只在该版本内取最后一行。找不到 → `None`
    （这是"没算过"，不是"算出来是空"；缺口请查 `compute_gaps.jsonl`）。
    """
    rows = history_for(root, derived_id)
    if method_version is not None:
        rows = [r for r in rows if str(r.get("method_version", "")) == method_version]
    return rows[-1] if rows else None


def iter_all_values(root: str | Path) -> Iterable[dict[str, Any]]:
    """遍历全部 `DerivedValue` 行（供完整性自检使用）。"""
    return read_rows(root, DERIVED_VALUES_STEM)
