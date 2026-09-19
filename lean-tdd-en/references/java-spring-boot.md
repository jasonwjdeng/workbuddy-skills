# Java / Spring Boot test reference

> lean-tdd stack supplement. Load only when a Java/Spring project is detected.

## Detection markers

`pom.xml` / `build.gradle(.kts)` / `src/main/java` present → this reference applies.

## Test layering and naming (project AGENTS.md wins)

- One test file per module: `*ServiceTest` (unit, external services mocked), `*IntegrationTest` (integration)
- Unit tests run without the Spring context (plain JUnit 5 + Mockito); when context is needed, use **slices**, not full `@SpringBootTest`: `@WebMvcTest` / `@DataJpaTest` / `@JsonTest`

## Writing the RED test

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

- AssertJ for assertions, not chained JUnit assertEquals
- Constructor injection — `new` directly; never introduce field injection for testability

## Common traps (prime suspects when watching red/green)

| Symptom | Likely root cause |
|---------|-------------------|
| Test green on first write | Testing existing behavior; or the slice brought in the real bean you meant to test |
| Context takes 30s+ to boot | Full `@SpringBootTest`; switch to a slice |
| Flaky integration tests | No DB isolation: one Testcontainers container per class + per-method cleanup; never shared dirty state |
| Mock not applying | `@MockBean` (inside context) vs `Mockito.mock()` (plain unit) mixed up |
| JPA assertion failures | `equals/hashCode` not on the business key; lazy loading triggered outside a transaction |

## Database and migrations

- Repository layer: `@DataJpaTest` + Testcontainers PostgreSQL (not H2 — dialect differences lie)
- Flyway migrations need an integration test: migrate an empty DB → assert key tables/constraints exist
- Transaction boundaries: tests roll back by default; for "visible after commit" behavior use explicit `@Commit` and clean up

## Numbers and precision

- Money/quotas in `BigDecimal`; assert with `isEqualByComparingTo` (ignores scale)
- Inject a `Clock` for time-dependent tests; no scattered `LocalDateTime.now()`
