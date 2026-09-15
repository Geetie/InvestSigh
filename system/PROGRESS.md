# 交付进度（跨会话唯一真源）

> **依据**：`00_开发Agent开工提示词 §十`——「每完成一个任务，更新进度文件
> （阶段 / 任务 / 证据路径）。**跨会话靠文件，不靠记忆**。」
>
> 本文件记录**已跑过**的东西（命令 + 退出码）。**没跑过的一律不写在这里。**

| 项 | 值 |
|---|---|
| 代码工程根 | `/Users/gaza/Developer/InvestSigh/system` |
| 设计区 | 仓库根 `00_*` + `01_`~`11_`（**只读**，`git status` 确认零改动） |
| 首个提交 | `8b41c94` · 117 个文件 · **pre-commit 钩子实测跑了 6 道门禁并全绿** |
| 隔离环境 | `/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python` |
| 依赖版本 | pydantic 2.13.5 · pyyaml 6.0.3 · jsonschema 4.26.0 · pytest 9.1.1 |
| 更新时间 | 2026-09-16 |

---

## 一、五阶段门禁状态

| 阶段 | 状态 | 证据 |
|---|---|---|
| ① `prep` | ✅ **判据 PASS**（但见 §五 缺口） | `stage_gate.py --stage prep` → `prep: PASS`，`EXIT=0`（deliverables 4 / confirmed_rules 17 / implementation_proposals 7 / freeze_params 11 / skills 6 / **criteria_bound 4，criteria_not_implemented 0**） |
| ② `nvidia_sample` | ⛔ **BLOCKED** | `G11-04` 前置未满足，`EXIT=1`；判据台账另列 2 条未绑定 |
| ③ `core_chain` | ⛔ **BLOCKED** | 同上；判据台账另列 `t01_t14_all_pass` / `graph_and_ask_traceable` 未绑定 |
| ④ `daily_run` | ⛔ **BLOCKED** | 同上；判据台账另列 `coverage_verifiable` 未绑定 |
| ⑤ `expansion` | ⛔ **BLOCKED** | 同上；判据台账另列 2 条未绑定 |

★ 后续阶段返回 **`passed=False`**，**绝不返回 True 冒充通过**（纪律 12）。

## 二、门禁真实退出码（`run_all_gates.py`，**18 项，全 0**）

命令：`python system/scripts/ops/run_all_gates.py --timeout 30` → **非零计数 0**

```
conflict_scan.py 3.38s      append_only_guard.py 0.21s   rules_lock_guard.py 0.29s
registry_schema_guard.py 0.47s   schema_sync_guard.py 0.45s
assert_gate_input.py 0.17s  freeze_guard.py 0.27s        launch_guard.py 0.19s
module_denylist.py 0.51s    no_signal_day.py 0.19s       no_placeholder_guard.py 0.80s
neutrality_check.py 0.17s   return_guard.py 0.19s        anti_padding.py 0.36s
gap_to_task.py 0.18s        traceback.py 0.18s           pipeline.py 0.20s
stage_gate.py --stage prep 0.24s
```

## 三、测试套件（**188 passed**，实测）

命令：`cd system && python -m pytest tests -q -p no:cacheprovider` → `188 passed in 49.36s`
运行后 `tests/.work/` **无残留**（`pytest_sessionstart/finish` 双保险）。

| 文件 | 内容 |
|---|---|
| `tests/unit/test_contracts.py` | 18 JSONL 唯一真源 · 枚举小写下划线 · 五类时间 · `Recommendation` 禁止字段 · 追加式 + 索引可重建 · `tbd` 边界 · 参数唯一读口 |
| `tests/unit/test_scope_matchers.py` | **作用域匹配器直测**（glob→前缀 / 决策域 / 免扫命名空间 / `freeze_param` 读口排除） |
| `tests/conflict/test_schema_no_stop.py` | `施工图 §3.4` 具名资产：P-03 止损类字段 + P-05 不得做空 |
| `tests/conflict/test_schema_no_aggregate.py` | `施工图 §3.4` 具名资产：P-07 聚合字段 + `expectations.source_id` 必填 |
| `tests/guards/test_exit_code_contract.py` | **18 个守卫 × 三条契约**：干净→0 / `code_root` 缺失→2 / 必报 `scanned` |
| `tests/test_ch11_invariants.py` | `Ch11 §F` 不变量：11 项恰为 {p01..p11} · A 6 + C 5 · 锚点非行号 · 指针不双写 |
| `tests/injection/test_guards_reject.py` | **注入违例 → exit 1**（L1–L5 / G11 / 红线二 / 基准口径 / 反凑数 / 反占位符）+ 反向对照 |
| `tests/injection/test_audit_regressions.py` | **审计反例 D3/D4/E/E2 回归**（防止绕过路径被重新打开） |
| `tests/injection/test_append_only.py` | 纪律 4：**真建 git 仓库**改写/删除/重命名 → exit 1 |
| `tests/injection/test_rules_lock.py` | 纪律 9/10：权限放开 / 哈希不符 / 未登记 / 删除 → exit 1 |
| `tests/injection/test_stage_gate.py` | 纪律 12：删 SKILL.md → FAIL；阶段②–⑤ 逐个 BLOCKED |
| `tests/injection/test_wiring_guards.py` | **接线**：`registry_models` 有读取方 · 判据绑定 · 空真源不得报"已验证" |

## 四、已交付组件（阶段①）

| 组件 | 落位 |
|---|---|
| 8 类对象模型（`Recommendation` 31 字段 / 18 JSONL 断言） | `schema/models.py` · `schema/registry_models.py`（含 `REGISTRY_MODELS`） |
| JSON Schema 聚合（`defs` 权威键 + `$ref` 内联） | `schema/build_jsonschema.py` → `schema/jsonschema/facts.schema.json` |
| **schema 生成物漂移守卫**（实测抓到漂移 exit 1） | `scripts/checks/schema_sync_guard.py` |
| 追加式真源读写 + 双时间轴 as-of + 索引重建 | `schema/store.py` |
| 参数唯一读口（`tbd` → 建议基线 + 来源标注） | `config/freeze.py` |
| 只读规则层（`is_read_only` 已接线） | `config/rules.py` |
| `rules/` 0444 + SHA256 锁（**校验方齐备**） | `scripts/ops/lock_rules.py` + `scripts/checks/rules_lock_guard.py` |
| 登记层真源结构守卫（防 `registry_models` 孤儿） | `scripts/checks/registry_schema_guard.py` |
| 追加式不可变 pre-commit（**已安装并实测**） | `.git/hooks/pre-commit` → `scripts/ops/pre-commit.sh` |
| 18 个守卫与脚本 | `scripts/{checks,benchmark,scope,tasks,trace,orchestrate,delivery,ingest,views,ops}/` |
| 六阶段流程固化（I/O 契约载体，**已接进阶段① 判据**） | `skills/<6 个>/SKILL.md` |
| 44 个原型节点迁库（五类时间正确） | `scripts/ingest/seed_industry_nodes.py` → `facts/industry_nodes.jsonl` |
| 阶段判据守卫（**判据与实现 AST 机械绑定**） | `scripts/delivery/stage_gate.py` |
| 未决设计张力 | `reports/phase1_open_tensions.md`（T-01~T-07 + D-1~D-8） |
| **缺口登记** | `reports/phase1_gap_register.md`（G-01~G-12 + D-9~D-18） |

## 五、**阶段① 不宣告完成**（独立审计结论，逐条登记在缺口登记）

第二轮独立审计（另一个会话）的结论是「**阶段① 不宜宣告完成**」，理由是
**大部分被检对象为空**——"无被检对象"≠"已验证"。

| 缺口 | 内容 | 状态 |
|---|---|---|
| **G-01 / G-02** | 注入防护 **10 用例**与**数据/指令分离执行器**（`施工图 §3.4` / `Ch9 §3.2.1` 明确是 C 档自建项）**全缺** | `OPEN` |
| **G-03** | `facts/` **13/18 个 JSONL 无消费方**（仅 `industry_nodes` 有 44 行且**有写无读**） | 阶段① 固有，②–⑤ 消解 |
| **G-04** | **7 条**声明为 `automated` 的判据未实现（已 AST 绑定 + 逐条列出，前置齐备时**直接阻断**） | `OPEN` |
| G-05 | `scripts/{compute,decision,graph,validators}/` 是**空包**（②③ 承重块） | `OPEN` |

## 六、下一步（按优先级）

1. **补 G-01/G-02**：注入防护执行器 + 10 用例（本阶段唯一"高"优先级未完成项）；
2. 需求方裁定 `reports/phase1_open_tensions.md` 的 T-01~T-07；
3. 冻结阻塞阶段② 的参数（至少 `p01` 主基准、`p03` 推荐范围）；
4. 采集 NVIDIA **真实公开信息**，跑通六步判断链 → `facts/baselines.jsonl`；
5. 过阶段② 判据后再评估 `core_chain`（届时 T01–T14 必须先实现）。
