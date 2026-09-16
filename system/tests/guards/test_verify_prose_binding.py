"""`verify.py` 的**散文**不得自存第二份「分片事实」（`G-28` 同族，卡 13-N）。

## 为什么需要这条测试

`verify.py` 的**真源**本来就只有一个：`INJECTION_SHARDS`（片名单）。
但它的 **docstring 表**与**注释**里长期并存着同一事实的第二个存放处：

- 表里写着 `injection-a`…`injection-f`（**枚举上界**）与"**6 个分片**"；
- 各批注释里写着 `现为 a27 b28 c27 d29 e32 f29，合计 172`（旧分片数）；
- 常量新增 `injection-g` 之后，上述散文**一处都没跟上** ⇒ 同一文件里"6 片"与"7 项"并存。

这不是笔误，是 `G-28` 的机理：**同一事实两处写必然漂移**。
本项目已在同一机理上栽过四次（`PROGRESS.md §7.5 #1` → 卡 13-J → `CONVENTIONS` 批次表 → 本处），
**本处是第 4 次**，故本文件用**机器绑定**收口，而不是靠"下次注意"。

★ 判据刻意**从真源派生**（不写死片名、不写死片数）：片名集合 = `verify.py::INJECTION_SHARDS` 现读。
改片名 / 加片 ⇒ 本文件自动跟上；**若有人把散文改回去 ⇒ 本文件立刻变红**。

## 三条判据（都只作用于**散文**：模块 docstring + 注释）

| # | 退化 | 判据 |
|---|---|---|
| ① | 散文里出现**分片名单**（同一处 ≥2 个不同全名） | 现读片名逐个在散文里找；同一处命中 ≥2 个 = 违规 |
| ② | 散文里出现**片数 / 轮次**的数字写法 | 正则 `6 片` / `6片` / `6 个分片` / `六片` / `6 个轮次`；命中即违规 |
| ③ | 散文里出现**「片字母+用例数」**的旧分片数写法 | 由片名后缀现算字母集（`a`…`g`），匹配独立的 `<后缀><1~3 位数字>`（`a27` / `e32`）；命中即违规 |

★ ① 的阈值取"**≥2 个**"而不是"0 个"，理由是**单个**片名是**交叉引用**
（"由 `injection-d` 移入"这类注释是必要的），**2 个以上**才构成"名单/枚举"。
★ ② 把惯用语"**一片**"（"每次只跑一片"）**排除**在外：它说的是"一个片"，不是"片数"。
这条例外**刻意**保留，且不掩盖真实退化 —— `六片` / `6 片` / `6 个分片` 都仍然命中。
★ ③ 用**前后都不是 `[0-9A-Za-z_]`** 的边界，正是为了不误伤夹具目录名里的十六进制片段
（docstring 里就有 `…/test_L3_…-0a05b843`：`a05` 前面是 `0`，故**不**算）。

## 为什么判据不作用在代码上

`INJECTION_SHARDS` 与 `ORDER` 的**字面量**本来就要写出全部片名（那是真源本身）。
故本文件用 `ast` 取 docstring、用 `tokenize` 取 `COMMENT` token —— **只看散文，不看代码**。

## 为什么这条测试不用 `code_root` 夹具

它只读仓库里的一个文件，**零夹具副本 ⇒ 零宿主删除配额**（`P-05`）。
这一点是刻意的：卡 13-N 落地时 `injection-f` 已因用例数越限而红，
新守卫若落在 `tests/injection/` 会**继续抬高**该片用例数；落在 `tests/guards/`
则被既有的 `guards` 批（目录式目标）自然覆盖，`V-06` 与分片配额都**零影响**。
"""

from __future__ import annotations

import ast
import importlib.util
import io
import re
import sys
import tokenize
from pathlib import Path
from typing import Any

import pytest

from conftest import SYSTEM_ROOT

VERIFY_REL = "scripts/ops/verify.py"

# ② 散文里的「片数 / 轮次」写法。
#   - `\d+\s*个?\s*(?:分片|片)` 覆盖 `6 片` / `6片` / `6 个分片`；
#   - `[二三四五六七八九十两]\s*片` 覆盖 `六片` / `两片`（**排除"一"** —— "一片"是惯用语）；
#   - `\d+\s*个\s*轮次` 覆盖 `6 个轮次`。
# ★ 不写"应等于几片"：**任何**片数写法都是第二存放处，一律不该出现（卡 13-N 的口径）。
SHARD_COUNT_RX = re.compile(
    r"\d+\s*个?\s*(?:分片|片)"
    r"|(?:[二三四五六七八九十两])\s*片"
    r"|\d+\s*个\s*轮次"
)


def _load_verify() -> Any:
    """按**文件路径**加载本仓库的 `verify.py`（与 `test_shard_coverage.py::_load_verify` 同一手法）。

    ★ 用 `spec_from_file_location` 而非 `import scripts.ops.verify`：`verify.py` 只依赖 stdlib，
      按路径加载零全局副作用，且**确保看的是本仓库这一份**（不是解释器里可能存在的同名模块）。
    """
    path = SYSTEM_ROOT / VERIFY_REL
    assert path.exists(), f"缺少验证器: {path}"
    name = "_verify_under_prose_binding_check"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"无法加载 {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def _prose(source: str) -> tuple[str, list[tuple[int, str]]]:
    """把源码切成**散文**两部分：模块 docstring + 注释（`行号, 文本`）。

    ★ 只看散文、**不看代码** —— `INJECTION_SHARDS` / `ORDER` 的字面量本来就要写出全部片名。
    """
    doc = ast.get_docstring(ast.parse(source)) or ""
    comments: list[tuple[int, str]] = [
        (tok.start[0], tok.string)
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT
    ]
    return doc, comments


def _shard_size_rx(shards: tuple[str, ...]) -> re.Pattern[str]:
    """③ 的判据，**字母集从片名后缀现算**（不写死 `a`…`g`）。

    `injection-g` ⇒ 后缀 `g` ⇒ 匹配独立的 `g<1~3 位数字>`（`g18`）。
    后缀**按长度倒序**拼进正则，保证多字符后缀（若将来改名）不会被短后缀截断。
    """
    suffixes = sorted({s.rsplit("-", 1)[-1] for s in shards}, key=len, reverse=True)
    assert suffixes, "片名为空 —— 分片真源失效，本判据随后的一切都无意义"
    body = "|".join(re.escape(s) for s in suffixes)
    return re.compile(rf"(?<![0-9A-Za-z_])(?:{body})\d{{1,3}}(?![0-9A-Za-z_])")


def _violations(doc: str, comments: list[tuple[int, str]], shards: tuple[str, ...]) -> list[str]:
    """**纯函数**：给定"散文"与"片名真源"，返回违规清单（空 = 合格）。

    ★ 做成纯函数是为了让反向对照能**在进程内**注入一段坏散文再跑一次 ——
      不必改仓库文件、不必复制夹具（`P-05`），因此反向对照**零成本**且**必然可复现**。
    """
    out: list[str] = []
    size_rx = _shard_size_rx(shards)
    units = [("docstring", doc)] + [(f"注释 :{ln}", text) for ln, text in comments]

    for where, text in units:
        listed = sorted({s for s in shards if s in text})
        if len(listed) >= 2:
            out.append(f"①{where}：出现了分片名单 {listed}（片名单的真源只有 `INJECTION_SHARDS`）")
        for match in SHARD_COUNT_RX.finditer(text):
            out.append(f"②{where}：出现了片数写法 {match.group(0)!r}")
        for match in size_rx.finditer(text):
            out.append(f"③{where}：出现了旧分片数写法 {match.group(0)!r}")
    return out


def _real_violations() -> list[str]:
    source = (SYSTEM_ROOT / VERIFY_REL).read_text(encoding="utf-8")
    shards = tuple(_load_verify().INJECTION_SHARDS)
    doc, comments = _prose(source)
    return _violations(doc, comments, shards)


def test_verify_prose_has_no_shard_list_or_shard_count() -> None:
    """**正向**：`verify.py` 的 docstring 与注释里，既无分片名单、也无片数/旧分片数写法。

    这是一条**反漂移**断言：散文里的片数/枚举每新增一次就漂移一次
    （本项目已复发 4 次）。要写片数/名单，去改 `INJECTION_SHARDS`，不要改散文。
    """
    violations = _real_violations()
    assert not violations, (
        "`verify.py` 的散文里出现了「分片事实」的第二个存放处：\n  "
        + "\n  ".join(violations)
        + "\n→ 处置：**删掉**（能删就删）或改为引用真源（`INJECTION_SHARDS` / 现算命令）；"
        "\n  不要把数字改对 —— 改对了仍然会再漂移一次（`G-28`）。"
    )


def test_guard_is_not_vacuous_on_pristine_source() -> None:
    """**基线**：真文件必须**零违规**。

    ★ 没有这一条，上面那条断言就可能是"恒非空"的空实现
      （`G-05`：声称必须有反例把守）。
    """
    assert _real_violations() == [], "基线坏了：真文件竟然违规 —— 后面的反向对照失去意义"


@pytest.mark.parametrize(
    "bad_prose",
    [
        "分片：`injection-a`…`injection-f`",              # ① 枚举上界（同一处 2 个片名）
        "tests/injection/ 的 **6 个分片**",                # ② 阿拉伯片数
        "必须切成 6 片（门禁曾被静默关掉）",                  # ② 阿拉伯片数
        "`--batch all` 会把六片连着跑完",                   # ② 中文片数
        "完整覆盖该目录现在需要 6 个轮次",                    # ② 轮次
        "现为 a27 b28 c27 d29 e32 f29，合计 172",          # ③ 旧分片数
        "最大余量只有 5 例（现为 a27 b28 c27 d29）",          # ③ 旧分片数（夹在别的数字里）
    ],
)
def test_guard_fires_on_injected_prose(bad_prose: str) -> None:
    """**反向对照**：把卡 13-N 删掉的那些散文**逐条**注入 ⇒ 守卫必须变红。

    ★ 参数化到"每一条真实出现过的写法"而不是只测一条：这样**任何一条判据被改窄**
      （例如把 `[二三四五六七八九十两]` 里的"六"删掉、或把 ③ 的后缀集写死成空）
      都会被抓到 —— 与 `test_exit_code_contract.py` 那条"防覆盖被静默收窄"的元测试同一立意。
    ★ 片名用**真源现读**（不是本地写一份小元组）：否则 ① 会因为"注入的散文里的片名
      不在我这份小元组里"而**放过**，反向对照就成了假的。
    """
    shards = tuple(_load_verify().INJECTION_SHARDS)
    violations = _violations(bad_prose, [], shards)
    assert violations, f"注入的坏散文 {bad_prose!r} **未被**守卫抓到（判据被改窄或失效）"


def test_guard_ignores_single_shard_reference_and_idiom() -> None:
    """**反向的反向**：单个数量的片名引用、惯用语「一片」、十六进制片段**不得**被误报。

    三者都是真文件里**正当**的写法。没有这一条，守卫可能被"改宽"
    （例如把 ① 的阈值改成 ≥1 个片名）而没人发现 —— 那会把正当注释逼成无法书写的状态，
    最终结果是**门禁被关掉**（`G-01`）。
    """
    shards = tuple(_load_verify().INJECTION_SHARDS)
    for ok_prose in (
        "★ 每次**只跑一片**：同一轮里连跑多片会重新越过配额",              # ② 的"一片"例外
        "`test_time_contract.py`   # ← 由 `injection-d` 移入",          # ① 单个片名 = 交叉引用
        "同一片 `injection-a` 在**工作树**里跑成 80.92s",                # ① 单个片名
        '{"count":102044,"targets":["…/tests/.work/test_L3_…-0a05b843"]}',  # ③ 十六进制片段
        "阈值 99999 时 ≈360 例/轮，阈值 9999 时 ≈36 例/轮",               # ② 数字后面是"例"，不是"片"
    ):
        assert _violations(ok_prose, [], shards) == [], (
            f"误报了正当散文 {ok_prose!r} —— 守卫过宽会把注释逼到无法书写，进而被关掉"
        )
