#!/bin/sh
# 在**沙箱外**跑 pytest（关闭 Python 层 FS broker hook）。
#
# 用法：
#   sh system/scripts/ops/run_pytest.sh tests/unit                 # 跑一批
#   sh system/scripts/ops/run_pytest.sh tests/unit/test_contracts.py -v
#
# ★ 为什么必须这样跑（实测根因）：
#   WorkBuddy 的 `sitecustomize.py` shim 会在**每一次文件操作**上 brokered 到
#   宿主进程走 IPC。触发条件是：
#       CODEBUDDY_SAFE_DELETE_SANDBOX=1   或   CODEBUDDY_BROKERED_FS_HOOK_ENABLED=1
#   **Bash 工具的沙箱开关关不掉它**（它在 Python 解释器层）。
#
#   后果：夹具 `copytree` 每个用例复制 130 个文件 → 每个用例数百次 broker 往返 →
#   数百用例累积数万次 → **在某个点 broker 阻塞，进程卡死且卡点漂移**
#   （实测 `tests/unit/test_contracts.py` 分别卡在第 15 / 17 / 19 条）。
#
#   实测对照：
#     broker 开 → 卡死（faulthandler 堆栈落在 `_brokered_shutil_copytree`）
#     broker 关 → 12 次 copytree 每次 0.026s，全部通过
#
# ★ 只用 pytest 请走本脚本；跑整套请用 `python system/scripts/ops/verify.py --batch <名>`
#   （已内置同一环境修正，且**分批 + 每批独立超时**）。

set -eu

export CODEBUDDY_SAFE_DELETE_SANDBOX=0
export CODEBUDDY_BROKERED_FS_HOOK_ENABLED=0
# ★ 第三道闸门：**安全删除本身**的开关（`E` 裁定 = (甲) 合法配置，非绕过）。
# 只关前两个时，每次删除仍会 spawn 一次 node CLI ⇒ 夹具批次照样打穿宿主
# **回合级**删除预算（`V-08`/`V-09`）⇒ 连单个用例目录都被拒删、后面全部报 `E`。
# `E` 下即**生产/门禁口径**（本仓 CI 与 `verify.py` 派生批次亦然）。
# 守卫 `verification_policy_guard.py::BROKER_ENV_VARS` 是这三行的**唯一真源**，
# 少写一行会被它据实判红（声明↔实现机器绑定）。
export CODEBUDDY_SAFE_DELETE_ENABLED=0

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT/system"

PY="${WORKBUDDY_PY:-}"
if [ -z "$PY" ]; then
  # ★ 候选必须**同时覆盖两种 venv 布局**（2026-09-17 实测修复）：
  #   POSIX = `<venv>/bin/python`；Windows = `<venv>/Scripts/python.exe`。
  #   与 pre-commit.sh / bootstrap_worktree.sh 保持**同一优先级**（三处必须一致，
  #   否则会出现"钩子用一个解释器、跑测用另一个"的错位，排查成本极高）。
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
if [ -z "$PY" ]; then
  echo "run_pytest.sh: 找不到可用的 python" >&2
  exit 2
fi

exec "$PY" -m pytest "$@" -p no:cacheprovider
