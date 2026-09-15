"""`rules/freeze.yaml::freeze_param` 的**唯一读口**（`Ch11 §D.2` / §C / §E.1 / §F.1）。

设计要点（逐条对应设计文档）：

1. **唯一真源**：参数值只从 `rules/freeze.yaml` 读；其余配置（`rules/schedule.yaml`、
   `rules/data-sources.allowlist.yaml`、`rules/benchmark.yaml`、`rules/scope.yaml`、
   `rules/notification.yaml`、`rules/publish.yaml`）只**指针**、不双写（`Ch11 §D.2`）。
2. **`tbd` 是唯一合法占位**（`00_开发Agent开工提示词 §6.1`）：
   参数值可以不确定，**代码路径必须确定**。
   `freeze_status == "tbd"` 时返回值 = `suggested_value`（基线建议值），
   并以 `value_source = "suggested_baseline"` 显式标注**它不是已冻结值**；
   若连 `suggested_value` 都没有 → 抛 `ParamValueUnavailable`（**不静默返回 None / 0**）。
3. **决策作用域隔离**：本模块**不得**被 `scripts/decision/**` 或 `scripts/graph/**` 引用
   （`Ch11 §E.1` / `Ch2 §B.3` Checker-1 排除项）。
4. **锚点纪律**：`blocking_targets` 一律节号锚点（形如 `Ch10 §N10.3-04`），禁绝对行号（纪律 6）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from .rules import load_yaml

FREEZE_PATH = "rules/freeze.yaml"

# 节号锚点形如 `Ch2 §D.1` / `Ch10 §N10.3-04` / `Ch9 §3.4.2` / `Ch8 §C8-1`
# / `Ch9 §张力 C5` / `Ch8 §K ③` / `Ch9 §3.10 J3`——一律"ChN §<非空后缀>"。
_ANCHOR_RE = re.compile(r"^Ch\d+\s*§\S.*$")
# 绝对行号的形态（纪律 6 真正要拦的东西）
_LINE_NUMBER_RE = re.compile(r"(第\s*\d+\s*行|L\d+\b|\bline\s*\d+|:\d+\s*$)", re.IGNORECASE)

# 禁词（red line 一：借参数补门槛）由 rules/banned_tokens.yaml 提供，
# **不新立禁词**（Ch11 §G：「复用 Ch2 §B.2 禁词表」）。


class UnknownParamError(KeyError):
    """未知 `param_id` —— **响亮失败**，不返回兜底值。"""


class ParamValueUnavailable(RuntimeError):
    """参数既未冻结、又无 `suggested_value` —— 明确失败（不静默返回 None / 0）。"""


class NewGateError(RuntimeError):
    """参数被补成了新的策略门槛 —— 红线一（`Ch11 §E.1`）。"""


class AnchorFormatError(ValueError):
    """`blocking_targets` 含绝对行号 —— 违反纪律 6。"""


@dataclass(frozen=True)
class ParamResolution:
    """一次参数解析的完整结果。**带来源标注**，使"值从哪来"可审计。"""

    param_id: str
    param: str
    freeze_status: str                     # tbd / frozen
    effective_value: Any                   # 冻结值（frozen）或建议基线值（tbd）
    value_source: str                      # "frozen" | "suggested_baseline"
    param_tier: str
    decision_owner: str
    option_set: list[dict[str, Any]] = field(default_factory=list)
    blocking_targets: list[str] = field(default_factory=list)

    @property
    def is_frozen(self) -> bool:
        return self.freeze_status == "frozen"

    def as_dict(self) -> dict[str, Any]:
        return {
            "param_id": self.param_id,
            "param": self.param,
            "freeze_status": self.freeze_status,
            "effective_value": self.effective_value,
            "value_source": self.value_source,
            "param_tier": self.param_tier,
            "decision_owner": self.decision_owner,
        }


def load_freeze(root: str | Any | None = None) -> dict[str, Any]:
    """读 `rules/freeze.yaml` 全文。缺失/空 → **响亮失败**。"""
    return load_yaml(FREEZE_PATH, root)


def _index(freeze_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    params = freeze_doc.get("freeze_params")
    if not isinstance(params, list) or not params:
        raise ValueError(f"{FREEZE_PATH} 缺少 freeze_params 列表")
    out: dict[str, dict[str, Any]] = {}
    for row in params:
        pid = row.get("param_id")
        if not pid:
            raise ValueError(f"{FREEZE_PATH} 存在缺 param_id 的项: {row!r}")
        if pid in out:
            raise ValueError(f"{FREEZE_PATH} 中 param_id 重复: {pid}")
        out[pid] = row
    return out


def get_param(param_id: str, root: str | Any | None = None) -> ParamResolution:
    """**唯一参数读口**。`param_id ∈ {p01..p11}`。

    - `freeze_status == "frozen"` → `effective_value` = 冻结值，`value_source = "frozen"`
    - `freeze_status == "tbd"`    → `effective_value` = `suggested_value`（**基线建议值**），
      `value_source = "suggested_baseline"`（显式标注"这不是已冻结值"）
    - 两者皆无 → `ParamValueUnavailable`（**不静默返回 None / 0**）
    - `param_id` 不存在 → `UnknownParamError`
    """
    doc = load_freeze(root)
    rows = _index(doc)
    if param_id not in rows:
        raise UnknownParamError(
            f"未知 param_id: {param_id!r}；合法值: {sorted(rows)}（{FREEZE_PATH}）"
        )
    row = rows[param_id]
    status = row.get("freeze_status")
    if status not in ("tbd", "frozen"):
        raise ValueError(f"{param_id}: freeze_status 非法取值 {status!r}（只允许 tbd / frozen）")

    if status == "frozen":
        if "value" not in row:
            raise ParamValueUnavailable(
                f"{param_id}: freeze_status=frozen 但缺少 value（冻结必须原子携带 value）"
            )
        value, source = row["value"], "frozen"
    else:
        if "suggested_value" not in row:
            raise ParamValueUnavailable(
                f"{param_id}: freeze_status=tbd 且无 suggested_value —— "
                f"参数值不可用；请需求方拍板或实现方补基线建议值（不静默返回 None/0）"
            )
        value, source = row["suggested_value"], "suggested_baseline"

    return ParamResolution(
        param_id=param_id,
        param=row.get("param", ""),
        freeze_status=status,
        effective_value=value,
        value_source=source,
        param_tier=row.get("param_tier", ""),
        decision_owner=row.get("decision_owner", ""),
        option_set=list(row.get("option_set") or []),
        blocking_targets=list(row.get("blocking_targets") or []),
    )


def get_param_value(param_id: str, root: str | Any | None = None) -> Any:
    """便利函数：只要值（仍走同一读口，**不绕过** `get_param`）。"""
    return get_param(param_id, root).effective_value


def iter_params(root: str | Any | None = None) -> Iterator[ParamResolution]:
    """按 `param_id` 字典序遍历全 11 项（排序统一走字典序，**无 `weight`/`score`** — P-09）。"""
    doc = load_freeze(root)
    for pid in sorted(_index(doc)):
        yield get_param(pid, root)


# ───────────────────────── 守卫实现（供 scripts/checks/freeze_guard.py 调用） ─────────────────────────

def _banned_tokens(root: str | Any | None = None) -> set[str]:
    """复用 Ch2 §B.2 禁词表（**不新立禁词**，`Ch11 §G`）。"""
    doc = load_yaml("rules/banned_tokens.yaml", root)
    return {t["token"] for t in doc.get("tokens", [])}


def assert_no_new_gate(root: str | Any | None = None) -> None:
    """红线一：**不得把待定项补成新的策略门槛**（`Ch11 §E.1` / N11.2-12 / 源稿第 386 行）。

    ① 参数名 / 建议值中的**键名**不得命中 Ch2 §B.2 禁词；
       值**文本**只在"它们是禁词本身作为标识符出现"时才算命中——散文说明（`basis` / `impact_note`）
       允许提到禁词（否则无法解释为什么禁止它）。
    ② 参数**不得进决策函数** —— 由 `scripts/checks/freeze_guard.py` 的 AST 断言承载。
    """
    doc = load_freeze(root)
    banned = _banned_tokens(root)
    hits: list[str] = []
    for row in doc["freeze_params"]:
        # 只检查"会变成标识符"的位置：param 名、option_set/suggested_value 的**键名**
        surfaces: list[str] = [str(row.get("param", ""))]
        for container in ("option_set", "suggested_value"):
            node = row.get(container)
            if isinstance(node, list):
                for item in node:
                    surfaces.extend(_identifier_keys(item))
            else:
                surfaces.extend(_identifier_keys(node))
        hit = sorted({s for s in surfaces if s in banned})
        if hit:
            hits.append(f"{row.get('param_id')} → {hit}")
    if hits:
        raise NewGateError(
            "借参数补门槛（红线一，Ch11 §E.1）：" + "; ".join(hits)
        )


def _identifier_keys(node: Any) -> list[str]:
    """取可当标识符的位置：mapping 的**键名**；字符串值只有当它是单个 token 时才算。"""
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            out.append(str(k))
            out.extend(_identifier_keys(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_identifier_keys(v))
    elif isinstance(node, str):
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", node):
            out.append(node)
    return out


def assert_anchor_only(root: str | Any | None = None) -> None:
    """G11-05：`blocking_targets` 一律**节号锚点**，禁绝对行号（纪律 6）。

    合法形态：`ChN §<非空后缀>`，后缀允许中文/符号/空格
    （如 `Ch9 §张力 C5`、`Ch8 §K ③`、`Ch9 §3.10 J3`、`Ch10 §N10.3-04`）。
    非法形态：不含 `ChN §` 前缀；或形如 `第 570 行` / `L344` / `line 570` / 以 `:123` 结尾。
    """
    doc = load_freeze(root)
    bad: list[str] = []
    for row in doc["freeze_params"]:
        for anchor in row.get("blocking_targets") or []:
            text = str(anchor)
            if not _ANCHOR_RE.match(text) or _LINE_NUMBER_RE.search(text):
                bad.append(f"{row.get('param_id')}: {text!r}")
    if bad:
        raise AnchorFormatError(
            "blocking_targets 必须是节号锚点（形如 `Ch10 §N10.3-04`），禁绝对行号："
            + "; ".join(bad)
        )
