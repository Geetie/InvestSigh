# 批次 13-pre 方向 2 —— 「`rules/` 键 → 消费者」三态扫描 · **阶段一交付报告**

> 对象：`system/scripts/checks/rule_key_consumer_scan.py`（新增）
> 用例：`system/tests/guards/test_rule_key_consumer_scan.py`（4 例）
> 提交：**`e6a0201`**（分支 `ws/ch13-e-benchmark-fields`；基线树 `e9a009b` = `main`，已快进）
> 依据：主理人裁定 `batch13_taskbook.md:947-956`「**先做方向 2**（13-post 随后）+ 四条硬约束」
> 纪律：读数**带树**（口径 9）+ 判词**带对象与 SHA**（口径 10）+ 两变量同变**不归因**（口径 12）。

---

## §① 一句话结论

**阶段一（候选生成器）已交付并自证**；**阶段二的判词不在本卡** —— 因为主理人自己在 `:521-525`
立的 `口径 5` 已裁定：判「某个声明有没有被消费」**必须用「判别力」口径（改值 ⇒ 是否变红）**，
不许拿"有人实现过 / 有测试覆盖 / 名字被人提过"当结论。

⇒ 本卡交付的是一个**只报 note、恒 `exit 0`、未接门禁**的**候选生成器**，
以及它自己抓出来的一个**真缺陷**（§⑤）。

---

## §② 四条硬约束的逐条落实

| # | 硬约束 | 落法 | 机器可核 |
|---|---|---|---|
| ① | 扫描域 = `scripts/**` **全域** | `RUNTIME_DIRS = ("scripts",)`（**118** 文件） | `scanned runtime_corpus_files` / `ast_py_files_parsed` |
| ② | 先出**三态计数 + 分类抽样复核** | 见 §③ / §④ | 三态计数各自独立；抽样 11/11 |
| ③ | 误报未降前**只 note、绝不接门禁** | 恒 `exit 0`；**未注册**进 `GATES`/`pre-commit` | 用例 #3 断言 `exit 0` **且**输出里必须出现「候选 / 判别力 / 不阻断」 |
| ④ | 白名单/比值走 `口径 13` | `zero_candidate_permille`（**千分比整数**，不动 `dict[str,int]` 契约）+ **逐键明细** | 用例 #2 断言「明细条数 = 计数」 |

---

## §③ 三态计数（对象 `e9a009b`，**纯只读**）

```
== rule_key_consumer_scan.py ==
  scanned ast_py_files_parsed: 114        scanned rule_files: 14
  scanned leaf_keys: 255                  scanned tri_state_sum_check: 255   ← 自证互斥且穷尽
  scanned consumers_runtime_ast: 81       scanned consumers_runtime_text: 72
  scanned consumers_runtime_total: 153    scanned consumers_gate_test_schema: 11
  scanned zero_consumer_candidates: 91    scanned zero_candidate_permille: 356
  scanned runtime_corpus_files: 118       scanned gate_test_corpus_files: 110
RESULT: PASS（0 violations）
```

| 态 | 判据 | 数 | 占比 |
|---|---|---|---|
| ① 运行时·AST | 方向 1 解析出的读**覆盖**该叶键路径（等于或为其前缀） | **81** | 31.8% |
| ① 运行时·文本 | 键名在 `scripts/**` 里以**词边界**出现 | **72** | 28.2% |
| ② 门禁·测试·schema | AST 命中 `scripts/checks/**`，或键名在 `tests/ schema/ registry/ config/ views/` 词边界出现 | **11** | 4.3% |
| ③ **零消费者候选** | 前两条都不中 | **91** | 35.7% |

逐文件 ③：`publish 20/26` · `metric-sets 11/30` · `scope 11/15` · `review 9/24` · `baseline 9/25` ·
`notification 8/12` · `data-sources.allowlist 6/10` · `schedule 5/14` · `banned_tokens 3/11` ·
`benchmark 3/12` · `freeze 3/6` · `scenario 3/32` · `valuation-methods 1/28` · `pipeline 0/10`。

★★ **与我第一版自报的 139 不可比**：那一版**只扫 `scripts/checks/`**（域过窄），这一版是 `scripts/**`
**全域**。两个变量同时变 ⇒ **按口径 12 不归因**，只报两个数。

★ **`tri_state_sum_check`** 是**自证字段**：三类之和必须 = 叶键总数。它让"分类漏掉一批键"
（也就是"静默漏检"）**当场可见**，而不是留给人去心算。

---

## §④ 分类抽样复核（硬约束②的下半句）

抽 11 条 ③ 候选，逐条用 `/usr/bin/grep -rn`（★ **不用裸 `grep`**，见 §⑥）在
`scripts tests schema registry config views` 全域搜**键名字面**：

| 键 | 代码区字面出现 |
|---|---|
| `frozen_at` · `render_failure_keeps_old_view` · `short_selling` · `must_surface_degradation` · `cross_business_reference` · `budget_value` · `threshold_n` · `blocks_business_modeling` · `registry_driven` · `metric_item_fields` · `implementation_status` | **0（11/11）** |

⇒ 索引**没有算错**。**但这只是"没人按字面名读过它"**，不等于"真零消费者" —— 见 §⑤ 的残余误报源。

---

## §⑤ 判据：为什么本脚本**不**给结论（`口径 5`）

> **「有人实现了同一件事」≠「这个键有人消费」**……判「某声明是否被消费」，
> **必须用「判别力」口径（改值 ⇒ 是否变红）**，不能把「这个行为已被测试覆盖」当成「键被消费」。
> —— `batch13_taskbook.md:521-525`（出处：`13-G` 实测 `metric-sets.yaml` 9 键：行为有实现、
> 有测试覆盖，但把键删掉或改成矛盾值，**测试照样全绿**）

**两条规矩是不同层次，不矛盾**：

| 层次 | 规矩 | 出处 |
|---|---|---|
| **搜索域** | 找消费者时**必须**覆盖门禁/schema/测试 | `:467-473`（主理人给我的） |
| **判据** | 但「**存在覆盖**」≠「**被消费**」；定案须用**判别力**（改值 ⇒ 是否变红） | `:521-525`（`口径 5`） |

⇒ **本脚本的输出只能是「判别力探针的输入清单」**。定案那一步（scratch 副本改值 ⇒ 跑门禁 +
相关批次 ⇒ 看是否变红）**有删除成本**，须按主理人宣布的窗口单独跑（`V-08` 一轮一批）。
**本脚本一次删除都不做。**

### 已登记的残余误报源（**会让 ③ 偏多 ⇒ 假红**；必须有人看过才能定案）

1. **整组通用消费**：`for k, v in group.items()` / `**group` / 由 `param_ref` 拼出的**动态键**
   —— 叶键名可以**一次都不出现**却被真读到；
2. **跨进程 / 跨语言消费**：被外部命令、`views/**` 前端、运行态产物消费时，键名不在语料面内。

### 已登记的漏报源（方向相反：**会让 ③ 偏少**，属安全方向）

1. AST 分支「**读父即消费子树**」的前缀规则**偏宽** ⇒ 组内某子键真没被读时不会进 ③；
2. 文本命中**不区分语境** ⇒ 注释里提过一次键名就算「有消费者」。

⇒ 两个方向**都写进了输出**（`notes`）。**宁可漏报零消费者，不可假报零消费者** ——
天天误报的门禁一定会被关掉。

---

## §⑥ ★★ 本次由**我自己的用例**抓出的一个真缺陷（已修在源头）

**症状**：单文件跑 ⇒ `4 passed`；跑 `tests/guards` **整目录** ⇒ **2 failed**，
且 `zero_consumer_candidates` 从 **91 塌成 0**（`consumers_gate_test_schema` 从 11 涨到 **102**）。

**根因**：前面用了 `code_root` 夹具的用例在 `tests/.work/<id>/` 留下**整棵 `system/` 树的副本**
⇒ 每一个键名都能在副本里"找到消费者" ⇒ ③ **全场归零**。
**单文件通过 / 整目录失败 = 顺序相关** ⇒ 病根在**语料面**，不在用例。

**为什么这条特别值钱**：本脚本**只报 note、不阻断**；它给出"零消费者 0 条"这种
**完全安静**的假结论时，**没有任何门禁会拦它**。

**修法（两件，都在源头）**：
1. `PRUNE_DIR_NAMES`（`.work` / `__pycache__` / `.pytest_cache` / `.git`）+ `_is_pruned()`
   ⇒ AST 索引与两处语料面**一并剪枝**，并把剪掉的条数记进 `ast_py_files_pruned` /
   `corpus_paths_pruned`（**可见，不静默**）；
2. ★ **自证**：`check()` 里断言「语料面**不得**残留 scratch 路径」，违反即 `ValueError` ⇒ `exit 2`
   —— **没有魔数、精确判定**，把"安静的假结论"变成"响亮的输入异常"。

**验证**：修后单文件 `4 passed`、整目录 `93 passed`。

---

## §⑦ 性能（`V-02` 不许回退）

| 版本 | `user` 时间 | 说明 |
|---|---|---|
| 初版（**逐键正则扫全部语料**） | **7.36s** | 同对象上方向 1 守卫是 `1.19s` ⇒ **我是它的 6 倍** |
| 现版（**单遍 token 索引**） | **0.98s** | **低于**守卫 |

**等价性论证**（这是"图快"与"有理据地快"的分界）：词边界正则
`(?<![A-Za-z0-9_])name(?![A-Za-z0-9_])` **恰好**等价于「`name` 是文本里一段**极大**的
`[A-Za-z0-9_]+` 游程」。⇒ 把语料**只切一遍**得到 token 集合后，命中判定退化成 O(1) 成员测试，
**逐位等价**。
★ **前提**：`name` 自身必须是纯 `[A-Za-z0-9_]+`（实测本仓 **255 个叶键全部**满足）。
**不满足时报输入异常**（`ValueError`），**绝不**静默判「无消费者」（`G-62`）。

**回归**：`tests/guards` 整目录 **44.09s → 15.80s**，`93 passed`。

---

## §⑧ 测试证据（4 例，★ **零夹具、零删除**）

| # | 不变量 | 它证伪什么 |
|---|---|---|
| 1 | 三态**互斥且穷尽**（和 = 叶键数；`tri_state_sum_check` 同值） | 少算的那批键**不在任何一态里** ⇒ 读者以为"都分类过了" |
| 2 | ③ 候选**逐键列出**（明细条数 = 计数） | 计数说有 91 条、明细只有 3 条 ⇒ **无法复核任何一条**；★ **兼语料中毒探测器**（§⑥） |
| 3 | 恒 `exit 0`，且输出必须出现「候选 / 判别力 / 不阻断 / `口径 5`」 | 有人把"候选"读成"已判定"（硬约束③的**机器绑定**） |
| 4 | 根下缺 `rules/` ⇒ `exit 2` | 折叠成 `exit 0` + "零消费者 0 条" = 把「**没查到**」说成「查过且没问题」（`G-03`） |

★ 4 条全部用**真实仓库**、**只读**，**不起 `code_root` 夹具**（零 `copytree` ⇒ 零删除成本）；
第 4 条的"缺 `rules/`"臂用 `system/views`（本就无 `rules/`）⇒ **零新建零删除**、与宿主
批量删除配额**解耦**。

**实测**（★ **E 口径**：`CODEBUDDY_SAFE_DELETE_ENABLED=0`，依据主理人裁定 `:1154`）：
```
tests/guards/test_rule_key_consumer_scan.py ....   4 passed
tests/guards                                    93 passed in 15.80s
pre-commit ✓ 全部门禁放行（14 道，EXIT=0）
```

---

## §⑨ 阶段二（**未做**）：判别力定案

**做法**（`口径 5`）：对 91 条 ③ 候选，在 **scratch 副本**上把该键改成**矛盾值**或**删掉**
⇒ 跑 `pre-commit` + 相关批次 ⇒ **是否变红**。
**变红** ⇒ (a)/(b) 有消费者（**须指名 `文件:行`**）；**不变红** ⇒ (c) 真零消费者 ⇒ 报警（非阻断）。

**前置**：① 需要主理人宣布窗口（`V-08` 一轮一批）；② 有删除成本，本会话配额已越顶
（实测 `count 108656 ≥ threshold 99999`）。

★ 与 `13-G` 的分工**待主理人确认**：`13-G` 已把 `metric-sets.yaml` 的 **9 个顶层键**逐键三分类；
我的 ③ 里 `metric-sets` 有 **11 条**但粒度是**叶键**（`binding.…`）⇒ 顶层 vs 叶是**关键差别**。

---

## §⑩ 复现命令

```bash
cd .worktrees/ws-schema-expand/system
# 扫描（纯只读；★ 恒 exit 0）
$HOME/.workbuddy/binaries/python/envs/default/bin/python scripts/checks/rule_key_consumer_scan.py --no-report
# 只看向量化的部分（去掉 91 行逐键明细）
… --no-report | /usr/bin/grep -vE '^  scanned zero::'
# 用例（★ 需 E 口径：本会话删除配额已越顶）
cd .worktrees/ws-schema-expand
CODEBUDDY_SAFE_DELETE_ENABLED=0 sh system/scripts/ops/run_pytest.sh tests/guards
```

---

## §⑪ 纪律留痕

- 只改**自己的 worktree/分支**；`git add` **逐文件**（未用 `-A`）；提交经 `pre-commit` **全绿**；
  merge `main` 后按 `V-07` 重跑 `bootstrap_worktree.sh`（`rules_lock_guard` PASS）。
- **未改**：`rules/**`、设计区、`run_pytest.sh` / `verify.py`、`GATES` / `pre-commit`。
- ★ **本次未使用裸 `grep`**：所有检索走 `/usr/bin/grep` 或内置 `Grep` 工具 ——
  依据同批次的实测结论（`batch13_taskbook.md:1146-1148`、本卡 R2 报告 §⑦-3）：
  bash 里的裸 `grep` 命中的是 **broker 包装器**，对**反斜杠转义的 BRE 算符族**静默返回
  `0` + `rc=1`，与"诚实零命中"不可区分。
