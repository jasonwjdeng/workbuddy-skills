# 发音人与语速速查

## 一、macOS 内置英文发音人

用 `tts.py --list-voices --english` 查询当前系统实际安装的发音人。常见如下：

| 发音人 | 口音 | 音质与适用场景 |
| --- | --- | --- |
| **Samantha** | en_US | 清晰自然、语调中性。**默认首选**，适合讲解、跟读、长文 |
| **Alex** | en_US | 男声，沉稳、略机械。适合正式文档、有声书式朗读 |
| **Victoria** | en_US | 女声，柔和偏慢。适合抒情文本 |
| **Fred** | en_US | 老式合成音，音质差。仅在其它发音人缺失时兜底 |
| **Daniel** | en_GB | 英式男声，公认质量高。适合正式书面语、商务文本 |
| **Moira** | en_IE | 爱尔兰口音，语调有音乐性，辨识度高 |
| **Karen** | en_AU | 澳式女声，听感略特殊 |
| **Tessa** | en_ZA | 南非口音 |
| **Rishi / Veena** | en_IN | 印度英语，语速感偏快 |
| **Fiona** | en-scotland | 苏格兰口音，辨识度极高，慎用 |

**实测清单**（本机已验证）：Alex、Daniel、Fiona、Fred、Karen、Moira、Rishi、Samantha、Tessa、Veena、Victoria，共 11 个英文发音人。

**关键提示**：发音人是否可用取决于本机已安装的语音包。脚本在指定了不存在的发音人时会直接报错并列出可用项，不会静默降级——听到的声音不是你要的那个口音，问题往往在这里。

## 二、中文发音人

中文文本必须用中文发音人，否则英文发音人会把中文念成怪音。

| 发音人 | 语言 | 备注 |
| --- | --- | --- |
| **Tingting** | zh_CN | 标准普通话，最常用 |
| **Meijia** | zh_TW | 台湾普通话 |
| **Sinji** | zh_HK | 粤语 |
| **Yu-shu** | zh_CN | 男声（视系统版本） |

查询方式：`tts.py --list-voices` 后用 `zh_` 过滤。

## 三、语速建议（wpm = words per minute）

| 场景 | 建议语速 | 说明 |
| --- | --- | --- |
| 跟读 / 逐句复述 | 130–150 | 留出跟读间隔感，学习者能跟上 |
| 泛听 / 通勤听 | 165–180 | 接近正常语速 |
| 母语者自然语速参照 | 190–210 | 听读练习的高阶目标，不宜作为首次接触材料 |
| 正式书面语朗读 | 160–170 | 配合正式语体，节奏刻意放缓 |
| 自然口语朗读 | 175–190 | 配合口语语体，稍微偏快更像真人对话 |

**默认值 175**。脚本会把 `--rate` 限制在 80–400 之间，超出直接报错——过低的语速听感失真，过高则失去可懂度。

## 四、多版本对照朗读的推荐组合

同一段内容做语体/难度对照时，**同时用口音和语速做区分**，耳朵才能听出差别：

| 版本 | 发音人 | 语速 | 播报语（--label） |
| --- | --- | --- | --- |
| 正式书面语 | Daniel (en_GB) | 165 | Version one. Formal, written register. |
| 自然口语 | Samantha (en_US) | 180 | Version two. Casual, spoken register. |

配套做法：
- 每个音频开头加 `--label`，避免多个文件听混。
- 文件名带语体标记（`-formal-reading.m4a` / `-casual-reading.m4a`）。
- 交付时给一张对照表（文件 / 语体 / 发音人 / 语速 / 时长）。

## 五、发音陷阱与处理

合成器在技术文本上最容易翻车的几类，处理方式是在**朗读稿**里改写、源文件不动：

| 类别 | 例子 | 朗读稿写法 |
| --- | --- | --- |
| 缩写词逐字母读 | PgSQL / K8s / a11y | Postgres / Kubernetes / accessibility |
| 数字字母混排 | 2FA / S3 / 5xx | two factor authentication / S three / five hundred errors |
| 品牌名 | Nginx / SQLite | Engine X / S Q Lite |
| 版本号 | Java 17 / v1.2.3 | Java seventeen / version one point two point three |
| URL 与路径 | https://x.com/a/b | 用 `--pronounce` 换成口语描述（"the Actuator Prometheus endpoint on localhost"），**绝不逐字符念** |
| 符号 | & / + / → | and / plus / leads to |
| 缩写 | e.g. / etc. | for example / et cetera |
| Markdown 标记 | `**加粗**`、`## 标题` | 剥离标记，只留文字 |

内置替换表在 `references/pronunciation.json`，可按项目追加。用 `--pronounce custom.json` 指定自有替换表，或用 `--no-pronounce` 完全关闭。

**始终向用户报告做了哪些替换**——这是朗读稿与原文的差异，不告知就等于偷偷改了内容。
