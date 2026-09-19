# Java / Spring Boot 测试参考

> lean-tdd 的技术栈补充。仅在检测到 Java/Spring 项目时加载。

## 检测标记

`pom.xml` / `build.gradle(.kts)` / `src/main/java` 存在 → 本参考生效。

## 测试分层与命名（遵循项目 AGENTS.md 优先）

- 每模块一个测试文件：`*ServiceTest`（单元，mock 外部服务）、`*IntegrationTest`（集成）
- 单元测试不用 Spring 上下文（纯 JUnit 5 + Mockito）；需要上下文时用**切片**而不是 `@SpringBootTest` 全量：`@WebMvcTest` / `@DataJpaTest` / `@JsonTest`

## RED 的写法

```java
@Test
void rejectsDuplicateNamespace() {
    var repo = mock(ConfigNamespaceRepository.class);
    when(repo.existsByName("payments")).thenReturn(true);
    var service = new NamespaceService(repo);

    assertThatThrownBy(() -> service.create("payments"))
        .isInstanceOf(DuplicateNamespaceException.class);
}
```

- 断言库用 AssertJ，不用 JUnit 原生 assertEquals 链
- 构造器注入直接 `new`，不为了测试引字段注入

## 常见坑（看红/看绿时重点怀疑）

| 症状 | 根因方向 |
|------|----------|
| 测试一写就绿 | 在测已有行为；或切片注解带进了真实 bean 而你想测的正是它 |
| 上下文启动 30s+ | 用了 `@SpringBootTest` 全量；换切片 |
| 集成测试 flaky | 数据库没隔离：Testcontainers 每类一个容器 + 每方法清表，别共享脏状态 |
| mock 没生效 | `@MockBean`（上下文内）vs `Mockito.mock()`（纯单元）用混 |
| JPA 相关断言失败 | `equals/hashCode` 没按业务键实现；懒加载在事务外触发 |

## 数据库与迁移

- Repository 层用 `@DataJpaTest` + Testcontainers PostgreSQL（不用 H2，方言差异会撒谎）
- Flyway 迁移脚本要有集成测试：空库 migrate → 断言关键表/约束存在
- 事务边界测试：默认每个测试方法回滚；要测"提交后可见"的行为时显式 `@Commit` 并清理

## 数值与精度

- 金额/配额用 `BigDecimal`，断言用 `isEqualByComparingTo`（忽略 scale）
- 时间相关测试注入 `Clock`，禁止 `LocalDateTime.now()` 散落代码中
