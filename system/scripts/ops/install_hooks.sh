#!/bin/sh
# 安装 git hooks（把版本化的钩子脚本挂到 `.git/hooks/`）。
#
# ```
# sh system/scripts/ops/install_hooks.sh
# ```
#
# 设计：`.git/hooks/pre-commit` 只做**薄壳**，真正逻辑在
# `system/scripts/ops/pre-commit.sh`（版本化、可审、可改）。
# 薄壳不覆盖已有钩子：已存在且不是本脚本装的 → 拒绝并提示，**不静默覆盖**。

set -eu

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"
SOURCE="$REPO_ROOT/system/scripts/ops/pre-commit.sh"
TARGET="$HOOKS_DIR/pre-commit"
MARKER="# installed-by: system/scripts/ops/install_hooks.sh"

if [ ! -f "$SOURCE" ]; then
  echo "缺少源钩子脚本: $SOURCE" >&2
  exit 1
fi

if [ -e "$TARGET" ] && ! grep -qF "$MARKER" "$TARGET" 2>/dev/null; then
  echo "已存在不受本脚本管理的 pre-commit 钩子: $TARGET" >&2
  echo "请先人工处理（合并或移走），**不自动覆盖**。" >&2
  exit 1
fi

{
  echo "#!/bin/sh"
  echo "$MARKER"
  echo "exec sh \"$SOURCE\""
} > "$TARGET"
chmod +x "$TARGET"
echo "已安装: $TARGET → $SOURCE"
