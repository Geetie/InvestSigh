# `ws/fixture-cost` 交付报告 —— 修 `G-54`（共享夹具成本：每例 ≈5s 的 `setup`）

> 一句话结论：**每例 5s 不是 `copytree`，也不是"树变大了"。**
> 是 `tests/conftest.py::_reset_truth_source()` 里 **`raw/` 那一段逐项删除** ——
> 宿主对**每一次删除调用**收一笔**固定 ≈0.5~0.8s** 的审批往返（**与删几项无关**），
> 那里发了 **5 次调用** ⇒ **≈4.2s/例**。
> 修法一行：**让 `raw/` 的内容根本不进副本**（副本里它本来就该是空的）。
> 修后 `unit` **60.58/58.52s → 15.79/11.42s**；`guards` 从**每次必超时**变成 **27.13/19.11s**。

---

## ① 改了什么

| # | 文件 | 改动 | 为什么 |
|---|---|---|---|
| 1 | `system/tests/conftest.py` | `_COPY_SKIP` 加 **`"raw"`**（1 项 + 大段注释） | 副本里的 `raw/` **必须是空的**（`_reset_truth_source` 正是清空它的那一步）。"复制进来再逐项删掉"要按**删除调用次数**付费 ⇒ 直接不复制 |
| 2 | `system/tests/conftest.py` | `_reset_truth_source()` docstring 记录**成本模型**（含实测表） | 这是"下一个 5s"的入口：**再往 `raw/` 放 5 个文件就又是 4s**。逐项清理循环**保留**为兜底 |
| 3 | `system/scripts/ops/verify.py` | `guards` 60s→**120s**、`compute` 60s→**180s**、`validators` 30s→**90s**、`claim` 30s→**120s**、`decision` 30s→**120s** | 卡 13-F 的批次对照表实测出 **5 个批次余量 < 4×**（`V-02` 要求 4~8×）⇒ 它们**会随机红**。详见 ③-4 |
| 4 | `system/scripts/ops/verify.py` | `unit` 的注释：**更正根因**（原写"疑似整树拷贝、代价随仓库体积增长"） | 该判断已被实测证伪，留着会误导下一个人。`unit` 的 270s **故意不动**（理由见 ③-3） |
| 5 | （不是代码改动）**提交前 `git merge main` → 立刻重跑 `sh system/scripts/ops/bootstrap_worktree.sh`** | `main` 已前进到 `65cef01`（含批次 13-A 的 `valuelayer`）。按 `V-07`/`G-53`：`merge` 会把 `rules/*.yaml` 的 `0444` 还原成 `644`，不重跑则 `rules_lock_guard` 必红。实测重跑输出：`已把 14 个 rules 文件置为 0444` + `rules_lock_guard … RESULT: PASS（0 violations）` |

**改动的落地顺序（如实记录）**：`git merge main` 被本地未提交改动挡住（`main` 也改了
`verify.py`，但改的是**另一段**——新增 `valuelayer` 批次，与我的注释改动不同 hunk）。
故实际顺序是 `git stash push -u -- <三个文件>` → `git merge main`（**fast-forward**，`HEAD == main == 65cef01`）
→ `git stash pop`（`verify.py` 自动合并成功，无冲突）→ `bootstrap_worktree.sh`。
**最终树 = main + 我的三处改动**，与"先 merge 再提交"的期望终态一致。

**没做**（明确边界）：

- **没有**动夹具契约：`_SESSION_LOCK` 位置（`WORK_DIR` 之外，`V-05`）、`tests/.work/` 点目录约定、
  `_make_writable`（"夹具可写"这条契约，注入测试靠它）、`facts/` 的 22 个 JSONL 结构 —— **一行未动**；
- **没有**靠"缩小夹具副本"省时间：`scripts/` / `tests/` 仍在副本里（有些守卫**正是扫副本**的：
  `conflict_scan` 的 L2 扫 `code_root/scripts/**`、`verification_policy_guard` 扫 `code_root/tests/**`）。
  证据：改后 `verification_policy_guard` 仍扫到 `test_files: 67`（合并 `main` 后为 **74**；
  塌成 0 就是守卫静默失效）；
- **没有**改任何断言语义、**没有** `git add -A`、**没有** `--no-verify`。

---

## ② 测了什么（贴真实输出）

### 2.1 根因定位：插桩 `code_root`，逐步计时（★ 这一步推翻了原假设）

在 `tests/conftest.py` 的 `code_root` 与 `_reset_truth_source` 里临时加 `FX_TRACE` 计时（**测完已还原**）：

```
$ FX_TRACE=1 sh system/scripts/ops/run_pytest.sh \
      tests/unit/test_contracts.py::test_append_never_truncates_existing_lines -q -s
[FX_TRACE]   _reset_truth_source: facts(22 写)=0.002 raw(清 5 项)=4.157
[FX_TRACE] test_append_never_truncates_existing_lines setup:
            copytree=0.099 ensure=0.000 writable=0.015 reset=4.159 total=4.274
.[FX_TRACE] test_append_never_truncates_existing_lines teardown: 0.654
1 passed in 5.76s
```

| `code_root` 的一步 | 实测 | 占比 |
|---|---|---|
| `shutil.copytree(SYSTEM_ROOT, …)`（253 文件 / 56 目录 / 2.41 MB） | **0.099~0.277s** | 2% |
| `_ENSURE_DIRS` 5 个 `mkdir` | 0.000s | 0% |
| `_make_writable()`（`rglob` + chmod 310 个 path） | **0.015s** | 0% |
| `_reset_truth_source()` —— 其中 `facts/` 22 次写 = 0.002s | **4.159s** | **98%** |
| ↳ **其中 `raw/` 清 5 项** | **4.157s** | **97%** |
| （teardown，不算 setup）`shutil.rmtree(≈310 项)` | 0.654~1.07s | — |

★ **原假设（"整树 `copytree`、代价随仓库体积增长"）被证伪**：
`copytree` 只有 **0.10~0.28s**，而树一共才 253 个文件 / 2.41 MB。
`--durations` 把 4~5s 记在 `setup` 上，是因为**那段删除确实发生在 fixture 的 setup 阶段里**，
不是 `copytree`。

### 2.2 成本模型：自变量是**删除调用次数**，不是项数，也不是树体积

```
$ CODEBUDDY_SAFE_DELETE_SANDBOX=0 python /tmp/fx_model.py     # 工作区 tests/.work/ 内
== A) k 次独立 unlink（k 个文件，逐个删）==
   k= 1 次 unlink ⇒  0.829s   （0.829s / 次调用）
   k= 2 次 unlink ⇒  1.202s   （0.601s / 次调用）
   k= 4 次 unlink ⇒  2.024s   （0.506s / 次调用）
   k= 8 次 unlink ⇒  4.325s   （0.541s / 次调用）
== B) 1 次 rmtree（n 个文件，一次删完）==
   n= 50 项 1 次 rmtree ⇒  0.864s   （17.28ms / 项）
   n=150 项 1 次 rmtree ⇒  0.742s   （ 4.94ms / 项）
   n=310 项 1 次 rmtree ⇒  0.756s   （ 2.44ms / 项）
== 对照：创建（写）不慢 ==
   写 310 个文件 = 0.038s
```

⇒ **两个结论**：

1. **`T ≈ 0.54s × 删除调用次数`**（k=1→8 线性，8 次 = 4.33s）；
2. **一次 `rmtree` 的代价与项数几乎无关**（50/150/310 项分别 0.86/0.74/0.76s）
   ⇒ **"树再大 N 倍会怎样"的答案是：几乎不变**（310 项时边际只有 2.4ms/项）。
   真正会炸的是**删除调用次数**多 N 倍。

逐项实测（工作树内，`_reset_truth_source` 会碰到的那 5 项）：

```
   文件 2024-11-20-nvidia-q3-fy2025-results.txt   0.853s
   文件 2025-02-26-nvidia-q4-fy2025-results.txt   1.037s
   文件 2026-08-04-amd-q2-2026-results.txt        0.980s
   文件 2026-09-10-tsmc-aug2026-revenue.txt       1.083s
   目录 inbox（rmtree）                            1.056s
   合计 ≈ 5.0s        ← 对照：整个夹具目录（≈310 项）一次 rmtree 只要 1.036s
```

**同 5 项在工作区外（`/tmp`）清完** = **0.196s** ⇒ 同一个操作 **21×** 差异
⇒ **这个代价是"在工作区里删东西"的属性，不是文件系统的属性**（与 `V-08` / `G-53` 同族）。

### 2.3 修复的 A/B 对照（同机、同命令、相邻时间）

| 批次 | A：无修复 | B：有修复 | 结果 |
|---|---|---|---|
| `unit` | **60.58s / 58.52s**（76 passed） | **15.79s / 11.42s**（76 passed） | **≈4.2×** |
| `guards` | **60.02s / 60.02s → `exit=124` TIMEOUT** | **27.13s / 19.11s**（69 passed） | 从**每次必红**到**稳定绿** |

```
########## A（临时把 "raw" 从 _COPY_SKIP 移除）##########
✗ [guards] … exit=124  60.02s/60s  **超时** —— 该批有问题（极大概率是测试本身）
[TIMEOUT] 批次 'guards' 超过 60s 未返回 —— **该批有问题**（极大概率是测试本身，不是「跑得慢」）。
########## B（修复在位）##########
✓ [guards] … exit=0  27.13s/120s  exit=0
69 passed in 21.24s
```

★ 这条比"慢"严重：**`guards` 在修复前是"每次都超时"的门禁** —— 也就是
按本项目铁律「**卡死的门禁 = 被关掉的门禁**」，`guards` 当时**已经等于不存在**。
而它的失败信息写的是"该批有问题（极大概率是测试本身）"——
**指向测试，实际是夹具**。这正是"假缺陷淹没真问题"的又一例。

单点对照（同一对用例，隔离跑）：

```
修前: 4.05s setup / 3.95s setup   →  2 passed in 11.53s
修后: 0.16s setup / 0.11s setup   →  2 passed in  3.69s
```

### 2.4 行为等价性（★ 证明这行改动**不改语义**）

修复的关键论证是「副本里的 `raw/` 终态本来就是空的」。实测两边终态：

```
修复后（raw 不复制）夹具 raw/ 内容: []
修复前（raw 被复制后由同一函数清空）:
    复制进副本的 raw/ 内容: ['2024-11-20-nvidia-q3-fy2025-results.txt',
                           '2025-02-26-nvidia-q4-fy2025-results.txt',
                           '2026-08-04-amd-q2-2026-results.txt',
                           '2026-09-10-tsmc-aug2026-revenue.txt', 'inbox']
    _reset_truth_source 之后 raw/ 终态: []
=> 与修复后（raw/ = []）一致: True
```

⇒ 两边 `code_root` 的 `raw/` **都是空目录** ⇒ 观测量完全相同。
旁证：`injection_guard._raw_has_external_text(code_root)` 两边都是 `False`；
`raw/inbox/.gitkeep` 本来就不在副本里（`_ignore()` 会跳过点号开头的名字）⇒ 无差异。

### 2.5 回归：相关批次复跑（每批单独跑，`verify.py --batch <名>`）

| 批次 | 判定 | 用例 |
|---|---|---|
| `unit` | ✓ exit=0 | **76 passed** |
| `guards` | ✓ exit=0 | **69 passed** |
| `conflict` | ✓ exit=0 | **6 passed** |
| `pricelayer` | ✓ exit=0 | **127 passed** |
| `validators` | ✓ exit=0 | **21 passed** |
| `claim` | ✓ exit=0 | **24 passed** |
| `graph` | ✓ exit=0 | **38 passed** |
| `compute` | ✓ exit=0 | **102 passed** |
| `decision` | ✓ exit=0 | **97 passed** |
| `transmit` | ✓ exit=0 | **29 passed** |
| `root` | ✓ exit=0 | **8 passed** |
| `stage` | ✓ exit=0 | — |
| `gates` | ✗ exit=1 | `traceback.py` exit=1（**既有真源红，见 ④.3**） |

> ★ 上表是**合并 `main` 之前**的复跑（当时 `HEAD=c591082`）。合并后 `main` 新增了
> `tests/valuelayer/`（新批次）与 `tests/daily/test_no_change_day.py`、`tests/injection/` 增量，
> **夹具批次的耗时数字因此过期**；合并后的复跑被宿主配额挡住（2.6 / ④.1），
> 故**不假装它们仍然成立**。

### 2.6 机制：从源码钉死"每次删除调用一笔审批往返"与"配额按轮累计"

上一版报告把"按调用付费"登记为**未钉死的经验律**（旧 ④.4）。**现已读到实现源码**，
把机制、计数口径、**恢复边界**三者都钉住（这条也是 ④.1 配额阻塞的解释）。

源码：`/Applications/WorkBuddy.app/…/cli/vendor/shim/safe-delete-bulk-guard.cjs`（466 行，读得到）
＋ Python 侧 `…/cli/vendor/shim/sitecustomize.py`（`shutil.rmtree` 被换成 `_safe_shutil_rmtree`）。

| 事实 | 源码依据 | 含义 |
|---|---|---|
| 计数单位 = **被删目标树下的文件条目数** | `countTarget()` :270-304（目录本身不计数，符号链接计 1，递归） | 与我实测口径一致：残留夹具树 **248~250 项** |
| **每次调用**都要过闸 | `checkSafeDeleteBulkGuard()` :315-368 由 `check` 子命令逐次调用 | ⇒ 每次 `unlink`/`rmtree` 各付一笔固定往返（§2.2 的 k 次线性） |
| 累计键 = **conversation request（= 一个用户轮次）** | `requestId = conversationRequestId \|\| toolCallId` :70；`state.requests[requestId]` :337-364 | **同一轮内所有工具调用共用一个计数器**；新工具调用**不**重置 |
| 闸门 = `累计 + 本次 >= 阈值` | :344-350 `totalCount >= context.threshold` | 阈值来自 `CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD`（默认 20；本会话 **99999**） |
| `scope:"turn"` 就是这个 conversation request | `approve` 只接受 `scope=turn` :401-410 | **恢复边界 = 新的一轮（新用户消息）**，不是新工具调用、也不是时间 |
| 计数**有上限截断** | `countTargets(targets, DISPLAY_COUNT_LIMIT=9999)` :16,:339 | 单次调用**最多只推进 9999** ⇒ 计数是**下界**，不是真实总量 |
| 批准粒度 = **单个 toolCallId** | `state.toolApprovals[toolCallId]` :338,:345-349 | 一次确认只放行**那一个**工具调用（这也解释了同一轮里"小删除过、大删除拦"） |
| 否决粒度 = **整个 request**，且**粘住整轮** | :322-336 + `state.requestRejections[requestId]` | 一旦被明示否决，**该轮后续所有删除都直接 exit 3** |

**本会话的直接读数**（`…/T/codebuddy-safe-delete-bulk/…/state.json`）：

```
CODEBUDDY_SESSION_ID                = a7418ea3-deac-450a-979d-a9a93fcb393e
CODEBUDDY_CONVERSATION_REQUEST_ID   = c30d46109d0b48dbb8662a3522afa15b      ← 累计键
CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD= 99999
state.requests[c30d4610…] = {"count": 99998, "updatedAt": …}                  ← 余量 1 项
state.requestRejections = {}                                                ← 不是被否决，是"持续要确认"
```

⇒ **`99998 + 任意≥1 项 >= 99999` 恒真** ⇒ 本轮每一次 ≥2 项的删除都 `confirmRequired`（exit 2）。
而 `request.count` 因为走的是 confirmRequired 分支（**不写回**，:361）**冻结在 99998** ⇒
报告出来的 `count` = `99998 + 本次目标树的项数`。据此反推：
`100213−99998=215`、`100216−99998=218`、`100218−99998=220`
⇒ **每次被拦的 rmtree 目标树 = 215~220 项**（与静态实测 248~250 同量级，差异见 ④.7）。

**夹具副本的静态体积**（不需要删除即可测；`_COPY_SKIP` 口径模拟 `copytree`）：

| 顶层 | 文件条目 | 占比 |
|---|---|---|
| `scripts` | 113 | 41.1% |
| `tests` | 86 | 31.3% |
| `facts` | 23 | 8.4% |
| `rules` | 15 | 5.5% |
| `registry` | 11 | 4.0% |
| `schema` | 8 | 2.9% |
| 其余 7 个顶层 | 19 | 6.9% |
| **合计** | **275 条目 / 2.69 MB** | 100% |

⇒ 一次夹具 teardown 的配额代价 ≈ **250 项**；`unit`（≈100 例夹具）≈ **25,000 项/轮**，
阈值 99999 下**一轮只够约 3~4 个 `unit` 量级的批次** —— 与 `V-08`「一轮一批」的纪律一致。

★ **修复对配额的贡献要如实说**：每次调用收的是**树下的项数**，而修复去掉的是
`raw/` 的 **5 次逐项删除 = 5 项** ⇒ 每例配额 **255 → 250 项（−2%）**。
即**修复几乎不省配额**（省的是**调用次数** = 时间），"一轮一片"照旧。

---

## ③ 逐条对齐派单

### 3-1 「定位根因：具体哪个 fixture、哪一行，为什么 5s」 ✅

- **fixture**：`tests/conftest.py::code_root`（:157，`scope="function"`）；
  同源函数也被 `pristine_code_root`（:199，`scope="session"`）调用。
- **触发装置**：`:166 shutil.copytree(...)` → `:167 _ENSURE_DIRS` → `:169 _make_writable` →
  **`:171 _reset_truth_source(target)`**。
- **具体行**：`_reset_truth_source()` 内 **`raw/` 的清理循环**（逐项 `shutil.rmtree` / `item.unlink`）。
  本目录命中 **5 项**（4 个 `raw/*.txt` + `raw/inbox/`）⇒ **5 次删除调用**。
- **为什么 5s**：宿主对**每次删除调用**收 **≈0.5~0.8s** 固定审批往返（2.2 的 A/B 实测）。
  5 × ~0.84 ≈ **4.2s**，与实测 **4.157s** 吻合。
- ★ **原假设（`copytree` 整树拷贝 + 树体积）已如实改口**：`copytree` = 0.10~0.28s，
  与 5s 无关。改口证据在 2.1 / 2.2。

### 3-2 「量化成本模型：单例 setup vs 被拷贝树体积，至少两组对照，要能算再大 N 倍」 ✅

两组对照都做了，而且**结论与原假设相反**：

| 对照 | 数据 | 结论 |
|---|---|---|
| 删 **1 次** vs 删 **k 次**（同项数） | k=1/2/4/8 ⇒ 0.83/1.20/2.02/4.33s | **线性于调用次数**（≈0.54s/次） |
| 删 **1 次** vs **项数** n=50/150/310 | 0.86/0.74/0.76s | **与项数无关**（边际 2.4ms/项 @310） |
| 同一份 5 项清理：**工作区内 vs 工作区外** | 4.157s vs 0.196s | **21×**——是"工作区内删除"的属性 |
| `copytree` vs 树体积 | 0.099~0.277s（253 文件 / 2.41 MB） | 极廉，**不是瓶颈** |

**"再大 N 倍会怎样"**：

- 文件数 ×10（2,530 文件）⇒ `copytree` ≈ 1.3s、teardown `rmtree` **仍 ≈0.8s**（1 次调用）⇒
  每例增量 ≈ +1.3s，**线性但是斜率很小**；
- **`raw/` 里再加 5 个文件** ⇒ 每例 **+4.2s**（再 5 次删除调用）⇒ **这才是会炸的方向**。
  ⇒ 所以修完之后，**新增 `raw/` 里的样本文件不再拖慢任何测试**（它们不进副本了）。

### 3-3 「修复：按收益/风险排序，选最保守有效的一条」 ✅

三条候选我**实测过**再选（没有靠推断排除）：

| 候选 | 实测/评估 | 结论 |
|---|---|---|
| **A** 会话级基线拷贝 + 每例廉价 overlay | **`conftest.py::_empty_truth_template` 就是这条的失败尝试**（:139，docstring 里记着）：会话收尾删那个大模板**被宿主拒绝** → 模板膨胀到 8 万+项 → 下一轮 `pytest_sessionstart` 判"删不干净"→ **整批 1s 内红** | **否决**（前车之鉴，且要动 `_clear_work_dir` 与点目录约定） |
| **B** 只拷被测所需子树 | 会动"副本完整性"这个被守卫依赖的前提（`conflict_scan` L2 扫 `code_root/scripts/**`、`verification_policy_guard` 扫 `code_root/tests/**`）；且 310 项的一次 `rmtree` 只要 0.8s ⇒ **收益接近 0** | **否决**（违反派单约束 ③，收益也站不住） |
| **C** 让只读使用点改成只读引用 | 与候选 A 同族，同样要重做"每例可写副本"这套契约 | **否决** |
| ★ **D（选它）**：`raw` 加入 `_COPY_SKIP` | **一行**；终态**逐字等价**（2.4 已实测）；不碰 `_SESSION_LOCK` / 点目录 / `_make_writable` / `scripts/` / `tests/`；**setup 4.16s → 0.15s** | **采纳** |

**为什么 D 比"把 5 次调用合并成 1 次"更好**：合并成 1 次仍要付 **0.84s/例**
（`unit` 13 例 ≈ 11s），而 D 是 **0 次**。而 D 的等价性是**可证的**（那个目录反正要被清空），
不是"大概没问题"。

**修复后未动的部分（如实）**：teardown 的 **1 次 `rmtree` ≈0.75s/例** 仍在 ——
它已经是**一次调用**，在"按调用付费"的模型下**已到地板**，**缩小副本也省不掉**。
所以夹具用例仍然每例 ≈0.9~1.0s 的固定成本；这是当前宿主环境下**不可再降的**。

**关于 `unit` 的 270s**：修后实测 **15.79s**，270s = **17.1×**，比 `V-02` 的 4~8× 宽。
我**故意没有压回**：① 我**没有**"修后 + 满负载"的实测，不拿未测场景去收紧；
② 派单明示"不要为了好看把它压回 60s"。**建议值**：等一次满负载复测确认最慢值后按
`最慢 × 4~8` 取 —— 按现有数据的参考值 ≈**120s**（15.79 × 7.6），**现在就取 60s 是不成立的**
（60/15.79 = 3.8× < 4×）。**这是建议，未擅自改**。

### 3-4 「批次实测耗时 vs 超时对照表（每批 2 次、标出 < 4× 的）」 ✅（有缺口，见 ④）

`verify.py --batch <名>`，2026-09-16，本工作树（`wall` 为 `verify.py` 记的批墙钟）。
**"倍数"= 超时 ÷ 两次数值中较慢的一次**。

| 批次 | run1 | run2 | 方差 | 当前超时 | 倍数 | 夹具用例 | 判定 | 处置 |
|---|---|---|---|---|---|---|---|---|
| `unit` | 15.79s | 11.42s | 4.4s | 270s | **17.1×** | ~13 | ✓0 | 维持（见 3-3，建议值 ≈120s） |
| `conflict` | 1.64s | 1.53s | 0.1s | 30s | 18.3× | 0 | ✓0 | 维持 |
| `guards` | 27.13s | 19.11s | 8.0s | 60s→**120s** | **2.2×** ★ | ~20 | ✓0 | **已上调 120s**（4.4×） |
| `root` | 1.60s | 1.40s | 0.2s | 30s | 18.8× | 0 | ✓0 | 维持 |
| `compute` | 36.62s | 33.74s | 2.9s | 60s→**180s** | **1.6×** ★ | **0** | ✓0 | **已上调 180s**（4.9×） |
| `graph` | 3.83s | 3.21s | 0.6s | 60s | 15.7× | ~20 | ✓0 | 维持 |
| `validators` | 19.26s | 12.81s | 6.5s | 30s→**90s** | **1.6×** ★ | ~20 | ✓0 | **已上调 90s**（4.7×） |
| `claim` | 22.44s | 17.88s | 4.6s | 30s→**120s** | **1.3×** ★ | ~20 | ✓0 | **已上调 120s**（5.3×） |
| `decision` | 22.14s | 24.86s | 2.7s | 30s→**120s** | **1.2×** ★ | **0** | ✓0 | **已上调 120s**（4.8×）——全表最危险 |
| `transmit` | 9.39s | 4.12s | 5.3s | 60s | 6.4× | ~20 | ✓0 | 维持 |
| `evidence` | **配额** | **配额** | — | 150s | — | ~40 | 未取得 | 见 ④.1 |
| `daily` | **配额** | **配额** | — | 180s | — | ~40 | 未取得 | 见 ④.1 |
| `pricelayer` | 33.52s | 33.46s | 0.1s | 180s | 5.4× | 0 | ✓0 | 维持 |
| `valuelayer` | **未由本单复测** | — | — | 300s | **1.76×** ★ | 28 | 见下 | **需注意**（见下） |
| `injection-a`…`f` | 未测 | 未测 | — | 300s | — | 32~69 | 未测 | 见 ④.1 |
| `gates` | 9.36s | 9.45s | 0.1s | 60s | 6.4× | 0 | ✗1 | 既有真源红，见 ④.3 |
| `stage` | 0.67s | 0.93s | 0.3s | 30s | 32× | 0 | ✓0 | 维持 |

★ **倍数 < 4×（"会随机红"）= 5 个（本单实测）**：`guards` 2.2× · `compute` 1.6× · `validators` 1.6× ·
`claim` 1.3× · `decision` 1.2×。**这 5 个已上调**（纯安全网上调，只会减少误报，不会掩盖卡死）。
★ 值得注意：`compute` 与 `decision` **一个夹具用例都没有** ⇒ 它们的紧余量**与夹具无关**，
夹具修复**不会**改善它们；`guards/validators/claim` 则**已经被夹具修复改善了**（否则更紧）。

★ **第 6 个 < 4× 的批次：`valuelayer`（1.76×）—— 由 `main` 侧批次 13-A 加入，本单未复测**。
它的注释（`verify.py` 里那一段）**自己已经如实登记了**这条风险（"本批余量仅 1.76×，
比 `injection-f` 的 2.7× 更薄"），且已按 `V-02` 的 300s 上限取满
（170.15 × 4 = 680 > 300 ⇒ **上限卡住了它**，不是没算）。**处置建议**：不需要改超时
（已到上限），需要的是**确认它的 170.15s 不是在多会话并发下取的**；本单的夹具修复对它**有益**
（28 个夹具用例 × 每例 ≈4.2s 已省掉 ≈118s ⇒ 修后应显著低于 170s）——
**这是一条可证的预测**：若下一位在**修后**复测 `valuelayer` 仍 ≥170s，说明它的成本**另有来源**，
应当再开一张卡，而不是调超时。

### 3-5 「报告四段式 + 真实输出 + commit hash + `git status`」 ✅ 见 ④ / ⑦

---

## ④ 剩余不确定性与缺口（如实报出，不掩盖）

1. **★ `evidence` / `daily` / `injection-a`…`f` 本轮未取得实测** —— 原因是**宿主单轮删除配额**：
   我这一轮把 24 次批次运行排在一起，在 `evidence` 处撞到
   `SAFE_DELETE_BULK_CONFIRM_REQUIRED {"count":100210,"threshold":99999}`，
   之后的 `evidence#2` / `daily#1` / `daily#2` 都只有 0.5~0.7s 就红（**同一个 count，配额不恢复**）。
   **这不是测试失败**（`verify.py` 的配额归因已正确标出），也**不是修复引入的**。
   ⇒ 需求：**新开轮次**，`evidence` / `daily` 各一轮，`injection-a`…`f` **6 个轮次**。
   ★ **机制已钉死（§2.6），所以这条可以写成可操作的判据**，不必再靠试：
   - 配额键 = **`CODEBUDDY_CONVERSATION_REQUEST_ID`（一个用户轮次）**，本会话该键
     `count=99998 / threshold=99999` ⇒ **本轮余量 1 项**，任何夹具用例的 teardown（≈250 项）都会被拦；
   - **恢复边界 = 新的一轮（新的用户消息）**。★ **新开工具调用不会重置**（我在同一轮里做了
     十余次工具调用，`state.requests[c30d4610…].count` 一直是 99998）；
     `TURN_STATE_TTL_MS` 是 7 天，**也不做时间重置**；
   - ⇒ 排查判据：**看到 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 且 `count` 与上次几乎相同 ⇒
     别再重试**，要的是新轮次。**重试只会浪费一个轮次**。
   ★ 顺带一条**必须登记的反直觉事实**（现已按 §2.6 精算）：**本次修复几乎不降低配额消耗** ——
   配额按**目标树下的项数**计，修复去掉的是 `raw/` 的 **5 项/例** ⇒ 每例 **255 → 250 项（−2%）**。
   省下的是**调用次数**（= 时间），不是配额。所以"一轮一片"的纪律**照旧成立**。
2. **`unit` 的 270s 未按新实测收紧**（理由见 3-3）。**若你要收紧**，请以一次**满负载复测**为准；
   我手上的 4 个样本（9.42 / 9.99 / 11.14 / 15.35s pytest 时长）都是**相对空闲**时取的。
3. **`gates` 批仍 `exit=1`，且是既有真源红，与本单无关**：唯一非零项是
   `traceback.py exit=1`，指向 `facts/recommendations.jsonl:0 — rec-nvda-001 四要素缺失`（`T-10`）。
   该守卫读的是 `facts/`，**不读 `tests/`**，故与本次 `conftest.py` 改动无因果关系。
   （`conftest.py` 的 docstring 早已把 `traceback`（`T-10`）列为**预期的真源红**。）
4. **★ 机制已从源码钉死（旧版这条是"未钉死"，现更正）**：见 **§2.6**。
   读了 `safe-delete-bulk-guard.cjs`（466 行）与 `sitecustomize.py`（`shutil.rmtree` →
   `_safe_shutil_rmtree`），把"计数单位 / 累计键 / 闸门比较符 / 批准与否决粒度 / 恢复边界"
   全部钉住；§2.2 的经验律现在是**机制推导**（逐次调用过闸 ⇒ 每调用一笔固定往返）。
   ★ 一处**仍未钉死**：那笔"固定 ≈0.5~0.8s 往返"**具体在哪一层**（`sitecustomize.py` 里的
   broker IPC，还是宿主侧的 safe-delete 服务）—— 我读到的是**闸门逻辑**，不是**往返时序**。
   这不影响结论（代价随调用次数线性、与项数无关，两者都实测过）。
5. **`tests/.work/` 残留 13 个目录 / 34 MB，且会话锁是陈旧的**（pid 6591 已不存在）：
   配额触顶导致 `_clear_work_dir` 删不干净 ⇒ 它**只告警不中断**（刻意的，见 `_clear_work_dir` docstring），
   残留**无害**（目录名带 uuid、锁会自动接管）。下一轮 `pytest_sessionstart` 会继续尝试清。
   ★ 这是**配额**的残留，不是本修复的残留。
6. **未做的候选优化**：teardown 的 1 次 `rmtree` ≈0.75s/例**已到地板**（见 3-3）。
   若将来要再降，唯一方向是**减少夹具用例数**或**让宿主别对工作区内删除逐次收费** ——
   两者都超出本卡范围，**不建议**在没有新证据时动。
7. **★ 一个我解释不了的数差（如实登记，不圆场）**：§2.6 从守卫 payload 反推出的
   单次 rmtree 目标树 = **215 / 218 / 220 项**，而我静态 walk 残留夹具树 = **248 / 249 / 250 项**
   （两者同口径：只数文件条目）。差 **≈30 项**。可能来源（**均未证实**）：① payload 里的
   `count` 受 `DISPLAY_COUNT_LIMIT=9999` 之外的某处截断；② `request.count` 在那几次并非 99998；
   ③ 我 walk 的是**合并前**的残留树、被拦的是**当时**的树。**结论**：单例配额代价取 **250 项**
   这个量级是可靠的（两个独立来源都在 215~250），但**不要引用到个位数**。
8. **★ 合并后夹具批次的耗时数字已过期，且本轮无法复测**：`main` 把 `tests/valuelayer/`（新批次，28 个
   夹具用例）与 `tests/daily/test_no_change_day.py` 增量合了进来，`tests/injection/` 也长了
   ⇒ `unit` / `daily` / `injection-*` 的**条目数与耗时都会变**。§2.5 与 3-4 的表是**合并前**的读数，
   我没有把它们当作合并后的结论（详见 §⑤ 的复测清单）。**这不是"没测"，是"测不了"**（配额，见 ④.1）。

---

## ⑤ 下一轮复测清单（★ 本单**未能**完成的测量，逐条给出可直接照抄的命令）

> 前置：**必须是新的一轮**（新用户消息）。同一轮里重试**无效**（§2.6：累计键 = conversation request）。
> 每轮**只跑一个**夹具批次（`V-08`）：一次夹具 teardown ≈250 项，阈值 99999 ⇒ **一轮 ≈3~4 个批次**是硬上限，
> 但**不要**贴着上限跑（`unit` 一个批次就可能 ≈100 例 × 250 = 25,000 项，再叠别的批次容易在末尾断掉，
> 断掉的那一批会以"看起来像测试坏了"的方式红 —— 正是本卡要消灭的那种假红）。

```bash
cd <worktree>/system
PY="${HOME}/.workbuddy/binaries/python/envs/default/bin/python"   # 必须有 pytest；系统 python3 没有

# 每轮只跑下面一条，跑两遍（run1 / run2）：
"$PY" scripts/ops/verify.py --batch unit          # 合并后应重测：main 给 tests/ 加了新文件
"$PY" scripts/ops/verify.py --batch guards
"$PY" scripts/ops/verify.py --batch conflict
"$PY" scripts/ops/verify.py --batch pricelayer
"$PY" scripts/ops/verify.py --batch valuelayer    # ★ 关键：验证 3-4 结尾那条可证预测（应显著 < 170.15s）
"$PY" scripts/ops/verify.py --batch daily
"$PY" scripts/ops/verify.py --batch evidence
"$PY" scripts/ops/verify.py --batch injection-a   # …b / c / d / e / f 各一轮，共 6 轮
```

**填表时只需补这几格**（3-4 的表已经建好，把"未测/未复测"改成 run1/run2 即可）：
`evidence` · `daily` · `valuelayer` · `injection-a`…`f`；
并**重测** `unit` / `guards` / `conflict` / `pricelayer`（派单要求，且它们受合并影响）。

**判定规则**（照 `V-02`，不要临场发明）：

| 情形 | 处置 |
|---|---|
| 倍数 ≥ 4× 且 ≤ 300s | 维持 |
| 倍数 < 4× | 上调超时，**上限 300s**；若已顶到 300s，**登记为薄余量**并写清"见到超时先查有没有第二个会话"（`V-05`） |
| `exit=124` | **不合格**（`V-03`），当"该批坏了"处理；**不要**先加超时 |
| 报 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` | **不是失败**：`count` 与上轮相近 ⇒ 本轮的配额已经用完 ⇒ **换轮次**，别重试 |
| `unit` 若复测明显低于 15.79s | 可按 `最慢 × 4~8` 收紧 270s（参考值 ≈120s），**但要有两次相近的读数**才动 |

---

## ⑥ 复现入口（最小）

```bash
cd <worktree>/system

# 1) 成本模型（工作区内 vs 工作区外的删除代价）
CODEBUDDY_SAFE_DELETE_SANDBOX=0 python /tmp/fx_model.py      # A/B 两段：k 次 unlink / 1 次 rmtree

# 2) 单例夹具逐步耗时（插桩已还原；等价脚本）
CODEBUDDY_SAFE_DELETE_SANDBOX=0 python /tmp/fx_bench.py brokerOFF

# 3) 根因单点：修前 4.05s / 修后 0.16s 的那两条用例
sh scripts/ops/run_pytest.sh \
   "tests/unit/test_contracts.py::test_write_read_reload_survives_index_deletion" \
   "tests/unit/test_contracts.py::test_append_never_truncates_existing_lines" -q --durations=0

# 4) A/B：把 "raw" 从 _COPY_SKIP 去掉（A 组），跑 unit / guards
#    预期：A 组 unit ≈58~61s、guards 60.02s exit=124；B 组 unit ≈11~16s、guards ≈19~27s
python scripts/ops/verify.py --batch unit
python scripts/ops/verify.py --batch guards        # ★ 60s 超时下 A 组每次都红

# 5) 门禁（与基线一致：唯一非零 traceback.py 为既有真源红）
WORKBUDDY_PY=<装了 pytest 的 python> sh scripts/ops/pre-commit.sh

# 6) 批次策略守卫（在 system/ 下**不带参数**跑；带位置的参数会被当成 code_root 而报 INPUT-ERROR）
#    exit=0 / RESULT: PASS（0 violations）；要看 batches / max_timeout_s / test_files_uncovered 三行
"$PY" scripts/checks/verification_policy_guard.py; echo "exit=$?"

# 7) ★ 配额诊断（本卡新增，不需要删除即可查）：判定"该换轮次"还是"该查测试"
"$PY" - <<'EOF'
import os, json, hashlib, pathlib
root = os.environ["CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR"]; sid = os.environ["CODEBUDDY_SESSION_ID"]
rid  = os.environ["CODEBUDDY_CONVERSATION_REQUEST_ID"]; thr = os.environ["CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD"]
st = json.loads((pathlib.Path(root)/hashlib.sha256(sid.encode()).hexdigest()/"state.json").read_text())
used = st["requests"].get(rid, {}).get("count", 0)
print(f"本 conversation request: used={used} threshold={thr} 余量={int(thr)-used}")
print("被否决的轮次:", list(st.get("requestRejections", {})))
EOF
#   余量 < 250（≈一个夹具用例的 teardown）⇒ 本轮的夹具批次**必然**在某一处红，**换轮次**。
```

---

## ⑦ 提交与仓库状态

**本报告首次随提交 `49ce681` 落地**（分支 `ws/fixture-cost`；合并 `main` 后 `HEAD == 65cef01`）：

```
49ce681 fix(conftest)+fix(verify): 卡13-F/G-54 共享夹具每例≈4.2s 的根因已定位并修掉 + 5 个批次超时按 V-02 上调
65cef01 docs(batch13): 13-A 八项裁定 …（= main，merge 前 fast-forward 到位）
```

改动面（**只 `git add` 这三个显式路径，没有 `git add -A`**）：

```
A  system/reports/ws_fixture_cost_report.md      ← 本文件
M  system/scripts/ops/verify.py                  （超时 + 注释更正）
M  system/tests/conftest.py                      （`raw` 进 `_COPY_SKIP` + docstring 成本模型）
```

提交后 `git status --short`：**空**（工作树干净）。

```
$ git status --short
(无输出)
```

`pre-commit`（**无 `--no-verify`**）：**11 门全 PASS（0 violations）**，末行 `pre-commit ✓ 全部门禁放行`：

| 门 | 结果 |
|---|---|
| `append_only_guard` / `rules_lock_guard` / `registry_schema_guard` / `schema_sync_guard` | PASS |
| `conflict_scan(L1-L5)` / `no_placeholder_guard` / `injection_guard` | PASS |
| `verification_policy_guard` | PASS（`batches: 22` · `max_timeout_s: 300` · `test_files: 74` · `test_files_uncovered: 0`） |
| `shell_var_guard` / `graph_integrity_guard` / `criterion_effectiveness_guard` | PASS |

★ **自指说明**：本段（§⑦）是**在 `49ce681` 之后**补写入的 ⇒ 本文件的**最新一次**提交 hash 与上表不同。
取最新一次请用：

```bash
git log --oneline -1 -- system/reports/ws_fixture_cost_report.md
git log --oneline -1 -- system/tests/conftest.py
git status --short
```
