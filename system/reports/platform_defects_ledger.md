# 平台缺陷台账（Windows 宿主环境）

> **用途**：本仓原生于 **macOS**，2026-09-17 起在 **Windows** 上续作。本文汇总**该环境暴露出的全部缺陷**——
> 它们的共同点是：**症状看起来都像"代码坏了"或"机制正常"，实际都是平台假设**。
>
> **为什么单独立册**（而不是只写在阶段报告里）：阶段报告会过期，而**这些缺陷会在每一次
> 新克隆 / 新会话 / 新工作树上复现**。下一个接手者应当**先读本册**，再判断"是不是环境问题"。
>
> ★ **时效**：取样于 `main` 的 2026-09-17 会话；每条都带**检测法**，重读时先跑检测法再下结论。

---

## 0. 一句话总纲

**六条缺陷里有四条同形态**：**平台假设 ⇒ 机制"静默失效或恒红"，而输出与"真的违规"或"正常"完全同形**（`CONVENTIONS §五 G-62`「静默等价态」）。
⇒ **它们只能靠"真跑 + 交叉印证"发现，读代码看不出来**。这也是为什么本册把"检测法"与"根因"并列——**根因决定修法，检测法决定你是否又在重蹈覆辙**。

---

## 1. `fcntl` —— Unix 专用模块（全仓 ImportError）

| 项 | 内容 |
|---|---|
| **症状** | `pytest` 与 `stage_gate` 全线 `ModuleNotFoundError: No module named 'fcntl'` ⇒ **整条验证链路不可用** |
| **根因** | `system/schema/store.py` 模块级 `import fcntl`（POSIX 专用；Windows 无此模块），用于单写者文件锁（纪律 9） |
| **检测法** | `"$V" -c "import fcntl"`；或直接跑任一 pytest |
| **修法** | 跨平台锁后端：posix → `fcntl.flock`；nt → `msvcrt.locking`（**取锁前必须先 `lseek` 到区间起点**，否则静默锁错位置）；其余平台**抛 `RuntimeError`** |
| **★ 为什么不是 `fcntl` shim** | shim 会让锁在 Windows 上**退化为无操作**，与"没上锁"逐字同形（`G-62`）。本项目铁律「**锁必须有校验方**」不允许无操作降级 |
| **状态** | ✅ 已修（`store.py::_select_lock_backend` / `_acquire_exclusive`） |

## 2. CRLF —— `rules/` 哈希锁恒红

| 项 | 内容 |
|---|---|
| **症状** | `rules_lock_guard` 报 14 条 `内容哈希不符（期望 8af5f31a4009… 实得 c1a31b031a6f…）` ⇒ **所有工作树的 pre-commit 恒红** |
| **根因** | 本机 `core.autocrlf=true` 且仓库**无 `.gitattributes`** ⇒ 检出时全文件转 CRLF；而 `rules/` 按**内容哈希**上锁（纪律 9，0444 + SHA256） |
| **检测法** | `"$V" -c "from pathlib import Path; print(Path('system/rules/banned_tokens.yaml').read_bytes().count(b'\r\n'))"` → 非 0 即中招 |
| **修法** | ① `.gitattributes` 写 `* -text`（不做行尾转换，字节一致）；② `git config core.autocrlf false`；③ **物理删除受跟踪文件后 `git checkout-index -a -f` 重建** |
| **★ 陷阱** | 只跑 `git reset --hard` **不生效** —— git 的 eol 比较会认为"CRLF 工作区 == LF blob"从而**跳过重写**。必须**先物理删除**再重建 |
| **★ 副作用** | 重建后 `git status` 会冒出**数百个假 `M`**（stat 缓存假象）。判据：`git diff HEAD --name-only` 为 0 才是真相 |
| **状态** | ✅ 已修（389 个受跟踪文件 CRLF 残留 0；`rules_lock_guard` PASS） |

## 3. ★★ loose ref 被**静默丢弃** —— 分支 ref 建不出来

| 项 | 内容 |
|---|---|
| **症状** | `git commit` 回显成功、对象与 reflog 都写入，**但分支 ref 不前进** ⇒ 在 worktree 里 `git log` 报 `your current branch does not have any commits yet` |
| **根因** | 宿主沙箱**静默丢弃 `.git/refs/heads/<含斜杠>/` 的写入**（该目录不存在、创建被回滚） |
| **★ 更硬的证据**（2026-09-17 实测） | `git update-ref refs/heads/ws/<name> <sha>` **返回 0，且在同一命令内验证就已经无效**（`rev-parse` 仍回旧值、目录未创建）——**连"同命令内可见"都没有**。这排除了"时序/延迟"假说，确认是**写入被丢弃** |
| **检测法** | `git update-ref refs/heads/ws/probe <main-sha> && git rev-parse --short ws/probe` → 若回旧值 ⇒ 中招 |
| **唯一可靠通路** | **改写 `.git/packed-refs`**（它是**已存在的文件**，覆写能持久）。落盘姿势：`git write-tree` → `git commit-tree <tree> -p <parent> -m <msg>` → 把 `<sha> refs/heads/ws/<name>` 写回 `packed-refs` |
| **★★ 写 packed-refs 的铁律** | **必须用 `write_bytes`，绝不用 `write_text`** —— Python 在 Windows 上会把 `\n` 翻译成 `\r\n`，导致每一行 refname 尾部多一个 `\r` ⇒ git 报 `warning: ignoring ref with broken name refs/heads/xxx?` ⇒ **全仓 ref 一次性失效**（本项目真实发生过，见 §6） |
| **分支名含斜杠是诱因** | `ws/xxx` 需要新建 `refs/heads/ws/` 目录 ⇒ 撞上本缺陷。**不含斜杠的分支名（如 `ws-xxx`）可能不受影响**（未经实测，勿当结论） |
| **状态** | ✅ 已建流程（主控统一落盘）；**根本解法未落实**（需要宿主侧或改用 `ws-xxx` 命名） |

## 4. `rel()` 返回平台原生分隔符 ⇒ **豁免与分桶双重静默失效**

| 项 | 内容 |
|---|---|
| **症状** | `no_placeholder_guard` 对 **已登记豁免**的行（`chain_steps.py:142`）报 `PLACEHOLDER-CN` FATAL ⇒ **每次提交被拒** |
| **根因** | `_common.rel()` 用 `str(path.relative_to(root))`，Windows 上得 `scripts\orchestrate\chain_steps.py`（反斜杠）；而 `config/placeholder_exemptions.yaml` 登记的是正斜杠形式 ⇒ **豁免集合失配** |
| **★ 为什么值得单列** | 该文件里 `_load_exemptions` 与 `_is_exempt` **都做了** `replace("\\","/")` 归一化，**唯独真正做集合匹配的那一处没有** ⇒ 证明「让每个消费方各自 replace」的写法**必然漏掉一两处** |
| **连带缺陷** | `rule_key_consumer_scan.py:265` 的 `relpath.startswith("scripts/checks/")` **在 Windows 上恒为 False** ⇒ 所有模块落进 `runtime` 桶 ⇒ **候选集分桶错误且无任何报错**（`G-62` 静默等价态） |
| **检测法** | `"$V" -c "from scripts._common import rel; from pathlib import Path; print(repr(rel(Path('system/scripts/x.py'), Path('system'))))"` → 含 `\` 即中招 |
| **修法** | **在源头修**：`rel()` 返回 `path.relative_to(root).as_posix()`。**一处修、全局正确** |
| **状态** | ✅ 已修；`rel()` docstring 已写明"本函数保证 POSIX，消费方无需再归一化，且**绝不要在消费方逐处补 replace**" |

## 5. ops 脚本的解释器候选只覆盖 POSIX venv 布局 ⇒ **pre-commit 对每次提交假红**

| 项 | 内容 |
|---|---|
| **症状** | 恢复 `.git/hooks/pre-commit` 后实跑：`scenario_tag_binding_guard` / `rule_key_alignment_guard` 各阻断一次，报 `ModuleNotFoundError: No module named 'yaml'` ⇒ **每一次提交都会被拒** |
| **根因** | `pre-commit.sh` / `bootstrap_worktree.sh` / `run_pytest.sh` 的解释器候选**只列 POSIX 布局** `<venv>/bin/python`；Windows 是 `<venv>/Scripts/python.exe` ⇒ 全部落空 ⇒ 回落 `python3`（宿主 Python，**没装 yaml/pydantic**） |
| **★ 为什么最危险** | **天天误报的门禁一定会被关掉**（`V-07`）⇒ 必然有人 `--no-verify` 绕过 ⇒ **纪律 9 的防线静默失效**。这比"某批测试跑不动"严重得多 |
| **检测法** | `unset WORKBUDDY_PY && sh .git/hooks/pre-commit` → 若出现 `No module named 'yaml'` ⇒ 中招 |
| **修法** | 候选**同时覆盖两种 venv 布局**（`bin/python` + `Scripts/python.exe`，两级 venv 各一对，末位 `python3` 兜底）；**三处必须同一优先级**（否则会出现"钩子用一个解释器、跑测用另一个"的错位） |
| **状态** | ✅ 已修（`4c1727d`）。实测：不设 `WORKBUDDY_PY` 时 `pre-commit ✓ 全部门禁放行` |

## 6. 事故记录：一次由 `write_text` 触发的 `.git` 连锁损坏

| 项 | 内容 |
|---|---|
| **经过** | 宿主回滚 `.git` 内部写入（§3）+ 我用 Python `write_text` 改写 `packed-refs` 时触发 CRLF 翻译 ⇒ `refs/`、`worktrees/`、**近端 loose 对象**连锁损坏 ⇒ `653dfa5` / `2aafc56` / `b027c20` / `7477216` **四个提交对象不可达** |
| **恢复依据** | **工作区内容完好无损** ⇒ 从工作区重建主干、逐个收集并行工作流的改动后汇聚 |
| **已固化的三条纪律** | ① 改 `.git/**` 一律 `write_bytes`，**永不** `write_text`；② **多 agent 并发写 `.git` 是事故放大器** ⇒ git 操作必须**单点（主控）**；③ 每次提交后立刻 `git log` + `git cat-file -e` 验证对象**真实可达**（不能只看回显） |
| **状态** | ✅ 已恢复（数据零丢失） |

---

## 7. 通用于新会话的检查清单（**接手者先跑这四条**）

```bash
export PATH="/usr/bin:/bin:$PATH"                      # 本机 shell PATH 是坏的
V="C:/Users/ghf/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# ① 解释器与依赖齐备？
"$V" -c "import yaml, pydantic, jsonschema, pytest; print('deps OK')"   # §5

# ② rules/ 哈希锁是否因 CRLF 恒红？
"$V" system/scripts/checks/rules_lock_guard.py system                    # §2

# ③ loose ref 是否被丢弃？（含斜杠分支名必测）
git rev-parse --short HEAD && git log --oneline -1                       # §3

# ④ 权威验证（秒级、不复制夹具 —— 优先用这两条，别一上来跑 pytest）
"$V" system/scripts/ops/run_all_gates.py --timeout 30
"$V" system/scripts/delivery/stage_gate.py system --stage all
```

### 关于 `pytest` 批次的额外提醒（非缺陷，但会伪装成缺陷）

宿主对**每一次删除调用**收固定审批往返（`tests/conftest.py` 实测注释：≈0.5~0.8s/次），
而夹具是**每个用例复制一份 `system/`（约 300 项）用完即删**；且**计费在同一轮（turn）内累积**。
⇒ 同一轮内连跑多批会**越跑越慢**（实测单文件 `test_contracts.py` 从数秒涨到 **186s**），
症状**看起来完全像"测试坏了"**（超时、`E` 标记）。
**处置**：需要 pytest 时**新会话/新轮次**，一次只跑一批；定位用单文件。
`V-08` 的教训比文档写的更严格：**不只是"全量"，多个小批次串跑也会累积**。

---

## 8. 建议的后续根治项（**未做，如实登记**）

| # | 项 | 说明 |
|---|---|---|
| 1 | §3 的根本解 | 或让宿主放行 `.git/refs/heads/<含斜杠>/` 写入，或约定**分支名不含斜杠**（`ws-xxx`）。目前靠"主控统一落盘"维持，属**流程补丁而非根治** |
| 2 | CRLF 写入面 | `schema/store.py::append_records` 在 Windows 上以文本模式追加，产出 CRLF（`tasks.jsonl` / `recommendations.jsonl` 已有实例）。**无守卫强制 LF**，属全仓既有伪影 |
| 3 | 平台缺陷的机器强制 | 本册**是文档，不是门禁**。按本项目铁律「声明与实现必须有机器绑定」，上述每条都值得有一个 `platform_guard` 或在 CI 里跑的探针 —— **尚未建** |
