# T-CPL · 文件锁跨平台化（`schema/store.py::_file_lock`）· DoD

> **开工前先写 DoD**（`00_开发Agent开工提示词 §5.1`）。**未写出的标准 = 未满足的标准。**
> 分支：`fix/cross-platform-lock`（从 `main` 起）。代码区：`system/`。
> 锚点：`Ch9 §3.4.2`（追加式真源写入口）· `Ch9 §3.10 J6`（首版单写者 + 文件锁）·
> `CONVENTIONS.md §三 P-05`（热路径不许拖慢）· `§四 R-02`（docstring 只写真做到的事）·
> `§五 G-62`（静默等价态）· `00_开发Agent开工提示词 §七 纪律 9`（单写者 + 文件锁）。

## 0. 一句话

> 让 `schema/store.py::_file_lock` 在 **Windows 与 Unix 上都真上锁**——
> Windows 走 `msvcrt.locking`（**强制锁**），Unix 走 `fcntl.flock`（**建议锁**）；
> 两条分支都必须满足「排他 / 阻塞等待 / 可释放 / 异常路径也释放」，**不得有无操作降级**。

## 1. 背景（为什么不是"改个 import"就完事）

| 事实 | 证据 |
|---|---|
| `fcntl` 是 Unix 专用模块，Windows 无 ⇒ 全仓 `ImportError` | 基线实测：`python -c "import schema.store"` → `ModuleNotFoundError: No module named 'fcntl'`（exit 1） |
| `_file_lock` 是**全仓唯一锁路径**，不只 `store.append_records` 用它 | `scripts/compute/store.py` `from schema.store import _file_lock`（纪律 11 / `G-06` 唯一真源） |
| 已否决方案：写 `fcntl` shim 让 Windows 上退化为无操作 | 需求方（峰宝）拍板：那是 `CONVENTIONS.md §五 G-62`「与成功同形的异常态」 |

## 2. 八条 AC（逐条可测）

| # | AC | 判定方式（可观察结果，不是"我觉得"） |
|---|---|---|
| **AC-01** | **真跑通（unit）** | `python system/scripts/ops/verify.py --batch unit` → **exit 0**，贴原始 stdout |
| **AC-01b** | **真跑通（conflict）** | 同上 `--batch conflict` → **exit 0**，贴原始 stdout |
| **AC-01c** | **真跑通（stage）** | 同上 `--batch stage` → **不再 `ImportError`**，输出真实五阶段判据结论（该批 `exit=1` 是设计预期，纪律 12 阻塞） |
| **AC-02** | **持久化 write-read-reload** | 写入 → 删 `index/` → `rebuild_index` 重建 → 数据仍在（沿用既有断言，本改动不得使其变红） |
| **AC-03** | **真接线** | ① `append_records` 函数体内 `with _file_lock(root, stem)`（AST/文本可核）；② `scripts/compute/store.py::_append_lines` 复用同一锁；③ 调用链可指出：`pipeline/orchestrate` → `append_records` → `_file_lock` |
| **AC-04** | **守卫真拦得住（正向）** | 跨进程排他：子进程持锁期间，父进程**非阻塞**取锁**必然失败**（不是"可能失败"）；反向对照（AC-05） |
| **AC-05** | **错误路径（反向对照，`G-05`）** | ① 持锁者释放后，他人**必然**可取（不永久锁死）；② `append_records` 在持锁期间写入抛异常 → 异常**照常上抛**（不吞）且锁**仍被释放** |
| **AC-06** | **边界** | ① 两条分支各自的语义被**分别**断言（Windows = 强制锁 / Unix = 建议锁，差异如实写进 docstring，`R-02`）；② 未知平台（`os.name` 非 `nt`/`posix`）→ **响亮失败**，不许静默降级；③ 空 `records` → 不取锁、不建文件、返回 0 |
| **AC-07** | **无占位符** | 新增代码无 `pass` / `TODO` / `NotImplementedError` / 假数据；`no_placeholder_guard` 相关批次不因本改动变红 |
| **AC-08** | **设计对齐** | 报告逐条写明对应节号：`Ch9 §3.4.2` / `Ch9 §3.10 J6` / `CONVENTIONS.md` 的 `P-05`·`R-02`·`G-62`·`G-05`·`G-06`·`V-01` |

## 3. 非目标（本轮明确不做）

- ❌ 不改任何业务逻辑；❌ 不重构 `_file_lock` 以外的代码；❌ 不改设计区（`00_*` / `01_`~`11_`）。
- ❌ **只修"Windows 上跑不起来"的兼容性问题**，不做顺手优化。
- ❌ 不引入设计里没有的新依赖。

## 4. 附带项：Windows 兼容性问题登记（逐类：现象原文 + 根因 + 改法 + 修后输出）

> 修完锁层后**逐批实跑**（`unit` / `conflict` / `stage`），把真撞到的逐类登记进本报告 §6。

## 5. 提交纪律

- 一律 `git add system/`；**永不** `git add -A` / `git add .`（`R-05`）。
- 用 `git status` 证明设计区零改动。
- 提交信息用 `git commit -F <文件>`，`-m` 里不写反引号/`$()`（`CONVENTIONS.md V-12` 规矩 5）。

## 6. 实跑登记（边跑边填）

| # | 批次/命令 | 现象原文 | 根因 | 改法 | 修后输出 |
|---|---|---|---|---|---|
| W-1 | `import schema.store` | `ModuleNotFoundError: No module named 'fcntl'`（exit 1） | Windows 无 `fcntl`（Unix 专用） | `store.py` 内按 `os.name` 分支：`nt` → `msvcrt.locking`，`posix` → `fcntl.flock` | 待填 |
