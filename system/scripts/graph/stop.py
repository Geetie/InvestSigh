"""`stop.py` —— 传导**停止判定**（7 条件）与**累计放大上限**（`Ch7 §C.2 / §C.5 / §C.6`）。

> 模型 vs 程序的边界（`Ch7 §C.2` 逐字）：**模型只负责抽取字段**；`should_stop` 与其
> 7 个条件全部落在**结构化字段**上，由程序判定。**模型不决定停不停**（承 N9.2-03）。

7 个条件（`Ch7 §C.2` 顺序，各配单测）：

| # | 条件 | 动作 |
|---|---|---|
| ① | 依据门槛 `evidence_gate` | `stop` + `mark=evidence_insufficient` |
| ② | 经济重要性阈值 | `stop`（除非 `unknown_but_important`） |
| ③ | 环（`node_key` 已在路径上） | `stop` + `effect=record_cycle` |
| ④ | 正向力量 > 反向力量 | `stop` + `mark=direction_doubtful` |
| ⑤ | 纯重复证据 | `stop` |
| ⑥ | 终端需求已计 | `stop` + `effect=allocate` |
| ⑦ | 累计放大超上限 | `stop` + `effect=decay` |

★ **纪律 1（零新增门槛；参数不进决策函数）**：本模块**不内置任何阈值** ——
  `TransmitParams` 的字段**全部必填**，由调用方显式传入，或经 `load_transmit_params()`
  从 `rules/transmission.yaml`（唯一真源，值待冻结）读取。**代码路径确定，值可切换。**
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

#: `gain_map` 中"未披露幅度"须使用的**保守值**键（`Ch7 §J5`：未披露用保守值，不点估计）。
GAIN_KEY_UNDISCLOSED = "undisclosed"

TRANSMISSION_CONFIG_RELPATH = "rules/transmission.yaml"


@dataclass(frozen=True)
class TransmitParams:
    """传导参数（唯一真源 = `rules/transmission.yaml`，`Ch7 §C.5`）。

    **全部字段必填**：本模块不自带任何阈值默认值 —— 这落实"零新增门槛、参数不进决策函数"。
    """

    importance_threshold: float
    amplification_cap: float
    gain_map: dict[str, float]
    max_depth: int


@dataclass(frozen=True)
class Hop:
    """一跳的**结构化字段**（模型抽取的结果，程序据此判定，`Ch7 §C.2`）。"""

    node_key: str
    relation_id: str | None
    evidence_claim_ids: tuple[str, ...] = ()
    variable: str | None = None
    direction: Literal["+", "-", "0", "unknown"] = "unknown"
    conditions: tuple[str, ...] = ()
    target_type: str = ""
    location: str | None = None
    supply_mode: str | None = None
    procurement_link: str | None = None
    importance: float = 0.0
    unknown_but_important: bool = False
    forward_forces: float = 0.0
    counter_forces: float = 0.0
    terminal_demand_id: str | None = None
    evidence: tuple[str, ...] = ()
    gain_key: str = GAIN_KEY_UNDISCLOSED


@dataclass
class PathState:
    """一条传导路径的累积状态（`Ch7 §C.2`）。"""

    visited: tuple[str, ...] = ()
    upstream_evidence: frozenset[str] = frozenset()
    counted_terminals: frozenset[str] = frozenset()
    cumulative_amplification: float = 1.0


@dataclass(frozen=True)
class StopDecision:
    """停止判定结果（`Ch7 §C.2`）。"""

    action: Literal["continue", "stop"]
    reason: str | None = None
    mark: str | None = None
    effect: str | None = None


# ───────────────────────── 7 条件各自的判据（纯函数） ─────────────────────────

def evidence_gate(hop: Hop, params: TransmitParams) -> bool:
    """① 依据门槛（`Ch7 §C.6` 形式化）。

    基础四要素：关系 id 非空 + 证据 ≥1 + 变量非空 + 方向 ∈ {+,-,0,unknown} + 条件非空。
    目标为**具体经营实体**时，额外要求 `location / supply_mode / procurement_link`
    **至少一项非空** —— 否则该跳不成立（电力公司那一跳的验收点）。
    """
    base = (
        hop.relation_id is not None
        and len(hop.evidence_claim_ids) >= 1
        and hop.variable is not None
        and hop.direction in {"+", "-", "0", "unknown"}
        and bool(hop.conditions)
    )
    if hop.target_type == "specific_operating_entity":
        base = base and bool(hop.location or hop.supply_mode or hop.procurement_link)
    return base


def importance(hop: Hop) -> float:
    """② 经济重要性（由字段直接给值，不做二次加工）。"""
    return hop.importance


def forward_gt_counter(hop: Hop) -> bool:
    """④ 正向力量 > 反向力量（严格大于）。"""
    return hop.forward_forces > hop.counter_forces


def evidence_subset(hop: Hop, upstream: frozenset[str]) -> bool:
    """⑤ 纯重复证据：本跳证据**非空**且**全部**已在路径上游出现。"""
    current = set(hop.evidence)
    return bool(current) and current.issubset(upstream)


def gain(hop: Hop, params: TransmitParams) -> float:
    """该跳的**有界传导增益**（由幅度 / 份额映射；未披露用**保守值**，`Ch7 §C.5` / `J5`）。"""
    if hop.gain_key in params.gain_map:
        return float(params.gain_map[hop.gain_key])
    if GAIN_KEY_UNDISCLOSED not in params.gain_map:
        raise KeyError(
            f"gain_map 缺少保守键 {GAIN_KEY_UNDISCLOSED!r}（未披露幅度必须用保守值，Ch7 §J5）"
        )
    return float(params.gain_map[GAIN_KEY_UNDISCLOSED])


def cumulative_amplification(
    previous: float, hop: Hop, params: TransmitParams
) -> float:
    """路径累计放大 = `previous × gain(hop)`（沿路径逐跳累乘，`Ch7 §C.5`）。"""
    return previous * gain(hop, params)


def should_stop(hop: Hop, path: PathState, params: TransmitParams) -> StopDecision:
    """7 条件逐条判定（`Ch7 §C.2`）。**顺序即优先级**，命中即停。"""
    if not evidence_gate(hop, params):                                    # ① 依据门槛
        return StopDecision("stop", "evidence_insufficient", mark="evidence_insufficient")
    if importance(hop) < params.importance_threshold and not hop.unknown_but_important:
        return StopDecision("stop", "low_importance")                     # ② 重要性阈值
    if hop.node_key in path.visited:                                      # ③ 环
        return StopDecision("stop", "cycle", effect="record_cycle")
    if not forward_gt_counter(hop):                                       # ④ 正向>反向
        return StopDecision("stop", "direction_doubtful", mark="direction_doubtful")
    if evidence_subset(hop, path.upstream_evidence):                      # ⑤ 纯重复证据
        return StopDecision("stop", "duplicate_evidence")
    if hop.terminal_demand_id is not None and hop.terminal_demand_id in path.counted_terminals:
        return StopDecision("stop", "terminal_demand_dup", effect="allocate")  # ⑥ 终端已计
    if cumulative_amplification(path.cumulative_amplification, hop, params) > params.amplification_cap:
        return StopDecision("stop", "amplification_capped", effect="decay")    # ⑦ 累计上限
    return StopDecision("continue")


def load_transmit_params(root: str | Path) -> TransmitParams:
    """从 `rules/transmission.yaml`（唯一真源）读阈值（`Ch7 §C.5`）。

    配置读取走 `scripts._common._cached_yaml()`（`CONVENTIONS.md §三 P-02`：带 mtime/size 缓存）。
    文件缺失 / 缺键 → **响亮失败**（不静默兜底）—— 该文件由主理人在集成时提供，
    值随第十一章 `p04` 相关参数一并冻结。
    """
    from scripts._common import _cached_yaml

    path = Path(root) / TRANSMISSION_CONFIG_RELPATH
    if not path.exists():
        raise FileNotFoundError(
            f"缺少传导参数真源: {path}（唯一真源，值待冻结；不得在代码里内置阈值）"
        )
    doc: dict[str, Any] = _cached_yaml(path)
    required = ("importance_threshold", "amplification_cap", "gain_map", "max_depth")
    missing = [k for k in required if k not in doc]
    if missing:
        raise ValueError(f"{TRANSMISSION_CONFIG_RELPATH} 缺字段: {missing}")
    return TransmitParams(
        importance_threshold=float(doc["importance_threshold"]),
        amplification_cap=float(doc["amplification_cap"]),
        gain_map={str(k): float(v) for k, v in dict(doc["gain_map"]).items()},
        max_depth=int(doc["max_depth"]),
    )
