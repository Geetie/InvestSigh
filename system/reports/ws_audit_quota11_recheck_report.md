# 口径 11 全仓审计 —— 复跑（卡 `#82`）

| 项 | 值 |
|---|---|
| 工作树 | `/Users/gaza/Developer/InvestSigh/.worktrees/ws-step56-skipped` |
| 分支 | `ws/step56-skipped` |
| 复跑读数时的树 | **`28e1eff`**（= 当时 `main` 的 HEAD；`HEAD..main == 0`） |
| 复跑时点 | 2026-09-16 22:47~22:48 +0800 |
| 原审计时点 | `main@fe14d93`，2026-09-16 22:30:41（见卡 `#82` 描述） |
| 本次动作 | **只读 git** + **一处零删除 pytest**（`--noconftest`，不建夹具、不删任何东西） |
| 未做的事 | 未改 `main`、未合并任何分支、未动 `conftest.py`、未跑任何需夹具的批次 |

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

### 3.1 机器证据（一次跑完，`main@28e1eff`，零删除）

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

⇒ `run_all_gates.py` 与 `pre-commit.sh` **都不跑 verify 的分片批**。`injection-f` 的红只有**显式**跑 `verify.py --batch injection-f` 的人才能看到。
⇒ 与 §3.2 那句"门禁被静默关掉"是**同一件事的两种形态**：一个是"该片跑不完"，一个是"该片压根不在门禁链上"。
★ 这是**观察，不是建议** —— 要不要把 verify 分片接进门禁链属主理人裁决（接了会显著拉长提交耗时）。

---

## §4 对原审计三处定性的更正

### 4.1 `ws/verify-shard`：原判「陈旧无害」**不成立**

原审计写：*"`ws/verify-shard`：陈旧无害 —— main 已有分片机制（`injection-a` 命中 7、main `verify.py` 590 行 > 分支 568 行）"*。

**该判读只看了"机制在不在"，没看"实现全不全"**，属原审计自己登记的方法学自纠第 2 条（**存在性判别漏报"只改既有文件"型缺口**）的**又一次复发** —— 而且这次漏掉的不是"新增文件"，是**同一文件里的一段实现**。
⇒ 更正为：**"陈旧 + 有内容缺口，且在 `main` 上现红"**（§3.3）。

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
7. **本报告 §3 的两条红灯（§3.2 / §3.3）与两种判读方法无关**：它们建立在"**blob 逐字节比较**"（`main:verify.py` 无 `PYTEST_MISSING`）+ "**真实 pytest 执行**"之上，不依赖任何 diff 方向判读 ⇒ **不受 §7.2 的更正影响**。

---

## §6 复跑指引（可照抄，★ 已按 §7 更正）

```bash
R=/Users/gaza/Developer/InvestSigh

# 0) 先记住时点，并★写明 ref 全名（本仓有三个含 main 的 ref，会互相冒充）
git -C "$R" rev-parse refs/heads/main        # ★ 不要只写 "main"

# 1) 步骤①：哪些分支 main..b != 0
for b in $(git -C "$R" for-each-ref --format='%(refname:short)' refs/heads | grep -v '^main$'); do
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

## §7 自我更正留痕（`refs/heads/main = c5a0a22` 时点）

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

### 7.2 我犯的错与反证（原判 → 更正）

我把 §2.1 的 tip-to-tip 差分读成"**分支要删掉 `main` 已有内容 ⇒ 以分支为准并入会回退 `main`**"，并对 `ws/fixture-cost`、`ws/ch2-rules` 各下一句判词。**两句都错。**

- `ws-ch2-rules` 给出**符号相反的反证**：他真实 `merge main`（`1e1a197`，零冲突）后 `taskbook +140 / gap_register +121 / audit_batch11 +10` —— **全是 `+`**，且这三个数**正是我看到的那些行数**（`main` 又前进了）。他相对 merge-base **只改 2 个文件**。
- 我用**同一方法复核 `ws/fixture-cost`**：merge-base `ed9687b`，相对它**只改 2 个文件**；`merge-tree --write-tree`（rc=0，无冲突）结果树里三份共享报告的 blob **逐字节等于 `main` 那一份** ⇒ **未回退**。唯一需人看的是 `verify.py`（合并产生第三个版本）。

**根因**：我拿一个**不表达该语义的读数**（tip-to-tip 差分）去下**语义结论**（合并方向）。这与我在同一天给 `verify.py` 抓的错**同类**（"归因与对象不同源"），所以按同一标准处理：**就地更正 + 保留原判原文 + 给出反证**，不把错句悄悄删掉。

★ 副作用提醒：我此前发给 team-lead / `ws-ch2-rules` 的消息里**已含这两句错判**，已在随后的更正消息中撤回；**以本报告 §4.2 / §4.4 为准**。
