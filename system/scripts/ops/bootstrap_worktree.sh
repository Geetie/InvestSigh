#!/bin/sh
# `bootstrap_worktree.sh` —— **新建工作树后的必做第一步**：复原 `rules/` 的 0444。
#
# ```
# sh system/scripts/ops/bootstrap_worktree.sh
# ```
#
# ## 为什么必须单独做（系统性伪影，不是谁的代码错）
#
# 纪律 9 要求 `rules/` 下全部 `0444`（模型对规则无写权，纪律 10）。但
# **git 只跟踪可执行位，不跟踪只读位** —— 于是 `git worktree add` / 新 clone
# checkout 出来的 `rules/*.yaml` 一律是 `0644`，`rules_lock_guard` **必红**。
#
# 实例：`fix/claim-propagation` 与 `fix/compute-silent-defects` 两个工作树首次提交时
# 都被 `rules_lock_guard` 拦下，报 10 条「权限为 0o644，应为 0o444」。
#
# **天天误报的门禁一定会被关掉**（`CONVENTIONS.md §二 G-01`）——
# 所以必须在流程层根治，而不是让每个工程师各自 `chmod`。
#
# ## 本脚本**只**做一件事（边界从严）
#
# 1. 把 `rules/` 下的 `*.yaml` / `*.yml` / `*.json` 置为 `0444`。
# 2. 自检 `rules_lock_guard` 并把结论打印出来。
#
# **不做**（刻意的）：
# - **不碰任何文件内容**（内容改动是被禁的：`rules/` 属设计真相源）；
# - **不碰 `registry/rules.lock.json`** —— 那是**被 git 跟踪**的锁清单，
#   重写它会产生与本任务无关的提交噪音（这一条正是"不用 `lock_rules.py` 代替
#   `chmod`"的理由：`lock_rules.py` 会顺带重写该清单的 `locked_at` 与 SHA 台账）；
# - 不改任何 `0444` 之外的东西。
#
# 因为只改权限位、内容零改动，**`git status` / `git diff` 对本脚本的效果一律为空** ——
# 所以它不会污染任何提交。

set -eu

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "bootstrap_worktree: 无法定位仓库根（git rev-parse 失败）" >&2
  exit 1
}
CODE_ROOT="${REPO_ROOT}/system"
RULES_DIR="${CODE_ROOT}/rules"

if [ ! -d "${RULES_DIR}" ]; then
  echo "bootstrap_worktree: 找不到 rules 目录: ${RULES_DIR}" >&2
  exit 1
fi

# 解析 Python：与 pre-commit.sh 同一优先级（环境变量 → 隔离 venv → python3）
#
# ★ 候选必须**同时覆盖两种 venv 布局**（2026-09-17 实测修复）：
#   POSIX = `<venv>/bin/python`；Windows = `<venv>/Scripts/python.exe`。
#   原先只列 POSIX 形式 ⇒ Windows 上全部落空 ⇒ 回落 `python3`（无 yaml）
#   ⇒ `rules_lock_guard` 假红并提示"请勿用 --no-verify 绕过" —— 而真正的问题是**解释器选错了**。
PY="${WORKBUDDY_PY:-}"
if [ -z "${PY}" ]; then
  for cand in \
    "${HOME}/.workbuddy/binaries/python/envs/default/bin/python" \
    "${HOME}/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
    "${REPO_ROOT}/system/.venv/bin/python" \
    "${REPO_ROOT}/system/.venv/Scripts/python.exe" \
    python3
  do
    if command -v "${cand}" >/dev/null 2>&1; then PY="${cand}"; break; fi
  done
fi
if [ -z "${PY}" ]; then
  echo "bootstrap_worktree: 找不到可用的 python" >&2
  exit 1
fi

CHANGED=0
for suffix in yaml yml json; do
  for f in "${RULES_DIR}"/*."${suffix}"; do
    [ -f "${f}" ] || continue
    chmod 0444 "${f}"
    CHANGED=$((CHANGED + 1))
  done
done

echo "bootstrap_worktree: 已把 ${CHANGED} 个 rules 文件置为 0444（内容零改动）"

# 自检：把"是否真的复原了"交给守卫判，而不是靠本脚本自称
echo "bootstrap_worktree: 自检 rules_lock_guard …"
if "${PY}" "${CODE_ROOT}/scripts/checks/rules_lock_guard.py" "${CODE_ROOT}" --no-report; then
  echo "bootstrap_worktree ✓ rules_lock_guard 通过（纪律 9 不变量已复原）"
else
  rc=$?
  echo "bootstrap_worktree ✗ rules_lock_guard 仍不合格（exit=${rc}）—— 请勿用 --no-verify 绕过，报告主理人" >&2
  exit 1
fi

echo "bootstrap_worktree: 提示 —— 本脚本只改权限位，故下面两条命令应无任何输出："
echo "  git status --short system/rules system/registry"
echo "  git diff --stat -- system/rules system/registry"
