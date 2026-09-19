# Java / Spring Boot 评审清单

> lean-review 的技术栈补充。检测到 `pom.xml` / `build.gradle(.kts)` 时加载。
> 按严重度预分级：⚠️ = 通常 Critical，◆ = 通常 Major，· = Minor。

## JPA / 数据层

- ⚠️ `@Transactional` 自调用失效（同类内部调用绕过代理）
- ⚠️ 事务方法内做了远程调用/慢 IO（长事务占连接）
- ◆ 懒加载在事务外触发（`LazyInitializationException` 或 silently 在视图层打开 session）
- ◆ N+1：循环里查库/访问懒加载关联，应 join fetch 或批量查询
- ◆ 实体 `equals/hashCode` 用可变字段或未按业务键实现（进 Set/Map 就出错）
- ◆ 迁移脚本无回滚路径/不向后兼容（先加后删两阶段？）；大表 DDL 没考虑锁
- · 该 `readOnly = true` 的查询事务没标

## Web / API

- ⚠️ 输入未校验直接进 SQL/JPQL 拼接（一律参数化）
- ⚠️ 接口破坏性变更没版本化（删字段、改语义、改错误码）
- ◆ 错误处理把内部异常栈/敏感信息泄给客户端
- ◆ 分页缺失或无上限（`List<X>` 全量返回）
- · 幂等性：重试安全的写接口有没有去重键

## 数值 / 时间

- ⚠️ 金额用 `double`/`float`（必须 BigDecimal）
- ◆ `LocalDateTime.now()` 散落各处无法测试；时区假设隐式（应 UTC + 显式 ZoneId）
- · 除法未处理除零/未定义舍入模式

## 并发 / 资源

- ⚠️ 共享可变状态无同步（单例 bean 里的实例字段）
- ◆ 线程池无界队列/无拒绝策略；连接池耗尽路径没测
- ◆ 锁粒度：`synchronized` 包住 IO；乐观锁重试缺失

## 测试

- ◆ 新代码路径无对应测试（对照 lean-tdd 完成清单）
- ◆ 集成测试共享脏状态（无隔离清表）
- · mock 断言替代了真实行为断言
