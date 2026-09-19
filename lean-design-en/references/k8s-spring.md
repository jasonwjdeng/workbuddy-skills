# K8s / Spring Boot service domain question bank

> lean-design domain supplement. When a K8s/Spring service project is detected (pom.xml/build.gradle + k8s manifests or Spring dependencies), use the following as candidate frontier questions during batch clarification — pick what fits the task; still attach your recommended answer to each.

## Consistency and write model

- Writer count: single writer or multi-writer? Which replica is authoritative? (Recommend: single writer + read-only replicas — smallest conflict surface)
- Consistency requirements: read-your-writes? Monotonic reads? Acceptable eventual-consistency window?
- Leader election: K8s Lease / DB leader_lease table / external coordinator? (Recommend: DB leader_lease — no new dependency)

## State and storage

- Stateful or stateless? State in DB / object storage / local disk? (Recommend: stateless where possible; large files in object storage + DB metadata)
- Migration strategy: Flyway versioned? Backwards-compatible (expand-then-contract)?
- Caching: needed at all? Invalidation policy? (Recommend: not yet — add only with performance evidence)

## Deployment and resilience

- Replica count and PDB? Rolling strategy (maxSurge/maxUnavailable)?
- Resource requests/limits: JVM heap vs container limit ratio? (Recommend: Xmx = 50-75% of limit, leave room for off-heap)
- Graceful shutdown: do preStop + terminationGracePeriodSeconds cover the longest request?
- Degradation and timeouts: timeout/retry/circuit-breaker budgets for downstream calls?

## Failure and operations

- Failure domains: impact of losing one AZ? Cross-DC requirements?
- OOM semantics: separate handling paths for OOMKilled vs JVM OOM? How are dumps preserved?
- On-call self-service: how complete are the logs/traces/metrics pillars?

## Security and auth

- Caller identity: K8s SA TokenReview / mTLS / gateway?
- Secrets management: mounted Secrets vs external secret store? Rotation policy?
- Egress policy: allowlist?

## Observability

- Metrics: RED (requests) or USE (resources)? What is the core SLO?
- Alert grading: what counts as P1? Who gets paged when?
