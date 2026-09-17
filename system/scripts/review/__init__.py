"""`scripts/review/` —— **验收与持续复盘链路的记录与守卫**（`Ch10 §C` / `Ch10 §D`）。

本包职责（与 `scripts/checks/` 的"门禁"区分开）：把"复盘"这件事落成**可追加、可追溯**的真源记录。

- `record_eval.py` —— 三层复盘记录器（研究质量 / 预测质量 / 投资结果），**本模块**。
- `review_return.py` / `capability_source.py` —— 复盘收益计算与能力来源（由其他工作流交付）。

★ 命名纪律（`Ch2 §B.2 P-09`）：本包**不是** `decision` / `graph` 决策作用域，
  故模块级普通业务标识符不受 P-09（`decision_scope_only`）约束。
"""
