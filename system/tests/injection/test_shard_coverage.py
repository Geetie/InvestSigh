"""分片绑定：`tests/injection/` 的**穷尽 · 不重 · 不超量**（`CONVENTIONS.md::V-02`）。

## 为什么需要这条测试

`tests/injection` 原先是一个批次（`_pytest("tests/injection")`）。
★ 当时是 **165 个用例** —— **这是历史观测值，不是当前真源**：目录用例数每加一条用例就变，
**现值一律现算**（`test_shard_case_counts_within_quota` 的 `--collect-only` 输出），本文件不写死任何用例数。
夹具是**每用例复制一份 `system/`**（`conftest.py::code_root`，完整夹具实测每份
**`COPIED_ITEMS_PER_CASE` 项** —— 真源是该常量，不在此处重抄），
且**每个用例用完即删**。宿主对**单轮（turn）**的删除操作有**累积配额**，
耗尽后**连单个用例目录都被拒删**，之后所有夹具 setup 直接报 `E`
—— **看起来像"测试坏了"**，实际是这一整批被**静默关掉**。

★ 本单**实测复现**（`reports/ws_verify_shard_report.md §2.3`，跑旧的全目录目标）：

```
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
  {"count":102044,"threshold":99999,"scope":"turn",
   "targets":["…/tests/.work/test_L3_inject_banned_config_key_is_rejected-0a05b843"],"targetCount":1}
```

被拒之后 78 个**建夹具**的用例集体 `E`，而**不建夹具**的用例照常通过
（本文件正是"不建夹具"的那些 —— ★ 那一轮 4 passed，**4 是当时的条数**，本文件现有多少条
**不在此处写死**，现算见 `--collect-only`）——
**这一对照证明那些 `E` 不是代码缺陷**。

修法 = 按**显式文件路径**分片（`R-06 ①` 禁止 `-k` / 关键词 / 名单式判据）。

分片一旦落地，就出现下面几类**会静默复发配额问题、静默漏测、或把"归因"洗成"放行"**的退化，
本文件用 **6 条断言**把它们逐个钉死：

| # | 退化 | 后果 | 对应断言 |
|---|---|---|---|
| ① | 新增注入测试文件，却没人把它放进任何片 | 该文件**永远不被跑**（"没跑"与"跑过且没问题"长得一样） | `test_every_injection_test_file_is_covered_by_shards` |
| ② | 同一文件被两片**重复收录** | 夹具副本数按片累加 ⇒ 删除量**直接翻倍** ⇒ 配额问题复发 | `test_shard_targets_are_pairwise_disjoint` |
| ③ | 某片用例数越过配额折算上限 | 该片单轮跑不完 ⇒ 又是一次"门禁被静默关掉" | `test_shard_case_counts_within_quota` |

另有一条**判据形态**断言：片目标必须是 `tests/injection/` 下的**显式测试文件路径**
（目录式目标会一次拉起整个目录 = 配额问题的成因；`-k` 式分片违反 `R-06 ①`）：

| # | 退化 | 对应断言 |
|---|---|---|
| ④ | 片目标写成目录 / 用 `-k` 关键词 | `test_shard_targets_are_explicit_test_file_paths` |

最后两条管的是**「归因」分支本身不得被改成放行**（`verify.py::_exit_zero` 里"配额"与
"解释器缺 pytest"两条分支都**只做归因**）：

| # | 退化 | 后果 | 对应断言 |
|---|---|---|---|
| ⑤ | 有人把"配额耗尽"改成 `return True`（"只是配额，不算失败"） | 被宿主关掉的批次会**以 `exit=0` 出现在报告里** —— 比"看起来像测试坏了"的红危险得多 | `test_quota_attribution_never_passes` |
| ⑥ | 有人把"解释器缺 pytest"洗成通过 | 0.1s 全红被静默吞掉，人不会去换解释器 | `test_missing_pytest_attribution_never_passes` |

★ ⑤⑥ 的立意与 `G-05`（**每条判据必须有反向对照**）一致：**"只做归因、绝不放行"是一句
声称**，没有断言把守就只是一句话。两条断言都带**基线**（`exit=0` 仍必须判合格），
否则"永远返回不合格"的空实现也能过。

## 判据真源 = `verify.py`（本文件**不写死**文件清单或用例数字）

`INJECTION_SHARDS`（片名单）· `BATCHES`（各片目标）直接从 `verify.py` **按文件路径加载**现读。
写死了就是同一事实的第二个存放处，必然漂移 —— 本项目曾在批次描述里
先后出现过 18/19/20/23 四个"门禁项数"，正是这个机理。

## 为什么收集计数带 `--noconftest`

本文件是**测试里的测试**：它在运行中的 pytest 会话内**再起一个 pytest 子进程**做
`--collect-only`。若照常加载 `tests/conftest.py`，子进程的 `pytest_sessionstart`
会执行 `_clear_work_dir()` —— **把外层会话正在用的 `tests/.work/` 删掉**
（`V-05` 的姊妹问题：两个会话互删夹具）。故用 `--noconftest` 关掉 conftest 的**插件**加载，
再用 `PYTHONPATH=<system>/tests` 让测试模块的 `from conftest import ...` 仍能解析
（pytest 的 `prepend` 模式对无 `__init__.py` 的目录本来就这么解析，这里只是显式补上）。

★ **收集结果不受影响**：`tests/conftest.py` 里**没有** `pytest_generate_tests` /
`pytest_collection_modifyitems` 之类参与**收集**的钩子（只有 `pytest_sessionstart` /
`pytest_sessionfinish` 与 fixture 定义），故"关掉 conftest"只去掉会话钩子、不去掉任何用例。
实测对照（两种跑法得出**相同**数字，逐条读数见 `reports/ws_verify_shard_report.md`）：
`test_stage_gate.py + test_wiring_guards.py` 与 `test_guards_reject_{a,b}.py` 都各自一致。
（★ 具体条数**不在此处重抄**：它会随用例增长而漂移；现值现算 —— 见
`test_shard_case_counts_within_quota` 的输出。）
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from conftest import SYSTEM_ROOT

VERIFY_REL = "scripts/ops/verify.py"

# ── 用例数上限：**授权上限**，其原始推导已被实测证伪（见下）────────────────────
#
# ★★ 读本段前必读（与 `verify.py` 散文同一口径，卡 13-N / #89）：
#   **本段出现的数字全部是"某次实测的读数"或"某条已被推翻的推导的原文"（= 留档）**，
#   它们**不是"当前事实的真源"**。凡描述**当前**状态的量，一律**现算或取常量**：
#     用例数 = 现跑 `--collect-only`（`test_shard_case_counts_within_quota`）·
#     夹具项数 = `COPIED_ITEMS_PER_CASE` · 每片上限 = `MAX_CASES_PER_SHARD` ·
#     片名单/各片归属 = `verify.py::INJECTION_SHARDS` / `BATCHES`。
#   ⇒ **别把留档里的数字当现值去改代码**；也别在别处再抄一份（`G-28`）。
#
# ★★ 诚实的口径（本单实测，2026-09-16）：
#
# 原始推导（主理人任务书）：「夹具副本 271 项 × 用例数 ≤ 宿主单轮配额 9999 ⇒ 上限 32」。
# ★ 这是**引用原文**，故其中数字原样保留 —— 注意 **271 与真源 `COPIED_ITEMS_PER_CASE` 并不相等**，
#   而这本身就是该推导被推翻的一环（计数单位不是"夹具项数"）。
# **该推导不成立**，两个前提都被实测推翻：
#
#   ① **计数的单位不是"夹具项数"**：本单同轮累计到 `count: 102044` 时被拒，
#      而同轮实际只跑了 ≈130 个建夹具的用例 ⇒ **≈792 计数/例 ≈ 2.9 × 273**。
#      （被拒的 `targets` 是**单个**用例目录、`targetCount: 1` —— 即"累计计数"而非"单次批量大小"。）
#   ② **阈值不是固定常量**：主理人观测到 `threshold: 9999`，本单观测到 `threshold: 99999`
#      （当前宿主环境变量 `CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD=99999`）。
#
#   故 `32 × 271 = 8672 < 9999` 这句**不能**用来论证 32 是安全的：
#     按 9999 阈值 + 792 计数/例 ⇒ 安全上限只有 ≈**12 例**
#     （即完整覆盖 `tests/injection` 需 ≈**14 片** / **14 个轮次**）；
#     按本机当前的 99999 阈值 ⇒ 安全上限 ≈**126 例**。
#   （以上都是**条件推导**：结论只在"阈值 = 9999"这个前提成立时成立，见下。）
#
#   ★★ 保留 32 的**定位 = 「实测可跑的当前配置」，不是「已证明安全」**：
#   它成立的**前提是阈值处于观测到的较高值（99999）**。
#   保留它的理由：① 32 是主理人在分片任务书里给的**授权上限**
#   （**片数是主理人决策**，本文件不擅自改）；
#   ② 它**有工作树实测支持** —— 各片都能单轮 `exit=0` 跑完（含当时最接近上限的那一片）。
#   ★ 当时**逐片的条数与"哪一片最接近上限"不在此处写死**：它们随用例增长而变，
#   现值现算（见 `test_shard_case_counts_within_quota` 的输出）。
#   ★ **若宿主阈值回落到 9999，当前分片立刻不成立**（按 `9999 ÷ 792 ≈ 12 例/片` 折算，
#   需要 ≈14 片 —— 当前的**片数与各片用例数**请现算，本段不抄）：
#   请按该折算重排，并把 `verify.py::INJECTION_SHARDS` 扩到 ≈14 片。
#   —— 但**不要为了"更安全"就先去改 14 片**：14 轮没人会跑，那等于把门禁关掉
#   （`CONVENTIONS.md` 铁律：「卡死的门禁 = 被关掉的门禁」）。**改片数要主理人定。**
HOST_TURN_DELETE_QUOTA = 9999   # ★ 观测到的**较低**取值（另有 99999）；仅用于文案，判据不依赖它
COPIED_ITEMS_PER_CASE = 273     # ★ 夹具项数的**真源**：散文里要引用就引用本名，不要抄 273
MAX_CASES_PER_SHARD = 32
COLLECT_TIMEOUT_S = 120.0


def _load_verify() -> Any:
    """按**文件路径**加载本仓库的 `verify.py` —— `V-02` 判据的**唯一真源**。

    ★ 用 `spec_from_file_location` 而非 `import scripts.ops.verify`：与
      `verification_policy_guard._load_verify()` 同一手法（`verify.py` 只依赖 stdlib，
      按路径加载零全局副作用），且**确保看的是本仓库这一份**。
    """
    path = SYSTEM_ROOT / VERIFY_REL
    assert path.exists(), f"缺少验证器: {path}"
    name = "_verify_under_shard_binding_check"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"无法加载 {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def _pytest_file_targets(batch: Any) -> tuple[str, ...]:
    """从批次 argv 里抽 `-m pytest <targets...> -q ...` 的 targets（与守卫同一手法）。"""
    argv = list(batch.argv)
    if "pytest" not in argv:
        return ()
    out: list[str] = []
    for item in argv[argv.index("pytest") + 1 :]:
        if item.startswith("-"):
            break
        out.append(item)
    return tuple(out)


def _shard_specs() -> dict[str, dict[str, Any]]:
    """各 injection 片的 `{名称: {targets, argv}}` —— 全部现读自 `verify.py`。"""
    module = _load_verify()
    names = tuple(getattr(module, "INJECTION_SHARDS", ()))
    batches = dict(getattr(module, "BATCHES", {}))
    order = tuple(getattr(module, "ORDER", ()))

    assert names, (
        "`verify.py::INJECTION_SHARDS` 为空 —— 注入测试没有任何分片，"
        "等于这一整批被关掉了（`CONVENTIONS.md::V-02`）"
    )
    missing = [n for n in names if n not in batches]
    assert not missing, f"INJECTION_SHARDS 里的名字不在 BATCHES 中: {missing}"
    misplaced = [n for n in names if n not in order]
    assert not misplaced, (
        f"INJECTION_SHARDS 里的名字不在 ORDER 中（`--batch all` 会静默跳过它们）: {misplaced}"
    )
    return {
        name: {"targets": _pytest_file_targets(batches[name]), "argv": tuple(batches[name].argv)}
        for name in names
    }


def _injection_test_files() -> set[str]:
    """`tests/injection/` 下的**测试文件**（与 `verification_policy_guard::_test_files` 同一定义）。

    ★ 同一定义是刻意的：`V-06` 判"有没有被批次覆盖"用的是 `test_*.py`，
      本文件判"片有没有漏掉文件"必须用**同一把尺子**，否则两个判据会各说各话
      （例如 `_guard_common.py` 不匹配 `test_*.py`，本就不该、也不能作为片目标）。
    """
    root = SYSTEM_ROOT
    out: set[str] = set()
    for path in sorted((root / "tests" / "injection").rglob("test_*.py")):
        rel = path.relative_to(root)
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts):
            continue
        out.add(rel.as_posix())
    return out


def _collect_count(targets: tuple[str, ...]) -> int:
    """**现算**这组目标的用例数（`pytest --collect-only`，子进程）。

    ★ 见模块 docstring「为什么收集计数带 `--noconftest`」：避免子进程的
      `pytest_sessionstart` 把外层会话的 `tests/.work/` 删掉。
    ★ 子进程同样在 `V-04` 要求的 broker hook 关闭状态下跑。
    """
    argv = [
        sys.executable, "-m", "pytest", *targets,
        "--collect-only", "-q", "-p", "no:cacheprovider", "--noconftest",
    ]
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            p for p in (str(SYSTEM_ROOT / "tests"), os.environ.get("PYTHONPATH", "")) if p
        ),
        "CODEBUDDY_SAFE_DELETE_SANDBOX": "0",
        "CODEBUDDY_BROKERED_FS_HOOK_ENABLED": "0",
    }
    proc = subprocess.run(
        argv, cwd=str(SYSTEM_ROOT), capture_output=True, text=True,
        timeout=COLLECT_TIMEOUT_S, env=env,
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    # 5 = pytest 的 NO_TESTS_COLLECTED（"一个都没收集到"是**合法返回值**，
    #     不是环境错误 —— 它本身就是要被断言出来的退化，见下面 `empty` 那条）。
    assert proc.returncode in (0, 5), (
        f"收集失败（目标 {targets}，exit={proc.returncode}）—— 这是**环境/导入错误**，"
        f"不是用例数问题:\n{text}"
    )
    match = re.search(r"(\d+) tests? collected", text)
    if match:
        return int(match.group(1))
    if "no tests ran" in text or "no tests collected" in text:
        return 0
    counted = sum(1 for line in (proc.stdout or "").splitlines() if "::" in line)
    assert counted, f"无法从输出解析用例数（目标 {targets}）:\n{text}"
    return counted


# ═══════════ ④ 判据形态：片目标必须是显式测试文件路径 ═══════════

def test_shard_targets_are_explicit_test_file_paths() -> None:
    """片目标一律 `tests/injection/test_*.py` —— **不许目录、不许 `-k`**。

    - **目录式目标**会一次拉起整个目录的用例 ⇒ 夹具副本数 = 目录用例数 × `COPIED_ITEMS_PER_CASE`
      ⇒ 正是 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 的成因；
    - **`-k` / 关键词式分片**违反 `R-06 ①`（判据不可穷尽）：**新用例不会出现在任何名单里**，
      会静默落进 `not <关键词>` 分支，而"漏测"与"测过没问题"在报告里长得一样。
    """
    for name, spec in _shard_specs().items():
        assert spec["targets"], f"片 {name!r} 没有任何 pytest 目标"
        assert "-k" not in spec["argv"], (
            f"片 {name!r} 用了 `-k`（关键词式分片）—— 违反 `R-06 ①`："
            "判据不可穷尽，新用例会静默落到 not 分支里"
        )
        for target in spec["targets"]:
            assert target.startswith("tests/injection/") and target.endswith(".py"), (
                f"片 {name!r} 的目标 {target!r} 不是 `tests/injection/` 下的**文件路径**"
            )
            assert Path(target).name.startswith("test_"), (
                f"片 {name!r} 的目标 {target!r} 不是测试文件（名不匹配 `test_*.py`）"
                "—— pytest 会收集到 0 个用例而「通过」，是静默空跑"
            )


# ═══════════ ① 穷尽：文件集合 == 各片目标并集 ═══════════

def test_every_injection_test_file_is_covered_by_shards() -> None:
    """`tests/injection/test_*.py` 的集合 **恰好等于** 各片目标文件的并集。

    两个方向都查，各自对应一种真实退化：

    - **漏**（文件 ∉ 并集）：写了却**永远不被跑** —— `V-06` 的同类缺陷；
    - **多**（并集 ∉ 文件）：片目标指向不存在的文件 ⇒ pytest 收集到 0 个用例而"通过"，
      且会让人误以为该文件被覆盖了。
    """
    specs = _shard_specs()
    union = {t for spec in specs.values() for t in spec["targets"]}
    files = _injection_test_files()

    uncovered = sorted(files - union)
    assert not uncovered, (
        f"以下注入测试文件**不在任何片的目标里**（写了却永远不被验证）: {uncovered}\n"
        "→ 处置：把它们加进 `verify.py` 的某个 injection 片（该文件同时也是 `V-06` 的落点）"
    )
    phantom = sorted(union - files)
    assert not phantom, (
        f"以下片目标**指向不存在的测试文件**（该片会收集到 0 个用例而「通过」）: {phantom}\n"
        "→ 处置：修正 `verify.py` 里对应片的目标路径"
    )


# ═══════════ ② 不重：各片目标两两不相交 ═══════════

def test_shard_targets_are_pairwise_disjoint() -> None:
    """同一文件**不得**被两片重复收录 —— 重复收录 = 每轮删除量**翻倍** = 配额问题复发。"""
    owners: dict[str, list[str]] = {}
    for name, spec in _shard_specs().items():
        for target in spec["targets"]:
            owners.setdefault(target, []).append(name)
    duplicated = {t: ns for t, ns in owners.items() if len(ns) > 1}
    assert not duplicated, (
        f"以下文件被**多个片重复收录**（重复收录会按片累加夹具副本 ⇒ "
        f"单轮删除量直接翻倍 ⇒ `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 复发）: {duplicated}\n"
        "→ 处置：同一文件只留在**一个**片里"
    )


# ═══════════ ③ 不超量：每片用例数 ≤ 上限（现算） ═══════════

def test_shard_case_counts_within_quota() -> None:
    """每片用例数（`--collect-only` **现算**，非写死）必须 ≤ `MAX_CASES_PER_SHARD`。

    **不写死各片的用例数** —— 写了就是第二个存放处，加一条用例就会过期。
    上限的来历与它**已被实测证伪的原始推导**见 `MAX_CASES_PER_SHARD` 上方注释
    （简言之：它是**授权上限**，不是 `HOST_TURN_DELETE_QUOTA ÷ COPIED_ITEMS_PER_CASE` 算出来的）。
    """
    specs = _shard_specs()
    counts = {name: _collect_count(spec["targets"]) for name, spec in specs.items()}

    assert sum(counts.values()) > 0, "所有 injection 片合计收集到 0 个用例 —— 分片目标是空的"
    empty = sorted(n for n, c in counts.items() if c == 0)
    assert not empty, f"以下片一个用例都没收集到（目标写错了？）: {empty}"

    over = {n: c for n, c in counts.items() if c > MAX_CASES_PER_SHARD}
    assert not over, (
        f"以下片的用例数超过上限 {MAX_CASES_PER_SHARD}: {over}（现算值）\n"
        "→ 超限 ⇒ 该片单轮跑不完 ⇒ 又是一次「门禁被静默关掉」。\n"
        "处置（两种都可，**不必新增片**）：① 把一个文件**迁到有余量的片**"
        "（`#89` 的先例）；② 把该片再拆一片，并在 `verify.py::INJECTION_SHARDS` 登记。\n"
        "★★ 该上限是**授权上限**（片数由主理人定），**不是**由"
        f"「宿主配额 {HOST_TURN_DELETE_QUOTA} ÷ 每例 {COPIED_ITEMS_PER_CASE} 项」算出来的 ——"
        "那个推导已被实测证伪（计数单位实为 ≈792/例；阈值观测到 9999 与 99999 两种）。\n"
        "★★ 它的**前提是阈值处于观测到的较高值（99999）**；若阈值回落到 9999，"
        "安全上限降到 ≈12 例/片（⇒ 需 ≈14 片 / 14 个轮次）。详见本文件"
        "`MAX_CASES_PER_SHARD` 上方注释。"
    )


# ═══════════ ⑤ 归因分支**绝不放行**（`G-05`：声称"只会归因"必须有反例把守）═══════════

def test_quota_attribution_never_passes() -> None:
    """命中「宿主删除配额」标记的批次**必须仍判不合格** —— 归因**不是**放行。

    这一条不是形式主义：`_exit_zero` 里那条配额分支的**全部价值**就是"说清归因"，
    而它一旦被后来的人改成 `return True`（"只是配额，不算失败"），
    **配额问题立刻变成静默通道** —— 一个被宿主关掉的批次会以 `exit=0` 的姿态出现在报告里，
    比原来那个"看起来像测试坏了"的红**危险得多**（红的至少会被看见）。

    反向对照（把分支改成 `return True, …` 后本用例变红）：
    本文件实测记录见 `reports/ws_verify_shard_report.md §8.2/§8.8`。
    """
    module = _load_verify()
    verdict = module._exit_zero

    ok, why = verdict(0, "any output")            # 基线：**真通过**仍必须是通过
    assert ok is True, "基线坏了：exit=0 竟然不判合格 —— 本断言随后的一切都无意义"

    ok, why = verdict(
        3,
        '[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":116669,'
        '"threshold":99999,"scope":"turn","targets":["…/tests/.work/x"],"targetCount":1}',
    )
    assert ok is False, (
        "命中配额标记的批次被判**合格**了 —— 归因分支被改成了放行。"
        "这是本项目最危险的一类退化（门禁静默失效）；配额问题**必须**仍是不合格。"
    )
    assert "配额" in why, f"归因文案里应指明是配额问题，实际是: {why!r}"


def test_missing_pytest_attribution_never_passes() -> None:
    """「解释器里没有 pytest」也必须仍判**不合格** —— 且要说清是**环境**，不是测试。

    实测来历（本单，`verify.py` 用 `sys.executable` 派生子进程）：
    用裸 `python3` 跑 `verify.py` 会让**每一批**在 0.1~0.2s 内 `exit=1`，
    输出只有一行 `No module named pytest` —— 症状是"一秒钟全红"，极易被读成
    "分片方案坏了 / 测试坏了"。它既不是超时（`124`）也不是配额，
    故需要一个**独立的第三类归因**（`verify.py::PYTEST_MISSING_MARKER`）。

    同 `test_quota_attribution_never_passes`：**归因不是放行**。
    """
    module = _load_verify()
    ok, why = module._exit_zero(
        1, "/…/python3: No module named pytest\n"
    )
    assert ok is False, (
        "「解释器里没有 pytest」被判**合格**了 —— 环境错误绝不能洗成通过"
        "（换解释器同一批就是绿的，但那要人去做，不是让判据闭嘴）"
    )
    assert "环境" in why and "pytest" in why, (
        f"归因文案应同时指明是「环境」问题与「pytest」缺失，实际是: {why!r}"
    )
