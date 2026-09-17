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
| 3 | **iFinD**（同花顺） | ✅ 在册 | ✅ 已授权 + 工具已载入 + **已购月度账号** | ✅ **已就绪可用**（配额恢复，实测 10 项，见 §四）：**能解缺口 1**（后复权可指定）· **补上 westock 两个空壳**（AGIX 净值 `45.03` + 跟踪指数名）· ❌ 但**美股/基金的公司行动（分红·拆股）为空** |
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

### 三条路的**实测结论**（15:2x 已全部落地）

| 缺口 | 路线 | 实测结果 | 判定 |
|---|---|---|---|
| **缺口 1**（复权口径） | **① iFinD（在册）** | ✅ **后复权可指定并成功返回**（`"复权方式":"后复权"`，序列连续无跳变） | ★ **已解决，无需审批、无需改白名单** |
| **缺口 2**（公司行动） | ① iFinD（在册） | ❌ **美股与基金两个市场、分红与拆股三类指标，全部空行** | **此路不通** |
| **缺口 2** | **② tdx 入册**（走 `N6.1-13` 变更审批） | ✅ tdx 实测有（AGIX 2 条分红 / NVDA 12 条 + 1 条拆股） | ⏳ **待你批准**（涉 0444 锁定真源） |
| **缺口 2** | **③ WebSearch / WebFetch**（在册 builtin） | 未测（作为保底手段） | ✅ 立即可用，但人工、不可批量、无结构化事件表 |

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

### ★ 曾经卡在配额（已解决）

15:00 时三个不同工具（`get_security_indicators` / `get_stock_summary` / `search_trending_news`）、
三类不同后端，**全部**返回同一条文案：
`{"code":1,"msg":"success","data":{"answer":"用户使用工具已超限 "}}` ⇒ 判为**账号级配额限制**。

★ 判读要点：**外壳 `msg:"success"`，失败藏在 `data.answer` 里** —— 只看外层状态会误判为成功。
（这是"伪成功"形态，与 §二 的"空壳陷阱"并列，见 `mcp-availability-check` 技能。）

**→ 用户已购月度账号，配额恢复。** 15:2x 复测：`get_security_indicators` **正常返回真实数据**。

### ★★ 配额恢复后的完整实测（15:2x，共 10 项）

| # | 调用（market / 意图） | 结果 |
|---|---|---|
| 1 | **美股** · NVDA 9/8–9/16 开收高低量 | ✅ **真实数据**：`20260916 收盘 213.9 / 量 9656.359万 / 开 214.14`；区间高 `233.71` 低 `208.93`，`USD` —— **与 westock、tdx 三方一致（213.9）** |
| 2 | **美股** · NVDA 同区间"三种复权方式" | ⚠️ 只回两列且**都是不复权**（`indicators_params` 两处均 `"复权方式":"不复权"`）⇒ **自然语言同时指定多口径不可靠** |
| 3 | **美股** · NVDA "**后复权**收盘价" | ✅ **成功**：`indicators_params` = `"复权方式":"后复权"`；`20240605 = 64066.79` → `20240612 = 65516.34`，**连续无跳变** |
| 4 | **美股** · NVDA **不复权**（隐含） | ✅ `20240605 = 1224.4` → `20240610 = 121.79`（**含拆股跳变**），**与 tdx `tqFlag=0` 逐字一致** |
| 5 | **美股** · NVDA 拆股（年度 2023） | ❌ 空行（工具从 query 里取了年度=2023，而拆股在 2024） |
| 6 | **美股** · NVDA 拆股（年度 **2024**） | ❌ **空行**（年度正确仍空）⇒ **iFinD 美股拆股无数据**（字段结构在：每股合并拆细比例/股份变更生效日期/除净日/方案说明） |
| 7 | **美股** · NVDA 分红（2024–2026 年度） | ❌ **空行**（字段结构在：除净日/每股派息/货币种类）⇒ **iFinD 美股分红无数据** |
| 8 | **美股** · AGIX（名称 与 `AGIX.O` 各一次） | ❌ `{"answer":"查询结果为空"}`（`indicators_params` 也空 ⇒ 连指标都未解析） |
| 9 | **基金** · AGIX 单位净值 | ✅ **`单位净值 45.03`**、`增长率 0.8737%`、净值日 `20260916`、代码 `AGIX.O` ★ **补上 westock 的空壳**（westock 的 `nav` = 0） |
| 10 | **基金** · AGIX 跟踪指数 | ✅ **`Solactive Etna人工智能通用智能指数`** ★ **补上 westock 的空壳**（westock 的 `trackIndexName` = `""`） |
| 11 | **基金** · AGIX 分红（收益分配方案） | ❌ 空行 ⇒ **基金市场也无公司行动数据** |

★ **举证半径**：`market` ∈ {美股, 基金} · 标的 ∈ {NVDA.O, AGIX.O} · 方法 = `get_security_indicators`；
**不外推**为"iFinD 整体没有公司行动数据"（其他方法如 `security_highfreq_quotes` 未测；iFinD 也可能有专用工具）。

### 由这 10 项得出的三条结论

1. **iFinD 已就绪**，且**是唯一在册、又能给复权口径的源** ⇒ **缺口 1 用它解，不必动白名单**。
2. **公司行动（分红 / 拆股）iFinD 给不了** —— 美股与基金两个市场、三类指标**全空** ⇒ **缺口 2 仍需另想办法**（见 §三之二）。
3. **★ 额外收获：iFinD 补上了 westock 的两个空壳** —— AGIX 的**净值 `45.03`** 与**跟踪指数名**。
   ★ 顺带印证了设计判断：该 ETF 跟踪的是 **Solactive 的定制指数**，与 `rules/benchmark.yaml` 里
   `includes_non_listed_assets: true` / `non_listed_assets.disclosure_state: undisclosed` 的设定**方向一致**。
   ★ 也印证 `N3.4-07`（"净值仅标 `diagnostic`"）：**市价（westock `44.92`）与净值（iFinD `45.03`）本就是两个不同的量**，
   设计要求区分它们是对的。

### 一个使用注意（自然语言接口的固有弱点）

第 2 项 vs 第 3 项说明：**同一个工具，query 写法不同，参数解析结果不同**。
- ✗ "三种复权方式" → 被解析成两列、且**都退化为不复权**
- ✓ "**后复权**收盘价" → 正确落到 `复权方式: 后复权`

⇒ **一次只指定一个复权口径**，并且**回读 `indicators_params` 确认工具真的按你要的口径查了**
（`indicators_params` 是这套自然语言接口的**自证字段**，务必逐次核对）。

---

## 四之二、★ 三源能力互补图（15:2x 实测汇总）

**没有任何单一源能全覆盖。** 现状（✅ 有 / ❌ 无 / ❓ 未测）：

| 数据项 | westock（在册） | iFinD（在册） | tdx（**不在册**） |
|---|---|---|---|
| AGIX **市场价** | ✅ `44.92` | ❌ 空 | ✅ `44.92` |
| AGIX **日 K 线** | ✅ | ❌ | ✅（三口径可区分） |
| AGIX **单位净值** | ❌ 空壳（`nav:0`） | ✅ **`45.03`** | ❓ |
| AGIX **跟踪指数** | ❌ 空串 | ✅ **Solactive Etna…** | ❓ |
| AGIX **分红** | ❌ | ❌ 空 | ✅ 2 条 |
| AGIX **拆股** | ❌ | ❌ 空 | ✅ 0 行（真实空） |
| NVDA **复权口径** | ❌ 只有单一已调整口径 | ✅ **后复权可指定** | ✅ 三口径可区分 |
| NVDA **分红/拆股** | ❌ | ❌ 空 | ✅ 12 条 + 1 条 |
| **延迟分钟数** | ❌ | ❓ | ✅ `DelayHQMin:15` |

⇒ **缺口 1**：`iFinD`（在册）可解 ✅
⇒ **缺口 2**：只有 `tdx` 实测有 —— 而它**不在册**（见 §三之二 路线②）

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

## 九、动作清单（**15:3x 最终版**）

| 优先级 | 动作 | 性质 | 阻断谁 |
|---|---|---|---|
| **P0** | **缺口 1 已解决**：用 iFinD 取复权序列（**在册源，无审批**）。★ 每次回读 `indicators_params` 核对口径 | 我已验证 / 落库时用 | 缺口 1 |
| **P0** | ★ **决策：缺口 2 走哪条路** —— ①按 `N6.1-13` 变更审批把 **`tdx` 补进白名单**（它实测有公司行动）② 用 WebFetch 人工取（保底）③ 暂缓 | **你决策** | 缺口 2；`T11`（有效价/公司行动） |
| **P0** | 向 pandadata 侧确认账号为何**整体无数据权限**（连交易日历都拒）→ 开不了则按 `N9.3-07` 如实标注该来源"不可用" | 你去问 / 我改登记 | `N9.3-07` 备选来源 |
| **P0** | 写"行情 → `facts/prices.jsonl` / `benchmarks.jsonl`"落库脚本（★ 现在三源数据都验证可取，**这是最后的堵点**） | 我做 | ★ **`batch 0` 的实质工作** |
| **P1** | 落库时用 iFinD 补 AGIX 的**净值 `45.03`** 与**跟踪指数名**（westock 空壳的那两项） | 我做 | `benchmarks` 表的覆盖率字段 |
| **P2** | 可选的保底：WebSearch/WebFetch 取 AGIX 公开分红记录（在册能力，不可批量） | 我做 | 缺口 2 的兜底 |
| — | 不动 `agent-mail` / `github` | — | — |

### 一句话（15:3x 最终）

> **三个在册源：`westock` ✅ 可用 · `iFinD` ✅ 已就绪（已购月度账号）· `pandadata` ❌ 账号整体无数据权限。**
> **缺口 1（复权口径）已用 `iFinD` 解决 —— 在册源，不需任何审批。**
> **缺口 2（公司行动）`iFinD` 给不了**（美股+基金、分红+拆股全空）⇒ **只剩 `tdx`（不在册，需你批准补登记）或 WebFetch 保底**。
> ★ 三源**能力互补**（见 §四之二），没有任何单点能全覆盖 —— 这本身就是"备选来源"（`N9.3-07`）该有的样子。
> 而无论缺口怎么解，**`batch 0` 都仍要先写落库脚本** —— 否则 `prices` / `benchmarks` 还是 0 行。
