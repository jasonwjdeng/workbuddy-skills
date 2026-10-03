#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lakebook_parser.py -- 解析语雀（Yuque）导出的 .lakebook 文件

.lakebook 的本质是一个 tar 归档（可能带 gzip 压缩），内部结构：

    <repo_dir>/
        $meta.json          知识库元信息：{ "meta": "<JSON 字符串>" }
                              -> { "book": {...book.name / book.tocYml...},
                                   "docs": [ {slug, type, format, title, ...} ] }
        <slug>.json         每篇文档：{ "doc": { type, format, body, body_asl } }
                            body      = HTML 正文（Doc）/ lakesheet JSON（Sheet）
                            body_asl  = Lake(ASL) 源码，数学公式真身在这里

本脚本把上面这套私有结构还原成通用产物：
    Doc   -> Markdown（还原 LaTeX 公式、可选下载图片到本地）
    Sheet -> CSV（zlib/gzip 解压后的行列矩阵）
    Board -> 原始 JSON + 说明占位文件（官方未定义可转换结构）
    目录按 TOC 的 level 还原成文件夹层级

用法：
    python lakebook_parser.py 我的知识库.lakebook -o ./out
    python lakebook_parser.py ./exports -o ./out --nopic
    python lakebook_parser.py 我的知识库.lakebook --list
"""

from __future__ import annotations

import argparse
import csv
import gzip
import html as html_mod
import io
import itertools
import json
import os
import re
import sys
import tarfile
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
import zlib
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from markdownify import markdownify as _md  # type: ignore
    HAS_MARKDOWNIFY = True
except ImportError:
    HAS_MARKDOWNIFY = False

# 允许强制走兜底实现，便于在没有第三方库的环境里验证
if os.environ.get("LAKEBOOK_NO_MARKDOWNIFY"):
    HAS_MARKDOWNIFY = False
if os.environ.get("LAKEBOOK_NO_YAML"):
    HAS_YAML = False


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) lakebook-parser/1.0"
ATTACH_DIR = "_attachments"


# --------------------------------------------------------------------------
# 通用小工具
# --------------------------------------------------------------------------
def _int(value, default=0):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _maybe_json(value):
    """语雀会把 JSON 再塞进 JSON 字符串里，这里做展开。"""
    if isinstance(value, str):
        s = value.strip()
        if s[:1] in "{[":
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return value
    return value


def sanitize_name(name, fallback="untitled"):
    """清掉文件名非法字符，避免跨平台炸掉。"""
    if name is None:
        name = ""
    name = unicodedata.normalize("NFC", str(name))
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
    name = name.replace("\u200b", "").replace("\ufeff", "")
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip(" .")
    if len(name) > 110:
        name = name[:110].rstrip(" .")
    return name or fallback


class NameAllocator:
    """同一目录下重名文件自动加 _2 / _3 后缀。"""

    def __init__(self):
        self._used = set()

    def allocate(self, parent: Path, stem: str, suffix: str) -> Path:
        base, n = stem, 1
        while True:
            cand = parent / f"{base}{suffix}"
            key = str(cand).casefold()
            if key not in self._used and not cand.exists():
                self._used.add(key)
                return cand
            n += 1
            base = f"{stem}_{n}"


# --------------------------------------------------------------------------
# 1. 解包
# --------------------------------------------------------------------------
def extract_lakebook(path: Path, dest: Path) -> Path:
    """.lakebook -> 解压目录，返回 repo_dir（含 $meta.json 的那一层）。"""
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "r:*") as tf:  # r:* 自动识别 gzip/bz2/无压缩
        root = dest.resolve()
        for member in tf.getmembers():
            target = (dest / member.name).resolve()
            if not str(target).startswith(str(root)):
                raise ValueError(f"压缩包内含越界路径，已拒绝解压：{member.name}")
        try:
            tf.extractall(dest, filter="data")
        except TypeError:  # Python < 3.12 没有 filter 参数
            tf.extractall(dest)

    metas = sorted(dest.rglob("$meta.json"))
    if not metas:
        raise FileNotFoundError(f"{path.name} 内未找到 $meta.json，可能不是语雀 lakebook 文件")
    return metas[0].parent


# --------------------------------------------------------------------------
# 2. 元信息与目录树
# --------------------------------------------------------------------------
_FALLBACK_KV = re.compile(r"^(\s*)-\s+([\w_]+)\s*:\s*(.*)$")
_FALLBACK_CONT = re.compile(r"^\s+([\w_]+)\s*:\s*(.*)$")


def _strip_scalar(raw: str) -> str:
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    return s


def _fallback_yaml(text: str):
    """pyyaml 缺失时的极简 tocYml 解析（该字段只是扁平的 key: value 列表）。"""
    items, cur, pending_key = [], None, None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _FALLBACK_KV.match(line)
        if m:
            cur = {m.group(2): _strip_scalar(m.group(3))}
            items.append(cur)
            pending_key = None
            continue
        m = _FALLBACK_CONT.match(line)
        if m and cur is not None:
            key, raw = m.group(1), m.group(2)
            if raw == "" and pending_key is None:
                pending_key = key  # 多行标量（本场景基本不出现）
                cur[key] = ""
            else:
                cur[key] = _strip_scalar(raw)
    return items


def load_meta(repo_dir: Path):
    """返回 (book: dict, toc: list, docs_meta: dict[slug, dict])。"""
    raw = json.loads((repo_dir / "$meta.json").read_text(encoding="utf-8"))
    meta = _maybe_json(raw.get("meta", raw))
    if not isinstance(meta, dict):
        meta = {}

    book = _maybe_json(meta.get("book") or {})
    if not isinstance(book, dict):
        book = {}

    docs = _maybe_json(meta.get("docs") or [])
    docs_meta = {}
    if isinstance(docs, list):
        for d in docs:
            if isinstance(d, dict) and d.get("slug"):
                docs_meta[str(d["slug"])] = d

    return book, parse_toc(book), docs_meta


def parse_toc(book: dict):
    toc_raw = book.get("tocYml") or book.get("toc") or ""
    toc_raw = _maybe_json(toc_raw)
    if isinstance(toc_raw, str):
        if HAS_YAML:
            items = yaml.safe_load(toc_raw) or []
        else:
            items = _fallback_yaml(toc_raw)
    elif isinstance(toc_raw, list):
        items = toc_raw
    else:
        items = []

    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        kind = str(it.get("type") or "DOC").upper()
        if kind == "META":  # 第一条是知识库自身的元数据，不是内容
            continue
        out.append(
            {
                "type": kind,
                "title": str(it.get("title") or "").strip(),
                "level": _int(it.get("level"), 0),
                "url": str(it.get("url") or "").strip(),
                "uuid": str(it.get("uuid") or "").strip(),
                "child_uuid": str(it.get("child_uuid") or "").strip(),
            }
        )
    return out


def has_children(toc, pos: int, item: dict) -> bool:
    """判断某个 DOC 条目是否同时充当了下级条目的父节点。

    语雀的目录树里，`type: TITLE` 是纯分组，但 **文档本身也可以嵌套文档**——
    实测一个 139 篇的知识库里，顶层 `Kubernetes` 是 DOC，却挂着 99 个子文档。
    只按 TITLE 建目录会把它们全部平铺到根目录。

    两条判据并用：TOC 里显式的 `child_uuid`，以及紧随其后、层级更深的条目
    （部分导出会省略 child_uuid，不能只依赖其中一条）。
    """
    if item.get("child_uuid"):
        return True
    if pos + 1 >= len(toc):
        return False
    return max(0, toc[pos + 1]["level"]) > max(0, item["level"])


def book_name(book: dict, lakebook_path: Path) -> str:
    """知识库名。新版语雀导出常常省略 book.name，此时用导出文件名兜底——
    语雀下载时默认以知识库名命名文件，比 book.path 末段的随机 slug（如 ehyyx7）可靠得多。
    """
    name = str(book.get("name") or "").strip()
    if name:
        return name
    stem = lakebook_path.stem.strip()
    if stem:
        return stem
    path = str(book.get("path") or "").strip().rstrip("/")
    if path:
        seg = path.split("/")[-1]
        if seg:
            return seg
    return "未命名知识库"


def index_doc_files(repo_dir: Path):
    """slug -> 文档 json 路径（slug 即 $meta 里的 url 字段，也就是文件名）。"""
    idx = {}
    for p in repo_dir.rglob("*.json"):
        if p.name == "$meta.json":
            continue
        idx.setdefault(p.stem, p)
    return idx


def load_doc(doc_file: Path):
    data = json.loads(doc_file.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("doc"), dict):
        return data["doc"]
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------
# 3. LaTeX 还原
# --------------------------------------------------------------------------
CARD_FULL_RE = re.compile(r"<card\b([^>]*?)/?>(?:\s*</card>)?", re.I)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')


def _attrs(blob: str) -> dict:
    return {k: v for k, v in ATTR_RE.findall(blob or "")}


def extract_math_from_asl(asl: str):
    """ASL 里 <card name="math" value="..."> 按出现顺序取出公式真身（已解码）。"""
    if not asl:
        return []
    out = []
    for m in CARD_FULL_RE.finditer(asl):
        a = _attrs(m.group(1))
        if str(a.get("name", "")).lower() == "math":
            latex = _math_latex(a.get("value", ""))
            if latex:
                out.append(latex)
    return out


_DISPLAY_ENV_RE = re.compile(
    r"\\begin\{(cases|align|aligned|gather|gathered|equation|array|split|matrix|bmatrix|vmatrix)\}"
)


class BlockCollector:
    """先把公式 / 代码块等「已经是 Markdown」的内容换成纯 ASCII 占位符，
    待 Markdown 转换完成后再原样回填。

    这样公式里的反斜杠、换行，以及代码块里的下划线 / 星号 / 井号，
    都不会被 HTML 解析器折叠空白或被 Markdown 转义逻辑破坏。
    """

    def __init__(self):
        self.items = []

    def add(self, markdown: str) -> str:
        token = f"@@LKBBLOCK{len(self.items)}@@"
        self.items.append((token, markdown or ""))
        return token

    def apply(self, md: str) -> str:
        for token, block in self.items:
            md = md.replace(token, block)
        return md


def render_math(value: str, block=False) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if "\n" in v:
        block = True
    return f"\n\n$$\n{v}\n$$\n\n" if block else f"${v}$"


def _decode_card_value(raw: str) -> str:
    """卡片 value 常见两种形态：`data:<urlencode 后的 JSON>`，或 HTML 实体转义后的明文。"""
    v = html_mod.unescape(raw or "")
    if v.startswith("data:"):
        v = v[5:]
        try:
            v = urllib.parse.unquote(v)
        except Exception:
            pass
    return v


def _card_json(raw: str):
    """尽力把卡片 value 解成 dict；不是 JSON 就返回 None。"""
    try:
        obj = json.loads(_decode_card_value(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _math_latex(raw: str) -> str:
    """math 卡片的 value 实测有 3 种写法，统一取出 LaTeX 真身：

    1) `data:` + urlencode(JSON)，形如 {"code": "<LaTeX>", "src": "...__latex/x.svg"}
    2) HTML 实体转义后的同款 JSON
    3) 明文，形如 value="E = mc^2"

    正文里的公式（走 extract_math_from_asl）和 ASL 里的公式（走 render_cards）
    必须共用这一个函数，否则两条路径会各自漂移。
    """
    obj = _card_json(raw)
    return str((obj or {}).get("code") or _decode_card_value(raw)).strip()


def render_code_block(value: str) -> str:
    """codeblock 卡片：{"mode": "python", "code": "..."}。"""
    lang, code = "", _decode_card_value(value)
    obj = _card_json(value)
    if obj:
        lang = str(obj.get("mode") or obj.get("language") or obj.get("lang") or "").strip()
        code = str(obj.get("code") or obj.get("text") or "")
    code = code.strip("\n")
    if not code:
        return ""
    return f"\n\n```{lang}\n{code}\n```\n\n"


def render_diagram(value: str) -> str:
    """diagram 卡片：{"type": "mermaid"|"puml", "code": "..."}。"""
    obj = _card_json(value)
    if not obj or not str(obj.get("code") or "").strip():
        return ""
    kind = str(obj.get("type") or "mermaid").strip().lower()
    fence = {"puml": "plantuml", "plantuml": "plantuml", "mermaid": "mermaid"}.get(kind, kind or "text")
    return f"\n\n```{fence}\n{str(obj['code']).strip()}\n```\n\n"


def _card_link(value: str, prefix: str = "") -> str:
    """bookmarkInline / yuque 内嵌文档等：「有 URL 就还原成链接」，避免静默丢内容。"""
    obj = _card_json(value)
    if not obj:
        return ""
    url = str(obj.get("url") or obj.get("src") or "").strip()
    if not url:
        return ""
    detail = obj.get("detail") if isinstance(obj.get("detail"), dict) else {}
    title = str(detail.get("title") or obj.get("text") or "").strip() or url
    return f"\n\n{prefix}[{title}]({url})\n\n"


def render_cards(html_text: str, collector: BlockCollector) -> str:
    """把 Lake 卡片换成占位符。正文来自 ASL 时，复杂内容都以卡片形式出现。"""

    def _sub(m):
        a = _attrs(m.group(1))
        name = str(a.get("name", "")).strip().lower()
        value = a.get("value", "")
        obj = _card_json(value)

        if name == "math":
            latex = _math_latex(value)
            left = html_text[max(0, m.start() - 60):m.start()]
            right = html_text[m.end():m.end() + 60]
            alone = bool(re.search(r"<p>\s*$", left, re.I) and re.match(r"\s*</p>", right, re.I))
            return collector.add(render_math(latex, block=alone or bool(_DISPLAY_ENV_RE.search(latex))))
        if name in ("codeblock", "code", "code-block"):
            return collector.add(render_code_block(value))
        if name in ("diagram", "mermaid", "plantuml"):
            return collector.add(render_diagram(value))
        if name in ("bookmarkinline", "bookmark", "link"):
            text = _card_link(value)
            return collector.add(text) if text else ""
        if name == "yuque":
            text = _card_link(value, prefix="> 语雀内嵌文档：")
            return collector.add(text) if text else ""
        if name in ("hr", "divider", "separator"):
            # 也要走占位符：裸的 --- 若与上一行文本紧贴，会被 Markdown 当成 setext 标题下划线
            return collector.add("\n\n---\n\n")
        if name in ("image", "img"):
            src = str((obj or {}).get("src") or (obj or {}).get("url") or "").strip()
            if not src:
                src = _decode_card_value(value).strip()
            if not src:
                return ""
            alt = str((obj or {}).get("name") or "").strip()
            # 输出真正的 <img> 标签，这样图片本地化（--nopic 之外）才能接管它
            return f'\n\n<img src="{src}" alt="{alt}" />\n\n'
        # 未知卡片：能捞出 URL 就还原成链接，否则丢弃标签避免留下脏字符
        text = _card_link(value)
        return collector.add(text) if text else ""

    return CARD_FULL_RE.sub(_sub, html_text)


HEADING_RE = re.compile(r"<(h[1-6])\b[^>]*>(.*?)</\1>", re.I | re.S)
IMG_ANY_RE = re.compile(r"<img\b[^>]*/?>", re.I)


def hoist_images_out_of_headings(html_text: str) -> str:
    """把标题标签内部的 `<img>` 提到标题之前。

    markdownify 会**静默丢弃标题里的图片**：

        <h2><img src="x"/><span>标题</span></h2>   ->   ## 标题

    图片凭空消失，但下载早已完成、附件也落盘了，于是变成没人引用的孤儿。
    语雀里把封面图塞进标题是常见写法，实测踩到过一次（英语库「托业考试」）。
    绝大多数 HTML→Markdown 转换器都有类似行为，所以在转换前统一把图片挪出来，
    两条转换路径（markdownify 与纯标准库兜底）都能受益。
    """
    if "<h" not in html_text.lower():
        return html_text

    def _sub(m):
        inner = m.group(2)
        imgs = IMG_ANY_RE.findall(inner)
        if not imgs:
            return m.group(0)
        # 图片挪到标题前，保留原始先后关系（标题内的图通常本就是封面，排在最前）
        return "".join(imgs) + f"<{m.group(1)}>{IMG_ANY_RE.sub('', inner)}</{m.group(1)}>"

    return HEADING_RE.sub(_sub, html_text)


def replace_latex_images(html_text: str, formulas, collector: BlockCollector) -> str:
    """语雀把公式渲染成 cdn.nlark.com/...__latex/xxx.svg，按出现顺序换回 LaTeX。"""
    if not formulas:
        return html_text
    counter = itertools.count()

    def _sub(m):
        tag = m.group(0)
        src = _attrs_loose(tag, "src")
        if "latex" not in src.lower():
            return tag
        i = next(counter)
        if i >= len(formulas):
            return tag
        left = html_text[max(0, m.start() - 60):m.start()]
        right = html_text[m.end():m.end() + 60]
        block = bool(re.search(r"<p>\s*$", left, re.I) and re.match(r"\s*</p>", right, re.I))
        return collector.add(
            render_math(formulas[i], block=block or bool(_DISPLAY_ENV_RE.search(formulas[i])))
        )

    return IMG_RE.sub(_sub, html_text)


def _attrs_loose(tag: str, key: str) -> str:
    m = re.search(rf'{key}\s*=\s*"([^"]*)"', tag, re.I) or re.search(
        rf"{key}\s*=\s*'([^']*)'", tag, re.I
    )
    return html_mod.unescape(m.group(1)) if m else ""


def _attr_raw(tag: str, key: str) -> str:
    """取属性的**原样**字符串（不做 HTML 实体反转义）。

    用途是「在标签内部做字符串替换」：语雀的 `<img src>` 里带查询参数时会被写成
    `&amp;`，若拿 `html_mod.unescape` 之后的值去 `tag.replace`，就永远匹配不上——
    图片下载了、文件也落盘了，但 Markdown 里的链接原封不动，留下孤儿附件。
    """
    m = re.search(rf'{key}\s*=\s*"([^"]*)"', tag, re.I) or re.search(
        rf"{key}\s*=\s*'([^']*)'", tag, re.I
    )
    return m.group(1) if m else ""


# --------------------------------------------------------------------------
# 4. HTML -> Markdown
# --------------------------------------------------------------------------
_BLOCK_TAGS = {
    "p", "div", "section", "article", "header", "footer", "figure",
    "figcaption", "details", "summary", "main", "aside", "form", "dl",
}
_SKIP_TAGS = {"script", "style", "noscript", "iframe"}


class _SimpleHtmlToMd(HTMLParser):
    """markdownify 缺失时的兜底转换器，覆盖标题/段落/列表/表格/代码/链接/图片。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.pre = 0
        self.pre_lang = ""
        self.pre_buf: list[str] = []
        self.quote = 0
        self.lists: list[list] = []
        self.in_table = 0
        self.row: list[str] = []
        self.cell: list[str] | None = None
        self.rows: list[list[str]] = []
        self.href = None

    def _nl(self, n=1):
        self.parts.append("\n" * n)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in _SKIP_TAGS:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._nl(2)
            self.parts.append("#" * int(tag[1]) + " ")
        elif tag in _BLOCK_TAGS:
            self._nl(2)
            if self.quote:
                self.parts.append("> ")
        elif tag == "br":
            self.parts.append("  \n")
        elif tag == "hr":
            self._nl(2)
            self.parts.append("---")
            self._nl(2)
        elif tag in ("strong", "b"):
            self.parts.append("**")
        elif tag in ("em", "i"):
            self.parts.append("*")
        elif tag == "del":
            self.parts.append("~~")
        elif tag == "code" and not self.pre:
            self.parts.append("`")
        elif tag == "pre":
            self.pre += 1
            self.pre_buf = []
            self.pre_lang = _lang_from_attrs(a)  # 语言常挂在 <pre> 上
        elif tag == "code" and self.pre:
            self.pre_lang = _lang_from_attrs(a) or self.pre_lang  # <code> 上的优先
        elif tag == "blockquote":
            self.quote += 1
            self._nl(2)
        elif tag in ("ul", "ol"):
            self._nl(1)
            self.lists.append([tag, 0])
        elif tag == "li":
            if self.lists:
                self.lists[-1][1] += 1
                n = self.lists[-1][1]
                mark = f"{n}. " if self.lists[-1][0] == "ol" else "- "
                self._nl(1)
                self.parts.append("  " * (len(self.lists) - 1) + mark)
        elif tag == "a":
            self.href = a.get("href") or ""
            self.parts.append("[")
        elif tag == "img":
            src = a.get("src") or ""
            if src:
                self.parts.append(f"![{a.get('alt') or ''}]({src})")
        elif tag == "table":
            self.in_table += 1
            self.rows = []
            self._nl(2)
        elif tag == "tr" and self.in_table:
            self.row = []
        elif tag in ("td", "th") and self.in_table:
            self.cell = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in ("br", "hr", "img", "meta", "link", "input", "source", "col"):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "section",
                   "article", "figure", "figcaption"):
            self._nl(2)
        elif tag == "blockquote":
            self.quote = max(0, self.quote - 1)
            self._nl(2)
        elif tag in ("ul", "ol"):
            self._nl(1)
            if self.lists:
                self.lists.pop()
        elif tag in ("strong", "b"):
            self.parts.append("**")
        elif tag in ("em", "i"):
            self.parts.append("*")
        elif tag == "del":
            self.parts.append("~~")
        elif tag == "code" and not self.pre:
            self.parts.append("`")
        elif tag == "pre":
            self.pre = max(0, self.pre - 1)
            self._nl(2)
            self.parts.append("```" + self.pre_lang + "\n")
            self.parts.append("".join(self.pre_buf).strip("\n"))
            self.parts.append("\n```")
            self._nl(2)
            self.pre_buf = []
            self.pre_lang = ""
        elif tag == "a":
            href = self.href or ""
            self.href = None
            self.parts.append(f"]({href})" if href else "]")
        elif tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell).strip().replace("|", "\\|"))
            self.cell = None
        elif tag == "tr" and self.in_table:
            self.rows.append(self.row)
            self.row = []
        elif tag == "table" and self.in_table:
            self.in_table -= 1
            self._emit_table()

    def handle_data(self, data):
        if self.skip:
            return
        if self.cell is not None:
            self.cell.append(data)
        elif self.in_table:
            return  # 表格里的裸空白不参与正文
        elif self.pre:
            self.pre_buf.append(data)
        else:
            self.parts.append(re.sub(r"\s+", " ", data))

    def _emit_table(self):
        rows = [r for r in self.rows if any(c for c in r)]
        if not rows:
            return
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        head = rows[0]
        self.parts.append("| " + " | ".join(head) + " |\n")
        self.parts.append("|" + "---|" * width + "\n")
        for r in rows[1:]:
            self.parts.append("| " + " | ".join(r) + " |\n")
        self._nl(2)

    def result(self) -> str:
        return "".join(self.parts)


def tidy_md(md: str) -> str:
    """规范化 Markdown：清行尾空白、压缩多余空行，但代码围栏内原样保留。"""
    if not md:
        return ""
    md = md.replace("\r\n", "\n").replace("\r", "\n")

    def _rstrip(line: str) -> str:
        # 行尾两个空格是 Markdown 的硬换行，不能被清掉
        return line.rstrip() + "  " if line.endswith("  ") else line.rstrip()

    out, in_fence, blank_run = [], False, 0
    for line in md.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(_rstrip(line))
            blank_run = 0
            continue
        if in_fence:
            out.append(line)
            continue
        clean = _rstrip(line)
        if clean:
            blank_run = 0
        else:
            blank_run += 1
            if blank_run > 1:
                continue
        out.append(clean)
    return "\n".join(out).strip() + "\n"


def _lang_from_attrs(attrs: dict) -> str:
    """从标签属性里提取代码语言：优先 data-language，其次 class 里的 language-xxx。"""
    v = attrs.get("data-language") or ""
    if str(v).strip():
        return str(v).strip()
    classes = attrs.get("class") or ""
    if isinstance(classes, (list, tuple)):
        classes = " ".join(classes)
    m = re.search(r"(?:language|lang)-([\w+#.-]+)", str(classes), re.I)
    return m.group(1) if m else ""


def _code_language(el):
    """语雀的语言标注可能挂在 <pre> 上（data-language / class="ne-codeblock language-python"），
    也可能挂在内层 <code> 上（class="language-xxx"）。两处都要看，<code> 优先。"""
    nodes = []
    try:
        if hasattr(el, "find"):
            code = el.find("code")
            if code is not None:
                nodes.append(code)
    except Exception:
        pass
    nodes.append(el)
    for node in nodes:
        try:
            lang = _lang_from_attrs(dict(node.attrs))
        except Exception:
            lang = ""
        if lang:
            return lang
    return ""


def html_to_markdown(html_text: str) -> str:
    if not html_text or not html_text.strip():
        return ""
    if HAS_MARKDOWNIFY:
        opts = dict(
            heading_style="ATX",
            bullets="-",
            escape_asterisks=False,
            escape_underscores=False,
            escape_misc=False,
            code_language_callback=_code_language,
        )
        try:
            return tidy_md(_md(html_text, **opts))
        except TypeError:
            try:
                return tidy_md(_md(html_text, heading_style="ATX", bullets="-"))
            except Exception:
                pass
        except Exception:
            pass
    parser = _SimpleHtmlToMd()
    try:
        parser.feed(html_text)
        parser.close()
    except Exception:
        return tidy_md(re.sub(r"<[^>]+>", "", html_text))
    return tidy_md(parser.result())


# --------------------------------------------------------------------------
# 5. 图片本地化
# --------------------------------------------------------------------------
_EXT_RE = re.compile(
    r"\.(png|jpe?g|gif|webp|svg|bmp|tiff|ico|pdf|zip|rar|xlsx?|docx?|pptx?|mp4|mov|mp3|wav|csv|txt)(?:\?|#|$)",
    re.I,
)


def guess_ext(url: str, content_type: str = "") -> str:
    m = _EXT_RE.search(url or "")
    if m:
        ext = m.group(1).lower()
        return ".jpg" if ext == "jpeg" else f".{ext}"
    ct = (content_type or "").split(";")[0].strip().lower()
    return {
        "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
        "image/webp": ".webp", "image/svg+xml": ".svg", "application/pdf": ".pdf",
    }.get(ct, ".bin")


class ImageDownloader:
    def __init__(self, enabled=True, timeout=20, attempts=3):
        self.enabled = enabled
        self.timeout = timeout
        self.attempts = max(1, attempts)
        self.cache: dict[str, str] = {}
        self.ok = 0
        self.fail = 0
        self.only_local = 0                     # src 不是 URL（裸文件名），无法下载
        self.local_names: list[str] = []

    def fetch(self, url: str):
        """下载单张图片，返回 (bytes, content_type)；失败返回 None。

        CDN 偶发限流 / 抖动很常见（实测 96 张里 9 张首轮失败，原地重试后 100% 成功），
        所以带上退避重试。同时先剥掉 `#averageHue=...&clientId=...` 之类的 URL 片段，
        那部分是语雀的编辑态参数，对取图无用。
        """
        clean = url.split("#", 1)[0]
        for i in range(self.attempts):
            try:
                req = urllib.request.Request(clean, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read(), resp.headers.get("Content-Type", "")
            except Exception:
                if i + 1 < self.attempts:
                    time.sleep(0.5 * (i + 1))       # 0.5s, 1.0s 退避
        return None

    def localize(self, html_text: str, dest_dir: Path, doc_title: str, allocator: NameAllocator) -> str:
        """把 <img src> 下载到 dest_dir/_attachments/ 并改写为相对路径。"""
        if not html_text or "<img" not in html_text.lower():
            return html_text
        attach = dest_dir / ATTACH_DIR
        seq = itertools.count(1)

        def _sub(m):
            tag = m.group(0)
            raw = _attr_raw(tag, "src")             # 用于替换：保留 &amp; 原样
            src = html_mod.unescape(raw)            # 用于请求：需要真正的 & 与参数
            if (not src or src.startswith("data:") or src.startswith("./")
                    or "__latex" in src.lower() or not self.enabled):
                return tag
            if "://" not in src:
                # 源里留的是 `0.png` / `Untitled 3.png` 这类裸文件名（多为从别处粘贴时
                # 残留的本地文件名），既不是可下载的 URL，也不是「网络失败」，
                # 混进失败计数会把排查方向带偏，所以单独记账。
                self.only_local += 1
                self.local_names.append(src)
                return tag
            cache_key = f"{dest_dir}|{src}"
            if cache_key in self.cache:
                return tag.replace(raw, self.cache[cache_key], 1)
            got = self.fetch(src)
            if not got:
                self.fail += 1
                return tag
            data, ctype = got
            ext = guess_ext(src, ctype)
            stem = sanitize_name(f"{doc_title}_{next(seq):03d}", "img")
            try:
                attach.mkdir(parents=True, exist_ok=True)
                target = allocator.allocate(attach, stem, ext)
                target.write_bytes(data)
            except OSError:
                self.fail += 1
                return tag
            self.ok += 1
            rel = f"./{ATTACH_DIR}/{target.name}"
            self.cache[cache_key] = rel
            return tag.replace(raw, rel, 1)

        return IMG_RE.sub(_sub, html_text)


# --------------------------------------------------------------------------
# 6. 表格文档（lakesheet）
# --------------------------------------------------------------------------
def _decompress(blob: bytes) -> bytes:
    for fn in (
        zlib.decompress,
        gzip.decompress,
        lambda b: zlib.decompress(b, -15),
        lambda b: zlib.decompress(b, 47),
    ):
        try:
            return fn(blob)
        except Exception:
            continue
    return blob


def _fmt_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _cell_text(cell) -> str:
    if isinstance(cell, dict):
        v = cell.get("v")
        if isinstance(v, dict):
            return _fmt_cell(v.get("text") or v.get("url") or v.get("value") or "")
        if v is None:
            for k in ("text", "value", "url"):
                if cell.get(k):
                    return _fmt_cell(cell[k])
            return ""
        return _fmt_cell(v)
    return _fmt_cell(cell)


def _rows_from_data(data) -> list[list[str]]:
    if not isinstance(data, dict):
        return []
    grid, max_col = {}, -1
    for rk, cols in data.items():
        r = _int(rk, None)
        if r is None or not isinstance(cols, dict):
            continue
        row = {}
        for ck, cell in cols.items():
            c = _int(ck, None)
            if c is None:
                continue
            row[c] = _cell_text(cell)
            max_col = max(max_col, c)
        grid[r] = row
    if not grid:
        return []
    return [[grid[r].get(c, "") for c in range(max_col + 1)] for r in sorted(grid)]


def parse_lakesheet(body) -> list[list[str]]:
    """三层嵌套：body(JSON 字符串) -> sheet(latin-1 压缩字节) -> 解压后的表格 JSON。"""
    obj = body
    if isinstance(obj, (bytes, bytearray)):
        obj = json.loads(bytes(obj).decode("utf-8", "replace"))
    if isinstance(obj, str):
        obj = json.loads(obj)
    if not isinstance(obj, dict):
        raise ValueError("不是合法的 lakesheet 结构")

    raw = obj.get("sheet")
    if raw is None:
        data = obj.get("data", obj)
        if isinstance(data, str):
            data = json.loads(_decompress(data.encode("latin-1", "ignore")).decode("utf-8", "replace"))
        return _rows_from_data(data)

    if isinstance(raw, str):
        blob = raw.encode("latin-1", "ignore")
    elif isinstance(raw, (bytes, bytearray)):
        blob = bytes(raw)
    else:
        return _rows_from_data(raw.get("data") if isinstance(raw, dict) else raw)

    decoded = _decompress(blob).decode("utf-8", "replace")
    payload = json.loads(decoded)
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    return _rows_from_data(payload)


def excel_serial_to_date(rows: list[list[str]]) -> list[list[str]]:
    """可选：把 Excel 日期序列号（20000~80000）转成 YYYY-MM-DD。"""
    import datetime

    out = []
    for row in rows:
        new = []
        for cell in row:
            try:
                f = float(cell)
                if f.is_integer() and 20000 <= f <= 80000:
                    d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(f))
                    new.append(d.isoformat())
                    continue
            except (TypeError, ValueError):
                pass
            new.append(cell)
        out.append(new)
    return out


def rows_to_csv_text(rows: list[list[str]]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


# --------------------------------------------------------------------------
# 7. 主流程
# --------------------------------------------------------------------------
class Options:
    def __init__(self, **kw):
        self.nopic = kw.get("nopic", False)
        self.nosheet = kw.get("nosheet", False)
        self.keep_json = kw.get("keep_json", False)
        self.excel_dates = kw.get("excel_dates", False)
        self.quiet = kw.get("quiet", False)


def doc_kind(doc: dict, meta_entry: dict | None = None) -> str:
    fmt = str(doc.get("format") or (meta_entry or {}).get("format") or "").strip().lower()
    typ = str(doc.get("type") or (meta_entry or {}).get("type") or "").strip().lower()
    if fmt == "lakebook" or typ == "board":
        return "board"
    if fmt == "lakesheet" or typ in ("sheet", "table"):
        return "sheet"
    if fmt == "lake" or typ == "doc":
        return "doc"
    if isinstance(doc.get("body"), str) and doc["body"].lstrip().startswith("{"):
        return "sheet"
    return "doc"


def convert_one(
    slug: str,
    item: dict,
    doc: dict,
    meta_entry: dict | None,
    dest_dir: Path,
    allocator: NameAllocator,
    downloader: ImageDownloader,
    opts: Options,
    keep_dir: Path | None,
):
    """把一篇文档转成文件，返回 (状态, 输出路径, 备注)。"""
    title = item.get("title") or (meta_entry or {}).get("title") or doc.get("title") or slug
    body = doc.get("body")
    if body is None:
        body = doc.get("body_html") or ""
    asl = doc.get("body_asl") or doc.get("body_lake") or ""
    kind = doc_kind(doc, meta_entry)

    if keep_dir is not None:
        keep_dir.mkdir(parents=True, exist_ok=True)
        try:
            (keep_dir / f"{slug}.json").write_text(
                json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    if kind == "board":
        out = allocator.allocate(dest_dir, sanitize_name(title), ".json")
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return "board", out, "画板无官方转换规范，已导出原始 JSON"

    if kind == "sheet":
        if opts.nosheet:
            return "skipped", None, "按 --nosheet 跳过表格文档"
        try:
            rows = parse_lakesheet(body)
        except Exception as exc:
            out = allocator.allocate(dest_dir, sanitize_name(title), ".json")
            out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            return "error", out, f"表格解析失败({exc})，已导出原始 JSON"
        if opts.excel_dates:
            rows = excel_serial_to_date(rows)
        out = allocator.allocate(dest_dir, sanitize_name(title), ".csv")
        out.write_text(rows_to_csv_text(rows), encoding="utf-8")
        return "sheet", out, f"{len(rows)} 行"

    # 普通文档
    html_text = body if isinstance(body, str) else ""
    asl_text = asl if isinstance(asl, str) else ""
    source = "body"
    if not html_text.strip() and asl_text.strip():
        # 部分导出的 doc.body 为空，正文只存在 body_asl 里（内容是 HTML 风格的 Lake 源码）
        html_text = asl_text
        source = "asl"

    collector = BlockCollector()
    html_text = render_cards(html_text, collector)
    html_text = hoist_images_out_of_headings(html_text)
    formulas = extract_math_from_asl(asl_text)
    if formulas:
        html_text = replace_latex_images(html_text, formulas, collector)
    html_text = downloader.localize(html_text, dest_dir, sanitize_name(title), allocator)
    md = tidy_md(collector.apply(html_to_markdown(html_text)))
    note = ""
    if source == "asl":
        note = "正文来自 body_asl（doc.body 为空）"
        if not md.strip():
            md = f"<!-- 语雀文档正文为空：{title} -->\n"
    elif not md.strip():
        md = f"<!-- 语雀文档正文为空：{title} -->\n"
    out = allocator.allocate(dest_dir, sanitize_name(title), ".md")
    out.write_text(md, encoding="utf-8")
    return "doc", out, note


def process_lakebook(lakebook_path: Path, out_root: Path, opts: Options) -> dict:
    stats = Counter()
    manifest = []
    stem = sanitize_name(lakebook_path.stem, "lakebook")

    with tempfile.TemporaryDirectory(prefix="lakebook_") as tmp:
        repo_dir = extract_lakebook(lakebook_path, Path(tmp))
        book, toc, docs_meta = load_meta(repo_dir)
        name = sanitize_name(book_name(book, lakebook_path), stem)
        root = out_root / name
        root.mkdir(parents=True, exist_ok=True)

        idx = index_doc_files(repo_dir)
        if not toc:  # tocYml 缺失时退化为按 meta.docs 顺序
            toc = [
                {"type": "DOC", "title": m.get("title") or s, "level": 0, "url": s}
                for s, m in docs_meta.items()
            ]

        allocator = NameAllocator()
        downloader = ImageDownloader(enabled=not opts.nopic)
        keep_dir = (out_root / "_raw" / name) if opts.keep_json else None
        stack: list[str] = []
        seen_docs = set()

        for pos, item in enumerate(toc):
            level = max(0, item["level"])
            while len(stack) > level:
                stack.pop()
            if item["type"] == "TITLE":
                stack.append(sanitize_name(item["title"], "分组"))
                stats["groups"] += 1
                continue

            slug = item["url"]
            parent = root.joinpath(*stack)
            parent.mkdir(parents=True, exist_ok=True)

            # 语雀允许「文档嵌套文档」：DOC 也可以是下级条目的父节点。
            # 这类父文档既要输出自身（<name>.md），又要承担目录角色（<name>/）。
            # 先入栈，这样即使本文档自身转换失败，下级仍能落到正确位置。
            if has_children(toc, pos, item):
                stack.append(sanitize_name(item["title"] or slug, "文档"))
                stats["nested_doc_dirs"] += 1

            meta_entry = docs_meta.get(slug)

            doc = {}
            if slug and slug in idx:
                try:
                    doc = load_doc(idx[slug])
                except Exception as exc:
                    stats["error"] += 1
                    manifest.append({"title": item["title"], "slug": slug,
                                     "status": "error", "note": f"读取失败: {exc}"})
                    continue
            elif meta_entry is None:
                stats["error"] += 1
                manifest.append({"title": item["title"], "slug": slug,
                                 "status": "error", "note": "目录里有条目但找不到对应 json"})
                continue
            else:
                doc = dict(meta_entry)
            seen_docs.add(slug)

            status, out_path, note = convert_one(
                slug, item, doc, meta_entry, parent, allocator, downloader, opts, keep_dir
            )
            stats[status] += 1
            manifest.append({
                "title": item["title"] or doc.get("title") or slug,
                "slug": slug,
                "type": doc_kind(doc, meta_entry),
                "level": item["level"],
                "status": status,
                "path": str(out_path.relative_to(root)) if out_path else None,
                "note": note,
            })

        # $meta.docs 里存在但目录树里没有的文档，兜底转一遍
        for slug, meta_entry in docs_meta.items():
            if slug in seen_docs or slug not in idx:
                continue
            try:
                doc = load_doc(idx[slug])
            except Exception:
                continue
            item = {"type": "DOC", "title": meta_entry.get("title") or slug,
                    "level": 0, "url": slug}
            status, out_path, note = convert_one(
                slug, item, doc, meta_entry, root, allocator, downloader, opts, keep_dir
            )
            stats[status] += 1
            manifest.append({
                "title": item["title"], "slug": slug, "type": doc_kind(doc, meta_entry),
                "level": 0, "status": status,
                "path": str(out_path.relative_to(root)) if out_path else None,
                "note": note + "（未出现在目录树中，已放在根目录）",
            })

        (root / "_manifest.json").write_text(
            json.dumps(
                {"book": name, "source": str(lakebook_path), "docs": manifest},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "lakebook": str(lakebook_path),
            "book": name,
            "root": str(root),
            "stats": dict(stats),
            "images": {
                "ok": downloader.ok,
                "fail": downloader.fail,
                "only_local": downloader.only_local,
                "local_names": sorted(set(downloader.local_names))[:50],
            },
        }


# --------------------------------------------------------------------------
# 8. CLI
# --------------------------------------------------------------------------
def collect_inputs(paths) -> list[Path]:
    files = []
    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_dir():
            files.extend(sorted(p.glob("*.lakebook")))
        elif p.exists():
            files.append(p)
        else:
            print(f"[warn] 不存在，已跳过：{p}", file=sys.stderr)
    return files


def print_tree(toc):
    """打印目录树：`[D]` 纯分组，`[+]` 既是文档又带了级文档，其余为普通文档。"""
    for pos, item in enumerate(toc):
        pad = "    " * max(0, item["level"])
        if item["type"] == "TITLE":
            mark = "[D]"
        elif has_children(toc, pos, item):
            mark = "[+]"
        else:
            mark = "   "
        print(f"{pad}{mark} {item['title']}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="解析语雀 .lakebook 导出包，还原为 Markdown / CSV + 目录树",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("inputs", nargs="+", help=".lakebook 文件，或包含它们的目录")
    ap.add_argument("-o", "--output", default="./lakebook_out", help="输出根目录（默认 ./lakebook_out）")
    ap.add_argument("--list", action="store_true", help="只打印目录树，不做转换")
    ap.add_argument("--nopic", action="store_true", help="不下载图片，保留原始外链 URL")
    ap.add_argument("--nosheet", action="store_true", help="跳过表格文档")
    ap.add_argument("--keep-json", action="store_true", help="额外保留每篇文档的原始 JSON")
    ap.add_argument("--excel-dates", action="store_true", help="把表格中的 Excel 日期序列号转成日期")
    ap.add_argument("-q", "--quiet", action="store_true", help="安静模式")
    args = ap.parse_args(argv)

    files = collect_inputs(args.inputs)
    if not files:
        print("没有找到可处理的 .lakebook 文件", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"markdownify: {'on' if HAS_MARKDOWNIFY else 'off (使用内置兜底转换)'} | "
              f"pyyaml: {'on' if HAS_YAML else 'off (使用内置兜底解析)'}")

    if args.list:
        for f in files:
            with tempfile.TemporaryDirectory() as tmp:
                repo = extract_lakebook(f, Path(tmp))
                book, toc, docs_meta = load_meta(repo)
                print(f"\n== {f.name} ==  {book_name(book, f)}  "
                      f"({len(toc)} 个目录条目 / {len(docs_meta)} 篇文档)")
                print_tree(toc)
        return 0

    opts = Options(
        nopic=args.nopic, nosheet=args.nosheet,
        keep_json=args.keep_json, excel_dates=args.excel_dates, quiet=args.quiet,
    )
    out_root = Path(args.output).expanduser()
    results = []
    for f in files:
        try:
            res = process_lakebook(f, out_root, opts)
        except Exception as exc:
            print(f"[error] {f.name}: {exc}", file=sys.stderr)
            results.append({"lakebook": str(f), "error": str(exc)})
            continue
        results.append(res)
        if not args.quiet:
            s = res["stats"]
            print(f"\n[ok] {Path(res['lakebook']).name} -> {res['root']}")
            print(f"     文档 {s.get('doc', 0)} | 表格 {s.get('sheet', 0)} | 画板 {s.get('board', 0)}"
                  f" | 分组目录 {s.get('groups', 0)} | 嵌套文档目录 {s.get('nested_doc_dirs', 0)}"
                  f" | 跳过 {s.get('skipped', 0)} | 失败 {s.get('error', 0)}")
            if not args.nopic:
                img = res["images"]
                line = f"     图片 成功 {img['ok']} / 失败 {img['fail']}"
                if img.get("only_local"):
                    line += f" / 源文件名为裸文件名无法下载 {img['only_local']}"
                print(line)
                if img.get("local_names") and not args.quiet:
                    print(f"          （如：{', '.join(img['local_names'][:5])}）")

    (out_root / "_last_run.json").parent.mkdir(parents=True, exist_ok=True)
    (out_root / "_last_run.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if not has_errors(results) else 2


def has_errors(results) -> bool:
    for r in results:
        if "error" in r or (r.get("stats") or {}).get("error"):
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
