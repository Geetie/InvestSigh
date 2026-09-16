# 批次 12-A 报告：NVIDIA 样本真实信息采集扩容 + 反编造门禁

| 项 | 值 |
|---|---|
| 批次 | 12-A |
| 工作树 | `/Users/gaza/Developer/InvestSigh/.worktrees/ws-real-collect-2`（分支 `ws/real-collect-2`） |
| 代码区 | `system/`（根目录 `00_*`~`11_*` 只读设计区**未触碰**） |
| 采集通道 | `rules/data-sources.allowlist.yaml::websearch_webfetch`（`0444`，**未修改**） |
| 结果 | 来源 **4 → 18**（登记 14 条新来源 + 既有 4 条）· claim **5 → 21**（新增 **16** 条）· 新增守卫 1 个（含正向/反向对照测试 18 条） |

---

## 0. 一句话结论

NVIDIA 样本的真实来源从 4 份扩到 **18 份**（新增 14 条登记来源，对应 14 份新落盘的 `raw/` 抓取物），
新增 **16 条真实 claim**（≥8 条要求）；每条 claim 的 `quote_hash` 都等于其 `locator` 所指
`raw/` 行区间的 `sha256` —— 这条性质由新增的 `quote_provenance_guard.py` **机械强制**，
并配了**正向（不误伤）+ 反向（能拦）双向对照测试**。

**没有编造任何一条数据。** 抓不到的来源（TSMC 三个域名 HTTP 403）**如实记为"直取被拒"**
并改走 allowlist 内的 `webfetch` 通道，落盘物头部如实标 `transport`、**不伪造** `body_sha256`。

---

## 1. 交付物清单

| # | 交付物 | 路径 | 状态 |
|---|---|---|---|
| 1 | 真实抓取器 | `system/scripts/ingest/public_fetcher.py`（新建） | ✅ |
| 2 | 抓取清单（14 条 `FetchSpec` + 1 条 `WebfetchOnlySpec`） | `system/scripts/ingest/fetch_manifest.py`（新建） | ✅ |
| 3 | 来源登记 + 引文级采集 | `system/scripts/ingest/real_collector.py`（修改） | ✅ |
| 4 | 真实抓取物 ×14 | `system/raw/2025-05-28-…` ~ `2026-09-16-…` | ✅ |
| 5 | 来源登记 ×14 行 | `system/facts/sources.jsonl` | ✅ |
| 6 | 真实 claim ×16 条 | `system/facts/claims.jsonl` | ✅ |
| 7 | **反编造守卫** | `system/scripts/checks/quote_provenance_guard.py`（新建） | ✅ |
| 8 | 守卫注册 | `run_all_gates.py::GATES` + `pre-commit.sh` 第 ⑪ 项（**两处**，`G-07` 要求的两处） | ✅ |
| 8b | ~~`tests/guards/test_exit_code_contract.py::GUARDS`~~ | **已按主理人指令撤销**（理由见 §6.2） | ⛔ 撤销 |
| 9 | 正/反向对照测试 | `system/tests/injection/test_quote_provenance.py`（新建，18 条） | ✅ |
| 10 | 本报告 | `system/reports/ws_real_collect_2_report.md` | ✅ |

---

## 2. 逐条 claim 对照表（`claim_id` ↔ URL ↔ raw 落点 ↔ locator ↔ quote）

> 下表 `quote` 一列是**从 `raw/` 文件里逐字切出来的原文**（不是复述）。
> `sha256 复核` 一列是把该切片再算一次 hash 与真源里的 `quote_hash` 比对的**独立复算结果**：
> 21/21 全部 OK。复算脚本见 §7.2。

### 2.1 既有 5 条（本批次**未改动**，仅列出以划清边界）

| 行 | claim_id | locator | 备注 |
|---|---|---|---|
| 1 | `claim-nvidia-newsroom-q4-fy2025-4d13454fd859` | `raw/2025-02-26-nvidia-q4-fy2025-results.txt#L1-L1146` | 既有 |
| 2 | `claim-nvidia-newsroom-q3-fy2025-30d8b9bb6b87` | `raw/2024-11-20-nvidia-q3-fy2025-results.txt#L1-L1089` | 既有 |
| 3 | `claim-inbox-2026-09-10-tsmc-aug2026-revenue.txt` | `raw/2026-09-10-tsmc-aug2026-revenue.txt#L1-L231` | 既有 |
| 4 | `claim-nvidia-newsroom-q4-fy2025-4d13454fd859` | `raw/2025-02-26-nvidia-q4-fy2025-results.txt#L1-L1146` | ★ **与第 1 行 `claim_id` 完全相同（既有重复行）** |
| 5 | `claim-inbox-2026-08-04-amd-q2-2026-results.txt` | `raw/2026-08-04-amd-q2-2026-results.txt#L1-L71` | 既有 |

★ 第 1/4 行重复是**本批次之前就存在**的（`git diff` 只显示 21 行的**追加**，既有 5 行一字未动）。
追加式真源**不可回删**，故此处**如实记录、不掩盖、不修改**。

### 2.2 本批次新增 16 条

| 行 | claim_id | 来源 URL | raw 落点 | locator | quote（逐字） | sha256 复核 |
|---|---|---|---|---|---|---|
| 6 | `claim-nvidia-newsroom-q1-fy2026-6e8c4d485442` | `nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-first-quarter-fiscal-2026` | `2025-05-28-nvidia-q1-fy2026-results.txt` | `#L59-L59` | `Data Center revenue of $39.1 billion, up 10% from Q4 and up 73% from a year ago` | OK |
| 7 | `claim-nvidia-newsroom-q2-fy2026-5c0d9a5c0209` | `…/second-quarter-fiscal-2026` | `2025-08-27-nvidia-q2-fy2026-results.txt` | `#L59-L59` | `Data Center revenue of $41.1 billion, up 5% from Q1 and up 56% from a year ago` | OK |
| 8 | `claim-nvidia-newsroom-q3-fy2026-b4b6290015d2` | `…/third-quarter-fiscal-2026` | `2025-11-19-nvidia-q3-fy2026-results.txt` | `#L60-L60` | `Record Data Center revenue of $51.2 billion, up 25% from Q2 and up 66% from a year ago` | OK |
| 9 | `claim-nvidia-newsroom-q4-fy2026-d5f45e87454c` | `…/fourth-quarter-and-fiscal-2026` | `2026-02-25-nvidia-q4-fy2026-results.txt` | `#L60-L60` | `Record full-year revenue of $215.9 billion, up 65%` | OK |
| 10 | `claim-nvidia-newsroom-q1-fy2027-068b3c9b9ed2` | `…/first-quarter-fiscal-2027` | `2026-05-20-nvidia-q1-fy2027-results.txt` | `#L59-L59` | `Record Data Center revenue of $75.2 billion, up 92% from a year ago` | OK |
| 11 | `claim-nvidia-newsroom-q1-fy2027-830c08c73da9` | 同上 | 同上 | `#L68-L68` | `Under the previous sub-markets, Data Center compute revenue was a record $60.4 billion, up 77% from a year ago and up 18% sequentially. Data Center networking revenue was a record $14.8 billion, up 199% from a year ago and up 35% sequentially.` | OK |
| 12 | `claim-nvidia-newsroom-q2-fy2027-290302aa42bc` | `…/second-quarter-fiscal-2027` | `2026-08-26-nvidia-q2-fy2027-results.txt` | `#L59-L59` | `Data Center revenue of $89.0 billion, up 117% from a year ago` | OK |
| 13 | `claim-sk-hynix-newsroom-hbm4e-96f21f3561e1` | `news.skhynix.com/en/sk-hynix-ships-samples-of-12-layer-next-gen-hbm4e-2/` | `2026-06-18-sk-hynix-hbm4e-samples.txt` | `#L60-L60` | `SK hynix utilizes Advanced MR-MUF1 technology for HBM4E products to achieve a 48GB capacity in a 12-layer stack while ensuring structural stability. In particular, the company has also improved heat resistance by 17 percent, compared to the preceding HBM4, enabling stable operation of memory chips in high-performance computing environments.` | OK |
| 14 | `claim-micron-newsroom-hbm4-bc96147b7516` | `investors.micron.com/news/press-release/2026/Micron-in-High-Volume-Production-of-HBM4-Designed-for-NVIDIA-Vera-Rubin-…-03-16-2026/default.aspx` | `2026-03-16-micron-hbm4-volume-production.txt` | `#L23-L23` | `HBM4 36GB 12H in high-volume production, designed for NVIDIA® Vera Rubin — greater than 2.8 TB/s1 and with 20% better power efficiency2` | OK |
| 15 | `claim-tsmc-ir-monthly-revenue-2026-360aefb23911` | `investor.tsmc.com/english/monthly-revenue/2026`（**webfetch**） | `2026-09-10-tsmc-monthly-revenue-2026.txt` | `#L52-L52` | `514,806 53.3%` | OK |
| 16 | `claim-tsmc-ir-monthly-revenue-2026-f6fcc096cb0b` | 同上 | 同上 | `#L50-L52` | `Aug.` ↵ ↵ `514,806 53.3%` | OK |
| 17 | `claim-xinhua-nvidia-fy2026-27d10bf77315` | `news.cn/world/20260226/8e2d572e6317402aa6b5be64c3a6cefd/c.html` | `2026-02-26-xinhua-nvidia-fy2026-results.txt` | `#L20-L20` | `财报显示，该公司截至2026年1月底的2026财年第四季度营收为681亿美元，较上季度增长20%，较上财年同期增长73%；2026财年营收为2159.4亿美元，较2025财年增长65%；四季度净利润为429.6亿美元，较上财年同期增长94%；全年净利润为1200.76亿美元，较2025财年增长65%。` | OK |
| 18 | `claim-stcn-nvidia-q1-fy2027-a62443aa1fa0` | `stcn.com/article/detail/3919308.html` | `2026-05-20-stcn-nvidia-q1-fy2027.txt` | `#L104-L104` | `英伟达对业务进行了新的划分，此前分为数据中心、游戏、专业视觉、汽车与机器人业务，该季度开始重新划分为数据中心和边缘计算两大业务。按照此前的划分，该季度英伟达数据中心收入达到创纪录的604亿美元，同比增长77%，另有数据中心网络收入148亿美元，同比增长199%。` | OK |
| 19 | `claim-herald-sk-hynix-hbm4-hotchips-8034f8590f` | `biz.heraldcorp.com/article/10849578` | `2026-08-24-herald-sk-hynix-hbm4-hotchips.txt` | `#L46-L46` | `SK hynix officially announced Sunday (local time) that its sixth-generation high bandwidth memory chip, the HBM4, is currently in mass production at the 12-layer configuration, while the 16-layer version has entered the qualification stage.` | OK |
| 20 | `claim-ajupress-cowos-capacity-487412b5656f` | `m.ajupress.com/amp/20260105152112913` | `2026-01-05-ajupress-cowos-bottleneck.txt` | `#L23-L23` | `According to TrendForce, TSMC’s monthly CoWoS capacity grew from roughly 13,000–15,000 wafers at the end of 2023 to 35,000–40,000 wafers by late 2024 that doubled to 75,000–80,000 wafers by the end of 2025. The capacity is expected to expand to 120,000 wafers or more in 2026. Even so, demand continues to outstrip supply.` | OK |
| 21 | `claim-semihub-cowos-capacity-4617badc5ec5` | `semihub.io/en/blog/cowos-guide-4.html` | `2026-09-16-semihub-cowos-supply-war-undated.txt` | `#L255-L255` | `As of late 2025, 75,000–80,000 wafers per month, expanding to 120,000–130,000 per month by the end of 2026 — roughly a 4x increase over 2024. New packaging fabs are ramping across Taiwan: AP5 (Taichung), AP6 (Zhunan), AP7 (Chiayi), and AP8 (Tainan).` | OK |

**覆盖面**（任务要求的四类）：
- 官方一手 IR/newsroom 季度业绩：第 6~12 行（NVIDIA 连续六季，FY2026 Q1~FY2027 Q2）；
- 上游 HBM 厂商官方：第 13 行（SK hynix HBM4E）、第 14 行（Micron HBM4，**点名 NVIDIA Vera Rubin**）；
- 上游代工官方：第 15、16 行（TSMC 月度营收，2026 年 8 月）；
- 主流财经媒体（二手/三手）：第 17~19 行（新华网、证券时报、The Herald）；
- **阶段③ 传导所需的上游产能/瓶颈证据**：第 20、21 行（CoWoS 月产能与扩产节奏）。

★ 关于第 15/16 行：第 15 行（`#L52-L52`）只有两个裸数字 `514,806 53.3%`，
引文本身**不含月份标签**，作为证据**不自洽**（读者无法从引文判断它指哪个月）。
发现后补了第 16 行（`#L50-L52`，含 `Aug.` 行）。两条都已入真源——追加式真源**不可回删**，
故此处如实说明二者关系，并把这个判断写进了 `real_collector.py` 的 `tier_basis`。

---

## 3. 每条来源的 `tier` 与分级依据（`Ch2 §C.1` / `Ch6 §C.1`）

`tier` **不是**按"内容像不像官方"猜的，而是按**发布方是谁**机械判定的。

| # | source_id | 发布方 | tier | 分级依据 |
|---|---|---|---|---|
| 1-6 | `nvidia-newsroom-q1-fy2026` … `-q2-fy2027` | NVIDIA Corporation | `primary` | 发布方 = 公司自家 IR/newsroom，属公司**一手披露**；内容为其自述的季度经营结果 |
| 7 | `sk-hynix-newsroom-hbm4e` | SK hynix Inc. | `primary` | 发布方 = 公司官方 newsroom；内容为其自述的产品规格与送样进度 |
| 8 | `micron-newsroom-hbm4` | Micron Technology, Inc. | `primary` | 发布方 = 公司官方投资者关系新闻稿 |
| 9 | `tsmc-ir-monthly-revenue-2026` | TSMC | `primary` | 发布方 = 公司官方投资者关系网站的月度营收页 |
| 10 | `xinhua-nvidia-fy2026` | 新华网（新华社） | `secondary_tertiary` | 发布方为**第三方媒体**，内容系对公司披露的**转述**，非一手 |
| 11 | `stcn-nvidia-q1-fy2027` | 证券时报（stcn.com） | `secondary_tertiary` | 同上 |
| 12 | `herald-sk-hynix-hbm4-hotchips` | The Herald Business | `secondary_tertiary` | 同上 |
| 13 | `ajupress-cowos-capacity` | Aju Press | `secondary_tertiary` | 同上；且该行是媒体**转述 TrendForce 估算** → `claim_nature=interpretation`（**不**记 fact） |
| 14 | `semihub-cowos-capacity` | SemiHub (semihub.io) | `secondary_tertiary` | 同上；且为行业博客**汇总产能估算** → `interpretation` |

**几条如实标注（不美化）**：

- 第 12 条（The Herald）的 `access_restriction` 里如实写了
  「页面自述为 AI 机器翻译，准确性由发布方声明不作保证」——
  该来源的文本质量有已知缺陷，不因"读起来通顺"就当作可靠。
- 第 13、14 条的 CoWoS 数字**不是任一家公司的自述**，是媒体/博客转述第三方研究机构的**估算**。
  故 `claim_nature` 取 `interpretation`、`claim_form` 取 `citation`，
  **并写进 `tier_basis`**——避免下游把"估算"当"已发生事实"。
- 第 9 条 TSMC 的 `obtainable_content_type` 如实填 `summary`（不是 `full_text`）：
  经 webfetch 拿到的是页面文本的**汇总视图**，不是完整原文。

---

## 4. 未取得的部分（如实列出）

### 4.1 本机 HTTP 直取被 WAF 拒绝（**已实测**，非推测）

| 域名 | 结果 | 实测方式 |
|---|---|---|
| `investor.tsmc.com` | **HTTP 403** | `urllib` 与 `curl`（带完整浏览器请求头）均 403 |
| `pr.tsmc.com` | **HTTP 403** | 同上 |
| `www.tsmc.com` | **HTTP 403** | 同上 |
| `investor.nvidia.com` | **HTTP 403** | 同新闻稿在 `nvidianews.nvidia.com` 上 **200**，故改用后者 |
| `www.news.cn` | **HTTP 403** | 同站点 `/world/...` 路径 200 |
| `biz.chosun.com` | 返回 HTML 但为 **JS 壳**（正文不在 HTML 里） | 已放弃该来源 |

**处置**：TSMC 来源改走 allowlist 内的 `builtin_capability websearch_webfetch`
（`rules/data-sources.allowlist.yaml` 明文许可"公开网页采集（IR / 媒体），尊重登录、付费与访问限制"）。
落盘物头部如实标注：

```
# transport: webfetch
# body_sha256: n/a（本机未取得原始响应体，故无此哈希）
# deposit_note: investor.tsmc.com 对本机 IP 一律 HTTP 403（WAF，实测 urllib/curl 均 403）…
```

**没有伪造** HTTP 直取的元数据：`body_sha256` 明确写 `n/a` 而不是编一个值；
`content_hash` 是**运行期由落盘文件现算**的（不是手填）。

### 4.2 明确**未**采集的东西（以及为什么）

| 项 | 状态 | 原因 |
|---|---|---|
| NVIDIA 10-Q / 10-K 原文 | **未取得** | 需 SEC EDGAR；本批次时间预算内未纳入。**不**用"我知道季报里有…"补 |
| NVIDIA 电话会（earnings call）要点 | **未取得** | 需 transcript 来源。**未**凭记忆补任何一句 CEO/CFO 发言 |
| NVIDIA 官方 blog / 技术公告 | **未取得** | 同上 |
| 更多上游（如 Samsung HBM、Amkor、日月光） | **未取得** | 同上 |
| `2026-09-16-semihub-…` 的发布日 | **未披露** | 页面**确无**发布日 → `occurred_at` 保持 `None`，`raw_name` 标 `undated`，**不**用抓取日冒充 |

★ 这些"未取得"**就是未取得**。任务书写的"宁可少 3 条，不可编 1 条"在此严格执行：
本批次每条 claim 都能指到一份**真的落盘了的**抓取物的**具体行**。

### 4.3 `p09` 检索预算 `tbd` 的处理（如实说明）

`rules/freeze.yaml::p09`（`0444`，未修改）：

```
param: public_data_and_budget
freeze_status: tbd
suggested_value: { budget: tbd }
```

**处理方式**：经 `config.freeze.get_param("p09", root).effective_value` 唯一读口读 `budget`；
读到 `tbd` 时 `public_fetcher.budget_note()` 返回：

```
BUDGET_TBD: p09.budget='tbd'（未冻结，Ch11 §F.1）—— 不设人为上限、不填数字，抓取照常执行
```

即：**不为 `tbd` 编一个数字**（既不填 0 也不填 50），也**不因此阻塞**抓取
（`Ch11 §D.2` impact_note：「预算值 tbd 不阻塞开工」）。
本次实际抓取 **14 个来源**、逐个 1 次 HTTP GET、串行、无重试放大。
★ `tbd` 的含义是"参数未冻结"，**不是**"可以随便填"——故本报告不给出"预算消耗 X/Y"这类
看起来精确、实则无来源的数字。

---

## 5. 反编造守卫 `quote_provenance_guard.py`

### 5.1 它守什么（一句话）

> **每一条 claim 的 `quote_hash` 必须等于其 `locator` 所指 `raw/` 行区间的 `sha256`。**

于是"引文"与"原始物"之间是**内容等价**的机械绑定，而不是"模型说它引了"。

### 5.2 为什么需要它 —— 缺口 `G-B10-05` 的真实形态

`scripts/validators/locator_check.py` 判据 4 **只在 `full_text_read == true` 时**
校验 `quote_hash == sha256(整份原文)`；判据 5 对显式"未披露"哨兵强制 `full_text_read=false`。

而**真实入真源的主张全部是 `full_text_read == false`**（引文级定位只覆盖片段）。
于是出现一个**空档**：

```
locator 覆盖某段 + quote_hash 随便写 + full_text_read=false
    → 既有校验器不发声（它把该行归类为"未主张读过全文"，于是不比 hash）
```

**`full_text_read=false` 的 claim 数量最多、来源最杂，却是唯一没有任何"引文↔原文"机械校验的一类。**

→ 本守卫**只管辖 `full_text_read == false` 那支**（与 `locator_check` 判据 4/5 **互补而非重复**，
满足 `G-06` 唯一真源）：该类**逐条**断言区间绑定；`true` 那支仍归 `locator_check`，
本守卫只**计数**并记 note 声明管辖边界（`G-03`：不把"不归我管"伪装成"我验过了"）。

### 5.3 判据（可判定 + 穷尽 + 二值；`R-06`）

管辖范围 = `full_text_read == false` 的全部 claim。每一步都是确定算法，**没有"可疑/可能/待定"第三态**：

| # | 判据 | 违例码 |
|---|---|---|
| 1 | `locator` 非空 | `QUOTE_LOCATOR_MISSING` |
| 2 | `locator` 形如 `raw/<relpath>#L<a>-L<b>`，**或**为显式"未披露"哨兵 | `QUOTE_LOCATOR_UNRECOGNIZED` |
| 3 | `raw/<relpath>` 落在 `raw/` 内且为常规可读文件 | `QUOTE_LOCATOR_ESCAPE` / `QUOTE_LOCATOR_UNRESOLVABLE` |
| 4 | `1 ≤ a ≤ b ≤ 原文行数` | `QUOTE_LOCATOR_RANGE_OUT_OF_BOUNDS` |
| 5 | `quote_hash` 非空 | `QUOTE_HASH_MISSING` |
| 6 | ★ `sha256(locator 区间文本) == quote_hash` | `QUOTE_PROVENANCE_MISMATCH` |

- **可判定**：6 条判据全部是二值函数，无阈值、无"人工判断"。
- **穷尽**：判据 2 的两支（机械可解析 / 显式未披露）互斥且穷尽，其余一律 `UNRECOGNIZED`（**默认拒绝**，`R-06` ⑤ allowlist 语义）。
- **无关键词/名单式判据**（`R-06` ①）：**不**检查引文里有没有"违规词"、**不**比对来源名单；
  唯一的判据是"这段文字与那份文件的那些行的 sha256 是否相等"。
- **穷尽性是被机器检查的**：`_assert_code_domain_covered()` 在**导入期**断言
  `_resolve_raw_artifact` 的每个可能码都能被收编进 `QUOTE_CODES`（声明的穷尽性不许只是注释）。

**区间文本取法（逐字，含行尾换行）**：

```python
"".join(text.splitlines(keepends=True)[a-1 : b])
```

`a==1 and b==原文行数` 时它**恒等于**原文本身 ⇒ 覆盖全篇的 claim 走同一公式，
退化为 `sha256(整份原文)`（与 `scripts.guard.executor._derive_quote_hash` **同值**）——**同一公式、无第二套语义**。

### 5.4 ★ 本守卫的计算**刻意不复用被验证方的实现**

区间切片在守卫里**独立实现**（`_segment`），**不**复用
`scripts/ingest/real_collector.py::_quote_segment`：若守卫调用被验证方来计算判据，
则"改一行采集代码"就能让**证据与判据同时改变** —— 那是自证同义，不是防护。
**独立实现是判据有效性的前提**，不是重复代码。

（`locator` 的**语法解析**则复用 `locator_check.parse_raw_locator`：那是两个校验器之间的
共享**契约**，不构成"被验证方可以改判据"。）

### 5.5 退出码（`G-01`）

| 码 | 含义 |
|---|---|
| `0` | 放行 |
| `1` | 命中违例（**命中即 fail，禁 warn-only**） |
| `2` | 输入异常：`code_root` 缺失 / **真源 JSONL 缺失** / JSONL 损坏 |

「真源 `facts/claims.jsonl` **缺失**」与「存在但 0 行」是**两件事**（`G-03`）：
前者是结构性违例（`Ch9 §3.3.3`：18 个 JSONL 不得增删改名）→ `exit 2`；
后者真空成立 → 显式 `NO_CLAIMS` note + `exit 0`。

### 5.6 空样本与降级（`R-03` / `G-03`）

- 0 条 claim → `NO_CLAIMS` note + `exit 0`（**真空成立 ≠ 已验证**）；
- 有 claim 走"未披露"支 → **显式计数** `scanned claims_without_locator: N` + 一条
  `CLAIMS_WITHOUT_LOCATOR` note 声明"这些主张**未**经本守卫核验"。

### 5.7 关于 `full_text_read` 的判定口径（顺带收 `G-B10-05`）

本批次新增的 16 条 claim **一律 `full_text_read = false`**。这是一个**机械结论**，不是谦虚：

- `locator_check.py` 判据 4 规定 `full_text_read=true` **仅当**定位覆盖**整份**原文
  **且** `quote_hash == sha256(原文)`；
- 本批次全部采用**引文级**定位（`#L59-L59` 这类），**只覆盖片段** ⇒ 机械取 `false`。

**这个 `false` 的正确读法不是"没读过原文"，而是"未证明读过全文"。**
★ 为什么**不**为了让这个字段变 `true` 而把 locator 改成 `#L1-L<全篇>`：
那等于用"覆盖整份文件"伪装"读过整份文件"——`locator` 会退化成无信息的"我引了这份文件"，
恰好是本次要消灭的那种"反正这一整份文件里有这个数"的证据形态。**宁可如实记 `false`。**

→ 这也正是 `quote_provenance_guard` 存在的理由：`false` 那支此前是**零机械校验**的盲区。
**新增的 16 条 claim 100% 落在这个盲区里，100% 被新守卫逐条覆盖**（见 §7 输出：`claims_checked: 21`、`claims_without_locator: 0`）。

---

## 6. 守卫注册（`G-07`：新守卫必须同时进两处）

| 位置 | 改动 |
|---|---|
| `scripts/ops/run_all_gates.py::GATES` | 追加 `("quote_provenance_guard.py", "scripts/checks/quote_provenance_guard.py", ())` → **25 项** |
| `scripts/ops/pre-commit.sh` | 追加第 **⑫** 项 `run_gate "quote_provenance_guard" …` → **12 道门禁** |

（提交 `03959f1`；`HEAD` 上 `grep quote_provenance` 回读两处**均在**。）

★ 一处**如实申报的张力**：`run_all_gates.py` 里有一行既有注释
「由主理人集成时注册（各 WS 按纪律不得自行改本文件）」。该注释针对**批次 6** 的集成动作。
本批次任务书**明确要求**把新守卫注册进 `run_all_gates.py` 与 `pre-commit.sh`，
且 `CONVENTIONS.md::G-07` 是硬规范——故本批次**做了注册**，并在此显式申报这一冲突，
由主理人复核时裁定。注册是**纯追加一行**，不改动任何既有项。

### 6.2 `tests/guards/test_exit_code_contract.py` 的改动**已撤销**（按主理人指令）

初版曾把 `quote_provenance_guard` 加进该文件的 `GUARDS` 矩阵，
并把 `assert len(GUARDS) == 20` 改成 `21`（该矩阵是**手写清单**，
不改这一行，新守卫就不算子矩阵成员）。

主理人指出：该手写清单本身就是既有缺口 **`G-28`**
（`GUARDS` 手写 20 项，而 `run_all_gates.GATES` 实有 24 项 ⇒ 4 条守卫无退出码契约覆盖），
主理人**正在从根上修它**（让矩阵从 `GATES` **派生**，此后任何新守卫自动被覆盖、
谁都不用再动那个文件）。故：

```
$ git checkout -- system/tests/guards/test_exit_code_contract.py
$ git status --short system/tests/guards/
（无输出 = 干净）
```

**我这一侧因此无法验证那三条退出码契约**（干净树 → `exit 0` 且输出含 `scanned `；
缺 `code_root` → `exit 2`；必报 `scanned` 计数）。`G-28` 合入后
`quote_provenance_guard` 会被自动纳管，请主理人届时复跑确认。

**★ 复跑结果（好消息）：`G-28` 的修复已经在**本分支**里了**（`git log` 可见
`1c35154 fix(guards): 退出码契约矩阵改为从 GATES 派生（根治 G-28）`），
`tests/guards/test_exit_code_contract.py` 现在的 `GUARDS` 是**从 `run_all_gates.GATES` 派生**的，
并有元断言 `assert {s for _, s, _ in GUARDS} == {s for _, s, _ in gates}` 防止派生被削弱。
→ **`quote_provenance_guard` 已自动进入矩阵，我无需再动那个文件。**

矩阵元断言（含我的守卫）已实测通过（**仪器 = 裸 pytest 墙钟（`run_pytest.sh`）= 旁证**；
按 `口径 21`，此类读数**不得**据以给 `Batch.timeout` 定值 —— 见 §8）：

```
$ sh system/scripts/ops/run_pytest.sh tests/guards/test_exit_code_contract.py -q
12 failed, 42 passed in 23.60s
```

★ 12 条失败**全部**是 `test_guard_exits_zero_and_reports_scanned_on_pristine_tree[...]`，
**且包含既有守卫**（`locator_check` / `traceback` / `stage_gate` / `verification_policy_guard` / …），
`code=2` + `[INPUT-ERROR] code_root 不存在: …/tests/.work/_pristine/system` ——
即 **session 级 `pristine_code_root` 夹具目录在中途被删掉了**，
属**并发 pytest 会话**的 `pytest_sessionfinish → _clear_work_dir` 互相清目录
（见 §7.6 的并发写者问题），**不是**任何守卫的缺陷。
★ 我**不**把这次全绿的结果当"契约已验证" —— 它没绿，我如实报。

**所以我改用自建干净副本，直接验这三条契约**（不经共享 session 夹具，故不受并发清目录影响）：

```
$ # 复刻 conftest._reset_truth_source（18 个 JSONL 归零、raw/ 只留 .gitkeep）
$ # 复刻 conftest._lock_rules_perms（rules/** → 0444）
$ cp -R <worktree>/system /tmp/guard-contract-probe/system

########## 契约①：干净树 → 必须 exit 0 且输出含 "scanned " ##########
== quote_provenance_guard.py ==
  scanned claims: 0
  note: NO_CLAIMS: facts/claims.jsonl 为空 —— 无被检对象（真空成立，非'已验证'，G-03）
RESULT: PASS（0 violations）
EXIT=0                                    ← ✅ 且输出含 `scanned claims: 0`

########## 契约②：code_root 不存在 → 必须 exit 2 ##########
[INPUT-ERROR] code_root 不存在: /nonexistent/code_root_for_guard_contract
EXIT=2                                    ← ✅

########## 契约③：真源 JSONL 缺失（结构性违例）→ 必须 exit 2 ##########
[INPUT-ERROR] quote_provenance_guard.py: FileNotFoundError: facts/claims.jsonl 缺失 ——
Ch9 §3.3.3 规定 facts/ 下 18 个 JSONL 不得增删改名，文件缺失即结构性违例（与'存在但 0 行'不同；G-03）
EXIT=2                                    ← ✅
```

★ 三条契约**逐条实测通过**。探针在 `/tmp` 下，用完即删（与仓库无关）。

**另外**：`pre-commit.sh` 的第 ⑫ 道已实测**真的在跑**（不是只写在文件里）：

```
$ sh system/scripts/ops/pre-commit.sh 2>&1 | grep "pre-commit →\|pre-commit ✓"
pre-commit → append_only_guard
…
pre-commit → graph_integrity_guard
pre-commit → criterion_effectiveness_guard
pre-commit → quote_provenance_guard        ← ★ 本批次新守卫真的被执行
pre-commit ✓ 全部门禁放行
```

---

## 7. 实际命令输出与退出码（正向 + 反向）

### 7.1 门禁全量（worktree 真仓库根）

```
$ /Users/gaza/.workbuddy/binaries/python/envs/default/bin/python system/scripts/ops/run_all_gates.py --timeout 30
```

```
════════ 退出码汇总 ════════
  conflict_scan.py                   exit=0        2.53s
  append_only_guard.py               exit=0        0.28s
  rules_lock_guard.py                exit=0        0.35s
  registry_schema_guard.py           exit=0        0.68s
  schema_sync_guard.py               exit=0        0.61s
  assert_gate_input.py               exit=0        0.32s
  freeze_guard.py                    exit=0        0.51s
  launch_guard.py                    exit=0        0.20s
  module_denylist.py                 exit=0        1.83s
  no_signal_day.py                   exit=0        0.26s
  no_placeholder_guard.py            exit=0        3.11s
  neutrality_check.py                exit=0        0.24s
  return_guard.py                    exit=0        0.26s
  anti_padding.py                    exit=0        0.63s
  gap_to_task.py                     exit=0        0.19s
  traceback.py                       exit=1        0.23s     ← 既有 T-10（非本批次）
  pipeline.py                        exit=0        0.23s
  stage_gate.py --stage prep         exit=0        0.59s
  injection_guard.py                 exit=0        0.48s
  verification_policy_guard.py       exit=0        0.44s
  shell_var_guard.py                 exit=0        0.21s
  graph_integrity_guard.py           exit=0        0.58s
  locator_check.py                   exit=0        0.92s     ← 既有校验器：新 claim 全部放行
  quote_provenance_guard.py          exit=0        1.25s     ← 本批次新守卫
  非零计数                               1
EXIT=1
```

`traceback.py` 的 exit=1 **不是**本批次引入的：它报的是
`facts/recommendations.jsonl` 的 `G1-03`（既有 `T-10` 议题），
本批次**未改动** `recommendations.jsonl`（`git diff` 只含 `claims.jsonl` / `sources.jsonl`）。
★ 此处**不**声称"全绿"：1 个非零，归因如实。

**复核复跑**（在同一个 worktree 上再跑一次全门禁，用于确认上表不是一次侥幸）：

```
$ /Users/gaza/.workbuddy/binaries/python/envs/default/bin/python \
      system/scripts/ops/run_all_gates.py --timeout 30
  …
  no_placeholder_guard.py            exit=0        1.34s
  traceback.py                       exit=1        0.20s     ← 仍是既有 T-10
  …
  locator_check.py                   exit=0        0.70s
  quote_provenance_guard.py          exit=0        0.86s     ← 本批次新守卫
  非零计数                               1
EXIT=1
```

★ 两次独立运行结论一致：**本批次相关的每一道门禁 `exit=0`**，
唯一的非零项 `traceback.py` 两次都归因于同一个既有 `T-10` 议题。
★ 复跑里 `no_placeholder_guard.py exit=0` —— 这一条曾是 ①（我的措辞红灯），现已消除。

**守卫在真源上的原样输出**（直接跑，不经门禁包装）：

```
$ python system/scripts/checks/quote_provenance_guard.py <worktree>/system --no-report
== quote_provenance_guard.py ==
  scanned claims: 21
  scanned claims_checked: 21
  scanned claims_delegated_full_text: 0
  scanned claims_without_locator: 0
  note: GOVERNED_SCOPE: 本守卫管辖 full_text_read=false 的 claim（21 条）；full_text_read=true 的 0 条由 locator_check.py 判据 4/5 管辖 —— 不计入本守卫的通过结论（G-03）
RESULT: PASS（0 violations）
EXIT=0
```

`claims_checked: 21` + `claims_without_locator: 0` ⇒ **21 条 claim 一条不落、
全部用判据 6 逐条核过**，没有任何一条借"未披露"逃过核验。

**过程中真实踩到并修掉的一个自造红灯**（如实记录）：
本批次初次跑门禁时 `no_placeholder_guard.py exit=1`，命中的是**我自己新写的**
`real_collector.py` 两处中文词「不留空**占位**」被反占位符规则的字面表命中
（`git show HEAD:… | grep 占位` **无输出**，证明是本批次引入）。
已改为「七个字段无一空缺」——**改的是措辞，不是规则**，未加任何豁免条目。
改后 `no_placeholder_guard.py exit=0`（见上表）。

### 7.2 引文对照的独立复算（只读，21/21 OK）

```
$ python - <<'PY'   # 逐条从 raw/ 重新切片并重算 sha256，与真源 quote_hash 比对
…
PY
```

结果：**21 条 claim 的 `quote_hash` 与"其 locator 所指区间重算的 sha256" 全部相符**（0 MISMATCH）。

### 7.3 守卫正向 / 反向对照（在**副本**上做，真仓库零污染）

★ 探针建在 `system/tests/.work/probe_quote/system/`（复制 `facts/` + `raw/`），
**不是**真仓库的 `facts/`；跑完即 `rm -rf` 删除。

```
=== 探针副本（不是真仓库）: tests/.work/probe_quote/system ===
claims 行数: 21  raw 文件数: 19

########## 正向（A）：真源原样 → 期望 exit 0 ##########
== quote_provenance_guard.py ==
  scanned claims: 21
  scanned claims_checked: 21
  scanned claims_delegated_full_text: 0
  scanned claims_without_locator: 0
  note: GOVERNED_SCOPE: 本守卫管辖 full_text_read=false 的 claim（21 条）；full_text_read=true 的 0 条由 locator_check.py 判据 4/5 管辖 —— 不计入本守卫的通过结论（G-03）
RESULT: PASS（0 violations）
EXIT_A=0

########## 反向（B）：第 1 条 quote_hash 换成凭空指纹 → 必须 exit 1 ##########
  [FATAL] QUOTE_PROVENANCE_MISMATCH @ facts/claims.jsonl:1 — quote_hash 与 locator 所指原文区间（2025-02-26-nvidia-q4-fy2025-results.txt L1-L1146, 共 1146 行）的 sha256 不符 —— 引文与 raw/ 落点不是同一条内容（反编造：该主张不能回溯到已落盘的抓取物）
RESULT: FAIL（1 violations）
EXIT_B=1

########## 反向（C）：第 1 条 locator 指向不存在的 raw/ 文件 → 必须 exit 1 ##########
  [FATAL] QUOTE_LOCATOR_UNRESOLVABLE @ facts/claims.jsonl:1 — raw/ 下无此常规文件: '2099-01-01-never-fetched.txt'
RESULT: FAIL（1 violations）
EXIT_C=1

########## 反向（D）：真源 claims.jsonl 缺失 → 必须 exit 2 ##########
[INPUT-ERROR] quote_provenance_guard.py: FileNotFoundError: facts/claims.jsonl 缺失 —— Ch9 §3.3.3 规定 facts/ 下 18 个 JSONL 不得增删改名，文件缺失即结构性违例（与'存在但 0 行'不同；G-03：不得把'无被检对象'当'已验证'）
EXIT_D=2

########## 复位后复跑（正向对照）：必须回到 exit 0 ##########
RESULT: PASS（0 violations）
EXIT_E=0
```

### 7.4 对照测试（`tests/injection/test_quote_provenance.py`，18 条）

```
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_quote_provenance.py -q
..................                                                       [100%]
18 passed in 266.20s (0:04:26)
EXIT=0
```

★ **仪器标注（`口径 21`）**：此处的 `266.20s` 是**裸 pytest 墙钟（`run_pytest.sh`）= 旁证**，
**不是**门禁口径；**门禁口径**的同片读数是 `verify.py` 的 **`15.37s/90s`**（§13.1）——
两者差 **16 倍**，成因见 §13.3（宿主沙箱下的删除路径）。★ **不得**拿 `266.20s` 去推
"该片该配多少超时"；也**不得**在两者之间做比较（`口径 21` 禁混比）。

**双向对照两半都在**（只证"能拦"不够；把所有输入都拒掉也能"能拦"）：

| 方向 | 用例 |
|---|---|
| **不误伤**（`exit 0`） | `test_quote_hash_of_exact_segment_passes` · `test_full_span_quote_hash_equals_whole_file_hash` · `test_multi_line_segment_passes` · `test_undisclosed_locator_is_allowed_but_counted` · `test_full_text_read_true_is_delegated_not_silently_passed` |
| **能拦**（`exit 1`） | `test_fabricated_quote_hash_is_rejected` · `test_one_byte_change_in_raw_makes_existing_hash_stale` · `test_missing_raw_artifact_is_rejected` · `test_range_out_of_bounds_is_rejected` · `test_unrecognized_locator_is_rejected` · `test_empty_locator_is_rejected` · `test_path_traversal_locator_is_rejected` · `test_empty_quote_hash_is_rejected` |
| **穷尽性** | `test_every_emitted_code_lies_in_declared_domain`（跑遍全部必拦场景，断言输出的每个码都在声明的 `QUOTE_CODES` 域内） |
| **空样本 / 输入异常** | `test_empty_truth_source_passes_with_explicit_note`（`exit 0` + `NO_CLAIMS`）· `test_missing_truth_source_is_input_error`（`exit 2`） |
| **CLI 接线（真子进程）** | `test_cli_exit_code_reaches_shell[同源引文-0]` / `[编造引文-1]` |

★ **灵敏度**：`test_one_byte_change_in_raw_makes_existing_hash_stale` 把
`$1.0 billion` 改成 `$1.1 billion`（行数不变、locator 不变、`quote_hash` 不变），
原本 `exit 0` 的 claim **立刻** `exit 1` —— 证明判据真的在读 `raw/` 内容，
而不是在比对两个常量。

★ `test_every_emitted_code_lies_in_declared_domain` 是**开发中被真实抓到的缺陷**催生的：
守卫初版把 `locator_check._resolve_raw_artifact` 的裸码 `LOCATOR_ESCAPE` /
`LOCATOR_UNRESOLVABLE` **原样透传**出去。门禁行为完全正确（照拦不误），
但"每条判定只落在 `QUOTE_CODES` 里"这句**声明是假的**。
已加 `_namespaced()` 机械收编（`LOCATOR_X` → `QUOTE_LOCATOR_X`）+ 导入期自检。

### 7.5 相关的既有批次（确认未被本批次破坏）

```
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_idempotency_rows.py -q
6 passed in 107.75s
EXIT=0              ← 该文件引用 real_collector.py，本批次改过它 → 复跑确认无回归
```

★ **仪器标注（`口径 21`）**：`107.75s` 为**裸 pytest 墙钟 = 旁证**（`idempotency` 分片不在本单
登记范围，故这里**不存在**门禁口径对照值；如实标注为"仅有旁证一种仪器"）。

★ `tests/guards/test_exit_code_contract.py` 在本批次**最终状态下未被改动**（已撤销，见 §6.2），
故不在此列。撤销前它曾以 `21` 项矩阵跑出 `46 passed`，但那个状态已不存在 ——
**不把已撤销状态的绿灯当作本批次交付的证据**。

★ 如实记录一次**我自造的**假失败：第一次跑 `test_idempotency_rows.py` 出现
`1 failed, 1 error`，报 `FileNotFoundError: …/tests/.work/…/facts/claims.jsonl`。
根因是我在测试**运行中**执行了 `rm -rf system/tests/.work/*`，
把该进程**正在使用的夹具目录**删了。**不是**代码缺陷，复跑即 6 passed（见上）。

★ 另如实记录一次**工具层的静默丢失**：本批次对 `test_exit_code_contract.py` 的两次编辑
第一次报"成功"但复核时**内容未变**（`grep` 无匹配、`len(GUARDS)` 仍为 20）。
重新应用并**立即用 `grep` 复核**后才落盘（20 → 21，用例 44 → 46）。
★ 教训：**"编辑报成功"不等于"磁盘内容变了"**——凡改动都必须用独立手段（`grep` / 复跑）
在**同一步内**回读确认。`AddEdit` 这类工具的成功返回值不能当证据。

### 7.6 ★★ 同一 worktree 存在**并发写者**（本报告的一份重要新发现，必须上报）

**已实测的证据链**（三条独立观测，指向同一结论）：

1. **本报告文件在我不曾创建它时出现**：`system/reports/ws_real_collect_2_report.md`
   在我准备首次写入时已存在（`544` 行 / `35531` 字节，`mtime 20:01`），
   `Write` 工具直接拒绝写入并提示"File has not been read yet" ——
   说明**在我动手之前**已有进程把这份报告写到了盘上。
2. **我撤销的改动被重新应用**：
   ```
   $ git checkout -- system/tests/guards/test_exit_code_contract.py && git status --short system/tests/guards/
   （无输出 = 干净）
   $ git diff --quiet system/tests/guards/test_exit_code_contract.py || echo "★ 又被改了"
   ★ 又被改了
   ```
   即：撤销后数分钟内，该文件**再次**被改成"含 `quote_provenance_guard` 的 21 项矩阵"。
3. **`facts/claims.jsonl` 出现一行"没人报过的新增"**：
   我执行 `real_collector.py` 时输出 `NO_NEW_RECORDS：清单材料均已入库（幂等，无新增）`，
   但同一时刻 `facts/claims.jsonl` 由 **20 行变成 21 行**，新增行的
   `first_seen_at = 2026-09-16T11:53:07Z`、`recorded_seq = 21`。
   我在 `/tmp/rcprobe` 的**副本**上复现了上报逻辑本身（`20→21` 且**打印**
   `created claim(引文级): claim-tsmc-ir-monthly-revenue-2026-f6fcc096cb0b …`），
   证明"报无新增却写入"**不是** `real_collector.py` 的缺陷。
4. **我的两处门禁注册被覆盖、导致提交内容缺项**（本轮最严重的一次）：
   我把 `quote_provenance_guard` 追加进 `run_all_gates.py::GATES` 与 `pre-commit.sh`，
   `git add` 后提交 `fc7c982`；**提交后核对发现两份文件里都没有这行**：

   ```
   $ git show HEAD:system/scripts/ops/pre-commit.sh    | grep -c quote_provenance_guard  → 0
   $ git show HEAD:system/scripts/ops/run_all_gates.py | grep -c quote_provenance_guard  → 0
   ```

   而**工作区**同一时刻却又有了（且被放在 `criterion_effectiveness_guard` 之后、编号 ⑫）。
   解释：并发写者在我 `git add` 之后又写了这两份文件并**重新 `git add`**，
   于是提交取到的是它的版本。→ 已用补提交 `03959f1` 修正，并**在同一个 shell 步内**
   用 `git show HEAD:… | grep` 复核确认两个文件都含该行（输出见 §6.2）。
5. **并发跑 pytest 会互相清掉夹具目录**：一次 `tests/guards/test_exit_code_contract.py`
   运行中，session 级 `pristine_code_root` 目录**中途消失**，导致 **12 条**
   `test_guard_exits_zero_and_reports_scanned_on_pristine_tree[…]`（**含既有守卫**）
   以 `code=2` + `[INPUT-ERROR] code_root 不存在: …/tests/.work/_pristine/system` 失败。
   机制是另一个会话的 `pytest_sessionfinish → _clear_work_dir` 与本会话的
   `pytest_sessionstart` 互清 `.work/`（实测输出见 §6.2）。

**结论（如实说）**：根因**不是**采集代码或守卫代码，而是
**同一 worktree / 同一分支上有一个并发的执行体在写同样的文件**
（很可能是被中断的那次会话仍有一个未终止的实例）。我的应对：

- **不抢**：不试图删除或覆盖对方的产出（那是别人的在途工作）；
- **不掩盖**：把五条观测逐条登记在此，供主理人裁定归属；
- **自己这一步做确定的事**：只 `git add` 我明确产出的路径，
  提交后**立即用 `git show HEAD:<path> | grep` 回读复核**提交内容
  （这一步正是 `fc7c982` 缺项能被发现的原因）。

★ 给主理人的处置建议：确认 `ws-real-collect-2` 是否有两个执行体；
若是，应**只保留一个**再合并 —— 否则同一分支会出现"互相撤销对方的改动"这种
最难排查的冲突形态（本批次的 `test_exit_code_contract.py` 与 `pre-commit.sh`
都已经是这个形态的实例）。

---

## 8. 性能与规范申报（`P-05` / `P-03`）—— **未达标，如实说明**

`CONVENTIONS.md::P-05`：**新守卫单次耗时 < 0.5s**。

★ **按 `口径 21`（两个仪器）**：本节所有读数**必须标明仪器**，且**两个仪器的读数不得混比**。
`给 Batch.timeout 定值的唯一合法仪器是「门禁口径」`；`/usr/bin/time` 与裸 pytest 墙钟
**只能作旁证**。本节**不**用任何读数给任何 `Batch.timeout` 定值（那是 `verify.py` 的登记面）。

**仪器 A = `/usr/bin/time -p` 全进程口径（旁证，含解释器启动与导入链）**

| 命令 | real |
|---|---|
| 空解释器基线 `python -c "pass"` | 0.23 / 0.19 / 0.21 s |
| `quote_provenance_guard.py`（本批次新守卫） | **1.29 / 1.95 / 1.75 s** |
| `locator_check.py`（**既有**校验器，同口径对照） | 1.47 / 1.13 s |

**仪器 B = 门禁口径**（`run_all_gates.py` 自己打印的墙钟，即 `Batch.timeout` 判定所用的那个仪器）

| 出处 | `quote_provenance_guard.py` | `locator_check.py`（既有对照） |
|---|---|---|
| `run_all_gates --timeout 30`（§6.2 第一次） | **1.25s** | 0.92s |
| `run_all_gates --timeout 30`（§6.2 第二次） | **0.86s** | 0.70s |
| `run_all_gates --timeout 30`（§13 合并 `main` 后） | **2.19s** | 2.31s |
| `run_all_gates --timeout 30`（§13 补锁后） | **2.15s** | 2.04s |
| `run_all_gates --timeout 30`（本报告 §8 这版，合并 `main` 后） | **0.76s** | 0.53s |

⇒ **两个仪器下的结论一致**（都**未达标**）：仪器 A 下本守卫 **1.29~1.95s**、仪器 B 下 **0.76~2.19s**，
`0.5s` 在**任一**仪器下都不满足；且既有 `locator_check` 在**同一仪器内**处于**同一量级**
（A：1.13~1.47s；B：0.53~2.31s）⇒ 不是本守卫独有。
★ 如实说清：仪器 A 通常比仪器 B 高约 **1.1~1.7 倍**（A 多算解释器启动 + 导入链），
**故 A 的 1.29s 与 B 的 0.86s 不可直接相减/相除**——这正是 `口径 21` 要防的错。
**不挑对自己有利的那个仪器报**：两个都列。

★ **一条附加实测（对 `口径 21` 本身有用）**：**仪器 B 自身也不稳定** ——
同一个守卫、同一份代码，`run_all_gates` 五次读数落在 **`0.76 / 0.86 / 1.25 / 2.15 / 2.19s`**
（**≈2.9×** 波动，与宿主负载有关；`locator_check` 同族 `0.53~2.31s`）。
⇒ **单次门禁口径读数不足以定值**；给 `Batch.timeout` 定值时宜取**多次读数的上沿**并留余量
（与主理人对 `unit`/`injection-g` 采取"**不确定时取上限**"同构）。
本报告**不**用这些数给任何超时定值（那是 `verify.py` 的登记面）。

**归因**（实测，非推测；下述分解属**仪器 A + `-X importtime`**，是**旁证**、非门禁口径）：

| 组成 | 耗时 | 说明 |
|---|---|---|
| 解释器启动 | ≈0.21s | 与守卫无关的固定成本 |
| `schema.store` → `schema.models` → `pydantic` 导入链 | **≈1.0~1.6s** | `-X importtime` 实测 `schema.store` 累计 2.11s（含 pydantic 1.66s）；**每个读真源的守卫都要付** |
| 本守卫自身的扫描（21 条 claim，热态） | **≈0.23s** | `check()` 在同一进程内预热后计时；**这一项 < 0.5s** |

- 该导入链由 `schema.store.read_records` / `truth_source_status` 触发（`G-06` 要求走唯一真源，
  不能自建第二条 JSONL 解析路径来绕开它）；
- **既有的 `locator_check.py` 处于同一量级**（1.13~1.47s），并非本守卫独有；
- 该导入是**惰性**的（在 `check()` 内，不在模块级），故 `P-03`
  「守卫不得在模块级急切导入 pydantic」**满足**——`-X importtime` 里 pydantic 出现在
  **执行期**而非 `import` 语句期。

★ 本报告**不**声称满足 `P-05`。若主理人认为该门槛必须硬达标，
可行方向是"把 `schema.store` 的模型校验做成可选/延迟到真正需要时"——
但那会改动**既有共享模块**，影响面超出本批次，需单独立项。

---

## 9. 纪律自查

| 项 | 结果 |
|---|---|
| 只改 `system/`；根目录 `00_*`~`11_*` 只读区 | ✅ 未触碰 |
| `rules/data-sources.allowlist.yaml`（`0444`） | ✅ **未修改**（`git status` 无该文件） |
| `rules/freeze.yaml`（`0444`） | ✅ **未修改** |
| 禁止 `git add -A` / `git add .` | ✅ 逐文件 `git add` |
| 不从真仓库 `facts/` 做实验 | ✅ 探针在 `tests/.work/probe_quote/` 副本上跑，跑完删除 |
| 自己的 worktree、不切分支 | ✅ 全程在 `.worktrees/ws-real-collect-2`（分支 `ws/real-collect-2`） |
| 真仓库零污染 | ✅ 见 §10 |
| 唯一写入口 `schema.store.append_records` | ✅ 全部 append 均经该入口 |
| 一次只跑一个测试目录（`G-RC-08`） | ✅ 未跨目录混跑 |

---

## 10. 真仓库零污染证明

```
$ cd /Users/gaza/Developer/InvestSigh && git status --short
 M system/reports/phase1_gap_register.md
 M system/tests/conftest.py
?? system/tests/.audit-b11/
?? system/tests/guards/test_session_lock.py

$ git diff --stat -- system/facts/
（无输出 = 真仓库 facts/ 一行未动）
```

**这 4 项没有一项是本批次的**：

| 项 | 归属（旁证） |
|---|---|
| `M system/reports/phase1_gap_register.md` | 主理人的缺口台账（本批次从未打开该文件） |
| `M system/tests/conftest.py` | 主理人正在改的测试基础设施（本批次**刻意未动**，见 §12.3） |
| `?? system/tests/.audit-b11/` | `auditor-batch11` 的工作产物 |
| `?? system/tests/guards/test_session_lock.py` | 主理人新建的"会话互斥"守卫 —— 恰好对应本批次 §7.6 报的并发写者问题 |

真仓库 `system/facts/` **零改动**（`git diff --stat` 无输出）、
`system/raw/` 无新增文件、`system/scripts/` 无改动。
→ **本批次的全部交付物都只在 `.worktrees/ws-real-collect-2/` 内（已提交，见 §10.1）。**

### 10.1 提交记录（worktree 分支 `ws/real-collect-2`）

```
$ git log --oneline -3
03959f1 fix(12-A): 把 quote_provenance_guard 注册进 run_all_gates.py 与 pre-commit.sh
fc7c982 feat(12-A): NVIDIA 样本真实采集扩容 + 反编造引文溯源守卫
1c35154 fix(guards): 退出码契约矩阵改为从 GATES 派生（根治 G-28）；登记 G-RC-10 夹具非确定性

$ git rev-list --count main..HEAD
2                      ← 本批次贡献 fc7c982 + 03959f1（1c35154 是主理人的 G-28 修复）
$ git status --short
（无输出 = 工作区干净，全部已提交）
```

★ 为什么是**两个**提交：`fc7c982` 提交后回读发现两处门禁注册被并发写者覆盖而缺失，
故补 `03959f1`（详见 §7.6 观测 ④）。**没有**用 `--amend` 改写已存在的提交。

worktree 内的改动（`git status --short`，worktree 根）：

```
 M system/facts/claims.jsonl          ← 追加 16 行
 M system/facts/sources.jsonl         ← 追加 14 行
 M system/scripts/ingest/real_collector.py
 M system/scripts/ops/pre-commit.sh
 M system/scripts/ops/run_all_gates.py
?? system/raw/*.txt ×14
?? system/scripts/checks/quote_provenance_guard.py
?? system/scripts/ingest/fetch_manifest.py
?? system/scripts/ingest/public_fetcher.py
?? system/tests/injection/test_quote_provenance.py
?? system/reports/ws_real_collect_2_report.md
```

★ `system/tests/guards/test_exit_code_contract.py` **不在**上表中 —— 它已按主理人指令撤销
（见 §6.2）。提交前会**最后一次**复核它仍是干净的（因为存在并发写者，见 §7.6）。

★ `facts/claims.jsonl` / `facts/sources.jsonl` 的改动是**纯追加**
（`git diff --stat` 为新增行；追加式不可变由 `append_only_guard.py` 逐行验证，`exit 0`）。

---

## 11. 遗留与建议（不掩盖）

| # | 事项 | 建议 |
|---|---|---|
| 1 | `claim-nvidia-newsroom-q4-fy2025-4d13454fd859` 在真源里**重复两行**（既有，非本批次） | 追加式真源不可回删；建议后续批次评估是否需要"去重边"机制或至少一个只读的重复检测器 |
| 2 | `P-05` 的 0.5s 对**所有读真源的守卫**都不达标（含既有 `locator_check`） | 建议把 `P-05` 的口径改为"**守卫自身扫描耗时** < 0.5s（不含解释器与共享依赖导入）"，或单独立项解耦 `schema.store` 的 pydantic 导入。★ **事后：主理人已把本项并入 `口径 21`（两个仪器）** —— 需在同一仪器内陈述，且**两个仪器的读数都不达标**（见 §8） |
| 3 | 第 15 行 TSMC claim（`#L52-L52`）引文不含月份标签，信息量不足 | 已补第 16 行（`#L50-L52`）；旧行不可回删，建议下游消费方**优先使用第 16 行** |
| 4 | The Herald 页面自述为 AI 机翻 | 已在 `access_restriction` 标注；若该来源要用于决策，建议换更可靠来源 |
| 5 | `run_all_gates.py` 的"各 WS 不得自行改本文件"注释 vs 本批次被要求注册新守卫 | 已在 §6 申报，请主理人裁定口径（是否统一为"新守卫注册由交付方做、主理人只复核） |
| 6 | 未取得：10-Q/10-K、电话会 transcript、NVIDIA blog、Samsung/Amkor 等 | **未编造**；建议后续批次按同一"落盘 + 逐字引文 + 守卫"流程补齐 |
| 7 | ★ **`raw/` 数据量增长会增大 `code_root` 夹具命中宿主 safe-delete 配额的概率**（见 §12） | ★ 收到 `G-60` 后**已更正定位**：把 `"raw"` 加进 `conftest._COPY_SKIP` 只是**边际优化**（每例约 600 项删除里的 18 项 ≈ 3%）；`G-60` 的解是**把 `_clear_work_dir()` / 夹具 teardown 改成逐文件删除**（`ws-ch2-rules` 方向）。两者可同时做，但前者**不解决问题** |
| 8 | ★ **同一 worktree 有并发写者**（见 §7.6） | 建议确认并只保留一个执行体后再合并。★ **事后：主理人已判为真问题并并入卡 13-M**（"**不并发跑批**"为 13-M 硬要求之一），**不单独立卡**（避免同一机制两张卡） |
| 9 | ★ **`traceback.py` 在 main 上就红**（`facts/recommendations.jsonl::rec-nvda-001` 缺 `assumptions` + `computation`） | ★ **事后：主理人已立卡并指派 owner**（真实采集/决策线，接"第一个真实建议底稿"），**不归本批次**。证据（守卫与输入与 `main` **逐字节相同**、`git log` 指向批次 8 的 `08eddd3`）已采纳 |
| 10 | `verify.py` 分片数 **6↔7 文档滞后**（`INJECTION_SHARDS` 实为 7 项，正文 8 处仍写「6 片/六片」，§29 枚举上界只到 `injection-f`） | ★ **事后：主理人已立卡 13-N**（归 `ws-ch4-valuelayer`）。**我未改动** |
| 11 | ★ **本报告的时间读数是否都标了仪器**（`口径 21`）/ 退出码是否都不经管道（`口径 22`） | ✅ **已自查并补齐**：§8 列出**仪器 A（`/usr/bin/time -p`，旁证）与仪器 B（门禁口径）** 两套读数并声明**不得混比**；§7.4 / §7.5 / §6.2 / §12.5 的裸 pytest 墙钟均就地标注"**旁证、不得据以定值**"；§13 全部读数**不经管道**取退出码。★ 另贡献一条：**仪器 B 自身也有 ≈2.9× 波动**（0.76~2.19s）⇒ 单次门禁读数不足以定值 |

---

## 12. ★ 新增发现：`raw/` 数据量增长会打红 `code_root` 夹具（**与全队验证批相关**）

> ### ★★ 事后更正（收到 `ws-ch2-rules` 的 `G-60` 广播后，2026-09-16 22:3x）
>
> **本节的归因方向对、但量级判断要下调；§12.3 的建议不足以解决问题。**
>
> `ws-ch2-rules` 实测到了**硬数字**：
> ```
> [safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
>   {"count":100267,"threshold":99999,"scope":"turn","targetCount":1}
> ```
> ⇒ 删除预算是 **宿主「回合级」+ 全流共享**的**累计式**配额（`count` = 累计 + 本次）；
> 越过阈值后**连"删 1 项"都被拒**；恢复只能等下一个宿主回合或用户授权批量删除。
>
> **对 §12.3 的更正（我原建议的问题）**：`_COPY_SKIP` 加 `"raw"` 只减少**每例约 18 项**
> 删除量，而一次 `code_root` 用例的 teardown `rmtree` 要删**整棵副本约 600 项**
> （`system/` 共 629 文件 + 123 目录）—— 18/600 ≈ **3%**。
> ⇒ 它是**减少触发概率的边际优化**，**不是** `G-60` 的解。
> 真正能救的方向是 `ws-ch2-rules` 指出的：**把 `_clear_work_dir()` / 夹具 teardown
> 改成逐文件删除**（单次体量 ~600 → 1）。
> **我不撤回 §12.3 的建议，但下调其定位**：它值得做（少复制 281 KB、少 18 次删除、
> 且与 `derived`/`.gitkeep` 同源），但**不要**指望它解决全流打红的问题。
>
> ★ 另：`G-60` 也**解释了本节之外的两处观测**，因此那两处**不应**记为本批次缺陷：
> - §7.4 的 `17 passed, 1 error`（同一个 safe-delete fail-closed 机制）；
> - §6.2 的 `12 failed` 全部是 `…_on_pristine_tree[…]`、`code=2` +
>   `[INPUT-ERROR] code_root 不存在: …/_pristine/system` ——
>   `pytest_sessionstart` 的 `_clear_work_dir()` 失败后 `pristine_code_root` 建不起来
>   （我当时归因给"并发 pytest 互清目录"，**方向一致但描述不准确**：
>   更准确的说法是**共享删除配额被全流推爆**，不一定是另一个 pytest 会话主动删的）。

### 12.1 现象（原样）

`tests/injection/test_quote_provenance.py` 第二次运行时：

```
$ sh system/scripts/ops/run_pytest.sh tests/injection/test_quote_provenance.py -q
.....E............                                                       [100%]
==== ERRORS ====
ERROR tests/injection/test_quote_provenance.py::test_fabricated_quote_hash_is_rejected
17 passed, 1 error in 273.51s (0:04:33)
EXIT=1
```

★ **仪器标注（`口径 21`）**：`273.51s` 为**裸 pytest 墙钟 = 旁证**。此处**只用其"E vs F"的定性**
（夹具 setup 被 fail-closed 打掉），**不用**其数值做任何定值或比较。

★ 关键：这是一个 **`ERROR`（夹具 setup 阶段失败）**，**不是** `FAILED`（断言失败）。
报错栈：

```
request = <SubRequest 'code_root' for <Function test_fabricated_quote_hash_is_rejected>>
    @pytest.fixture()
    def code_root(request: pytest.FixtureRequest) -> Path:
        target = WORK_DIR / f"{request.node.name}-{uuid.uuid4().hex[:8]}" / "system"
        shutil.copytree(SYSTEM_ROOT, target, ignore=_ignore)
        …
>       _reset_truth_source(target)
tests/conftest.py:153:
tests/conftest.py:94: in _reset_truth_source
    item.unlink(missing_ok=True)
…/sitecustomize.py:902: in _try_trash_via_binary
E  OSError: [safe-delete] 操作失败: ERROR \
   …/tests/.work/test_fabricated_quote_hash_is_rejected-98fafbfe/system/raw/2026-05-20-nvidia-q1-fy2027-results.txt: \
   FSMoveObjectToTrashSync failed (status -43) for "…/2026-05-20-nvidia-q1-fy2027-results.txt"
---------------------------- Captured stderr setup -----------------------------
[safe-delete][SAFE_DELETE_FAIL_CLOSED] {"target": "…/raw/2026-05-20-nvidia-q1-fy2027-results.txt", "reason": "trash-failed", …}
```

同一次输出的开头还出现了夹具工作目录清理残留的告警：

```
[WARNING] 夹具工作目录未能清空（残留 1 项，例如 ['test_rerun_many_times_stays_single_row-0fadddb1']）…
```

### 12.2 机制（我的判断；★ **未做实验验证**，如实标注）

1. `code_root` / `pristine_code_root` 夹具每例都 `shutil.copytree(SYSTEM_ROOT, target)` ——
   **连同 `raw/` 一起复制**（`_COPY_SKIP` 目前只跳 `__pycache__` / `.pytest_cache` / `.venv` /
   `.work` / `index` / `reports` / `derived` / `.locks`，**不含 `raw`**）；
2. 紧接着 `_reset_truth_source(target)` 会**逐个 `unlink`** 副本 `raw/` 下的每个文件
   （`for item in list(raw.iterdir())`）；
3. 宿主 shim 把每次 `unlink` 变成"移入废纸篓"的 IPC（`sitecustomize._safe_path_unlink`）；
4. 配额 / 阈值耗尽时 `trash-failed`，且该 shim 是 **fail-closed**（`SAFE_DELETE_FAIL_CLOSED`）
   —— 直接抛 `OSError`，**不降级为真删除**；
5. 于是**夹具 setup 失败** → 用例报 `E`（还没开始跑就结束）。

本批次把 `raw/` 从 **4 份扩到 18 份**（新增 14 份、合计 **281,138 字节**）⇒
**每个用例多了 14 次删除操作 + 14 个文件的复制量**，命中配额的概率显著上升。

**观测支持的旁证**（但**不是**证明）：同一文件**前一次运行 `18 passed`（0 error）**、
后一次 `17 passed + 1 error`；报错的用例本身**没有任何特殊性**
（它就只是"配额耗尽时正在跑的那一个"）；两条工作目录清理告警同时出现。
⇒ 特征是**配额相关的抖动**，不是确定性缺陷。

### 12.3 建议的修法（★ 已按 `G-60` 更正定位：**边际优化，不是解**）

把 `"raw"` 加进 `conftest._COPY_SKIP`：

```python
_COPY_SKIP = {
    "__pycache__", ".pytest_cache", ".venv", ".work", "index", "reports", "derived", ".locks",
    "raw",          # ← 建议新增
}
```

**为什么这是"行为不变"的**：

- `_reset_truth_source` **本来就**会把副本的 `raw/` 清空 ——
  所以"复制真实抓取物"是**纯浪费**（复制进来、马上删掉）；
- `_ENSURE_DIRS` 里已经有 `"raw"`，夹具会补出**空目录**，
  需要写 `raw/` 的注入测试（含本批次的 18 条）**照旧可写**；
- 效果：每个用例少 18 次 `unlink`、少复制 281 KB。

**★ 但它的定位要下调（见本节顶部的事后更正）**：
每例 teardown 的 `rmtree` 总量约 **600 项**（`system/` 共 629 文件 + 123 目录），
`raw` 只占 **18 项 ≈ 3%** ⇒ **这是边际优化，不是 `G-60` 的解**。
`G-60` 的解是 `ws-ch2-rules` 指出的方向：
**把 `_clear_work_dir()` / 夹具 teardown 改成逐文件删除**（单次体量 ~600 → 1）。
两者互不冲突、可同时做；但**不要**把"跳过 `raw`"当成"问题已解决"。

**为什么我**没有**自行改**：`tests/conftest.py` 是**团队共享的测试基础设施**，
主理人刚刚明确要求我撤销对 `tests/guards/` 的改动、并正在集中修 `G-28`
（同样在测试基础设施里）。同一时刻由我在另一个共享测试文件上单方面动手，
只会制造新的冲突面。**故此条作为发现上报，不自行实施。**

★ 这与当初为 `derived` / `state.json` 加 `_COPY_SKIP`（commit `23f78db`）**同源**：
**夹具不该继承真仓库的数据量**。本批次把 `raw/` 的数据量提高了 4.5 倍，
把这个原本潜伏的耦合推得更显形 —— 但要**如实说**：`G-60` 的主因是
**全流共享的回合级累计删除配额**（`ws-ch2-rules` 实测 `count=100267 > threshold=99999`），
**不是**我这 14 个文件；把主因记到我头上同样是错误归因。

### 12.4 对全队的影响面（为什么要上报而不是自己咽下）

任何**新增 `raw/` 抓取物**的工作流都会放大这个问题，而"真实信息采集扩容"
正是本阶段多个批次的任务。受影响的是所有用 `code_root` / `pristine_code_root` 的批次：
`unit` / `conflict` / `guards` / `injection` / `root`（`verify.py::ORDER` 的全部五项）。
症状是 `ERROR`（不是 `FAILED`）+ `[WARNING] 夹具工作目录未能清空` +
`[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":…,"threshold":99999,…}`，
**极易被误读成"某个守卫坏了"** —— 这正是本项目三令五申要避免的**假缺陷**形态。

### 12.5 本批次受影响用例的**净结论**（不拿 `E` 冒充结论）

| 观测 | 归因 | 是否本批次缺陷 |
|---|---|---|
| `17 passed, 1 error`（§7.4） | `G-60`：夹具 setup 被 safe-delete fail-closed 打掉 | ❌ 不是 |
| `12 failed`，全是 `…_on_pristine_tree[…]`（含既有 `locator_check` 等，§6.2） | `G-60`：`_clear_work_dir()` 失败 ⇒ `pristine_code_root` 建不起来 | ❌ 不是 |
| 该跑的**断言**（18 条正反向对照、21/21 引文逐字复核、三条退出码契约、全门禁 exit 码） | 均有**未受 `G-60` 影响**的实测证据（直连探针 / 自建干净副本 / 真源直跑） | ✅ 已交付 |

★ 我**没有**用"墙钟没跑绿"冒充"跑绿了"，也**没有**用"绕过 safe-delete 得到的绿"当证据
（与 `ws-ch2-rules` 的立场一致）：那条 `17 passed, 1 error` 原样留在 §7.4，
`12 failed` 原样留在 §6.2，都没有被抹掉或改写成"已通过"。
★ 并发删配额耗尽后我**没有**再跑任何依赖 `code_root` 夹具的批次 ——
不是"跑过了"，而是**因 `G-60` 未跑**；本报告里所有绿灯都取自不删文件的路径
（守卫/门禁直跑、`/tmp` 副本、`/tmp` 探针）。
★ **本条已被 §13 更新（不是撤回）**：`G-60` 缓解后我按门禁口径补跑了 `injection-g`
并取得绿灯（`exit=0` / `18 passed` / `15.37s/90s`）。§12 保留的是**当时的**如实记录，
两节并存 = 同一事实在不同时点的读数；**若只读一节，请读 §13**（更新的在下）。

---

## 13. 补测（`G-60` 缓解后）：`injection-g` 墙钟绿灯 + 一处**口径更正**

`ws-ch2-rules` 的 `G-60` 广播要求"需要跑测试的流先只报『因 `G-60` 未跑』"。
本节是**后来补上的实测**：绿灯已取得，且过程中推翻了我自己的一个推断（原样登记，不删）。

### 13.1 绿灯（走**项目自己的 harness**，非我手搓命令）

先把我这一侧的 worktree 与主干齐平（**纯快进**，`git merge main`，
`我独有 0 / 我缺少 133` → 现 `0 / 0`，HEAD `c25880d`；**未用** `--no-verify`，
**未改** `pre-commit.sh` / `run_all_gates.py` 的内容）：

```console
$ cd system && python scripts/ops/verify.py --batch injection-g >/tmp/vg.out 2>&1 ; echo "verify.py 真实 exit=$?"
✓ [injection-g] tests/injection/ 分片 G（反编造：引用溯源守卫）  exit=0  15.37s/90s  exit=0
------------------------------------------------------------------------------
..................                                                       [100%]
18 passed in 15.08s
------------------------------------------------------------------------------
证据留档: reports/verify_injection-g_latest.log
verify.py 真实 exit=0
```

⇒ 补的是**门禁口径**的绿灯。★ 需要说准：§7.4 **本来就已有一次** `18 passed in 266.20s`
（`run_pytest.sh`，`EXIT=0`）—— 也就是说"18 条全过"这件事**早就有实测**，
本节的价值**不是**"补上一个缺失的绿"，而是两件事：
① 走**项目自己的 harness**（`verify.py`，含其 `Batch.timeout` 判定）也**绿**；
② 把 §7.4 的 `266s` 与这里的 `15.37s` 之间**16 倍**的差异**归因清楚**（见 §13.3）——
**这两个数都真实，但只有后者是门禁口径**；把前者当门禁耗时读会得到相反的结论。
★ 退出码是**不经管道**直接取的（`>/tmp/… ; echo $?`）—— 先前我用 `cmd | tail` 取
`${PIPESTATUS[0]:-$?}`，在 **zsh** 里数组是 1-based、`${PIPESTATUS[0]}` 不存在
⇒ 回落到 `$?` = `tail` 的退出码 ⇒ 会打出**假的 `exit=0`**。
这是个真实的取证陷阱，故 §13 的读数一律不经管道。

### 13.2 同一条命令、前后两次结果相反（`G-60` 的**可复现**数据点）

```console
# 第 1 次（~2 分钟前，Bash 工具沙箱内）
✗ [injection-g] …  exit=1  3.06s/90s  **宿主单轮删除配额耗尽**（`scope: "turn"`）—— …
.E.E.E.E.E.E.E.E.E.E.E.E.E.E.EFE.E.E        ← 15 个 E + 1 个 F
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":100268,"threshold":99999,"scope":"turn","targetCount":1}

# 第 2 次（同一条命令、同一棵树，Bash 沙箱旁路）
✓ [injection-g] …  exit=0  15.37s/90s        18 passed
```

**判据：差异不在代码，在宿主沙箱状态。** 值得一提的两点：

1. `verify.py` 的 `_clean_env()` 会把验证子进程的
   `CODEBUDDY_SAFE_DELETE_SANDBOX` / `CODEBUDDY_BROKERED_FS_HOOK_ENABLED` 置 `0`
   （源码注释自称"**验证子进程一律在沙箱外跑**（用户要求）"）；
   **但第 1 次里守卫照样在子进程内报错** ⇒ **该 env 置 0 并不足以左右守卫**，
   真正决定它的是**外层 Bash 工具那一层的沙箱状态**。这条对 `G-60` 的处置有用：
   想靠"改 env 关沙箱"绕过是**不成立**的（与广播"不要绕过"一致，且现在有实测依据）。
2. `verify.py` 自身**正确识别**了这种形态并直接写明"这多半不是测试失败 / 处置：新开一轮"，
   没有把它渲染成"测试坏了" ⇒ 之前 §12.4 担心的"假缺陷"形态在 harness 层**已被防住**。

### 13.3 ★ 口径更正：我先前那句"247s"**不是**门禁口径（我的推断已被 13.1 推翻）

| # | 命令 | 沙箱 | 读数 | 是否门禁口径 |
|---|---|---|---|---|
| ① | `pytest tests/injection/test_quote_provenance.py -q -p no:cacheprovider` | 内（brokered FS 生效） | `18 passed in 247.19s` | ❌ **不是** |
| ② | `time pytest <单例>` | 内 | pytest 自报 `13.05s` / `real 13.86s` | ❌ |
| ③ | `time pytest <单例>`，另加 `CODEBUDDY_*=0` | 内 | pytest 自报 **`1.37s`** / `real` **`13.43s`** | ❌ |
| ④ | `verify.py --batch injection-g` | **旁路** | **`15.37s/90s`，`18 passed`** | ✅ |

①③④ 的读数差到 **16 倍**（247s vs 15.4s）；③ 里"同一份工作"从 pytest 计时窗口内
（② 的 13.05s）挪到窗口外（③ 的 real 13.43s − 1.37s ≈ 12s）而**总量不变** ——
⇒ 那 ~12s/例是**沙箱内删除路径**的代价，与用例本身无关。

**被推翻的推断（如实登记）**：我据 ① 一度推断"`injection-g` 超时登记 `90s` < 实测 247s
⇒ 该片经 `verify.py` 必被判 `[TIMEOUT]`"。**这个推断是错的**，实测 `15.37s/90s`、余量 **5.9×**。
该推断**未写进报告、也未发给主理人**，仅在本节留痕；教训是
**"直接跑 pytest 的墙钟"不能给 `verify.py::Batch.timeout` 定值**（两者不同源）。

### 13.4 `injection-g` 超时 `90s` 的评估（建议，非阻断）

★ **仪器标注（`口径 21`）**：本节用于**定值讨论**的读数是 **`15.37s`（门禁口径，`verify.py` 自己打印）**
——这是唯一合法仪器；`247s`（沙箱内裸 pytest）与 §7.4 的 `266s` **只是旁证**，此处**仅用作风险上界**，
**不与 `15.37s` 做比值比较**。

- 门禁口径余量 `15.37s / 90s` ≈ **5.9×**，**够用**；与 `injection-a…f` 同为"够用"量级。
- 但按注册注释里自述的规则（"实测 × 8 上沿、不低于 90s"）应为 `15.37 × 8 ≈ 123s`
  （上限 300s）⇒ 现登记的 `90s` 是按**未实测**的起步值填的（注释亦自述"待 13-F 对照表重算"）。
- ★ **保留一条真风险**：一旦 `verify.py` 的子进程落在**沙箱内**（13.2 已复现该状态），
  本片单次即 **247s ≫ 90s** ⇒ 会被判 `[TIMEOUT]`，而**同一时刻 `a–f` 因登记 300s 不会**。
  ⇒ 建议把 `injection-g` 与 `a–f` **齐平为 `300.0`**（只改一个数、无副作用），
  使其在"环境变差"时不比邻片更早红。**我不自行改动**：`verify.py` 属测试基础设施、
  且我无权改主理人的登记值。

★ **处置结果（事后补记）**：主理人**已批准并提交**：`injection-g` **`90 → 300`**
（与 `a..f` 齐平，吸收上面那条已复现的宿主状态），同时把 `unit` 批 **`120 → 300`**，
并**据此更正了 `G-54` 自己的一个结论**（我曾被用来纠错的同族错误：拿"门禁口径 `49.35s`"
与"裸 pytest `66.72s`"相比得"高方差"，属**混用两个仪器**）。
⇒ 本次的"仪器"教训已立为团队 **`口径 21`**（两个仪器），`PIPESTATUS` 陷阱立为 **`口径 22`**。
本节建议**已闭环**，无需再动。

### 13.5 本次补测的干净性与纪律

- `reports/verify_injection-g_*.log` 被 `system/.gitignore:22`（`reports/*.log`）忽略
  ⇒ `git status --short` 仍为**空**；`tests/.work` 残留 **0** 项。
- `git merge main` 是**纯快进**（无冲突、无 `MERGE_HEAD`），**未使用** `--no-verify`。
- 真仓库根仍处于 **`merge ws/verify-shard` 的中间态**（`UU CONVENTIONS.md` / `UU verify.py`）——
  **非我方**：我方 4 个提交（`fc7c982` / `03959f1` / `a54da80` / `5872fa3`）只触碰
  `facts/*.jsonl`、`raw/*.txt`、`quote_provenance_guard.py`、`ingest/*`、
  `ops/{run_all_gates.py,pre-commit.sh}` 与报告，与那 5 个脏文件**零交集**。
- 顺带（**不属本批次**，已单独报主理人）：`verify.py` 的 `INJECTION_SHARDS` 实为 **7** 项
  （含 `injection-g`），而正文/注释里仍有 8 处写「6 片/六片」、第 29 行枚举上界也只到
  `injection-f` ⇒ **文档滞后**（机器绑定绑的是"分片集合 ↔ 目录文件全集"，绑不到散文里的数字）。
  **我未改动**；★ 主理人已立**卡 13-N**（归 `ws-ch4-valuelayer`）。
