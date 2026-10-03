#!/usr/bin/env python3
"""校验 english-essay-rewrite 的产物文件。

检查项：
  1. 命名是否遵循 <source-stem>-formal.md / <source-stem>-casual.md
  2. 四个必需章节是否齐全且非空
  3. 正式版正文是否混入缩略形式（最常见的语体泄漏）
  4. 正式版正文是否混入口语话语标记
  5. 口语版正文是否确实具备口语特征（缩略 + 话语标记）
  6. 原稿中的技术专名是否在两版中都保留（信息对等性启发式检查）

用法：
    check_rewrite.py <output-dir> --source <draft-file>
    check_rewrite.py <output-dir> --stem <source-stem>

退出码：0 = 通过（可能有 warning）；1 = 存在 error。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "## Rewritten Text",
    "## 修改理由说明",
    "## 重点词汇、短语及常用搭配",
    "## 迁移练习",
]

# 缩略形式检测：用模式而非硬编码清单，避免漏掉 Here's / you'll 这类形式。
# 关键约束：不能把属格（system's / application's）误判为缩略——属格在正式写作里完全合法。
PRONOUN_S_FORMS = (
    "here", "there", "what", "who", "where", "when", "how", "that", "it", "he", "she", "let",
    "this", "these", "those", "somebody", "someone", "something", "nobody", "nothing", "one",
)

# 名词 + 's 后若跟这些词，说明 's 是 is / has 的缩略（the data's in、the app's written），
# 而不是属格。属格后面跟的是名词（the customer's portfolio），不会落进这个集合。
CONTRACTION_FOLLOW_WORDS = [
    # 介词 / 副词 / 小品词
    "in", "out", "on", "off", "up", "down", "back", "over", "through", "around", "about",
    "into", "onto", "with", "for", "from", "at", "to", "by",
    "here", "there", "now", "then", "still", "already", "just", "only", "not", "no", "so",
    "too", "very", "really", "quite", "all", "done", "gone",
    # 常见过去分词（被动 / 完成结构）
    "been", "being", "got", "gotten", "written", "built", "made", "set", "based",
    "coming", "going", "running", "working", "finished", "deployed", "started", "added",
    "changed", "broken", "fixed", "called", "named", "using", "doing", "getting",
    "loaded", "stored", "shipped", "moved", "put", "taken", "given", "seen", "shown",
    "kept", "held",
]

CONTRACTION_PATTERNS = [
    re.compile(r"\b\w*n't\b", re.IGNORECASE),                 # don't / can't / won't / isn't ...
    re.compile(r"\b\w+'(?:re|ve|ll|m)\b", re.IGNORECASE),     # we're / I've / you'll / I'm
    re.compile(
        r"\b(?:" + "|".join(PRONOUN_S_FORMS) + r")'s\b",
        re.IGNORECASE,
    ),                                                        # here's / it's / let's / that's ...
    re.compile(
        r"\b(?!(?:" + "|".join(PRONOUN_S_FORMS) + r")'s)\w+'s\s+"
        r"(?:" + "|".join(CONTRACTION_FOLLOW_WORDS) + r")\b",
        re.IGNORECASE,
    ),                                                        # data's in / frontend's written
]
# 无需模式即可判定的口语缩写词
CASUAL_ONLY_WORDS = ["gonna", "wanna", "gotta", "ain't", "y'all"]

CASUAL_MARKERS = [
    "basically", "kind of", "sort of", "pretty much", "you know",
    "a bit", "a lot of", "stuff", "thing", "hi,", "okay", "ok,", "well,",
    "really", "just",
    # 口语常用的其他标记
    "all sorts of", "a bunch of", "here's", "there's", "that's",
    "so,", "and one of", "plus", "anyway",
]

# 句首 so 单独判定：只在句首/段首出现时才算口语标记，
# 避免误伤正式的 so that / so as to。
SENTENCE_INITIAL_SO = re.compile(r"(?:^|[.!?]\s+)so\b", re.IGNORECASE | re.MULTILINE)

# 正式版正文里不该出现的口语标记（不含单独的 so，so that 等正式用法需要放行）
FORMAL_FORBIDDEN = [
    "basically", "kind of", "sort of", "pretty much", "you know",
    "gonna", "wanna", "gotta", "ain't", "stuff", "a bunch of",
]

# 专名等价映射：原稿写左边，口语版可写右边，不算信息丢失
TERM_EQUIVALENTS = {
    "pgsql": {"pgsql", "postgres", "postgresql"},
    "postgresql": {"pgsql", "postgres", "postgresql"},
    "postgres": {"pgsql", "postgres", "postgresql"},
}

# 提取专名时要排除的句首/高频普通词
PROPER_NOUN_STOPLIST = {
    "i", "today", "this", "that", "there", "it", "the", "a", "an", "my", "we",
    "in", "on", "at", "and", "but", "so", "if", "as", "is", "are", "was", "were",
}

# 术语归一化：把官方拆分写法合并，避免 "Open Telemetry" 与 "OpenTelemetry" 被当成两个词
NORMALIZE_PATTERNS = [
    (re.compile(r"\bOpen\s+Telemetry\b", re.IGNORECASE), "OpenTelemetry"),
]

MIN_CONTRACTIONS_CASUAL = 3
MIN_MARKERS_CASUAL = 1


class Result:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def info(self, msg: str) -> None:
        self.infos.append(msg)


def split_sections(text: str) -> dict[str, str]:
    """按二级标题切分 Markdown，返回 {标题: 正文}。"""
    pattern = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        title = "#" * 2 + " " + m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()
    return sections


def lookup_section(sections: dict[str, str], required: str) -> tuple[bool, str]:
    """按前缀匹配章节，容忍标题后缀，如「## 迁移练习（建议自己写一遍）」。

    返回 (是否存在, 正文)。
    """
    for title, body in sections.items():
        if title.startswith(required):
            return True, body
    return False, ""


def find_terms(text: str) -> set[str]:
    """提取正文中的技术专名/大写词（含驼峰），用于信息对等性检查。

    只取**句中**的大写词：句首词（换行后、句末标点后）通常是 Here / Startup /
    Assume 这类被改写的普通词，把它们当专名会产生大量假告警。
    """
    for pattern, repl in NORMALIZE_PATTERNS:
        text = pattern.sub(repl, text)

    # 句首位置集合：字符串/行开头，以及句末标点 + 空白之后
    sentence_starts = {m.end() for m in re.finditer(r"(?:^|[.!?;:]\s+)", text, re.MULTILINE)}

    terms: set[str] = set()
    for m in re.finditer(r"\b[A-Za-z][A-Za-z0-9+#.\-]*\b", text):
        if m.start() in sentence_starts:
            continue
        token = m.group(0)
        if len(token) < 4:
            continue
        if token[0].isupper() and token.lower() not in PROPER_NOUN_STOPLIST:
            terms.add(token.lower())
    return terms


def find_contractions(text: str) -> dict[str, int]:
    """找出口语缩略形式，返回 {小写形式: 出现次数}。

    按出现次数统计而非去重——`I've` 用了三次就是三处口语特征，
    去重会让一篇充满缩略形式的文本被误判为"缩略偏少"。

    属格（system's / application's / Prometheus's）不在命中范围内——
    属格在正式写作中完全合法，误报会让这个检查失去可信度。
    """
    counts: dict[str, int] = {}
    for pattern in CONTRACTION_PATTERNS:
        for m in pattern.finditer(text):
            key = m.group(0).lower()
            counts[key] = counts.get(key, 0) + 1
    lowered = text.lower()
    for word in CASUAL_ONLY_WORDS:
        found = len(re.findall(rf"\b{re.escape(word)}\b", lowered))
        if found:
            counts[word] = counts.get(word, 0) + found
    return counts


def check_file(path: Path, register: str, res: Result) -> str:
    """校验单个产物文件，返回 Rewritten Text 正文。"""
    rel = path.name
    if not path.exists():
        res.error(f"[{rel}] 文件不存在")
        return ""

    text = path.read_text(encoding="utf-8")
    sections = split_sections(text)

    # 2. 必需章节
    for sec in REQUIRED_SECTIONS:
        found, body_text = lookup_section(sections, sec)
        if not found:
            res.error(f"[{rel}] 缺少章节：{sec}")
        elif len(body_text) < 40:
            res.warn(f"[{rel}] 章节内容过短（<40 字符）：{sec}")

    _, body = lookup_section(sections, "## Rewritten Text")
    if not body:
        res.error(f"[{rel}] Rewritten Text 为空，跳过语言特征检查")
        return ""

    body_lower = body.lower()

    # 3. 正式版不得出现缩略形式
    if register == "formal":
        hits = find_contractions(body)
        if hits:
            detail = ", ".join(
                f"{form}×{n}" if n > 1 else form for form, n in sorted(hits.items())
            )
            res.error(f"[{rel}] 正式版正文出现缩略形式（语体泄漏）：{detail}")

    # 4. 正式版不得出现口语话语标记
    if register == "formal":
        hits = sorted({m for m in FORMAL_FORBIDDEN if m in body_lower})
        if hits:
            res.error(f"[{rel}] 正式版正文出现口语话语标记：{', '.join(hits)}")

    # 5. 口语版应确实口语化
    if register == "casual":
        n_contr = sum(find_contractions(body).values())
        marks = {m for m in CASUAL_MARKERS if m in body_lower}
        if SENTENCE_INITIAL_SO.search(body):
            marks.add("so（句首）")
        n_mark = len(marks)
        if n_contr < MIN_CONTRACTIONS_CASUAL:
            res.warn(f"[{rel}] 口语版缩略形式偏少（{n_contr} 处，建议 ≥{MIN_CONTRACTIONS_CASUAL}）")
        if n_mark < MIN_MARKERS_CASUAL:
            res.warn(f"[{rel}] 口语版缺少话语标记（如 so / basically / a bit）")
        res.info(f"[{rel}] 口语特征：缩略 {n_contr} 处，话语标记 {n_mark} 种")

    return body


def check_parity(bodies: dict[str, str], source: Path, res: Result) -> None:
    """检查原稿中的技术专名是否在两种语体中都保留。"""
    if not source.exists():
        res.warn(f"原稿不存在，跳过信息对等性检查：{source}")
        return

    src_text = source.read_text(encoding="utf-8")
    terms = find_terms(src_text)
    if not terms:
        res.info("原稿未识别出技术专名，跳过信息对等性检查")
        return

    for register, body in bodies.items():
        if not body:
            continue
        body_lower = body.lower()
        missing = []
        for term in sorted(terms):
            variants = TERM_EQUIVALENTS.get(term, {term})
            if not any(re.search(rf"\b{re.escape(v)}\b", body_lower) for v in variants):
                missing.append(term)
        if missing:
            res.warn(
                f"[{register}] 原稿专名未在两版中体现，请确认是刻意省略还是信息丢失："
                f"{', '.join(missing)}"
            )


def main() -> int:
    ap = argparse.ArgumentParser(description="校验 english-essay-rewrite 的产物文件")
    ap.add_argument("output_dir", help="产物所在目录（通常是 output/）")
    ap.add_argument("--source", help="原稿路径（draft/xxx.md），用于推导命名并做对等性检查")
    ap.add_argument("--stem", help="原稿文件名主干（不含扩展名）；与 --source 二选一")
    args = ap.parse_args()

    out_dir = Path(args.output_dir).expanduser().resolve()
    if not out_dir.is_dir():
        print(f"ERROR: 输出目录不存在：{out_dir}")
        return 1

    if args.source:
        source = Path(args.source).expanduser().resolve()
        stem = source.stem
    elif args.stem:
        source = out_dir.parent / "draft" / f"{args.stem}.md"
        stem = args.stem
    else:
        print("ERROR: 需要 --source 或 --stem 之一来推导期望文件名")
        return 1

    res = Result()
    expected = {
        "formal": out_dir / f"{stem}-formal.md",
        "casual": out_dir / f"{stem}-casual.md",
    }

    bodies: dict[str, str] = {}
    for register, path in expected.items():
        bodies[register] = check_file(path, register, res)

    check_parity(bodies, source, res)

    # 输出报告
    print("=" * 62)
    print(f"产物校验报告  |  stem = {stem}")
    print("=" * 62)
    for register, path in expected.items():
        status = "OK  " if path.exists() else "MISS"
        print(f"  [{status}] {path.name}")

    for label, items in (("ERROR", res.errors), ("WARN", res.warnings), ("INFO", res.infos)):
        print(f"\n--- {label} ({len(items)}) ---")
        if not items:
            print("  (none)")
        for item in items:
            print(f"  - {item}")

    print()
    if res.errors:
        print(f"结论：不通过（{len(res.errors)} 个 error，{len(res.warnings)} 个 warning）")
        return 1
    print(f"结论：通过（{len(res.warnings)} 个 warning）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
