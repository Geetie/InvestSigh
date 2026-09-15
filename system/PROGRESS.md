# 交付进度（跨会话唯一真源）

> **依据**：`00_开发Agent开工提示词 §十`——「每完成一个任务，更新进度文件
> （阶段 / 任务 / 证据路径）。**跨会话靠文件，不靠记忆**。」
>
> 本文件记录**已跑过**的东西（命令 + 退出码）。**没跑过的一律不写在这里。**

| 项 | 值 |
|---|---|
| 代码工程根 | `/Users/gaza/Developer/InvestSigh/system` |
| 设计区 | 仓库根 `00_*` + `01_`~`11_`（**只读**，未改一个字节） |
| 隔离环境 | `/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python` |
| 依赖版本 | pydantic 2.13.5 · pyyaml 6.0.3 · jsonschema 4.26.0 · pytest 9.1.1 |
| 更新时间 | 2026-09-16 |

---

## 一、五阶段门禁状态

| 阶段 | 状态 | 证据 |
|---|---|---|
| ① `prep` | ✅ **PASS** | `stage_gate.py --stage prep` → `prep: PASS`，`EXIT=0`（scanned：deliverables 4 / confirmed_rules 17 / implementation_proposals 7 / freeze_params 11 / skills 6） |
| ② `nvidia_sample` | ⛔ **BLOCKED** | `stage_gate.py --stage all` → `nvidia_sample: BLOCKED`，`G11-04` 违例，`EXIT=1` |
| ③ `core_chain` | ⛔ **BLOCKED** | 同上（缺 `facts/relations.jsonl` + `facts/impacts.jsonl` 真实关系与影响） |
| ④ `daily_run` | ⛔ **BLOCKED** | 同上（缺 `check_record`） |
| ⑤ `expansion` | ⛔ **BLOCKED** | 同上（缺 `eval_result`） |

★ 后续阶段返回 **`passed=False`**，**绝不返回 True 冒充通过**（纪律 12）。

## 二、门禁真实退出码（`run_all_gates.py`，16 项，全 0）

命令：`python system/scripts/ops/run_all_gates.py --timeout 30` → **非零计数 0**

```
conflict_scan.py           exit=0  2.63s     append_only_guard.py       exit=0  0.20s
rules_lock_guard.py        exit=0  0.25s     assert_gate_input.py       exit=0  0.17s
freeze_guard.py            exit=0  0.25s     launch_guard.py            exit=0  0.19s
module_denylist.py         exit=0  0.39s     no_signal_day.py           exit=0  0.18s
no_placeholder_guard.py    exit=0  0.73s     neutrality_check.py        exit=0  0.17s
return_guard.py            exit=0  0.19s     anti_padding.py            exit=0  0.31s
gap_to_task.py             exit=0  0.18s     traceback.py               exit=0  0.18s
pipeline.py                exit=0  0.19s     stage_gate.py --stage prep exit=0  0.25s
```

★ `conflict_scan.py` 首版**卡死**（`TIMEOUT`）→ 已修（见 §四 D-2）；
`no_placeholder_guard.py` 首版**卡死** → 已修。**卡死的门禁等于被关掉的门禁。**

## 三、测试套件

命令：`python -m pytest tests -q -p no:cacheprovider` → **94 passed**，运行后 `tests/.work/` **无残留**

| 目录 | 内容 | 用例数（实测） |
|---|---|---|
| `tests/unit/test_contracts.py` | 18 JSONL 唯一真源 · 枚举小写下划线 · 五类时间 · `Recommendation` 禁止字段 · 追加式 + 索引可重建 · `tbd` 边界 · 参数唯一读口 | 21 |
| `tests/unit/test_scope_matchers.py` | **作用域匹配器直测**（glob→前缀、决策域、免扫命名空间、`freeze_param` 读口排除） | 21 |
| `tests/injection/test_guards_reject.py` | **注入违例 → exit 1**（L1–L5 / G11 / 红线二 / 基准口径 / 反凑数 / 反占位符），含 9 条**反向对照** | 30 |
| `tests/injection/test_stage_gate.py` | 纪律 12：删 SKILL.md → FAIL；阶段②–⑤ 逐个 BLOCKED | 10 |
| `tests/injection/test_append_only.py` | 纪律 4：**真建 git 仓库**改写/删除/重命名 → exit 1；纯追加放行 | 6 |
| `tests/injection/test_rules_lock.py` | 纪律 9/10：权限放开 / 哈希不符 / 未登记 / 删除 → exit 1 | 6 |
| **合计** | `pytest tests --collect-only -q` → **94 tests collected** | **94** |

## 四、已交付组件（阶段①）

| 组件 | 落位 | 状态 |
|---|---|---|
| 8 类对象模型（31 字段 `Recommendation` / 18 JSONL 断言） | `schema/models.py` · `schema/registry_models.py` | ✅ |
| JSON Schema 聚合（`defs` 权威键 + `$ref` 内联） | `schema/build_jsonschema.py` → `schema/jsonschema/facts.schema.json` | ✅ |
| 追加式真源读写 + 双时间轴 as-of + 索引重建 | `schema/store.py` | ✅ |
| 参数唯一读口（`tbd` → 建议基线 + 来源标注） | `config/freeze.py` | ✅ |
| 只读规则层（`rules/` 无写函数） | `config/rules.py` | ✅ |
| L1–L5 聚合门禁（4 时机） | `scripts/checks/conflict_scan.py` | ✅ |
| `rules/` 0444 + SHA256 锁（**校验方齐备**） | `scripts/ops/lock_rules.py` + `scripts/checks/rules_lock_guard.py` | ✅ 10 文件已锁 |
| 追加式不可变 pre-commit（**已安装**） | `.git/hooks/pre-commit` → `scripts/ops/pre-commit.sh` | ✅ 已装 |
| 60+ 守卫与脚本 | `scripts/{checks,benchmark,scope,tasks,trace,orchestrate,delivery,ingest,views,ops}/` | ✅ |
| 六阶段流程固化（I/O 契约载体） | `skills/<6 个>/SKILL.md` | ✅ 已接进阶段① 判据 |
| 44 个原型节点迁库（五类时间正确） | `scripts/ingest/seed_industry_nodes.py` → `facts/industry_nodes.jsonl` | ✅ |
| 阶段判据守卫（未过即阻塞） | `scripts/delivery/stage_gate.py` | ✅ |
| 未决张力登记 | `reports/phase1_open_tensions.md`（T-01~T-07 + D-1~D-8） | ✅ |

## 五、仍缺 / 依赖外部输入（**明说**）

| # | 项 | 性质 | 依据 |
|---|---|---|---|
| 1 | 11 项参数仍为 `tbd` | **验收前置**，不阻塞开工；代码路径已完整、值一改即生效 | `§6.1` / `§十二 N-03` |
| 2 | `J8` 脱敏清单 | **待法务口径**，不自定合规边界 | `§十二 N-04` |
| 3 | 运行时刻 / 时区（`p07`） | 随阶段④ 前置冻结 | `§十二 N-05` |
| 4 | `ledger` 类外部数据接入（付费研报库等） | `optional` + `deferred`，不进首版 | `Ch11 §E.2` 红线二 |
| 5 | 6 处设计张力 | 待需求方裁定，**已带节号锚点原文登记** | `reports/phase1_open_tensions.md` |
| 6 | 阶段②–⑤ 全部组件 | **前置未满足 → 阻塞**，按纪律 12 不开工 | `Ch11 §B` |

## 六、下一步（阶段② 前置）

1. 需求方裁定 `reports/phase1_open_tensions.md` 的 T-01~T-07；
2. 冻结 11 项参数中阻塞阶段② 的项（至少 `p01` 主基准、`p03` 推荐范围）；
3. 采集 NVIDIA 真实信息（公开源），跑通六步判断链，产出 `facts/baselines.jsonl` 的 NVIDIA 基线；
4. 过阶段② 判据后再评估 `core_chain`。
