#!/bin/sh
# 施工纪律门禁（`施工图 §8` 纪律 2/4/12 · `Ch2 §B.4` pre_commit 时机）
#
# 用法：由 `.git/hooks/pre-commit` 薄壳调用（安装方式见 `install_hooks.sh`）。
# 也可手动跑：`sh system/scripts/ops/pre-commit.sh`
#
# 为什么门禁放在 pre-commit 而不是"靠自觉"：
#   纪律 4 的手段**就是** pre-commit 拒改既有行（`Ch9 §3.4.2`）——
#   不装钩子，追加式不可变就只是一句口号（= 假交付第 2 类：接线失败）。
#
# ★ 一律 `exit 非零`，禁 warn-only（纪律 2）。
#
# ★★ **退出码契约**（`CONVENTIONS.md G-01`：`0` 放行 / `1` **违规** / `2` **输入错误**）：
#   本文件里凡"**无法确定被检对象/无法进入被检树**"的前置失败一律 `exit 2` ——
#   它们不是"你改坏了"，而是"**判据与对象不同源**"（缺 `G-61`）。
#   卡 13-O 已把 `run_gate` 的"门禁脚本不在被检树"改成 `2`；本卡（`#96`）补齐
#   **"根/环境不明"这一族共五处**（三处根解析 + `cd` 进不去被检树 + 解释器不可用），
#   使**同一次提交里的输入错误只有一个码**。★ 后两处是主理人在 `#96` 裁定里扩的范围：
#   "半清空不是收口" —— 只改三处会让本卡要消除的缺陷**只消除一半**。
#   ★ 调用点已枚举（`#96`）：① `.git/hooks/pre-commit` 薄壳（`exec sh`；git 只区分"零/非零"，
#     **不解释 1 与 2 的区别**）② 人工 `sh system/scripts/ops/pre-commit.sh`
#     ③ `tests/guards/*` 两条测试 ④ `install_hooks.sh --check`（只读内容、不看退出码）。
#   ⇒ 无任何调用方依赖"非零即违规"这一具体码值，本改动**不改变任何调用方的行为**；
#     新增的读者是**人**（诊断）与**测试**（契约）。

set -u

# ★★ 卡 `#96` §③（缺口 `G-65` 的可见性修复）之前，先修一处**我自己在 13-O 写下的静默缺陷**：
#   `$0` **必须先钉成绝对路径** —— 本文件后面会 `cd "$REPO_ROOT"`，
#   若调用方式是相对路径（`cd system/scripts/ops && sh pre-commit.sh`），相对 `$0` 就再也解不开：
#   `done < "$0"` 的重定向**失败** ⇒ **整个 while 循环体一次都不执行** ⇒ `_gate_count` 静默停在 `0`，
#   而脚本**照常 `exit 0`**、报"全部门禁放行"。
#   实测（2026-09-17，本树 `0582804`，cwd=`system/scripts/ops`）：
#       $ sh pre-commit.sh
#       pre-commit.sh: line 129: pre-commit.sh: No such file or directory
#       pre-commit: 判据树 HEAD=0582804 · 本树门禁 0 道 · 判据=pre-commit.sh
#       …（14 道**确实都跑了**）…   pre-commit ✓ 全部门禁放行     ⇒ rc=0
#   ⇒ 13-O 那行"可见性输出"**当场报了个假数**，而假数比不报更坏（`G-03`：`0 道` ≠ 没门禁）。
#   ★ 这是"判据用了相对路径，而对象在 `cd` 之后"的同族第三例（前两例见 `run_gate` 的载荷约定）。
_SELF="$0"
case "${_SELF}" in
  /*) ;;
  *) _SELF="$(cd "$(dirname "${_SELF}")" 2>/dev/null && pwd)/$(basename "${_SELF}")" ;;
esac

# ★★ 问根之前**必须摘掉 `GIT_DIR`**（与 `append_only_guard` 那处**同一根因**，实测过）：
#   在 git 钩子里 `GIT_DIR` 是**已导出**的；此时**不带** `GIT_WORK_TREE` 的
#   `git rev-parse --show-toplevel` **不查仓库、直接把 cwd 当工作树根**返回。
#   后果：**从子目录提交**时 `REPO_ROOT` 会算成那个子目录 ⇒ `CODE_ROOT` 指错 ⇒
#   各门要么扫不到对象、要么找不到 `rules/`。
#   （`append_only_guard` 已经在 linked worktree 上因此**恒空放行**过 —— 纪律 4 静默失效。
#     本处是同一根因的第二个落点。）
#   → 摘掉 `GIT_DIR`/`GIT_WORK_TREE`/`GIT_PREFIX`，让 git 从 cwd **向上**发现仓库；
#     ★ 但**保留 `GIT_INDEX_FILE`** —— 它指向**本工作树自己的索引**，摘了会读错暂存区。
REPO_ROOT="$(
  unset GIT_DIR GIT_WORK_TREE GIT_PREFIX
  git rev-parse --show-toplevel 2>/dev/null
)" || {
  echo "pre-commit [INPUT-ERROR] 无法定位仓库根（git rev-parse --show-toplevel 失败）" >&2
  echo "  ★ 这是**输入错误**（exit=2），**不是**违规：根不明 ⇒ 无从确定判据作用的对象。" >&2
  echo "  ★ 处置：在**某棵工作树内**执行（cwd 须能做仓库发现），或检查 .git 可读。" >&2
  exit 2
}
if [ -z "$REPO_ROOT" ]; then
  echo "pre-commit [INPUT-ERROR] 仓库根解析为空 —— 拒绝在根不明的情况下跑门禁" >&2
  echo "  ★ 这是**输入错误**（exit=2），**不是**违规（cwd=${PWD}）。" >&2
  echo "  ★ 处置：本文件预期由仓库内的 git 钩子或手工 'sh system/scripts/ops/pre-commit.sh' 调用。" >&2
  exit 2
fi
# ★ 分类（`G-01`）：`cd` 进不去被检树 ⇒ **输入错误**（`exit 2`），不是违规。
#   实测（2026-09-16，本树 HEAD=f014222）：`git` 给出一个不存在的根时，旧版只打 shell 的
#   `cd: … No such file or directory` 然后 `exit 1` ⇒ 提交者被告知"你改坏了"，而根因是环境/输入。
cd "$REPO_ROOT" || {
  echo "pre-commit [INPUT-ERROR] 无法进入仓库根：cd '${REPO_ROOT}' 失败" >&2
  echo "  ★ 这是**输入错误**（exit=2），**不是**违规：被检树进不去，与你的改动无关。" >&2
  echo "  ★ 处置：检查该路径是否存在/可进入（cwd=${PWD}），或本文件的调用方是否传了错误的环境。" >&2
  exit 2
}

# ★ 自检：根算错时**响亮失败**，不要让它退化成"所有门都扫不到对象而通过"。
#   这正是本项目反复对抗的形态：**没有可检对象 ≠ 已验证**（`G-03`）。
#   ★ 分类（`G-01`）：这是"**根解析可疑 ⇒ 没有可检对象**"，属**输入错误**（`exit 2`），
#     不是代码违规 —— 与 `run_gate` 的"门禁脚本不在被检树"同族（`#96`）。
if [ ! -d "$REPO_ROOT/system/scripts" ]; then
  echo "pre-commit [INPUT-ERROR] 根解析可疑 —— '${REPO_ROOT}/system/scripts' 不存在（cwd=${PWD}）" >&2
  echo "  ★ 这是**输入错误**（exit=2），**不是**违规：没有可检对象（G-03），不是你的改动有问题。" >&2
  echo "  ★ 处置：确认在**某棵工作树内**执行；若本文件被复制到别处，请从仓库内跑。" >&2
  exit 2
fi

# 解析 Python：优先环境变量，其次隔离 venv，最后退回 python3
#
# ★ 候选必须**同时覆盖两种 venv 布局**（2026-09-17 实测修复）：
#   POSIX 布局 = `<venv>/bin/python`；Windows 布局 = `<venv>/Scripts/python.exe`。
#   原先只列 POSIX 形式 ⇒ 在 Windows 上**全部候选都不命中** ⇒ 回落到 `python3`
#   （宿主 Python，**没有装 yaml/pydantic**）⇒ 所有走 `_common._cached_yaml()` 的门禁
#   一律 `ModuleNotFoundError: No module named 'yaml'` ⇒ **pre-commit 对每一次提交假红**。
#   而 `requirements.txt` 的抬头注释早已写明这一族症状（「看起来像代码坏了，其实是环境缺包」）——
#   区别只是那次是"手里没有清单"，这次是"有清单但解释器选错了"。
#   ★ 后果的严重性：**天天误报的门禁一定会被关掉**（`V-07`）⇒ 必然有人 `--no-verify` 绕过
#   ⇒ 纪律 9 的防线彻底失效。故必须在**解析层**根治，而不是让每个人 export 环境变量。
PY="${WORKBUDDY_PY:-}"
if [ -z "$PY" ]; then
  for cand in \
    "${HOME}/.workbuddy/binaries/python/envs/default/bin/python" \
    "${HOME}/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
    "${REPO_ROOT}/system/.venv/bin/python" \
    "${REPO_ROOT}/system/.venv/Scripts/python.exe" \
    python3
  do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
  done
fi
# ★ 分类（`G-01`）：**环境里没有可用解释器** ⇒ 输入错误（`exit 2`），不是违规。
if [ -z "$PY" ]; then
  echo "pre-commit [INPUT-ERROR] 找不到可用的 python（WORKBUDDY_PY 未设，三个候选都不在 PATH / 不存在）" >&2
  echo "  ★ 这是**输入错误**（exit=2），**不是**违规 —— 环境缺解释器，与你的改动无关。" >&2
  echo "  ★ 处置：export WORKBUDDY_PY=<解释器绝对路径>；或清空它让它回落到候选/python3。" >&2
  exit 2
fi
# ★★ 解释器还必须**真的可用**（`#96` 扩的两处之一）。放过它会怎样 —— **实测**（2026-09-16，
#   本树 HEAD=f014222，`WORKBUDDY_PY=/nonexistent/python`）：
#       pre-commit → append_only_guard
#       pre-commit.sh: line 131: /nonexistent/python: No such file or directory
#       …（共 14 次）…
#       pre-commit ✗ rule_key_alignment_guard 阻断（exit=127）
#       pre-commit: 有门禁阻断，提交被拒。        ⇒ rc=1
#   ⇒ **14 道门禁一道都没跑**，却全部被报成「阻断」= 把"环境错了"伪装成"你改坏了 14 道门禁"。
#     这与 `G-61`（`rc=2` 被报成阻断）是**同一族的第四种形态**，且**假指责面积最大**（14 条）。
#   ★ 判据用 `command -v` **或** `-x`：裸名（如 `python3`）只有前者成立，绝对路径两者皆可
#     —— 单用 `-x` 会把"在 PATH 上的 python3"误判成不可用（实测过）。
if ! command -v "$PY" >/dev/null 2>&1 && [ ! -x "$PY" ]; then
  echo "pre-commit [INPUT-ERROR] 解释器不可用：'${PY}'（既不在 PATH，也不是可执行文件）" >&2
  echo "  ★ 这是**输入错误**（exit=2），**不是**违规：环境里的解释器不可用，与你的改动无关。" >&2
  echo "  ★ 若放过它（实测）：14 道门禁**一道都没跑**，却全部被报成「阻断（exit=127）」" >&2
  echo "    ⇒ 把「环境错了」伪装成「你改坏了 14 道门禁」（与 G-61 同族，rc=127 形态）。" >&2
  echo "  ★ 处置：export WORKBUDDY_PY=<可用解释器路径>；或清空它让它回落到候选/python3。" >&2
  exit 2
fi

CODE_ROOT="$REPO_ROOT/system"
FAILED=0
# ★ 卡 13-O：把「输入错误」与「违规」分开记（`CONVENTIONS.md G-01`：`2`=输入异常 / `1`=违规）。
#   两者此前**被同款报成"阻断"** —— 见 `run_gate` 的注释。
INPUT_ERROR=0

# ★★ 卡 13-O §11 / 主理人裁定「要」：把**本次用的是哪份清单**留在现场（`口径 10`）。
#   方向②（判据**旧**于对象 ⇒ 静默少跑门禁）**完全不可观测** ⇒ 用**一行输出**换它一个可见性。
#   本树实测（2026-09-16）：32 棵工作树里 **20 棵**的清单比 `main` 短（最多短 6 道）
#   ⇒ 没有这一行，"本次只跑了 8 道"**谁都不会知道**；有它，拿 `main` 一比即知。
#   ★ 门禁数**由本文件自身派生**（不写死 —— 13-J 的纪律：写死计数会漂）。
#   ★ 用 `case` 扫行、**不用 grep**：本机 `grep` 是被 broker 影子化的 toybox 方言
#     （`CONVENTIONS.md V-10`）⇒ 取数脚手架**不得依赖方言**。
#   ★★ 取不到时必须说"**取不到**"，**不许报 0**：`0 道` 与"扫描没生效"是两件事，
#     报成 `0 道` 就是上面那处实测过的假数。
_gate_count=0
if [ -r "${_SELF}" ]; then
  while IFS= read -r _line; do
    case "${_line}" in
      run_gate\ \"*) _gate_count=$((_gate_count + 1)) ;;
    esac
  done < "${_SELF}"
fi
if [ "${_gate_count}" -gt 0 ]; then
  _gate_count_text="${_gate_count}"
else
  _gate_count_text="**取不到**（⚠ 不得当作 0）"
fi
#   ★ 问 HEAD 之前**同样**要摘 `GIT_DIR`（与第 15–23 行同一根因）：钩子里它是已导出的，
#     不摘会让 git 读**钩子注入的那个**仓库，而我们要的是 `$REPO_ROOT` 这棵树自己的 HEAD。
_tree_head="$(
  unset GIT_DIR GIT_WORK_TREE GIT_PREFIX
  git rev-parse --short HEAD 2>/dev/null
)" || _tree_head=""

# ★★ 卡 `#96` §③ / 缺口 `G-65`：把**两组门禁集合之差**变成机器可见（此前它**完全不可观测**）。
#   问题：`run_all_gates.py::GATES` 27 道 vs 本文件 14 道**不是同一集合**
#   ⇒ 有 13 道**只在集成时跑，红着也不挡提交**（`traceback.py` 就是活例：主干即红而提交照过）。
#   ★ **明确不做**：把 27 道塞进本文件 —— 那会让每次提交变慢，而"**卡死的门禁 = 被关掉的门禁**"；
#     且 `口径 16` 已定 pre-commit 不跑 pytest（13 道里的多数）。
#   ⇒ 只换一行**可见性**：差是多少、是哪些，读输出即知（`口径 10`：本次用的是哪份清单要留现场）。
#   ★ 取数**不许 grep**（`V-10`），且道数必须**派生**：
#     本树门禁数 = 上面 `case` 扫 `${_SELF}`；`run_all_gates` 侧 = **装载真源模块**取 `len(GATES)`
#     （不是文本扫 `GATES` —— 格式一变计数会静默漂，本文件上面刚实测过同族形态）。
#   ★ 派生器 `gate_set_diff.py` **永不阻断提交**（它是可见性工具，不是门禁）；取不到数时
#     输出"取不到"，**不报 0**。
_gate_sets="$( "$PY" "$CODE_ROOT/scripts/ops/gate_set_diff.py" \
  "$CODE_ROOT/scripts/ops/run_all_gates.py" "${_SELF}" "${_gate_count}" 2>/dev/null )" \
  || _gate_sets=""
if [ -z "${_gate_sets}" ]; then
  _gate_sets="run_all_gates 集合差**取不到**（⚠ 不得当作 0；派生器未产出）"
fi
echo "pre-commit: 判据树 HEAD=${_tree_head:-（无提交）} · 本树门禁 ${_gate_count_text} 道 · ${_gate_sets} · 判据=${_SELF}"

run_gate() {
  # ★★★ 载荷约定（**改动这里必看**）：调用点是 `run_gate <label> <script> <args…>`，
  #   而真正要执行的是 `"$PY" "$@"` —— 即 **`$@` 的首位必须是脚本路径**。
  #   ⇒ 先取 `$1`/`$2`，再 `shift 1` **只摘掉 label**。
  #   ★ 踩过两次，两次都被 `tests/guards/test_hook_same_source.py` 当场抓住：
  #     ① `shift 2` ⇒ 把**脚本路径**也摘掉了 ⇒ 每道门都失败；
  #     ② 忘了 `shift` ⇒ `$@` 首位是 **label** ⇒ `python <label> <script> …`
  #        ⇒ `can't open file '…/<label>'`（错误信息里出现的是**门禁名而不是路径**，很有迷惑性）。
  label="$1"; script="$2"; shift 1
  echo "pre-commit → ${label}"

  # ★★ 卡 13-O（缺口 `G-61`）：**先判"判据在不在被检树里"，再跑判据**。
  #   旧行为：脚本缺失时 `python` 报 `can't open file … [Errno 2]`，退出码 `2`，
  #   而下面那条分支把它与 `rc=1`（真违规）**同款报成"阻断"** ⇒ 提交者被告知"你改坏了"，
  #   实际原因是**判据与对象不同源**（清单比被检树新）。本批次实测 3 次、≥2 条流撞上。
  #   ⇒ 缺脚本 = **输入错误**（`exit 2`），**不写"阻断"**，且**一次性把处置写清**。
  if [ ! -f "${script}" ]; then
    echo "pre-commit [INPUT-ERROR] ${label}：门禁脚本不在被检树 —— ${script}" >&2
    echo "  ★ 这是**输入错误**（exit=2），**不是**违规：判据与对象不同源（缺 G-61）。" >&2
    echo "  ★ 被检树 REPO_ROOT=${REPO_ROOT}（cwd=${PWD}）；判据清单来自本树的 scripts/ops/pre-commit.sh。" >&2
    echo "  ★ 处置：在本树 \`git merge main\` 后重试。**不许** \`--no-verify\`（绕过门禁得到的绿不算证据）。" >&2
    INPUT_ERROR=1
    return 0
  fi

  "$PY" "$@" || {
    rc=$?
    # ★ 变量一律加花括号：`$rc` 紧跟全角括号 `）` 时，多字节首字节会被并进变量名
    #   → `set -u` 下报 `rc<乱码>: unbound variable`，脚本**当场中止**，
    #   于是 `FAILED=1` 没设上、**后续门禁（⑤–⑧）根本没跑**（实测踩到，已修）。
    if [ "${rc}" -eq 2 ]; then
      # ★ `2` = 判据自己的输入异常（`Ch2 §B.3`）⇒ **不是**"你改坏了"。
      echo "pre-commit [INPUT-ERROR] ${label}（exit=2）：判据报**输入异常**，不是违规" >&2
      INPUT_ERROR=1
    else
      echo "pre-commit ✗ ${label} 阻断（exit=${rc}）" >&2
      FAILED=1
    fi
  }
}

# ① 纪律 4：追加式不可变（拒改 facts/*.jsonl 既有行）
run_gate "append_only_guard" "$CODE_ROOT/scripts/checks/append_only_guard.py" "$CODE_ROOT"

# ② 纪律 9/10：rules/ 0444 + SHA256 锁（含校验方）
run_gate "rules_lock_guard" "$CODE_ROOT/scripts/checks/rules_lock_guard.py" "$CODE_ROOT"

# ③ 登记层真源结构（防 registry_models 落入孤儿模块，§一 底线 2）
run_gate "registry_schema_guard" "$CODE_ROOT/scripts/checks/registry_schema_guard.py" "$CODE_ROOT"

# ④ schema 生成物与 models.py 一致（防"改模型不改生成物"的假绿灯）
run_gate "schema_sync_guard" "$CODE_ROOT/scripts/checks/schema_sync_guard.py" "$CODE_ROOT"

# ⑤ Ch2 §B.4 pre_commit 时机：L1–L5 全量
run_gate "conflict_scan(L1-L5)" "$CODE_ROOT/scripts/checks/conflict_scan.py" "$CODE_ROOT" --timing pre_commit

# ⑥ N-2 反占位符（命中即 fail）
run_gate "no_placeholder_guard" "$CODE_ROOT/scripts/checks/no_placeholder_guard.py" "$CODE_ROOT" --fail-on warn

# ⑦ 注入防护：数据/指令分离执行器 + 效果断言守卫（`Ch9 §3.4.6`；命中即 fail）
run_gate "injection_guard" "$CODE_ROOT/scripts/checks/injection_guard.py" "$CODE_ROOT"

# ⑧ 验证规范：禁止全量验证 / 每批必带超时 / 超时不算通过 / 沙箱外跑（`CONVENTIONS.md §一`）
run_gate "verification_policy_guard" "$CODE_ROOT/scripts/checks/verification_policy_guard.py" "$CODE_ROOT"

# ⑨ shell 变量紧邻多字节字符（`$rc` 紧跟全角括号会被并名 → `set -u` 下**中止脚本**，
#    实测曾使本文件的后续 4 道门禁全部未执行 —— 一个门禁失败竟让别的门禁不被检查）
run_gate "shell_var_guard" "$CODE_ROOT/scripts/checks/shell_var_guard.py" "$CODE_ROOT"

# ⑩ 图结构完整性（命中即 fail）：自环 / 重复边 / 陈旧缓存（`Ch2 §B.3`）
run_gate "graph_integrity_guard" "$CODE_ROOT/scripts/graph/graph_integrity_guard.py" "$CODE_ROOT"

# ⑪ 判据有效性（缺口 G9）：**每条已绑定判据必须有可执行反例** ——
#    绑定只证明"接了"，不证明"真的在查"（把 coverage_check 换成空实现，绑定数不变而门禁变绿）。
run_gate "criterion_effectiveness_guard" "$CODE_ROOT/scripts/checks/criterion_effectiveness_guard.py" "$CODE_ROOT"

# ⑫ 反编造：每条 claim 的 quote_hash 必须等于其 locator 所指 raw/ 区间的 sha256
#    （缺口 `G-B10-05` —— `locator_check` 判据 4/5 只覆盖 full_text_read=true 那支，
#      `false` 那支此前无任何"引文↔原文"机械校验。命中即 fail，禁 warn-only。）
run_gate "quote_provenance_guard" "$CODE_ROOT/scripts/checks/quote_provenance_guard.py" "$CODE_ROOT"
# ⑬ 跨载体绑定（缺口 G-55）：`rules/scenario.yaml` 的取值域 ↔ 实现侧枚举 ——
#    两侧值相同、各自自洽，**只改一侧不会红** ⇒ 漂移可以无限期存在。
#    ★ 必须与 `run_all_gates.py::GATES` **同时**登记（`G-07`）：只进一处 = "提交时放行、CI 时拦"（或反之），
#      两处口径不一致本身就是同一族的缺陷。
run_gate "scenario_tag_binding_guard" "$CODE_ROOT/scripts/checks/scenario_tag_binding_guard.py" "$CODE_ROOT"

# ⑭ 键对齐（批次 13-pre 方向 1）：**代码读的 `rules/` 键必须存在** ——
#    `dict.get()` 读一个不存在的键时静默返回 `None`，被 `or ""` 洗成"看起来合法"的值，
#    于是"这条规则其实没被读"在**任何输出里都不可见**。
#    两条断言：① 代码引用的规则文件必须存在；② 代码读的键必须在实有键里。
#    ★ 与 `run_all_gates.py::GATES` **同时**登记（`G-07`）。
#
# ⑭′ 同一道门禁还含**方向 2**（`WS-D` / 张力 `T-18`）：**`rules/` 声明的记录列必须有消费者** ——
#    `rules/` 里声明了语义、`scripts/**` 却零消费者 ⇒ 该声明**在机器上零效力**（死列）。
#    域 = 记录集合 × 列（纯遍历 YAML）；消费者 = `scripts/**` 的**非 docstring 字符串字面量**；
#    未登记的无消费者列 ⇒ **命中即 fail**（`G-01`）。方向 1 与方向 2 **共用本脚本**，故本行
#    与 `run_all_gates.py::GATES` 的同一行**一次覆盖两个方向**（`G-07`：两处必须一致）。
run_gate "rule_key_alignment_guard" "$CODE_ROOT/scripts/checks/rule_key_alignment_guard.py" "$CODE_ROOT"

# ⑮ 复盘标记字段不得进入决策函数（`Ch10 §C.1` / `10_02 §G.1`；`S-07`）：
#    `eval_layer` / `error_axis` / `error_axis_note` 是**复盘标记**，**不进决策函数** ——
#    此前只写在文档里，把它们接进 `scripts/decision/**` 没有任何门禁会响。
#    域 = `rules/banned_tokens.yaml::decision_scope` 枚举出的作用域（allowlist，`R-06`）；
#    判据 = 「决策函数体里是否出现这三个标记名」（标识符/属性/字符串键/形参/关键字实参，函数体级 AST，`G-02`）。
#    ★ 与 `run_all_gates.py::GATES` **同时**登记（`G-07`）。
run_gate "error_axis_guard" "$CODE_ROOT/scripts/checks/error_axis_guard.py" "$CODE_ROOT"

# ★ 卡 13-O：先把「输入错误」结掉 —— 它比违规更该先说（`2`：门禁没跑全，结论不成立）。
#   两者同时出现时**两条都报**，仍以 `exit 2` 结束：此时"跑了哪些、没跑哪些"本身不可信。
if [ "${INPUT_ERROR}" -ne 0 ]; then
  if [ "${FAILED}" -ne 0 ]; then
    echo "pre-commit: 另有门禁**阻断**（见上）—— 但因存在输入错误，本次结论**不成立**。" >&2
  fi
  # ★ 注意：这里**不许**出现未转义的反引号 —— 它是**命令替换**。
  #   我第一版写成 ``…判据与对象不同源，\`G-61\`）`` 时漏了转义 ⇒ shell 去执行 `G-61`
  #   ⇒ `line 161: G-61: command not found`，而 **echo 仍打印出一行"看起来正常"的话**
  #   （那个词被静默吞成空）⇒ 又一个**静默失败**（`G-62` 第 4 型：失败通道）。
  echo "pre-commit: [INPUT-ERROR] 有门禁脚本不在被检树 —— 这是**输入错误**，不是违规（exit=2；判据与对象不同源，缺口 G-61）。" >&2
  echo "pre-commit: 处置：在本树执行 git merge main 后重试。" >&2
  exit 2
fi

if [ "$FAILED" -ne 0 ]; then
  echo "pre-commit: 有门禁阻断，提交被拒。" >&2
  exit 1
fi
echo "pre-commit ✓ 全部门禁放行"
exit 0
