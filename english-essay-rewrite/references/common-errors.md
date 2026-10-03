# 中文母语者写英语的高频错误清单

诊断时对照扫描。每条给出错误形式、正确形式与一句话机制说明——**机制说明是必须写进"修改理由说明"里的部分**，只给正确答案对学习者没用。

## 一、冠词（最高频失分区）

| 错误 | 正确 | 机制 |
| --- | --- | --- |
| designing wealth management system | designing **a/the** wealth management system | 可数名词单数在英语中必须有限定词，中文没有冠词，靠语感察觉不到 |
| a on-premise Kubernetes | **an** on-premises Kubernetes cluster | 冠词看**音素**不看字母：on 以元音音素开头用 an；且 on-premises 作定语用复数形式 |
| I am backend engineer | I am **a** backend engineer | 职业前必须加不定冠词 |
| He is responsible for develop system | for **developing a** system | 介词后接动名词；且 system 需冠词 |
| in the last year（想说"去年"） | **last year** | 表示"去年"不加 the；in the last year = 在过去一年里 |

## 二、介词与动词搭配

| 错误 | 正确 | 机制 |
| --- | --- | --- |
| be composed **by** tens of microservices | **comprise** / be composed **of** / consist **of** | compose 表"由…构成"时只接 of；by 用于施动者 |
| be responsible **to do** sth | be responsible **for doing** sth | 表"负责某事"用 for + 动名词 |
| discuss **about** the issue | discuss the issue | discuss 是及物动词，不加 about |
| contact **with** me | contact me | 同上 |
| depend **of** | depend **on** | 固定搭配 |
| It uses Spring Boot **as application framework** | as **its** application framework | 单数可数名词前需限定词 |

## 三、数量与程度表达

| 错误 | 正确 | 机制 |
| --- | --- | --- |
| **tens of** microservices | **dozens of** microservices | tens of 只用于 tens of thousands 这类大数；"几十个"用 dozens of |
| **several** dozens of | **several dozen** / dozens of | dozen 前有数词时用单数 |
| I **very like** it | I **like it very much** / I really like it | very 不能直接修饰动词 |
| **most of** people | **most** people | 泛指时不加 of |

## 四、并列结构与句子完整性

| 错误 | 正确 | 机制 |
| --- | --- | --- |
| I am a backend engineer **and working** at ... | I am a backend engineer **and I work** at ... | 并列项必须同形：be 动词不能与现在分词并列（或改成 and work，需与 am 语义匹配） |
| The system is fast, it is reliable. | The system is fast **and** reliable. / 用分号或连词 | 逗号拼接句（comma splice），英语两个独立句不能只用逗号连接 |
| Because it is on-prem, so it is secure. | Because it is on-prem, it is secure. | 中文"因为…所以…"成对，英语 because 与 so 不同时出现 |
| Although ..., but ... | Although ..., ... | 同上，although 与 but 不同时出现 |

## 五、逻辑主被动错位（技术写作高发）

| 错误 | 正确 | 机制 |
| --- | --- | --- |
| The system **deploys** as a Docker image. | The system **is deployed / is released** as a Docker image. | 系统不会主动部署自己；施动者是人或流水线 |
| The application **builds** by the pipeline. | The application **is built** by the pipeline. | 被动语态用 be + 过去分词，不是动词原形 + by |
| The service **runs** the cluster. | The service **runs on** the cluster. | run 及物/不及物含义不同：run sth = 运行某物；run on sth = 运行于某平台 |
| We design and developing the system. | We design and **develop** the system. | 并列动词形式一致 |

## 六、修饰语顺序与中式直译

| 错误 | 正确 | 机制 |
| --- | --- | --- |
| a **software backend** engineer | a **backend software** engineer | 英语修饰语顺序：领域泛称在前、具体职能在后；也常用 backend engineer |
| There are many information. | There **is much/a lot of** information. | information 不可数 |
| I have **many knowledges**. | I have **a lot of knowledge**. | knowledge 不可数 |
| open the light | **turn on** the light | 中文"开"对应多个英语动词，需按对象选词 |
| He plays phone. | He **is on his phone** / **uses his phone**. | play 只用于 play games / play the piano 等 |
| Please **colleague with** me（想说"配合"） | Please **coordinate with** me / **work with** me | 逐字对译造成的生造动词 |

## 七、术语与技术专名（技术类习作专项）

| 项 | 规范写法 | 说明 |
| --- | --- | --- |
| PostgreSQL | 正式写作写全称，口语可说 Postgres；PgSQL 是缩写但不正式 | 正式文档避免口语缩写 |
| Kubernetes / Docker / Java / Helm / Spring Boot | 专名首字母大写，不改写、不翻译 | 产品名是专有名词 |
| on-premises | 形容词用复数形式 on-premises；口语缩写 on-prem | 美式偶见 on-premise，但规范为 on-premises |
| microservices | 泛指用复数 microservices；作定语可写 microservice architecture | |
| CI/CD pipeline | 首次出现给全称 continuous integration / continuous delivery | |

## 八、时态与语态一致性（快速自查）

过一遍全文，问三个问题：

1. 描述系统的客观属性（用什么语言写的、跑在什么上）——**现在时**。
2. 描述已完成的构建与部署链路——**现在时被动**（is deployed）或**一般现在时**（the pipeline deploys it）。
3. 段落内时态是否突然跳变？中文无形态变化，英语时必须逐句校验。
