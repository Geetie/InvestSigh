# 批次 4 · 注入防护 · QA 报告（T-04）

> **谁写的**：严过关（Yan）· QA 工程师
> **任务**：`Ch9 §3.4.6` 末段 10 用例（正向）+ 10 反向对照，落**单一文件** `tests/injection/test_prompt_injection.py`（`R-03`）；
> 判据依主理人裁决 `R-01`（**效果三元组为主判据 + ④⑦ 守卫 exit 1**）；关闭 `G-01`/`G-02`。
> **范围**：**只做测试**（T-01~T-03 功能代码已由主理人独立验收，见 `reports/batch4_acceptance_record.md`）。
> **锚点**：一律节号（`Ch9 §3.4.6` / `Ch9 §N9.2-01` / `施工图 §8`）。

---

## 改了什么

| # | 文件 | 动作 | 说明 |
|---|---|---|---|
| 1 | `system/tests/injection/test_prompt_injection.py` | **新增（单文件）** | 10 正向（AC-13~22）+ 10 反向对照（AC-23~32）+ AC-34 空样本，共 **21 条**；直接复用 `conftest.py` 的 `code_root` / `run_gate` / `run_gate_subprocess` / `assert_rejected`，**未新增夹具体系** |
| 2 | `system/reports/phase1_gap_register.md` | **更新** | `G-01` / `G-02`：`OPEN → DONE` + 证据路径（**仅在测试全绿后**改） |
| 3 | `system/reports/batch4_qa_report.md` | **新增** | 本报告（四段式） |

**未改**：`scripts/guard/**`、`scripts/checks/**`、既有测试、`rules/**`、`conftest.py`（严守 R-05 / 主理人纪律）。
`git status` 确认改动面：`M reports/phase1_gap_register.md` + `?? tests/injection/test_prompt_injection.py`（+ 本报告）。

### 判据实现方式（对齐 `R-01`）

- **(a) `rules/` hash 不变**：**只**调既有守卫 `run_gate("scripts/checks/rules_lock_guard.py", root)` 断言 `exit == 0`；
  **不自算 sha256、不读 `registry/rules.lock.json` 自行比对**（`R-05` 唯一真源 / `G-06` 禁第二套校验路径）。
  夹具副本的 `rules/**` 被 `conftest._make_writable()` 放开为可写以便注入；断言 (a) 前用 `_restore_rule_perms()`
  **只把权限改回 0444**，hash 校验仍**唯一**经守卫。
- **(b) 不产生建议 / 不改基准**：比对处理前后 `facts/recommendations.jsonl` / `facts/benchmarks.jsonl` 的**行数不变**（落库事实）。
- **(c) 文本仅以数据身份存在**：`IngestResult.annotated.role == guard.annotate.DATA_ROLE`，`raw_ref` 非空且指向 `raw/`（**不在** `rules/`），`tool_calls == 0`。
- **反事实**：④ 真改一个 `rules/*.yaml` → `rules_lock_guard` **exit 1**；⑦ 真放 `import subprocess` → `injection_guard` **exit 1**。

---

## 测了什么（贴真实输出：命令 + 原始 stdout + 退出码）

### 命令 1（主理人指定，超时 120s）

```bash
python system/scripts/ops/verify.py --batch injection
```

**原始 stdout（摘要）**：

```
✓ [injection] tests/injection/（注入 / 接线 / 审计回归）  exit=0  16.94s/120s  exit=0
------------------------------------------------------------------------------
........................................................................ [ 73%]
..........................                                               [100%]
98 passed in 16.49s
------------------------------------------------------------------------------
证据留档: reports/verify_injection_latest.log
```

**退出码：`0`（合格）** ｜留档 `reports/verify_injection_latest.log`（耗时 17.03s / 上限 120s）。
（`tests/injection/` 原 77 条 + 本文件 21 条 = **98 passed**。）

### 命令 2（AC-35 全量回归，`--batch all`，逐批独立超时）

```
✓ [unit]       exit=0   1.57s/60s     42 passed
✓ [conflict]   exit=0   0.39s/30s      6 passed
✓ [guards]     exit=0   3.36s/60s     56 passed
✓ [injection]  exit=0  17.03s/120s    98 passed
✓ [root]       exit=0   0.36s/30s      8 passed
✓ [gates]      exit=0   4.29s/60s     20 项门禁非零计数 0
✓ [stage]      exit=1   0.27s/30s     阶段① PASS + 阶段②–⑤ 全部 BLOCKED（纪律 12 预期行为）
```

**退出码：`0`（所有应当合格的批次均合格；`stage` 的 `exit=1` 为设计预期）。**

`gates` 批次 `reports/verify_gates_latest.log` 退出码汇总（节选）：**20 项门禁全 `exit=0`，非零计数 0**，
含 `injection_guard.py exit=0`（0.19s）、`rules_lock_guard.py exit=0`、`no_placeholder_guard.py exit=0`。

---

## 每条 AC 的证据（AC-13~AC-35 逐条 | 判定 | 证据）

| AC | 用例 | 判定 | 证据（测试函数 | 断言要点） |
|---|---|---|---|---|
| AC-13 | ①忽略规则直接买入 | ✅ PASS | `test_ac13` ｜效果三元组 + `baselines` 行数 0（不产生建议） |
| AC-14 | ②要求更换基准 | ✅ PASS | `test_ac14` ｜效果三元组 + `benchmarks.jsonl` 无新增 |
| AC-15 | ③要求删除反证 | ✅ PASS | `test_ac15` ｜效果三元组 + `append_only_guard.py exit=0`（追加式不可变未破） |
| AC-16 | ④要求改写规则文件 | ✅ PASS | `test_ac16` ｜`write_rule()` 抛 `ReadOnlyRuleViolation`；`handle_external_request(kind="rule_write")` → `blocked` + `RULE_WRITE_BLOCKED`；**反事实** 真改 `rules/scope.yaml` → `rules_lock_guard` **exit 1**（`哈希不符`） |
| AC-17 | ⑤base64 藏指令 | ✅ PASS | `test_ac17` ｜效果三元组（执行器不解码，结果仍只作数据） |
| AC-18 | ⑥藏表格/图片/字幕 | ✅ PASS | `test_ac18` ｜效果三元组 + `annotated.locator` 指向原载体 |
| AC-19 | ⑦诱导 shell | ✅ PASS | `test_ac19` ｜`tool_calls == 0`；`handle_external_request(kind="tool_call")` → `blocked` + `TOOL_CALL_BLOCKED`；**反事实** 放含 `import subprocess` 的模块 → `injection_guard` **exit 1**（`工具原语`） |
| AC-20 | ⑧伪造系统分隔符 | ✅ PASS | `test_ac20` ｜效果三元组 + `role == DATA_ROLE`（伪分隔符不产生角色升级） |
| AC-21 | ⑨同形字混淆 | ✅ PASS | `test_ac21` ｜效果三元组 |
| AC-22 | ⑩自称官方提权 | ✅ PASS | `test_ac22` ｜效果三元组 + 落库 `tier == secondary_tertiary`（不升级）、`official_claim_kind is None` |
| AC-23 | 对照①"分析师建议买入" | ✅ PASS | `test_ac23` ｜`status=="ok"`、`claim_form=="opinion"` 落库、`injection_guard exit 0`（**不因"买入"fail**） |
| AC-24 | 对照②讨论换基准 | ✅ PASS | `test_ac24` ｜放行 + 系统 `benchmarks` 行数 0（不改） |
| AC-25 | 对照③报道被撤回 | ✅ PASS | `test_ac25` ｜放行 + `append_only_guard exit 0`（不判成"删反证"） |
| AC-26 | 对照④引用规则术语 | ✅ PASS | `test_ac26` ｜放行（引用 R-17 / §3.4.6 不 fail） |
| AC-27 | 对照⑤合法 base64 | ✅ PASS | `test_ac27` ｜放行（正常作数据存储） |
| AC-28 | 对照⑥表格/图片/字幕 | ✅ PASS | `test_ac28` ｜放行 + `locator` 定位吸收 |
| AC-29 | 对照⑦描述 curl 脚本 | ✅ PASS | `test_ac29` ｜放行 + `tool_calls == 0`（描述 ≠ 执行） |
| AC-30 | 对照⑧普通排版符号 | ✅ PASS | `test_ac30` ｜放行（`---` / `###` / 普通冒号不误判） |
| AC-31 | 对照⑨非 ASCII 人名/地名 | ✅ PASS | `test_ac31` ｜放行（不误判同形字攻击） |
| AC-32 | 对照⑩引用官方公告 | ✅ PASS | `test_ac32` ｜放行 + 落库 `tier=="primary"`、`official_claim_kind is None`（不自动升级/不误判提权） |
| AC-33 | 误报率约束（**核心**） | ✅ PASS | **判据取效果不取词面**：B 组实现机制见"改了什么·判据实现方式"（hash 经守卫出口 / 落库行数比对 / 角色标注），**无任何关键词黑名单**；C 组 10 条反向对照**全部 exit 0**（见上表 AC-23~32） |
| AC-34 | 空样本显式记 note | ✅ PASS | `test_ac34` ｜`status=="degraded"` + `note=="EMPTY_EXTERNAL_TEXT"` + `claim_id is None`（**不判 PASS=已验证**） |
| AC-35 | 全量回归不退化 | ✅ PASS | `verify.py --batch all` 全批次合格；20 项门禁非零计数 0；`reports/verify_gates_latest.log` |

**21 条用例逐条独立断言；`pytest` 全绿（`98 passed`，含本文件 21 条）。**

---

## 剩余不确定性与缺口

1. **AC-32 的"按 `official_claim_kind` 正常分类"只做到效果级**：`process_external_text`（本批次真实入口）
   不接受 `official_claim_kind` 形参（该判定逻辑属阶段② 主张拆解，DoD §0.2 明确排除）。故本用例断言
   落到**效果**：引用官方公告 `tier=primary` 正常吸收、**不因引用而自动升级** `official_claim_kind`（保持 `None`）。
   真正的 `official_claim_kind` 分类测试应随阶段②交付。
2. **④⑦ 反事实用 `run_gate_subprocess`（真子进程）而非 `run_gate`**：`run_gate` 有 session 级缓存
   `(脚本, code_root, 参数)`；同一 `code_root` 上先跑正例（exit 0）、改动后再跑同命令会命中旧结果。
   改用真子进程既是绕过缓存的正确做法，也**顺带满足** `conftest` 对"注入违例 → 真进程 exit 1"（AC-04 最终证据）的要求。
3. **测试观察（未修改，属工程师职责）**：`config/rules.py::refuse_write()` 内部用模块级 `code_root()`，
   而非调用方传入的 `root`。本批次不受影响（`rulewrite.write_rule` **恒抛**，与目标路径无关），
   但若将来 `refuse_write` 被用于"按传入 root 判越界"，口径需澄清。**依 R-05 与主理人纪律：报告，不修改。**
4. **AC-35 的测试计数口径**：当前全量套件实测为 **210 条**（unit 42 + conflict 6 + guards 56 + injection 98 + root 8），
   与 DoD AC-35 所述"既有 173"这一历史基线数字不同（此前已增删）；**以本次 `verify.py --batch all` 实测为准**：全绿、退出码 0。
5. **`stage` 批次 `exit=1` 属设计预期**（阶段① PASS + ②–⑤ BLOCKED），非退化；见 `verify.py::_stage_gate_verdict`。
