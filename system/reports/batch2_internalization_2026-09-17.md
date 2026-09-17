# 批次 II 收口报告 —— 把会话脚本的机制内化进版本库（2026-09-17）

> **本文回答**：「冷启动端到端那 395 行真源，是怎么来的、现在还依赖不依赖会话里的一次性脚本」。
> **前置**：`implementation_plan_2026-09-17.md` §5 批次 II（`B-3` / `B-4` / `S-3` / `S-5`）。
> **结论一句话**：**依赖已经去掉** —— 188 行研究内容现在由**版本库里的一份清单 + 两个机制模块**
> 完整重建，且重建过程**纠正了 3 个原先潜伏的真缺陷**。

---

## 一、内化掉了什么

| 原 `.workbuddy/seed/*.py`（**不入版本库**，7 个 / 3063 行） | 内化后（版本库内） |
|---|---|
| `seed_sources_claims.py` · `seed_research_structure.py` · `seed_entities.py` · `seed_fundamentals.py` 的**机制部分** | **`scripts/ingest/research_ingest.py`**（机制 + 清单编译器） |
| `seed_repair_and_finish.py` 的**引文指纹修复**段 | 同上 —— 变成**产出即正确**（见 §二-1） |
| `build_views.py` | ⏳ 批次 II 剩余（`S-4`，与 `B-7` 一起做） |
| `build_readable_views.py` | ⏳ 同上 |
| 各脚本里的**研究内容**（来源 / 主张 / 关系 / 基线 / 建议…） | **`raw/inbox/research_manifest_2026-09-17.json`**（188 行 / 17 表，进版本库） |

接线：`scripts/orchestrate/ingest_step.py` 的 STEP 1 **按文件名分派**新增第三类投递物
（`research_manifest_*` → 研究清单编译器），与"常规文本""行情清单"两条通路**互斥**
（同一份文件不得被两条吃）。

---

## 二、内化过程中抓到的 3 个**真缺陷**（都不是"写法不统一"，是会算错的）

### 1. ★★ `quote_hash` 的契约从一开始就写错了（4 份实现全都错）

`quote_provenance_guard` 要求 **`quote_hash == sha256(locator 区间逐字切片)`**
（切片**含原文换行与缩进**）。而会话脚本算的是 `sha256(" ".join(quote.split()))`
—— **归一化后的引文串**，与切片不是同一条内容。

⇒ 那批数据**天生不满足契约**，所以 `seed_repair_and_finish.py` 里才会有整整一段
"引文指纹修复"在事后逐条重算。**那是补丁，不是修复**：
只要还有人从旧路径写数据，同一段修复就必须再跑一次。

**内化后的处置**：`quote_hash` 由 `locator` **派生**，清单**不得**自带；
带了就**重算并比对**，不一致即响亮失败。
⇒ 修复从"事后跑一段脚本"变成"产出即正确"，且**没有第二个地方能算它**。

### 2. ★ `period_bucket` 的年份/季度互换（原脚本的 bug，**已进入真源**）

原 `seed_research_structure.py` 写的是 `y, q = tok[1:].split("-")` ——
把 `q2-2026` 拆成 `y="2", q="2026"` ⇒ 产出 **`CY2Q2026`**（应为 `CY2026Q2`）。

它没被发现，是因为该路径产出的主张**在别处显式写了 `period_bucket`**
（`seed_entities.py` 的 TSMC/AMD 事件），派生值**从未被消费** ⇒ 错值静默存活。

**实测后果**：`facts/claims.jsonl` 现存 **5 行**带 `CY2Q2026`
（`claim-src-amd-q2-2026-pr-{rev,dc-rev}-q2-2026` · `claim-src-tsmc-q2-2026-pr-{rev,gm,node-mix}-q2-2026`）。

**为什么这不是无害的**：`period_bucket` **确实被独立佐证指纹消费** ——
`scripts/evidence/independence.py::claim_group_fingerprint` 读
`impact_capability.{event_type,metric,period_bucket}`（`Ch9 §3.4.7`）。
那 5 行目前**组内彼此一致**（都错成同一种形态），故**尚未**造成错误计数；
但只要再出现一条同一真实期间的**正确**形态，两者就**不再分到一组**
⇒ 同源证据被算成两份独立佐证（正是 `T01` 修的那个错）。
⇒ 登记为 **`gap-claim-period-bucket-swapped`**（潜伏缺陷，非活跃缺陷）。
**未自裁改数据**（追加更正版涉及"独立佐证计数取哪一版"的口径，属待裁定项）。

### 3. ★ 幂等键按主键去重会**丢掉第 2 个版本**

往返验证实测：`facts/drivers.jsonl` **18 行 / 只有 9 个不同 `driver_id`**
（会话的"收口"脚本为补 `financial_link.formula_ref` 把 9 条各**追加了一份**）。

按主键去重 ⇒ 首跑把后 9 行**当重复丢掉** ⇒ 而"补过 `formula_ref` 的"正是后 9 行
⇒ **静默丢掉修正版**；且重跑时"恰好"看起来对（重跑本就该一行不写）——
典型的**首跑就错、重跑隐藏**。

⇒ 幂等键改为 **主键 + 出现序**（清单是有序序列；某主键的第 N 行对应真源里第 N 行）。
首跑写全部、重跑一行不写，**且版本序列完整**。往返实测 `drivers` 恢复为 **+18**。

---

## 三、★ 内化前的四份机制**已经互相漂移**（这是"必须内化"的直接理由）

| 机制 | 原先份数 | 漂移的后果 |
|---|---|---|
| `locator`（引文定位） | 2 份，**各只实现一种归一化** | "某些引文能定位、另一些报 MISS"取决于**是哪段脚本写的** —— 同一缺陷表现不同，最难排查 |
| `period_bucket` | 2 份，**正则不同** | 只有一份认 `q2-2026` / `q2 fy27` 形态 |
| `metric_of` | 2 份（有无 `override` 参数） | 覆盖值 vs 派生值两套口径 |
| `event_type_of` | 2 份，**`_EARNINGS` 元组差 6 个词元** | ★ 同一个 metric（`azure`/`rpo`/`hpc`/`capex`…）在两条路径下拿到**不同 `event_type`** ⇒ 独立佐证**分组不同** ⇒ **影响结论强度且无人会发觉** |
| 行幂等追加 / `recorded_seq` 分配 | 3 份 | 同 §二-3 |

⇒ 内化后**各一份**，且 `TABLES`（表清单 / 顺序 / 主键 / 派生规则）**导出与导入共用**
—— 两个方向**不可能**漂移（本仓最高频的漂移源"清单手工维护"从结构上被消除）。

---

## 四、★ 验收：往返等价（`B-3` 的判据）

命令（只用**版本库里**的东西）：

```bash
V=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python
# ① 导出当前研究内容为清单
$V system/scripts/ingest/research_ingest.py system \
    --export system/raw/inbox/research_manifest_2026-09-17.json --run-date 2026-09-17
# ② 清空**副本**真源（副本建在 system/ **之外**）
# ③ 只用上一步的清单重跑
$V system/scripts/ingest/research_ingest.py <副本>/system \
    --manifest system/raw/inbox/research_manifest_2026-09-17.json
# ④ 逐表逐字段比对
```

**结果**：17 张表 / 188 行**逐一重建**，字段差异只剩三类，**每一类都有明确归属**：

| 差异 | 处数 | 归属 |
|---|---|---|
| `recorded_seq` | — | **机制分配的版本水位**（导出时剥离、导入时重算）。保证的不是逐字相等，而是"**按业务键取 `recorded_seq` 最大者**取到同一行"（`Ch9 §3.4.1` 的用法） |
| `first_seen_at` / `analyzed_at` | 4 | **补全**（`Ch9 §2.2`：system_time 永不未知）。★ 逐表**报出条数**（`R-03`：补全不等于"原本就是这样"） |
| `claims.impact_capability.period_bucket` | 6 | ★ **真源里的错值被派生纠正**（§二-2）——**这是唯一的内容级差异，且方向是"改对"** |

无第四类差异。⇒ 内化后的机制**真的能重建会话产出**。

---

## 五、这次内化**没有**解决的问题（如实登记）

| # | 项 | 说明 |
|---|---|---|
| 1 | **`views` 构建 / 渲染**（`S-4`、`B-7`） | `build_views.py` / `build_readable_views.py` **仍未内化**；`B-7`（`company_pages` 未沿 `supersedes` 链取末节点）**未修**。**这是批次 II 的剩余部分** |
| 2 | `metric` 覆盖值 | 10 行主张的 `metric` 来自会话的**显式覆盖值**（`anthropic-2gw` vs 派生的 `anthropic-2gw-mi450`）。导出器已按"**只导出派生不出来的输入**"带上它，故往返等价；但**约定不统一**（历史数据用覆盖值、未来由 key 派生）⇒ 建议后续新增主张**不再用覆盖** |
| 3 | `gap-claim-period-bucket-swapped` | §二-2。**未改数据**（需裁定"更正版与独立佐证计数"口径） |
| 4 | `B-2`（`dependency_edges` 零写入方） | 未做。批次 I 的四步里只完成了前三步 |
| 5 | 批次 III（`B-9` 提问入口 / `B-10` 事件触发） | 未做 |

---

## 六、新增 / 改动的文件

| 文件 | 变更 |
|---|---|
| `scripts/ingest/research_ingest.py` | **新增**（机制 + 清单编译器；`TABLES` 为表清单唯一真源；导出/导入双向） |
| `scripts/orchestrate/ingest_step.py` | STEP 1 新增第三类投递物分派（`research_manifest_*`） |
| `raw/inbox/research_manifest_2026-09-17.json` | **新增**（188 行 / 17 表研究内容，进版本库） |
| `tests/unit/test_research_ingest.py` | **新增**（47 条：机制 12 组参数 + 元断言 + 往返等价 + 5 条拒错） |

## 七、复现命令

```bash
V=/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python
export CODEBUDDY_SAFE_DELETE_SANDBOX=0 CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0

$V -m pytest system/tests/unit/test_research_ingest.py -q    # 47 passed
$V system/scripts/ops/verify.py --batch unit                 # 242 passed
$V system/scripts/ops/run_all_gates.py --timeout 30           # 非零 0
$V system/scripts/delivery/stage_gate.py system --stage all   # PASS(0)
```
