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
| **G-01** | **注入防护 10 用例全缺**：base64 藏指令 / 同形字 / 诱导 shell / 伪造分隔符 / 自称官方提权 / 忽略规则买入 / 换基准 / 删反证 / 改规则文件 / 藏表格图片字幕。全仓 `grep base64\|同形字\|homoglyph\|伪造分隔符\|官方提权\|诱导` **零命中** | `施工图 §3.4`（测试资产）· `Ch9 §3.2.1`「注入防护 = B 规则 + C 执行器」 | **高** | `DONE`（证据：`tests/injection/test_prompt_injection.py`（10 正向 AC-13~22 + 10 反向对照 AC-23~32 + AC-34 空样本）；`reports/verify_injection_latest.log` 批次 `injection` **98 passed / exit=0**） |
| **G-02** | **数据/指令分离执行器未实现**：G-01 的被测对象。设计明确它是 C 档自建项（"规则 = 只读 Git 文件（模型不可写）" + "数据/指令分离执行器 + 测试"） | `Ch9 §3.2.1` 第 6 行 | **高** | ⚠️ **PARTIAL（独立审计否决了 `DONE`）**：**实现已完成且经独立验证**（`scripts/guard/` 7 模块 + `injection_guard` 第 19 项门禁 + `handle_external_request` 路由入口；我逐条复现过四处反事实），**但从未被任何非测试代码调用** —— 真实仓库 `facts/claims.jsonl` = **0 行**、`raw/` 仅 `.gitkeep`，`grep process_external_text\|guard.executor` 在 `tests/` 之外 **0 命中**。按 `§一 底线 2` 属 **Wiring Failure**（能通过 100% 覆盖率测试、主流程从不触发）。★ 生产接线**不属阶段②**（原判已被推翻，见 `G-13` 的判据纠正）→ 追踪项 **G-13**。审计报告：`reports/batch4_independent_audit.md` · 第二轮 `…_round2.md` |
| **G-03** | **`facts/` 13/18 个 JSONL 无消费方**：仅 `industry_nodes.jsonl` 有 44 行（且**有写无读**，`§6.2 Empty Execution`）；其余 12 个业务代码零引用、且为空文件 | `Ch9 §3.3.3` / `§十三 第 2 问` | **高**（阶段① 固有） | `PARTIAL`：消费方按设计在 ②–⑤ 阶段随各层交付而产生；**不得据此判"已验证"** |
| **G-04** | **7 条声明为 `automated` 的通过判据未实现**（本实现已用 `criterion()` 在函数体内**显式绑定**，并在报告里逐条列出）：<br>`nvidia_sample`: `chapter4_g_depth` · `evidence_locatable`<br>`core_chain`: `t01_t14_all_pass` · `graph_and_ask_traceable`<br>`daily_run`: `coverage_verifiable`<br>`expansion`: `research_standard_consistent` · `investment_result_verifiable` | `registry/delivery.yaml` 各阶段 `pass_criteria_testable` | **高** | `OPEN`（阶段②–⑤ 前置；**前置齐备时会直接阻断该阶段**） |
| **G-05** | **`scripts/{compute,decision,graph,validators}/` 是空包**：施工图把它们列为 ②③ 阶段 C 档承重块（确定性计算 / 三维决策函数 / T12 传播 / `locator_check`） | `施工图 §3.2` | 中（②③ 前置） | ⚠️ **PARTIAL（已实现，但仍是孤儿）**：批次 5/5b/5c 已建成 `compute`（82 用例）· `graph`（36）· `validators`+`claim`（20+20）· `decision`（86）；**但四者 `AC-03 真接线` 全部 FAIL** —— `pipeline.py` 只注册 step 1 → 见 `G-20`/`G-21`/`G-14`。**"包里不是空的" ≠ "已验收"** |
| **G-06** | **`--require-l4` / `--require-l5` 无调用方**：阶段③/④ 的硬门开关是死代码 | `Ch2 §B.4` / `conflict_scan.py` docstring | 中 | `OPEN`（阶段③④ 前置） |
| **G-07** | **`run_all_gates.py` 只跑 `stage_gate --stage prep`**：阶段②–⑤ 的阻塞只在测试里跑 `--stage all`，不进 CI/pre-commit | `施工图 §2` | 中 | `PARTIAL`：阶段① 内合理（②–⑤ 本应阻塞）；进入② 时须改为跑当前阶段 | 
| **G-08** | **`rules/review.yaml:32` 的 `guard:` 指向不存在的 `detect_horizon_extension`**：该 yaml 已注明"（阶段②/③ 实现）"，但 `guard:` 字段仍指向一个不存在的函数名 | `Ch2 §D.3` | 低 | `OPEN`：`rules/` 已锁 0444，修改须走 `chmod → 改 → 重锁` 显式流程（见 `lock_rules.py` 文档头） | 
| **G-09** | **卡口未声明 `frontend animation_policy`**：`Ch8 §K ③` 要求"接口先定、值 `tbd`"，`rules/publish.yaml` 只落了指针骨架 | `Ch8 §K ③` | 低（④ 前置） | `PARTIAL`：指针骨架已落，值 `tbd` |
| **G-10** | **`facts/industry_nodes.jsonl` 有写无读**：写入方 `scripts/ingest/seed_industry_nodes.py`，业务代码零读取方 | `§6.2 Empty Execution` | 中 | `OPEN`：读取方（图谱页 / 关系核验）属阶段③ |
| **G-11** | **`index/facts.sqlite` 只在测试里重建**：无生产读取方（可重建索引尚未被真正使用） | `Ch9 §3.3.2` | 低 | `OPEN`（④ 前置） |
| **G-12** | **11 项参数全部 `tbd`**：A 档拍板是**验收前置**，不阻塞开工 | `§6.1` / `§十二 N-03` | — | `OPEN`（**等需求方**；代码路径完整、值一改即生效） |
| **G-13** | **编排器未兑现 `rules/pipeline.yaml` 的步骤声明**（批次 4 独立审计 `D-1` 的根因）：该文件（**0444 锁定，属设计真相源，不可改**）声明 **step 1–6 `implemented_in_first_version: True`**、`blocking: True`、**step 1 无 hook**；只有 step 7–8 是 `False` + `gap_behavior: explicit_gap_when_hook_absent`。而 `pipeline.py` **一个 handler 都没注册** → 实跑 8 步全为 `gap`。**step 1 = `ingest_public_information`，`process_external_text` 正是它的实现。** | `rules/pipeline.yaml::steps[1]`（声明）· `Ch1 §B/§E`（8 步闭环与注册面）· `Ch9 §3.4.6` 措施① · `§一 底线 2` | **高** | `OPEN` —— ★ **原判"属阶段② 采集层"是错的，已纠正**：step 1 的声明要求首版实现，故这属**阶段① 编排缺陷 + 声明脱节**，不是跨阶段。**验收判据**：`pipeline.py` 注册 step 1 handler（消费外部文本 → `process_external_text`），实跑后真实 `system/` 留下 `raw/<file>` 与 `facts/claims.jsonl`（≥1 行），且 `Pipeline.run_daily` 的 step 1 报 `ok` 而非 `gap`。**step 2–6 的声明同样高于现实**（其组件属阶段②③）→ 已升级为**张力 `T-08`**（不能改 `rules/`，须需求方裁定） |

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

## 追加：性能与隔离缺陷（D-19 ~ D-23，用户反馈"测试跑一次不该这么久"后排查）

用户反馈：**一次完整测试 49s 不正常**。排查结论是"**不是测得多，是三类纯浪费**"。

| # | 缺陷 | 症状（实测） | 根因 | 修复 | 效果 |
|---|---|---|---|---|---|
| **D-19** | `check_L2` **O(n²)** | 单次 4.57s（加缓存前恶化到 8.4s） | 对"模块 + 每个函数"各做一次 `ast.walk`，且对**每个被访问节点**再 `ast.walk` 一次 | 改**单遍扫描**：作用域只覆盖自己的语句（模块级不穿透函数体），token 一次遍历产出 | 8.4s → **0.52s** |
| **D-20** | **配置读取无缓存** | 每个函数都重读并 YAML 解析一次 `banned_tokens.yaml`（50 文件 × 上百函数 ≈ 数千次） | `matches_call_chain()` / `is_freeze_param_reader()` 均经 `decision_scope_config()` → `load_banned_tokens()` 直接读盘 | `_common._cached_yaml()`：键 = (路径, mtime_ns, size)，**夹具改配置后自动失效**（注入测试仍安全） | 与 D-19 合计：端到端 `conflict_scan` **1.36s → 1.0s** |
| **D-21** | `check_L1` 白付 **pydantic 导入** | 0.449s（其中大头是导入，不是 JSON 解析） | `from schema.assertions import …` 会先执行 `schema/__init__.py`，而它**急切导入** `models`（pydantic ≈ 0.3s）——**每个守卫启动都付一次** | `schema/__init__.py` 改 **PEP 562 惰性导入**（`__getattr__`） | 0.449s → **0.022s**（20×） |
| **D-22** | 测试**子进程启动**是全部耗时 | 49.2s ≈ **80 次调用 × 0.31s**（夹具复制实测仅 0.021s，**不是瓶颈**）；另有同一命令被两个用例各跑一遍 | 每次都起新解释器 + 重导入依赖；两个用例共享同一次执行却拆开写 | ① `run_gate` 改 **`runpy` 走真实 `__main__` 入口**（不 mock）② 同 `(脚本, root, 参数)` session 缓存 ③ 合并共享执行的断言 | 49.2s → **13.6s** |
| **D-23** | **进程内执行的交叉污染** | 改进程内后 **16 条用例集体失败** | `schema_sync_guard._load_builder()` 会 `sys.path.insert` 并删 `sys.modules` 的 `schema*`；子进程里无害，**进程内会污染整个测试进程**（后续检查器从已删除的夹具目录导入 `schema`） | 用 `try/finally` **恢复 `sys.path` 与 `sys.modules`**：带全局副作用的加载器必须自己收尾 | 16 失败 → 0 |

★ **同时修掉一个语义缺陷（与 D-19 同源）**：初版"模块作用域"会穿透进**所有**函数体，
于是 `is_freeze_param_reader()` 的排除（`Ch11 §E.1`）在**决策目录内的文件上完全失效**——
排除发生在函数作用域层，而模块作用域早已把函数体扫过一遍。现按作用域正确划分。

★ **进程级保真度没有丢**：由两条**真子进程**用例守住 ——
`test_cli_wiring_exits_with_main_return_code`（CLI 真能把退出码交给 shell）与
`test_injection_blocks_at_process_level`（注入违例 → **真进程** `exit 1`，AC-04 的最终证据）。
**"更快"不是靠少测**：用例从 188 条变为 173 条，减少的 15 条全部是**重复执行**，
覆盖面未减（见 §三 文件表）。

★ **证据留档**：`scripts/ops/verify.py` 一次跑完 pytest + 18 门禁 + 阶段判据并写
`reports/verify_latest.log` —— **后续引用证据直接读该文件，不必重跑**。

---

## 批次 4 独立审计（换人 · 对抗性）—— 结论与已处理项

审计报告：`reports/batch4_independent_audit.md`（356 行）。判定统计 **PASS 29 / FAIL 5 / UNKNOWN 0 / HUMAN_REVIEW 1**。

| 审计编号 | 缺陷 | 处理 |
|---|---|---|
| **D-4（高，且是主理人自己引入的回归）** | `no_placeholder_guard` 的 `FAKE_DATA` / `DEMO_TALK` / `HARDCODED_FALLBACK` **永不命中** —— 早先为消除 docstring 误报把**所有**字符串抹白，等于把探测器一起抹掉（`§一 底线 1` 第一类假交付） | ✅ **已修**（根因有**两个**：抹白过度 + `HARDCODED_FALLBACK` 正则写坏）。改为**只抹白注释与 docstring**、保留普通字符串；新增 4 条回归测试；反向对照实测 **8 条占位全部命中**、docstring 里的 `TODO/占位/mock` **不误报** |
| **D-1（高）** | 执行器一族**零生产调用方**（真实仓库 `facts/claims.jsonl` = 0 行、`raw/` 仅 `.gitkeep`）→ `§一 底线 2` Wiring Failure，`G-02` 不该 `DONE` | ✅ **已如实纠正**：`G-02` 改 `PARTIAL`；新增追踪项 **G-13**（含明确验收判据） |
> **第二轮独立审计（换人 · 对抗性）修正了上表**：审计员**自造 24+ 条探针**重测，
> 结论是 **D-5 / D-6 真闭合**，而 **D-2 / D-3 只闭合了被点名的那几例**（同族残口 + 4 个新绕过仍在），
> **D-7 文字层反而被我自己的提交引入了新的错误陈述**（见下 A-6）。
> 判定统计 **PASS 31 / FAIL 3（AC-01 · AC-03 · AC-05）**。报告：`reports/batch4_independent_audit_round2.md`

| 第一轮发现 | 第二轮判定 | 依据 / 现状 |
|---|---|---|
| D-2 异常逃逸 | **PARTIAL** | 已拦：缺文件 → `blocked/SOURCE_MISSING`；payload 缺字段 → `blocked/MISSING_PAYLOAD_FIELDS`；`rule_write` 空 payload → `blocked`。**仍逃逸**：路径指向**目录** → `IsADirectoryError`；文件 0000 → `PermissionError`（应 `except OSError`）→ 下称 **A-1** |
| D-3 B/C 绕过 | **PARTIAL** | 原 4 例全部 `exit 1` 且归因正确、4 条反向对照全 `exit 0` ✓。**但 4 个新绕过仍 `exit 0`**（`__builtins__['__import__']` / `builtins.exec` / `append_records` **别名** / `os.__dict__['system']`）→ 下称 **A-3** |
| D-5 真空证据 | ✅ **CLOSED** | 审计自证四步：未改动夹具 `exit 0 + staged=0 + 真空 note`（**证明旧断言确为真空**）→ 注入后 `staged=1` 且无真空 note → 反事实改写既有行 `exit 1` → 反事实**删除整份 JSONL** `exit 1` |
| D-6 静默覆盖 | ✅ **CLOSED** | `same.txt`(版本A) 保留 + `same.<hash>.txt`(版本B)；同内容幂等；前缀碰撞自动加长 8→16；写侧穿越 `ValueError`；经**真执行器**同样两份 |
| D-7 docstring 强度 | **PARTIAL / 文字层 REGRESSED** | "不再是孤儿"已删 ✓、`KNOWN_STATIC_LIMIT` note 每轮可见 ✓。**但** `executor.py` 新写"生产接线属**阶段②** 采集层"，与本提交自己把 `G-13` 改成**阶段①** **直接相反** → **A-6**（我主理人的时序错误：先要求工程师写"阶段②"，后自己改判为阶段①） |
| 措辞耦合 | ✅ 已解耦 | `rule_hint` 零残留；且审计**结构性证明**：`CheckReport.passed` 只由 violations 决定、退出码只由 `passed` 决定 ⇒ 改文字**原理上不可能**改退出码 |

### 第二轮新增发现（`A-1`~`A-13`）—— 逐条登记，未闭合者保持 OPEN

| # | 严重度 | 内容 | 状态 |
|---|---|---|---|
| **A-1** | 中 | `process_raw_file` 同类异常仍逃逸（`IsADirectoryError` / `PermissionError`）→ 应 `except OSError` | ✅ **已独立复现**（我实测目录路径 → `IsADirectoryError`）；待修 |
| **A-2** | **中（安全）** | **读侧路径穿越未校验**：`process_raw_file(root, "raw/../rules/scope.yaml")` → `status='ok'`，把 `rules/` 文件内容**写进 `raw/` 并主张化** → **反转了"外部文本只从 `raw/` 来"的前提**。写侧有 `_validate_name`、读侧没有 → **契约不对称**（应复用同一校验，`G-06` 唯一真源） | ✅ **已独立复现**（我实测：`raw/scope.yaml` 生成 + `claim_id` 非空；写侧 `ValueError`）；待修 |
| **A-3** | 中 | 4 个新绕过（token 全字面量、静态可见）：`__builtins__['__import__']('subprocess')`、`import builtins; builtins.exec(...)`、`from schema.store import append_records as ar`（**别名一次改名**即绕过 C）、`os.__dict__['system']`。**不属于**已声明的 `KNOWN_STATIC_LIMIT`（该 note 只声明"**计算得到的路径**不可判定"）→ 属"**该拦没拦**"。修法成本低：`visit_Subscript` 查字面量 slice；别名预扫描；`Attribute.attr` 末段（`builtins.exec` 漏在末段匹配）；`eval/exec/compile` 的参数是**代码文本**，应用"包含"而非全等 | 待修 |
| **A-4** | 中 | **D-2 / D-6 的修复零回归测试**（`SOURCE_MISSING` / `MISSING_PAYLOAD_FIELDS` / `DECODE_DEGRADED` / hash 兄弟在 tests 中命中数全为 **0**）→ 与本项目铁律"**没有机器绑定的规范等于不存在**"直接冲突（D-3/D-4 都配了测试，偏偏这两个没配） | 待补 |
| **A-5** | 低中 | D-6 新增调用点会把 `ExternalTextDecodeError` 抛给调用方（hash 落点已存在且非法 UTF-8 时） | 待修 |
| **A-6** | 低中 | 两处"阶段②"残留与 `G-13` 新判据**自相矛盾**（`scripts/guard/executor.py` 顶部 docstring；本文件 `§六` 旧句） | ✅ 本节已修正文；`executor.py` 待工程师改 |
| **A-7** | 低中 | 本登记表未随修复更新（D-2/D-3/D-5/D-6/D-7 五行仍写 `OPEN`；旧句仍称"另开 4 条 OPEN"） | ✅ **本节已修**（改为第二轮判定） |
| **A-8** | 低中 | **`G-07` 规范在现行仓库上不成立**：`pre-commit.sh` 只跑 **8** 个守卫、`run_all_gates.py` 跑 **20** 个（13 个仅后者），且**无任何机器检查**核对两集合 | 待修（应加机器断言） |
| **A-9** | 低 | `verification_policy_guard` 的 V-04 用**裸文本包含** `VAR=0` 判定 → 注释里的 `VAR=0` 也会通过（与 `G-04`"注释须抹白"教训反向）；当前是真 `export`，无假通过 | 待修 |
| **A-10** | 低 | **`AC-05` 第 2 例判据枚举不符**：`rules/` 目录缺失实得 **`exit 1`**（10 条"真源不得删除"违例），而判据写 **`exit 2`** | ⚖️ **主理人裁定：以实测为准，改判据为 `exit 1`**（真源缺失是**内容违例**，不是输入异常；`exit 2` 保留给"参数/路径不存在"类） |
| **A-11** | 低 | `CONVENTIONS.md §V-02` 表陈旧（写"19 项门禁"实为 20；实测耗时列与审计实测不符） | ✅ **已修** |
| **A-12** | 低 | `V-01` 规范文字与"正确用法 `--batch all`"的措辞张力（实质风险已由"无 `--batch` 即 exit 2 + 无裸 `tests` 批次"消除） | ✅ **已修**（补一句说明 `all` 也是逐批独立超时且超时即停） |
| **A-13** | nit | `scripts/orchestrate/pipeline.py` 注释把 `D-14` 误述为"第二轮独立审计指出"，而该文件自 `8b41c94` 起从未改动 | 待修 |

### ★ 审计员最重要的**概念**判断（我认同，且必须记下来）

> **B 组（AC-13~22）与 C 组（AC-23~32）都不具备判别力** —— 把注入文本换成完全无害的文本，
> 两边断言**同样全绿**，因为执行器与守卫**都不读文本内容**。
> 这两组证明的是「**该链路没有副作用**」，**不是**「系统识别出了注入」。

这是**设计取向的必然结果**（`R-01` 与 `AC-33` 明确要求判据取**效果**、禁词面判定），
**不是测试写错**。但它意味着：**"10 个注入用例全绿"这句话的强度被高估了**。
真正有鉴别力的只有 **④改写规则文件** 与 **⑦诱导 shell** 两条**反事实**（审计已逐条复现成立）。
→ 后继批次若要"识别注入"，必须引入**内容级**判据，而那与 `AC-33` 的降噪要求存在张力，**需需求方裁定**。

---

## 结论一句话

**批次 4 不宣告完成。** `G-01`（10 用例）**DONE**；`G-02` 仅 **PARTIAL** ——
执行器实现与验证都是真的，但**从未被非测试代码调用**，属 `§一 底线 2` 的 Wiring Failure，
其生产接线（`G-13`）**不属阶段②** —— `rules/pipeline.yaml`（0444 锁定声明）要求 **step 1–6 首版已实现**，
故这是**阶段① 编排缺陷 + 声明脱节**（原判"阶段② 采集层"已由主理人推翻，见 `G-13` 行与张力 `T-08`）。
`AC-01` / `AC-03` 因此**保持 FAIL**，在 `T-08` 裁定与接线完成前**不得标完成**。
独立审计另开 4 条 `OPEN`（`AC-05` 异常逃逸 / `injection_guard` B·C 可绕过 / `AC-15` 证据真空 / `raw/` 静默覆盖）。

---

# 批次 6 新增缺口（`G-14` ~ `G-22`）—— `§九` 独立审计（并行三流）产物

> **来源**：`reports/ws_independent_audit_compute.md` · `reports/ws_independent_audit_graph_claim.md`
> （**换人、新会话、对抗性**；判据全部为 raw CLI / 短脚本 + `文件:行号` 证据）
> **结论**：`ws/compute` · `ws/graph` · `ws/claim` **均 not accepted**（FAIL 5 / PARTIAL 5 / UNKNOWN 6）。
> **任务书**：`reports/batch6_fix_taskbook.md`

| # | 缺口 | 设计锚点 | 严重度 | 状态 |
|---|---|---|---|---|
| **G-14** | **★ 阻断级：`claim → graph` 跨流传播契约三层不匹配**。`transition.py:335` 调 `forward_closure(claim_id, max_depth=3, detect_cycle=True)`；真实签名 `forward_closure(code_root, start, *, max_depth, source, edges, known_refs, valid_asof)` —— ① `code_root` 才是第 1 位置参数；② `start` 必填；③ **无 `detect_cycle`**。实测 `TypeError: forward_closure() got an unexpected keyword argument 'detect_cycle'`。**且**返回 `ClosureResult`（`@dataclass`，**不可迭代**）其 `reached` 为**裸 ref 字符串**，而 `_normalize_ref` 要求 `.object_type`/`.object_id` → 永不成立。**后果**：任何 `superseded` 真跑都抛错，且因 `_append_claim`（`:403`）先于 `_propagate`（`:414`），**在真源留下 `status=superseded` 行 + 0 条 recheck 任务 = 半数据**，违反追加式一致性 | `Ch6 §E.4`（`superseded` 复用第九章传播）· `Ch9 §3.4.3` · `§3.4.2`（追加式） | **阻断** | `IN-FIX`（`fix/claim-propagation`） |
| **G-15** | **重复实现同一传播（`G-06` 唯一真源）**：`scripts/graph/propagate.py::propagate_retraction` 已完整实现闭包+入队+深度回退（幂等键 `recheck::<ref>::<target>`）；`transition.py` 又自带一套（`_normalize_ref` + `_append_recheck_task`），用**第三种键格式** `recheck::<claim_id>::<type>::<id>` → 在**同一 `facts/tasks.jsonl`** 争用同段前缀，同逻辑任务得出两种键 → **重复建单**。违反 `纪律 11 复用优先` | `Ch9 §3.4.3` · `§3.5` 阶段④幂等键 · `G-06` | 高 | `IN-FIX`（同上，一并消除） |
| **G-16** | **测试桩吞掉参数 → 真实路径零覆盖**（`G-14` 长期潜伏的**元凶**）：`tests/claim/test_transition.py:92` 的 `_closure_fn(*_args, **_kwargs)` 接受一切参数，签名错位**永远测不出来**；唯一另一处（`:276`）用 `monkeypatch` 把 resolver 换成 `lambda: None`，同样**绕过**真实路径 | `§5.1 AC-04`（真跑真实脚本）· `§一 底线 3` | 高 | `IN-FIX`（删桩 + 补真实路径用例） |
| **G-17** | **`schema/store.py::read_records` 对缺失真源静默 `return []`** → 与"真源存在但 0 行"**不可区分**；守卫据此 `exit 0` 判 PASS。属"**无被检对象被当已验证**"的翻版 | `G-03` · `§一 底线 3` | 中 | `OPEN`（集成 `I-3`） |
| **G-18** | **`ws/compute` 四条静默缺陷**（详见任务书 §2）：`C-01` `require_nonzero` 放过 `None` → 裸 `TypeError` 而非缺口对象（含 `rate=None` 缺汇率，DoD AC-05 明文要求缺口）· `C-02` 幂等键缺 `version` → 上游重述后**静默保留陈旧值并报 OK** · `C-03` `step.py:49` `produced` 语义错 → **击穿 `G1-05` 空执行守卫** · `C-05` `valuation.py` 双 `None` 静默跳过 `Ch5 §D.3` 顺序校验并注入 `now()` | `Ch9 §3.5` · `Ch5 §D.2/§D.3` · `Ch2 §B.4` G1-05 | 高 | `IN-FIX`（`fix/compute-silent-defects`） |
| **G-19** | **`ws/compute` 设计偏离 4 项**：`growth.py:104` `cash_threshold = 0.8` **硬编码阈值**（`纪律 1` 禁参数内置）· `Ch4 §D.3` 分档实现给 `medium`+标志位与 DoD"四档不压成分数"表述不一致 · `NumericClaim` 复用**零命中**（DoD AC-08 声称复用） · `share_count`/`compute_date` 从未落库（`Ch5 §D.2` 要求） | `Ch4 §D.3` · `Ch5 §D.2` · `纪律 1` · `纪律 11` | 中 | `OPEN`（修或如实登记，由 `fix/compute-silent-defects` 逐条判定） |
| **G-20** | **`ws/graph` 无生产调用方（`AC-03` FAIL）**：全树 grep 穷尽，`scripts.graph` / `graph_integrity_guard` 在 `scripts/graph/**` 之外**零引用**；`run_all_gates.py`（20 项）与 `pre-commit.sh` 均未收录；`pipeline.py` 只注册 step 1 → **孤儿模块** | `Ch2 §B.3`（命中即 fail）· `§一 底线 2` | 高 | `OPEN`（集成 `I-2`） |
| **G-21** | **`ws/claim` 孤儿调用孤儿（`A-AC-03` FAIL）**：`transition.py` 确实调 `claim_locator_problems(...)`（调用**真实存在**），但 `transition.py` **自身零生产调用方**，且 `locator_check` **未注册门禁** | `Ch6 §D` · `G-07` | 高 | `OPEN`（集成 `I-1` + `I-2`） |
| **G-22** | **DoD 契约文本过期（`B-AC-01` FAIL）**：`ws_claim_dod.md` 的 AC-01 与迁移表基于"采集层写 `status='active'`"，但 `schema/models.py::Claim.status` 默认值**已改为 `ClaimStatus.pending_verification`**（封闭 `StrEnum`，`active` 非合法取值）→ DoD 迁移表 `(active, pending_verification)` 那格标 ✅ 而**代码无 `active` 键**。属"**DoD 写了、代码不认**"（`§六 假交付`）。另：`ws_claim_dod.md A-AC-08` 引用的 `Ch9 §3.4.6 措施①/②` **子锚点在设计区不存在**（`§3.4.6` = 注入防护，无 ①②）→ 违反 `纪律 6` | `Ch6 §E.1` · `Ch9 §3.4.6` · `纪律 6` | 中 | `OPEN`（集成 `I-5`；**根因是主理人改 schema 默认值后未同步 DoD，主理人自己的失误**） |

### ★ 批次 6 审计的三条方法论价值（必须记住）

1. **"已合并 ≠ 已验收"被实证**：三流的 AC 判定原本**全部来自作者自报**；换人审计后，
   同一批代码多出 **5 条 FAIL + 5 条 PARTIAL**，其中 `G-14` 是**阻断级**。
2. **吞参数的测试桩 = 签名错位的永久掩体**（`G-16`）。凡"注入式"测试，桩**必须显式形参签名**，
   否则测的是桩、不是实现。这条应升格为通用规范。
3. **`--no-verify` 的反向证实有效**：集成 worktree 未用 `--no-verify` 即通过 pre-commit
   → 反证三流的 `--no-verify` 属环境性（`V-06` 未预置批次），不是掩盖代码问题。

