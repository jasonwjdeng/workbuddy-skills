---
name: read-aloud-audio
description: "把文本读成音频（TTS 朗读）。使用 macOS 内置语音合成把英文/中文文本、Markdown 文档或作文改稿转成可播放的音频文件（m4a），支持指定发音人、语速、多版本对照朗读与专名发音修正。触发场景：用户说「读给我听」「念给我听」「生成朗读音频」「做成音频/语音」「用真人音读一下」「跟读素材」，或要求把文章、作文、单词表转为听力材料。"
agent_created: true
---

# Read Aloud Audio — 文本朗读音频生成

## 用途

把文本变成能直接播放的音频文件。基于 macOS 内置的语音合成（`say`）+ 音频转码（`afconvert`），**离线、无需 API key、无网络请求**。

产物统一为 `.m4a`（AAC 编码，22050 Hz 单声道，语音场景足够且体积小），可直接播放、可传手机当听力素材。

## 触发场景

- "读给我听 / 念给我听 / 帮我读一下"
- "把这篇作文做成音频"、"生成朗读音频"、"做成听力材料"
- "用英式发音读正式版，美式读口语版"（语体对照朗读）
- 把单词表、范文、Markdown 文档转成可听的素材

## 前置检查

只在 macOS 上可用。第一步先确认命令存在：

```bash
which say afconvert afinfo
```

三者都应返回 `/usr/bin/...`。若任意一个缺失，直接告知用户该 skill 不可用，不要尝试用网络 TTS 替代。

再确认可用发音人：

```bash
<python> scripts/tts.py --list-voices --english
```

## 核心流程

### 步骤 1：确定朗读内容

| 输入形态 | 处理方式 |
| --- | --- |
| 用户直接给的文本 | 直接使用 |
| 本地文件（.md/.txt） | 读取后**只取要朗读的部分**——Markdown 的标题标记、表格、代码块、链接语法都要剥掉，否则会被逐字念出来 |
| 已有改稿（如 `output/*-formal.md`） | 朗读 `## Rewritten Text` 章节的正文，不要念"修改理由""词汇表"等中文讲解部分，除非用户明确要求 |

朗读稿是"给嘴听的稿"，不是"给眼看稿"：写成 `# 标题`「`**加粗**`」这类标记会让合成音念出符号或产生怪停顿。

### 步骤 2：选发音人与语速

发音人速查表见 `references/voices.md`。默认策略：

- **单篇朗读**：Samantha（en_US，自然清晰）或 Alex（en_US）。
- **多版本对照**：刻意用不同口音区分语体——正式版用 Daniel（en_GB），口语版用 Samantha（en_US）。
- **跟读素材**：语速降到 130–150 wpm。
- **日常听读**：170–185 wpm。

语速是 wpm（words per minute）。默认 175。

### 步骤 3：准备朗读文本并处理发音陷阱

技术文本里有一类专名会被合成器念错或念得支离破碎：缩写词（PgSQL、K8s）、品牌名（Nginx、Kubernetes）、版本号、URL、文件路径。

处理方式：把它们在**朗读稿**里改写成发音友好的等价形式，**同时保留原文件不动**，并在交付时明确告知用户改了哪几处。

常用替换（`references/pronunciation.json` 内置默认表）：

| 原文 | 朗读稿写法 | 原因 |
| --- | --- | --- |
| PgSQL | Postgres | 逐字母念会变成 pg-s-q-l |
| K8s | Kubernetes | 数字字母混排易错 |
| Nginx | Engine-X | 默认读音不稳定 |
| 5xx | five-hundred | 数字读法歧义 |

**URL 必须单独处理**：合成器会把 `http://localhost/actuator/prometheus` 逐字符念成 "h-t-t-p colon slash slash ..."，听感很糟。用 `--pronounce` 指定一张临时表，把 URL 替换成口语描述：

```json
{ "http://localhost/actuator/prometheus": "the Actuator Prometheus endpoint on localhost" }
```

```bash
<python> scripts/tts.py article.md --section "Rewritten Text" \
  --pronounce /tmp/tts-extra.json -o output -v Daniel -r 165
```

`--pronounce` 指定的表会**叠加**在默认表之上（同名键以自定义为准），不必重复内置条目；要完全接管则加 `--no-default-pronounce`。

其余情况按需临时替换，不追求全量词典。**无论替换了几处，都要在交付时明确告知用户。**

**不要靠猜缩写会不会念错——用"时长对比法"验证**（见技术要点最后一条）。很多缩写其实本地合成器读得完全正确，多余替换反而让朗读稿不自然。

### 步骤 4：生成音频

```bash
<python> scripts/tts.py <input.txt> -o <out-dir> -v Samantha -r 180
```

默认命名：`<input-stem>-reading.m4a`。可用 `-n/--name` 覆盖，`--label` 在音频开头插入一句播报（如 "Version one. Formal, written register."），便于多版本对照时知道听的是哪一版。

多份文本一次性生成（多发音人对照的标准做法）：

```bash
<python> scripts/tts.py formal.txt -o output -v Daniel -r 165 --label "Version one. Formal, written register." -n xxx-formal-reading
<python> scripts/tts.py casual.txt -o output -v Samantha -r 180 --label "Version two. Casual, spoken register." -n xxx-casual-reading
```

脚本会自动完成 `say → aiff → afconvert → m4a`，并用 `afinfo` 校验产物、打印时长。

### 步骤 5：校验与呈现

1. 确认输出文件存在、时长合理（一段 120 词的英文约 40–50 秒；时长明显偏短说明文本被吞了）。
2. 调用 present_files 呈现音频。
3. 文字回复里给一张小表：文件名 / 语体 / 发音人 / 语速 / 时长。**并说明朗读稿相对原文的发音替换**。
4. 主动给一句后续动作：可换发音人、可调语速做跟读版。

## 技术要点（踩过的坑）

- **`afconvert -b 128000` 会失败**：报 `Error: Couldn't set audio converter property ('!dat')`。改用质量参数 `-q 127`，不要用码率参数。
- **中间产物走 `.aiff` 更稳**：`say -o x.m4a` 在部分系统版本上行为不一致（可能写出与扩展名不符的格式），所以脚本固定 `say -o x.aiff` → `afconvert` → `.m4a` 两步走。
- **对话/长文要拆段**：`say` 对超长文本会连续读完、不分段，停顿节奏变差。长文拆成多个文件分别生成，或按段落插入额外换行。
- **`say -x` / `--phrasal` 在本机不可用**（报 `invalid option`），拿不到音素表示，别把它当验证手段。
- **判断缩写会不会被念错：时长对比法**。分别合成"缩写原样"和"空格拆开的大写字母"（如 `JSON` vs `J S O N`），用 `afinfo` 比 `estimated duration`：
  ```bash
  for w in "JSON" "J S O N"; do say -v Daniel -o "/tmp/t_$(echo $w|tr ' ' '_').aiff" "$w"; done
  for f in /tmp/t_*.aiff; do echo "$f $(afinfo "$f" | grep -o 'estimated duration: [0-9.]*')"; done
  ```
  两次时长相同 ⇒ 合成器走"逐字母"路径，读法正确，**无需替换**。2026-09-29 实测（macOS + Daniel）：`JSON`=`J S O N`=1.20s、`TPS`=`T P S`=1.13s、`JVM`=`J V M`=1.04s、`HikariCP`=`Hikari C P`=1.29s、`HTTP` 逐字母 —— 这五类都**不用写进替换表**。2026-09-30 补测需替换的一侧：`PgSQL` 1.61s = `P G S Q L` 1.61s（走逐字母路径，读成 pg-s-q-l），而 `Postgres` 仅 1.01s —— 证实内置表的这条替换确有必要；反之 `Nginx` 这类时长明显偏离预期的同理。
  注意：**"逐字母念"本身不等于读错**。JSON / TPS / JVM / HTTP 逐字母就是它们的正常读法，只有像 PgSQL 这种"逐字母念反而没人这么说"的才需要替换。
- **`--` 开头的文本**：命令行里传文本用 `-f 文件`，不要直接当位置参数，避免被解析成选项。
- **中文文本**：需指定中文发音人（如 Tingting / Meijia），否则英文发音人会把中文读成怪音。用 `--list-voices` 查 `zh_CN`。

## 相关技能

- 需要先批改/改写英文作文再朗读 → `english-essay-rewrite`
- 需要把多段朗读**按精确时间点拼成一条音轨**做视频配音（不是单篇朗读）→ `ak-output-ladder` 的四级视频那节（`say` 量时长 → `afconvert` → Python `wave` 定长拼轨，总长必须等于视频总长）
