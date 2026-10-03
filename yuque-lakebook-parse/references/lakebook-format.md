# lakebook / Lake 格式规范

语雀知识库导出格式的完整说明。解析前先读本文，可避免踩坑。

## 1. 物理结构

`.lakebook` 是一个 **tar 归档**（无压缩或 gzip 压缩）。`tarfile.open(path, "r:*")` 可自动识别。

```
<repo_dir>/                  tar 包内的根子目录，目录名是知识库 ID（纯数字）
├── $meta.json               知识库元信息：书名 + 目录树 + 文档清单
├── abc123def.json           一篇文档，文件名 = TOC 条目里的 url 字段
├── 9f8e7d6c5.json
└── ...
```

**注意**：也有导出包把文件直接放在 tar 根目录（没有 `<repo_dir>` 这层）。定位方式应为「在解压目录里递归找 `$meta.json`，以其所在目录为 repo_dir」，不要假设固定层级。

解压时务必做路径越界校验（拒绝 `../` 与绝对路径）。Python 3.12+ 可直接用 `tarfile.extractall(dest, filter="data")`。

## 2. `$meta.json` —— 两层 JSON 嵌套

外层是普通 JSON 文件，其 `meta` 字段的**值本身又是一段 JSON 字符串**：

```json
{
  "meta": "{\"book\":{\"name\":\"前端开发笔记\",\"path\":\"https://www.yuque.com/zhangsan/frontend\",\"tocYml\":\"- title: 第一章\\n  type: TITLE\\n  url: \\\"\\\"\\n  level: 0\\n\"},\"docs\":[{\"slug\":\"abc123def\",\"type\":\"Doc\",\"format\":\"lake\",\"title\":\"HTML入门\"}]}"
}
```

解析：

```python
raw  = json.loads(Path("$meta.json").read_text(encoding="utf-8"))
meta = raw.get("meta", raw)
if isinstance(meta, str):          # 真实导出通常是字符串，官方文档示例是对象，两种都要兼容
    meta = json.loads(meta)
book = meta.get("book") or {}
docs = meta.get("docs") or []      # 每项含 slug / type / format / title
```

`docs` 条目里的 `body` 通常是空字符串，正文在 `<slug>.json` 里。

**`book.name` 可能不存在**——新版语雀导出会省略它。此时**不要**用 `book.path` 的末段当名字，那是随机 slug（如 `ehyyx7`）。应回退到导出文件名：语雀下载时默认以知识库名命名文件，比 slug 可靠得多。

```python
name = (book.get("name") or "").strip() or lakebook_path.stem.strip()
# 最后才考虑 book.path 末段
```

## 3. `book.tocYml` —— 目录树

YAML 字符串，一个扁平列表。第一条是 `type: META`（知识库自身的元数据），**不是内容，要跳过**。

```yaml
- type: META
  count: 7
  version_id: 38
- type: DOC
  title: parent_doc_1
  uuid: YkPvoCdaSic2BWKp
  url: sv7ht7
  prev_uuid: ''
  sibling_uuid: V0DDKrEhEONljJ0u
  child_uuid: ub8ceD8qSFl6CwpM
  parent_uuid: ''
  doc_id: 9
  level: 0
- type: TITLE
  title: 分组_1
  url: ''
  level: 0
```

字段含义：

| 字段 | 说明 |
|---|---|
| `type` | `META` / `DOC`（文档）/ `TITLE`（分组目录，不对应文件） |
| `url` | 文档 slug，对应 `<url>.json`；TITLE 为空 |
| `level` | 层级，从 0 开始。**还原目录树最可靠的字段** |
| `uuid` / `parent_uuid` / `prev_uuid` / `sibling_uuid` | 目录树关系；`level` 与之一致，但 `level` 更简单可靠 |
| `doc_id` / `id` | 语雀内部 ID，可忽略 |

**层级还原算法**（用栈，不要用 uuid 追链，因为部分导出里 uuid 字段缺失）：

```python
stack = []
for item in toc:
    lvl = item["level"]
    while len(stack) > lvl:
        stack.pop()                    # 回退到当前层级
    if item["type"] == "TITLE":
        stack.append(sanitize(item["title"]))   # 分组成为目录
    else:
        out_dir = root.joinpath(*stack[:lvl])   # 文档落在当前分组下
```

**例外：DOC 本身也可以是父节点。** `type: DOC` 的条目若带非空 `child_uuid`（或紧随其后出现更高 `level` 的条目），说明它**既是一篇文档、又是一个目录**。实测 139 篇的「技术笔记」导出里有 12 个这样的节点（如顶层的 `Kubernetes`、`Java`、`Istio`）。

处理方式：文档自身照常输出为 `<标题>.md`，同时再建一个同名目录承载子节点，并把该目录压栈供后续条目使用：

```python
def has_children(toc, pos, item):
    if item.get("child_uuid"):
        return True
    if pos + 1 >= len(toc):
        return False
    return max(0, toc[pos + 1]["level"]) > max(0, item["level"])

# ...
if has_children(toc, pos, item):
    stack.append(sanitize(item["title"] or slug))
```

**只按 `type == "TITLE"` 判目录会漏掉这一整类节点**，导致其下所有子文档被平铺到上一层。预览目录树时建议对这类节点单独打标记（如 `[+]`），便于核对。

## 4. `<slug>.json` —— 单篇文档

```json
{
  "doc": {
    "type": "Doc",
    "format": "lake",
    "title": "HTML 入门",
    "body": "<h1>HTML 入门</h1><p>...</p>",
    "body_asl": "<h1>HTML 入门</h1><card name=\"math\" value=\"E = mc^2\" />",
    "word_count": 428
  }
}
```

部分导出没有外层 `doc` 包裹，直接把文档对象放在根上——两种都要兼容。

| 字段 | 说明 |
|---|---|
| `type` | `Doc` / `Sheet` / `Board` / `Table` |
| `format` | `lake`（富文本）/ `lakesheet`（表格）/ `lakeboard`（画板） |
| `body` | 正文 HTML；表格文档时是 lakesheet 的 JSON 字符串 |
| `body_html` | 部分导出的正文别名 |
| `body_asl` | Lake(ASL) 源码，**LaTeX 真身在这里** |
| `body_draft` / `body_draft_asl` | 草稿版本，一般忽略 |

### 路由规则

| `format` / `type` | 处理 |
|---|---|
| `lake` / `Doc` | HTML → Markdown |
| `lakesheet` / `Sheet` / `Table` | 解压三层嵌套 → CSV |
| `lakeboard` / `Board` | 无公开规范，导出原始 JSON |

### `body` 可能为空，正文只存在 `body_asl` 里

真实导出中确实会出现 `doc.body == ""` 但 `doc.body_asl` 有内容的情况（实测 11 篇的导出里有 2 篇如此）。此时必须以 ASL 为源渲染，否则会产出空文档。

好消息是 ASL 本身就是 HTML 风格的标记（`<h2><span>…</span></h2>` 之类），可以直接走同一套 HTML → Markdown 流程；差别只在于复杂内容以 `<card>` 形式出现，需要额外渲染（见下节）。

## 5. LaTeX 公式

语雀把公式**渲染成图片**放进正文，图片地址形如：

```
https://cdn.nlark.com/yuque/__latex/<hash>.svg
```

真正的 LaTeX 源码在 `body_asl` 的 math card 里。**`value` 有 3 种写法，必须统一处理**：

| 写法 | 形态 | 出现频率 |
|---|---|---|
| 明文 | `value="E = mc^2"` | 官方文档示例，实测少量 |
| HTML 实体转义后的 JSON | `value="{&quot;code&quot;: ...}"` | 偶尔 |
| `data:` + URL 编码的 JSON | `value="data:%7B%22code%22%3A...%7D"` | **实测主流** |

JSON 写法里真身在 `code` 字段，另有 `src`（指向 `__latex/<hash>.svg`）与 `id`：

```json
{"code": "f(n)=\\begin{cases}0&(n=0)\\\\1&(n=1)\\end{cases}", "src": "https://cdn.nlark.com/yuque/__latex/974788.svg", "id": "sXHvm"}
```

**配对方式**：正文字段里出现的 latex 图片，与 ASL 里出现的 math card **按顺序一一对应**。（实测校验：某篇正文 15 个 `__latex` 图片 ↔ ASL 15 张 math 卡片，全库无错配。）

**两条路径必须共用同一个解码函数 —— 这是实测踩过的坑。** 公式有两条入口：正文非空时走「正文 `__latex` 图片 + ASL 卡片配对」，正文为空时走「ASL 卡片直接渲染」。若两处各自实现解码，必然漂移——实际发生过的是前者只做了 HTML 实体反转义、没解 `data:` 也没取 `code`，于是把整串 `data:%7B...%7D` 原样塞进了 `$...$`，在 3 篇文档里留下 19 处脏公式。正确做法是抽一个 `_math_latex(value)`，两条路径都调它：

```python
def _math_latex(raw):
    obj = _card_json(raw)          # data: 解码 + json.loads，失败返回 None
    return str((obj or {}).get("code") or _decode_card_value(raw)).strip()
```

**行内 / 行间判定**：若该图片是 `<p>` 里的唯一内容，判为行间公式（`$$...$$`），否则为行内（`$...$`）：


```python
block = re.search(r"<p>\s*$", html[:img.start()]) and re.match(r"\s*</p>", html[img.end():])
```

**关键技巧 —— 占位符延后回填**：LaTeX 含 `\` 与换行，直接注入 HTML 会被解析器折叠空白、被 Markdown 转换器转义破坏。正确做法是先把公式替换为纯 ASCII 占位符（如 `@@LKBBLOCK0@@`），Markdown 转换完成后再回填：

```python
html = replace_latex_images(html, formulas, collector)   # -> 占位符
md   = html_to_markdown(html)
md   = collector.apply(md)                               # -> 真 LaTeX
```

若正文本身就是 Lake 源码（`<card name="math" ...>` 直接出现），同样先换占位符。**两条路径都应用同一套行间判定**：`\begin{cases|align|aligned|gather|equation|array|split|matrix|bmatrix|vmatrix}` 或含换行的公式强制用 `$$`；`pmatrix` 等保持行内。注意 `render_math` 会先 `strip()` 再判换行，所以 `" sudo apt update\n"` 这种只是行尾换行的内容不会被误判成行间公式。

## 6. 表格文档（lakesheet）—— 三层嵌套压缩

```
doc.body                   第一层：JSON 字符串
  └── .sheet               第二层：zlib 压缩字节，被 latin-1 编码成字符串
        └── 解压后          第三层：真正的表格数据
              └── .data    {"行号": {"列号": {"v": 值}}}
```

```python
outer = json.loads(doc["body"])                       # {"format":"lakesheet","sheet":"\u0078\u009c..."}
blob  = outer["sheet"].encode("latin-1", "ignore")    # 还原字节流
data  = json.loads(zlib.decompress(blob))             # 可能需依次尝试 zlib / gzip / raw-deflate
rows  = data["data"]                                  # {"0":{"0":{"v":"姓名"},...}, ...}
```

**为什么是 latin-1**：压缩后的字节流被当作字符串存进 JSON，用了 latin-1 这种字节到码点一一对应的编码。用 UTF-8 编解码会破坏数据。

**解压顺序**：`zlib.decompress` → `gzip.decompress` → `zlib.decompress(b, -15)`（裸 deflate）→ 直接当 JSON。

**取行列**：行号 / 列号的 key 是字符串，需转 int 后排序（`"10" < "2"` 的字符串排序是错的）；用最大列号补齐每行长度。

**单元格取值**：`v` 是标量就直接用；`v` 是字典（超链接等）时优先取 `text`，其次 `value` / `url`。

Excel 日期可能以序列号（如 `45292`）存储，基准日为 `1899-12-30`，需显式开启才转换（避免误伤真实数字）。

## 7. Lake 卡片（card）

ASL 里复杂内容都以卡片形式出现，形如 `<card type="inline" name="xxx" value="..." />`。**`value` 常常不是明文，而是 `data:` + URL 编码后的 JSON**：

```
<card type="inline" name="codeblock" value="data:%7B%22mode%22%3A%22python%22%2C%22code%22%3A%22print(1)%22%7D" />
```

解码链：`value` → 去掉 `data:` 前缀 → `urllib.parse.unquote` → `json.loads` → `{"mode": "python", "code": "print(1)"}`。

已确认的卡片类型：

| `name` | 还原为 |
|---|---|
| `math` | `$...$` / `$$...$$`，真身见 §5（3 种写法，实测主流是 `data:`+JSON） |
| `codeblock` | 围栏代码块，语言取解码后 JSON 的 `mode`（或 `language` / `lang`），代码取 `code`（或 `text`） |
| `diagram` | 围栏代码块：`type: mermaid` → ```` ```mermaid ````，`puml` / `plantuml` → ```` ```plantuml ````，代码取 `code` |
| `image` | 输出真 `<img src=... alt=...>`，好让后续图片本地化接手（不要直接输出 `![]()`，否则本地化那一步认不出） |
| `bookmarkInline` / `bookmark` / `link` | `[标题](URL)`，标题取 `detail.title`，退化为 `text` / URL |
| `yuque` | `> 语雀内嵌文档：[标题](URL)` |
| `hr` / `divider` / `separator` | `---` |
| 其他（如 `yuque/lake-sheet`） | 尽力从 JSON 里捞出 URL 还原成链接；捞不到才丢弃标签 |

**未知卡片不要静默丢弃。** 实测里 `bookmarkInline` 这类卡片数量不少，直接 `return ""` 会把用户正文成片吞掉——先尝试捞 URL，实在无内容可还原再说。

**代码块同样必须走占位符**。代码里的 `_`、`*`、`#` 会被 Markdown 转换器转义破坏（例如 `_x_ * 2` 变成 `\_x\_ \* 2`）。所以卡片的还原产物要和公式一起进 `BlockCollector`，转换完再原样回填。

**`hr` 与链接卡片也要走占位符**：裸的 `---` 若紧贴上一行文字，Markdown 会把它当成 setext 标题下划线，把上一行渲染成一个巨大的 `<h2>`。统一进 `BlockCollector` 可规避。

### 代码语言标注在两处，都要看

正文 HTML 里代码块的写法是：

```html
<pre data-language="python" class="ne-codeblock language-python">
  <code class="ne-code">...</code>
</pre>
```

**语言写在 `<pre>` 上**（`data-language` 属性 + `language-xxx` class），内层 `<code>` 只有无语义的 `ne-code`。所以取语言时要先看 `<code>`、再看 `<pre>`，并同时支持 `data-language` 属性和 `language-` / `lang-` 前缀的 class——只看 `<code>` 的 class 会导致所有代码块都丢失语言标注。

## 8. 其他注意事项

- **转换器会静默吞掉某些容器里的图片**。实测 markdownify 的行为（各容器一遍扫下来）：

  | 容器 | 图片是否保留 | 处理 |
  |---|---|---|
  | `<p>` / `<div>` / `<span>` / `<li>` / `<blockquote>` / `<strong>` / `<a>` / `<pre>` | ✅ 保留 | — |
  | `<h1>`–`<h6>` | ❌ **静默丢弃**（`<h2><img/><span>标题</span></h2>` → `## 标题`） | 转换前把标题内的 `<img>` 提到标题之前 |
  | `<td>` / `<th>` | ❌ **静默丢弃**（单元格变成空 `\|  \|`） | 未处理：实测 7 个知识库 385 张图里 0 例。若出现，附件会成孤儿，由 `audit_output.py` 兜住 |

  这类丢失之所以危险，是因为**下载早已完成、附件也已落盘**，只是没人引用——不核对产物根本发现不了。所以「标题内图片上提」是必须的预处理，而不是可选优化。
- **图片是 CDN 链接**，会失效。本地化时改写成 `./_attachments/<文档名>_<序号>.<ext>`，并**跳过 `__latex` 图片**（那是公式，不是图）。
- **替换属性值要用原值、不能反转义**：`src` 里带 `&amp;` 时，用 `html_mod.unescape` 之后的值去 `tag.replace` 永远匹配不上（详见 SKILL.md「图片本地化的两个隐形陷阱」）。
- **文件名清洗**：`/ \ : * ? " < > |` 与控制字符替换为 `_`；同名文档加 `_2`、`_3` 后缀。注意括号 `()` 会保留在文件名里——这在附件名中很常见（`istio 原理(1) - xxx_001.png`），CommonMark 允许配对括号，但写校验正则时要兼容，别用 `[^)]+` 硬切。
- **导出上限 200 篇**：超出需在语雀端拆分知识库后分次导出。
- **权限**：只有知识库开启「下载」权限且当前账号有权访问的内容才会出现在导出包里。
- **规范化文本时跳过代码围栏**：清行尾空白、压缩多余空行这类操作必须识别 ` ``` ` 围栏，否则会把代码里的连续空行压掉。反过来，公式 / 代码块占位符的**回填要放在规范化之后**，不然刚插入的内容会被再处理一遍。
- **实测数据**（同一账号 7 个导出全部跑通，合计 385 篇 / 320+ 张图）：
  - 《股票分析》11 篇：仅 `codeblock` 卡片 14 个；2 篇 `body` 为空；`book.name` 缺失。
  - 《技术笔记》139 篇 / 143 个目录条目：`codeblock` 249、`bookmarkInline` 若干、`image` 8、`diagram` 2、`hr` 1；**61 篇 `body` 为空**（需 ASL 回退）；19 处 LaTeX（3 篇）全部走 `data:`+JSON 形态；12 个「文档即目录」节点；3 层目录。
  - 其余 5 个（人工智能 31 / 知识碎片 41 / 码农水哥 87 / 系统架构 66 / 英语 10）：TITLE 分组最多 3 层（码农水哥的草稿箱/待发布/已发布），「文档即目录」共 11 个（系统架构占 10），另有 286 张图。全库**表格内嵌图 0 例、标题内嵌图仅 1 例**（英语/托业考试）。
- **7 个导出共同点**：`book.name` 全部缺失，所以知识库名必须按 `book.name` → 导出文件名 stem → `book.path` 末段 的顺序兜底，否则会得到 `ehyyx7` 这种随机 slug。
