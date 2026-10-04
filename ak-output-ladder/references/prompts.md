# 四个提示词模板（全文）

`{{ }}` 是填空位，方括号 `[ ]` 是可选项。变量之外的文字**一个字都别改**——那些约束就是模板的全部价值。

---

## 1A · 受控语言写作（中文版）

**变量**：`{{主题}}`、`{{输出语言}}`

> 注意：中文版只能继承**句法纪律**，拿不到**受控词汇约束**（ASD-STE100 的词表是英文的）。想要完整效果用下面的 1B。

```text
用 ASD-STE100（Simplified Technical English，航空航天维修文档的受控语言规范）
解释 {{主题}}，做到约八成合规——这套规范很严苛，刻意留 20% 的灵活性。

写作规则：
1. 一句一个意思。操作句 ≤ 20 个词，描述句 ≤ 25 个词。
2. 只用主动语态。被动语态只在无法避免时使用，且必须写出施动者。
3. 只用一般现在时。不用进行时、不用完成时、不用复杂的复合谓语。
4. 一词一义：同一个概念全程用同一个词，不许换同义词。
5. 名词堆叠不超过 3 个词。
6. 三个以上的并列项，一律改成竖排列表，不许写成一句话。
7. 每个专业术语第一次出现时，就地用一句话定义。
8. 一段只讲一个主题，不超过 6 句。

禁止隐喻。遇到隐喻式术语（注意力、门控、记忆、遗忘、幻觉这类），
不要翻译这个词，直接把它拆成可以执行的步骤——把名词换成机制。

结构顺序：是什么 → 怎么工作 → 能做什么 → 不能做什么。

输出语言：{{输出语言}}。
最后附一张自检表，逐条对照上面 8 条，标出哪条没做到；
再指出哪 20% 是刻意放松的，以及放松的代价是什么。
```

---

## 1B · Controlled-language writing (English — preferred)

**变量**：`{{TOPIC}}`、`{{OUTPUT LANGUAGE}}`（填 `English` 才拿得到完整的受控词汇约束；填 `Chinese` 只有句法纪律）

> 这段提示词本身按 STE 风格写：短句、祈使、一词一义。等于顺手给模型一个"照这个样子写"的样例。

```text
Explain {{TOPIC}} in ASD-STE100 (Simplified Technical English), the controlled
language of aerospace maintenance documentation. Target about 80 percent
compliance. This specification is strict. Keep 20 percent of the flexibility.

Writing rules:
1. One idea in one sentence. Procedural sentences: 20 words maximum.
   Descriptive sentences: 25 words maximum.
2. Use the active voice. Use the passive voice only when you cannot avoid it.
   Then give the agent of the action.
3. Use the simple present tense. Do not use the progressive form.
   Do not use the perfect form.
4. Use one word for one meaning. Use the same word for the same concept in the
   full text. Do not use synonyms.
5. Do not put more than three nouns together.
6. For three or more items, make a vertical list. Do not write one long sentence.
7. Define each technical term at its first use. Use one sentence.
8. One topic in one paragraph. Six sentences maximum.

Do not use metaphors. Some technical terms are metaphors (attention, gate,
memory, forget, hallucination). Do not translate these terms. Replace each
metaphor with its mechanism. Write the steps that the mechanism does.

Use this structure: what it is -> how it works -> what it can do ->
what it cannot do.

Output language: {{OUTPUT LANGUAGE}}.

At the end, add a compliance table. Compare your text with the 8 rules above.
Mark each rule "met" or "not met". Then state which 20 percent you relaxed,
and the cost of that relaxation.
```

---

## 2 · 图表

**变量**：`{{主题}}`、`{{张数}}`、`{{配色主题}}`、`{{图内语言}}`

```text
为 {{主题}} 生成 {{张数}} 张说明图，输出为可直接嵌入的内联 SVG。

规划要求：
1. 先给我一句话的图结构规划（画几张、每张回答什么问题），我确认后再出图。
2. 每张图只回答一个问题；图与图之间要递进——先讲「长什么样」，再讲「怎么动起来」。
3. 优先用这五类结构：流程、层级、对比、流向、矩阵。装饰性图形一律不要。
4. 至少有一张图要标注每一步的「数据形态」——这一步的输入输出到底是什么形式、
   什么量级（例：字符串 → 词元列表 → 3×768 个数字 → 100 层 → 下一个词元）。

绘制要求：
5. 配色跟随 {{配色主题}} 主题；图内文字用 {{图内语言}}。
6. 图中任何数值，必须在图注或图内显式标注它是「示意值」还是「实测值」。
7. 每张图配 1–2 句图注，指出这张图最值得看的位置是哪里。
8. 输出带 viewBox、字体栈、背景底的完整 SVG，确保在浅色和深色主题下都能读。
```

---

## 3 · 单文件可交互 HTML

**变量**：`{{主题}}`、`{{区块数}}`、`{{主色}}`

```text
把 {{主题}} 做成一个单文件可交互 HTML 页面。

硬约束：
1. 单个 .html 文件，零外部依赖——不引用任何 CDN、外部字体、外链图片，
   离线双击即可打开。
2. 交互背后必须是真计算，不是预设动画。公式要真的在页面上跑。

结构要求：
3. 分成 {{区块数}} 个区块，每块一个明确的知识点，按「是什么 → 怎么变 → 为什么这样设计」
   递进排列。
4. 至少有一块可交互：用户能调输入（滑杆 / 点击选择）→ 页面实时重算 → 结果立刻变化。
5. 打开时的默认状态就要有信息量，不能是一屏空白等用户操作。

诚实性要求：
6. 页面上凡是引用了图表数字的说明文字，数字一律由运行时计算回填，不许写死——
   否则改了数据忘了改文案，图和话会互相打脸。
7. 页脚必须标注：本页数据是示例值还是真实值，真实值来自哪里。
8. 页面里出现的关键数值，交付时单独列给我（默认状态下的数值），方便我核对。

样式：主色 {{主色}}，中文字体栈，自适应宽度，跟随浅色主题。
```

---

## 4 · 讲解视频

**变量**：`{{主题}}`、`{{总时长}}`、`{{场景数}}`、`{{旁白语言/发音人}}`

```text
做一个 3Blue1Brown 风格的讲解视频，讲解 {{主题}}，总长 {{总时长}}。

顺序要求（重要）：
1. 先写旁白稿，按场景分段，每段 1–2 句。
2. 先合成旁白、量出每段的真实时长，再据此排画面的起止时间。
   时间轴是算出来的，不是先画后配出来的。

画面要求：
3. {{场景数}} 个场景，从「提出一个问题」开始，到「一句总结」结束；
   场景之间交叉淡入淡出。
4. 视觉风格：深色底、两三种克制的强调色、平滑缓动、逐层揭示
   （元素逐个出现，不要一次性铺满）。
5. 画面必须由确定性渲染函数生成——同一时刻永远渲染出同一帧，
   不依赖 CSS 动画或真实时钟。
6. 至少有一处「数值 / 权重 / 概率」的可视化，且画面上的数字要和旁白说的对得上。

配音：
7. 旁白语言 {{旁白语言}}，发音人 {{发音人}}。
   如果有 ElevenLabs API Key 就用它；没有就用本地算力的免费替代方案，
   并告诉我这一层是机器音还是拟真音。

交付前必须报告：
8. 从**成片**里抽帧核对，而不是只看渲染源帧。
9. 报告：总时长、分辨率、帧率、音轨是否存在、抽查了哪几个时间点。
10. 说明三件事：配音属机器音还是拟真音；哪些数据是示意值；音画同步有没有人工听过。
```

---

## 填空示例：同一主题走完四级

主题取 `RAG（检索增强生成）`：

| 级别 | 变量怎么填 | 产出 |
| --- | --- | --- |
| 1B | `{{TOPIC}}` = What is RAG<br>`{{OUTPUT LANGUAGE}}` = English | 短句、一词一义、无隐喻的受控语言解释，附自检表 |
| 2 | `{{主题}}` = RAG 的检索链路<br>`{{张数}}` = 3<br>`{{配色主题}}` = 浅色<br>`{{图内语言}}` = 中文 | 3 张递进图：链路全景 → 向量检索打分 → 检索结果如何进上下文；每步标数据形态 |
| 3 | `{{主题}}` = 向量相似度与 top-k 检索<br>`{{区块数}}` = 3<br>`{{主色}}` = 靛蓝 | 单文件网页：可拖动查询向量、调 k 值，实时看命中哪些文档块 |
| 4 | `{{主题}}` = RAG 为什么需要检索<br>`{{总时长}}` = 80 秒<br>`{{场景数}}` = 9<br>`{{旁白语言/发音人}}` = 中文 / Ting-Ting | 80 秒讲解视频，先录旁白再排画面，成片抽帧核对后交付 |

`{{场景数}}` 这类变量是**内容密度的探针**：填不出 8 个场景，说明概念撑不起视频，该退回二级。
