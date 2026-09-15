"""检查器 / 守卫的公共约定。

退出码约定（`00_开发Agent开工提示词 §八 N-2` / `Ch2 §B.3`）：
- `0` 放行
- `1` **阻断**（命中违例）
- `2` 输入异常（文件缺失 / 解析失败 / 用法错误）——**不静默**

★ 纪律 2：所有扫描 / 断言**命中即 fail，禁 warn-only**。本模块只提供
  `Violation` 与 `run_checker`，**不提供任何只 warn 的出口**。
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_INPUT_ERROR = 2


@dataclass(frozen=True)
class Violation:
    """一条违例。`severity` **恒为 FATAL**——本包不接受 warn-only（纪律 2）。"""

    rule: str
    reason: str
    file: str = ""
    line: int = 0
    severity: str = "FATAL"

    def render(self) -> str:
        loc = f"{self.file}:{self.line}" if self.file else "<no-file>"
        return f"[{self.severity}] {self.rule} @ {loc} — {self.reason}"


@dataclass
class CheckReport:
    checker: str
    violations: list[Violation] = field(default_factory=list)
    scanned: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations

    def to_json(self) -> dict[str, Any]:
        return {
            "checker": self.checker,
            "passed": self.passed,
            "violation_count": len(self.violations),
            "scanned": self.scanned,
            "notes": self.notes,
            "violations": [asdict(v) for v in self.violations],
        }


def code_root_from_argv(default: str | None = None) -> Path:
    """CLI 取 `code_root`：显式位置参数优先，否则用本文件上两级。"""
    if default:
        return Path(default)
    return Path(__file__).resolve().parents[1]


def write_report(code_root: Path, report: CheckReport) -> Path:
    """把报告落 `reports/<checker>_<date>.json`（`Ch2 §B.4`：命中 → 写报告）。"""
    out_dir = code_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{report.checker}_{date.today().isoformat()}.json"
    out.write_text(json.dumps(report.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run_checker(
    name: str,
    fn: Callable[[Path], CheckReport],
    argv: Sequence[str] | None = None,
    *,
    dry_run: bool = False,
) -> int:
    """统一 CLI 包装：`--dry-run` 只打印不写报告。

    返回进程退出码（0 放行 / 1 阻断 / 2 输入异常）。
    """
    parser = argparse.ArgumentParser(prog=name, description=f"{name}（命中即 fail）")
    parser.add_argument("code_root", nargs="?", default=None, help="代码工程根（默认 system/）")
    parser.add_argument("--no-report", action="store_true", help="不写 reports/ 报告文件")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = code_root_from_argv(args.code_root)
    if not root.exists():
        print(f"[INPUT-ERROR] code_root 不存在: {root}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    try:
        report = fn(root)
    except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
        # ★ 不吞异常：输入异常明确报出并返回 2，绝不折叠成"通过"
        print(f"[INPUT-ERROR] {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    print(f"== {name} ==")
    for key, val in sorted(report.scanned.items()):
        print(f"  scanned {key}: {val}")
    for note in report.notes:
        print(f"  note: {note}")

    if report.passed:
        print(f"RESULT: PASS（0 violations）")
        if not args.no_report and not dry_run:
            write_report(root, report)
        return EXIT_OK

    for v in report.violations:
        print(f"  {v.render()}")
    print(f"RESULT: FAIL（{len(report.violations)} violations）")
    if not args.no_report and not dry_run:
        path = write_report(root, report)
        print(f"  report: {path}")
    return EXIT_VIOLATION


# ───────────────────────── 文件遍历 ─────────────────────────

def walk_files(root: Path, subdir: str = "", exts: tuple[str, ...] = (".py",)) -> list[Path]:
    """遍历 `root/subdir` 下指定扩展名的文件（字典序，保证可复现）。

    ★ **跳过点目录与缓存目录**（`.git` / `.venv` / `.work` / `__pycache__` …）：
      这些目录里没有源码，只有副本与缓存。若不跳，检查器会去扫**测试夹具的副本**
      与虚拟环境，制造大规模误报 —— 而误报的终点就是"门禁被关掉"。
      实测触发：夹具临时目录建在 `tests/.work/` 下，L2 会把它当成源码扫。
    """
    base = root / subdir if subdir else root
    if not base.exists():
        return []
    out = [
        p
        for p in base.rglob("*")
        if p.is_file()
        and p.suffix in exts
        and not any(part.startswith(".") or part == "__pycache__" for part in p.relative_to(base).parts)
    ]
    return sorted(out)


def rel(path: Path, root: Path) -> str:
    """把 `path` 表示成相对 `root` 的路径。

    ★ **参数顺序是 `(path, root)`**。写反了（`rel(root, p)`）时
      `path.relative_to(root)` 会抛 `ValueError`——初版这里 `return str(path)`
      静默兜底成绝对路径，导致 `_is_exempt()` 永远为 False、**免扫机制整体失效**
      （检查器开始扫自己的源码与 tests/），正是"误报刷屏 → 门禁被关掉"的引信。

    故此处**不再静默兜底**：不在 `root` 下 → 抛 `ValueError`（经 `run_checker`
    折叠为 `exit 2 输入异常`）。**程序写错必须响，不能变成一条安静的错路径。**
    """
    try:
        return str(path.relative_to(root))
    except ValueError as exc:
        raise ValueError(
            f"rel(path, root) 要求 path 位于 root 之下；实际 path={path} root={root}"
            "（若为 rel(root, p)，即参数顺序写反）"
        ) from exc


# ───────────────────────── 决策作用域判定（Ch2 §B.3 Checker-1） ─────────────────────────

# ── 配置读取缓存 ────────────────────────────────────────────────────────────
#
# ★ 为什么必须缓存（实测根因）：`matches_call_chain()` 与 `is_freeze_param_reader()`
#   每次调用都会经 `decision_scope_config()` → `load_banned_tokens()` →
#   **重新读取并 YAML 解析 `rules/banned_tokens.yaml`**。而这两个函数在 L2 里
#   是**按函数**调用的 —— 50 个文件 × 上百个函数 = 数千次重复解析，
#   `check_L2` 因此从"本该 0.1s"变成 4.5s~8.4s（实测）。
#
#   缓存键 = (路径, mtime_ns, size)：配置中途被改动会自动失效，
#   所以对"夹具里改配置再跑检查器"的注入测试也安全。
#
# ⚠️ 调用方**不得修改返回值**（返回的是同一个缓存对象）。当前所有调用点只读。
_CONFIG_CACHE: dict[tuple[str, int, int], Any] = {}


def _cached_yaml(path: Path) -> Any:
    import yaml

    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _CONFIG_CACHE:
        _CONFIG_CACHE.clear()                      # 只保留当前有效版本，防无限增长
        _CONFIG_CACHE[key] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _CONFIG_CACHE[key]


def load_banned_tokens(root: Path) -> dict[str, Any]:
    path = root / "rules" / "banned_tokens.yaml"
    if not path.exists():
        raise FileNotFoundError(f"缺少禁词表（全包唯一禁词源）: {path}")
    return _cached_yaml(path)


def decision_scope_config(root: Path) -> dict[str, Any]:
    cfg = load_banned_tokens(root).get("decision_scope") or {}
    return cfg


def exempt_namespaces(root: Path) -> list[str]:
    doc = load_banned_tokens(root)
    return list(doc.get("exempt_namespaces") or [])


def strip_system_prefix(pattern: str) -> str:
    """把 `system/scripts/decision/**` 这类 glob 模式收敛成**裸路径前缀** `scripts/decision`。

    ★ 必修的一步。初版写成 `p.replace("system/", "").rstrip("/")`，结果
      `key = "scripts/decision/**"`，`f"/{key}/" in normalized` **永远为假** ——
      `decision_scope.include_paths` 里的两条 `**` 路径**全部失效**，
      P-09 的 `decision_scope_only` 在 `scripts/decision/**` 与
      `scripts/graph/**` 上形同不存在（门禁恒绿，却什么也没拦）。
      实测暴露：注入 `scripts/decision/rank_candidates.py` 里的 `weight` 未被拦下。
    """
    text = pattern.replace("\\", "/")
    if text.startswith("system/"):
        text = text[len("system/"):]
    for marker in ("**", "*"):
        text = text.replace(marker, "")
    return text.strip("/")


def is_checker_namespace(relpath: str, root: Path) -> bool:
    """检查器命名空间免扫（`Ch2 §B.1 通则第 4 点`）。

    `system/scripts/checks/**` 与 `system/tests/**`：检查器自身的函数/变量名
    可能含禁词（如 `assert_no_composite_score`），朴素扫描会误报。
    """
    normalized = relpath.replace("\\", "/").lstrip("/")
    for pattern in exempt_namespaces(root):
        prefix = strip_system_prefix(pattern)
        if not prefix:
            continue
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    return False


def _call_names(node: ast.AST) -> Iterator[str]:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            fn = sub.func
            if isinstance(fn, ast.Name):
                yield fn.id
            elif isinstance(fn, ast.Attribute):
                yield fn.attr


def is_decision_scope_module(relpath: str, root: Path) -> bool:
    """模块是否整体位于决策作用域（`decision_scope.include_paths` / `include_modules`）。"""
    cfg = decision_scope_config(root)
    normalized = relpath.replace("\\", "/").lstrip("/")
    for pattern in cfg.get("include_paths") or []:
        prefix = strip_system_prefix(pattern)
        if not prefix:
            continue
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    stem = Path(relpath).stem
    return stem in set(cfg.get("include_modules") or [])


def matches_call_chain(fn_name: str, root: Path) -> bool:
    cfg = decision_scope_config(root)
    for pattern in cfg.get("include_call_chain") or []:
        if pattern.endswith("*") and fn_name.startswith(pattern[:-1]):
            return True
        if fn_name == pattern:
            return True
    return False


def is_freeze_param_reader(fn: ast.AST, root: Path) -> bool:
    """该函数是否为"仅读参数"的配置函数 —— 是则不属决策作用域（`Ch11 §E.1` 排除项）。"""
    if isinstance(fn, ast.FunctionDef) and matches_call_chain(fn.name, root):
        return False  # classify_* / assert_* 即使读参数也算决策作用域（调用链纳入优先）
    cfg = decision_scope_config(root)
    markers = set(cfg.get("exclude_markers") or [])
    names = set(_call_names(fn))
    # 直接引用 marker 名称
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Name) and sub.id in markers:
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in markers:
            return True
    return bool(names & markers)
