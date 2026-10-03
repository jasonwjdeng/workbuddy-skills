#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对 lakebook_parser.py 的产物做完整性体检（只读，不联网，不改任何文件）。

用法：
    python audit_output.py <输出根目录> [更多输出根目录 ...]

为什么要单独体检：计数器说「成功」不等于产物正确。实测踩过的坑是
图片下载了、文件也落盘了、`ok += 1`，但 Markdown 里的链接因为 HTML 实体
没被替换掉，于是留下成堆孤儿附件。只有拿「落盘数 vs 被引用数」交叉核对
才能发现。所以转换完建议都跑一遍这个脚本。

检查项：
  1. 每篇 Markdown 是否为空
  2. 附件落盘数 vs Markdown 引用数 → 孤儿附件 / 死链
  3. 非 URL 的图片引用（源里就是 `0.png` 这类裸文件名，无法下载，属正常但需知晓）
  4. 残留的未还原痕迹：`<card>` 标签、`__latex` 图片、`data:` 原文、CDN 外链
  5. `_manifest.json` 的状态分布

退出码：0 = 无问题；1 = 有需要处理的问题（孤儿 / 死链 / 残留）。
"""

import json
import re
import sys
from pathlib import Path

CARD_RE = re.compile(r"<card\b", re.I)
# 只匹配**图片**引用（`!` 前缀），不要误抓 `[文字](#锚点)` 这类普通链接。
# 附件文件名可能带括号（如 `istio 原理(1) - xxx_001.png`），所以目标里允许一层配对括号
# ——这也是 CommonMark 允许的合法写法，用 [^)]+ 会在一半处截断。
REF_RE = re.compile(r"!\[[^\]]*\]\(((?:[^()\n]|\([^()\n]*\))+)\)")
TITLE_TAIL_RE = re.compile(r'\s+"[^"]*"$')
RESIDUE = {
    "未还原的 <card> 标签": lambda t: len(CARD_RE.findall(t)),
    "__latex 公式图片": lambda t: t.count("__latex"),
    "data: 编码原文": lambda t: t.count("data:%7B"),
}


def audit(root: Path) -> dict:
    # 统一解析为绝对路径：附件侧用了 resolve()（会归一化 macOS 大小写不敏感的路径），
    # 这里若不归一化，relative_to() 会因为 WorkBuddy/Workbuddy 这类差异直接抛异常。
    root = root.resolve()
    mds = sorted(p for p in root.rglob("*.md"))
    attachments = [p for p in root.rglob("_attachments/*") if p.is_file()]
    on_disk = {p.resolve() for p in attachments}

    texts = {}
    for p in mds:
        try:
            texts[p] = p.read_text(encoding="utf-8")
        except OSError:
            texts[p] = ""

    referenced, dead, nonurl = set(), [], []
    external = []
    for md, text in texts.items():
        for m in REF_RE.finditer(text):
            target = TITLE_TAIL_RE.sub("", m.group(1)).strip()
            if not target or target.startswith("data:"):
                continue
            if target.startswith(("http://", "https://")):
                # 仍是外链 = 这一张没本地化成功（下载失败，或转换时用了 --nopic）。
                # 只认 cdn.nlark.com 会漏掉第三方图源（实测有 GitHub raw 的截图）。
                external.append(f"{md.relative_to(root)} -> {target[:100]}")
                continue
            cand = (md.parent / target).resolve()
            referenced.add(cand)
            if cand in on_disk:
                continue
            if target.startswith(("_attachments/", "./_attachments/")):
                dead.append(f"{md.relative_to(root)} -> {target}")
            else:
                # 源文档里本就是裸文件名，不是 URL，无从下载
                nonurl.append(f"{md.relative_to(root)} -> {target}")

    orphans = sorted(p.relative_to(root).as_posix() for p in on_disk - referenced)
    empties = sorted(p.relative_to(root).as_posix() for p, t in texts.items() if not t.strip())

    joined = "\n".join(texts.values())
    residue = {k: f(joined) for k, f in RESIDUE.items()}

    manifests = []
    for mp in sorted(root.rglob("_manifest.json")):
        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        statuses = {}
        for d in data.get("docs", []):
            statuses[d.get("status", "?")] = statuses.get(d.get("status", "?"), 0) + 1
        manifests.append({"path": mp.relative_to(root).as_posix(), "docs": len(data.get("docs", [])),
                          "statuses": statuses})

    return {
        "root": root, "n_docs": len(mds), "n_attachments": len(attachments),
        "orphans": orphans, "dead": dead, "nonurl": nonurl, "empties": empties,
        "external": external, "residue": residue, "manifests": manifests,
    }


def report(r: dict) -> bool:
    """打印报告；返回 True 表示发现问题。"""
    print(f"\n{'=' * 66}\n{r['root']}")
    print(f"{'=' * 66}")
    print(f"Markdown 文档 : {r['n_docs']}")
    print(f"附件落盘      : {r['n_attachments']}")
    if r["manifests"]:
        for m in r["manifests"]:
            st = ", ".join(f"{k}={v}" for k, v in m["statuses"].items())
            print(f"manifest      : {m['path']}（{m['docs']} 条：{st}）")

    problems = False

    res = {k: v for k, v in r["residue"].items() if v}
    if res:
        problems = True
        print("\n[问题] 残留未还原内容：")
        for k, v in res.items():
            print(f"    {k}: {v} 处")
    else:
        print("\n[OK] 无残留：<card> / __latex / data: 均为 0")

    if r["external"]:
        problems = True
        print(f"\n[问题] 未本地化的外链图片 {len(r['external'])} 处（下载失败，或本次用了 --nopic）：")
        for p in r["external"][:10]:
            print("    " + p)
        if len(r["external"]) > 10:
            print(f"    … 另有 {len(r['external']) - 10} 处")
    else:
        print("[OK] 无未本地化的外链图片")

    if r["orphans"]:
        problems = True
        print(f"\n[问题] 孤儿附件 {len(r['orphans'])} 个（下载了但没有任何 Markdown 引用）：")
        for p in r["orphans"][:10]:
            print("    " + p)
        if len(r["orphans"]) > 10:
            print(f"    … 另有 {len(r['orphans']) - 10} 个")
    else:
        print("[OK] 无孤儿附件：每个落盘的图片都被引用了")

    if r["dead"]:
        problems = True
        print(f"\n[问题] 死链 {len(r['dead'])} 处（引用了 _attachments 但文件不存在）：")
        for p in r["dead"][:10]:
            print("    " + p)
    else:
        print("[OK] 无死链")

    if r["nonurl"]:
        print(f"\n[提示] {len(r['nonurl'])} 处图片来源本就是裸文件名（非 URL，无法下载，属正常）：")
        for p in r["nonurl"][:5]:
            print("    " + p)
        if len(r["nonurl"]) > 5:
            print(f"    … 另有 {len(r['nonurl']) - 5} 处")

    if r["empties"]:
        print(f"\n[提示] 空文档 {len(r['empties'])} 篇（源头正文与 ASL 都为空）：")
        for p in r["empties"][:5]:
            print("    " + p)

    return problems


def main(argv=None) -> int:
    args = (argv if argv is not None else sys.argv[1:]) or []
    if not args:
        print(__doc__)
        return 2
    roots = []
    for a in args:
        p = Path(a).expanduser()
        if p.is_dir():
            # 允许传入「输出根目录」，其下每个知识库子目录都体检一遍
            subs = [d for d in sorted(p.iterdir()) if d.is_dir() and d.name != "_attachments"]
            roots.extend(subs or [p])
        else:
            print(f"[warn] 不是目录，跳过：{a}", file=sys.stderr)

    # 必须先把所有库都体检完再聚合：写成 any(generator) 会在第一个有问题的库处短路，
    # 后面的库连报告都不打印，看起来像「只有这一个库有问题」。
    results = [report(audit(r)) for r in roots]
    bad = any(results)
    print("\n" + ("发现问题，请按上面 [问题] 处理 ❌" if bad else "体检通过，产物干净 ✅"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
