#!/usr/bin/env python3
"""`sample_batch_times.py` —— 卡 `#83`：按「**门禁口径**」取样批次耗时（**只取样，不改登记值**）。

## 这个脚本存在的唯一理由（`口径 21`）

给 `Batch.timeout` 定值的**唯一合法仪器**是「**门禁口径**」——
即 `verify.py --batch <名>` **自己打印**的 `<elapsed>s/<timeout>s` 与**它自己**的退出码。

- 裸 `pytest` 墙钟 / `--durations` / `/usr/bin/time` **只能作旁证**，**不得**据以定值
  （同一份代码在宿主沙箱内/外可差 **16 倍**：本仓实测 `247.19s` vs `15.37s`）；
- ⇒ 本脚本**从不**直接调 `pytest`，一律委派给 `verify.py`，只**读它的产物**。

## ★ 关于"开工前配额预检"的**能力边界**（本单实测，必须写明，否则会误用）

`13-F §⑥-7` 给了一个**只读**诊断：读宿主 safe-delete 的 `state.json`，取当前
`CODEBUDDY_CONVERSATION_REQUEST_ID` 的 `count` 与阈值相减得"余量"。
**本单实测它不可复现**（同一 `rid`、同一文件、相隔数分钟）：

| 时刻 | 读数 |
|---|---|
| T1 | `used=99998 / threshold=99999` ⇒ 余量 **1** |
| T2（数分钟后） | 该 `rid` **已不在 `requests` 表里**（⇒ 按"缺省 0"算，余量 = 99999） |

且 T2 时表里存活的 20 个 `rid` 计数为 **111,716 ~ 384,892**，**全都远高于** 阈值 `99,999`
⇒ 这个计数**不是**"每轮从 0 涨到 9,9999 就重置"的简单模型。

**结论（照实写，不替宿主机制编解释）**：该诊断只能当**当时那一瞬的旁证**，
**不能**当"本轮能不能跑"的判决。⇒ 本脚本的预检据此**降级为"保守建议"**：

- 读数**可用且显示不足** ⇒ **默认拒绝开跑**（安全方向），但输出里**明说"该读数可能不成立"**，
  并给出显式覆盖开关（`--no-quota-check`，读数会如实标注 `skipped`）；
- **真正可靠的信号仍然是运行中**：`SAFE_DELETE_BULK_CONFIRM_REQUIRED` 一旦出现即 `verdict=QUOTA`
  并**停止整轮**（见下"不许"第 2 条）。

## 三个"不许"（写在代码里，不靠记性）

1. **不套管道取退出码**（`口径 22`）：全程用 `subprocess` 的 `returncode`。
   `cmd | tail` 后取 `${PIPESTATUS[0]:-$?}` 在 **zsh** 里会回落到 `tail` 的退出码 ⇒ **假 `exit=0`**。
2. **不在 `G-60` 上重试**：一旦输出里出现 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`
   （或 `verify.py` 的"宿主单轮删除配额耗尽"），本格记为 `QUOTA` 并**立即停止整轮取样** ——
   `count` 与上轮相近 ⇒ 本轮的删除配额已用完，**重试只会浪费一个轮次**，而且会**把已测得的数据搅脏**。
3. **不把 `G-60` 污染读数当读数**：被污染的格子一律作废（只记"因 `G-60` 未测"），
   **绝不用"上一次的数"或"别的批次的数"补齐**（这正是 `G-03` 与 `口径 21` 要防的）。

## 记录什么（每格每次一行）

`refs/heads/main` 的 SHA · 取样时刻（本地 + UTC）· **并发流数** · 门禁口径 `elapsed/timeout` ·
`verify.py` 退出码 · `pytest` 退出码 · 是否受 `G-60` 污染 · 是否 `exit=124`（超时）。

★ **并发流数**是**操作性代用指标**（`ps` 里含 `pytest` / `verify.py` 的进程数），
**不是**宿主真实并发度 —— 它只用来解释"同格两次读数为什么差很多"，故**如实标注为代用指标**。

## 用法

```bash
cd <worktree>/system
PY="${HOME}/.workbuddy/binaries/python/envs/default/bin/python"

"$PY" scripts/ops/sample_batch_times.py --plan                # ★ 只打印计划，不执行任何批次
"$PY" scripts/ops/sample_batch_times.py --quota               # ★ 只读诊断本回合配额余量（零删除）
"$PY" scripts/ops/sample_batch_times.py --batch valuelayer    # 单格，默认重复 2 次
"$PY" scripts/ops/sample_batch_times.py --scheduled --max-cells 2
"$PY" scripts/ops/sample_batch_times.py --scheduled --json    # 机器可读
```

★ **取样在"子进程实际配置 = `E=0`"下即可**。自 `main@612cafe`（`3653c7c`）起
`verify.py::_child_env()` **自己强制**置 `E=0` ⇒ **调用者不需要（也不再能左右）export 它**：

```bash
"$PY" scripts/ops/sample_batch_times.py --scheduled --max-cells 2
```

★ 脚本仍会在开跑前**打印子进程实际配置**（并列出调用者值以便对账）；
只有"子进程实际配置不是 `E=0`"（即有人把 `_child_env()` 的第三行删了）才**拒绝开跑**。

★ **开工前**会做**配额预检**（`--quota` 的同一读数）：余量 < 本格所需 ⇒ **拒绝开跑并 `exit=2`**，
**不重试、不降 `repeat`、不拿旧值代替**。宿主未注入诊断所需环境变量时预检**不可用** ⇒
同样**拒绝开跑**（`--no-quota-check` 可显式跳过，但读数里会如实标注 `skipped`，**不得**当成"预检通过"）。

★ 本脚本**不写任何文件**（结果打到 stdout，需要留档就 `> /tmp/...`）——
避免在 `system/reports/` 里堆无人消费的产物（`verify.py` 自己的日志已经够用）。

## ★ 前置：已由主理人解除（裁定记录在 `batch13_taskbook.md`）

原硬前置（新宿主回合 / `/tmp` 方案验证通过 / 用户授权，三者任一）**已因裁定「`E` = 合法配置」而解除** ——
`E`（`CODEBUDDY_SAFE_DELETE_ENABLED=0`）下 `verify.py` 可正常跑夹具，且**CI/门禁就是这个配置**
⇒ **`#83` 应在 `E` 下取样**。`--plan` / `--quota` 不受任何前置限制（它们不跑批次）。

## ★★ 「被测配置」也是仪器的一部分（`口径 21` 的延伸）

`口径 21` 说"给 `Batch.timeout` 定值只认门禁口径"。**但门禁口径本身依赖两件配置** ——
换个配置跑出来的数，**不是同一个仪器的读数**：

| 配置维度 | 合法值 | 非法/不可比的值 | 后果 |
|---|---|---|---|
| 守卫开关 | 子进程实际 `CODEBUDDY_SAFE_DELETE_ENABLED=0`（= 生产/门禁口径） | 守卫开 | 夹具 teardown **每项 spawn 一个 node CLI** ⇒ 实测慢约 **30×**（`58s → 2s`） |
| 夹具根位置 | **仓库内**（`<worktree>/system/tests/.work/…`） | `/tmp` 副本 | 见下（主理人裁定：`#83` 不得在 `/tmp` 夹具模式下取样） |

★★ **取数必须同源**：本脚本读的是**被测程序自己的** `verify.py::_child_env()` 返回值，
**不是调用者的 shell env**。
理由（本单实测的两次更正）：`main@e9a009b` 时 `_child_env()` 只置两个开关、**继承**调用者的 `E`
⇒ 当时"调用者 export 了什么"**就是**被测配置；而 `main@612cafe`（`3653c7c`）起它**强制**把
`E` 也置 `0` ⇒ 调用者 export 什么都不影响批次。
⇒ 若仍按调用者判，就会拒绝一个**本来就是合法生产口径**的读数（**假阻断**，`G-61` 家族）。
**教训**：配置类判据也必须**与被测对象同源**，且**标明 SHA**（`V-11` 时间轴）。

- 子进程实际配置**不是** `E=0` ⇒ 默认**拒绝开跑**（`exit=2`）；确要**对照**用 `--profile-baseline`
  （读数会**逐行**标注 `NON_E` 并写明"**不得据以定值**"）。
- ★ **`#83` 不得在 `/tmp` 夹具模式下取样**（主理人裁定）：`/tmp` 方案只解决 `G-60` **配额**这一件事；
  而 `Batch.timeout` 对应的是**仓库内夹具**的耗时 ⇒ 换位置即与生产口径不可比。
  这是**硬拒绝**，**不提供覆盖开关**。
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # .../system
sys.path.insert(0, str(ROOT))

# ★ 超时值的**唯一真源**是 `verify.py::BATCHES`。本脚本**不复制**任何超时数字（会静默过期）。
# ★ `_child_env` 也是**被测程序自己的真源** —— 被测配置以"子进程实际拿到什么"为准（见 `_env_profile`）。
from scripts.ops.verify import BATCHES, _child_env  # noqa: E402

#: 决定"这一轮算不算生产口径"的三个开关（顺序 = 守卫唯一真源 `BROKER_ENV_VARS` 的顺序）。
_PROFILE_KEYS = (
    "CODEBUDDY_SAFE_DELETE_ENABLED",
    "CODEBUDDY_SAFE_DELETE_SANDBOX",
    "CODEBUDDY_BROKERED_FS_HOOK_ENABLED",
)

#: `G-60` 的标志串（宿主 safe-delete shim 打印）。
QUOTA_MARKER = "SAFE_DELETE_BULK_CONFIRM_REQUIRED"
#: `verify.py` 对同一件事的自述（两处都认，避免只认一个）。
QUOTA_PHRASE = "宿主单轮删除配额耗尽"
#: `verify.py` 超时时的标志。
TIMEOUT_MARKER = "[TIMEOUT]"
#: `V-03`：`exit=124` 一律不合格。
TIMEOUT_EXIT = 124

#: 一个 `code_root` 型夹具用例 teardown 的配额消耗（项）。出处 `13-F §2.6`：修后 **250 项/例**（修前 255）。
#: ★ 引用值，会随 `system/` 树体积漂移 ⇒ 用前请重新量（`13-F §①` 的静态实测口径）。
#: ★★ **本仓有两个读数，未对齐，不要静默挑一个**（`口径 10`）：
#:   `13-F §2.6` = **250 项/例**（teardown 删除的项数）；`verify.py:48` 自述 = **271 项**
#:   （每用例复制一份 `system/` 的项数）。**复制项数 ≠ 删除项数**（`_COPY_SKIP` 与 `raw/` 清理会改这个差），
#:   故两者可能都"对"；但**差 8%** 会直接放大到总预算 ⇒ **实测前按大的那个（271）想**，别按小的想。
#: ★★ **不是所有夹具都这个量级** —— 轻量夹具（只建几个空目录）要小一个数量级，见 `Cell.quota_per_case`。
QUOTA_PER_FIXTURE_CASE = 250

#: `pricelayer` 夹具的每例配额消耗（项）。★ 它的夹具是**轻量工程根**（`tests/pricelayer/conftest.py:29`
#: `make_minimal_root()` 只建 `facts/ derived/ rules/ registry/ index/ reports/` 六个**空目录**，
#: 用例再自写少量 jsonl/yaml）⇒ teardown 删的是 `1 + 6 + N` 项，**不是** 130 文件副本的 250 项。
#: ★ 这是**估算值**（`7 + N`，取 `N≈3`）；**真值请在取样时补测**，但即使乘 2 也仍比 `250` 小一个数量级。
PRICELAYER_QUOTA_PER_CASE = 10

#: 只读配额诊断所需的环境变量（宿主注入；缺任一 ⇒ 诊断不可用，**如实返回原因，不猜**）。
_QUOTA_ENV_KEYS = (
    "CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR",
    "CODEBUDDY_SESSION_ID",
    "CODEBUDDY_CONVERSATION_REQUEST_ID",
    "CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD",
)

#: `verify.py` 日志头部的**稳定**字段行（`｜` 是全角竖线，原样匹配）。
_LOG_HEADER = re.compile(
    r"^#\s*耗时\s*(?P<elapsed>[0-9.]+)s\s*｜\s*超时上限\s*(?P<timeout>[0-9.]+)s"
    r"\s*｜\s*退出码\s*(?P<code>-?[0-9]+)\s*$",
    re.MULTILINE,
)


@dataclasses.dataclass(frozen=True)
class Cell:
    """一个待取样单元格。

    `fixture_cases` 是**配额成本**的自变量（`13-F §2.6`：配额按"目标树下的项数"计，
    每例夹具 teardown ≈ **250 项**）⇒ `fixture_cases × 250` ≈ 本格一次的配额消耗。
    ★ 该数是**引用值**（出处见 `source`），会随用例增删而漂移；**引用时请重新量**。
    """

    name: str
    priority: str
    fixture_cases: int
    source: str
    note: str = ""
    #: 夹具用例数是否为**假设值**（未知批次用保守上界）⇒ 预检按"宁可高估"处理，且**标注**出来。
    assumed: bool = False
    #: **每例**的配额消耗（项）。默认 `QUOTA_PER_FIXTURE_CASE`（`code_root` 型重型夹具）；
    #: 轻量夹具（只建几个空目录）显式给更小的值 —— 用一个全局常量套所有夹具会把轻夹具**高估 25 倍**，
    #: 那是"假阻断"的配方（`G-61` 同族：判据与对象不同源）。
    quota_per_case: int = QUOTA_PER_FIXTURE_CASE

    @property
    def quota_per_run(self) -> int:
        """本格**一次**的配额消耗（≈项）。"""
        return self.fixture_cases * self.quota_per_case


#: 卡 `#83` 的取样清单 —— 机械抄自 `13-F 报告 §⑤` 的填表清单，**不自行增删**：
#: 「`evidence` · `daily` · `valuelayer` · `injection-a`…`f`；并**重测**
#:   `unit` / `guards` / `conflict` / `pricelayer`」
#:
#: ★★ 主理人已裁定**格数以「覆盖面」为准 = 13 格**，并**把 `injection-g` 并入为第 14 格**
#:   （它已有 1 次门禁读数 `15.37s/300s` ⇒ 只需补第 2 次）。**不删格**（`conflict` 保留）。
#:   理由（原样采纳）：**标题里的数字是"当初的计数"，清单是"覆盖面"；两者不一致时以覆盖面为准**。
SCHEDULED_CELLS: tuple[Cell, ...] = (
    # ---- P0：薄余量 / 读数从未取得（最需要复测）----
    Cell("valuelayer", "P0", 28, "13-F §3-4 表", "1.76× 薄余量；★ 带一条**可证预测**：修后应显著 < 170.15s"),
    Cell("evidence", "P0", 40, "13-F §3-4 表（轮换值）", "读数**从未取得**（13-F 撞配额）"),
    Cell("daily", "P0", 40, "13-F §3-4 表（轮换值）", "读数**从未取得**（13-F 撞配额）"),
    Cell("injection-c", "P0", 27, "V-02 批次表", "读数**从未取得**（V-02 标「未取得（配额触顶）」）"),
    Cell("injection-e", "P0", 27, "V-02 批次表", "读数**从未取得**（V-02 标「未取得（配额触顶）」）"),
    # ---- P1：已登记值待收紧 / 只需补第 2 次 ----
    Cell("unit", "P1", 13, "13-F §3-4 表", "合并前读数；13-F §④.2 明确要求**满负载**复测（现登记 300s）"),
    Cell("guards", "P1", 20, "13-F §3-4 表", "合并前读数（现登记 300s；主理人裁「纳入 #83 统一收紧」）"),
    Cell(
        "injection-g", "P1", 24, "taskbook 裁定：分片再平衡后 `f 27 / g 24`（≤32）",
        "★ 第 14 格（裁定并入）；**已有 1 次**门禁读数 `15.37s/300s`（余量 19.5×）⇒ 只需补第 2 次",
        assumed=True,
    ),
    Cell(
        "pricelayer", "P1", 100, "`ast` 实测（本单）：`tests/pricelayer/` 共 188 用例，其中 **100** 例带 `scratch`",
        "用例数已变（127 → 168 → 188）；★ 更正「0 夹具用例」（真值 **100**），"
        "但它是**轻量根**夹具 ⇒ 每例 ≈10 项而非 250 项 ⇒ 本格 ≈1,000 项/次，**仍然几乎不吃配额**",
        quota_per_case=PRICELAYER_QUOTA_PER_CASE,
    ),
    # ---- P2：有读数但为合并前 ----
    Cell("injection-a", "P2", 27, "V-02 批次表", "有读数（63.67s）但为**合并前**"),
    Cell("injection-b", "P2", 28, "V-02 批次表", "有读数（63.72s）但为**合并前**"),
    Cell("injection-d", "P2", 31, "V-02 批次表", "有读数（136.80s，2.2×）但为**合并前**"),
    Cell("injection-f", "P2", 31, "V-02 批次表", "有读数（110.13s，2.7×）但为**合并前**；#89 再平衡后 27 例"),
    # ---- P3：搭车末位 ----
    Cell("conflict", "P3", 0, "13-F §3-4 表",
         "**真 0 夹具用例**（主理人已核）；登记 30s 对旧读数 1.64/1.53s = 18.3×、**无余量风险** ⇒ "
         "批准为「搭车末位」（只吃墙钟、几乎不耗配额）"),
)


#: 未知批次的**保守**夹具用例数上界：取**重型夹具**（`code_root` 型）格里的最大值。
#: ★ 只看重型格：轻量夹具格的用例数（`pricelayer` 100）乘 `250` 会**高估 25 倍** ⇒
#:   那不是"保守"，是**另一个错误**（用错的系数）。未知批次按重型格的上界估。
#: ★ 这是**假设值**：配额预检**宁可高估**（高估 ⇒ 更容易拒绝开跑 ⇒ 不会盲跑）。
UNKNOWN_FIXTURE_CASES = max(
    c.fixture_cases for c in SCHEDULED_CELLS if c.quota_per_case == QUOTA_PER_FIXTURE_CASE
)

_BY_NAME = {c.name: c for c in SCHEDULED_CELLS}


def _cell_for(name: str) -> Cell:
    """把命令行给的批次名映射成 `Cell`；不在清单里 ⇒ 用**保守上界**并标 `assumed=True`。

    ★ 为什么不能默认 `fixture_cases=0`：那样配额预检会**放行**，等于把"未知成本"当成"零成本"，
    正是 `G-03` 禁止的"无被检对象当成已核"。宁可高估 ⇒ 该拒绝时拒绝。
    """
    if name in _BY_NAME:
        return _BY_NAME[name]
    return Cell(name, "手动", UNKNOWN_FIXTURE_CASES,
                f"（未知批次：按清单最大值 {UNKNOWN_FIXTURE_CASES} 例**保守上界**估计）", assumed=True)


def _main_sha(root: Path) -> str:
    """取 `refs/heads/main` 的 SHA —— 读数必须能与一个**确定的代码状态**对应。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "refs/heads/main"],
            cwd=str(root), capture_output=True, text=True, check=False,
        )
        return out.stdout.strip() or "unknown(rev-parse 无输出)"
    except OSError as exc:  # git 不在 PATH 等
        return f"unknown({exc.__class__.__name__})"


def _env_profile() -> dict[str, dict[str, str]]:
    """本轮的**被测配置**（守卫开关）—— 它是**仪器的一部分**，必须逐行记录。

    ★★ **主读数必须取「子进程实际拿到什么」，不是「我导出过什么」。**
    本仓 `verify.py::_child_env()` 自 `3653c7c`（`main@612cafe`）起**强制**把
    `CODEBUDDY_SAFE_DELETE_ENABLED` 等三道闸门置 `0`（`{**os.environ, …}` 覆盖在**后**）
    ⇒ **调用者 export 什么，批次都在 `E=0` 下跑**。

    ★ 我上一版只读调用者 env ⇒ 在 `3653c7c` 之后它变成**假阻断**
    （调用者 `E=1` 时会拒跑一个**本来是合法生产口径**的读数）。
    ★ 这正是 `G-61` 家族（**判据与对象不同源**）+ `V-11` **时间轴**：
    该结论在 `main@e9a009b` 为真、在 `main@612cafe` 为假 —— **所以必须同源取数**。
    故这里**直接调用被测程序自己的 `_child_env()`**（唯一真源），并同时记录调用者值以便对账。

    返回 `{"child": {...}, "caller": {...}}`；`child` = 子进程实际环境（定值只看它）。
    """
    child = _child_env()  # ★ 被测程序自己的真源，不复制那个字典
    return {
        "child": {k: child.get(k, "<unset>") for k in _PROFILE_KEYS},
        "caller": {k: os.environ.get(k, "<unset>") for k in _PROFILE_KEYS},
    }


def _profile_tag(env: dict[str, dict[str, str]]) -> str:
    """把**子进程实际环境**折成一个**可判定**的短标签：`E=0`（生产口径）/ `NON_E`（对照口径）。"""
    return "E=0(生产口径)" if env["child"]["CODEBUDDY_SAFE_DELETE_ENABLED"] == "0" else "NON_E(对照口径)"


def _fixture_mode(root: Path) -> str:
    """判定**夹具根**是否在**工作树内**（`V-02`：标定超时必须在工作树内测）。

    `root` 是 `verify.py` 的 `code_root`（= `<toplevel>/system`，与 `verify.py:114` 的 `ROOT` 同源）。

    ★ 主理人裁定：**`#83` 不得在 `/tmp` 夹具模式下取样** —— `/tmp` 方案只解决 `G-60` 配额，
    但 `Batch.timeout` 对应的是**仓库内夹具**的耗时；换位置 ⇒ **读数与生产口径不可比**。

    返回 `"repo-internal"`（唯一可用于定值的值）或**带原因的**其它字符串
    （★ 不返回 `None`/`False` —— 静默的"假"和"没查"不可区分，同 `_read_log_header` 的既有教训）。

    ★ 本函数首版把 `code_root` 直接与 `git rev-parse --show-toplevel` 比 ⇒
    `.../system` ≠ `.../<worktree>` ⇒ **恒假警报**（"判据与对象不同源"，`G-61` 同族）。
    正确形状是**包含**关系：`code_root == toplevel/"system"`。
    """
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(root), capture_output=True, text=True, check=False,
        )
    except OSError as exc:  # git 不在 PATH 等
        return f"git_unavailable({exc.__class__.__name__})"
    if top.returncode != 0:
        return f"not_a_git_worktree(exit={top.returncode}):{top.stderr.strip()[:80]}"
    toplevel = Path(top.stdout.strip()).resolve()
    s = str(toplevel)
    if s.startswith("/tmp") or s.startswith("/private/tmp"):
        return f"tmp-copy:{s} ⇒ ★ 不得据以定值（读数与生产口径不可比）"
    if root.resolve() != (toplevel / "system"):
        return (f"unexpected_layout:code_root={root.resolve()} toplevel={toplevel} ⇒ "
                f"不是「<仓库根>/system」的形状，读数与生产口径不可比")
    if not (root / "tests" / "conftest.py").exists():
        return f"no_tests_conftest:{root} ⇒ 不像是本仓的 system/"
    return "repo-internal"


def _concurrency() -> int:
    """并发流数（**代用指标**）：`ps` 里含 `pytest` 或 `scripts/ops/verify.py` 的进程数。

    `ps` 不可用时返回 **`-1`**（**可见哨兵**，不是静默的 `0` —— `0` 会被读成"确实没有并发"）。
    """
    try:
        out = subprocess.run(["ps", "-Ao", "command"], capture_output=True, text=True, check=False)
    except OSError:
        return -1
    n = 0
    for line in out.stdout.splitlines():
        if "pytest" in line or "scripts/ops/verify.py" in line:
            if line.strip().startswith("ps "):
                continue
            n += 1
    return n


def _quota_state() -> dict[str, int] | str:
    """**只读**宿主 safe-delete 状态 ⇒ 当前 request 的删除计数（**不删任何东西**）。

    这是 `13-F §⑥-7` 的"不需要删除即可查"的诊断。★ 但**它的读数不可复现**（本单实测：
    同一 `rid` 在 T1 读作 `99998`、T2 数分钟后**已不在 `requests` 表里**）⇒
    **只能当瞬时的旁证，不能当判决**；可靠的信号是运行中出现的 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`。
    详见模块 docstring 的「能力边界」一节。

    返回 `{"used", "threshold", "remaining"}`；不可用时返回**原因字符串**
    （★ 不返回 `None` —— `no_placeholder_guard.py::SWALLOW_EXCEPTION_CONTINUE` 已在本文件
    抓过一次"静默吞异常"，不得重蹈）。
    """
    missing = [k for k in _QUOTA_ENV_KEYS if k not in os.environ]
    if missing:
        return f"env_missing:{','.join(missing)}"
    state_dir = Path(os.environ["CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR"])
    sid = os.environ["CODEBUDDY_SESSION_ID"]
    rid = os.environ["CODEBUDDY_CONVERSATION_REQUEST_ID"]
    try:
        threshold = int(os.environ["CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD"])
    except ValueError as exc:
        return f"threshold_not_int({exc.__class__.__name__})"
    state_file = state_dir / hashlib.sha256(sid.encode()).hexdigest() / "state.json"
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except OSError as exc:
        return f"state_unreadable({exc.__class__.__name__}):{state_file.name}"
    except ValueError as exc:
        return f"state_not_json({exc.__class__.__name__}):{state_file.name}"
    used = int(data.get("requests", {}).get(rid, {}).get("count", 0))
    return {"used": used, "threshold": threshold, "remaining": threshold - used}


def _read_log_header(root: Path, name: str) -> tuple[float, float, int] | str:
    """从 `verify.py` 的日志头部取 `(elapsed, timeout, 退出码)`。

    ★ **取不到时不返回 `None`，而是返回「原因字符串」** ——
    `no_placeholder_guard.py` 的 `SWALLOW_EXCEPTION_CONTINUE` 判据**当场抓过这一处**
    （初版写 `except OSError: return None`），抓得对：**静默吞掉失败**会让"日志缺失"与
    "日志正常但没解析到"在调用方看来一模一样。故失败也**必须携带原因**并进入输出数据
    （同 `scripts/daily/coverage.py:145` 记录的既有做法）。

    ★ 这也是**旁证式二次读取**：主读数是 `verify.py` 的 stdout。两者**不一致时两者都报**，
    不去"挑一个信"。
    """
    log = root / "reports" / f"verify_{name}_latest.log"
    if not log.exists():
        return f"no_log:{log.name}"
    try:
        text = log.read_text(encoding="utf-8")
    except OSError as exc:
        return f"log_unreadable({exc.__class__.__name__}):{log.name}"
    m = _LOG_HEADER.search(text)
    if not m:
        return f"log_header_unparsable:{log.name}"
    return float(m.group("elapsed")), float(m.group("timeout")), int(m.group("code"))


def sample_one(name: str, repeat: int, root: Path, preflight: str, profile: str) -> tuple[list[dict], str]:
    """对单个批次取样 `repeat` 次。

    返回 `(rows, stop_reason)`；`stop_reason` 非空 ⇒ **整轮取样必须停止**（不重试）。
    `preflight` 是开跑前的配额预检结论，`profile` 是本轮的被测配置标签 ——
    两者都**原样写进每一行**（读数必须能自证当时的条件，否则不同条件下的数会被当成同一条序列）。
    """
    rows: list[dict] = []
    for run in range(1, repeat + 1):
        before = _concurrency()
        started = dt.datetime.now().astimezone()
        # ★ 每次都现取（而不是每格一次）：配置是**被测对象**的一部分，取一次就假设它不变。
        env_now = _env_profile()
        proc = subprocess.run(
            [sys.executable, "scripts/ops/verify.py", "--batch", name],
            cwd=str(root), capture_output=True, text=True, check=False,
        )
        verify_exit = proc.returncode          # ★ 不经管道（口径 22）
        blob = proc.stdout + proc.stderr
        quota = (QUOTA_MARKER in blob) or (QUOTA_PHRASE in blob)
        timed_out = (TIMEOUT_MARKER in blob) or (verify_exit == TIMEOUT_EXIT)
        input_error = "INPUT-ERROR" in blob
        # ★ `_read_log_header` 取不到时返回**原因字符串**（不是 None）⇒ 这里显式分流，
        #   两者都进输出（`log_header` 是三元组或 None，`log_header_note` 是原因）。
        raw_header = _read_log_header(root, name)
        header = None if isinstance(raw_header, str) else raw_header
        header_note = raw_header if isinstance(raw_header, str) else ""

        # 从 `verify.py` 的 stdout 抠出这一批的读数行：`[<名>] … exit=<pytest 码>  <s>/<s>s …`
        elapsed = timeout = None
        pytest_exit = None
        m = re.search(
            r"\[" + re.escape(name) + r"\][^\n]*?exit=(-?[0-9]+)\s+([0-9.]+)s/([0-9.]+)s",
            blob,
        )
        if m:
            pytest_exit = int(m.group(1))
            elapsed = float(m.group(2))
            timeout = float(m.group(3))

        rows.append({
            "batch": name,
            "run": run,
            "started_at_local": started.isoformat(timespec="seconds"),
            "started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "main_sha": _main_sha(root),
            # ★★ 「被测配置」也是仪器的一部分（口径 21 延伸）⇒ 逐行记录，不靠上下文记性。
            #    `env_child` = 子进程**实际**环境（定值只看它）；`env_caller` 只作对账。
            "env_profile": profile,
            "env_child": env_now["child"],
            "env_caller": env_now["caller"],
            "caller_forced_by_child_env": env_now["child"] != env_now["caller"],
            "fixture_mode": _fixture_mode(root),
            "concurrency_before": before,
            "concurrency_after": _concurrency(),
            "elapsed_s": elapsed,                      # ★ 门禁口径
            "timeout_s": timeout,                      # ★ 门禁口径
            "pytest_exit": pytest_exit,
            "verify_exit": verify_exit,                # ★ 不经管道
            "log_header": header,
            "log_header_note": header_note,
            "log_disagrees_with_stdout": bool(
                header is not None and elapsed is not None and abs(header[0] - elapsed) > 0.005
            ),
            "quota_polluted": quota,
            "quota_preflight": preflight,
            "timeout_hit": timed_out,
            "input_error": input_error,
            "verdict": (
                "QUOTA" if quota
                else "TIMEOUT" if timed_out
                else "INPUT_ERROR" if input_error
                else "OK" if verify_exit == 0
                else f"EXIT_{verify_exit}"
            ),
        })

        # 停手条件（三条都**不重试**：重试只会浪费一个轮次，并把已测数据搅脏）
        if quota:
            return rows, "QUOTA：宿主单轮删除配额已用完（count 与上轮相近）⇒ 换轮次，不重试"
        if timed_out:
            return rows, f"TIMEOUT：本格撞满超时（{timeout}s）⇒ 按 V-03 当「该批坏了」处理，**不要**先加超时"
        if input_error:
            return rows, "INPUT_ERROR：批次名或输入不合法 ⇒ 先修输入，别取样"
    return rows, ""


def _render(rows: list[dict], stop_reason: str) -> str:
    lines: list[str] = []
    if not rows:
        # ★ 没有读数时**也必须把拒绝原因打出来** —— 否则"预检拒绝"与"跑完没结果"在输出上
        #   完全一样（这就是本仓一直在消灭的静默形态）。
        lines.append("（本轮没有任何读数）")
        if stop_reason:
            lines.append("")
            lines.append(f"★ **未开跑** —— {stop_reason}")
        return "\n".join(lines)
    lines.append("| # | 批次 | run | 门禁口径 elapsed/timeout | pytest 退出码 | verify 退出码 | 并发(前/后) | G-60 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        el = "—" if r["elapsed_s"] is None else f'{r["elapsed_s"]:.2f}s/{r["timeout_s"]:.0f}s'
        lines.append(
            f'| {i} | `{r["batch"]}` | {r["run"]} | {el} | {r["pytest_exit"]} | '
            f'{r["verify_exit"]} | {r["concurrency_before"]}/{r["concurrency_after"]} | '
            f'{"★污染" if r["quota_polluted"] else "无"} | {r["verdict"]} |'
        )
    if stop_reason:
        lines.append("")
        lines.append(f"★ **已停止整轮取样** —— {stop_reason}")
    lines.append("")
    lines.append(f"main SHA: `{rows[0]['main_sha']}` ｜ 首格时刻: {rows[0]['started_at_local']}")
    # ★ 仪器条件的"抬头"必须跟读数**同框**打印：读数脱离配置就没有可比性（口径 21 延伸）。
    prof = rows[0]["env_profile"]
    lines.append(f"被测配置（仪器）: **`{prof}`** ｜ 夹具模式: `{rows[0]['fixture_mode']}`"
                 f"（逐行同值，已在 JSON 里逐行记录）")
    if prof != "E=0(生产口径)":
        lines.append("★★ **本表不是生产/门禁口径的读数** ⇒ **不得据以给 `Batch.timeout` 定值**"
                     "（只能当「守卫开」的对照；守卫开时夹具 teardown 实测慢约 30×）。")
    return "\n".join(lines)


def _print_plan(cells: tuple[Cell, ...], repeat: int) -> None:
    total_quota = 0
    print("## 取样计划（`--plan`：**不执行任何批次**）")
    print()
    print("| 优先级 | 批次 | 登记超时（★ 真源 `BATCHES`） | 夹具用例（引用值） | 项/例 | 本格一次 ≈配额项 | 理由 |")
    print("|---|---|---|---|---|---|---|")
    for c in cells:
        timeout = BATCHES[c.name].timeout if c.name in BATCHES else None
        t = "—" if timeout is None else f"{timeout:.0f}s"
        cost = c.quota_per_run
        total_quota += cost * repeat
        cases = f"{c.fixture_cases}" + ("（假设）" if c.assumed else "")
        print(f"| {c.priority} | `{c.name}` | {t} | {cases} | {c.quota_per_case} | ≈{cost:,} | {c.note} |")
    print()
    print(f"- 单元格数：**{len(cells)}** ｜ 每格重复：**{repeat}** 次 ⇒ 共 **{len(cells) * repeat}** 次批次运行")
    print(f"- ★ 估算总配额消耗：**≈{total_quota:,} 项**"
          f"（= Σ 夹具用例 × 每例项数 × {repeat}；重型夹具的 `250` 出处 `13-F §2.6`）")
    print("- ★ **该估算必须与「全流共享的回合级配额」比**（本会话实测阈值 `99,999`）⇒"
          " 一轮**装不下**，须跨多轮并与其它流**互斥**（卡 `13-M` 不得并发跑批）。")
    print("- ★ 夹具用例数与「项/例」都是**引用值**（出处见 `source`），会随用例增删与夹具形状漂移 ⇒ 用前请重新量。")
    st = _quota_state()
    if isinstance(st, str):
        print(f"- ⚠ **本回合余量读不到**（{st}）⇒ 开工前预检会**拒绝开跑**（不盲跑）。")
    else:
        print(f"- ★ **当前余量（瞬读，可能不成立）**："
              f"`used={st['used']} / threshold={st['threshold']}` ⇒ **余量={st['remaining']}**"
              f"（只读诊断，`13-F §⑥-7`）")
    # ★ 零成本地暴露"这一轮到底算不算生产口径"——否则要到跑完才发现仪器不对。
    # ★★ 读数取**子进程实际环境**（同源），并把调用者值并列 —— 两者不同时读者必须看得见。
    env = _env_profile()
    print(f"- ★ **本轮被测配置（子进程实际）**：`{_profile_tag(env)}`"
          f"（`E={env['child']['CODEBUDDY_SAFE_DELETE_ENABLED']}`）"
          f" ｜ **夹具模式**：`{_fixture_mode(ROOT)}`")
    if env["child"] != env["caller"]:
        print(f"  - 调用者 env 与子进程 env **不同**（`E`: "
              f"caller `{env['caller']['CODEBUDDY_SAFE_DELETE_ENABLED']}` → "
              f"child `{env['child']['CODEBUDDY_SAFE_DELETE_ENABLED']}`；"
              f"`verify.py::_child_env()` 强制置 0）⇒ **以子进程为准**。")
    if _profile_tag(env) != "E=0(生产口径)":
        print("  ★★ 该配置**不是**生产/门禁口径 ⇒ 默认**拒绝开跑**"
              "（对照用 `--profile-baseline`，读数会逐行标注且**不得据以定值**）。")


def _quota_gate(cell: Cell, repeat: int, skip: bool) -> str:
    """开跑**前**的配额预检：返回空串 = 放行；非空 = **保守拒绝**的原因。

    ★ **这是"保守建议"，不是判决**：该读数**不可复现**（见 `_quota_state` 与模块 docstring）。
    故拒绝时**必须**把"读数可能不成立 + 怎么显式覆盖"一起打出来 —— 否则它会变成一个
    **假阻断**（`G-61` 那种"判据与对象不同源"的错误，换成配额版本）。
    覆盖方式：`--no-quota-check`（读数会如实标注 `skipped`，**不得**当成"预检通过"）。
    """
    if skip:
        return ""
    st = _quota_state()
    if isinstance(st, str):
        return f"QUOTA_PREFLIGHT_UNAVAILABLE：{st} ⇒ 不得盲跑"
    need = cell.quota_per_run * repeat
    if st["remaining"] < need:
        return (f"QUOTA_PREFLIGHT_FAIL（**保守建议，非判决**）：瞬读余量 {st['remaining']} "
                f"< 本格所需 ≈{need}（= {cell.fixture_cases} 例 × {cell.quota_per_case} 项/例 "
                f"× {repeat}） ⇒ 建议**换轮次**（不重试、不降 `repeat`、不拿旧值代替）。"
                f"★ 该读数是**瞬读、可能不成立**（本单实测同一 rid 数分钟后从 `99998` 变为"
                f"**不在表里**）；若你确知环境已变，用 `--no-quota-check` 显式覆盖"
                f"（读数会如实标注 `skipped`，**不得**当成「预检通过」）")
    return ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="按门禁口径取样批次耗时（只取样，不改登记值）")
    ap.add_argument("--batch", action="append", default=[], help="批次名（可重复）")
    ap.add_argument("--scheduled", action="store_true", help="跑卡 #83 的取样清单")
    ap.add_argument("--repeat", type=int, default=2, help="每格重复次数（默认 2；口径 21：单次不足）")
    ap.add_argument("--max-cells", type=int, default=0, help="本轮最多跑几格（0 = 不限）")
    ap.add_argument("--plan", action="store_true", help="只打印计划，**不执行**任何批次")
    ap.add_argument("--quota", action="store_true", help="只读诊断本回合删除配额余量（**不删任何东西**）")
    ap.add_argument("--no-quota-check", action="store_true",
                    help="跳过开工前配额预检（★ 仅当宿主未注入诊断所需环境变量时用；"
                         "读数会如实标注为 skipped，**不得**当成「预检通过」）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--profile-baseline", action="store_true",
                    help="★ 允许在**非生产口径**（`E` 未关 ⇒ 守卫开）下取样，只作**对照**；"
                         "读数会逐行标注 `NON_E`，**不得据以给 `Batch.timeout` 定值**")
    args = ap.parse_args(argv)

    if args.quota:
        st = _quota_state()
        if isinstance(st, str):
            print(f"配额诊断**不可用**：{st}")
            return 2
        print(f"本 conversation request: used={st['used']} threshold={st['threshold']} "
              f"余量={st['remaining']}")
        print("（只读诊断，出处 `13-F §⑥-7`；此命令**不含任何删除**）")
        return 0

    if args.repeat < 2:
        print("★ 警告：`--repeat < 2` 与 `口径 21` 冲突（单次门禁读数不足以定值；"
              "实测同一守卫有 ≈2.9× 波动）——读数仍会打印，但**不得**据以定值。", file=sys.stderr)

    cells = SCHEDULED_CELLS if args.scheduled else tuple(_cell_for(n) for n in args.batch)
    if args.max_cells > 0:
        cells = cells[: args.max_cells]

    if args.plan or not cells:
        _print_plan(cells or SCHEDULED_CELLS, args.repeat)
        return 0

    if args.no_quota_check:
        print("★ 已显式跳过配额预检（`--no-quota-check`）—— 读数里会如实标注 `skipped`，"
              "**不得**把它当成「预检通过」。", file=sys.stderr)

    # ★★ 两条**仪器**前置（口径 21 延伸：仪器不止测量工具，还包括**被测量的配置**）。
    #    这两条检查**必须在跑任何批次之前**做 —— 跑完才发现仪器不对，那一轮的配额就白烧了。
    fmode = _fixture_mode(ROOT)
    if fmode != "repo-internal":
        print(f"★ 拒绝开跑：**夹具模式不可用于定值** —— `{fmode}`", file=sys.stderr)
        print("  硬规则（主理人裁定）：`#83` **不得在 `/tmp` 夹具模式下取样** —— "
              "`Batch.timeout` 对应的是**仓库内夹具**的耗时，换位置即与生产口径不可比。"
              "（本规则**不提供覆盖开关**。）", file=sys.stderr)
        return 2

    env = _env_profile()
    profile = _profile_tag(env)
    if profile != "E=0(生产口径)" and not args.profile_baseline:
        print(f"★ 拒绝开跑：**本轮不是生产/门禁口径** —— 子进程实际配置 `{profile}`"
              f"（`_child_env()['CODEBUDDY_SAFE_DELETE_ENABLED']="
              f"{env['child']['CODEBUDDY_SAFE_DELETE_ENABLED']}`）。", file=sys.stderr)
        print("  裁定：`#83` **应在 `E`（`CODEBUDDY_SAFE_DELETE_ENABLED=0`）下取样** —— "
              "那是 CI/门禁的配置；守卫开时夹具 teardown 实测慢约 **30×**（`58s → 2s`）⇒ "
              "两者**不可混比**（`口径 21`）。", file=sys.stderr)
        print("  说明：判据取自**被测程序自己的** `verify.py::_child_env()`（同源），不是调用者的 shell env。"
              "确要一份**对照**用 `--profile-baseline`（读数会逐行标注 `NON_E`，**不得据以定值**）。",
              file=sys.stderr)
        return 2
    if profile != "E=0(生产口径)":
        print(f"★★ 已显式采用**对照口径** `{profile}` —— 本轮读数**不得**用来给 "
              "`Batch.timeout` 定值（只能回答「守卫开时慢多少」）。", file=sys.stderr)
    elif env["child"] != env["caller"]:
        # ★ 这行不是噪音：它把「调用者 export 了什么」与「批次实际在什么下跑」分开，
        #   两者不同时**读数仍然合法**（以子进程为准），但读者必须知道这件事。
        print(f"★ 调用者 env 与子进程 env **不同**（以子进程为准 = `E=0` 生产口径）："
              f"caller `E={env['caller']['CODEBUDDY_SAFE_DELETE_ENABLED']}` → "
              f"child `E={env['child']['CODEBUDDY_SAFE_DELETE_ENABLED']}`"
              f"（`verify.py::_child_env()` 强制置 0）⇒ 读数**不因此失效**，但已逐行记录。",
              file=sys.stderr)

    all_rows: list[dict] = []
    stop_reason = ""
    for c in cells:
        if c.name not in BATCHES:
            print(f"★ 跳过 `{c.name}`：不在 `BATCHES` 里（超时真源无此批）", file=sys.stderr)
            continue
        if c.assumed:
            print(f"★ `{c.name}` 的夹具用例数是**假设值 {c.fixture_cases}**（清单里没有它）"
                  f"⇒ 预检按**上界**估计；跑之前请把真实值补进 `SCHEDULED_CELLS`。", file=sys.stderr)
        # ★ 每一格开跑**前**都重新预检（配额是**消耗型**的：跑了前几格，后面的余量会变小）
        gate = _quota_gate(c, args.repeat, args.no_quota_check)
        if gate:
            stop_reason = f"{c.name} → {gate}"
            break
        rows, reason = sample_one(c.name, args.repeat, ROOT,
                                  "skipped(--no-quota-check)" if args.no_quota_check else "ok",
                                  profile)
        all_rows.extend(rows)
        if reason:
            stop_reason = f"{c.name} → {reason}"
            break

    if args.json:
        print(json.dumps({"rows": all_rows, "stop_reason": stop_reason}, ensure_ascii=False, indent=2))
    else:
        print(_render(all_rows, stop_reason))
    # 退出码（`G-01`）：一轮都没开跑（预检拒绝）⇒ `2`（输入/环境异常，不是"测出问题"）；
    # 跑过之后因 `G-60` / 超时停下 ⇒ `1`（阻断）；全部跑完 ⇒ `0`。
    if stop_reason and not all_rows:
        return 2
    return 0 if not stop_reason else 1


if __name__ == "__main__":
    raise SystemExit(main())
