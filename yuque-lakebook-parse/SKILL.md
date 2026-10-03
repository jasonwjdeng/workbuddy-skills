---
name: yuque-lakebook-parse
description: 解析语雀（Yuque）导出的 .lakebook 文件，还原为 Markdown / CSV 并保留知识库目录层级，用于迁移、归档与二次加工。当用户提供 .lakebook 文件或语雀导出包，或提出解析、迁移、备份语雀知识库，以及询问能否解析 lakebook / Lake 格式时使用。触发词：lakebook、语雀导出、语雀迁移、语雀备份、Lake 格式、yuque export。
version: 1.3.0
category: knowledge-management
agent_created: true
---

# 语雀 lakebook 解析

把语雀私有导出格式 `.lakebook` 还原成通用产物：Doc → Markdown、Sheet → CSV、Board → 原始 JSON，并复刻知识库的目录层级。

## 何时使用

- 用户给出 `.lakebook` 文件（或存放它们的目录），需要转成 Markdown / CSV
- 需要把语雀知识库迁移到 Obsidian、Notion、飞书、GitBook、Confluence
- 需要本地归档、备份语雀知识库
- 用户问「能不能解析 lakebook / Lake 格式」

## 执行流程

1. **确认输入**：拿到 `.lakebook` 文件路径或其所在目录。若用户只有语雀账号没有导出包，先引导其在语雀「知识库设置 → 更多设置 → 导出」生成（单次上限 200 篇，超出需先拆分知识库）。
2. **先跑语法检查与目录预览**，确认结构符合预期再全量转换：

   ```bash
   python3 scripts/lakebook_parser.py <输入> --list
   ```

3. **正式转换**。知识库较大时先加 `--nopic` 跑一遍（跳过图片下载，速度快数倍），确认无误后再跑一次带图片的：

   ```bash
   python3 scripts/lakebook_parser.py <输入> -o <输出目录>
   ```

4. **核对结果**：读取输出目录下的 `_manifest.json`，检查每篇文档的 `status`（`doc` / `sheet` / `board` / `skipped` / `error`）与输出路径。`error` 条目会在 `note` 里给出原因。随后跑 `scripts/audit_output.py <输出根目录>` 做产物体检（孤儿附件 / 死链 / 残留标记）。
5. **按目标平台微调**（见下节）。

## 参数

| 参数 | 作用 |
|---|---|
| `-o, --output` | 输出根目录，默认 `./lakebook_out` |
| `--list` | 只打印目录树，不做转换 |
| `--nopic` | 不下载图片，保留原始 CDN 外链 |
| `--nosheet` | 跳过表格文档 |
| `--keep-json` | 额外保留每篇文档的原始 JSON 到 `_raw/` |
| `--excel-dates` | 把表格里的 Excel 日期序列号转成 `YYYY-MM-DD` |
| `-q, --quiet` | 安静模式 |

输入可以是多个文件、也可以是一个目录（自动收集其中的 `*.lakebook`）。

## 输出结构

```
<输出目录>/
├── _last_run.json          本次运行的统计
└── <知识库名>/
    ├── _manifest.json      逐篇文档的标题/类型/层级/输出路径/状态
    ├── <分组>/             按 tocYml 的 level 还原
    │   ├── <文档>.md
    │   ├── <表格>.csv
    │   ├── <画板>.json
    │   └── _attachments/   本地化后的图片（--nopic 时不生成）
    └── ...
```

## 依赖

`markdownify` + `pyyaml` 转换质量最佳；两者缺失时脚本自带兜底实现（纯标准库）仍可运行，仅格式还原度略降。脚本运行时会打印当前生效的依赖状态。

托管环境可用解释器：`/Users/lvchajason/.workbuddy/binaries/python/envs/default/bin/python`

## 迁移到具体平台的后续处理

解析器产出的是平台中立的 Markdown，迁移前按目标改写：

- **Obsidian**：把 `](./_attachments/...` 改成 `![[...]]` 双链；需要电子表格时用 `--excel-dates` 并转换 CSV。
- **Notion**：Notion 只能导入扁平结构，把目录层级折叠进文件名前缀（`第一章 入门 - HTML 入门.md`）。
- **飞书文档**：直接导入 Markdown 或先用 `tencent-docx` 转 Word。
- **GitBook / MkDocs**：保留目录结构，补一个 `SUMMARY.md` 或 `mkdocs.yml`。
- **纯本地归档**：加 `--keep-json` 保留原始 JSON，便于将来重解析。

## 关键实现要点

解析前务必读 `references/lakebook-format.md`，尤其是这九个坑：

1. `$meta.json` 是**两层 JSON 嵌套**——`meta` 字段的值本身是 JSON 字符串。
2. 目录树靠 `tocYml` 的 `level` 字段用栈还原，第一条 `type: META` 不是内容。
3. **`type: DOC` 也可以同时是目录**：带非空 `child_uuid`（或后面紧跟更高 `level` 的条目）的文档，自身要输出 `<标题>.md`，同时再建一个同名目录承载子节点。只认 `type: TITLE` 会漏掉一整类节点，导致其子文档被平铺到上一层。
4. LaTeX 真身在 `body_asl` 的 math card 里，与正文的 `__latex` 图片**按顺序配对**；必须用占位符延后回填，否则换行被折叠、反斜杠被转义。
5. math card 的 `value` 有 **3 种写法**（明文 / HTML 实体的 JSON / `data:`+URL 编码的 JSON，后者是实测主流）。公式有「正文配对」和「ASL 直渲染」**两条入口，必须共用同一个解码函数**——分开写必然漂移，实测踩过：一条只做了实体反转义，把 `data:%7B...` 原样当 LaTeX 塞进了 `$...$`。
6. 表格是**三层嵌套压缩**：`body`(JSON) → `sheet`(**zlib 字节按 latin-1 编码**成字符串) → 解压后才是行列数据。
7. `doc.body` 可能为空，正文只在 `body_asl` 里——不回退就会产出空文档（实测 139 篇里有 61 篇如此）。
8. 卡片 `value` 常是 `data:` + URL 编码的 JSON（如 `codeblock`），解码后才知道代码语言和内容；**未知卡片先尝试捞 URL 还原成链接，不要静默丢弃**。
9. **转换器会静默吞掉标题内的图片**（`<h2><img/></h2>` → `## `），图片下载了却没人引用。转换前要把标题内的 `<img>` 提到标题外——详见下面「图片本地化的三个隐形陷阱」。

### 图片本地化的三个隐形陷阱

这三条都在实测中造成过「统计说成功、结果却不对」的问题：

- **替换必须用未反转义的属性原值**。语雀带查询参数的 `<img src>` 里写的是 `&amp;`；若把 `html_mod.unescape` 后的 URL 拿去 `tag.replace`，永远匹配不上——图片下载了、文件也落盘了、计数器还 `ok += 1`，但 Markdown 里的链接原封不动，留下一堆孤儿附件。请求用反转义值、替换用原值。
- **转换器会静默吞掉标题里的图片**。`<h2><img/><span>标题</span></h2>` 经 markdownify 变成 `## 标题`，图片凭空消失（表格单元格 `<td>` 同理，但实测 385 张图里 0 例）。语雀里把封面图塞进标题是常见写法，所以转换前必须把标题内的 `<img>` 提到标题之前 —— 见 `hoist_images_out_of_headings()`。
- **CDN 会瞬时限流**，同一批图里零星几张会失败（实测 96 张里 9 张首轮失败，原地重试全部成功）。下载要带退避重试。

这三条的共同特征是**失败不报错**：计数器是绿的、退出码是 0，只有拿「落盘附件数 vs Markdown 引用数」交叉核对才看得出来。所以转换后一定要跑 `audit_output.py`。

## 故障排查

| 现象 | 处理 |
|---|---|
| 报「未找到 $meta.json」 | 文件不是 lakebook，或下载不完整（分次导出只下了一部分） |
| 知识库名是一串随机字符（如 `ehyyx7`） | 新版导出省略了 `book.name`，脚本已回退用导出文件名；若仍不对，用 `-o` 指定输出目录名 |
| 某篇文档转出来是空的 | 检查该篇 `body_asl` 是否也为空；两者都空说明语雀端就是空文档 |
| 公式变成图片链接 | `body_asl` 为空（草稿态导出），无法还原，属正常 |
| 公式变成 `$data:%7B%22code%22...$` 这样的乱码 | math card 的解码没走到「取 JSON `code` 字段」那一步；两条公式路径要共用同一个解码函数 |
| 目录里少了整层，子文档被平铺到上一层 | `type: DOC` 的节点也可以是目录，检查是否只按 `type: TITLE` 判目录 |
| 分隔线把上一行渲染成了大标题 | 裸 `---` 紧贴文字会被 Markdown 当成 setext 下划线；`hr` / 链接卡片必须走占位符 |
| 代码块里的下划线/星号多了反斜杠 | 代码内容没走占位符，被 Markdown 转义了；应进 `BlockCollector` |
| `_attachments/` 里文件数明显多于 Markdown 中的引用数 | 有孤儿附件，说明替换环节没命中（多半是 `&amp;` 未处理）；见「图片本地化的两个隐形陷阱」 |
| 少数图片保留 CDN 外链未本地化 | 多为 CDN 瞬时限流，脚本已带退避重试（默认 3 次）；仍失败则保留原外链，不影响其余内容 |
| CSV 打不开或乱码 | 用 `--nosheet` 先跳过，单独用 `--keep-json` 取出原始 JSON 排查 |
| 退出码 2 | 有文档条目解析失败，逐条记录在 `_manifest.json`，不代表整体失败 |
| 文档数少于预期 | 语雀导出上限 200 篇；或知识库关闭了「下载」权限 |

## 自检

改动脚本后跑一遍回归，会在临时目录合成样本并执行 **93 项断言**（图片下载器单测 6 项 + 产物体检单测 8 项 + 默认模式 40 项 + 纯标准库兜底模式 39 项），跑完不残留任何文件：

```bash
python3 scripts/verify.py
```

`scripts/make_fixture.py` 单独可用来生成符合官方规范的测试用 `.lakebook`（覆盖 TITLE 分组、三层嵌套、「文档即目录」、Doc/Sheet/Board、三种 math 卡片写法、`&amp;` 图片、非法文件名字符、缺失 json 条目、ASL 回退等）。

转换真实导出后，**务必跑一遍产物体检**——计数器说「成功」不等于产物正确：

```bash
python3 scripts/audit_output.py <输出根目录>
```

它会逐库核对：孤儿附件（下载了但没人引用）、死链、残留的 `<card>` / `__latex` / `data:` / CDN 外链、空文档、manifest 状态分布。有需要处理的问题时退出码为 1。只读、不联网、不改文件。
