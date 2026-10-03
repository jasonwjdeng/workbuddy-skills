#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按语雀官方 lakebook 规范合成一个测试样本，用来验证 lakebook_parser.py。

覆盖点：
  - $meta.json 的两层 JSON 嵌套（meta 字段本身是 JSON 字符串）
  - tocYml 的 level 层级（一级分组 / 二级分组 / 三级嵌套文档）
  - 文档类型 Doc / Sheet(lakesheet, zlib+latin-1 三层嵌套) / Board
  - LaTeX 公式（正文里是 __latex 图片，真身在 body_asl 的 math card）
  - HTML 表格、代码块、列表、外链
  - 非法文件名字符、重名文档
  - 目录里存在但 json 缺失的条目
用法：python make_fixture.py [输出目录]
"""

import io
import json
import sys
import tarfile
import urllib.parse
import zlib
from pathlib import Path

REPO = "1234567"  # 语雀 tar 包内的知识库目录名

TOC_YML = """- type: META
  count: 9
  display_level: 1
  version_id: 38
- type: TITLE
  title: 第一章 入门
  uuid: t1
  url: ''
  level: 0
- type: DOC
  title: HTML 入门
  uuid: u1
  url: aaa111
  level: 1
- type: DOC
  title: 公式与表格
  uuid: u2
  url: ddd444
  level: 1
- type: TITLE
  title: 第二章 进阶
  uuid: t2
  url: ''
  level: 0
- type: TITLE
  title: 子分组/含:非法*字符
  uuid: t3
  url: ''
  level: 1
- type: DOC
  title: 嵌套很深的文档
  uuid: u5
  url: eee555
  level: 2
- type: DOC
  title: 数据表
  uuid: u3
  url: bbb222
  level: 1
- type: DOC
  title: 画板示例
  uuid: u4
  url: ccc333
  level: 1
- type: DOC
  title: 空正文文档
  uuid: u7
  url: fff666
  level: 1
- type: DOC
  title: 找不到正文的文档
  uuid: u6
  url: missing9
  level: 1
- type: DOC
  title: 父文档含子文档
  uuid: p1
  url: ggg777
  child_uuid: c1
  level: 0
- type: DOC
  title: 子文档一
  uuid: c1
  url: hhh888
  child_uuid: ''
  level: 1
- type: DOC
  title: 孙文档
  uuid: c2
  url: iii999
  child_uuid: ''
  level: 2
"""

DOC_HTML = """<h1>HTML 入门</h1>
<p>HTML 是 <strong>HyperText Markup Language</strong> 的缩写，用来描述网页的<em>结构</em>。</p>
<p>行内公式示例：质能方程 <img src="https://cdn.nlark.com/yuque/__latex/aaaa11.svg"/> 非常著名。</p>
<p><img src="https://cdn.nlark.com/yuque/__latex/bbbb22.svg"/></p>
<ul><li>标签（Tag）</li><li>属性（Attribute）</li></ul>
<ol><li>打开编辑器</li><li>写第一行代码</li></ol>
<blockquote><p>结构、表现、行为要分离。</p></blockquote>
<pre data-language="html" class="ne-codeblock language-html"><code class="ne-code">&lt;div class="box"&gt;hello&lt;/div&gt;</code></pre>
<table>
<tr><th>标签</th><th>含义</th></tr>
<tr><td>p</td><td>段落</td></tr>
<tr><td>a</td><td>链接 | 竖线测试</td></tr>
</table>
<p>参考 <a href="https://www.yuque.com/">语雀官网</a> 与 <a href="https://developer.mozilla.org/">MDN</a>。</p>
<p>普通图片：<img src="https://cdn.nlark.com/yuque/0/2022/png/1234-abc.png" alt="示意图"/></p>
<h2><img src="https://cdn.nlark.com/yuque/0/2022/png/9-cover.png"/><span>带图的标题</span></h2>
<p>标题里那张封面图不能被丢掉。</p>
"""

DOC_ASL = (
    '<h1>HTML 入门</h1>'
    '<p>行内公式示例：质能方程 <card name="math" value="E = mc^2" /> 非常著名。</p>'
    '<p><card name="math" value="\\int_0^1 x^2 dx = \\frac{1}{3}" /></p>'
)

DOC_HTML_2 = """<h1>公式与表格</h1>
<p>下面是一个分段函数：</p>
<p><img src="https://cdn.nlark.com/yuque/__latex/cccc33.svg"/></p>
<p>矩阵写法 <img src="https://cdn.nlark.com/yuque/__latex/dddd44.svg"/> 也是支持的。</p>
<table>
<tr><th>项目</th><th>值</th><th>备注</th></tr>
<tr><td>代码块数</td><td>12</td><td>含 PlantUML</td></tr>
<tr><td>公式数</td><td>7</td><td>MathJax</td></tr>
</table>
"""

def make_math_card_json(latex: str) -> str:
    """实测写法：math 卡片的 value = data:<urlencode 后的 JSON>，
    LaTeX 真身在 code 字段，src 指向 __latex 图片，另有 id。
    正文非空时，公式只以「正文里 __latex 图片 + ASL 里这张卡片」的形式出现，
    因此这条路径必须单独覆盖。"""
    payload = {"code": latex, "src": "https://cdn.nlark.com/yuque/__latex/syn0.svg", "id": "m0"}
    return (f'<card type="inline" name="math" '
            f'value="data:{urllib.parse.quote(json.dumps(payload, ensure_ascii=False))}" />')


DOC_ASL_2 = (
    '<h1>公式与表格</h1>'
    + make_math_card_json("f(x) = \\begin{cases} x^2 & x \\ge 0 \\\\ -x & x < 0 \\end{cases}")
    + make_math_card_json("A = \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}")
)


def make_sheet_body():
    """lakesheet：body(JSON 字符串) -> sheet(latin-1 压缩字节) -> 表格 JSON。"""
    grid = {
        "data": {
            "0": {"0": {"v": "姓名"}, "1": {"v": "入职日期"}, "2": {"v": "部门"}},
            "1": {"0": {"v": "张三"}, "1": {"v": 45292}, "2": {"v": "技术部"}},
            "2": {"0": {"v": "李四"}, "1": {"v": 3942259200}, "2": {"v": "产品部"}},
            "3": {"0": {"v": "王五"}, "1": {"v": 46000}, "2": {"v": {"text": "官网", "url": "https://x.com"}}},
        }
    }
    payload = json.dumps(grid).encode("utf-8")
    blob = zlib.compress(payload)
    return json.dumps({"format": "lakesheet", "sheet": blob.decode("latin-1")})


def make_codeblock_card(lang: str, code: str) -> str:
    """真实导出里 codeblock 卡片的形式：value 是 data:<urlencode 后的 JSON>。"""
    payload = json.dumps({"search": "", "mode": lang, "code": code}, ensure_ascii=False)
    return f'<card type="inline" name="codeblock" value="data:{urllib.parse.quote(payload)}" />'


def make_card(name: str, payload: dict) -> str:
    """通用卡片：value = data:<urlencode 后的 JSON>。"""
    return (f'<card type="inline" name="{name}" '
            f'value="data:{urllib.parse.quote(json.dumps(payload, ensure_ascii=False))}" />')


# doc.body 为空、正文只存在于 body_asl 的场景（实测 139 篇的知识库里有 68 篇如此），
# 且复杂内容全以卡片形式出现 —— 各种卡片都要能还原。
ASL_ONLY = (
    "<h2><span>只存在于 ASL 的正文</span></h2>"
    "<p><span>这篇文档的 doc.body 是空的，需要回退到 body_asl 才能拿到内容。</span></p>"
    + make_codeblock_card("python", 'rank = _x_ * 2  # 下划线与星号\nprint(f"{rank:.2f}")')
    # 明文写法（官方文档风格），需向后兼容
    + '<p>明文公式 <card type="inline" name="math" value="E = mc^2" /> 结束</p>'
    # 实测写法：JSON {"code": <LaTeX>, "src": <latex 图片>}
    + '<p>JSON 公式 <card type="inline" name="math" value="data:'
    + urllib.parse.quote(json.dumps({"code": "O(\\log n)", "src": "https://cdn.nlark.com/yuque/__latex/x.svg", "id": "m1"}))
    + '" /> 结束</p>'
    + make_card("diagram", {"type": "mermaid", "code": "graph TD\nA-->B", "id": "d1"})
    + make_card("bookmarkInline", {"mode": "title", "src": "https://leetcode.cn/problems/binary-search/",
                                   "text": "https://leetcode.cn/problems/binary-search/",
                                   "detail": {"title": "704. 二分查找 - 力扣"}})
    + make_card("image", {"src": "https://cdn.nlark.com/yuque/0/2022/png/9-abc.png",
                          "name": "示意图", "status": "done"})
    + make_card("hr", {"id": "h1"})
    + "<p><span>结束。</span></p>"
)

DOCS = {
    "aaa111": {"doc": {"type": "Doc", "format": "lake", "title": "HTML 入门",
                       "body": DOC_HTML, "body_asl": DOC_ASL, "word_count": 428}},
    "ddd444": {"doc": {"type": "Doc", "format": "lake", "title": "公式与表格",
                       "body": DOC_HTML_2, "body_asl": DOC_ASL_2, "word_count": 96}},
    "bbb222": {"doc": {"type": "Sheet", "format": "lakesheet", "title": "数据表",
                       "body": make_sheet_body(), "body_asl": ""}},
    "ccc333": {"doc": {"type": "Board", "format": "lakeboard", "title": "画板示例",
                       "body": "", "body_asl": ""}},
    "eee555": {"doc": {"type": "Doc", "format": "lake", "title": "嵌套很深的文档",
                       "body": "<p>我在第三层目录里。</p>", "body_asl": "", "word_count": 9}},
    "fff666": {"doc": {"type": "Doc", "format": "lake", "title": "空正文文档",
                       "body": "", "body_asl": ASL_ONLY, "word_count": 21}},
    # 「文档即目录」：父文档既有正文，又是下级文档的容器
    "ggg777": {"doc": {"type": "Doc", "format": "lake", "title": "父文档含子文档",
                       "body": "<p>我是父文档，同时也是一个目录。</p>", "body_asl": "", "word_count": 14}},
    "hhh888": {"doc": {"type": "Doc", "format": "lake", "title": "子文档一",
                       "body": "<p>我是子文档，下面还有一篇。</p>", "body_asl": "", "word_count": 12}},
    "iii999": {"doc": {"type": "Doc", "format": "lake", "title": "孙文档",
                       "body": "<p>我在第三层，父节点是 DOC 不是 TITLE。</p>", "body_asl": "", "word_count": 18}},
}

META_DOCS = [
    {"slug": "aaa111", "type": "Doc", "format": "lake", "title": "HTML 入门", "body": "", "body_asl": ""},
    {"slug": "ddd444", "type": "Doc", "format": "lake", "title": "公式与表格", "body": "", "body_asl": ""},
    {"slug": "eee555", "type": "Doc", "format": "lake", "title": "嵌套很深的文档", "body": "", "body_asl": ""},
    {"slug": "bbb222", "type": "Sheet", "format": "lakesheet", "title": "数据表", "body": "", "body_asl": ""},
    {"slug": "ccc333", "type": "Board", "format": "lakeboard", "title": "画板示例", "body": "", "body_asl": ""},
    {"slug": "fff666", "type": "Doc", "format": "lake", "title": "空正文文档", "body": "", "body_asl": ""},
    {"slug": "ggg777", "type": "Doc", "format": "lake", "title": "父文档含子文档", "body": "", "body_asl": ""},
    {"slug": "hhh888", "type": "Doc", "format": "lake", "title": "子文档一", "body": "", "body_asl": ""},
    {"slug": "iii999", "type": "Doc", "format": "lake", "title": "孙文档", "body": "", "body_asl": ""},
]


def build(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    lakebook = out_dir / "测试知识库.lakebook"

    inner = {
        "book": {
            "name": "测试知识库",
            "path": "https://www.yuque.com/zhangsan/testbook",
            "type": "Book",
            "public": 0,
            "tocYml": TOC_YML,
        },
        "docs": META_DOCS,
    }
    meta_file = {"meta": json.dumps(inner, ensure_ascii=False)}

    with tarfile.open(lakebook, "w:gz") as tf:
        def add(name: str, text: str):
            data = text.encode("utf-8")
            info = tarfile.TarInfo(f"{REPO}/{name}")
            info.size = len(data)
            info.mtime = 1659689108
            tf.addfile(info, io.BytesIO(data))

        add("$meta.json", json.dumps(meta_file, ensure_ascii=False))
        for slug, payload in DOCS.items():
            add(f"{slug}.json", json.dumps(payload, ensure_ascii=False))

    return lakebook


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "./_selftest/fixture")
    p = build(target)
    print(f"已生成：{p}  ({p.stat().st_size} bytes)")
