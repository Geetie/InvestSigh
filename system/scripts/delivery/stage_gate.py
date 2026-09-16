#!/usr/bin/env python3
"""`stage_gate.py` —— **阶段判据守卫**（`Ch11 §B` / §G G11-04 / 纪律 12）。

```
python system/scripts/delivery/stage_gate.py [code_root] [--stage prep|nvidia_sample|core_chain|daily_run|expansion|all]
```

★ 纪律 3（`00_交付施工图 §0 第 3 条`）：**阶段未过即阻塞** ——
  每阶段通过判据未过 → **不出该阶段交付物，不得静默跳过**。
★ 退出码：0 通过 / 1 阶段阻塞 / 2 输入异常。

判据可执行化（逐条对齐 `00_交付施工图 §2` 各阶段的"通过判据（可执行）"伪码）：

| 阶段 | 判据 |
|---|---|
| ① prep | 四类交付物齐备 + 「已确认规则 vs 建议实现方式」显式区分（可逐条指认）+ 口径 `tbd` 占位 + 首版无付费必需项 |
| ② nvidia_sample | 六步链完整 + 证据可定位 + 推导可复查（coverage == 1.0）+ Ch4 §G 深度 |
| ③ core_chain | 多公司传导跑通 + **T01–T14 全过**（`10/01 §2.1`）+ 图谱/提问任务可追溯 |
| ④ daily_run | 时点可核 + 覆盖可核 + 任务状态可核 + 降级保留上次有效结果 |
| ⑤ expansion | 研究标准一致（Ch4 §G）+ 结果可核验 + 复盘 append-only |
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._common import CheckReport, Violation, run_checker  # noqa: E402

STAGES = ("prep", "nvidia_sample", "core_chain", "daily_run", "expansion")

DELIVERABLES_FILE = "registry/prep_deliverables.yaml"
FREEZE_FILE = "rules/freeze.yaml"
LAUNCH_FILE = "registry/launch_criteria.yaml"
DELIVERY_FILE = "registry/delivery.yaml"

# ───────────── 判据绑定：**由函数体自己声明**，不靠任何手写清单 ─────────────
#
# 背景（第二轮独立审计抓到的 P0）：初版用一张手写集合 `IMPLEMENTED_CRITERIA`
# 记载"哪些判据实现了"。审计员只用**一行数据编辑**（往集合里塞两个 id）
# 就让"从未实现的 `t01_t14_all_pass`"判成 PASS —— 集合与函数体**零绑定**，
# 它只是"把声明从 YAML 复制到了 Python"。
#
# 现改为**机械绑定**：
#   ① 每条判据必须在对应 `stage_*_passed()` 函数体内出现一次
#      `criterion("<stage_key>", "<criterion_id>", v)` 调用（字面量）
#   ② `bound_criteria()` 用 **AST 扫本文件自身** 抽出这些字面量
#   ③ `assert_criteria_implemented()` 比对"YAML 声明为 automated 的"与"函数体里真的有的"
#
# 于是"伪造实现"不再是改一行数据，而必须往**被审计的那个函数体**里加一行 ——
# 且加了之后它是可读、可审的代码。同时禁止用 `check_kind: manual` 把判据自行降级。
CRITERION_STAGE_FUNC: dict[str, str] = {
    "prep": "stage_prep_passed",
    "nvidia_sample": "stage_nvidia_sample_passed",
    "core_chain": "stage_core_chain_passed",
    "daily_run": "stage_daily_run_passed",
    "expansion": "stage_expansion_passed",
}

_SELF_PATH = Path(__file__)


def criterion(stage_key: str, criterion_id: str, violations: list[Violation]) -> list[Violation]:
    """在 `stage_*_passed()` 内声明"本阶段**真的检查了**某条判据"。

    本函数**不做检查**——它的唯一作用是让该判据 id 以**字面量**出现在函数体里，
    供 `bound_criteria()` 通过 AST 抽取。真正的检查由调用点上方/下方的代码完成。
    """
    return violations


def bound_criteria() -> dict[str, set[str]]:
    """AST 扫本文件，抽出每个 `stage_*_passed()` **函数体内**声明的判据 id。

    ★ 必须按**函数**归属：只看整文件里出现过某字符串是不够的
      （那样在任何地方写一个无关字符串就能冒充实现）。
    """
    import ast

    func_to_stage = {fn: key for key, fn in CRITERION_STAGE_FUNC.items()}
    tree = ast.parse(_SELF_PATH.read_text(encoding="utf-8"), filename=str(_SELF_PATH))
    out: dict[str, set[str]] = {key: set() for key in CRITERION_STAGE_FUNC}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in func_to_stage:
            continue
        key = func_to_stage[node.name]
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call) or getattr(sub.func, "id", None) != "criterion":
                continue
            args = sub.args
            if len(args) < 2:
                continue
            stage_lit, id_lit = args[0], args[1]
            if not (isinstance(stage_lit, ast.Constant) and isinstance(id_lit, ast.Constant)):
                continue
            if stage_lit.value == key:
                out[key].add(str(id_lit.value))
    return out


def load_delivery(root: Path) -> dict[str, Any]:
    import yaml

    return yaml.safe_load((root / DELIVERY_FILE).read_text(encoding="utf-8"))


def declared_criteria(root: Path) -> dict[str, list[dict[str, Any]]]:
    """阶段 key → 声明的通过判据列表（来自 `registry/delivery.yaml`）。"""
    out: dict[str, list[dict[str, Any]]] = {}
    for stage in load_delivery(root).get("delivery_stages") or []:
        out[str(stage.get("key"))] = list(stage.get("pass_criteria_testable") or [])
    return out


def criteria_not_implemented(root: Path, stage_key: str) -> list[str]:
    """返回"声明为 automated 但**函数体里没有对应 `criterion()` 声明**"的判据 id。

    判据 id 与声明的对应关系由 YAML 给；是否实现由 **AST** 判。
    两侧都在同一份代码里、但**必须同时对得上**才放行。
    """
    bound = bound_criteria().get(stage_key, set())
    missing: list[str] = []
    for crit in declared_criteria(root).get(stage_key) or []:
        if "automated" not in str(crit.get("check_kind", "")):
            continue
        cid = str(crit.get("id"))
        if cid not in bound:
            missing.append(cid)
    return sorted(missing)


def assert_criteria_implemented(root: Path, stage_key: str) -> list[Violation]:
    """把"判据绑定"变成**可执行断言**（前置产物齐备时调用）。

    两条断言：
    A. **判据不得自行降级**：`pass_criteria_testable` 每条都必须含 `automated`
       （初版可把 `automated` 改成 `manual` 一个词即绕过 —— 审计反例 D4）。
    B. **声明必须绑函数体**：YAML 声明为 automated 的每条，都必须在对应
       `stage_*_passed()` 函数体内有一处 `criterion(...)` 字面量声明
       （初版可往手写集合塞 id 即绕过 —— 审计反例 D3）。
    """
    v: list[Violation] = []
    for crit in declared_criteria(root).get(stage_key) or []:
        if "automated" not in str(crit.get("check_kind", "")):
            v.append(
                Violation(
                    "G11-04",
                    f"阶段 {stage_key} 的判据 {crit.get('id')!r} 的 check_kind="
                    f"{crit.get('check_kind')!r} —— 通过判据**不得**降级为非自动检查"
                    "（`施工图 §2` 要求「通过判据（可执行）」）",
                    DELIVERY_FILE,
                )
            )
    bound = bound_criteria().get(stage_key, set())
    for cid in criteria_not_implemented(root, stage_key):
        v.append(
            Violation(
                "G11-04",
                f"阶段 {stage_key} 的判据 {cid!r} 已在 {DELIVERY_FILE} 声明为 automated，"
                f"但 {CRITERION_STAGE_FUNC[stage_key]}() 函数体内无对应 criterion() 声明 "
                "→ **不得据此判 PASS**（静默漏判据）",
                f"scripts/delivery/stage_gate.py::{CRITERION_STAGE_FUNC[stage_key]}",
            )
        )
    # 反向：函数体声明了、YAML 里却没有 → 声明与实现脱节（同样要报）
    declared_ids = {
        str(c.get("id")) for c in (declared_criteria(root).get(stage_key) or [])
    }
    for extra in sorted(bound - declared_ids):
        v.append(
            Violation(
                "G11-04",
                f"{CRITERION_STAGE_FUNC[stage_key]}() 声明了判据 {extra!r}，"
                f"但 {DELIVERY_FILE} 未登记 → 声明与实现脱节",
                DELIVERY_FILE,
            )
        )
    return v

FOUR_DELIVERABLE_CLASSES = (
    "the_document_itself",
    "first_batch_relations_checklist",
    "public_data_registration",
    "benchmark_and_key_calibers",
)
VALID_LAYERS = ("confirmed_rule", "implementation_proposal")

# ── 六阶段流程固化（`施工图 §3.3` / `Ch9 §3.5`，名字逐字有出处，零发明）──
# 每个 SKILL.md 是**模块 I/O 契约的载体**，所以判据不只是"文件在",
# 还必须含 ① I/O 契约出处锚点 ② 幂等键 —— 否则它是文档，不是契约。
SKILL_NAMES = (
    "aichain-claim-extract",
    "aichain-price-expectation",
    "aichain-valuation-baseline",
    "aichain-ask",
    "aichain-daily",
    "aichain-delivery",
)
SKILLS_DIR = "skills"
SKILL_IO_ANCHOR = "Ch9 §3.5"


# ───────────────────────────────── 阶段① prep ─────────────────────────────────

def has_all_four_deliverables(cfg: Mapping[str, Any]) -> list[Violation]:
    """四类交付物齐备（`Ch11 §B` 阶段① 逐字）。"""
    v: list[Violation] = []
    items = list(cfg.get("deliverables") or [])
    got = {i.get("deliverable_class") for i in items}
    if len(items) != 4:
        v.append(Violation("prep", f"交付物项数应为 4，实为 {len(items)}", DELIVERABLES_FILE))
    for cls in FOUR_DELIVERABLE_CLASSES:
        if cls not in got:
            v.append(Violation("prep", f"缺交付物类别: {cls}", DELIVERABLES_FILE))
    for item in items:
        if not item.get("artifact"):
            v.append(
                Violation("prep", f"{item.get('deliverable_id')} 未标明落位 artifact", DELIVERABLES_FILE)
            )
    return v


def rules_and_impl_explicitly_separated(root: Path, cfg: Mapping[str, Any]) -> list[Violation]:
    """「已确认规则 vs 建议实现方式」**有显式区分**，且**可逐条指认**（`Ch11 §B`）。

    四层断言：
    ① 每个交付物项都带 `layer ∈ {confirmed_rule, implementation_proposal}`；
    ② `confirmed_rules` 与 `implementation_proposals` **两层均非空**（不能只做一层）；
    ③ 每条 `confirmed_rule` **必有设计锚点**（节号锚点）与实现载体 —— 否则"确认"无出处；
    ④ ★ **载体必须真实存在**（第二轮独立审计反例 E）：初版只断言
       `implementation_carrier` 是**非空字符串**，于是把它改成
       `scripts/does_not_exist/nowhere_guard.py` 阶段① 仍然 PASS ——
       "声明了载体"与"载体存在"是两件事，前者不蕴含后者。
    """
    v: list[Violation] = []
    for item in cfg.get("deliverables") or []:
        if item.get("layer") not in VALID_LAYERS:
            v.append(
                Violation(
                    "prep",
                    f"{item.get('deliverable_id')}: layer={item.get('layer')!r} 非法（须 {VALID_LAYERS}）",
                    DELIVERABLES_FILE,
                )
            )

    confirmed = list(cfg.get("confirmed_rules") or [])
    proposed = list(cfg.get("implementation_proposals") or [])
    if not confirmed:
        v.append(Violation("prep", "confirmed_rules 为空：无「已确认规则」层", DELIVERABLES_FILE))
    if not proposed:
        v.append(
            Violation("prep", "implementation_proposals 为空：无「建议实现方式」层", DELIVERABLES_FILE)
        )

    for row in confirmed:
        rid = row.get("id", "<unnamed>")
        if row.get("layer") != "confirmed_rule":
            v.append(Violation("prep", f"{rid}: layer 必须为 confirmed_rule", DELIVERABLES_FILE))
        for field in ("design_anchor", "implementation_carrier", "statement"):
            if not str(row.get(field) or "").strip():
                v.append(
                    Violation("prep", f"{rid}: 已确认规则缺 {field}（不可逐条指认）", DELIVERABLES_FILE)
                )
        carrier = str(row.get("implementation_carrier") or "")
        if carrier.strip():
            v.extend(_carrier_exists(root, rid, carrier))
    for row in proposed:
        rid = row.get("id", "<unnamed>")
        if row.get("layer") != "implementation_proposal":
            v.append(
                Violation("prep", f"{rid}: layer 必须为 implementation_proposal", DELIVERABLES_FILE)
            )
        if not str(row.get("design_anchor") or "").strip():
            v.append(Violation("prep", f"{rid}: 建议实现方式缺 design_anchor", DELIVERABLES_FILE))
    return v


# 载体字符串里的路径形态（如 `schema/registry_models.py QualityLabel（…）`）
_CARRIER_PATH_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|yaml|yml|json|md)\b")


def _carrier_exists(root: Path, rule_id: str, carrier: str) -> list[Violation]:
    """载体字符串里出现的每个**仓库相对路径**都必须真实存在。

    宽容处：允许路径后跟类名 / 函数名 / 中文说明（如 `… .py QualityLabel（…）`）——
    只把**像路径的 token** 拿出来查存在性，不对载体格式提额外要求。
    一个都提取不到路径时**不报**（可能是纯描述，如"见 Ch2 §B.3"）。
    """
    out: list[Violation] = []
    for match in _CARRIER_PATH_RE.finditer(carrier):
        token = match.group(0)
        if (root / token).exists():
            continue
        out.append(
            Violation(
                "prep",
                f"{rule_id}: implementation_carrier 指向的文件不存在 → {token!r}"
                "（声明了载体 ≠ 载体存在；不得据非空字符串判 PASS）",
                DELIVERABLES_FILE,
            )
        )
    return out


def all_calibers_tbd(freeze_doc: Mapping[str, Any]) -> list[Violation]:
    """口径字段 `tbd` 占位（`Ch11 §B` 阶段① 判据 / §F.1 拍板前恒 tbd）。"""
    v: list[Violation] = []
    rows = list(freeze_doc.get("freeze_params") or [])
    if len(rows) != 11:
        v.append(
            Violation("prep", f"待冻结参数应为 11 项，实为 {len(rows)}", FREEZE_FILE)
        )
    for row in rows:
        pid = row.get("param_id", "<unknown>")
        status = row.get("freeze_status")
        if status == "tbd":
            continue
        if status == "frozen":
            missing = [k for k in ("confirmed_by", "confirmed_at", "version") if not row.get(k)]
            if missing:
                v.append(
                    Violation("prep", f"{pid}: frozen 但缺 {missing}（切换须原子）", FREEZE_FILE)
                )
            continue
        v.append(Violation("prep", f"{pid}: freeze_status 非法 {status!r}", FREEZE_FILE))
    return v


def no_paid_in_required(criteria: Mapping[str, Any]) -> list[Violation]:
    """首版启动条件不含付费订阅（`Ch11 §E.2` 红线二）。"""
    v: list[Violation] = []
    for c in criteria.get("required") or []:
        if isinstance(c, Mapping) and c.get("requires_paid_subscription") is True:
            v.append(
                Violation("prep", f"首版启动条件含付费订阅: {c.get('id')}", LAUNCH_FILE)
            )
    if not (criteria.get("required") or []):
        v.append(Violation("prep", "首版启动条件 required 为空（无从判定）", LAUNCH_FILE))
    return v


def skills_carry_io_contract(root: Path) -> list[Violation]:
    """六阶段流程固化：六个 `SKILL.md` 齐备，且各自**真的载了 I/O 契约**。

    `施工图 §3.3`：`skills/` 的定位是「**模块 I/O 契约的载体**」。
    所以只判"文件存在"是不够的（那只是文档）——还要求每个 SKILL.md：
    ① 引用 I/O 契约的唯一出处 `Ch9 §3.5`；② 写明幂等键。

    ★ 这条判据同时也是 `skills/` 的**接线**：没有它，`skills/` 就是一个
      没有任何读取方的孤儿目录（`§一 底线 2` 真接线）。
    """
    v: list[Violation] = []
    for name in SKILL_NAMES:
        rel = f"{SKILLS_DIR}/{name}/SKILL.md"
        path = root / SKILLS_DIR / name / "SKILL.md"
        if not path.exists():
            v.append(Violation("prep", f"缺 SKILL.md：{rel}（Ch9 §N9.2-09 模块 I/O 契约载体）", rel))
            continue
        text = path.read_text(encoding="utf-8")
        if SKILL_IO_ANCHOR not in text:
            v.append(Violation("prep", f"{rel} 未引用 I/O 契约出处 {SKILL_IO_ANCHOR}", rel))
        if "幂等键" not in text:
            v.append(Violation("prep", f"{rel} 未写明幂等键（模块契约要素缺失）", rel))
    return v


def stage_prep_passed(root: Path) -> tuple[bool, list[Violation], dict[str, int]]:
    """`00_交付施工图 §2 阶段①` 的可执行判据（逐条实现）。"""
    import yaml

    v: list[Violation] = []
    scanned: dict[str, int] = {}

    cfg = yaml.safe_load((root / DELIVERABLES_FILE).read_text(encoding="utf-8"))
    freeze_doc = yaml.safe_load((root / FREEZE_FILE).read_text(encoding="utf-8"))
    criteria = yaml.safe_load((root / LAUNCH_FILE).read_text(encoding="utf-8"))

    scanned["deliverables"] = len(cfg.get("deliverables") or [])
    scanned["confirmed_rules"] = len(cfg.get("confirmed_rules") or [])
    scanned["implementation_proposals"] = len(cfg.get("implementation_proposals") or [])
    scanned["freeze_params"] = len(freeze_doc.get("freeze_params") or [])
    scanned["skills"] = sum(
        1 for name in SKILL_NAMES if (root / SKILLS_DIR / name / "SKILL.md").exists()
    )

    v += has_all_four_deliverables(cfg)
    v += rules_and_impl_explicitly_separated(root, cfg)
    v += all_calibers_tbd(freeze_doc)
    v += no_paid_in_required(criteria)
    v += skills_carry_io_contract(root)
    scanned["declared_criteria"] = len(declared_criteria(root).get("prep") or [])
    scanned["criteria_not_implemented"] = len(criteria_not_implemented(root, "prep"))
    # 判据绑定声明（供 AST 抽取；见 `criterion()` 与 `bound_criteria()`）
    criterion("prep", "four_deliverables", v)
    criterion("prep", "rule_vs_impl_split", v)
    criterion("prep", "caliber_tbd_placeholder", v)
    criterion("prep", "no_paid_required", v)
    v += assert_criteria_implemented(root, "prep")
    return (not v), v, scanned


# ───────────────────── 阶段②–⑤：判据已就位，被测对象在后续阶段交付 ─────────────────────

def _deferred(stage: str, needed: str, anchor: str) -> tuple[bool, list[Violation], dict[str, int]]:
    """后续阶段的判据尚未有被检对象 —— **阶段阻塞**（不得静默跳过，纪律 12）。

    返回 `passed=False` 且带一条明确的"前置未满足"违例，**绝不返回 True 冒充通过**。
    """
    return (
        False,
        [
            Violation(
                "G11-04",
                f"阶段 {stage} 的前置产物尚不存在：{needed}（{anchor}）→ **阶段阻塞**，"
                "不得静默跳过；前置阶段通过后再评估",
                "scripts/delivery/stage_gate.py",
            )
        ],
        {"missing_precondition": 1},
    )


def stage_nvidia_sample_passed(root: Path) -> tuple[bool, list[Violation], dict[str, int]]:
    """六步判断链完整 + 证据可定位 + 推导可复查（`Ch11 §B` / `00_交付施工图 §2 阶段②`）。"""
    baselines = _read_jsonl(root / "facts" / "baselines.jsonl")
    if not baselines:
        return _deferred(
            "nvidia_sample", "facts/baselines.jsonl 中的 NVIDIA 研究基线", "Ch4 §G / Ch9 §3.3.3"
        )
    v: list[Violation] = []
    # 六步链（Ch1 §D 五问 + Ch10 §N1 六结果）：baseline 必须齐六项深度
    required = ("business_mechanism", "historical_numeric_claims", "driver_model", "value_state_refs")
    for row in baselines:
        missing = [f for f in required if not row.get(f)]
        if missing:
            v.append(
                Violation("nvidia_sample", f"{row.get('baseline_id')} 六项深度缺: {missing}", "facts/baselines.jsonl")
            )
    # 推导可复查：每条建议 traceback 覆盖率须为 1.0
    from scripts.trace.traceback import check as trace_check

    tr = trace_check(root)
    v += tr.violations
    criterion("nvidia_sample", "six_step_chain_complete", v)
    criterion("nvidia_sample", "derivation_reviewable", v)
    v += assert_criteria_implemented(root, "nvidia_sample")
    return (not v), v, {"baselines": len(baselines), **tr.scanned}


def stage_core_chain_passed(root: Path) -> tuple[bool, list[Violation], dict[str, int]]:
    """多公司传导跑通 + **T01–T14 全过**（唯一权威表 = `10/01 §2.1`）+ 图谱/提问任务可追溯。

    ★ **诚实声明**：本函数**已实现**的判据是 `multi_company_transmission`
      （关系图公司数 ≥ 2、影响六要素齐备）。`registry/delivery.yaml` 声明为
      automated 的 `t01_t14_all_pass` 与 `graph_and_ask_traceable`
      **尚未实现** —— 它们登记在 `IMPLEMENTED_CRITERIA` 之外，
      由 `assert_criteria_implemented()` 在**前置产物齐备时直接阻断本阶段**，
      并在报告里以 `criteria_not_implemented` 计数显式暴露。

      **绝不**把"声明了就算做到"：首次独立审计抓到的正是这条
      （当时 docstring 声称检查了 T01–T14，代码里根本没有）。
    """
    impacts = _read_jsonl(root / "facts" / "impacts.jsonl")
    relations = _read_jsonl(root / "facts" / "relations.jsonl")
    if not impacts or not relations:
        return _deferred(
            "core_chain",
            "facts/relations.jsonl 与 facts/impacts.jsonl 的真实关系与影响",
            "Ch7 §C.7 / Ch9 §N9.1-06~16",
        )
    v: list[Violation] = []
    companies = {r.get("object_id") for r in relations} | {r.get("subject_id") for r in relations}
    if len(companies) < 2:
        v.append(Violation("core_chain", f"关系图公司数 {len(companies)} < 2：无法构成多公司传导", "facts/relations.jsonl"))
    for row in impacts:
        missing = [f for f in ("conditions", "counter_forces", "time_lag") if not row.get(f)]
        if missing:
            v.append(
                Violation("core_chain", f"{row.get('impact_id')} 影响六要素缺: {missing}（缺条件则不成立）", "facts/impacts.jsonl")
            )
    criterion("core_chain", "multi_company_transmission", v)
    v += assert_criteria_implemented(root, "core_chain")
    return (not v), v, {"relations": len(relations), "impacts": len(impacts)}


def stage_daily_run_passed(root: Path) -> tuple[bool, list[Violation], dict[str, int]]:
    """时点可核 + **覆盖可核** + **任务状态可核** + **降级保留上次有效结果**（`Ch11 §B`）。

    ★ 四条判据**均已真接线**（不再是"只有声明、没有检查"）：

    | 判据 | 检查落点 |
    |---|---|
    | `timing_replayable` | 本函数内（每条 `check_record` 必须有 `run_date`） |
    | `task_state_auditable` | 本函数内（每条任务 `status` ∈ `TaskStatus`，缺口 `G9-1` 补） |
    | `degrade_keeps_last_valid` | 本函数内（失败行不得丢 `last_valid_result_ref`） |
    | `coverage_verifiable` | 复用 `scripts/daily/coverage.py`（`G-06`，不重造） |

    ★ `coverage_verifiable`（覆盖可核）**已在本函数内绑定**（批次 9 集成）：
      实现住 `scripts/daily/coverage.py`（`Ch3 §N3.2-03/04` 三分量分别可表达 + 深度四态可回退 +
      `10/01 §N10.1-06` 无静默遗漏 + `G-03` 非真空），本函数**复用**它，并调
      `criterion("daily_run", "coverage_verifiable", v)` 使其对本阶段的**门禁**生效。

    ★ **为什么必须绑**（否则判据形同虚设）：`registry/delivery.yaml` 声明它是 automated，
      而"声明"与"实现"必须有**机器绑定**（本项目的血泪铁律 5）——
      不绑的话，**覆盖不达标时阶段④门禁不会红**，等于判据没接。
      但**绑定只是必要条件**：绑定证明"接了"，**不证明"真的在查"**
      （把 `cv = coverage_check(root)` 换成空 `CheckReport`，`criteria_bound` 仍是 4
      而门禁对不达标数据变绿 —— 见 `tests/injection/test_criterion_effectiveness.py`
      ::test_daily_run_coverage_verifiable_counterexample_is_load_bearing 钉住的现象）。
      ⇒ 本阶段 4 条判据**各自**都有一条**可执行反例**登记在
        `registry/criterion_counterexamples.yaml`，并另有 `criterion_effectiveness_guard.py`
        强制"新绑判据必须登记反例"。

    ★ 「该行是否持有有效结果」的谓词**只有一份** —— 从 `scripts/daily/degrade` **import**
      （`G-45` 收口）。本模块**不再自持一套**：此前这里另写了一个 `_holds_valid_result()`
      （只认 `last_valid_result_ref` / `output_refs` 两个载体），而 `degrade.py` 认的是
      "一次成功的运行" ⇒ 同一批行两个模块给出**相反结论**（实测：`degrade` 说 'check_d1_full'
      有、`stage_gate` 说 False 无）。"上次有效结果"是**同一个业务概念**，
      必须与写路径（`pipeline._write_check_record` 复用 `degrade.last_valid_result_ref()`）
      同源，否则同一契约在三处各说各话。
    """
    from scripts.daily.degrade import holds_valid_result

    tasks = _read_jsonl(root / "facts" / "tasks.jsonl")
    check_records = [t.get("check_record") for t in tasks if t.get("check_record")]
    if not check_records:
        return _deferred("daily_run", "facts/tasks.jsonl 中的 check_record（每日运行记录）", "Ch1 §C.2 / Ch8 §C.2")
    v: list[Violation] = []
    # 「降级保留上次有效结果」（Ch8 §E.4）：失败任务必须保留上一次有效结果的引用，
    # **不得置 null、不得标最新**。
    #
    # ★ **首日豁免** —— 判据 = 「**该失败行之前，没有任何行持有有效结果**」。
    #
    #   需求来源（批次 10 审计 `G7`：两个口径打架）：
    #   `scripts/daily/degrade.py` 对首日降级行（`status=failed` 且 `last_valid_result_ref=None`）
    #   判 **0 违例**（依据 `G-03`：无上次有效结果时**如实为 None**，不得编一个）；
    #   而本函数原先**无条件**判 FATAL → 同一批行两个口径打架，且真仓库每次日更都会多一条红。
    #
    #   ★★ 为什么**不**用"run_date 最早" —— 我第一版就是这么写的，**是死代码**，批次 11 自查抓到：
    #     ① `_write_check_record()` 写的 `parent_context` 只有
    #        `{"orchestrator": "pipeline.run_daily"}`，**不含 `run_date`**；run_date 真正落在
    #        `check_record.run_date`。旧实现只取 `parent_context.run_date` → 每个任务都取到 `""`
    #        → `min(...)` = `""` → `_earliest` 为**空串**（假值）→ 豁免分支**永不进入**
    #        → `degrade_first_day_exempt` 恒为 0，红条一条没少（实测：2 条违例 / 0 条豁免）。
    #        这正是本项目反复出现的形态：**"改了"但机器上不生效**（声明与实现脱节）。
    #     ② 即便取对 run_date，"同一 run_date 内先成功后失败"的次序仍无法用它区分
    #        —— 同日重跑 `_r1` 会被误判成首日。
    #     → 改用**追加序**：`facts/tasks.jsonl` 是 append-only 真源，**行序即时序**
    #       （与 `recorded_seq` 的版本语义同源）。判据于是变成：
    #         "此前**无**任何行持有有效结果" ⇒ 结构上不可能保留 ⇒ **豁免**；
    #         "此前**有**行持有有效结果"   ⇒ 引用本该在却丢了 ⇒ **仍判 FATAL**（强度未放松）。
    #     ★ 该判据**可判定且穷尽**：每个 failed 行只落入"豁免"或"违例"之一（`R-06 ①`），
    #       不存在第三态、不依赖任何关键词或名单。
    #
    #   ★ `degrade_first_day_exempt` **必须为可观测计数**（不是静默 `continue`）：
    #     上一版正是"静默失效"—— 计数恒 0 而没人注意。计数走 `scanned`，
    #     在门禁输出里逐字可见（`scanned daily_run.degrade_first_day_exempt: N`）。
    #
    #   ★★★ **谓词必须外移**（本单 `G-43` 修的就是这一半）：上面"追加序"只解决了**外层**
    #     条件；**内层谓词**若恒为 False，结论照样是"全员豁免"。批次 11 独立审计实测：
    #     真实字段形状 `[done + output_refs=[] + last_valid_result_ref=null, failed]`
    #     ⇒ `degrade_first_day_exempt=1`、**预期的那条真违规 FATAL 一条不报**
    #     （唯一 FATAL 是无关的 CV4）。根因：`pipeline._write_check_record()` 此前
    #     **两个载体都不填** ⇒ 旧谓词在生产数据上恒 False。
    #     ⇒ 现改为唯一真源 `degrade.holds_valid_result()`，其载体②"一次成功的运行"
    #       不依赖任何**未被写入**的字段；配合写路径补齐后，
    #       "此前有成功运行却丢引用"才真的会红。
    #
    #   ★ `rows_holding_valid_result` 与 `degrade_first_day_exempt` **成对可观测**：单看"豁免 0"
    #     分不清"没有失败行"与"谓词恒 False"（两者观测量相同）。同一条命令里给出
    #     "按该谓词真的持有有效结果的行数"，任何一方的恒真 / 恒假都当场可见
    #     （`G-03`：空样本不得当已核）。
    first_day_exempt = 0
    rows_holding_valid_result = 0
    for _idx, t in enumerate(tasks):
        if t.get("status") == "failed" and not t.get("last_valid_result_ref"):
            if not any(holds_valid_result(_prior) for _prior in tasks[:_idx]):
                first_day_exempt += 1
                continue
            v.append(
                Violation(
                    "daily_run",
                    f"{t.get('task_id')} 失败但未保留 last_valid_result_ref"
                    "（此前已有行持有有效结果 ⇒ 引用本该在，不得置空）",
                    "facts/tasks.jsonl",
                )
            )
        elif holds_valid_result(t):
            rows_holding_valid_result += 1
    # 时点可核（Ch9 §2.2）：每条 check_record 必须能被 run_date 定位
    for cr in check_records:
        if not cr.get("run_date"):
            v.append(Violation("daily_run", f"{cr.get('check_id')} 缺 run_date：时点不可核", "facts/tasks.jsonl"))
    # 「任务状态可核」（`Ch8 §C.2` / `施工图 §2 阶段④` 的 `all_tasks_have_status(run_window)`）。
    #
    # ★ 补实现的原因（缺口 `G9-1`，由本批次实测钉出）：本判据原先**只有一行
    #   `criterion(...)` 声明、零检查** —— 把任务 `status` 置成 `totally_bogus_status`，
    #   阶段④ 照样 `exit 0`。即「阶段④ 的 PASS 只有 3/4 是真的」，正是
    #   `提示词 §一 底线 2`「真接线」点名的形态。绑定（AST 有那行字面量）**不等于**会拦。
    #
    # ★ 判据 = 「每条任务都有**可判定的** status，**且**落在 `TaskStatus` 合法取值域内」。
    #   两个条件缺一不可：
    #     只查"键存在" ⇒ `status="totally_bogus_status"` 照样过（键在、值非法）；
    #     只查"值合法" ⇒ 说不出违例是"缺字段"还是"值非法"，逐行定位会含糊。
    #   ⇒ 用同一个 `not in legal` 判定覆盖两种形态，违例文案里分别显形。
    #
    # ★ 取值域**唯一真源**是 `schema/models.py::TaskStatus`（`G-06`：不重抄那 5 个字面量）。
    #   该枚举的 5 态逐字来自 `08/02 §N8.2-04` / `Ch1 §C.3`：
    #   `queued` / `researching` / `pending_evidence` / `done` / `failed`。
    #   ★ **就地导入**（不放模块顶层）：`schema.models` 是 pydantic 重模块，实测顶层导入
    #     会把 `stage_gate --stage prep` 由 0.51s 拖到 0.86s；而只有本阶段用得到它 ⇒
    #     不该让别的阶段替它付这份开销。
    from schema.models import TaskStatus

    # ★ 字段名用**磁盘上的真名 `status`**（`models.py::Task.status`），
    #   不用 `08/02` 表里的 `task_status` 别名 —— 真仓库实测该键不存在（避免照抄文档写错域）。
    # ★ 可判定且穷尽（`R-06 ①`）：每条任务只落入"合法"或"违例"之一，无第三态、
    #   不依赖任何关键词或名单。
    legal_status = {s.value for s in TaskStatus}
    for t in tasks:
        got = t.get("status")
        if not isinstance(got, str) or got not in legal_status:
            v.append(
                Violation(
                    "daily_run",
                    f"{t.get('task_id')} 的 status={got!r} 不在 TaskStatus 合法取值域内"
                    f"（合法值 = {sorted(legal_status)}）⇒ 任务状态不可核",
                    "facts/tasks.jsonl",
                )
            )
    criterion("daily_run", "timing_replayable", v)
    criterion("daily_run", "task_state_auditable", v)
    criterion("daily_run", "degrade_keeps_last_valid", v)
    # ★ 「覆盖可核」（`coverage_verifiable`）：阶段④ 声明的第 4 条判据。
    #   实现住 `scripts/daily/coverage.py`，此处**复用**（`G-06` 唯一真源，不重造）。
    #   下面这一行 `criterion(...)` 既是**记录**也是**绑定** —— `assert_criteria_implemented()`
    #   用 AST 抽取"函数体内的 `criterion()` 字面量"，故缺了这一行该判据就**不会被算作已实现**。
    from scripts.daily.coverage import check as coverage_check

    cv = coverage_check(root)
    v += cv.violations
    criterion("daily_run", "coverage_verifiable", v)
    v += assert_criteria_implemented(root, "daily_run")
    return (not v), v, {"tasks": len(tasks), "check_records": len(check_records), "degrade_first_day_exempt": first_day_exempt, "rows_holding_valid_result": rows_holding_valid_result, **cv.scanned}


def _declared_eval_layers(task: Mapping[str, Any]) -> set[str]:
    """该行复盘记录**声明的全部层** = 当前 `eval_result.eval_layer` ∪ `eval_result_history[*].eval_layer`。

    ★ 取**并集**而非单选：`eval_result` 是"当前那条"，`eval_result_history` 是**追加式累积**
      （`models.py::Task.eval_result_history` 注明 `append-only`）。只看当前会漏掉
      "历史里声明过、当前不再出现"的层 —— 而那正是要判的形态。
    """
    out: set[str] = set()
    cur = task.get("eval_result")
    if isinstance(cur, Mapping) and isinstance(cur.get("eval_layer"), str):
        out.add(cur["eval_layer"])
    hist = task.get("eval_result_history")
    if isinstance(hist, list):
        for item in hist:
            if isinstance(item, Mapping) and isinstance(item.get("eval_layer"), str):
                out.add(item["eval_layer"])
    return out


def stage_expansion_passed(root: Path) -> tuple[bool, list[Violation], dict[str, int]]:
    """研究标准一致（Ch4 §G）+ 投资结果可核验 + 复盘 **append-only**。

    ★ `research_standard_consistent` 与 `investment_result_verifiable` 已在
      `registry/delivery.yaml` 声明为 automated，本函数**尚未实现** →
      由 `assert_criteria_implemented()` 在前置产物齐备时阻断。

    ★ `review_append_only` 的**真检查**（缺口 `G9-2` 补实现）逐字据 `Ch10 §D.5`，
      见函数体内两处 `① / ②` 的注释。要点：**不重造 append-only 比对**（`G-06`），
      而是①读 `append_only_guard` 的**判据**确认它覆盖本真源，②判**语义单调性**
      （两处被检面互不重叠，见 ② 的注释）。
    """
    tasks = _read_jsonl(root / "facts" / "tasks.jsonl")
    eval_records = [t.get("eval_result") for t in tasks if t.get("eval_result")]
    if not eval_records:
        return _deferred("expansion", "facts/tasks.jsonl 中的 eval_result（三层复盘记录）", "Ch10 §N10.3-01")
    v: list[Violation] = []
    layers = {e.get("eval_layer") for e in eval_records}
    for need in ("research_quality", "forecast_quality", "investment_result"):
        if need not in layers:
            v.append(Violation("expansion", f"三层复盘缺层: {need}", "facts/tasks.jsonl"))

    # ═══ `review_append_only`（`Ch10 §D.5`）—— 两个**互不重叠**的被检面 ═══
    aog_pathspec = ""
    aog_tracked = 0
    aog_covers = 0
    try:
        # ①「append-only 路径**真的覆盖**了这个真源」—— 读**判据**，不读输出文字。
        #
        # `Ch10 §D.5` 第 2 行逐字：「**append-only**：复盘记录一次写入即不可改
        # （承 `Ch9 §3.4.2` pre-commit 拒改既有行）」。机制由 `scripts/checks/append_only_guard.py`
        # 承担 ⇒ 此处**只问它的判据函数**要 pathspec 与"被跟踪文件数"，
        # **不解析它的输出文字**、**不重造第二套 diff 比对**（`G-06`）。
        #
        # ★ 为什么"覆盖性"本身必须被显式检查（而不是假定）：该守卫曾有一处**既有假绿** ——
        #   在 linked worktree 里 `GIT_DIR` 使 `rev-parse --show-toplevel` 返回 cwd ⇒
        #   pathspec 指错 ⇒ `git diff --cached` **恒空** ⇒ 守卫对任何输入都放行
        #   （`G-RC-12`，已由 `ws-schema-expand` 修正）。"机制存在" ≠ "机制在这个真源上生效"。
        #
        # ★ 判据 = 「守卫的 pathspec 指向的真源目录，正是**本函数读的那个** facts 目录，
        #   且 glob 到 `*.jsonl`（`tasks.jsonl` 在其中）」。用**相对仓库根**的前缀比对，
        #   而不是"被跟踪文件数 > 0" —— 后者在**夹具副本**里恒为 0（副本的 facts 不在
        #   git 跟踪范围内），会把环境伪影误判成数据违例。故 `tracked` 只**记账**不判红
        #   （与 `append_only_guard` 自身的既定口径一致，见其 `count_tracked_matches` docstring）。
        from scripts.checks.append_only_guard import (
            count_tracked_matches,
            facts_pathspec,
            repo_toplevel,
        )

        top = repo_toplevel(root)
        aog_pathspec = facts_pathspec(root, top)
        aog_tracked = count_tracked_matches(top, aog_pathspec)
        facts_rel = (root / "facts").resolve().relative_to(top).as_posix()
        aog_covers = 1 if aog_pathspec == f"{facts_rel}/*.jsonl" else 0
    except Exception as exc:  # 非 git 仓库 / git 不可用 —— 显式显形（下方按未覆盖判红）
        aog_pathspec = f"<不可用: {exc}>"
    if not aog_covers:
        v.append(
            Violation(
                "expansion",
                f"append-only 守卫的 pathspec={aog_pathspec!r} 未覆盖本函数所读的 facts/*.jsonl"
                " ⇒ 复盘记录所在真源不在「既有行不得改写」的射程内（`Ch10 §D.5` 第 2 行 / `Ch9 §3.4.2`）",
                "scripts/checks/append_only_guard.py",
            )
        )

    # ②「**已声明过的 `eval_layer` 层不得从记录集里消失**」—— 本判据的**真判别力**所在。
    #
    # `Ch10 §D.5` 第 3 行逐字：「**禁"只留赢的"**：断言 **某标的的复盘记录集合
    # ⊇ 其历史全部建议（含已验证失败者）**」；第 1 行「三类记录齐全……**不可选择性删除**」。
    #
    # ★ 可判定的快照形态：`facts/tasks.jsonl` 是**追加式**真源 ⇒ **行序即时序**
    #   （与 `degrade_first_day_exempt` 的追加序判定同源）。于是"同一任务在追加序上，
    #   声明的层集合**只增不减**"就是该断言的快照形态。
    #
    # ★ 为什么这条**不是**重造 append-only 比对（`G-06` 的关键论据）：
    #   diff 级 append-only 只能发现"**既有行被改写**"；而
    #   「**新增**一行、该行不再声明此前声明过的层」在 diff 上**完全合法**（纯追加），
    #   却正是"选择性删除"的语义违反（用户看到的历史被悄悄收窄）。
    #   ⇒ 两者的被检面**不重叠、互补**：前者管"行有没有被改"，后者管"层有没有被丢"。
    #
    # ★ 可判定且穷尽（`R-06 ①`）：每条参与复盘记录流的行，其每个历史层要么仍在、要么已丢，
    #   无第三态；不依赖任何关键词或名单。
    seen_layers: dict[str, set[str]] = {}
    for t in tasks:
        tid = str(t.get("task_id"))
        cur = _declared_eval_layers(t)
        if not cur:
            continue  # 该行不参与复盘记录流（不构成"记录集"），按 G-03 不计入判定
        lost = seen_layers.get(tid, set()) - cur
        if lost:
            v.append(
                Violation(
                    "expansion",
                    f"{tid} 的复盘记录里层 {sorted(lost)} 消失（此前已声明过）"
                    " ⇒ 违反『已声明过的层不得从记录集里消失』（Ch10 §D.5 禁「只留赢的」）",
                    "facts/tasks.jsonl",
                )
            )
        seen_layers[tid] = seen_layers.get(tid, set()) | cur

    criterion("expansion", "review_append_only", v)
    v += assert_criteria_implemented(root, "expansion")
    return (not v), v, {
        "eval_records": len(eval_records),
        "aog_covers_carrier": aog_covers,
        "aog_tracked_files": aog_tracked,
        "tasks_with_eval_history": len(seen_layers),
    }


GATES = {
    "prep": stage_prep_passed,
    "nvidia_sample": stage_nvidia_sample_passed,
    "core_chain": stage_core_chain_passed,
    "daily_run": stage_daily_run_passed,
    "expansion": stage_expansion_passed,
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"缺少真源文件: {path}")
    out: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if raw:
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} 非法 JSON: {exc}") from exc
    return out


def check(root: Path, stage: str = "prep") -> CheckReport:
    report = CheckReport(checker=f"stage_gate[{stage}]")
    targets = list(STAGES) if stage == "all" else [stage]
    for key in targets:
        passed, violations, scanned = GATES[key](root)
        for k, val in scanned.items():
            report.scanned[f"{key}.{k}"] = val
        report.violations += [
            Violation(v.rule if v.rule != "G11-04" else f"G11-04[{key}]", v.reason, v.file, v.line)
            for v in violations
        ]
        report.notes.append(f"{key}: {'PASS' if passed else 'BLOCKED'}")

    # ★ 判据台账：把"声明为 automated 但**函数体里没有对应 criterion() 声明**"的
    #   判据逐条列出。判据 id 与声明的对应关系由 `registry/delivery.yaml` 给，
    #   是否实现由**本文件的 AST** 判（`bound_criteria()`）—— 两侧必须同时对得上。
    #   它不是"通过"，但也不能被藏起来：阶段因前置缺失而阻塞时，
    #   这些缺口更不该被"反正阻塞了"掩盖过去。
    bound = bound_criteria()
    for key in targets:
        missing = criteria_not_implemented(root, key)
        report.scanned[f"{key}.criteria_bound"] = len(bound.get(key, set()))
        report.scanned[f"{key}.criteria_not_implemented"] = len(missing)
        # ★ **无条件发射**（不写 `if missing:`）。理由：若只在有缺口时打印，
        #   "该阶段无未实现判据"与"台账代码路径根本没执行"在输出上**不可区分** ——
        #   前者是好事、后者是守卫静默失效，而两者的观测量完全相同。
        #   五阶段输出形状一致后，任何一条 `判据台账[key]` 缺失都成为真信号。
        #   这也是 `tests/injection/test_wiring_guards.py::test_unimplemented_criteria_are_listed_as_notes`
        #   要求"逐条列出、不得藏起来"的**加强版**：0 缺口也要显式声明为 0，
        #   而不是靠沉默表达。
        if missing:
            report.notes.append(
                f"判据台账[{key}]：函数体内已绑定 {len(bound.get(key, set()))} 条，"
                f"**声明为 automated 但未绑定 {len(missing)} 条 → {missing}**"
                "（前置产物齐备时这些缺口会直接阻断该阶段；不得据声明判 PASS）"
            )
        else:
            report.notes.append(
                f"判据台账[{key}]：函数体内已绑定 {len(bound.get(key, set()))} 条，"
                "**声明为 automated 但未绑定 0 条**（该阶段判据已全部绑定）"
            )
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="stage_gate.py", description="阶段判据守卫（未过即阻塞）")
    parser.add_argument("code_root", nargs="?", default=None)
    parser.add_argument("--stage", default="prep", choices=(*STAGES, "all"))
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.code_root) if args.code_root else _ROOT
    return run_checker(
        f"stage_gate[{args.stage}]",
        lambda r: check(r, args.stage),
        [str(root)] + (["--no-report"] if args.no_report else []),
    )


if __name__ == "__main__":
    sys.exit(main())
