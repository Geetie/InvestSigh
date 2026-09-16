# 口径 11 全仓审计 —— 复跑（卡 `#82`）

| 项 | 值 |
|---|---|
| 工作树 | `/Users/gaza/Developer/InvestSigh/.worktrees/ws-step56-skipped` |
| 分支 | `ws/step56-skipped` |
| 复跑读数时的树 | **`refs/heads/main = 28e1eff`**（当时 `HEAD..main == 0`） |
| 复跑时点 | 2026-09-16 22:47~22:48 +0800 |
| **复验时点（§3.3 / §3.4 用）** | **`refs/heads/main = a368c4e`**，2026-09-16 22:5x +0800 |
| 原审计时点 | `refs/heads/main = fe14d93`，2026-09-16 22:30:41（见卡 `#82` 描述） |
| 本次动作 | **只读 git** + **零删除 pytest**（`--noconftest`，不建夹具、不删任何东西） |
| 未做的事 | 未改 `main`、未合并任何分支、未改 `conftest.py`/`verify.py`、未跑任何需夹具的批次 |

★ **两条红灯的状态随时点变化**：§3.3 的红灯已被 `1f58b16`（22:48:26）消除 —— **我在 22:5x 用 `refs/heads/main = a368c4e` 复验为 `PASSED`**（见 §3.5）；§3.2 的红灯（`injection-f` 33 例）**在 `a368c4e` 上仍在**。

★★ **追加（`refs/heads/main = 1052793` 时点）：§3.2 的红灯 A 也已关闭** —— `#89` 的移片提交 `11968b2`（把 `test_shard_coverage.py` 由 `injection-f` 移入 `injection-g`）落地后，我**同语义复算**逐片例数 = **a30 b32 c31 d29 e32 f27 g24，合计 205，无片 >32**。★ 但 **`b=32`、`e=32` 零余量**（下一例新增无处可放），见 §3.6。**本条是"时点会变结论"的第三次实例**，也见 §3.6.1（我自己就差点把它报成假分歧）。
★ **该提交的作者不可归到任何队友**：本机全局 git 身份统一为 `Geetie`（我自己的提交也是），`%an` 对"哪位队友"零区分力 —— 见 §7.3.5。

---

## §0 一句话

原审计点名的 **3 处「完成卡未进主干」已全部归零**（`ws/real-collect-2` / `ws/ch5-pricelayer` 补合完成、`ws/verify-shard` 也已归零），
**但复跑发现两件原审计没有的事**：① **`ws/verify-shard` 属"只进了一半"** —— 测试进了 `main`、被它断言的实现（`verify.py::PYTEST_MISSING_MARKER`）没进；
② **`main` 上 `verify.py --batch injection-f` 现在必红**（实测 `2 failed, 4 passed`），而这条红**不被 `pre-commit.sh` 也不被 `run_all_gates.py` 跑到**（两者都不跑 verify 分片）⇒ 是一条**静默红**。

---

## §1 复跑快照与一个必须记录的事实：**审计期间 `main` 被推进了 5 次**

我按写死路径开工时 `main = 53de9a3`，复跑结束时 `main = 28e1eff`。期间观测到的推进序列：

```
fe14d93   ← 原审计（卡 #82）时点
53de9a3   merge ws/step56-skipped（口径 11 补合）        ← 我开工时
f2d1371   merge ws/fixture-cost（口径 11 补合）—— 冲突取分支侧：guards 维持 300s
8aa7862   merge ws/ch13-e-benchmark-fields（门禁清单取并集 ⑫/⑬）
69e0090   docs: G-60 源码级升级 + 口径 11 扩展之二（禁用三点 main...b；merge commit 是第 4 种失效模式）
3e644a2   …（继续推进）
28e1eff   ← 本次读数时点
```

★ **口径 11 的结论必须带时点**，否则"某分支已归零"这句话在下一次合并后就可能不再成立 —— 本报告 §2/§3 的所有数字**只对 `refs/heads/main = 28e1eff` 负责**。
★ 附注：**我在本次复跑中把 `ws/verify-shard` 从 `main..b = 3` 观测到 `main..b = 0`**（同一场审计内），即 team-lead 在审计进行中把它合掉了。**这正是"复跑的时点必须写死"的实证。**

### 1.1 ★ 报"`main` 在哪"必须写 **ref 全名**（本仓有三个含 `main` 的 ref）

```
c5a0a22e2f0e  refs/heads/main            ← 真正的 main
3cbc21716ff8  refs/remotes/origin/main
53de9a3e6f59  refs/remotes/tmp/main      ← ★ 值正是本会话开头我读到的 53de9a3
```

⇒ 光写"`main` 是 `53de9a3`"**是有歧义的**（`refs/remotes/tmp/main` 现在仍是这个值）。
**本报告此后一律写全名**：§0~§6 的读数为 `refs/heads/main = 28e1eff`；§7 的更正读数为 `refs/heads/main = c5a0a22`。
（此条由 `ws-ch2-rules` 指出，我复核成立。）

---

## §2 复跑结果（`main@28e1eff`）

### 2.1 步骤① + 步骤③（按口径 11 扩展之二的**两点**写法，不用三点）

| 分支 | `main..b` | 两点内容差分 `main..b` | 判读 |
|---|---|---|---|
| `ws/ch13r-rule-candidates` | 2 | `files=106 +1353/-32938` | **有意丢弃**（见 §4.3） |
| `ws/ch2-rules` | 13 | `files=5 +1569/-159` | **在办**（卡 #69） |
| `ws/fixture-cost` | 3 | `files=5 +165/-119` | **非缺口**（见 §4.2，★ 已更正） |
| 其余 30 个分支 | **0** | — | 已归零 |

★ **本表的"两点内容差分"列只描述"两个末端快照差多少"，它判不出"合并会不会回退 `main`"。**
★ 我最初据该列下的两句判读（"合并会回退 `main`"）**是错的**，已在 **§7** 更正并给出反证。
⇒ **判"回退"必须用 merge-base 语义或干跑**，见 §6 步骤 ③′。

原审计点名的 3 处，现状：

| 分支 | 原判 | 现在 |
|---|---|---|
| `ws/real-collect-2` | ★★ 真缺口（19 文件 main 全无） | **已归零**（`403a398` 补合） |
| `ws/ch5-pricelayer` | ★★ 真缺口（"改写型"，存在性判别抓不住） | **已归零**（`f5700dc` 补合） |
| `ws/fixture-cost` | ★ | `main..b=3`，但**非缺口**（§4.2，★ 已更正判读） |

⇒ **原审计"3 处真缺口"的处置已闭环。**

---

## §3 ★★ 本次复跑的两条新发现（都只在 `injection-f` 批里暴露）

> **状态（`refs/heads/main = a368c4e`，2026-09-16 22:5x 复验）**
> - 红灯 A（`injection-f` 33 例 > 32）：**本行是 `a368c4e` 时点的读数**。★ **已由 `#89` 的移片提交 `11968b2` 关闭**（`f 33→27`、`g 18→24`）—— 我在 `main = 1052793` 时点同语义复算确认，见 §3.6 与头部追加说明。
> - 红灯 B（`PYTEST_MISSING_MARKER` 未进 `main`）：**已被 `1f58b16` 修复**（见 §3.5）。**本条是我在 `28e1eff` 上的真实读数，但描述的是当时状态**；`1f58b16` 的作者**不可判**（本机身份统一，见 §7.3.5），但它与我观测到的形态确实是同一件事。

### 3.1 机器证据（一次跑完，`refs/heads/main = 28e1eff`，零删除）

命令（`--noconftest` 是为了**不触发 `conftest.py::pytest_sessionstart → _clear_work_dir()`**，即不占宿主删除配额）：

```bash
cd /Users/gaza/Developer/InvestSigh/.worktrees/ws-step56-skipped/system
PYTHONPATH=$PWD/tests /Users/gaza/.workbuddy/binaries/python/envs/default/bin/python \
  -m pytest tests/injection/test_shard_coverage.py -q -p no:cacheprovider --noconftest -rA
```

原始输出：

```
PASSED tests/injection/test_shard_coverage.py::test_shard_targets_are_explicit_test_file_paths
PASSED tests/injection/test_shard_coverage.py::test_every_injection_test_file_is_covered_by_shards
PASSED tests/injection/test_shard_coverage.py::test_shard_targets_are_pairwise_disjoint
PASSED tests/injection/test_shard_coverage.py::test_quota_attribution_never_passes
FAILED tests/injection/test_shard_coverage.py::test_shard_case_counts_within_quota
FAILED tests/injection/test_shard_coverage.py::test_missing_pytest_attribution_never_passes
2 failed, 4 passed in 2.21s
```

**注意 4 passed 里有 `test_quota_attribution_never_passes`** —— 这条是**正对照**：它与失败的那条走**完全相同**的机制（`_load_verify()` 加载本仓 `verify.py` + 调 `_exit_zero`），它绿 ⇒ 证明"探针/加载方式"没坏，红的是**被检对象**本身。

### 3.2 红灯 A：`injection-f` 33 例，越过授权上限 32

```
E  AssertionError: 以下片的用例数超过上限 32: {'injection-f': 33}（现算值）
E    → 超限 ⇒ 该片单轮跑不完 ⇒ 又是一次「门禁被静默关掉」。
```

逐文件现算（`--collect-only`，非写死）：

| 文件 | 例数 |
|---|---|
| `tests/injection/test_stage_gate.py` | 10 |
| `tests/injection/test_wiring_guards.py` | 17 |
| `tests/injection/test_shard_coverage.py` | 6 |
| **片 `injection-f` 合计** | **33** |

★ 这正是该断言存在的理由（docstring 逐字）："超限 ⇒ 该片单轮跑不完 ⇒ 又是一次「门禁被静默关掉」"。**实测已经越线**。
★ **处置要 team-lead 裁决**（该文件自己写着"片数是主理人决策，本文件不擅自改"）⇒ 我**不自裁**。
★ 另记：`merge ws/step56-skipped` 带进的 `test_step56_skipped_wiring.py`（3 例）已由主理人**补录进 `injection-a`**（`verify.py:324-334`），故"① 穷尽性"断言是**绿**的 —— 这条 33 例**不是**我那一单造成的。

### 3.3 红灯 B：`ws/verify-shard` 的实现**被合掉了**（"只进了一半"）

```
E  AssertionError: 归因文案应同时指明是「环境」问题与「pytest」缺失，实际是: 'exit=1'
E  assert ('环境' in 'exit=1')
tests/injection/test_shard_coverage.py:386
```

同一文件里那条**在写、且写得很清楚**的断言（第 ⑥ 条，`G-05` 反例）：

```python
assert "环境" in why and "pytest" in why, (
    f"归因文案应同时指明是「环境」问题与「pytest」缺失，实际是: {why!r}"
)
```

它要求 `verify.py::_exit_zero` 对 `No module named pytest` 给出一条**独立归因**（既不是超时 `124`、也不是配额）。实测 `main` 上 `_exit_zero(1, "No module named pytest")` 返回 `'exit=1'` —— **没有任何归因**。

版本计数（只读）：

| 版本 | `PYTEST_MISSING` 计数 |
|---|---|
| `90e58b0^:system/scripts/ops/verify.py` | 0 |
| **`90e58b0:system/scripts/ops/verify.py`** | **3** ← 该提交**加了**这个归因分支 |
| `f2d1371^:system/scripts/ops/verify.py` | 0 |
| `main:system/scripts/ops/verify.py`（28e1eff） | **0** |

⇒ `90e58b0` 把**测试 + 报告 + CONVENTIONS** 带进了 `main`，而**同一提交对 `verify.py` 的改动没有进**。
⇒ 这就是口径 11 第 4 种失效模式（**merge commit 是失效模式**）的一个**活体样本**：单看 `main..b` 已经归零，但**内容有缺口**，而且缺口**表现为 `main` 上的一条红**。

★ **为什么这条红很危险**：`verify.py` 的 `PYTEST_MISSING_MARKER` 正是为了把**"0.1s 全红"归因成"解释器缺 pytest"**（本团队此刻最缺的就是"别把 `E` 读成缺陷"的能力，见 `G-60`/`G-61`）。它现在不在 `main` 上，而**守着它的断言在 `main` 上**。

### 3.4 这两条红**不会被任何门禁自动暴露**

```
$ grep -n "injection\|verify.py" system/scripts/ops/run_all_gates.py      → 无匹配
$ grep -n "injection\|verify.py" system/scripts/ops/pre-commit.sh         → 无匹配
```

★ **本节的取证方法已更正（结论不变，但原取证过程不可信）**：
我最初是用 **shell `grep -n "injection\|verify.py"`** 得到"无匹配"的。事后（`ws-verify-shard` 广播的环境告警）查明：**Bash 工具里的 `grep` 解析到的是宿主 broker 包装器（toybox），不是真 `grep`；我那个模式里的 `\|` 正是它不支持的 GNU 扩展运算符，于是它静默给出空输出，而 `exit 0` 是管道（`| head`/`| wc`）的退出码** —— 精确机制见 **§7.3.4**。我**用 Python 复算**（不经任何 grep）后才敢下结论：

```
run_all_gates.py   "verify.py" 出现 0 次   "verify" 出现 0 次   "injection" 出现 2 次
pre-commit.sh      "verify.py" 出现 0 次   "verify" 出现 0 次   "injection" 出现 2 次
                   那 2 处 "injection" 的真身是 ↓（与分片无关，是另一道门禁）
   run_all_gates.py:47   ("injection_guard.py", "scripts/checks/injection_guard.py", ()),
   pre-commit.sh:95      run_gate "injection_guard" "$CODE_ROOT/scripts/checks/injection_guard.py" "$CODE_ROOT"
```

★ **上面那句"静默给出空输出"不是一个推测 —— 是活体反例，而且受害者是我自己**（可直接复跑）：

```
$ 裸 grep -n "injection\|verify.py" scripts/ops/run_all_gates.py   → （空）      rc=1   ★ 假阴性
$ /usr/bin/grep -n "injection\|verify.py" scripts/ops/run_all_gates.py
    47:    ("injection_guard.py", "scripts/checks/injection_guard.py", ()),      rc=0   ← 真有匹配
$ 裸 grep -n "injection" scripts/ops/run_all_gates.py
    47:    ("injection_guard.py", "scripts/checks/injection_guard.py", ()),      rc=0   ← 去掉 \| 就对
```

⇒ 同一文件、同一实现，**唯一变量是模式里那个 `\|`**；裸 grep 把一行**确实存在**的匹配**藏掉了**（不是"文件里没有"）。
⇒ 我 §3.4 的**结论仍然成立**（`verify.py` 计数为 0，那是 Python 复算的），但**取证过程是真的踩了坑**：如果当时 `run_all_gates.py` 里恰有一行 `verify.py` 的引用，我会**直接把它读成"没有"** —— 这就是 §7.3.4 那张表里 `\|` 那一格的现场证据。

⇒ **结论不变**：`run_all_gates.py` 与 `pre-commit.sh` **都不引用 `verify.py`** ⇒ 都不跑 verify 的分片批。`injection-f` 的红只有**显式**跑 `verify.py --batch injection-f` 的人才能看到。
⇒ ★ 但**过程要被记住**：这次是"**错的工具给出对的结论**" —— **方法不可信时，结论对也是运气**（这正是本项目 `G-03`/`R-04` 要挡的形态）。
⇒ 与 §3.2 那句"门禁被静默关掉"是**同一件事的两种形态**：一个是"该片跑不完"，一个是"该片压根不在门禁链上"。
★ 这是**观察，不是建议** —— 要不要把 verify 分片接进门禁链属主理人裁决（接了会显著拉长提交耗时）。

### 3.5 红灯 B 的**复验**（`refs/heads/main = a368c4e`）：已被修复

有一笔提交修好了同一件事（**★ 该提交的作者不可归到任何队友** —— 本机全局身份统一为 `Geetie`，我自己的提交也全是 `Geetie`，见 §7.3.5）：

```
1f58b16  2026-09-16 22:48:26 +0800
fix(verify): ★ 复原我在 ea0ceae 的补合并里因「整文件取一侧」而丢失的内容
（PYTEST_MISSING_MARKER 常量 + 注释块 + _exit_zero 的环境错误归因分支）
—— 当时 main 上 test_shard_coverage.py 断言其存在 ⇒ injection-f 必红
```

★ 它的 commit message **比我 §3.3 的表述更精确地指出了根因**：不是"合并随机丢了"，而是**在那次补合并里"整文件取一侧"** ⇒ 我 §3.3 的形态判定（口径 11 第 4 种失效模式：merge commit）**方向对，但归因粒度不够** —— 真正的机制是"**冲突解决时整文件取一侧**"，**不是** merge 机制本身。⇒ 我据此在 §7.1′ 把这一条写得更准。

复验读数（我在 `a368c4e` 上重跑同一命令）：

```
PASSED ::test_shard_targets_are_explicit_test_file_paths
PASSED ::test_every_injection_test_file_is_covered_by_shards
PASSED ::test_shard_targets_are_pairwise_disjoint
PASSED ::test_quota_attribution_never_passes
PASSED ::test_missing_pytest_attribution_never_passes     ← ★ 由 FAILED 转 PASSED
FAILED ::test_shard_case_counts_within_quota              ← 红灯 A 仍在
1 failed, 5 passed in 1.74s
```

⇒ **红灯 B 关闭，红灯 A 仍开**（★ 此句是 `a368c4e` 时点；红灯 A 后在 `11968b2` 后关闭，见 §3.6）。本节两条读数（`28e1eff` 的 `2 failed, 4 passed` 与 `a368c4e` 的 `1 failed, 5 passed`）**都是真实读数**，差别只在时点。

### 3.6 ★ 红灯 A 的关闭与一次**我自己的假分歧**（`refs/heads/main = 1052793` 时点）

**结论**：`#89` 的移片提交 `11968b2`（`fix(verify): 按主理人裁定把 test_shard_coverage.py 由 injection-f 移入 injection-g`）落地后，**无片超过 32 ⇒ 红灯 A 关闭**。

我按与 `test_shard_coverage.py::_collect_count` **同语义**独立复算（`pytest <targets> --collect-only -q -p no:cacheprovider --noconftest`，解释器 = `$HOME/.workbuddy/binaries/python/envs/default/bin/python`，pytest 9.1.1，**只收集、不建夹具、零删除**；targets 抽取同 `verification_policy_guard._pytest_targets` 的"遇 `-` 即 break"口径）：

| 片 | 例数 | 余量（32 − 例数） |
|---|---|---|
| `injection-a` | 30 | +2 |
| `injection-b` | **32** | **0 ⚠** |
| `injection-c` | 31 | +1 |
| `injection-d` | 29 | +3 |
| `injection-e` | **32** | **0 ⚠** |
| `injection-f` | 27 | +5 |
| `injection-g` | 24 | +8 |

⇒ **合计 205 / 片数 7 / `tests/injection` 文件 16** —— 与卡 `#91` 的现算真值**逐格一致**（`a30 b32 c31 d29 e32 f27 g24`）。
⇒ ★★ **但 `b=32`、`e=32` 是零余量**：**下一条新增用例无处可放**（任一片 +1 即越限）。红灯 A 关闭不等于"配额问题解决"，只等于"当前配置不再超限"（与 `test_shard_coverage.py` 上方"保留 32 的定位 = 实测可跑的当前配置，**不是**已证明安全"同调）。

#### 3.6.1 ★ 我自己在这里差点报出一个**假分歧**（留痕，`V-11` 仪器轴实例）

对账过程中我先在自己的树里量到 **`f33 g18`**（合计同为 205），与 `#91` 的 `f27 g24` 冲突。**差一点就把它当"卡片写错"报出去。** 实测根因：

```
$ git merge-base --is-ancestor 11968b2 HEAD   → ★ 不成立（不在我 HEAD 里）
$ git merge-base --is-ancestor 11968b2 main   → 成立（在 main 里）
```
⇒ **我的树落后 main 一格**（我上轮 merge 的是 `3653c7c`，而 `11968b2` 是**之后**才进的 main）。**两组数都是真的，被测对象版本不同**：`f33 g18` = 移片前，`f27 g24` = 移片后；**移片只改归属不改总数，故合计都是 205** —— 这个"总数相同、分组不同"的形态最容易让人以为"其中一个是错的"。
⇒ 这正是我在 **§7.3.7 第 4 条**刚写完的那条（`V-10` 的 `607 → 615` 同型）：**真值随被测对象的版本变，结论主语必须写出被测对象的版本/commit**。写完之后不到一小时，我自己就撞了同一堵墙 —— **纪律不是给人看的，是给下一次的自己用的**。
⇒ 处置：`git merge refs/heads/main --no-edit`（`V-12` 非交互）后再复算，得 `f27 g24`；**`f33 g18` 这个读数作废**（它是移片前树上的真值，不是错误，但**不能用于对 `#91` 的判读**）。

---

## §4 对原审计三处定性的更正

### 4.1 `ws/verify-shard`：原判「陈旧无害」**不成立**

原审计写：*"`ws/verify-shard`：陈旧无害 —— main 已有分片机制（`injection-a` 命中 7、main `verify.py` 590 行 > 分支 568 行）"*。

**该判读只看了"机制在不在"，没看"实现全不全"**，属原审计自己登记的方法学自纠第 2 条（**存在性判别漏报"只改既有文件"型缺口**）的**又一次复发** —— 而且这次漏掉的不是"新增文件"，是**同一文件里的一段实现**。
⇒ 更正为：**"陈旧 + 有内容缺口，且在 `main` 上现红"**（§3.3）。
⇒ **结果（`a368c4e`）**：该缺口已由 `1f58b16` 补齐，`test_missing_pytest_attribution_never_passes` 转绿（§3.5）。

### 4.2 `ws/fixture-cost`：`main..b = 3` —— ★ **判读已更正**（原判"合并会回退 `main`"**是错的**）

**原判（错，留痕）**：我据 tip-to-tip 的两点差分说"除它自己的报告外，其余四个文件都是**分支要删掉 `main` 已有内容** ⇒ 以分支为准并入会回退 `main`"。**该推论无效**，反证见 §7.2。

**更正后的判读（`refs/heads/main = c5a0a22`，用 merge-base 语义 + 干跑）**：

```
$ git merge-base ws/fixture-cost main          → ed9687b
$ git diff --name-status ed9687b ws/fixture-cost
M  system/reports/ws_fixture_cost_report.md
M  system/scripts/ops/verify.py
```
⇒ 该分支**相对共同祖先只动了 2 个文件**，**不碰** `batch13_taskbook.md` / `phase1_gap_register.md` / `ws_independent_audit_batch11.md`。

```
$ git merge-tree --write-tree ws/fixture-cost main      → rc=0（无冲突），结果树 35671356
     batch13_taskbook.md          merge == main   ⇒ 未回退
     phase1_gap_register.md       merge == main   ⇒ 未回退
     ws_independent_audit_batch11.md  merge == main   ⇒ 未回退
     verify.py                    merge ≠ main 且 ≠ 分支  ⇒ 双向改动被合并成第三个版本
```

⇒ **更正结论**：`ws/fixture-cost` **不会回退 `main` 的任何报告**；它唯一有语义的是 **`verify.py`**（其中含 13-F 的 `guards` 超时取值，与 `main` 已裁决的 300s 属**同处不同值**）。
⇒ 由"**不要合**"改为"**合不合由主理人按 `verify.py` 那一处取值裁**；报告类文件不是障碍"。
⇒ 3 个提交里 2 个是 `Merge branch 'main'`（口径 11 失效模式 4 仍成立），但**这不构成"回退"**。

### 4.3 `ws/ch13r-rule-candidates`：不是「悬挂引用」，是**`main` 已文档化的「禁止复活」**

原审计写：*"5 个新增文件缺失，但内容已落 `main` 的 `system/rules/*.yaml` …… 候选目录属暂存面；main 有 4 份报告引用该路径 ⇒ 悬挂引用。"*

复跑在 `main` 自己的 `batch13_taskbook.md` 里读到**明确裁决**：

> ### R1 · `ws/ch13r-rule-candidates` **废弃 · 禁止合并**（副产物为 `ws/x13r-dual-diff-audit`）
> `b2e269c` / `ad33a6d` 两个 commit 把 4 份规则候选写进 `system/registry/rule-candidates/`。该目录在 `bb32863` 里已**转为安装件并清除**（`rules/` 成为唯一真源）。若合并该分支，`registry/rule-candidates/` 会复活 ⇒ 违 `G-06`（第二份真源）。

⇒ 更正为：**"有意丢弃，且 `main` 上已有成文理由"**。5 个文件缺失（两点复核仍为 5，`cat-file -e` 逐个确认）**是预期状态**，不是缺口。
⇒ 那 4 份报告对 `system/registry/rule-candidates/` 的引用**是"讲清为何不得复活"的引用**（例如 `ws_ch2_rules_consumption_review.md:800` 逐字写着"已于 `bb32863` 转为安装件后清除……不得复活"）⇒ **不是悬挂引用**。

### 4.4 `ws/ch2-rules`：在办 —— ★ **判读已更正**（原判"会回退 `main`"**是错的**）

**原判（错，留痕）**：我据 tip-to-tip 两点差分说"与 §4.2 同一形态：分支相对 `main` 是'要删掉 taskbook/gap_register/batch11 审计'"。

**更正后的判读（`ws-ch2-rules` 亲测 + 我复核）**：

```
$ git merge-base ws/ch2-rules main          → 261f8c9
$ git diff --name-status 261f8c9 ws/ch2-rules
M  system/reports/ws_ch2_rules_consumption_review.md
M  system/tests/injection/test_criterion_effectiveness.py
```
⇒ 他相对共同祖先**只改 2 个文件**，**不碰**那三份共享报告。

**符号相反的反证（他实测的真实合并 `1e1a197`，两父 = `fc76c23` + `main` `261f8c9`，零冲突）**：

```
batch13_taskbook.md                | 140 ++++
phase1_gap_register.md             | 121 ++++
ws_audit_quota11_recheck_report.md | 246 ++++（本报告，新文件）
ws_independent_audit_batch11.md    |  10 +
verify.py                          |  21 +
5 files changed, 538 insertions(+)
```
⇒ **全是 `+`，一行都没删**；而"140 / 121 / 10"**正是我看到的那几个行数**（`main` 又往前走了：77→140）。
⇒ **更正结论**：合并该分支**不会**回退 `main` 的任何内容；"提交前先 `git merge main`"这条建议**仍成立且他已执行**，但理由是**别的**（`G-61` 门禁清单、避免后续冲突），**不是"防回退"**。

★ 教训（已并入 §6 步骤 ③′ 与 §7.1）：**tip-to-tip 的两点差分判不出"合并会不会回退"** —— 我犯的正是我自己在同一天给 `verify.py` 抓的那类错（**拿一个不表达该语义的读数去下语义结论**）。

---

## §5 残余与边界（做不到的如实说）

1. **`main` 在动**：本报告的数字对 `main@28e1eff` 负责；此后 `main` 再合并，§2 的"已归零"需要复跑确认（复跑命令见 §6）。
2. **我只跑了 `test_shard_coverage.py` 一个文件**：该文件是"不建夹具"的（`--noconftest` 也不影响它，它自己不建夹具），故**零删除配额消耗**。§3.2 的 `injection-f = 33` 是用**同一个文件里现算的**读数，我没有跑整片（整片有 33 例、含建夹具的用例，**会消耗宿主删除配额**，且当前是 `G-60` 噪声期 ⇒ 我不占）。
3. **我没有修任何东西**：`verify.py` 属 team-lead / `ws-verify-shard`，分片划属主理人裁决。本卡是审计卡。
4. **两条红灯没有 `G-` 编号**：编号由主理人分配（`R-04` 不自裁）。我在报告里只给可复现事实与定位。
5. **`ws/ch13r-rule-candidates` 的"两个提交"我没有逐提交判"是否含别的应当保留的内容"** —— 只核了 5 个新增文件的存在性与 `main` 的成文裁决。若主理人要"确认无遗漏的正向价值"，需另开一次逐 diff 复核。
6. **★ 本报告 §4.2 / §4.4 的原始判读是错的**（见 §7.2）。§2.1 表中"两点内容差分"一列**数值本身没错**（它是 tip-to-tip 的真实差值），错的是我据它下的"合并会回退 `main`"结论。两项**已在 §4.2 / §4.4 就地更正**。
7. **本报告 §3 的两条红灯（§3.2 / §3.3）与两种判读方法无关**：它们建立在"**blob 逐字节比较**"（`28e1eff` 时 `main:verify.py` 的 `PYTEST_MISSING` 计数为 0）+ "**真实 pytest 执行**"之上，不依赖任何 diff 方向判读 ⇒ **不受 §7.2 的更正影响**。
   ★ 但**时点会变结论**：**§3.3 的红灯已由 `1f58b16` 修复**（复验 `a368c4e` = `PASSED`，见 §3.5）；**§3.2 的红灯仍在**。
8. **★ 取证工具本身有坑**（§7.3）：Bash 工具里的 `grep` 是 broker 包装器（**toybox 0.8.13**，非 GNU），**失效集 = GNU 扩展运算符 `\|` `\+` `\?` `\<` `\>` `\b`**（★ 按 `team-lead` 定稿，**含 `\b`**；我此前几处漏写 `\b`，已一并补上）—— 对这些会静默返回空（`rc=1`，**不是 `rc=0`**）；而 **POSIX BRE（`\.` `\{n,m\}` `\(\)` `\1`）与纯字面是准的**（§7.3.1/§7.3.4 逐格有真值）。**★ 三条后续修正**：(a) `-E` **不是万能解、更不是"遇到问题就加"**（只对**已改写成 ERE 的模式**有效，见 §7.3.7 第 2 条）；(b) 带 `| head`/`| wc`/`| tail` 的命令 **`rc` 列不可用**（管道吞一切非零码）；(c) `Grep` 工具与 `rg` CLI **在"响亮性"上不同源**（§7.3.7 第 3 条）。
   ★★ **本条的规范出处是主干 `CONVENTIONS.md::V-10`**（它比我全：多一格第三引擎，且已有管道规矩 4）—— 本节只是**独立收敛**，见 §7.3.6。
   ★★★ **本条我原先写的处置是错的、已作废**：我原写"**此后一律用 Grep 工具** / `/usr/bin/grep` / Python"。按 `V-10` 规矩 1，**没有"一律改成 X"的安全写法** —— `Grep` 工具（ripgrep）**也是方言**：它把 `\|` 当**字面竖线**（0 / 真值 20，**静默零**）、**不支持反向引用**（`(.)\1` → 0 / 真值 607，且不报错），只是支持 `\b`。⇒ 正确处置是**知道你在用哪个方言 + 附引擎指纹与 `rc` 原文 + 每格给地板真值**，不是换一把"更高级"的锤子。
   **§3.2/§3.3 的数字不来自 greps**（一个来自断言消息、一个来自 pytest 执行），故不受影响。
9. **本报告 §3.4 的"都不跑 verify 分片"这条**：我最初用坏 grep 取证，**已用 Python 复算重取**（`verify.py` 0 次 / `injection` 各 2 次、均为 `injection_guard`，与分片无关）⇒ 结论保持。★ 且现已**复现出当初那个假阴性**：`grep -n "injection\|verify.py" run_all_gates.py` 裸 grep 给空 + `rc=1`，`/usr/bin/grep` 给**第 47 行**（真的存在）—— 唯一变量就是 `\|`（§3.4 末尾）。
10. **★ `1f58b16` 的作者归不到任何队友**（§7.3.5）：本机全局 git 身份统一为 `Geetie`（我自己的提交也全是），**`%an`/`%ae` 对"哪位队友"零区分力** ⇒ 属 `G-61`（判据与对象不同源）。我只保留"分支名 + commit message 自述"这一层证据，并标注**不可证**。**连带**：`ws/step56-skipped` 上我这 3 个提交，别人同样无法用 git 元数据证明是我写的。
11. **★ 我从主干重新学到的两条方法论**（§7.3.6）：**(a) 举证半径陷阱的反向形态** —— `ws-verify-shard` 按 `V-11` 更正了他"你没覆盖 X"的越界（只读了回信、没读主干）；**我接受前也没去主干查**，同族。⇒ 收到"你没覆盖 X"，**第一步是去主干查 X 是否存在**。**(b) `V-10` 规范仪器 `probe_grep_engine.sh` 只跑 BRE 列、不含 `-E`** —— 我那张表的 `-E` 列**恰好补上这个缺口的一半证据**，但**我不动主干文件、也不另做重复探针**，只向主理人申报（§7.3.6 末）。
12. **★ 按 `team-lead` 定稿补测后的三条修正**（§7.3.7）：**(a)** 失效集**含 `\b`**，我此前多处漏写，已全部补上（实测裸 BRE `\bxaa` → 0 / `rc=1`，真值 1）；**(b)** 「遇到问题就加 `-E`」**是危险建议**，我原先的表述不够严 —— `-E` 只对**已改写成 ERE 的模式**有效，**原样字符串加 `-E`** 在 `/usr/bin/grep` 上 `rc=2` 响亮、在裸 toybox 上**静默 `rc=1`**（同一条建议换引擎，后果反向）；**(c)** `V-12`（非交互 merge）我已自查：`5318e74` 明确带 `-m`，`981e7cc` **不可判**（默认消息非唯一指纹），且**无 `MERGE_HEAD`/`MERGE_MSG` 残留、全仓无模板污染提交** ⇒ 我这边**未发生** `V-12` 事故。
13. **★ 我申报的仪器缺口（`-E` 两列 + ripgrep 列无背书）在主干仍开着**（`refs/heads/main = 612cafe` 时点：`probe_grep_engine.sh` 仍只有 `BARE_GREP` / `REAL_GREP` 两列）。**等主理人派活，我不自裁、不改主干文件、不另建重复探针。** 另附一条：`V-10:481` 的"**且不报错**"只对 **`Grep` 工具**成立，对 **`rg` CLI 不成立**（后者 `rc=2` + 解析错误 + `--pcre2` 提示）—— 见 §7.3.7 第 3 条。
14. **★ 红灯 A 已关闭（`11968b2` 之后），但"关闭"≠"解决"**（§3.6）：我同语义复算 `a30 b32 c31 d29 e32 f27 g24 = 205`，无片 >32 ⇒ 关；**但 `b=32` / `e=32` 零余量，下一条新增用例无处可放**。另：**`f33 g18` 是我落后 main 一格时量到的旧值，已作废**（§3.6.1 留痕 —— 我自己差点把"版本不同"报成"卡片写错"）。
15. **★ 我 6 个提交已全部进 `main`**（`8ada895` merge；`main..ws/step56-skipped` 现已为空）；且 `main` **已采纳**我 §7.3.7 的两条发现：`3d35a76`「`V-10` 拆分 `rg` CLI 与 `Grep` 工具（响亮性不同源）+ 数字带对象版本 + 同名参数不同义」、`1052793`「`V-10` 地板真值改引仪器（**承认此前违反自身 `V-11` 仪器轴**）」。**"待合并"这一项对我的卡已清零。**

---

## §6 复跑指引（可照抄，★ 已按 §7 更正）

```bash
R=/Users/gaza/Developer/InvestSigh

# 0) 先记住时点，并★写明 ref 全名（本仓有三个含 main 的 ref，会互相冒充）
git -C "$R" rev-parse refs/heads/main        # ★ 不要只写 "main"

# 1) 步骤①：哪些分支 main..b != 0
for b in $(git -C "$R" for-each-ref --format='%(refname:short)' refs/heads | /usr/bin/grep -v '^main$'); do
  n=$(git -C "$R" rev-list --count refs/heads/main.."$b"); [ "$n" != 0 ] && echo "$n  $b"
done

# 2) 步骤②：存在性（"分支有而 main 没有的文件"）
#    ★ 不要用 git rev-parse main:$f —— 路径不存在时它会把参数回显到 stdout（口径 11 自我更正 1）
for f in $(git -C "$R" diff --diff-filter=A --name-only refs/heads/main..<branch>); do
  git -C "$R" cat-file -e refs/heads/main:"$f" 2>/dev/null && echo "IN_MAIN  $f" || echo "MISSING  $f"
done

# 3) 步骤③：分支"相对共同祖先改了什么"（= 我方改动面）
#    ★★ 不要用 tip-to-tip 的 `git diff main..b` 下"会不会回退 main"的结论 —— 它不表达 merge-base 语义（§7.1）
base=$(git -C "$R" merge-base refs/heads/main <branch>)
git -C "$R" diff --name-status "$base" <branch>

# 3′) ★ 判"合并会不会回退 main"：干跑，看结果树里的 blob 是不是 main 那一份
T=$(git -C "$R" merge-tree --write-tree <branch> refs/heads/main | head -1); echo "rc=$?"
for f in <你关心的文件…>; do
  a=$(git -C "$R" rev-parse refs/heads/main:"$f" | cut -c1-10)
  b=$(git -C "$R" rev-parse "$T:$f" | cut -c1-10)
  [ "$a" = "$b" ] && echo "未回退  $f" || echo "★需人看 $f（=$b）"
done
#    rc=0 ⇒ 无冲突；blob==main ⇒ 该文件未被分支改动/未被回退；blob 两侧都不是 ⇒ 双向改动被合并成第三个版本

# 4) 本报告 §3 的两条红灯（零删除：--noconftest 关掉夹具会话钩子）
cd "$R/.worktrees/<你的树>/system"
PYTHONPATH=$PWD/tests /Users/gaza/.workbuddy/binaries/python/envs/default/bin/python \
  -m pytest tests/injection/test_shard_coverage.py -q -p no:cacheprovider --noconftest -rA
```

★ 若矩阵里出现 `E`/`INTERNALERROR`：**先查有没有 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`**（`G-60`），**不要**读成缺陷、**不要**绕过（`G-60` 处置规矩）。本报告 §3 的全部读数**不建夹具、不删文件**，故**不受 `G-60` 影响**。
★ 别把 `*.yml` 和 `*.yaml` 写进同一条 glob（`no matches found` 会让整条命令静默中止）；别把"无匹配即 `exit 1`"的命令（如 `git grep -c`）串在 `&&` 前面。

---

## §7 自我更正留痕（`refs/heads/main = c5a0a22` → 复验 `a368c4e` 时点）

### 7.1 口径 11 的**第三个**失效模式：**两点号 `main..b` 也不能判"会不会回退 `main`"**

team-lead 已入册"**禁用三点 `main...b`**"（多 merge base 时任意选一）。本次**新增一条**：**两点号同样不行**，因为

```
git diff A..B   ≡   git diff A B       # ★ tip-to-tip：两个末端快照的差，不携带 merge-base 语义
```

⇒ 当 `main` 在分叉后**继续前进**时，tip-to-tip 里那些 `−` 行**是 `main` 自己新增的内容**，不是"分支要删的内容"。
⇒ **判"回退"必须二选一**：① `git diff --name-status $(git merge-base main <b>) <b>`（写明 merge-base，即"我方改动面"）；② **最直接**：`git merge-tree --write-tree <b> main` 干跑，再比对结果树里的 blob。

**三种读法的对照表**（`A`=`main`，`B`=分支）：

| 命令 | 语义 | 能判"分支有而 main 没有的文件" | 能判"合并会不会回退 main" |
|---|---|---|---|
| `git diff --diff-filter=A --name-only A..B` | tip-to-tip；`A` 过滤 = "在 B 不在 A" | ✅ | ❌ |
| `git diff A...B` | merge-base→B，多 base 时**任意选一** | ⚠（多 base 时不可靠） | ⚠ |
| `git diff $(git merge-base A B) B` | 我方改动面 | ⚠（同左） | ✅ |
| `git merge-tree --write-tree B A` | **真干跑** | — | ✅✅（最直接） |

### 7.1′ 对 team-lead「失效模式 4（merge commit）」的一处**精确化**

§3.3 我原写"这是 merge commit 这种失效模式的活体样本"。修复提交 `1f58b16` 的 commit message 逐字给出了**真正的机制**（★ 该提交**归不到具体队友**，理由见 §7.3.5；但机制由 message 自述 + diff 内容支撑，**与作者是谁无关**）：

> 复原我在 `ea0ceae` 的补合并里**因「整文件取一侧」而丢失**的内容

⇒ 精确化：**失效的不是"merge 这件事"，而是"冲突/补合并时对整文件取一侧"这个动作**。
⇒ **可操作条文化**：补合并/解冲突时，**不要对整个文件取一侧**；要么逐 hunk 判，要么在合并后用 `git diff` 逐文件复核"我方改动面"（§7.1 表第 3 行）是否仍在结果里。
⇒ 这比"merge commit 危险"更能指导下一次操作 —— 归因粒度决定处置是否可执行。
（本次两半互补：`1f58b16` 的 message 报出机制；我报出"测试进了、实现没进"这个可观测形态。**发现权不可归人** —— 作者身份在本机不可判，见 §7.3.5。）

### 7.2 我犯的错与反证（原判 → 更正）

我把 §2.1 的 tip-to-tip 差分读成"**分支要删掉 `main` 已有内容 ⇒ 以分支为准并入会回退 `main`**"，并对 `ws/fixture-cost`、`ws/ch2-rules` 各下一句判词。**两句都错。**

- `ws-ch2-rules` 给出**符号相反的反证**：他真实 `merge main`（`1e1a197`，零冲突）后 `taskbook +140 / gap_register +121 / audit_batch11 +10` —— **全是 `+`**，且这三个数**正是我看到的那些行数**（`main` 又前进了）。他相对 merge-base **只改 2 个文件**。
- 我用**同一方法复核 `ws/fixture-cost`**：merge-base `ed9687b`，相对它**只改 2 个文件**；`merge-tree --write-tree`（rc=0，无冲突）结果树里三份共享报告的 blob **逐字节等于 `main` 那一份** ⇒ **未回退**。唯一需人看的是 `verify.py`（合并产生第三个版本）。

**根因**：我拿一个**不表达该语义的读数**（tip-to-tip 差分）去下**语义结论**（合并方向）。这与我在同一天给 `verify.py` 抓的错**同类**（"归因与对象不同源"），所以按同一标准处理：**就地更正 + 保留原判原文 + 给出反证**，不把错句悄悄删掉。

★ 副作用提醒：我此前发给 team-lead / `ws-ch2-rules` 的消息里**已含这两句错判**，已在随后的更正消息中撤回；**以本报告 §4.2 / §4.4 为准**。

### 7.3 ★ 环境坑：Bash 工具里的 `grep` 是 broker 包装器 —— ★ **但"静默返回空"是过度概括**

由 `ws-verify-shard` 广播、`ws-criterion-effectiveness` 更正过一轮；**我按"每格都要地板真值"重做了一张完整矩阵**，结论见下。

★ **读本节请按这个顺序**（结论已被后续证据三次修正，别只读前半）：**§7.3.1 矩阵（POSIX BRE 可信；失效集按定稿含 `\b`）→ §7.3.4 闭环（`rc` 差异 = 管道吞码；`-E` 非万能）→ §7.3.5 归属更正（作者不可判）→ §7.3.6 与主干 `V-10` 对账（★ 本节 grep 结论主干**已先有**，本节**不是增量**）→ §7.3.7 按定稿补测（★ **3 处修正 + 2 条新发现**：`rg` CLI 与 `Grep` 工具**响亮性不同源**）**。其中 §7.3.2 里"我复现不出他的读数"这个措辞**已作废**。

```
$ which -a grep
/Applications/WorkBuddy.app/…/cli/vendor/shim/brokered-bin/grep    ← ★ PATH 优先命中
/usr/bin/grep
```

**我中的两次**（都在本次审计里）：

1. 查 `main:verify.py` 里 `环境\|pytest` 的分布 ⇒ **返回空**。我先是怀疑"模式方言"，后才用**分开的两次 grep + 逐版本计数**得到真值。**若我当时就用它下结论，会得出"main 里连 `pytest` 字样都没有"这种明显错误的判断。**
2. 查 `run_all_gates.py` / `pre-commit.sh` 是否跑 verify（§3.4）⇒ **两条"无匹配"**，我用它写了"都不跑 verify 分片"。**结论后来经 Python 复算是对的**（两者确实不引用 `verify.py`），但 **`injection` 其实各出现 2 次** —— 我的取证过程给出的是**假证据**，只是碰巧结论为真。

#### 7.3.1 ★ 地面真值矩阵（受控输入 `['aab','ab','a.b','aa','zz']`，真值列 = Python `re`；**每格都有真值**）

| 用例 | 真值 | 裸 `grep`(BRE) | rc | `/usr/bin/grep`(BRE) | rc | 裸 `-E` | rc | `/usr/bin/grep -E` | rc |
|---|---|---|---|---|---|---|---|---|---|
| 纯字面 `ab` | 2 | **2** ✅ | 0 | 2 | 0 | 2 | 0 | 2 | 0 |
| `\.` 字面点 | 1 | **1** ✅ | 0 | 1 | 0 | 1 | 0 | 1 | 0 |
| `\|` 交替 | 5 | **0** ★ | 1 | 5 | 0 | 5 | 0 | 5 | 0 |
| `\+` 一或多个 | 2 | **0** ★ | 1 | 2 | 0 | 2 | 0 | 2 | 0 |
| `\?` 零或一 | 3 | **0** ★ | 1 | 3 | 0 | 3 | 0 | 3 | 0 |
| `\(a\)\1` 反向引用 | 2 | **2** ✅ | 0 | 2 | 0 | **0** ★ | 1 | **2** ✅ | 0 |
| `\{2\}` 恰好两个 | 2 | **2** ✅ | 0 | 2 | 0 | 2 | 0 | 2 | 0 |
| 不匹配字面 `zz9` | 0 | 0 ✅ | 1 | 0 | 1 | 0 | 1 | 0 | 1 |

⇒ **精确规则（`ws-criterion-effectiveness` 的更正成立；失效集按 `team-lead` 定稿补齐 `\b`）**：裸 `grep` = **严格 POSIX BRE**，缺的只是 **GNU 扩展运算符 `\|` `\+` `\?` `\<` `\>` `\b`**（★ 我这一版此前漏写 `\b`，实测裸 BRE `\bxaa` → **0 / `rc=1`**，真值 1 ⇒ 确实在失效集内）；POSIX BRE 的 `\.`、`\{n\}`、`\(…\)`、`\1` **全部正常**。失败形态 = **0 命中 + `rc=1` + 无诊断**（**不是 `rc=0`**）。

#### 7.3.2 ★ 我补的两格（两张既有矩阵都没有的）

1. **"纯字面**且**确有匹配"这一格**：裸 `grep` **返回 2 = 真值，完全正确**（用 `-c "_safe_shutil_rmtree"` 打一个含 4 次命中的文件 → `'4\n' rc=0`，与 `/usr/bin/grep` 一致）。
   ⇒ 我据此把"**裸 grep 一概静默返回空**"这个一般化表述收窄。**★ 但此后（`ws-verify-shard` 回信）这个"复现不出"的措辞本身也作废了** —— 见 **§7.3.4**：`rc` 差异的真根因是**管道吞退出码**，既不是他的输入不同、也不是 shim 有状态。**本节结论（POSIX BRE 范围内裸 grep 可信）仍成立**，只是"复现不出"这个理由已作废，以 §7.3.4 为准。
2. **`-E` 并非无条件安全**：`-E` 反向引用在**裸 grep 上丢**（0，真值 3）、在 **`/usr/bin/grep` 上正确** ⇒ **"改用 `-E`"只在 `/usr/bin/grep` 下成立**。★ 此条已在 **§7.3.4** 被**加强**：裸 `grep -E` 连 `\b`（词边界）也照样静默丢 ⇒ **`-E` 不是万能解**。

#### 7.3.3 我自己在这张矩阵里也犯过一次"对照不成立"（留痕）

第一版探针里，我给 `\+` / `\?` 两格**把 ERE 写法喂给了 BRE 的 grep**（`a+b` 而不是 `a\+b`），于是那两格的 0 是"**真值本身就该是 0**"（BRE 里 `+` 是字面），**不是工具失效**。我发现后**重做**了整张表（上面这版每格都重新对了真值）。
⇒ 这正是本轮大家在收敛的同一件事：**没有真值列的格子不许进结论**；而且**真值必须与被测命令用同一个语义**（我这次的错法是"真值用 ERE、命令用 BRE"）。

#### 7.3.4 ★ 闭环：`rc=1` vs `exit 0` 之争的真根因 = **管道吞退出码** —— 两个读数都是真的，**对象不同**

> ★ **先读 §7.3.6**：本节的管道结论与 `\b` / `-E` 结论，主干 **`CONVENTIONS.md::V-10` 已先有**（且多一格"`Grep` 工具"）。本节是**独立收敛**，**不是新发现**。

`ws-verify-shard` 给出决定性差分（同文件、同模式、**唯一变量 = 是否过管道**），**我逐格独立复算，全部成立**：

```
文件 system/scripts/ops/verify.py（710 行）、模式 "def \|import"
(1) 裸 grep 单独跑                  → 0 行   rc=1
(2) 裸 grep | head -1               → 0 行   rc=0    ← ★ 管道吞码
(3) 裸 grep | wc -l                 → 0 行   rc=0
(4) 裸 grep > /dev/null             →        rc=1    ← 重定向不吞码，只有管道吞
对照：裸 grep -c "import"            → 12     rc=0    ← 无扩展运算符时正确
      /usr/bin/grep -c "def \|import" → 20
      Python re 真值                 → 20     （= 8("def ") + 12("import")）
```

⇒ **`rc=1` 是 grep 的；`exit 0` 是管道的。** 他把 `0` 记成 grep 的退出码，是因为当时的命令形状里带 `| head` / `| wc -l` —— 正是主理人告警里那条"管道会吞退出码"。**"谁也复现不出谁"到此关闭。**

★ **我额外补一格（他矩阵里没有）**：管道吞的是**所有非零码，不只是 1**。我第一次拿错路径跑出 `rc=2`（`No such file or directory`），过 `| head -1` 之后同样变成 **`rc=0`**。
⇒ 纪律升级：**命令形状里带 `| head` / `| wc` / `| tail` 的，`rc` 列一律不可用**；要真码就写 `{ cmd; echo "EXIT=$?"; } 2>&1 | head`。

★ **他给的另两条，我也逐格复算成立**（**每列按各自的方言书写**；真值列 = Python `re` 同语义的匹配行数；★ = 该格 ≠ 真值）：

| 用例（语义） | 真值 | 裸 `grep` BRE | `/usr/bin/grep` BRE | 裸 `grep -E` | `/usr/bin/grep -E` |
|---|---|---|---|---|---|
| 字面 `ab` | 2 | 2 ✅ rc=0 | 2 ✅ rc=0 | 2 ✅ rc=0 | 2 ✅ rc=0 |
| 交替（BRE 写 `\|` ↔ ERE 写裸竖线） | 7 | **0 ★ rc=1** | 7 ✅ rc=0 | 7 ✅ rc=0 | 7 ✅ rc=0 |
| 一次以上（BRE `\+` ↔ ERE `+`） | 2 | **0 ★ rc=1** | 2 ✅ rc=0 | 2 ✅ rc=0 | 2 ✅ rc=0 |
| 可有可无（BRE `\?` ↔ ERE `?`） | 6 | **0 ★ rc=1** | 6 ✅ rc=0 | 6 ✅ rc=0 | 6 ✅ rc=0 |
| **词边界 `\b`** | 1 | **0 ★ rc=1** | 1 ✅ rc=0 | **0 ★ rc=1** | 1 ✅ rc=0 |
| **反向引用（BRE `\(a\)\1` ↔ ERE `(a)\1`）** | 3 | 3 ✅ rc=0 | 3 ✅ rc=0 | **0 ★ rc=1** | 3 ✅ rc=0 |
| 词边界改用 `-w xaa`（替代解） | 1 | **1 ✅ rc=0** | 1 ✅ rc=0 | 1 ✅ rc=0 | 1 ✅ rc=0 |

⇒ 三条硬结论：
1. **`-E` 不是万能解**：裸 `grep -E` 修好了 `\|` `+` `?`，**却仍然静默丢掉 `\b` 与反向引用**（同样是"空输出 + `rc=1` + 零诊断"）。
2. **词边界一律用 `-w`，不要用 `\b`**（`-w` 在裸 grep 上即正确）。
3. **反向引用留在 BRE**（`\(a\)\1` 在裸 grep 上正确；**改 `-E` 反而会丢**）。

★ 附带一条我自己**第二次**犯的同类错（留痕）：第一版新探针我把 **BRE 写法的模式喂给了 `-E` 列**，于是 `-E` 两列恒为 0 —— 那是"**真值本来就该是 0**"的假象，**不是工具失效**。已重做（上表每列给对的写法）。**同一条纪律在本报告里已写两遍、我犯了两遍** ⇒ 它值得进 `CONVENTIONS.md`。

#### 7.3.5 ★ 归属更正：`1f58b16` **归不到任何队友** —— 本机 `%an` 恒为 `Geetie`

`ws-verify-shard` 要我把 §3.3 / §3.5 / §7.1′ 里"`1f58b16` 是 `ws-verify-shard` 修的"撤回。**结论我接受；但他的理由不成立，而真实理由更要命**：

```
$ git config --global user.name   → Geetie
$ git config --global user.email  → 23301010041@m.fudan.edu.cn
$ git config --local  user.name   → （未设 ⇒ 全部继承全局）
$ 1f58b16 的 author / committer   → Geetie <23301010041@m.fudan.edu.cn>
★ 我确信由我提交的 7c816c4 / c319858 / 988d800 / 0ccf90d → 四个也全是 Geetie
$ git log --format=%an -12 main | sort | uniq -c → 12 行全为 Geetie
```

⇒ **全机所有队友共用一个 git 身份**，`%an` / `%ae` 对"**是哪个队友**"**零区分力**。他证的是"作者名叫 Geetie"—— 可**每个人都是 Geetie**，所以这条证据**指向不了任何结论**（他排除掉的那个候选，本来是唯一正确解释）。
⇒ 这是 **`G-61`（判据与对象不同源）** 的又一实例：拿"**提交者姓名**"回答"**哪位队友执行了这次提交**"。

**我只能写能证的**：
- **可证**：`1f58b16` 的 parent 是 `28e1eff`；message 自述"复原**我**在 `ea0ceae` 的补合并里因「整文件取一侧」而丢失的内容"；`ea0ceae` 的 message 是 `merge ws/verify-shard（口径 11 补合）—— 冲突取主干侧`。
- **不可证**：`ea0ceae` 与 `1f58b16` **分别由哪位队友执行**。git 元数据给不出答案（作者字段恒定、无签名、无 note）；commit message 的措辞**可猜测但不构成证据**。
- ⇒ 处置：把"`ws-verify-shard` 自己修的"**改为"作者不可判"**（已就地改 §3.3/§3.5/§7.1′/头部），同时**保留机制归因**（"补合并整文件取一侧"）—— 那条由 message 自述 + diff 内容支撑，**与作者是谁无关**，仍然成立。
- ⇒ 同理 §7.1′ 的"发现权归 `ws-verify-shard`"改为"机制由 `1f58b16` 的 message 给出；**由哪位队友写出不可判**"。
- ★ 连带自查：本报告 §3.3 那句"`ws/verify-shard` 的实现被合掉了"里的**分支名**是真的（`ea0ceae` 的 message 明写 `ws/verify-shard`），**但"哪些提交属于他"仍然不可判** —— 分支名与队友名的对应关系同样是别人的口头声明，不是 git 事实。**这条同样适用于我自己的分支**：`ws/step56-skipped` 上的 3 个提交，别人也无法用 git 元数据证明是我写的。

#### 7.3.6 ★ 与主干 `V-10` 对账：**本节是独立收敛，不是增量**（`refs/heads/main = 3653c7c`）

`ws-verify-shard` 按 `V-11`（举证半径 = 结论半径）**自我更正**：他那封"两个你还没覆盖的 ★"**越界了** —— 他只核了**我的回信**，**没核主干**。我随后 `git merge refs/heads/main`（merge commit `5318e74`）读到主干原文。**核对结果：他对，而且比他说的更彻底。**

主干 `system/CONVENTIONS.md::V-10` **已经**包含（逐项对账）：

| 我 §7.3.4 里写的 | 主干 `V-10` 的对应物 | 判定 |
|---|---|---|
| 裸 BRE 丢 `\|` / `\+` / `\?`（0 + `rc=1`） | 失效集合表**同一行** | **已有**（★ 我此前漏写 `\b`，主干**含** `\b` —— 见 §7.3.7 第 1 条） |
| 裸 `-E` 丢 `\b` 与反向引用；处置 = 改 `-w` / 留 BRE | 失效集合表**同一行 + 同一处置**（明写"`-E` 救不了""`-E` 会静默丢"） | **已有** |
| 管道吞退出码（`\|head` → rc0；**重定向不吞**） | **规矩 4**（并**点名**"`ws-verify-shard` 差分 + `ws-step56-skipped` 独立复算"） | **已有** |
| ★ 管道吞的是**所有**非零码（`rc=2` 过 `\|head` 也变 `0`） | 规矩 4 的 ★ 行（**逐字收录了我这条**） | **已有** |
| ——（我没有这一格） | 规矩 1 **多一格第三引擎**：`Grep` 工具（ripgrep）把 `\|` 当**字面竖线** ⇒ 0 / 真值 20，**也是静默零** | **主干比我全** |
| 真值纪律"真值必须与被测命令同语义" | 规矩 3（地板真值）+ 元规矩（先做区分实验） | **已有** |

⇒ **我 §7.3.4 那张表是"独立收敛"，不是"新发现"**。我原先那句"他给的另两条"**两头都错**：①不是我发现的；②也不是他发现的 —— **主干先有**。已在 §7.3.4 顶部挂指针、§5 第 8 条改引 `V-10`。

★ **主干多出来的第三引擎，我逐格复算**（用 `Grep` 工具本体，同一文件 `ops/verify.py`）：

| 模式 | ripgrep（`Grep` 工具） | 地板真值（Python `re`） | 判定 |
|---|---|---|---|
| `def \|import` | **0**（No matches） | **20** | ✗ 静默零（`\|` = 字面竖线） |
| `(.)\1` | **0**（No matches，**不报错**） | **607** | ✗ 静默零（不支持反向引用） |
| `\bdef ` | **8** | **8** | ✓ 支持 `\b` |

（真值 20 / 607 / 8 与 `V-10` 印的数字**逐字相同** ⇒ 主干那三格也是在同一个 `verify.py` 上量的。）

★★ **唯一可能算增量的东西 —— 我只有一半证据，故只申报、不自裁**：`V-10` 的失效集合表**有两列 `-E`**，但其**规范仪器 `probe_grep_engine.sh`（106 行）只跑 BRE 列、不含 `-E`**（我逐行核过，脚本里没有任何 `-E`）；`ws-verify-shard` 也独立指出并向主理人登记了这一点。我那张表**恰好测了 `-E` 列且每格带 Python 真值**，但那只是**一次性测量、没有沉淀成仪器**。⇒ **我不做**：①不碰主干那个脚本（不是我的文件）；②**不另做一份重复探针**（会与主干撞车，且这是主理人的活）。**若要给 `-E` 两列补仪器背书，请主理人指派。**

★★ **元教训（`V-11` 的实例）**：`ws-verify-shard` 的越界形态是"**举证半径 = 我读过的材料**"（只读了我的回信，没读主干），结论半径却写成"你还没覆盖"。**这与我自己"复现不出"的错法同族** —— 都是**样本比结论窄**。⇒ 收到"你没覆盖 X"这类断言，**第一步是去主干查 X 是否存在**，而不是先接受它。

#### 7.3.7 ★ 按 `team-lead` 定稿（唯一一封广播）补测：**3 处修正 + 2 条新发现**

定稿把口径定死（`CONVENTIONS.md::V-10 / V-11 / V-12` + 仪器 `probe_grep_engine.sh`）。我逐条对账，**有 3 处我该改、2 条是我先前没测出来的**。

**1. 失效集含 `\b` —— 我此前几处漏写，已补**

定稿失效集 = `\|` `\+` `\?` `\<` `\>` **`\b`**。实测复核（真值 1，输入含 `xaa`）：

```
裸  BRE '\bxaa'   → 0   rc=1   ★ 在失效集内（静默）
ub  BRE '\bxaa'   → 1   rc=0   真值 1 ✓
rg      '\bxaa'   → 1   rc=0   ✓（ripgrep 支持 \b）
裸  -w  xaa       → 1   rc=0   ✓ 正解
```
我已把 **§5 第 8 条 / §7.3.1 结论 / §7.3 规矩 / §7.3.6 对账表**里漏掉的 `\b` 全部补上。

**2. ★★「遇到问题就加 `-E`」是危险建议 —— 实测坐实（这一段我原先是错的）**

定稿第 4 条：`-E` 只对**已改写成 ERE 的模式**有效。我按仪器纪律**先自检模式字节**（`assert BRE == "\\(abc\\)\\1" and len(BRE)==9`，输入含 `abcabc`，真值 1），再测：

| 命令 | 命中 | `rc` | 诊断 | 判定 |
|---|---|---|---|---|
| `ub` BRE `\(abc\)\1` | **1** | 0 | — | ✓ |
| `裸` BRE `\(abc\)\1` | **1** | 0 | — | ✓ |
| `ub -E` `(abc)\1`（**已改写**） | **1** | 0 | — | ✓ |
| `裸 -E` `(abc)\1`（已改写） | 0 | 1 | 无 | ✗ 静默零 |
| **★ `ub -E` `\(abc\)\1`（原样）** | 0 | **2** | `grep: invalid backreference number` | ★ **全表唯一响亮** |
| **★ `裸 -E` `\(abc\)\1`（原样）** | 0 | **1** | 无 | ✗ **静默** |
| `ub -E` `\(abc\)`（原样、去掉 `\1`） | 0 | 1 | 无 | ✗ 静默 |

⇒ **同一句"加 `-E`"，在 `/usr/bin/grep` 上是响亮的 `rc=2`，在裸 toybox 上是静默的 `rc=1`** —— 「从一种静默换到更广的静默」**实锤**，而且**换引擎会让同一条建议的后果反向**。
⇒ 正确动作（定稿第 4 条，我照抄）：`-E` **且同时改写模式**（`\|`→`|`、`\+`→`+`、`\{n\}`→`{n}`）；词边界用 **`-w`**；**反向引用只能留在 BRE**。
⇒ ★ 附带留痕：我在补测这段时**又**把 BRE 模式写错一次（漏一个反斜杠，被 `ub` 回 `parentheses not balanced` 暴露），**第二次**把模式写成双反斜杠（被我自己打印的 `repr` 暴露）⇒ 我加了 `assert`，**模式字节自检不过就中止**。这是本报告里我第 **4** 次在"对照不成立"上栽跟头，**每次都不是结论错，而是仪器错**。

**3. ★★ 新发现：`Grep` 工具与 `rg` CLI **在"响亮性"上不同源**（定稿把 `rg` 列为独立引擎，但 `V-10:481` 仍把两者当同一对象）**

主干 `V-10:481` 现行措辞：「`Grep` 工具（ripgrep / Rust regex）… 但**不支持反向引用**（`(.)\1` 实测 **0**、地板真值 **607**，**且不报错**）」。**同一模式、同一文件（`ops/verify.py`）、我实测两层外壳**：

| 对象 | 命令 | 结果 | 响亮？ |
|---|---|---|---|
| **`rg` CLI** | `rg -c '(.)\1' ops/verify.py` | **`rc=2`** + `rg: regex parse error: (?:(.)\1) … error: backreferences are not supported` + **`Consider enabling PCRE2 with the --pcre2 flag`** | ★ **响亮，还给正解** |
| **`Grep` 工具** | `Grep pattern='(.)\1'` | **「No matches found」**（0） | ★ **静默** |

⇒ **`Grep` 工具这层封装把 `rg` 的 `rc=2` + 解析错误吞成了"零命中"。** 这是 `G-62` 的最坏形态 —— **响亮信号被外壳销毁**，也正是 `V-10` 规矩 2 那句"`Grep` 工具**不暴露 `rc`**"的**后果**。
⇒ 处置建议（**供主理人，我不自裁**）：`V-10:481` 的"**且不报错**"应限定为 **`Grep` 工具**；`rg` CLI 那一行宜写"**`rc=2` 响亮，并给出 `--pcre2` 出路**"。**"改用 `rg` CLI"在反引用这一格上确实比 `Grep` 工具好** —— 因为它至少会喊。
⇒ ★ 另一条 `rg` 专属坑：**`rg -E` 不是 extended-regex，是 `--encoding`** ⇒ `rg -E '(abc)\1'` → `rc=2` + `unknown encoding`。**跨引擎照抄参数，本身就是一个新的静默/响亮来源。**

**4. ★ 真值随被测对象的**版本**变：`607` → `615`**

`V-10:481 / :538` 引的"地板真值 **607**"是**合并前**的读数。我 `merge refs/heads/main`（`5318e74`）时，那次合并给 `verify.py` **增了 9 行** ⇒ 同文件、同模式 `(.)\1` 真值变 **615**（`rg -c` 仍是 `rc=2` 响亮，不受影响）。
⇒ **不是仪器坏了，是被测对象换了版本** —— 这正是 `V-11` **仪器轴**要求"结论主语必须写出被测对象（含版本）"的理由：否则"607 对不上"会被误读成工具问题。

**5. `V-12` 自查（非交互参数）**

`V-12` 立条的事故正是**裸 `git merge main` 在无 TTY 下挂起**（`Waiting for the editor to close` ⇒ 被终止 ⇒ 留下 `MERGE_HEAD` + 模板污染的 `MERGE_MSG`）。我审自己那两次 merge：

- `5318e74`：**我明确带了 `-m`** ✓；
- `981e7cc`：消息是 git **默认**合并消息（`Merge branch 'refs/heads/main' into ws/step56-skipped`）⇒ **无法从提交对象反推当时是否带 `-m`**（默认消息在"带 `-m` 之外的非交互路径"下也一样）。**我不编**。
- 实测残留检查：**无 `MERGE_HEAD`、无 `MERGE_MSG` 残留**；全仓 `git log --all` **无任何提交含模板行**（`Please enter the commit message` / `Do not edit` 等）⇒ **未发生 `V-12` 事故**。
- ⇒ 此后一律 `git merge --no-edit`（或带 `-m`）。

**规矩（本报告此后遵守；★ 已按主干 `V-10` 重写，`refs/heads/main = 3653c7c`）**：
- ★★ **没有"一律改成 X"的安全写法** —— 三个引擎三种方言（裸 toybox / `/usr/bin/grep` BSD / `Grep` 工具 ripgrep），**同一个 `\|` 三个答案**。**我原先写的"一律用 Grep 工具"已作废**（ripgrep 对 `\|` 是**字面竖线**、且**不支持反向引用**，都是静默零）。选工具的原则是"**你知道它的方言**"；
- ★★ **凡结论建立在某次 grep 类输出之上，必须同时给出**：**引擎指纹**（`command -v` 绝对路径 / `--version` 原文 / 工具名 **+ 是否 ripgrep**）+ **`rc` 原文**；`Grep` 工具**不暴露 `rc`** ⇒ 用它时**必须**额外给地板真值，否则"零"与"出错"分不开；
- **`"空输出" ≠ "无匹配"`**，且**读到 0 命中必须先排除三候选**：真没有 / 语法不支持（`\|` 这类）/ 路径参数错；
- **带 `| head` / `| wc` / `| tail` 的命令，`rc` 列一律不可用**（管道吞掉**一切**非零码，实测 `2` 也会变 `0`）；要真码写 `{ cmd; echo "EXIT=$?"; } 2>&1 | head` —— 见 §7.3.4；
- 若非要用裸 `grep`：只写 **POSIX BRE**（`\.` `\{n,m\}` `\(\)` `\1`），**别写 `\|` `\+` `\?` `\<` `\>` `\b`**；
- ★★★ **不要"遇到问题就加 `-E`"**：`-E` **只对已改写成 ERE 的模式**有效；**原样字符串加 `-E`** 是**从一种静默换到更广的静默**（`/usr/bin/grep` 会**响亮**拒绝 `\(abc\)\1`：`rc=2` + `invalid backreference number`，而裸 toybox **静默给 0**）。正确动作 = `-E` **且同时改写模式**（`\|`→`|`、`\+`→`+`、`\{n\}`→`{n}`）；词边界用 **`-w`**；**反向引用只能留在 BRE**（§7.3.7 第 2 条）；
- **裸 `grep -E` 不是万能解**：它修 `\|` `+` `?`，但**照样静默丢 `\b` 与反向引用** ⇒ **词边界用 `-w`**，**反向引用留 BRE**（§7.3.4 表）；
- 同族一条（`ws-verify-shard` 实测、**我已独立复算**）：**`head -N` 会截断 diff**（会漏 hunk ⇒ 误判成"只删了注释"）；
- **提交作者不能用于队友归因**：本机全局身份统一 ⇒ `%an` 恒为 `Geetie`，**判据与对象不同源**（`G-61`）。要归因只能用"分支名 + message 自述"，且标注"不可证"（§7.3.5）。

★ **对 §3.2 的连带自查**：`injection-f = 33` 这个数字来自 **`test_shard_case_counts_within_quota` 主动跑出来的断言消息**（`assert not {'injection-f': 33}`），**不是**我 greps 出来的；§3.3 的红来自**真实 pytest 执行**。⇒ 两条红灯**不受本环境坑影响**。

---

## §8 对卡 `#91` 的**定位表与补漏**（`main = 3d265bc` 时点；**只读**，未改任何共享文件）

卡 `#91` 登记「6 片」表述漂移 = **16 处**（`verify.py` 9 + `CONVENTIONS.md` 7）。我按**内容**（不是按行号）逐处核对，结论三条：

1. **卡里给的行号全部没有漂移** —— 9 + 7 处逐行命中，可直接用。
2. ★ **但清单漏了 13 处**（都在 `CONVENTIONS.md`），其中 **1 处是整表缺行、1 处是结论方向已错**。
3. ⇒ **真源不是 16 处，至少 29 处**。漏改 L71~L76 那张表 = **"写死的例数"最显眼的地方没改**。

**真值（我按 `_collect_count` 同语义独立复算，见 §3.6）**：片数 **7**（`a`~`g`）/ 文件 **16** / 逐片 **`a30 b32 c31 d29 e32 f27 g24`** / 合计 **205**。

### 8.1 卡 `#91` 已列出的 16 处 —— 行号未漂移，可照改

`verify.py`：L44「必须切成 6 片」L95「六片连着跑完」L248「为什么分 6 片」L259「6 片（每片 ≤32 例）」L260「维持 6 片」L350「六片统一 300s」L435「与 `injection-a..f` 齐平」L437「同期 `a..f`」L571「6 片必须逐片单独跑」。
`CONVENTIONS.md`：L111「6 片连着跑完」L153「当前的 6 片」L154「6 片立刻不成立」L155「171 例」L156「`a` 27 / `b` 28 / `d` 31 / `f` 31」L167「六片统一取 300s」L292「切成 6 片（`injection-a`~`f`）」。

★ **同文件自相矛盾的现成证据**：`verify.py` **L29 已经写「`injection-a`…`injection-g` 的 **7 个分片**」**（正确）—— 与同文件 L44/L95/L248/L259/L260/L350/L571 的"6 片"**并存**。⇒ 这不是"文字陈旧"，是**同一文件内两处互相打脸**，可直接引为"必须一起改"的理由。

### 8.2 ★ 卡 `#91` **漏掉**的 13 处（我补；全在 `CONVENTIONS.md`）

| # | 行 | 现文（节录） | 为什么必改 | 类别 |
|---|---|---|---|---|
| 1 | **L71** | `` `injection-a` … · **27 例** `` | → **30** | 硬例数 |
| 2 | **L72** | `` `injection-b` … · **28 例** `` | → **32** | 硬例数 |
| 3 | **L73** | `` `injection-c` … · **27 例** `` | → **31** | 硬例数 |
| 4 | **L74** | `` `injection-d` … · **31 例** `` | → **29** | 硬例数 |
| 5 | **L75** | `` `injection-e` … · **27 例** `` | → **32** | 硬例数 |
| 6 | **L76** | `` `injection-f` … · 31 例 …（**29 例时**测得）`` | → **27**；括号备注也过期 | 硬例数 |
| 7 | **L76′** | ——（**无此行**） | ★ **整表缺 `injection-g` 一行（24 例）** | **缺行** |
| 8 | **L97** | 「`tests/injection` 合并跑 **165 例**」 | → **205** | 硬例数 |
| 9 | **L155** | 「（目录现有 **171 例**，需要 ≈14 片）… 会把轮次从 6 抬到 **14**」 | → **205 例**；★ 按卡内自己的常数（L152「≈12 例/片」）应为 **≈18 片**（205 ÷ 12 向上取整），**"轮次 7 → ≈18"** | 硬例数+推导 |
| 10 | **L156** | 「`a` 27 / `b` 28 / `d` 31 / `f` 31」 | → **`a`30 / `b`32 / `c`31 / `d`29 / `e`32 / `f`27 / `g`24** | 硬例数 |
| 11 | **L157** | 「（`d` 的 31 例是**最接近上限**的一片，也过了）」 | ★★ **结论方向已错**：现在压线的是 **`b`/`e`=32**，`d`=29 已不是 | **结论错** |
| 12 | **L286 / L293** | 「一次全量 ≈ 119 用例 × 250」「该目录 **165 例** × 273 项/例」 | → **205 例** | 硬例数 |
| 13 | **L52 / L166** | 「`injection-f` 隔离 12.53s / 工作树 110.13s」 | ★ `f` 现为 **27 例**（测时是 31/29 例）⇒ **时间基线必须注明例数口径**，否则是 `V-11` 仪器轴越界 | 时间基线 |

### 8.3 ★ 两条超出"改数字"范围、需主理人裁的口径问题（我不自裁）

- **口径冲突**：L152 的推导是「`9999 ÷ 792` ⇒ 安全上限 **≈12 例/片**」，但 L153~L156 同时说"**每片 ≤32**"。
  ⇒ **12 与 32 是两个不同的上限**：`≈12` 是**按回落阈值 `9999`** 推的、`32` 是**实测阈值 `99999`** 下的当前配置（L153 已注明）。**两处都在同一段里，读者极易把 32 当推导常数**。
  ⇒ 建议（比"改数字"更重要）：把这段改成**只留三句口径**——「授权上限 **32**（实测阈值下）／回落阈值 `9999` 时应降到 **≈12 例/片 ⇒ 需 ≈18 片**／现状 `b`/`e` **零余量**」，**删除所有写死的逐片例数**，改为"真源 = `verify.py::INJECTION_SHARDS` + `test_shard_coverage.py` 的现算值"。**这样才不会第三次漂移**（这也正是卡 `#91` 自己提的方向）。
- **`≈18 片` 是我按卡内常数套算的**，不是新推导。若主理人的口径是用 32 算（⇒ 205 ÷ 32 ≈ 7 片、即"7 片够用"），**结论会完全相反**（"回落时需重排" vs "7 片已够"）。**请裁定用哪个常数**，我不自裁。

### 8.4 ★ 我的一条留痕（第 6 次仪器错，同属 `V-10` 规矩 5）

核对时我写了一条含**反引号**的 grep 模式（`` "a`~`f" `` 放在双引号里）⇒ **反引号被 shell 当命令替换执行**，报 `permission denied: /Users/gaza`。
⇒ 即 `V-10` 规矩 5「**取数命令本身不得使用尚未证明可用的语法**」的第 N 次实例 —— 这次不是 grep 方言，是**我没给自己的命令加引号纪律**。后续我改用不带反引号的模式重取，结论不受影响（上面每一行都来自重取后的输出）。
