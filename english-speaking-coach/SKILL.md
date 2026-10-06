---
name: english-speaking-coach
description: "英语朗读/口语评测教练。对用户的朗读录音做客观测量 + 三维评分（发音准确性、语音语调、语速与流畅度），指出读错的单词、语调不自然的位置与语速问题，并给出跟读改进方案。触发场景：用户发来朗读录音要求打分/点评/纠音，说「帮我听听读得怎么样」「评估我的发音」「口语陪练」，或要求把 output/ 里的改稿朗读后做反馈。"
agent_created: true
---

# English Speaking Coach — 朗读录音评测

## 用途

把一段朗读录音变成一份**有数据支撑、可执行**的评测报告。分成两半：

1. **测量（脚本）**：`scripts/analyze_reading.py` 用 ASR + 声学分析产出客观数字（转写、词级时间戳、与参考文本的对齐差异、语速、停顿、音高曲线）。
2. **判断（模型）**：读 JSON，做评分、归类、写教学反馈。**脚本不打分**，分档判断必须由模型结合语境完成。

## 触发场景

- 用户发来录音（m4a / wav / mp3）+ 想听点评、打分、纠音
- "我读一段你评评"、"帮我看看发音哪里不对"、"口语练习反馈"
- 用户朗读了 `output/` 里的改稿（`## Rewritten Text` 段落）要求反馈

## 前置检查

python 解释器固定用（whisper + torch 装在这里）：

```bash
V=/Users/lvchajason/.workbuddy/binaries/python/envs/torch312/bin/python
$V -c "import whisper, numba, torch, parselmouth; print('ok')"
```

若报缺包，见文末「环境备忘」——**不要**试图用 pip 重装 `openai-whisper`、`av` 或 `librosa`。`parselmouth` 缺失时音高会退化到自写追踪器，**结论不可信**，必须先装上。

## 核心流程

### 步骤 1：确定录音与参考文本

- 参考文本**优先**取改稿正文。若用户读的是 `output/<名>-<formal|casual>.md`，直接传 `--ref-md`，脚本会自动抽 `## Rewritten Text` 段落并剥掉 Markdown 装饰。
- 录音默认放在 `recordings/`（如 `recordings/202610061415.m4a`）；`draft/` 存的是习作原稿，不要往那里塞录音。
- 用户只给了录音、没说读的哪篇：先看录音时长，再到 `output/` 里比对哪篇改稿的朗读时长接近（`afinfo <file> | grep duration`）。更可靠的做法是**先无参考转写一遍**，再把转写与各篇 `Rewritten Text` 做相似度比对（`difflib.SequenceMatcher`）——实测能一眼分出（命中篇 0.82 vs 其余 <0.15）。
- 用户自由口语（不是朗读）时告知：本 skill 的发音评估依赖参考文本，自由说只能评流畅度/语调，建议拿改稿朗读。

### 步骤 2：先校准，再测（**不要跳过校准**）

本 skill 的每个阈值都是估计值。用范读音频验证它们在**已知正确的母语语音**上表现正常，再拿去评学习者：

```bash
V=/Users/lvchajason/.workbuddy/binaries/python/envs/torch312/bin/python
cd /Users/lvchajason/Documents/workspace/notes
OMP_NUM_THREADS=4 $V /Users/lvchajason/.workbuddy/skills/english-speaking-coach/scripts/calibrate_reference.py \
  --json /tmp/calibration.json
```

12 篇范读约 7 分钟（有缓存后复跑很快）。**判定标准：句末降调判定在范读上的命中率必须 ≥90%**；实测 96%（103/107）。若明显偏低，说明指标坏了，先修指标，不要急着出报告。

### 步骤 3：跑测量

```bash
OMP_NUM_THREADS=4 $V /Users/lvchajason/.workbuddy/skills/english-speaking-coach/scripts/analyze_reading.py \
  --audio draft/<录音>.m4a \
  --ref-md output/<改稿>.md \
  --model small.en --domain-prompt \
  --asr-cache ~/.cache/english-speaking-coach/asr \
  --json /tmp/<name>-analysis.json
```

- **`--domain-prompt` 必加**：不加会把 `employs Spring Boot` 听成 "implies Springboard"、`Azure DevOps` 听成 "Zoo DevOps"、`backend` 听成 "background"，制造一堆假的"发音错误"。
- **`--asr-cache` 必加**：命中的话 40 秒的分析变 4 秒，调参期差别巨大。缓存键含文件 size+mtime，重录不会读到旧结果。
- `--model small.en`（默认）比 `base.en` 准；`base.en` 只在赶时间时用。
- 音频解码走系统自带 `afconvert`，波形以 numpy 数组喂给 whisper，**不需要 ffmpeg**。

### 步骤 4：读 JSON 并写报告

拿 JSON 里的这几块：`speech_rate` / `pause` / `pitch` / `alignment` / `sentences`。

**关键纪律 —— 不要把 ASR 误听当成发音错误。** 判读顺序：

1. `alignment.substituted` 里 `domain_term: true` 的条目（kubernetes / postgresql / grafana / actuator / micrometer / airflow…）→ 一律先归为「疑似 ASR 误听，待人工复核」，**不写进"读错的单词"**。small.en 对这类低频专名本来就弱。
2. `alignment.skipped` 中若跳过的是 `-ed` / `-s` / 冠词 / 介词这类**弱读虚词** → 多为真实问题（词尾吞音、弱读过度），要写。
3. `alignment.substituted` 中 `domain_term: false` 且 `prob` 低的实词 → 高置信度发音问题，要写。
4. `alignment.added` 里若出现 `uh` / `um` / 重复词 → 归入流畅度；若是不成词的碎片 → 归入发音/重启。
5. 报告里必须声明 ASR 的局限，并请用户对存疑项对照参考音频自己复核。

**语调判读**：看 `sentences[].final_slope_st_per_s` 与 `final_delta_st`。陈述句、wh- 疑问句**句末应收束下降**（斜率为负）；列举未完项、句中的逗号从句、yes/no 问句**可以上扬**。只有在句末位置测到明显上扬（`final_slope_st_per_s > 0.5` 且 `final_delta_st > 0.8`）才算不自然。`range_st` 小、且句子时长 ≥1.5s → 语调平板（单调）。

**语速判读**：`overall_wpm` 与 `articulation_wpm` 要分开看。朗读目标约 **130–160 wpm**；`silence_share` >15% 或 `pause.longest` >1.2s 说明卡顿明显。注意：非母语者把难词读慢是正常的，错在**同一篇内速率波动过大**，所以要看 `sentences[].wpm` 的离散度。

### 步骤 5：写报告并交付

产物写到 `output/`：`output/<改稿名>-speaking-feedback.md`（例如 `output/20260924-application-i-am-working-on-formal-speaking-feedback.md`），正文中文、引用英文。建议同时产出一份同名的 `.html`，用曲线图把「该降却升／降幅不够」直接画出来 —— 用文字很难讲清，一张图就明白了。最后用 present_files 交付。

曲线图用脚本生成，不要手工画：

```bash
$V scripts/plot_terminal_contours.py \
  --ref-md output/<改稿>.md \
  --series "本次=recordings/<新录音>.m4a" \
  --series "上次=<旧录音>.m4a" \
  --series "Daniel=output/<改稿>-reading.m4a" \
  --out /tmp/contours.svg --json /tmp/contours.json
```

输出一段 `<svg>`（viewBox `0 0 680 H`），直接嵌进 HTML 即可。每个 `--series` 是 `标签=路径`，最多 3 条，第一条画得最粗。**做多轮对比时务必把「上次」也画上**，进步与退步一目了然。

**报告里必须写的一句话**：每轮都要给「下轮验证点」，并和上一轮的分数、指标并列成表，让用户看到趋势而不是单点。

## 评分锚点（用范读实测值定标，别凭感觉给分）

`calibrate_reference.py` 在 12 篇范读上跑出的基准（2026-10-06 实测）：

| 指标 | Daniel 英音正式版（男声，可比对象） | Samantha 美音口语版 |
| --- | --- | --- |
| 整体语速 | **137.5 wpm**（区间 126–144） | 175.0 wpm（162–186） |
| 静音占比 | 13.3%（12–16） | 13.3%（11–16） |
| 中位 F0 | 109.7 Hz | 172.1 Hz |
| 音域（p5–p95） | **8.87 半音**（8.2–9.7） | 10.38 半音 |
| 句末半音变化 | 中位 **−5.10** | 中位 −7.44 |
| 句末降调命中率 | **51/52 句下降（98%）** | 52/54 |

（全库合计 103/106 = 97%。以上为 2026-10-06 用 Praat 算法重算后的值。）

打分时用"**与同性别的同语体范读比**"（男声对 Daniel、女声对 Samantha），否则中位音高根本不可比。

**关键判读经验**

1. **"慢"要拆开看**：静音占比低于范读（如 9.5% < 13.3%）说明**不是卡顿型慢**，而是词本身被拉长 → 病因是功能词没弱读，不是"停顿太多"。练习方向完全不同。
2. **音域大 ≠ 语调好**：学习者音域可能比范读还宽（11.84 vs 9.43 半音），但起伏动在句内、句末却不收束。所以"音域/i 标准差"低分**不能**直接推"语调平板"；要看 `final_contour`。
3. **同词时长对比最有力**：用能量包络算实际发声时长再除以范读同词时长。典型结果是功能词 1.4–2.5×、实词 ~1.0×——"重音关系反了"这句话就有据可依。见 `output/20260924-...-speaking-feedback.md` 第三节。
4. **低置信词比例是公平性指标**：学习者 vs 范读（≤0.6 的比例）。实测 19.8% vs 3.6%。**但必须先排查录音电平**（见下），否则会把录音问题算成发音问题。

## 报告模板

```markdown
# 朗读评测报告 — <篇名>（<正式/口语>版）

## 一、总评
| 维度 | 得分 | 一句话结论 |
| --- | --- | --- |
| 发音准确性 | xx/100 | ... |
| 语音语调 | xx/100 | ... |
| 语速与流畅度 | xx/100 | ... |
| **加权总分** | **xx/100** | 权重 发音 40% / 语调 30% / 流畅 30% |

（一句总评：最值得先改的一件事）

## 二、发音准确性（xx/100）
### 需要修正的词（高置信度）
| 单词 | 时间点 | 问题类型 | 应该怎么读 | 纠正动作 |
### 疑似 ASR 误听，请自行复核
| 参考词 | 听到的 | 时间点 |
（逐条说明为什么可能是误听，建议对着 `-reading.m4a` 复听）

## 三、语音语调（xx/100）
### 句末升降调
| 句子 | 实测尾调 | 应然 | 判定 |
### 语调平板 / 重音与节奏 / 连读弱读
（点名具体位置，给数值）

## 四、语速与流畅度（xx/100）
- 整体 wpm / 发音速率 / 静音占比
- 停顿清单（时长 + 位置 + 是否落在意群边界）
- 语速波动最大的句子

## 五、优先改进清单（只列 3 条）
1. ... 2. ... 3. ...

## 六、下一步练习
- 跟读材料：`output/<改稿名>-<register>-reading.m4a`（Daniel 165wpm / Samantha 180wpm）
- 具体动作：本轮 3 个音 + 2 个语调位置，逐句跟读 3 遍，再录一遍对比

## 附：测量数据摘要
（duration / words / wpm / pauses / pitch median & range）
```

## 已知限制（必须向用户说明）

- ASR 是**间接**证据：它只告诉你"系统听成了什么词"，不能证明某个音素读错了。元音长短、/θ/、/v/ 这类细微差别它抓不到——这些要靠用户复听参考音频。
- **先查录音电平再看结论**：报告里的 `audio_quality.peak_dbfs` 若低于 −20 dBFS（实测一次只有 −24.1 dBFS），说明麦克风太远。低电平会拉低识别置信度，把"录音问题"混进"发音问题"。此时应在报告里明确提示重录，并把"低置信词比例"写成**混合信号**而非纯发音问题。
- 音高曲线在录音有背景噪声、爆音、呼吸声、或离麦克风过远时会失真。若某句 `final_contour` 为 null，直接写"数据不足，无法判定"，**不要猜**。
- 录音可能有响度高于语音的非语音爆发（呼吸/碰麦），会同时干扰识别与测量。
- 只听**朗读**。自由口语的语法/用词不在此 skill 范围（那是 `english-essay-rewrite` 的领域）。
- **勘误纪律**：这份报告是会被存档、会被用户拿来回看的。如果后续发现某个指标有问题、结论被推翻，**必须回头修正已经交付的报告**（在文首加勘误块、就地标注作废的表述、重画受影响的图），不能只在新的报告里悄悄改掉。2026-10-06 就出现过一次：因为 F0 追踪器锁谐波，第 1 轮的「音域比母语者宽」「句末有 +10 半音上扬」两条结论完全错误，两份报告（md + html）都已回头修正。

## 环境备忘（踩过的坑）

- python：`/Users/lvchajason/.workbuddy/binaries/python/envs/torch312/bin/python`（Python 3.12.8，已有 torch 2.2.2）。跑分析时加 `OMP_NUM_THREADS=4`，否则并行跑两个任务会互相拖慢。
- **录音存放目录**：`recordings/`（用户的录音落点），参照文本仍在 `output/`。语音备忘录导出的临时文件要立刻拷出来 —— `/private/var/folders/.../com.apple.VoiceMemos/...temporary.*/xxxx.m4a` 会被清理。注意录音格式不固定：语音备忘录是 44.1kHz 立体声（两声道相同，实为单声道），其他录音 App 可能产出 16kHz 单声道；`afconvert` 都能处理，但**格式不同意味着链路不同，跨录音对比前先看 `audio_quality` 与噪声底**。
- **`pip install openai-whisper` 会失败**：沙箱的 shim 拦截 pip 建临时目录，对源码包稳定报 `EEXIST ... pip-install-*/<pkg>_<hash>`。解法是手动装：
  ```bash
  U=$(curl -s https://mirrors.aliyun.com/pypi/simple/openai-whisper/ | grep -o 'href="[^"]*openai_whisper-[0-9.]*\.tar\.gz[^"]*"' | tail -1 | sed 's/href="//;s/"$//;s|^\.\./\.\./|https://mirrors.aliyun.com/pypi/|;s|#.*$||')
  curl -sL -o /tmp/whisper.tar.gz "$U" && cd /tmp && tar xzf whisper.tar.gz
  cp -R /tmp/openai_whisper-*/whisper <site-packages>/
  ```
- **`av` 装不上**：py3.12/3.13 都没有预编译 wheel，源码编译需要 ffmpeg 开发库。所以本 skill 绕开它——用 `afconvert` 解码，把 numpy 波形直接传给 `model.transcribe()`，whisper 不会去 import av。
- **`numba` 必须钉 0.60.0**：更新的 numba 要求 numpy ≥ 2.0，而 torch 2.2.2 环境里是 numpy 1.26.4。
- **`librosa` 装不上**（会连带要求 numba ≥0.61 并回退到源码包，同样撞 EEXIST）。不要再试；音高分析改用 `praat-parselmouth`：
  ```bash
  <torch312>/pip install --no-cache-dir praat-parselmouth   # 0.4.7 有 cp312 x86_64 wheel，装得上
  ```
  它是编译好的 wheel，不走源码包，因此不受沙箱 EEXIST 影响。**这是音高分析的首选方案。**
- **`huggingface.co` 直连不通**：`faster_whisper` 路线需要 `HF_ENDPOINT=https://hf-mirror.com`。本 skill 用 openai-whisper，模型走 `openaipublic.azureedge.net`，实测可直连，下载到 `~/.cache/whisper/`。
- 模型：`base.en`（139MB）与 `small.en`（484MB）已下载；更大模型在 CPU 上不值得。

### 音高测量：必须用 Praat，不要自写追踪器

**这条是从一次真实事故里学来的，请严格遵守。** 我最初自写了一个能量门限 + 自相关的 F0 追踪器。它在干净的 TTS 范读上表现正常，于是通过了校准 —— 但在学习者低电平、高噪声的真人录音上，它会**锁到谐波**，稳定报出高 10–19 半音的假值，持续 100–250 ms。由此我给出了两个完全错误的结论（「音域比母语者还宽」「句末升 +10 半音」），并写进了正式报告。事后的排查过程：

1. 加能量门限 → 没用：那些伪迹帧的能量与正常语音相当（−0.7 dB）。
2. 加 110 ms 局部中位数跳变滤波 → 没用：伪迹持续 250 ms，局部中位数被它带跑了。
3. 加长到 450 ms 窗口 → 能压掉，但**对两次录音的处理不一致**（长伪迹被保留、短的被剔除），说明方法本身不可靠。
4. 最终解法：换成 **Praat 的 `To Pitch (ac)`**（Boersma 自相关法，`praat-parselmouth` 包），再加 450 ms 窗口 Hampel 滤波（阈值 5 半音）。两次录音立刻互相印证（5.32 / 4.87 半音），与范读的 8.87 半音形成合理对比。

**留给后人的判据**：如果某个学习者的「音域」比母语范读还宽、或出现 +10 ~ +19 半音的孤立跃迁，**先怀疑测量，不要先写结论**。真实的人声朗读极少超过 1 个八度。

`_clean_f0` 的两道处理（全局带宽 2.5×/0.4× + 长窗口 Hampel）保留作为兜底，但主力是 Praat。

### 跨录音复现：区分真实问题与识别噪声

学习者同一个词在**两次独立录音**里都被听低 → 高可信度问题，写进报告。只出现一次 → 标为「待观察」，不要下结论。这个方法能有效过滤单次的识别噪声。

### 句末判定不能用「连续有声段」

低电平录音的有声帧是断续的。要求连续会让绝大多数句子返回 null。正确做法：在句末窗口内**取全部有声帧**，只约束总帧数（≥8）与时间跨度（≥0.20s）。

## 与现有工作流的衔接

`english-essay-rewrite`（写作）→ `read-aloud-audio`（产出 Daniel/Samantha 范读音频）→ **`english-speaking-coach`（朗读评测）**。
用户长期薄弱点（见工作区 memory）里的**冠词、词尾、并列结构**在朗读中会以"吞音/弱读过度"的形式复现，评测时应主动交叉检查。
