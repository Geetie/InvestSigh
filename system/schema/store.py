"""追加式不可变真源的读写层（`Ch9 §3.3.2` / `§3.4.2`）。

机制（逐字对齐 `Ch9 §3.4.2`）：

| 机制 | 实现 |
|---|---|
| 每次写入 | 一次 commit（commit message 带 `task_id`） |
| 防覆盖 | **pre-commit hook 拒绝修改既有行的 diff**（新增行放行，修改/删除既有行报错） |
| 并发冲突 | 文件锁 + `git pull --rebase` |
| 版本类型标记 | `version_kind ∈ {forecast_revision, financial_restatement, source_retraction}` |

本模块只做"追加 + 读取 + as-of 过滤"；**不做任何 UPDATE/DELETE**——
`append_records` 是本文件唯一的写入口，`truncate` 仅测试夹具可用且需显式开关。

★ **文件锁的跨平台实现见 `_file_lock`**（`Ch9 §3.10 J6`）：Unix 走 `fcntl.flock`
（**建议锁**）、Windows 走 `msvcrt.locking`（**强制锁**）。两条分支的语义**并不等价**，
差异逐字写在该函数的 docstring 里（`CONVENTIONS.md §四 R-02`：docstring 只写真做到的事），
**不得**含糊成"跨平台文件锁"。
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Sequence

from pydantic import BaseModel

from .models import JSONL_MODELS, model_for

FACTS_DIRNAME = "facts"

# ── 跨平台文件锁后端（`Ch9 §3.10 J6` 首版单写者 + 文件锁；纪律 9）──────────────
#
# ★★ 为什么是「按平台分支」而**不是**写一个 `fcntl` shim：
#    shim 在 Windows 上会让锁**退化为无操作** —— 那与"没上锁"在可观测输出上**逐字同形**，
#    正是 `CONVENTIONS.md §五 G-62` 的「静默等价态」：并发保护被静默取消，而调用方
#    完全看不出来。本项目的铁律是「锁必须有校验方」，故**不允许**无操作降级。
#    ⇒ 两条分支都**真上锁**；既不支持的平台**直接抛异常**（响亮失败），不静默放行。
def _select_lock_backend() -> str:
    """按 `os.name` 选锁后端；既不支持的平台 → **抛 `RuntimeError`**。

    ★ 为什么**不是**静默返回一个"无锁"后端（`CONVENTIONS.md §五 G-62`）：
      无锁与"锁上了但没冲突"在可观测输出上**逐字同形** —— 并发保护被静默取消，
      而调用方完全看不出来。按 `Ch9 §3.10 J6`（单写者 + 文件锁）必须**响亮失败**。

    ★ 为什么单独成函数（而不是内联在模块 `if/elif/else` 里）：内联写法下
      这条分支**不可测** —— 要触发它就得改 `os.name` 后重新导入本模块，
      而 `pathlib` 在 `os.name` 非 `nt` 的 Windows 上会先抛
      `RuntimeError: cannot instantiate 'PosixPath' on your system`，
      真正的守卫根本轮不到执行（实测）。抽出成函数后，测试可以**直接调用**它
      （此时 `pathlib` 早已导入完毕，不会再实例化 `Path`）⇒ 该分支**真的被测到**。
    """
    if os.name == "nt":
        return "msvcrt"
    if os.name == "posix":
        return "fcntl"
    raise RuntimeError(
        f"不支持的平台 os.name={os.name!r}：`_file_lock` 无法提供排他文件锁。"
        "按 `Ch9 §3.10 J6`（单写者 + 文件锁）必须**响亮失败**，不得静默退化为无锁。"
    )


LOCK_BACKEND: str = _select_lock_backend()
"""当前生效的锁后端：`"fcntl"`（Unix）/ `"msvcrt"`（Windows）。测试与诊断可直读。"""

if LOCK_BACKEND == "msvcrt":
    import msvcrt
elif LOCK_BACKEND == "fcntl":
    import fcntl

_LOCK_NBYTES = 1
"""Windows 侧锁的**字节数**（自偏移 0 起）。

★ 为什么 1 字节就够：互斥来自"**所有写者都锁同一把锁文件的同一区间**"
（纪律 11：全仓唯一锁路径），而**不是**靠锁住锁文件的全部内容。
锁文件本身不承载数据 —— 它只是各方约定的**一个争用点**。
"""


def _acquire_exclusive(fd: int) -> None:
    """**阻塞**取排他锁；取不到 → **抛 `OSError`**（`G-01`：命中即 fail，不静默降级）。"""
    if LOCK_BACKEND == "fcntl":
        fcntl.flock(fd, fcntl.LOCK_EX)
        return
    # Windows：`msvcrt.locking` 锁的是「**当前文件位置**起的 `_LOCK_NBYTES` 字节」，
    # 故取锁前**必须**先 `lseek` 到区间起点 —— 少了这一步会锁到别处（**静默失效**）。
    os.lseek(fd, 0, os.SEEK_SET)
    msvcrt.locking(fd, msvcrt.LK_LOCK, _LOCK_NBYTES)


def _release_exclusive(fd: int) -> None:
    """释放 `_acquire_exclusive` 取到的锁（与之严格配对）。"""
    if LOCK_BACKEND == "fcntl":
        fcntl.flock(fd, fcntl.LOCK_UN)
        return
    os.lseek(fd, 0, os.SEEK_SET)
    msvcrt.locking(fd, msvcrt.LK_UNLCK, _LOCK_NBYTES)


class AppendOnlyViolation(RuntimeError):
    """试图修改/删除既有行 —— 追加式不可变被破坏（`Ch9 §3.4.2`）。"""


class UnknownJsonlError(KeyError):
    """未知 JSONL —— **响亮失败**，不返回兜底空结果。"""


def facts_dir(code_root: str | Path) -> Path:
    return Path(code_root) / FACTS_DIRNAME


def jsonl_path(code_root: str | Path, stem: str) -> Path:
    """取 JSONL 路径；stem 非法 → 抛 `UnknownJsonlError`（**不静默建新文件**）。"""
    if stem not in JSONL_MODELS:
        raise UnknownJsonlError(f"未知 JSONL: {stem!r}；合法值见 Ch9 §3.3.3: {sorted(JSONL_MODELS)}")
    return facts_dir(code_root) / f"{stem}.jsonl"


@contextmanager
def _file_lock(root: Path, stem: str) -> Iterator[None]:
    """排他文件锁（`Ch9 §3.10 J6` 首版单写者 + 文件锁；纪律 9）。

    锁文件落在 `index/.locks/`（**非真源目录**），避免污染 `facts/` 的追加式真源。
    全仓**只有这一条锁路径** —— `scripts/compute/store.py::_append_lines` 复用本函数
    （纪律 11 复用优先 / `CONVENTIONS.md §二 G-06` 唯一真源）。

    ★★ **两条平台分支的语义并不等价**，逐字写明
    （`CONVENTIONS.md §四 R-02`：docstring 只写代码**真做到**的事）：

    | | Unix（`fcntl.flock`） | Windows（`msvcrt.locking`） |
    |---|---|---|
    | 锁的性质 | **建议锁**（advisory）：只在**同样调用 `flock`** 的各方之间生效 | **强制锁**（mandatory）：不调用 `locking` 的访问**也会被拒** |
    | 锁的范围 | 整个文件（open file description） | **字节区间**：偏移 0 起的 `_LOCK_NBYTES`（=1）字节；**区间外**的读写不受影响 |
    | 等待 | `LOCK_EX` **无限期阻塞** | `LK_LOCK` **有界重试**：CRT 内部约 10 次 × ≈1s，之后**抛 `OSError`** |
    | 同进程不同 fd | 互斥（新 fd = 新的 open file description） | **互斥** |

    ⇒ 二者在**本项目的使用方式**下给出**同一个排他性结论**：所有写者都按同一约定锁
    同一把锁文件的同一字节区间 ⇒ 互斥成立。
    **但差异确实存在**，不许含糊成"跨平台文件锁" —— 尤其是 Windows 侧
    「等待**有界**（≈10s）、取不到就**响亮失败**」这一点（实测 9.41s 后
    `OSError(36, 'Resource deadlock avoided')`）。

    ★ 取不到锁 → **抛异常**，绝不静默降级为无锁（`CONVENTIONS.md §五 G-62`）。
    ★ `finally` 里**先解锁再关 fd**；且**只有真的取到锁才解锁**（`held` 标志）——
      取锁失败时不再去做一次可能自己抛异常、并**掩盖真正原因**的解锁。
    """
    lock_dir = root / "index" / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{stem}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    held = False
    try:
        _acquire_exclusive(fd)
        held = True
        yield
    finally:
        if held:
            _release_exclusive(fd)
        os.close(fd)


def append_records(code_root: str | Path, stem: str, records: Sequence[BaseModel]) -> int:
    """**追加**若干行（唯一写入口）。返回写入行数。

    写入前逐条做 pydantic 校验；校验失败 → **抛异常，不写入**（不留半截数据）。
    """
    root = Path(code_root)
    path = jsonl_path(root, stem)
    model = model_for(stem)
    lines: list[str] = []
    for rec in records:
        if not isinstance(rec, model):
            rec = model.model_validate(rec)  # 触发校验；非法即抛
        lines.append(json.dumps(rec.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
    if not lines:
        return 0
    payload = "\n".join(lines) + "\n"
    with _file_lock(root, stem):
        # ★ **`newline="\n"` 是刻意的，不是冗余**（本仓 macOS 会话补；见 `platform_defects_ledger §8-2`）：
        #   文本模式默认 `newline=None` ⇒ 写出的 `\n` 会被翻成 **`os.linesep`** ——
        #   在 Windows 上就是 `\r\n`。而 `system/.gitattributes` 是 `* -text`（不做行尾转换，
        #   字节原样存取）+ `rules/` 按内容哈希上锁 ⇒ **写入端必须与平台无关**。
        #   实测（修复前）：`facts/tasks.jsonl` / `facts/recommendations.jsonl` 已是
        #   **混合行尾**（Windows 写的行 CRLF / Mac 写的行 LF），因它们**是追加式真源、
        #   不能回改**，只能从**写入端**根治。
        #   钉 `"\n"` = 显式声明"本真源一律 LF" ⇒ 两个平台写出**逐字节相同**的追加。
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
    return len(lines)


def read_records(code_root: str | Path, stem: str) -> list[dict[str, Any]]:
    """读全部行（**不校验为对象模型**，返回原始 dict，供检查器扫描）。空文件名 → 空列表。"""
    path = jsonl_path(code_root, stem)
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
            except json.JSONDecodeError as exc:  # 损坏行 → 响亮失败
                raise ValueError(f"{path}:{lineno} 不是合法 JSON: {exc}") from exc
    return out


TRUTH_MISSING = "missing"
TRUTH_EMPTY = "empty"
TRUTH_PRESENT = "present"
"""`truth_source_status` 的三个**穷尽且互斥**的取值（见该函数）。"""


def truth_source_status(code_root: str | Path, stem: str) -> str:
    """判定真源 JSONL 的三态：`"missing"` / `"empty"` / `"present"`。

    ★ 为什么需要它（`CONVENTIONS.md §二 G-03`）：`read_records` 对**两种互不相同的
      成因**都返回 `[]` —— ① 真源文件**根本不存在**；② 真源文件存在但**没有有效行**。
      仅凭 `[]` 无法区分，于是调用方（尤其门禁 / 守卫）会把「无被检对象」当成
      「已验证」—— 而这两件事在报告里长得一模一样，正是本项目最忌的**假信号**。

    ★ 锚点（逐字引用 `Ch9 §3.3.3`）：`facts/` 下的 **JSONL 不得增删改名**
      （表集合的唯一真源 = `schema/stems.py::JSONL_STEMS`；数量经需求方 2026-09-16 裁定
      由 18 扩至 22，故此处**不写数字**）。因此「真源文件**缺失**」**本身
     就是结构性违例**，必须与「存在但为空」区分开。

    三态定义（穷尽、互斥）：

    - `"missing"` = 文件不存在（结构性违例，消费方应**响亮失败**）；
    - `"empty"`   = 文件存在但**无有效行**（全空白 / 零字节；真空成立，消费方记 `note` 后放行）；
    - `"present"` = 文件存在且有 **≥1 条**可解析行。

    ★ **不改 `read_records` 的缺省语义**：该访问器被**全仓库**（`scripts/**` / `tests/**`）
      依赖，把它对缺失的返回值从 `[]` 改成抛异常会以**无关原因**让大量既有测试变红
      （本项目最忌的假信号）。故需要区分的调用方在本函数上**显式区分**。

    未知 `stem` → 抛 `UnknownJsonlError`（经 `jsonl_path`，**不静默建新文件**）。
    复用 `read_records` 判「有无有效行」——**不引入第二条解析路径**（`G-06` 唯一真源）。
    """
    path = jsonl_path(code_root, stem)
    if not path.exists():
        return TRUTH_MISSING
    return TRUTH_PRESENT if read_records(code_root, stem) else TRUTH_EMPTY


def read_models(code_root: str | Path, stem: str) -> list[BaseModel]:
    """读全部行并**逐条校验**为对象模型；任一行非法 → 抛异常。"""
    model = model_for(stem)
    return [model.model_validate(row) for row in read_records(code_root, stem)]


def as_of(
    rows: Sequence[dict[str, Any]],
    business_key: Sequence[str],
    *,
    system_asof: datetime | None = None,
    valid_asof: datetime | None = None,
) -> list[dict[str, Any]]:
    """双时间轴 as-of 选取（`Ch9 §3.4.1`）。

    1. 按业务键分组，取 `recorded_seq` 最大且 `first_seen_at <= system_asof` 的版本
    2. 用 `valid_time`（`effective_from` ≤ `valid_asof` < `valid_to`，若存在）过滤业务有效区间

    这是 `git checkout` 之外的**第二步与第三步**：system 轴由 checkout 承载，
    此处只做"取当前版本 + valid 过滤"。
    """
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(row.get(k) for k in business_key)
        groups.setdefault(key, []).append(row)

    selected: list[dict[str, Any]] = []
    for key, group in sorted(groups.items(), key=lambda kv: [str(x) for x in kv[0]]):
        candidates = group
        if system_asof is not None:
            candidates = [
                r
                for r in candidates
                if r.get("first_seen_at") is None
                or datetime.fromisoformat(r["first_seen_at"]) <= system_asof
            ]
        if not candidates:
            continue  # 该时点尚不可知 → 不出现（**不得**用未来版本兜底）
        latest = max(candidates, key=lambda r: (r.get("recorded_seq") or 0))
        if valid_asof is not None:
            eff = latest.get("effective_from")
            if eff is not None and datetime.fromisoformat(eff) > valid_asof:
                continue
        selected.append(latest)
    return selected


def rebuild_index(code_root: str | Path, out_path: str | Path | None = None) -> Path:
    """从 `facts/*.jsonl` **全量重建**索引（`Ch9 §3.3.2`：索引可全量重建）。

    索引**非真源**：删掉 `index/` 后可从 `facts/` 完整重建（write-read-reload AC-02）。
    """
    import sqlite3

    root = Path(code_root)
    target = Path(out_path) if out_path else root / "index" / "facts.sqlite"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    conn = sqlite3.connect(target)
    try:
        conn.execute(
            """
            CREATE TABLE objects (
                jsonl       TEXT NOT NULL,
                line_no     INTEGER NOT NULL,
                recorded_seq INTEGER,
                first_seen_at TEXT,
                payload     TEXT NOT NULL,
                PRIMARY KEY (jsonl, line_no)
            )
            """
        )
        conn.execute("CREATE INDEX ix_jsonl ON objects(jsonl)")
        for stem in sorted(JSONL_MODELS):
            for line_no, row in enumerate(read_records(root, stem), start=1):
                conn.execute(
                    "INSERT INTO objects (jsonl, line_no, recorded_seq, first_seen_at, payload)"
                    " VALUES (?,?,?,?,?)",
                    (
                        stem,
                        line_no,
                        row.get("recorded_seq"),
                        row.get("first_seen_at"),
                        json.dumps(row, ensure_ascii=False, sort_keys=True),
                    ),
                )
        conn.commit()
    finally:
        conn.close()
    return target
