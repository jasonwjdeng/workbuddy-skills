# Java / Spring Boot diagnostics reference

> lean-debug stack supplement. Load when `pom.xml` / `build.gradle(.kts)` is detected.

## Feedback loop construction (Phase 1, stack-preferred order)

1. Failing test: unit / slice test (`@DataJpaTest` for the data-layer seam)
2. Curl against local actuator or business endpoints (`curl localhost:8080/actuator/health`)
3. Testcontainers minimal repro (real PG, single repository method)
4. CLI entry point + fixture data, diff the output

## Instrumentation points at hypothesis boundaries (Phase 4)

| Suspected direction | Tool | Key move |
|--------------------|------|----------|
| N+1 / SQL issues | `spring.jpa.show-sql` or datasource-proxy | Count SQL statements per request — don't read contents |
| Connection pool exhaustion | HikariCP metrics + `leakDetectionThreshold=30000` | Leak stack traces point straight at unclosed connections |
| Transaction boundaries | `[DEBUG-xxxx]` logs at method entry/exit | Verify actual boundaries under self-invocation / nesting |
| Cache hit rate | Micrometer cache metrics | Sudden hit-rate drop = invalidation-policy suspect |
| Startup failure | Read the FailureAnalyzer output in full | Circular deps / config binding errors are in the first block |

## JVM live state (production / in-container)

- **Threads**: `jstack <pid>` or `jcmd <pid> Thread.print` — deadlocks get their own section at the end
- **Heap**: `jcmd <pid> GC.heap_info` for a quick water level; dumps via `-XX:+HeapDumpOnOutOfMemoryError`
- **Live diagnosis**: Arthas (`dashboard` / `watch` / `trace`) — one watch beats ten log lines
- **GC logs**: Full GC frequency and pause time first, allocation rate second; never tune flags first

## OOM decision tree (identify which OOM first)

```
Container gone / restarting?
├─ Yes → kubectl describe, Last State Reason
│   ├─ OOMKilled → container over limit (heap + off-heap > limit) → check Xmx:limit ratio and off-heap (DirectBuffer / thread stacks / Metaspace)
│   └─ Error 1 + OutOfMemoryError in logs → JVM OOM → dominator tree in MAT
└─ No → alive but slow/unresponsive → GC death spiral (jcmd for GC overhead)
```

## PostgreSQL

- Slow query: `EXPLAIN (ANALYZE, BUFFERS)` — check estimated vs actual rows first (stale stats → ANALYZE)
- Global slow queries: `pg_stat_statements` ordered by mean_exec_time
- Locks: `pg_locks` + `pg_stat_activity` for blocking chains, `pg_blocking_pids()`
- Long transactions: `state = 'idle in transaction'` in pg_stat_activity is the classic connection-leak shape

## K8s layer

- CrashLoopBackOff: `kubectl logs --previous` for the dying container's last words
- Image/config issues: read `kubectl describe pod` Events bottom-up in time order
- Liveness-probe kills: slow startup (Flyway migrations, cache warm-up) gets probed before ready — use startupProbe instead of inflating liveness delays
- In-container debugging: `kubectl debug` ephemeral containers (the proper path for distroless images)
