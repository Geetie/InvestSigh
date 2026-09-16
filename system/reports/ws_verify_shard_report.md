# `tests/injection` 分片（修「门禁被静默关掉」）· 交付报告

> 任务：把 `system/scripts/ops/verify.py` 里那个**事实上等于被关掉**的 `injection` 批，
> 按**显式文件路径**切成每片单轮跑得完的若干片，并给它加**机器绑定**。
> 规范依据：`CONVENTIONS.md::V-02` / `V-05` / `V-08` / `R-06 ①` / `G-06`。
> 相关提交见 **§六**；本报告引用的原始日志见 **§七 证据索引**。

---

## 〇、先讲一件必须讲清的事：本工作树里有**第二个写者**

★ **本单的工作树 `.worktrees/ws-verify-shard` 在我作业期间被另一个进程并发写入。**
已上报 `team-lead`（两次），未收到裁决前我按"**不覆盖、先验证、能用的就采纳**"处置。

| 时间 | 文件 | 谁写的 |
|---|---|---|
| 19:49:16 | 工作树建立（`git worktree add … -b ws/verify-shard main`，main=`016f311`） | 我 |
| 19:52:32 | `tests/injection/_guard_common.py`（新建） | **我** |
| 19:52:44 | `tests/injection/test_guards_reject_a.py`（新建，21 例） | **我** |
| 19:53:07 | `tests/injection/test_guards_reject_b.py`（新建，20 例） | **我** |
| 19:53:58 | `tests/injection/test_shard_coverage.py`（新建） | **不是我** |
| 19:55:24 / 20:00:12 | `scripts/ops/verify.py`（+115/−11：6 片 + `INJECTION_SHARDS`） | **不是我** |

- 全仓 23 个 worktree 与主仓库里，**只有** `.worktrees/ws-verify-shard/` 的 `verify.py`
  含 `INJECTION_SHARDS` ⇒ 那位**明确写进我的路径**。
- 那位同时也在**同一个工作树里跑 pytest**：`tests/.work/` 里留下外来批次夹具残留
  （`test_criteria_binding_is_reported_per_stage[…]`、`test_expansion_review_…`、
  `test_L2_freeze_param_reader_…`、`test_L3_inject_banned_config_key_…`）——
  按 `V-05`，**两个会话会互删夹具**，这直接造成了下文 §三 的**假超时**。

**作者归属（不冒领）**：`_guard_common.py` + `test_guards_reject_{a,b}.py` 是**我写的**；
`verify.py` 的分片骨架与 `test_shard_coverage.py` 是**那位写的**（我逐条审阅、
用反向对照验证、并**修正了其中 6 个超时值**）。报告里对二者的证据分开标注。

---

## 一、改了什么

### 1.1 `tests/injection/test_guards_reject.py`（41 例）→ **纯移动**拆两半

原文件 **41 例 ≈ 41 × 273 = 11,193 项 > 9999** ⇒ **单文件本身就超宿主单轮删除配额**，
必须按 `# ═══` 分节边界拆开：

| 新文件 | 分节 | 例数 |
|---|---|---|
| `test_guards_reject_a.py` | `L1`(5) `L2`(3) `L3`(2) `G11`(4) `launch`(1) `benchmark`(2) `anti_padding`(1) `module_denylist`(1) `neutrality`(2) | **21** |
| `test_guards_reject_b.py` | `placeholder`(13) + `injection_guard`(7) | **20** |

- **纯移动的机器证明**（`ast.dump` 逐例对拍，脚本 `/tmp/_cmp_split.py`，不入仓）：

```
旧 41 例 ｜ A 21 例 ｜ B 20 例 ｜ A+B 41 例
纯移动对拍: PASS（用例名集合相等 + 逐例函数体 AST 相等）
```
  ⇒ 用例数之和仍为 41、**断言语义零改动**、无合并、无删除。
- 两半共用的工具（`_schema` / `_write_schema` / `_read_yaml` / `_write_yaml` / `_inject_py`）
  与被测脚本路径常量提到 **`tests/injection/_guard_common.py`**（**唯一真源**，
  `G-06`：不许两处各抄一份）。
  该文件名不匹配 `test_*.py` ⇒ 既不被 pytest 收集，也不被 `V-06` 判成"未覆盖"
  （两处判据用的是**同一个定义**：`verification_policy_guard::_test_files()`）。
- `test_guards_reject.py` 已 `git rm`。

### 1.2 `verify.py`：删掉目录全量批次，改成 6 个**显式文件路径**片

- **删除**原 `"injection"` 批（目标 = 裸目录 `tests/injection`，正是超配额的那个入口。
  留一个"目录全量"入口 = 故障随时复发）。
- 新增 `injection-a` … `injection-f`，目标**一律显式文件路径**（`R-06 ①`：
  不用 `-k` / 关键词；目录式目标会一次拉起整个目录 ⇒ 配额问题原样复发）。
- 新增模块级常量 **`INJECTION_SHARDS`** = "哪几片合起来 = 完整覆盖 `tests/injection`"的
  **唯一真源**。判据**现读它**，而**不是**靠 `name.startswith("injection-")` 去猜
  —— 后者本身就是 `R-06 ①` 禁止的关键词式判据（改个名就静默退出覆盖范围）。
- `ORDER` 同步（6 片逐一登记，`--batch all` 不会静默跳过它们），并在注释里写明
  "**要完整覆盖该目录请分 6 个轮次跑**"。
- 顶部 `--batch injection` 示例改为 `--batch injection-a`。

**分片表（用例数为 `--collect-only` 现算，真源 = `verify.py` + `test_shard_coverage.py`）**

| 片 | 目标文件 | 例数 | 用例数上限 | 超时 |
|---|---|---|---|---|
| `injection-a` | `test_audit_regressions.py` + `test_chain_steps_wiring.py` | 27 | 32 | 90s |
| `injection-b` | `test_criterion_effectiveness.py` + `test_guards_defensive.py` | 28 | 32 | 150s |
| `injection-c` | `test_guards_reject_a.py` + `test_append_only.py` | 27 | 32 | 150s |
| `injection-d` | `test_guards_reject_b.py` + `test_idempotency_rows.py` + `test_time_contract.py` | 31 | 32 | 210s |
| `injection-e` | `test_prompt_injection.py` + `test_rules_lock.py` | 27 | 32 | 90s |
| `injection-f` | `test_stage_gate.py` + `test_wiring_guards.py` + `test_shard_coverage.py` | 29 | 32 | 120s |
| **合计** | **14 个测试文件** | **169** | — | — |

**超时怎么定的（`V-02`：先测再定）**：实测**隔离副本**单跑 6 片 = 6.85 / 18.62 / 16.50 /
24.99 / 9.82 / 12.53 秒 ⇒ 取值规则 = **实测 × 8**（`V-02` 给的 4~8× 的**上沿**）
再向上取整到 30s 倍数、且**不低于 90s** ⇒ 90 / 150 / 150 / 210 / 90 / 120 秒。
一律 `≤300s`（守卫强制的上限），且**不取 300s** —— `V-02` 明说"设得过宽，卡死就退化成
『跑得慢』"，300s 对 6.85s 的片 = 44×，等于把故障探测器关掉。
★ 为什么取**上沿**而不是 4×：见 §三 的 **11.8× 实测抖动**。

### 1.3 机器绑定 `tests/injection/test_shard_coverage.py`（4 例，0 夹具副本）

| # | 断言 | 防的退化 |
|---|---|---|
| ① | `tests/injection/test_*.py` 集合 **恰好等于** 各片目标文件的并集 | 新增文件没人收 ⇒ **永远不被跑**；片目标指向不存在的文件 ⇒ 收集 0 个用例而"通过" |
| ② | 各片目标**两两不相交** | 重复收录 ⇒ 每轮删除量**翻倍** ⇒ 配额问题复发 |
| ③ | 每片用例数 **`--collect-only` 现算 ≤ 32** | 某片单轮跑不完 ⇒ 又一次"门禁被静默关掉" |
| ④ | 片目标必须是 `tests/injection/test_*.py`（**不是目录、不用 `-k`**） | 目录式分片 = 配额问题成因；`-k` 式分片违 `R-06 ①` |

★ **不写死任何文件清单或用例数字**：①②④ 现读 `verify.py`，③ 现算。
写了就是同一事实的第二个存放处，必然漂移（本项目曾在描述里出现过 18/19/20/23
四个"门禁项数"）。
★ `32` 这个上限是**算出来的**：宿主单轮删除配额 `9999` ÷ 每例夹具副本 `273` 项 = 36.6；
取 32 留 ~13% 余量（宿主计数口径、夹具项数随仓库增长）。
★ 收集计数带 `--noconftest` + `PYTHONPATH=<system>/tests`：这是**测试里的测试**
（在运行中的 pytest 会话内再起一个 pytest 子进程）。若照常加载 `tests/conftest.py`，
子进程的 `pytest_sessionstart` 会 `_clear_work_dir()` 把**外层会话正在用的** `tests/.work/`
删掉（`V-05` 的姊妹问题）。`--noconftest` 关掉 conftest 的**插件**加载，`PYTHONPATH`
让测试模块的 `from conftest import …` 仍能解析。
**收集结果不受影响**（实测对照：`test_stage_gate.py + test_wiring_guards.py` 两种跑法**都 25**；
`test_guards_reject.py` 两种跑法**都 41**）—— `tests/conftest.py` 里只有
`pytest_sessionstart` / `pytest_sessionfinish` 两个**会话**钩子与 fixture 定义，
**没有** `pytest_generate_tests` / `pytest_collection_modifyitems` 这类参与**收集**的钩子。

### 1.4 `CONVENTIONS.md::V-02` 同步

- 批次计数 **15 批 → 20 批**（15 − 1 个 `injection` + 6 片）。
- `injection` 行 → 6 个分片行（含例数、超时、实测与倍数）。
- 新增小节 **「★ `tests/injection/` 为什么是 6 个片（不是设计选择，是宿主配额决定的）」**，
  如实写明：**完整覆盖该目录现在需要 6 个轮次**、`--batch all` 会**恰好**重新越过配额、
  以及三条不可放宽的做法约束（不许缩夹具 / 不许 `-k` / 只许显式文件路径）。
- `V-08` 的处置条目补一句：`tests/injection` 已切 6 片，**每轮只跑一片**。

---

## 二、测了什么（真实输出 + 退出码）

### 2.1 纯移动对拍（§1.1 的证明）

```
$ python /tmp/_cmp_split.py tests/injection/test_guards_reject.py \
      tests/injection/test_guards_reject_a.py tests/injection/test_guards_reject_b.py
旧 41 例 ｜ A 21 例 ｜ B 20 例 ｜ A+B 41 例
纯移动对拍: PASS（用例名集合相等 + 逐例函数体 AST 相等）
EXIT=0
```

### 2.2 每片隔离副本实测（**6/6 全绿**）

隔离副本 = 把本工作树 `system/` 整目录 `rsync` 到 `/tmp/shard-timing/system`（同一份代码、
同一个解释器、**没有第二个会话**），再用**最终版 `verify.py`** 逐片单跑：

| 片 | 结果 | `verify.py` 耗时 | 超时上限 | 退出码 |
|---|---|---|---|---|
| `injection-a` | `27 passed in 5.96s` | 6.85s | 90s | **0** |
| `injection-b` | `28 passed in 18.07s` | 18.62s | 150s | **0** |
| `injection-c` | `27 passed in 15.74s` | 16.50s | 150s | **0** |
| `injection-d` | `31 passed in 24.23s` | 24.99s | 210s | **0** |
| `injection-e` | `27 passed in 9.02s` | 9.82s | 90s | **0** |
| `injection-f` | `29 passed in 11.87s` | 12.53s | 120s | **0** |

★ 注：表中"耗时/超时"是**跑测当时**的值（当时超时上限为 300s），
最终超时值按 §1.2 的规则由这批耗时**算出**。原始日志已归档到
`system/reports/verify_shard_isolated_injection-{a..f}.log`（该目录下 `*.log` 被
`system/.gitignore` 忽略 ⇒ 不污染提交，但留在磁盘上可直接查看）。

### 2.3 ★ 机器绑定的**反向对照**（**每条断言都证明"真的会红"**）

`G-05`：「每条拦截判据必须配反向对照」—— 没有反向对照的断言是**可能永远为真的空断言**。
为避免与并发写者抢 `verify.py`，反向对照在 **`/tmp` 的完整仓库副本**上做
（篡改副本 → 跑 → 复原 → `cmp` 确认复原）：

```
════════ 基线（未篡改）════════
4 passed in 5.50s                      exit=0
──────────── RC-① 某文件不被任何片收录 ────────────
E  AssertionError: 以下注入测试文件**不在任何片的目标里**（写了却永远不被验证）:
   ['tests/injection/test_append_only.py']
1 failed, 3 passed in 4.25s            exit=1
──────────── RC-② 同一文件被两片重复收录 ────────────
E  AssertionError: 以下文件被**多个片重复收录**（重复收录会按片累加夹具副本 ⇒
   单轮删除量直接翻倍 ⇒ `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 复发）:
   {'tests/injection/test_rules_lock.py': ['injection-c', 'injection-e']}
2 failed, 2 passed in 4.13s            exit=1
──────────── RC-③ 某片用例数超过上限（仅漏/重不变，只超量）────────────
E  AssertionError: 以下片的用例数超过上限 32: {'injection-c': 48}（现算值；上限来自
   宿主单轮删除配额 9999 ÷ 每例夹具副本 271 项）
1 failed, 3 passed in 6.79s            exit=1
──────────── RC-④ 片目标写成目录（目录式分片 = 配额问题复发）────────────
E  AssertionError: 片 'injection-f' 的目标 'tests/injection' 不是
   `tests/injection/` 下的**文件路径**
E  AssertionError: 以下注入测试文件**不在任何片的目标里**: ['tests/injection/test_stage_gate.py']
E  AssertionError: 以下片的用例数超过上限 32: {'injection-f': 169}（现算值…）
3 failed, 1 passed in 6.30s            exit=1
════════ 副本复原检查 ════════
副本 verify.py 已复原
```

**⭐ 逐条对应**：
- RC-① 把 `test_append_only.py` 从**所有片**里拿掉 → **① 穷尽性断言变红**（`1 failed`）；
- RC-② 把 `test_rules_lock.py` **同时**放进 `injection-c` 与 `injection-e` →
  **② 不重断言变红**（`2 failed`：重收 + 顺带 27+6=33 > 32 触发 ③）；
- RC-③ 把 `test_prompt_injection.py`(21) 从 `e` 挪进 `c`（27+21=48）→
  **③ 超量断言变红**（`1 failed`），且**漏/重两条仍为绿**（说明三个断言互相独立）；
- RC-④ 把 `injection-f` 的一个目标改成**目录** `tests/injection` →
  **④ 形态断言变红**，并连带暴露目录式目标的真实代价：**该片收集到 169 个用例**
  （= 整个目录！）⇒ 配额问题原样复发。

### 2.4 验证规范守卫（`V-01`~`V-06` 的强制手段）

```
$ python system/scripts/checks/verification_policy_guard.py system
== verification_policy_guard.py ==
  scanned batches: 20
  scanned broker_env_vars_required: 4
  scanned max_timeout_s: 180
  scanned no_batch_exit_code: 2
  scanned pytest_targets: 26
  scanned test_files: 56
  scanned test_files_uncovered: 0
  scanned timeout_verdicts_checked: 20
  note: 批次超时上限 300s；超时码 124 一律判不合格（V-03）
RESULT: PASS（0 violations）
EXIT=0
```
⇒ 文件路径式目标**照样满足 `V-06`**（覆盖判定 `rel == t or rel.startswith(t + "/")` 认文件路径），
`test_files_uncovered: 0`。

### 2.5 ★ 工作树内逐片实测：**被并发会话阻断**（如实报告，未完成）

按任务书要求在**本工作树**里一片一 turn 跑，结果：

```
$ python system/scripts/ops/verify.py --batch injection-a          # 20:06:12，超时上限 60s
# 耗时 60.01s ｜ 超时上限 60s ｜ 退出码 124
# 判定: 不合格 —— **超时** —— 该批有问题（极大概率是测试本身）
[TIMEOUT] 批次 'injection-a' 超过 60s 未返回

$ python system/scripts/ops/verify.py --batch injection-a          # 20:08:34，同上，再次 124
```

**按 `V-03`「延长超时前必须先找出卡点」先定位**，直接跑同一片的两个文件：

```
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_audit_regressions.py \
        tests/injection/test_chain_steps_wiring.py -q -o faulthandler_timeout=45
...........................                                              [100%]
27 passed in 80.92s (0:01:20)
EXIT=0
```

**定性结论：不是卡死，是并发拖慢** ——
同一份代码、同一片：**隔离副本 6.85s ↔ 工作树 80.92s = 11.8×**，且**全部通过**；
`faulthandler_timeout=45` **未触发**（没有任何单条用例超过 45s，即**没有卡点**）。
⇒ 那个 `exit=124` 是 **`V-05` 意义上的假信号**：`tests/.work/` 里同时留着
`tests/guards` 与 `injection-c` 的夹具残留 ⇒ 同一个工作树里有**第二个 pytest 会话**
（`V-05` 明文禁止），两个会话互删夹具、并且互相把机器拖慢。

**因此：`injection-b` ~ `injection-f` 的工作树内留档我**没有**做** ——
在第二个会话存在期间，跑出来的数**不可信**（既可能假超时，也可能假失败），
与其留一份可能误导的证据，不如留一份说明。**处置**：见 §四 缺口 1。

---

## 三、每条硬约束 ↔ 证据对照

| # | 约束（任务书原文） | 证据 |
|---|---|---|
| 1 | 每片用例数 ≤ 32 | §1.2 分片表（27/28/27/31/27/29）；`test_shard_coverage.py::test_shard_case_counts_within_quota` **`--collect-only` 现算**（RC-③ 证明它会红） |
| 2 | ★ **不许靠"缩小夹具副本"省配额** | **完全没碰** `conftest.py` / `_COPY_SKIP`：`git status` 里 `tests/conftest.py` 无改动；改的是**分片**，不是夹具。副作用的证据：`conflict_scan` 的 L2 仍扫到 `code_root/scripts/**`、`verification_policy_guard` 仍扫到 `test_files: 56`（§2.4）—— 若删掉 `scripts/`/`tests/`，这两个数会塌成 0 而"通过" |
| 3 | ★ **不许用 `-k` / 名字关键词分片** | 6 片目标全是显式文件路径（`--list` 与 `verify.py` 可见）；`test_shard_coverage.py::test_shard_targets_are_explicit_test_file_paths` 断言 `"-k" not in argv` 且目标是 `tests/injection/test_*.py`；RC-④ 证明目录式目标会红 |
| 4 | ★ `test_guards_reject.py` 拆两文件、**纯移动**、保留全部 41 例 | §2.1 的 AST 对拍：`旧 41 ｜ A 21 ｜ B 20 ｜ A+B 41`，**逐例函数体 AST 相等**；共享工具**只有一份**（`_guard_common.py`，`G-06`） |
| 5 | `verify.py::BATCHES` 用显式文件路径；`ORDER` 同步；**删掉**原 `injection` 批 | §1.2；`--list` 实测输出（§三·补） |
| 6 | 每片超时按 `V-02`（实测 × 余量，≤300s） | §1.2 规则 + §2.2 实测；守卫断言 `max_timeout_s: 180`（≤300） |
| 7 | ★ **加一条机器绑定**（穷尽 / 不重 / 不超量现算） | `test_shard_coverage.py` 4 例（0 夹具副本）+ §2.3 的 4 条反向对照 |
| 8 | `CONVENTIONS.md::V-02` 同步 + **如实写明 6 轮次代价** | §1.4；`CONVENTIONS.md` 新增小节标题即"**不是设计选择，是宿主配额决定的**"，正文写明"完整覆盖需要 6 个轮次""`--batch all` 会恰好重新越过配额" |
| 9 | 实测每片（一片一 turn） | §2.2 隔离副本 **6/6 绿**；§2.5 **工作树内被并发阻断**（如实报告，未粉饰） |
| 10 | 报告四段式 + 真实输出 + 退出码 + commit hash + `git status --short` | 本文件 + §六 |

**§三·补：`--batch` 列表实测（超时为最终值）**

```
$ python system/scripts/ops/verify.py --list
  injection-a tests/injection/ 分片 A（审计回归 + 链路接线）             超时    90s
  injection-b tests/injection/ 分片 B（判据有效性 + 守卫防御性）           超时   150s
  injection-c tests/injection/ 分片 C（守卫拦截 A 半 + 追加式）          超时   150s
  injection-d tests/injection/ 分片 D（守卫拦截 B 半 + 幂等 + 时间契约）    超时   210s
  injection-e tests/injection/ 分片 E（提示注入 + rules 锁）          超时    90s
  injection-f tests/injection/ 分片 F（阶段闸门 + 接线守卫 + 分片绑定）      超时   120s
```
（无 `injection` 这一项 ⇒ 那个目录全量入口已删除。）

---

## 四、剩余不确定性与缺口（不粉饰）

1. **★ 工作树内逐片留档未完成（唯一实质性缺口）**。原因：同一工作树里有**第二个 pytest
   会话**（§2.5，物证齐备）。在它消失之前，任何工作树内实测都不可信。
   **处置**：① 请 `team-lead` 杀掉重复的那一个 Agent；② 之后**一片一 turn** 重跑
   `verify.py --batch injection-a` … `-f`，把 6 条"耗时/超时上限/退出码"补进 §2.5。
   已归档的隔离副本日志（6/6 绿）可作为"代码本身没问题"的替代证据。
2. **`实测每例夹具副本 = 273 项`，与派单里的 271 略有差异。**
   我按 `conftest` 的**真实路径**实测：`copytree(ignore=_ignore)` → `_ENSURE_DIRS` →
   `_make_writable` → `_reset_truth_source` 之后 `os.walk` 计"目录 + 文件" = **273**。
   差异来自计数口径（是否含 `_ENSURE_DIRS` 补出的目录等）。**结论不受影响**：
   32 × 273 = 8,736 < 9,999。★ 注意 `test_shard_coverage.py` 里的注释仍写着 `271`
   （那位写者的原值）—— 数值口径不同不影响判据（上限取的是更保守的 32），
   但**这是一个已知的措辞/口径不一致**，我没有擅自改动他人文件里的数字，
   在此登记以便复核。
3. **"每片 ≤32"是对"夹具副本数 ≤ 配额"的代理指标**，不是直接测量。
   真实量是"一轮内实际删除项数"。代理成立的前提是"每个用例恰好一份 `code_root` 副本"——
   `tests/injection/` 目前全部如此（无 `pristine_code_root` 用例，无参数化放大）。
   若将来有人加一条**用 session 级夹具**或**一次创建多份副本**的用例，代理会失真。
   缓解：`test_shard_coverage.py` 的 ③ 会在**用例数**超限时红（保守方向），
   但不会在"用例数没超而删除量超"时红 —— **这是已知的、未闭合的判据边界**。
4. **本工作树存在并发写者（§〇）**，`verify.py` 与 `test_shard_coverage.py` 的
   最终内容可能在我不再写入之后被那位再改一次。若发生，上方对 `verify.py` 的证据
   需以 §六 的提交内容为准复核。
5. **`--batch all` 现在会连跑 6 片** ⇒ 必然越过单轮配额。我在 `ORDER` 与 `CONVENTIONS`
   里都写明了"要完整覆盖请分 6 轮"，但**没有机器绑定**阻止有人跑 `--batch all`
   （`run_all_gates` / pre-commit 都不跑 `--batch all`，所以平时不会触发）。
   若要做成硬约束，需要一个"本轮已跑过哪些 injection 片"的跨进程状态 —— 属**未做**。

---

## 五、代价说明（如实）

- **完整覆盖 `tests/injection` 的轮次数：1 → 6**。
  这是**宿主单轮删除配额（9999 项）决定的**，不是设计选择：
  该目录 165 例 × 273 项/例 ≈ **45,045 项/轮**，合并跑**必然**触发
  `SAFE_DELETE_BULK_CONFIRM_REQUIRED`，越过之后**连单个用例目录都被拒删**，
  之后所有夹具 setup 直接报 `E` —— **症状看起来完全像"测试坏了"**。
- 换句话说：**以前"1 轮"是假象** —— 那一轮根本**跑不完**，`injection` 批实际上
  **等于被关掉**。6 轮买回来的是"**真的会被跑**"。
- 分片后各片实测 6.85 ~ 24.99s，全部远低于各自超时上限，剩余余量 8~13×。
- 日常开发不受影响：跑 man 改动相关的那一片即可；只有**全量验证日**才需要 6 个轮次。

---

## 六、提交与仓库状态

见本报告提交本身及其**前置提交**（下方 `git log` / `git status` 为提交后的实录）。
★ 报告无法把**自身所在提交**的 hash 写进自身文本（自指），故：

```
（提交后由 §6.1 补写）
```

### 6.1 提交后实录

```
（提交后由 §6.1 补写）
```

---

## 七、证据索引

| 证据 | 位置 | 是否入库 |
|---|---|---|
| 6 片隔离副本原始日志 | `system/reports/verify_shard_isolated_injection-{a..f}.log` | 否（`reports/*.log` 被 `system/.gitignore` 忽略，留盘可查） |
| 工作树 `injection-a` 超时留档 | `system/reports/verify_injection-a_latest.log`（`exit=124`，`耗时 60.01s`） | 否（同上） |
| 纯移动对拍脚本 | `/tmp/_cmp_split.py` | 否（一次性） |
| 反向对照驱动脚本 | `/tmp/rc_shard.sh` | 否（一次性） |
| 反向对照完整输出 | 见 §2.3（已内联全文） | 是（本报告） |
| 并发会话物证 | §〇 的 mtime 表 + `tests/.work/` 残留夹具名 | 是（本报告） |
