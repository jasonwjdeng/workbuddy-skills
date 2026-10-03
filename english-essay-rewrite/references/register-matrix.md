# 语体对照矩阵（Formal Written vs Casual Spoken）

改写时逐维度过一遍。**同一句话可以在多个维度上同时调整**——这正是两个版本读起来"气质不同"的原因，而不是简单地加减几个词。

## 一、十二个语体维度

| # | 维度 | 正式书面语 | 自然口语 |
| --- | --- | --- | --- |
| 1 | 缩略形式 | 一律展开：I am / it is / there is / we have | 一律缩略：I'm / it's / there's / we've got |
| 2 | 人称视角 | 中性或第三人称，弱化"我"；用 the system / the application 作主语 | 第一人称在场，把说话人放进句子里：we use / we've got / my job is to |
| 3 | 动词选择 | 单字正式动词：comprise, employ, act as, serve as, release | 短语动词：be made up of, use, run on, ship as, get ... running |
| 4 | 名词化 | 把动作压成名词：configuration, deployment, the build and deployment | 保持动词形态，动作直说：we run it in a ... setup |
| 5 | 句长与从句 | 长句为主，用定语从句 / 分词短语焊接：the application on which I am working；operating in a ... configuration | 短句为主，用 and / so 并列推进，一事一句 |
| 6 | 连接方式 | 显性逻辑连接词：while, whereas, accordingly, thereby | 话语标记：so, and, basically, you know, like |
| 7 | 被动语态 | 系统作主语时用被动：is written in Java / is deployed as | 尽量主动，或换成不强调施动的动词：it ships as |
| 8 | 词汇层级 | 拉丁/法语词源：institution, introduce, responsible for, participate in | 日耳曼/本土词：big bank, talk about, in charge of, join |
| 9 | 缓和与强调 | 少用缓和语；靠句式与副词表达分寸（arguably, to some extent） | 缓和语高频：basically, a bit, kind of, pretty much, actually |
| 10 | 信息密度 | 高，一句可承载多层信息 | 低，一层信息一个短句，允许重复与自我补充 |
| 11 | 限定词准确性 | 冠词、物主代词完整：its application framework / the underlying database | 允许省略与含糊：as the framework |
| 12 | 术语外围表述 | 完整形式：on-premises, primary–secondary configuration, PostgreSQL | 业界口语缩写：on-prem, primary-secondary setup, Postgres |

## 二、本类习作的典型改写动作（以"介绍自己在做的系统"为例）

| 原稿 | 正式版做法 | 口语版做法 |
| --- | --- | --- |
| I am a software backend engineer and working in a global banking enterprise | 改正修饰语顺序与并列结构；升格为 at a global banking institution, where I am responsible for ... | 拆成两句完整小句：I'm a backend software engineer and I work at a big global bank |
| I am responsible for designing and developing wealth management system | 补冠词；保留 be responsible for + doing | My job is basically to design and build ... |
| Today I would like to talk about ... | introduce the application on which I am currently working | I want to talk a bit about the app I'm working on |
| This system is composed by tens of microservices | comprises dozens of microservices | is made up of dozens of microservices |
| running on a on-premise Kubernetes | runs on an on-premises Kubernetes cluster | runs on an on-prem Kubernetes cluster |
| It uses Spring Boot as application framework | employs Spring Boot as its application framework | We use Spring Boot as the framework |
| deploys as a Docker image | is released as a Docker image | it ships as a Docker image |
| There is an Azure DevOps pipeline to build and deploy | An Azure DevOps pipeline is responsible for building and deploying it | There's an Azure DevOps pipeline that builds and deploys it |
| Helm is the deployment tool | Helm serves as the deployment tool | Helm is what we use to do the deployment |
| PgSQL is the database. It is running in a primary and secondary mode. | 合并：PostgreSQL acts as the underlying database, operating in a primary–secondary configuration. | 合并：The database is Postgres, and we've got it running in a primary-secondary setup. |

## 三、反向检查：别把语体改过头

- **正式版不要变成官方文书**：避免 hereby / aforementioned / pursuant to 这类法律腔，除非用户明确要求公文风格。商务技术写作的"正式"是精确与克制，不是古板。
- **口语版不要变成俚语秀**：避免 gonna / ain't / dude 这类标记过强的俚语，除非用户要求口语方言化。自然口语的门槛是"母语者开会时真的会这么说"。
- **两个版本都要能朗读出口**：口语版尤其要过一遍"这句话我能在会议上说出来吗"。

## 四、可复用的语体转换句式

| 功能 | 正式 | 口语 |
| --- | --- | --- |
| 自我介绍 | I am a ... at ..., where I am responsible for ... | I'm a ..., and I work at ... My job is basically to ... |
| 引出话题 | Today, I would like to introduce / outline ... | Today I want to talk a bit about ... |
| 说明组成 | The system comprises / consists of ... | This thing is made up of ... |
| 说明运行环境 | It runs on an on-premises Kubernetes cluster | It runs on an on-prem Kubernetes cluster |
| 说明技术栈 | It is written in X, employs Y as its framework, and is released as Z | It's all written in X. We use Y as the framework, and it ships as Z |
| 说明工具链 | An X pipeline is responsible for ...ing, while Y serves as the ... tool | There's an X pipeline that ..., and Y is what we use to do ... |
| 说明数据层 | X acts as the underlying database, operating in a ... configuration | The database is X, and we've got it running in a ... setup |
