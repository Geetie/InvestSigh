# 开发规范（`system/` 代码区）

> **性质**：本文件是**代码区的开发规范**，补充 `00_开发Agent开工提示词.md`（任务书）与
> `00_交付施工图.md §8`（施工纪律 12 条）。**设计区（`00_*` 与 `01_`~`11_`）只读，本文件不改设计。**
>
> **本项目的铁律（贯穿全部条目）**：**"声明"与"实现"必须有机器绑定**。
> 任何只写在文档里、没有检查器强制的规范，都等于不存在 ——
> 实测教训：手工台账能被**一行数据编辑**绕过（见 `reports/phase1_gap_register.md::D-9`）。
> 故本文件**每条规范都标注它的强制手段**；标 `⚠️ 人工` 的条目表示当前尚无机器绑定，属已知弱点。

---

## 一、验证规范（V 系列）★ 最高优先级

### V-01 禁止「一条命令全量验证」

**规范**：**不得**用一条命令跑完整个测试套件 + 全部门禁 + 阶段判据。
必须**分批**，每批一个独立子进程。

**为什么**（实测故障）：旧版 `verify.py` 把 `pytest tests`（全量）+ 19 项门禁 + 阶段判据
塞进**一条命令、一个超时**。任一处卡住 ⇒ **整条命令零输出、退出码只剩 `137`（SIGTERM）**，
既看不出卡在哪一批，也拿不到任何证据。**定位成本远高于分批的执行成本。**

**强制手段**：`scripts/checks/verification_policy_guard.py` 断言
① `verify.py` 不带 `--batch` 时必须 **exit 2**（拒绝隐式全量）；
② **不存在**任何 pytest 批次以裸 `tests` 为目标的"全量批次"。

**正确用法**：
```bash
python system/scripts/ops/verify.py --list                      # 看批次与超时
python system/scripts/ops/verify.py --batch <名>                # 一次一批（推荐）
python system/scripts/ops/verify.py --batch all                 # 逐批跑，超时即停
```

### V-02 每批必须设定**适合的**超时时间

**规范**：每个批次必须带独立的超时上限，取值约为**该批实测典型耗时的 8~30 倍** ——
宽到不会因偶发抖动误报，紧到能在"真的卡住"时**快速暴露**。

**为什么**：超时值就是**故障探测器**。设得过宽（如统一 600s），卡死就退化成"跑得慢"，
又回到 V-01 的老问题。

**强制手段**：守卫断言每批 `timeout > 0` 且 `<= 300s`，且 `BATCHES` 与 `ORDER` 键集合一致。

**当前批次表**（超时随实测更新，更新须同步守卫上限）：

| 批次 | 内容 | 超时 | 实测 |
|---|---|---|---|
| `unit` | `tests/unit/` | 60s | 1.5s |
| `conflict` | `tests/conflict/` | 30s | 0.4s |
| `guards` | `tests/guards/` | 60s | 1.9s |
| `injection` | `tests/injection/` | 120s | 13.3s |
| `root` | `tests/test_ch11_invariants.py` | 30s | 0.4s |
| `gates` | `run_all_gates.py`（19 项门禁） | 60s | 4.0s |
| `stage` | `stage_gate.py --stage all` | 30s | 0.3s |

### V-03 **超时 = 该批有问题**，且**绝不算通过**

**规范**：批次超时必须判定为**不合格**，并按下列优先级归因：

1. **极大概率是测试本身的问题**（死循环 / 竞态 / 环境依赖 / 资源累积）；
2. 其次是被测代码卡住；
3. **不是**"跑得慢"，不得以"延长超时"了事 —— 延长前必须先找出卡点。

**强制手段**：守卫断言超时码 `124` 经批次判定函数后**必然返回不合格**（含"超时"字样），
**不存在**把 `124` 当放行的路径。

**排查方法**（分批 + 二分 + 抓栈，实测有效）：
```bash
python system/scripts/ops/verify.py --batch <名>                       # 1. 确认哪一批超时
sh system/scripts/ops/run_pytest.sh tests/<批>/某文件.py -v > /tmp/x.log 2>&1   # 2. 缩到单文件
# 3. 卡在用例之间且位置漂移 ⇒ 累积型问题（本批次的真实案例）
# 4. 用 faulthandler 抓栈，精确定位：
python -m pytest tests/<批> -q -p no:cacheprovider -o faulthandler_timeout=15
```

### V-04 验证必须**在沙箱外**跑（Python 层 broker 必须关）

**规范**：跑测试/门禁必须关闭 Python 层的 FS broker hook。

**为什么**（实测故障）：WorkBuddy 的 `sitecustomize.py` shim 把**每一次文件操作**
brokered 到宿主进程走 IPC：

```python
_IN_SANDBOX               = os.environ.get("CODEBUDDY_SAFE_DELETE_SANDBOX") == "1"
_BROKERED_FS_HOOK_ENABLED = os.environ.get("CODEBUDDY_BROKERED_FS_HOOK_ENABLED") == "1" or _IN_SANDBOX
```

**Bash 工具的沙箱开关关不掉它**（它在解释器层）。后果：测试夹具每用例 `copytree`
复制 130 个文件 ⇒ 每用例数百次 IPC ⇒ 数百用例累积**数万次**往返 ⇒
**broker 阻塞、进程卡死且卡点漂移**（实测卡在第 15/17/19 条不等，`exit 137`、零输出）。

**实测对照**：broker **开 → 卡死**；broker **关 → 12 次 copytree 每次 0.026s，12/12 全过**。

**强制手段**：守卫断言 `run_pytest.sh` 与 `verify.py` **都**把两个环境变量置 `0`；
`conftest.py::pytest_sessionstart` 在检测到 broker 启用时打印响亮警告。

**正确用法**：
```bash
sh system/scripts/ops/run_pytest.sh tests/<子目录>     # 直接跑 pytest 的唯一正确入口
python system/scripts/ops/verify.py --batch <名>       # 已内置同一环境修正
```

### V-05 验证**严格串行**，且必须**留档**

**规范**：不得并行跑两个 pytest；每批输出必须落盘。

**为什么**：`tests/conftest.py::pytest_sessionstart` 会整目录清理 `tests/.work/` ——
并行会话会**互删夹具**，产生不可复现的偶发失败。

**强制手段**：⚠️ **人工**（守卫无法可靠检测并发进程）。

**留档约定**：`verify.py` 自动写 `reports/verify_<批次>_latest.log`（每批保留最近 3 份）。
**引用证据一律读该文件，不必重跑。**

### V-06 新增测试目录必须同时新增批次

**规范**：在 `tests/` 下新增**子目录**时，必须同时在 `verify.py::BATCHES` 里加一个批次。

**为什么**：否则新测试**永远不被验证到** —— 而"没被跑"与"跑过且没问题"在报告里长得一样。

**强制手段**：守卫断言 **`tests/` 下每个含测试文件的子目录都有对应批次**
（`tests/*/` 逐目录核对 `BATCHES` 的 pytest 目标）。

---

## 二、守卫与检查器规范（G 系列）

| # | 规范 | 强制手段 |
|---|---|---|
| **G-01** | **命中即 fail，禁 warn-only**；退出码 `0` 放行 / `1` 阻断 / `2` 输入异常 | 各守卫统一走 `_common.run_checker`；`tests/guards/test_exit_code_contract.py` 逐守卫断言 |
| **G-02** | **"X 调用了 Y"必须函数体级 AST 绑定**，禁止全文件字符串匹配（否则一行数据即可绕过） | `tests/injection/test_audit_regressions.py` + 各守卫自查；例：`injection_guard._body_calls()` |
| **G-03** | **不得把"无被检对象"当"已验证"**：空样本必须显式记 `note` | 各守卫 `note` + `tests/injection/test_wiring_guards.py` |
| **G-04** | **注释与 docstring 在扫描前抹白**，否则"描述规则的文字"会被规则自己判成违例。<br>★ **但普通字符串字面量必须保留** —— 有些规则的检测对象**就是字符串**（`FAKE_DATA` / `DEMO_TALK` / `HARDCODED_FALLBACK`）。**抹白过头 = 把探测器一起抹掉**（实测 `D-4`：三条规则曾永不命中，正是 `§一 底线 1` 的第一类假交付） | `no_placeholder_guard.strip_comments_and_docstrings()`（逐行规则）+ `strip_comments_and_strings()`（跨行规则）+ 双向对照测试 |
| **G-05** | **降噪就是有效性 —— 宁可漏报不可吵**：每条拦截判据必须配**反向对照** | 注入测试一律成对（正向 + 反向） |
| **G-06** | **唯一真源**：不得出现第二条同类校验路径（如第二套 `rules/` hash 校验） | `tests/injection/test_audit_regressions.py` |
| **G-07** | 每新增守卫必须**同时**注册进 `run_all_gates.py` 与 `pre-commit.sh`（防孤儿） | 守卫注册在跑测器里可核对 |

## 三、性能与进程卫生规范（P 系列）

| # | 规范 | 实测依据 |
|---|---|---|
| **P-01** | 全树/AST 扫描**单遍**；**禁止**"对每个被访问节点再 `ast.walk`"（O(n²)） | `D-19`：`check_L2` 曾 4.57s→8.4s，单遍后 0.52s |
| **P-02** | 配置读取一律走 `_common._cached_yaml()`（键含 mtime/size），禁止循环内直接读盘 | `D-20`：曾每函数重解析 YAML 数千次 |
| **P-03** | 包 `__init__` **惰性导入**（PEP 562）；守卫**不得**在模块级急切导入 pydantic | `D-21`：pydantic ≈0.3s/次，曾拖慢每个守卫 |
| **P-04** | 带全局副作用的加载器必须 `try/finally` 恢复 `sys.path` / `sys.modules` | `D-23`：曾致进程内测试 16 条集体失败 |
| **P-05** | 新守卫单次耗时 **< 0.5s**（门禁在 pre-commit 里跑，慢门禁会被关掉） | 实测基线 |

## 四、引用与文档规范（R 系列）

| # | 规范 |
|---|---|
| **R-01** | 跨文件引用**一律节号锚点**（`Ch9 §3.4.6`），**禁绝对行号** |
| **R-02** | docstring **只写代码做到的事**；声称了却没做 = `D-15` 类缺陷 |
| **R-03** | 空样本 / 降级 / 阻断必须带**显式 note 前缀**（如 `NO_RAW_EXTERNAL_TEXT`） |
| **R-04** | 设计未写的一律**不新增**；有歧义 → 写进「待明确」并**上报**，不自行裁决 |
| **R-05** | 设计区（`00_*` + `01_`~`11_`）**只读**；提交一律 `git add system/`，**禁用** `git add -A` |

---

## 附：本规范的强制手段总览

| 规范 | 强制手段 |
|---|---|
| V-01 / V-02 / V-03 / V-04 / V-06 | `scripts/checks/verification_policy_guard.py`（进 `run_all_gates.py` + `pre-commit.sh`）+ `tests/guards/test_verification_policy.py` |
| V-05 | ⚠️ 人工（并发不可靠检测）；留档由 `verify.py` 自动完成 |
| G-01~G-07 / P-01~P-05 | `tests/guards/` 与 `tests/injection/` 的既有断言 + 各守卫自查 |
| R-01 / R-02 | `tests/injection/test_guards_reject.py` + 各守卫 docstring 自检 |
