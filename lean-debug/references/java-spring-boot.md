# Java / Spring Boot 诊断参考

> lean-debug 的技术栈补充。检测到 `pom.xml` / `build.gradle(.kts)` 时加载。

## 反馈回路构造（Phase 1，栈内优先序）

1. 失败测试：单测/切片测试（`@DataJpaTest` 打数据层接缝）
2. curl 打本地 actuator 或业务端点（`curl localhost:8080/actuator/health`）
3. Testcontainers 最小复现（起真实 PG，单 Repository 方法复现）
4. CLI/命令行入口 + fixture 数据，diff 输出

## 假设区分边界的插桩点（Phase 4）

| 怀疑方向 | 工具 | 关键动作 |
|---------|------|---------|
| N+1 / SQL 问题 | `spring.jpa.show-sql` 或 datasource-proxy | 数请求内 SQL 条数，不是看内容 |
| 连接池耗尽 | HikariCP metrics + `leakDetectionThreshold=30000` | 泄漏堆栈直接指到未关连接处 |
| 事务边界 | 在事务方法入口/出口打 `[DEBUG-xxxx]` 日志 | 验证自调用/嵌套事务实际边界 |
| 缓存命中率 | Micrometer cache metrics | 命中率突变 = 失效策略嫌疑 |
| 启动失败 | FailureAnalyzer 输出读完整 | 循环依赖/配置绑定错误就在第一段 |

## JVM 现场（线上/容器内）

- **线程**：`jstack <pid>` 或 `jcmd <pid> Thread.print`——死锁在末尾有专门段
- **堆**：`jcmd <pid> GC.heap_info` 快速看水位；dump 用 `-XX:+HeapDumpOnOutOfMemoryError`
- **在线诊断**：Arthas（`dashboard` / `watch` / `trace`）——一个 watch 顶十条日志
- **GC 日志**：先看 Full GC 频率与耗时，再看分配速率，不要上来就调参

## OOM 决策树（先分清是哪种）

```
容器消失/重启？
├─ 是 → kubectl describe 看 Last State Reason
│   ├─ OOMKilled → 容器内存超限（堆+堆外 > limit）→ 查 Xmx 与 limit 比例、堆外（DirectBuffer/线程栈/Metaspace）
│   └─ Error 1 + 日志 OutOfMemoryError → JVM OOM → dump 分析支配树（MAT dominator tree）
└─ 否 → 应用还活着但慢/无响应 → GC 死亡螺旋（jcmd 看 GC overhead）
```

## PostgreSQL

- 慢查询：`EXPLAIN (ANALYZE, BUFFERS)`，先看 rows 估计 vs 实际的偏差（统计信息过期 → ANALYZE）
- 全局慢查：`pg_stat_statements` 按 mean_exec_time 排序
- 锁：`pg_locks` + `pg_stat_activity` 找 blocking 链，`pg_blocking_pids()`
- 长事务：`pg_stat_activity` 里 `state = 'idle in transaction'` 是连接泄漏的常见形态

## K8s 层

- CrashLoopBackOff：`kubectl logs --previous` 看上一个容器的临终日志
- 镜像/配置类：`kubectl describe pod` 的 Events 段按时间从下往上读
- 存活探针误杀：启动慢（Flyway 迁移/懒加载缓存）时探针先于就绪——用 startupProbe 而不是调大 liveness 延迟
- 在线进容器：`kubectl debug` ephemeral container（发行版无 shell 时的正路）
