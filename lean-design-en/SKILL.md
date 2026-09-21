---
name: lean-design-en
description: Orchestration skill (user-invoked — start only on explicit user request, never auto-trigger). Lean design-first workflow: when the user asks to build/create/implement something and explicitly wants design alignment first — classify, batch-clarify, get one approval, then code. Triggers: design, spec, architecture, brainstorm, "let's build X", plan this.
invocation: user
---

# Lean Design — Design-First, Lightly

## Invocation tier

This is an **orchestration skill (user-invoked)**: start only when the user explicitly asks. If the task looks like a fit but the user hasn't named it, ask "want to run lean-design?" instead of auto-starting an interrogation. Orchestration skills may invoke discipline skills (lean-tdd-en / lean-debug-en / lean-review-en); discipline skills never invoke this one back.

Align before writing code. Two iron rules throughout:

1. **The approval gate fires once.** Present the design → user explicitly agrees → only then build. No second stop.
2. **Ceremony scales with the task; approval never scales.** A small task's design may be two sentences, but it must be confirmed.

## Step 1: Classify (announce first, user can override)

Before anything, classify the request and **say the classification out loud**:

- **Spike**: a feasibility question ("can we…", "let's try…"). The output is an answer, not code you keep. Say what you'll try in 2-3 sentences; a nod starts the probe. Label anything built as throwaway.
- **Bounded**: a change to a flow that **already exists in this repo** (a flag, a small endpoint, a one-file fix). If there is no existing flow to change, it is not bounded.
- **Architectural**: new projects, new subsystems, changes to interfaces others depend on.

When in doubt, take the heavier path. **The ratchet is one-way**: hidden complexity discovered mid-task means stop, announce, and step up. No downgrades.

## Step 2: Batch clarification (bounded & architectural)

**Domain question banks (optional)**: detect the project stack (`pom.xml`/`build.gradle` + k8s manifests or Spring deps → `references/k8s-spring.md`; vectorbt/pypfopt/akshare etc. → `references/quant.md`). On a hit, use the matching question bank as candidate frontier questions — pick what fits, don't ask everything.

Model the design as a **decision tree**: every decision branches into the decisions that hang off it. Each round, ask only the **frontier** — questions whose prerequisites are already settled. Rules:

- **Ask the whole frontier in one round.** Number each question and **attach your recommended answer** — the user's job is to judge your recommendation, not to invent answers from scratch.
- **Facts are yours to find; decisions are the user's.** Never ask the user anything you can look up (files, commands, docs). A pending lookup only blocks the questions downstream of it — ask the rest of the frontier now.
- After each round of answers, recompute the frontier. **Frontier empty = shared understanding reached.** No silently assumed branches allowed.

```
❓ Q1 - <title>: <question body, may include options>
➡️ Recommend: <your answer + one-line rationale>

❓ Q2 - …
➡️ Recommend: …
```

## Step 3: Present the design (one message)

Once the frontier is empty, present the complete design **in a single message**, scaled to the task:

- **Bounded**: a few sentences — which files change, the approach, how it gets verified.
- **Architectural**: short sections covering architecture, components, data flow, error handling, and testing; where multiple approaches are plausible, give 2-3 options with trade-offs and a clear recommendation (the user prefers numbered choices).

Then **stop and wait for approval**. Build only on an explicit yes; on objections, revise and re-present. Never present the design and start coding in the same breath.

## Step 4: Wrap up

- **Spike**: report findings (recommendation + evidence); label any code as throwaway.
- **Bounded**: after approval, proceed with the normal development workflow (tests first).
- **Architectural**: by default, skip the design document and start building; write one only when the user asks (or the project has a spec convention), to `docs/specs/YYYY-MM-DD-<topic>-design.md`, and commit it.

No forced handoff to any downstream workflow.

## Red Flags

| Thought | Reality |
|---------|---------|
| "Too simple to need a design" | Simple means a two-sentence design, not no design |
| "I'll start while they read the plan" | Presented ≠ approved. Stop |
| "Section-by-section approval is safer" | The gate fires once. One message, one approval |
| "Asking the user for this fact is fastest" | Look it up yourself. Users make decisions |
| "Close enough, we'll decide the rest as we go" | An unsettled frontier is misalignment. Finish the tree |
| "It grew, but we're almost done" | Stop, step up a path, say so |
