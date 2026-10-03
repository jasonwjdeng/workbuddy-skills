#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lakebook_parser.py 的端到端自检：合成样本 -> 跑解析 -> 断言产物。

设计上刻意做成「一份文件、两种布局都能跑」，避免同一个脚本维护两份而漂移
（历史上就因为工作区版与技能版布局假设不同，互相覆盖过两次）：

  - 技能布局：scripts/{verify,make_fixture,lakebook_parser,audit_output}.py
  - 工作区布局：lakebook_parser.py 在上一层，其余在 _selftest/

两条硬性约束：
  1. 所有产物一律写进临时目录，绝不污染所在目录（可无限次重复执行）
  2. fixture 每次重新合成，绝不缓存 —— 否则改了 make_fixture.py 却测的是旧样本

用法：python verify.py
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _locate(name: str) -> Path:
    """按「同目录 → 上一层」找依赖脚本，从而同时兼容技能与工作区两种布局。"""
    for base in (HERE, HERE.parent):
        p = base / name
        if p.exists():
            return p
    raise FileNotFoundError(f"找不到 {name}（已查找 {HERE} 与 {HERE.parent}）")


PARSER = _locate("lakebook_parser.py")
MAKE_FIXTURE = _locate("make_fixture.py")
AUDIT = _locate("audit_output.py")
PY = sys.executable

FAILS = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + (f"  <- {extra}" if extra and not cond else ""))
    if not cond:
        FAILS.append(label)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(fixture, out_dir, extra_env=None):
    env = dict(os.environ)
    env.update(extra_env or {})
    cmd = [PY, str(PARSER), str(fixture), "-o", str(out_dir), "--nopic", "--keep-json"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode not in (0, 2):  # 2 = 存在 error 条目，属预期
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
    return r


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def verify(mode, out_dir):
    print(f"\n=== 模式：{mode} ===")
    book = out_dir / "测试知识库"
    ch1 = book / "第一章 入门"
    ch2 = book / "第二章 进阶"
    c1 = read(ch1 / "HTML 入门.md")
    c2 = read(ch1 / "公式与表格.md")
    c3 = read(ch2 / "子分组_含_非法_字符" / "嵌套很深的文档.md")
    c4 = read(ch2 / "空正文文档.md")
    csv_text = read(ch2 / "数据表.csv")

    check("目录树按 level 还原", (ch1 / "HTML 入门.md").exists()
          and (ch2 / "子分组_含_非法_字符" / "嵌套很深的文档.md").exists())
    check("非法文件名字符已替换", (ch2 / "子分组_含_非法_字符").is_dir())
    check("标题转 Markdown", "# HTML 入门" in c1)
    check("粗体/斜体", "**HyperText Markup Language**" in c1 and "*结构*" in c1)
    check("行内公式还原为 $...$", "$E = mc^2$" in c1, c1[:200])
    check("块级公式还原为 $$...$$", "$$" in c1 and "\\int_0^1 x^2 dx = \\frac{1}{3}" in c1)
    check("cases 公式按块输出", "\\begin{cases}" in c2)
    check("pmatrix 保持行内", "$A = \\begin{pmatrix}" in c2, c2)
    check("公式卡片 data:JSON 已解码（无原文污染）",
          "data:" not in c2 and "%7B" not in c2 and "__latex" not in c2, c2[:300])
    check("HTML 表格转 Markdown 表格", "| 标签 | 含义 |" in c1 and "| p | 段落 |" in c1)
    check("代码块语言回填", "```html" in c1, c1)
    check("链接保留", "[语雀官网](https://www.yuque.com/)" in c1)
    check("顺序列表", "1. 打开编辑器" in c1)
    check("引用块", "> 结构、表现、行为要分离。" in c1)
    check("图片保留外链(--nopic)", "https://cdn.nlark.com/yuque/0/2022/png/1234-abc.png" in c1)
    check("标题内的图片被提到标题外（markdownify 会静默丢弃）",
          "https://cdn.nlark.com/yuque/0/2022/png/9-cover.png" in c1 and "带图的标题" in c1, c1[-300:])
    check("嵌套层级文档内容", "第三层目录" in c3)

    check("body 为空时回退到 body_asl", "只存在于 ASL 的正文" in c4, c4[:200])
    check("codeblock 卡片还原为代码块", "```python" in c4, c4)
    check("代码块内下划线/星号未被转义", "rank = _x_ * 2" in c4 and "\\_" not in c4, c4)
    check("math 卡片：明文写法", "$E = mc^2$" in c4, c4)
    check("math 卡片：JSON 写法取 code 字段", "$O(\\log n)$" in c4, c4)
    check("diagram 卡片还原为 mermaid", "```mermaid" in c4 and "graph TD" in c4, c4)
    check("bookmarkInline 还原为链接",
          "[704. 二分查找 - 力扣](https://leetcode.cn/problems/binary-search/)" in c4, c4)
    check("image 卡片保留图片地址",
          "https://cdn.nlark.com/yuque/0/2022/png/9-abc.png" in c4, c4)
    check("hr 卡片还原为分隔线", "\n---\n" in c4, c4)

    check("DOC 作为父节点：自身输出为 .md", (book / "父文档含子文档.md").exists())
    check("DOC 作为父节点：同时建同名目录",
          (book / "父文档含子文档" / "子文档一.md").exists())
    check("DOC 嵌套可连续两层",
          (book / "父文档含子文档" / "子文档一" / "孙文档.md").exists())

    rows = [r for r in csv_text.splitlines() if r]
    check("表格解压为 CSV（4 行）", len(rows) == 4, str(rows))
    check("CSV 表头", rows[0] == "姓名,入职日期,部门", rows[0] if rows else "")
    check("CSV 单元格字典取值", "官网" in rows[3] and "https://x.com" not in rows[3], rows[3] if rows else "")

    board = json.loads(read(ch2 / "画板示例.json"))
    check("画板导出原始 JSON", isinstance(board, dict) and board.get("format") == "lakeboard")

    manifest = json.loads(read(book / "_manifest.json"))
    by_title = {d["title"]: d for d in manifest["docs"]}
    check("manifest 记录所有条目", len(manifest["docs"]) == 10, str(len(manifest["docs"])))
    check("缺失正文条目被标为 error",
          by_title.get("找不到正文的文档", {}).get("status") == "error")
    check("manifest 标注 ASL 回退来源",
          "body_asl" in by_title.get("空正文文档", {}).get("note", ""),
          by_title.get("空正文文档", {}).get("note", ""))
    check("文档类型路由正确",
          by_title["数据表"]["type"] == "sheet" and by_title["画板示例"]["type"] == "board")

    raw_dir = out_dir / "_raw" / "测试知识库"
    check("--keep-json 保留原始 JSON", (raw_dir / "aaa111.json").exists())
    check("_last_run.json 生成", (out_dir / "_last_run.json").exists())


def verify_downloader():
    """图片下载器单测：URL 片段剥离 + 退避重试 + 实体替换。不联网（打桩 urlopen）。"""
    print("\n=== 单测：图片下载器 ===")
    mod = _load("lk_parser_under_test", PARSER)

    class FakeResp:
        headers = {"Content-Type": "image/png"}

        def read(self):
            return b"PNG"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    state = {"seen": [], "n": 0}

    def fake_urlopen(req, timeout=None):
        state["seen"].append(req.full_url)
        state["n"] += 1
        if state["n"] < 3:
            raise OSError("boom")
        return FakeResp()

    orig_open = urllib.request.urlopen
    orig_sleep = mod.time.sleep
    urllib.request.urlopen = fake_urlopen
    mod.time.sleep = lambda _s: None
    try:
        dl = mod.ImageDownloader(attempts=3)
        got = dl.fetch("https://cdn.nlark.com/a.png#averageHue=%23fff&clientId=u123")
    finally:
        urllib.request.urlopen = orig_open
        mod.time.sleep = orig_sleep

    check("下载器：前两次失败后重试成功", bool(got) and got[0] == b"PNG", repr(got))
    check("下载器：URL 片段已剥离", bool(state["seen"]) and all("#" not in u for u in state["seen"]),
          str(state["seen"][:1]))
    check("下载器：按 attempts 精确重试 3 次", len(state["seen"]) == 3, str(len(state["seen"])))

    # 持续失败时应放弃并返回 None，且不无限重试
    state["seen"].clear()
    state["n"] = -10**9
    urllib.request.urlopen = fake_urlopen
    mod.time.sleep = lambda _s: None
    try:
        dl2 = mod.ImageDownloader(attempts=3)
        got2 = dl2.fetch("https://cdn.nlark.com/b.png")
    finally:
        urllib.request.urlopen = orig_open
        mod.time.sleep = orig_sleep
    check("下载器：彻底失败返回 None 且重试有限", got2 is None and len(state["seen"]) == 3,
          f"{got2!r} / {len(state['seen'])}")

    # localize 改写：语雀带查询参数的图片 src 里是 `&amp;`，
    # 若拿反转义后的值去 tag.replace 就匹配不上，图片会变成「下载了但没被引用」的孤儿附件。
    state["seen"].clear()
    state["n"] = 10**9                      # 恒成功
    urllib.request.urlopen = fake_urlopen
    mod.time.sleep = lambda _s: None
    try:
        with tempfile.TemporaryDirectory() as td:
            dl3 = mod.ImageDownloader(attempts=1)
            html = '<p><img src="https://cdn.nlark.com/yuque/a.png?a=1&amp;b=2" alt="x"/></p>'
            out = dl3.localize(html, Path(td), "t", mod.NameAllocator())
            n_files = len([f for f in Path(td).rglob("*") if f.is_file()])
    finally:
        urllib.request.urlopen = orig_open
        mod.time.sleep = orig_sleep
    check("本地化：含 &amp; 的 src 也被改写（不留孤儿附件）",
          "cdn.nlark" not in out and "_attachments/" in out and dl3.ok == 1 and n_files == 1,
          f"{out} / ok={dl3.ok} / 落盘={n_files}")

    # 源里残留的裸文件名（不是 URL）应单独记账，混进「下载失败」会把排查带偏
    urllib.request.urlopen = fake_urlopen            # 恒成功；被调用即说明判定错了
    try:
        with tempfile.TemporaryDirectory() as td:
            dl4 = mod.ImageDownloader(attempts=1)
            html = '<p><img src="Untitled 3.png"/><img src="https://cdn.nlark.com/yuque/b.png"/></p>'
            dl4.localize(html, Path(td), "t", mod.NameAllocator())
    finally:
        urllib.request.urlopen = orig_open
    check("本地化：裸文件名单独记账，不算下载失败",
          dl4.only_local == 1 and dl4.fail == 0 and dl4.ok == 1,
          f"only_local={dl4.only_local} fail={dl4.fail} ok={dl4.ok}")


def verify_audit():
    """产物体检脚本单测：构造已知问题，确认能被逐项识别并正确渲染。"""
    print("\n=== 单测：产物体检脚本 ===")
    mod = _load("lk_audit", AUDIT)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "知识库"
        att = root / "分组" / "_attachments"
        att.mkdir(parents=True)
        (att / "ok.png").write_bytes(b"x")
        (att / "orphan.png").write_bytes(b"x")              # 没人引用 → 孤儿
        (root / "分组" / "甲.md").write_text(
            '# 甲\n\n![](./_attachments/ok.png)\n\n![](./_attachments/missing.png)\n\n'
            '裸文件名：![](0.png)\n\n外链：![](https://example.com/x.png)\n\n'
            '<card name="math" />\n', encoding="utf-8")
        (root / "空.md").write_text("", encoding="utf-8")
        (root / "_manifest.json").write_text(
            json.dumps({"docs": [{"status": "doc"}, {"status": "error"}]}), encoding="utf-8")
        r = mod.audit(root)

    check("体检：识别孤儿附件", r["orphans"] == ["分组/_attachments/orphan.png"], str(r["orphans"]))
    check("体检：识别死链", len(r["dead"]) == 1 and "missing.png" in r["dead"][0], str(r["dead"]))
    check("体检：裸文件名引用归入 nonurl 而非死链",
          len(r["nonurl"]) == 1 and "0.png" in r["nonurl"][0], str(r["nonurl"]))
    check("体检：未本地化的外链单独列出", len(r["external"]) == 1, str(r["external"]))
    check("体检：识别残留 <card>", r["residue"]["未还原的 <card> 标签"] == 1, str(r["residue"]))
    check("体检：识别空文档", r["empties"] == ["空.md"], str(r["empties"]))
    check("体检：汇总 manifest 状态",
          r["manifests"][0]["statuses"].get("error") == 1, str(r["manifests"]))

    # 干净产物不应报问题
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "干净库"
        att = root / "_attachments"
        att.mkdir(parents=True)
        (att / "a.png").write_bytes(b"x")
        (root / "文档.md").write_text("# 标题\n\n![](./_attachments/a.png)\n", encoding="utf-8")
        clean = mod.audit(root)
    check("体检：干净产物无问题",
          not clean["orphans"] and not clean["dead"] and not clean["external"]
          and not any(clean["residue"].values()), str(clean["residue"]))

    # report() 的冒烟测试：曾因 r["residue"] 未赋值导致 NameError，
    # 而只有 audit() 被测到，问题溜了过去。这里确保渲染分支也被执行。
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc_clean = mod.report(clean)
        rc_dirty = mod.report(r)
    printed = buf.getvalue()
    check("体检：report() 可渲染且返回值语义正确",
          isinstance(rc_clean, bool) and rc_clean is False and rc_dirty is True,
          f"clean={rc_clean!r} dirty={rc_dirty!r}")
    check("体检：report() 输出含关键小节",
          "孤儿附件" in printed and "未本地化的外链图片" in printed, printed[-200:])

    # main() 必须遍历全部传入的库：曾写成 any(generator)，会在第一个有问题的库处短路，
    # 后面的库连报告都不打印，看起来像「只有这一个库有问题」。
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        dirty = tdp / "脏库"
        (dirty / "_attachments").mkdir(parents=True)
        (dirty / "_attachments" / "orphan.png").write_bytes(b"x")
        (dirty / "a.md").write_text("没有引用任何图\n", encoding="utf-8")
        ok_dir = tdp / "干净库"
        (ok_dir / "_attachments").mkdir(parents=True)
        (ok_dir / "_attachments" / "b.png").write_bytes(b"x")
        (ok_dir / "b.md").write_text("![](./_attachments/b.png)\n", encoding="utf-8")
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            rc2 = mod.main([str(dirty), str(ok_dir)])
        out2 = buf2.getvalue()
    check("体检：main() 遍历全部传入的库（不在首个问题库处短路）",
          out2.count("Markdown 文档") == 2 and rc2 == 1,
          f"报告块数={out2.count('Markdown 文档')} rc={rc2}")


def main():
    verify_downloader()
    verify_audit()

    with tempfile.TemporaryDirectory(prefix="lakebook-selftest-") as tmp:
        tmp = Path(tmp)
        fixture = tmp / "fixture"
        subprocess.run([PY, str(MAKE_FIXTURE), str(fixture)], check=True)

        lakebook = fixture / "测试知识库.lakebook"
        r = run(lakebook, tmp / "out_default")
        verify("默认（markdownify + pyyaml）", tmp / "out_default")
        check("退出码：存在 error 条目时为 2", r.returncode == 2, str(r.returncode))

        run(lakebook, tmp / "out_fallback",
            extra_env={"LAKEBOOK_NO_MARKDOWNIFY": "1", "LAKEBOOK_NO_YAML": "1"})
        verify("纯标准库兜底（无 markdownify / pyyaml）", tmp / "out_fallback")

    print("\n" + ("全部通过 ✅" if not FAILS else f"失败 {len(FAILS)} 项：{FAILS} ❌"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
