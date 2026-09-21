---
name: lean-implement-en
description: Orchestration skill (user-invoked — start only when the user brings a plan and explicitly asks to execute it, never auto-trigger). Plan execution workflow: review the plan critically, execute task by task with per-task verification, stop to ask instead of guessing when blocked. Triggers: implement the plan, start building, execute the plan, let's develop this.
invocation: user
---

# Lean Implement — Follow the Plan, Ask When Blocked

## Invocation tier

This is an **orchestration skill (user-invoked)**: start only when the user brings a plan/design and explicitly asks to execute it. It may invoke discipline skills (wrap-up must go through lean-review-en; coding goes through lean-tdd-en); discipline skills never invoke this one back.

**Opening line**: "I'm executing this plan with lean-implement."

## Iron rules

1. **No implementation on main/master** without the user's explicit consent.
2. **Raise plan concerns first — never start while doubting it.**
3. **When blocked, stop and ask. Never guess.** Guessed progress is rework.

## Step 1: Review the plan critically

- Read the plan/design end to end; find questions, gaps, and contradictions with current reality
- Concerns: list them for the user and **wait for answers before starting**
- No concerns: create one todo per task and begin

## Step 2: Execute task by task

For each task:

1. Mark it in_progress
2. **Follow the plan's steps exactly** — no improvising (if a step is wrong, that is a "stop and ask", not a workaround)
3. Run the verification the plan specifies
4. Verified → mark completed (**individually, never batch-complete at the end**)

Skipping a specified verification = task not done.

## Step 3: Wrap up

After all tasks complete and verify, enter the verification and review workflow (lean-review-en): run full verification for evidence, review the diff by severity, and only then talk about committing.

## When to stop and ask (not guess)

- Any blocker: missing dependency, failing test, unclear instruction
- The plan has fatal gaps that prevent starting
- Verification fails repeatedly
- The plan's direction itself needs rethinking

If the user updates the plan from your feedback → return to Step 1 and re-review. **Never force through a blocker.**

## Red Flags

| Thought | Reality |
|---------|---------|
| "Roughly get the plan, just start" | Ask first. Starting with doubts wastes work |
| "I can optimise this step away" | Follow it. Plan changes go through the user |
| "Mark everything at the end" | Mark individually. Batch completion hides mid-flight failures |
| "Skip the verification, the next step will test it" | Run the specified verification. Skipped = not done |
| "Faster to just edit on main" | Get consent first |
| "Blocked — let me route around it" | Stop and ask. Routing around a blocker buries a landmine |
