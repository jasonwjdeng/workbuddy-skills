---
name: lean-review-en
description: Verification before completion and pre-commit review. Use before claiming work is done/fixed/passing, before committing or creating a PR, or when accepting delegated work — run fresh verification first, then review the diff by severity. Triggers: review, verify, double-check, ready to commit, almost done, looks finished.
---

# Lean Review — Evidence Before Claims

**Iron law: no completion claims without fresh verification evidence.** Confidence ≠ evidence.

## The gate (before any completion-type claim)

```
1. IDENTIFY: which command proves this claim?
2. RUN: the full command, fresh (not last run's output)
3. READ: full output, exit code, failure counts
4. CHECK: does the output actually support the claim?
   — if not, report the real status with evidence
5. ONLY THEN: make the claim, with evidence
Skipping any step is lying, not verifying.
```

## Claims and their evidence

| Claim | Requires | Not sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | A previous run, "should pass" |
| Build succeeds | Build command: exit 0 | Linter clean (lint ≠ compilation) |
| Bug fixed | The original-symptom command now passes | Code changed (changed ≠ fixed) |
| Regression test works | Red-green cycle verified | Test passed once |
| Agent completed | Your own VCS diff inspection | Agent reports "success" |
| Requirements met | Line-by-line checklist against the spec | All tests green (green ≠ complete) |

**Regression test red-green loop**: write test → run (pass) → revert the fix → run (must FAIL) → restore the fix → run (pass). A "regression test" missing the middle steps is not trustworthy.

## Pre-commit review (before commit / PR)

Two axes against the **original requirement or design**, reported in one message, ordered by severity:

1. **Compliance**: does the diff faithfully implement the spec? Check line by line, report gaps.
2. **Quality**: violations of project conventions and common sense (error handling, security, naming, test coverage)?

Severity report: **Critical** (blocking — no commit until resolved) / **Major** (fix this round) / **Minor** (follow-up is fine). Report only real findings; never pad the list.

## When to apply (always)

Before any of: success/completion wording, expressions of satisfaction ("Done!", "Great!"), commit, push, PR creation, marking a task complete, or accepting delegated agent work. The rule covers exact phrases, paraphrases, and any implication of success.

## Red Flags

| Thought | Reality |
|---------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ compiler |
| "The agent said success" | Verify the diff independently |
| "Partial check is enough" | Partial proves nothing |
| "I'm tired, let's wrap up" | Exhaustion is not an exemption |
