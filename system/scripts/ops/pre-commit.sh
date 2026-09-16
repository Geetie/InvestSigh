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

set -u

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
  echo "pre-commit: 无法定位仓库根（git rev-parse 失败）" >&2
  exit 1
}
if [ -z "$REPO_ROOT" ]; then
  echo "pre-commit: 仓库根解析为空 —— 拒绝在根不明的情况下跑门禁" >&2
  exit 1
fi
cd "$REPO_ROOT" || exit 1

# ★ 自检：根算错时**响亮失败**，不要让它退化成"所有门都扫不到对象而通过"。
#   这正是本项目反复对抗的形态：**没有可检对象 ≠ 已验证**（`G-03`）。
if [ ! -d "$REPO_ROOT/system/scripts" ]; then
  echo "pre-commit: 根解析可疑 —— '${REPO_ROOT}/system/scripts' 不存在（cwd=${PWD}）" >&2
  exit 1
fi

# 解析 Python：优先环境变量，其次隔离 venv，最后退回 python3
PY="${WORKBUDDY_PY:-}"
if [ -z "$PY" ]; then
  for cand in \
    "$HOME/.workbuddy/binaries/python/envs/default/bin/python" \
    "$REPO_ROOT/system/.venv/bin/python" \
    python3
  do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
  done
fi
if [ -z "$PY" ]; then
  echo "pre-commit: 找不到可用的 python" >&2
  exit 1
fi

CODE_ROOT="$REPO_ROOT/system"
FAILED=0

run_gate() {
  label="$1"; shift
  echo "pre-commit → ${label}"
  "$PY" "$@" || {
    rc=$?
    # ★ 变量一律加花括号：`$rc` 紧跟全角括号 `）` 时，多字节首字节会被并进变量名
    #   → `set -u` 下报 `rc<乱码>: unbound variable`，脚本**当场中止**，
    #   于是 `FAILED=1` 没设上、**后续门禁（⑤–⑧）根本没跑**（实测踩到，已修）。
    echo "pre-commit ✗ ${label} 阻断（exit=${rc}）" >&2
    FAILED=1
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

if [ "$FAILED" -ne 0 ]; then
  echo "pre-commit: 有门禁阻断，提交被拒。" >&2
  exit 1
fi
echo "pre-commit ✓ 全部门禁放行"
exit 0
