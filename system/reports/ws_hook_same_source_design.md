# 卡 13-O 设计短文：钩子同源化（判据与对象必须同源）

> 状态：**设计 + 已实现待安装**（`.git/hooks/` 为**全 worktree 共享**，安装动作需主理人批准 —— 见 §7）。
> 归属：`ws-ch2-rules`（team-lead 本轮裁定「`13-O` 升为要做，该卡归你」）。
> 对象：worktree `.worktrees/ws-ch2-rules`，设计时 `HEAD = 7459476`。

## 1. 现象（三份现场，两条流）

| # | 门禁 | 报错 | 撞上者 |
|---|---|---|---|
| 1 | `quote_provenance_guard` | `can't open file …ws-ch2-rules/system/scripts/checks/quote_provenance_guard.py: [Errno 2]` ⇒ `阻断（exit=2）` | `ws-ch2-rules` |
| 2 | `scenario_tag_binding_guard` | 同上（脚本只在未合并分支 + 暂存在主仓索引） | `ws-ch2-rules` |
| 3 | `rule_key_alignment_guard` | 同上（脚本在 `main`、不在被检树） | `ws-ch2-rules` **与** `ws-real-collect-2` |

★ 三次的**输出逐字同型**，且**与"你改坏了"不可区分**。

## 2. 根因（两行代码）

```
$ cat .git/hooks/pre-commit
#!/bin/sh
# installed-by: system/scripts/ops/install_hooks.sh
exec sh "/Users/gaza/Developer/InvestSigh/system/scripts/ops/pre-commit.sh"     # ← 硬编码「主仓」绝对路径
```
```
# pre-commit.sh:60
CODE_ROOT="$REPO_ROOT/system"        # ← REPO_ROOT 从 **cwd** 反解 ⇒ 指向「发起提交的那棵树」
```

⇒ **一次提交里有两个根**：
- **判据根** = 脚本从哪来 = **永远是主仓**（被钩子钉死）；
- **对象根** = `CODE_ROOT` = **被检的那棵树**（从 cwd 反解）。

**两者可以不同，且没有任何一处断言它们必须相同。** 于是：

| 方向 | 判据根 vs 对象根 | 后果 | 可观测性 |
|---|---|---|---|
| ① **幽灵门禁** | 判据**新**于对象 | `python $CODE_ROOT/scripts/checks/<新>.py` **文件不存在** ⇒ `[Errno 2]` ⇒ `rc=2` | ⚠ **被 `run_gate` 与 `rc=1`（违例）同款报成"阻断"** ⇒ 用户被告知"你改坏了" |
| ② **静默失去门禁** | 判据**旧**于对象 | 树里已落地的新门禁（以及清单里那一行）**根本不在被执行的脚本里** ⇒ **不跑，零报错** | ❌ **完全不可观测** |

★ 方向②是 `team-lead` 补的对称风险，**我未实测**（如实标注）——但机制上由同一个变量决定，**两个方向同源**。

## 3. 为什么"每次 merge 一下"不是解

1. 它要求**每条流**在**每一道新门禁落地后立刻 merge**，否则**全体当场被堵**（本批次 3 次实测、≥2 条流）；
2. **反向无解**：没有任何东西会提示"你这棵树少跑了一道门禁"（方向②）；
3. 它把**门禁面的变更**变成**全体流的运维负担** —— 这是**每加一道门禁的常规副作用**，不是偶发。

## 4. 设计目标（可判定）

| # | 目标 | 可判定形式 |
|---|---|---|
| **T1 同源** | 一次提交里，"跑哪些判据"与"被判的对象"必须来自**同一个根** | 钩子生成物中**不出现任何绝对路径**；解析只用 `git rev-parse --show-toplevel` |
| **T2 输入错误 ≠ 违规** | "脚本不在被检树"必须**与"违例"可区分** | 缺脚本 ⇒ 输出含 `[INPUT-ERROR]`、**不含** `阻断`、`exit=2`；真违例 ⇒ 含 `阻断`、`exit=1` |
| **T3 漂移可见** | 装上的钩子与版本化模板**不一致**时必须可见 | `install_hooks.sh --check` 返回 `0`/`1`(+差异说明)/`2`；**有测试强制**（§8 用例 3，判红见 E5） |
| **T4 不引入新门禁** | 不得新增门禁、不得改守卫判据 | 本节只动 `ops/` 两个脚本 + 新增测试 |

## 5. 候选方案与取舍

### 方案 A：薄壳同源（**采用**；两条流独立提出的同一修法）
```sh
#!/bin/sh
# installed-by: system/scripts/ops/install_hooks.sh
root="$(unset GIT_DIR GIT_WORK_TREE GIT_PREFIX; git rev-parse --show-toplevel 2>/dev/null)" || exit 2
[ -n "${root}" ] || { echo "pre-commit: 无法定位仓库根" >&2; exit 2; }
exec sh "${root}/system/scripts/ops/pre-commit.sh"
```
- ✅ **T1**：判据根 == 对象根（都是"发起提交的那棵树"）。
- ✅ **方向①消失**：清单里列的门禁脚本，必然就在同一棵树里（同一份清单规定的）。
- ✅ 主仓自身提交时行为**完全不变**（`--show-toplevel` = 主仓根 ⇒ 与旧钩子等效）。
- ✅ 简单、可审、**一处**（`install_hooks.sh` 的模板）。
- ❌ **不直接治方向②**：落后树跑自己的**旧**清单 ⇒ 少跑新门禁。**处置见 §6**。

### 方案 B：双源 + 显式同源断言（**否决**）
薄壳同时取两个根（判据 = 主仓 / 对象 = 被检树），门禁脚本从主仓取、`CODE_ROOT` 取被检树，并对比两份清单。
- ⚠ **否决理由（原理性，不是工程量）**：它要求**用一棵树里不存在的规则去判它** —— 这正是幽灵门禁的**同一根因**，
  只是换了个失败模式：**新门禁（按新代码写）去判旧代码** ⇒ 会造出**假红**（判据引入的新断言在旧代码上必然不满足）
  或**假绿**（判据的期望值取自它自己的树）。**同源原则**要求：**一棵树只能被它自己的规则判**。
- 另：改动面大（`run_gate` 每次调用要区分两个根），而收益被上面这条否定。

### 方案 C：只做"错误可区分"（**采用，作为 A 之外的第二件**）
`pre-commit.sh` 增加：
1. **跑门禁前的输入预检**：`run_gate` 先判 `[ ! -f "${script}" ]`，缺失则
   `echo "[INPUT-ERROR] <门禁名>：门禁脚本不在被检树 —— <绝对路径>"` ⇒ 记 `INPUT_ERROR=1` 并 `return 0`；
   ★ **不 break** ⇒ **14 道逐条走完、缺的逐条列出**（实测：全缺时打印 14 条，见 §8.2），
   而不是"停在第一道"。缺脚本时**根本不调 python**（因此输出里**没有** `can't open file`）；
2. `run_gate` 区分退出码：`rc=2 ⇒ [INPUT-ERROR]`（计入输入错误，**不写"阻断"**）；`rc=1 ⇒ 阻断`；
3. 收尾：`INPUT_ERROR=1 ⇒ exit 2`（若同时有阻断则**两条都报**，并声明"本次结论不成立"），
   否则 `exit 1`（`CONVENTIONS.md G-01`：`2`=输入异常、`1`=违规）。
- ✅ **T2**；✅ 零风险（纯报错措辞 + 一处预检）；✅ 即使方案 A 未安装，**方向①当场从"假阻断"变成"真输入错误"**。

### 方案 D：钩子漂移可观测（**采用，第三件**）
`install_hooks.sh` 重构：**钩子正文由一个函数生成**（`print_hook()`，单一真源，安装与打印走同一份），
安装路径用 `git rev-parse --git-common-dir` 解析（**修掉旧的 `$REPO_ROOT/.git/hooks` 在 linked worktree 下指错**），
并支持
- `--print`：把正文打到 stdout（**不安装**）⇒ 可被测试直接断言，**测试不需要动共享钩子**；
- `--check`：比对"已安装"与"模板"，漂移则 `exit 1` 并打印双方正文（`2` = 未安装）；
- 安装时**自动备份** `${TARGET}.bak.$(date +%Y%m%d%H%M%S)` 并打印**一条命令**的回滚方式。
- ✅ **T3**；★ 它治的是**钩子自己的**"装上的 ≠ 版本化的"漂移（与 `G-59`/`G-RC-12` 同族：**共享状态没有同源校验**）。

## 6. 方向②的处置（不靠方案 B）

在方案 A 下，"落后树少跑新门禁"是**设计上可接受**的，理由：
1. **门禁绑定的是集成线**：落后树的内容要进 `main` 必须在 `main` 上再跑一遍（合并提交在主仓根下 ⇒ 用主仓清单）⇒ **新门禁在集成点必然生效**；
2. 真正的风险不是"少跑"，而是**"少跑且无人知道"** ⇒ 因此把**可见性**补上：
   `pre-commit.sh` 在开头打印**它自己所在树的 HEAD**（`git rev-parse HEAD`，一行 note），
   于是"本次提交是用哪份清单跑的"**留痕在输出里**（`口径 10`：读数必须能定位到对象）。
   ⇒ 与 `main` 的差距**可被任何人一眼看出**（比对 `main` 的 HEAD 即可），不需要机器强制。
3. ★ 仍存在的残余（如实登记）：**没有人会自动去比对**。这是本节的能力边界，不粉饰。

## 7. 风险、共享影响与回滚

| 项 | 内容 |
|---|---|
| **共享性** | `.git/hooks/pre-commit` 位于**共享 git 目录** ⇒ 影响**全 34 人**的 `git commit`。改坏 = 全体无法提交 |
| **本节的处置** | ① 代码（`install_hooks.sh`/`pre-commit.sh`/测试/本设计）**先落库、不安装**；② 安装前**先在本树空跑** `sh system/scripts/ops/pre-commit.sh` 必须仍 PASS（**已做，见 §9**）；③ 安装时**自动备份** |
| **备份** | 安装脚本自动写 `${TARGET}.bak.$(date +%Y%m%d%H%M%S)`（`TARGET` = `--git-common-dir`/hooks/pre-commit），并把该路径**打印在屏幕上** |
| **回滚** | `cp '<打印出来的 .bak 路径>' '<TARGET>' && chmod +x '<TARGET>'`（一条命令回到当前行为） |
| **我未自行动作** | 安装需 team-lead 批准 ⇒ 见 §9 |

## 8. 可判红反例（2 条，`team-lead` 要求）

新增 `system/tests/guards/test_hook_same_source.py`（`tests/guards/` 已存在 ⇒ **不触发 `V-06`**）：

| # | 用例 | 断言 | **判红条件**（改回旧实现就红） |
|---|---|---|---|
| 1 | `test_install_hooks_prints_a_same_source_shell` | `sh install_hooks.sh --print` 的输出：**不含 `exec sh "/…` 形式的绝对路径**、含 `git rev-parse --show-toplevel`、含 `unset GIT_DIR`、含 `[INPUT-ERROR]`/`exit 2`，且 `sh -n` 语法通过 | 把正文改回 `exec sh "/abs/path/…"` ⇒ "不含绝对路径"失败 |
| 2 | `test_input_error_is_distinguishable_from_violation` | 在 `tmp_path` 里造两棵假树：**(a) 门禁脚本全缺** ⇒ 输出含 `[INPUT-ERROR]`、**不含** `阻断`、**不含** `can't open file`、`exit=2`；**(b) 脚本齐（全是桩）但有一道 `exit 1`** ⇒ 输出含 `阻断`、`exit=1`；并断言两条路径的输出**不同形** | 去掉预检 / 把 `rc=2` 也写成"阻断" ⇒ `exit` 与措辞断言失败 |
| 3 | `test_check_detects_drift_between_installed_hook_and_template` | 在 `tmp_path` 的**夹具树**里：未安装 ⇒ `2`；刚装完 ⇒ `0`；把装上的钩子改一个字 ⇒ `1` 且 **diff 里打得出那个改动**；收尾断言三态 `{2,0,1}` | `--check` 只 `exit 0`（不做 `cmp`）⇒ 第 ③ 步拿到 `0` ⇒ 失败 |
| 4 | `test_gate_script_list_is_parseable`（**防真空**） | 清单能被解析、≥10 条、无重复、全 `.py` | 解析式失效 ⇒ 用例 2 静默空跑（`G-03`） |

★ **用例 3 绝不触碰共享钩子**：`--git-common-dir` 在夹具树里就是 `<夹具>/.git`
⇒ 目标 = `<夹具>/.git/hooks/pre-commit`。**实测**：跑完该用例后
`.../InvestSigh/.git/hooks/pre-commit` 的 **mtime 仍是 `00:13`、内容仍是旧版、`.bak` 计数 `0`**。

★ **四条用例都用 `tmp_path`（系统临时目录）** ⇒ ① 夹具不在受管桶内（`G-60` 的 `/tmp` 低桶洞察）；
② 因此**可 `--noconftest` 运行**（`main` `261f8c9` 已采纳该零配额范式）⇒ 本卡的验证**不消耗删除预算**。
（另有：`verify.py` 的 `guards` 批是 `_pytest("tests/guards")` **整目录** ⇒ 本文件**自动**被收集，
**无需**改 `verify.py`，也**不**触发 `V-06`。）

### 8.1 判红实测（仪器：`/tmp/probe13o_killtest.py`，只比红/绿，**不测耗时**）

全程在 `/tmp` 里的**临时树**上做，**不动仓库任何文件**（E4/E5 是对生成正文做**单点字符串替换**的单变量实验）：

| 例 | 换回的旧件 | 预期 | 实得 | 红的断言（逐字） |
|---|---|---|---|---|
| E0 | —（新实现基线） | PASS | ✅ PASS `4 passed in 2.77s` | — |
| E1 | 旧 `install_hooks.sh` | 红 | ✅ FAIL rc=1 | `assert res.returncode == 0` ⇒ `assert 128 == 0`（旧脚本在夹具树里以 `128` 结束） |
| E2 | 旧 `pre-commit.sh` | 红 | ✅ FAIL rc=1 | `assert res_a.returncode == 2` ⇒ `assert 1 == 2`（旧版把缺脚本报成**阻断/1**） |
| E3 | 两个都旧 | 红 | ✅ FAIL rc=1 `3 failed, 1 passed` | 上面两条 **+** 用例3 的 `assert res0.returncode == 2` ⇒ `assert 0 == 2`（旧脚本**根本没有 `--check`**） |
| E4 | **只回退薄壳正文那一行**（`exec sh "${root}/…"` → `exec sh "/Users/…"`） | 用例1 红 | ✅ FAIL rc=1 `1 failed, 3 passed` | `AssertionError: 薄壳里出现硬编码绝对路径（判据与对象不同源）：['exec sh "/Users/gaza/Developer/InvestSigh/system/scripts/ops/pre-commit.sh"']` |
| E5 | **只把 `--check` 的比对变成恒真**（`if cmp -s …` → `if true`） | 用例3 红 | ✅ FAIL rc=1 `1 failed, 3 passed` | `assert res2.returncode == 1` ⇒ `assert 0 == 1`（"漂移"不可见） |

★ E4/E5 的意义：**判红条件精确落在"那一行"上**（单变量），不是靠"整个文件都换掉"才红
⇒ 反例**确实**在守那两条不变量。
★ **反向对照**：E4 只让用例1 红（`3 passed`）、E5 只让用例3 红（`3 passed`）
⇒ 四条用例**互不耦合**、各自有独立判别力（若它们整体一起红，说明断言太粗、说不清是谁失效）。

### 8.2 两份输出**不同形**（逐字，仪器 `/tmp/probe13o_capture.py`）

```
=== A-脚本全缺 ===  exit=2
  pre-commit [INPUT-ERROR] append_only_guard：门禁脚本不在被检树 —— …/system/scripts/checks/append_only_guard.py
  …（14 道**逐条**列出，含 rule_key_alignment_guard）…
  pre-commit: [INPUT-ERROR] 有门禁脚本不在被检树 —— 这是**输入错误**，不是违规（exit=2；判据与对象不同源，缺口 G-61）。
  pre-commit: 处置：在本树执行 git merge main 后重试。
  ⇒ 出现 "pre-commit → " 14 次 · 出现「阻断」0 次 · 出现 "can't open file" 0 次

=== B-一道真违规 ===  exit=1
  pre-commit ✗ append_only_guard 阻断（exit=1）
  pre-commit: 有门禁阻断，提交被拒。
```

★ 关键读数（**`口径 9`：连"在哪个树上跑的"一起报**）：上面两份都在 **`/tmp` 临时夹具树**上、
**用本卡新实现**、取样时刻 **2026-09-16 23:05**（`/tmp/probe13o_cap/1789571148/`）。
**不是**在仓库树上、也**不是**经共享钩子跑的。
★ 「阻断」计数 **0** 是这里唯一真正要紧的那个数：**旧实现的同一场景该位置是 1**（E2/E3 已实测）。

### 8.3 漂移探测实测（`--check`）

对**当前仍装着旧薄壳**的共享钩子（只读，未改）：

```
$ sh system/scripts/ops/install_hooks.sh --check
install_hooks --check: **漂移** —— 已安装的薄壳 != 版本化模板（…/.git/hooks/pre-commit）
  * 装的是旧的 => 你正在用**过期判据**跑门禁（可能静默少跑门禁）；…
  -- diff（< 已安装 / > 模板） --
3c3,18
< exec sh "/Users/gaza/Developer/InvestSigh/system/scripts/ops/pre-commit.sh"
---
> # ★ 同源（卡 13-O / G-61）：…
exit=1
```

⇒ **T3 成立**（且**有机器强制**：§8 用例 3）：方向②（"静默失去门禁"）虽**不能自动修**，
但**"装上的 != 版本化的"从此可见**（此前无任何通道能看出来 —— 这正是方向②完全不可观测的原因）。

★ **自指检验**（`CONVENTIONS.md §5.2`，team-lead 升格为通用手法）：本节自身过一遍必问项后，
**如实标注"有无机器强制"** 的那张表在 §8 用例 4 的 `Q8` 自答里：
有机器强制 = 薄壳正文形态 / 退出码契约 / 漂移可分；**没有** = ①方向②不自动报警 ②"钩子真被 git 调用"未验。

## 9. 交付状态与待批准的动作

### 9.1 已完成（**未安装任何共享文件**）

| 项 | 证据 |
|---|---|
| 设计方案 | 本节 §1–§8 |
| `install_hooks.sh` 同源薄壳 + `--print` / `--check` + 自动备份 | `git diff` 130 行改动；`sh -n` 通过 |
| `pre-commit.sh` 输入预检 + 退出码分流 | `git diff` 52 行改动；`sh -n` 通过 |
| **两条可判红反例** | `tests/guards/test_hook_same_source.py`，`--noconftest` ⇒ `4 passed in 2.77s` |
| **判红实测（E0–E5 六例全部符合预期）** | §8.1 |
| **两份输出不同形（逐字）** | §8.2 |
| **漂移可探测（`--check` = 1）** | §8.3 |
| **安装前全量门禁** | 在本树跑**修改后**的 `sh system/scripts/ops/pre-commit.sh` ⇒ `exit=0`，14 道全 PASS（日志 `/tmp/ch2_pc_new.log`） |

### 9.2 待你批准（我**一律没做**）

1. **安装同源钩子**（覆盖共享 `.git/hooks/pre-commit`）——影响全 34 人的 `git commit`，**需你 go**。
   安装后我会：① `--check` 必须返回 `0`；② 在**本树**做一次**真实的 `git commit`** 验证仍能提交；
   ③ 把 `.bak` 路径与回滚命令回贴给你。**不用 `--no-verify`。**
2. 是否同意**否决方案 B**（理由见 §5：**一棵树只能被它自己的规则判**）；
3. `§6` 的"每次提交打印本树 HEAD 一行"要不要（会给每次提交多一行输出）。
   ★ 我**倾向于要** —— 它把"本次用的是哪份清单"变成**可复核的现场**（`口径 10`）；但它是**输出噪音**，故请你定。
4. ★ 顺带登记一个**我没改**的东西（`G-62` 自指检验顺出来的）：
   `pre-commit.sh:29/33/41` 三处"仓库根解析失败/可疑"现在仍 `exit 1`（**违规**语义），
   而按 `G-01` 它们是**输入错误**（`2`）。**改它会动到"根不明"这条路径**，
   与本卡同族但**不是**同源问题的本体 ⇒ 我**没顺手改**（避免把两件事混进一个提交）。
   要不要另开一张小卡？

## 10. 边界（如实）
1. 方向②**我未实测**（我未造出"判据旧于对象"的现场）——机制推断成立，但按 `G-03` **不计为已验证**；
2. 方案 A 的**残余风险 R1**：被检树可以改自己那份 `pre-commit.sh` 来放行自己。
   **缓解**：该改动**必然出现在 diff 里**（明文可见，非静默），且主仓提交用主仓清单 ⇒ **不能在集成线上逃逸**；
   但仍**不是一个机器强制点**，如实登记，不粉饰。
3. 本节**不新增门禁、不改任何守卫判据**（遵 `G-07` 与 team-lead 约束）。
4. 本节所有耗时/配额类读数：**无**（本节不含任何跑批测量）。
