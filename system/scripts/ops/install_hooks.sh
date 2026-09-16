#!/bin/sh
# 安装 git hooks（把版本化的钩子脚本挂到 `.git/hooks/`）。
#
# ```
# sh system/scripts/ops/install_hooks.sh            # 安装 / 更新（默认）
# sh system/scripts/ops/install_hooks.sh --print    # 只把薄壳正文打到 stdout（**不安装**）—— 供测试断言
# sh system/scripts/ops/install_hooks.sh --check    # 比对「已安装」与「模板」；漂移 ⇒ exit 1（未安装 ⇒ 2）
# ```
#
# 设计：`.git/hooks/pre-commit` 只做**薄壳**，真正逻辑在
# `system/scripts/ops/pre-commit.sh`（版本化、可审、可改）。
# 薄壳不覆盖已有钩子：已存在且不是本脚本装的 → 拒绝并提示，**不静默覆盖**。
#
# ★★ 卡 13-O（缺口 `G-61`）：薄壳**必须与对象同源**
#
#   旧版薄壳把 `pre-commit.sh` 的路径**硬编码成主仓绝对路径**，而 `pre-commit.sh:60` 的
#   `CODE_ROOT="$REPO_ROOT/system"` 里 `REPO_ROOT` 是**从 cwd 反解**的
#   ⇒ 一次提交里存在**两个根**（判据根 = 永远是主仓 / 对象根 = 发起提交的那棵树），
#     **且没有任何一处断言它们必须相同**。于是两个方向都会坏：
#
#     ① 判据**新**于对象：`$CODE_ROOT/scripts/checks/<新>.py` 不存在 ⇒ `python … [Errno 2]`，
#        且被 `run_gate` 与 `rc=1`（真违规）**同款报成"阻断"** ⇒ 提交者被告知"你改坏了"（**假指控**）。
#        ★ 本批次实测 3 次、**≥2 条流**撞上（`quote_provenance_guard` / `scenario_tag_binding_guard` /
#          `rule_key_alignment_guard`）。
#     ② 判据**旧**于对象：树里已有的新门禁**根本不跑**，**零报错**（静默失去一道门禁）。
#
#   → 薄壳改为**取被检树自己的 `pre-commit.sh`**，即「判据根 == 对象根」。
#     ★ 主仓自身提交时行为**不变**：在主仓里 `--show-toplevel` 就是主仓根。
#     ★ 方向②的残余（落后树跑自己的旧清单）是**设计上可接受**的：门禁绑定**集成线** ——
#       落后树的内容要进 `main` 必须在 `main` 根下再跑一遍。详见
#       `system/reports/ws_hook_same_source_design.md §6`。
#
#   ★ 薄壳内**必须摘掉 `GIT_DIR`**：git 在钩子里已导出 `GIT_DIR`，而**不带** `GIT_WORK_TREE` 的
#     `git rev-parse --show-toplevel` **不查仓库、直接把 cwd 当工作树根**返回
#     （`G-RC-12` 的同一根因；`pre-commit.sh` 里已有一处同样的注释）。
#
# ★ 本脚本自身的一处小修：目录改用 `--git-common-dir`
#   —— 在 linked worktree 里 `<worktree>/.git` 是**文件**不是目录，
#   旧的 `"$REPO_ROOT/.git/hooks"` 在 worktree 下根本不成立（安装会失败）。

set -eu

MODE="${1:-install}"
MARKER="# installed-by: system/scripts/ops/install_hooks.sh"

# ── 薄壳正文：**唯一真源**（安装与 `--print` 都读这里；测试也只断言这里） ──
print_hook() {
  cat <<'HOOK'
#!/bin/sh
# installed-by: system/scripts/ops/install_hooks.sh
# ★ 同源（卡 13-O / G-61）：判据（pre-commit.sh）取自**被检的那棵树**，
#   与 pre-commit.sh 内从 cwd 反解的 CODE_ROOT 同根；禁止硬编码主仓绝对路径。
root="$(
  unset GIT_DIR GIT_WORK_TREE GIT_PREFIX
  git rev-parse --show-toplevel 2>/dev/null
)" || exit 2
if [ -z "${root}" ]; then
  echo "pre-commit: [INPUT-ERROR] 无法定位仓库根（exit=2，输入错误）—— 拒绝在根不明时跑门禁" >&2
  exit 2
fi
if [ ! -f "${root}/system/scripts/ops/pre-commit.sh" ]; then
  echo "pre-commit: [INPUT-ERROR] 门禁清单脚本不在被检树：${root}/system/scripts/ops/pre-commit.sh" >&2
  echo "  ★ 判据与对象不同源（G-61）；这是**输入错误**（exit=2），不是违规。" >&2
  exit 2
fi
exec sh "${root}/system/scripts/ops/pre-commit.sh"
HOOK
}

case "${MODE}" in
  --print)
    print_hook
    exit 0
    ;;
  --check)
    GIT_COMMON_DIR="$(git rev-parse --git-common-dir)"
    COMMON_ABS="$(cd "${GIT_COMMON_DIR}" && pwd)"
    TARGET="${COMMON_ABS}/hooks/pre-commit"
    if [ ! -e "${TARGET}" ]; then
      echo "install_hooks --check: 未安装: ${TARGET}" >&2
      exit 2
    fi
    TMP="$(mktemp)"
    print_hook > "${TMP}"
    if cmp -s "${TARGET}" "${TMP}"; then
      rm -f "${TMP}"
      echo "install_hooks --check: 已安装的薄壳 == 版本化模板（${TARGET}）"
      exit 0
    fi
    echo "install_hooks --check: **漂移** —— 已安装的薄壳 != 版本化模板（${TARGET}）" >&2
    echo "  * 装的是旧的 => 你正在用**过期判据**跑门禁（可能静默少跑门禁）；" >&2
    echo "    装的是新的 => 模板被回退了。处置：sh system/scripts/ops/install_hooks.sh 重装。" >&2
    echo "  -- diff（< 已安装 / > 模板） --" >&2
    diff "${TARGET}" "${TMP}" >&2 || true
    rm -f "${TMP}"
    exit 1
    ;;
  install|--install)
    ;;
  *)
    echo "install_hooks: 未知参数 ${MODE}（可用：无 / --print / --check）" >&2
    exit 2
    ;;
esac

REPO_ROOT="$(git rev-parse --show-toplevel)"
GIT_COMMON_DIR="$(git rev-parse --git-common-dir)"
COMMON_ABS="$(cd "${GIT_COMMON_DIR}" && pwd)"
HOOKS_DIR="${COMMON_ABS}/hooks"
SOURCE="${REPO_ROOT}/system/scripts/ops/pre-commit.sh"
TARGET="${HOOKS_DIR}/pre-commit"

if [ ! -f "${SOURCE}" ]; then
  echo "缺少源钩子脚本: ${SOURCE}" >&2
  exit 1
fi

if [ -e "${TARGET}" ] && ! grep -qF "${MARKER}" "${TARGET}" 2>/dev/null; then
  echo "已存在不受本脚本管理的 pre-commit 钩子: ${TARGET}" >&2
  echo "请先人工处理（合并或移走），**不自动覆盖**。" >&2
  exit 1
fi

# ★ 覆盖前**自动备份**：改坏钩子 = **全体流无法提交**（`.git/hooks` 是全 worktree 共享的）
#   ⇒ 任何一次安装都必须能一条命令回滚。
if [ -e "${TARGET}" ]; then
  BACKUP="${TARGET}.bak.$(date +%Y%m%d%H%M%S)"
  cp "${TARGET}" "${BACKUP}"
  echo "已备份原钩子: ${BACKUP}"
  echo "  回滚一条命令: cp '${BACKUP}' '${TARGET}' && chmod +x '${TARGET}'"
fi

print_hook > "${TARGET}"
chmod +x "${TARGET}"

# ★★ 收尾措辞（`V-11`「举证半径 = 结论半径」的一次自查）：
#   本行**曾**写成 `已安装: ${TARGET} -> ${SOURCE}` —— 而 `${SOURCE}` 是**本次运行 install_hooks.sh
#   的那棵树**的路径，读起来像"**钩子钉死了这棵树**"（= 旧钩子的毛病，我们刚把它治掉）。
#   实际上薄壳是**运行时**用 `git rev-parse --show-toplevel` 解析根的 ⇒ **不指向任何固定的树**。
#   ⇒ 主语必须写对：钩子**不绑定**任何一棵树；`${SOURCE}` 只说明"本次是从哪棵树取的模板"。
echo "已安装: ${TARGET}"
echo "  ★ 该薄壳**不绑定任何一棵树**：它在运行时用 git rev-parse --show-toplevel 解析"被检的那棵树""
echo "    ⇒ 任一棵树提交时，跑的都是**它自己那棵**的 system/scripts/ops/pre-commit.sh（判据与对象同源）。"
echo "  （本次模板取自: ${SOURCE} —— 仅说明来源，**不是**被写进钩子的路径）"
