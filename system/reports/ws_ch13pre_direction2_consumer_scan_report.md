# 批次 13-pre 方向 2 —— 「`rules/` 键 → 消费者」三态扫描 · **阶段一交付报告**

> 对象：`system/scripts/checks/rule_key_consumer_scan.py`（新增）
> 用例：`system/tests/guards/test_rule_key_consumer_scan.py`（★ 阶段一 4 例 ⇒ 本轮 8 例，见 §⑧/§⑬）
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

## §③ 三态计数（对象 `e9a009b` @ 阶段一，**纯只读**）

> ⚑ **本节是阶段一的读数，已被 §⑰ 取代**（阶段一之后我修了两处真缺陷 ⇒ 读数按 `口径 9` 移动）。
> 保留原样是为了让"读数为什么动"可逐项归因；**引用数字请用 §⑰ 的表**。

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

### 已登记的漏报源（方向相反：**会让 ③ 偏少** —— ★ 本轮已实测证明它**不等于无害**，见 §⑬/§⑭）

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

## §⑧ 测试证据（★ 阶段一 4 例 ⇒ **本轮 8 例**；新增 4 例见 §⑬/§⑭/§⑰）

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
# 只看向量化的部分（★ 去掉 255 行逐键明细：exact/prefix/text/zero 四类）
… --no-report | /usr/bin/grep -vE '^  scanned (exact|prefix|text|zero)::'
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

---

## §⑫ ★★ 回答主理人的问题 1：**粒度不是"偏好"，两个口径各有独有发现 ⇒ 必须两个都要**

> 我在交付时问的是「③ 里 `metric-sets` 的 11 条叶键 vs `13-G` 已定性的 9 个顶层键，是不是重复劳动」。
> 我把它当成"粒度偏好"去问，**问错了**。做完逐项交叉后，答案是**硬的**：

`13-G`（`ws-ch2-rules`，全仓 `grep` + 逐键定性，`batch13_taskbook.md:431-457`）的 9 个**顶层键**
× 本扫描的 **11 条叶键**，逐项交叉：

| `13-G` 的顶层键（判零消费者） | 本扫描对应的叶键 | 一致？ |
|---|---|---|
| `binding_guard` | `binding_guard.{rule_model_class_mismatch, rule_metric_owner_must_be_own_business, cross_business_reference}` 3 条在 ③ | ✅ 一致（叶粒度更细：`guard`/`entry`/`rollup` 另有消费者） |
| `metric_item_fields` | `metric_item_fields` 在 ③ | ✅ |
| `segment_evidence` | `segment_evidence.{blocks_business_modeling, blocks_financial_link, evidence_field}` 3 条在 ③ | ✅ |
| `conversion_chain_generic_stages` | 同名叶键在 ③ | ✅ |
| `extension_policy` | `extension_policy.{new_model_class_requires_code_change, unregistered_type_action}` 2 条在 ③ | ✅ |
| **`conversion_chain_per_model_class`** | ❌ **本扫描一个都没报**（3 个叶键全被判成"有消费者"） | ❌ **本扫描漏了** |
| **`routing.key`** | ❌ **本扫描没报** | ❌ **本扫描漏了** |
| **`routing.binding_field`** | ❌ **本扫描没报** | ❌ **本扫描漏了** |
| **`routing.metric_owner_field`** | ❌ **本扫描没报** | ❌ **本扫描漏了** |

**反向也有一条**：`financial_link.cross_section_consistency_checker` 是**本扫描发现、`13-G` 没发现**
的零消费者键（真 `grep -rnw` 全仓 **0 处**；`13-G` 的顶层视角把 `financial_link` 归入"有消费者"，
因为同组别的子键有人读）。

⇒ ★★ **结论（可判定，不是意见）**：
1. **顶层口径**（`13-G`）在"深层子键"上盲：`financial_link.cross_section_consistency_checker` 它看不见；
2. **叶键口径**（本扫描）在"通用词叶名 + 前缀推定"上盲：4 个键它看不见；
3. 两个口径的**盲区不重叠** ⇒ **不是重复劳动，是互补**。我原先的"默认按叶键继续"**会让 4 个已定性的
   真缺口从报告里消失** —— 幸好交叉了一次。
4. ★ 我**不再**建议二选一。建议：**`13-G` 那 9 个顶层键 + 那 1 条叶键，作为"地板真值"钉进用例**
   （已做：见 §⑬ 的可执行反例）。

---

## §⑬ ★★ 自抓第二个真缺陷：③ 原来只报一个数，而那个数**对 255 条里只 25 条有强证据**

### 事实

本扫描把"键被判成有消费者"的理由压成了**一个布尔值**（`_covered_by`），于是下面三件判别力**完全不同**
的事在输出里**逐位不可区分**（`G-62`）：

| 证据级 | 形状 | 数（对象 `5fce848`） |
|---|---|---|
| `evidence_ast_exact` | 方向 1 的 AST 精确读到**这条**叶键路径 | **25** |
| `evidence_ast_prefix` | AST 只读到**严格前缀**（通常是整个组）⇒ **推定**子树全消费 | **56** |
| `evidence_text` | 都不中，只靠"键名在语料里词边界出现过一次" | **82** |
| `evidence_none` | 三条都不中 ⇒ 就是 ③（**必然等于**候选数，自证） | **92** |

★ **`evidence_none == zero_consumer_candidates` 是脚本里的自证字段**（`evidence_tier_selfcheck`）——
两根轴本该是"同一条判据的两个出口"，不一致就说明其中一个在说谎。

### 代价（实测，已确证）

被这套宽口径**静默吞掉的 4 个键**，全部由 `13-G` 独立证实为零消费者：

| 键 | 被怎么吞掉的 |
|---|---|
| `metric-sets.yaml::routing.key` | `scripts/valuelayer/_rules.py:220` 的 `doc.get("routing")` ⇒ **前缀推定**覆盖整组 5 个叶键；而 `metric_set_routing()` 写的是 `dict(group)`，**只被 `.get("fallback_metric_set_id")` 用掉一个** |
| `metric-sets.yaml::routing.binding_field` | 同上（前缀推定） |
| `metric-sets.yaml::routing.metric_owner_field` | 同上（前缀推定） |
| `metric-sets.yaml::conversion_chain_per_model_class.{hardware,cloud,software}` | 叶名是**通用词** ⇒ 在 `scripts/**` 里到处"命中"（`cloud`/`software`/`hardware` 就是 `model_class` 名） |

⇒ 于是输出改成**区间**（`G-62` 要求的可区分枚举）：

```
scanned zero_consumer_candidates: 92              # 下界 = 严格判定 = 候选集（硬约束③的口径不变）
scanned zero_candidate_lower_bound: 92
scanned zero_candidate_permissive_bound: 230      # = 92 + 前缀推定 56 + 文本 82
scanned zero_candidate_permissive_permille: 901   # ‰，基数仍是叶键 255
```

★★ **上界不是候选集**（输出里写死了这句话）：它表达的是「凡证据不是『精确读到该路径』的，
都可能其实零消费者」。**只报 92 时**，「92 条都有强证据」与「92 条里只有极少数有强证据」
**输出逐位相同** —— 这正是本轮要修的形态。

### 可执行反例（绊线，已实测会红）

`tests/guards/test_rule_key_consumer_scan.py::test_independently_confirmed_zero_consumers_are_not_given_exact_evidence`

把 `_read_kind` 的前缀分支**伪装成** `exact`（一行注入），用例当场红，且报出**具体键名**：

```
E  AssertionError: metric-sets.yaml::routing.key 被判成「有人**精确读**了这条路径」
   —— 这与 `13-G` 的独立结论**直接矛盾**。★ 两个独立方法矛盾时必须当场爆
1 failed, 7 passed in 5.21s
```

还原后 `8 passed in 5.71s`。★ 这条绑定的**地板真值来自独立方法（`13-G`）**，不是我自己算的两个数
（`V-10` 规则 6：比的是**集合包含关系**，绑定的意图是"两个独立方法不得互相矛盾而不发声"）。

---

## §⑭ ★★ 自指污染：我用来证明"宽口径必要"的那个反例，**是宽口径自己造出来的**

### 事实链（每一步都可复核）

1. 阶段一我在扫描器 docstring 里举例：「`rules/banned_tokens.yaml::decision_scope.exclude_fields`
   由 `scripts/_common.py:209` 读到，但接收者是 `Call` ⇒ AST 看不见它 ⇒ **故必须有文本回退**」。
2. 本轮把本扫描器自己从语料面排除后，`exclude_fields` **掉进了 ③**（真 `grep -rnw` 全仓 0 处，
   排除本文件）。⇒ 它之所以被判成"有消费者"，**唯一原因是本文件的 docstring 提到了它**。
3. 进一步用独立方法核：`decision_scope_config()` 全仓只有 **3 个调用点**
   （`scripts/_common.py:264` / `:277` / `:290`），分别只读
   `include_paths`（`:266`）/ `include_modules`（`:273`）/ `include_call_chain`（`:278`）/
   `exclude_markers`（`:291`）。
   ⇒ **没有任何人读 `exclude_fields`** ⇒ `rules/banned_tokens.yaml::decision_scope.exclude_fields`
   是**真零消费者**（它是 ③ 里**第一条我有独立定案证据的**，见 §⑱ 待裁第 3 件）。

⇒ ★★ 三条教训（已写进代码注释，防止复发）：
- **反例必须来自独立方法**：我拿着宽口径去挑"宽口径必要的证据"，挑出来的必然是宽口径自己的回声
  （**自证循环**）。换成真 `grep` + 读调用点，立刻就分开了。
- **仪器必须与语料隔离**：本文件每加一句"举例说明"，就可能把某个键从 ③ 里**挪走**，
  而输出看不出异常。已加 `SELF_RELPATH` 排除 + **自证**（文件存在却排除次数 ≠ 1 ⇒ `exit 2`）
  + 用例 `test_scanner_excludes_its_own_file_from_the_corpus`。
- **同一个数不等于同一个事实**（`G-62` 家族）：见 §⑰ 的 A/B/C 台账 —— A 与 C 的 ② 都是 11，
  但**理由完全不同**。

---

## §⑮ ★ 试过并**否掉**的判据（负面结果，留痕防后人重复）

想法：证据文件若**成组重述**了同一 rules 文件的键名（`mirror` 计数高），那这个命中大概是"照抄"
而不是"消费"，不算消费者。实测：

| `mirror` 阈值 | ≥1 | ≥2 | ≥3 | ≥5 | ≥8 |
|---|---|---|---|---|---|
| 被标为可疑的文本命中数 | 83 | 50 | 23 | 16 | 3 |

**没有一档能分开"照抄"与"真读"**，根因是**同形**：一个**真读多个键**的消费者
（`scripts/_common.py` 读 `banned_tokens.yaml::decision_scope.*`）与一个**逐字照抄**的夹具
（`tests/valuelayer/_fixtures.py::ROUTING` 重述 `metric-sets.yaml::routing`）
在"提到了几个同名键"这个度量上**无法区分**。
- 取 1：`::version` / `::spec_anchor`（真读）被大量误标；
- 取 8：`financial_link.per_share_metric`、`segment_evidence.*`（真嫌疑）被漏标。

⇒ **不采纳**。「照抄」与「真读」只能由**判别力探针**（改值 ⇒ 是否变红）分开，不能用文本度量近似。

---

## §⑯ ★ 本轮新发现、**未修**的残余缺陷：①/② 的分桶在两条分支上不同源

`scripts/checks/**` 在 **AST** 分支归 **②（门禁）**（`bucket = gate if relpath.startswith("scripts/checks/")`），
但它的**文本**命中会落到 **①（运行时）** —— 因为 `runtime_corpus` 是 `scripts/**` **全域**，
而 `gate_corpus` 不含 `scripts/checks/**`。

⇒ 同一个文件里的同一个键名，**走 AST 与走文本会得到不同的态**（`G-62` 同族）。
⇒ **本卡不修**：它会改动 ①/② 的语义，属于独立一轮（且 ①/② 的边界正是 `13-G` 的
(a)运行时 vs (b)门禁 那条边界，改错会污染那套定性）。

---

## §⑰ ★ 读数台账（`口径 9` + `口径 12`：改了仪器 ⇒ 读数会动，必须逐项归因）

**对象**：worktree `.worktrees/ws-schema-expand`，HEAD `5fce848`（`main` 已并入），纯只读。

| 步 | 代码 | 本文件文本 | 语料含自身 | ①AST | ①文本 | ② | ③ |
|---|---|---|---|---|---|---|---|
| **A** 阶段一（§③） | 旧 | 旧 | 含 | 81 | 72 | 11 | **91** |
| **B** 加了证据分级 | 新 | 新 | 含 | 81 | **75** | **8** | **91** |
| **C** 终态 | 新 | 新 | **排除** | 81 | **71** | 11 | **92** |

**归因（两个变量同变 ⇒ 必须先隔离，再归因）**：
- **A→B 只变了"本文件的文本"**（证据分级代码**不改三态** —— 我给了逻辑等价论证：
  `_covered_by` 只是 `_read_kind(...)[0] != "none"` 的薄封装，真值条件与原实现逐位相同）。
  ⇒ 观测到 **3 个键 ②→①**：`conversion_chain_per_model_class.{hardware,cloud,software}`。
  **这就是自指污染的直接观测**（我在 docstring 里写下这 3 个词 ⇒ 它们立刻在 `scripts/**` "命中"）。
- **B→C 只变了"排除自身"** ⇒ 4 个键离开 ①文本：3 个**回落到 ②**（它们在 `tests/pricelayer/test_valuation.py`
  里本来就有文本命中）、1 个落到 **③**（`banned_tokens.yaml::decision_scope.exclude_fields`）。
- **A 与 C 的 ② 都是 11，但理由不同**：A 是"我还没往 docstring 里写那 3 个词"，
  C 是"我已排除自身"。★ **同一个数 ≠ 同一个事实** —— 直接引用 §③ 的 11 会让读者以为"没动过"。

**终态完整读数**：
```
== rule_key_consumer_scan.py ==
  scanned leaf_keys: 255                  scanned rule_files: 14
  scanned tri_state_sum_check: 255         scanned evidence_tier_sum_check: 255
  scanned consumers_runtime_ast: 81        scanned consumers_runtime_text: 71
  scanned consumers_runtime_total: 152     scanned consumers_gate_test_schema: 11
  scanned zero_consumer_candidates: 92     scanned zero_candidate_permille: 360
  scanned zero_candidate_lower_bound: 92   scanned zero_candidate_permissive_bound: 230
  scanned zero_candidate_permissive_permille: 901
  scanned evidence_ast_exact: 25           scanned evidence_ast_prefix: 56
  scanned evidence_text: 82                scanned evidence_none: 92
  scanned evidence_tier_selfcheck: 1       scanned corpus_self_paths_excluded: 1
  scanned ast_py_files_parsed: 114         scanned runtime_tokens: 5236
  scanned runtime_corpus_files: 118        scanned gate_test_corpus_files: 110
RESULT: PASS（0 violations）
```
★ 逐键明细行 **255 条**（`exact::` 25 + `prefix::` 56 + `text::` 82 + `zero::` 92 = 255 ——
四级互斥穷尽在**明细层**也自证了一次）。

**测试**：`tests/guards` 整目录 **100 passed in 18.96s**（含本文件 8 例）；
本文件单跑 `8 passed in 5.71s`。**零夹具、零删除** ⇒ 与宿主删除配额解耦（未用 E 口径也绿）。

**性能（`V-02`）**：`user` 时间（★ 取 3 次**上沿**，`real` 本机波动 3.8–21.6s，不可用）——
扫描器 **0.82s** vs 方向 1 守卫 **0.75s** ⇒ 同量级（≈1.1×，在噪声内）。

---

## §⑱ 请主理人裁三件（前两件是上轮的，第三件是本轮新出的）

1. **粒度**：已在 §⑫ 用数据回答了 —— **不是二选一，建议两个口径都保留 + 把 `13-G` 的 9+1 条钉成地板真值**
   （后者我已做成可执行反例）。若你要我改成纯顶层重算，说一句。
2. **阶段二（判别力定案）需要窗口**：对候选在 **scratch 副本**上改值/删键 ⇒ 跑门禁 + 相关批次 ⇒
   看是否变红。★ **优先级清单已机读化**：`prefix::` 那 **56** 条是**第一优先级**（结构上可疑：
   "读了整组就把子树全标成已消费"这条推定**已被证实吞掉 3 个键**），`text::` 那 82 条第二。
   **宣布窗口前我不动手**（`V-08` 一轮一批）。
3. **★ 新：`rules/banned_tokens.yaml::decision_scope.exclude_fields` 要不要当"定案"处理？**
   我有**独立于探针**的证据链：真 `grep -rnw` 全仓 **0 处**（排除本文件）+
   `decision_scope_config()` 的 3 个调用点（`_common.py:264/277/290`）只读另外 4 个键
   ⇒ 零消费者。而它声明的语义是"评审标记字段不得进入 `decision/graph` 作用域"
   ⇒ 属于 `G-03` 要求定性的那一类。**它是 ③ 里第一条我有硬证据的** ——
   但**定案与登记格式**（补消费者 / 显式登记"首版不消费"）是你的裁量，我没动 `rules/**`。
