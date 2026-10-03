#!/usr/bin/env python3
"""把文本朗读成 m4a 音频（macOS 内置语音合成，离线、无网络请求）。

流程：say -> aiff -> afconvert -> m4a -> afinfo 校验

用法示例：
    # 列出可用英文发音人
    tts.py --list-voices --english

    # 单篇朗读
    tts.py article.txt -o output -v Samantha -r 180

    # 多版本对照：正式版英式，口语版美式，各带一句播报
    tts.py formal.txt  -o output -v Daniel   -r 165 --label "Version one. Formal register."  -n art-formal-reading
    tts.py casual.txt  -o output -v Samantha -r 180 --label "Version two. Casual register."  -n art-casual-reading

    # 直接朗读字符串
    tts.py --text "Hello world." -o /tmp -n demo

退出码：0 = 成功；1 = 失败。
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PRONOUNCE_MAP = SCRIPT_DIR.parent / "references" / "pronunciation.json"

# 发音人偏好顺序（按音质与稳定性）
PREFERRED_US = ["Samantha", "Alex", "Ava", "Allison", "Susan", "Tom", "Fred", "Victoria"]
PREFERRED_GB = ["Daniel", "Serena", "Kate", "Oliver", "Arthur"]
PREFERRED_ZH = ["Tingting", "Meijia", "Sinji", "Li-mu", "Yu-shu"]

DEFAULT_VOICE = "Samantha"
DEFAULT_RATE = 175
MIN_RATE, MAX_RATE = 80, 400


class TTSError(RuntimeError):
    pass


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def require_macos() -> None:
    if platform.system() != "Darwin":
        raise TTSError(
            f"本 skill 依赖 macOS 内置语音合成，当前系统为 {platform.system()}，不可用。"
        )
    for tool in ("say", "afconvert"):
        if not shutil.which(tool):
            raise TTSError(f"缺少系统命令 {tool}，请确认在 macOS 上运行。")


def list_voices(english_only: bool = False) -> list[tuple[str, str, str]]:
    """返回 [(name, locale, sample)]。"""
    proc = run(["say", "-v", "?"])
    if proc.returncode != 0:
        raise TTSError(f"读取发音人列表失败：{proc.stderr.strip()}")

    voices: list[tuple[str, str, str]] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in re.split(r"\s{2,}", line.strip())]
        if len(parts) < 2:
            continue
        name, locale = parts[0], parts[1]
        sample = parts[2].lstrip("# ").strip() if len(parts) > 2 else ""
        if english_only and not locale.lower().startswith(("en_", "en-")):
            continue
        voices.append((name, locale, sample))
    return voices


def voice_exists(name: str) -> bool:
    return any(v[0].lower() == name.lower() for v in list_voices())


def load_pronounce_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TTSError(f"发音替换表不是合法 JSON：{path}（{exc}）") from exc
    # 允许以 "_comment" 之类的键存说明，一律跳过下划线开头的键
    return {k: v for k, v in data.items() if isinstance(v, str) and not k.startswith("_")}


def apply_pronounce(text: str, mapping: dict[str, str]) -> tuple[str, list[tuple[str, str]]]:
    """应用发音替换，返回 (新文本, 实际发生的替换列表)。"""
    applied: list[tuple[str, str]] = []
    for src, dst in mapping.items():
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(src)}(?![A-Za-z0-9_])")
        if pattern.search(text):
            text = pattern.sub(dst, text)
            applied.append((src, dst))
    return text, applied


def strip_markdown(text: str) -> str:
    """剥掉 Markdown 标记，避免合成器念出符号。"""
    # 代码块整体删除（朗读代码没有意义且会读出符号）
    text = re.sub(r"```.*?```", "\n", text, flags=re.DOTALL)
    # 行内代码保留内容、去掉反引号
    text = re.sub(r"`([^`]*)`", r"\1", text)
    # 图片整体删除，链接保留文字
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # 标题、引用、列表符号
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}[-*+]\s+", "", text, flags=re.MULTILINE)
    # 表格与分隔线整行删除
    text = re.sub(r"^\s*\|.*\|\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # 强调与删除线标记
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    # 压缩多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def synthesize(text: str, voice: str, rate: int, aiff_path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        txt_path = Path(fh.name)
    try:
        proc = run(["say", "-v", voice, "-r", str(rate), "-f", str(txt_path), "-o", str(aiff_path)])
        if proc.returncode != 0:
            raise TTSError(f"语音合成失败：{proc.stderr.strip() or proc.stdout.strip()}")
    finally:
        txt_path.unlink(missing_ok=True)


def convert(aiff_path: Path, m4a_path: Path) -> None:
    """aiff -> m4a。注意：不要用 -b 码率参数，会触发 '!dat' 属性错误。"""
    m4a_path.parent.mkdir(parents=True, exist_ok=True)
    proc = run(["afconvert", "-f", "m4af", "-d", "aac", "-q", "127", str(aiff_path), str(m4a_path)])
    if proc.returncode != 0 or not m4a_path.exists():
        raise TTSError(f"音频转码失败：{proc.stderr.strip() or proc.stdout.strip()}")


def duration_seconds(path: Path) -> float | None:
    proc = run(["afinfo", str(path)])
    match = re.search(r"estimated duration:\s*([\d.]+)", proc.stdout)
    return float(match.group(1)) if match else None


def pick_default_voice() -> str:
    """按偏好顺序挑一个当前系统实际存在的英文发音人。"""
    available = [v[0] for v in list_voices()]
    lowered = {v.lower(): v for v in available}
    for cand in PREFERRED_US + PREFERRED_GB:
        if cand.lower() in lowered:
            return lowered[cand.lower()]
    return DEFAULT_VOICE


def main() -> int:
    ap = argparse.ArgumentParser(
        description="把文本朗读成 m4a 音频（macOS 内置语音合成）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("input", nargs="?", help="朗读文本文件（.txt/.md 等）")
    ap.add_argument("--text", help="直接指定要朗读的字符串（与 input 二选一）")
    ap.add_argument("-o", "--out-dir", help="输出目录")
    ap.add_argument("-n", "--name", help="输出文件名主干（默认取输入文件名）")
    ap.add_argument("-v", "--voice", help="发音人名（默认自动选择）")
    ap.add_argument("-r", "--rate", type=int, default=DEFAULT_RATE, help=f"语速 wpm（默认 {DEFAULT_RATE}）")
    ap.add_argument("--label", help="在音频开头插入的播报句，如 'Version one. Formal register.'")
    ap.add_argument("--section", help="只朗读 Markdown 中该二级标题下的内容，如 'Rewritten Text'")
    ap.add_argument("--no-strip-markdown", action="store_true", help="不剥离 Markdown 标记")
    ap.add_argument("--pronounce", help="发音替换表 JSON 路径；会叠加在默认表之上（同名键以本表为准）")
    ap.add_argument("--no-pronounce", action="store_true", help="禁用全部发音替换")
    ap.add_argument("--no-default-pronounce", action="store_true",
                    help="只用 --pronounce 指定的表，忽略内置默认表")
    ap.add_argument("--keep-aiff", action="store_true", help="保留中间产物 .aiff")
    ap.add_argument("--list-voices", action="store_true", help="列出可用发音人后退出")
    ap.add_argument("--english", action="store_true", help="配合 --list-voices，只列英文发音人")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要朗读的文本，不合成")
    args = ap.parse_args()

    try:
        require_macos()

        if args.list_voices:
            voices = list_voices(args.english)
            print(f"共 {len(voices)} 个发音人" + ("（英文）" if args.english else ""))
            for name, locale, sample in voices:
                print(f"  {name:<18} {locale:<14} {sample[:48]}")
            return 0

        if not (MIN_RATE <= args.rate <= MAX_RATE):
            raise TTSError(f"语速 {args.rate} 超出合理范围 {MIN_RATE}-{MAX_RATE} wpm")

        # 取朗读文本
        if args.text:
            raw = args.text
            stem = args.name or "speech"
        elif args.input:
            src = Path(args.input).expanduser()
            if not src.is_file():
                raise TTSError(f"输入文件不存在：{src}")
            raw = src.read_text(encoding="utf-8")
            stem = args.name or f"{src.stem}-reading"
        else:
            raise TTSError("需要提供 input 文件或 --text")

        # 只取指定章节
        if args.section:
            pattern = re.compile(
                rf"^##\s+{re.escape(args.section)}.*?$(.*?)(?=^##\s|\Z)",
                re.MULTILINE | re.DOTALL,
            )
            match = pattern.search(raw)
            if not match:
                raise TTSError(f"未找到章节：{args.section}")
            raw = match.group(1)

        text = raw if args.no_strip_markdown else strip_markdown(raw)

        # 发音替换：自定义表叠加在默认表之上（同名键以自定义为准）
        applied: list[tuple[str, str]] = []
        if not args.no_pronounce:
            mapping = {} if args.no_default_pronounce else load_pronounce_map(DEFAULT_PRONOUNCE_MAP)
            if args.pronounce:
                custom = load_pronounce_map(Path(args.pronounce).expanduser())
                mapping = {**mapping, **custom}
            text, applied = apply_pronounce(text, mapping)

        if args.label:
            text = f"{args.label.strip()}\n\n{text}"

        if not text.strip():
            raise TTSError("朗读文本为空（可能是章节选择或 Markdown 剥离后无内容）")

        words = len(re.findall(r"[A-Za-z']+", text))
        est = words / max(args.rate, 1) * 60

        if args.dry_run:
            print("--- 朗读稿预览 ---")
            print(text)
            print("--- 预览结束 ---")
            print(f"约 {words} 词，按 {args.rate} wpm 预计 {est:.0f} 秒")
        else:
            voice = args.voice or pick_default_voice()
            if not voice_exists(voice):
                available = ", ".join(v[0] for v in list_voices(True))
                raise TTSError(f"发音人 '{voice}' 不存在。可用英文发音人：{available}")

            out_dir = Path(args.out_dir or ".").expanduser()
            out_dir.mkdir(parents=True, exist_ok=True)
            m4a_path = out_dir / f"{stem}.m4a"

            print(f"发音人：{voice}   语速：{args.rate} wpm   约 {words} 词（预计 {est:.0f} 秒）")
            if applied:
                pairs = ", ".join(f"{a}→{b}" for a, b in applied)
                print(f"发音替换：{pairs}")

            with tempfile.TemporaryDirectory() as tmp:
                aiff_path = Path(tmp) / f"{stem}.aiff"
                synthesize(text, voice, args.rate, aiff_path)
                convert(aiff_path, m4a_path)
                if args.keep_aiff:
                    kept = out_dir / f"{stem}.aiff"
                    shutil.copy2(aiff_path, kept)
                    print(f"保留中间产物：{kept}")

            dur = duration_seconds(m4a_path)
            size_kb = m4a_path.stat().st_size / 1024
            print(f"输出：{m4a_path}")
            print(f"时长：{dur:.1f} 秒" if dur else "时长：未知")
            print(f"大小：{size_kb:.0f} KB")

            if dur and est > 3 and dur < est * 0.5:
                print("警告：实际时长明显短于预估，请试听确认文本没有被截断。")

        return 0

    except TTSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
