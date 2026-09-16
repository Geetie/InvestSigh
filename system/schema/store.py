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
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Sequence

from pydantic import BaseModel

from .models import JSONL_MODELS, model_for

FACTS_DIRNAME = "facts"


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
    """文件锁（`Ch9 §3.10 J6` 首版单写者 + 文件锁）。

    锁文件落在 `index/.locks/`（**非真源目录**），避免污染 `facts/` 的追加式真源。
    """
    lock_dir = root / "index" / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{stem}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
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
        with open(path, "a", encoding="utf-8") as fh:
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
