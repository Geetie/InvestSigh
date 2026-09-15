# 阶段① 缺口登记（G-01 ~ G-12）

> **为什么要有这个文件**：`00_开发Agent开工提示词 §一 底线 3` 要求**真验证**，
> `§6.3` 点名"用假数据填满 `facts/` 让流程'跑通'"是无效做法。
> 第二轮独立审计的结论是「**阶段① 不宜宣告完成**」，主要理由是
> **大部分被检对象为空**（"无被检对象"≠"已验证"）。
> 本文件逐条登记**尚未满足**的项，含设计锚点与补齐方式。
>
> **状态约定**：`OPEN` 未动 / `PARTIAL` 部分完成 / `DONE` 已完成（已附证据）。

| # | 缺口 | 设计锚点 | 严重度 | 状态 |
|---|---|---|---|---|
| **G-01** | **注入防护 10 用例全缺**：base64 藏指令 / 同形字 / 诱导 shell / 伪造分隔符 / 自称官方提权 / 忽略规则买入 / 换基准 / 删反证 / 改规则文件 / 藏表格图片字幕。全仓 `grep base64\|同形字\|homoglyph\|伪造分隔符\|官方提权\|诱导` **零命中** | `施工图 §3.4`（测试资产）· `Ch9 §3.2.1`「注入防护 = B 规则 + C 执行器」 | **高** | `OPEN` |
| **G-02** | **数据/指令分离执行器未实现**：G-01 的被测对象。设计明确它是 C 档自建项（"规则 = 只读 Git 文件（模型不可写）" + "数据/指令分离执行器 + 测试"） | `Ch9 §3.2.1` 第 6 行 | **高** | `OPEN` |
| **G-03** | **`facts/` 13/18 个 JSONL 无消费方**：仅 `industry_nodes.jsonl` 有 44 行（且**有写无读**，`§6.2 Empty Execution`）；其余 12 个业务代码零引用、且为空文件 | `Ch9 §3.3.3` / `§十三 第 2 问` | **高**（阶段① 固有） | `PARTIAL`：消费方按设计在 ②–⑤ 阶段随各层交付而产生；**不得据此判"已验证"** |
| **G-04** | **7 条声明为 `automated` 的通过判据未实现**（本实现已用 `criterion()` 在函数体内**显式绑定**，并在报告里逐条列出）：<br>`nvidia_sample`: `chapter4_g_depth` · `evidence_locatable`<br>`core_chain`: `t01_t14_all_pass` · `graph_and_ask_traceable`<br>`daily_run`: `coverage_verifiable`<br>`expansion`: `research_standard_consistent` · `investment_result_verifiable` | `registry/delivery.yaml` 各阶段 `pass_criteria_testable` | **高** | `OPEN`（阶段②–⑤ 前置；**前置齐备时会直接阻断该阶段**） |
| **G-05** | **`scripts/{compute,decision,graph,validators}/` 是空包**：施工图把它们列为 ②③ 阶段 C 档承重块（确定性计算 / 三维决策函数 / T12 传播 / `locator_check`） | `施工图 §3.2` | 中（②③ 前置） | `OPEN` |
| **G-06** | **`--require-l4` / `--require-l5` 无调用方**：阶段③/④ 的硬门开关是死代码 | `Ch2 §B.4` / `conflict_scan.py` docstring | 中 | `OPEN`（阶段③④ 前置） |
| **G-07** | **`run_all_gates.py` 只跑 `stage_gate --stage prep`**：阶段②–⑤ 的阻塞只在测试里跑 `--stage all`，不进 CI/pre-commit | `施工图 §2` | 中 | `PARTIAL`：阶段① 内合理（②–⑤ 本应阻塞）；进入② 时须改为跑当前阶段 | 
| **G-08** | **`rules/review.yaml:32` 的 `guard:` 指向不存在的 `detect_horizon_extension`**：该 yaml 已注明"（阶段②/③ 实现）"，但 `guard:` 字段仍指向一个不存在的函数名 | `Ch2 §D.3` | 低 | `OPEN`：`rules/` 已锁 0444，修改须走 `chmod → 改 → 重锁` 显式流程（见 `lock_rules.py` 文档头） | 
| **G-09** | **卡口未声明 `frontend animation_policy`**：`Ch8 §K ③` 要求"接口先定、值 `tbd`"，`rules/publish.yaml` 只落了指针骨架 | `Ch8 §K ③` | 低（④ 前置） | `PARTIAL`：指针骨架已落，值 `tbd` |
| **G-10** | **`facts/industry_nodes.jsonl` 有写无读**：写入方 `scripts/ingest/seed_industry_nodes.py`，业务代码零读取方 | `§6.2 Empty Execution` | 中 | `OPEN`：读取方（图谱页 / 关系核验）属阶段③ |
| **G-11** | **`index/facts.sqlite` 只在测试里重建**：无生产读取方（可重建索引尚未被真正使用） | `Ch9 §3.3.2` | 低 | `OPEN`（④ 前置） |
| **G-12** | **11 项参数全部 `tbd`**：A 档拍板是**验收前置**，不阻塞开工 | `§6.1` / `§十二 N-03` | — | `OPEN`（**等需求方**；代码路径完整、值一改即生效） |

---

## 本轮**已**修掉的审计发现（附证据）

| 编号 | 缺陷 | 证据 |
|---|---|---|
| D-9 | `stage_gate` 用手写集合记载"哪些判据实现了" → **一行数据即可把未实现的 T01–T14 判成 PASS** | 集合已删除，改用 `bound_criteria()` 对**本文件 AST** 抽取函数体内的 `criterion()` 字面量；`tests/injection/test_audit_regressions.py` 3 条回归 |
| D-10 | `check_kind: automated` → `manual` 一词即绕过 | 新增断言「通过判据不得降级为非自动检查」 |
| D-11 | `implementation_carrier` 只校验非空 → 指向不存在的文件仍 PASS（审计反例 E） | 新增 `_carrier_exists()`，并对 2 条裸文件名载体改为完整相对路径 |
| D-12 | `schema/` 生成物漂移无守卫：改 `models.py` 不同步生成物 → 17 门禁 + 105 测试全绿（反例 E2） | 新增 `scripts/checks/schema_sync_guard.py`，**已实测抓到漂移 exit 1**，重建后转绿 |
| D-13 | `schema/registry_models.py` **孤儿模块**，而 `prep_deliverables.yaml` 声明它是载体 | 新增 `REGISTRY_MODELS` + `scripts/checks/registry_schema_guard.py`（唯一读取方），注册进 `run_all_gates.py` 与 `pre-commit.sh` |
| D-14 | `assert_steps_complete()`（G1-05）**零调用**，而 `rules/pipeline.yaml` 与 `SKILL.md` 都声明它承载 G1-05 | 已接进 `Pipeline.run_daily()` 主流程：步不全 → 记 gap + 置 `blocked` |
| D-15 | 多处 docstring 声称 vs 函数体脱节（`pipeline.check` 声称校验 `state.json`、`gap_to_task` 声称"终态有输出"、`config/rules` 声称写 `rules/` 抛异常、`return_guard` 断言③落点含糊） | 逐条改为**代码做到**或**文档说清**：`state.json` 自洽校验已实现、终态必须有 `output_refs` 已实现、`is_read_only()` 已接线、`return_guard` 三种落点分表说明 |
| D-16 | `ExpectationSample.source_id` 可选空串，而 `Ch5 §C2` 要求必填非空「否则校验失败」 | 改为 `Field(min_length=1)`；由新增测试 `test_expectation_sample_requires_source` 抓出 → 重建 schema |
| D-17 | `system/` **从未入库**（`git ls-files system` = 0），纪律 4 守卫恒无被检对象 | 已 `git add system/` + 提交（117 文件），**pre-commit 钩子实测跑了 6 道门禁并全绿** |
| D-18 | 夹具临时目录残留 53 个目录会被当源码提交 | `system/.gitignore` + `pytest_sessionstart/finish` 双保险清空 `tests/.work/` |

---

## 结论一句话

**阶段① 的四条书面判据（`registry/delivery.yaml::prep.pass_criteria_testable`）全部真实满足，
且判据与实现已由 AST 机械绑定；但 G-01/G-02 两项"注入防护"测试资产与执行器尚未交付，
G-03 的"无被检对象"问题在 ②–⑤ 阶段才会自然消解 —— 因此阶段① 判据 PASS，
但 `施工图 §3.4` 层面的阶段① ≠ 可宣告完成。**
