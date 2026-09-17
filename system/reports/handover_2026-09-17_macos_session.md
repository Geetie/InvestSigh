# 交接与情况说明（2026-09-17 · Windows 会话 → **macOS 接续会话**）

> **给接手者**：本文件是 **macOS 会话**（2026-09-17）读完
> `handover_2026-09-17_windows_session.md` 之后的**收尾记录**。
> Windows 会话把五阶段从 3 BLOCKED 推到**全 PASS**、留下**两条跨平台真债**；
> 本会话把它们**做完**，并修掉 Windows 会话**没有跑到**的 5 条预先存在红。
>
> ★ **时效核对件（`V-11` 规矩 5）**：本文件取样于 **`main@0e89ae0`**（`git rev-parse HEAD` 实测），
> 修改前基线 = 该 SHA。**一切数字都是当时读数**；重读时先跑 §六 的命令重取，不要直接引用。

---

## 一、本次会话的成果（一句话 + 实测读数）

> **Windows 会话遗留的 2 条跨平台真债已做完；全量 20 个验证批次 + 29 道门禁 + 五阶段判据全绿；
> 另修掉 5 条 Windows 会话漏跑而未被发现的预先存在红（其中 4 条同族：清单/夹具手工维护 ⇒ 漂移）。**

| 指标 | 会话开始（`0e89ae0`） | **现在** |
|---|---|---|
| `stage_gate --stage all` | PASS（0 violations） | **PASS（0 violations）** |
| 全部门禁（29 道） | 非零 0 | **非零 0** |
| `verify.py` 全 20 批 | ⚠️ **未在 Windows 上跑过全量** | ✅ **20/20 全绿** |
| 已知红 | 2 条（交接报告列出的两条真债） | **0 条** |
| 实际红（全量跑出来的） | **7 条**（交接只列了 2 条） | **0 条** |

★ **最重要的一句**：Windows 交接报告只登记了 **2** 条未完成项，而**全量跑一遍实测出 7 条红** ——
差额 5 条全部来自「**Windows 上没跑 pytest 批次**」（宿主的删除配额让 pytest 批次在那边极不可靠，
见 `platform_defects_ledger.md §7` 末段）。**"没跑过" ≠ "没问题"**。

---

## 二、两条跨平台真债（交接报告 §四-2 / §四-3）：已完成

### 2.1 `review_return.py` 接线（违反"真接线"底线的孤儿模块）

| 项 | 内容 |
|---|---|
| **根因** | `scripts/review/review_return.py` 的 docstring 逐字声明「★ 真接线（`AC-03`）…消费方 = `scripts/review/record_eval.py`（WS-E）的 `investment_result` 层」，但 `record_eval.py` 里**零调用** ⇒ 本项目**第三次**「有声明、零消费者」事故（前两次 `G-50` / `G-RC-12`） |
| **设计依据** | `10_验收与持续复盘/02_实现方案.md §C.2` 三层表「**投资结果**」行的可测判据 = 「同区间**绝对 / 相对收益可算**」⇒ 该层必经复盘收益计算 |
| **改动** | `scripts/review/record_eval.py`：新增 `LAYER_INVESTMENT_RESULT`（派生自 `schema.models.EvalLayer`，不手抄）+ `review_investment_result()`（**真调用** `compute_review_return()`）+ `_realize_investment_result()`（层分派，非该层返回 `None`）；落 `Task.parent_context["investment_result"] = as_dict()` |
| **不越界** | **不改** `review_return.py`（其 29 例自测保持）；**不改** `stage_gate.py`；**不新增 schema 字段**（`parent_context` 本就是 `dict[str, Any]`） |
| **三层不合并** | 落账的是 `ReviewReturn.as_dict()` 原样序列化 —— `total_return`（绝对）/ `relative_return`（相对）**两个各自独立、各自可追溯**的数值 + `formula_refs`；**不含** `score` / `confidence`（`N10.3-01`） |
| **如实落账** | 口径未冻结（`p10` 全 `tbd`）⇒ `status="blocked_by_caliber"` + `missing=[signal_effective_price, transaction_cost, pre_tax_caliber, review_window]`，两个数值 `None`。**这是合法结果**（源稿红线：不伪造数字），**不抛异常、也不静默跳过** |
| **★ 调用点（交接 §四-2 判据⑤要求）** | `scripts/review/record_eval.py`：<br>· `review_investment_result()` —— 函数体 `return compute_review_return(target_ref, root=root).as_dict()`（真调用在**生产代码**里，不在测试里）<br>· `_realize_investment_result()` —— 层分派<br>· `record_eval()` 的两处 `_build_task(...)` 调用点各传入 `investment_result=_realize_investment_result(layer, target_ref, root)`<br>· `_build_task()` —— 落 `parent_context` |
| **新增测试** | `tests/unit/test_record_eval.py::test_investment_result_layer_is_wired_to_review_return`（三段：① 与**直接调用**逐字段相等的真接线证据；② 不伪造数字 + 不合并成综合分；③ **反向对照**：另两层不落该键 —— `G-05`） |

### 2.2 `closure.py` 跳数截断（交接 §四-3）：**判定为测试夹具缺陷，非代码缺陷**

★ 交接报告写的是「涉及 `scripts/graph/closure.py` 的**跳数截断语义**…需单独排查 `forward_closure` 的截断条件」。
**做了区分实验后判定：`closure.py` 是对的，红的是夹具。**

区分实验（`V-10` 元规矩：因果解释落纸前必须先做区分实验）：

| 构型 | 边 | 从 `a` 出发的 `reached` | `truncated` |
|---|---|---|---|
| **测试原样** | `(a,n1) (b,n2) (c,n3) (d,n4) (e,n5) (f,n6)` | `('n1',)` | **`False`**（走到第 1 跳就没了） |
| 对照 A（真链，字母名） | `a→b→c→d→e→f→g` | `('b','c','d','e','f')` | **`True`** ✅ |
| 对照 B（真链，`n` 编号） | `n0→n1→…→n6` | `('n1'…'n5')` | **`True`** ✅ |

**根因**：夹具写的是 `Edge(n, f"n{i + 1}", ...)` —— 源用字母 `a..f`、目标用 `n{i}`
⇒ **产出 6 条互不相连的边（不是链）**，而 `max_depth=5` 下从 `a` 出发只到 `n1`。
它的 `known_refs={n0..n6}|{a}` 与 docstring 写的「`a→b→c→d→e→f→g`」也**自相矛盾**
⇒ 作者在「字母链」与「`n` 编号」两套命名之间混淆了。

**处置**：**只订正夹具、不改 `closure.py`**（真链下截断语义正确）。
并补 3 条断言以防夹具**再次退化后断言空转**：① 链真的连到第 5 跳（`reached` / `max_reached_depth`）；
② `truncated is True`；③ **反向对照** —— 同一条链在 `max_depth=6`（够走到末端）时**不得**报截断。

**读数**：`verify.py --batch graph` → **47 passed / exit=0**（修前 `1 failed, 46 passed`）。

---

## 三、★ Windows 会话**漏跑**而实际编号在册的 5 条红（本次全部修掉）

这 5 条**都不在** Windows 交接报告的未完成项里 —— 它们只会在 `pytest` 批次里显形，
而 Windows 上跑 pytest 极不可靠。四条同族：**清单 / 夹具被手工维护 ⇒ 与真源漂移**。

| # | 红（批次） | 根因 | 处置 |
|---|---|---|---|
| 1 | `test_verification_policy.py::test_v02_table_missing_row_is_detected`（`guards`） | 提交 `a361585` 的信息写「V-02 反例注入器**改为按批次名定位（不再锚整行字面量）**」，但它**只新增了** `_v02_row_index` / `_delete_v02_row` / `_rewrite_v02_row_cell` 三个 helper，**一个调用点都没改**（`_delete_v02_row` / `_rewrite_v02_row_cell` 调用者为零=死代码）⇒ 该用例仍锚**整行字面量**；而 `#109` 恰好改了那行的「内容」格 ⇒ 反例**自己先崩**，产出**正是它声称修好的那种假红** | 三处反例注入器**接到 helper 上**；表头锚点改用常量 `_V02_HEADER_PREFIX`（单一真源） |
| 2 | `test_rule_key_alignment.py::test_expiry_mechanism_is_a_deterministic_function_of_the_review_date`（`guards`） | 「三张豁免表」的清单被**手抄三份**：`_selfcheck_waivers()` 一份、`_expired_waivers()` 一份、**本用例第三份（且只抄了前两张）**。新增第三张表（`KNOWN_UNCONSUMED_RULE_COLUMNS`）后，测试那份**静默停在两张** ⇒ `assert 30 == 2` 假红 | 收敛为**唯一真源** `rule_key_alignment_guard.waiver_tables()`；测试改为**派生**；并补**元断言**（模块里凡`_Waiver` 注解的表都必须在册）把"漏登第 4 张表"变成机器可查。<br>★ 该函数**必须是函数而非常量**：两条现存用例用 `monkeypatch.setattr(G, "<表名>", …)` 替换表来证伪校验机制，导入期常量会**看不见**替换（实测踩到，两条双双 `DID NOT RAISE`） |
| 3 | `test_gate_set_visibility.py::test_real_tree_still_passes_with_the_new_line`（`guards`） | 该用例用 `assert "阻断" not in text` 做**散文子串匹配**；而 `rule_key_alignment_guard` 的 note 正文里逐字写着「只报 note、**不阻断**」⇒ **解释性文字与被解释输出同形**（`G-62`），假红。该文件 docstring 早已记录这条教训，但只对 `_visibility_line` 应用了 | 改为 **行首词法**判据 `_block_lines()`（`_BLOCK_LINE_HEADS` 三条：`pre-commit ✗ ` / `pre-commit: 有门禁阻断` / `pre-commit: 另有门禁`）；并在 `test_emitted_literals_are_still_in_the_sources` 里加**元断言**（每个行首都必须有对应 `echo "…` 发射语句），防该断言退化 |
| 4 | `test_coverage_verifiable.py::test_acceptance_absent_is_explicit_note`（`daily`） | 用例断言 `ACCEPTANCE_INPUT_ABSENT`，却**没有自己制造"文件不存在"这一条件**，而是依赖"仓库里恰好没有 `registry/acceptance_input_set.yaml`"。Windows 会话把该文件落进仓库后，夹具 `copytree` 连 `registry/` 一起复制 ⇒ 走 `ACCEPTANCE_INPUT_NO_LIST` 分支 ⇒ **永远红**（`G-RC-02` / `G-RC-07` 同族：观测被"仓库恰好有什么"污染） | 用例**显式删除**该文件来声明"缺输入"；**新增**一条独立用例覆盖 `NO_LIST`（该分支此前**零覆盖**）。另更正 `coverage.py` 模块 docstring —— 它只写了 `ABSENT` 一条 note，**把另外三条漏成"未声明"**，现补成四条穷尽清单 |
| 5 | `test_schema_expand.py::test_real_repo_existing_rows_still_validate`（`unit`） | 真源 `facts/baselines.jsonl` 第 3 行带 `version_kind="forecast_revision"`，而 `Baseline` 模型**没有这个字段**（`extra="forbid"` ⇒ 拒）。`Claim` / `Event` / `Recommendation` 三张**版本化**表都已有该字段，**独缺** `Baseline` | 见 §四 |

★ **第 5 条另有一层**：全表扫描确认**整个真源只有这一处**多余键（`baselines` 第 3 行），
不是"模型普遍落后于数据"。

---

## 四、两处**跨平台根治**（Mac 适配相关）

### 4.1 `Baseline.version_kind` —— 补契约，**不**改数据

| 项 | 内容 |
|---|---|
| **证据（`V-11` 举证半径：先量全量再定结论）** | 逐表扫真源的全部多余键 ⇒ 只有 `baselines` 第 3 行多 `version_kind` 一个键；`Baseline` 已有版本链指针 `prev_version_id`（`Ch4 §H.3`）与 `conclusion_version`，**只缺** `version_kind` |
| **为什么是补 schema 而不是改数据** | ① `Baseline` **是版本化表**（主键 = (`company_id`, `version`) + 已有 `prev_version_id`）；② `Ch9 §3.4.2` 把 `version_kind` 定为**追加式版本链的通用标记**（写在**通用机制表**里，未按表限定）；③ 三类事件里「**预测修订** = 系统（我们）改」（`Ch9 §2.3.2`）正是 baseline 追加新版的语义；④ **`append_only_guard` 禁止改既有行** ⇒ 只能补契约、不能改数据 |
| **改动** | `schema/models.py::Baseline` 增 `version_kind: VersionKind | None = None` —— 与另三处**同名同枚举**（不新增枚举/机制），**可选 + 默认 `None`**（承本表 docstring 已订的纪律：契约变更不得让既有行失效）；同步重建 `schema/jsonschema/facts.schema.json` |
| **★ 待需求方确认（如实登记）** | `Ch4 §H.3` 的 JSON 示例块**未列** `version_kind`；本次补字段的依据是 `Ch9 §3.4.2` 的**通用机制声明**（非该节逐字枚举）。若需求方认为 baseline 的版本标记应走别的载体，改动点只有本字段一处 |

### 4.2 `append_records` 钉 `newline="\n"` —— 真源行尾平台无关

| 项 | 内容 |
|---|---|
| **症状（实测，非推测）** | `facts/tasks.jsonl` **6 CRLF + 4 LF = 混合行尾**；`facts/recommendations.jsonl` **2 CRLF + 1 LF = 混合** |
| **根因** | `schema/store.py::append_records` 的写入端 `open(path, "a", encoding="utf-8")` **未钉 `newline`** ⇒ 文本模式默认把 `\n` 翻成 `os.linesep`；Windows 上 = CRLF。而 `system/.gitattributes` 是 `* -text`（字节原样存取）、`rules/` 按内容哈希上锁 ⇒ **写入端必须与平台无关** |
| **为什么只能从写入端根治** | 那两张表是**追加式真源**，既有行**不可回改**（`append_only_guard`）⇒ 已污染的混合行尾**不改**（如实留作伪影），但从**写入端**堵住"继续增长" |
| **改动** | 写入端加 `newline="\n"`（+ 注释说明"这是刻意的，不是冗余"） |
| **测试** | `tests/unit/test_file_lock.py::test_append_records_pins_newline_so_writes_are_platform_independent` —— ★ **必须是源码级（AST）断言**：本仓在 macOS 上跑测试，`os.linesep == "\n"` ⇒ **无论有没有修复，行为断言在 Mac 上恒真**（`G-03`），它永远抓不到这个缺陷；能区分修复前后的只有"写入调用有没有显式钉住 `newline`"本身 |

---

## 五、未做项（**如实登记，不粉饰**）

| # | 项 | 性质 | 建议 |
|---|---|---|---|
| 1 | **已污染的混合行尾**（`tasks.jsonl` / `recommendations.jsonl`） | 既有伪影 | 追加式真源**不可回改** ⇒ 只堵住增长（§4.2），历史行尾**保留现状**。若需求方要求全仓统一 LF，须单独开卡（要动真源，须先裁 `append_only_guard` 的例外通道） |
| 2 | `registry/rules.lock.json`（80 CRLF）/ `derived/derived_values.jsonl`（1 CRLF）/ `scripts/checks/rule_key_alignment_guard.py`（1199 CRLF，**行尾一致、非混合**） | 既有伪影 | 三者**均不影响功能**（全部门禁/测试绿）。`* -text` 是**刻意的**仓库策略（字节稳定），故**不**擅自统一（会造成上千行无功能收益的 diff）。要统一须需求方裁定策略 |
| 3 | `platform_defects_ledger.md §8-3`：平台缺陷"**台账是文档，不是门禁**" | 结构性 | 仍**未建** `platform_guard`。本会话新增的两处跨平台修复（§4）**都带了机器绑定**（§4.1 走真数据回归用例；§4.2 走 AST 源级断言），但台账本身仍是文档 |
| 4 | Windows 侧缺陷 7（`test_gate_set_visibility` 的 MSYS 路径形态） | 仅 Windows | 本会话实测：**Mac 上红的不是那个原因**（是 §三-3 的散文子串），已修。MSYS 路径那条是否仍在 Windows 上红，**未复核**（无 Windows 环境） |
| 5 | `review_return` 接线后，"p10 冻结时"的夹具耦合 | 跨平台、**未来**风险 | 现 `p10` 全 `tbd` ⇒ 走 `blocked_by_caliber` 短路，`_load_recommendation()` 不会被触达。**一旦冻结 `p10`**，夹具（空真源）里那两条 `record_eval("investment_result", …)` 用例会走到"建议不存在"分支 ⇒ `CaliberViolation` **响亮上抛** ⇒ 届时须同步这两条用例。**这是可见的、响亮的变化，不是静默的** |

---

## 六、复现与验证命令（接手者先跑这四条）

```bash
V=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python      # 隔离环境

# ① 权威验证（秒级，不复制测试夹具 —— 优先用这两条）
"$V" system/scripts/ops/run_all_gates.py --timeout 30           # 期望：非零计数 0
"$V" system/scripts/delivery/stage_gate.py system --stage all   # 期望：五阶段全 PASS

# ② rules 锁（合并检出后权限会被翻回 0644 ⇒ 先跑 bootstrap 复原）
"$V" system/scripts/checks/rules_lock_guard.py system           # 期望：PASS
sh system/scripts/ops/bootstrap_worktree.sh                     # 只 chmod 0444 + 自检

# ③ 全量批次（20 批；★ 按片轮流次跑，别指望 --batch all）
"$V" system/scripts/ops/verify.py --list
"$V" system/scripts/ops/verify.py --batch <unit|guards|graph|daily|…>

# ④ 本会话的两个机器绑定
"$V" -c "import sys;sys.path.insert(0,'system');from schema.store import append_records;import ast,inspect,textwrap;\
t=ast.parse(textwrap.dedent(inspect.getsource(append_records)));\
print([kw.value.value for n in ast.walk(t) if isinstance(n,ast.Call) for kw in n.keywords if kw.arg=='newline'])"
# 期望：['\n']
```

**本会话实测读数（`main@0e89ae0` + 未提交改动）**：

| 批次 | 结果 | | 批次 | 结果 |
|---|---|---|---|---|
| `unit` | 164 passed | | `injection-a` | 30 passed |
| `guards` | 145 passed | | `injection-b` | 32 passed |
| `conflict` | 6 passed | | `injection-c` | 31 passed |
| `root` | 8 passed | | `injection-d` | 29 passed |
| `compute` | 102 passed | | `injection-e` | 32 passed |
| `graph` | 47 passed | | `injection-f` | 27 passed |
| `validators` | 21 passed | | `injection-g` | 29 passed |
| `claim` | 24 passed | | `evidence` | 48 passed |
| `decision` | 97 passed | | `daily` | 65 passed |
| `transmit` | 29 passed | | `pricelayer` | 202 passed |
| `valuelayer` | 211 passed | | `gates` / `stage` | exit=0 |
| **合计** | **20/20 全绿** | | | |

---

## 七、方法论收获（供后续复用）

1. **"交接报告的未完成项" ≠ "实际未完成项"**：Windows 会话列了 2 条，全量跑出 7 条。
   差额全在**那边跑不了的 pytest 批次**里。⇒ **拿到交接报告后，第一件事是全量跑一遍**，
   而不是只按清单逐条做（本仓 `V-11` 举证半径的另一面：**结论的"完整性"也要有实测支撑**）。
2. **"提交信息声称的修复"必须回源码核验**：`a361585` 的信息写着"改为按批次名定位"，
   实际只加了三个 helper、调用点一个没改。⇒ 与铁律 1（"只建模块、不接线"=未完成）同族，
   **第四次**（`G-50` / `G-RC-12` / `T-18` / 本次）。**判据：新增的 helper 有没有调用者。**
3. **"清单手工维护"是本仓最高频的漂移源**（`G-RC-02` / `G-RC-07` / conftest `_TRUTH_STEMS` / 本次 §三-1、§三-2、§三-4）：
   凡"同一份清单出现在两处以上"，一定有一处会漏改。⇒ **收敛到一处 + 留一条元断言把"漏登"变红**。
4. **收敛时要注意"可替换性"**：把清单做成**导入期常量**会破坏 `monkeypatch.setattr` 式的用例
   （实测：两条用例双双 `DID NOT RAISE`）⇒ 需在**调用时**读模块全局（用函数，不用常量）。
5. **平台专属缺陷的测试必须选用"能区分"的判据**：在 Mac 上测"不写 CRLF"是**恒真**的
   （`os.linesep == "\n"`）⇒ 只能测**机制**（源码里有没有钉 `newline`），不能测**现象**。
   这是 `G-03`（不得把"无被检对象"当"已验证"）在**跨平台场景**下的形态。
6. **散文子串匹配是假红的高发区**：`"阻断" not in text` 被守卫 note 里的「只报 note、不阻断」打红。
   ⇒ 判"某行为是否发生"一律认**行首词法**，并在元断言里钉住"发射语句还在"
   （本文件 `_LINE_HEAD` 的先例已经这么做了，只是当时没推广到全部断言）。

---

## 八、一句话总结

> Windows 会话留下 2 条真债；本会话把 2 条**做完**（`review_return` 真接线 / `closure` 夹具订正），
> 全量跑出并修掉 **5 条**此前无人知晓的预先存在红（**4 条同族：清单或夹具被手工维护 ⇒ 漂移**），
> 另做 **2 处跨平台根治**（`Baseline.version_kind` 补契约 / `append_records` 钉 LF），
> 并把每一处修复都配上**能区分修复前后的**机器绑定。
> **20/20 批次 + 29 道门禁 + 五阶段判据 + 真实 pre-commit 钩子 —— 全绿。**
