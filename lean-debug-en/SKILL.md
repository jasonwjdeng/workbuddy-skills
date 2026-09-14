---
name: lean-debug-en
description: Systematic debugging workflow. Use for any bug, test failure, build failure, unexpected behavior, or performance regression — build a red-capable feedback loop before proposing fixes. Triggers: debug, diagnose, fix this bug, why is this broken, failing test, performance regression.
---

# Lean Debug — Loop First, Fix Second

**Iron law: no fixes without root cause. Symptom fixes are failure.** Phases run in order; skipping one needs an explicit justification.

## Phase 0: Redaction

Before showing any command, output, or captured artifact, replace secrets with `<REDACTED>`. Loop scripts read credentials from env vars — never hardcode them into scripts or what you display. If redacted output is not enough to diagnose, say so and ask the user.

## Phase 1: Build a feedback loop (this is the skill)

**A tight loop that can go red on this bug makes the cause inevitable; without one, no amount of staring at code will save you.** Spend disproportionate effort here. Construction methods, in order:

1. Failing test at whatever seam reaches the bug (unit / integration / e2e)
2. Curl / HTTP script against a running dev server
3. CLI invocation with a fixture input, diffing stdout
4. Headless browser script driving the UI with assertions
5. Replay a captured request / payload / event log
6. Throwaway minimal harness (mocked deps, single function call)

**Tighten the loop**: faster (seconds)? Sharper signal (assert the exact symptom, not "didn't crash")? Deterministic (pin time, seed RNG, isolate filesystem)? Agent-runnable unattended?
**Non-deterministic bugs**: the goal is a higher reproduction rate — loop the trigger 100×, stress it, narrow timing windows. 50% reproducible is debuggable; 1% is not.
**Genuinely cannot build one**: stop, say so, list what you tried, and ask the user for one of: access to an environment that reproduces it, a redacted captured artifact (HAR / log dump / core dump / screen recording with timestamps), or permission for temporary production instrumentation. **No loop, no hypothesising.**

**Done when**: one command you have already run at least once (show the invocation and output, redacted) that is red-capable (asserts the user's exact symptom) + deterministic + seconds-fast + agent-runnable. Catch yourself reading code to build a theory before this command exists — **stop; that is the exact failure this skill prevents.**

## Phase 2: Reproduce + minimise

Run the loop. Watch it go red. Confirm the failure mode is the one the user described (fixing the wrong bug is worse than none). Then cut inputs, callers, config, and data one at a time, re-running after each cut, **until every remaining element is load-bearing** — removing any one makes the loop go green. The minimal repro becomes the regression test in Phase 5.

## Phase 3: Hypothesise

Generate **3-5 ranked, falsifiable hypotheses** — never a single anchoring guess. Each must state a prediction:

> Format: "If X is the cause, then changing Y will make the bug disappear / changing Z will make it worse."

No prediction = a vibe; discard or sharpen it. **Show the ranked list to the user once** (non-blocking): their domain knowledge often re-ranks instantly ("we just deployed a change to #3") or rules items out.

## Phase 4: Instrument

Every probe maps to a specific Phase 3 prediction. **Change one variable at a time.** Priority: debugger / REPL > targeted logs at hypothesis-distinguishing boundaries > never "log everything and grep". Tag every debug log with a unique prefix like `[DEBUG-a4f2]` — cleanup becomes one grep. **Performance branch**: logs are usually wrong — establish a baseline measurement (timing harness / profiler / query plan), then bisect. Measure first, fix second.

## Phase 5: Fix + regression test

**Write the regression test before the fix only if a correct seam exists** — one where the test exercises the real bug pattern as it occurs at the call site. Too-shallow seams (single-caller, broken chain) buy false confidence. **No correct seam is itself the finding**: the architecture prevents locking this bug down — record it and feed it back to the design workflow. With a seam: minimal repro → failing test → watch it go red → fix → watch it pass → **re-run the Phase 1 loop against the original, un-minimised scenario.**

## Phase 6: Cleanup (required before declaring done)

- [ ] Phase 1 loop re-run on the original scenario — no longer reproduces
- [ ] Regression test passes (or absence of seam documented)
- [ ] All `[DEBUG-...]` logs removed (grep the prefix)
- [ ] Throwaway prototypes deleted or moved to a clearly-marked debug location
- [ ] The confirmed hypothesis is stated in the commit message, so the next debugger learns

## Red Flags

| Thought | Reality |
|---------|---------|
| "I know what's wrong, just fix it" | That's a hypothesis. Build the red loop first |
| "Changed it, looks fine" | Run the loop on the original symptom. Symptom gone ≠ root cause found |
| "Log everything and grep" | One variable at a time, at hypothesis boundaries |
| "Can't reproduce, patch anyway" | No loop means stop and say so. Never guess a fix |
| "All tests are green" | Green ≠ red-capable. No loop, no debugging |
| "Fixed means done" | The cleanup checklist defines done |
