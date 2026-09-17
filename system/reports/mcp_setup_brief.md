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

| # | MCP | 白名单 | 宿主实况 | 实测结论（14:40 状态） |
|---|---|---|---|---|
| 1 | **westock**（腾讯自选股） | ✅ 在册 | ✅ 已连 | ✅ **可用**（见 §二；14:40 复测仍正常：NVDA `213.9`） |
| 2 | **pandadata**（PandaData） | ✅ 在册 | ⚠️ 已连 `bound:true`，但**认证已掉** | ❌ **当前 `unauthorized`**（见 §三-B；14:2x 时曾为"无数据权限"`200103`，见 §三-A） |
| 3 | **iFinD**（同花顺） | ✅ 在册 | ⏳ **14:30 授权成功**（`bound:true` + `Authorization` 已写入） | ⏳ **本会话载不到其工具** ⇒ **需新开一轮会话**再实测（见 §四） |

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

### ★ 另一处缺口：基准「含分红再投资」无数据

`rules/benchmark.yaml::return_basis.dividends_reinvested: true`（AGIX 主基准要求总回报口径）。
但 westock 只给 `dividend_ttm` / `dividend_ratio_ttm`（**汇总值**），**无分红事件表**（除权日 / 金额 / 拆股比率）
⇒ `registry/corporate-actions.jsonl` 目前 **0 字节**，无自动填充方。

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

### §三-D 处置（按顺序做）

1. **先重新连接/授权 pandadata**（连接器管理页），让宿主重新写入 Authorization。
2. 重连后**立刻验证**：
   ```bash
   # 期望：不再 unauthorized。若回到 200103 ⇒ 进入第 3 步
   grep -A3 '"pandadata"' ~/.workbuddy/connectors/*/connector-states.json
   ```
3. **若回到 `200103`** ⇒ 那是**第二层、与授权无关**的问题（账号套餐对该数据集无权限），须去 pandadata 侧确认能否开通；
   开不了就按 `N9.3-07` 在 `registry/sources.yaml` 如实标注"不可用"（**不许留空装成"有备选"**）。
4. **待补测**（把举证半径补全）：重连后逐个类别各测一个方法 ——
   `get_trade_cal`（日历）/ `get_stock_detail`（A股基础）/ `get_index_detail`（指数）/ `get_fina_reports`（财务），
   以确定"无权限"是**全库**还是**仅美股类**。

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

### ★ 结论：工具列表在**会话启动时**固定 ⇒ 需要**新开一轮会话**

`connector-states` 与 `Authorization` 都已就位（**宿主侧连接成功**），但 **WorkBuddy 的 MCP 工具是在会话开始时载入的**，
本会话（14:25 启动）载不到 14:30 才绑定的 iFinD。⇒ **新开一个会话**（或重启 WorkBuddy）后 iFinD 工具才会出现。

### 新会话里第一件要做的事：实测 iFinD（别只看"已连接"）

```text
# 在**新会话**里，让 AI 依次做这三步，并把原始返回贴出来：
1) 列出 iFinD 提供的工具名（确认工具真的载入了）
2) 用 iFinD 取 usNVDA.OQ（或 NVDA）的**日线**与**行情快照**
3) 用 iFinD 取 usAGIX.OQ（KraneShares 人工智能 ETF）的**行情**与**持仓/净值**
```
**重点看两件**：① 美股 / ETF 是否覆盖；② **有没有"分红、拆股、复权因子"这类公司行动数据**
（`N9.3-08` 的 P0 需求；正是 §二 里 westock 缺的那块）。

⚠️ pandadata 就是活证据 —— **"连上" ≠ "能用"**。iFinD 装完必须实测。

---

## 五、不在册但已连的 3 个：要不要处理

| 已连 | 在册？ | 实测 | 处置建议 |
|---|---|---|---|
| **tdx-connector**（通达信） | ❌ **不在白名单** | ✅ **能取美股**：`tdx_lookup_stock(query="英伟达", range="MG-GP")` → `NVDA / setcode=74`；`tdx_quotes(code="NVDA", setcode="74")` → `213.9`，**并显式暴露 `DelayHQMin: 15`**（延迟分钟数） | 它实测是三者中**唯一提供"延迟分钟数"字段**的源（直接支撑 `PriceSnapshot.delayed` 与 T13）。但按 `N6.1-13` + `Ch6 §I.1`「allowlist + 变更审批」，**要用它落库须先补登记**（照 `allowlist` 里 westock 那三行格式加，并同步 `launch_criteria.yaml::available_sources`）。**若只作一次性人工核对、不落库，则不需改**（但需在试验记录里注明来源） |
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

## 九、动作清单（14:40 更新版）

| 优先级 | 动作 | 性质 | 阻断谁 |
|---|---|---|---|
| **P0** | **重新连接 pandadata** → 观察 `headerOverrides` 是否重新出现 `pandadata`（证伪/证实 §三-C 的假设） | 你在连接器页点一下 | 现状：`unauthorized`，**完全不可用** |
| **P0** | 重连后**立刻实测**：若仍 `200103` ⇒ 转「向 pandadata 确认数据权限」（与授权无关的第二层问题） | 我测 / 你去问 | `N9.3-07` 备选来源；公司行动数据面 |
| **P0** | **新开一个会话**，让 iFinD 工具载入，然后按 §四 的三步实测 | 你操作 / 我测 | 备选来源；第三腿 |
| **P1** | 决定 tdx 是否入册（要用它落库就必须补 `allowlist` + `launch_criteria`） | **你决策** | 不阻断测试，但影响"延迟口径"能否用 |
| **P1** | 写"行情 → `facts/prices.jsonl` / `benchmarks.jsonl`"落库脚本 | 我做 | ★ **`batch 0` 的实质工作** |
| — | 不动 `agent-mail` / `github` | — | — |

### 一句话

> **在册的 3 个源，此刻的真实状态是**：`westock` ✅ 可用 · `pandadata` ❌ 掉线（先重连，再看是不是卡在"无数据权限"）·
> `iFinD` ⏳ 已授权成功但**本会话载不到**，**新开一轮**才能测。
> 别的金融连接器（wind / tushare / 大智慧 / 东财妙想 …）**市场里有很多，但一个都不要加** ——
> D-01 白名单只认这三个，加别的要先走 `N6.1-13` 变更审批。
> 而即便三个全绿，**`batch 0` 仍要先写落库脚本**，否则 `prices` / `benchmarks` 还是 0 行。
