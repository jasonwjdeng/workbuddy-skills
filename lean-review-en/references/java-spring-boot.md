# Java / Spring Boot review checklist

> lean-review stack supplement. Load when `pom.xml` / `build.gradle(.kts)` is detected.
> Pre-graded severity: ⚠️ = usually Critical, ◆ = usually Major, · = Minor.

## JPA / data layer

- ⚠️ `@Transactional` self-invocation (intra-class call bypasses the proxy)
- ⚠️ Remote calls / slow IO inside a transactional method (long transactions hold connections)
- ◆ Lazy loading triggered outside a transaction (`LazyInitializationException`, or an open-session-in-view silently papering over it)
- ◆ N+1: queries or lazy associations inside loops — use join fetch or batch queries
- ◆ Entity `equals/hashCode` on mutable fields or not on the business key (breaks in Set/Map)
- ◆ Migration without a rollback path / not backwards-compatible (expand-then-contract?); large-table DDL without lock analysis
- · Missing `readOnly = true` on query-only transactions

## Web / API

- ⚠️ Unvalidated input reaching SQL/JPQL concatenation (always parameterized)
- ⚠️ Breaking API change without versioning (removed fields, changed semantics, changed error codes)
- ◆ Error handling leaking internal stack traces / sensitive data to clients
- ◆ Missing or unbounded pagination (`List<X>` full-table responses)
- · Idempotency: do retry-safe write endpoints have dedup keys?

## Numbers / time

- ⚠️ Money in `double`/`float` (must be BigDecimal)
- ◆ Scattered `LocalDateTime.now()` making code untestable; implicit timezone assumptions (should be UTC + explicit ZoneId)
- · Division without zero-guard / undefined rounding mode

## Concurrency / resources

- ⚠️ Shared mutable state without synchronization (instance fields on singleton beans)
- ◆ Unbounded thread-pool queues / no rejection policy; untested connection-pool exhaustion
- ◆ Lock granularity: `synchronized` wrapping IO; missing optimistic-lock retry

## Tests

- ◆ New code paths without tests (cross-check the lean-tdd completion checklist)
- ◆ Integration tests sharing dirty state (no isolation/cleanup)
- · Mock-call assertions substituting for real behavior assertions
