#!/bin/sh
# grep 引擎地板真值探针 —— `CONVENTIONS.md::V-10` 的**仪器**
#
# 立此仪器的原因（`V-10` 元规矩「因果解释落纸前必须先做区分实验」）：
# 本会话在"裸 `grep` 到底哪些语法失效"上出现了**四轮互相矛盾的读数**，
# 继续互相传读数**无法收敛** —— 分歧只能由一个**可复现、带指纹、带地板真值**的仪器关掉。
#
# 设计要点（每一条都对应本会话踩过的一个坑）：
#   1. **内容与模式都不经过 shell 展开**：内容用 `printf '%s\n'` 逐行给出，
#      模式从**单引号 here-doc** 读入 ⇒ 不存在"反斜杠被外壳吃掉"的可能；
#   2. ★ **证明模式字节真的到达了 grep**：每格打印 `od -c` 的模式字节。
#      没有这一步，读数为 0 时**无法区分**"grep 不支持"与"外壳把 `\` 吃了"；
#   3. **每次都打印引擎指纹**（`command -v` + `--version` 原文）——
#      `V-11` 仪器轴要求结论主语**逐字写出被测对象**；
#   4. **每一格都带地板真值**（Python `re`，第三法）——
#      `V-10` 规矩 3：无真值的格子不许进结论；
#   5. ★ 真值引擎也**逐行**匹配（`re.search` per line），与 `grep -c` 的
#      "计**行**数"口径**同源** —— 否则又是 `V-11` 仪器轴越界。
#
# 用法：`sh system/scripts/ops/probe_grep_engine.sh`
# 退出码：恒 `0`（这是**仪器**，不是**门禁** —— 它只出数据，不做判定）。

set -u

PY="${PY:-/Users/gaza/.workbuddy/binaries/python/envs/default/bin/python}"
BARE_GREP="grep"
REAL_GREP="/usr/bin/grep"

echo "==================== 引擎指纹（结论主语必须是这个）===================="
printf '%-16s %s\n' 'command -v grep' "$(command -v "${BARE_GREP}")"
printf '%-16s %s\n' 'bare --version' "$("${BARE_GREP}" --version 2>&1 | head -1)"
printf '%-16s %s\n' 'real --version' "$("${REAL_GREP}" --version 2>&1 | head -1)"
printf '%-16s %s\n' 'python' "$("${PY}" -c 'import sys; print(sys.version.split()[0])')"
echo

# 受控输入：8 行。`%s\n` 逐行给出 ⇒ **零转义解释**。
print_content() {
    printf '%s\n' aab ab a.b aa zz abcabc abb abab
}
echo "------------------------------ 受控输入 ------------------------------"
print_content | od -c | head -3
echo "（上面 8 行就是全部输入；任何「真值」都只能相对它成立）"
echo

echo "============================ 逐格对照 ============================"
printf '%-16s %-9s %-9s %-11s %-11s %-7s %s\n' \
    '模式' '裸BRE' '/usr BRE' '裸ERE(原样)' '/usr ERE' '★真值' '判定'
echo "---------------------------------------------------------------------------------"

# 每行：BRE 模式@**同一字符串**在 -E 下@Python 等价正则@说明
#   ★ `-E` 列刻意用**原样字符串**（不转换）：那才是"遇到问题就加个 -E"的真实动作。
#     `-E` 下原样字符串与转换后字符串**不是同一个量**，两列都要有真值对照。
while IFS='@' read -r pat ere py label; do
    [ -z "${pat}" ] && continue
    case "${pat}" in \#*) continue ;; esac

    bytes="$(printf '%s' "${pat}" | od -c | head -1 | sed 's/^[0-9]* *//; s/ *$//')"

    out_bare="$(print_content | "${BARE_GREP}" -c "${pat}" 2>&1)"; rc_bare=$?
    out_real="$(print_content | "${REAL_GREP}" -c "${pat}" 2>&1)"; rc_real=$?
    out_beraw="$(print_content | "${BARE_GREP}" -E -c "${ere}" 2>&1)"; rc_beraw=$?
    out_reraw="$(print_content | "${REAL_GREP}" -E -c "${ere}" 2>&1)"; rc_reraw=$?

    truth="$("${PY}" -c '
import re, sys
pat = sys.argv[1]
lines = ["aab", "ab", "a.b", "aa", "zz", "abcabc", "abb", "abab"]
try:
    print(sum(1 for l in lines if re.search(pat, l)))
except re.error as exc:
    print("RE-ERR:" + str(exc))
' "${py}")"

    # 判定只看两个 **BRE** 列（-E 列另按同法比对，见下方汇总行）
    verdict="MISMATCH"
    if [ "${out_bare}" = "${truth}" ] && [ "${out_real}" = "${truth}" ]; then
        verdict="both-OK"
    elif [ "${out_real}" = "${truth}" ]; then
        verdict="bare-BAD"
    elif [ "${out_bare}" = "${truth}" ]; then
        verdict="real-BAD"
    fi

    printf '%-16s %-9s %-9s %-11s %-11s %-7s %s\n' \
        "${label}" "${out_bare}/rc${rc_bare}" "${out_real}/rc${rc_real}" \
        "${out_beraw}/rc${rc_beraw}" "${out_reraw}/rc${rc_reraw}" "${truth}" "${verdict}"
    printf '  └ 模式字节: %s\n' "${bytes}"
done <<'PATTERNS'
a\|z@a\|z@a|z@GNU扩展 交替
a\+b@a\+b@a+b@GNU扩展 一或多
ab\?@ab\?@ab?@GNU扩展 零或一
\<ab\>@\<ab\>@\bab\b@GNU扩展 词边界
ab\{2\}@ab\{2\}@ab{2}@POSIX-BRE 区间
a\.b@a\.b@a\.b@POSIX-BRE 字面点
ab@ab@ab@纯字面(对照)
\(abc\)\1@\(abc\)\1@(abc)\1@POSIX-BRE 组+反向引用
PATTERNS

echo "-------------------------------------------------------------------------"
echo "判定口径："
echo "  both-OK   两引擎都等于地板真值"
echo "  real-BAD  裸 grep 等于真值、/usr/bin/grep 不等于 ⇒ **/usr/bin/grep 才是坏的那个**"
echo "  bare-BAD  裸 grep 不等于真值、/usr/bin/grep 等于 ⇒ 常见形态（toybox 方言）"
echo "  MISMATCH  两个都不等于真值 ⇒ ★ 先怀疑本项目自己的真值口径，不要下结论"
echo
echo "★ 本脚本**恒 exit 0**：它是仪器不是门禁。判定由人（或 13-L 的 safe_grep 助手）做。"
exit 0
