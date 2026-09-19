# K8s / Spring Boot 服务领域问题库

> lean-design 的领域补充。检测到 K8s/Spring 服务端项目（pom.xml/build.gradle + k8s 清单或 Spring 依赖）时，把下列问题作为批量澄清的候选前沿——按任务选用；每题仍附你的推荐答案。

## 一致性与写模型

- 写者数量：单写者还是多写者？谁是权威副本？（推荐：单写者 + 其余只读副本，冲突面最小）
- 一致性要求：读己之写？单调读？最终一致可接受窗口？
- 选主方式：K8s Lease / DB leader_lease 表 / 外部协调？（推荐：DB leader_lease——不引入新依赖）

## 状态与存储

- 有状态还是无状态？状态放 DB / 对象存储 / 本地盘？（推荐：能无状态就无状态；大文件对象存储 + DB 元数据）
- 迁移策略：Flyway 版本化？向后兼容（expand-then-contract）？
- 缓存：要不要？失效策略？（推荐：先不要，性能证据驱动再加）

## 部署与弹性

- 副本数与 PDB？滚动策略（maxSurge/maxUnavailable）？
- 资源 requests/limits：JVM 堆与容器 limit 的比例？（推荐：Xmx = limit 的 50-75%，留堆外）
- 优雅停机：preStop + terminationGracePeriodSeconds 够不够覆盖最长请求？
- 降级与超时：下游调用的超时/重试/熔断预算？

## 故障与运维

- 故障域：单 AZ 挂掉的影响？跨 DC 需求？
- OOM 语义：OOMKilled 与 JVM OOM 的处置路径分别是什么？dump 怎么留存？
- 值班能自助吗：日志/trace/metrics 三支柱覆盖到哪个程度？

## 安全与鉴权

- 调用方身份：K8s SA TokenReview / mTLS / 网关？
- 密钥管理：Secret 挂载 vs 外部密钥服务？轮换策略？
- 出网策略：egress 白名单？

## 可观测性

- 指标：RED（请求）还是 USE（资源）？核心 SLO 是什么？
- 告警分级：什么算 P1？谁在什么时间收到？
