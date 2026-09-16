#!/usr/bin/env python3
"""`verify.py` —— **分批验证器**（**禁止一条命令全量验证**）。

> 用户的硬要求：**「以后不许一条命令全量验证。必须分批验证，每批还要设定适合的超时时间。」
> 且「若有超时，说明这批验证有问题，极大概率还是测试本身的问题」。**

```
python system/scripts/ops/verify.py --list                 # 看有哪些批次与超时
python system/scripts/ops/verify.py --batch injection-a    # 只跑一批（推荐用法）
python system/scripts/ops/verify.py --batch all            # 逐批跑，每批独立超时，超时即停
```

## 为什么必须分批（上一版的真实故障）

旧版把 `pytest tests`（全量） + 19 项门禁 + 阶段判据塞进**一条命令、一个超时**。
后果：任一处卡住 → **整条命令无任何输出**、退出码只有 `137`（SIGTERM），
既看不出卡在哪一批，也拿不到任何证据。

分批之后：**卡住的那一批会自己超时并报出批次名**；其余批次照常跑完。
超时＝**该批有问题**（极大概率是测试本身），不是"跑得慢"。

## 批次设计（每批一个独立子进程 + 独立超时）

| 批次 | 内容 |
|---|---|
| `unit`       | `tests/unit/`（契约 + 作用域匹配器） |
| `conflict`   | `tests/conflict/`（P-03/P-05/P-07 schema 断言） |
| `guards`     | `tests/guards/`（门禁退出码契约 + 验证规范） |
| `injection-*`（**片名单不在本表重复**） | `tests/injection/` 的分片（每片一组显式文件路径） |
| `root`       | `tests/test_ch11_invariants.py` |
| `gates`      | `run_all_gates.py`（全部门禁逐项退出码） |
| `stage`      | `stage_gate.py --stage all`（阶段判据 + 退出码自洽） |

★ **超时值不在本表重复** —— 唯一真源是下面的 `BATCHES`（每批一个 `Batch.timeout`）。
  本表原先带一列"超时"，**已实测漂移**（`unit` 那行写着 `60s`，真值早不是它；分片那行写 `6 个`
  而常量早已新增片；且整张表漏了 `compute`/`claim`/`decision`/`transmit`/`evidence`/`daily`/
  `pricelayer`/`valuelayer` 八批）—— 同一事实两处写必然漂移，与 `guards` 那段
  "不在描述里重复真源"是同一课（卡 13-F 发现并删除该列）。
  查真值：`python -c "from scripts.ops.verify import BATCHES; print({n: b.timeout for n, b in BATCHES.items()})"`。

★ **注入分片的"名单/枚举上界"与"片数"同样不在本表重复** —— 真源是下面的 `INJECTION_SHARDS`。
  本表原先逐字写出分片的**枚举上界**与"片数"，而常量后来新增了片 ⇒ **两处同时漂移**
  （这类改动每发生一次就漂移一次，卡 13-N 已整处删除）。查真值：
  `python -c "from scripts.ops.verify import INJECTION_SHARDS; print(len(INJECTION_SHARDS), INJECTION_SHARDS)"`。

超时值的**判据**见 `CONVENTIONS.md::V-02`（现行判据：`0 < timeout <= 300s`，且余量要能区分
"慢"与"卡死"——慢批次 4~8× 即可；倍数在慢批次上会撞 300s 上限，此时取不超过上限的最大值）。

## ★ 为什么 `tests/injection/` 必须分片（**门禁曾被静默关掉**）

实测（细节与原始输出见 `reports/ws_verify_shard_report.md §2`；规范见 `CONVENTIONS.md::V-08`）：

- 夹具是**每用例复制一份 `system/`**（`conftest.py::code_root`，实测每份 **271 项**），**用完即删**；
- 宿主对**单轮（turn）**的删除操作有**累积配额**，耗尽后**连单个用例目录都被拒删**
  → 此后所有夹具 setup 直接报 `E` —— **看起来完全像"测试坏了"**。

★ 本单**实测复现**（跑旧的全目录目标 `tests/injection`，169 例 / 290s）：

```
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
  {"count":102044,"threshold":99999,"scope":"turn","targetCount":1, "targets":["…/tests/.work/test_L3_…-0a05b843"]}
```

被拒之后 **78 个"建夹具"的用例集体 `E`**，而**不建夹具**的用例照常通过
（`tests/injection/test_shard_coverage.py` 4 passed）——
**这个对照本身就是"那些 E 不是代码缺陷"的判据**。

★ 两条**实测修正**（原任务书的量化依据在这两点上不成立，故此处不重复它的算术）：

| 项 | 原依据 | 实测 |
|---|---|---|
| 计数单位 | "夹具项数"（271/例） | **≈785 计数/例**（≈2.9 × 271）—— 102,044 计数 ≈ 130 个建夹具用例 |
| 阈值 | 固定 `9999` | **两次观测不同**：主理人 `9999`、本单 `99999` |

⇒ 故 `32 × 271 = 8,672 < 9,999` **不能**用来论证"32 例是安全的"。
片大小的**上限值不在本文件重复**（`G-28`：同一事实两处写必然漂移）——
真源 = `tests/injection/test_shard_coverage.py::MAX_CASES_PER_SHARD`：
① 它是主理人的**授权上限**；② 有**实测支持**（用例数接近该上限的片，在本机当前阈值下单轮跑完、`exit=0`）。
**若宿主阈值回落到 9999**，按 `9999 ÷ 785 ≈ 12` 例/片重排 —— 判据落点在 `MAX_CASES_PER_SHARD` 上方注释。

修法**只能**是分片（**不靠缩小夹具副本**，理由见下）。

★ 三条**不可放宽**的做法约束：

1. **不靠"缩小夹具副本"省配额** —— 有些守卫**就是扫副本**的
   （`conflict_scan` 的 L2 扫 `code_root/scripts/**`；`verification_policy_guard` 扫
   `code_root/tests/**`）。把 `scripts/` / `tests/` 从 `_COPY_SKIP` / 副本里去掉，会让它们
   **扫到 0 个文件而"通过"** —— 那是比配额严重得多的"守卫静默失效"；
2. **不用 `-k` / 关键词式分片**（`R-06 ①` 禁关键词/名单式判据：**新用例会静默落进
   `not` 分支**，而"漏测"与"测过没问题"在报告里长得一样）；
3. 片目标一律**显式文件路径**（目录式目标会一次拉起整个目录的用例
   ⇒ 配额问题原样复发）。

★ 三条都有**机器绑定**：`tests/injection/test_shard_coverage.py`
（穷尽性 · 两两不相交 · 每片用例数 `--collect-only` 现算 ≤ 32 · 目标必须是显式测试文件路径）。

★ **代价（如实写明）**：完整覆盖 `tests/injection` 现在需要**逐片各跑一个轮次**
（片数 = `INJECTION_SHARDS` 的长度，**不在此处重复**）。
这是**宿主单轮删除配额决定的，不是设计选择** —— 同一轮里连跑多片会重新耗尽配额，
表现为"某片在几秒内突然红 + 一堆 `E`"（`scope: "turn"`）。
`--batch all` 会把所有分片连着跑完，因此它**不能**用来做 `tests/injection` 的完整覆盖。

## 退出码
`0` 该批通过 / `1` 该批不合格（含超时）/ `2` 环境异常（批次名非法等）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]          # .../system
KEEP_LOGS = 3

Verdict = Callable[[int, str], tuple[bool, str]]

# 宿主**单轮删除配额**耗尽时打进子进程输出的标记（`CONVENTIONS.md::V-08`，本单实测原文见
# `reports/ws_verify_shard_report.md §2.3`）：
#   [safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":102044,"threshold":99999,
#     "scope":"turn","targets":[…/tests/.work/test_L3_…-0a05b843],"targetCount":1}
# ★ 它的用途**只是归因**（把"配额耗尽"与"测试真的坏了"分开），**不是放行** ——
#   命中它的批次仍然判**不合格**。只因它的症状（一批夹具 setup 集体报 `E`、进程像坏掉）
#   与"测试坏了"**长得一模一样**，而本项目最怕的正是"把配额问题误当成代码缺陷去改断言"。
QUOTA_MARKER = "SAFE_DELETE_BULK_CONFIRM_REQUIRED"

# 第三类**环境性假红**（本单实测；与「超时」「配额」都不同类，症状也完全不同）：
# `verify.py` 用 `sys.executable` 派生子进程（见 `_run` 的 `argv = [sys.executable] + …`），
# 所以用**没有装 pytest 的解释器**跑它，每一批都在 0.2s 内 `exit=1`，输出只有一行：
#
#   $ python3 system/scripts/ops/verify.py --batch injection-d
#   ✗ [injection-d] tests/injection/ 分片 D（…）  exit=1  0.16s/300s  exit=1
#   /…/python3: No module named pytest
#
# ★ 与 `QUOTA_MARKER` 同样**只做归因，不做放行**（命中即判不合格）。
#   要分开它的原因：0.16s 就全红的批次**极容易被读成"分片方案坏了 / 测试坏了"**，
#   而真正要换的只是解释器（`run_pytest.sh` / `pre-commit.sh` 里的 `WORKBUDDY_PY`，
#   或 `system/.venv`）—— 换个解释器同一批就是绿的。
PYTEST_MISSING_MARKER = "No module named pytest"


@dataclass(frozen=True)
class Batch:
    name: str
    label: str
    argv: tuple[str, ...]           # 追加到 [sys.executable] 之后
    timeout: float
    verdict: Verdict
    note: str = ""


def _exit_zero(code: int, out: str) -> tuple[bool, str]:
    if code == 0:
        return True, "exit=0"
    if code == 124:
        return False, "**超时** —— 该批有问题（极大概率是测试本身）"
    if QUOTA_MARKER in out:
        # ★ 仍然是**不合格**（绝不放行）；这里做的只是**把归因说准**。
        return False, (
            "**宿主单轮删除配额耗尽**（`scope: \"turn\"`）—— "
            "**这多半不是测试失败**：配额用尽后夹具 setup 会集体报 `E`，"
            "看起来和「测试坏了」一模一样（本单实测：78 个建夹具的用例集体 `E`，"
            "而同一批里**不建夹具**的用例照常通过）。"
            "处置：**新开一轮**、只跑本片（配额按轮重置）；"
            "**不要**去改断言 —— 详见 `CONVENTIONS.md::V-08`。"
        )
    if PYTEST_MISSING_MARKER in out:
        # ★ 仍然**不合格**，只是把归因说准（见 `PYTEST_MISSING_MARKER` 上方注释）。
        return False, (
            "**环境错误：当前解释器里没有 pytest** —— 这既不是测试失败、也不是配额。"
            "`verify.py` 用 `sys.executable` 跑子进程，故要用装了 pytest 的解释器跑它"
            "（实测用裸 `python3` 会 0.16s 全红）。处置：换解释器，**不要**改断言。"
        )
    return False, f"exit={code}"


def _stage_gate_verdict(code: int, out: str) -> tuple[bool, str]:
    """`stage_gate --stage all` 的设计预期 —— **不硬编码"哪个阶段该阻塞"**。

    ## ★ 为什么必须改成数据驱动（实测教训，批次 11）

    原实现把 `("nvidia_sample", "core_chain", "daily_run", "expansion")` **写死在期望里**，
    要求这四者**都** `BLOCKED`。批次 11 修实 `stage_gate` 的首日豁免后，阶段④ 由
    `BLOCKED` 转 **`PASS`** ⇒ 这条判据立刻变成**假红**（`main` 上同样红，与本改动无关）。
    而"哪些阶段已通过"是**随进度变化的事实** —— 把它写进判据里**必然过期**。
    这跟本文件对 `guards` / `gates` 的描述**刻意不写条数**是同一个道理：
    **同一事实不要有第二个存放处。**

    ## 新判据（可判定 + 穷尽，`R-06`）

    1. **五阶段必须逐个显式出现**，且取值为 `PASS` / `BLOCKED` 之一 ——
       ★ 这一条才是真的在防"静默跳过"（原实现只查了四个阶段的 `BLOCKED` 字样，
       压根没查"是否五个都出现了"）；
    2. 阶段① 必须 `PASS`（它是整条链的进入条件）；
    3. **退出码必须与阶段取值自洽，且两个方向都查**：
       有任一 `BLOCKED` ⇒ 退出码非零（不放过"阻塞却报成功"）；
       全部 `PASS` ⇒ 退出码为 0（也不放过"全通过却仍报阻塞"这一反向错误）。
    """
    if code == 124:
        return False, "**超时** —— 该批有问题（极大概率是测试本身）"

    stages = ("prep", "nvidia_sample", "core_chain", "daily_run", "expansion")
    seen: dict[str, str] = {}
    for stage in stages:
        has_pass = f"{stage}: PASS" in out
        has_blocked = f"{stage}: BLOCKED" in out
        # ★ 两者**同时**出现 = 输出不自洽，**必须响亮失败**（缺口 `G-47`，独立审计发现）：
        #   原实现用 `if/elif` ⇒ 同时出现时**静默取 PASS**，而"取 PASS"恰好是最危险的那一侧
        #   （把阻塞读成通过）。判据要么可判定，要么报错，**不得**在歧义时默默选一个。
        if has_pass and has_blocked:
            return False, (
                f"阶段 {stage} 的输出里**同时**出现 `{stage}: PASS` 与 `{stage}: BLOCKED` —— "
                "判据不自洽，无法据以判定（**不得静默取其一**，尤其不得取 PASS）"
            )
        if has_pass:
            seen[stage] = "PASS"
        elif has_blocked:
            seen[stage] = "BLOCKED"
    absent = [s for s in stages if s not in seen]
    if absent:
        return False, f"以下阶段既未标 PASS 也未标 BLOCKED（可能静默跳过）：{absent}"
    if seen["prep"] != "PASS":
        return False, f"阶段① 未 PASS（进入条件不成立）—— 实得 {seen['prep']}"

    blocked = [s for s in stages if seen[s] == "BLOCKED"]
    if blocked and code == 0:
        return False, f"存在阻塞阶段 {blocked} 却 exit=0 —— 疑似把阻塞阶段判成通过"
    if not blocked and code != 0:
        return False, f"五阶段全部 PASS 却 exit={code} —— 疑似把通过判成阻塞"
    if blocked:
        return True, f"阶段① PASS；{blocked} 阻塞（纪律 12 预期行为）"
    return True, "五阶段全部 PASS"


def _pytest(*targets: str) -> tuple[str, ...]:
    return ("-m", "pytest", *targets, "-q", "-p", "no:cacheprovider")


# ★ `tests/injection/` 的**分片名单** —— "哪几片合起来 = 完整覆盖该目录"的**唯一真源**。
#
# 为什么要有这个常量，而不是让判据去猜批次名：
#   `tests/injection/test_shard_coverage.py` 需要知道"哪些片属于 `tests/injection`"。
#   若它靠 `name.startswith("injection-")` 去认，那就是 `R-06 ①` 明文禁止的
#   **关键词式判据**（改个名就静默退出该判据的覆盖范围）。
#   故这里给一份**显式**名单：改名忘改名单 ⇒ 绑定测试立刻红。
#
# 为什么分片（**不是设计选择，是宿主配额决定的**，见模块 docstring 与 `V-08`）：
#   `tests/injection` 的每个用例各带一份夹具副本 ⇒ 单轮总量 ≫ 宿主单轮配额。
#   ★ 用例数**不在此处写死**：它随目录增长（写进来必然漂移）。现量：
#     `pytest tests/injection --collect-only -q`（真源 = 目录本身）。
#   完整覆盖该目录现在需要**逐片各跑一个轮次**（片数 = 本常量的长度，不重复）。
#   ★ 卡 13-F（`G-54`）实测更正两处**写死的数**（这类数必然漂移，别把它们当常量读）：
#     ① 每例副本 **271 项 → 275 项**（2026-09-16 静态实测：`_COPY_SKIP` 口径下 275 个文件条目 /
#        2.69 MB；`scripts/` 113 + `tests/` 86 就占 72%）。**它会随目录增长而涨**，
#        引用时请重新量（`countTarget` 口径 = 目标树下的文件条目数，见 ③）。
#     ② 单轮配额阈值**不是固定 9,999**：它是宿主环境变量
#        `CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD`（本会话实测 `99999`；此前观测到 `9,999`）。
#        9,999 还同时是 bulk-guard 里 `DISPLAY_COUNT_LIMIT` 的**显示上限**，两者容易混。
#        ⇒ **安全上界必须按当次实测的阈值算**：阈值 99999 时 ≈360 例/轮，阈值 9999 时 ≈36 例/轮。
#        **当前片数**（每片都接近用例数上限）在 **9,999** 这个较低阈值下**不成立**；
#        维持当前片数是"按观测到的较高阈值 + 风险登记"的口径，详见 `reports/ws_verify_shard_report.md`。
INJECTION_SHARDS: tuple[str, ...] = (
    "injection-a", "injection-b", "injection-c",
    "injection-d", "injection-e", "injection-f",
    "injection-g",
)

# ★★ 读本字典前必读（卡 13-N 定的口径，别再改回去）：
#   **超时值的唯一真源 = 每批 `Batch(...)` 里那个位置参数**（`Batch.timeout`）。
#   各批注释里出现的秒数（`60s → 300s`、`120s ≈ 7.6×`、`270s` 之类）一律是**取值沿革/留档**，
#   **不是** 可以据以改代码的声明 —— 要以它们为准就会重现 13-F 那种漂移
#   （本文件的 `unit` 批就曾同时写着 `270s` 与参数 `120.0`，散文与真源互相矛盾）。
#   同理：**"哪几片 / 每片多少用例 / 上限多少"的真源分别是** `INJECTION_SHARDS`（片名单）、
#   目录本身（`--collect-only` 现量）、`test_shard_coverage.py::MAX_CASES_PER_SHARD`。
#   查超时真值：`python -c "from scripts.ops.verify import BATCHES; print({n: b.timeout for n, b in BATCHES.items()})"`。
BATCHES: Mapping[str, Batch] = {
    "unit": Batch(
        # ★ 超时由 60s 上调（**真值 = 本行 `Batch.timeout`**；散文不重复它，见 `G-28`）。
        #   实测两次**同一套件**（76 例）耗时：**48.73s** 与 **66.72s** —— **高方差**，第二次**已越过 60s 上限**。
        #   ⇒ 60s 会让 `unit` 批**随机被判 TIMEOUT**（`V-03`：超时一律不合格）⇒
        #     **"会随机变红"的门禁 = 会被关掉的门禁**（本项目铁律）。
        #
        # ★★ 根因已由**卡 13-F（`G-54`）**定位并修掉（`tests/conftest.py`），**此处更正原判断**：
        #   ~~"疑似共享 fixture 每例整树拷贝，代价随仓库体积增长"~~ —— **实测证伪**。
        #   实测（插桩 `code_root`，工作树内）每例 setup = copytree **0.10~0.14s** + `_ensure_dirs` 0.000s
        #   + `_make_writable` 0.015s + **`_reset_truth_source` 4.157s**，其中
        #   **`raw/` 逐项清理 5 项 = 4.157s**（`facts/` 22 次写只有 0.002s）。
        #   真自变量是**删除调用次数**（宿主每次 `unlink`/`rmtree` 收固定 ≈0.5~0.8s 审批往返，
        #   **与项数无关**：一次 `rmtree` 删 310 项只用 0.76s）⇒ 5 次调用 ≈4.2s。
        #   ⇒ 修法 = 让 `raw/` 的内容**根本不进副本**（副本里它本就该是空的）。**与仓库体积无关。**
        #   修后实测：`unit` **15.79s / 11.42s**（修前同机对照 **60.58s / 58.52s**）。
        #
        # ★ 取值沿革（**真值只有一个 = 本行的 `Batch.timeout`**；下面都是留档的历史值，
        #   **不构成对当前值的理由** —— 当前值的理由写在本行参数之后的注释里）：
        #   60s（原值，上条实测证明会随机红）
        #   → 270s（13-F 修前按 15.79s × 17.1 的保守取值，当时**没有**"修后 + 高并发"实测，
        #     且主理人明示"不要为了好看压回 60s"）
        #   → 120s（一度按**裸 pytest 墙钟** 15.79s/11.42s 定为 ≈7.6× —— **该依据已被推翻**：
        #     它与门禁口径读数可差 16×，两个仪器不能混用）
        #   → 300s（**主理人裁定**：无"修复后的门禁口径"读数时取上限，待受控复测后按 `V-02` 收紧）。
        #   ⇒ **若将来在满负载下复测**（确认最慢一次），按 `V-02` 重算：`最慢一次 × 4~8`（≤300s）。
        "unit", "tests/unit/（契约 + 作用域匹配器）",
        _pytest("tests/unit"), 300.0, _exit_zero,
        # ★ 超时 120s → **300s**（主理人裁定）：**我们目前没有"修复后的门禁口径"读数**。
        #   旧的两个数不能混用（实测可差 16×）：
        #     · **门禁口径**（`verify.py` 自己的墙钟）修复前 = **49.35s**（⇒ 4× = 197s，仍在 300s 内）
        #     · **裸 pytest 墙钟**修复后 = 15.79s/11.42s（**不是**门禁口径，不能据此定值）
        #   ⇒ 按"不确定时取上限"（与 `guards`/`injection-*`/`pricelayer`/`valuelayer` 齐平），
        #     待一次 **门禁口径的受控复测** 后再按 `V-02` 收紧。

    ),
    "conflict": Batch(
        "conflict", "tests/conflict/（P-03/P-05/P-07 schema）",
        _pytest("tests/conflict"), 30.0, _exit_zero,
    ),
    "guards": Batch(
        # ★ 不写"多少项"（批次 7 审计）：本批跑的是 `tests/guards/`，其契约矩阵**自带真源**
        #   （`test_exit_code_contract.py::GUARDS` 并 `assert len(GUARDS) == <它自己的数>`），
        #   与 `run_all_gates.GATES` 的项数是**两个不同的数**。此前我在描述里写过 18 / 19 / 20 / 23
        #   四种值 —— 同一事实四个数字，且"由对改错"过一次（把 20 改成 23，而 23 是另一批的数）。
        #   **根治办法 = 不在描述里重复真源**：数字只留在各自的真源里。
        # ★★ 超时 60s → **300s**（`G-54` 同族）。**两批读数合起来看**：
        #   主理人实测（6 条并发流）：**101.96s**（`exit=124` 超时）；安静时 **30.73s** ⇒ **高方差**。
        #   卡 13-F 修后复测（2026-09-16，本工作树）：**27.13s / 19.11s**（修前两次均 `exit=124` @60.02s）。
        #   ⇒ 60s 会让本批**随机被判 TIMEOUT**（`V-03`）⇒ **"会随机变红"的门禁 = 会被关掉的门禁**。
        #   取值依据 `V-02`（以较慢一次 101.96s 为基准；4× = 408s 越 300s 上限）⇒ **取上限 300s**。
        #   ★ 与 `valuelayer` 同属「**上限 300s 但 4× 已越限**」形态 ⇒ 根治要降实测（卡 13-F 已完成），
        #     本行只是**先让门禁可信**。
        #   ★★ **卡 13-F 的自我更正（留档，别重犯）**：我一度把本行改成 **120s**
        #     （依据：修后 27.13s × 4.4）。**合并时主动放弃该值、回到 300s**，理由：
        #     ① 我那次 27.13/19.11s 是**较轻负载**下的读数，而本批有 **6 并发 101.96s** 的实测
        #        —— **较慢一次**才是 `V-02` 的取值基准，我没有"修后 + 6 并发"的读数；
        #     ② 拿未测场景去**收紧**超时，等于把本卡要消灭的"随机红"重新装回去；
        #     ③ 收紧门禁属于"把门关小"，应由主理人按新证据裁决，不由我顺手做。
        #     ⇒ **120s 是"确认后可选"的值**（需一次修后+满负载复测），**不是现在该取的值**。
        #   ★★ **一处必须登记的丢失（卡 13-F 第三次合并时发现，不改值、只登记）**：
        #     `main` 曾在另一支上把本行定成 **210s**，推导是**按 13-F 自己给分片定的规则**
        #     「实测 × 8 + 取整 30s 倍数 + 不低于 90s」（`27.13 × 8 = 217 ⇒ 210`，7.7×，落在 4~8× 内）
        #     —— 那条推导**比我这个 300s 更有依据**（300s 是"4× 越上限只好取顶"的兜底）。
        #     但随后 `main` 的 `f2d1371`（合并 `ws/fixture-cost`）**冲突取了分支侧 = 我这个旧的 300s**，
        #     210s 因此**被覆盖丢失**。⇒ **本行现值 300s 是"合并产物"，不是谁的裁决**。
        #     ★ 我**不**在这次合并里顺手改回 210s：**收紧门禁应由主理人裁**（同 ③ 的理由）。
        #     若主理人认可 210s，改动只有一处：把下面的 `300.0` 换成 `210.0`，并删掉本段。
        "guards", "tests/guards/（门禁退出码契约 + 验证规范）",
        _pytest("tests/guards"), 300.0, _exit_zero,
    ),
    # ── `tests/injection/` 的各分片（**原 `injection` 目录全量批次已删除**）──────────────
    # ★ 目标一律**显式文件路径**，**不用目录**（目录 = 一次拉起整个目录的用例 = 配额问题复发），
    #   **不用 `-k`**（`R-06 ①`：关键词式判据不可穷尽，新用例会静默落进 `not` 分支）。
    # ★ 每次**只跑一片**：同一轮里连跑多片会重新越过宿主单轮删除配额
    #   （`SAFE_DELETE_BULK_CONFIRM_REQUIRED`），表现为"某片突然在几秒内变红"。
    # ★ 超时的**真源 = 本文件各批的 `Batch.timeout`**，散文里**不再抄一份**
    #   （`G-28`：同一事实两处写必然漂移；取值判据见 `CONVENTIONS.md::V-02`）。
    #   查真值：`python -c "from scripts.ops.verify import BATCHES; print({n: b.timeout for n, b in BATCHES.items()})"`。
    #   历史读数（**隔离副本**单跑，`verify.py --batch <片>`，供 `V-02` 重算参考）：
    #   a 6.85s · e 9.82s · f 12.53s · c 16.50s · b 18.62s · d 24.99s。
    #   ★ 为什么取上沿（**本单实测教训**）：同一片 `injection-a` 在**工作树**里跑成
    #     **80.92s**（`run_pytest.sh` 直接实测，27 passed，**不是卡死**），而隔离副本同代码
    #     只要 6.85s ⇒ **宿主并发可把单片拖慢 11.8×**。当时 `tests/.work/` 里留着
    #     `tests/guards` 与 `injection-c` 的夹具残留 ⇒ **同一个工作树里有第二个 pytest 会话**
    #     （`V-05` 禁止的情形）。取上沿正是 `V-02` 说的"让偶发抖动不误报"。
    #     ⇒ 见到本批超时的**第一步**不是改断言，而是先确认有没有第二个会话在同一工作树里跑。
    #   ★ **最终取值 = 按 `V-02` 取"不超过上限的最大值"**（真值见各批 `Batch.timeout`，
    #     不在此处抄；**各片是否同值也不在此处断言** —— 它随裁定时点变化，见各批自己的注释）。
    #     理由与上面那条相反方向的取舍：
    #     ① 作为**故障探测器**，**本批的上限**对**工作树实测**是 2.7~4.7×
    #        （上限值见 `Batch.timeout`，不在此处抄）：
    #        实测（工作树内 `verify.py --batch <片>`）a 70.74~80.92s · b 63.72s · f 110.13s；
    #     ② `V-02` 的"4~8×"对 f（110.13s × 4 = 440s）**越过了 300s 上限** ⇒ 与 `daily`
    #        （43s 实测 → 180s，4.2×）同一处境：**取不超过上限的最大值**；
    #     ③ 反过来，"取 8× 隔离副本实测（6.85s）"= 60s 会**必然误报**：f 的隔离实测 12.53s
    #        对应工作树 110.13s（8.8×），60s 上限当场变红 ⇒ `G-01`「天天误报的门禁一定会被
    #        关掉」。**故一律以工作树实测为标定基准，不用隔离副本的秒数**。
    #     ★ 遗留风险（如实登记）：f 的余量只有 2.7×，若**同时**有第二个 pytest 会话在同一
    #       工作树里跑（`V-05` 禁止的情形），f 仍可能被拖到 300s 以上而**假红**。
    #       见到本批超时的**第一步不是改断言**，而是先确认有没有第二个会话在同一工作树里跑。
    "injection-a": Batch(
        # ★ 2026-09-16 主理人补录：`test_step56_skipped_wiring.py`（3 例，收 `G-44`）由
        #   `merge ws/step56-skipped` 带进 ⇒ `test_shard_coverage.py` 的**穷尽性断言如实变红**
        #   （"写了却永远不被验证"），按设计生效。本片用例数随之增加
        #   （**现值不在此处写死**：现算与"≤ 上限"的断言见 `tests/injection/test_shard_coverage.py`）。
        #   ★ 给后续各流的固定约束：**新增注入测试文件必须同时登记进本文件的一片**，
        #     否则绑定会红 —— 这是刻意的（防"写了没人跑"），不是障碍。
        "injection-a", "tests/injection/ 分片 A（审计回归 + 链路接线 + step5/6 接线）",
        _pytest(
            "tests/injection/test_audit_regressions.py",
            "tests/injection/test_chain_steps_wiring.py",
            "tests/injection/test_step56_skipped_wiring.py",
        ),
        300.0, _exit_zero,
    ),
    "injection-b": Batch(
        "injection-b", "tests/injection/ 分片 B（判据有效性 + 守卫防御性）",
        _pytest(
            "tests/injection/test_criterion_effectiveness.py",
            "tests/injection/test_guards_defensive.py",
        ),
        300.0, _exit_zero,
    ),
    "injection-c": Batch(
        # `test_guards_reject_a.py` 是原 `test_guards_reject.py` 的**前半**：
        # 原文件单文件 ≈ 11,111 项就超配额，必须按 `# ═══` 分节边界拆两半（纯移动，断言语义零改动）。
        # ★ 两半各自的用例数**不在此处写死**（会随用例增长而漂移）：现算见
        #   `tests/injection/test_shard_coverage.py`。
        "injection-c", "tests/injection/ 分片 C（守卫拦截 A 半 + 追加式）",
        _pytest(
            "tests/injection/test_guards_reject_a.py",
            "tests/injection/test_append_only.py",
        ),
        300.0, _exit_zero,
    ),
    "injection-d": Batch(
        # ★ 重平衡记录（2026-09-16，主理人）：`test_time_contract.py`(5 例) 由本片**移入**
        #   `injection-e`。原因：合并 `main` 带进了 `ws/idempotency` 新增的 3 条用例
        #   （`test_idempotency_rows.py` 6 → 9），本片因此涨到 **34 例**、**越过每片用例数上限** ——
        #   `tests/injection/test_shard_coverage.py::test_shard_case_counts_within_quota`
        #   **如实变红**并给出了具体片名与数字（机器绑定按设计生效，不是假红）。
        #   ⇒ 此后各片的用例数**不在此处写死**（`G-28`）：它随用例增长而变，而现算 + "≤ 上限"的
        #     断言都在 `tests/injection/test_shard_coverage.py`（`--collect-only` 逐片现量）。
        "injection-d", "tests/injection/ 分片 D（守卫拦截 B 半 + 幂等）",
        _pytest(
            "tests/injection/test_guards_reject_b.py",
            "tests/injection/test_idempotency_rows.py",
        ),
        300.0, _exit_zero,
    ),
    "injection-e": Batch(
        "injection-e", "tests/injection/ 分片 E（提示注入 + rules 锁 + 时间契约）",
        _pytest(
            "tests/injection/test_prompt_injection.py",
            "tests/injection/test_rules_lock.py",
            "tests/injection/test_time_contract.py",   # ← 由 `injection-d` 移入（见 D 片注释）
        ),
        300.0, _exit_zero,
    ),
    "injection-g": Batch(
        # ★ 新增分片（主理人，批次 13 集成期）：合并 `ws/real-collect-2` 带进了
        #   `tests/injection/test_quote_provenance.py`（17 例），而 `V-06` **如实变红**：
        #   「以下测试文件不被任何批次覆盖（写了却永远不被验证）」—— 机器绑定按设计生效。
        #   ★ 为什么**不能**塞进既有分片：**当时各片的余量都装不下本文件**（各片用例数都贴着
        #     每片上限）⇒ 只能**新开一片**。（各片当时的用例数**不在此处写死**：现算与
        #     "≤ 上限"的断言见 `tests/injection/test_shard_coverage.py`。）
        #   ★ 超时：**真值见本批 `Batch.timeout`**，不在此处重复；
        #     当前值的理由写在本批参数之后的注释里（**沿革与理由分开存放，别把旧理由当现值**）。
        "injection-g", "tests/injection/ 分片 G（反编造：引用溯源守卫）",
        _pytest(
            "tests/injection/test_quote_provenance.py",
        ),
        # ★ 超时 90s → **300s**（主理人裁定）：与 `injection-a..f` **齐平**（同族一致性优先），
        #   并吸收一个**已复现**的宿主状态 —— 子进程若落回沙箱内，本片单次实测可达 **247s ≫ 90s**
        #   会被判 `[TIMEOUT]`，而同期 `a..f`（300s）不会。⇒ 只是让本片**不比邻片更早红**。
        300.0, _exit_zero,
    ),
    "injection-f": Batch(
        "injection-f", "tests/injection/ 分片 F（阶段闸门 + 接线守卫 + 分片绑定）",
        _pytest(
            "tests/injection/test_stage_gate.py",
            "tests/injection/test_wiring_guards.py",
            "tests/injection/test_shard_coverage.py",
        ),
        300.0, _exit_zero,
    ),
    "root": Batch(
        "root", "tests/test_ch11_invariants.py（Ch11 不变量）",
        _pytest("tests/test_ch11_invariants.py"), 30.0, _exit_zero,
    ),
    # ── 并行工作流（ws/compute · ws/graph · ws/claim · ws/decision）交付的批次 ──
    # 由主理人在集成时统一加入（`reports/parallel_workstreams.md §5 I-3`）：
    # 各 WS **不得**自行改本文件（多方同改必冲突），只报"需新增批次"。
    "compute": Batch(
        # ★★ 超时 60s → 180s（卡 13-F / `G-54` 的**批次对照表**实测，2026-09-16）：
        #   两次实测 **36.62s / 33.74s** ⇒ 旧 60s 只剩 **1.6×**（`V-02` 要求 4~8×）⇒ **会随机红**。
        #   ★ 本批**一个夹具用例都没有**（`tests/compute/` 不用 `code_root`）⇒
        #     这段耗时**与夹具无关**，是 102 例真实测试工作；即夹具修好也**不会**变快。
        #     ⇒ 只能按 `V-02` 提高上限：180s 对较慢一次 = **4.9×**，≤300s。
        "compute", "tests/compute/（确定性计算层）",
        _pytest("tests/compute"), 180.0, _exit_zero,
    ),
    "pricelayer": Batch(
        # 新增测试目录必须同时加批次，否则 `V-06` 会把新目录判成"未覆盖"（`CONVENTIONS.md::V-06`）。
        # 由**批次 13-B**（Ch5 价格层）随 `tests/pricelayer/` 一并加入（任务卡 13-B 明令）。
        # 超时：工作树内实测 **53.89s / 83.80s**（168 例，两次采样）→ 取 **300s（≈3.6~5.6×）**。
        # 依据 `CONVENTIONS.md::V-02` 注：判据是「`<= 300s` + 余量足以区分"慢"与"卡死"」，
        # 倍数边界在慢批次上已不成立（8× = 671s > 300s）⇒ 与 `daily`/`injection-*` 同属
        # "慢批次取不超过上限的最大值"。
        # ★ 13-F 曾据 **127 例**的复测（33.52s / 33.46s）主张 180s = 5.4×；但本批现为 **168 例**
        #   且 13-F 的夹具降本（`raw` 入 `_COPY_SKIP`）**落地后**尚无 168 例的复测数 ⇒
        #   **主理人裁定：暂取上限 300s**（安全网），最终值由 13-F 的「批次实测耗时 vs 超时」对照表按 `V-02` 重算。
        # ★ 卡 13-F 的旧读数 **33.52s / 33.46s（127 例）已被取代**（用例数 127→168，13-B 后续追加）
        #   ⇒ 取舍：**以 168 例的 83.80s 为基准**，180s 只有 **2.1×**、不成立；**300s 保留**。
        # ★ 本批 **0 个夹具用例** ⇒ 卡 13-F 的夹具修复**不会**改善它（别拿修后去预期它变快）。
        # ★ 13-F 收口时的实测状态：**168 例的修后复测仍未取得**（宿主单轮删除配额），
        #   清单见 `reports/ws_fixture_cost_report.md §⑤` ⇒ 本行 300s 仍是"待重算"的暂取值。
        "pricelayer", "tests/pricelayer/（Ch5 价格层：反解多解/估值路由/倒填/情景/历史外推/每日解释）",
        _pytest("tests/pricelayer"), 300.0, _exit_zero,
    ),
    "graph": Batch(
        # 卡 13-F 复测（2026-09-16）：**3.83s / 3.21s** ⇒ 60s = 15.7×，维持不变。
        "graph", "tests/graph/（依赖图与 T12 传播）",
        _pytest("tests/graph"), 60.0, _exit_zero,
    ),
    "validators": Batch(
        # ★★ 超时 30s → 90s（卡 13-F / `G-54` 批次对照表实测，2026-09-16）：
        #   两次实测 **19.26s / 12.81s** ⇒ 旧 30s 只剩 **1.6×** ⇒ **会随机红**。
        #   本批约 20 例用 `code_root`（每例的 `raw/` 清理已由夹具修复去掉 ⇒ 修后才会是这个数）。
        #   90s 对较慢一次 = **4.7×**，≤300s。
        "validators", "tests/validators/（locator 定位校验器）",
        _pytest("tests/validators"), 90.0, _exit_zero,
    ),
    "claim": Batch(
        # ★★ 超时 30s → 120s（卡 13-F / `G-54` 批次对照表实测，2026-09-16）：
        #   两次实测 **22.44s / 17.88s** ⇒ 旧 30s 只剩 **1.3×** ⇒ **会随机红**（本批是 5 个"红候选"之一）。
        #   120s 对较慢一次 = **5.3×**，≤300s。
        "claim", "tests/claim/（主张五态状态机）",
        _pytest("tests/claim"), 120.0, _exit_zero,
    ),
    "decision": Batch(
        # ★★ 超时 30s → 120s（卡 13-F / `G-54` 批次对照表实测，2026-09-16）：
        #   两次实测 **22.14s / 24.86s** ⇒ 旧 30s 只剩 **1.2×** —— **全表最危险的一批**（余量 20%）。
        #   ★ 本批**一个夹具用例都没有** ⇒ 与夹具无关，是 97 例真实测试工作。
        #   120s 对较慢一次 = **4.8×**，≤300s。
        "decision", "tests/decision/（决策层 triage / gate / rules）",
        _pytest("tests/decision"), 120.0, _exit_zero,
    ),
    "transmit": Batch(
        # 由主理人在集成时加入（`reports/batch8_parallel_taskbook.md`）：
        # 新测试目录必须同时加批次，否则 `V-06` 会把新目录判成"未覆盖"（`CONVENTIONS.md::V-06`）。
        "transmit", "tests/transmit/（Ch7 传导编排引擎）",
        _pytest("tests/transmit"), 60.0, _exit_zero,
    ),
    "evidence": Batch(
        # 新增测试目录必须同时加批次，否则 `V-06` 会把新目录判成"未覆盖"（`CONVENTIONS.md::V-06`）。
        # 由主理人在集成时加入（`reports/batch9_stage3_4_taskbook.md §3 I-1`）。
        # 超时：实测 ~18s → 150s（**≥8×**，符合 `V-02`）。
        "evidence", "tests/evidence/（Ch6 证据层：去重/独立判定/预算闸门）",
        _pytest("tests/evidence"), 150.0, _exit_zero,
    ),
    "daily": Batch(
        # 新增测试目录必须同时加批次，否则 `V-06` 会把新目录判成"未覆盖"（`CONVENTIONS.md::V-06`）。
        # 由主理人在集成时加入（`reports/batch9_stage3_4_taskbook.md §3 I-1`）。
        # 超时：实测 ~43s。★ 批次 10 审计 `G8` 指出原值 60s 只有 **1.4×**（违 `V-02` 的 8~30×）。
        #   但 8× = 344s **超过 `V-02` 的 300s 上限** ⇒ 取 **180s（约 4.2×）**：
        #   仍有充足余量区分"慢"与"卡死"，且不越上限。
        #   → `V-02` 的"8~30×"是**慢批次出现前**的经验值；该规则的适用边界已登记（见 `CONVENTIONS.md::V-02` 注）。
        "daily", "tests/daily/（阶段④每日运行：覆盖可核/降级/幂等/调度）",
        _pytest("tests/daily"), 180.0, _exit_zero,
    ),
    "valuelayer": Batch(
        # 新增测试目录必须同时加批次，否则 `V-06` 会把新目录判成"未覆盖"（`CONVENTIONS.md::V-06`）。
        # 由**批次 13-A（Ch4 价值层）**加入（`system/reports/batch13_taskbook.md` 卡 13-A 的
        # 显式要求："`tests/valuelayer/` 新目录 ⇒ 必须同步在 `verify.py::BATCHES` 加一批"）。
        # 目标 `tests/valuelayer/` 是**本批次新建**的目录（rollup / route_guard / growth_quality /
        #   moat_guard / state_machine / completeness 六模块的用例）。
        # 超时：工作树内**实测 170.15s**（191 passed）→ 按 `V-02` 取**不超过上限的最大值**
        #   （真值见本批 `Batch.timeout`；170 × 4 = 680s 越过 `V-02` 的 300s 上限，
        #    与 `daily` / `injection-*` 同一处境）。
        #   ★ 遗留风险（如实登记）：本批余量仅 **1.76×**，比 `injection-f` 的 2.7× 更薄 ——
        #     若同一工作树里有第二个 pytest 会话（`V-05` 禁止的情形）并发，本批可能被拖过上限而**假红**。
        #     见到本批超时的**第一步不是改断言**，而是先确认有没有第二个会话在同一工作树里跑。
        #   ★ 夹具配额：本目录 **28 个用例**用 `code_root` 夹具（2026-09 实测 `def test_*(… code_root …)`
        #     计数，会随用例增长；其余为纯内存用例，`P-05`），与 `injection-*` 各片同一量级
        #     （各片现值**不在此处写死**：见 `tests/injection/test_shard_coverage.py`）。
        "valuelayer", "tests/valuelayer/（Ch4 价值层：指标集/加总/增长质量/护城河/状态机/完备性）",
        _pytest("tests/valuelayer"), 300.0, _exit_zero,
    ),
    "gates": Batch(
        # ★ 不写"多少项"（批次 7 审计）：数字的真源在 `run_all_gates.GATES`，
        #   描述里重复它必然漂移（同一事实曾出现 18/19/20/23 四个值）。
        "gates", "run_all_gates.py（全部门禁逐项退出码）",
        ("scripts/ops/run_all_gates.py", "{root}", "--timeout", "30"), 60.0, _exit_zero,
        note="门禁内部已有逐项 30s 硬超时（卡死也算不合格）",
    ),
    "stage": Batch(
        # ★ 描述**不写"哪些阶段该阻塞"**（同一事实第二个存放处必然过期 —— 见 `_stage_gate_verdict`）。
        #   真源 = 判据函数里的判据本身：五阶段逐个必须显式取值 + 退出码与取值自洽。
        "stage", "stage_gate.py --stage all（五阶段判据台账 + 退出码自洽）",
        ("scripts/delivery/stage_gate.py", "{root}", "--stage", "all", "--no-report"),
        30.0, _stage_gate_verdict,
    ),
}

ORDER = (
    "unit", "conflict", "guards",
    # ★ `tests/injection/` 的各片必须**逐片单独跑**（见 `INJECTION_SHARDS` 上方的理由）。
    #   `--batch all` 会把它们连着跑完 —— 那**恰好**会重新越过宿主单轮删除配额，
    #   在某一处突然变红（`V-08`）。要完整覆盖该目录，请**逐片各跑一个轮次**
    #   （片数 = `INJECTION_SHARDS` 的长度，不在此处重复）。
    "injection-a", "injection-b", "injection-c",
    "injection-d", "injection-e", "injection-f",
    "injection-g",
    "root",
    "compute", "graph", "validators", "claim", "decision", "transmit", "evidence", "daily",
    "pricelayer",
    "valuelayer",
    "gates", "stage",
)


def _child_env() -> dict[str, str]:
    """给验证子进程的**环境**：关闭 Python 层的 FS broker hook。

    ★ 实测根因（本批次的真实故障）：WorkBuddy 的 `sitecustomize.py` shim 会在
      **每一次文件操作**上 brokered 到宿主进程走 IPC —— 触发条件是
      `CODEBUDDY_SAFE_DELETE_SANDBOX=1` 或 `CODEBUDDY_BROKERED_FS_HOOK_ENABLED=1`
      （见 shim 的「触发条件」区段）。Bash 工具的沙箱开关**关不掉它**。

      后果：测试夹具的 `copytree` 每次要复制 130 个文件 ⇒ 每个用例数百次 IPC 往返
      ⇒ 数百个用例累积数万次 ⇒ **在某个点 broker 阻塞，进程卡死且卡点漂移**
      （实测 `tests/unit/test_contracts.py` 卡在第 15/17/19 条不等）。

      实测对照（同一台机器、同一份代码）：

      | broker | 12 次 copytree |
      |---|---|
      | 开 | **卡死**（faulthandler 堆栈落在 `_brokered_shutil_copytree`） |
      | 关 | 每次 **0.026s**，12/12 全过 |

      故**验证子进程一律在沙箱外跑**（用户要求），只影响本进程派生的验证子进程。
    """
    return {
        **os.environ,
        "CODEBUDDY_SAFE_DELETE_SANDBOX": "0",
        "CODEBUDDY_BROKERED_FS_HOOK_ENABLED": "0",
    }


def _run(batch: Batch, root: Path) -> tuple[int, str, float]:
    argv = [sys.executable] + [a.format(root=str(root)) for a in batch.argv]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=batch.timeout,
            env=_child_env(),
        )
        code, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        code = 124
        partial = exc.stdout or ""
        head = partial if isinstance(partial, str) else ""
        out = (
            head
            + f"\n[TIMEOUT] 批次 {batch.name!r} 超过 {batch.timeout:.0f}s 未返回 —— "
            "**该批有问题**（极大概率是测试本身，不是「跑得慢」）。\n"
            "排查建议：只跑该批内的单个文件 / 单条用例，定位卡在哪一个用例。\n"
        )
    return code, out.rstrip(), time.monotonic() - t0


def _prune(out_dir: Path) -> None:
    """每个批次只保留最近 KEEP_LOGS 份带时间戳的日志（避免仓里日志堆积）。"""
    for name in ORDER:
        for old in sorted(out_dir.glob(f"verify_{name}_2*.log"), reverse=True)[KEEP_LOGS:]:
            old.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify.py", description="分批验证器（禁止一条命令全量验证）"
    )
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--batch", default=None, help="批次名或 all")
    parser.add_argument("--list", action="store_true", help="列出批次与超时")
    parser.add_argument("--quiet", action="store_true", help="只打印摘要与失败批次的输出")
    args = parser.parse_args(argv)

    if args.list or args.batch is None:
        print("可用批次（每批独立子进程 + 独立超时）：")
        for name in ORDER:
            b = BATCHES[name]
            print(f"  {name:<10} {b.label:<46} 超时 {b.timeout:>5.0f}s")
            if b.note:
                print(f"             └ {b.note}")
        print("\n用法：--batch <名>（推荐，一次一批） 或 --batch all（逐批跑，超时即停）")
        return 0 if args.list else 2

    code_root = Path(args.code_root).resolve() if args.code_root else ROOT
    if not code_root.exists():
        print(f"[INPUT-ERROR] code_root 不存在: {code_root}", file=sys.stderr)
        return 2

    names = ORDER if args.batch == "all" else (args.batch,)
    unknown = [n for n in names if n not in BATCHES]
    if unknown:
        print(f"[INPUT-ERROR] 未知批次 {unknown}；可用: {list(ORDER)}", file=sys.stderr)
        return 2

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = code_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for name in names:
        batch = BATCHES[name]
        code, out, elapsed = _run(batch, code_root)
        ok, why = batch.verdict(code, out)

        lines = [
            f"# 分批验证留档 · {stamp} · 批次 {name}",
            f"# code_root = {code_root}",
            f"# python    = {sys.executable}",
            f"# 耗时 {elapsed:.2f}s ｜ 超时上限 {batch.timeout:.0f}s ｜ 退出码 {code}",
            f"# 判定: {'合格' if ok else '不合格'} —— {why}",
            "=" * 78,
            out,
        ]
        log = out_dir / f"verify_{name}_{stamp}.log"
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        shutil.copyfile(log, out_dir / f"verify_{name}_latest.log")

        mark = "✓" if ok else "✗"
        print(f"{mark} [{name}] {batch.label}  exit={code}  {elapsed:.2f}s/{batch.timeout:.0f}s  {why}")
        if not ok or (not args.quiet):
            print("-" * 78)
            print(out)
            print("-" * 78)

        if not ok:
            failures += 1
            if args.batch == "all":
                print(f"✗ 批次 {name!r} 不合格 —— **停止后续批次**（fail-fast，不让问题批次拖垮整轮）")
                break

    if len(names) == 1:
        print(f"证据留档: reports/verify_{names[0]}_latest.log")
    _prune(out_dir)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
