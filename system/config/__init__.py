"""配置层：`rules/` 与 `registry/` 的**只读**读取口，以及 `freeze_param` 的唯一读口 `get_param`。

权威出处：
- `Ch11 §D.2`：「全部落 `rules/freeze.yaml` + 各自 `rules/*.yaml`，**读参数处一律经
  `get_param(param_id)`**（**不硬编码**），故拍板后改 `freeze_status`/`value` 即可生效、无需改代码。」
- `Ch11 §D.2` 单一真源：**参数值唯一真源 = `rules/freeze.yaml::freeze_param`**。
- `Ch9 §3.2.1`：「**模型对 `rules/` 无写权（硬要求）**」；`rules/` 0444 + SHA256 锁。

★ 决策作用域隔离（纪律 1 / `Ch2 §B.3` Checker-1 排除项 / `Ch11 §E.1`）：
  参数**只做"基准 / 范围 / 口径 / 披露"，不进决策函数**。
  `scripts/decision/**` 与 `scripts/graph/**` **不得**调用本模块——
  由 `scripts/checks/freeze_guard.py :: assert_no_freeze_param_in_decision_scope()` 以 AST 强制。
"""

from .freeze import (
    ParamResolution,
    UnknownParamError,
    assert_anchor_only,
    assert_no_new_gate,
    get_param,
    get_param_value,
    iter_params,
    load_freeze,
)
from .rules import RuleFileMissingError, code_root, load_yaml

__all__ = [
    "ParamResolution",
    "RuleFileMissingError",
    "UnknownParamError",
    "assert_anchor_only",
    "assert_no_new_gate",
    "code_root",
    "get_param",
    "get_param_value",
    "iter_params",
    "load_freeze",
    "load_yaml",
]
