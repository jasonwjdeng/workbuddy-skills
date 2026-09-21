---
name: lean-tdd-en
description: Discipline skill (model-invoked — applies automatically when the task fits). Test-driven development workflow: use when implementing any feature, fixing a bug, refactoring, or changing behavior — write a failing test before production code. Triggers: tdd, write tests, test first, implement, refactor.
invocation: model
---

# Lean TDD — Red First, Then Green

## Invocation tier

This is a **discipline skill (model-invoked)**: it applies automatically when the task fits — no explicit user request needed. It never launches orchestration skills (lean-design-en / lean-implement-en) on its own — when it finds a problem that needs a design decision (unclear requirements, forking approaches), it reports to the user and lets them decide whether to enter the design flow.

**Iron law: no production code without a failing test first.** Already wrote code? Delete it and start over — do not keep it "as reference", do not "adapt" it, do not look at it. Delete means delete.

## Stack detection (once, before starting)

Scan the project root for stack markers (`pom.xml`/`build.gradle` → Java; `pyproject.toml`/`requirements.txt` → Python). On a hit, read the matching stack reference under `references/` (e.g. `java-spring-boot.md`, `python-quant.md`) and apply its conventions. No marker matched → skip this step and use the generic rules only. **The project's AGENTS.md conventions take precedence over stack references.**

## The cycle

```
RED (failing test) → watch it fail → GREEN (minimal code) → watch it pass → REFACTOR (stay green) → next
```

### RED — write the failing test

One behavior at a time, a name that states intent, real code wherever possible (mocks only when external side effects are unavoidable). Write the assertion first.

### Watch it fail (mandatory, never skip)

Run the test and confirm:

- It **fails** (assertion failure), not errors (broken test)
- It fails because the feature is missing, not a typo
- **Passes immediately?** You're testing existing behavior — fix the test

### GREEN — minimal code

Write the simplest code that makes the test pass. No extra features, no drive-by refactors, no "improvements" (YAGNI).

### Watch it pass (mandatory)

The test passes + every other test still passes + pristine output (no errors, no warnings). If another test breaks, fix it now.

### REFACTOR — only after green

Remove duplication, improve names, extract helpers. Keep everything green, add no behavior. Then the next RED.

## Good-test principles

| Principle | Good | Bad |
|-----------|------|-----|
| Minimal | One behavior | "and" in the name — split it |
| Clear | Name describes behavior | `test('test1')` |
| Real behavior | Assert the code's output | Assert how many times a mock was called |

## Exceptions

Throwaway prototypes, generated code, and pure config files may skip TDD — **but ask the user first**. "Just this once" is a rationalization, not an exception.

## When stuck

| Problem | Solution |
|---------|----------|
| Don't know how to test | Write the API you wish existed, assertion first; still stuck, ask the user |
| Test too complicated | Design too complicated. Simplify the interface |
| Must mock everything | Too coupled. Use dependency injection |
| Huge setup | Extract helpers. Still complex? Simplify the design |

## Red Flags (each means: delete the code, start over)

| Thought | Reality |
|---------|---------|
| "Too simple to test" | Simple code breaks. The test takes 30 seconds |
| "I'll add tests after" | Tests written after pass immediately — proving nothing. You never watched them fail, so you never proved they can catch the bug |
| "Already manually tested" | Manual testing leaves no record, can't re-run, and drops edge cases under pressure |
| "Let me explore first" | Fine. Throw the exploration away, then TDD |
| "Deleting X hours is wasteful" | Sunk cost. The real choice: TDD rewrite (trusted) vs keeping it and bolting tests on (untrusted) |
| "Keep it as reference" | You'll adapt it — that's testing after. Delete means delete |
| "TDD is dogma, I'm pragmatic" | TDD IS the pragmatic path: catches bugs before commit, prevents regressions, makes refactors safe |

## Completion checklist

- [ ] Every new function/method has a test
- [ ] Each test was watched failing (for the right reason)
- [ ] Each implementation is the minimal code that passes
- [ ] All tests green, output pristine
- [ ] Edge cases and error paths covered

Can't check them all? You skipped TDD. Start over.
