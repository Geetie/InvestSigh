"""`ingest_step.py` —— step 1 `ingest_public_information` 的步进处理器。

权威声明：`rules/pipeline.yaml::steps[1]`（**0444 锁定，属设计真相源，不可改**）——
`implemented_in_first_version: true`、`blocking: true`、**无 hook**。故编排器
（`scripts/orchestrate/pipeline.py`）必须**默认注册**本处理器，使 `Pipeline.run_daily`
开箱即跑 step 1（否则"编排器能真干活"不成立，`G-13`）。

数据流（`Ch9 §3.4.6` 措施①·载体侧）：

    待采集外部文本（`raw/inbox/`） → `scripts.guard.executor.process_raw_file`
        ├─ 文本落 `raw/`
        └─ 主张落 `facts/claims.jsonl`

★ **采集入口的接缝（不是临时手段）**：本处理器默认从 `raw/inbox/` 读取**待采集外部文本**。
  `raw/inbox/` 是"外部文本进入本系统"的**投递口**；阶段② 的真实连接器（公开 API / 抓取器）
  只需把采集到的文本**投递到同一投递口**，本处理器与执行链路（`scripts.guard.executor`）
  **保持不变** —— 亦即：接缝在**投递侧**，不在**处理侧**。
  （`rules/pipeline.yaml` 只声明 step 1 存在，不规定采集实现方式；替换来源 = 替换投递侧。）

★ 空样本（无 `raw/inbox/` 目录、或无待采集文件）→ 返回 `degraded=True` 且 `produced` 为空：
  **不得**静默当成功，也**不得**凭空生成数据。

★ `signals_emitted` 恒为 0：step 1 只做"信息入库"，**不产生交易信号**
  （信号由 step 6 的建议产生，`Ch1 §D.3` 反 KPI：每日维护 ≠ 每日产信号）。

★ 五类时间语义（`Ch9 §2.2` / `§3.4.1`）在**采集层显式赋值**（`seed_industry_nodes.py` 为正确范例）：

  - **system_time**（永不未知 → **不得为 None**）：
    `first_seen_at` = `analyzed_at` = 本次处理时刻（UTC）；
    `recorded_seq` = 从 `facts/claims.jsonl` 现有最大 `recorded_seq` **递增**
    （追加式不可变真源据此区分同一业务键的版本，`Ch9 §3.4.1`；**不得**恒为 1）。
  - **valid_time**（来源未披露时保持 None 合法）：
    `occurred_at` 仅当投递文件名带 ISO 日期前缀（`YYYY-MM-DD…`）时取其日期，否则 None；
    `published_at` / `effective_from` 本层无从取得 → None（在报告中说明）。
  - **backfill**：资料日期（`occurred_at`）早于补入日 → `backfilled_at` = 补入日
    （显式标记"事后补入"，防"事后信息伪装成当时已知"，`Ch9 §N9.1-31/32`）。
  - **`locator`**：给出可定位信息（指向 `raw/<file>` 的行区间）；来源确无可定位信息时
    **显式记"未披露"**，**不得**留空字符串（`Ch9 §3.4.6` 措施①/②：含定位、可复查）。
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.guard.executor import STATUS_OK, STATUS_SKIPPED, process_raw_file  # noqa: E402
from scripts.orchestrate.pipeline import StepOutcome  # noqa: E402
from schema.models import ClaimForm, ClaimNature, SourceTier  # noqa: E402
from schema.store import read_records  # noqa: E402

INBOX_RELPATH = "raw/inbox"
"""采集入口的**投递口**（相对 `system/`）。阶段② 真实连接器把外部文本投递到此。"""

# ── 采集入口的**缺省标注**（接缝：阶段② 连接器按来源逐条给出真实标注）──────────────
#
# 缺省取最保守的一档：来源分级 `secondary_tertiary`（二三手）、性质 `interpretation`（解释性）、
# 形式 `opinion`（观点）—— 即"未核实的二手材料"。**不**据文件名/内容猜测升级（`Ch6 §C.1`）。
DEFAULT_SOURCE_TIER = SourceTier.secondary_tertiary
DEFAULT_CLAIM_NATURE = ClaimNature.interpretation
DEFAULT_CLAIM_FORM = ClaimForm.opinion

LOCATOR_UNDISCLOSED = "未披露（来源未提供可定位信息）"
"""来源确无可定位信息时的**显式**取值（`Ch9 §3.4.6`：不得留空字符串）。"""

_ISO_DATE_PREFIX_LEN = 10
"""ISO 日期前缀长度（`YYYY-MM-DD`）—— 采集接缝的文件命名约定，`occurred_at` 的唯一来源。"""


def _code_root() -> Path:
    """本处理器**自身**所属的代码工程根（`system/`）。

    ★ 它只是**缺省回落**，不是权威来源 —— 权威来源是**编排器绑定的 `root`**。
      见 `make_ingest_handler` 与缺陷 `G-RC-05`。
    """
    return _ROOT


def make_ingest_handler(root: str | Path) -> Callable[[date, str], "StepOutcome"]:
    """构造 step 1 处理器，**把 `root` 绑定进去**（与 `compute` / `decision` 的
    `make_*_handler(root)` 同一范式）。

    ★ 为什么必须有这个工厂（缺陷 `G-RC-05`，实测**真源被污染**）：
      `StepHandler = Callable[[date, str], StepOutcome]` —— **签名里根本没有 root**。
      原先把裸函数直接注册进编排器，于是处理器只能从**自身模块位置**（`Path(__file__)`）
      解析路径。后果：**任何拿副本 `code_root` 调用 `run_daily` 的测试都会写进真仓库真源**。
      实测：`tests/injection/test_chain_steps_wiring.py` 跑 11 次 `run_daily`，
      在真 `system/facts/claims.jsonl` 里追加了 **12 行重复 claim**（`recorded_seq` 6–17）。

      → 这与 `P7-2`（`run_decide` 忽略传入的 `root`）**是同一类缺陷**，
        但更隐蔽：那里是"参数被忽略"，这里是"**参数根本不存在**"。
    """
    root_path = Path(root)

    def handler(run_date: date, scope: str) -> StepOutcome:
        return ingest_public_information(run_date, scope, root=root_path)

    handler.__name__ = "ingest_public_information_bound"
    handler.__doc__ = f"step 1 处理器（已绑定 root={root_path}）"
    return handler


def _inbox_files(root: Path) -> list[Path]:
    """列出投递口下**待采集**的常规文本文件（跳过点文件与子目录），按名排序保证可复现。"""
    inbox = root / INBOX_RELPATH
    if not inbox.is_dir():
        return []
    return sorted(
        (p for p in inbox.iterdir() if p.is_file() and not p.name.startswith(".")),
        key=lambda p: p.name,
    )


def _source_id(path: Path) -> str:
    """由投递文件名派生的**缺省**来源标识（接缝：阶段② 连接器提供真实 `source_id`）。"""
    return f"inbox-{path.name}"


def _process_now() -> datetime:
    """本次处理时刻（UTC，与 `seed_industry_nodes.py` 同源约定）。

    system_time（`first_seen_at` / `analyzed_at`）由此派生 —— **永远可知**，不得为 None。
    """
    return datetime.now(timezone.utc)


def _next_recorded_seq(root: Path) -> int:
    """`facts/claims.jsonl` 现有最大 `recorded_seq` **+ 1**（**不得**恒为 1）。

    追加式不可变真源以 `recorded_seq` 区分同一业务键的版本（`Ch9 §3.4.1`）：
    每次进货取当前最大者加一，使"按业务键取 recorded_seq 最大"的判据可用。
    """
    numeric = [
        row.get("recorded_seq")
        for row in read_records(root, "claims")
        if isinstance(row.get("recorded_seq"), int)
    ]
    return (max(numeric) if numeric else 0) + 1


def _occurred_at_from_name(name: str) -> datetime | None:
    """投递文件名带 ISO 日期前缀（`YYYY-MM-DD…`）→ 取其日期为有效时间 `occurred_at`。

    仅作**确定性**命名约定解析（文件名 → 业务日期）；无该前缀、或前缀日期非法
    （如 `2026-13-40`）→ 返回 None（来源未披露明确业务日期 → 保持 None **合法**，
    **不猜测**，`Ch9 §2.2`）。
    """
    prefix = name[:_ISO_DATE_PREFIX_LEN]
    if len(prefix) != _ISO_DATE_PREFIX_LEN or prefix[4] != "-" or prefix[7] != "-":
        return None
    if not (prefix[:4] + prefix[5:7] + prefix[8:10]).isdigit():
        return None
    parsed = None
    try:
        parsed = datetime(
            int(prefix[:4]), int(prefix[5:7]), int(prefix[8:10]), tzinfo=timezone.utc
        )
    except ValueError:
        # 形如 YYYY-MM-DD 但月/日越界 → 回退为 None（视为来源未披露），不猜测
        parsed = None
    return parsed


def _locator(raw_name: str, text: str) -> str:
    """可定位信息：指向 `raw/` 落点与**行区间**；无内容可定位 → 显式"未披露"（不留空串）。"""
    line_count = len(text.splitlines())
    if line_count <= 0:
        return LOCATOR_UNDISCLOSED
    return f"raw/{raw_name}#L1-L{line_count}"


def _read_text_for_locator(path: Path) -> str:
    """读投递文本以给 `locator` 计算行区间；读取/解码失败 → `""`（交由执行器统一降级）。

    ★ **不**在此处吞错并当成功：本函数仅用于 `locator` 的行数估计；真正落库/降级由
      `process_raw_file`（`A-1`/`A-5` 后的明确降级）负责，两处不重复判定写入结果。
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return ""


def ingest_public_information(
    run_date: date, scope: str, *, root: str | Path | None = None
) -> StepOutcome:
    """step 1：把投递口的外部文本经**执行器**摄入（文本落 `raw/`、主张落 `facts/claims.jsonl`）。

    - 逐个 `process_raw_file(...)`（**复用**执行器，不另写一条写库路径）；
    - 每文件在**采集层**赋五类时间（`Ch9 §2.2`）：system_time 三元组显式传入（不得为 None），
      valid_time/backfill 按命名约定/比对派生（取不到保持 None）；
    - 有文件被摄入 → `produced` = **本轮真正新写入**的各置 claim 的 `claim_id`（**对象引用**）；
    - **行幂等命中**（同源同 `quote_hash` 的 claim 已入库，`Ch9 §3.5` 阶段②）→ 执行器返回
      `status="skipped"`：**不是降级**（重跑同日不重复落库是**设计行为**，`Ch9 §N9.2-11`），
      故不置 `degraded`；命中对象走**独立的 `skipped` 列表**（`StepOutcome.skipped`）——
      `produced` **只记本轮新写入**，命中**不得**折进 `produced`（否则"幂等重跑"与"首跑"
      的 `produced` 观测量相同，`G-B10-07` 要暴露的信号会被重新掩盖；`tests/compute/
      test_step_wiring.py` 已把 `produced` 钉死为"本轮真正新写入"）。
      `G1-05` 的「空执行」判据为 `produced` 与 `skipped` **双空**才违例，故命中不会误报。
    - 任一文件未落库（`blocked` / `degraded`）→ 本步 `degraded=True`（显式，不静默略过）；
    - 无待采集文件 → `produced=[]` + `degraded=True`（空样本，**不得**当成功）。

    ★ `run_date` / `scope` 由编排器传入；step 1 的采集语义**逐文件独立**，不据日期/范围筛选
      （范围筛选属阶段② 采集层，见模块 docstring「接缝」）。
    ★ `root` **必须**由调用方（编排器）绑定 —— 见 `make_ingest_handler` 与缺陷 `G-RC-05`：
      缺省回落 `_code_root()`（模块自身位置）**只对"在真仓库上直接调用"成立**，
      在**副本 `code_root`**（测试 / 多 root）场景下会**写错地方**。
    """
    root = Path(root) if root is not None else _code_root()
    candidates = _inbox_files(root)
    produced: list[str] = []
    skipped: list[str] = []
    degraded = False
    processed_at = _process_now()
    for path in candidates:
        relpath = path.relative_to(root).as_posix()
        name = path.name
        text = _read_text_for_locator(path)
        occurred_at = _occurred_at_from_name(name)
        backfilled_at = (
            processed_at
            if occurred_at is not None and occurred_at.date() < processed_at.date()
            else None
        )
        result = process_raw_file(
            root,
            relpath,
            source_id=_source_id(path),
            claim_nature=DEFAULT_CLAIM_NATURE,
            claim_form=DEFAULT_CLAIM_FORM,
            tier=DEFAULT_SOURCE_TIER,
            first_seen_at=processed_at,
            analyzed_at=processed_at,
            recorded_seq=_next_recorded_seq(root),
            locator=_locator(name, text),
            occurred_at=occurred_at,
            published_at=None,
            effective_from=None,
            backfilled_at=backfilled_at,
        )
        if result.status == STATUS_OK and result.claim_id:
            produced.append(result.claim_id)
        elif result.status == STATUS_SKIPPED and result.claim_id:
            # 行幂等命中（同源同 quote_hash 的 claim 已入库）：**跳过重复落库**（`Ch9 §3.5` 阶段②）。
            # 这不是降级 —— 重跑同日不重复落库是设计行为（`Ch9 §N9.2-11`）。
            # ★ 命中对象走**独立的 `skipped` 列表**，**不得**折进 `produced`：
            #   `produced` 的语义是"本轮真正新写入的集合"（`tests/compute/test_step_wiring.py`
            #   已钉死）；若命中折进 `produced`，"首跑"与"幂等重跑"的 `produced` 相同
            #   → `G-B10-07` 要暴露的信号被重新掩盖。`G1-05` 判据为 `produced`/`skipped`
            #   双空才违例，故命中仍不会误报"空执行"。
            skipped.append(result.claim_id)
        else:
            # 显式降级：该文件未落库（blocked / degraded）—— 不得静默略过。
            degraded = True
    if not candidates:
        # 空样本：投递口为空 → 显式降级，不得当成功。
        degraded = True
    return StepOutcome(produced=produced, skipped=skipped, degraded=degraded, signals_emitted=0)
