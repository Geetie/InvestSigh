# MCP 配置说明（正式测试前必读）

> 产出：macOS 会话（2026-09-17）。**用途**：正式测试前把「该连哪些 MCP、为什么、连不上怎么办」一次说清。
> **关键原则**：本文所有「可用/不可用」结论都来自**本轮真实调用**，不是文档推测。举证半径逐条声明。

---

## 一、结论：设计只认 **3 个** MCP，你已连 2 个、缺 1 个

**权威依据**（三处一致，均可查）：

| 依据 | 位置 | 逐字 |
|---|---|---|
| 数据源白名单 | `rules/data-sources.allowlist.yaml`（0444 锁定） | `sources:` = `westock` / `iFinD` / `pandadata`（均 `kind: mcp_connector`）+ `websearch_webfetch`（`kind: builtin_capability`） |
| 首版启动条件 | `registry/launch_criteria.yaml::available_sources` | `westock` / `iFinD` / `pandadata`（均 `license_tier: free_quota`、`cost: 0`） |
| 设计结论 | `Ch6 §H.1`（`06_公开信息与证据筛选/02_实现方案.md:470`） | "现有 MCP 覆盖一手财务/行情/公告主干…**完全不需要新增付费订阅**（守住 `N6.1-13`）" |

> `D-01`（2026-09-15 已拍板）：iFinD / pandadata 有免费额度，**暂不视为"付费数据订阅"** ⇒ 可进首版清单；
> 但 `may_enter_decision_logic: false`（**不得写入裁决逻辑**）。

### 三个在册源的宿主实况 + 本轮实测

| # | MCP | 白名单 | 宿主实况 | 实测结论（**15:00 最新**） |
|---|---|---|---|---|
| 1 | **westock**（腾讯自选股） | ✅ 在册 | ✅ 已连 | ✅ **可用**（见 §二）；★ 但只有**已调整**的单一复权口径，ETF 持仓/净值为空壳 |
| 2 | **pandadata**（PandaData） | ✅ 在册 | ✅ 已连、**已重连** | ❌ **认证已通，但业务层仍无权限**：`auth_status` → `ok` ✅，而 `get_trade_cal` / `get_us_daily` / `get_stock_detail` **三类全部 `200103 API访问权限不足`**（见 §三-D） |
| 3 | **iFinD**（同花顺） | ✅ 在册 | ✅ **已授权 + 工具已载入**（本会话可见 `mcp__ifind-mcp__*`） | ⚠️ **账号级配额超限**：3 个不同工具全部返回 `用户使用工具已超限`（见 §四） |
| 4 | **tdx-connector**（通达信） | ❌ **不在白名单** | ✅ 已连 | ✅ **实测覆盖面最广**：美股行情（`DelayHQMin:15`）· K 线**三口径可区分** · **公司行动表（分红/拆股）**（见 §二/§五） |

---

## 二、westock：唯一"连上且真能用"的在册源

**实测命令与返回**（`mcp__westock-mcp__data_search` / `data_quote` / `data_kline` / `data_profile`）：

| 能力 | 调用 | 实测返回 |
|---|---|---|
| 标的检索 | `data_search(query="AGIX", type="etf")` | `usAGIX.OQ` = 人工智能ETF-KraneShares ✅ |
| 行情快照 | `data_quote(codes="usNVDA.OQ,usAGIX.OQ")` | NVDA `213.90` / AGIX `44.92`，含 `prev_close`、`time:"2026-09-16"`、`pre_market_price` / `post_market_price` ✅ |
| 日 K 线 | `data_kline(code="usNVDA.OQ", period="day")` | 开/高/低/收/量/额，按日期倒序 ✅ |
| 个股概览 | `data_profile(code="usNVDA.OQ")` | 上市日 `1999-01-22`、行业"半导体"、官网、简介 ✅ |
| **ETF 持仓/净值** | `data_etf(code="usAGIX.OQ")` | ❌ **全字段为 0 / null / 空串**（`holdings:null`、`nav:0`、`size:0`、`trackIndexCode:""`、`manageInstitution:""`） |
| ETF 净值（专项） | `data_etf(code=…, aspect="nav")` | ❌ **服务端报错**：`查询ETF净值异常：error_type=2 msg=service error` |

### ★ 对 `N9.3-08`（复权口径）的实测：`fq` 参数**不可区分**

**区分实验**（设计要对齐意图：必须**跨除权日**才有区分力）：

| 区间 | 事件 | `fq` 未传 | `fq=qfq` | `fq=hfq` | 结论 |
|---|---|---|---|---|---|
| 2024-06-05..06-12 | 跨 NVDA 2024-06-07 **十拆一** | 06-06 `120.623` → 06-10 `121.413` | **同上** | **同上** | 三取值逐字段相同；序列**无 10 倍跳变** ⇒ 返回的是**已按拆股调整**的单一口径 |

（首轮实验区间 2024-06-01..05 **不跨除权日**，三取值相同属正常 —— 已重做。★ `V-10` 元规矩：先做区分实验再落结论。）

⇒ **含义**：`adjustment_caliber_version` 只能记**一个**口径（"该源返回的已调整序列"），**没有第二口径可对拍**。

#### ★★ 解法（15:00 实测，已找到）：`tdx` 的 `tqFlag` **三口径真的可区分**

`mcp__tdx-connector__tdx_kline` 有 `tqFlag`（`0`=不复权 / `1`=前复权 / `2`=后复权）。
**区分实验**（同标的、同区间：`NVDA` / `setcode=74` / `period=4` / `startxh=560` / `wantNum=12`）：

| 日期 | `tqFlag="0"` 不复权 | `tqFlag="2"` 后复权 | westock（已调整） |
|---|---|---|---|
| 2024-06-05 | **1224.40** | **58845.02** | 122.061 |
| 2024-06-07 | 1208.88 | 58100.05 | 120.514 |
| 2024-06-10（拆股后） | **121.79** | **58533.02** | 121.413 |
| 2024-06-21 | 126.57 | 60832.22 | 124.825 |
| **区间涨跌** | **−89.66%**（拆股假跌） | **+3.38%** | — |

⇒ **三种口径返回三套不同的数**（`0` 含拆股跳变、`2` 累积调整连续），**口径可对拍**。
⇒ 缺口 1 **有解**，但解法在 **`tdx`**（**不在** D-01 白名单，见 §五 / §九）。


### ★ 另一处缺口：基准「含分红再投资」无数据

`rules/benchmark.yaml::return_basis.dividends_reinvested: true`（AGIX 主基准要求总回报口径）。
但 westock 只给 `dividend_ttm` / `dividend_ratio_ttm`（**汇总值**），**无分红事件表**（除权日 / 金额 / 拆股比率）
⇒ `registry/corporate-actions.jsonl` 目前 **0 字节**，无自动填充方。

#### ★★ 解法（15:00 实测，已找到）：`tdx` 的深度资料**直接给出公司行动表**

`mcp__tdx-connector__tdx_security_deep_info` 自动规划到两个专用工具，**主基准与研究对象都取到了**：

| 标的 | 工具 | 实测返回 |
|---|---|---|
| **AGIX**（主基准 ETF） | `f9_us_dividend_payout_detail` | ✅ **2 条分红**：`2025-12-22` 美元 `0.437658`（派发 12-23）· `2024-12-17` 美元 `0.109841`（派发 12-18）—— 含**除息日 / 货币 / 每股派息 / 登记日 / 派发日**六个字段 |
| **AGIX** | `f9_us_split_reverse_split` | ✅ **0 行**（= **真实的"无拆股事件"**，不是取数失败；ETF 通常不拆股） |
| **NVDA**（研究对象） | `f9_us_split_reverse_split` | ✅ **1 条拆股**：`2024-06-10` · 股票拆分 · 实施 · 比例 `0.1` · **"每1股拆分为10股"** |
| **NVDA** | `f9_us_dividend_payout_detail` | ✅ **12 条分红**（2023-12-05 ~ 2026-09-10），含 `2024-03-05` 的 `0.04` 与 `2026-09-10` 的 `0.25` |

★ 这正是 `Ch9 §N9.3-08`（P0）要求的那张「**公司行动表**：证券、类型、生效日、拆股比率/分红金额、来源」+ 复权方法。
⇒ 缺口 2 **有解**（`f9_us_dividend_payout_detail` + `f9_us_split_reverse_split`），**但同样在 `tdx`**（不在白名单）。

★ **另一条更合规的路**（未验证，因配额受阻）：**`iFinD` 在册** —— 它的 `get_security_indicators` 覆盖"基础信息/行情K线/**财务分析**"
且支持**基金**市场，**可能**也能给公司行动/复权。**若 iFinD 能覆盖，就不必动白名单。**（见 §九 动作 3）


---

## 三、pandadata：**两层不同的错，必须分开看**（★ 本节为 14:40 修订版）

> ★ **修订说明**：本报告初版（14:2x）把 pandadata 记为"连上了、认证了，但无数据权限"。
> 14:30 前后用户授权 iFinD，之后**同一批调用返回的错误变了**。现已把两个状态分别记录 —— 见 §三-A / §三-B。

### §三-A 第一层（14:2x 实测）：业务层「无数据权限」

| 调用 | 返回 |
|---|---|
| `auth_status` | `ok: true`、`username: 8617350527956`、`reauth_required: false`、`data_mode: gateway`、token 剩余 ~23 天 |
| `sdk_status` | `ok: true`、`doc_method_count: 219` |
| `get_us_daily(symbol=["NVDA","AGIX"], …)` | ❌ `{"code":"200103","message":"API访问权限不足"}` |
| `get_adj_factor(symbol="000001.SZ", …)` | ❌ 同上 |

**举证半径**：本账号（`8617350527956`）、这两个方法、这两个标的。**不外推**为"pandadata 所有方法都无权限"—— 我当时**只测了 2 个方法**，`get_trade_cal` / `get_stock_detail` 当次未测（见 §三-D 待补测）。
（注：文档初版写的"**全类**无权限"是**超出举证半径的表述**，已按 `V-11` 更正。）

### §三-B 第二层（14:40 实测，当前状态）：传输层「根本没认证」

授权 iFinD 之后，重测同一批调用，错误**换了层**：

| 调用 | 返回 |
|---|---|
| `call_pandadata(method="get_last_trade_date")` | ❌ `[MCP] Streamable HTTP error: Error POSTing to endpoint: {"error":"unauthorized"}` |
| `call_pandadata(method="get_stock_detail")` | ❌ 同上 |
| `call_pandadata(method="get_trade_cal")` | ❌ 同上 |
| `auth_status`（连它本身） | ❌ 同上 |

★ **`get_last_trade_date`（交易日历，最基础的接口）也失败** —— 这不再是"某个数据集没权限"，而是**请求根本没被接受**。
★ **对照实验**（同一时刻）：

| 源 | 同一时刻调用 | 结果 |
|---|---|---|
| `westock-mcp` | `data_quote(codes="usNVDA.OQ")` | ✅ `213.9` |
| `tdx-connector` | `tdx_quotes(code="NVDA", setcode="74")` | ✅ `213.9` |
| `pandadata` | `get_last_trade_date` | ❌ `unauthorized` |

⇒ **不是"全部 MCP 挂了"，只有 pandadata 这一个掉线。**

### §三-C 证据指向：pandadata 的托管认证头丢了（**假设，非断言**）

| # | 事实（可复现） | 位置 |
|---|---|---|
| 1 | `headerOverrides` 里**只有** `tdx-connector` / `github` / **`ifind-mcp`** 三项有 `Authorization`；**pandadata 没有**（`westock-mcp` 也没有，但 westock **不需要** —— 它的端点是免认证的公开入口，实测可用） | `connectors/<id>/connector-states.json` |
| 2 | 同一份文件里有 `"staleManagedAuthHeadersPurged": true`（宿主执行过"**清理陈旧的托管认证头**"） | 同上 |
| 3 | 四个源的 `mcp.json` 配置里**都没有 `headers`** ⇒ 认证**全部靠宿主运行时注入**（所以 `headerOverrides` 缺项 = 无认证） | `connectors/<id>/mcp.json` |
| 4 | `mcp.json` 与 `connector-states.*.json` 的 mtime 都是 **14:30**（= 授权 iFinD 的时刻） | `ls -l` |

**推论**（供排查方向，**不是已证实的根因**）：pandadata 的 Authorization 由宿主托管注入；它**不在** `headerOverrides` 里，
而 `staleManagedAuthHeadersPurged` 表明发生过一次清理 ⇒ 时序上「能进网关（200103）→ 授权 iFinD（14:30 重载配置）→ 进不去了（unauthorized）」与"托管认证头被清掉"**相符**。
★ 我**没有**读到任何写入日志能直接证明这条因果 ⇒ 按本仓纪律，**这是假设**。要证实，需在你重新授权 pandadata 时观察
`headerOverrides` 是否重新出现 `pandadata` 项。

### §三-D 处置结果（★ 用户已于 14:5x 重连，结论已出）

**重连把第一层修好了，第二层暴露为真问题。** 断言逐条兑现如下：

| 步骤 | 期望 | **实测结果** |
|---|---|---|
| ① 重连 pandadata | Authorization 重新写入 | ✅ **认证层已恢复**：`auth_status` → `{"ok": true, "username": "8617350527956", "reauth_required": false}`（不再是 `unauthorized`） |
| ② 重连后立刻验证业务层 | 若回到 `200103` ⇒ 是"第二层"权限问题 | ✅ **`get_trade_cal`（交易日历，最基础）→ `{"code":"200103","message":"API访问权限不足"}`** |
| ③ 补测三类，把举证半径补全 | 确定"无权限"的范围 | ✅ 已测 **3 类**，**三类全拒**：`get_trade_cal`（日历）· `get_us_daily`（美股日线）· `get_stock_detail`（A股基础资料） |

**⇒ 结论（措辞已按举证半径限定）**：
**"是不是我没授权"——不是。授权层已经通了**（`auth_status` 正常）。
**是账号在 pandadata 网关侧没有数据权限** —— 而且**连交易日历都取不到**，
说明这不是"某几个数据集没开通"，而是**该账号套餐整体未开通数据权限**。
（举证半径：本账号、本轮 3 个方法、3 个类别；未测满全部 219 个方法，故不说"全部"。）

**处置**：去 pandadata 侧确认能否开通（免费额度内）；**开不了就按 `N9.3-07` 在 `registry/sources.yaml`
如实标注该来源"不可用"** —— `fallback_source_ids` 里留着它却不标注，等于把"没有备选"装成"有备选"。

---

## 三之二、★ 两个缺口的处置（都有解，已实测）

> §二 提出两条实测缺口。经 15:00 的针对性实验，**两条都找到了可用解法**，但解法**都在 `tdx`**（不在白名单）。

### 缺口 1：复权口径只有一个 → **用 `tdx` 的 `tqFlag`，三口径可区分**
见 §二 "★★ 解法"。`tqFlag="0"/"1"/"2"` 返回三套不同的数，口径**可对拍**。

### 缺口 2：公司行动（分红/拆股）无数据 → **用 `tdx` 深度资料，直接给出事件表**
见 §二 "★★ 解法"。AGIX 与 NVDA 的**分红与拆股事件**都取到了（含除息日/每股派息/登记日/派发日/拆股比率）。

### 三条路，按合规优先级

| 优先级 | 路线 | 代价 | 状态 |
|---|---|---|---|
| **① 最合规** | 等 **iFinD** 配额恢复，测它能否给公司行动/复权（**iFinD 在册，不必改白名单**） | 等配额；结果未知 | ⏳ 待测（§四） |
| **② 次优** | **把 `tdx` 补进 `rules/data-sources.allowlist.yaml`**（同 `registry/launch_criteria.yaml`），走 `N6.1-13` **变更审批** | 需**需求方批准** + 改 0444 锁定文件（走 bootstrap 流程） | ⏳ 待决策 |
| **③ 保底** | 用 **WebSearch / WebFetch** 取 AGIX 公开分红记录（在册的 `builtin_capability`） | 人工、不可批量、无结构化事件表 | ✅ 立即可用 |

★ **② 不是技术问题，是审批问题**：`rules/data-sources.allowlist.yaml` 是 0444 锁定 + SHA256 登记的真源，
且 `N6.1-13`（P0）明写"部署清单中不存在未经授权的付费源"⇒ 加源**必须走变更审批**，不能由我自行改。
★ 另外 `launch_guard.py` **只校验 `iFinD` / `pandadata` 两项**，加 `tdx` 也不会有门禁替你拦（见 §八-1）。

**影响**（这才是重点）：
- pandadata 在 `registry/sources.yaml` 里是 westock 的 `fallback_source_ids` 之一，而 `N9.3-07`（P0）要求
  "**每个来源登记至少一个备选来源**，保证采集失败/限流时可持续…**没有备选就只能停摆或伪造**"。
- 现状：**主源一旦限流，备选是空的**（iFinD 未连、pandadata 无权）。
- pandadata 还持有本项目唯一可见的**公司行动数据面**（`get_stock_split` / `get_stock_cash_dividend` / `get_stock_dividend` / `get_adj_factor`）—— 正是 §二 那处缺口的数据来源。

**动作**：① 去 pandadata 侧确认该账号能否开通数据权限（免费额度）；② 若不能，按 `N9.3-07` 在登记侧**如实标注"不可用"**（不许留空装成"有备选"）。

---

## 四、iFinD：★ **你已授权成功**，但本会话还用不了

**连接器市场缓存证据**：`~/.workbuddy/connectors-marketplace/connectors/ifind-mcp/mcp.json`

```json
{ "mcpServers": { "iFinD-MCP": { "url": "https://api-mcp.51ifind.com:8643/ds-mcp-servers/hexin-ifind-financial-mcp" } } }
```

### 14:30 授权后的本地实况（实测）

| 检查项 | 结果 |
|---|---|
| `connector-states.v3.json::enabled` | ✅ 含 **`ifind-mcp`** |
| `connector-states.v3.json::everConnected` | ✅ 含 **`ifind-mcp`** |
| `connector-states.json::connectors["ifind-mcp"]` | ✅ `{"bound": true, "enabled": true}` |
| `headerOverrides` | ✅ **有 `ifind-mcp` 的 `Authorization`**（加密存储）⇒ **认证已写入** |
| `connectors/skills/` 目录 | ❌ **尚无 `connector-ifind`**（其余 4 个都有） |
| 本会话工具检索 | ❌ 搜不到任何 iFinD 工具（返回的都是 tdx / westock） |

### ★ 更正：iFinD 工具**本会话已可用**（我上一条结论被推翻）

我 14:45 曾写"工具列表在会话启动时固定 ⇒ 必须新开一轮会话"。**15:00 实测推翻了这个说法** ——
**本会话（未重启）已能检索到 `mcp__ifind-mcp__*`**：
`get_security_indicators`（核心，含**美股/基金**市场）· `security_highfreq_quotes` · `get_stock_summary` ·
`search_news` · `search_trending_news` …

⇒ 更正为：**宿主会在连接器授权后动态注入工具**（至少本次如此）；不必新开会话。
（★ 记录这次自我更正，是我把"本会话搜不到"当成了"机制上必然搜不到"——**又一次把一次观测上升成了机制**。）

### ★ 但真正的障碍是**配额**：3 个工具全报"已超限"

| 调用 | 返回 |
|---|---|
| `get_security_indicators(market="美股", query="英伟达NVDA …开盘价、收盘价…成交量")` | `{"code":1,"msg":"success","data":{"answer":"用户使用工具已超限 "}}` |
| `get_stock_summary(query="同花顺 最新一期利润增速、ROE、资产负债率")` | 同上 |
| `search_trending_news(size=3)` | 同上 |

★ **三个不同工具（指标 / 摘要 / 资讯）、三类不同后端，全部同一条文案** ⇒ **账号级配额限制**，不是单个工具的问题。
★ 判读：`code:1, msg:"success"` 但 `data.answer` 是错误文案 —— **响应的外壳是成功的，内容才是失败**。
这正是"不能只看 HTTP/外层状态"的又一例（同 §二 的"空壳陷阱"）。

### 配额恢复后，第一件要做的事（这是缺口 1/2 的**最合规解法**）

```text
# 在**不超限**时依次做，并贴出原始返回：
1) get_security_indicators(market="美股",   query="英伟达NVDA … 复权因子"）或类似指标，看有无复权口径
2) get_security_indicators(market="基金",   query="KraneShares 人工智能 ETF AGIX … 分红、拆分")
3) 若 iFinD 能给**公司行动与复权** ⇒ ★ 缺口 1/2 用**在册的 iFinD** 解决，**不必改白名单**
```
**为什么优先 iFinD**：它是 `D-01` **在册**的源 ⇒ 用它补缺口**不需要任何审批**；而 `tdx` 虽已实测能覆盖，却**不在白名单**。

⚠️ pandadata 就是活证据 —— **"连上" ≠ "能用"**；iFinD 则是**第四种**形态：**连上、能调、但配额超限**。

---

## 五、不在册但已连的 3 个：要不要处理

| 已连 | 在册？ | 实测 | 处置建议 |
|---|---|---|---|
| **tdx-connector**（通达信） | ❌ **不在白名单** | ★ **本轮实测覆盖面最广，且补上了两个缺口**：`tdx_lookup_stock(range="MG-GP")` → `NVDA/setcode=74`；`tdx_quotes` → `213.9` + **`DelayHQMin: 15`**；`tdx_kline` 的 **`tqFlag` 三口径可区分**（缺口 1 解法）；`tdx_security_deep_info` **直出分红/拆股事件表**（缺口 2 解法，AGIX + NVDA 均成） | 它实测是**唯一**同时提供"延迟分钟数 + 三复权口径 + 公司行动事件表"的源。但按 `N6.1-13` + `Ch6 §I.1`「allowlist + 变更审批」，**要用它落库须先补登记**（见 §三之二「路线②」）。**若只作一次性人工核对、不落库，则不需改**（但需在试验记录里注明来源） |
| **agent-mail** | ❌ 不在册 | 未使用 | 对应通知层（`rules/notification.yaml` = `pointer_skeleton`，**不提前实现**）⇒ 现在**无消费者**，留着无害 |
| **github** | ❌ 不在册 | 未用于取数 | 版本管理用途（`git` 走本机），**与取数无关**，无需处理 |

> ★ 注意：`launch_guard.py` **只校验 `iFinD` / `pandadata` 两项**（`D01_SOURCE_IDS`），**不检 tdx / agent-mail / github**
> ⇒ 用 tdx 取数**不会让任何门禁变红**，但**违反设计纪律**（未授权源）。这是"门禁不覆盖"而非"被允许"。

---

## 六、不用配的（内置能力，不是 MCP）

| 能力 | 在册名 | 覆盖哪几类来源 |
|---|---|---|
| **WebSearch / WebFetch** | `websearch_webfetch`（`kind: builtin_capability`，`cost: 0`） | `registry/sources.yaml` 里 **4 类来源的唯一通道**：`src_company_ir`（公司 IR）/ `src_regulatory_filing`（监管披露，如 SEC EDGAR）/ `src_public_media`（媒体）/ `src_social_kol`（X / YouTube / Substack） |

⇒ 这 4 类**不需要任何 MCP**，宿主自带即可。`Ch6 §H.1` 明写：X/YouTube/Substack 走 WebSearch/WebFetch；研报与一致预期**只取公开摘要**（引付费库是红线）。

---

## 七、⚠️ 真正卡你的不是 MCP：**取到数也落不了库**

**实测**：全仓扫 `append_records`，**`facts/prices.jsonl` 与 `facts/benchmarks.jsonl` 除测试外零生产写入方**；
`scripts/ingest/` 四件（`seed_industry_nodes` / `real_collector` / `public_fetcher` / `fetch_manifest`）
**只处理文本**（sources / claims）；
`real_collector.py::collect_quotes` 名字有歧义，实为"**引文级 claim 摄入**"，**不是行情取数**。

⇒ **MCP 只解决"取到数"；没有任何脚本把 MCP 取到的行情落进 `facts/`。**
⇒ 这就是 `batch 0`（补前置数据）里**必须先写落库脚本**的原因。详见
`system/reports/unimplemented_by_design_inventory.md §八`。

---

## 八、两条顺带发现（新登记）

1. **`launch_guard` 不探活**：它只校验 YAML 里的**纸面声明**（`license_tier=free_quota` / `cost=0`），
   **不校验数据源实际可达**。⇒ pandadata 现在"声明免费额度、实际无权限"，**29 道门禁全绿、无一报红**。
   这是 `N6.1-13` 的一个空洞（"部署清单无未授权源"被满足成"清单上写着授权"）。
2. **`fq` 参数不可区分 + 分红再投资无数据**（详见 §二）⇒ 直接影响 `T11`（复权正确）与
   `benchmark.return_basis.dividends_reinvested` 能否达标。

---

## 九、动作清单（**15:00 更新版**）

| 优先级 | 动作 | 性质 | 阻断谁 |
|---|---|---|---|
| **P0** | **向 pandadata 侧确认账号为何整体无数据权限**（连交易日历都拒）→ 开不了则按 `N9.3-07` 如实标注该来源"不可用" | 你去问 / 我改登记 | `N9.3-07` 备选来源；公司行动数据面 |
| **P0** | **等 iFinD 配额恢复**，按 §四 的三步测它能否给**公司行动 / 复权口径**（★ 若可以 ⇒ 缺口 1/2 **用在册源解决，不必动白名单**） | 等 + 我测 | ★ 缺口 1/2 的最合规解法 |
| **P0** | 写"行情 → `facts/prices.jsonl` / `benchmarks.jsonl`"落库脚本 | 我做 | ★ **`batch 0` 的实质工作**（与上面无关，独立必做） |
| **P1** | **决策**：若 iFinD 不覆盖公司行动，是否按 `N6.1-13` 变更审批把 **`tdx` 补进白名单**（它已实测能覆盖缺口 1/2） | **你批准**（涉 0444 锁定真源） | 缺口 1/2 的次优解法 |
| **P2** | 可选的保底：用 WebSearch/WebFetch 取 AGIX 公开分红记录（在册能力，但不可批量） | 我做 | 缺口 2 的保底 |
| — | 不动 `agent-mail` / `github` | — | — |

### 一句话（15:00）

> **在册的 3 个源，此刻的真实状态**：`westock` ✅ 可用（但只有单一复权口径、ETF 持仓为空壳）·
> `pandadata` ❌ 授权已通、**账号整体无数据权限** · `iFinD` ⚠️ 已授权、工具已载入，但**账号配额超限**。
> **两个缺口都已有实测解法**（`tdx` 的 `tqFlag` 三口径 + 公司行动事件表），但解法**不在白名单** ⇒
> **首选**是配额恢复后用**在册的 iFinD** 复测，**不改白名单**；只有 iFinD 也不覆盖时，才走 `N6.1-13` 变更审批引入 `tdx`。
> 而无论哪条路，**`batch 0` 都仍要先写落库脚本** —— 否则 `prices` / `benchmarks` 还是 0 行。
