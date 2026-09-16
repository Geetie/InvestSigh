# 卡 `#91`：`tests/injection` 分片表述漂移 —— 真源化订正 + 边界声明

| 项 | 值 |
|---|---|
| 卡 | `#91`（「6 片」表述漂移；真源为 7 片 / 16 文件 / 205 例） |
| 归属 | `ws-step56-skipped` |
| 工作树 | `/Users/gaza/Developer/InvestSigh/.worktrees/ws-step56-skipped`（分支 `ws/step56-skipped`） |
| 被测对象 | `main@d766a32`（本分支已 FF 到该 tip，**改前 `git status --short` 为空**） |
| 我的提交 | `1706916`（`verify.py`）· `41fbe7e`（`test_shard_coverage.py`）· `6f71a3c`（`CONVENTIONS.md`） |
| 取数解释器 | `$HOME/.workbuddy/binaries/python/envs/default/bin/python` = **Python 3.13.12 / pytest 9.1.1** |
| 计数口径 | 与 `tests/injection/test_shard_coverage.py::_collect_count` **同源**（`--collect-only -q -p no:cacheprovider --noconftest`，`PYTHONPATH=<system>/tests`） |
| 收尾状态 | `pre-commit`（**真钩子**）**6 次全绿**（6 个提交各一次）、未用 `--no-verify`；`git status --short` 空 |

★ **全文行号约定**：一律是**改前**行号（= `main@d766a32`，我用 `git show d766a32:<file>` 逐条取，不靠回忆）。
改后行号会整体偏移（`verify.py` +4 / `test_shard_coverage.py` +2 / `CONVENTIONS.md` +7，且**不是均匀平移** —— 改动是分散的）
⇒ **定位请用每行的引号原文，不要用行号**。这与我在 `#82` 报告 §8.1 踩过的坑是同一类（当时错判"`V-10/V-11/V-12` 插入会挤偏行号"，实测未漂移，已留痕）。

---

## §0 一句话结论

「6 片」不是笔误，是**同一事实的第二个存放处**——它随 `#89` 移片漂到 7 片之后，**没有一处被更新**，而这段文字正是 `#89` 裁定的依据；本次把**片数与例数**从三个文件里**全部改成指向真源**（不再写死），并把「没改哪些」也逐条写清（否则下一次没人分得清「漏改」与「刻意不改」）。

---

## ★★ §0.1 撤回与并列声明（**先读这一段，再读 §1~§8**）

**本卡已被别人先做完。** 我在 `main` 前进之后才发现：

| 时间 | 提交 | 谁做了什么 |
|---|---|---|
| 09-16 **23:26:00** | `bf99f91` | 给 `tests/pricelayer/` 加 **9 例**（`183 + 9 = 192`，见 §9.3） |
| 09-16 **23:41:03** | `d3f5701` | **`#91` 的实质修复**：按它自己的 commit message = 「`verify.py` 9+5 处散文 + `CONVENTIONS.md` V-02 表/附录/V-08 一行 —— 删写死数字改指真源，**并订正 V-02 表 6 行过期超时 + 补 `injection-g` 行**」 |
| 09-16 **23:47:41** | `1706916` | （我）`verify.py` 16 处真源化 —— **同一件事，晚了 6 分钟** |

★ **署名不可判（如实说明）**：本机**全局 git 身份统一**，`d3f5701` / `bf99f91` / 我的提交的 `%an` 全是 `Geetie` ⇒ **git 事实里没有"谁"**。上表只用**提交时间 + 内容 + commit message**；「属 `ws-ch2-rules`」是**按卡归属的推断**，不是 git 事实（`G-61` 已登记过这个坑）。
★ `main` 现在那张**批次表**（新超时 + 新实测）的成形**不只 `d3f5701`**：其后还合入了 `ws/fixture-cost` 的 `b7c0c8f`（其 message 含「`#91` 收口段」）等。我**按内容 diff 归因**，不按提交归因。

★ **为什么会撞**：我开工时 `main` 的 tip 是 `d766a32`（**不含 `d3f5701`**），任务列表里 `#91` 仍是 `in_progress` 且 owner 是我，**没有任何消息告诉我它被接手**。我把分支 FF 到 `d766a32` 之后工作，期间 `main` 前进到 `cd05e1f`。**这是一次赛跑，不是谁疏忽。**

### ⇒ 结论（我的自我处置建议，**不自裁**）

| 我的提交 | 建议 | 理由 |
|---|---|---|
| `6f71a3c`（`CONVENTIONS.md`） | ★★ **丢弃** | **`main` 已把这段重写得比我的版本更新更全**（批次表换成了**新测的超时/实测**、`injection-g` 行已在、另有一段 `#91` 漂移记录）。**合我这一版会把新表回退成旧表** —— 这不是"重复"，是**倒退** |
| `1706916`（`verify.py`） | **按增量取舍** | `main` **仍未修** 4 处：L29「`injection-a`…`injection-g`／**7 个分片**」、L72「**27 / 28 例**的片」、L73「（**≈14 片**）」、L259「（需 **≈14 片**）」。其余 12 处 `main` 已用**等价或更好**的措辞覆盖（例：L420 那段 `main` 补了「**当时快照**」四字，比我的不动更好） |
| `41fbe7e`（`test_shard_coverage.py`） | **保留（纯增量）** | `main` **一处都没改**这个文件；尤其 **L331 是断言失败消息**，它仍印着「需 ≈14 片 / 14 个轮次」 |
| `89c6e96`（本报告） | **保留** | §1/§4/§5.1/§9.3 是与 `#91` 无关的独立读数与发现 |

★ **我做了什么、没做什么**：
- **没有**把任何东西合进 `main`（4 个提交只在 `ws/step56-skipped`）⇒ **`main` 未被我的重复/回退污染**；
- **没有**改写我的分支历史（`rebase`/`reset` **未做**）—— 那是共享引用上的动作，等你裁定；
- **没有**去改 `main` 已经修好的那 12 处（避免两版措辞互相覆盖）。

★ **推荐动作（一句话，执行很快）**：我基于 `cd05e1f` 重做**一个**小提交 = `main` 未修的 4 处 + `test_shard_coverage.py` 的 4 处，**不碰 `CONVENTIONS.md`**；本报告保留。**要我做就回一个字。**

---

## §1 现算真值（机器证据，含 `rc`）

```
$ python /tmp/m91/measure.py <worktree>/system          # 口径同 _collect_count，含显式 rc
=== 真源：verify.py::INJECTION_SHARDS = 7 片 ===
  injection-a injection-b injection-c injection-d injection-e injection-f injection-g
=== 逐片（现算）===
  injection-a     30 例   targets= 3 个
  injection-b     32 例   targets= 2 个
  injection-c     31 例   targets= 2 个
  injection-d     29 例   targets= 2 个
  injection-e     32 例   targets= 3 个
  injection-f     27 例   targets= 2 个
  injection-g     24 例   targets= 2 个
  合计             205 例
=== tests/injection/test_*.py = 16 个文件 ===
=== 目录整体（判 V-05 用，不是为了跑）: 205 例  (rc=0) ===
=== 断言 ===
  片数 7 ?        True
  文件数 16 ?     True
  合计 205 ?      True
  逐片 a30 b32 c31 d29 e32 f27 g24 ?  True
  超过授权上限 32 的片: 无
  零余量（=32）的片: ['injection-b', 'injection-e']        ← ★ 两片顶到授权上限，零余量
```

★ 与卡面登记值**逐格一致**；★ **新事实**：`b`、`e` 两片都是 **32**（零余量）—— 卡面只写了「`b`/`e` 零余量」的结论，这里给出**逐片读数**作为其证据。

### §1.1 地板真值 / 控制组（`V-10` 规则 3）

「7 片 / 205 例」是**读数**，不是**判据**；证明仪器真的会区分，需要一个**已知非零的对照**：

```
$ python /tmp/m91/counts.py <worktree>/system <pybin> tests/pricelayer tests/valuelayer tests/guards ...
tests/pricelayer         rc=0  count=192      ← 与 CONVENTIONS 写的「168 例」不一致（见 §6.1）
tests/valuelayer         rc=0  count=206      ← 与 CONVENTIONS 写的「206 例」一致
tests/guards             rc=0  count=96
tests/unit               rc=0  count=85
tests/daily              rc=0  count=56
tests/evidence           rc=0  count=48
```

⇒ 同一仪器在**能给出非零值**也**能给出不一致**的场景下都给出了可判读的读数 ⇒ 「205」不是「仪器恒回 0」的产物。

---

## §2 改了什么（逐文件逐处）

**总原则**：片数 → 指向 `verify.py::INJECTION_SHARDS`；例数 → 指向「`--collect-only` 现算」；**只保留三句不随树漂移的口径**（授权上限 32 / 阈值前提 / 回落时按 `9999 ÷ 计数/例` 重排）。理由不是我的发明 —— 是这两份文件**自己已经立过的规矩**：

> `CONVENTIONS.md`：★ **刻意不写"批次数"** —— 唯一真源是 `verify.py::BATCHES`；**数字只留在各自的真源里**，否则"手写的数"会随新增批次**静默过期**。
> `verify.py`：本表原先带一列"超时"，**已实测漂移**（`unit` 那行写着 `60s`，真值早不是它；分片那行写 `6 个` 而实际已 7 个）。

⇒ 分片这段只是**没被执行同一条规矩**，本次把它补上。

### §2.1 `system/scripts/ops/verify.py`（16 处，提交 `1706916`）

| # | 行（改前） | 原文（过期声明） | 改后 |
|---|---|---|---|
| 1 | L29 | 表行标签 `injection-a`…`injection-g` + 「**7 个分片**」 | 标签 `injection-*` + 「**片名单与片数**的唯一真源 = `INJECTION_SHARDS`，此处刻意不写」 |
| 2 | L44 | 标题「必须切成 **6 片**」 | 「必须切成**多个分片**」 |
| 3 | L72 | 「**27 / 28 例**的片…跑完」 | 「当次观测下**最接近授权上限的那片**也单轮跑完」（+「片内例数不要照抄本文档，用现算值」） |
| 4 | L73 | 回落时「（**≈14 片**）」 | 「片数 = ⌈该目录**现算例数** ÷ 12⌉」 |
| 5 | L92 | 「现在需要 **6 个轮次**」 | 「**与 `INJECTION_SHARDS` 等量**的轮次」 |
| 6 | L95 | 「`--batch all` 会把**六片**连着跑完」 | 「会把 `INJECTION_SHARDS` 里的**每一片**连着跑完」 |
| 7 | L248 | 「为什么分 **6 片**」 | 「为什么必须分片」 |
| 8 | L249 | 「共 **165 例** × 每例一份夹具副本 ≈ **44,715** 项/轮」 | 「**例数 × 每例一份夹具副本**已远超配额」（例数用现算值） |
| 9 | L250 | 「现在需要 **6 个轮次**」 | 「与 `INJECTION_SHARDS` 等量」 |
| 10 | L259 | 「**6 片**（每片 ≤32 例）…不成立（需 **≈14 片**）」 | 「当前这个分片方式…不成立（需 ⌈现算例数 ÷ ≈12⌉ 片）」 |
| 11 | L260 | 「维持 **6 片**是…」 | 「维持现状是…」 |
| 12 | L350 | 「**六片**统一 300s」 | 「**各 injection 片**统一 300s」 |
| 13 | L435 | 「与 `injection-a..f` **齐平**」 | 「与 `INJECTION_SHARDS` 的**其它各片齐平**」 |
| 14 | L437 | 「同期 **`a..f`**（300s）不会」 | 「同期**其它 injection 片**（300s）不会」 |
| 15 | L571 | 「的 **6 片**必须逐片单独跑」 | 「的**每一片**必须逐片单独跑」 |
| 16 | L573 | 「请分 **6 个轮次**跑」 | 「请按片数分**等量**的轮次跑」 |

★ **无一行是代码**：`git diff` 的新增行**逐行落在注释/docstring 内**；`INJECTION_SHARDS` 与 `BATCHES` 的**成员、目标、超时一律未动**（`INJECTION_SHARDS` 仍是 7 名，见 §4 门禁 `verification_policy_guard exit=0`）。

### §2.2 `system/CONVENTIONS.md`（10 处，提交 `6f71a3c`）

| # | 行（改前） | 改法 |
|---|---|---|
| 1 | L61-64（表头说明） | 「刻意不写"批次数"」**扩为**「刻意不写"批次数"，**也刻意不写"每批例数"**」，并写明后者的唯一真源 = 「`--collect-only` 现算」 |
| 2 | L71-76（injection 6 行） | **删掉每行末尾的「· N 例」**（27/28/27/31/27/31 **六个全过期**）；`injection-f` 的「+ 分片绑定」删除（该文件已按 `#89` 移入 G） |
| 3 | L76 之后（新增行） | **补漏掉的 `injection-g`** —— 原表**整表没有 G 行**（`#89` 新增的片从未进过这张"人的索引"） |
| 4 | L86-87 | `pricelayer` / `valuelayer` 的「· 168 例 / · 206 例」**同样删除**（理由见 §2.3） |
| 5 | L97-98 | 「合并跑 **165 例**…≈ **13 万计数/轮**」→ 「合并跑（例数现算）…**例数 × 792** 远超阈值」（删掉由过期例数算出的 13 万） |
| 6 | L109-112 | 「现在需要 **6 个轮次**／`--batch all` 会把 **6 片**连着跑完／请分 **6 个轮次**跑」→ 三处均改为指向 `INJECTION_SHARDS` |
| 7 | L152 | 「完整覆盖需 **≈14 片**」→ 「需 **⌈该目录现算例数 ÷ 12⌉ 片**」 |
| 8 | L153-157 | 「当前的 **6 片**（每片 ≤32）／**6 片立刻不成立**（目录现有 **171 例**，需要 **≈14 片**）／会把轮次从 **6** 抬到 **14**／`a` **27 例** / `b` **28 例** / `d` **31 例** / `f` **31 例**…`d` 的 **31 例**是最接近上限的一片」→ **全部真源化**（片数、例数、片名都不再写死） |
| 9 | L164 | 「合并跑 **165 例**光删除就要 ≈12 分钟」→ 「合并跑该目录**全部用例**」（保留 ≈12 分钟的结论，它是对量级的判断） |
| 10 | L167 / L292-293 | 「故**六片**统一取 300s」→「各 injection 片」；「现在切成 **6 片**（`injection-a`~`f`）／该目录 **165 例 × 273 项/例 ≈ 45,045** 项/轮」→ 指向 `INJECTION_SHARDS` + 「例数 × 每例一份夹具副本」 |

### §2.3 为什么连 `pricelayer` / `valuelayer` 的「· N 例」也删

它们**不是**「顺手多改」：`pricelayer` 那格写 **168**，**现算 192**（§1.1 的 rc=0 读数），**已经漂了**。而这两格与我改的 injection 6 行**同在一张表、同一个列语义**——只把 injection 行的例数删掉、留下同样会漂的另两行，等于把「本表刻意不写例数」这句话变成假的。故按**同一判据**一并处理（判据 = 「本列是同一事实的第二存放处」，不是「文件属于谁」）。

### §2.4 `system/tests/injection/test_shard_coverage.py`（4 处，提交 `41fbe7e`）

★ **这个文件不在卡面的 16 处清单里 —— 是我复算时新查出来的第三处存放点。**

| # | 行（改前） | 改法 |
|---|---|---|
| 1 | L104 | 「需 ≈**14 片** / **14 个轮次**」→ 「需 **⌈该目录现算例数 ÷ 12⌉ 片** / 等量的轮次」 |
| 2 | L111-112 | 「`a` **27 例** / `b` **28 例** / `d` **31 例** / `f` **31 例**…`d` 是最接近上限的一片」→「当次观测下**最接近授权上限的那片**也单轮 `exit=0` 跑完了」 |
| 3 | L113-115 | 「**6 片**立刻不成立（目录现有 **171 例**，需要 **≈14 片**）／请按…扩到 **≈14 片**／不要先去改 **14 片**：**14 轮**没人会跑」→ 全真源化（保留「**改片数要主理人定**」这句治理声明） |
| 4 | L331（**断言失败消息**） | 「需 **≈14 片 / 14 个轮次**」→ 「需 ⌈该目录现算例数 ÷ 12⌉ 片；**片数不写死在本消息里**，`INJECTION_SHARDS` 是唯一真源」 |

★ 第 4 处是**判据自己的失败消息**：它也要指向真源，否则下一个人读到的还是过期数字。

---

## §3 我**没**改哪些，以及为什么（★ 本节比 §2 更重要）

本次改动的边界判据是**「声明 vs 留痕」**：

- **声明** = 对**当前状态**的断言（读起来是"现在是 N 片 / 目录有 N 例"）→ **必须真源化**，因为它**此刻就是错的**；
- **留痕** = 带**时间锚**或**决策上下文**的记录（"本单实测"、"当时"、"曾"、"批次 13 集成期"）→ **一律不动**，改了就是**篡改历史证据**。

| 文件:行 | 内容 | 判定 | 为什么 |
|---|---|---|---|
| `verify.py:35-38` | 「分片那行写 `6 个` 而实际已 7 个」 | 留痕 | 这是**上一次同类漂移的教训记录**，它**本来就该**写着 6 → 7 |
| `verify.py:52` | 「跑旧的全目录目标 `tests/injection`，**169 例** / 290s」 | 留痕 | 当时那次复现的读数（169 例是那一刻的目录大小） |
| `verify.py:67,70` | 「**271**/例」「`32 × 271 = 8,672`」 | 留痕 | 引述**被证伪的原始推导**；改掉就毁掉"为什么它不成立"的论证 |
| `verify.py:252` | 「每例副本 **271 项 → 275 项**」 | 留痕 | 卡 13-F 的实测更正记录；（且 `273`/`275` 项数本身是**另一族漂移**，见 §6.2） |
| `verify.py:345` | 「工作树实测 **80.92s**（`27 passed`…）」 | 留痕 | 那一次运行的输出 |
| `verify.py:352` | 「a 70.74~80.92s · b 63.72s · f 110.13s」 | 留痕 | 标定超时用的**当时**实测 |
| `verify.py:416-425` | 「现为 **a27 b28 c27 d29 e32 f29**，最大余量只有 5 例」 | 留痕 | **`#89` 为什么"移片而非改上限"的全部依据**；这是我**最想改也最不能改**的一处 |
| `verify.py:441-444` | 「本片曾 **33 例 > 上限 32**」 | 留痕 | 同上，用"曾"标注 |
| `verify.py:423` | 「`injection-a`（**27 例** / 6.85s 隔离）同阶」 | 留痕 | 批次 13 期的量级比较 |
| `verify.py:475-478`（`pricelayer` 段） | 「但本批现为 **168 例**」／「用例数 **127→168**」 | ★ **声明**（该改）**但越卡面范围** | 见 §6.1 —— **登记，不自裁** |
| `test_shard_coverage.py:5` | 「原先是一个批次（…，**165 个用例**）」 | 留痕 | 描述**分片引入之前**的状态 |
| `test_shard_coverage.py:93,102,118` | 「**271** 项」「`32 × 271 = 8672`」「`COPIED_ITEMS_PER_CASE = 273`」 | 留痕 + 项数族 | 引述被证伪的推导；项数族见 §6.2 |
| `CONVENTIONS.md:49,94,162` | 「**273 项**夹具副本」 | 项数族 | 见 §6.2 |

⇒ **本次漏改的可能性是明确的、可判的**：凡我判定为"声明"的，§2 已逐处列出；凡我判定为"留痕"的，本表已逐处列出。**没有第三类**（既没说改、也没登记）。

---

## §4 证据（4 条，均可复跑）

```
(1) 全门禁（卡面指定口径）
$ python scripts/ops/run_all_gates.py --timeout 30
  → 27 项中 26 项 exit=0；唯一非零 = traceback.py exit=1；非零计数 1；EXIT=1

(2) ★ traceback.py 的**干净树对照**（证明非我引入）
$ git stash push -- system/CONVENTIONS.md system/scripts/ops/verify.py system/tests/injection/test_shard_coverage.py
$ python scripts/trace/traceback.py .
  [FATAL] G1-03 @ facts/recommendations.jsonl:0 — rec-nvda-001 四要素（**适用项**）缺失: ['assumptions','computation']
  [FATAL] G1-03 … 反查成功率 0.0000 < 1.0
  RESULT: FAIL（2 violations）   EXIT=1
$ git stash pop        # 恢复，status 复现为 3 个 M
⇒ 唯一变量 = 我的改动被移除，**红灯不变** ⇒ **pre-existing，与本次文案改动无关**（它是运行态数据门禁）

(3) pre-commit **真钩子**（**6 个提交各一次，全部 ✓ 全部门禁放行**，全程未用 --no-verify）
  1706916 / 41fbe7e / 6f71a3c / 89c6e96 / 420800e / 7bab705  → 逐次 pre-commit ✓

(4) 我改过/受影响的两个测试文件
$ sh scripts/ops/run_pytest.sh tests/injection/test_shard_coverage.py
  → 6 passed in 2.36s       ← ★ 断言消息被改的就是这个文件，它**自证仍绿**
$ sh scripts/ops/run_pytest.sh tests/guards/test_verification_policy.py
  → 15 passed in 1.52s      ← 该文件用**精确字符串锚点**改 verify.py 造反向对照；
                               15 绿 ⇒ 我改的 16 处文案**没碰到任何一个锚点**
```

★ `test_verification_policy.py` 这一条是**刻意**跑的：`verify.py` 是**被注入对象**（`_patch(code_root, VERIFY_REL, <锚点>, …)`），若我的文案改动覆盖了锚点，这个文件会以「注入失败：未找到锚点」**响亮红**。它绿 ⇒ **文案改动与机器绑定正交**。（我另用脚本逐个核对 8 个锚点（7 个 `verify.py` + 1 个 `run_pytest.sh`），逐个 `OK`。）

### §4.1 举证半径声明（`V-11`）

- **时间轴**：全部读数取 `main@d766a32`（= 我的分支 tip），**改前改后同一对象**；
- **类别轴**：「片数/例数」这一族**穷尽**（§2 改了 30 处 = 16+10+4；§3 列了全部未改的）；
- **仪器轴**：片数与例数用**项目自己的判据**（`_collect_count` 同源口径 + `run_pytest.sh` 指定解释器）；门禁用**真钩子**；**没有**用裸 `grep` 得到任何结论（§5.1 是我因此少犯一次错）。
  ★ **边界**：`tests/guards/`（96 例）与 `injection-a..g` 各片**本次没有整批跑**（删除配额约束）；我跑的是**直接相关**的两个文件。**这不是"已验证全仓无回归"**，只能说"受本改动直接影响的机器绑定已绿"。

---

## §5 反向对照与残余

### §5.1 ★ 我自己差点犯的第 7 次仪器错：**「假小」**（与 `auditor-batch11` 报的「假零」同族、不同形态）

登记用 §1.1 的读数时，我第一版写的是：

```
$ for t in tests/pricelayer tests/valuelayer tests/guards; do
    n=$("$P" -m pytest $t --collect-only -q -p no:cacheprovider --noconftest 2>&1 \
        | /usr/bin/grep -oE '[0-9]+ tests? collected' | head -1); echo "$t -> $n"; done
tests/pricelayer -> 192 tests collected
tests/valuelayer ->  47 tests collected     ← ★★ 假小 ★★
tests/guards     ->                        ← ★★ 假零 ★★（连一行都没有）
```

**两个错叠在一起**：① 少了 `PYTHONPATH=<system>/tests`；② `| grep` **吞掉退出码**（`V-10` 规矩 4）。补上控制组后真相出来了：

```
--- (甲) 不设 PYTHONPATH ---
  ERROR tests/valuelayer/test_route_guard.py
  !!!! Interrupted: 4 errors during collection !!!!
  47 tests collected, 4 errors in 0.24s
  EXIT=2                                   ← ★ 是响亮的（rc=2 + "Interrupted"）
--- (乙) 设 PYTHONPATH=<system>/tests ---
  206 tests collected in 0.18s
  EXIT=0
```

**唯一变量 = `PYTHONPATH`；同一条命令，47 vs 206。** 而 `grep` 把 `EXIT=2` 抹成 `0`，于是"4 个文件收集失败"被读成"目录只有 47 例"。

★ **这是 `G-62` 的一个新形态，值得进 `#98`（`auditor-batch11` 手上的"grep 依赖型结论全量重证"）：**

> **响亮信号被读取姿势销毁**：`rc=2` 与 `Interrupted: N errors during collection` 都在 stdout/stderr 里，**没有任何东西静默**；但只要你用 `| grep` / `| head` 只取一行，**证据就没了**，剩下一个**格式完全合法、数值完全错误**的读数。
> ⇒ 与「假零」（`0` 命中 + `rc=1` + 无诊断）**互补**：那个是**仪器**不给信号，这个是**读取姿势**把信号扔掉。
> ⇒ 判据（可直接抄）：**任何 `| grep` 取的"数量类"读数，必须同时打印 `rc`**；`rc ∉ {0,5}` 时**该读数作废**（不是"打折扣"）。

★ 我把它算作**我自己的第 7 次仪器错**（前 6 次已在 `#82` 报告 §7.3 留痕）。**这一次是我自己抓到的，不是别人报的** —— 但抓到的原因仍然是同一条老规矩：**取证后补一个"已知非零"的控制组**（`tests/pricelayer` 那格与 CONVENTIONS 的 `168` 不一致，才逼我去看那一行到底成不成立）。**若我这次的控制组恰好全对，我就带着 47 走了。**

### §5.3 ★ 副作用披露（**我主动报的，不是被问出来的**）

`ws-real-collect-2` 在后台起「轮 1」批次实测时问过我 `/tmp` 判据会不会撞车。核过 `conftest.py` 后答复如下（结论 + 证据都在这儿，便于复核）：

```
system/tests/conftest.py:23    SYSTEM_ROOT = Path(__file__).resolve().parents[1]   # 按**树**推导
system/tests/conftest.py:258   _SESSION_LOCK = SYSTEM_ROOT / "tests" / ".pytest-session.lock"
$ ls system/tests/.pytest-session.lock   →  No such file or directory     （无会话）
$ ls -la system/tests/.work/             →  空（只有 . 与 ..）             （无残留夹具）
```

⇒ **会话锁与夹具目录都是"按工作树"的** ⇒ 两条流**互不排斥、也互不触碰**（他的判断成立，不必让路）；我的 `/tmp` 两个脚本是**一次性只读**（`--collect-only` + `--noconftest` ⇒ 不建夹具、不删、不碰 `.work/`、不取锁），**跑完即退**，不是常驻判据。

★ **但我要主动报两件我做过、且可能有代价的事**：

| # | 事实 | 潜在代价 | 我的处置 |
|---|---|---|---|
| 1 | 我在 **23:47~23:50** 走 `run_pytest.sh` 跑过**两次真 pytest**（§4(4) 的那两条证据），它们**碰了我树的 `tests/.work/`**（现已清空） | 若"`.work/` 未被触碰"是**扫整个 repo**（含各工作树）的判据，我这两次**违规** | **如实报给 `ws-real-collect-2`**，请他按他的判据处置；**不自我豁免** |
| 2 | 同一窗口内我占用了宿主 CPU/IO | ★ 本仓有明证：宿主并发可把单片拖慢 **11.8×**（`verify.py` L344-349：`injection-a` 工作树 **80.92s** vs 隔离 **6.85s**）；他的轮 1 正好含 `valuelayer`/`pricelayer` 这类慢批次 ⇒ **落在该窗口的墙钟读数可能被抬高** | 已请他把**落在 23:47~23:50 的格子重跑**；并声明**此后我零负载**（本卡已交付，在等裁定） |

★ 为什么写进报告而不是只发消息：这是**本次会话的副作用记录**。§4(4) 那两条证据正是我跑出来的，**读证据的人有权知道取证动作本身动了什么**（`V-11` 仪器轴的同一逻辑：仪器的动作也在被测范围内）。

### §5.2 残余风险（如实登记）

| # | 残余 | 影响 | 我做了什么 / 没做什么 |
|---|---|---|---|
| 1 | **`≈12 例/片` 这个数我没动**（它来自 `9999 ÷ 792`，而 `792` 与 `verify.py` 写的 `785` 不一致，见 §6.3） | 回落时的片数换算不唯一 | **登记，不自裁**（属 `V-08` 口径，非卡面） |
| 2 | 改后若读者**只读 `CONVENTIONS.md`**，拿不到"现在到底几片" | 需跳一次到真源 | **刻意如此** —— 这正是"消灭第二存放处"的代价，且文件自己已有同款先例（批次数） |
| 3 | `tests/guards/` 整批、各 injection 片整片**本次未跑** | 回归覆盖面有限 | §4.1 已写明边界 |

---

## §6 登记：**同族但越卡面范围**的项（我不动，请主理人裁定归属）

### §6.1 ★ `pricelayer` 的例数也漂了（**声明**，非留痕）

```
CONVENTIONS.md（批次表，改前）：  `pricelayer` … · 168 例
现算（rc=0）：                    tests/pricelayer -> 192
verify.py:475-478（改前）：       「但本批现为 **168 例**」
```

⇒ 与我这次改的**完全同一族缺陷**（写死的例数过期），但**对象是 `pricelayer`** ⇒ 我**没有改**（`verify.py` 那处**不在我卡面的 16 处清单里**，且该段属 `ws-ch4-valuelayer` / `ws-ch5-pricelayer` 的领域）。**推荐**：与我这次同样的处理（删掉写死值，指向现算）。**这批我一句都没动，`git diff` 可证。**

### §6.2 项数族：`271` / `273` / `275` 三个值并存

```
verify.py:48      「实测每份 **271 项**」                 ← 声明，与下一条矛盾
verify.py:252     「每例副本 **271 项 → 275 项**」        ← 卡 13-F 的更正记录（留痕）
CONVENTIONS:49,94 「同一个 **273 项**夹具副本」/「实测每份 **273 项**」
test_shard_coverage.py:118  COPIED_ITEMS_PER_CASE = 273
test_guards_reject_{a,b}.py 「41 × 每例 **271** 项…」
```

⇒ **同一个量在三处有三个值**。这**不是**我这次改的两族（片数 / 例数），故**没动**；但它与本次是**同一个机理**，建议单开一卡（对象明确、可现算：`_COPY_SKIP` 口径下的文件条目数）。

### §6.3 计数/例：`785`（`verify.py`）vs `792`（`CONVENTIONS.md` + 测试）

两处都在用这个数做**除法**（`9999 ÷ X`）。若两值真有差别，则「≈12 例/片」在两边**不是同一个数**。**我没动**（属 `V-08`），但**它与 §6.4 直接相乘**：

### §6.4 ★（重申 `#82` 报告 §8.3）`12` vs `32`：两个"上限"并存，**结论相反**

- 读「**授权上限 32**」⇒ `205 ÷ 32 ≈ 6.4` ⇒ **现有 7 片已经够**；
- 读「**安全上限 ≈12 例/片**」⇒ `205 ÷ 12 ≈ 17.1` ⇒ **需要 ≈17 片，现有 7 片是违规的**。

**本次我没有消除这个歧义，只做了两件事**：① 把**片数/例数**都改成真源（不再有第三个数字参与混淆）；② 在 `CONVENTIONS.md` 里把两者的**限定语**写得更紧（`32` = 授权上限、**前提是阈值 99999**；`≈12` = **阈值回落到 9999 时**的推导值）。
⇒ **「每片到底以哪个数为准」是主理人决策**（`R-04`：不自裁）。`#82` 报告 §8.3 已上报一次，本次原地重申**不改**。

---

## §7 复跑指引

```
W=/Users/gaza/Developer/InvestSigh/.worktrees/ws-step56-skipped
P=$HOME/.workbuddy/binaries/python/envs/default/bin/python

# ① 我的 3 个提交（逐文件可单独取舍）
git -C $W log --oneline -3                 # 6f71a3c / 41fbe7e / 1706916

# ② 真值复算（含逐片 + 地板真值；脚本在 /tmp，命令本体已写进 §1）
$P /tmp/m91/measure.py $W/system
$P /tmp/m91/counts.py  $W/system $P tests/pricelayer tests/valuelayer

# ②′ ★ **不依赖我那两个 /tmp 脚本**的等价写法（只用项目自己的真源 + stdlib）
cd $W/system && PYTHONPATH=$PWD/tests $P -c '
import importlib.util,sys,subprocess,re
spec=importlib.util.spec_from_file_location("v","scripts/ops/verify.py")
m=importlib.util.module_from_spec(spec); sys.modules["v"]=m; spec.loader.exec_module(m)
tot=0
for n in m.INJECTION_SHARDS:
    a=list(m.BATCHES[n].argv); t=[]
    for x in a[a.index("pytest")+1:]:
        if x.startswith("-"): break
        t.append(x)
    r=subprocess.run([sys.executable,"-m","pytest",*t,"--collect-only","-q",
                      "-p","no:cacheprovider","--noconftest"],capture_output=True,text=True)
    c=int(re.search(r"(\d+) tests collected",r.stdout+r.stderr).group(1)); tot+=c
    print(f"{n:14s} {c:3d}  rc={r.returncode}")
print("片数",len(tuple(m.INJECTION_SHARDS)),"合计",tot)'
# 期待：injection-a 30 / b 32 / c 31 / d 29 / e 32 / f 27 / g 24；片数 7；合计 205；每行 rc=0
# ★ rc 必须逐行打印：rc ∉ {0,5} ⇒ 该行读数作废（§5.1 的教训）
# ★ 子进程用的是 `sys.executable` —— **只有当父进程就是 `$P` 时它才等于正确解释器**
#   （本仓有"`sys.executable` 不是 `run_pytest.sh` 选定的那份"的前车之鉴）。**必须用 `$P -c` 起。**
# 实测（2026-09-16，`d766a32` + 我的 3 个提交）：逐行 rc=0，输出与上面期待值逐格一致，EXIT=0
# 文件数：ls $W/system/tests/injection/test_*.py | wc -l   → 16（实测）

# ③ 门禁（注意 traceback.py 的 pre-existing 红，§4(2)）
cd $W/system && $P scripts/ops/run_all_gates.py --timeout 30

# ④ 受影响的两个机器绑定
cd $W/system && sh scripts/ops/run_pytest.sh tests/injection/test_shard_coverage.py
cd $W/system && sh scripts/ops/run_pytest.sh tests/guards/test_verification_policy.py

# ⑤ 「已消灭第二存放处」的自检：应只剩留痕项（§3 表）
/usr/bin/grep -nE '六片|6 片|6片|165|171|14 片' \
  $W/system/CONVENTIONS.md $W/system/scripts/ops/verify.py \
  $W/system/tests/injection/test_shard_coverage.py
```

---

## §8 边界声明（我没做的事）

1. **没改片数** —— 7 片 / 上限 32 一律保留（那是主理人决策）；
2. **没改 `pipeline.py` / `chain_steps.py`**（派单明令）；
3. **没碰 `rules/**`**（0444；本次 `git status` 全程无 `rules/` 变更）；
4. **没用 `git add -A`**（6 个提交均为显式单文件路径）；
5. **没用 `--no-verify`**（6 次 `pre-commit` 输出均在 §4(3)）；
6. **没把 `traceback.py` 的红算在我头上、也没掩盖它**（§4(2) 给了干净树对照）；
7. **没跑整批 `tests/guards` 与各 injection 整片**（删除配额约束）—— §4.1 已写明这是**边界**而非"已验证"；
8. **没动 §6 的四项**（`pricelayer` 例数 / 项数族 / 计数-例两值 / `12 vs 32`）—— 登记 + 推荐，**不自裁**。

---

## §9 重复工作的事后取证（**先读 §0.1**）

### §9.1 我是怎么发现的（★ **不是靠"看一眼 main"，是靠一个不成立的读数**）

我做最终范围自检时用了：

```
$ git diff --stat main..HEAD          # ★ 两点号
 system/CONVENTIONS.md                              |  257 +--
 system/PROGRESS.md                                 |   17 -
 ...（共 20 个文件，含 pipeline.py / pre-commit.sh / install_hooks.sh）
```

**我的分支里不可能有 `pipeline.py` 的改动** ⇒ 这个"20 个文件"是**假的**。原因正是我在 `#82` 报告 §4.2 亲手写下过的那条：

> ★ 两点号 `git diff main..b` ≡ **tip-to-tip**、**不携带 merge-base 语义** ⇒ 判"我的改动"必须写显式 `merge-base`。

`main` 在我工作期间从 `d766a32` 前进到 `cd05e1f`，于是 tip-to-tip 把**别人的 20 个文件**算成了我的。改用显式 merge-base 后立刻干净：

```
$ MB=$(git merge-base main HEAD)      # = d766a32
$ git diff --stat $MB..HEAD
 system/CONVENTIONS.md                          |  57 ++--
 system/reports/ws_card91_shard_drift_report.md | 351 +++++++++
 system/scripts/ops/verify.py                   |  36 +--
 system/tests/injection/test_shard_coverage.py  |  16 +-
 4 files changed, 412 insertions(+), 48 deletions(-)
$ git diff --name-only $MB..HEAD | grep -E 'pipeline\.py|chain_steps\.py|^system/rules/'
 （空，rc=1）      ← 没碰
```

★ **方法论**：**"我的改动范围"这个读数，永远不能用 `A..B` 两点号去取**（除非你确知 `A` 未前进）。本次若我信了那个 20 文件清单，就会得出"我改坏了 pipeline"的假结论；若我不做这一步自检，就会**带着重复提交去请人合并** —— 而 §0.1 那个表里有**一个会回退 `main`** 的提交。

### §9.2 两版修法的净对照（`git diff main:<file> HEAD:<file>`）

| 文件 | 净差异行数 | 性质 |
|---|---|---|
| `verify.py` | 60 | `main` **已覆盖 12 / 16 处**（措辞等价或更好）；`main` **未覆盖 4 处**（见 §0.1 表） |
| `CONVENTIONS.md` | **259** | ★ **不是并列，是回退**：`main` 的批次表已换成**新测的超时与实测值**且已含 `injection-g` 行；我这一版是**旧表** |
| `test_shard_coverage.py` | 18 | 纯增量（`main` 未动此文件） |

### §9.3 ★★ 一条**独立于 `#91` 归属**的发现：`#91` 的修法**自己的漂移记录，15 分钟后就已经漂了**

`d3f5701` 在 `CONVENTIONS.md` 里写下（**这是很好的做法** —— 它把漂移留了痕）：

> 本表此前写死过片数与例数，实测已漂移（写「6 片」实为 **7**；`a` 写 27 实为 **30**、`b` 写 28 实为 **32**、`d` 写 31 实为 **29**、`f` 写 31 实为 **27**，`g` **整行缺失**；**`pricelayer` 写 168 实为 183**）

**但 `183` 在我复算时已经不成立：**

```
$ ...（口径同 _collect_count，rc 已打印）
pricelayer   targets=['tests/pricelayer']  count=192  rc=0
valuelayer   targets=['tests/valuelayer']  count=206  rc=0
```

★ **根因闭合到单个提交**：

```
$ git show bf99f91 -- system/tests/pricelayer/ | grep -cE '^\+\s*def test_'   → 9
$ git show bf99f91 -- system/tests/pricelayer/ | grep -cE '^-\s*def test_'   → 0
$ git log -1 --date=format:'%m-%d %H:%M:%S' --format='%h %ad %s' bf99f91
  bf99f91  09-16 23:26:00  test(pricelayer): 补第四轮「缺子键必须红」的回归锁（9 新例 + 2 反向对照）
$ git log -1 --date=format:'%m-%d %H:%M:%S' --format='%h %ad %s' d3f5701
  d3f5701  09-16 23:41:03  fix(docs): #91 …
```

**`183 + 9 = 192`，精确闭合**；且 `bf99f91`（23:26）**比** `d3f5701`（23:41）**早 15 分钟**。

⇒ **两条结论**：
1. **`pricelayer` 现算 = 192**（不是 183、不是 168）。**请归属者把 `CONVENTIONS.md` 里那句 `183` 改成真源或重取**（我不动 `main`）。
2. ★★ **这一族漂移的"最省事解法"本身也会漂**：把写死的 `168` 换成写死的 `183` —— **换了个更近期的快照，仍然是第二个存放处**。`bf99f91` 那 9 例一落地，新快照当场过期。
   ⇒ 这正是我在 §2 采用**「指向真源」而不是「更新数字」**的实测理由：**更新数字只能把漂移推迟到下一次提交**。
   ★ 与 `V-10` 的「地板真值也要带控制组」是同一课：**任何"数量"读数都必须连着"它是哪一刻、在哪棵树上、用什么仪器量的"一起报**，否则它一出生就在倒计时。

### §9.4 我保留的增量（若 §0.1 的建议被采纳，就是这些）

| 文件 | 处 | 内容 | 为什么 `main` 没有 |
|---|---|---|---|
| `verify.py` | L29 | 表行标签 `injection-a`…`injection-g` + 「**7 个分片**」→ `injection-*` + 指向真源 | `d3f5701` 精修的是「6 片→多片」，**没有回头修"7"** —— 而"7"是**下一个会漂的数** |
| `verify.py` | L72 | 「**27 / 28 例**的片…」→ 「最接近授权上限的那片…（片内例数用现算值）」 | 同上，`d3f5701` 未覆盖 |
| `verify.py` | L73 | 「（**≈14 片**）」→ 「片数 = ⌈现算例数 ÷ 12⌉」 | `d3f5701` 保留了 `≈14`（见其 diff：`（需 ≈14 片）`） |
| `verify.py` | L259 | 「（需 **≈14 片**）」→ 「（需 ⌈现算例数 ÷ ≈12⌉ 片）」 | 同上 |
| `test_shard_coverage.py` | L104 / L111-112 / L113-115 / **L331** | 同上四处的同款真源化；**L331 是断言失败消息** | **`d3f5701` 完全没碰这个文件** |

★ 其中 **`≈14 片` 这 3 处是本次**唯一仍会立刻漂**的数：`205 ÷ 12 ≈ 17.1` ⇒ 真值是 **≈17 片**，不是 14。

★★ **`main` 上（复算于 `b1000b4`）这些行号是**（接手的人直接用这一列，别用"改前行号"）：

| 文件 | `main@b1000b4` 行号 | 内容 |
|---|---|---|
| `verify.py` | **L29** | `| \`injection-a\`…\`injection-g\` | … **7 个分片** |` |
| `verify.py` | **L72** | 「（**27 / 28 例**的片在本机当前阈值下单轮跑完、`exit=0`）。」 |
| `verify.py` | **L73** | 「…约 12` 例/片重排（**≈14 片**）——」 |
| `verify.py` | **L262** | 「现登记的片数（每片 ≤32 例）…（需 **≈14 片**）；」 |
| `test_shard_coverage.py` | **L111** | 「`a` **27 例** / `b` **28 例** / `d` **31 例** / `f` **31 例**」 |
| `test_shard_coverage.py` | **L113-114** | 「**6 片**立刻不成立（目录现有 **171 例**，需要 **≈14 片**）／扩到 **≈14 片**」 |
| `test_shard_coverage.py` | **L331** | ★ 断言失败消息：「…（⇒ 需 **≈14 片 / 14 个轮次**）」 |

★ 复算方式（可复跑、不依赖我的分支）：
```
git show main:system/scripts/ops/verify.py | grep -nE '≈14 片|27 / 28 例|7 个分片'
git show main:system/tests/injection/test_shard_coverage.py | grep -nE '≈14 片|171 例|6 片|27 例'
git show main:system/CONVENTIONS.md | grep -nE '183|168'      # 见 §9.3：L96 的 183 已过期（现算 192）
```

### §9.5 流程观察（供团队参考，不是抱怨）

1. **`main` 前进后，`main..HEAD` 会骗人**（§9.1）—— 建议把「判自己的改动范围一律用显式 `merge-base`」写进 `V-10`/`V-11` 的方法论条目（我 `#82` §4.2 已单独报过这条，**这次它救了我**）。
2. **"别人的分支先落地"这件事没有可见信号**：我的分支 FF 到 `d766a32` 之后，`main` 前进、且**同一张卡被别人做了**，而**任务列表没有任何变化**（`#91` 一直是 `in_progress` + owner 我）。若开工前有一条「**认领卡时先 `git fetch` 并把 `main` tip 记进报告头部**」的纪律，我至少会**先发现 `d3f5701` 已经在 main 里**。★ 我这次记了 tip（`d766a32`），**但没记"记完之后 main 还会动"**。
3. **撞车时最有用的动作是"给出取舍表"而不是"解释为什么我会撞"**（§0.1 那张表）—— 因为对方要的是"**哪个提交能合**"，不是"谁对"。
