#!/usr/bin/env python3
"""`public_fetcher.py` —— 公开网页的**真实抓取器**（阶段② 采集侧的"投递"实现）。

## 为什么有它

`scripts/orchestrate/ingest_step.py` 把 `raw/inbox/` 定义为"外部文本进入本系统"的**投递口**，
并明确「阶段② 的真实连接器只需把采集到的文本投递到同一投递口」。本模块即该采集侧：
**公开网页 → 真实 HTTP 响应 → 确定性文本 → `raw/<name>`**。

`scripts/ingest/real_collector.py` 的 docstring 把分工写死为「本模块不抓取、不合成文本」，
载荷由采集侧落盘 —— 本模块就是那个采集侧。

## 数据流（两段，各自单一职责）

    https://…  ──(本模块)──▶  raw/<name>          # 真抓取 + 落盘
    raw/<name> ──(real_collector)──▶  facts/sources.jsonl + facts/claims.jsonl

## 落盘物的形态（**确定性**，可在同一 URL 上重放）

`raw/<name>` = 元数据头（`# ` 前缀的若干行）+ 正文行。元数据头逐字记录：

    # source_url:      <抓取时的 URL>
    # fetched_at:      <UTC ISO 时刻>
    # http_status:     <HTTP 状态码>
    # content_type:    <Content-Type>
    # body_sha256:     <HTTP 响应体原始字节的 sha256>
    # body_bytes:      <HTTP 响应体字节数>
    # text_sha256:     <本落盘文本（含头部）的 sha256>

正文由 `html_to_text()` **确定性**地从响应体提取（规则见该函数 docstring）。
**本模块不解释、不改写、不总结正文** —— 摘要式抓取会让"引文↔原文"的绑定失去意义。

## 健全性断言（可判定，非关键词黑名单）

每个来源带 `must_contain`：抓取到的正文**必须逐字包含**这些串，否则该来源判**失败**
（`exit 1`）。它拦的是"抓到了错误页 / 验证页 / 空壳页"——
判据是"与**调用方事先声明**的期望串比对"，不是"扫文本里有没有可疑词"（`R-06` ①）。

## 预算（`rules/freeze.yaml::p09`）

本模块**每个来源各发起 1 次 HTTP 请求**，请求数 = 来源数（由调用方给定的清单决定）。
p09 的 `budget` 当前是 `tbd`（**参数未冻结**，`Ch11 §F.1`）——
本模块**不擅自把它当数字用**，也不自行编一个上限：
读到 `tbd` 即记 `BUDGET_TBD` note 并**照常执行**（"未冻结"不等于"必须阻断"，见 `Ch11 §D.2`
`impact_note`：「预算值 tbd 不阻塞开工」）。**绝不**把它填成具体数字（红线一：不借参数补新门槛）。

## 用法

    python system/scripts/ingest/public_fetcher.py [code_root] [--only <raw_name> …]

退出码（`CONVENTIONS.md::G-01`）：`0` 全部抓取成功 · `1` 有来源失败 · `2` 输入异常。
"""

from __future__ import annotations

import argparse
import hashlib
import html
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.guard.rawsink import RAW_DIRNAME, store_raw  # noqa: E402

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " \
             "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 InvestSigh-research/1.0"
"""抓取用的 UA：**标识自己**是本项目的公开信息采集，不伪装成普通浏览器以外的身份。"""

TIMEOUT_SECONDS = 30
"""单次 HTTP 超时（秒）。超时即该来源失败 —— **不重试、不静默跳过**。"""

BUDGET_NOTE_PREFIX = "BUDGET_TBD"
"""`p09` 预算未冻结时的显式 note 前缀（`R-03`）。"""


@dataclass(frozen=True)
class FetchSpec:
    """一个待抓取的公开网页来源（`must_contain` 为抓取健全性断言）。"""

    url: str
    raw_name: str
    """`raw/` 下的落点名。命名约定 `YYYY-MM-DD-<slug>.txt`，日期 = 来源发布日。"""

    must_contain: tuple[str, ...]
    """正文必须**逐字包含**的串（声明在先、比对在后 —— 不是对文本做词面分类）。"""


@dataclass(frozen=True)
class FetchedArtifact:
    """一次成功抓取的**可审计**结果（供 `facts/sources.jsonl` 逐字登记）。"""

    url: str
    raw_name: str
    http_status: int
    content_type: str
    body_bytes: int
    body_sha256: str
    text_sha256: str
    fetched_at: str
    line_count: int


class FetchFailure(RuntimeError):
    """抓取失败（HTTP 错误 / 超时 / 期望串缺失）—— 明确失败，**不返回空文本兜底**。"""


# ── HTML → 文本（确定性；规则本身是判据，故写全） ────────────────────────────────

_BLOCK_TAGS = frozenset(
    {
        "address", "article", "aside", "blockquote", "br", "caption", "dd", "div", "dl",
        "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4",
        "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section",
        "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
    }
)
"""块级标签：其开始/结束处插入换行（使 `locator` 的行区间有意义）。"""

_SKIP_TAGS = frozenset({"script", "style", "noscript", "svg", "iframe", "template"})
"""非可见内容标签：整体丢弃（连同其文本）。

★ `head` **不在**此表（实测教训）：`HTMLParser` **不**做 HTML5 的隐式闭合 ——
  真实页面普遍省略 `</head>`，于是"遇到 `<head>` 就进入跳过态"会让 `_skip_depth` **永不归零**，
  整页正文被静默丢成 0 行（实测 `biz.chosun.com` / `ajupress.com` 两例，均 `lines=0`）。
  `head` 内真正要丢弃的只有 `script` / `style`（已在表内），其余（`title` / `meta` / `link`）
  要么有意义的标题文本、要么无文本 —— 故不整块丢弃。
"""


class _HtmlToText(HTMLParser):
    """把 HTML 提取为**可见文本**：丢弃脚本/样式，块级标签处断行。

    转换规则（穷尽、可判定）：
      1. 处于 `_SKIP_TAGS` 子树内的文本一律丢弃；
      2. `_BLOCK_TAGS` 的开始/结束标签各产生一次行边界；
      3. 其余标签不产生输出（行内标签的文本原样保留）；
      4. 字符实体由 `HTMLParser(convert_charrefs=True)` 解回原字符（`&amp;` → `&`）；
      5. 每行 `.strip()`，丢弃**空行** —— 使行号不随模板空行漂移。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        raw = html.unescape("".join(self._parts))
        lines = [line.strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def html_to_text(body: str) -> str:
    """把 HTML 响应体转为可见文本行（确定性，见 `_HtmlToText` 的 5 条规则）。"""
    parser = _HtmlToText()
    parser.feed(body)
    parser.close()
    return parser.text()


# ── 预算（唯一读口，`config.freeze`） ────────────────────────────────────────


def budget_note(root: Path) -> str:
    """读 `rules/freeze.yaml::p09` 的 `budget`，返回**显式** note。

    - `tbd`（未冻结）→ `"BUDGET_TBD: p09.budget=tbd（未冻结）—— 不设人为上限，不填数字"`；
    - 其它取值 → 如实回显该取值（**不回退、不猜测**）。
    """
    from config.freeze import get_param

    value = get_param("p09", root).effective_value
    budget = value.get("budget") if isinstance(value, dict) else value
    if budget == "tbd" or budget is None:
        return (
            f"{BUDGET_NOTE_PREFIX}: p09.budget={budget!r}（未冻结，Ch11 §F.1）"
            "—— 不设人为上限、不填数字，抓取照常执行"
        )
    return f"p09.budget={budget!r}"


# ── 抓取 ────────────────────────────────────────────────────────────────


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_one(spec: FetchSpec) -> tuple[str, str, int, str]:
    """抓取单个 URL，返回 `(响应体, content_type, http_status, body_sha256)`。

    HTTP 错误 / 超时 / 网络失败 → `FetchFailure`（**不返回空串兜底**）。
    """
    request = urllib.request.Request(spec.url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = int(getattr(response, "status", 0))
            content_type = str(response.headers.get("Content-Type", ""))
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise FetchFailure(f"HTTP {exc.code} {exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchFailure(f"{type(exc).__name__}: {exc}") from exc
    return body, content_type, status, hashlib.sha256(body.encode("utf-8")).hexdigest()


def compose_raw_text(
    spec: FetchSpec,
    *,
    content_type: str,
    status: int,
    body_sha256: str,
    fetched_at: str,
    body_text: str,
) -> str:
    """拼出 `raw/` 落盘文本：**元数据头 + 正文**（头部使落盘物自描述、可回溯）。

    头部 6 行逐字记录来源与哈希；`text_sha256` 覆盖头部自身之外的**全部落盘内容**
    （正文 + 结尾换行），使 `facts/sources.jsonl::content_hash` 可对该落盘物做完整性校验。
    """
    head_wo_digest = "\n".join(
        [
            f"# source_url:      {spec.url}",
            f"# fetched_at:      {fetched_at}",
            f"# http_status:     {status}",
            f"# content_type:    {content_type}",
            f"# body_sha256:     {body_sha256}",
        ]
    )
    tail = f"\n\n{body_text}\n"
    digest = hashlib.sha256(tail.encode("utf-8")).hexdigest()
    return f"{head_wo_digest}\n# text_sha256:     {digest}{tail}"


def fetch_all(
    root: str | Path, specs: tuple[FetchSpec, ...], *, fetched_at: str | None = None
) -> tuple[list[FetchedArtifact], list[tuple[str, str]], str]:
    """抓取 `specs` 全部来源并把文本经 `store_raw` 落 `raw/`。

    返回 `(成功物, [(url, 失败原因)], budget_note)`。
    单个来源失败**不中断**其余来源（配额/网络抖动不应让整批归零），但会在退出码上如实反映。
    """
    root_path = Path(root)
    stamp = fetched_at or _utc_now()
    note = budget_note(root_path)
    artifacts: list[FetchedArtifact] = []
    failures: list[tuple[str, str]] = []

    for spec in specs:
        try:
            body, content_type, status, body_sha = fetch_one(spec)
            text = html_to_text(body)
            missing = [needle for needle in spec.must_contain if needle not in text]
            if missing:
                raise FetchFailure(
                    "抓取物未逐字包含事先声明的期望串 "
                    f"{missing!r}（疑似错误页/验证页/页面改版）—— 不落盘，不当成功"
                )
            composed = compose_raw_text(
                spec,
                content_type=content_type,
                status=status,
                body_sha256=body_sha,
                fetched_at=stamp,
                body_text=text,
            )
            path = store_raw(root_path, spec.raw_name, composed)
            artifacts.append(
                FetchedArtifact(
                    url=spec.url,
                    raw_name=path.name,
                    http_status=status,
                    content_type=content_type,
                    body_bytes=len(body.encode("utf-8")),
                    body_sha256=body_sha,
                    text_sha256=hashlib.sha256(composed.encode("utf-8")).hexdigest(),
                    fetched_at=stamp,
                    line_count=len(composed.splitlines()),
                )
            )
        except FetchFailure as exc:
            failures.append((spec.url, str(exc)))
    return artifacts, failures, note


def deposit_transported_text(
    root: str | Path,
    *,
    raw_name: str,
    url: str,
    transport: str,
    text: str,
    note: str = "",
    fetched_at: str | None = None,
) -> Path:
    """把**经 builtin 能力取得**的页面文本落 `raw/`（本机 HTTP 直取被来源方拒绝时的路径）。

    ★ 为什么需要这个**独立**入口（而不是让 `fetch_all` 兼容它）：
      `fetch_all` 的元数据头记的是"HTTP 响应体字节的 sha256"等**本机实测**项；
      经 `websearch_webfetch` 取得的内容**没有**这些项。若共用一条落盘路径，
      头部要么缺项、要么得填假值 —— **填假值就是伪造抓取证据**。
      故此处显式记 `transport` 与 `body_sha256: n/a`，让"这份落盘物是怎么来的"一眼可辨。

    ★ 落盘仍经**唯一**的 `store_raw`（永不覆盖既有原始物）。
    `text` 由调用方（采集动作）提供：本函数**不**校验其真伪（它无从校验），
    可核性由 `quote_provenance_guard`（引文 ↔ 落盘物绑定）与报告中给出的原始取得内容共同承载。
    """
    if transport == "http_get":
        raise ValueError(
            "transport=http_get 不得走本入口 —— 那会绕过 fetch_all 的本机实测元数据"
            "（进而可能写出无 body_sha256 的「直取」落盘物）"
        )
    stamp = fetched_at or _utc_now()
    head_wo_digest = "\n".join(
        [
            f"# source_url:      {url}",
            f"# fetched_at:      {stamp}",
            f"# transport:       {transport}（非本机 HTTP 直取）",
            f"# body_sha256:     n/a（本机未取得原始响应体，故无此哈希）",
            f"# deposit_note:    {note}" if note else "# deposit_note:    (none)",
        ]
    )
    tail = f"\n\n{text}\n"
    digest = hashlib.sha256(tail.encode("utf-8")).hexdigest()
    composed = f"{head_wo_digest}\n# text_sha256:     {digest}{tail}"
    return store_raw(Path(root), raw_name, composed)


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。退出码：`0` 全部成功 · `1` 有来源失败 · `2` 输入异常。"""
    from scripts.ingest.fetch_manifest import FETCH_SPECS

    parser = argparse.ArgumentParser(
        prog="public_fetcher.py",
        description="公开网页真实抓取器：HTTP GET → 确定性文本 → raw/",
    )
    parser.add_argument("code_root", nargs="?", default=".", help="代码工程根（system/）")
    parser.add_argument("--only", nargs="*", default=None, help="只抓指定 raw_name（调试用）")
    parser.add_argument(
        "--deposit-raw-name",
        default=None,
        help="投递模式：把 stdin 的文本落成该 raw 名（配 --deposit-url / --deposit-transport）",
    )
    parser.add_argument("--deposit-url", default="", help="投递模式：该文本的来源 URL")
    parser.add_argument("--deposit-transport", default="", help="投递模式：取得方式（如 webfetch）")
    parser.add_argument("--deposit-note", default="", help="投递模式：说明")
    args = parser.parse_args(argv)

    root = Path(args.code_root)
    if not root.exists():
        print(f"[INPUT-ERROR] code_root 不存在: {root}", file=sys.stderr)
        return 2

    if args.deposit_raw_name:
        if not (args.deposit_url and args.deposit_transport):
            print("[INPUT-ERROR] 投递模式必须同时给出 --deposit-url 与 --deposit-transport", file=sys.stderr)
            return 2
        try:
            path = deposit_transported_text(
                root,
                raw_name=args.deposit_raw_name,
                url=args.deposit_url,
                transport=args.deposit_transport,
                text=sys.stdin.read(),
                note=args.deposit_note,
            )
        except (ValueError, OSError) as exc:
            print(f"[INPUT-ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        print(f"== public_fetcher.py（投递模式 transport={args.deposit_transport}）==")
        print(f"  deposited: {path.name}")
        print(f"  source_url: {args.deposit_url}")
        return 0

    specs = FETCH_SPECS
    if args.only:
        wanted = set(args.only)
        specs = tuple(s for s in specs if s.raw_name in wanted)
        if not specs:
            print(f"[INPUT-ERROR] --only 未匹配任何来源: {sorted(wanted)}", file=sys.stderr)
            return 2

    try:
        artifacts, failures, note = fetch_all(root, specs)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"[INPUT-ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("== public_fetcher.py ==")
    print(f"  note: {note}")
    for art in artifacts:
        print(
            f"  fetched: {art.raw_name}  http={art.http_status}  bytes={art.body_bytes}"
            f"  lines={art.line_count}  body_sha256={art.body_sha256[:16]}…"
        )
    for url, why in failures:
        print(f"  FAILED: {url} — {why}")
    print(f"  scanned sources: {len(specs)}  fetched: {len(artifacts)}  failed: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
