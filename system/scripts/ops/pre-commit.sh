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

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "pre-commit: 无法定位仓库根（git rev-parse 失败）" >&2
  exit 1
}
cd "$REPO_ROOT" || exit 1

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
  echo "pre-commit → $label"
  "$PY" "$@" || {
    rc=$?
    echo "pre-commit ✗ $label 阻断（exit=$rc）" >&2
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

if [ "$FAILED" -ne 0 ]; then
  echo "pre-commit: 有门禁阻断，提交被拒。" >&2
  exit 1
fi
echo "pre-commit ✓ 全部门禁放行"
exit 0
